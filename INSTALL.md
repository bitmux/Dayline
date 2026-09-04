# Installing

Two pieces: the **card** renders, the **feed** decides what it renders. There
are two ways to get the feed, and you only need one.

| | Integration (recommended) | YAML package |
|---|---|---|
| Setup | Click through a dialog | Edit a file, reload |
| Changing what it says | Settings → Devices & services → Configure | Edit Jinja, reload |
| Entities created | One | Two |
| Needs | HA 2024.11+ | HA 2024.6+ |
| Needs the card installed | Yes | Yes |

---

## The card — install this whichever feed you choose

**HACS → ⋮ (top right) → Custom repositories.** Repository
`https://github.com/bitmux/Dayline-card`, type **Dashboard**. Open it in the
HACS list, **Download**, then hard-refresh the browser.

HACS copies the bundle into `/config/www/community/Dayline-card/` and registers
it as a Lovelace resource for you. Check it landed under **Settings →
Dashboards → ⋮ → Resources**; you should see one `/hacsfiles/Dayline-card/…`
entry of type **JavaScript module**.

> **Why this is a separate repository.** HACS keys a custom repository by
> `owner/repo` and gives it exactly one category, so one repository cannot be
> both an Integration and a Dashboard. Dayline used to sidestep that by having
> the integration serve its own bundle and add the Lovelace resource itself —
> which meant reaching into `hass.data["lovelace"]` and writing to another
> integration's storage collection through no public API. It worked until it
> didn't. Registering a frontend resource is HACS's job.

---

## Option A — the integration

### Through HACS

**HACS → ⋮ (top right) → Custom repositories.** Repository
`https://github.com/bitmux/Dayline`, type **Integration**. It then appears in
the HACS list as Dayline — open it, **Download**, and restart Home Assistant.

### By hand

Copy `custom_components/day_spine/` to `/config/custom_components/day_spine/`
and restart Home Assistant.

### Either way

**Settings → Devices & services → Add integration → Dayline**.

Nothing on the setup form is required. Submit it untouched and every calendar in
the instance goes on the spine — a real day on the wall in one click, which
beats being interrogated before you have seen anything. Weather and a to-do list
are the two optional pickers: the first adds the forecast to upcoming rows, the
second adds actionable rows with a Done button.

Then narrow it with a label, below.

## Labels and tags — where the settings went

Dayline is configured almost entirely from outside its own config flow, by two
**labels** you apply in Home Assistant's own UI and by `#tags` you type into your
own calendar event titles.

This is not minimalism for its own sake. A label lives on the thing it describes,
takes effect without a restart, and is edited in the place you were already
looking; a setting lives in a list somewhere else and goes stale the moment you
add a calendar. And a `#tag` is the only place to put metadata on an event owned
by someone else's calendar provider — Google will not store a Dayline field for
you, but it will store the title you typed.

So when you go looking for a setting and cannot find it, the answer is usually a
label. **Settings → Areas, labels & zones → Labels** creates them; you apply one
from an entity's settings dialog, or in bulk by ticking rows in
**Settings → Devices & services → Entities** and choosing **Add label**.

The integration's **Configure → Labels and tags** page says which entities
currently carry each label, so you can check your work without leaving Home
Assistant.

### `Dayline` — what goes on the card

Apply it to a **calendar** and that calendar joins the spine. As soon as any
calendar carries it, the setup list stops being consulted entirely — adding a
calendar next month is a label, not a trip through Configure.

Apply it to **anything that is not a calendar** — a light, a lock, a media
player — and it means the other thing: explain that entity when it changes on
its own. You get a plain sentence built from the entity's own name
("Porch light turned off"), and **Configure → What just happened** is where you
write a better one.

With no `Dayline` label anywhere, the setup list is used; with neither, every
calendar is.

### `Dayline Control` — what is allowed to act

A `#tag` in an event title does nothing unless that calendar *also* carries
`Dayline Control`.

