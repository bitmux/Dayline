import { css } from "lit";

/**
 * Transcribed from timeline-card-reference.html, with every var(--*) resolved
 * against _ds/organic-8e49e359.../styles.css. Tokens are redeclared on :host so a
 * light variant later is a token swap rather than a rewrite of the rules below.
 */
export const styles = css`
  :host {
    /* Organic design system */
    --color-neutral-100: #f9f4ed;
    --color-neutral-300: #dcd3c4;
    --color-neutral-400: #c0b6a5;
    --color-neutral-500: #a19786;
    --color-neutral-600: #82796a;
    --color-accent: #c67139;
    --color-accent-200: #ffe1d0;
    --color-accent-300: #ffc6a5;
    --color-accent-400: #f6a06b;
    --color-accent-500: #d67f48;
    --color-accent-700: #8c491a;
    --color-accent-800: #643312;
    --color-accent-2-400: #aebf92;
    --color-accent-2-500: #8fa073;
    --radius-md: 16px;
    --radius-lg: 28px;
    --space-1: 4.4px;
    --space-2: 8.8px;
    --space-3: 13.2px;
    --space-4: 17.6px;
    --space-6: 26.4px;
    --font-heading: "Caprasimo", Georgia, serif;
    --font-body: "Figtree", system-ui, sans-serif;

    /* Dark ground — this card overrides the system's light cream default */
    --ds-bg: #1a1714;
    --ds-raised: #241f1a;
    --ds-divider: #2c2620;
    --ds-rail-past: #332c25;
    --ds-dot-past: #4a4038;
    --ds-alert: #2e2117;
    /* Text that sits *on* an accent fill rather than beside it. Its own token
       because in themed mode every accent shade collapses to the one
       --primary-color, and anything drawn accent-on-accent disappears. */
    --ds-on-accent: var(--color-accent-200);

    /*
     * Calendar identity — the *who* axis, since the spine already answers what
     * and when.
     *
     * Deliberately not theme-dependent. These are identities, not roles: the
     * calendar that is teal should stay teal when the dashboard changes clothes,
     * the way a highlighter does not change colour with the paper. They are also
     * only ever drawn as a filled dot, a ring, or a small swatch — never as text
     * on a background — so they need to be distinguishable, not readable, which
     * is what lets one set work on light and dark ground alike.
     *
     * Hues near 25deg and 85deg are absent on purpose: terracotta already means
     * *now* and sage already means *the house acting on its own*.
     */
    --cal-blue: #6aa9f0;
    --cal-cyan: #4fc3d9;
    --cal-teal: #45bfa5;
    --cal-green: #7bc86c;
    --cal-violet: #a98cf0;
    --cal-magenta: #d987d3;
    --cal-rose: #ef8098;

    /*
     * Now. The one mark on the card that must never be mistaken for anything
     * else, and the only colour with a job important enough to survive a
     * re-theme.
     *
     * Here it is simply the accent scale. The themed block is where the work
     * is — see --ds-now-seed there.
     */
    --ds-now: var(--color-accent-500);
    --ds-now-text: var(--color-accent-400);
    --ds-now-halo: rgba(198, 113, 57, 0.22);

    /*
     * Levels, for rows an automation pushed in and marked. Red is reserved
     * entirely for this: nothing else on the card is red, which is the only
     * reason red still means anything by the time you need it.
     */
    --ds-level-alert: #e5645f;
    --ds-level-info: #7fb2d9;

    display: block;
    /*
     * The fluid floor has to key off the card's own width, not the viewport: on a
     * wall tablet this card is one narrow column inside a wide window, and a
     * @media query would never fire.
     */
    container-type: inline-size;
    /*
     * Fill whatever the dashboard gives us. In a sections view that is the
     * height the user dragged; anywhere else the parent is auto and this
     * resolves to auto, which is the old behaviour exactly.
     */
    height: 100%;
  }

  /*
   * Theme mode. Colors defer to the active Home Assistant theme, with the
   * Organic values as fallbacks so an incomplete theme degrades to this card's
   * own palette rather than to browser defaults.
   *
   * Colors and the card surface — never the spine's geometry or its two
   * typefaces, which are the design. A theme that recolors the card, or gives it
   * the same glass and shadow as every other card on the dashboard, still reads
   * as this card. A theme that resizes it does not.
   */
  .card.themed {
    --ds-bg: var(--ha-card-background, var(--card-background-color, #1a1714));
    --ds-raised: var(--secondary-background-color, #241f1a);
    --ds-divider: var(--divider-color, #2c2620);
    --ds-rail-past: var(--divider-color, #332c25);
    --ds-dot-past: var(--disabled-text-color, #4a4038);
    --ds-alert: var(--error-color, #2e2117);

    --color-neutral-100: var(--primary-text-color, #f9f4ed);
    --color-neutral-300: var(--primary-text-color, #dcd3c4);
    --color-neutral-400: var(--secondary-text-color, #c0b6a5);
    --color-neutral-500: var(--secondary-text-color, #a19786);
    --color-neutral-600: var(--secondary-text-color, #82796a);

    --color-accent: var(--primary-color, #c67139);
    --color-accent-200: var(--primary-color, #ffe1d0);
    --color-accent-300: var(--primary-color, #ffc6a5);
    --color-accent-400: var(--primary-color, #f6a06b);
    --color-accent-500: var(--primary-color, #d67f48);
    --color-accent-700: var(--primary-color, #8c491a);
    --color-accent-800: var(--primary-color, #643312);

    --color-accent-2-400: var(--accent-color, #aebf92);
    --color-accent-2-500: var(--accent-color, #8fa073);

    /* The theme's own answer to "text on the primary colour", because ours
       would be the primary colour. */
    --ds-on-accent: var(--text-primary-color, #fff);

    /*
     * Now, under someone else's theme — tilted toward terracotta rather than
     * pinned to it.
     *
     * Deferring to --primary-color like the rest of the accent scale loses the
     * distinction entirely: the marker becomes the same colour as every other
     * themed thing on the card, and "where am I in the day" stops being
     * answerable at a glance. But a fixed terracotta is worse in the other
     * direction — on a warm background behind translucent cards, terracotta
     * text on near-terracotta ground is unreadable, and a theme's background is
     * not ours to predict.
     *
     * So each of these starts from the theme's own text colour, which is
     * readable against that theme's card by construction, and mixes our hue in.
     * Contrast comes from the theme; identity comes from us. On a light theme
     * the mix lands as a dark burnt orange, on a dark one as a warm peach, and
     * on an orange one it keeps roughly half the lightness distance the theme's
     * own text has — never the zero distance a pinned hex would give.
     *
     * oklab because mixing through sRGB darkens and greys the midpoint; the
     * whole value of this is that the midpoint stays a colour someone chose.
     */
    --ds-now-seed: #e07b39;
    --ds-now: color-mix(in oklab, var(--ds-now-seed) 72%, var(--primary-text-color, #f9f4ed));
    --ds-now-text: color-mix(in oklab, var(--ds-now-seed) 42%, var(--primary-text-color, #f9f4ed));
    --ds-now-halo: color-mix(in oklab, var(--ds-now-seed) 30%, transparent);

    /* A theme that has named its own error and info colours has said something
       more useful than our two guesses; take it. */
    --ds-level-alert: var(--error-color, #e5645f);
    --ds-level-info: var(--info-color, #7fb2d9);

    /*
     * The surface itself, on the same terms every other card gets.
     *
     * This card draws its own container rather than wrapping ha-card, so it
     * never saw these — which is why a frosted-glass theme came out the right
     * colours and the wrong material. Home Assistant themes can only set custom
     * properties, so honouring the four ha-card surface tokens is the whole of
     * what "looks like the other cards" means; the blur in particular is
     * --ha-card-backdrop-filter and nothing else.
     *
     * Every fallback is this card's existing look, so a theme that sets none of
     * them changes nothing. A border defaulting to ha-card's own 1px would put
     * a line around a card that has never had one.
     */
    border-radius: var(--ha-card-border-radius, var(--radius-lg));
    -webkit-backdrop-filter: var(--ha-card-backdrop-filter, none);
    backdrop-filter: var(--ha-card-backdrop-filter, none);
    box-shadow: var(--ha-card-box-shadow, none);
    border: var(--ha-card-border-width, 0px) solid
      var(--ha-card-border-color, transparent);
  }

  .card {
    background: var(--ds-bg);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
    height: 100%;
    box-sizing: border-box;
    /* The corners are the design; content must not square them off. */
    overflow: hidden;
  }

  /* ---------- header ---------- */

  .hdr {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-4);
  }
  /* The day name is what gives way when the card is narrow, never the clock. */
  .hdr-day {
    min-width: 0;
  }

  /*
   * The clock. Bounded above so it cannot grow past the two lines beside it and
   * push the day down the page — the whole reason this card exists is what is
   * under the header, and the header is not allowed to eat it.
   *
   * Tabular figures because a proportional 1 is narrower than a 0, and a clock
   * that shifts sideways every minute is the sort of thing you cannot un-see.
   */
  .clock {
    font-family: var(--font-heading);
    font-size: clamp(26px, 8.5cqw, 40px);
    line-height: 1;
    color: var(--color-neutral-300);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
    white-space: nowrap;
    flex: none;
  }
  .clock .mer {
    font-size: 0.4em;
    margin-left: 0.16em;
    letter-spacing: 0.06em;
    color: var(--color-neutral-500);
  }
  .day {
    font-family: var(--font-heading);
    font-weight: 400;
    font-size: 34px;
    line-height: 1;
    color: var(--color-neutral-100);
  }
  .sub {
    font-size: 14px;
    color: var(--color-neutral-500);
    margin-top: 4px;
  }
  /* At the foot of the card now, and wrapping: eight calendars overflowed a
     header built for three. */
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font: 600 10px/1 ui-monospace, Menlo, monospace;
    padding: 5px 8px;
    border-radius: 999px;
    background: var(--ds-divider);
    color: var(--color-neutral-400);
  }
  /*
   * The key. Without it the coloured dots up the spine are decoration; with it
   * they are an index, and the legend is where you go to read it.
   *
   * A swatch rather than tinting the pill's own text: the colours are chosen to
   * be told apart at dot size on any ground, not to be legible as 10px type,
   * and asking them to be both would mean a duller set that is worse at the one
   * job colour has here.
   */
  .pill .swatch {
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: var(--cal, transparent);
    flex: none;
  }
  .pill.stale {
    background: var(--ds-alert);
    color: var(--color-accent-200);
  }
  /* A stale pill is making a different point, and the colour would compete. */
  .pill.stale .swatch {
    background: var(--color-accent-300);
  }

  /* A #tag a person typed into an event title, in the three states the feed
     can put it in: outline for something the house is going to do, filled for
     something it has done, and flat grey for a tag that will do nothing at all.
     Grey is the default and the quietest, because a chip claiming the house is
     about to act has to earn it. */
  .tag {
    display: inline-block;
    font: 600 10px/1 ui-monospace, Menlo, monospace;
    padding: 3px 6px;
    margin-left: 6px;
    border: 1px solid var(--ds-divider);
    border-radius: 999px;
    color: var(--color-neutral-500);
    vertical-align: 1px;
    white-space: nowrap;
  }
  .tag.will_fire {
    border-color: var(--color-accent-700);
    color: var(--color-accent-300);
  }
  .tag.fired {
    border-color: var(--color-accent-500);
    background: var(--color-accent-800);
    color: var(--ds-on-accent);
  }

  /* ---------- all-day ---------- */

  /*
   * The count cap in the card does the real work; this is the safety net under
   * it. On a short card at phone width even four all-day rows can leave the
   * spine a couple of pixels tall, and expanding the frame deliberately should
   * not be able to swallow the day either.
   *
   * So the frame may never take more than two fifths of the card. Past that it
   * scrolls — which is the nested scroller worth avoiding as a primary
   * mechanism, and exactly right as a last resort, because by then the
   * alternative is a spine with no room to exist.
   *
   * The percentage resolves against the card only when the card has a definite
   * height. Under rows:auto it resolves to none, which is correct: nothing is
   * being crushed there, the card simply grows.
   */
  .allday {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--ds-raised);
    flex: 0 1 auto;
    min-height: 0;
    max-height: 40%;
    overflow-y: auto;
    scrollbar-width: thin;
    overscroll-behavior: contain;
  }
  .allday-item {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    font-size: 14.5px;
    color: var(--color-neutral-300);
  }
  .allday-item .icon {
    color: var(--cal, var(--color-accent-2-400));
    flex: none;
    margin-top: 1px;
  }
  .allday-body {
    flex: 1;
    min-width: 0;
  }
  /* Indented to the text column, so it reads as the end of the list rather
     than another entry with a missing icon. */
  .allday-more {
    margin-left: 28px;
    font-size: 13.5px;
  }

  /* ---------- spine ---------- */

  /*
   * The spine is what gives when the card is shorter than its day. Header,
   * all-day frame and footer are fixed points a person navigates by; the middle
   * is the part that is honestly a list, so the middle is what scrolls.
   *
   * min-height:0 because a flex child will not shrink below its content
   * without it, and the overflow would leave the card instead of entering the
   * scroller — which looks exactly like a broken layout.
   */
  .spine {
    display: flex;
    flex-direction: column;
    /*
     * A floor, not the zero it used to be. Zero let the all-day frame and the
     * legend squeeze the day itself down to a few pixels on a short card —
     * a timeline card showing no timeline. The frame above shrinks and scrolls
     * before this gives, because the day is the point and everything else on
     * the card is context for it.
     */
    min-height: 72px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--ds-rail-past) transparent;
  }
  .row {
    display: flex;
    gap: 14px;
  }
  .t {
    width: 66px;
    flex: none;
    text-align: right;
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .rail {
    width: 2px;
    flex: none;
    position: relative;
  }

  /*
   * Weather sits under the time, inside the gutter, so it reads as part of
   * *when* rather than competing with the event title for attention.
   */
  .wx {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 3px;
    margin-top: 4px;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--color-neutral-600);
  }
  .wx .icon {
    flex: none;
    opacity: 0.9;
  }
  /* Rain worth knowing about before you leave the house. */
  .wx.wet {
    color: var(--color-accent-400);
  }
  .c {
    flex: 1;
    min-width: 0;
  }

  /* past */
  .row.past .t {
    color: var(--color-neutral-600);
    padding-top: 13px;
  }
  .row.past .rail {
    background: var(--ds-rail-past);
  }
  /*
   * A past dot keeps a trace of whose it was, muted well down. Identity still
   * helps when you are scanning back up the morning, but past has to keep
   * reading as past — full strength here would make the finished half of the
   * day louder than the half still to come.
   *
   * With no --cal this mixes the grey with itself, which is the grey.
   */
  .row.past .rail::after {
    content: "";
    position: absolute;
    left: -4px;
    top: 18px;
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--cal, var(--ds-dot-past)) 45%, var(--ds-dot-past));
  }
  .row.past .c {
    padding: 10px 0 16px;
    font-size: 15px;
    color: var(--color-neutral-600);
    text-decoration: line-through;
    text-decoration-color: rgba(255, 255, 255, 0.2);
  }

  /*
   * recent — "what just happened". Past geometry, but sage rather than grey and
   * never struck through: nothing was completed, the house simply did something.
   */
  .row.recent .t {
    color: var(--color-neutral-600);
    padding-top: 13px;
  }
  .row.recent .rail {
    background: var(--ds-rail-past);
  }
  .row.recent .rail::after {
    content: "";
    position: absolute;
    left: -4px;
    top: 18px;
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--color-accent-2-500);
  }
  .row.recent .c {
    padding: 10px 0 16px;
    font-size: 14.5px;
    color: var(--color-neutral-500);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .row.recent .icon {
    color: var(--color-accent-2-400);
    flex: none;
  }

  /*
   * overdue — its time has passed but it is not done. Reads live, not finished:
   * accent time, full-strength title, filled terracotta dot, no strikethrough.
   */
  .row.overdue .t {
    color: var(--color-accent-400);
    padding-top: 13px;
  }
  .row.overdue .rail {
    background: var(--ds-rail-past);
  }
  .row.overdue .rail::after {
    content: "";
    position: absolute;
    left: -4px;
    top: 18px;
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--color-accent-500);
  }
  .row.overdue .c {
    padding: 10px 0 16px;
  }
  .row.overdue.done {
    opacity: 0.45;
  }

  /*
   * live — started, not finished. Reads as the most present thing on the card,
   * because it is: it sits above the marker in accent, never struck through, and
   * the budget never collapses it.
   */
  .row.live .t {
    color: var(--color-accent-400);
    padding-top: 13px;
  }
  .row.live .rail {
    background: var(--color-accent-500);
  }
  /* The colour starts at the first live dot, matching how the now marker does it. */
  .row.live.live-start .rail {
    background: linear-gradient(var(--ds-rail-past) 0 23px, var(--color-accent-500) 23px 100%);
  }
  .row.live .rail::after {
    content: "";
    position: absolute;
    left: -5px;
    top: 17px;
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: var(--color-accent-500);
    box-sizing: border-box;
  }
  .row.live .c {
    padding: 10px 0 16px;
  }

  /* the progress bar under a live entry */
  .prog {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-top: 9px;
  }
  .prog-track {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 14px;
    border-radius: 999px;
    background: var(--ds-divider);
    overflow: hidden;
  }
  .prog-fill {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: 999px;
    /* One step up from the rail's accent-800: at bar size that reads as filled
       rather than as a slightly different shade of dark. */
    background: var(--color-accent-700);
  }
  .prog-chip {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--color-accent-300);
    white-space: nowrap;
  }
  .prog-end {
    flex: none;
    font-size: 12px;
    font-weight: 700;
    color: var(--color-accent-400);
    font-variant-numeric: tabular-nums;
  }

  /* the duration chip on upcoming entries */
  .dur {
    display: inline-block;
    margin-left: 8px;
    padding: 2px 7px;
    border-radius: 999px;
    background: var(--ds-divider);
    color: var(--color-neutral-500);
    font-size: 11px;
    font-weight: 700;
    vertical-align: 2px;
    white-space: nowrap;
  }

  /* now */
  /*
   * The now marker draws from --ds-now rather than the accent scale directly.
   * That indirection is the whole point: in themed mode every accent shade
   * collapses to the single --primary-color, and the one mark on the card that
   * must never be mistaken for anything else would become the same colour as
   * everything else the theme touches. See the --ds-now block on :host.
   */
  .row.now .t {
    font-family: var(--font-heading);
    font-weight: 400;
    font-size: 20px;
    color: var(--ds-now-text);
    padding-top: 8px;
  }
  .row.now .rail {
    background: linear-gradient(var(--ds-rail-past) 0 20px, var(--ds-now) 20px 100%);
  }
  /* Something is already running above the marker — do not break the run. */
  .row.now.after-live .rail {
    background: var(--ds-now);
  }
  .row.now .rail::after {
    content: "";
    position: absolute;
    left: -8px;
    top: 12px;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    background: var(--ds-now);
    box-shadow: 0 0 0 5px var(--ds-now-halo);
  }
  .row.now .c {
    padding: 6px 0 18px;
  }
  .now-l {
    font-size: 15px;
    font-weight: 700;
    color: var(--ds-now-text);
  }
  .now-s {
    font-size: 14px;
    color: var(--color-neutral-500);
    margin-top: 1px;
  }

  /* future */
  .row.future .t {
    color: var(--color-neutral-300);
    padding-top: 13px;
  }
  .row.future .rail {
    background: var(--color-accent-800);
  }
  /*
   * The ring is where a calendar's colour lands on a future row. It is the one
   * mark on the spine that is not already saying something else: terracotta is
   * *now*, sage on the sub-line is *the house acting on its own*, and grey is
   * *done*. Falls back to the sage ring, so an uncoloured calendar looks exactly
   * as it always did.
   */
  .row.future .rail::after {
    content: "";
    position: absolute;
    left: -5px;
    top: 17px;
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: var(--ds-bg);
    border: 3px solid var(--cal, var(--color-accent-2-500));
    box-sizing: border-box;
  }
  .row.future .c {
    padding: 10px 0 16px;
  }

  /*
   * A level takes over the row's dot and its icon, and nothing else — not the
   * title, not the rail. The row still has to read as part of one day; a red
   * band across it would make the timeline stop being a timeline at the point
   * it matters most.
   */
  .row.lvl-alert .rail::after,
  .row.lvl-info .rail::after {
    background: var(--lvl);
    border-color: var(--lvl);
  }
  .row.lvl-alert .ttl .icon,
  .row.lvl-info .ttl .icon {
    color: var(--lvl);
    flex: none;
    margin-right: 6px;
    vertical-align: -2px;
  }
  .row.lvl-alert {
    --lvl: var(--ds-level-alert);
  }
  .row.lvl-info {
    --lvl: var(--ds-level-info);
  }
  /* Alert gets the halo the now marker has. It is the only other thing on the
     card allowed to interrupt you. */
  .row.lvl-alert .rail::after {
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--ds-level-alert) 22%, transparent);
  }

  /* last row — the rail fades out rather than stopping hard */
  .row.last .rail {
    background: linear-gradient(var(--color-accent-800) 0 28px, transparent 28px 100%);
  }
  .row.last.past .rail,
  .row.last.recent .rail,
  .row.last.live .rail,
  .row.last.overdue .rail {
    background: linear-gradient(var(--ds-rail-past) 0 28px, transparent 28px 100%);
  }
  .row.last .c {
    padding-bottom: 0;
  }

  .ttl {
    font-size: 16px;
    font-weight: 600;
    color: var(--color-neutral-100);
  }
  .auto {
    font-size: 13.5px;
    color: var(--color-accent-2-400);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 3px;
  }
  .auto .icon {
    flex: none;
  }

  /* ---------- the action button ---------- */

  .act {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 7px;
    padding: 6px 11px;
    border: none;
    border-radius: 999px;
    background: var(--ds-divider);
    color: var(--color-accent-300);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 120ms ease;
  }
  .act:hover {
    background: #3a322a;
  }
  .act:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .act[disabled] {
    cursor: default;
    opacity: 0.6;
  }
  /* Two buttons wrap rather than squeeze: this card is often one narrow column,
     and a truncated "Close it" is worse than a second line. */
  .acts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  /*
   * The second button is the decline. Quieter on purpose — it carries no tick
   * and no accent, because "not now" should not look as inviting as the thing
   * the row is actually asking for.
   */
  .act-alt {
    background: transparent;
    border: 1px solid var(--ds-divider);
    color: var(--color-neutral-500);
  }
  .act-alt:hover {
    background: var(--ds-divider);
    color: var(--color-neutral-300);
  }

  /* ---------- overflow ---------- */

  .row.more .rail {
    background: linear-gradient(var(--color-accent-800) 0 14px, transparent 14px 100%);
  }
  .row.more .c {
    padding: 8px 0 0;
  }
  .more-btn {
    padding: 0;
    border: none;
    background: none;
    font-family: inherit;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-neutral-500);
    cursor: pointer;
    text-align: left;
  }
  .more-btn:hover {
    color: var(--color-neutral-300);
  }
  .more-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 4px;
  }

  /* ---------- interactive rows (opt-in) ---------- */

  .row.tappable {
    cursor: pointer;
    border-radius: 10px;
    transition: background 120ms ease;
  }
  .row.tappable:hover {
    background: var(--ds-raised);
  }
  .row.tappable:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* ---------- loading ---------- */

  /*
   * The rail runs full height with no dots. The card must not change size while
   * loading — a card that resizes on every load reads as unreliable.
   */
  .row.skeleton .rail {
    background: var(--ds-rail-past);
  }
  .row.skeleton .rail::after {
    content: none;
  }
  .row.skeleton .c {
    padding: 10px 0 16px;
    min-height: 20px;
  }

  /* ---------- footer ---------- */

  .foot {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: var(--space-3);
    border-top: 1px solid var(--ds-divider);
    font-size: 12.5px;
    line-height: 1.45;
    color: var(--color-neutral-600);
  }
  .foot .icon {
    flex: none;
  }
  .foot.warn {
    color: var(--color-accent-200);
  }
  .foot + .foot {
    padding-top: 10px;
    border-top: none;
  }

  /* ---------- fluid floor ---------- */

  @container (max-width: 420px) {
    .card {
      padding: var(--space-4);
      gap: var(--space-4);
    }
    .day {
      font-size: 28px;
    }
    .t {
      width: 58px;
    }
    .row {
      gap: 11px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .row.tappable,
    .act {
      transition: none;
    }
  }
`;
