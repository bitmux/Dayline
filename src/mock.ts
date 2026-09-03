/**
 * Mock feeds for dev/index.html. Times are built relative to "now" so the harness
 * always shows a plausible mid-afternoon, whenever it is opened.
 */
import type { SpineEntry } from "./types";

const at = (h: number, m = 0): string => {
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};
const offset = (mins: number): string => new Date(Date.now() + mins * 60_000).toISOString();

export const ordinary: SpineEntry[] = [
  {
    id: "cal:trash",
    start: at(0),
    all_day: true,
    kind: "calendar",
    source: "CalDAV",
    title: "Trash out tonight",
    // An all-day tag is the common case, not an edge one — "#Away all weekend".
    tags: ["Away"],
  },
  {
    id: "auto:morning",
    start: at(7, 0),
    kind: "automation",
    source: "House",
    title: "Morning · lights up, thermostat to 70°",
  },
  // A past row, so the harness shows a chip beside a struck-through title too.
  { id: "cal:school", start: at(8, 20), kind: "calendar", source: "Google", title: "Kid to school",
    tags: ["Home"] },
  {
    id: "cal:kid-out",
    start: at(15, 50),
    kind: "calendar",
    source: "Google",
    title: "Kid out of school",
    automation: "Entry unlocks on her arrival",
    entity_id: "calendar.family",
  },
  {
    id: "cal:dinner",
    start: at(16, 15),
    kind: "calendar",
    source: "CalDAV",
    title: "Making dinner for house",
    automation: "Kitchen 90%, hallway 40%",
  },
  {
    id: "sun:set",
    start: at(19, 47),
    kind: "sun",
    source: "Sun",
    title: "Sunset",
    automation: "Evening lights over 20 minutes",
    entity_id: "sun.sun",
  },
  {
    id: "cal:bed",
    start: at(21, 0),
    kind: "calendar",
    source: "Google",
    title: "Kid bed time",
    tags: ["Quiet"],
    automation: "Story on Sonos, 20 min, then dark",
    priority: "high",
  },
];

export const emptyDay: SpineEntry[] = [
  { id: "sun:rise", start: at(6, 58), kind: "sun", source: "Sun", title: "Sunrise" },
  {
    id: "sun:set",
    start: at(19, 42),
    kind: "sun",
    source: "Sun",
    title: "Sunset",
    automation: "Evening lights over 20 minutes",
  },
];

export const staleSource: SpineEntry[] = [
  {
    id: "cal:school",
    start: offset(49),
    kind: "calendar",
    source: "CalDAV",
    title: "Kid to school",
    automation: "Doors lock behind her",
  },
];

