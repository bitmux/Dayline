"""Fetching the day and keeping it current."""

from __future__ import annotations

import logging
from datetime import timedelta
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
from .const import (
    CONF_CALENDARS,
    CONF_TODO,
    CONF_WEATHER,
    DEFAULT_RECENT_MAX,
    DEFAULT_RECENT_TTL,
    DEFAULT_SCAN_MINUTES,
    DEFAULT_SIMILARITY,
    DEFAULT_TITLE_NOISE,
    DOMAIN,
    EVENT_TAG,
    LABEL_CONTROL,
    LABEL_INCLUDE,
    OPT_CALENDAR_META,
    OPT_EXCLUDE,
    OPT_HEADLINE_TEMPLATE,
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
    attach_weather,
    dedupe,
    from_calendars,
    from_sun,
    from_todo,
    remaining_count,
    tags_seen,
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
        self._unsub_registries = None

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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=entry.options.get(OPT_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
            ),
        )

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
        )

    # -- the fast path ------------------------------------------------------

    async def async_setup(self) -> None:
        """Resolve the labels, remember what has already fired, start watching."""
        await self._load_fired()
        self._resolve()
        self._resubscribe()
        self._unsub_registries = labels.async_track_registries(
            self.hass, self._on_registry_change
        )
        self.entry.async_on_unload(self._teardown)

    @callback
    def _teardown(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        if self._unsub_registries:
            self._unsub_registries()
            self._unsub_registries = None
        self._cancel_fires()

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
        labelled = labels.resolve(self.hass, LABEL_INCLUDE, "calendar")
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
            for entity_id in labels.resolve(self.hass, LABEL_INCLUDE)
            if not entity_id.startswith("calendar.")
        ]
        self._control = set(labels.resolve(self.hass, LABEL_CONTROL, "calendar"))

    @callback
    def _snapshot(self) -> tuple:
        return (tuple(self._calendar_ids), tuple(self._watched_ids), tuple(sorted(self._control)))

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

    @callback
    def _on_state_change(self, event: Event) -> None:
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        if new is None or old is None or new.state == old.state:
            return
        # A parent context means something other than a person caused this.
        # Someone who flipped the switch themselves does not need telling.
        if new.context.parent_id is None:
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

        entries: list[Entry] = []
        entries += from_calendars(cfg, await self._fetch_calendars(day_start), day_start)
        entries += from_todo(cfg, await self._fetch_todo(), day_start)

        sun = self.hass.states.get("sun.sun")
        if sun:
            entries += from_sun(
                cfg,
                dt_util.parse_datetime(str(sun.attributes.get("next_rising") or "")),
                dt_util.parse_datetime(str(sun.attributes.get("next_setting") or "")),
                day_start,
            )

        entries = dedupe(cfg, entries)
        entries = attach_weather(entries, await self._fetch_forecast(), now)

        self._base = entries
        self._apply_tags(now)
        return self._compose()

    async def _fetch_calendars(self, day_start) -> dict[str, list[dict[str, Any]]]:
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
                    "end_date_time": (day_start + timedelta(days=1)).isoformat(),
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

        entries = sorted(self._base + self._recent, key=lambda e: e["start"])
        left = remaining_count(entries, now)

        return {
            "entries": entries,
            "remaining": left,
            "headline": self._headline(left, now),
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
        }

    def _headline(self, left: int, now) -> str:
        custom = self._render(self._opts.get(OPT_HEADLINE_TEMPLATE) or "")
        if custom:
            return custom
        date = now.strftime("%-d %B") if hasattr(now, "strftime") else ""
        if left == 0:
            return f"{date} · nothing scheduled"
        return f"{date} · {left} left today" if left > 1 else f"{date} · 1 left today"

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
        for entity_id, meta in self._meta().items():
            name = meta.get("label") or entity_id
            if name not in names:
                names.append(name)
            state = self.hass.states.get(entity_id)
            if state is None or state.state in UNAVAILABLE:
                bad.add(name)
        return [{"label": name, "stale": name in bad} for name in names]

    def _stale_message(self) -> str:
        bad = [s["label"] for s in self._sources() if s["stale"]]
        if not bad:
            return ""
        names = " and ".join(bad)
        verb = "calendars are" if len(bad) > 1 else "calendar is"
        them = "them" if len(bad) > 1 else "it"
        return f"{names} {verb} not updating. Anything on {them} is missing from today."
