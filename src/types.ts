/** Priority governs what survives the density budget. It never affects sort order. */
export type Priority = "high" | "normal" | "low";

export type EntryKind = "calendar" | "sun" | "automation" | "todo" | "event" | "manual";

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
  service: string; // "domain.service"
  target?: Record<string, unknown>;
  data?: Record<string, unknown>;
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
  /**
   * `#tags` the feed lifted out of the event title, as they were typed.
   *
   * Shown rather than hidden — seeing `#Away` on a row is how you know what the
   * house is about to do.
   */
  tags?: string[];

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
  action?: SpineAction | null;
  weather?: SpineWeather | null;
}

export interface SpineSource {
  label: string;
  stale?: boolean;
}

export interface DaySpineCardConfig {
  type: string;
  entity: string;
  show_all_day?: boolean;
  show_sources?: boolean;
  show_legend?: boolean;
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
