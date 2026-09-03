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

Copy `custom_components/day_spine/` to `/config/custom_components/day_spine/`
and restart Home Assistant. Then **Settings → Devices & services → Add
integration → Dayline**.

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

**Add card → Manual**:

```yaml
type: custom:day-spine-card
entity: sensor.day_spine
```

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

The dev harness renders every card state side by side with no Home Assistant
involved:

```bash
python3 -m http.server 8765
```

then open `http://localhost:8765/dev/index.html`. Its clock is
pinned to 2:39 PM so it reproduces the design reference whenever you open it.
Two of its panels are real feed output — `tools/render-integration.py` and
`tools/render-feed.py` regenerate them, and both catch errors in their
respective merge before they reach a live instance.
