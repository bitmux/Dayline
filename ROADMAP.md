# Roadmap

What Dayline is for, and the order the remaining work should happen in.

Nothing here is a commitment to a date. The phases are ordered by dependency and
by how much each one changes the experience, not by how interesting they are to
build.

---

## The through-line

Dayline answers two questions without interaction: *what is left of today?* and
*what will the house do without me?* Everything below is in service of those two
sentences, and anything that serves neither is out of scope no matter how good
an idea it is.

Five principles that decide the arguments:

1. **The card is dumb; the feed is where policy lives.** The card takes an
   ordered list and draws it. Every decision that will change over time is data
   the feed supplies.
2. **Capture surfaces, not input surfaces.** The best place to enter something
   is the place you were already standing — your calendar app, your voice, a
   notification on the lock screen. If a feature requires opening Home Assistant
   to type, it has failed before it ships.
3. **Every row is answerable in one tap, and every question the card asks has a
   defensible answer if you ignore it.** No forms. No modals. If a thing cannot
   be expressed as a row with at most two buttons, it belongs in Settings.
4. **Dayline observes and proposes. It does not own shared state.** House Mode
   is not ours. We call a script and the script decides. We are one caller among
   several, and we behave like it.
5. **A model may write a template. A template renders the row.** Nothing
   model-shaped ever sits between the sensor and the pixels.

---

## Phase 1 — Delete the setup

The config flow currently asks you to pick calendars out of a list of twenty.
That is the wrong shape: it is a decision you make once, in the wrong place,
and re-make every time anything changes.

**Labels replace it.** Apply the `Dayline` label to the calendars that matter
and the feed resolves them at runtime. Same for the "what just happened" entity
list — label the handful of entities whose automatic changes have ever confused
someone, instead of maintaining a second list here.

- Resolve calendars and watched entities from the label registry each refresh.
- Re-derive on registry update events so a newly labelled calendar appears
  without a restart.
- Config flow collapses to almost nothing. Weather and to-do list stay as
  explicit single pickers; they are one choice each and a label would be
  ceremony.
- With no `Dayline` label present anywhere, take every calendar and say so on
  the card. A first run should render, not interrogate.

The point is not the saving on day one. It is that **adding a calendar later
never involves Dayline** — you label it where you were already standing.

> Verify before building: `label_entities()` and the label registry's update
> events are 2024.4+ and the exact helper names should be checked against the
> version in `manifest.json`'s `homeassistant` floor.

---

## Phase 2 — Tags

A calendar event is someone else's object. The only place to put metadata on one
is in text a human types anyway, so: `#Away` in the title.

```
"Portland trip #Away"
        ↓
   script.house_away
        ↓
lights off · thermostat setback · garage closed
```

### Rules, settled

- **A tag binds to a script.** Not to a helper, not to a scene list, not to a
  mode enum. The script sets `input_select.house_mode`, or arms an alarm panel,
  or does nine other things — Dayline neither knows nor cares. This is what
  keeps us out of an argument the community has not settled (there is no
  first-party house-mode concept; `input_select.house_mode` is convention and
  `alarm_control_panel` is a borrowed security abstraction).
- **Fires once, on event start. Nothing fires on event end. Ever.** Coming back
  is its own calendar entry — `Return #Home from vacation` at 4pm. One
  mechanism, no special cases, and the return is *visible on the spine* the way
  an invisible end-action never would be.
- **Last write wins, and it is free.** Every input — a tag firing, phones
  arriving home, someone saying it out loud, a tap on the dashboard — is a write
  to shared state, ordered in time. There is no precedence engine because a
  state machine already is one. Come home early during `#Away` and presence
  writes Home; Dayline has nothing to say about it and does not fight back.
- **Overlaps need no rules.** Same tag twice: both write the same value. One
  tagged, one not: only one writes. Neither tagged: nobody writes. Different
  tags: the later start writes later.
- **Tags are not stripped from the title.** Seeing `#Away` is how you know what
  the house is about to do. Render it as a chip beside the title rather than
  text inside it — metadata that looks like metadata. All-day rows carry chips
  too: an all-day `#Away` is the most common real use, not an edge case.
- **No tag parameters.** `#Quiet(2h)` is a syntax someone has to remember. The
  binding carries the configuration.

### How a tag reaches a script

**Dayline fires an event. It does not write automations.**

