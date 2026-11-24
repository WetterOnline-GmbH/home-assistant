from __future__ import annotations

from aiohttp import ClientError

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .const import CONF_DASHBOARD_MODE, CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH, DOMAIN, MANUAL_DASHBOARD
from .coordinator import WoHomeCoordinator
from .dashboard import dashboard_url

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WoHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([WoHomeDashboardText(hass, entry, entry.runtime_data.coordinator)])


class WoHomeDashboardText(CoordinatorEntity[WoHomeCoordinator], TextEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "dashboard_url"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 255

    def __init__(self, hass: HomeAssistant, entry: WoHomeConfigEntry, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_dashboard_url"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str:
        return self._entry.options.get(
            CONF_DASHBOARD_PATH,
            self._entry.data.get(CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH),
        )

    async def async_set_value(self, value: str) -> None:
        if self._entry.options.get(CONF_DASHBOARD_MODE) != MANUAL_DASHBOARD:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="manual_dashboard_required")

        path = value.strip()
        try:
            if not path:
                raise ValueError("Empty dashboard URL")
            url = dashboard_url(self._hass, path)
        except ValueError as error:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="invalid_dashboard_url") from error
        except NoURLAvailableError as error:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="dashboard_failed") from error

        try:
            await self.coordinator.api.set_dashboard(url)
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="dashboard_failed") from error

        self._hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_DASHBOARD_PATH: path},
        )
        self.coordinator.async_update_listeners()
