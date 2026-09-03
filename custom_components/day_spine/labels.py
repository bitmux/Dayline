"""Resolving what Dayline watches from Home Assistant's label registry.

Picking calendars out of a dropdown of twenty is a decision made once, in the
wrong place, and re-made every time anything changes. A label is applied where
you were already standing — in the calendar's own settings — and it is the same
gesture for the first calendar and the ninth. Adding a calendar later never
involves Dayline at all.

Entities belonging to a labelled device count too, which is what Home
Assistant's own `label_entities` template function does. Matching it matters
more than being strict: a label should mean the same thing here as it does
everywhere else in the instance.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr


@callback
def resolve(hass: HomeAssistant, label_name: str, domain: str | None = None) -> list[str]:
    """Entity ids carrying `label_name`, directly or through their device.

    An absent label is not an error — it is the ordinary state of a fresh
    install, and the caller is expected to have an answer for the empty list.
    """
    label = lr.async_get(hass).async_get_label_by_name(label_name)
    if label is None:
        return []

    entities = er.async_get(hass)
    found = [e.entity_id for e in er.async_entries_for_label(entities, label.label_id)]
    for device in dr.async_entries_for_label(dr.async_get(hass), label.label_id):
        found += [e.entity_id for e in er.async_entries_for_device(entities, device.id)]

    ordered = sorted(dict.fromkeys(found))
    if domain:
        ordered = [e for e in ordered if e.startswith(f"{domain}.")]
    return ordered


@callback
def async_track_registries(
    hass: HomeAssistant, on_change: Callable[[], None]
) -> Callable[[], None]:
    """Call `on_change` whenever a registry moves under us.

    Three registries, because a label can arrive three ways: applied to an
    entity, applied to a device, or renamed out from under both. None of them
    fire on state changes, so this is quiet — and it is what makes a calendar
    labelled this afternoon appear without a restart.
    """

    @callback
    def _changed(_event: Event) -> None:
        on_change()

    unsubs = [
        hass.bus.async_listen(lr.EVENT_LABEL_REGISTRY_UPDATED, _changed),
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _changed),
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _changed),
    ]

    @callback
    def _unsub() -> None:
        for stop in unsubs:
            stop()

    return _unsub
