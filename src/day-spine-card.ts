import { LitElement, html, nothing, type TemplateResult } from "lit";
import { state } from "lit/decorators.js";
import { styles } from "./styles";
import { icon, conditionIcon } from "./icons";
import type {
  DaySpineCardConfig,
  HassEntity,
  HomeAssistant,
  Priority,
  SpineEntry,
  SpineRow,
  SpineSource,
} from "./types";

const DEFAULT_LEGEND =
  "Past entries stay, struck through, so the day reads as a whole. " +
  "Sage lines are what the house will do on its own.";

const FONT_LINK_ID = "day-spine-card-fonts";
const FONT_HREF =
  "https://fonts.googleapis.com/css2?family=Caprasimo&family=Figtree:wght@400;500;600;700&display=swap";

const DEFAULTS = {
  show_all_day: true,
  show_sources: true,
  show_legend: true,
  interactive_rows: false,
  max_past: 3,
  max_future: 6,
  collapse_low_priority: true,
  recent_events: true,
  recent_ttl: 300,
  load_fonts: true,
  show_weather: true,
  use_ha_theme: false,
  show_duration: true,
};

/** Chance of rain at or above this gets the accent treatment, not just an icon. */
const WET_THRESHOLD = 40;

/** Config with every default filled in — what the render code actually sees. */
type ResolvedConfig = DaySpineCardConfig & typeof DEFAULTS;

export class DaySpineCard extends LitElement {
  static override styles = styles;

  @state() private _config!: ResolvedConfig;
  @state() private _stateObj?: HassEntity;
  @state() private _now = Date.now();
  @state() private _expanded = false;
  /** Entry ids whose action was just pressed, dimmed until the feed confirms. */
  @state() private _pending = new Set<string>();

  private _hass?: HomeAssistant;
  private _timer?: number;
  private _align?: number;

  // ---------------------------------------------------------------- lifecycle

  public setConfig(config: DaySpineCardConfig): void {
    if (!config?.entity) {
      throw new Error("day-spine-card: `entity` is required (the merged feed sensor).");
    }
    this._config = { ...DEFAULTS, ...config };
    this._expanded = false;
  }

  public set hass(hass: HomeAssistant) {
    this._hass = hass;
    const next = hass?.states?.[this._config?.entity];
    // Gate on last_updated: HA pushes the whole state machine on every change and
    // this card has no business re-rendering for the dishwasher.
    if (next !== this._stateObj && next?.last_updated !== this._stateObj?.last_updated) {
      this._stateObj = next;
      this._pending = new Set();
    } else if (!next && this._stateObj) {
      this._stateObj = undefined;
    }
  }

