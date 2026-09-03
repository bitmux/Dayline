# Changelog

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
