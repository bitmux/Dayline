# Handoff: Home Assistant "Day Spine" timeline card

## Overview

A single dashboard card for Home Assistant that renders **today as one vertical spine**: calendar
events (CalDAV + Google, already integrated), sun events, and scheduled automations, merged into
one chronological list with a live "now" marker. Past entries stay visible but struck through.
Entries the *house* will handle on its own are annotated in sage with a sparkle icon, so no one is
surprised by what happens automatically.

This is the first bite-sized chunk of a larger page-one redesign. Scope of this handoff is the
timeline card only: its **data contract** and its **rendering**.

Why it's being built rather than installed: nothing in core Lovelace or HACS merges calendar +
sun + scheduled-automation entries into one annotated, time-sorted spine. `calendar` cards list
events only; `atomic-calendar-revive` comes closest but has no notion of automation intent and no
"now" marker positioned within the day.

## About the design files

The files in this bundle are **design references created in HTML** — a prototype showing intended
look and behavior, not production code to copy. The task is to recreate this design in Home
Assistant's own environment: a custom Lovelace card (Lit + TypeScript is the conventional choice,
matching how HACS frontend cards are built), consuming a data structure produced on the HA side.

Two implementable halves, and they can be built in either order:

1. **The card** (frontend) — a Lit element that takes a list of timeline entries and renders the
   spine. Should be dumb: no data merging logic in the card.
2. **The feed** (backend) — template sensors / a small custom integration that assembles the entry
   list from calendar entities, `sun.sun`, and automation schedules.

Building the card first against a hand-written mock entry list is recommended — it de-risks the
rendering work and makes the data contract concrete before wiring real entities.

## Fidelity

**High-fidelity.** Colors, typography, spacing, and radii are final and come from a bound design
system ("Organic"). Recreate pixel-accurately. All values are listed under Design Tokens; the
reference HTML carries them inline.

Note the card is designed **dark-first** — the household runs dark mode everywhere. The parent
design system's default ground is a light cream (`#f5ead8`); the card overrides to a dark ground.
If a light variant is wanted later, the token table lists both grounds.

---

## The card

### Purpose

Answer two questions at a glance, without interaction: *what is left of today?* and *what will the
house do without me?*

### Layout

Single column, fixed 520px design width (fluid down to ~360px; it is the left column of a wall-tablet
page one and full-width on phone). Root is `display:flex; flex-direction:column; gap:26.4px`, padding
`26.4px`, background `#1a1714`, border-radius `28px`.

Four stacked regions, top to bottom:

**1. Header** — `display:flex; align-items:baseline; justify-content:space-between; gap:17.6px`
- Left: day name, then a muted subline.
  - Day name: Caprasimo 400, 34px, line-height 1, `#f6f1e9` (`--color-neutral-100`).
  - Subline: Figtree 400, 14px, `--color-neutral-500`, `margin-top:4px`. Content is a rollup
    sentence, e.g. "2 September · everyone home by 6".
- Right: one pill per calendar source. Font `600 10px` ui-monospace, padding `5px 8px`,
  border-radius 999px, background `#2c2620`, color `--color-neutral-400`. Labels: "Google",
  "CalDAV". These are a trust signal — they say *where this came from*, which matters in a house
  where a renamed entity has broken things before. If a source is stale or erroring, that pill is
  the place to show it (see Error states).

**2. All-day row** (conditional; omit entirely when there are no all-day events)
- `display:flex; gap:10px; align-items:center`, padding `12px 14px`, border-radius 16px,
  background `#241f1a`.
- Lucide `calendar-days`, 18px, `--color-accent-2-400`, `flex:none`.
- Text: Figtree 400, 14.5px, `--color-neutral-300`. Format: `All day · <summary>`. Multiple
  all-day events join with " · ".

**3. The spine** — `display:flex; flex-direction:column` (no gap; each row owns its bottom padding)

Every row is a 3-column flex: time gutter (66px, `flex:none`, `text-align:right`), rail (2px wide,
`flex:none`, `position:relative`), content (`flex:1`).

Row variants:

