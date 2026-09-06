/** Priority governs what survives the density budget. It never affects sort order. */
export type Priority = "high" | "normal" | "low";

export type EntryKind =
  | "calendar"
  | "sun"
  | "automation"
  | "todo"
  | "event"
  /**
   * True for as long as something is true, rather than at a time.
   *
   * A door that is open, or a row an automation pushed in with
   * `day_spine.show`. Distinct from `event` — which is the five-minute "what
   * just happened" line — because these do not expire on their own and must not
   * be drawn as history. They read as live: full-strength title, no
   * strikethrough, never collapsed by the budget.
   */
  | "standing"
  | "manual";

/**
 * A service call the feed hands to the card, ready to fire.
 *
 * The card never constructs one of these and never inspects what it points at. That
 * is the whole point: switching the actionable backend from HA's `todo` integration
 * to Grocy, a CalDAV task list, or an input_boolean is an edit to the feed YAML, not
 * a card rebuild.
 */
export interface SpineAction {
  label: string;
  /** "domain.service" — the common case, and all the feed's own rows use. */
  service?: string;
  target?: Record<string, unknown>;
  data?: Record<string, unknown>;
  /**
   * The rest of Home Assistant's `tap_action` vocabulary, for buttons an
   * automation supplied through `day_spine.show`. The feed translates HA's
   * action schema into these, so the card never has to learn it.
   */
  more_info?: string;
  navigate?: string;
  url?: string;
}

/** The hourly forecast covering an entry's start, joined on by the feed. */
export interface SpineWeather {
  condition?: string;
  temperature?: number;
  precipitation_probability?: number;
  /** Millimetres. The fallback signal for providers that report no
   * probability — met.no, which is what a default install has. */
  precipitation?: number;
}

/** Conditions right now, off the weather entity itself rather than a forecast. */
export interface NowWeather {
  condition?: string;
  temperature?: number;
  temperature_unit?: string;
}

export interface SpineEntry {
  id: string;
  start: string; // ISO 8601
  end?: string | null;
  all_day?: boolean;
  kind?: EntryKind;
  source?: string;
  title: string;
  /** What the house does on its own, in plain words. Never an entity id or scene name. */
  automation?: string | null;
  /** Where the event is, as the calendar wrote it. Not always an address. */
  location?: string | null;
  /**
   * When to set off, so as to arrive on time: the start, less the drive, less
   * a buffer for parking and walking in.
   *
   * Present only when the feed could actually price the journey. A missing
   * leave-by line is a card that is quiet about it; a wrong one makes you late.
   */
  leave_by?: string | null;
  /** The journey behind `leave_by`. `minutes` is the drive, rounded up. */
  travel?: { minutes: number; buffer?: number; route?: string | null } | null;
  /**
   * `#tags` the feed lifted out of the event title, as they were typed.
   *
   * Shown rather than hidden — seeing `#Away` on a row is how you know what the
   * house is about to do.
   */
  tags?: string[];
  /**
   * Which calendar this came from, as a palette name the card resolves.
   *
   * Colour answers *who* — the spine already answers what and when. It reaches
   * the dot beside the entry and the pill in the legend, and deliberately
   * nothing else: terracotta means *now* and sage means *the house acting on
   * its own*, and a calendar borrowing either would be lying about the day.
   *
   * Home Assistant has no colour on a calendar entity, so this never comes from
   * CalDAV or Google however green they are at the source. The feed supplies it.
   */
  color?: string;