Default deny, deliberately. Subscribe to a school calendar and someone else's
`#vacation` would otherwise be a remote control for your house. Without the
second label the chip still renders — flat grey, meaning "this will do nothing"
— because silence is what makes people decide a system is broken.

### `#tags` — making an event do something

Put a tag anywhere in the title:

```
Dinner out #Away
Book club 7pm #Quiet
Ski trip #Vacation
```

Matching is loose on purpose, because real tags are messy: any position, any
case, trailing punctuation tolerated, so `#vacation!` reads as `vacation`. A
leading letter is required, which keeps "Room #3" out of it. The tag is lifted
out of the title before anything else reads it, so the card shows *Dinner out*
with a chip beside it.

When a tagged event starts, Dayline fires a `dayline_tag` event:

```yaml
event_type: dayline_tag
data:
  tag: Away
  calendar: calendar.family
  summary: Dinner out
  start: "2026-09-03T18:15:00-05:00"
  end: "2026-09-03T21:00:00-05:00"
  all_day: false
```

and stops there. **Dayline never runs your automations, writes automations, or
touches another integration's storage.** Binding a tag to an action is an
ordinary automation, which is Home Assistant's job.

The quickest way to write one is the shipped blueprint. **Settings → Automations
& scenes → Blueprints → Import blueprint**, and paste:

```
https://github.com/bitmux/Dayline/blob/main/blueprints/automation/dayline/dayline_tag.yaml
```

It asks for a tag and for what to do, and the "what to do" is a full action
selector — an Alarmo call, an `input_select.select_option` against a helper you
already have, a `script.turn_on`, whatever your house actually uses. Dayline
never guesses your entity names, which is why there is no "what sets house mode"
setting: there could not be one that was right.

The automation it writes is an ordinary automation. Open it and add conditions
("unless someone is still home") whenever you outgrow the blueprint.

Two rules worth knowing, both settled rather than incidental:

- **A tag fires once, at the event's start. Nothing fires at the end, ever.**
  Coming back is its own entry — `Return #Home from vacation` at 4pm — which
  keeps the return visible on the spine instead of hiding it in a timer.
- **An event already under way when Dayline first sees it fires immediately.**
  That is what makes an all-day `#Away` work at all: its start is midnight, and
  midnight is always behind us. What has already fired is remembered across
  restarts, so a reload does not re-assert this morning's tags.

Calendars are read every five minutes (Configure → Tuning). A tag added to an
event that starts within the next minute or two may miss its moment.

Chips say which of three things is true: **outline** for a tag that will fire,
**filled** for one that has, **flat grey** for one that will do nothing.

What a grey chip cannot tell you is whether anything is *bound* to the tag.
Home Assistant offers no trustworthy way to ask "does an automation listen for
this", and reading other integrations' stored configs to guess would be exactly
the mistake that broke this card's own Lovelace registration. Grey means "this
calendar is not allowed to fire" — never "nothing is listening".

### Changing what it says

**Settings → Devices & services → Dayline → Configure.** Six sections:

- **Labels and tags** — read-only. What is labelled right now, which calendars
  may act, which tags have been seen today, and where to change each.
- **Calendar wording** — each calendar's pill label, colour, default priority,
  and whether it is a *schedule* calendar. Order matters: when two calendars carry
  the same event worded differently, the first one listed supplies the wording.
  Which calendars appear here is the `Dayline` label's business, not this page's.
- **Sentences** — what the house does, in plain words, matched against text in
  an event's title. First match wins, so the order of the list is the order of
  precedence. This *describes*; to make an event act, use a `#tag`.
- **What just happened** — better wording for the automatic changes of entities
  carrying the `Dayline` label. The label decides what is watched; this decides
  how it reads.
- **Weather and to-do** — the two entity pickers, plus the fallback calendar
  list for anyone not using labels.
- **Tuning** — sun rows, merge similarity, excluded titles, timings, and
  optional templates for the headline and the "Now" subline.

