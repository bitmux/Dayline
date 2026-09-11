"""Fetching the day and keeping it current."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import labels
from . import tags as tagging
from .travel import Travel
from .const import (
    CONF_CALENDARS,
    CONF_TODO,
    CONF_WEATHER,
    DEFAULT_ALARM_HORIZON,
    DEFAULT_TOMORROW,
    DEFAULT_TOMORROW_HORIZON,
    DEFAULT_MIN_GAP,
    DEFAULT_LEAVE_BUFFER,
    DEFAULT_LEAVE_MAX,
    DEFAULT_LEAVE_ORIGIN,
    DEFAULT_LEAVE_REGION,
    DEFAULT_LEAVE_VEHICLE,
    DEFAULT_RECENT_MAX,
    DEFAULT_RECENT_TTL,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_SIMILARITY,
    DEFAULT_TITLE_NOISE,
    DOMAIN,
    EVENT_AUTOMATION_TRIGGERED,
    EVENT_SCRIPT_STARTED,
    EVENT_TAG,
    HOUSE_CONTEXT_MAX,
    HOUSE_CONTEXT_TTL,
    LABEL_CONTROL,
    LABEL_INCLUDE,
    OPT_LABEL,
    OPT_ALARMS,
    OPT_ALARM_HORIZON,
    OPT_ALARM_PACKAGES,
    OPT_TOMORROW,
    OPT_TOMORROW_HORIZON,
    OPT_MIN_GAP,
    OPT_CALENDAR_META,
    OPT_EXCLUDE,
    OPT_HEADLINE_TEMPLATE,
    OPT_LEAVE_BUFFER,
    OPT_LEAVE_BY,
    OPT_LEAVE_MAX,
    OPT_LEAVE_ORIGIN,
    OPT_LEAVE_REGION,
    OPT_LEAVE_VEHICLE,
    OPT_NOW_TEMPLATE,
    OPT_RECENT,
    OPT_RECENT_MAX,
    OPT_RECENT_TTL,
    OPT_SCAN_MINUTES,
    OPT_SENTENCES,
    OPT_SHOW_SUN,
    OPT_SIMILARITY,
    OPT_SUN_PRIORITY,
    OPT_TITLE_NOISE,
)
from .merge import (
    Entry,
    MergeConfig,
    attach_leave_by,
    attach_weather,
    briefing,
    dedupe,
    departure,
    from_alarms,
    from_gaps,
    from_calendars,
    from_sun,
    from_todo,
    remaining_count,
    tags_seen,
    travel_targets,
)

_LOGGER = logging.getLogger(__name__)

UNAVAILABLE = ("unavailable", "unknown")


class DaySpineCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Builds the payload the card reads.

    Two update paths, on purpose. The slow one polls calendars every few
    minutes. The fast one fires when a watched entity changes, and recomposes
    from the cached calendar data rather than re-fetching — a light turning off
    should reach the card immediately without costing a Google API call.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._base: list[Entry] = []
        self._recent: list[Entry] = []
        self._unsub_states = None
        self._unsub_alarms = None
        self._unsub_registries = None
        self._unsub_house: list[Callable[[], None]] = []

        # Context ids of automations and scripts currently running, and the
        # name of each. A state change carrying one of these was the house
        # acting, and we can say which automation did it.
        self._house_ctx: dict[str, tuple[float, str]] = {}

        # Resolved from labels, refreshed whenever a registry moves.
        self._calendar_ids: list[str] = []
        self._calendar_source = "all"
        self._watched_ids: list[str] = []
        self._control: set[str] = set()

        # Which tags have already fired today, and the timers for the ones that
        # have not. Persisted, because "fires once" has to survive a restart —
        # otherwise every reload re-asserts this morning's `#Away`.
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.tags")
        self._fired: set[str] = set()
        self._fired_day = ""
        self._unsub_fires: list[Callable[[], None]] = []

        # Rows pushed in by `day_spine.show`. Persisted, because a row an
        # automation put there is a claim about the house that a restart does
        # not make untrue — and losing it silently is worse than the row itself
        # ever was.
        self._rows_store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.rows")
        self._pushed: list[Entry] = []

        # Journeys, and the cache of what they cost. See travel.py.
        self._travel = Travel(hass)
        self._travel_origin = ""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(OPT_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
            ),
        )

    # -- what the labels resolved to ----------------------------------------
    #
    # Read by the options flow's status page. Exposed rather than reached for,
    # because that page's whole job is to report these accurately.

    @property
    def calendar_ids(self) -> list[str]:
        """Calendars on the spine."""
        return list(self._calendar_ids)

    @property
    def calendar_source(self) -> str:
        """How that list was arrived at: `label`, `config` or `all`."""
        return self._calendar_source

    @property
    def control_ids(self) -> list[str]:
        """Calendars whose `#tags` may act. Default deny: everything else shows
        its tags and fires nothing."""
        return sorted(self._control)

    @property
    def watched_ids(self) -> list[str]:
        """Non-calendar entities labelled for explanation."""
        return list(self._watched_ids)

    # -- options ------------------------------------------------------------

    @property
    def _opts(self) -> dict[str, Any]:
        return self.entry.options

    def _friendly(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return str((state.attributes.get("friendly_name") if state else None) or entity_id)

    def _meta(self) -> dict[str, dict[str, Any]]:
        """Per-calendar wording and priority, in the order the merge should see.

        Configured order comes first, because it decides whose phrasing wins a
        dedupe and that is the one thing a label cannot express. Everything the
        label turned up follows, alphabetically. A calendar nobody has ever
        configured still gets a pill — its own name, which is the name the
        person who labelled it was looking at.
        """
        configured = self._opts.get(OPT_CALENDAR_META) or {}
        order = [e for e in self.entry.data.get(CONF_CALENDARS, []) if e in self._calendar_ids]
        order += [e for e in self._calendar_ids if e not in order]

        out: dict[str, dict[str, Any]] = {}
        for entity_id in order:
            conf = dict(configured.get(entity_id) or {})
            if not conf.get("label"):
                conf["label"] = self._friendly(entity_id)
            out[entity_id] = conf
        return out

    def _merge_config(self) -> MergeConfig:
        return MergeConfig(
            calendar_meta=self._meta(),
            sentences=self._opts.get(OPT_SENTENCES) or [],
            exclude=self._opts.get(OPT_EXCLUDE) or [],
            show_sun=self._opts.get(OPT_SHOW_SUN, True),
            sun_priority=self._opts.get(OPT_SUN_PRIORITY, "low"),
            similarity=float(self._opts.get(OPT_SIMILARITY, DEFAULT_SIMILARITY)),
            title_noise=self._opts.get(OPT_TITLE_NOISE) or DEFAULT_TITLE_NOISE,
            todo_entity=self.entry.data.get(CONF_TODO),
            leave_buffer=int(self._opts.get(OPT_LEAVE_BUFFER, DEFAULT_LEAVE_BUFFER)),
            leave_max=int(self._opts.get(OPT_LEAVE_MAX, DEFAULT_LEAVE_MAX)),
            alarm_horizon=int(self._opts.get(OPT_ALARM_HORIZON, DEFAULT_ALARM_HORIZON)),
            alarm_packages=self._opts.get(OPT_ALARM_PACKAGES) or [],
            tomorrow_horizon=int(
                self._opts.get(OPT_TOMORROW_HORIZON, DEFAULT_TOMORROW_HORIZON)
            ),
            min_gap=int(self._opts.get(OPT_MIN_GAP, DEFAULT_MIN_GAP)),
        )

    # -- the fast path ------------------------------------------------------

    async def async_setup(self) -> None:
        """Resolve the labels, remember what has already fired, start watching."""
        await self._load_fired()
        await self._load_pushed()
        self._resolve()
        self._resubscribe()
        self._unsub_registries = labels.async_track_registries(
            self.hass, self._on_registry_change
        )
        self._unsub_house = [
            self.hass.bus.async_listen(event, self._on_house_action)
            for event in (EVENT_AUTOMATION_TRIGGERED, EVENT_SCRIPT_STARTED)
        ]
        self.entry.async_on_unload(self._teardown)

    @callback
    def _teardown(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        if self._unsub_alarms:
            self._unsub_alarms()
            self._unsub_alarms = None
        if self._unsub_registries:
            self._unsub_registries()
            self._unsub_registries = None
        for unsub in self._unsub_house:
            unsub()
        self._unsub_house = []
        self._cancel_fires()

    @property
    def label_include(self) -> str:
        """The label this spine answers to. `Dayline` unless someone said otherwise."""
        return str(self._opts.get(OPT_LABEL) or LABEL_INCLUDE).strip() or LABEL_INCLUDE

    @property
    def label_control(self) -> str:
        """Derived, never configured separately.

        Two free-text boxes where one would do is two chances to typo a label
        into silence, and the pair has to stay legible in a label list anyway:
        `Wife` and `Wife Control` read as a set, `Wife` and `Partner tags` do
        not. The default pair comes out as `Dayline` / `Dayline Control`, which
        is what it has always been.
        """
        include = self.label_include
        return LABEL_CONTROL if include == LABEL_INCLUDE else f"{include} Control"

    @callback
    def _resolve(self) -> None:
        """Work out what we are watching, from labels first.

        A calendar carrying the `Dayline` label is on the spine. With no such
        label anywhere, fall back to whatever the config flow was told, and
        failing that to every calendar in the instance — a first run should
        render a day, not interrogate you about one.

        The same label on anything that is not a calendar means the opposite
        direction: explain that entity when it changes on its own.
        """
        include = self.label_include
        labelled = labels.resolve(self.hass, include, "calendar")
        configured = list(self.entry.data.get(CONF_CALENDARS) or [])
        if labelled:
            self._calendar_ids, self._calendar_source = labelled, "label"
        elif configured:
            self._calendar_ids, self._calendar_source = configured, "config"
        else:
            self._calendar_ids = sorted(
                state.entity_id for state in self.hass.states.async_all("calendar")
            )
            self._calendar_source = "all"

        self._watched_ids = [
            entity_id
            for entity_id in labels.resolve(self.hass, include)
            if not entity_id.startswith("calendar.")
        ]
        self._control = set(labels.resolve(self.hass, self.label_control, "calendar"))

    @callback
    def _snapshot(self) -> tuple:
        return (
            tuple(self._calendar_ids),
            tuple(self._watched_ids),
            tuple(sorted(self._control)),
            self.label_include,
        )

    @callback
    def _on_registry_change(self) -> None:
        """A label was applied, removed or renamed somewhere.

        Registries move for all sorts of reasons that are none of our business,
        so re-derive and compare before doing anything — the point of this is
        that a calendar labelled this afternoon appears without a restart, not
        that renaming a light rebuilds the day.
        """
        before = self._snapshot()
        self._resolve()
        if self._snapshot() == before:
            return
        self._resubscribe()
        self.hass.async_create_task(self.async_refresh())

    @callback
    def _resubscribe(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        watched = [
            rule["entity_id"]
            for rule in (self._opts.get(OPT_RECENT) or [])
            if rule.get("entity_id")
        ]
        watched += self._watched_ids
        if watched:
            self._unsub_states = async_track_state_change_event(
                self.hass, list(dict.fromkeys(watched)), self._on_state_change
            )

        # Alarms get their own subscription rather than joining the list above:
        # that one feeds the "what just happened" lines, which need a phrase and
        # a house context an alarm sensor will never have. This one only wants
        # to know the value moved. Without it, setting an alarm at 10:50pm and
        # looking at the panel shows the old answer until the next cycle, which
        # reads as the card being broken.
        if self._unsub_alarms:
            self._unsub_alarms()
            self._unsub_alarms = None
        alarms = [e for e in (self._opts.get(OPT_ALARMS) or []) if e]
        if alarms:
            self._unsub_alarms = async_track_state_change_event(
                self.hass, list(dict.fromkeys(alarms)), self._on_alarm_change
            )

    @callback
    def _on_alarm_change(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is not None and old is not None and new.state == old.state:
            return
        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _on_house_action(self, event: Event) -> None:
        """Remember that an automation or script is running, and its name.

        This is how the logbook attributes a change, and it is the only thing
        that works. An automation on a *state* trigger inherits a parent
        context from whatever changed; one on a time, sun, template or MQTT
        trigger starts a fresh context with no parent, and its state changes
        are indistinguishable from a hand on a wall switch. Which meant the
        automations most worth explaining were the ones we said nothing about.
        """
        name = str(event.data.get("name") or "").strip()
        now = self.hass.loop.time()
        if len(self._house_ctx) >= HOUSE_CONTEXT_MAX:
            self._house_ctx = {
                ctx: seen for ctx, seen in self._house_ctx.items() if seen[0] > now
            }
            if len(self._house_ctx) >= HOUSE_CONTEXT_MAX:
                self._house_ctx.pop(next(iter(self._house_ctx)), None)
        self._house_ctx[event.context.id] = (now + HOUSE_CONTEXT_TTL, name)

    @callback
    def _house_actor(self, event: Event) -> tuple[bool, str | None]:
        """Did the house do this, and can we name what did it?

        Returns `(house_acted, name)`. A change carrying a user id was asked
        for by a person, and a person does not need telling what they just did.
        """
        context = event.data["new_state"].context
        if context.user_id is not None:
            return False, None

        now = self.hass.loop.time()
        for ctx in (context.id, context.parent_id):
            if ctx is None:
                continue
            seen = self._house_ctx.get(ctx)
            if seen is None:
                continue
            if seen[0] <= now:
                self._house_ctx.pop(ctx, None)
                continue
            return True, seen[1] or None

        # Downstream of *something* — an automation whose run we missed, or a
        # chain we cannot follow. Worth a line, without a name on it.
        return context.parent_id is not None, None

    @callback
    def _on_state_change(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None or old is None or new.state == old.state:
            return

        house, actor = self._house_actor(event)
        if not house:
            return

        phrase = self._phrase(event.data["entity_id"], new.state)
        if not phrase:
            return

        now = dt_util.now()
        ttl = int(self._opts.get(OPT_RECENT_TTL, DEFAULT_RECENT_TTL))
        self._recent.append(
            {
                "id": f"evt:{event.data['entity_id']}:{now.timestamp():.0f}",
                "start": now.isoformat(),
                "end": None,
                "expires": (now + timedelta(seconds=ttl)).isoformat(),
                "all_day": False,
                "kind": "event",
                "source": "House",
                "title": phrase,
                "automation": actor,
                "entity_id": event.data["entity_id"],
            }
        )
        self.async_set_updated_data(self._compose())

    def _phrase(self, entity_id: str, state: str) -> str | None:
        """What to say about a change nobody made by hand.

        A written rule wins, because someone chose those words. A labelled
        entity with no rule still gets a line — the entity's own name and what
        it did. Plainer than a person would write, and enormously better than
        the silence that made them go looking in the logbook.
        """
        for rule in self._opts.get(OPT_RECENT) or []:
            if rule.get("entity_id") == entity_id and rule.get("state") == state:
                return rule.get("phrase")
        if entity_id not in self._watched_ids:
            return None
        name = self._friendly(entity_id)
        if state in ("on", "off"):
            return f"{name} turned {state}"
        return f"{name} changed to {state}"

    def _log_fetch_failure(self, what: str) -> None:
        """A failed fetch while Home Assistant is still starting is an ordering
        detail, not a fault — the calendar or to-do integration simply is not up
        yet, and async_at_started asks again. Only shout once it should work."""
        if self.hass.state is CoreState.running:
            _LOGGER.exception("%s failed", what)
        else:
            _LOGGER.debug("%s not available yet during startup", what)

    def _present(self, entity_ids: list[str], what: str) -> list[str]:
        """The subset the state machine actually knows about.

        Asking a response service for an entity that has not been created yet
        makes `homeassistant.helpers.service` log "Referenced entities ... are
        missing or not currently available" — and it logs it before raising, so
        catching the error does not suppress it. On a cold boot that puts three
        lines at the top of the log naming the user's own calendars, which reads
        like a misconfiguration and is only an ordering detail; async_at_started
        asks again a moment later and the spine fills in.

        An entity that exists but is unavailable still has a state object, so
        this only ever filters out what genuinely is not there yet. Once
        everything has started, a name that is still missing is a real problem
        and says so.
        """
        missing = [e for e in entity_ids if self.hass.states.get(e) is None]
        if missing:
            names = ", ".join(missing)
            if self.hass.state is CoreState.running:
                _LOGGER.warning("%s: %s does not exist", what, names)
            else:
                _LOGGER.debug("%s: %s has not started yet", what, names)
        return [e for e in entity_ids if e not in missing]

    # -- the slow path ------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        cfg = self._merge_config()
        now = dt_util.now()
        day_start = dt_util.start_of_local_day(now)

        # Fetching a second day is what lets the evening say when tomorrow
        # starts. The extra events are held back by `when_empty` until today is
        # spent, so nothing changes about a day that still has something in it.
        pivot = bool(self._opts.get(OPT_TOMORROW, DEFAULT_TOMORROW))
        day_end = day_start + timedelta(days=1)
        window_end = day_end + timedelta(days=1) if pivot else day_end

        entries: list[Entry] = []
        entries += from_calendars(
            cfg,
            await self._fetch_calendars(day_start, window_end),
            day_start,
            day_end if pivot else None,
            now,
        )
        entries += from_todo(cfg, await self._fetch_todo(), day_start)

        sun = self.hass.states.get("sun.sun")
        if sun:
            entries += from_sun(
                cfg,
                dt_util.parse_datetime(str(sun.attributes.get("next_rising") or "")),
                dt_util.parse_datetime(str(sun.attributes.get("next_setting") or "")),
                day_start,
            )

        entries += from_alarms(cfg, self._read_alarms(), now, day_start)

        entries = dedupe(cfg, entries)
        entries = attach_weather(entries, await self._fetch_forecast(), now)
        entries = await self._attach_travel(cfg, entries, now)
        # Last, and deliberately: gaps are measured between the commitments that
        # survived dedupe, and a gap is not a thing to price a journey to or
        # hang a forecast on.
        entries += from_gaps(cfg, entries, now)

        self._base = entries
        self._apply_tags(now)
        return self._compose()

    async def _fetch_calendars(self, day_start, window_end) -> dict[str, list[dict[str, Any]]]:
        calendars = self._present(list(self._calendar_ids), "calendar.get_events")
        if not calendars:
            return {}
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": calendars,
                    "start_date_time": day_start.isoformat(),
                    "end_date_time": window_end.isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - one bad calendar must not blank the card
            self._log_fetch_failure("calendar.get_events")
            return {}
        return {
            entity_id: payload.get("events", [])
            for entity_id, payload in (response or {}).items()
        }

    async def _fetch_todo(self) -> list[dict[str, Any]]:
        todo = self.entry.data.get(CONF_TODO)
        if not todo or not self._present([todo], "todo.get_items"):
            return []
        try:
            response = await self.hass.services.async_call(
                "todo",
                "get_items",
                {"entity_id": todo, "status": "needs_action"},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001
            self._log_fetch_failure("todo.get_items")
            return []
        return ((response or {}).get(todo) or {}).get("items", [])

    async def _attach_travel(
        self, cfg: MergeConfig, entries: list[Entry], now: datetime
    ) -> list[Entry]:
        """Work out when to leave for the next few places you have to be.

        Off unless asked for: it is the one thing in here that talks to a
        server outside the house, and a timeline is still a timeline without
        it.
        """
        if not self._opts.get(OPT_LEAVE_BY):
            return entries
        origin = str(self._opts.get(OPT_LEAVE_ORIGIN) or DEFAULT_LEAVE_ORIGIN).strip()
        if origin != self._travel_origin:
            # Every cached journey started somewhere else.
            self._travel.forget()
            self._travel_origin = origin
        targets = travel_targets(entries, now, cfg.leave_max)
        priced = await self._travel.prices(
            targets,
            origin,
            now,
            region=str(self._opts.get(OPT_LEAVE_REGION) or DEFAULT_LEAVE_REGION),
            vehicle_type=str(
                self._opts.get(OPT_LEAVE_VEHICLE) or DEFAULT_LEAVE_VEHICLE
            ),
        )
        return attach_leave_by(entries, priced, cfg.leave_buffer)

    def _read_alarms(self) -> list[dict[str, Any]]:
        """Each configured phone's next alarm, straight off the state machine.

        A push sensor, so there is nothing to poll and nothing to call: the
        Companion app sends a value when the alarm changes and the state is
        already sitting there. `Package` names the app that set it, which is the
        only way to tell a wake-up from a bedtime reminder — the two look
        identical otherwise, because to Android they are.
        """
        out: list[dict[str, Any]] = []
        for entity_id in self._opts.get(OPT_ALARMS) or []:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            name = state.attributes.get("friendly_name") or entity_id
            # "Pixel 6a Next alarm" is the device talking about itself; the row
            # already says "Alarm", so the suffix is said twice.
            label = re.sub(r"\s*next alarm\s*$", "", str(name), flags=re.I).strip()
            out.append(
                {
                    "entity_id": entity_id,
                    "label": label or entity_id,
                    "start": state.state,
                    "package": state.attributes.get("Package"),
                }
            )
        return out

    async def _fetch_forecast(self) -> list[dict[str, Any]]:
        weather = self.entry.data.get(CONF_WEATHER)
        if not weather or not self._present([weather], "weather.get_forecasts"):
            return []
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001
            self._log_fetch_failure("weather.get_forecasts")
            return []
        return ((response or {}).get(weather) or {}).get("forecast", [])

    # -- tags ---------------------------------------------------------------

    async def _load_fired(self) -> None:
        stored = await self._store.async_load() or {}
        today = dt_util.now().date().isoformat()
        if str(stored.get("day") or "") == today:
            self._fired_day = today
            self._fired = set(stored.get("keys") or [])

    async def _load_pushed(self) -> None:
        stored = await self._rows_store.async_load() or {}
        self._pushed = list(stored.get("rows") or [])

    @callback
    def _save_pushed(self) -> None:
        self._rows_store.async_delay_save(lambda: {"rows": self._pushed}, 5)

    # -- rows an automation put there ---------------------------------------

    @callback
    def async_show(self, data: dict[str, Any]) -> None:
        """Put a row on the spine on behalf of an automation.

        The general case behind every specific one. Dayline cannot anticipate
        what is worth saying in someone else's house, and a config flow that
        tried would be a worse version of the automation editor they already
        have. So: an automation that has already decided says it, and gets the
        same row shape everything else on the card gets.

        Calling again with the same id replaces the row rather than stacking a
        second copy, which is what makes this safe to call from an automation
        that runs on every state change.
        """
        now = dt_util.now()
        # A digest rather than hash(): Python salts string hashing per process,
        # so the id a row was saved under would not be the id it got back after a
        # restart — the row would resurrect as a duplicate and no dismiss would
        # ever match it.
        message = str(data.get("message") or "")
        row_id = (
            str(data.get("id") or "").strip()
            or "auto:" + hashlib.sha1(message.encode()).hexdigest()[:10]
        )
        seconds = data.get("duration")
        expires = (
            (now + timedelta(seconds=int(seconds))).isoformat() if seconds else None
        )

        buttons = [
            button
            for button in (
                _button(_spec(data, "confirm"), "Do it"),
                _button(_spec(data, "cancel"), "Not now"),
            )
            if button
        ]

        entry: Entry = {
            "id": f"push:{row_id}",
            "start": _when(data.get("start"), now),
            "end": None,
            "all_day": False,
            "kind": "standing",
            "source": "House",
            "title": str(data.get("message") or "").strip() or "(no message)",
            "automation": (str(data.get("sentence") or "").strip() or None),
            "priority": data.get("priority") or "high",
            "level": data.get("level") or "normal",
            "sticky": True,
            "entity_id": data.get("entity_id"),
            "expires": expires,
        }
        if buttons:
            # One button stays in the singular field every other source writes,
            # so nothing downstream has to learn a second shape for the common
            # case. Two is where the plural earns itself.
            entry["actions"] = buttons
            entry["action"] = buttons[0]

        self._pushed = [row for row in self._pushed if row["id"] != entry["id"]]
        self._pushed.append(entry)
        self._save_pushed()
        self.async_set_updated_data(self._compose())

    @callback
    def async_dismiss(self, row_id: str) -> None:
        """Take a pushed row off the spine. Unknown ids are not an error — an
        automation tidying up after itself should not have to check first."""
        wanted = f"push:{str(row_id).strip()}"
        before = len(self._pushed)
        self._pushed = [row for row in self._pushed if row["id"] != wanted]
        if len(self._pushed) != before:
            self._save_pushed()
            self.async_set_updated_data(self._compose())

    @callback
    def _remember(self, key: str) -> None:
        today = dt_util.now().date().isoformat()
        if today != self._fired_day:
            # Yesterday's keys are not worth keeping. Every one of them carries
            # its own event's start time, so nothing from yesterday could
            # collide with today even if we did.
            self._fired_day, self._fired = today, set()
        self._fired.add(key)
        self._store.async_delay_save(
            lambda: {"day": self._fired_day, "keys": sorted(self._fired)}, 10
        )

    @callback
    def _cancel_fires(self) -> None:
        for stop in self._unsub_fires:
            stop()
        self._unsub_fires = []

    @callback
    def _apply_tags(self, now) -> None:
        """Decide what the tags on today do, and arm the timers that do it.

        Re-armed from scratch on every fetch rather than tracked incrementally,
        because an event can be moved, retitled or deleted between two fetches
        and a timer holding the old answer would fire it anyway. What stops a
        rearm from re-firing is the record of what already went, not the timer.

        Home Assistant's own calendar trigger would do the per-event part for
        us, but it reads calendars every fifteen minutes and we read them every
        five. Scheduling off our own fetch is three times fresher, and correct
        across overlapping and back-to-back events either way — a calendar
        entity is only ever "an event is active", so it never transitions twice.
        """
        plan = tagging.plan(self._base, self._control, self._fired, now)

        for entry in self._base:
            state = plan.states.get(entry["id"])
            if state:
                entry["tag_state"] = state
            else:
                entry.pop("tag_state", None)

        self._cancel_fires()
        for fire in plan.now:
            self._fire(fire)
            # The plan decided these were still to come, then we went and did
            # them. Say so in the same breath, or the row spends up to a whole
            # poll promising something it has already delivered.
            fire.entry["tag_state"] = tagging.FIRED
        for fire in plan.later:
            self._unsub_fires.append(
                async_track_point_in_time(
                    self.hass, partial(self._fire_at_its_moment, fire), fire.when
                )
            )

    @callback
    def _fire(self, fire: tagging.Fire) -> None:
        if fire.key in self._fired:
            return
        self._remember(fire.key)
        self.hass.bus.async_fire(EVENT_TAG, tagging.payload(fire))
        _LOGGER.debug("%s fired for %s", EVENT_TAG, fire.key)

    @callback
    def _fire_at_its_moment(self, fire: tagging.Fire, _now) -> None:
        self._fire(fire)
        # Flip the chip from "will fire" to "fired" now rather than waiting out
        # the rest of the poll. The row is making a claim about the house, and a
        # claim that lags by five minutes is the kind of small lie that stops
        # people trusting the card.
        fire.entry["tag_state"] = tagging.FIRED
        self.async_set_updated_data(self._compose())

    # -- composing ----------------------------------------------------------

    def _compose(self) -> dict[str, Any]:
        now = dt_util.now()
        cap = int(self._opts.get(OPT_RECENT_MAX, DEFAULT_RECENT_MAX))
        self._recent = [
            e
            for e in self._recent
            if (dt_util.parse_datetime(e["expires"]) or now) > now
        ][-cap:]

        # Pushed rows expire the same way the "what just happened" lines do,
        # when they were given a duration at all. Most are not.
        kept = [
            row
            for row in self._pushed
            if not row.get("expires")
            or (dt_util.parse_datetime(row["expires"]) or now) > now
        ]
        if len(kept) != len(self._pushed):
            self._pushed = kept
            self._save_pushed()

        entries = sorted(
            self._base + self._recent + self._pushed, key=lambda e: e["start"]
        )
        left = remaining_count(entries, now)

        return {
            "entries": entries,
            "remaining": left,
            "headline": self._headline(left, now, entries),
            # The same answer the cards give, in a form a speaker can say. It
            # is computed here rather than in an automation's template so that
            # no surface can ever disagree with another about what is next.
            "briefing": briefing(entries, now),
            # A second sentence, for a second question. Told whether the
            # feature is on, so "nothing to leave for" and "you never switched
            # this on" can be told apart from across a room.
            "departure": departure(
                entries, now, bool(self._opts.get(OPT_LEAVE_BY))
            ),
            "now": self._render(self._opts.get(OPT_NOW_TEMPLATE) or ""),
            "sources": self._sources(),
            "stale_message": self._stale_message(),
            # The vocabulary people actually type, so a binding can be offered
            # for a tag rather than asked for up front.
            "tags_seen": tags_seen(entries),
            # Which calendars are on the spine and why, so "where is my
            # calendar" and "why did nothing happen" both have an answer that
            # does not involve reading the log.
            "calendars": list(self._calendar_ids),
            "calendar_source": self._calendar_source,
            "tag_control": sorted(self._control),
            # What it is doing outside right now, as opposed to what it will be
            # doing when an event starts. Both come from the same entity, and
            # neither is worth a second integration.
            "weather": self._now_weather(),
        }

    def _now_weather(self) -> dict[str, Any] | None:
        """Current conditions, read straight off the weather entity.

        The forecast is fetched through a service call because hourly data only
        exists there. Right now needs no such thing: a weather entity's state
        *is* the condition, and the temperature is an attribute of it. So this
        costs nothing per cycle and, unlike the forecast, is still correct when
        the provider stops answering.
        """
        entity_id = self.entry.data.get(CONF_WEATHER)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return {
            "condition": state.state,
            "temperature": state.attributes.get("temperature"),
            "temperature_unit": state.attributes.get("temperature_unit"),
        }

    def _headline(self, left: int, now, entries: list[Entry] | None = None) -> str:
        custom = self._render(self._opts.get(OPT_HEADLINE_TEMPLATE) or "")
        if custom:
            return custom
        date = now.strftime("%-d %B") if hasattr(now, "strftime") else ""
        if left == 0:
            # The pivot, in the one line that states what the card is about.
            # "Nothing scheduled" is true at eleven at night and answers the
            # question nobody is asking; what they want to know is when this
            # starts again. Only said when there is a held-back row to name it
            # with, so a genuinely empty day still reads as an empty day.
            first = self._first_held(entries or [], now)
            if first is not None:
                return f"{date} · tomorrow starts at {first.strftime('%-I:%M %p')}"
            return f"{date} · nothing scheduled"
        return f"{date} · {left} left today" if left > 1 else f"{date} · 1 left today"

    @staticmethod
    def _first_held(entries: list[Entry], now) -> datetime | None:
        """The earliest held-back row still ahead of us, if any."""
        moments = []
        for entry in entries:
            if not entry.get("when_empty"):
                continue
            start = dt_util.parse_datetime(str(entry.get("start") or ""))
            if start is not None and start > now:
                moments.append(start)
        return min(moments) if moments else None

    def _render(self, tpl: str) -> str:
        if not tpl.strip():
            return ""
        try:
            return str(Template(tpl, self.hass).async_render(parse_result=False)).strip()
        except Exception:  # noqa: BLE001 - a broken template must not blank the card
            _LOGGER.exception("Day Spine template failed: %s", tpl)
            return ""

    def _sources(self) -> list[dict[str, Any]]:
        """One pill per label. Two calendars sharing a label share a pill, and
        the pill goes stale if either of them is down."""
        names: list[str] = []
        bad: set[str] = set()
        colors: dict[str, str] = {}
        for entity_id, meta in self._meta().items():
            name = meta.get("label") or entity_id
            if name not in names:
                names.append(name)
            # First calendar listed under a shared label supplies the colour, as
            # it already supplies the wording. Two calendars deliberately given
            # one pill are one thing to the reader, so they get one colour.
            color = meta.get("color")
            if color and color != "default" and name not in colors:
                colors[name] = color
            state = self.hass.states.get(entity_id)
            if state is None or state.state in UNAVAILABLE:
                bad.add(name)
        return [
            {"label": name, "stale": name in bad, **({"color": colors[name]} if name in colors else {})}
            for name in names
        ]

    def _stale_message(self) -> str:
        bad = [s["label"] for s in self._sources() if s["stale"]]
        if not bad:
            return ""
        names = " and ".join(bad)
        verb = "calendars are" if len(bad) > 1 else "calendar is"
        them = "them" if len(bad) > 1 else "it"
        return f"{names} {verb} not updating. Anything on {them} is missing from today."


def _spec(data: dict[str, Any], which: str) -> dict[str, Any] | None:
    """Pull one button out of the call, whichever way it was written.

    A section in `services.yaml` groups fields in the editor and nothing more —
    what arrives is flat, the same way `light.turn_on` takes `brightness` from
    inside its `additional_fields` section. So the editor sends
    `confirm_label` and `confirm_action` at the top level, and the nested
    `confirm: {label, action}` shape only ever came from hand-written YAML
    following our own early documentation. Both are read; neither is required.
    """
    nested = data.get(which)
    spec = dict(nested) if isinstance(nested, dict) else {}
    if data.get(f"{which}_label") is not None:
        spec["label"] = data[f"{which}_label"]
    if data.get(f"{which}_action") is not None:
        spec["action"] = data[f"{which}_action"]
    return spec or None


def _button(spec: dict[str, Any] | None, fallback: str) -> dict[str, Any] | None:
    """Turn one `ui_action` into something the card can carry out.

    `ui_action` is the selector every Home Assistant card editor uses for "what
    does this button do", so what arrives here is the shape people have already
    filled in a hundred times, and a Dayline button ends up as capable as a
    button on any dashboard — not the script-only thing it started as.

    Translated rather than passed through, because the card should not have to
    learn Home Assistant's action schema to press a button. Anything unknown
    yields no button at all: a control that does nothing is worse than an
    absent one.
    """
    if not spec:
        return None
    action = spec.get("action") or {}
    label = str(spec.get("label") or "").strip() or fallback
    kind = action.get("action")

    if kind in ("perform-action", "call-service"):
        # `call-service` is the old spelling, still what older blueprints and
        # hand-written YAML produce.
        service = action.get("perform_action") or action.get("service")
        if not service:
            return None
        out: dict[str, Any] = {"label": label, "service": str(service)}
        if action.get("target"):
            out["target"] = action["target"]
        if action.get("data"):
            out["data"] = action["data"]
        return out

    if kind == "more-info":
        entity = (action.get("target") or {}).get("entity_id") or action.get("entity")
        return {"label": label, "more_info": entity} if entity else None
    if kind == "navigate" and action.get("navigation_path"):
        return {"label": label, "navigate": str(action["navigation_path"])}
    if kind == "url" and action.get("url_path"):
        return {"label": label, "url": str(action["url_path"])}
    return None


def _when(raw: Any, now: datetime) -> str:
    """Where a pushed row sorts into the day.

    Parsed and re-emitted rather than passed through. Whatever someone typed into
    a text field reaches the card as a string it has to `Date.parse`, and a value
    that parses differently there than here — or does not parse at all — puts the
    row at the wrong time of day, which is the one thing a timeline cannot get
    away with. A naive timestamp is read as the instance's own local time, which
    is what someone typing one means.
    """
    text = str(raw or "").strip()
    if not text:
        return now.isoformat()
    parsed = dt_util.parse_datetime(text)
    if parsed is None:
        # A bare date is the trap worth catching by name. `Date.parse` in the
        # browser reads a date-only ISO string as *UTC* midnight while reading a
        # date-and-time one as local — so "2026-09-04" would land the row on the
        # evening of the third, with the wrong meridiem, on any instance west of
        # Greenwich. Start of the local day is what someone typing a date means.
        day = dt_util.parse_date(text)
        if day is not None:
            return dt_util.start_of_local_day(
                datetime(day.year, day.month, day.day)
            ).isoformat()
    if parsed is None:
        _LOGGER.warning(
            "day_spine.show: could not read start %r, using now instead", text
        )
        return now.isoformat()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return parsed.isoformat()
