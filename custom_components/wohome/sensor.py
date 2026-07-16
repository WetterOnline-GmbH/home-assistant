from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WoHomeCoordinator


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
    ),
    WoHomeSensorDescription(
        key="humidity",
        translation_key="humidity",
        state_key="humidity_percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    WoHomeSensorDescription(
        key="illuminance",
        translation_key="illuminance",
        state_key="illuminance_lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    data = entry.runtime_data
    device_id = entry.unique_id or entry.entry_id
    async_add_entities(
        WoHomeSensor(device_id, data.coordinator, description)
        for description in SENSORS
    )


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
        return sensors.get(self.entity_description.state_key)
