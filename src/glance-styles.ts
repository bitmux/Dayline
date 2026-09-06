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
    box-sizing: border-box;
    overflow: hidden;
  }

  /* ---------- the clock ---------- */

  .clock-zone {
    /* Takes every pixel the alerts have not claimed, and gives them back the
       moment one arrives. */
    flex: 1 1 auto;
    min-height: 0;
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
    font-size: calc(clamp(64px, 34cqw, 200px) * var(--clock-scale, 1));
  }
  .a1 .clock {
    font-size: 72px;
    font-size: calc(clamp(52px, 26cqw, 152px) * var(--clock-scale, 1));
  }
  .a2 .clock {
    font-size: 58px;
    font-size: calc(clamp(42px, 20cqw, 118px) * var(--clock-scale, 1));
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
  .next-auto {
    font-size: 15px;
    font-size: clamp(13px, 3.4cqw, 20px);
    color: var(--color-accent-2-400);
    line-height: 1.25;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
  .f3,
  .f4,
  .f5 {
    --clock-scale: 0.62;
  }

  .f1 .next-auto,
  .f2 .next-auto,
  .f3 .next-auto,
  .f4 .next-auto,
  .f5 .next-auto,
  .f1 .alert-sub,
  .f2 .alert-sub,
  .f3 .alert-sub,
  .f4 .alert-sub,
  .f5 .alert-sub {
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
