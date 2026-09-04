# Changelog

## Unreleased

**Any automation can put a row on the spine.** `day_spine.show` and
`day_spine.dismiss` are the first services this integration has had. A row takes
a message, an optional sage second line, a level, a priority, an optional
duration, and up to two buttons — and every field is a selector, so it is filled
in from the automation editor like any other action, with no YAML to write.

**The buttons do anything a dashboard button can.** Each takes a label and Home
Assistant's own action picker — the same control a button card gives you — so a
Dayline button can perform an action, open a more-info dialog, navigate, or open
a URL. They are called *confirm* and *cancel* because that is what two buttons on
one row nearly always are, but nothing enforces it and one button is perfectly
normal. The second is drawn quieter and without a tick, because "not now" should
not look as inviting as the thing being asked for. There is no third: a row is
one line of a timeline, and a third button makes it a dialog. In YAML the four
fields are flat — `confirm_label`, `confirm_action`, `cancel_label`,
`cancel_action` — because an action editor's sections group fields visually and
nothing more; what Home Assistant sends is flat, and two sections both offering
a `label` collided badly enough that every call built in the UI was rejected.

Calling `show` again with the same id replaces the row rather than stacking a
copy, so it is safe from an automation that runs on every state change.
Dismissing an id that is not there is deliberately not an error. Rows persist, so
a restart does not silently drop a claim an automation made about your house.

**Levels: `alert` and `info`.** A pushed row can mark itself. Alert draws its dot
and icon in red with a halo, and **nothing else on this card is red** — which is
the only reason red still means anything by the time you need it. The level
reaches the dot and an icon and stops there; the row still has to read as part of
one day, and a red band across it would make the timeline stop being a timeline
exactly where it matters most. The icon is not decoration: colour alone would
leave the distinction invisible to anyone who cannot see red, on the one row
where "is this a problem" is the entire message.

Together these answer the question Dayline could not otherwise answer honestly:
**how does a script that declined tell you why?** It tells you itself, by calling
`day_spine.show`. Dayline learns nothing about what happens inside a script —
deliberately, the same way it never inspects what an automation does with a
`#tag` — so the explanation is written by the only thing that knows.

**Withdrawn before release: the declarative "While it's true" rules.** A brief
options section let you say *this entity in these states means this row*. It
worked, and it was the wrong home for it: the interesting cases all have a
decision in them, an automation can branch and a config page cannot, and having
both meant two places to look for the same answer. The services do the same job
with the editor people already know. Nothing shipped, so nothing breaks.

**Fixed: a pressed button could stay dimmed forever.** The optimistic dim waited
for the feed to confirm, which never comes when the script declined and nothing
about the house changed. It now gives up after twenty seconds, so a refusal
leaves a row that still reads as open rather than one that looks done.

**Calendars can carry a colour, which is the *who* axis.** The spine already
answered what and when; a colour per calendar in Configure → Calendar wording
now tints that calendar's pill in the legend and the dot beside each of its
entries, so a glance tells you whose day you are looking at.

Home Assistant gives us nothing to inherit here. Your CalDAV server almost
certainly stores a colour — `{http://apple.com/ns/ical/}calendar-color` is a de
facto standard across Radicale, Baikal, Nextcloud, SOGo and Fastmail, and Google
has `backgroundColor` on its calendarList entries — but a Home Assistant
calendar entity has no colour field, and neither does the data `get_events`
returns. So it is chosen rather than read. (It was never really the calendar's
colour anyway: in Google it belongs to your subscription, and two people sharing
a calendar already see different ones.)

Seven colours, no colour wheel. Names rather than hex, so a value survives a
re-theme and so the card can resolve to shades already checked against both the
Organic palette and a Home Assistant theme, light or dark. Terracotta and sage
are not among them: they already mean **now** and **the house acting on its
own**, and colour that means two things means neither. For the same reason the
colour reaches the pill, the ring on an upcoming dot, a muted past dot and an
all-day row's icon — and never the now marker, a running entry, or a sage
sentence.

**The now marker survives your theme.** Under `use_ha_theme` every accent shade
collapses to the single `--primary-color`, which made the one mark that must
never be mistaken for anything else the same colour as everything else the theme
touched. It is now derived rather than deferred: the marker starts from the
theme's *own* text colour — readable against that theme's card by construction —
and mixes terracotta in, in oklab so the midpoint stays a colour someone would
choose.

