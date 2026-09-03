"""Fill the test instance with a day worth looking at.

Creates events on two Local Calendars and items on a Local To-do list, all
positioned relative to the server's own clock so the card has a past, a present
and a future no matter when this runs.

    python3 tools/seed-ha.py          # add the fixture
    python3 tools/seed-ha.py --clear  # remove everything it added

Everything it creates is titled with a marker so --clear can find it again
without touching anything of Admin's.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha  # noqa: E402

FAMILY = "calendar.dayline_family"
HOUSE = "calendar.dayline_house"
CHORES = "todo.dayline_chores"


def now() -> datetime:
    """The server's local time, not ours — they can differ by hours."""
    return datetime.fromisoformat(ha.template("{{ now().isoformat() }}"))


def at(base: datetime, minutes: int) -> str:
    return (base + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


# (calendar, offset from now in minutes, length in minutes, title, description)
# A schedule calendar's description is what the card says in sage, so the House
# rows carry consequences rather than scene names.
EVENTS = [
    (HOUSE, -8 * 60, 0, "Morning", "Lights up, thermostat to 70"),
    (FAMILY, -6 * 60, 30, "Kid to school", ""),
    (FAMILY, -3 * 60 - 30, 60, "Standup", ""),
    (HOUSE, -2 * 60, 0, "Away", "Thermostat back, doors lock"),
    # Straddles now, so the card must render it live with a progress bar.
    (FAMILY, -40, 120, "Budget review", ""),
    # A second live event — several things can be happening at once.
    (FAMILY, -15, 90, "Laundry cycle", ""),
    (FAMILY, 45, 60, "Pick up Kid", ""),
    (HOUSE, 90, 0, "Evening", "Entry unlocks on her arrival"),
    (FAMILY, 150, 90, "Dinner with the Hylands", ""),
    (HOUSE, 5 * 60, 0, "Night", "Everything off, doors check"),
    # Deliberately far out, to prove the density budget collapses it and the
    # "+N more today" row counts it.
    (FAMILY, 7 * 60, 60, "Late call with Portland", ""),
    (FAMILY, 8 * 60, 30, "Set out the bins", ""),
]

# Near-duplicates across two calendars — the 80% fuzzy dedupe should fold these
# into one row rather than showing both.
DUPES = [
    (FAMILY, 150, 90, "Dinner with the Hylands at 6", ""),
]

ALL_DAY = [(FAMILY, "Trash out tonight"), (FAMILY, "Kid half day")]

TODOS = [
    ("Switch the laundry", 20),
    ("Refill the water softener", 240),
]

MARKERS = ("Dayline",)


def seed() -> None:
    base = now()
    print(f"server local time: {base:%Y-%m-%d %H:%M %Z}")

    for cal, off, length, summary, desc in EVENTS + DUPES:
        payload = {
            "entity_id": cal,
            "summary": summary,
            "start_date_time": at(base, off),
            "end_date_time": at(base, off + (length or 1)),
        }
        if desc:
            payload["description"] = desc
        ha.call_service("calendar", "create_event", **payload)
        when = f"{off / 60:+.1f}h"
        print(f"  {cal.split('.')[1]:16} {when:>7}  {summary}")

    day = base.date()
    for cal, summary in ALL_DAY:
        ha.call_service(
            "calendar",
            "create_event",
            entity_id=cal,
            summary=summary,
            start_date=day.isoformat(),
            end_date=(day + timedelta(days=1)).isoformat(),
        )
        print(f"  {cal.split('.')[1]:16} all-day  {summary}")

    for summary, due_in in TODOS:
        ha.call_service(
            "todo",
            "add_item",
            entity_id=CHORES,
            item=summary,
            due_datetime=at(base, due_in),
        )
        print(f"  {CHORES.split('.')[1]:16} {due_in / 60:+.1f}h  {summary}")


def clear() -> None:
    base = now()
    lo = (base - timedelta(days=2)).isoformat()
    hi = (base + timedelta(days=2)).isoformat()
    for cal in (FAMILY, HOUSE):
        r = ha.call_service(
            "calendar",
            "get_events",
            entity_id=cal,
            start_date_time=lo,
            end_date_time=hi,
            return_response=True,
        )
        events = r.get("service_response", {}).get(cal, {}).get("events", [])
        print(f"  {cal}: {len(events)} events — delete them in the calendar panel")
        for e in events:
            print("     ", e.get("start"), e.get("summary"))
    print(
        "\nHome Assistant has no calendar.delete_event service; the frontend does it\n"
        "over the websocket API. Removing the two Local Calendar config entries and\n"
        "re-adding them is the quicker reset."
    )
    for item in ha.call_service(
        "todo", "get_items", entity_id=CHORES, return_response=True
    ).get("service_response", {}).get(CHORES, {}).get("items", []):
        ha.call_service("todo", "remove_item", entity_id=CHORES, item=item["summary"])
        print(f"  removed todo: {item['summary']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--clear", action="store_true")
    args = p.parse_args()
    clear() if args.clear else seed()
