"""Run the integration's merge against a LIVE Home Assistant.

render-integration.py proves the merge against stub data. This proves it against
the real service responses, which is where the shapes actually differ — a stub
is only ever as right as the person who wrote it.

    python3 tools/live-merge.py

Needs HA_URL / HA_TOKEN (see tools/ha.py). Writes dev/live-sample.json so the
dev harness can render a real day.
"""

from __future__ import annotations

import importlib.util as _il
import json
import pathlib
import sys
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ha  # noqa: E402

# Loaded by path, not as `day_spine.merge` — importing the package would run its
# __init__ and pull in Home Assistant.
_spec = _il.spec_from_file_location(
    "day_spine_merge", ROOT / "custom_components" / "day_spine" / "merge.py"
)
merge = _il.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = merge
_spec.loader.exec_module(merge)

CALENDARS = {
    "calendar.dayline_family": {"label": "Family", "priority": "normal", "role": "people"},
    "calendar.dayline_house": {"label": "House", "role": "schedule"},
}
TODO_ENTITY = "todo.dayline_chores"
WEATHER_ENTITY = "weather.weather_krst_krst"  # NWS KRST — reports probability

CFG = merge.MergeConfig(
    calendar_meta=CALENDARS,
    sentences=[
        {"match": "pick up kid", "automation": "Entry unlocks on her arrival"},
        {"match": "laundry", "automation": "Washer reports when it finishes", "sticky": True},
    ],
    exclude=["Busy"],
    show_sun=True,
    similarity=0.8,
    title_noise=["a", "an", "the", "at", "to", "for", "with", "and", "of", "appointment"],
    todo_entity=TODO_ENTITY,
)


def fetch():
    now = datetime.fromisoformat(ha.template("{{ now().isoformat() }}"))
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    events = {}
    for entity in CALENDARS:
        r = ha.call_service(
            "calendar",
            "get_events",
            entity_id=entity,
            start_date_time=day_start.isoformat(),
            end_date_time=day_end.isoformat(),
            return_response=True,
        )
        events[entity] = r.get("service_response", {}).get(entity, {}).get("events", [])

    r = ha.call_service("todo", "get_items", entity_id=TODO_ENTITY, return_response=True)
    todo = r.get("service_response", {}).get(TODO_ENTITY, {}).get("items", [])

    r = ha.call_service(
        "weather", "get_forecasts", entity_id=WEATHER_ENTITY, type="hourly",
        return_response=True,
    )
    forecast = r.get("service_response", {}).get(WEATHER_ENTITY, {}).get("forecast", [])

    sun = ha.state("sun.sun")["attributes"]
    return now, day_start, events, todo, forecast, sun


def main() -> None:
    now, day_start, events, todo, forecast, sun = fetch()
    print(f"server now: {now:%Y-%m-%d %H:%M %z}\n")

    print("=== raw shapes, as Home Assistant actually returns them ===")
    for ent, evs in events.items():
        print(f"  {ent}: {len(evs)} events")
        if evs:
            print("    keys:", sorted(evs[0].keys()))
            print("    first:", json.dumps(evs[0])[:170])
    print(f"  todo: {len(todo)} items")
    if todo:
        print("    keys:", sorted(todo[0].keys()))
        print("    first:", json.dumps(todo[0])[:170])
    print(f"  forecast: {len(forecast)} hours")
    if forecast:
        print("    keys:", sorted(forecast[0].keys()))
    print()

    entries = merge.from_calendars(CFG, events, day_start)
    entries += merge.from_todo(CFG, todo, day_start)
    entries += merge.from_sun(
        CFG,
        next_rising=merge._parse(sun.get("next_rising")),
        next_setting=merge._parse(sun.get("next_setting")),
        day_start=day_start,
    )
    before = len(entries)
    entries = merge.dedupe(CFG, entries)
    merged = before - len(entries)
    entries = merge.attach_weather(entries, forecast, now)
    entries.sort(key=lambda e: e["start"])

    left = merge.remaining_count(entries, now)

    print("=== merged spine ===")
    for e in entries:
        when = "all-day" if e.get("all_day") else e["start"][11:16]
        extra = []
        if e.get("end"):
            extra.append(f"->{e['end'][11:16]}")
        if e.get("weather"):
            w = e["weather"]
            pop, mm = w.get("precipitation_probability"), w.get("precipitation")
            signal = f"{pop}%" if pop is not None else (f"{mm}mm" if mm is not None else "no-rain-signal")
            extra.append(f"wx={w.get('condition')}/{w.get('temperature')}/{signal}")
        if e.get("merged_from"):
            extra.append("MERGED")
        if e.get("action"):
            extra.append("ACTION")
        if e.get("automation"):
            extra.append(f"sage={e['automation'][:28]!r}")
        print(
            f"  {when:>7}  {e['kind']:<10} {str(e.get('source')):<9} "
            f"{e['title'][:34]:<36} {' '.join(extra)}"
        )
    print(f"\n{merged} merged away, {left} remaining after {now:%H:%M}")

    payload = {
        "entries": entries,
        "headline": f"{now:%-d %B} · {left} left today",
        "now": "Live from the test instance",
        "sources": [{"label": m["label"], "stale": False} for m in CALENDARS.values()],
        "stale_message": None,
    }
    out = ROOT / "dev" / "live-sample.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
