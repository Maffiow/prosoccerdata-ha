"""Constants for the ProSoccerData integration."""

DOMAIN = "prosoccerdata"

APP_URL = "https://app.prosoccerdata.com"
API_URL = "https://psd.prosoccerdata.com"

LOGIN_URL = f"{API_URL}/api/v2/login/oauth/token"
POSSIBLE_USERS_URL = f"{API_URL}/api/v2/central-users/current/possible-users"
# The API uses a custom header name instead of Authorization: Bearer
CENTRAL_TOKEN_HEADER = "central-token"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PLAYERS = "players"
CONF_PLAYER_IDS = "player_ids"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"

DEFAULT_SCAN_INTERVAL_MINUTES = 30
MIN_SCAN_INTERVAL_MINUTES = 5
MAX_SCAN_INTERVAL_MINUTES = 1440

# Used when Home Assistant has no language or time zone configured.
DEFAULT_LANGUAGE = "nl"
DEFAULT_TIME_ZONE = "Europe/Brussels"

# How many matches/messages the API is asked for per refresh.
MATCH_FETCH_COUNT = 20
PAYMENT_FETCH_COUNT = 10
MESSAGE_FETCH_COUNT = 30

# How many items end up in list-style state attributes. Every attribute is
# written to the recorder on each update, so these stay deliberately small.
MATCH_ATTRIBUTE_LIMIT = 10
MESSAGE_ATTRIBUTE_LIMIT = 15

ATTR_TEAM = "team"
ATTR_OPPONENT = "opponent"
ATTR_SCORE = "score"
ATTR_HOME_AWAY = "home_away"
ATTR_COMPETITION = "competition"
ATTR_LOCATION = "location"
ATTR_MEETING_HOUR = "meeting_hour"
ATTR_RECENT_MATCHES = "recent_matches"
ATTR_MATCH_START = "match_start"
ATTR_MATCH_END = "match_end"
ATTR_ATTENDANCE = "attendance_state"