```yaml
event_type: dayline_tag
data:
  tag: Away
  calendar: calendar.admin
  summary: "Portland trip"
  start: "2026-09-05T09:00:00-05:00"
  end: "2026-09-07T18:00:00-05:00"
  all_day: false
```

That is the whole primitive, and it is copied more or less exactly from Home
Assistant's own `tag` integration — scan an NFC tag HA has never seen, it fires
`tag_scanned`, the tag shows up in the Tags panel, and one button drops you into
the automation editor with the trigger filled in. Discovered rather than
declared, one click to make it mean something. Same noun, same shape, already
familiar to anyone who has used it.

Three consequences, all good:

- **The binding lives in the automation**, which is Home Assistant's job and not
  ours. Nothing to persist here, nothing to keep in sync with a `select` entity.
- **Conditions come free.** "Fire `#Away` *unless* someone is still home" is a
  condition on the user's own automation, not a feature request against us.
- **We never write to another integration's storage.** Generating automations
  from inside an integration is the same mistake as registering a Lovelace
  resource from inside one — someone else's collection, no public API, no
  contract. That lesson is already paid for.

**The paved path is a shipped blueprint**: two inputs, *which tag* and *what to
do*, the second an `action` selector so it is the full action editor rather than
a list of scripts. It produces an ordinary automation the user can open and
extend. The community precedent is strong here — keyword-in-calendar blueprints
are already a well-trodden pattern, so this is joining a crowd rather than
inventing a convention.

Two things the blueprint must get right, both of them inherited footguns:
**mode `queued` or `parallel`, never `single`**, or two tags starting at the same
minute lose one; and it triggers on our `dayline_tag` event rather than on a
calendar trigger of its own, so it inherits our 5-minute freshness instead of the
calendar trigger's 15, and so a tag is scoped and discovered exactly once rather
than per-automation.

The discovery surface then needs no invented UI at all: list the tags seen, and
next to each unbound one, a link that imports the blueprint. Exactly what the
Tags panel does.

### Detecting the start — verified, because the obvious answer is wrong

**A calendar entity's state cannot be the trigger.** It is defined as *on when an
active event exists*, and its attributes describe only the next event. So:

- **Overlapping events produce no second transition.** A tagged event starting
  inside an untagged one finds the state already `on`, and would be silently
  ignored. This is a recurring community complaint, not a corner case.
- **Back-to-back events are the same failure** — something is active at every
  instant, so there is no momentary `off` to catch.

**Home Assistant's own calendar trigger does fire per event**, which the docs
give away by warning against automation mode `single` so that *multiple events
starting at the same time* all fire. That is only meaningful for something
iterating events rather than watching state.

**But it is not polling-free**: "calendars are read once every 15 minutes […]
do not plan events less than 15 minutes away." It polls coarsely and schedules
precise fires from what it found.

So the trigger confirms the shape without being worth consuming. The feed
already fetches every 5 minutes; **schedule a callback per tagged event off that
fetch** — per-event by construction, correct across overlaps and back-to-back,
and three times fresher than the trigger we would otherwise inherit.

Entity state still earns a job, just not this one: an `off`→`on` transition is a
cheap *something started* nudge to re-fetch early, narrowing the window in which
an event created minutes before its start is missed. Use it for what it is
reliable at — that something changed — and never for what it is not: what.

**Ships with a documented caveat, whichever mechanism wins.** A tag on an event
created shortly before it starts may not fire at all — 15 minutes if we lean on
Home Assistant's trigger, 5 if we schedule off our own fetch. That is acceptable
but it is not discoverable, and a tag that silently does nothing is exactly the
failure this design is trying to avoid elsewhere. It goes in `INSTALL.md` next
to the tag documentation, not only here.

> Still open: a fire missed while Home Assistant was down. A grace window (fire
> on start-up if the tagged event is still running and we never fired) is
> probably right, but it fails silently in both directions, so it wants a
> decision rather than a discovery.

### Two layers of scope, and why both

**An unbound tag does nothing.** That is the primary defence and it covers the
common case by construction: a school calendar's `#vacation!` for winter break
sits inert forever because nobody ever pointed it at a script.

**A per-calendar `Dayline Control` label is the second layer**, and it exists
for one specific trap: the day you bind `#vacation` for your own trips, every
`#vacation` already sitting in every subscribed calendar becomes live
retroactively. Scoping which calendars may fire is what stops a binding made in
July from reaching backwards into an event someone else wrote in November.

Default deny. A calendar you add tomorrow displays but cannot fire.

