"""The Day Spine integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import DaySpineCoordinator
from .frontend import async_register_card

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # The card ships with the integration, so there is no Resources page step.
    await async_register_card(hass)

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
