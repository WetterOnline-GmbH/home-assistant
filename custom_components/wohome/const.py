from datetime import timedelta

DOMAIN = "wohome"
DEFAULT_NAME = "wetteronline home"
DEFAULT_PORT = 8080
UPDATE_INTERVAL = timedelta(seconds=60)

API_VERSION = 2
API_PATH = "/api/v2"

CONF_NAME = "name"
CONF_PORT = "port"
CONF_DASHBOARD_PATH = "dashboard_path"
CONF_DASHBOARD_MODE = "dashboard_mode"
MANUAL_DASHBOARD = "manual"

DEFAULT_DASHBOARD_PATH = "/lovelace"

MANUFACTURER = "WetterOnline"
MODEL = "WOH4"
