"""Constants for the WetterOnline Weather integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "wetteronline"
DEFAULT_NAME = "WetterOnline Weather"

CONF_LOCATION_ID = "location_id"
CONF_LOCATION_LABEL = "location_label"
CONF_ACCOUNT_TIER = "account_tier"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

ATTRIBUTION = "Weather data provided by WetterOnline"
MANUFACTURER = "WetterOnline"
