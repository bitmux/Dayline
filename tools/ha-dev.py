#!/usr/bin/env python3
"""Everything you end up doing twenty times a day against the test instance.

    tools/ha-dev.py doctor              # is everything actually wired up?
    tools/ha-dev.py deploy              # HACS pull both repos, restart, verify
    tools/ha-dev.py update [name...]    # HACS pull, no restart
    tools/ha-dev.py restart             # restart and wait for RUNNING
    tools/ha-dev.py resources           # what the dashboard will try to import
    tools/ha-dev.py logs [--all]        # warnings and errors, ours first
    tools/ha-dev.py feed                # the sensor's finished output
    tools/ha-dev.py repos               # what HACS knows about

Reads HA_URL and HA_TOKEN from `.ha-env` via tools/ha.py.

The deploy loop is the point. HACS downloads are slow (a couple of minutes on a
cold repository) and a restart takes the API away for a while, so every one of
these waits properly instead of sleeping a guessed number of seconds and hoping.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ha  # noqa: E402

# The repositories this project installs on the test instance, by GitHub name.
# Looked up by name rather than by id, because HACS's numeric ids are per
# instance and a hardcoded one is wrong the first time anyone else runs this.
REPOS = {
    "integration": "bitmux/Dayline",
    "card": "bitmux/Dayline-card",
}

FEED_SENSOR_HINT = "entries"  # the attribute that identifies our sensor


def _print(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'✓' if ok else '✗'} {label}{(' — ' + detail) if detail else ''}")


# --------------------------------------------------------------------- helpers


async def _hacs_repos(ws) -> dict[str, dict]:
    """Every HACS repository we care about, keyed by full_name."""
    wanted = set(REPOS.values())
    return {
        r["full_name"]: r
        for r in await ws.cmd("hacs/repositories/list")
        if r.get("full_name") in wanted
    }


def _feed_sensor() -> tuple[str, dict] | tuple[None, None]:
    """Find the feed by its shape, not its name — the entity id follows the
    config entry's title, so it is `sensor.dayline` here and something else on
    an instance where the entry was named differently."""
    for s in ha.rest("states"):
        if s["entity_id"].startswith("sensor.") and isinstance(
            s["attributes"].get(FEED_SENSOR_HINT), list
        ):
            return s["entity_id"], s
    return None, None


def _wait_for_running(timeout: float = 300.0) -> bool:
    """Block until the API answers RUNNING again.

    A restart takes the API away in stages: it keeps answering for a moment, then
    refuses connections, then answers STARTING, then RUNNING. Anything that just
    polls for "responds" gets a false positive off the first stage, which is how
    you end up reading the state of the instance you were trying to replace.
    """
    deadline = time.monotonic() + timeout
    went_away = False
    while time.monotonic() < deadline:
        try:
            state = ha.rest("config").get("state")
        except Exception:
            went_away = True
            state = None
        if went_away and state == "RUNNING":
            return True
        time.sleep(3)
    return False


# -------------------------------------------------------------------- commands


async def cmd_repos(_args) -> int:
    async with ha.WS() as ws:
        found = await _hacs_repos(ws)
    for name in REPOS.values():
        r = found.get(name)
        if not r:
            _print(False, name, "not known to HACS — add it as a custom repository")
            continue
        _print(
            bool(r.get("installed")),
            f"{name} [{r.get('category')}]",
            f"id={r.get('id')} installed={r.get('installed_version') or '—'} "
            f"available={r.get('available_version') or '—'}",
        )
    return 0


async def cmd_update(args) -> int:
    which = args.which or list(REPOS)
    async with ha.WS() as ws:
        found = await _hacs_repos(ws)
        for key in which:
            name = REPOS.get(key, key)
            repo = found.get(name)
            if not repo:
                _print(False, name, "not known to HACS")
                return 1
            print(f"  … downloading {name} (this takes a minute or two)")
            await ws.cmd("hacs/repository/download", repository=str(repo["id"]))
            _print(True, f"{name} downloaded")
    return 0


def cmd_restart(_args) -> int:
    try:
        ha.rest("services/homeassistant/restart", "POST", {})
    except Exception:
        pass  # the connection dies mid-response, which is the expected case
    print("  … restarting")
    if not _wait_for_running():
        _print(False, "restart", "never came back RUNNING")
        return 1
    _print(True, "restart", "RUNNING")
    return 0


async def cmd_resources(_args) -> int:
    async with ha.WS() as ws:
        for r in await ws.cmd("lovelace/resources"):
            print(f"  {r['type']:8} {r['url']}")
    return 0


async def cmd_logs(args) -> int:
    async with ha.WS() as ws:
        entries = await ws.cmd("system_log/list")
    ours = [e for e in entries if "day_spine" in str(e.get("name", ""))]
    rest = [e for e in entries if e not in ours]
    for e in ours + (rest if args.all else []):
        when = time.strftime("%H:%M:%S", time.localtime(e["timestamp"]))
        msg = e["message"][0] if isinstance(e.get("message"), list) else e.get("message")
        print(f"  {when} {e.get('level','?'):8} {e.get('name','?')}: {str(msg)[:150]}")
        if e.get("count", 1) > 1:
            print(f"           (x{e['count']})")
    if not ours:
        print("  nothing from day_spine" + ("" if args.all else " — --all for the rest"))
    return 0


def cmd_feed(_args) -> int:
    eid, s = _feed_sensor()
    if not eid:
        _print(False, "feed sensor", "no sensor carries an `entries` list")
        return 1
    a = s["attributes"]
    entries = a.get("entries") or []
    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e.get("kind", "?")] = kinds.get(e.get("kind", "?"), 0) + 1
    print(f"  {eid} = {s['state']}  ({len(entries)} entries)")
    print(f"  headline: {a.get('headline')!r}")
    print(f"  kinds:    {kinds}")
    print(f"  sources:  {a.get('sources')}")
    print(
        f"  weather on {sum(1 for e in entries if e.get('weather'))}, "
        f"actions on {sum(1 for e in entries if e.get('action'))}, "
        f"sentences on {sum(1 for e in entries if e.get('automation'))}"
    )
    if a.get("stale_message"):
        print(f"  stale:    {a['stale_message']}")
    return 0


async def cmd_doctor(_args) -> int:
    """One command that answers 'why is the card not showing up'.

    Checks the whole chain in the order it actually breaks: is HA up, is the
    integration producing a feed, did HACS install the card, is it registered as
    a resource, and does that resource actually serve a file.
    """
    bad = 0

    state = ha.rest("config").get("state")
    _print(state == "RUNNING", "Home Assistant", str(state))
    bad += state != "RUNNING"

    eid, s = _feed_sensor()
    if eid:
        _print(True, "feed sensor", f"{eid} = {s['state']}, "
                                    f"{len(s['attributes'].get('entries') or [])} entries")
    else:
        _print(False, "feed sensor", "no sensor carries an `entries` list")
        bad += 1

    async with ha.WS() as ws:
        repos = await _hacs_repos(ws)
        for name in REPOS.values():
            r = repos.get(name)
            ok = bool(r and r.get("installed"))
            _print(ok, f"HACS {name}", "installed" if ok else "not installed")
            bad += not ok

        resources = await ws.cmd("lovelace/resources")
        card = [r for r in resources if "day-spine-card" in r.get("url", "")]
        if not card:
            _print(False, "Lovelace resource", "the card is not registered")
            bad += 1
        for r in card:
            url = r["url"]
            try:
                code = ha.head(url)
            except Exception as e:  # noqa: BLE001
                code = str(e)
            ok = code == 200
            _print(ok, "Lovelace resource", f"{url} -> {code}")
            bad += not ok
            if url.startswith("/day_spine_frontend/"):
                _print(False, "stale resource", "left over from before the card "
                                                "moved to its own repository — delete it under "
                                                "Settings → Dashboards → ⋮ → Resources")
                bad += 1

        errs = [e for e in await ws.cmd("system_log/list")
                if "day_spine" in str(e.get("name", ""))]
        _print(not errs, "log", f"{len(errs)} day_spine entries"
                                if errs else "nothing from day_spine")
        bad += bool(errs)

    print()
    print("  all good" if not bad else f"  {bad} problem(s) above")
    return 1 if bad else 0


async def cmd_deploy(args) -> int:
    """Pull from the repos, restart, and prove it came back working."""
    if await cmd_update(args):
        return 1
    if cmd_restart(args):
        return 1
    print()
    return await cmd_doctor(args)


# ----------------------------------------------------------------------- main


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, help_ in [
        ("doctor", "check the whole chain, feed through to served bundle"),
        ("deploy", "HACS pull both repos, restart, then doctor"),
        ("restart", "restart and wait for RUNNING"),
        ("resources", "list the Lovelace resources"),
        ("feed", "dump the feed sensor's finished output"),
        ("repos", "what HACS knows about our repositories"),
    ]:
        sub.add_parser(name, help=help_)

    up = sub.add_parser("update", help="HACS pull without restarting")
    up.add_argument("which", nargs="*", choices=[*REPOS, []], default=None,
                    help="integration, card, or both if omitted")
    sub.add_parser("logs", help="warnings and errors").add_argument(
        "--all", action="store_true", help="not just ours")

    args = p.parse_args()
    for a in ("which", "all"):
        setattr(args, a, getattr(args, a, None))

    sync = {"restart": cmd_restart, "feed": cmd_feed}
    if args.cmd in sync:
        return sync[args.cmd](args)
    return asyncio.run(globals()[f"cmd_{args.cmd}"](args))


if __name__ == "__main__":
    sys.exit(main())
