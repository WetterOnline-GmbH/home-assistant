from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WoHomeCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [WoHomeDisplaySwitch(entry.unique_id or entry.entry_id, data.coordinator)]
    )


class WoHomeDisplaySwitch(CoordinatorEntity[WoHomeCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Screen"

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_display"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        display = (self.coordinator.data or {}).get("display")
        if not isinstance(display, dict):
            return None
        value = display.get("is_on")
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.api.set_display(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.api.set_display(False)
        await self.coordinator.async_request_refresh()
