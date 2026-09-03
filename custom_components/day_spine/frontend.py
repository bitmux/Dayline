"""Serving the card from the integration.

HACS treats a repository as either a frontend plugin or an integration, not
both. Rather than split this into two repositories that can drift apart in
version, the integration serves the card's bundle itself and registers it with
the frontend — so installing one thing gets you both, and nobody has to paste a
URL into the Resources page and remember to hard-refresh.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/day_spine_frontend"
CARD_FILE = "day-spine-card.js"

# Bumped when the bundle changes. It is a cache-buster, nothing more: without it
# a browser that has seen the old file will keep it after an upgrade, and the
# card will look broken in a way no amount of restarting fixes.
CARD_VERSION = "0.1.0"

_registered = False


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve dist/day-spine-card.js and add it to the frontend. Idempotent."""
    global _registered
    if _registered:
        return

    source = Path(__file__).parent / "www"
    if not (source / CARD_FILE).is_file():
        _LOGGER.warning(
            "%s is missing from %s — the integration will still produce the feed, "
            "but the card has to be installed by hand",
            CARD_FILE,
            source,
        )
        return

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, str(source), cache_headers=False)]
        )
    except ImportError:  # Home Assistant older than 2024.7
        hass.http.register_static_path(URL_BASE, str(source), cache_headers=False)

    add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILE}?v={CARD_VERSION}")
    _registered = True
    _LOGGER.debug("Day Spine card registered at %s/%s", URL_BASE, CARD_FILE)