/** The new variants: an overdue actionable, a recent event, and enough to overflow. */
export const busy: SpineEntry[] = [
  {
    id: "cal:recycling",
    start: at(0),
    all_day: true,
    kind: "calendar",
    source: "CalDAV",
    title: "Recycling out",
    automation: "Porch light stays on until 11",
  },
  {
    id: "todo:bins",
    start: at(0),
    all_day: true,
    kind: "todo",
    source: "Tasks",
    title: "Bins to the curb",
    sticky: true,
    action: { label: "Done", service: "todo.update_item", target: { entity_id: "todo.household" } },
  },
  {
    id: "auto:morning",
    start: at(6, 40),
    kind: "automation",
    source: "House",
    title: "Morning · lights up, thermostat to 70°",
  },
  { id: "cal:standup", start: at(9, 0), kind: "calendar", source: "Google", title: "Standup" },
  { id: "cal:dentist", start: at(10, 30), kind: "calendar", source: "Google", title: "Dentist" },
  { id: "cal:lunch", start: at(12, 0), kind: "calendar", source: "Google", title: "Lunch with Dana" },
  {
    id: "todo:laundry",
    start: offset(-38),
    kind: "todo",
    source: "Tasks",
    title: "The washer is full — switch the laundry",
    sticky: true,
    priority: "high",
    action: {
      label: "I switched the laundry",
      service: "todo.update_item",
      target: { entity_id: "todo.household" },
      data: { item: "Switch the laundry", status: "completed" },
    },
  },
  {
    id: "evt:lr-lights",
    start: offset(-3),
    kind: "event",
    source: "House",
    title: "Living room lights turned off by motion sensor",
  },
  {
    id: "cal:kid-out",
    start: offset(64),
    kind: "calendar",
    source: "Google + CalDAV",
    title: "Kid out of school",
    automation: "Entry unlocks on her arrival",
    weather: { condition: "rainy", temperature: 63, precipitation_probability: 70 },
  },
  { id: "cal:pt", start: offset(80), kind: "calendar", source: "Google", title: "Physio",
    weather: { condition: "pouring", temperature: 61, precipitation_probability: 90 } },
  { id: "cal:groceries", start: offset(110), kind: "calendar", source: "Google", title: "Grocery pickup",
    weather: { condition: "partlycloudy", temperature: 66, precipitation_probability: 15 } },
  { id: "cal:call", start: offset(140), kind: "calendar", source: "Google", title: "Call with Marcus",
    weather: { condition: "sunny", temperature: 68, precipitation_probability: 0 } },
  { id: "cal:dinner", start: offset(170), kind: "calendar", source: "CalDAV", title: "Making dinner for house", automation: "Kitchen 90%, hallway 40%" },
  { id: "cal:soccer", start: offset(200), kind: "calendar", source: "Google", title: "Soccer practice pickup",
    weather: { condition: "windy", temperature: 59, precipitation_probability: 20 } },
  { id: "cal:book", start: offset(230), kind: "calendar", source: "Google", title: "Book club" },
  { id: "sun:set", start: at(19, 47), kind: "sun", source: "Sun", title: "Sunset", automation: "Evening lights over 20 minutes" },
  {
    id: "cal:bed",
    start: at(21, 0),
    kind: "calendar",
    source: "Google",
    title: "Kid bed time",
    automation: "Story on Sonos, 20 min, then dark",
    priority: "high",
    weather: { condition: "clear-night", temperature: 54, precipitation_probability: 0 },
  },
];

/**
 * The overlap cases: several things running at once, an event that started
 * yesterday and ends this morning, and one that starts today and runs past
 * midnight. Durations throughout.
 */
const endAfter = (startMins: number, lengthMins: number): string =>
  new Date(Date.now() + (startMins + lengthMins) * 60_000).toISOString();

const dayShift = (days: number, h: number, m = 0): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};

export const overlapping: SpineEntry[] = [
  // Started yesterday 11am, ends 8am today — no position on today's spine.
  {
    id: "cal:conference",
    start: dayShift(-1, 11, 0),
    end: at(8, 0),
    kind: "calendar",
    source: "Google",
    title: "Wife at the conference",
  },
  { id: "cal:standup", start: at(9, 0), end: at(9, 15), kind: "calendar", source: "Google", title: "Standup" },
  // Three things running at once, started at different times.
  {
    id: "cal:class",
    start: offset(-155),
    end: endAfter(-155, 330),
    kind: "calendar",
    source: "CalDAV",
    title: "Kid's art class",
    automation: "Porch light on when she is due back",
  },
  {
    id: "cal:slowcooker",
    start: offset(-95),
    end: endAfter(-95, 240),
    kind: "automation",
    source: "House",
    title: "Slow cooker running",
    automation: "Kitchen fan low until it finishes",
  },
  {
    id: "cal:call",
    start: offset(-22),
    end: endAfter(-22, 60),
    kind: "calendar",
    source: "Google",
    title: "Call with Marcus",
  },
  {
    id: "cal:dinner",
    start: offset(70),
    end: endAfter(70, 195),
    kind: "calendar",
    source: "CalDAV",
    title: "Making dinner for house",
    automation: "Kitchen 90%, hallway 40%",
    weather: { condition: "rainy", temperature: 61, precipitation_probability: 65 },
  },
  { id: "cal:quick", start: offset(120), end: endAfter(120, 30), kind: "calendar", source: "Google", title: "Vet call" },
  // Starts today, runs past midnight.
  {
    id: "cal:nightshift",
    start: at(22, 0),
    end: dayShift(1, 6, 30),
    kind: "calendar",
    source: "Google",
    title: "Wife night shift",
    priority: "high",
  },
];
