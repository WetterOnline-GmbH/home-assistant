"""The WetterOnline Weather integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Location, WetterOnlineApiClient
from .const import CONF_LOCATION_ID, CONF_LOCATION_LABEL
from .coordinator import WetterOnlineCoordinator

PLATFORMS = [Platform.WEATHER]


@dataclass
class WetterOnlineData:
    client: WetterOnlineApiClient
    coordinator: WetterOnlineCoordinator


type WetterOnlineConfigEntry = ConfigEntry[WetterOnlineData]


async def async_setup_entry(hass: HomeAssistant, entry: WetterOnlineConfigEntry) -> bool:
    client = WetterOnlineApiClient(
        async_get_clientsession(hass), entry.data[CONF_API_KEY]
    )
    location = Location(
        id=entry.data[CONF_LOCATION_ID],
        lat=entry.data[CONF_LATITUDE],
        lon=entry.data[CONF_LONGITUDE],
        label=entry.data[CONF_LOCATION_LABEL],
    )
    coordinator = WetterOnlineCoordinator(hass, entry, client, location)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WetterOnlineData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WetterOnlineConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
