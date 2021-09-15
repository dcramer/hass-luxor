# Base component constants
NAME = "FXLuminaire Luxor"
DOMAIN = "luxor"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ISSUE_URL = "https://github.com/dcramer/hass-luxor/issues"

# Platforms
LIGHT = "light"
SCENE = "scene"
PLATFORMS = [LIGHT, SCENE]

# Configuration and options
CONF_HOST = "host"

# Defaults
DEFAULT_NAME = DOMAIN

# How long to wait to actually do the refresh after requesting it.
# We wait some time so if we control multiple lights, we batch requests.
REQUEST_REFRESH_DELAY = 0.3
