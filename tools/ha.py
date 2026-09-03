"""A thin Home Assistant client for driving a live instance from the terminal.

Reads HA_URL and HA_TOKEN from the environment, or from a `.ha-env` file at the
repo root (which is gitignored — a long-lived token is a credential).

    HA_URL=http://192.168.1.10
    HA_TOKEN=eyJhbGci...

Everything here speaks to a real instance. Nothing here is imported by the
integration or the card; it exists so the live tests can be scripted instead of
clicked.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> tuple[str, str]:
    url = os.environ.get("HA_URL")
    token = os.environ.get("HA_TOKEN")
    envfile = ROOT / ".ha-env"
    if (not url or not token) and envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if k == "HA_URL" and not url:
                url = v
            elif k == "HA_TOKEN" and not token:
                token = v
    if not url or not token:
        sys.exit(
            "Set HA_URL and HA_TOKEN, or write them into .ha-env at the repo root."
        )
    return url.rstrip("/"), token


URL, TOKEN = _load_env()
WS_URL = URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"


# --------------------------------------------------------------------------- REST


def rest(path: str, method: str = "GET", body: Any = None) -> Any:
    """One REST call. Returns parsed JSON, or the raw text if it isn't JSON."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{URL}/api/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code} {e.read().decode()[:400]}") from None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def state(entity_id: str) -> dict:
    return rest(f"states/{entity_id}")


def head(path: str) -> int:
    """Status code for a path served by Home Assistant itself, not the API.

    Frontend assets — a card registered as a Lovelace resource, say — live
    outside /api/ and are served unauthenticated. What matters about them is
    only whether they are there, which is the one thing a resource list cannot
    tell you: a resource row is just a string, and it stays exactly as
    convincing after the file behind it stops existing.
    """
    req = urllib.request.Request(f"{URL}/{path.lstrip('/')}", method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def call_service(domain: str, service: str, **data) -> Any:
    """Fire a service. Add return_response=True in `data` for a response service."""
    want_response = data.pop("return_response", False)
    path = f"services/{domain}/{service}"
    if want_response:
        path += "?return_response"
    return rest(path, "POST", data)


def template(tpl: str) -> str:
    return rest("template", "POST", {"template": tpl})


# ----------------------------------------------------------------------- WebSocket


class WS:
    """The websocket API, which is the only way to reach config entries,
    config flows, the entity registry and dashboards."""

    def __init__(self) -> None:
        self._ws = None
        self._id = 0

    async def __aenter__(self) -> "WS":
        import websockets

        self._ws = await websockets.connect(WS_URL, max_size=32 * 1024 * 1024)
        hello = json.loads(await self._ws.recv())
        assert hello["type"] == "auth_required", hello
        await self._ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        ok = json.loads(await self._ws.recv())
        if ok["type"] != "auth_ok":
            raise RuntimeError(f"auth failed: {ok}")
        return self

    async def __aexit__(self, *exc) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def cmd(self, type_: str, **kwargs) -> Any:
        """Send one command, wait for its result. Raises on an error result."""
        self._id += 1
        mine = self._id
        await self._ws.send(json.dumps({"id": mine, "type": type_, **kwargs}))
        while True:
            msg = json.loads(await self._ws.recv())
            if msg.get("id") != mine or msg.get("type") != "result":
                continue  # an event, or another command's reply
            if not msg.get("success"):
                raise RuntimeError(f"{type_} failed: {msg.get('error')}")
            return msg.get("result")


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------ config entries


async def entries(ws: WS, domain: str | None = None) -> list[dict]:
    got = await ws.cmd("config_entries/get")
    return [e for e in got if domain is None or e["domain"] == domain]


async def remove_entry(ws: WS, entry_id: str) -> Any:
    return await ws.cmd("config_entries/remove", entry_id=entry_id)


# Config and options flows are REST, not WebSocket — the websocket API only
# exposes `config_entries/flow/progress`, never the start/step commands.


def flow_start(handler: str) -> dict:
    return rest(
        "config/config_entries/flow",
        "POST",
        {"handler": handler, "show_advanced_options": True},
    )


def flow_step(flow_id: str, user_input: dict) -> dict:
    return rest(f"config/config_entries/flow/{flow_id}", "POST", user_input)


def flow_abort(flow_id: str) -> Any:
    return rest(f"config/config_entries/flow/{flow_id}", "DELETE")


def options_start(entry_id: str) -> dict:
    return rest(
        "config/config_entries/options/flow",
        "POST",
        {"handler": entry_id, "show_advanced_options": True},
    )


def options_step(flow_id: str, user_input: dict) -> dict:
    return rest(f"config/config_entries/options/flow/{flow_id}", "POST", user_input)


def describe_flow(step: dict) -> str:
    """Render a flow step the way a person would read the dialog, so a script
    can assert on what the form actually asks."""
    t = step.get("type")
    if t == "create_entry":
        return f"create_entry: {step.get('title')!r}"
    if t == "abort":
        return f"abort: {step.get('reason')}"
    if t == "menu":
        return f"menu {step.get('step_id')}: {step.get('menu_options')}"
    if t == "form":
        keys = _schema_keys(step.get("data_schema") or [])
        errors = step.get("errors") or {}
        out = f"form {step.get('step_id')}: {keys}"
        if errors:
            out += f"  ERRORS={errors}"
        return out
    return f"{t}: {step}"


def _schema_keys(schema: list) -> list[str]:
    out = []
    for f in schema:
        name = f.get("name")
        req = "" if f.get("required") else "?"
        out.append(f"{name}{req}")
    return out
