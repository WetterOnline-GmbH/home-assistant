from __future__ import annotations

from aiohttp import ClientError

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .coordinator import WoHomeCoordinator

PARALLEL_UPDATES = 1 # no parallel updates to avoid race conditions


async def async_setup_entry(
    hass: HomeAssistant, entry: WoHomeConfigEntry, async_add_entities
) -> None:
    data = entry.runtime_data
    device_id = entry.unique_id or entry.entry_id
    entities = [WoHomeDisplaySwitch(device_id, data.coordinator)]
    if data.coordinator.info.get("brightness_control") is True:
        entities.append(WoHomeAutoBrightnessSwitch(device_id, data.coordinator))
    async_add_entities(entities)


class WoHomeDisplaySwitch(CoordinatorEntity[WoHomeCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "display"

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
        try:
            await self.coordinator.api.set_display(True)
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(
                f"Could not turn on the WoHome display: {error}"
            ) from error
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.api.set_display(False)
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(
                f"Could not turn off the WoHome display: {error}"
            ) from error
        await self.coordinator.async_request_refresh()


class WoHomeAutoBrightnessSwitch(CoordinatorEntity[WoHomeCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "auto_brightness"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_auto_brightness"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        display = (self.coordinator.data or {}).get("display")
        if not isinstance(display, dict):
            return None
        value = display.get("auto_brightness")
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_enabled(False)

    async def _set_enabled(self, enabled: bool) -> None:
        try:
            await self.coordinator.api.set_auto_brightness(enabled)
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(
                f"Could not update WoHome automatic brightness: {error}"
            ) from error
        await self.coordinator.async_request_refresh()
