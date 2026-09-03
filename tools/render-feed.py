"""Render the day_spine.yaml templates against stub HA globals, to catch Jinja
errors before they land in a live instance."""
import re, sys, yaml, datetime as dt
from jinja2 import Environment, StrictUndefined

TZ = dt.timezone(dt.timedelta(hours=-5))
NOW = dt.datetime(2026, 9, 2, 14, 39, tzinfo=TZ)

STATES = {
    "calendar.family": "on",
    "calendar.school": "unavailable",
    "sun.sun": "above_horizon",
    "climate.house": "heat",
}
ATTRS = {
    ("sun.sun", "next_rising"): "2026-09-03T06:58:00-05:00",
    ("sun.sun", "next_setting"): "2026-09-02T19:47:00-05:00",
    ("climate.house", "current_temperature"): 71.4,
    ("sensor.day_spine_recent", "events"): [
        {"id": "evt:1", "start": "2026-09-02T14:36:00-05:00",
         "expires": "2026-09-02T14:41:00-05:00", "all_day": False, "kind": "event",
         "source": "House", "title": "Living room lights turned off by motion sensor"},
    ],
}


def as_datetime(v):
    if isinstance(v, dt.datetime):
        return v
    try:
        return dt.datetime.fromisoformat(v)
    except ValueError:
        return None


def today_at(t="00:00"):
    h, m = (int(x) for x in t.split(":"))
    return NOW.replace(hour=h, minute=m, second=0, microsecond=0)


class FakeLight:
    def __init__(self, state):
        self.state = state


class FakeStates:
    light = [FakeLight("on"), FakeLight("on"), FakeLight("off")]

    def __call__(self, eid):
        return STATES.get(eid, "unknown")


env = Environment(undefined=StrictUndefined)
env.filters["as_local"] = lambda d: d
env.filters["regex_replace"] = lambda v, f, r="": re.sub(f, r, v)
env.tests["in"] = lambda v, seq: v in seq
env.filters["combine"] = lambda d, *others: {k: v for o in (d,) + others for k, v in o.items()}
env.filters["split"] = lambda v, sep=None: v.split(sep)
env.globals.update(
    now=lambda: NOW,
    today_at=today_at,
    as_datetime=as_datetime,
    timedelta=dt.timedelta,
    states=FakeStates(),
    state_attr=lambda e, a: ATTRS.get((e, a)),
)

doc = yaml.safe_load(open(sys.argv[1]))
blocks = doc["template"]

# ---- block 1: the merged day -------------------------------------------------
ctx = {}
for step in blocks[0]["action"]:
    if "variables" not in step:
        continue
    # Pass 1: the plain config blocks only. The templated ones need the service
    # responses, which are stubbed in below.
    for k, v in step["variables"].items():
        if not (isinstance(v, str) and "{" in v):
            ctx[k] = v

# Stub the service responses the way HA shapes them.
ctx["cal"] = {
    "calendar.family": {"events": [
        {"start": "2026-09-02T15:50:00-05:00", "end": "2026-09-02T16:20:00-05:00",
         "summary": "Kid out of school"},
        {"start": "2026-09-02T08:20:00-05:00", "end": "2026-09-02T08:40:00-05:00",
         "summary": "Kid to school"},
        {"start": "2026-09-02", "end": "2026-09-03", "summary": "Trash out tonight"},
        {"start": "2026-09-02T13:00:00-05:00", "end": "2026-09-02T14:00:00-05:00",
         "summary": "Busy"},
    ]},
    "calendar.house_schedule": {"events": [
        {"start": "2026-09-02T07:00:00-05:00", "end": "2026-09-02T07:05:00-05:00",
         "summary": "Morning",
         "description": "Lights up over 20 minutes, thermostat to 70°"},
    ]},
    "calendar.wife": {"events": [
        # near-duplicate of the family calendar's 15:50, worded differently
        {"start": "2026-09-02T15:50:00-05:00", "end": "2026-09-02T16:20:00-05:00",
         "summary": "Kid out of the school"},
    ]},
    "calendar.school": {"events": [
        {"start": "2026-09-02T15:50:00-05:00", "end": "2026-09-02T16:20:00-05:00",
         "summary": "Kid out of school"},  # the duplicate
        {"start": "2026-09-02T21:00:00-05:00", "end": "2026-09-02T21:30:00-05:00",
         "summary": "Kid bed time"},
    ]},
}
ctx["calendars"]["calendar.wife"] = {"label": "CalDAV", "priority": "normal"}
ctx["fc"] = {"weather.home": {"forecast": [
    {"datetime": f"2026-09-02T{h:02d}:00:00-05:00", "condition": c,
     "temperature": t, "precipitation_probability": p}
    for h, c, t, p in [
        (15, "rainy", 63, 70), (16, "pouring", 61, 85), (19, "partlycloudy", 58, 10),
        (21, "clear-night", 54, 0), (22, "clear-night", 52, 0),
    ]
]}}
ctx["tasks"] = {"todo.household": {"items": [
    {"uid": "abc", "summary": "Switch the laundry", "status": "needs_action",
     "due": "2026-09-02T14:01:00-05:00"},
    {"uid": "def", "summary": "No due date task", "status": "needs_action"},
]}}

