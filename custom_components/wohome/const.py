from datetime import timedelta

DOMAIN = "wohome"
DEFAULT_NAME = "WetterOnline Home"
DEFAULT_PORT = 8080
UPDATE_INTERVAL = timedelta(seconds=60)

API_VERSION = 1
API_PATH = "/api/v1"

CONF_NAME = "name"
CONF_PORT = "port"
CONF_DASHBOARD_PATH = "dashboard_path"

DEFAULT_DASHBOARD_PATH = "/lovelace"

MANUFACTURER = "WetterOnline"
MODEL = "WOH4"
