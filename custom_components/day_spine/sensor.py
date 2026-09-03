"""The one sensor the card reads."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DaySpineCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DaySpineCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DaySpineSensor(coordinator, entry)])


class DaySpineSensor(CoordinatorEntity[DaySpineCoordinator], SensorEntity):
    """State is the count of what is left; the day itself rides in attributes.

    That split is not cosmetic. Home Assistant truncates state strings at 255
    characters, so the payload has to live in attributes — and a short numeric
    state is something you can usefully put in an automation or a badge.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:timeline-clock-outline"
    _attr_native_unit_of_measurement = "entries"

    def __init__(self, coordinator: DaySpineCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_name = None
        self._attr_unique_id = f"{entry.entry_id}_spine"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Day Spine",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        return None if data is None else data.get("remaining")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "entries": data.get("entries", []),
            "headline": data.get("headline", ""),
            "now": data.get("now", ""),
            "sources": data.get("sources", []),
            "stale_message": data.get("stale_message", ""),
            "tags_seen": data.get("tags_seen", []),
            "calendars": data.get("calendars", []),
            "calendar_source": data.get("calendar_source", ""),
            "tag_control": data.get("tag_control", []),
        }
