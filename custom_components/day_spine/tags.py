"""Which tagged events fire, and when.

Free of Home Assistant imports for the same reason merge.py is: the rules about
what fires are the part that is easy to get wrong, and they need no running
instance to test. Self-contained for the same reason — the ISO parse below is a
copy rather than an import because both modules have to load on their own, by
path, without the package around them.

The rules, all of them settled in ROADMAP.md:

* A tag fires once, at the event's start. Nothing fires at the end, ever;
  coming back is its own calendar entry.
* Only a calendar carrying the `Dayline Control` label may fire. Default deny —
  a calendar you subscribe to tomorrow displays but cannot act.
* An event already under way when we first see it fires immediately. Without
  that, an all-day `#Away` — the most common real use there is — would never
  fire at all, because its start is midnight and midnight is always behind us.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Entry = dict[str, Any]

# What the chip on a row says the tags will do.
WILL_FIRE = "will_fire"
FIRED = "fired"
INERT = "inert"


@dataclass(frozen=True)
class Fire:
    """One `dayline_tag` event waiting to happen."""

    key: str
    tag: str
    entry: Entry
    when: datetime


@dataclass
class Plan:
    """Everything the coordinator has to do about tags this refresh."""

    now: list[Fire] = field(default_factory=list)
    later: list[Fire] = field(default_factory=list)
    states: dict[str, str] = field(default_factory=dict)


def fire_key(entry: Entry, tag: str) -> str:
    """What "fires once" is counted against.

    The entry id already carries the calendar and the start time, so an event
    moved to a new time is a new key and fires again — which is the right answer:
    it is a different intention about a different moment.
    """
    return f"{entry.get('id')}|{tag.lower()}"


def plan(
    entries: list[Entry],
    control: set[str],
    fired: set[str],
    now: datetime,
) -> Plan:
    """Decide, for one composed day, what fires and what the chips say."""
    out = Plan()
    for entry in entries:
        tags = entry.get("tags") or []
        if not tags:
            continue

        if entry.get("entity_id") not in control:
            # Displayed, and honestly labelled as decoration. The grey chip is
            # the whole point: someone who types `#vacation!` gets an answer
            # instead of silence, and silence is what makes people conclude a
            # system is broken and start working around it.
            out.states[entry["id"]] = INERT
            continue

        start = _parse(entry.get("start"))
        if start is None:
            out.states[entry["id"]] = INERT
            continue

        seen: list[str] = []
        for tag in tags:
            key = fire_key(entry, tag)
            if key in fired:
                seen.append(FIRED)
            elif start > now:
                out.later.append(Fire(key, tag, entry, start))
                seen.append(WILL_FIRE)
            elif _running(entry, now):
                out.now.append(Fire(key, tag, entry, now))
                seen.append(WILL_FIRE)
            else:
                # A tag whose moment passed while nobody was watching. It is not
                # fired retroactively, and the chip says as much.
                seen.append(INERT)

        # One chip state for the row, because every tag on it shares a calendar
        # and a start. Something still to come outranks something already done,
        # which outranks nothing at all.
        out.states[entry["id"]] = next(
            (s for s in (WILL_FIRE, FIRED, INERT) if s in seen), INERT
        )
    return out


def payload(fire: Fire) -> dict[str, Any]:
    """The `dayline_tag` event body.

    Deliberately the whole event and not just the tag: a condition like "unless
    someone is still home" belongs in the user's own automation, and it can only
    be written if the automation can see what it is reacting to.
    """
    entry = fire.entry
    return {
        "tag": fire.tag,
        "calendar": entry.get("entity_id"),
        "summary": entry.get("title"),
        "start": entry.get("start"),
        "end": entry.get("end"),
        "all_day": bool(entry.get("all_day")),
    }


def _running(entry: Entry, now: datetime) -> bool:
    """Is this event under way right now?

    An all-day event is under way for the whole day, and entries only ever
    describe today. A timed event with no end is a moment, not a span: if you
    missed it, you missed it.
    """
    if entry.get("all_day"):
        return True
    start, end = _parse(entry.get("start")), _parse(entry.get("end"))
    return start is not None and end is not None and start <= now < end


def _parse(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