### Calendar colour — the *who* axis

The spine already answers *what* and *when*. Colour answers *who*: pick one per
calendar in **Configure → Calendar wording**, and it tints that calendar's pill
in the legend and the dot beside each of its entries.

**Home Assistant does not pass a calendar's own colour through.** Your CalDAV
server almost certainly stores one — `{http://apple.com/ns/ical/}calendar-color`
is a de facto standard that Radicale, Baikal, Nextcloud, SOGo and Fastmail all
serve, and Google has `backgroundColor` on its calendarList entries — but a
Home Assistant calendar entity has no colour field anywhere, and neither does
the event data `calendar.get_events` returns. There is nothing to read, so the
colour is chosen here instead. (It was never quite the calendar's colour anyway:
in Google it lives on *your subscription*, so two people sharing a calendar
already see different colours.)

Seven to choose from — blue, cyan, teal, green, violet, magenta, rose — plus
*default*, which means no colour of its own.

Terracotta and sage are deliberately not on the list. They already mean
something on this card: terracotta is **now**, sage is **the house acting on its
own**. A calendar wearing either would be making a claim about the day rather
than about whose day it is.

The colour reaches the legend pill, the ring on an upcoming entry's dot, a
muted version of the past dot, and the icon on an all-day row. It deliberately
never touches the now marker, a running entry, or a sage sentence — where a
colour already means something, meaning wins over identity.

## Rows an automation puts there

A calendar event happens at a time. Plenty of what is left of your day does not:
the garage is open, the dishwasher finished, a script declined to do something.
Any automation can put those on the spine, and take them away again.

Both are ordinary Home Assistant actions, filled in from the UI like anything
else — every field is a selector, so there is no YAML to write.

### `day_spine.show`

| Field | |
|---|---|
| **Message** | Required. The line on the card |
| **Id** | Your name for the row. Omit and one is derived from the message |
| **Level** | *Normal*, *Information*, or *Alert* |
| **What the house will do** | Optional second line, in sage |
| **Priority** | *High* (default) never collapses off the card |
| **Duration** | Seconds until it leaves on its own. Omit and it stays |
| **Start** | Where it sorts into the day. Defaults to now |
| **Related entity** | Optional. What the row is about, for the more-info dialog |
| **Confirm button** | A label and an action |
| **Cancel button** | A label and an action |

The two buttons are collapsible sections in the action editor. Each takes a
label and an **action picker** — the same control a button card gives you, so a
Dayline button can do anything a dashboard button can: perform an action, open a
more-info dialog, navigate somewhere, or open a URL.

They are only called *confirm* and *cancel* because that is what two buttons on
one row nearly always are. Nothing enforces it — both can call any action, and a
row with one button is perfectly normal. The second is drawn quieter and without
a tick, because "not now" should not look as inviting as the thing the row is
asking for. There is no third: a row is one line of a timeline, and a third
button makes it a dialog.

In YAML the four button fields are flat — `confirm_label`, `confirm_action`,
`cancel_label`, `cancel_action` — because a section in an action editor groups
fields visually and nothing more, the same way `light.turn_on` takes
`brightness` from inside its collapsed section. Filling them in from the UI
gets this right for you.

Calling `show` again with the same **id** *replaces* the row rather than stacking
a copy, so it is safe from an automation that runs on every state change.

### `day_spine.dismiss`

Takes the **id** and removes the row. An id that is not there is not an error, so
an automation tidying up after itself does not have to check first. This is the
usual thing to put behind a cancel button.

Pushed rows are persisted, so a restart does not silently drop a claim an
automation made about your house.

### Levels

*Normal* looks like everything else. *Information* is quieter. *Alert* draws the
row's dot and icon in red with a halo — and **nothing else on this card is red**,
which is the only reason red still means something by the time you need it. The
level reaches the dot and an icon and stops there: the row still has to read as
part of one day, and a red band across it would make the timeline stop being a
timeline exactly where it matters most. The icon is not decoration either —
colour alone would leave the distinction invisible to anyone who cannot see red,
on the one row where "is this a problem" is the whole message.