Frame it in the UI as *which calendars speak Dayline's vocabulary*, not as
trust. The honest answer is one or two of them, because everyone else is just
writing down their week.

### Chips

Three states, which happen to be exactly the card's thesis in miniature:

| Chip | Meaning |
|---|---|
| Outline, on a future row | **will fire** — the house's stated intention, hours ahead |
| Filled, on a past/current row | **did fire**, at this time |
| Flat grey | **will do nothing** — unbound, or on a calendar that cannot fire |

The grey chip matters more than it looks. Someone types `#vacation!` and gets an
answer instead of silence, and silence is what makes people conclude a system is
broken and start working around it.

### Discovery, and the options surface

Do not ship a config screen and ask for it to be filled in. **Collect every
`#tag` seen across the fetch window and surface the unbound ones**, so the
options surface populates itself from actual behaviour:

> `#Away` → House Away ▾
> `#Quiet` → *(seen 4 times, does nothing yet)* ▾
> `#vacation!` → *(seen 1 time, on Kid — that calendar cannot fire)*

Implement it as **generated entities, not a second custom card**: one `select`
per discovered tag, options being the available scripts and scenes plus
"nothing". A stock Entities card draws it. No second HACS repository, no second
bundle, no theme drift, and it inherits Home Assistant's own permission model
instead of inventing one.

Matching is loose (case-insensitive, word boundary, trailing punctuation
tolerated — real tags are messy) and binding is exact.

### The row it produces

A tag firing is already the shape of a "what just happened" row, with its cause
in hand:

> ✦ *Away — `#Away` on Admin's calendar, 9:12 AM. Lights off, thermostat to 62,
> garage closed.*

The consequences listed are the script's own steps, so the row is accurate by
construction rather than by maintaining a second description of what the script
does. Same trick as the schedule calendar: the thing that happens and the words
explaining it are one object, so they cannot drift.

> Not ours, but worth writing down: a short transition delay before presence
> commits to Away stops a phone blipping at the geofence edge from thrashing the
> house. That belongs in the user's own automation, not here.

---

## Phase 3 — Things that need no input at all

The cheapest magic is derived. None of the below asks anyone for anything.

- **Leave-by, not start-at.** "Leave at 3:40" beats "4:00 appointment". Event
  location plus a travel-time integration gets there with nothing typed.
  Highest value per unit of work on this page, and cheaper to set up than
  expected:
  - **Waze Travel Time needs no API key.** Google Maps Travel Time needs a key
    *and* billing enabled with a card on file, and at its 10-minute polling rate
    a single sensor roughly consumes the free tier on its own. Waze is the
    default; Google is for people who already have the key.
  - **Call it on demand, don't stand up sensors.** Waze exposes a
    `get_travel_times` action, so the feed can ask about the two or three events
    that actually have locations today rather than maintaining a standing sensor
    per destination. That sidesteps the polling cost entirely.
  - **A readiness buffer is not travel time.** Travel time is a fact about
    roads; "this family needs fifteen minutes to get out of the door" is a
    household constant, and conflating them makes both wrong. One number, set
    once, added to every leave-by.
  - Status quo until then is fine and worth not breaking: an extra calendar
    entry when travel is notable, with the phone's own native notification
    doing the telling. That path involves no Home Assistant at all, which by
    principle 2 makes it hard to beat.
- **The gaps.** "2h 40m free after lunch." People plan against negative space
  and no calendar app shows it.
- **The evening pivot.** After a cutoff hour the card's question changes from
  *what is left of today* to *what does tomorrow demand, and when must you get
  up*. `sensor.*_next_alarm` makes this real without configuration — it tells
  you when tomorrow starts from the person's own behaviour. (Android exposes it
  directly; iOS needs a Shortcut to push it.)
- **Collisions.** Two commitments, one car, or two people needed in different
  places. Detectable from attendees and locations.
- **Silent failure.** The dark half of *what will the house do without me*: an
  automation that should have fired and did not. Nobody surfaces this, and it is
  what quietly erodes trust in a smart home.

---

## Phase 4 — Reach

Dayline currently waits to be looked at. These give it hands.

- **Actionable notifications.** The `action` descriptor is already a service-call
  blob written by the feed, so it renders as a button on the spine *or* as a
  notification action on a lock screen with no second contract. "Laundry has been
  sitting 40 minutes" → [Moved it] → the row completes and nothing was opened.
- **`conversation` triggers** for fixed sentences. No model in the loop, works
  when the GPU is busy, and the spoken path lands in the same place the calendar
  path does — two surfaces, one state.