| Variant | Time gutter | Rail | Dot | Content |
|---|---|---|---|---|
| **Past** | `13px/700` `--color-neutral-600`, `padding-top:13px` | `#332c25` | 10px, `#4a4038`, at `left:-4px; top:18px` | 15px `--color-neutral-600`, `text-decoration:line-through` with `text-decoration-color:rgba(255,255,255,.2)` |
| **Now** | Caprasimo 20px `--color-accent-400`, `padding-top:8px`, time without AM/PM ("2:39") | `linear-gradient(#332c25 0 20px, var(--color-accent-500) 20px 100%)` — grey above the dot, terracotta below | 18px, `--color-accent-500`, `left:-8px; top:12px`, halo `box-shadow: 0 0 0 5px rgba(198,113,57,.22)` | Label "Now" 15px/700 `--color-accent-300`; subline 14px `--color-neutral-500` describing current house state |
| **Future** | `13px/700` `--color-neutral-300`, `padding-top:13px` | `--color-accent-800` | 12px, fill `#1a1714`, `border:3px solid var(--color-accent-2-500)` (hollow), `left:-5px; top:17px` | Title 16px/600 `--color-neutral-100`; optional automation line below |
| **Last future row** | as future | `linear-gradient(var(--color-accent-800) 0 28px, transparent 28px 100%)` — rail fades out rather than stopping hard | as future | as future |

The **automation annotation** is the design's whole point: `font-size:13.5px`,
`color:--color-accent-2-400`, `display:flex; align-items:center; gap:6px; margin-top:3px`, preceded
by a Lucide `sparkles` at 14px. It states the consequence in plain words — "Entry unlocks on her
arrival", "Kitchen 90%, hallway 40%", "Story on Sonos, 20 min, then dark". Never a scene's entity
id, never a bare scene name.

Content row vertical padding: past/future `10px 0 16px`, now `6px 0 18px`, final row `10px 0 0`.

**4. Footer note** — `padding-top:13.2px`, `border-top:1px solid #2c2620`,
`display:flex; align-items:center; gap:10px`. Lucide `info` 16px `--color-neutral-600`; text 12.5px /
line-height 1.45 `--color-neutral-600`. This is explanatory chrome for a card people are still
learning; it is a candidate for removal after a few weeks of use — make it a config option
(`show_legend`).

### Interactions & behavior

Deliberately close to inert. It is an information card, and every tappable thing is a thing that
can feel broken.

- **No row is tappable by default.** Optional `tap_action` per entry (`more-info` on the source
  entity) behind a config flag, off by default.
- **Now marker** advances on a 60s interval; re-sort and re-classify past/now/future on each tick.
  Do not animate its position — it should never appear to be moving on its own while someone reads.
- **Rollover at local midnight** re-fetches the day.
- **Hover** (mouse only, wall tablet is touch): row background lifts to `#241f1a`, 120ms ease.
  No hover treatment if rows are not interactive.
- **Focus-visible** on any interactive row: `outline: 2px solid var(--color-accent); outline-offset: 2px`.
- Respect `prefers-reduced-motion` — skip the hover transition.

### Loading, empty, and error states

These three states are the difference between a card that gets trusted and one that gets ignored,
so treat them as first-class rather than afterthoughts:

- **Loading** — render the header and the spine's rail at full height with no dots; do not collapse
  the card's height, and never flash a spinner. A card that changes size on every load reads as
  unreliable.
- **Empty day** (no events, no automations) — keep the sun rows and the now marker, and set the
  header subline to something plainly true, e.g. "Nothing scheduled." Never render an empty card.
- **Source error / stale entity** — this is the failure mode that has cost trust in this house
  before. Do not silently drop a source. Turn the affected source pill to
  `background:#2e2117; color:var(--color-accent-200)` and append a footer line: "Google calendar
  hasn't updated since 8:14 AM." The card should say what it doesn't know.
- **Entity gone** (renamed / removed) — same treatment, naming the missing entity id. Silence here
  is what makes people stop believing the dashboard.

### Card configuration (proposed)