### The garage, end to end

Two automations and a script, none of them knowing anything about Dayline beyond
the two actions.

**When it opens** — an automation triggered on `cover.garage` becoming `open`
calls `day_spine.show`: message *Garage is open*, id `garage_open`, level
*Information*, confirm button *Close it* performing `script.turn_on` on your safe
script, cancel button *Leave it* performing `day_spine.dismiss` with id
`garage_open`.

**When it closes** — the same automation on the other trigger calls
`day_spine.dismiss` with id `garage_open`.

**When the script declines** — the branch of `script.close_garage_safely` that
finds a person in the camera calls `day_spine.show` itself: level *Alert*,
message *Garage did not close — someone is in the driveway*, and a **Show me**
button whose action is more-info on the camera.

That last part is the whole design. **Dayline learns nothing about what happens
inside your script** — deliberately, the same way it never inspects what an
automation does with a `#tag` — so the explanation is written by the only thing
that actually knows. The card also stops dimming a pressed button after twenty
seconds whether or not anything came back, so a script that declined leaves a row
that still reads as unfinished.

### Schedule calendars

Set a calendar's role to **schedule** and it stops describing people's plans and
starts describing the house. Its events become House rows, and each event's
**description** becomes the sage sentence. Point your automations at the same
calendar:

```yaml
triggers:
  - trigger: calendar
    entity_id: calendar.house_schedule
    event: start
conditions:
  - "{{ trigger.calendar_event.summary == 'Morning' }}"
```

Now the schedule, the words explaining it, and the trigger that fires from it
are one thing you edit in the calendar panel. They cannot drift apart, which is
the failure mode a hand-kept list of times always eventually hits.

---

## Option B — the YAML package

Copy `ha/day_spine.yaml` to `/config/packages/day_spine.yaml`. If you have never
used packages, add this to `configuration.yaml` first:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Work through the blocks marked **EDIT ME**, then **Developer Tools → YAML →
Reload template entities**.

The card is installed exactly the same way as it is for the integration — the
HACS **Dashboard** repository above. The package changes where the feed comes
from, not how the card gets to the browser.

> The package needs two entities where the integration needs one. A template
> sensor has no memory between evaluations except its own previous attributes,
> so "what just happened" has to accumulate in a second sensor that the first
> one reads. The integration just keeps a list in memory.

> **One known difference:** when an event falls between forecast hours, the
> integration picks the *nearest* hour and the package picks the *first* hour
> within an hour either side. They can disagree by one forecast step on an event
> starting near the half hour. The integration's behaviour is the correct one.

---

## Adding the card

**Add card → search "Dayline"**, which fills in the feed sensor for you. Or **Add
card → Manual**:

```yaml
type: custom:day-spine-card
entity: sensor.day_spine
```

> **Check that entity id.** The sensor is named after the config entry's title,
> so an integration you named "Dayline" gives you `sensor.dayline`, not
> `sensor.day_spine`. Whatever appears under **Settings → Devices & services →
> Dayline → 1 entity** is the right answer.

> **If the card says "Custom element doesn't exist" and Dayline is missing from
> the card picker**, the bundle did not reach your browser — which is about the
> card repository, not the integration. Check **Settings → Dashboards → ⋮ →
> Resources** lists one `/hacsfiles/Dayline-card/day-spine-card.js` of type
> **module**; if it is missing, HACS did not finish installing the Dashboard
> repository. If it is there and the card still does not appear, hard-refresh
> (Ctrl/Cmd-Shift-R). On a YAML dashboard nothing is registered for you: add
> that URL to your own `resources:`, type **module**.

### Size and placement