Pinning a fixed terracotta would have been worse than the problem. On a warm
background behind translucent cards, terracotta text on near-terracotta ground
is unreadable, and a theme's background is not ours to predict. Deriving means
contrast comes from the theme and identity comes from us. Measured on a
deliberately hostile orange-glass theme, the marker reads at 2.93:1 where that
theme's own body text manages 3.07:1 and the old deferred-to-primary behaviour
managed 2.59:1 — no worse than the theme is on itself, and better than what it
replaces. On the frosted and light themes it lands at 6.7:1 and 8.7:1, above
both.

**The all-day frame no longer eats the day.** Eight all-day events on one real
day took the top two-thirds of the card, leaving a single spine row visible
underneath — a timeline card showing almost no timeline. All-day entries used to
be exempt from the density budget on the grounds that they are the day's frame;
that was written when a frame was one or two lines, and eight lines is not a
frame.

- `max_all_day` (default `4`) collapses the rest behind a `+N more all day`
  line that expands in place — the same idiom as `+N more today` at the foot,
  rather than a second scroll region competing with the spine's on touch. Set it
  to `20` for the old behaviour.
- Anything with a Done button, or a tag about to fire, is pulled to the front
  instead of queueing behind eight birthdays. An `#Away` that is going to act is
  not frame; it is the day happening.
- **And a floor under the spine, which is the deeper fix.** On a short card at
  phone width the header, the frame and the legend could squeeze the day itself
  down to thirteen pixels. The frame now takes at most two fifths of the card
  and shrinks before the spine does; the spine keeps a floor of 72px. A card
  with `rows: auto` still grows to its content, so nothing changes there.

**The integration's settings caught up with the labels.** Most of what this
config flow used to ask has not been a setting since labels arrived, and the
stale version of a question is worse than no question — two places claiming to
answer the same thing, one of them wrong.

- **Nothing on the setup form is required now.** Submit it untouched and every
  calendar in the instance is on the spine. The calendar picker survives as the
  fallback for anyone who would rather answer a question than apply a label, and
  it says so.
- **A new first page, "Labels and tags", that is not a setting at all.** It
  reports what carries `Dayline`, what carries `Dayline Control`, what tags
  today's events used, and where each of those is changed — read-only, because
  every fact on it is owned by the label registry or by an automation, and
  offering to write those from inside our own settings is the mistake that broke
  this card's Lovelace registration.
- **Fixed: a labelled calendar could never be given a pill name.** The
  per-calendar wording page iterated the *configured* list, which under labels is
  a different set — usually empty. It reads the resolved list now, and merges
  rather than replaces, so a calendar between labels does not lose the wording
  someone wrote for it.
- **Fixed: editing the fallback list discarded every labelled calendar's
  wording.** Pruning metadata to that list was right when it was the only way in.
- The remaining pages say what they are for. "Sentences" notes that it describes
  rather than acts, and points at `#tags` for the other thing. "What just
  happened" notes that the `Dayline` label decides what is watched and this only
  decides how it reads. "Tuning" notes that the poll interval is also how
  promptly a tag can fire.

**Labels, tags and the blueprint are documented.** `INSTALL.md` gains a "Labels
and tags — where the settings went" section: both labels and what each means on
a calendar versus anything else, `#tag` syntax and matching, the `dayline_tag`
payload, importing the blueprint, the two firing rules, the five-minute caveat,
and what the three chip states do and do not tell you — including that grey means
"not allowed to fire", never "nothing is listening", because Home Assistant
offers no honest way to ask the second question.

**A card you add now starts with `use_ha_theme: true`.** It is written into the
starting YAML rather than changed in the defaults, so upgrading never silently
restyles a card you already placed, and the line is visible and deletable by
anyone who wants the Organic palette back.

**`use_ha_theme` now takes the card's *material*, not just its colours.** A
frosted-glass theme came out the right colour and the wrong substance, because
this card draws its own container instead of wrapping `ha-card` and so never saw
the surface tokens every other card gets. It now honours
`--ha-card-backdrop-filter`, `--ha-card-box-shadow`, `--ha-card-border-width`
and `--ha-card-border-color` alongside the radius it already used. Every
fallback is this card's existing look, so a theme that sets none of them changes
nothing.

**The calendar pills are part of the legend now**, not merely near it:
`show_legend: false` takes them with it, and `show_sources` remains the finer
control for keeping the words without the pills. The stale-source warning stays
independent of both — it is the card telling you it is currently lying to you,
and switching off the legend must not switch that off.

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
card — so they now wrap at the bottom, in the legend, still tinting themselves
when a source goes stale.

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
