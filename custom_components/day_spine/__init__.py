"""The Day Spine integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, LEVELS, PRIORITIES, SERVICE_DISMISS, SERVICE_SHOW
from .coordinator import DaySpineCoordinator

PLATFORMS = [Platform.SENSOR]

# A button, in Home Assistant's own `tap_action` vocabulary rather than ours.
#
# The `ui_action` selector is what every card editor uses for "what does this
# button do", so the shape it produces is the shape people have already filled
# in a hundred times — perform an action, open more-info, navigate, open a URL.
# Validating it loosely on purpose: this is HA's schema, it grows, and rejecting
# a key we have not heard of would break on their release rather than ours.
_BUTTON = vol.Schema(
    {
        vol.Optional("label"): cv.string,
        vol.Optional("action"): vol.Any(dict, None),
    }
)

SHOW_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("id"): cv.string,
        vol.Optional("level", default="normal"): vol.In(LEVELS),
        vol.Optional("sentence"): cv.string,
        vol.Optional("priority", default="high"): vol.In(PRIORITIES),
        vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("start"): cv.string,
        vol.Optional("entity_id"): cv.entity_id,
        vol.Optional("confirm"): _BUTTON,
        vol.Optional("cancel"): _BUTTON,
    }
)

DISMISS_SCHEMA = vol.Schema({vol.Required("id"): cv.string})


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register once for the integration, not once per config entry.

    Both go to every configured feed. There is normally one, and someone running
    two spines almost certainly wants a row on both rather than a target
    selector to get wrong from inside an automation.
    """
    if hass.services.has_service(DOMAIN, SERVICE_SHOW):
        return

    async def _show(call: ServiceCall) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            coordinator.async_show(dict(call.data))

    async def _dismiss(call: ServiceCall) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            coordinator.async_dismiss(call.data["id"])

    hass.services.async_register(DOMAIN, SERVICE_SHOW, _show, schema=SHOW_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DISMISS, _dismiss, schema=DISMISS_SCHEMA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # This integration is the feed and nothing else. The card is a separate HACS
    # Dashboard repository, installed and registered as a Lovelace resource by
    # HACS itself — which owns that registration and does it through supported
    # paths. Serving the bundle from here meant writing into Lovelace's own
    # storage collection from outside, with no public API and no contract, and
    # it behaved accordingly.
    coordinator = DaySpineCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    # Calendars, to-do lists and weather are separate integrations, and on a
    # cold boot some of them are not set up yet when this one is. Their response
    # services then raise "did not match any entities" and the first spine comes
    # out missing the laundry and the forecast — which would sit there, looking
    # like a wrong answer rather than an early one, until the next poll five
    # minutes later. Ask once more when everything has finished starting.
    async def _refresh_when_everything_is_up(_now) -> None:
        await coordinator.async_refresh()

    entry.async_on_unload(async_at_started(hass, _refresh_when_everything_is_up))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options changed. Reload rather than patch state in place — the watched
    entity list, the poll interval and the merge rules can all have moved."""
    await hass.config_entries.async_reload(entry.entry_id)
