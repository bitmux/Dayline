/**
 * The calendar palette, as names the feed may use.
 *
 * A whitelist rather than a passthrough. The feed is ours, but this value ends
 * up inside a `style` attribute, and anything that reaches a stylesheet from
 * data should have to be on a list first. An unknown name simply gets no
 * colour, which is the same as not setting one.
 */
export const CAL_COLORS = ["blue", "cyan", "teal", "green", "violet", "magenta", "rose"];

/** `--cal` for a row, an all-day item or a pill; empty when it has no colour. */
export const calStyle = (name?: string): string =>
  name && CAL_COLORS.includes(name) ? `--cal: var(--cal-${name})` : "";
