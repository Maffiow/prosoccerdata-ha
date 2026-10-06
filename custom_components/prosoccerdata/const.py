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
MATCH_FETCH_COUNT = 40
PAYMENT_FETCH_COUNT = 10
MESSAGE_FETCH_COUNT = 30

# Rolling window the coordinator keeps for the calendar and the next-event
# sensors. The calendar panel asks for its own range on top of this.
SCHEDULE_PAST_DAYS = 1
SCHEDULE_FUTURE_DAYS = 30

# ProSoccerData event types, as used by its own web client.
EVENT_TYPE_GAME = "game"
EVENT_TYPE_TRAINING = "training"
EVENT_TYPE_OTHER = "other"

# How many items end up in list-style state attributes. Every attribute is
# written to the recorder on each update, so these stay deliberately small.
MATCH_ATTRIBUTE_LIMIT = 10
MESSAGE_ATTRIBUTE_LIMIT = 15
# Competition matches of the current season (home and return legs). Kept out
# of the recorder, like the other list attributes on the last-match sensor.
SEASON_MATCH_ATTRIBUTE_LIMIT = 40
# Belgian youth seasons start in July.
SEASON_START_MONTH = 7
# Cap on an opened message's body, so one long mail cannot bloat the state.
MESSAGE_BODY_LIMIT = 8000
# Upcoming events listed on the Upcoming Events sensor (about a month).
UPCOMING_EVENT_ATTRIBUTE_LIMIT = 40

ATTR_TEAM = "team"
ATTR_OPPONENT = "opponent"
ATTR_SCORE = "score"
ATTR_HOME_AWAY = "home_away"
ATTR_COMPETITION = "competition"
ATTR_LOCATION = "location"
ATTR_MEETING_HOUR = "meeting_hour"
ATTR_RECENT_MATCHES = "recent_matches"
ATTR_SEASON_MATCHES = "season_matches"
ATTR_MATCH_START = "match_start"
ATTR_MATCH_END = "match_end"
ATTR_ATTENDANCE = "attendance_state"
ATTR_EVENT_TYPE = "event_type"
ATTR_TITLE = "title"
