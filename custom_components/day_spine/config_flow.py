"""Setup and options UI.

Two principles here. Setup asks the fewest questions that can produce a working
card — pick your calendars and you are done. Everything else is an option you
find later, once you know you want it.

The lists (sentences, watched entities) are edited one item at a time through a
pick-or-add step rather than a textarea of delimited lines. A textarea would be
less code and would still be YAML wearing a costume; the point of this whole
piece of work is that the second person in the house can change what the card
says without being handed a syntax.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

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
    PRIORITIES,
    ROLES,
)

ADD = "__add__"
DONE = "__done__"


def _entity(domain: str, multiple: bool = False) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domain, multiple=multiple)
    )


def _select(options: list[str], key: str | None = None) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key=key,
        )
    )


def _words() -> selector.SelectSelector:
    """A free-text list — type a word, press enter, it becomes a chip."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=[], multiple=True, custom_value=True)
    )


class DaySpineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Setup: the shortest path to a card that renders."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            calendars = user_input[CONF_CALENDARS]
            return self.async_create_entry(
                title=user_input.get("name") or "Day Spine",
                data={
                    CONF_CALENDARS: calendars,
                    CONF_WEATHER: user_input.get(CONF_WEATHER),
                    CONF_TODO: user_input.get(CONF_TODO),
                },
                # Sensible defaults so the card works before anything is tuned.
                # Labels default to each calendar's own name.
                options={
                    OPT_CALENDAR_META: {
                        entity_id: {
                            "label": self._friendly(entity_id),
                            "priority": "normal",
                            "role": "people",
                        }
                        for entity_id in calendars
                    },
                    OPT_SENTENCES: [],
                    OPT_EXCLUDE: [],
                    OPT_RECENT: [],
                    OPT_SHOW_SUN: True,
                    OPT_SUN_PRIORITY: "low",
                    OPT_SIMILARITY: DEFAULT_SIMILARITY,
                    OPT_TITLE_NOISE: DEFAULT_TITLE_NOISE,
                    OPT_RECENT_TTL: DEFAULT_RECENT_TTL,
                    OPT_RECENT_MAX: DEFAULT_RECENT_MAX,
                    OPT_SCAN_MINUTES: DEFAULT_SCAN_MINUTES,
                    OPT_NOW_TEMPLATE: "",
                    OPT_HEADLINE_TEMPLATE: "",
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default="Day Spine"): selector.TextSelector(),
                    vol.Required(CONF_CALENDARS): _entity("calendar", multiple=True),
                    vol.Optional(CONF_WEATHER): _entity("weather"),
                    vol.Optional(CONF_TODO): _entity("todo"),
                }
            ),
        )

    def _friendly(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return (state.name if state else None) or entity_id.split(".")[-1].replace("_", " ").title()

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return DaySpineOptionsFlow()


class DaySpineOptionsFlow(OptionsFlow):
    """Everything you might want to change later, grouped by what it affects."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] = {}
        self._index: int | None = None

    # -- menu ---------------------------------------------------------------

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not self._opts:
            self._opts = dict(self.config_entry.options)
        return self.async_show_menu(
            step_id="init",
            menu_options=["sources", "calendars", "sentences", "recent", "tuning"],
        )

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=self._opts)

    # -- which entities feed the card ---------------------------------------

    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        data = dict(self.config_entry.data)
        if user_input is not None:
            calendars = user_input[CONF_CALENDARS]
            # Keep metadata for calendars that survived, seed it for new ones,
            # and drop it for removed ones so stale labels cannot linger.
            meta = self._opts.get(OPT_CALENDAR_META) or {}
            self._opts[OPT_CALENDAR_META] = {
                entity_id: meta.get(
                    entity_id,
                    {"label": self._friendly(entity_id), "priority": "normal", "role": "people"},
                )
                for entity_id in calendars
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    CONF_CALENDARS: calendars,
                    CONF_WEATHER: user_input.get(CONF_WEATHER),
                    CONF_TODO: user_input.get(CONF_TODO),
                },
            )
            return self._save()

        schema: dict[Any, Any] = {
            vol.Required(CONF_CALENDARS, default=data.get(CONF_CALENDARS, [])): _entity(
                "calendar", multiple=True
            )
        }
        _optional(schema, CONF_WEATHER, data.get(CONF_WEATHER), _entity("weather"))
        _optional(schema, CONF_TODO, data.get(CONF_TODO), _entity("todo"))
        return self.async_show_form(step_id="sources", data_schema=vol.Schema(schema))

    # -- per-calendar label, priority, role ---------------------------------

    async def async_step_calendars(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        calendars: list[str] = self.config_entry.data.get(CONF_CALENDARS, [])
        meta = self._opts.get(OPT_CALENDAR_META) or {}

        if user_input is not None:
            self._opts[OPT_CALENDAR_META] = {
                entity_id: {
                    "label": user_input.get(f"{entity_id}__label") or self._friendly(entity_id),
                    "priority": user_input.get(f"{entity_id}__priority", "normal"),
                    "role": user_input.get(f"{entity_id}__role", "people"),
                }
                for entity_id in calendars
            }
            return self._save()

        schema: dict[Any, Any] = {}
        for entity_id in calendars:
            current = meta.get(entity_id, {})
            schema[
                vol.Optional(f"{entity_id}__label", default=current.get("label") or self._friendly(entity_id))
            ] = selector.TextSelector()
            schema[
                vol.Optional(f"{entity_id}__priority", default=current.get("priority", "normal"))
            ] = _select(PRIORITIES, "priority")
            schema[
                vol.Optional(f"{entity_id}__role", default=current.get("role", "people"))
            ] = _select(ROLES, "role")

        return self.async_show_form(
            step_id="calendars",
            data_schema=vol.Schema(schema),
            description_placeholders={"count": str(len(calendars))},
        )

    # -- the sentence map ---------------------------------------------------

    async def async_step_sentences(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        items = self._opts.get(OPT_SENTENCES) or []
        if user_input is not None:
            choice = user_input["selection"]
            if choice == DONE:
                return self._save()
            self._index = None if choice == ADD else int(choice)
            return await self.async_step_sentence_edit()

        options = [
            selector.SelectOptionDict(
                value=str(i),
                label=f"{rule.get('match', '?')} → {rule.get('automation') or '(no sentence)'}",
            )
            for i, rule in enumerate(items)
        ]
        options.append(selector.SelectOptionDict(value=ADD, label="➕  Add a sentence"))
        options.append(selector.SelectOptionDict(value=DONE, label="✔  Done"))
        return self.async_show_form(
            step_id="sentences",
            data_schema=vol.Schema({vol.Required("selection", default=ADD): _options(options)}),
        )

    async def async_step_sentence_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        items = list(self._opts.get(OPT_SENTENCES) or [])
        current = items[self._index] if self._index is not None else {}

        if user_input is not None:
            if user_input.get("delete") and self._index is not None:
                items.pop(self._index)
            else:
                rule = {
                    "match": user_input["match"].strip(),
                    "automation": (user_input.get("automation") or "").strip() or None,
                    "priority": user_input.get("priority", "normal"),
                    "sticky": bool(user_input.get("sticky", False)),
                }
                if self._index is None:
                    items.append(rule)
                else:
                    items[self._index] = rule
            self._opts[OPT_SENTENCES] = items
            return await self.async_step_sentences()

        return self.async_show_form(
            step_id="sentence_edit",
            data_schema=vol.Schema(
                {
                    vol.Required("match", default=current.get("match", "")): selector.TextSelector(),
                    vol.Optional(
                        "automation", default=current.get("automation") or ""
                    ): selector.TextSelector(),
                    vol.Optional("priority", default=current.get("priority", "normal")): _select(
                        PRIORITIES, "priority"
                    ),
                    vol.Optional("sticky", default=current.get("sticky", False)): selector.BooleanSelector(),
                    vol.Optional("delete", default=False): selector.BooleanSelector(),
                }
            ),
        )

    # -- "what just happened" -----------------------------------------------

    async def async_step_recent(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        items = self._opts.get(OPT_RECENT) or []
        if user_input is not None:
            choice = user_input["selection"]
            if choice == DONE:
                return self._save()
            self._index = None if choice == ADD else int(choice)
            return await self.async_step_recent_edit()

        options = [
            selector.SelectOptionDict(
                value=str(i),
                label=f"{rule.get('entity_id', '?')} → {rule.get('state', '?')}: {rule.get('phrase', '')}",
            )
            for i, rule in enumerate(items)
        ]
        options.append(selector.SelectOptionDict(value=ADD, label="➕  Add a line"))
        options.append(selector.SelectOptionDict(value=DONE, label="✔  Done"))
        return self.async_show_form(
            step_id="recent",
            data_schema=vol.Schema({vol.Required("selection", default=ADD): _options(options)}),
        )

    async def async_step_recent_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        items = list(self._opts.get(OPT_RECENT) or [])
        current = items[self._index] if self._index is not None else {}

        if user_input is not None:
            if user_input.get("delete") and self._index is not None:
                items.pop(self._index)
            else:
                rule = {
                    "entity_id": user_input["entity_id"],
                    "state": user_input["state"].strip(),
                    "phrase": user_input["phrase"].strip(),
                }
                if self._index is None:
                    items.append(rule)
                else:
                    items[self._index] = rule
            self._opts[OPT_RECENT] = items
            return await self.async_step_recent()

        schema: dict[Any, Any] = {}
        if current.get("entity_id"):
            schema[vol.Required("entity_id", default=current["entity_id"])] = _entity(None)
        else:
            schema[vol.Required("entity_id")] = _entity(None)
        schema[vol.Required("state", default=current.get("state", "off"))] = selector.TextSelector()
        schema[vol.Required("phrase", default=current.get("phrase", ""))] = selector.TextSelector()
        schema[vol.Optional("delete", default=False)] = selector.BooleanSelector()
        return self.async_show_form(step_id="recent_edit", data_schema=vol.Schema(schema))

    # -- the dials ----------------------------------------------------------

    async def async_step_tuning(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._opts.update(user_input)
            return self._save()

        o = self._opts
        return self.async_show_form(
            step_id="tuning",
            data_schema=vol.Schema(
                {
                    vol.Optional(OPT_SHOW_SUN, default=o.get(OPT_SHOW_SUN, True)): selector.BooleanSelector(),
                    vol.Optional(OPT_SUN_PRIORITY, default=o.get(OPT_SUN_PRIORITY, "low")): _select(
                        PRIORITIES, "priority"
                    ),
                    vol.Optional(OPT_EXCLUDE, default=o.get(OPT_EXCLUDE) or []): _words(),
                    vol.Optional(
                        OPT_SIMILARITY, default=o.get(OPT_SIMILARITY, DEFAULT_SIMILARITY)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0.3, max=1.0, step=0.05, mode="slider")
                    ),
                    vol.Optional(
                        OPT_TITLE_NOISE, default=o.get(OPT_TITLE_NOISE) or DEFAULT_TITLE_NOISE
                    ): _words(),
                    vol.Optional(
                        OPT_RECENT_TTL, default=o.get(OPT_RECENT_TTL, DEFAULT_RECENT_TTL)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=30, max=3600, step=30, unit_of_measurement="s")
                    ),
                    vol.Optional(
                        OPT_RECENT_MAX, default=o.get(OPT_RECENT_MAX, DEFAULT_RECENT_MAX)
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=20, step=1)),
                    vol.Optional(
                        OPT_SCAN_MINUTES, default=o.get(OPT_SCAN_MINUTES, DEFAULT_SCAN_MINUTES)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")
                    ),
                    vol.Optional(
                        OPT_NOW_TEMPLATE, default=o.get(OPT_NOW_TEMPLATE, "")
                    ): selector.TemplateSelector(),
                    vol.Optional(
                        OPT_HEADLINE_TEMPLATE, default=o.get(OPT_HEADLINE_TEMPLATE, "")
                    ): selector.TemplateSelector(),
                }
            ),
        )

    def _friendly(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return (state.name if state else None) or entity_id.split(".")[-1].replace("_", " ").title()


def _options(options: list[selector.SelectOptionDict]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
    )


def _optional(schema: dict[Any, Any], key: str, current: Any, sel: Any) -> None:
    """Only pass a default when there is one — an explicit None default makes
    the field impossible to leave empty in the UI."""
    if current:
        schema[vol.Optional(key, default=current)] = sel
    else:
        schema[vol.Optional(key)] = sel
