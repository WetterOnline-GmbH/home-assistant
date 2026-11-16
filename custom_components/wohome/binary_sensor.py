from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .coordinator import WoHomeCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: WoHomeConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    if coordinator.info.get("display_rules_control") is True:
        async_add_entities([WoHomeScheduledOn(entry.unique_id or entry.entry_id, coordinator)])


class WoHomeScheduledOn(CoordinatorEntity[WoHomeCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "scheduled_on"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_scheduled_on"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        value = (self.coordinator.data or {}).get("scheduled_on")
        return value if isinstance(value, bool) else None
