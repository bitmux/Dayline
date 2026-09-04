"""Constants and option keys for the Day Spine integration."""

from __future__ import annotations

DOMAIN = "day_spine"

# --- config entry data (set once, at setup) ---------------------------------
CONF_CALENDARS = "calendars"
CONF_WEATHER = "weather_entity"
CONF_TODO = "todo_entity"

# --- options (editable afterwards, in the UI) -------------------------------
OPT_CALENDAR_META = "calendar_meta"  # {entity_id: {label, priority, role}}
OPT_SENTENCES = "sentences"  # [{match, automation, priority, sticky}]
OPT_EXCLUDE = "exclude"  # [str]
OPT_SHOW_SUN = "show_sun"
OPT_SUN_PRIORITY = "sun_priority"
OPT_SIMILARITY = "similarity"
OPT_TITLE_NOISE = "title_noise"
OPT_RECENT = "recent"  # [{entity_id, state, phrase}]
OPT_RECENT_TTL = "recent_ttl"
OPT_RECENT_MAX = "recent_max"
OPT_NOW_TEMPLATE = "now_template"
OPT_HEADLINE_TEMPLATE = "headline_template"
OPT_SCAN_MINUTES = "scan_minutes"

# --- labels, applied in Home Assistant's own UI rather than chosen here ------
# `Dayline` on a calendar puts it on the spine; on anything else it makes that
# entity's automatic changes worth explaining. `Dayline Control` is the second,
# narrower permission: this calendar's `#tags` may act on the house.
LABEL_INCLUDE = "Dayline"
LABEL_CONTROL = "Dayline Control"

# --- the tag primitive -------------------------------------------------------
# Fired when a tagged event starts, and that is the entire integration point.
# The binding from tag to script lives in an ordinary automation, which is Home
# Assistant's job and not ours.
EVENT_TAG = "dayline_tag"

# --- services ----------------------------------------------------------------
# The way in for anything Dayline has no opinion about. An automation that has
# already decided something is worth saying can put a row on the spine itself,
# with up to two buttons, without that shape having to be predicted here first.
SERVICE_SHOW = "show"
SERVICE_DISMISS = "dismiss"

# How a pushed row carries itself. `normal` is the default and looks like the
# rest of the card; the other two are for rows that are not simply another
# thing on the list. Two, not a scale — every extra level costs the reader a
# distinction to learn, and "is this a problem" is the only one that reliably
# earns its keep.
LEVELS = ["normal", "info", "alert"]

PRIORITIES = ["high", "normal", "low"]
ROLES = ["people", "schedule"]

# --- calendar colours --------------------------------------------------------
# Colour answers *who*, now that the spine already answers what and when.
#
# A fixed vocabulary rather than a colour wheel, and names rather than hex, for
# three reasons. The card resolves a name to a value it has already checked
# against both the Organic palette and a Home Assistant theme, light or dark —
# a green picked against Thunderbird's white background has no obligation to be
# legible on either. Hues near the card's own two meanings are left out
# entirely: terracotta already means *now* and sage already means *the house
# acting on its own*, and a calendar that borrowed either would be lying.
# And a name survives a re-theme; a hex does not.
CALENDAR_COLORS = [
    "default",
    "blue",
    "cyan",
    "teal",
    "green",
    "violet",
    "magenta",
    "rose",
]

DEFAULT_SIMILARITY = 0.8
DEFAULT_TITLE_NOISE = [
    "a",
    "an",
    "the",
    "at",
    "to",
    "for",
    "with",
    "and",
    "of",
    "appointment",
]
DEFAULT_RECENT_TTL = 300
DEFAULT_RECENT_MAX = 6
DEFAULT_SCAN_MINUTES = 5

# Left empty rather than guessed at. A wrong sentence about the house is worse
# than no sentence: the card's whole promise is that what it says is true.
DEFAULT_NOW_TEMPLATE = ""
DEFAULT_HEADLINE_TEMPLATE = ""