```yaml
type: custom:day-spine-card
entity: sensor.day_spine        # the merged feed (see Data contract)
title_source: sensor.day_spine  # attribute `headline` supplies the subline
show_all_day: true
show_sources: true              # the CalDAV / Google pills
show_legend: true               # the footer note
interactive_rows: false
max_past: 3                     # struck-through entries retained above "now"
```

`max_past` matters more than it looks: unbounded past entries push the useful part of the day off
the card by evening.

---

## The feed — data contract

The card consumes one ordered list. Everything below is a **proposal to be refined**; the
household's own definition of "what counts as an entry" is still being worked out, and the merge
rules are the genuinely unsettled part of this project.

### Entry shape

```jsonc
{
  "id": "gcal:abc123",           // stable across polls; used for keying
  "start": "2026-09-02T15:50:00-05:00",
  "end": null,                    // null for point-in-time entries
  "all_day": false,
  "kind": "calendar",             // calendar | sun | automation | manual
  "source": "Google",             // display label for the source pill
  "title": "Kid out of school",
  "automation": "Entry unlocks on her arrival",  // null when the house does nothing
  "entity_id": "calendar.family"  // for optional more-info tap
}
```

### Producing it

```yaml
# Recommended: one template sensor, list in an attribute (state itself stays short —
# HA truncates state strings at 255 chars, attributes are the right place for the payload)
template:
  - trigger:
      - platform: time_pattern
        minutes: "/5"
      - platform: homeassistant
        event: start
    action:
      - service: calendar.get_events
        target:
          entity_id: [calendar.family, calendar.wife_work, calendar.school]
        data:
          start_date_time: "{{ today_at('00:00') }}"
          end_date_time: "{{ today_at('00:00') + timedelta(days=1) }}"
        response_variable: events
    sensor:
      - name: Day Spine
        state: "{{ ... count of remaining entries ... }}"
        attributes:
          entries: "{{ ... merged, sorted list ... }}"
          headline: "{{ ... rollup sentence ... }}"
```

`calendar.get_events` (a service with a response, HA 2023.6+) is the right call — it returns a real
event list rather than only the current/next event that the `calendar.*` entity state exposes.

Merge sources:
- **Calendars** — `calendar.get_events` across the CalDAV and Google entities. Dedupe events
  present in both (same summary, start within 60s) — a shared family calendar subscribed twice is
  a common and confusing double-entry.
