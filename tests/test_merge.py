"""Tests for the merge logic.

Runs without Home Assistant, which is the point of keeping merge.py free of HA
imports — the decisions that are easy to get wrong are the ones testable here.

    .venv/bin/python -m pytest tests -q
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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
attach_leave_by = merge.attach_leave_by
attach_weather = merge.attach_weather
dedupe = merge.dedupe
from_calendars = merge.from_calendars
from_sun = merge.from_sun
from_todo = merge.from_todo
remaining_count = merge.remaining_count
is_place = merge.is_place
split_tags = merge.split_tags
tags_seen = merge.tags_seen
travel_targets = merge.travel_targets
from_alarms = merge.from_alarms
_similar = merge._similar

TZ = timezone(timedelta(hours=-5))
NOW = datetime(2026, 9, 2, 14, 39, tzinfo=TZ)
DAY_START = datetime(2026, 9, 2, 0, 0, tzinfo=TZ)
NOISE = ["a", "an", "the", "at", "to", "for", "with", "and", "of", "appointment"]


def cfg(**kw) -> MergeConfig:
    base = dict(
        calendar_meta={
            "calendar.family": {"label": "Google", "priority": "normal"},
            "calendar.wife": {"label": "CalDAV", "priority": "normal"},
        },
        sentences=[{"match": "out of school", "automation": "Entry unlocks on her arrival"}],
        exclude=["Busy"],
        similarity=0.8,
        title_noise=NOISE,
        todo_entity="todo.household",
    )
    base.update(kw)
    return MergeConfig(**base)


def ev(start: str, summary: str, end: str | None = None, **kw):
    out = {"start": start, "summary": summary}
    if end:
        out["end"] = end
    out.update(kw)
    return out


# --- similarity -------------------------------------------------------------


def test_similarity_is_measured_against_the_longer_title():
    # The asymmetry is the whole point: every word of "Dentist" appears in the
    # longer title, but they are plainly not the same event.
    assert _similar("Dentist", "Dentist appointment for Kid at 4", NOISE) < 0.8
    assert _similar("Kid out of school", "Kid out of the school", NOISE) >= 0.8
    assert _similar("Standup", "Book club", NOISE) == 0.0


# --- calendars --------------------------------------------------------------


def test_excluded_titles_never_get_a_row():
    entries = from_calendars(
        cfg(), {"calendar.family": [ev("2026-09-02T13:00:00-05:00", "Busy")]}, DAY_START
    )
    assert entries == []


def test_all_day_events_are_pinned_to_the_start_of_the_day():
    entries = from_calendars(
        cfg(), {"calendar.family": [ev("2026-09-02", "Trash out tonight", "2026-09-03")]}, DAY_START
    )
    assert entries[0]["all_day"] is True
    assert entries[0]["start"] == DAY_START.isoformat()
    assert entries[0]["end"] is None


def test_sentence_map_attaches_the_house_sentence():
    entries = from_calendars(
        cfg(), {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "Kid out of school")]}, DAY_START
    )
    assert entries[0]["automation"] == "Entry unlocks on her arrival"


def test_schedule_calendar_uses_the_event_description():
    c = cfg(
        calendar_meta={"calendar.house": {"label": "House", "role": "schedule"}},
    )
    entries = from_calendars(
        c,
        {
            "calendar.house": [
                ev("2026-09-02T07:00:00-05:00", "Morning", description="Lights up, thermostat to 70")
            ]
        },
        DAY_START,
    )
    assert entries[0]["kind"] == "automation"
    assert entries[0]["automation"] == "Lights up, thermostat to 70"


def test_a_schedule_event_without_a_description_says_nothing_rather_than_guessing():
    c = cfg(calendar_meta={"calendar.house": {"label": "House", "role": "schedule"}})
    entries = from_calendars(c, {"calendar.house": [ev("2026-09-02T07:00:00-05:00", "Morning")]}, DAY_START)
    assert entries[0]["automation"] is None


def test_an_event_running_across_midnight_starts_the_day_rather_than_ending_it():
    """`calendar.get_events` returns everything overlapping the window, so a
    live instance handed back a 10:11 PM start for an event that ran into
    today. At clock resolution that reads as tonight, already missed."""
    entries = from_calendars(
        cfg(),
        {
            "calendar.family": [
                ev("2026-09-01T22:11:00-05:00", "Budget review", "2026-09-02T00:11:00-05:00"),
                ev("2026-09-01T20:00:00-05:00", "Ended yesterday", "2026-09-01T21:00:00-05:00"),
            ]
        },
        DAY_START,
    )
    assert [e["title"] for e in entries] == ["Budget review"]
    assert entries[0]["start"] == DAY_START.isoformat()
    assert entries[0]["end"] == "2026-09-02T00:11:00-05:00"


# --- dedupe -----------------------------------------------------------------


def test_near_duplicates_merge_and_keep_both_labels():
    entries = from_calendars(
        cfg(),
        {
            "calendar.family": [
                ev("2026-09-02T15:50:00-05:00", "Kid out of school", "2026-09-02T16:20:00-05:00")
            ],
            "calendar.wife": [
                ev("2026-09-02T15:50:00-05:00", "Kid out of the school", "2026-09-02T16:20:00-05:00")
            ],
        },
        DAY_START,
    )
    merged = dedupe(cfg(), entries)
    assert len(merged) == 1
    assert merged[0]["source"] == "Google + CalDAV"
    # first calendar listed supplies the wording
    assert merged[0]["title"] == "Kid out of school"
    assert merged[0]["merged_from"] == ["calendar.family", "calendar.wife"]


def test_merging_never_loses_the_sentence_or_the_higher_priority():
    a = {
        "id": "a", "start": "2026-09-02T15:50:00-05:00", "end": None, "title": "School run",
        "source": "Google", "priority": "normal", "automation": None, "entity_id": "calendar.family",
    }
    b = {
        "id": "b", "start": "2026-09-02T15:50:00-05:00", "end": None, "title": "School run",
        "source": "CalDAV", "priority": "high", "automation": "Doors unlock",
        "entity_id": "calendar.wife",
    }
    merged = dedupe(cfg(), [a, b])
    assert len(merged) == 1
    assert merged[0]["priority"] == "high"
    assert merged[0]["automation"] == "Doors unlock"


def test_same_title_at_different_times_stays_two_events():
    a = {"id": "a", "start": "2026-09-02T09:00:00-05:00", "end": None, "title": "Standup",
         "source": "Google", "entity_id": "calendar.family"}
    b = {"id": "b", "start": "2026-09-02T17:00:00-05:00", "end": None, "title": "Standup",
         "source": "Google", "entity_id": "calendar.family"}
    assert len(dedupe(cfg(), [a, b])) == 2


def test_same_start_but_different_end_stays_two_events():
    a = {"id": "a", "start": "2026-09-02T09:00:00-05:00", "end": "2026-09-02T09:30:00-05:00",
         "title": "Review", "source": "Google", "entity_id": "calendar.family"}
    b = {"id": "b", "start": "2026-09-02T09:00:00-05:00", "end": "2026-09-02T17:00:00-05:00",
         "title": "Review", "source": "CalDAV", "entity_id": "calendar.wife"}
    assert len(dedupe(cfg(), [a, b])) == 2


# --- sun --------------------------------------------------------------------


def test_sun_uses_todays_times_even_though_the_entity_reports_tomorrows():
    entries = from_sun(
        cfg(),
        next_rising=datetime(2026, 9, 3, 6, 58, tzinfo=TZ),   # already happened today
        next_setting=datetime(2026, 9, 2, 19, 47, tzinfo=TZ),  # still to come
        day_start=DAY_START,
    )
    starts = {e["title"]: e["start"] for e in entries}
    assert starts["Sunrise"].startswith("2026-09-02T06:58")
    assert starts["Sunset"].startswith("2026-09-02T19:47")


def test_sun_survives_a_utc_date_that_has_already_rolled_over():
    """The values below are verbatim from a live instance in America/Chicago.

    `sun.sun` publishes UTC. In summer, sunset after 19:00 local lands on
    tomorrow's UTC date, and comparing calendar dates dropped the row —
    silently, and only for the half of the year anyone is outside.
    """
    utc = timezone(timedelta(0))
    entries = from_sun(
        cfg(),
        next_rising=datetime(2026, 9, 3, 11, 36, 2, tzinfo=utc),   # 06:36 local today
        next_setting=datetime(2026, 9, 4, 0, 42, 8, tzinfo=utc),   # 19:42 local today
        day_start=DAY_START,
    )
    starts = {e["title"]: e["start"] for e in entries}
    assert set(starts) == {"Sunrise", "Sunset"}
    assert starts["Sunrise"].startswith("2026-09-02T06:36")
    assert starts["Sunset"].startswith("2026-09-02T19:42")


def test_sun_can_be_switched_off():
    assert from_sun(cfg(show_sun=False), datetime(2026, 9, 3, 6, 58, tzinfo=TZ), None, DAY_START) == []


# --- todo -------------------------------------------------------------------


def test_todo_items_are_sticky_and_carry_a_ready_made_action():
    entries = from_todo(
        cfg(),
        [
            {"uid": "abc", "summary": "Switch the laundry", "due": "2026-09-02T14:01:00-05:00"},
            {"uid": "def", "summary": "No due date"},
        ],
        DAY_START,
    )
    assert len(entries) == 1
    assert entries[0]["sticky"] is True
    assert entries[0]["action"]["service"] == "todo.update_item"
    assert entries[0]["action"]["data"]["item"] == "abc"


# --- weather ----------------------------------------------------------------


def test_forecast_attaches_to_upcoming_entries_only():
    entries = [
        {"start": "2026-09-02T09:00:00-05:00", "title": "past"},
        {"start": "2026-09-02T15:50:00-05:00", "title": "future"},
        {"start": DAY_START.isoformat(), "title": "all day", "all_day": True},
    ]
    forecast = [
        {"datetime": "2026-09-02T09:00:00-05:00", "condition": "sunny", "temperature": 70},
        {"datetime": "2026-09-02T16:00:00-05:00", "condition": "rainy", "temperature": 63,
         "precipitation_probability": 70},
    ]
    out = attach_weather(entries, forecast, NOW)
    assert "weather" not in out[0]
    assert out[1]["weather"]["condition"] == "rainy"
    assert "weather" not in out[2]


# --- counting ---------------------------------------------------------------


def test_running_events_count_as_still_to_come():
    entries = [
        {"start": "2026-09-02T09:00:00-05:00", "end": "2026-09-02T09:30:00-05:00", "title": "done"},
        {"start": "2026-09-02T14:00:00-05:00", "end": "2026-09-02T17:00:00-05:00", "title": "running"},
        {"start": "2026-09-02T18:00:00-05:00", "end": None, "title": "later"},
        {"start": "2026-09-02T08:00:00-05:00", "end": None, "title": "overdue", "sticky": True},
        {"start": "2026-09-02T14:36:00-05:00", "end": None, "title": "just happened", "kind": "event"},
    ]
    assert remaining_count(entries, NOW) == 3


def test_todo_due_after_today_is_not_on_todays_spine():
    """A live instance had a to-do due at 02:51 tomorrow rendering as a bare
    "2:51 AM" row, which reads as this morning — i.e. as already missed."""
    items = [
        {"uid": "today", "summary": "Switch the laundry", "due": "2026-09-02T23:11:00-05:00"},
        {"uid": "tomorrow", "summary": "Refill the softener", "due": "2026-09-03T02:51:00-05:00"},
        {"uid": "overdue", "summary": "Bins, yesterday", "due": "2026-09-01T18:00:00-05:00"},
    ]
    titles = {e["title"] for e in from_todo(cfg(todo_entity="todo.x"), items, DAY_START)}
    assert titles == {"Switch the laundry", "Bins, yesterday"}


# --- tags -------------------------------------------------------------------


def test_tags_come_out_of_the_title_and_the_words_stay():
    assert split_tags("Portland trip #Away") == ("Portland trip", ["Away"])
    assert split_tags("#Away Portland trip") == ("Portland trip", ["Away"])
    assert split_tags("Weekend #Away #Quiet") == ("Weekend", ["Away", "Quiet"])


def test_tag_matching_is_loose_because_real_tags_are_messy():
    # A calendar someone else keeps will not spell it the way we would.
    assert split_tags("Winter break #vacation!") == ("Winter break", ["vacation"])
    assert split_tags("Trip #AWAY, then home") == ("Trip then home", ["AWAY"])
    # Same tag twice is one tag, whatever the casing.
    assert split_tags("#away trip #Away") == ("trip", ["away"])


def test_a_number_after_a_hash_is_not_a_tag():
    """"Room #3" and "#1 priority" are how people write, not how they tag."""
    assert split_tags("Meet in Room #3") == ("Meet in Room #3", [])
    assert split_tags("#1 priority") == ("#1 priority", [])


def test_an_event_titled_only_a_tag_still_renders_as_something():
    assert split_tags("#Away") == ("#Away", ["Away"])


def test_tagging_an_event_does_not_disturb_anything_that_reads_its_title():
    """Adding a tag must not change the id, the sentence match or the dedupe —
    it is metadata about the event, not a different event."""
    plain = from_calendars(
        cfg(), {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "Kid out of school")]},
        DAY_START,
    )[0]
    tagged = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "Kid out of school #Away")]},
        DAY_START,
    )[0]
    assert tagged["title"] == plain["title"]
    assert tagged["id"] == plain["id"]
    assert tagged["automation"] == plain["automation"] == "Entry unlocks on her arrival"
    assert tagged["tags"] == ["Away"]
    assert "tags" not in plain  # omitted, not empty — this rides to every browser


def test_exclusions_are_matched_against_the_title_without_its_tags():
    entries = from_calendars(
        cfg(), {"calendar.family": [ev("2026-09-02T13:00:00-05:00", "Busy #Away")]}, DAY_START
    )
    assert entries == []


def test_the_same_event_from_two_calendars_still_dedupes_when_one_is_tagged():
    entries = dedupe(
        cfg(),
        from_calendars(
            cfg(),
            {
                "calendar.family": [ev("2026-09-02T18:00:00-05:00", "Book club #Quiet")],
                "calendar.wife": [ev("2026-09-02T18:00:00-05:00", "Book club")],
            },
            DAY_START,
        ),
    )
    assert len(entries) == 1


def test_tags_seen_is_the_days_vocabulary_lowercased_and_in_order():
    entries = [
        {"tags": ["Away", "Quiet"]},
        {"tags": ["away"]},
        {"title": "no tags here"},
        {"tags": ["Guests"]},
    ]
    assert tags_seen(entries) == ["away", "quiet", "guests"]


def test_merging_never_loses_a_tag_that_was_only_on_one_copy():
    """Only one person keeping a shared event needs to have tagged it. The
    first calendar still supplies the wording — a tag is not wording."""
    entries = dedupe(
        cfg(),
        from_calendars(
            cfg(),
            {
                "calendar.family": [ev("2026-09-02T18:00:00-05:00", "Book club")],
                "calendar.wife": [ev("2026-09-02T18:00:00-05:00", "Book club #Quiet")],
            },
            DAY_START,
        ),
    )
    assert len(entries) == 1
    assert entries[0]["title"] == "Book club"
    assert entries[0]["tags"] == ["Quiet"]


# --- scale -----------------------------------------------------------------


def test_merging_two_thousand_entries_does_not_go_quadratic() -> None:
    """One enthusiast with a lot of calendars is not a hypothetical.

    Bounded by the match window rather than by the size of the day: nothing
    starting more than a minute earlier can be the same event, and `kept` is in
    start order, so the scan stops instead of walking the whole day for every
    row.
    """
    import time

    entries = [
        {
            "id": f"cal:x:{i}",
            "start": (DAY_START + timedelta(seconds=i * 30)).isoformat(),
            "end": None,
            "all_day": False,
            "kind": "calendar",
            "source": "Google",
            "title": f"Event number {i}",
            "entity_id": "calendar.x",
        }
        for i in range(2000)
    ]
    cfg = MergeConfig(similarity=0.8, title_noise=[])

    began = time.perf_counter()
    kept = dedupe(cfg, entries)
    elapsed = time.perf_counter() - began

    assert len(kept) == 2000
    # Generous on purpose — this is a guard against the quadratic scan coming
    # back, not a benchmark. The unbounded version takes tens of seconds here.
    assert elapsed < 2.0, f"dedupe took {elapsed:.1f}s for 2000 entries"


def test_the_window_still_folds_what_it_should_at_scale() -> None:
    """The early break must not cost a real merge: the same event on two
    calendars, in the middle of a crowded day, still becomes one row."""
    entries = []
    for i in range(500):
        start = (DAY_START + timedelta(seconds=i * 30)).isoformat()
        entries.append({
            "id": f"cal:a:{i}", "start": start, "end": None, "all_day": False,
            "kind": "calendar", "source": "Google", "title": f"Event number {i}",
            "entity_id": "calendar.a",
        })
    entries.append({
        "id": "cal:b:250",
        "start": (DAY_START + timedelta(seconds=250 * 30 + 20)).isoformat(),
        "end": None, "all_day": False, "kind": "calendar", "source": "CalDAV",
        "title": "Event number 250", "entity_id": "calendar.b",
    })

    kept = dedupe(MergeConfig(similarity=0.8, title_noise=[]), entries)

    assert len(kept) == 500
    folded = [e for e in kept if e["title"] == "Event number 250"]
    assert folded[0]["source"] == "Google + CalDAV"


# ---------------------------------------------------------------------------
# calendar colour — the "who" axis
# ---------------------------------------------------------------------------


def test_a_calendars_colour_rides_along_on_its_entries():
    c = cfg(
        calendar_meta={
            "calendar.family": {"label": "Google", "color": "blue"},
            "calendar.wife": {"label": "CalDAV", "color": "teal"},
        }
    )
    out = from_calendars(
        c,
        {
            "calendar.family": [ev("2026-09-02T15:50:00-05:00", "School run")],
            "calendar.wife": [ev("2026-09-02T18:00:00-05:00", "Night shift")],
        },
        DAY_START,
    )
    assert [e["color"] for e in out] == ["blue", "teal"]


def test_no_colour_means_no_key_at_all():
    """Omitted rather than empty. This payload is re-sent to every open browser
    on each refresh, and most people will never colour a calendar."""
    out = from_calendars(
        cfg(calendar_meta={"calendar.family": {"label": "Google"}}),
        {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "School run")]},
        DAY_START,
    )
    assert "color" not in out[0]


def test_the_default_choice_is_not_a_colour():
    """`default` is what the dropdown starts on, not a palette entry — it has to
    mean the same as never having chosen."""
    out = from_calendars(
        cfg(calendar_meta={"calendar.family": {"label": "Google", "color": "default"}}),
        {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "School run")]},
        DAY_START,
    )
    assert "color" not in out[0]


def test_a_deduped_event_keeps_the_first_calendars_colour():
    """Wording follows the first calendar listed, and colour is wording: one row
    cannot be two colours, and the alternative is that it changes depending on
    which copy happened to sort first."""
    c = cfg(
        calendar_meta={
            "calendar.family": {"label": "Google", "color": "blue"},
            "calendar.wife": {"label": "CalDAV", "color": "teal"},
        }
    )
    out = from_calendars(
        c,
        {
            "calendar.family": [ev("2026-09-02T19:00:00-05:00", "Dinner with the neighbours")],
            "calendar.wife": [ev("2026-09-02T19:00:00-05:00", "Dinner with the neighbours")],
        },
        DAY_START,
    )
    kept = dedupe(c, out)
    assert len(kept) == 1
    assert kept[0]["color"] == "blue"
    assert kept[0]["source"] == "Google + CalDAV"


# ---------------------------------------------------------------------------
# leaving in time
# ---------------------------------------------------------------------------


def _at(hour: int, minute: int = 0) -> str:
    return datetime(2026, 9, 2, hour, minute, tzinfo=TZ).isoformat()


def test_an_events_location_reaches_the_entry():
    out = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02T16:00:00-05:00", "Dentist", location="12 Main St")]},
        DAY_START,
    )
    assert out[0]["location"] == "12 Main St"


def test_an_event_with_no_location_does_not_carry_an_empty_one():
    """The payload is re-sent to every open browser on every refresh, and most
    events will never have a location."""
    out = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02T16:00:00-05:00", "Dentist", location="  ")]},
        DAY_START,
    )
    assert "location" not in out[0]


def test_things_that_are_not_places_are_never_routed_to():
    for text in ("Zoom", "https://meet.example/abc", "TBD", "Google Meet", "Home", "x"):
        assert not is_place(text), text
    for text in ("12 Main St", "O'Hare International Airport", "41.88, -87.62"):
        assert is_place(text), text


def test_targets_are_the_soonest_few_places_still_ahead():
    entries = [
        {"start": _at(9), "kind": "calendar", "location": "Past Place"},
        {"start": _at(16), "kind": "calendar", "location": "Dentist St"},
        {"start": _at(18), "kind": "calendar", "location": "Zoom"},
        {"start": _at(19), "kind": "calendar", "location": "School Rd"},
        {"start": _at(20), "kind": "calendar", "location": "Late Ave"},
        {"start": _at(21), "kind": "calendar"},
    ]
    got = travel_targets(entries, NOW, limit=2)
    assert [location for location, _ in got] == ["Dentist St", "School Rd"]


def test_the_same_place_twice_is_one_lookup():
    entries = [
        {"start": _at(16), "kind": "calendar", "location": "Dentist St"},
        {"start": _at(18), "kind": "calendar", "location": "dentist st"},
    ]
    assert len(travel_targets(entries, NOW)) == 1


def test_leave_by_is_the_start_less_the_drive_and_the_buffer():
    entries = [
        {"start": _at(16), "kind": "calendar", "location": "Dentist St"},
    ]
    attach_leave_by(entries, {"dentist st": {"minutes": 25.4, "route": "I-90 W"}}, buffer_minutes=10)
    # 25.4 minutes is rounded up, not to the nearest: being early is free.
    assert entries[0]["leave_by"] == _at(15, 24)
    assert entries[0]["travel"] == {"minutes": 26, "buffer": 10, "route": "I-90 W"}


def test_a_place_the_router_could_not_price_says_nothing_at_all():
    """A missing leave-by line is a card that is quiet. A wrong one makes you
    late, which is the only thing this feature exists to prevent."""
    entries = [{"start": _at(16), "kind": "calendar", "location": "Kid\'s school"}]
    attach_leave_by(entries, {})
    assert "leave_by" not in entries[0]
    attach_leave_by(entries, {"somewhere else": {"minutes": 10}})
    assert "leave_by" not in entries[0]


def test_an_all_day_event_is_never_given_a_departure_time():
    entries = [
        {"start": _at(0), "all_day": True, "kind": "calendar", "location": "Dentist St"},
    ]
    attach_leave_by(entries, {"dentist st": {"minutes": 25}})
    assert "leave_by" not in entries[0]


# ---------------------------------------------------------------------------
# alarms
# ---------------------------------------------------------------------------


def _alarm(when: str, **extra) -> dict:
    row = {"entity_id": "sensor.pixel_6a_next_alarm", "label": "Pixel 6a", "start": when}
    row.update(extra)
    return row


def _tomorrow(hour: int, minute: int = 0) -> str:
    return datetime(2026, 9, 3, hour, minute, tzinfo=TZ).isoformat()


def test_an_alarm_later_today_is_an_ordinary_row():
    out = from_alarms(cfg(), [_alarm(_at(22, 45))], NOW, DAY_START)
    assert len(out) == 1
    assert out[0]["start"] == _at(22, 45)
    assert out[0]["kind"] == "alarm"
    assert out[0]["title"] == "Alarm"
    assert out[0]["source"] == "Pixel 6a"
    # Never allowed to crowd out a real event.
    assert out[0]["priority"] == "low"
    # It is part of today, so it is shown as part of today.
    assert "when_empty" not in out[0]


def test_tomorrows_alarm_is_held_back_until_the_day_is_spent():
    """The whole point of the feature. Tomorrow's 6:30 has no business sitting
    above tonight's dinner, but at 11pm it is the only thing left worth saying."""
    out = from_alarms(cfg(), [_alarm(_tomorrow(6, 30))], NOW, DAY_START)
    assert len(out) == 1
    assert out[0]["when_empty"] is True


