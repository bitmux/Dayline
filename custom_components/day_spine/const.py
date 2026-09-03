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

PRIORITIES = ["high", "normal", "low"]
ROLES = ["people", "schedule"]

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
