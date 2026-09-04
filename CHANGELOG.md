# Changelog

## Unreleased

**The card honours the sections grid, and says what size it wants.** It asks for
the full width of one section and ten rows — it is a sidebar for the day, not a
tile — and both are defaults you can drag rather than rules. Give it a fixed
height and it fills exactly that: the spine scrolls inside while the header, the
all-day frame and the footer stay where you left them. `rows: auto` works too,
but the day grows and shrinks through the day and everything below the card
moves with it, so fixed height is the recommendation.

**Nine more card options, because a dashboard is where people go to change how a
dashboard looks.** `show_clock`, `show_day`, `show_headline`, `show_past`,
`show_sun`, `show_tags`, `show_progress`, and `time_format` (`auto`, `12` or
`24`) join the existing toggles. Hiding something is not the same as collapsing
it: switched-off entries are gone, not counted on the `+N more today` row,
because nobody is waiting to be shown what they asked never to see.

**A clock in the header, and the source pills moved to the foot.** Eight
calendars overflowed a header built for three. The pills are reference material
— you read them when something looks wrong, not every time you glance at the
card — so they now wrap at the bottom, above the legend, still tinting
themselves when a source goes stale. `show_sources` governs them there.

In their place, the time, in the card's heading face and sized so it cannot push
the day down the page. It runs off the same clock as the now marker, so the two
can never disagree, which means it steps on the minute rather than ticking
seconds. `show_clock: false` removes it.

While in there: times, the day name and the same-day test now all use the
instance's own timezone rather than the browser's, so a tablet whose clock has
wandered still shows the house's day. Only display was ever affected —
every comparison in the card is between absolute instants.

**Pick your own font.** `font_family: Arial, sans-serif` on the card, written
exactly as you would in CSS, replaces both typefaces; `heading_font_family`
overrides the day name alone. Pair either with `load_fonts: false` to stop
fetching webfonts nothing is using. The two typefaces are part of the design,
but they are not worth arguing with anyone about on their own dashboard.

**Fixed: a fired `#tag` chip was invisible under an active Home Assistant
theme.** In theme mode every accent shade resolves to the one `--primary-color`,
so the filled chip was drawing its text in its own background colour. Text that
sits *on* an accent fill now has its own token, and in theme mode it takes the
theme's `--text-primary-color`, which is the answer the theme already has.

**Two things that only matter at scale, fixed before anyone hit them.** The
merge compared every entry against every other one — invisible at twenty
entries, and tens of seconds at two thousand. It now stops at the match window,
since `kept` is in start order and nothing further back can be the same event.
And the day itself is no longer written to the recorder database: `entries` is
most of a megabyte on a busy instance and recording it every few minutes would
fill the database with a payload nobody will ever query. The state — a number,
and genuinely worth a graph — still records.

**Labels replace picking calendars out of a list.** Apply Home Assistant's
`Dayline` label to a calendar and it joins the spine — no config flow, no
restart, and adding a calendar next month never involves Dayline at all. The
same label on anything that is not a calendar means the other thing: explain
that entity when it changes on its own, in a sentence built from its name unless
you have written a better one. With no label anywhere, the configured list is
still used; with neither, every calendar in the instance is, because a first run
should render a day rather than interrogate you about one.

**A `#tag` can now act.** When a tagged event starts, Dayline fires a
`dayline_tag` event carrying the tag, the calendar, the summary and the times —
and a shipped blueprint binds it to whatever you like, usually a script. The
binding lives in an ordinary automation you can open and extend, so conditions
("unless someone is still home") are yours to write and Dayline never generates
automations or writes into another integration's storage.

Two rules worth knowing, both settled rather than incidental. **A tag fires once,
at the event's start; nothing fires at the end, ever** — coming back is its own
entry, `Return #Home from vacation` at 4pm, which keeps the return visible on the
spine. And **only a calendar carrying the `Dayline Control` label may fire**:
default deny, so a `#vacation` in a subscribed school calendar shows on the card
and does nothing. An event already under way when Dayline first sees it fires
immediately, which is what makes an all-day `#Away` work at all — its start is
midnight, and midnight is always behind us. What has already fired is persisted,
so a restart does not re-assert this morning's tags.

Calendars are read every five minutes. A tag added to an event starting within
the next few minutes may not fire.

Chips now say which of those three things is true: outline for a tag that will
fire, filled for one that has, flat grey for one that will do nothing.

**`#tags` in calendar event titles are now read and shown.** Put `#Away` in an
event title and the card draws it as a chip beside the row, on timed, past and
all-day entries alike. The tag is lifted out of the title before anything else
reads it, so exclusions, the sentence map, the entry id and the dedupe all
behave exactly as they did before it was added.

Matching is deliberately loose, because real tags are messy: any position, any
case, trailing punctuation tolerated, so `#vacation!` reads as `vacation`. A
leading letter is required, which keeps "Room #3" out of it.

**Nothing acts on a tag yet.** They render inert on purpose — a livelier chip
would be claiming the house is about to do something when it is not. The feed
also publishes `tags_seen` on the sensor, so the vocabulary people actually type
is observable before anything is built to bind it. See
[ROADMAP.md](ROADMAP.md) for where this goes.

Fixed along the way: `dedupe` merged an event's sentence, action, stickiness and
priority but would have dropped a tag that was only on one of the two copies —
and only one person keeping a shared event needs to have tagged it.

