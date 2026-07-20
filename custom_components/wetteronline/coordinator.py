"""DataUpdateCoordinator for the WetterOnline Weather integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Location,
    WeatherData,
    WetterOnlineApiClient,
    WetterOnlineAuthError,
    WetterOnlineConnectionError,
    WetterOnlineError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__name__)


class WetterOnlineCoordinator(DataUpdateCoordinator[WeatherData]):
    """Coordinator that polls the WetterOnline API for a single location."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: WetterOnlineApiClient,
        location: Location,
    ) -> None:
        update_interval = entry.options.get(CONF_SCAN_INTERVAL)
        if update_interval is None:
            update_interval = DEFAULT_SCAN_INTERVAL
        elif not isinstance(update_interval, timedelta):
            update_interval = timedelta(seconds=update_interval)

        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=update_interval,
            always_update=False,
        )
        self.client = client
        self.location = location

    async def _async_update_data(self) -> WeatherData:
        try:
            return await self.client.async_get_weather(self.location)
        except WetterOnlineAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except (WetterOnlineConnectionError, WetterOnlineError) as error:
            raise UpdateFailed(str(error)) from error