for step in blocks[0]["action"]:
    if "variables" not in step:
        continue
    for k, v in step["variables"].items():
        if isinstance(v, str) and "{" in v:
            out = env.from_string(v).render(**ctx)
            try:
                ctx[k] = eval(out.strip(), {"__builtins__": {}}, {"none": None,
                                                                  "false": False,
                                                                  "true": True})
            except Exception as exc:
                print(f"  ! {k} did not eval as a literal ({exc}); raw = {out.strip()[:120]}")
                ctx[k] = out.strip()

print(f"\n=== merged: {len(ctx['merged'])} entries ===")
for e in ctx["merged"]:
    tag = "all-day" if e.get("all_day") else e["start"][11:16]
    print(f"  {tag:>7}  {e['kind']:<9} {e.get('source','?'):<7} {e['title'][:44]:<46}"
          f" prio={e.get('priority','-'):<6} {'STICKY' if e.get('sticky') else ''}"
          f"{' ACTION' if e.get('action') else ''}"
          f"{'  wx=' + str(e['weather'].get('condition')) + ' ' + str(e['weather'].get('temperature')) + '° pop=' + str(e['weather'].get('precipitation_probability')) if e.get('weather') else ''}"
          f"{'  MERGED<-' + ','.join(e['merged_from']) if e.get('merged_from') else ''}")
print(f"\nremaining = {ctx['remaining']}")
print(f"sources   = {ctx['source_list']}")

sensor = blocks[0]["sensor"][0]
print(f"state     = {env.from_string(sensor['state']).render(**ctx).strip()}")
for k, v in sensor["attributes"].items():
    if k == "entries":
        continue
    print(f"{k:<9} = {' '.join(env.from_string(v).render(**ctx).split())!r}")

# ---- block 2: what just happened ---------------------------------------------
print("\n=== day_spine_recent ===")


class Ctxt:
    parent_id = "auto-1"


class ToState:
    state = "off"
    last_changed = dt.datetime(2026, 9, 2, 14, 36, tzinfo=TZ)
    context = Ctxt()


class Trigger:
    entity_id = "light.living_room"
    to_state = ToState()


class This:
    attributes = {"events": [
        {"id": "evt:old", "expires": "2026-09-02T14:20:00-05:00", "title": "expired"},
        {"id": "evt:live", "expires": "2026-09-02T14:50:00-05:00", "title": "still fresh"},
    ]}


ctx2 = {"trigger": Trigger(), "this": This()}
for step in blocks[1]["action"]:
    for k, v in step.get("variables", {}).items():
        ctx2[k] = v

cond = blocks[1]["condition"][0]["value_template"]
print("condition ->", env.from_string(cond).render(**ctx2).strip())
s2 = blocks[1]["sensor"][0]
for k, v in s2["attributes"].items():
    out = env.from_string(v).render(**ctx2).strip()
    evs = eval(out, {"__builtins__": {}}, {"none": None, "false": False, "true": True})
    print(f"{k} -> {len(evs)} kept")
    for e in evs:
        print("   ", e.get("title"), "| expires", e.get("expires"))
print("\nAll templates rendered.")

# Emit exactly what the sensor's attributes would carry, for the dev harness.
import json, os
payload = {
    "entries": ctx["merged"],
    "headline": " ".join(env.from_string(sensor["attributes"]["headline"]).render(**ctx).split()),
    "now": " ".join(env.from_string(sensor["attributes"]["now"]).render(**ctx).split()),
    "sources": ctx["source_list"],
    "stale_message": " ".join(env.from_string(sensor["attributes"]["stale_message"]).render(**ctx).split()),
}
out_path = os.path.join(os.path.dirname(sys.argv[1]), "..", "dev", "feed-sample.json")
with open(out_path, "w") as fh:
    json.dump(payload, fh, indent=1)
print(f"\nwrote {os.path.normpath(out_path)}")