def test_an_alarm_beyond_the_horizon_is_dropped_entirely():
    """The sensor reports the next alarm wherever it is. Without the cap, one
    set for Monday would sit on a Friday-night panel announcing Monday."""
    out = from_alarms(cfg(), [_alarm(_tomorrow(9, 0))], NOW, DAY_START)
    assert out == []
    # ...and the boundary is honoured rather than approximated.
    assert from_alarms(cfg(), [_alarm(_tomorrow(6, 38))], NOW, DAY_START) != []
    assert from_alarms(cfg(), [_alarm(_tomorrow(6, 40))], NOW, DAY_START) == []


def test_the_horizon_is_configurable():
    late = [_alarm(_tomorrow(9, 0))]
    assert from_alarms(cfg(alarm_horizon=24), late, NOW, DAY_START) != []
    assert from_alarms(cfg(alarm_horizon=0), late, NOW, DAY_START) == []


def test_an_alarm_that_has_already_gone_off_is_not_news():
    """The sensor keeps reporting one after it rings. A struck-through alarm row
    is a fact about the past nobody asked for."""
    assert from_alarms(cfg(), [_alarm(_at(7, 0))], NOW, DAY_START) == []


def test_the_package_filter_is_off_by_default_and_exact_when_set():
    rows = [_alarm(_at(22, 45), package="com.android.deskclock")]
    assert len(from_alarms(cfg(), rows, NOW, DAY_START)) == 1
    assert from_alarms(cfg(alarm_packages=["com.android.deskclock"]), rows, NOW, DAY_START)
    # A bedtime reminder from another app is exactly what the filter is for.
    assert from_alarms(cfg(alarm_packages=["com.android.deskclock"]),
                       [_alarm(_at(22, 45), package="com.google.android.wellbeing")],
                       NOW, DAY_START) == []


