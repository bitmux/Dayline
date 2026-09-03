"""Run the integration's merge against stub data and emit a card payload.

Home Assistant cannot run here, but merge.py is deliberately free of HA imports,
so the half that makes decisions can be exercised anyway. The output is written
to dev/integration-sample.json and rendered by the dev harness — which is what
proves the integration and the YAML package produce the same contract.

    .venv/bin/python tools/render-integration.py
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]

# merge.py is loaded by path rather than as `day_spine.merge`, because importing
# the package would run its __init__ and pull in Home Assistant. Keeping the
# merge logic importable on its own is the point of having no HA imports in it.
import importlib.util as _il

_spec = _il.spec_from_file_location(
    "day_spine_merge", ROOT / "custom_components" / "day_spine" / "merge.py"
)
merge = _il.module_from_spec(_spec)
assert _spec.loader is not None
# @dataclass resolves annotations through sys.modules, so register before exec.
import sys as _sys

_sys.modules[_spec.name] = merge
_spec.loader.exec_module(merge)

MergeConfig = merge.MergeConfig
attach_weather = merge.attach_weather
dedupe = merge.dedupe
from_calendars = merge.from_calendars
from_sun = merge.from_sun
from_todo = merge.from_todo
remaining_count = merge.remaining_count

TZ = timezone(timedelta(hours=-5))
NOW = datetime(2026, 9, 2, 14, 39, tzinfo=TZ)
DAY_START = NOW.replace(hour=0, minute=0)


def iso(h: int, m: int = 0, day: int = 2) -> str:
    return datetime(2026, 9, day, h, m, tzinfo=TZ).isoformat()


CFG = MergeConfig(
    # Order is precedence: the family calendar supplies the wording on a merge.
    calendar_meta={
        "calendar.family": {"label": "Google", "priority": "normal", "role": "people"},
        "calendar.wife": {"label": "CalDAV", "priority": "normal", "role": "people"},
        "calendar.house_schedule": {"label": "House", "role": "schedule"},
    },
    sentences=[
        {"match": "out of school", "automation": "Entry unlocks on her arrival"},
        {"match": "bed time", "automation": "Story on Sonos, 20 min, then dark", "priority": "high"},
        {"match": "sunset", "automation": "Evening lights over 20 minutes"},
    ],
    exclude=["Busy"],
    show_sun=True,
    similarity=0.8,
    title_noise=["a", "an", "the", "at", "to", "for", "with", "and", "of", "appointment"],
    todo_entity="todo.household",
)

EVENTS = {
    "calendar.family": [
        {"start": "2026-09-02", "end": "2026-09-03", "summary": "Trash out tonight"},
        {"start": iso(8, 20), "end": iso(8, 40), "summary": "Kid to school"},
        {"start": iso(13, 0), "end": iso(14, 0), "summary": "Busy"},
        {"start": iso(14, 0), "end": iso(17, 15), "summary": "Kid's art class"},
        {"start": iso(15, 50), "end": iso(16, 20), "summary": "Kid out of school"},
        {"start": iso(21, 0), "end": iso(21, 30), "summary": "Kid bed time"},
    ],
    "calendar.wife": [
        # near-duplicate of the family calendar's 15:50, worded differently
        {"start": iso(15, 50), "end": iso(16, 20), "summary": "Kid out of the school"},
        {"start": iso(22, 0), "end": iso(6, 30, day=3), "summary": "Wife night shift"},
    ],
    "calendar.house_schedule": [
        {
            "start": iso(7, 0),
            "end": iso(7, 5),
            "summary": "Morning",
            "description": "Lights up over 20 minutes, thermostat to 70°",
        }
    ],
}

TODO = [
    {"uid": "abc", "summary": "Switch the laundry", "due": iso(14, 1)},
    {"uid": "def", "summary": "No due date, no row"},
]

FORECAST = [
    {"datetime": iso(h, 0), "condition": c, "temperature": t, "precipitation_probability": p}
    for h, c, t, p in [
        (15, "rainy", 63, 70),
        (16, "pouring", 61, 85),
        (19, "partlycloudy", 58, 10),
        (21, "clear-night", 54, 0),
        (22, "clear-night", 52, 0),
    ]
]

RECENT = [
    {
        "id": "evt:light.living_room",
        "start": iso(14, 36),
        "end": None,
        "expires": iso(14, 41),
        "all_day": False,
        "kind": "event",
        "source": "House",
        "title": "Living room lights turned off by motion sensor",
        "entity_id": "light.living_room",
    }
]


def main() -> None:
    entries = from_calendars(CFG, EVENTS, DAY_START)
    entries += from_todo(CFG, TODO, DAY_START)
    entries += from_sun(
        CFG,
        next_rising=datetime(2026, 9, 3, 6, 58, tzinfo=TZ),
        next_setting=datetime(2026, 9, 2, 19, 47, tzinfo=TZ),
        today=NOW.date(),
    )
    entries = dedupe(CFG, entries)
    entries = attach_weather(entries, FORECAST, NOW)
    entries = sorted(entries + RECENT, key=lambda e: e["start"])

    left = remaining_count(entries, NOW)
    payload = {
        "entries": entries,
        "headline": f"2 September · {left} left today",
        "now": "Afternoon · house quiet, doors locked",
        "sources": [
            {"label": "Google", "stale": False},
            {"label": "CalDAV", "stale": False},
            {"label": "House", "stale": True},
        ],
        "stale_message": "House calendar is not updating. Anything on it is missing from today.",
    }

    for e in entries:
        when = "all-day" if e.get("all_day") else e["start"][11:16]
        extra = []
        if e.get("end"):
            extra.append(f"→{e['end'][11:16]}")
        if e.get("weather"):
            extra.append(f"wx={e['weather'].get('condition')}")
        if e.get("merged_from"):
            extra.append("MERGED")
        if e.get("action"):
            extra.append("ACTION")
        print(f"  {when:>7}  {e['kind']:<10} {str(e.get('source')):<16} "
              f"{e['title'][:38]:<40} {' '.join(extra)}")
    print(f"\nremaining = {left}")

    out = ROOT / "dev" / "integration-sample.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
