"""How long the journey takes, and therefore when to leave.

Home Assistant already ships a router. `waze_travel_time.get_travel_times`
takes two free-text addresses and gives back route alternatives with a duration
in minutes, needs no API key, and — the part that makes a leave-by time worth
printing — takes a `time_delta`, so it answers for the traffic at the time you
would actually be driving rather than the traffic right now. On a weekday
afternoon those differ by a fifth.

Everything here is about not asking it very often. A routing call is a network
round trip on someone else's server, the coordinator recomposes the day every
few minutes, and the answer to "how long to the dentist at four" does not
change materially between two consecutive polls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger(__name__)

WAZE_DOMAIN = "waze_travel_time"
WAZE_SERVICE = "get_travel_times"

# How long an answer is trusted, as a fraction of the time left before you have
# to be there, clamped. An event four hours out is re-priced hourly; one twenty
# minutes out, every five. Traffic that matters is traffic you are about to be
# sitting in.
_MIN_TTL = timedelta(minutes=5)
_MAX_TTL = timedelta(minutes=60)

# A destination the router could not make sense of is not asked about again
# today. The location field said "Kid's school" and no router on earth will
# turn that into a road; retrying it every five minutes until midnight is just
# noise in somebody's log.
_FAILURE_TTL = timedelta(hours=6)


class Travel:
    """Prices journeys, and remembers the answers.

    One of these lives on the coordinator. It holds the cache, which is the
    whole reason it is a class rather than a function.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        # location (lowercased) -> {"until": datetime, "minutes": float|None,
        #                           "route": str|None}
        self._cache: dict[str, dict[str, Any]] = {}
        self._warned = False

    def forget(self) -> None:
        """Drop everything. Used when the origin changes: every cached answer
        was to a different question."""
        self._cache.clear()

    async def prices(
        self,
        targets: list[tuple[str, datetime]],
        origin: str,
        now: datetime,
        region: str = "us",
        vehicle_type: str = "car",
    ) -> dict[str, dict[str, Any]]:
        """Travel time to each target, from cache where it is still good.

        Returns only the ones we have an answer for. A destination that failed
        is absent rather than zero — a missing leave-by line is a card that
        says nothing, and a wrong one is a card that makes you late.
        """
        if not targets or not origin:
            return {}
        if not await self._available():
            return {}

        out: dict[str, dict[str, Any]] = {}
        for location, start in targets:
            key = location.lower()
            hit = self._cache.get(key)
            if hit and hit["until"] > now:
                if hit.get("minutes") is not None:
                    out[key] = hit
                continue
            found = await self._ask(origin, location, start, now, region, vehicle_type)
            self._cache[key] = found
            if found.get("minutes") is not None:
                out[key] = found
        return out

    async def _ask(
        self,
        origin: str,
        location: str,
        start: datetime,
        now: datetime,
        region: str,
        vehicle_type: str,
    ) -> dict[str, Any]:
        """One routing call, for the traffic at the time of departure.

        Departure time depends on the journey length, which is what we are
        asking for — so seed it with whatever we last knew and ask about that
        moment. One iteration, not a loop: the difference between "leave in
        three hours" and "leave in two hours and thirty-five" is not enough
        traffic to be worth a second round trip, and a loop that converges on
        somebody else's server is a loop that can fail to.
        """
        previous = self._cache.get(location.lower(), {}).get("minutes") or 0
        depart = start - timedelta(minutes=float(previous))
        delta = max(0, int((depart - now).total_seconds()))

        try:
            response = await self.hass.services.async_call(
                WAZE_DOMAIN,
                WAZE_SERVICE,
                {
                    "origin": origin,
                    "destination": location,
                    "region": region,
                    "vehicle_type": vehicle_type,
                    "time_delta": delta,
                },
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - a router that is down must not take the day with it
            _LOGGER.debug("no route to %r", location, exc_info=True)
            return {"until": now + _FAILURE_TTL, "minutes": None}

        routes = (response or {}).get("routes") or []
        if not routes:
            return {"until": now + _FAILURE_TTL, "minutes": None}

        # Waze returns alternatives best-first; the first is the one it would
        # actually tell you to drive.
        best = routes[0]
        minutes = best.get("duration")
        if minutes is None:
            return {"until": now + _FAILURE_TTL, "minutes": None}
        return {
            "until": now + _ttl(start, now),
            "minutes": float(minutes),
            "route": best.get("name"),
        }

    async def _available(self) -> bool:
        """Whether the router is there to ask.

        `waze_travel_time` registers its service in `async_setup`, and a
        component nothing has asked for is never set up — so on most instances
        the service simply does not exist. Its config schema is
        `config_entry_only_config_schema`, which means loading it with no
        configuration is a supported thing to do: no entry, no entity, no
        second sensor on anybody's dashboard. Just the service, callable.

        So there is nothing for the user to install. That is the point.
        """
        if self.hass.services.has_service(WAZE_DOMAIN, WAZE_SERVICE):
            return True
        try:
            await async_setup_component(self.hass, WAZE_DOMAIN, {})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("could not load %s", WAZE_DOMAIN, exc_info=True)
        if self.hass.services.has_service(WAZE_DOMAIN, WAZE_SERVICE):
            return True
        if not self._warned:
            self._warned = True
            _LOGGER.warning(
                "Could not load %s, so leave-by times are unavailable", WAZE_DOMAIN
            )
        return False


def _ttl(start: datetime, now: datetime) -> timedelta:
    remaining = start - now
    if remaining <= _MIN_TTL:
        return _MIN_TTL
    return max(_MIN_TTL, min(_MAX_TTL, remaining / 4))
