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

Setup asks four things, and only the first is required:

- **Calendars** — the ones that belong on the wall. Calendars you leave out are
  never fetched, which is the point when you have twenty of them.
- **Weather** — optional, adds the forecast to upcoming rows.
- **To-do list** — optional, adds actionable rows with a Done button.

That is enough to render, provided the card is installed too.

### Changing what it says

**Settings → Devices & services → Dayline → Configure.** Five sections:

- **Sources** — which calendars, weather entity, to-do list.
- **Calendars** — each calendar's pill label, default priority, and whether it
  is a *schedule* calendar. Order matters: when two calendars carry the same
  event worded differently, the first one listed supplies the wording.
- **Sentences** — what the house does, in plain words, matched against text in
  an event's title. Added and edited one at a time. First match wins, so the
  order of the list is the order of precedence.
- **What just happened** — one line per entity per state. Only listed entities
  can produce a line, and only when something other than a person caused the
  change; someone who flipped the switch does not need telling.
- **Tuning** — sun rows, merge similarity, excluded titles, timings, and
  optional templates for the headline and the "Now" subline.

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
| `show_sources` | `true` | The calendar pills, at the foot of the card |
| `show_legend` | `true` | The explanatory footer. Turn it off once people stop needing it. |
| `legend` | — | Replace the footer text |
| `interactive_rows` | `false` | Rows with an entity open more-info on tap |
| `max_past` | `3` | Struck-through entries kept above "now" |
| `max_future` | `6` | Upcoming entries shown before collapsing |
| `collapse_low_priority` | `true` | Drop `low` entries from the window before `normal` ones |
| `recent_events` | `true` | The short-lived "what just happened" lines |
| `recent_ttl` | `300` | Seconds a recent line lives if the feed did not set `expires` |
| `show_weather` | `true` | Condition icon and temperature under the time, on upcoming entries |
| `show_duration` | `true` | The duration chip on upcoming entries that have an end |
| `use_ha_theme` | `false` | Take colors from the active HA theme instead of the Organic palette. Geometry and typefaces stay fixed either way. |
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