def test_the_package_filter_ignores_case_because_it_is_typed_by_hand():
    rows = [_alarm(_at(22, 45), package="com.android.deskclock")]
    assert from_alarms(cfg(alarm_packages=["  COM.Android.Deskclock "]), rows, NOW, DAY_START)


def test_the_package_reaches_the_entry_so_a_mystery_row_can_be_identified():
    out = from_alarms(cfg(), [_alarm(_at(22, 45), package="com.android.deskclock")],
                      NOW, DAY_START)
    assert out[0]["package"] == "com.android.deskclock"


def test_a_naive_timestamp_is_read_as_local_not_as_the_process_timezone():
    naive = datetime(2026, 9, 2, 22, 45).isoformat()
    out = from_alarms(cfg(), [_alarm(naive)], NOW, DAY_START)
    assert out[0]["start"] == _at(22, 45)


def test_several_phones_each_get_their_own_row():
    out = from_alarms(
        cfg(),
        [
            _alarm(_at(22, 45)),
            {"entity_id": "sensor.pixel_9_next_alarm", "label": "Wife", "start": _at(23, 0)},
        ],
        NOW,
        DAY_START,
    )
    assert [e["source"] for e in out] == ["Pixel 6a", "Wife"]
    assert len({e["id"] for e in out}) == 2


