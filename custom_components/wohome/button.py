from __future__ import annotations

from aiohttp import ClientError
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .coordinator import WoHomeCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: WoHomeConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    if coordinator.info.get("brightness_control") is True and coordinator.info.get("auto_brightness_control") is not True:
        async_add_entities([WoHomeRestoreBrightness(entry.unique_id or entry.entry_id, coordinator)])


class WoHomeRestoreBrightness(CoordinatorEntity[WoHomeCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "restore_brightness"

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_restore_brightness"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.set_brightness(None)
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(f"Could not restore WoHome brightness: {error}") from error
        await self.coordinator.async_request_refresh()
