/**
 * Rows that run out, drawn between the ticks.
 *
 * Everything else on these cards changes on the minute, so a minute is all the
 * resolution it ever needed: an appointment at 3:05 is at 3:05 for the whole of
 * 3:05. A timer is the first thing here that is watched rather than read. Ten
 * minutes of cookies advances its bar by a tenth on each tick, which is not a
 * bar filling, it is a bar teleporting — and the last minute of it says "1m
 * left" for sixty seconds and then the row is simply gone.
 *
 * Two mechanisms, and neither of them is a frame loop:
 *
 * The bar is a CSS animation with a negative delay. The browser is told the
 * whole span once -- fill linearly over ten minutes, and you are four minutes
 * in already -- and it runs the rest on the compositor without asking us
 * anything. The card's own re-render on each minute hands it the same
 * instruction with a fresh offset, which costs nothing and silently corrects
 * any drift, including a device that was asleep.
 *
 * The text is scheduled to the moment it would change rather than to the wall
 * clock, which is the part a minute tick gets wrong even when it is prompt: a
 * timer ending at 6:40:20 changes what it has to say at :20 past, not on the
 * minute. Under a minute left it counts seconds, because at that point a
 * countdown that does not count is just a label.
 */

/**
 * Live spans under this show seconds. A countdown ends by counting.
 *
 * 59 rather than 60, so the handover reads right in both directions: a minute
 * and a half rounds down to "1m" and stays there, and the first thing seconds
 * mode ever says is "59s". At a flat 60_000 the rounding on one side and the
 * ceiling on the other overlap, and the row spends a second announcing "60s".
 */
const SECONDS_UNDER = 59_000;

/**
 * "2h 41m left", "9m left", "45s left".
 *
 * Minutes are rounded, as they have always been on these cards -- an event with
 * 9m40 to run reads 10m, the way a person would say it. Seconds are rounded up
 * instead, because a row reading "0s left" while the thing is still running is
 * the one number a countdown is not allowed to get wrong.
 */
export const remaining = (endMs: number, nowMs: number): string => {
  const rem = Math.max(0, endMs - nowMs);
  if (rem <= SECONDS_UNDER) return `${Math.ceil(rem / 1000)}s left`;
  const mins = Math.round(rem / 60_000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h && m ? `${h}h ${m}m` : h ? `${h}h` : `${m}m`} left`;
};

/**
 * Milliseconds until `remaining` would say something else, or null when the
 * span is over and there is nothing further to wait for.
 *
 * The minute case lands one millisecond past the rounding boundary rather than
 * on it: at exactly 90 seconds the label is still "2m", and waking up there
 * would schedule the same text again and then sit through the whole of the next
 * minute showing a number that went stale immediately.
 *
 * And whichever comes first, because the last minute does not arrive on a
 * minute boundary. A row reading "1m left" changes when it drops under sixty
 * seconds, which from 1:29 is thirty seconds away, not a minute -- miss that
 * and the row says "1m" for the whole of the minute it should have spent
 * counting down.
 */
export const nextChange = (endMs: number, nowMs: number): number | null => {
  const rem = endMs - nowMs;
  if (rem <= 0) return null;
  if (rem <= SECONDS_UNDER) return (rem % 1000) || 1000;
  return Math.min(((rem - 30_000) % 60_000) + 1, rem - SECONDS_UNDER);
};

/**
 * The inline style for a progress fill: how full it is, and how it gets fuller.
 *
 * Both at once, deliberately. The transform is the truth of this instant and
 * the animation overrides it while it runs, so the one rule that turns the
 * animation off -- reduced motion, in the stylesheet -- lands on a bar that is
 * already in the right place rather than an empty one.
 *
 * Translation rather than a width or a scale. A width animates by relayout
 * every frame, which is the expensive thing on the hardware these cards get
 * left running on, and a scale would squash the rounded cap on the leading edge
 * into an ellipse. Sliding a full-width bar out from under the track's own
 * clipping keeps the cap circular and keeps the whole thing on the compositor.
 */
export const fillStyle = (startMs: number, endMs: number, nowMs: number): string => {
  const span = endMs - startMs;
  const pct = Math.min(1, Math.max(0, (nowMs - startMs) / span)) * 100;
  const offset = `transform:translateX(${(pct - 100).toFixed(2)}%)`;
  // A span that is over, or one whose arithmetic never made sense, gets the
  // position and no animation. There is nothing left to animate toward.
  if (!Number.isFinite(span) || span <= 0 || nowMs >= endMs) return offset;
  return `${offset};animation:dayline-run ${Math.round(span)}ms linear ${Math.round(startMs - nowMs)}ms 1 both`;
};