## 0.2.0 — alpha, 3 September 2026

**The card is now a separate HACS repository, and you need to install both.**
Add `https://github.com/bitmux/Dayline-card` with category **Dashboard**
alongside this one.

The integration used to serve the card's bundle and register it as a Lovelace
resource itself. Registering a frontend resource is not something an
integration has a public API for: it meant reaching into `hass.data["lovelace"]`
and writing into another integration's storage collection, with no contract
about when or whether the frontend would honour it. It worked, then stopped
working, in ways that did not reduce to anything in this repository — and 0.1.1
tried to shore it up rather than replace it.

HACS owns that registration and does it through supported paths, which is what
the Dashboard category is for. One repository cannot be both categories, so
there are two.

- The integration is now only the feed. `frontend.py`, the bundled `www/` copy,
  and the `frontend` / `http` / `lovelace` manifest dependencies are gone.
- Existing installs: HACS will not clean up the old Lovelace resource pointing
  at `/day_spine_frontend/day-spine-card.js`. Delete it under **Settings →
  Dashboards → ⋮ → Resources** after installing the card repository, or the
  dashboard will keep asking for a URL nothing serves any more.

## 0.1.1 — alpha, 3 September 2026

Upgrading the integration could leave the card broken in the browser until a
hard refresh. Two independent causes, both fixed.

- **The cache-buster never changed.** The `?v=` on the card's URL was a
  hand-typed constant, so a rebuilt bundle arrived under the same URL and every
  browser that had already seen it kept serving itself the old copy. It is now
  a hash of the file's own bytes, so the URL changes exactly when the file does
  — and the Lovelace resource is rewritten to match on the next restart.
- **A second load of the bundle threw and took the rest of it with it.** The
  card is registered two ways on purpose, and after an upgrade the
  service-worker-cached index shell can still import the *previous* URL while
  the dashboard imports the current one. Same file, two URLs, two executions —
  and `customElements.define` throws on a name already taken, aborting the
  module below that line. The define is now guarded, so whichever copy arrives
  first wins and the other is a no-op.
- **A cold boot no longer opens the log with three warnings naming your own
  calendars.** They were only an ordering detail — the sources had not started
  yet, and the refresh a moment later filled the spine in — but
  `homeassistant.helpers.service` logs them before raising, so catching the
  error never suppressed them. Entities that do not exist yet are now left out
  of the call instead. A name still missing once everything has started is a
  real problem and still says so.

## 0.1.0 — alpha, 3 September 2026

First release that actually runs somewhere. Installed through HACS on Home
Assistant 2026.8, set up through its config flow, drawing a real day.

### The card

- One vertical spine for today: calendar events, sun times, schedule-calendar
  automations and due to-dos, merged and sorted, with a live now marker that
  jumps on the minute rather than animating.
- Past entries stay, struck through. Things the house will do on its own are
  annotated in sage, in sentences a person wrote.
- Running events show a progress bar, time remaining and end time — several at
  once when that is the truth.
- To-do rows are sticky and carry a Done button, so the laundry does not quietly
  slide into the past.
- "What just happened" lines, short-lived, for changes nobody made by hand.
- Hourly forecast joined to upcoming entries.
- A density budget that collapses low-priority entries first and counts what it
  collapsed on a `+N more today` row. Overdue actionables, high priority, all-day
  entries and the now marker are never collapsed.
- Loading, empty-day and stale-source states are first-class renders. A stale
  calendar tints its own pill and the footer names what is missing.
- The Organic palette by default, `use_ha_theme: true` to take colours from the
  active Home Assistant theme instead.

### The feed

- A config-flow integration (`day_spine`) with a five-section options UI:
  sources, per-calendar labels and roles, sage sentences, what-just-happened
  rules, and tuning.
- Schedule calendars: a calendar whose events describe the house, with each
  event's description as its sage sentence — so the schedule, the words and the
  automation trigger are one thing you edit in the calendar panel.
- The same feed is also available as a template-sensor package,
  `ha/day_spine.yaml`, for anyone who would rather not install an integration.
- Actions are service-call descriptors written by the feed, so repointing the
  Done button at something other than `todo` is a config change.

### Fixed before anyone else saw it

Four things that only a live instance could show:

- `sun.sun` publishes UTC, so west of Greenwich a sunset after 19:00 local
  belongs to tomorrow's UTC date. Comparing calendar dates dropped the sunset
  row for half the year — silently, and only in summer.
- Only `precipitation_probability` was carried. met.no, which is what a default
  Home Assistant install has, reports millimetres and no probability at all, so
  rain never once rendered as rain there.
- `calendar.get_events` returns everything *overlapping* today, so a meeting
  that ran from 10pm yesterday to half past midnight drew as "10:11 PM, struck
  through" at the top of today. It now starts the day; one that also ended
  before midnight is dropped.
- On a cold boot the calendar, to-do and weather integrations may not be up when
  this one is, and the first spine came out with no laundry and no forecast —
  and stayed that way for five minutes.

### Known limits

- Tested against Local Calendar and Local To-do only; Google and CalDAV, and
  recurring events, are unproven.
- Weather tested against NWS and met.no.
- Automatic card registration needs a storage-mode dashboard. YAML dashboards
  must add the resource by hand — see INSTALL.md.
- No visual editor for the card's own options yet, and no drag-to-reschedule.