**This card is designed to be a full-width column, run at its full height — a
sidebar for the day, not a tile.** In a sections dashboard it asks for the whole
width of one section and ten rows, and you can drag both from the card's own
layout controls.

Height is worth a deliberate choice. **Fixed height is the recommendation**: the
card fills what you give it, and the spine scrolls inside while the header,
the all-day frame and the footer stay put. `rows: auto` also works, but the day
grows and shrinks through the day, so everything below the card moves with it.

If the height you pick is shorter than the day, nothing is lost — the spine
scrolls, and the density budget below decides what is worth showing first.

### Options

Every key below is optional except `entity`. They live on the card because the
dashboard is where people go to change how a dashboard looks; what the feed
*says* is configured in the integration.

| Key | Default | What it does |
|---|---|---|
| `entity` | — | The merged feed sensor. Required. |
| `show_all_day` | `true` | The all-day region |
| `max_all_day` | `4` | All-day entries drawn before the rest collapse behind a `+N more all day` line, expandable in place. Anything with a Done button or a tag about to fire is pulled to the front rather than collapsed. Set it to `20` to show every one, as before. The frame is also capped at two fifths of the card's height and scrolls past that, so it can never squeeze the day itself off the card |
| `show_clock` | `true` | The clock in the header |
| `show_day` | `true` | The big day name |
| `show_headline` | `true` | The line under the day name |
| `show_past` | `true` | Entries whose time has passed. Off makes the card purely forward-looking. |
| `show_sun` | `true` | Sunrise and sunset rows |
| `show_tags` | `true` | The `#tag` chips beside event titles |
| `show_progress` | `true` | The progress bar on entries currently running |
| `time_format` | `auto` | `auto` follows your Home Assistant locale; `12` or `24` overrides it |
| `font_family` | — | A CSS font stack for the whole card, e.g. `Arial, sans-serif` |
| `heading_font_family` | — | Overrides `font_family` for the day name and clock alone |
| `show_sources` | `true` | The calendar pills, inside the legend section. `show_legend: false` hides them too; this is the finer control for keeping the words without the pills. |
| `show_legend` | `true` | The whole footer section — explanatory text *and* the calendar pills. Turn it off once people stop needing it. |
| `legend` | — | Replace the footer text |
| `interactive_rows` | `false` | Rows with an entity open more-info on tap |
| `max_past` | `3` | Struck-through entries kept above "now" |
| `max_future` | `6` | Upcoming entries shown before collapsing |
| `collapse_low_priority` | `true` | Drop `low` entries from the window before `normal` ones |
| `recent_events` | `true` | The short-lived "what just happened" lines |
| `recent_ttl` | `300` | Seconds a recent line lives if the feed did not set `expires` |
| `show_weather` | `true` | Condition icon and temperature under the time, on upcoming entries |
| `show_duration` | `true` | The duration chip on upcoming entries that have an end |
| `use_ha_theme` | `false`, but a newly added card starts with `true` in its YAML | Take colors *and the card surface* from the active HA theme instead of the Organic palette — including a frosted theme's blur, shadow and border, so the card is made of the same material as everything around it. Geometry and typefaces stay fixed either way. |
| `load_fonts` | `true` | Fetch Caprasimo and Figtree from Google Fonts. Set `false` on an offline tablet — the card falls back to Georgia and the system sans. |

Live rows, overdue actionables and all-day entries are never collapsed by
`max_past` / `max_future`. Anything that is collapsed is counted on the
`+N more today` row — the card never hides something without saying so.

---

## Working on it

```bash
npm install && npm run build
```

`npm run build` writes `dist/day-spine-card.js`. `npm run watch` rebuilds on
save. To publish a card change, `npm run stage-card` copies that bundle into the
sibling `Dayline-card/` checkout, which is the HACS Dashboard repository and
holds the built file and nothing else — commit and push it there.

Checks, all of which run without a Home Assistant:

```bash
npx tsc --noEmit
.venv/bin/python -m pytest tests -q
.venv/bin/python tools/check-flow.py
```

