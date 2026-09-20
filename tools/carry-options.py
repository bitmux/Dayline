"""Copy one Dayline config entry's settings onto another.

The 0.4.0 rename changes the integration's domain, and Home Assistant has no
migration for that: the old entry stops loading and a new one has to be added.
Setup itself is a name and two dropdowns, so that part costs nothing — but the
sentence map, the per-calendar wording, leave-by and the alarm list are real
work somebody did by hand, and losing them to a rename would be a poor trade.

Everything is read back through the options flow's own defaults, which is the
only route that works: `config_entries/get` redacts `data` and `options`.

Read before the upgrade, write after it. Doing it in two halves is the point:
the alternative is leaving the old integration on disk so both can be loaded at
once, and two integrations both creating `sensor.dayline` is a worse problem
than the one being solved.

    python3 tools/carry-options.py --list
    python3 tools/carry-options.py --from <old_id> --save settings.json
    #  ... upgrade, delete the old entry, add Dayline again ...
    python3 tools/carry-options.py --to <new_id> --load settings.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import ha  # noqa: E402

# The plain form-per-step pages. The two list editors are handled separately,
# because a pick-or-add step has no fields of its own to read.
SIMPLE_STEPS = ("sources", "leaving", "alarms", "tuning", "labels")

ADD = "__add__"
DONE = "__done__"


def _flow(entry_id: str) -> str:
    return ha.rest("config/config_entries/options/flow", "POST", {"handler": entry_id})["flow_id"]


def _step(flow_id: str, step: str) -> dict[str, Any]:
    return ha.rest(f"config/config_entries/options/flow/{flow_id}", "POST", {"next_step_id": step})


def _submit(flow_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return ha.rest(f"config/config_entries/options/flow/{flow_id}", "POST", body)


def _defaults(form: dict[str, Any]) -> dict[str, Any]:
    return {
        f["name"]: f["default"]
        for f in form.get("data_schema", [])
        if f.get("default") is not None
    }


def read(entry_id: str) -> dict[str, Any]:
    """Every setting on one entry, keyed by the step that owns it."""
    out: dict[str, Any] = {}
    for step in SIMPLE_STEPS:
        out[step] = _defaults(_step(_flow(entry_id), step))

    # Sentences: the list page shows one option per rule, and the rule's own
    # fields only appear once it is opened. So open each in turn.
    form = _step(_flow(entry_id), "sentences")
    count = sum(
        1
        for opt in form["data_schema"][0]["selector"]["select"]["options"]
        if opt["value"] not in (ADD, DONE)
    )
    sentences = []
    for i in range(count):
        fid = _flow(entry_id)
        _step(fid, "sentences")
        sentences.append(_defaults(_submit(fid, {"selection": str(i)})))
    out["sentences"] = sentences

    # Per-calendar wording is a flat form keyed `<entity>__label` and friends.
    out["calendars"] = _defaults(_step(_flow(entry_id), "calendars"))
    return out


def write(entry_id: str, settings: dict[str, Any]) -> None:
    for step in SIMPLE_STEPS:
        body = settings.get(step) or {}
        if not body:
            continue
        fid = _flow(entry_id)
        _step(fid, step)
        _submit(fid, body)
        print(f"  ✓ {step}")

    for rule in settings.get("sentences") or []:
        fid = _flow(entry_id)
        _step(fid, "sentences")
        _submit(fid, {"selection": ADD})
        _submit(fid, {k: v for k, v in rule.items() if k != "delete"})
        _submit(fid, {"selection": DONE})
    if settings.get("sentences"):
        print(f"  ✓ sentences ({len(settings['sentences'])})")

    # Only the calendars the new entry already knows about: wording for a
    # calendar it cannot see would be rejected as an unexpected key, and the
    # label decides what it can see.
    wanted = settings.get("calendars") or {}
    if wanted:
        fid = _flow(entry_id)
        form = _step(fid, "calendars")
        allowed = {f["name"] for f in form.get("data_schema", [])}
        body = {k: v for k, v in wanted.items() if k in allowed}
        if body:
            _submit(fid, body)
            print(f"  ✓ calendars ({len(body)} fields)")
        missing = sorted({k.split("__")[0] for k in wanted if k not in allowed})
        if missing:
            print(f"  … wording not carried for: {', '.join(missing)}")
            print("    (those calendars do not carry the label on the new entry yet)")


def entries() -> list[dict[str, Any]]:
    return [
        e
        for e in ha.rest("config/config_entries/entry")
        if e.get("domain") in ("dayline", "day_spine")
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show Dayline entries and their ids")
    ap.add_argument("--from", dest="src", help="entry id to read from")
    ap.add_argument("--to", dest="dst", help="entry id to write to")
    ap.add_argument("--save", help="write the settings read from --from to this file")
    ap.add_argument("--load", help="write the settings in this file to --to")
    ap.add_argument("--dry-run", action="store_true", help="print what would be carried")
    args = ap.parse_args()

    if args.list or not (args.src or args.dst or args.load):
        for e in entries():
            print(f"  {e['entry_id']}  {e.get('domain'):9s}  {e.get('title')}  [{e.get('state')}]")
        if not args.list:
            print("\nPass --from <id> --save <file>, then --to <id> --load <file>.")
        return 0

    settings = None
    if args.src:
        print(f"reading {args.src}")
        settings = read(args.src)
        if args.save:
            with open(args.save, "w") as fh:
                json.dump(settings, fh, indent=1)
            print(f"saved to {args.save}")
    elif args.load:
        with open(args.load) as fh:
            settings = json.load(fh)
        print(f"loaded {args.load}")

    if settings is None:
        print("nothing to carry: pass --from or --load")
        return 1
    if args.dry_run or not args.dst:
        print(json.dumps(settings, indent=1))
        return 0

    print(f"writing {args.dst}")
    write(args.dst, settings)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
