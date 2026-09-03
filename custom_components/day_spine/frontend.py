"""Serving the card from the integration.

HACS treats a repository as either a frontend plugin or an integration, not
both. Rather than split this into two repositories that can drift apart in
version, the integration serves the card's bundle itself and registers it with
the frontend — so installing one thing gets you both, and nobody has to paste a
URL into the Resources page and remember to hard-refresh.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/day_spine_frontend"
CARD_FILE = "day-spine-card.js"

# The release this bundle belongs to. Human-facing only — it is the hash below
# that actually busts caches.
CARD_RELEASE = "0.1.1"

_registered = False


def _card_url(source: Path) -> str:
    """The URL to serve the card under, ending in something that changes when
    the file does.

    A hand-typed version constant does not change when the file does. During an
    alpha the bundle is rebuilt far more often than the release is bumped, so
    HACS happily delivers new code under the same `?v=0.1.0` and every browser
    that has already seen that URL keeps serving itself the old one out of
    cache — while the dashboard looks broken in a way no amount of restarting
    the server fixes. Hashing the bytes makes the URL wrong exactly when, and
    only when, the file is different.
    """
    digest = hashlib.sha256((source / CARD_FILE).read_bytes()).hexdigest()[:8]
    return f"{URL_BASE}/{CARD_FILE}?v={CARD_RELEASE}.{digest}"


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

    # Two mechanisms, deliberately, because they load at different moments.
    #
    # add_extra_js_url bakes an import into the frontend's index shell. That
    # shell is cached hard by the frontend's service worker, so a browser that
    # loaded the page before this integration existed keeps serving itself a
    # shell with no mention of the card — and the card is then missing on every
    # machine that ever visited, which no amount of restarting the server fixes.
    #
    # A Lovelace resource is fetched by the dashboard at runtime over the
    # websocket instead, so it survives a stale shell. It is also the documented
    # way to put a card in front of the picker.
    #
    # Both point at the identical URL string, so the browser's module registry
    # runs the file once however many times it is asked for — until an upgrade
    # changes the URL, at which point a service-worker-cached shell can still be
    # importing the old one. The card guards its own `customElements.define`
    # against exactly that.
    card_url = await hass.async_add_executor_job(_card_url, source)
    add_extra_js_url(hass, card_url)
    await _async_register_resource(hass, card_url)

    _registered = True
    _LOGGER.debug("Day Spine card registered at %s", card_url)


async def _async_register_resource(hass: HomeAssistant, card_url: str) -> None:
    """Add the card to Lovelace's resource list, or update the version on it.

    Storage mode only — a YAML dashboard's resources are the user's file to
    edit, and INSTALL.md says so. Never fatal: the feed is worth having even
    when the card cannot be registered.
    """
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_create_item"):
        _LOGGER.debug("Dashboards are in YAML mode; register the card by hand")
        return

    try:
        # A storage collection does not read its store until something asks.
        if not resources.loaded:
            await resources.async_get_info()

        for item in resources.async_items():
            if str(item.get("url", "")).split("?")[0] != f"{URL_BASE}/{CARD_FILE}":
                continue
            if item.get("url") != card_url:
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": card_url}
                )
                _LOGGER.debug("Updated the Dayline card resource to %s", card_url)
            return

        await resources.async_create_item({"res_type": "module", "url": card_url})
        _LOGGER.debug("Added the Dayline card as a Lovelace resource")
    except Exception:  # noqa: BLE001 - a dashboard quirk must not break the feed
        _LOGGER.exception("Could not register the Dayline card as a Lovelace resource")
