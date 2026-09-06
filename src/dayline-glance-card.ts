import { LitElement, html, nothing, type TemplateResult } from "lit";
import { state } from "lit/decorators.js";
import { glanceStyles } from "./glance-styles";
import { icon } from "./icons";
import { calStyle } from "./cal";
import { loadFonts } from "./fonts";
import type {
  DaylineGlanceCardConfig,
  HassEntity,
  HomeAssistant,
  SpineAction,
  SpineEntry,
} from "./types";

/**
 * Dayline, reduced to what survives being read from across a room.
 *
 * The spine card answers "what is left of today". This one answers the two
 * questions a wall panel is actually asked in passing — what time is it, and is
 * anything wrong — plus the one event close enough to matter. It reads the same
 * `sensor.dayline` feed and adds nothing to it: everything here is a selection
 * from `entries[]`, so a panel and a dashboard can never disagree about the day.
 *
 * Built for the View Assist tablets, but there is nothing View Assist about it;
 * it is a Lovelace card and will sit anywhere one fits.
 */


/** Matches the spine card: long enough for a door to move, short enough that a
 *  script which declined does not leave the row looking done. */
const PENDING_TIMEOUT = 20_000;

const DEFAULTS = {
  show_date: true,
  show_next: true,
  max_alerts: 2,
  quiet_message: "Nothing else today",
  inset_bottom: 0,
  inset_top: 0,
  time_format: "auto" as "auto" | "12" | "24",
  load_fonts: true,
  use_ha_theme: false,
};

type ResolvedConfig = DaylineGlanceCardConfig & typeof DEFAULTS;

/**
 * How much has been given up to make the content fit the panel, in the order it
 * is given up.
 *
 * A wall panel is a fixed rectangle: it cannot scroll, and there is no one there
 * to scroll it. So when the content does not fit, something has to go, and the
 * card decides which rather than letting `overflow: hidden` cut a button in half
 * at whatever height the tablet happens to be.
 *
 * The order is the priority argument, written down. Secondary lines go first,
 * because the primary line above each one still says the thing. Then the clock
 * comes down, twice, with the date going between the two — the clock is the
 * point of the card, but it is also by far the largest thing on it, and taking
 * two smaller bites out of it beats dropping an alert that someone needs to
 * press. Then the second alert. The next-event band goes last of all: on a
 * panel, what is wrong now outranks what is happening later, and if only one of
 * the two fits it should be the alert.
 */
const FIT_STEPS = 6;

/** The chosen event, and whether it has already started. */
interface NextUp {
  entry: SpineEntry;
  running: boolean;
}

export class DaylineGlanceCard extends LitElement {
  static override styles = glanceStyles;

  @state() private _config!: ResolvedConfig;
  @state() private _stateObj?: HassEntity;
  @state() private _now = Date.now();
  @state() private _pending = new Set<string>();
  /** 0 = everything drawn. See FIT_STEPS. */
  @state() private _fit = 0;

  private _hass?: HomeAssistant;
  private _timer?: number;
  private _align?: number;
  private _ro?: ResizeObserver;
  /** Last size the observer saw, so a shrink this card caused is not read as
   *  the panel getting bigger. */
  private _box = { h: 0, w: 0 };

  // ---------------------------------------------------------------- lifecycle

  public setConfig(config: DaylineGlanceCardConfig): void {
    if (!config?.entity) {
      throw new Error("dayline-glance-card: `entity` is required (the merged feed sensor).");
    }
    this._config = { ...DEFAULTS, ...config };
    // A different box is a different answer about what fits in it.
    this._fit = 0;
    this._applyFonts();
    this._applyInsets();
  }

  private _applyInsets(): void {
    // A length, straight into a custom property. Restricted to the shapes a
    // length actually takes, because this one is a string rather than a number
    // and a custom property is a place CSS gets read from.
    const max = this._config.max_height;
    if (max && /^[0-9.]+(px|em|rem|vh|svh|dvh|lvh|%)$/.test(max.trim())) {
      this.style.setProperty("--glance-max-height", max.trim());
    } else {
      this.style.removeProperty("--glance-max-height");
    }
    for (const [prop, value] of [
      ["--inset-bottom", this._config.inset_bottom],
      ["--inset-top", this._config.inset_top],
    ] as const) {
      // Numbers only, and they become a length here rather than anywhere the
      // value could be read as CSS of its own.
      const px = Number(value);
      if (Number.isFinite(px) && px > 0) this.style.setProperty(prop, `${px}px`);
      else this.style.removeProperty(prop);
    }
  }

