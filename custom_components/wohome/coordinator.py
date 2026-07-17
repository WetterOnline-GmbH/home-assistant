from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WoHomeApi
from .const import (
    API_VERSION,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    UPDATE_INTERVAL,
)

LOGGER = logging.getLogger(__name__)


class WoHomeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: WoHomeApi
    ) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.api = api
        self.entry = entry
        self.info: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        self.info = await self.api.get_info()
        if self.info.get("api_version") != API_VERSION:
            raise ConfigEntryError("Unsupported WoHome API version")

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_state()
        except Exception as error:
            raise UpdateFailed(str(error)) from error

    @property
    def device_info(self) -> DeviceInfo:
        device_id = self.entry.unique_id or self.entry.entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self.info.get(
                "name", self.entry.data.get(CONF_NAME, DEFAULT_NAME)
            ),
            manufacturer=self.info.get("manufacturer", MANUFACTURER),
            model=self.info.get("model", MODEL),
            sw_version=self.info.get("software_version"),
        )