- **An LLM tools API.** Register `dayline.whats_left`, `dayline.next_commitment`,
  `dayline.complete_action` with the conversation agent. A small local model gets
  a sentence that was already computed correctly instead of twenty raw calendar
  entities to reason over. Write tools are **exactly the action descriptors the
  card already renders** — one contract, one thing to test, and a model can only
  invoke what was already valid to invoke.

Keep "prefer handling commands locally" on so the deterministic path stays
deterministic.

---

## Phase 5 — Learning

Ordered by confidence. The first one is a straight improvement to code that
already exists; the last is genuinely speculative.

- **Semantic dedupe.** The merge currently folds near-duplicates by string
  similarity, which will never fold "Dentist — Kid" against "kid dental appt".
  A ~130MB embedding model does. Improves a thing already built rather than
  adding a new failure mode; highest confidence item here.
- **Priority prediction.** Same embeddings plus a regression trained on observed
  behaviour — what got expanded from `+N more`, what got tapped, what got
  ignored. A few kilobytes of learned weights per household, and the card stops
  needing declared priorities.
- **The proposal loop.** Mine recorder history for repetition; when a pattern
  crosses a threshold, put a *question* on the spine:
  > *You have turned the porch light on within 10 minutes of sunset 9 of the last
  > 12 evenings.* **[Let me do it] [No]**

  This is statistics, not language — co-occurrence windows, day-of-week
  periodicity, sequence mining. Do not reach for a model. **The confirmation is
  the product**: a system that silently automates is frightening, a system that
  proposes and remembers the answer is a colleague. Ignoring a proposal is a
  valid answer, and one ignored three times stops being offered.
- **Phrasing, at authoring time only.** A small instruct model turning a
  newly-accepted proposal into a sage sentence — once, cached as a template,
  never regenerated at render. The hand-written sentence map stays the fallback.

Everything here runs in the coordinator, off the render path, cached.

---

## Open questions

- **A tag fire missed while Home Assistant was down.** Fire late on start-up if
  the event is still running, or stay quiet? Silent either way, which is what
  makes it worth deciding deliberately rather than discovering.
- **Chip geometry on all-day rows**, which have their own layout — a question
  for the card, not the feed.
- **Whether the blueprint should offer the tag as a dropdown** of discovered
  tags or a free-text field. A dropdown is friendlier and immediately stale;
  free text always works and lets you bind a tag before you have ever used it.

## What was looked up rather than assumed

- [Tags](https://www.home-assistant.io/integrations/tag/) and the
  [announcement post](https://www.home-assistant.io/blog/2020/09/15/home-assistant-tags/)
  — the discovered-then-bound pattern the `#tag` surface copies.
- [Calendar Notifications & Actions](https://community.home-assistant.io/t/calendar-notifications-actions/612326)
  — the established community blueprint for keyword-in-calendar → action.
- [Input select](https://www.home-assistant.io/integrations/input_select/) and
  [Correct way to implement home modes?](https://community.home-assistant.io/t/correct-way-to-implement-home-modes/460255)
  — `input_select.house_mode` is convention, not a standard.
- [Alarm control panel](https://www.home-assistant.io/integrations/alarm_control_panel/)
  and the [vacation-mode architecture discussion](https://github.com/home-assistant/architecture/discussions/500)
  — the first-party abstraction people borrow, and why it fits imperfectly.
- [Waze Travel Time](https://www.home-assistant.io/integrations/waze_travel_time/)
  (no API key) versus
  [Google Maps Travel Time](https://www.home-assistant.io/integrations/google_travel_time/)
  (key plus billing).
- [Calendar entity](https://www.home-assistant.io/integrations/calendar/) — state
  is "on when *an* active event exists", attributes describe only the next event,
  which is why state cannot be the trigger.
- [Calendar event started trigger](https://www.home-assistant.io/triggers/calendar.event_started/)
  — fires per event (hence the mode-`single` warning), reads calendars every 15
  minutes.
- [Local Calendar concurrent events with automation triggers](https://community.home-assistant.io/t/local-calendar-concurrent-events-with-automation-triggers/656797)
  — the overlap failure, reported repeatedly by people who reached for state
  first.

## Explicitly not doing

Carried forward and still deferred: drag-to-reschedule, the card's own
`getConfigElement`, the `day_spine` → `dayline` internal rename, Grocy as an
actionable backend, security/awareness variants 2b/2c, a light theme, email or
message ingest for flight confirmations.