  /**
   * What those tags will do, decided by the feed.
   *
   * `will_fire` before the event starts, `fired` once it has, and `inert` when
   * the calendar is not allowed to act. The inert state is the important one:
   * someone who types `#vacation!` gets an answer rather than silence, and
   * silence is what makes people decide a system is broken.
   */
  tag_state?: "will_fire" | "fired" | "inert";
  entity_id?: string | null;
  priority?: Priority;
  /** Stays on the spine past its time until the action is taken, rather than sliding into the past. */
  sticky?: boolean;
  /** ISO time after which the entry stops rendering. Used by the "what just happened" rows. */
  expires?: string | null;
  /**
   * How the row carries itself, for rows an automation pushed in.
   *
   * `alert` is the only red on the card, which is what makes it worth having;
   * `info` is quieter than normal. Everything the feed generates itself stays
   * `normal`, because a card where most things are urgent has no way left to
   * say that one of them is.
   */
  level?: "normal" | "info" | "alert";
  action?: SpineAction | null;
  /**
   * Up to two buttons, for rows that pose a choice rather than a chore.
   *
   * `action` stays the single-button case every other source writes, and the
   * first of these mirrors into it, so nothing that only knows about `action`
   * has to learn a second shape.
   */
  actions?: SpineAction[] | null;
  weather?: SpineWeather | null;
}

export interface SpineSource {
  label: string;
  stale?: boolean;
  /** Palette name, matching the `color` on that calendar's entries. */
  color?: string;
}

export interface DaySpineCardConfig {
  type: string;
  entity: string;
  show_all_day?: boolean;
  /**
   * Most all-day entries drawn before the rest collapse behind a `+N more`
   * line. The all-day frame is the day's header, and a header that eats
   * two-thirds of a phone is not a header any more.
   *
   * Set high to keep the old behaviour of showing every one.
   */
  max_all_day?: number;
  show_sources?: boolean;
  show_legend?: boolean;
  /** The big day name in the header. */
  show_day?: boolean;
  /** The line under the day name — "4 left today", or whatever the feed says. */
  show_headline?: boolean;
  /** Sunrise and sunset rows. The feed can also drop them; this hides them per card. */
  show_sun?: boolean;
  /** Entries whose time has passed. Off makes the card purely forward-looking. */
  show_past?: boolean;
  /** The `#tag` chips beside event titles. */
  show_tags?: boolean;
  /** The progress bar on entries that are currently running. */
  show_progress?: boolean;
  /**
   * Clock format. `auto` follows the Home Assistant locale, which is almost
   * always what you want; the other two are for when it isn't.
   */
  time_format?: "auto" | "12" | "24";
  interactive_rows?: boolean;
  max_past?: number;
  max_future?: number;
  collapse_low_priority?: boolean;
  recent_events?: boolean;
  /** Seconds. Card-side floor for entries that arrive without their own `expires`. */
  recent_ttl?: number;
  load_fonts?: boolean;
  /**
   * The clock in the header. On by default — a card about today should say what
   * time it is, and the header had room once the source pills moved down.
   */
  show_clock?: boolean;
  /**
   * A CSS `font-family` for the whole card, written exactly as you would in
   * CSS: `Arial, sans-serif`.
   *
   * The two typefaces are part of the design, but they are not worth arguing
   * with someone about on their own dashboard. Setting this replaces both
   * unless `heading_font_family` says otherwise, and pairs with
   * `load_fonts: false` to stop fetching webfonts nothing is using.
   */
  font_family?: string;
  /** Overrides `font_family` for the day name alone. */
  heading_font_family?: string;
  legend?: string;
  show_weather?: boolean;
  /** The duration chip on upcoming entries that have an end. */
  show_duration?: boolean;
  /** Draw the "leave by" line on events the feed could price a journey to. */
  show_leave_by?: boolean;
  /** Adopt the active Home Assistant theme's colors instead of the Organic palette. */
  use_ha_theme?: boolean;
}

/**
 * The slice of Home Assistant's frontend object this card touches.
 *
 * Deliberately hand-written rather than pulled from `custom-card-helpers`: five
 * fields we actually use beat a dependency that drifts out of date and breaks the
 * build for reasons unrelated to this card.
 */
export interface HassEntity {
  entity_id: string;
  state: string;
  last_updated: string;
  attributes: Record<string, any>;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  locale?: { language: string };
  /** The instance's own settings. `time_zone` is what makes the card show the
   *  house's day rather than the browser's. */
  config?: { time_zone?: string };
  language?: string;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: Record<string, unknown>,
  ): Promise<unknown>;
}