  private _applyFonts(): void {
    const body = this._config.font_family;
    const heading = this._config.heading_font_family ?? body;
    // The clock does not inherit from `font_family`. Someone setting a font for
    // the card is choosing how the text reads; the clock is an instrument and
    // wants its own answer, which is why it has its own key.
    for (const [prop, value] of [
      ["--font-body", body],
      ["--font-heading", heading],
      ["--font-clock", this._config.clock_font_family],
    ] as const) {
      if (value) this.style.setProperty(prop, value);
      else this.style.removeProperty(prop);
    }
  }

  public set hass(hass: HomeAssistant) {
    this._hass = hass;
    const next = hass?.states?.[this._config?.entity];
    if (next !== this._stateObj && next?.last_updated !== this._stateObj?.last_updated) {
      this._stateObj = next;
      this._pending = new Set();
      // Different content, different answer. Start from everything drawn and
      // let the measure below take things away again if it still has to.
      this._fit = 0;
    } else if (!next && this._stateObj) {
      this._stateObj = undefined;
    }
  }

  public override connectedCallback(): void {
    super.connectedCallback();
    if (this._config?.load_fonts) loadFonts();
    this._startClock();
    // A panel gets resized by rotation, by a dashboard edit, and once by the
    // browser settling after load. Each time, start from everything drawn — a
    // card that only ever gives things up would stay stripped down forever
    // after one brief moment of being too small.
    //
    // Only when it got *bigger*, though. Where the parent lets this card size
    // to its own content, taking something away shrinks the host, which fires
    // this observer, which puts it back, which grows the host again: the card
    // oscillates and settles at everything-drawn, overflowing, which is exactly
    // the state the fit steps exist to prevent.
    if (typeof ResizeObserver !== "undefined") {
      this._ro = new ResizeObserver(() => {
        const h = this.clientHeight;
        const w = this.clientWidth;
        if (h > this._box.h + 1 || w !== this._box.w) this._fit = 0;
        this._box = { h, w };
      });
      this._ro.observe(this);
    }
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this._timer) window.clearInterval(this._timer);
    if (this._align) window.clearTimeout(this._align);
    this._timer = this._align = undefined;
    this._ro?.disconnect();
    this._ro = undefined;
  }

  /**
   * Give something up, one step per frame, until the card fits its panel.
   *
   * Measuring after the fact rather than predicting: the alternative is
   * arithmetic over font metrics and line wrapping that would be wrong on the
   * first tablet with a different default font size. Converges in at most
   * FIT_STEPS frames because each step only ever removes content, and the
   * ResizeObserver above is the only thing that ever winds it back.
   */
  protected override updated(): void {
    if (this._fit >= FIT_STEPS) return;
    const card = this.renderRoot.querySelector(".card") as HTMLElement | null;
    if (!card) return;
    // A pixel of slack throughout: sub-pixel layout rounding otherwise reads as
    // an overflow on a card that fits perfectly well.
    if (card.scrollHeight > card.clientHeight + 1 || this._overflowsScreen()) {
      this._fit += 1;
    }
  }

  /**
   * The case the card's own box cannot see.
   *
   * `height: 100%` only means something when the parent has a height to be a
   * percentage of. Where it does not — a view that lets its cards size to their
   * content — the card grows to fit whatever it drew, its scrollHeight equals
   * its clientHeight, it concludes everything is fine, and the bottom of it goes
   * off the screen instead. Which is a card that has been told it has infinite
   * room by a device that plainly does not have any.
   *
   * So when the box says nothing, ask the window — but only when the box really
   * did say nothing. Two guards, and both matter:
   *
   * There must be no slack left in the card, which is what tells us no height
   * was handed down. Comparing the content against the box does not answer that
   * — the clock zone grows to absorb whatever is spare, so the content always
   * appears to fill the card exactly. What the spare room went into is the clock
   * zone itself, so that is where to look for it: a zone standing taller than
   * the clock and date inside it is a card with room going begging, which means
   * a parent that gave it a height. A 600px card on a 480px phone is a card the
   * page scrolls to see, not one that should start throwing away alerts.
   *
   * And its top must be in the upper part of the screen. That is a panel view,
   * or a card at the top of a dashboard, where what falls below the fold is
   * genuinely lost. A card halfway down a long dashboard has a whole page under
   * it and must not strip itself because the fold happens to land nearby.
   */
  private _overflowsScreen(): boolean {
    const zone = this.renderRoot.querySelector(".clock-zone") as HTMLElement | null;
    if (!zone) return false;
    const kids = Array.from(zone.children) as HTMLElement[];
    const gap = parseFloat(getComputedStyle(zone).rowGap) || 0;
    const content =
      kids.reduce((h, el) => h + el.getBoundingClientRect().height, 0) +
      gap * Math.max(0, kids.length - 1);
    if (zone.getBoundingClientRect().height - content > 2) return false;

    const rect = this.getBoundingClientRect();
    const screen = window.innerHeight || 0;
    if (!screen || !rect.height || rect.top > screen * 0.4) return false;
    return rect.bottom > screen + 1;
  }

  /** On the minute boundary, so the digits change when the wall clock does. */
  private _startClock(): void {
    const tick = () => {
      this._now = Date.now();
    };
    this._align = window.setTimeout(() => {
      tick();
      this._timer = window.setInterval(tick, 60_000);
    }, 60_000 - (Date.now() % 60_000));
  }

  public getCardSize(): number {
    return 4;
  }

  public getGridOptions(): Record<string, unknown> {
    return { columns: 12, rows: 6, min_columns: 6, min_rows: 3 };
  }

  public static getStubConfig(hass?: HomeAssistant): DaylineGlanceCardConfig {
    const found = Object.keys(hass?.states ?? {}).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass?.states[id]?.attributes?.entries),
    );
    return {
      type: "custom:dayline-glance-card",
      entity: found ?? "sensor.day_spine",
      use_ha_theme: true,
    };
  }

  // ------------------------------------------------------------------- render

  protected override render(): TemplateResult {
    const cfg = this._config;
    const s = this._stateObj;
    const down = !s || s.state === "unavailable" || s.state === "unknown";

    const entries = down ? [] : this._live(Array.isArray(s!.attributes.entries) ? s!.attributes.entries : []);
    // Steps 1, 2 and 4 are pure CSS — the classes below hide the secondary lines
    // and shrink the clock twice. The rest drop whole things, so they are here.
    const alerts = this._alerts(entries).slice(0, this._fit >= 5 ? 1 : undefined);
    const next = this._next(entries, alerts);
    const showNext = cfg.show_next && this._fit < 6;
    const showDate = cfg.show_date && this._fit < 3;

    return html`<div class="card ${cfg.use_ha_theme ? "themed" : ""} a${alerts.length} f${this._fit}">
      <div class="clock-zone">
        ${this._renderClock()} ${showDate ? html`<div class="date">${this._dateLine()}</div>` : nothing}
      </div>
      ${showNext ? this._renderNext(next, down) : nothing}
      ${alerts.length ? html`<div class="alerts">${alerts.map((e) => this._renderAlert(e))}</div>` : nothing}
    </div>`;
  }

  /**
   * The clock, which is the one thing on this card that does not come from the
   * feed — and so the one thing still true when the feed is not.
   */
  private _renderClock(): TemplateResult {
    const full = this._fmt(this._now, false);
    const bare = this._fmt(this._now, true);
    const meridiem = full.startsWith(bare) ? full.slice(bare.length).trim() : "";
    return html`<div class="clock">
      ${bare}${meridiem ? html`<span class="mer">${meridiem}</span>` : nothing}
    </div>`;
  }

  private _dateLine(): string {
    return new Intl.DateTimeFormat(this._locale, {
      weekday: "long",
      month: "long",
      day: "numeric",
      timeZone: this._tz,
    }).format(new Date(this._now));
  }

  private _renderNext(next: NextUp | undefined, down: boolean): TemplateResult {
    if (down) {
      // Named plainly rather than left blank. A panel showing a clock and an
      // empty band looks like a quiet day, and "quiet" is exactly the wrong
      // thing to imply when we have stopped hearing from the house.
      return html`<div class="next"><div class="quiet">Dayline feed unavailable</div></div>`;
    }
    if (!next) {
      return html`<div class="next"><div class="quiet">${this._config.quiet_message}</div></div>`;
    }
    const { entry, running } = next;
    // No dot at all rather than an invisible one: a transparent circle still
    // occupies its space, and the sun rows — which never carry a calendar colour
    // — would sit indented from every row that does.
    const dot = calStyle(entry.color);
    return html`<div class="next">
      <div class="next-when">
        <div class="next-time">${this._fmt(Date.parse(entry.start), false)}</div>
        <div class="next-rel">${running ? "now" : this._relative(Date.parse(entry.start))}</div>
      </div>
      <div class="next-what">
        <div class="next-title">
          ${dot ? html`<span class="dot" style=${dot}></span>` : nothing}${entry.title}
        </div>
        ${entry.automation ? html`<div class="next-auto">${entry.automation}</div>` : nothing}
      </div>
    </div>`;
  }

  private _renderAlert(e: SpineEntry): TemplateResult {
    const buttons = (e.actions?.length ? e.actions : e.action ? [e.action] : []).slice(0, 2);
    const level = e.level === "info" ? "var(--ds-level-info)" : "var(--ds-level-alert)";
    return html`<div
      class="alert ${this._pending.has(e.id) ? "pending" : ""}"
      style="--lv: ${level}"
    >
      <span class="alert-ico">${icon(e.level === "info" ? "info" : "triangle-alert", 24)}</span>
      <div class="alert-body">
        <div class="alert-title">${e.title}</div>
        ${e.automation ? html`<div class="alert-sub">${e.automation}</div>` : nothing}
      </div>
      ${buttons.length
        ? html`<div class="btns">
            ${buttons.map(
              (a, i) =>
                html`<button
                  class=${i ? "quiet-btn" : ""}
                  @click=${() => this._act(e, a)}
                  ?disabled=${this._pending.has(e.id)}
                >
                  ${i === 0 ? icon("check", 18) : nothing}${a.label}
                </button>`,
            )}
          </div>`
        : nothing}
    </div>`;
  }

  // ------------------------------------------------------------------ actions

  /** Identical in behaviour to the spine card's, deliberately: the same button
   *  on the same row must do the same thing whichever card you press it on. */
  private _act(e: SpineEntry, action?: SpineAction): void {
    const a = action ?? e.actions?.[0] ?? e.action;
    if (!a) return;

    if (a.more_info) return this._moreInfo(a.more_info);
    if (a.url) return void window.open(a.url, "_blank", "noopener");
    if (a.navigate) {
      history.pushState(null, "", a.navigate);
      window.dispatchEvent(new CustomEvent("location-changed"));
      return;
    }

    if (!a.service) return;
    const [domain, service] = a.service.split(".");
    if (!domain || !service) return;
    this._pending = new Set(this._pending).add(e.id);
    const clear = () => this._clearPending(e.id);
    window.setTimeout(clear, PENDING_TIMEOUT);
    this._hass?.callService(domain, service, a.data ?? {}, a.target).catch(clear);
  }

  private _clearPending(id: string): void {
    if (!this._pending.has(id)) return;
    const next = new Set(this._pending);
    next.delete(id);
    this._pending = next;
  }

  private _moreInfo(entityId: string): void {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }),
    );
  }

  // ----------------------------------------------------------------- the feed

  private get _locale(): string {
    return this._hass?.locale?.language ?? this._hass?.language ?? navigator.language;
  }

  private get _tz(): string | undefined {
    return this._hass?.config?.time_zone;
  }

  /** Drop entries that have aged out. The card expires them on its own tick so
   *  a stalled feed cannot leave a five-minute row on a wall for an hour. */
  private _live(entries: SpineEntry[]): SpineEntry[] {
    return entries.filter((e) => {
      if (!e?.start || !e?.title) return false;
      const expires = e.expires ? Date.parse(e.expires) : null;
      return expires === null || Number.isNaN(expires) || expires > this._now;
    });
  }

  /**
   * What is currently wrong, at most `max_alerts` of it.
   *
   * Two sources, both of them things an automation pushed in deliberately:
   * rows marked `level: alert`, and `standing` rows — the ones that are true
   * until something changes, which is what "the garage is open" is. Nothing the
   * feed generates on its own can reach this list, which is what keeps a busy
   * calendar from ever crowding out a door.
   *
   * Newest first. On a panel the thing that just happened is the thing being
   * walked toward.
   */
  private _alerts(entries: SpineEntry[]): SpineEntry[] {
    const rank = (e: SpineEntry) => (e.level === "alert" ? 0 : 1);
    return entries
      .filter((e) => e.level === "alert" || e.kind === "standing")
      .sort((a, b) => rank(a) - rank(b) || Date.parse(b.start) - Date.parse(a.start))
      .slice(0, Math.max(0, this._config.max_alerts));
  }

  /**
   * The one event worth naming: whatever is running now, else whatever is next.
   *
   * Preferring the running one matters more than it sounds. A panel reading
   * "4:00 — School pickup" while the 3:00 thing is still going is technically
   * true and practically a lie about where the day is.
   *
   * All-day entries are excluded — they are the day's frame, not a moment in it,
   * and one would otherwise sit in this band from midnight and never move. So
   * are the rows already drawn as alerts, which would otherwise be said twice
   * on a card with room to say two things.
   */
  private _next(entries: SpineEntry[], alerts: SpineEntry[]): NextUp | undefined {
    const shown = new Set(alerts.map((e) => e.id));
    const timed = entries
      .filter(
        (e) =>
          !e.all_day &&
          e.kind !== "event" &&
          e.kind !== "standing" &&
          e.level !== "alert" &&
          !shown.has(e.id),
      )
      .sort((a, b) => Date.parse(a.start) - Date.parse(b.start));

    const running = timed.find((e) => {
      const start = Date.parse(e.start);
      const end = e.end ? Date.parse(e.end) : NaN;
      return start <= this._now && !Number.isNaN(end) && end > this._now;
    });
    if (running) return { entry: running, running: true };

    const upcoming = timed.find((e) => Date.parse(e.start) > this._now);
    return upcoming ? { entry: upcoming, running: false } : undefined;
  }

  /** "in 8 min", "in 2h 15m". Minutes only below an hour, because that is the
   *  resolution anyone acts on. */
  private _relative(ms: number): string {
    const mins = Math.max(0, Math.round((ms - this._now) / 60_000));
    if (mins < 1) return "any moment";
    if (mins < 60) return `in ${mins} min`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return m ? `in ${h}h ${m}m` : `in ${h}h`;
  }

  private _fmt(ms: number, stripMeridiem: boolean): string {
    const out = new Intl.DateTimeFormat(this._locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: this._tz,
      hour12: this._config.time_format === "auto" ? undefined : this._config.time_format === "12",
    }).format(new Date(ms));
    return stripMeridiem ? out.replace(/\s*[APap][.\s]*[Mm][.\s]*$/, "").trim() : out;
  }
}

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
}

// Guarded for the same reason the spine card is. A Lovelace resource left behind
// from a manual install and the HACS-managed one are two URLs serving one file,
// and the browser will happily execute both. `customElements.define` throws on a
// name already taken, and an exception at the top level of a module aborts the
// rest of it — so unguarded, the second execution would take out the picker
// registration below and report an error for a card that is in fact fine.
if (!customElements.get("dayline-glance-card")) {
  customElements.define("dayline-glance-card", DaylineGlanceCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "dayline-glance-card",
    name: "Dayline Glance",
    description: "The time, what is next, and anything wrong — sized to be read from across a room.",
    preview: false,
  });
}