def test_junk_from_the_sensor_is_skipped_not_raised():
    out = from_alarms(cfg(), [_alarm(""), _alarm("not a time"), _alarm(_at(22, 45))],
                      NOW, DAY_START)
    assert len(out) == 1


def test_tomorrows_alarm_is_not_counted_as_left_today():
    """The headline says "N left today". A row that only appears once the day is
    spent is the thing after the last of them, not one of them."""
    entries = [
        {"start": _at(22), "kind": "calendar"},
        {"start": _tomorrow(6, 30), "kind": "alarm", "when_empty": True},
    ]
    assert remaining_count(entries, NOW) == 1


# --- the evening pivot ------------------------------------------------------

DAY_END = DAY_START + timedelta(days=1)
# The pivot only ever speaks once today is spent, so these ask it at ten at
# night. Asked at 2:39pm a 16-hour horizon reaches 6:39 tomorrow morning, which
# is correct and is not the question anyone is asking mid-afternoon.
EVENING = datetime(2026, 9, 2, 22, 0, tzinfo=TZ)


def test_without_a_day_end_nothing_is_marked_or_dropped():
    # Which day an event belongs to is the fetch window's business, not this
    # function's: it has always rendered whatever it was handed. Passing no
    # `day_end` has to leave that exactly as it was.
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-03T07:00:00-05:00", "Standup")]},
        DAY_START,
    )
    assert len(entries) == 1
    assert "when_empty" not in entries[0]


