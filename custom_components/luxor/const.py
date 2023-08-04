# Base component constants
NAME = "FXLuminaire Luxor"
DOMAIN = "luxor"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.2"
ISSUE_URL = "https://github.com/dcramer/hass-luxor/issues"

# Platforms
LIGHT = "light"
SCENE = "scene"
PLATFORMS = [LIGHT, SCENE]

# Configuration and options
CONF_HOST = "host"
CONF_GROUP_INTERVAL = "group_interval"
CONF_THEME_INTERVAL = "theme_interval"

# Defaults
DEFAULT_NAME = DOMAIN
DEFAULT_GROUP_INTERVAL = 60
DEFAULT_THEME_INTERVAL = 600

# How long to wait to actually do the refresh after requesting it.
# We wait some time so if we control multiple lights, we batch requests.
REQUEST_REFRESH_DELAY = 0.3