  public override connectedCallback(): void {
    super.connectedCallback();
    if (this._config?.load_fonts) this._loadFonts();
    this._startClock();
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this._timer) window.clearInterval(this._timer);
    if (this._align) window.clearTimeout(this._align);
    this._timer = this._align = undefined;
  }

  /**
   * Tick on the minute boundary rather than 60s after load, so the marker flips
   * when the clock does. The marker jumps; it is never animated into place.
   */
  private _startClock(): void {
    const tick = () => {
      this._now = Date.now();
    };
    this._align = window.setTimeout(() => {
      tick();
      this._timer = window.setInterval(tick, 60_000);
    }, 60_000 - (Date.now() % 60_000));
  }

  private _loadFonts(): void {
    if (document.getElementById(FONT_LINK_ID)) return;
    const link = document.createElement("link");
    link.id = FONT_LINK_ID;
    link.rel = "stylesheet";
    link.href = FONT_HREF;
    document.head.appendChild(link);
  }

  public getCardSize(): number {
    return 6;
  }

  public static getStubConfig(hass?: HomeAssistant): DaySpineCardConfig {
    // The sensor is named after the config entry's title, so an integration set
    // up as "Dayline" produces `sensor.dayline` and one left at the default
    // produces `sensor.day_spine`. Guessing either one is wrong half the time,
    // so find the feed by its shape: a sensor carrying an `entries` list.
    const found = Object.keys(hass?.states ?? {}).find(
      (id) => id.startsWith("sensor.") && Array.isArray(hass?.states[id]?.attributes?.entries),
    );
    return { type: "custom:day-spine-card", entity: found ?? "sensor.day_spine" };
  }

  // ------------------------------------------------------------------- render

  protected override render(): TemplateResult {
    const cfg = this._config;
    const s = this._stateObj;
    const loading = !s || s.state === "unavailable" || s.state === "unknown";

    const attrs = s?.attributes ?? {};
    const dayName = new Intl.DateTimeFormat(this._locale, { weekday: "long" }).format(
      new Date(this._now),
    );

    if (loading) {
      return html`<div class="card ${cfg.use_ha_theme ? "themed" : ""}">
        ${this._renderHeader(dayName, attrs.headline ?? "…", this._sources(attrs, []))}
        ${this._renderSkeleton()}
        ${cfg.show_legend ? this._renderFoot(cfg.legend ?? DEFAULT_LEGEND, false) : nothing}
      </div>`;
    }

    const entries = this._live(Array.isArray(attrs.entries) ? attrs.entries : []);
    // An event that began before today has no honest position on today's spine —
    // its start is off the top of the day. It belongs to the day's frame, next to
    // the all-day entries, where it reads as a condition of today rather than a
    // moment in it.
    const allDay = entries.filter((e) => e.all_day || this._startedEarlier(e));
    const timed = entries.filter((e) => !e.all_day && !this._startedEarlier(e));
    const { rows, hidden } = this._plan(timed);
    const sources = this._sources(attrs, entries);
    const staleMessage: string | undefined = attrs.stale_message || undefined;

    return html`<div class="card ${cfg.use_ha_theme ? "themed" : ""}">
      ${this._renderHeader(dayName, attrs.headline ?? "", sources)}
      ${cfg.show_all_day && allDay.length ? this._renderAllDay(allDay) : nothing}
      <div class="spine">
        ${rows.map((r) => this._renderRow(r))}
        ${hidden.length ? this._renderMore(hidden.length) : nothing}
      </div>
      ${staleMessage ? this._renderFoot(staleMessage, true) : nothing}
      ${cfg.show_legend ? this._renderFoot(cfg.legend ?? DEFAULT_LEGEND, false) : nothing}
    </div>`;
  }

  private _renderHeader(day: string, sub: string, sources: SpineSource[]): TemplateResult {
    return html`<div class="hdr">
      <div>
        <div class="day">${day}</div>
        ${sub ? html`<div class="sub">${sub}</div>` : nothing}
      </div>
      ${this._config.show_sources && sources.length
        ? html`<div class="pills">
            ${sources.map(
              (src) =>
                html`<span class="pill ${src.stale ? "stale" : ""}" title=${src.stale ? "Not updating" : ""}
                  >${src.label}</span
                >`,
            )}
          </div>`
        : nothing}
    </div>`;
  }

  private _renderAllDay(items: SpineEntry[]): TemplateResult {
    return html`<div class="allday">
      ${items.map((e) => {
        // An all-day `#Away` is the common case for a tag, not an edge one, so
        // the chips ride along through all three of these shapes.
        const ttl = html`${e.title}${this._renderTags(e)}`;
        return html`<div class="allday-item">
          ${icon("calendar-days", 18)}
          <div class="allday-body">
            ${this._startedEarlier(e) && e.end
              ? html`<div>${ttl}<span class="dur">until ${this._endLabel(e)}</span></div>`
              : items.length === 1 && !e.automation && !e.action
                ? html`All day · ${ttl}`
                : html`<div>${ttl}</div>`}
            ${e.automation
              ? html`<div class="auto">${icon("sparkles", 14)}${e.automation}</div>`
              : nothing}
            ${this._renderAction(e)}
          </div>
        </div>`;
      })}
    </div>`;
  }

  private _renderSkeleton(): TemplateResult {
    // Header and a full-height rail with no dots. Never a spinner, never a collapse.
    return html`<div class="spine">
      ${[0, 1, 2, 3].map(
        () => html`<div class="row past skeleton">
          <div class="t"></div>
          <div class="rail"></div>
          <div class="c"></div>
        </div>`,
      )}
    </div>`;
  }

  private _renderRow(row: SpineRow): TemplateResult {
    const e = row.entry;
    const tappable =
      this._config.interactive_rows && !!e?.entity_id && row.variant !== "now";

    const classes = [
      "row",
      row.variant,
      row.last ? "last" : "",
      row.firstLive ? "live-start" : "",
      row.afterLive ? "after-live" : "",
      tappable ? "tappable" : "",
      e && this._pending.has(e.id) ? "done" : "",
    ]
      .filter(Boolean)
      .join(" ");

    return html`<div
      class=${classes}
      role=${tappable ? "button" : nothing}
      tabindex=${tappable ? 0 : nothing}
      @click=${tappable ? () => this._moreInfo(e!.entity_id!) : nothing}
      @keydown=${tappable ? (ev: KeyboardEvent) => this._rowKey(ev, e!.entity_id!) : nothing}
    >
      <div class="t">${row.time}${this._renderWeather(row)}</div>
      <div class="rail"></div>
      <div class="c">${this._renderContent(row)}</div>
    </div>`;
  }

  /**
   * The `#tags` a person typed into the event title.
   *
   * Drawn, never swallowed: a tag is how you know at breakfast what the house
   * intends to do at nine. They all render inert for now, because nothing binds
   * them yet — a chip that looked live would be claiming something untrue.
   */
  private _renderTags(e: SpineEntry): TemplateResult | typeof nothing {
    if (!e.tags?.length) return nothing;
    // Inert unless the feed says otherwise. A chip that claims the house is
    // about to act should have to earn it; one that stays quiet is only ever
    // under-promising.
    const state = e.tag_state ?? "inert";
    return html`${e.tags.map((t) => html`<span class="tag ${state}">#${t}</span>`)}`;
  }

  private _renderContent(row: SpineRow): TemplateResult | string {
    const e = row.entry;
    switch (row.variant) {
      case "now":
        return html`<div class="now-l">Now</div>
          ${row.subline ? html`<div class="now-s">${row.subline}</div>` : nothing}`;
      case "past":
        return html`${e!.title}${this._renderTags(e!)}`;
      case "recent":
        return html`${icon("sparkles", 14)}<span>${e!.title}</span>`;
      case "live":
        return html`<div class="ttl">${e!.title}${this._renderTags(e!)}</div>
          ${e!.automation
            ? html`<div class="auto">${icon("sparkles", 14)}${e!.automation}</div>`
            : nothing}
          ${this._renderProgress(row)} ${this._renderAction(e!)}`;
      default: {
        const dur = this._config.show_duration ? this._duration(e!) : null;
        return html`<div class="ttl">
            ${e!.title}${this._renderTags(e!)}${dur
              ? html`<span class="dur">${dur}</span>`
              : nothing}
          </div>
          ${e!.automation
            ? html`<div class="auto">${icon("sparkles", 14)}${e!.automation}</div>`
            : nothing}
          ${this._renderAction(e!)}`;
      }
    }
  }

  /**
   * The forecast for when this entry starts. Only ahead of now — what the
   * weather was during a meeting you already attended is not information.
   */
  private _renderWeather(row: SpineRow): TemplateResult | typeof nothing {
    const w = row.entry?.weather;
    if (!this._config.show_weather || !w || row.variant !== "future") return nothing;
    if (w.condition === undefined && w.temperature === undefined) return nothing;

    const pop = w.precipitation_probability;
    const mm = w.precipitation;
    // Two signals because providers disagree about which one they publish:
    // met.no gives millimetres and no probability at all.
    const wet =
      (typeof pop === "number" && pop >= WET_THRESHOLD) ||
      (typeof pop !== "number" && typeof mm === "number" && mm > 0);
    const hint =
      typeof pop === "number"
        ? `${Math.round(pop)}% chance of precipitation`
        : typeof mm === "number" && mm > 0
          ? `${mm} mm of precipitation forecast`
          : nothing;
    return html`<div class="wx ${wet ? "wet" : ""}" title=${hint}>
      ${conditionIcon(w.condition, 13)}
      ${w.temperature !== undefined ? html`<span>${Math.round(w.temperature)}°</span>` : nothing}
    </div>`;
  }

  /**
   * The progress bar on a running event: it fills left to right toward the end
   * time on the right, with the time left riding the middle of the line.
   */
  private _renderProgress(row: SpineRow): TemplateResult {
    const pct = Math.round((row.progress ?? 0) * 100);
    return html`<div class="prog">
      <div class="prog-track" role="progressbar" aria-valuenow=${pct} aria-valuemin="0" aria-valuemax="100">
        <div class="prog-fill" style="width:${pct}%"></div>
        <span class="prog-chip">${this._remaining(row.entry!)}</span>
      </div>
      <div class="prog-end">${this._endLabel(row.entry!)}</div>
    </div>`;
  }

  private _renderAction(e: SpineEntry): TemplateResult | typeof nothing {
    if (!e.action) return nothing;
    const pending = this._pending.has(e.id);
    return html`<button
      class="act"
      ?disabled=${pending}
      @click=${(ev: Event) => {
        ev.stopPropagation();
        this._act(e);
      }}
    >
      ${icon("check", 14)}${e.action.label}
    </button>`;
  }

  private _renderMore(count: number): TemplateResult {
    return html`<div class="row more">
      <div class="t"></div>
      <div class="rail"></div>
      <div class="c">
        <button class="more-btn" @click=${() => (this._expanded = !this._expanded)}>
          ${this._expanded ? "Show less" : `+${count} more today`}
        </button>
      </div>
    </div>`;
  }

  private _renderFoot(text: string, warn: boolean): TemplateResult {
    return html`<div class="foot ${warn ? "warn" : ""}">
      ${icon(warn ? "wifi-off" : "info", 16)}<span>${text}</span>
    </div>`;
  }

  // ------------------------------------------------------------------ actions

  private _act(e: SpineEntry): void {
    const a = e.action!;
    const [domain, service] = a.service.split(".");
    if (!domain || !service) return;
    // Dim optimistically; the next feed poll is the source of truth.
    this._pending = new Set(this._pending).add(e.id);
    this._hass?.callService(domain, service, a.data ?? {}, a.target).catch(() => {
      const next = new Set(this._pending);
      next.delete(e.id);
      this._pending = next;
    });
  }

  private _moreInfo(entityId: string): void {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private _rowKey(ev: KeyboardEvent, entityId: string): void {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      this._moreInfo(entityId);
    }
  }

  // ------------------------------------------------------- the render pipeline

  private get _locale(): string {
    return this._hass?.locale?.language ?? this._hass?.language ?? navigator.language;
  }

  /** True when the entry began on an earlier day than the one being shown. */
  private _startedEarlier(e: SpineEntry): boolean {
    const start = new Date(Date.parse(e.start));
    return start.toDateString() !== new Date(this._now).toDateString() && start.getTime() < this._now;
  }

  /** Drop entries that have aged out, and event rows the config has switched off. */
  private _live(entries: SpineEntry[]): SpineEntry[] {
    const ttl = this._config.recent_ttl * 1000;
    return entries.filter((e) => {
      if (!e?.start || !e?.title) return false;
      if (e.kind === "event" && !this._config.recent_events) return false;
      const expires = e.expires
        ? Date.parse(e.expires)
        : e.kind === "event"
          ? Date.parse(e.start) + ttl
          : null;
      return expires === null || Number.isNaN(expires) || expires > this._now;
    });
  }

  /**
   * Classify, apply the density budget, and splice in the now marker.
   *
   * Nothing is dropped silently: everything the budget removes is returned in
   * `hidden` and counted on the overflow row.
   */
  private _plan(timed: SpineEntry[]): { rows: SpineRow[]; hidden: SpineEntry[] } {
    const cfg = this._config;
    const now = this._now;
    const sorted = [...timed].sort((a, b) => Date.parse(a.start) - Date.parse(b.start));

    const past: SpineEntry[] = [];
    const recent: SpineEntry[] = [];
    const overdue: SpineEntry[] = [];
    const live: SpineEntry[] = [];
    const future: SpineEntry[] = [];

    for (const e of sorted) {
      const t = Date.parse(e.start);
      const end = e.end ? Date.parse(e.end) : NaN;
      if (e.kind === "event") recent.push(e);
      else if (t > now) future.push(e);
      // Started and not finished. Several can be true at once — a class that runs
      // all afternoon, a slow cooker, and a call inside both — and each gets its
      // own row, because "what is running right now" is never a single answer.
      else if (!Number.isNaN(end) && end > now) live.push(e);
      else if (e.sticky && e.action) overdue.push(e);
      else past.push(e);
    }

    // The budget is computed whether or not the card is expanded, so the overflow
    // row can still say how many entries it is holding open.
    let budgetedPast = past;
    if (past.length > cfg.max_past) {
      // Keep the most recent. Recent events are counted separately — they are the
      // freshest thing on the card and the shortest-lived.
      budgetedPast = past.slice(past.length - cfg.max_past);
    }

    // Future: high priority is never collapsed; low goes first.
    let budgetedFuture = future;
    if (future.length > cfg.max_future) {
      const high = future.filter((e) => this._prio(e) === "high");
      const rest = future.filter((e) => this._prio(e) !== "high");
      const slots = Math.max(0, cfg.max_future - high.length);
      const ranked = cfg.collapse_low_priority
        ? [
            ...rest.filter((e) => this._prio(e) !== "low"),
            ...rest.filter((e) => this._prio(e) === "low"),
          ]
        : rest;
      const taken = new Set(ranked.slice(0, slots));
      budgetedFuture = future.filter((e) => high.includes(e) || taken.has(e));
    }

    const hidden = [
      ...past.filter((e) => !budgetedPast.includes(e)),
      ...future.filter((e) => !budgetedFuture.includes(e)),
    ];
    const keptPast = this._expanded ? past : budgetedPast;
    const keptFuture = this._expanded ? future : budgetedFuture;

    // Everything before the marker, back in time order. Live rows are never
    // budgeted away — a thing that is happening outranks a thing that already did.
    const before: SpineRow[] = [
      ...keptPast.map((e) => this._row("past", e)),
      ...recent.map((e) => this._row("recent", e)),
      ...overdue.map((e) => this._row("overdue", e)),
      ...live.map((e) => this._row("live", e)),
    ].sort((a, b) => Date.parse(a.entry!.start) - Date.parse(b.entry!.start));

    // The rail turns accent at the first thing that is currently happening and
    // stays accent through the marker, so "what is live" reads as one run of
    // colour rather than a stripe that switches on and off.
    const firstLive = before.find((r) => r.variant === "live");
    if (firstLive) firstLive.firstLive = true;

    const nowRow: SpineRow = {
      variant: "now",
      time: this._fmt(now, true),
      subline: this._stateObj?.attributes?.now ?? undefined,
      afterLive: !!firstLive && before[before.length - 1]?.variant === "live",
    };

    const rows = [...before, nowRow, ...keptFuture.map((e) => this._row("future", e))];
    // Only the final row fades its rail — and only when nothing follows it.
    if (rows.length && !hidden.length) rows[rows.length - 1].last = true;
    return { rows, hidden };
  }

  private _row(variant: SpineRow["variant"], entry: SpineEntry): SpineRow {
    const row: SpineRow = { variant, entry, time: this._fmt(Date.parse(entry.start), false) };
    if (variant === "live") {
      const start = Date.parse(entry.start);
      const end = Date.parse(entry.end!);
      row.progress = Math.min(1, Math.max(0, (this._now - start) / (end - start)));
    }
    return row;
  }

  /**
   * "3h 15m", "45m". Returns null when there is nothing worth saying — no end, an
   * all-day entry, or something so short the chip is noise.
   */
  private _duration(e: SpineEntry): string | null {
    if (!e.end || e.all_day) return null;
    const mins = Math.round((Date.parse(e.end) - Date.parse(e.start)) / 60_000);
    if (!Number.isFinite(mins) || mins < 5) return null;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    if (h && m) return `${h}h ${m}m`;
    return h ? `${h}h` : `${m}m`;
  }

  /** "2h 41m left" for the chip riding the progress bar. */
  private _remaining(e: SpineEntry): string {
    const mins = Math.max(0, Math.round((Date.parse(e.end!) - this._now) / 60_000));
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    const span = h && m ? `${h}h ${m}m` : h ? `${h}h` : `${m}m`;
    return `${span} left`;
  }

  /**
   * The end time, with a day when it is not today. A bare "8:00 AM" on an event
   * that runs until tomorrow morning is the kind of small lie that costs trust.
   */
  private _endLabel(e: SpineEntry): string {
    const end = new Date(Date.parse(e.end!));
    const time = this._fmt(end.getTime(), false);
    const today = new Date(this._now);
    if (end.toDateString() === today.toDateString()) return time;
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    if (end.toDateString() === tomorrow.toDateString()) return `${time} tomorrow`;
    return `${time} ${new Intl.DateTimeFormat(this._locale, { weekday: "short" }).format(end)}`;
  }

  private _prio(e: SpineEntry): Priority {
    if (e.priority === "high" || e.priority === "low") return e.priority;
    // Sun should never crowd out a real event, but still surfaces on a quiet day.
    return e.kind === "sun" ? "low" : "normal";
  }

  /** `stripMeridiem` renders the now marker as "2:39" per the design. */
  private _fmt(ms: number, stripMeridiem: boolean): string {
    const out = new Intl.DateTimeFormat(this._locale, {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(ms));
    return stripMeridiem ? out.replace(/\s*[APap][.\s]*[Mm][.\s]*$/, "").trim() : out;
  }

  private _sources(attrs: Record<string, any>, entries: SpineEntry[]): SpineSource[] {
    if (Array.isArray(attrs.sources) && attrs.sources.length) {
      return attrs.sources.filter((s: SpineSource) => s?.label);
    }
    // No `sources` attribute: derive labels so the pills still say where this came
    // from. Staleness cannot be derived, so nothing is claimed about it.
    const seen: string[] = [];
    for (const e of entries) {
      if (e.source && !seen.includes(e.source)) seen.push(e.source);
    }
    return seen.map((label) => ({ label }));
  }
}

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
}

// This file can legitimately be executed twice in one page. The integration
// registers the card two ways — an import baked into the frontend's index shell
// and a Lovelace resource — and after an upgrade the shell is still served from
// the service worker's cache, so it imports the *previous* versioned URL while
// the dashboard imports the current one. Two URLs, one file, two executions.
//
// `customElements.define` throws on a name that is already taken, and an
// exception at the top level of a module aborts the rest of it. Unguarded, the
// second execution would take out the picker registration below it, and the
// browser would report an error for a card that is in fact perfectly fine.
// Whichever copy arrives first wins; they are the same code.
if (!customElements.get("day-spine-card")) {
  customElements.define("day-spine-card", DaySpineCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "day-spine-card",
    name: "Dayline",
    description: "Today as one vertical spine: calendar, sun, and what the house will do on its own.",
    preview: false,
  });

  console.info("%c DAYLINE %c 0.1.1 ", "background:#d67f48;color:#1a1714", "");
}