def test_tomorrows_event_is_held_back_until_the_day_is_spent():
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-03T07:00:00-05:00", "Standup")]},
        DAY_START,
        DAY_END,
        EVENING,
    )
    assert len(entries) == 1
    assert entries[0]["when_empty"] is True
    assert entries[0]["title"] == "Standup"


def test_todays_events_are_never_marked_held_back():
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02T15:50:00-05:00", "Kid out of school")]},
        DAY_START,
        DAY_END,
        EVENING,
    )
    assert "when_empty" not in entries[0]


def test_tomorrow_beyond_the_horizon_is_dropped():
    # 16 hours from ten at night reaches two tomorrow afternoon. A dinner
    # tomorrow evening is true and is not what an evening panel is being asked.
    entries = from_calendars(
        cfg(),
        {
            "calendar.family": [
                ev("2026-09-03T06:00:00-05:00", "Early start"),
                ev("2026-09-03T19:00:00-05:00", "Dinner tomorrow"),
            ]
        },
        DAY_START,
        DAY_END,
        EVENING,
    )
    assert [e["title"] for e in entries] == ["Early start"]


def test_an_all_day_event_tomorrow_is_not_pinned_to_today():
    # The bug this guards: an all-day entry is pinned to the start of the day,
    # so tomorrow's would have been drawn at midnight this morning.
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-03", "Bin day", "2026-09-04")]},
        DAY_START,
        DAY_END,
        EVENING,
    )
    assert entries == []


