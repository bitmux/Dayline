"""Building one day's spine out of several sources.

Deliberately free of any Home Assistant import. Everything here takes plain data
and returns plain data, which is what makes it testable without a running
instance — see tests/test_merge.py. The integration's job is to fetch; this
module's job is to decide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

Entry = dict[str, Any]

_PRIORITY_ORDER = {"low": 0, "normal": 1, "high": 2}
_WORD_RE = re.compile(r"[^a-z0-9 ]+")

# A leading letter is required, which keeps "Room #3" and "#1 priority" out.
_TAG_RE = re.compile(r"(^|\s)#([A-Za-z][A-Za-z0-9_-]*)[!?.,;:]*")


@dataclass
class MergeConfig:
    """Everything the merge needs to know, all of it user-editable in the UI."""

    calendar_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    sentences: list[dict[str, Any]] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    show_sun: bool = True
    sun_priority: str = "low"
    similarity: float = 0.8
    title_noise: list[str] = field(default_factory=list)
    todo_entity: str | None = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _match_sentence(cfg: MergeConfig, title: str) -> dict[str, Any]:
    """First sentence whose `match` appears in the title. First wins, so the
    order of the list is the order of precedence — visible in the UI."""
    low = title.lower()
    for rule in cfg.sentences:
        match = str(rule.get("match", "")).strip().lower()
        if match and match in low:
            return rule
    return {}


def split_tags(title: str) -> tuple[str, list[str]]:
    """Separate `#tags` from the words of an event title.

    A calendar event belongs to whoever provides the calendar, so the only place
    to put metadata on one is in text a person types anyway. `#Away` is that.

    Matching is loose because real tags are messy — any position, any case,
    trailing punctuation tolerated, so `#vacation!` yields `vacation`. Binding,
    when it exists, will be exact.

    Returns the title with the tags lifted out, and the tags as typed. Lifted
    out, not discarded: the card draws them as chips, because seeing `#Away` is
    how you know what the house is about to do. Taking them out of the string is
    what keeps them away from the dedupe, the sentence match and the entry id —
    none of which should notice a tag being added to an event they already know.
    """
    tags: list[str] = []
    seen: set[str] = set()
    for _, tag in _TAG_RE.findall(title):
        if tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    if not tags:
        return title, []
    stripped = " ".join(_TAG_RE.sub(lambda m: m.group(1), title).split())
    # An event titled nothing but tags still has to render as something.
    return (stripped or title), tags


def tags_seen(entries: list[Entry]) -> list[str]:
    """Every distinct tag on the day, lowercased, in the order first seen.

    This is the discovery surface: nobody can bind a tag they have not been
    shown, and asking someone to declare their vocabulary up front is exactly
    the setup this design is trying to delete.
    """
    out: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        for tag in entry.get("tags") or []:
            low = tag.lower()
            if low not in seen:
                seen.add(low)
                out.append(low)
    return out


def _excluded(cfg: MergeConfig, title: str) -> bool:
    low = title.lower()
    return any(bad.strip().lower() in low for bad in cfg.exclude if bad.strip())


def _words(title: str, noise: Iterable[str]) -> list[str]:
    stripped = _WORD_RE.sub("", title.lower())
    drop = {n.lower() for n in noise}
    return [w for w in stripped.split() if w and w not in drop]


def _similar(a: str, b: str, noise: Iterable[str]) -> float:
    """Word overlap measured against the *longer* title.

    Measuring both ways is what stops "Dentist" from swallowing "Dentist
    appointment for Kid at 4": they share every word of the shorter title but
    only a third of the longer one.
    """
    wa, wb = _words(a, noise), _words(b, noise)
    if not wa or not wb:
        return 0.0
    shared = len(set(wa) & set(wb))
    return shared / max(len(set(wa)), len(set(wb)))


def _higher(a: str | None, b: str | None) -> str:
    pa = _PRIORITY_ORDER.get(a or "normal", 1)
    pb = _PRIORITY_ORDER.get(b or "normal", 1)
    return (a or "normal") if pa >= pb else (b or "normal")


# How far apart two copies of "the same event" are allowed to start.
_WINDOW = 60


def _within(a: datetime | None, b: datetime | None, seconds: int = _WINDOW) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs((a - b).total_seconds()) < seconds


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def from_calendars(
    cfg: MergeConfig,
    events_by_entity: dict[str, list[dict[str, Any]]],
    day_start: datetime,
) -> list[Entry]:
    """Calendar events, in the order the calendars were configured.

    That order matters: when two calendars carry the same event with different
    wording, the first one listed supplies the words.
    """
    out: list[Entry] = []
    for entity_id, meta in cfg.calendar_meta.items():
        is_schedule = meta.get("role") == "schedule"
        for ev in events_by_entity.get(entity_id, []):
            title = str(ev.get("summary") or "(untitled)").strip()
            # Before anything reads the title: exclusion, sentence matching, the
            # id and the dedupe should all behave identically whether or not
            # somebody has tagged the event.
            title, tags = split_tags(title)
            if _excluded(cfg, title):
                continue
            raw_start = str(ev.get("start", ""))
            all_day = "T" not in raw_start
            start = day_start if all_day else _parse(raw_start)
            if start is None:
                continue
            end = None if all_day else _parse(str(ev.get("end") or "")) or None

            # `calendar.get_events` returns everything *overlapping* the window,
            # so a meeting that ran from 10pm yesterday to half past midnight
            # comes back with yesterday's start. Rendered as a clock time that
            # reads "10:11 PM", it looks like tonight, already struck through.
            # It was running when the day began, so that is where it goes.
            if not all_day and start < day_start:
                if end is None or end <= day_start:
                    continue
                start = day_start

            rule = _match_sentence(cfg, title)
            # A schedule calendar describes the house, not the household: its
            # event descriptions are the sage sentences, written where the
            # automation that fires from them can be seen alongside.
            if is_schedule:
                automation = (str(ev.get("description") or "").strip()) or None
            else:
                automation = rule.get("automation") or None

            entry: Entry = {
                "id": f"cal:{entity_id}:{raw_start}:{title}",
                "start": _iso(start),
                "end": _iso(end),
                "all_day": all_day,
                "kind": "automation" if is_schedule else "calendar",
                "source": meta.get("label") or entity_id,
                "title": title,
                "automation": automation,
                "priority": rule.get("priority") or meta.get("priority") or "normal",
                "sticky": bool(rule.get("sticky", False)),
                "entity_id": entity_id,
            }
            # Omitted rather than empty: this payload is re-sent to every open
            # browser on each refresh, and most events will never carry a tag.
            if tags:
                entry["tags"] = tags
            out.append(entry)
    return out


def from_todo(cfg: MergeConfig, items: list[dict[str, Any]], day_start: datetime) -> list[Entry]:
    """To-do items that have a due time.

    These are sticky: their time passing does not slide them into the
    struck-through past. They stay, with a button, until someone says they are
    done — which is the whole point of the laundry.

    Anything due after today ends is somebody else's day. Overdue items from
    before today are kept: that is the laundry going mouldy, and the reason the
    row exists at all.
    """
    if not cfg.todo_entity:
        return []
    day_end = day_start + timedelta(days=1)
    out: list[Entry] = []
    for item in items:
        due = item.get("due")
        if not due:
            continue
        all_day = "T" not in str(due)
        start = day_start if all_day else _parse(str(due))
        if start is None:
            continue
        if start >= day_end:
            continue
        out.append(
            {
                "id": f"todo:{item.get('uid')}",
                "start": _iso(start),
                "end": None,
                "all_day": all_day,
                "kind": "todo",
                "source": "Tasks",
                "title": str(item.get("summary") or "").strip(),
                "automation": None,
                "priority": "high",
                "sticky": True,
                "entity_id": cfg.todo_entity,
                # The card never builds this — it only fires what it is handed.
                # Pointing it at Grocy later is a change here and nowhere else.
                "action": {
                    "label": "Done",
                    "service": "todo.update_item",
                    "target": {"entity_id": cfg.todo_entity},
                    "data": {"item": item.get("uid"), "status": "completed"},
                },
            }
        )
    return out


def from_sun(cfg: MergeConfig, next_rising: datetime | None, next_setting: datetime | None,
             day_start: datetime) -> list[Entry]:
    """Today's sunrise and sunset.

    `sun.sun` only ever reports the *next* occurrence, so an event that already
    happened today is that time minus a day. Off by a minute or two around the
    solstices, which nobody has ever noticed.

    The window has to be the *local* day, not the UTC one. `sun.sun` publishes
    UTC, so west of Greenwich a sunset after 19:00 local already belongs to
    tomorrow's UTC date — comparing calendar dates dropped the sunset row for
    half the year, silently, only in summer.
    """
    if not cfg.show_sun:
        return []
    tz = day_start.tzinfo
    day_end = day_start + timedelta(days=1)
    out: list[Entry] = []
    for value, label, key in ((next_rising, "Sunrise", "rising"), (next_setting, "Sunset", "setting")):
        if value is None:
            continue
        local = value.astimezone(tz)
        moment = local if day_start <= local < day_end else local - timedelta(days=1)
        if not (day_start <= moment < day_end):
            continue
        rule = _match_sentence(cfg, label)
        out.append(
            {
                "id": f"sun:{key}",
                "start": _iso(moment),
                "end": None,
                "all_day": False,
                "kind": "sun",
                "source": "Sun",
                "title": label,
                "automation": rule.get("automation") or None,
                "priority": rule.get("priority") or cfg.sun_priority,
                "sticky": False,
                "entity_id": "sun.sun",
            }
        )
    return out


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def dedupe(cfg: MergeConfig, entries: list[Entry]) -> list[Entry]:
    """Fold near-duplicates into one row that names every calendar it came from.

    Two people keeping the same appointment on their own calendars, worded
    slightly differently, is one event. Merging must never lose information:
    the surviving row keeps whichever sentence existed, whichever action
    existed, and the higher priority.
    """
    kept: list[Entry] = []
    for entry in sorted(entries, key=lambda e: e["start"]):
        start = _parse(entry["start"])
        hit = None
        for candidate in reversed(kept):
            candidate_start = _parse(candidate["start"])
            # `kept` is in start order, so once we are further back than the
            # match window nothing earlier can match either. Without the break
            # this is quadratic — invisible at twenty entries, and not at two
            # thousand, which is one enthusiast with a lot of calendars away.
            if (
                start is not None
                and candidate_start is not None
                and (start - candidate_start).total_seconds() >= _WINDOW
            ):
                break
            if not _within(candidate_start, start):
                continue
            if not _within(_parse(candidate.get("end")), _parse(entry.get("end"))):
                continue
            if _similar(candidate["title"], entry["title"], cfg.title_noise) >= cfg.similarity:
                hit = candidate
                break

        if hit is None:
            kept.append(dict(entry))
            continue

        labels = str(hit.get("source") or "").split(" + ")
        if entry.get("source") and entry["source"] not in labels:
            labels.append(entry["source"])
        merged_from = hit.get("merged_from") or [hit.get("entity_id")]
        if entry.get("entity_id") not in merged_from:
            merged_from = [*merged_from, entry.get("entity_id")]

        # Tags union, because only one person keeping the shared event needs to
        # have tagged it. Wording follows the first calendar listed; a tag is not
        # wording, and dropping one here would lose the very thing it was for.
        tags = list(hit.get("tags") or [])
        lowered = {t.lower() for t in tags}
        for tag in entry.get("tags") or []:
            if tag.lower() not in lowered:
                lowered.add(tag.lower())
                tags.append(tag)

        hit.update(
            {
                # The wording comes from the calendar listed first — predictable,
                # and it lets you choose whose phrasing wins by ordering them.
                "source": " + ".join(l for l in labels if l),
                "automation": hit.get("automation") or entry.get("automation"),
                "action": hit.get("action") or entry.get("action"),
                "sticky": bool(hit.get("sticky")) or bool(entry.get("sticky")),
                "priority": _higher(hit.get("priority"), entry.get("priority")),
                "merged_from": merged_from,
            }
        )
        if tags:
            hit["tags"] = tags
    return kept


def attach_weather(entries: list[Entry], forecast: list[dict[str, Any]], now: datetime) -> list[Entry]:
    """Hang the forecast for its starting hour on each upcoming entry."""
    if not forecast:
        return entries
    parsed = [(_parse(str(f.get("datetime", ""))), f) for f in forecast]
    parsed = [(dt, f) for dt, f in parsed if dt is not None]

    for entry in entries:
        start = _parse(entry["start"])
        if entry.get("all_day") or start is None or start < now:
            continue
        best = min(
            (pair for pair in parsed if abs((pair[0] - start).total_seconds()) < 3600),
            key=lambda pair: abs((pair[0] - start).total_seconds()),
            default=None,
        )
        if best:
            _, f = best
            entry["weather"] = {
                "condition": f.get("condition"),
                "temperature": f.get("temperature"),
                # Not every provider reports a probability. met.no — the one
                # Home Assistant sets up by default — reports millimetres and
                # no probability at all, so carrying only the probability meant
                # rain never once got the wet treatment on a default install.
                "precipitation_probability": f.get("precipitation_probability"),
                "precipitation": f.get("precipitation"),
            }
    return entries


def remaining_count(entries: list[Entry], now: datetime) -> int:
    """What is still ahead: upcoming, running, or waiting to be ticked off.

    An event you are in the middle of has not happened yet as far as the rest of
    your day is concerned.
    """
    count = 0
    for entry in entries:
        if entry.get("kind") == "event":
            continue
        start = _parse(entry["start"])
        end = _parse(entry.get("end"))
        running = end is not None and start is not None and start <= now < end
        if entry.get("sticky") or running or (start is not None and start >= now):
            count += 1
    return count


def _parse(value: Any) -> datetime | None:
    """Tolerant ISO parse. Bad data becomes None and is skipped, never a crash
    that takes the whole card down."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
