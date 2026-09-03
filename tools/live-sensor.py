"""Draw the card from what the *integration* actually published.

live-merge.py runs merge.py here, on this machine, against live service
responses. This one goes a step further and takes the finished attributes off
`sensor.dayline` — the real coordinator's output, from inside Home Assistant —
so the only thing left unproven is the card itself.

    python3 tools/live-sensor.py [sensor.dayline]

Writes dev/live-sample.json; open dev/live.html to look at it.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ha  # noqa: E402

KEYS = ("entries", "headline", "now", "sources", "stale_message")


def main() -> None:
    entity = sys.argv[1] if len(sys.argv) > 1 else "sensor.dayline"
    state = ha.state(entity)
    attrs = state["attributes"]
    payload = {k: attrs.get(k) for k in KEYS}

    entries = payload.get("entries") or []
    print(f"{entity} = {state['state']}  ({len(entries)} entries)")
    print(f"  headline: {payload.get('headline')!r}")
    print(f"  sources:  {payload.get('sources')}")
    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e.get("kind", "?")] = kinds.get(e.get("kind", "?"), 0) + 1
    print("  kinds:   ", kinds)
    print("  with weather:", sum(1 for e in entries if e.get("weather")))
    print("  with an action:", sum(1 for e in entries if e.get("action")))
    print("  with a sentence:", sum(1 for e in entries if e.get("automation")))

    out = ROOT / "dev" / "live-sample.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out.relative_to(ROOT)} — open dev/live.html")


if __name__ == "__main__":
    main()