def test_todays_all_day_event_still_pins_to_today():
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02", "Trash out tonight", "2026-09-03")]},
        DAY_START,
        DAY_END,
        EVENING,
    )
    assert entries[0]["start"] == DAY_START.isoformat()


# --- free time --------------------------------------------------------------

from_gaps = merge.from_gaps


def _gaps(events, now=NOW, **kw):
    entries = from_calendars(cfg(**kw), {"calendar.family": events}, DAY_START)
    return from_gaps(cfg(**kw), entries, now)


def test_a_clear_afternoon_gets_a_row():
    gaps = _gaps(
        [
            ev("2026-09-02T12:00:00-05:00", "Lunch", "2026-09-02T13:00:00-05:00"),
            ev("2026-09-02T17:00:00-05:00", "Dentist"),
        ],
        now=datetime(2026, 9, 2, 11, 0, tzinfo=TZ),
    )
    assert [g["title"] for g in gaps] == ["4h free"]
    assert gaps[0]["kind"] == "gap"
    assert gaps[0]["priority"] == "low"


def test_a_gap_is_measured_from_now_not_from_the_last_event():
    # Half the afternoon is already gone; the row has to say what is left of it,
    # not what it was at lunchtime.
    gaps = _gaps(
        [
            ev("2026-09-02T12:00:00-05:00", "Lunch", "2026-09-02T13:00:00-05:00"),
            ev("2026-09-02T17:00:00-05:00", "Dentist"),
        ],
        now=datetime(2026, 9, 2, 15, 0, tzinfo=TZ),
    )
    assert [g["title"] for g in gaps] == ["2h free"]


