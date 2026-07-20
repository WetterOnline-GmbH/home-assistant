"""Weather platform for the WetterOnline Weather integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WetterOnlineConfigEntry
from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WetterOnlineCoordinator

PARALLEL_UPDATES = 0

# TODO(api): complete the WetterOnline condition-code → HA condition mapping.
# The placeholder codes below are stand-ins until the real API documents its
# full set of condition codes. HA's allowed `condition` values are the
# constants in homeassistant.components.weather.const (ATTR_CONDITION_*).
CONDITION_MAP: dict[str, str] = {
    "1": "sunny",
    "2": "partlycloudy",
    "3": "cloudy",
    "4": "rainy",
    "5": "snowy",
    "6": "lightning-rainy",
    "7": "fog",
}


def _map_condition(code: Any) -> str | None:
    """Map a WetterOnline condition code to an HA condition string."""
    if code is None:
        return None
    return CONDITION_MAP.get(str(code))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WetterOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities([WetterOnlineWeatherEntity(data.coordinator)])


class WetterOnlineWeatherEntity(
    CoordinatorEntity[WetterOnlineCoordinator], WeatherEntity
):
    """Representation of WetterOnline weather data for one location."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(self, coordinator: WetterOnlineCoordinator) -> None:
        super().__init__(coordinator)
        location = coordinator.location
        self._attr_unique_id = location.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location.id)},
            name=location.label,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_temperature(self) -> float | None:
        return self.coordinator.data.current.get("temperature")

    @property
    def humidity(self) -> float | None:
        return self.coordinator.data.current.get("humidity")

    @property
    def native_pressure(self) -> float | None:
        return self.coordinator.data.current.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        return self.coordinator.data.current.get("wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        return self.coordinator.data.current.get("wind_bearing")

    @property
    def condition(self) -> str | None:
        return _map_condition(self.coordinator.data.current.get("condition_code"))

    async def async_forecast_daily(self) -> list[Forecast] | None:
        return [
            Forecast(
                datetime=day["datetime"],
                native_temperature=day.get("temperature"),
                native_templow=day.get("templow"),
                condition=_map_condition(day.get("condition_code")),
            )
            for day in self.coordinator.data.daily
        ]

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        return [
            Forecast(
                datetime=hour["datetime"],
                native_temperature=hour.get("temperature"),
                condition=_map_condition(hour.get("condition_code")),
            )
            for hour in self.coordinator.data.hourly
        ]
