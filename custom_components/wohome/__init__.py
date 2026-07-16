from __future__ import annotations

from dataclasses import dataclass
from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError

from .api import WoHomeApi
from .const import (
    CONF_DASHBOARD_PATH,
    CONF_PORT,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import WoHomeCoordinator
from .dashboard import dashboard_url

PLATFORMS = [Platform.SWITCH, Platform.SENSOR, Platform.SELECT]


@dataclass
class WoHomeData:
    api: WoHomeApi
    coordinator: WoHomeCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = WoHomeApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = WoHomeCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    device_name = coordinator.info.get("name")
    if isinstance(device_name, str) and device_name:
        hass.config_entries.async_update_entry(
            entry,
            title=device_name,
            data={**entry.data, CONF_NAME: device_name},
        )
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)}
        )
        if device is not None and device.name_by_user is None:
            device_registry.async_update_device(device.id, name=device_name)

    dashboard_path = entry.options.get(
        CONF_DASHBOARD_PATH,
        entry.data.get(CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH),
    )
    try:
        await api.set_dashboard(dashboard_url(hass, dashboard_path))
    except (ClientError, NoURLAvailableError, OSError, ValueError) as error:
        raise ConfigEntryNotReady(
            "Could not transfer the Home Assistant dashboard to WoHome"
        ) from error

    entry.runtime_data = WoHomeData(api=api, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
