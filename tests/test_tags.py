"""Tests for the tag firing rules.

Runs without Home Assistant, like test_merge.py and for the same reason: what
fires the house into Away mode is the last thing that should only be testable by
trying it on a live instance.

    .venv/bin/python -m pytest tests -q
"""

from __future__ import annotations

import importlib.util as _il
import sys as _sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = _il.spec_from_file_location(
    "day_spine_tags", ROOT / "custom_components" / "day_spine" / "tags.py"
)
tags = _il.module_from_spec(_spec)
assert _spec.loader is not None
_sys.modules[_spec.name] = tags
_spec.loader.exec_module(tags)

plan = tags.plan
payload = tags.payload
fire_key = tags.fire_key
FIRED, WILL_FIRE, INERT = tags.FIRED, tags.WILL_FIRE, tags.INERT

TZ = timezone(timedelta(hours=-5))
NOW = datetime(2026, 9, 3, 14, 39, tzinfo=TZ)
CONTROL = {"calendar.admin"}


def event(
    start: datetime,
    *,
    tags_: list[str] | None = None,
    end: datetime | None = None,
    entity_id: str = "calendar.admin",
    all_day: bool = False,
    eid: str = "cal:1",
) -> dict:
    entry = {
        "id": eid,
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "all_day": all_day,
        "kind": "calendar",
        "title": "Portland trip",
        "entity_id": entity_id,
    }
    if tags_:
        entry["tags"] = tags_
    return entry


# --- what fires ------------------------------------------------------------


def test_a_tag_still_to_come_is_scheduled_not_fired() -> None:
    result = plan([event(NOW + timedelta(hours=2), tags_=["Away"])], CONTROL, set(), NOW)

    assert result.now == []
    assert [f.tag for f in result.later] == ["Away"]
    assert result.later[0].when == NOW + timedelta(hours=2)
    assert result.states["cal:1"] == WILL_FIRE


def test_an_all_day_tag_fires_even_though_midnight_has_passed() -> None:
    """The common case: `#Away all weekend`, seen for the first time at 2pm.

    An all-day event starts at midnight, and midnight is always behind us.
    Scheduling only future starts would mean this never fires at all.
    """
    day_start = datetime(2026, 9, 3, 0, 0, tzinfo=TZ)
    result = plan([event(day_start, tags_=["Away"], all_day=True)], CONTROL, set(), NOW)

    assert [f.tag for f in result.now] == ["Away"]
    assert result.later == []


def test_an_event_under_way_fires_but_a_moment_that_passed_does_not() -> None:
    running = event(NOW - timedelta(minutes=30), end=NOW + timedelta(minutes=30), tags_=["Away"])
    over = event(NOW - timedelta(hours=3), tags_=["Home"], eid="cal:2")

    result = plan([running, over], CONTROL, set(), NOW)

    assert [f.tag for f in result.now] == ["Away"]
    assert result.states["cal:1"] == WILL_FIRE
    assert result.states["cal:2"] == INERT


def test_a_tag_that_already_fired_does_not_fire_again() -> None:
    entry = event(NOW + timedelta(hours=2), tags_=["Away"])
    already = {fire_key(entry, "Away")}

    result = plan([entry], CONTROL, already, NOW)

    assert result.now == [] and result.later == []
    assert result.states["cal:1"] == FIRED


def test_moving_an_event_makes_it_a_new_fire() -> None:
    """The id carries the start time, so a rescheduled event fires at its new
    time — which is right: it is a different intention about a different
    moment."""
    first = event(NOW + timedelta(hours=1), tags_=["Away"], eid="cal:admin:09:00:Portland")
    moved = event(NOW + timedelta(hours=3), tags_=["Away"], eid="cal:admin:11:00:Portland")

    assert fire_key(first, "Away") != fire_key(moved, "Away")


def test_two_tags_on_one_event_fire_separately() -> None:
    result = plan(
        [event(NOW + timedelta(hours=1), tags_=["Away", "Quiet"])], CONTROL, set(), NOW
    )

    assert sorted(f.tag for f in result.later) == ["Away", "Quiet"]


def test_case_is_not_what_makes_two_fires() -> None:
    entry = event(NOW + timedelta(hours=1), tags_=["Away"])
    assert fire_key(entry, "away") == fire_key(entry, "AWAY")


# --- what does not fire ----------------------------------------------------


def test_a_calendar_without_the_control_label_cannot_act() -> None:
    """Default deny, and the row says so rather than going quiet.

    This is what stops a `#vacation!` on a school calendar from setting the
    house to 62 degrees over winter break.
    """
    entry = event(NOW + timedelta(hours=1), tags_=["vacation"], entity_id="calendar.kid")

    result = plan([entry], CONTROL, set(), NOW)

    assert result.now == [] and result.later == []
    assert result.states["cal:1"] == INERT


def test_untagged_events_get_no_chip_state_at_all() -> None:
    result = plan([event(NOW + timedelta(hours=1))], CONTROL, set(), NOW)

    assert result.states == {}


def test_nothing_fires_at_the_end_of_an_event() -> None:
    """Settled, and the reason there is no end handling to test around: coming
    back is its own calendar entry."""
    entry = event(NOW - timedelta(hours=2), end=NOW - timedelta(minutes=1), tags_=["Away"])

    result = plan([entry], CONTROL, set(), NOW)

    assert result.now == [] and result.later == []


def test_an_unparseable_start_is_inert_rather_than_a_crash() -> None:
    entry = event(NOW, tags_=["Away"])
    entry["start"] = "not a time"

    result = plan([entry], CONTROL, set(), NOW)

    assert result.states["cal:1"] == INERT
    assert result.now == [] and result.later == []


# --- the payload -----------------------------------------------------------


def test_the_event_carries_enough_to_write_a_condition_against() -> None:
    entry = event(NOW + timedelta(hours=1), end=NOW + timedelta(hours=3), tags_=["Away"])

    body = payload(plan([entry], CONTROL, set(), NOW).later[0])

    assert body == {
        "tag": "Away",
        "calendar": "calendar.admin",
        "summary": "Portland trip",
        "start": entry["start"],
        "end": entry["end"],
        "all_day": False,
    }


def test_the_tag_is_carried_as_typed() -> None:
    """Matching is loose and binding is exact, so the automation compares
    lowercased — but what we hand it is what the person wrote."""
    entry = event(NOW + timedelta(hours=1), tags_=["AwayForTheWeekend"])

    assert payload(plan([entry], CONTROL, set(), NOW).later[0])["tag"] == "AwayForTheWeekend"