- **Sun** — `sun.sun` attributes `next_dawn`, `next_setting`, plus solar noon if wanted.
- **Automations** — the unsolved piece. Options, roughly in order of effort: a hand-maintained
  `input_text`/YAML map of "schedule → human sentence"; parsing `automation.*` attributes (fragile;
  triggers aren't introspectable in a useful form); or a small custom integration where each
  automation declares its own display sentence. **A hand-maintained map is the honest starting
  point** — there are maybe a dozen daily automations, and their sentences need human wording
  anyway. Don't build the clever version first.

### Open questions worth resolving before writing the merge

1. **What earns a row?** Every calendar event, or only those with a location, an attendee match, or
   a matching automation? An unfiltered work calendar will bury the household's day.
2. **Whose calendars appear on the shared wall tablet?** Wife's work meetings arguably don't
   belong on a kitchen display; per-source inclusion needs to be config, not code.
3. **How is the rollup sentence computed?** "everyone home by 6" implies presence prediction from
   calendar end times. Start with something dumber and always-true (count of remaining entries)
   and improve it once the card exists.
4. **Timed automations vs. conditional ones.** A sunset automation has a time; "unlock when she
   arrives" does not — it is pinned to the calendar event it relates to. The contract handles this
   by hanging `automation` off the calendar entry rather than giving it its own row. Confirm that
   holds for every case.
5. **Poll interval.** 5 minutes is cheap and fine for calendars; the now marker is client-side and
   ticks every 60s regardless. Google's API quota is the only real constraint.

---

## Design tokens

Taken from the Organic design system's `styles.css` — reference `var(--*)` rather than the hexes
where the stylesheet is available.

**Dark ground (this card)**
| Role | Value |
|---|---|
| Card background | `#1a1714` |
| Raised surface (all-day row, hover) | `#241f1a` |
| Source pill / divider | `#2c2620` |
| Rail, past | `#332c25` |
| Dot, past | `#4a4038` |
| Alert tint | `#2e2117` |

**Design-system tokens used**
| Token | Value | Used for |
|---|---|---|
| `--color-neutral-100` | `#f6f1e9` | Event titles, day name |
| `--color-neutral-300` | `#d9cdb8` | All-day text, future times |
| `--color-neutral-400` | — | Source pill text |
| `--color-neutral-500` | — | Sublines |
| `--color-neutral-600` | — | Past rows, footer, icons |
| `--color-accent` | `#c67139` | Focus ring |
| `--color-accent-300` | — | "Now" label |
| `--color-accent-400` | — | Now time, alert pill text |
| `--color-accent-500` | — | Now dot, active rail |
| `--color-accent-800` | — | Future rail |
| `--color-accent-2-400` | — | Automation annotations, all-day icon |
| `--color-accent-2-500` | `#7a8a5e` | Future dot ring |
| `--radius-md` | 16px | All-day row, stills |
| `--radius-lg` | 28px | Card |

**Spacing** — the Organic scale is density-1.10 and has **no `--space-5`**; steps are
`--space-1` 4.4px, `--space-2` 8.8px, `--space-3` 13.2px, `--space-4` 17.6px, `--space-6` 26.4px,
`--space-8` 35.2px.

**Type** — Caprasimo 400 for the day name only; Figtree 400/600/700 for everything else;
ui-monospace at `600 10px` with `letter-spacing:.14em` and uppercase for kickers and source pills.
Both faces are Google Fonts.

**Icons** — Lucide, stroke-width 2.75 per the design system. Used here: `calendar-days`,
`sparkles`, `info`, and (in the security variants) `footprints`, `package`, `warehouse`, `wifi-off`.

## Assets

None. No images, no logos. The camera stills shown in the wider prototype are diagonal-hatch
placeholders — real camera snapshots substitute in at those positions.

## Screenshots

`screenshots/` — 01, 02, 03 and 07 are captures of the **built card**, produced by
`tools/shots.py` from the mock data in `src/mock.ts`. They are regenerated rather
than drawn, so they cannot drift from what the card actually does. 04 is still a
design-tool export of a variant that has not been built.

| File | What it shows |
|---|---|
| `01-card-ordinary.png` | The card mid-afternoon — the ordinary case, all row variants visible |
| `02-card-empty-day.png` | Empty day: sun rows and now marker remain, card never collapses |
| `03-card-stale-source.png` | Stale Google source — pill tinted, footer states what is missing |
| `04-security-quiet-line-2b.png` | Security option 2b: one fixed slot, three escalation levels |
| `07-card-busy-day.png` | Busy day: overdue actionable, recent event, weather, `+N more today` |

The two other design exports — security option 2c on the spine, and the timeline
in page-one context — had a household's names rendered into the pixels, so they
are not in this repository. They are design references for work not in this pass.

## Files

- `timeline-card-reference.html` — **start here.** The card alone, standalone, dark, opens in a
  browser. Three states side by side: mid-afternoon, empty day, and stale-source.
- `Page One Directions.dc.html` — the full design exploration this came from. Section `2a` is this
  card; `2b` and `2c` show two ways security/awareness could sit next to or inside it; turn 1
  (`1a`/`1b`/`1c`) is the page-one context. Needs `support.js` and `_ds/` alongside it.
- `support.js`, `_ds/organic-.../` — runtime and design system for the file above.

## A note on the household

Worth knowing, because it explains the design's conservatism. Three users: one who built the system,
one who will abandon a control permanently if it fails or is ambiguous once, and a 12-year-old who
will press everything. That third user is why nothing on this card is destructive, and the second
is why the card states its sources, never lies about stale data, and spells out consequences instead
of showing scene names. Latency is a feature request here: the card should paint from cached state
immediately and never block on a fetch.