/** What the render pipeline produces: entries classified and ready to draw. */
export type RowVariant = "past" | "recent" | "overdue" | "live" | "now" | "future";

export interface SpineRow {
  variant: RowVariant;
  entry?: SpineEntry;
  /** Synthetic "Now" row carries its subline here. */
  subline?: string;
  time: string;
  last?: boolean;
  /** 0–1, how far through a live entry we are. Only set on `live` rows. */
  progress?: number;
  /** First live row — the rail turns accent at its dot, as the now marker does. */
  firstLive?: boolean;
  /** Set on the now row when live rows sit above it, so the rail stays accent. */
  afterLive?: boolean;
}

/**
 * The glance card: the same feed read from across a room.
 *
 * Deliberately a separate config type rather than a superset of
 * `DaySpineCardConfig`. Nearly every key on that one is about the spine — the
 * density budget, the legend, the source pills — and none of it has any meaning
 * on a card whose whole content is a clock, one event and at most two alerts.
 * The four that do overlap are spelled the same way so nobody has to learn two
 * names for the clock format.
 */
export interface DaylineGlanceCardConfig {
  type: string;
  entity: string;
  /** The weekday and date under the clock. */
  show_date?: boolean;
  /** The next-event band. Off leaves a clock and whatever alerts arrive. */
  show_next?: boolean;
  /**
   * Most alerts drawn at once. Anything past this is dropped, not counted.
   *
   * The spine's house rule — say what you are not showing — is suspended here
   * on purpose. A `+2 more` line is unreadable from eight feet and unactionable
   * from a wall, and the space it costs comes out of the two alerts that *are*
   * legible.
   */
  max_alerts?: number;
  /** What the next-event band says when the day has nothing left in it. */
  quiet_message?: string;
  /** Draw the "leave by" line under the event the card is naming. */
  show_leave_by?: boolean;
  /**
   * Conditions now, in the top corner, and the forecast for the event the band
   * is naming. One key, because they are the same question asked about two
   * moments and nobody wants one without the other.
   */
  show_weather?: boolean;
  /** The NOW / NEXT label above the time in the event band. */
  show_eyebrow?: boolean;
  /**
   * How long before a leave-by time the clock turns `warn_color`. `0` skips
   * the amber stage; the clock still turns `urgent_color` at the time itself.
   */
  warn_minutes?: number;
  /** Any CSS colour. Empty disables that stage. */
  warn_color?: string;
  /** Any CSS colour, from the leave-by time onward. Empty disables it. */
  urgent_color?: string;
  /**
   * Pixels along the bottom and top edges that something else is drawing over.
   *
   * A panel app is not always honest about how much of the view is yours. View
   * Assist paints its voice status line across the bottom of the view, and the
   * card underneath has no way to know: it is handed the full height, fills it,
   * and the last few pixels of whatever it drew are simply covered up.
   *
   * These take that room out of the card's own box, so the content sits above
   * the overlay instead of under it — and the fit steps see the smaller box, so
   * a card that no longer fits will give something up rather than tuck it
   * behind the bar.
   */
  inset_bottom?: number;
  inset_top?: number;
  /**
   * A hard ceiling for the card, as a CSS length — `580px`, `100vh`, `60svh`.
   *
   * The card works out what fits by measuring itself, which needs the parent to
   * have given it a height to measure against. Most do. A view that lets its
   * cards size to their own content has not, and the card falls back to what is
   * left of the window — a good guess, and still a guess. This is the way to
   * stop guessing: say the number and everything else follows from it.
   */
  max_height?: string;
  time_format?: "auto" | "12" | "24";
  load_fonts?: boolean;
  font_family?: string;
  heading_font_family?: string;
  /**
   * A CSS `font-family` for the clock alone, written exactly as you would in
   * CSS. Deliberately separate from `font_family`: the clock is the one thing
   * on this card being read from across a room, and what works for a paragraph
   * is rarely what works at 200px.
   */
  clock_font_family?: string;
  use_ha_theme?: boolean;
}