def test_a_gap_that_has_passed_is_not_free_time():
    gaps = _gaps(
        [
            ev("2026-09-02T08:00:00-05:00", "School run", "2026-09-02T08:30:00-05:00"),
            ev("2026-09-02T11:00:00-05:00", "Standup"),
        ],
        now=datetime(2026, 9, 2, 14, 0, tzinfo=TZ),
    )
    assert gaps == []


def test_short_gaps_are_not_worth_saying():
    gaps = _gaps(
        [
            ev("2026-09-02T15:00:00-05:00", "Call", "2026-09-02T15:30:00-05:00"),
            ev("2026-09-02T16:00:00-05:00", "Call two"),
        ],
        now=datetime(2026, 9, 2, 14, 0, tzinfo=TZ),
    )
    assert gaps == []


def test_an_event_inside_another_does_not_reopen_the_gap():
    # A class runs all afternoon and a call sits inside it. The afternoon is not
    # free, and a naive walk would have called the space after the call free.
    gaps = _gaps(
        [
            ev("2026-09-02T13:00:00-05:00", "Class", "2026-09-02T18:00:00-05:00"),
            ev("2026-09-02T14:00:00-05:00", "Call", "2026-09-02T14:15:00-05:00"),
        ],
        now=datetime(2026, 9, 2, 12, 0, tzinfo=TZ),
    )
    assert gaps == []


