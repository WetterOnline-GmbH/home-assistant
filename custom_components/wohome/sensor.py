from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, LIGHT_LUX, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WoHomeConfigEntry
from .coordinator import WoHomeCoordinator

PARALLEL_UPDATES = 0 # allow parallel updates for sensors since they are read-only and do not cause race conditions


@dataclass(frozen=True, kw_only=True)
class WoHomeSensorDescription(SensorEntityDescription):
    state_key: str


SENSORS = (
    WoHomeSensorDescription(
        key="temperature",
        translation_key="temperature",
        state_key="temperature_celsius",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    WoHomeSensorDescription(
        key="humidity",
        translation_key="humidity",
        state_key="humidity_percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    WoHomeSensorDescription(
        key="illuminance",
        translation_key="illuminance",
        state_key="illuminance_lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: WoHomeConfigEntry, async_add_entities
) -> None:
    data = entry.runtime_data
    device_id = entry.unique_id or entry.entry_id
    entities = [
        WoHomeSensor(device_id, data.coordinator, description)
        for description in SENSORS
    ]
    if data.coordinator.info.get("display_rules_control") is True:
        entities.append(WoHomeDisplayRules(device_id, data.coordinator))
    async_add_entities(entities)


class WoHomeSensor(CoordinatorEntity[WoHomeCoordinator], SensorEntity):
    entity_description: WoHomeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        coordinator: WoHomeCoordinator,
        description: WoHomeSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        sensors = (self.coordinator.data or {}).get("sensors")
        if not isinstance(sensors, dict):
            return None
        value = sensors.get(self.entity_description.state_key)
        # Round to the display precision so tiny fluctuations on every refresh
        # don't register as state changes and bloat the recorder database.
        precision = self.entity_description.suggested_display_precision
        if precision is not None and isinstance(value, (int, float)):
            return round(value, precision)
        return value


class WoHomeDisplayRules(CoordinatorEntity[WoHomeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "display_rules"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = None

    def __init__(self, device_id: str, coordinator: WoHomeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_display_rules"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        rules = (self.coordinator.data or {}).get("display_rules")
        return len(rules) if isinstance(rules, list) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"rules": (self.coordinator.data or {}).get("display_rules")}