`tests/` covers the merge — deduping, sentence matching, sun times, stickiness,
forecast joining, counting. `tools/check-flow.py` catches config-flow fields
with no translation, which Home Assistant renders as a blank label rather than
an error.

### Driving a test instance

`tools/ha-dev.py` is the whole deploy loop in one place, so it does not have to
be retyped:

```bash
python3 tools/ha-dev.py doctor
```

checks the chain in the order it actually breaks — Home Assistant up, feed
sensor producing entries, both HACS repositories installed, the card registered
as a Lovelace resource, and that resource's URL actually serving a file. That
last check matters: a resource row is just a string, and it stays exactly as
convincing after the file behind it stops existing.

```bash
git push origin main && python3 tools/ha-dev.py deploy
```

pulls both repositories through HACS, restarts, waits for the API to go away and
come back `RUNNING` — not merely to answer, which it keeps doing for a moment
after the restart request — and then runs `doctor`. Push first: HACS pulls from
GitHub, not from your working tree.

Also `update [integration|card]`, `restart`, `resources`, `feed`, `logs [--all]`
and `repos`. There is a `ha-dev` skill wrapping the same commands.

### Testing against a real instance

The checks above prove the merge against stub data, which is only ever as right
as whoever wrote the stub. To run the same code against a live instance, put its
address and a long-lived access token in `.ha-env` at the repo root (gitignored —
it is a credential):

```bash
printf 'HA_URL=http://your-ha\nHA_TOKEN=eyJhbGci...\n' > .ha-env && chmod 600 .ha-env
```

Then:

```bash
python3 tools/seed-ha.py
```

`seed-ha.py` creates two Local Calendars and a to-do list and fills them with a
day positioned around the server's own clock — a couple of overlapping live
events, a schedule calendar carrying sage sentences in its event descriptions, a
near-duplicate pair for the dedupe to fold, and enough entries to make the
density budget engage.

```bash
python3 tools/live-merge.py
```

`live-merge.py` fetches through the real `calendar.get_events`,
`todo.get_items` and `weather.get_forecasts`, prints the exact keys each one
returned, runs `merge.py` over them, and writes `dev/live-sample.json`. Open
`dev/live.html` to see the real card draw a real day on the real clock.

That last part matters: `dev/index.html` pins its clock to 2:39 PM to reproduce
the design reference, so it can never show you a timezone bug. `dev/live.html`
does not pin anything, which is how the missing sunset was found.

```bash
python3 tools/live-sensor.py
```

`live-sensor.py` goes one step further and takes the finished attributes off
`sensor.dayline` — the coordinator's own output, from *inside* Home Assistant —
into the same `dev/live-sample.json`. `live-merge.py` proves the merge; this
proves the integration. Between them the only thing left unproven is the card.

`tools/seed-ha.py` is safe to re-run, but it appends: run it twice in a day and
you get two of everything. It cannot clear up after itself — Home Assistant has
no `calendar.delete_event` service — so remove and re-add the Local Calendar
entries when the fixtures get muddy.

> `dev/live-sample.json` is gitignored. It is generated from whatever calendars
> the instance actually has, and on a real instance that is family data.

### The dev harness

Renders every card state side by side with no Home Assistant involved:

```bash
python3 -m http.server 8765
```

then open `http://localhost:8765/dev/index.html`. With that server running,

```bash
.venv/bin/python tools/shots.py
```

regenerates `design/screenshots/01`, `02`, `03` and `07` by driving headless
Chrome over `dev/shot.html` — the screenshots in the README are captures of the
built card, not drawings of it, so they cannot claim something the card does not
do. Its clock is
pinned to 2:39 PM so it reproduces the design reference whenever you open it.
Two of its panels are real feed output — `tools/render-integration.py` and
`tools/render-feed.py` regenerate them, and both catch errors in their
respective merge before they reach a live instance.