def test_only_calendar_events_count_as_commitments():
    # Sunset is not somewhere you have to be, so it must not carve the evening
    # in two.
    entries = from_calendars(
        cfg(),
        {"calendar.family": [ev("2026-09-02T20:00:00-05:00", "Dinner")]},
        DAY_START,
    )
    entries += from_sun(cfg(), None, datetime(2026, 9, 2, 19, 47, tzinfo=TZ), DAY_START)
    gaps = from_gaps(cfg(), entries, datetime(2026, 9, 2, 17, 0, tzinfo=TZ))
    assert gaps == []


def test_free_time_is_not_counted_among_what_is_left_today():
    entries = from_calendars(
        cfg(),
        {
            "calendar.family": [
                ev("2026-09-02T12:00:00-05:00", "Lunch", "2026-09-02T13:00:00-05:00"),
                ev("2026-09-02T17:00:00-05:00", "Dentist"),
            ]
        },
        DAY_START,
    )
    now = datetime(2026, 9, 2, 11, 0, tzinfo=TZ)
    entries += from_gaps(cfg(), entries, now)
    assert remaining_count(entries, now) == 2


def test_gap_durations_read_the_way_a_countdown_does():
    assert merge._spell(160) == "2h 40m"
    assert merge._spell(180) == "3h"
    assert merge._spell(95) == "1h 35m"
    assert merge._spell(45) == "45m"
