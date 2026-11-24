from __future__ import annotations

from aiohttp import ClientError
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .const import DOMAIN
from .coordinator import WoHomeCoordinator

PARALLEL_UPDATES = 1
MIN_DEVICE_BRIGHTNESS = 1
MAX_DEVICE_BRIGHTNESS = 255


async def async_setup_entry(hass: HomeAssistant, entry: WoHomeConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    if coordinator.info.get("brightness_control") is True:
        async_add_entities([WoHomeBrightness(entry.unique_id or entry.entry_id, coordinator)])


class WoHomeBrightness(CoordinatorEntity[WoHomeCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "brightness"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_brightness"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        display = (self.coordinator.data or {}).get("display")
        value = display.get("brightness") if isinstance(display, dict) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not MIN_DEVICE_BRIGHTNESS <= value <= MAX_DEVICE_BRIGHTNESS
        ):
            return None
        return round(value * 100 / MAX_DEVICE_BRIGHTNESS)

    async def async_set_native_value(self, value: float) -> None:
        try:
            brightness = round(value * MAX_DEVICE_BRIGHTNESS / 100)
            await self.coordinator.api.set_brightness(max(MIN_DEVICE_BRIGHTNESS, brightness))
        except (ClientError, TimeoutError, OSError) as error:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="device_action_failed") from error
        await self.coordinator.async_request_refresh()
