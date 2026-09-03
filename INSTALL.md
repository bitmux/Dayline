# Installing

Two pieces: the **card** renders, the **feed** decides what it renders. There
are two ways to get the feed, and you only need one.

| | Integration (recommended) | YAML package |
|---|---|---|
| Setup | Click through a dialog | Edit a file, reload |
| Changing what it says | Settings → Devices & services → Configure | Edit Jinja, reload |
| Entities created | One | Two |
| Needs | HA 2024.11+ | HA 2024.6+ |
| Ships the card | Yes, automatically | No, register it yourself |

---

## Option A — the integration

### Through HACS

**HACS → ⋮ (top right) → Custom repositories.** Repository
`https://github.com/bitmux/Dayline`, type **Integration**. It then appears in
the HACS list as Dayline — open it, **Download**, and restart Home Assistant.

One repository, one category. The card is not a separate HACS *Dashboard* entry:
Home Assistant does file out plugins and integrations separately, but that split
is about where HACS copies files to, and this integration carries its own card
under `custom_components/day_spine/www/` and registers it at startup. Adding it a
second time as a Dashboard repository would install a duplicate copy of the
bundle that nothing loads.

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

That is enough to render. The card is served by the integration, so there is
**no Resources page step** — add the card to a dashboard and it is there.

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

Then install the card by hand: copy
`custom_components/day_spine/www/day-spine-card.js` to `/config/www/`, and
register it under **Settings → Dashboards → ⋮ → Resources → Add resource** with
URL `/local/day-spine-card.js`, type **JavaScript module**. Hard-refresh
afterwards.

(That is the committed bundle. `dist/` is build output and is not in the repo —
run `npm run build` if you want to rebuild it from source.)

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
> the card picker**, the bundle did not reach your browser. On a storage-mode
> dashboard the integration registers itself under **Settings → Dashboards → ⋮ →
> Resources** as `/day_spine_frontend/day-spine-card.js?v=…` — check it is
> listed, then hard-refresh (Ctrl/Cmd-Shift-R). On a YAML dashboard nothing can
> be registered for you: add that same URL to your `resources:` yourself, type
> **module**.

Every key below is optional except `entity`.

| Key | Default | What it does |
|---|---|---|
| `entity` | — | The merged feed sensor. Required. |
| `show_all_day` | `true` | The all-day region |
| `show_sources` | `true` | The calendar pills |
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

`npm run build` writes `dist/` and stages the bundle into
`custom_components/day_spine/www/`, which is the copy that ships — HACS installs
only what is committed, so the staged one is the one that matters. `npm run
watch` rebuilds on save.

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
