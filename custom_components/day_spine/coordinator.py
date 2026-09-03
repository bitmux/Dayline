"""Fetching the day and keeping it current."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

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

    def _merge_config(self) -> MergeConfig:
        meta = self._opts.get(OPT_CALENDAR_META) or {}
        # Preserve the configured order: it decides whose wording wins a merge.
        ordered = {
            entity_id: meta.get(entity_id, {})
            for entity_id in self.entry.data.get(CONF_CALENDARS, [])
        }
        return MergeConfig(
            calendar_meta=ordered,
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
        """Start watching the entities that produce 'what just happened' lines."""
        self._resubscribe()
        self.entry.async_on_unload(self._teardown)

    @callback
    def _teardown(self) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None

    @callback
    def _resubscribe(self) -> None:
        self._teardown()
        watched = [
            rule["entity_id"]
            for rule in (self._opts.get(OPT_RECENT) or [])
            if rule.get("entity_id")
        ]
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

        phrase = None
        for rule in self._opts.get(OPT_RECENT) or []:
            if rule.get("entity_id") == event.data["entity_id"] and rule.get("state") == new.state:
                phrase = rule.get("phrase")
                break
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
        return self._compose()

    async def _fetch_calendars(self, day_start) -> dict[str, list[dict[str, Any]]]:
        calendars = self.entry.data.get(CONF_CALENDARS) or []
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
            _LOGGER.exception("calendar.get_events failed")
            return {}
        return {
            entity_id: payload.get("events", [])
            for entity_id, payload in (response or {}).items()
        }

    async def _fetch_todo(self) -> list[dict[str, Any]]:
        todo = self.entry.data.get(CONF_TODO)
        if not todo:
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
            _LOGGER.exception("todo.get_items failed")
            return []
        return ((response or {}).get(todo) or {}).get("items", [])

    async def _fetch_forecast(self) -> list[dict[str, Any]]:
        weather = self.entry.data.get(CONF_WEATHER)
        if not weather:
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
            _LOGGER.exception("weather.get_forecasts failed")
            return []
        return ((response or {}).get(weather) or {}).get("forecast", [])

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
        meta = self._opts.get(OPT_CALENDAR_META) or {}
        labels: list[str] = []
        bad: set[str] = set()
        for entity_id in self.entry.data.get(CONF_CALENDARS, []):
            label = (meta.get(entity_id) or {}).get("label") or entity_id
            if label not in labels:
                labels.append(label)
            state = self.hass.states.get(entity_id)
            if state is None or state.state in UNAVAILABLE:
                bad.add(label)
        return [{"label": label, "stale": label in bad} for label in labels]

    def _stale_message(self) -> str:
        bad = [s["label"] for s in self._sources() if s["stale"]]
        if not bad:
            return ""
        names = " and ".join(bad)
        verb = "calendars are" if len(bad) > 1 else "calendar is"
        them = "them" if len(bad) > 1 else "it"
        return f"{names} {verb} not updating. Anything on {them} is missing from today."
