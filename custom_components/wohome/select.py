from __future__ import annotations

from aiohttp import ClientError

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .const import CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH
from .coordinator import WoHomeCoordinator
from .dashboard import DashboardOption, dashboard_options, dashboard_url

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WoHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [
            WoHomeDashboardSelect(
                hass,
                entry,
                data.coordinator,
            )
        ]
    )


class WoHomeDashboardSelect(CoordinatorEntity[WoHomeCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "dashboard"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:view-dashboard"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WoHomeConfigEntry,
        coordinator: WoHomeCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.unique_id or entry.entry_id}_dashboard"
        )
        self._attr_device_info = coordinator.device_info

    @property
    def options(self) -> list[str]:
        return [option.label for option in self._dashboard_options]

    @property
    def current_option(self) -> str | None:
        current_path = self._current_path
        return next(
            (
                option.label
                for option in self._dashboard_options
                if option.path == current_path
            ),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        selected = next(
            (
                dashboard
                for dashboard in self._dashboard_options
                if dashboard.label == option
            ),
            None,
        )
        if selected is None:
            raise ValueError(f"Unknown dashboard: {option}")

        try:
            url = dashboard_url(self._hass, selected.path)
            await self.coordinator.api.set_dashboard(url)
        except (ClientError, TimeoutError, OSError, NoURLAvailableError) as error:
            raise HomeAssistantError(
                f"Could not set WoHome dashboard to {selected.label}: {error}"
            ) from error

        self._hass.config_entries.async_update_entry(
            self._entry,
            options={
                **self._entry.options,
                CONF_DASHBOARD_PATH: selected.path,
            },
        )
        self.async_write_ha_state()

    @property
    def _dashboard_options(self) -> list[DashboardOption]:
        return dashboard_options(self._hass)

    @property
    def _current_path(self) -> str:
        return self._entry.options.get(
            CONF_DASHBOARD_PATH,
            self._entry.data.get(
                CONF_DASHBOARD_PATH,
                DEFAULT_DASHBOARD_PATH,
            ),
        )
