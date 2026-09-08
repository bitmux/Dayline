import { css } from "lit";

import { tokens } from "./tokens";

/**
 * The glance card, sized for a wall.
 *
 * The spine card is read at arm's length by someone deciding what to do next.
 * This one is read at eight feet by someone walking past, so the rules are
 * different in one way that drives everything else here: type is enormous and
 * there is almost none of it. What survived the cut is the clock, one event,
 * and whatever is currently wrong.
 *
 * The three .a0 / .a1 / .a2 classes are the reflow. Space on a fixed panel is
 * zero-sum — an alert can only appear by taking room from the clock — so the
 * clock is sized by how many alerts are on screen rather than left to fight
 * them for the space.
 */
export const glanceStyles = css`
  ${tokens}

  .card {
    background: var(--ds-bg);
    border-radius: var(--radius-lg);
    /* The insets are extra padding rather than a smaller card on purpose: the
       background still runs edge to edge under whatever is drawing over it, so
       a panel overlay sits on the card rather than on a gap beside it. */
    padding: calc(var(--space-6) + var(--inset-top, 0px)) var(--space-6)
      calc(var(--space-6) + var(--inset-bottom, 0px));
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
    height: 100%;
    /* Unset by default, so this is inert until someone gives the card a ceiling
       the parent would not. */
    max-height: var(--glance-max-height, none);
    box-sizing: border-box;
    overflow: hidden;
    /* Only so the corner weather has something to be a corner of. */
    position: relative;
  }

  /* ---------- conditions now ---------- */
  /*
   * Absolutely placed, and that is the point: on a panel that cannot scroll,
   * anything in the normal flow is height taken away from the clock. This costs
   * nothing, because it sits in room the centred clock was never going to use.
   */
  .wx-now {
    position: absolute;
    top: calc(var(--space-6) + var(--inset-top, 0px));
    right: var(--space-6);
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--color-neutral-500);
    line-height: 1;
    /* Below the clock in the reading order it belongs to. Loud enough to read
       at a glance, quiet enough that nobody looks at it first. */
    font-size: 20px;
    font-size: clamp(15px, 4cqw, 26px);
  }
  .wx-now svg {
    width: 1.15em;
    height: 1.15em;
  }
  .wx-temp {
    font-variant-numeric: tabular-nums;
  }

  /* ---------- the clock ---------- */

  .clock-zone {
    /* Takes every pixel the alerts have not claimed, and gives them back the
       moment one arrives.

       No min-height of zero, which would be the reflex here and is wrong. It lets
       this box shrink below the clock inside it; the clock then spills out of a
       zone that is centring it, in both directions at once, and the card's own
       scrollHeight never changes — so the measure concludes everything fits
       while the top of the clock is being cut off. Left at its content floor,
       the overflow reaches the card, where it can be seen and answered by making
       the clock smaller, which is the actual remedy. */
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-1);
  }

  .clock {
    font-family: var(--font-clock);
    font-weight: 500;
    color: var(--color-neutral-100);
    /* Tabular figures so the whole line does not shift sideways at 1:10.
       A clock that twitches every minute is the thing you notice from across
       a room, and noticing the clock is not the point. */
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum" 1;
    line-height: 1;
    letter-spacing: -0.02em;
    /* Plain px first, so a browser too old for container units still gets a
       readable size rather than an inherited default. The clamp below wins
       wherever cqw resolves. */
    font-size: 96px;
    font-size: calc(clamp(64px, 32cqw, 176px) * var(--clock-scale, 1));
  }
  .a1 .clock {
    font-size: 72px;
    font-size: calc(clamp(52px, 24cqw, 140px) * var(--clock-scale, 1));
  }
  .a2 .clock {
    font-size: 58px;
    font-size: calc(clamp(42px, 19cqw, 108px) * var(--clock-scale, 1));
  }

  .mer {
    /* Small, and quieter than the digits. At a third of a 200px clock the
       meridiem was competing with the time for the same glance, and nobody has
       ever needed to know it is the afternoon from across a room. */
    font-size: 0.24em;
    font-weight: 400;
    color: var(--color-neutral-500);
    margin-left: 0.14em;
    /* Baseline-aligned rather than superscript: this is a word after a number,
       not a footnote on it. */
    letter-spacing: 0;
  }

  .date {
    font-size: 20px;
    font-size: clamp(15px, 4.4cqw, 26px);
    color: var(--color-neutral-500);
    letter-spacing: 0.01em;
  }

  /* ---------- what is next ---------- */

  .next {
    flex: 0 0 auto;
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--ds-divider);
    min-width: 0;
  }

  .next-when {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  /* Small, spaced, and upper case — a label, so it is never mistaken for part
     of the sentence underneath it. */
  .next-eyebrow {
    font-size: 12px;
    font-size: clamp(10px, 2.6cqw, 15px);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
    color: var(--color-neutral-500);
    line-height: 1;
    margin-bottom: 2px;
  }
  .next-time {
    font-size: 24px;
    font-size: clamp(19px, 5.4cqw, 32px);
    font-weight: 600;
    color: var(--color-neutral-100);
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }
  /* The relative reading is the one that gets acted on. "In 10 min" is a
     decision; "3:40" is arithmetic someone has to do while walking. */
  .next-rel {
    font-size: 14px;
    font-size: clamp(12px, 3.2cqw, 18px);
    color: var(--ds-now-text);
    letter-spacing: 0.01em;
  }

  .next-what {
    /* Grows, so the lines inside it have the full width of the band to work
       with: the progress track reaches across, and the forecast at the end of
       the follow-on line sits at the edge of the card instead of trailing the
       title by a space. Behind a short title that was the whole of the empty
       lower right. */
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .next-title {
    font-size: 22px;
    font-size: clamp(17px, 4.8cqw, 30px);
    color: var(--color-neutral-100);
    line-height: 1.2;
    /* Two lines, then stop. A long calendar summary must never push the alerts
       off the bottom of a panel that cannot scroll. */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  /* An alarm carries no calendar colour, so it gets the icon where a coloured
     dot would go. Same box either way, or the row would sit indented from
     every row that has one. */
  .next-ico {
    display: inline-flex;
    vertical-align: -0.12em;
    margin-right: 0.42em;
    color: var(--color-neutral-500);
  }
  .next-ico svg {
    width: 0.82em;
    height: 0.82em;
  }
  /* Which phone, said quietly after the word. "Alarm" is the fact; whose it is
     only matters in a house with more than one. */
  .next-whose {
    margin-left: 0.5em;
    font-size: 0.68em;
    color: var(--color-neutral-500);
  }

  .next-auto {
    font-size: 15px;
    font-size: clamp(13px, 3.4cqw, 20px);
    color: var(--color-accent-2-400);
    line-height: 1.25;
    display: flex;
    align-items: center;
    gap: 0.4em;
  }
  /* The icon keeps its size; the sentence is the part that gives way. */
  .next-auto .icon,
  .next-leave .icon {
    flex: none;
  }
  .next-auto span,
  .next-leave span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* Neutral while there is time; the accent the moment there is not. The only
     line on this card that is an instruction rather than a fact. */
  /* ---------- how far through ---------- */
  /*
   * A few pixels of track instead of a line of text. That is the whole reason
   * the follow-on line below can also be afforded: "how much of this is left"
   * and "what is after it" together cost about what one sentence would.
   */
  .prog {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: 5px;
  }
  .prog-track {
    flex: 1 1 auto;
    height: 6px;
    border-radius: 3px;
    background: var(--ds-prog-track, rgba(255, 255, 255, 0.11));
    overflow: hidden;
  }
  .prog-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--ds-now-dot, var(--color-accent-500));
  }
  .prog-left {
    flex: none;
    font-size: 13px;
    font-size: clamp(11px, 2.9cqw, 17px);
    color: var(--color-neutral-500);
    font-variant-numeric: tabular-nums;
  }

  /* ---------- and then ---------- */
  .then {
    font-size: 15px;
    font-size: clamp(13px, 3.4cqw, 20px);
    color: var(--color-neutral-500);
    line-height: 1.25;
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  /* The title gives way first: the temperature is two characters and losing
     them saves nothing, while a long summary can always spare its tail. */
  .then-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .then .next-wx {
    font-size: 1em;
  }
  /* Matches the eyebrow's treatment, so "Next" means the same thing in both
     places it appears on this card. */
  .then-lead {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.78em;
    font-weight: 600;
    color: var(--color-neutral-600, var(--color-neutral-500));
    margin-right: 0.6em;
  }
  /* Quieter than the clock time beside it: the two say the same thing, one as
     a fact and one as arithmetic, and the arithmetic is the supporting half. */
  .then-rel {
    color: var(--color-neutral-600, var(--color-neutral-500));
    font-variant-numeric: tabular-nums;
    margin-right: 0.5em;
  }
  /* The time carries the weight, because it is the part that gets acted on. */
  .then-time {
    color: var(--color-neutral-400, var(--color-neutral-500));
    font-variant-numeric: tabular-nums;
    margin-right: 0.5em;
  }

  /* The meridiem follows the tint, so the clock reads as one object going
     amber rather than a number arguing with its own AM. */
  .clock.tint .mer {
    color: inherit;
    opacity: 0.72;
  }

  /*
   * The forecast for the event being named, in what was dead space behind every
   * short title. margin-left:auto rather than a fixed column: with a long
   * title the band still gives the words the room, and this closes up.
   */
  .next-wx {
    flex: 0 0 auto;
    margin-left: auto;
    align-self: center;
    padding-left: var(--space-3);
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--color-neutral-500);
    line-height: 1;
    font-size: 17px;
    font-size: clamp(14px, 3.6cqw, 22px);
  }
  .next-wx svg {
    width: 1.15em;
    height: 1.15em;
  }
  /* Rain is the only forecast that changes what someone does on the way out. */
  .next-wx.wet {
    color: var(--color-accent-400);
  }

  .next-leave {
    font-size: 15px;
    font-size: clamp(13px, 3.4cqw, 20px);
    color: var(--color-neutral-500);
    line-height: 1.25;
    display: flex;
    align-items: center;
    gap: 0.4em;
  }
  .next-leave.late {
    color: var(--color-accent-300);
  }
  .dot {
    display: inline-block;
    width: 0.62em;
    height: 0.62em;
    border-radius: 50%;
    margin-right: 0.42em;
    /* No colour on the calendar means no dot at all, rather than a grey one
       standing in for an answer we do not have. */
    background: var(--cal, transparent);
    vertical-align: baseline;
  }
  /*
   * A ring, not a disc, for anything that has not started — the spine says the
   * same thing with its rail dots, and a card that fills the dot early is
   * asserting "now" about an event that is not.
   */
  .dot.ring {
    background: transparent;
    border: 0.16em solid var(--cal);
    box-sizing: border-box;
  }

  .quiet {
    font-size: 18px;
    font-size: clamp(15px, 4cqw, 24px);
    color: var(--color-neutral-500);
  }

  /* ---------- alerts ---------- */

  .alerts {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .alert {
    background: var(--ds-raised);
    border-radius: var(--radius-md);
    /* The stripe carries the level. It is the only red on either card, which is
       the whole reason red still means something by the time one of these
       appears. */
    border-left: 4px solid var(--lv, var(--color-neutral-500));
    padding: var(--space-3) var(--space-4);
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
    /* Always, rather than below some measured width. The buttons will not
       shrink, so without this the text is the only thing that can, and it
       collapses to one letter per line long before anything overflows and the
       fit steps notice. Wrapping instead pushes the buttons onto their own row,
       which does overflow, which is a problem the card knows how to solve. */
    flex-wrap: wrap;
  }
  .alert.pending {
    opacity: 0.45;
  }

  .alert-ico {
    flex: 0 0 auto;
    color: var(--lv, var(--color-neutral-400));
    display: flex;
  }

  .alert-body {
    /* The floor is what makes the wrap happen at the right moment: below about
       this much room the text stops being readable, so the buttons go under. */
    flex: 1 1 10em;
    min-width: 8em;
  }
  .alert-title {
    font-size: 19px;
    font-size: clamp(15px, 4.2cqw, 26px);
    color: var(--color-neutral-100);
    line-height: 1.25;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .alert-sub {
    font-size: 14px;
    font-size: clamp(12px, 3cqw, 17px);
    color: var(--color-neutral-500);
    margin-top: 2px;
  }

  .btns {
    flex: 0 0 auto;
    display: flex;
    gap: var(--space-2);
    margin-left: auto;
  }
  button {
    font-family: inherit;
    font-size: 16px;
    font-size: clamp(14px, 3.4cqw, 20px);
    color: var(--color-accent-300);
    background: var(--ds-alert);
    border: 1px solid transparent;
    border-radius: 999px;
    /* Sized for a thumb on a wall, not a cursor on a desk. Below about 44px
       these stop being reliably pressable by someone walking past. */
    min-height: 44px;
    padding: 0 var(--space-4);
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    cursor: pointer;
    white-space: nowrap;
    -webkit-tap-highlight-color: transparent;
  }
  button.quiet-btn {
    color: var(--color-neutral-400);
    background: transparent;
    border-color: var(--ds-divider);
  }
  button:focus-visible {
    outline: 2px solid var(--color-accent-400);
    outline-offset: 2px;
  }
  button:active {
    transform: translateY(1px);
  }
  @media (prefers-reduced-motion: reduce) {
    button:active {
      transform: none;
    }
  }

  /* ---------- the fit steps ----------
     Steps 3 and 4 drop whole elements and so live in the render; these two only
     hide, which CSS does without another pass through Lit. */

  /* Step 2: the clock comes down before anything else is taken away.
     Sizing off the container's width alone is right on a panel roughly as tall
     as it is wide, and wrong on a wide short one — 1024x300 would give a clock
     taller than the card. Rather than reach for height units, which need a
     definite height this card cannot promise in every dashboard, the measure
     that is already running just tells it to be smaller. */
  .f2,
  .f3 {
    --clock-scale: 0.78;
  }
  .f4,
  .f5,
  .f6 {
    --clock-scale: 0.56;
  }

  .f1 .next-auto,
  .f2 .next-auto,
  .f3 .next-auto,
  .f4 .next-auto,
  .f5 .next-auto,
  .f6 .next-auto,
  .f4 .next-leave,
  .f5 .next-leave,
  .f6 .next-leave,
  .f4 .then,
  .f5 .then,
  .f6 .then,
  .f1 .alert-sub,
  .f2 .alert-sub,
  .f3 .alert-sub,
  .f4 .alert-sub,
  .f5 .alert-sub,
  .f6 .alert-sub {
    display: none;
  }

  /* ---------- narrow ---------- */

  @container (max-width: 380px) {
    /* Once they have wrapped onto their own row anyway, spread them across it:
       a thumb aimed from a doorway wants the whole width, not two pills tucked
       into the right corner. */
    .btns {
      width: 100%;
    }
    button {
      flex: 1 1 0;
      justify-content: center;
    }
    .next {
      flex-direction: column;
      align-items: flex-start;
      gap: var(--space-1);
    }
  }
`;
