"""Sensors: live forecasts, the nightly snapshot, and the thermal-mass estimate."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import model
from .const import DOMAIN
from .coordinator import ForecastCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ForecastCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [MassSensor(coordinator)]
    for scenario in model.SCENARIOS:
        entities += [
            LiveForecastSensor(coordinator, scenario),
            SnapshotCurveSensor(coordinator, scenario),
            SnapshotHorizonSensor(coordinator, scenario),
        ]
    async_add_entities(entities)


class _Base(CoordinatorEntity[ForecastCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: ForecastCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )


class LiveForecastSensor(_Base):
    """State is the curve's peak; `hourly_forecast` ends with the horizon value."""

    def __init__(self, coordinator: ForecastCoordinator, scenario: str) -> None:
        super().__init__(coordinator, f"live_{scenario}")
        self._scenario = scenario

    @property
    def native_value(self) -> float:
        return self.coordinator.data.forecasts[self._scenario].peak

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        return {
            "hourly_forecast": data.forecasts[self._scenario].hourly,
            "computed_at": data.computed_at.isoformat(),
            "horizon_end": data.horizon_end.isoformat(),
        }


class _SnapshotBase(_Base):
    """Snapshot sensors stay available while the live forecast is failing."""

    def __init__(self, coordinator: ForecastCoordinator, key: str, scenario: str) -> None:
        super().__init__(coordinator, key)
        self._scenario = scenario

    @property
    def _curve(self) -> list | None:
        snapshot = self.coordinator.snapshot
        return snapshot["curves"].get(self._scenario) if snapshot else None

    @property
    def available(self) -> bool:
        return bool(self._curve)


class SnapshotCurveSensor(_SnapshotBase):
    """The curve frozen at the last nightly snapshot; state is its value for the current hour."""

    def __init__(self, coordinator: ForecastCoordinator, scenario: str) -> None:
        super().__init__(coordinator, f"snapshot_curve_{scenario}", scenario)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.snapshot_value_now(self._scenario)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "hourly_forecast": self._curve,
            "computed_at": self.coordinator.snapshot["computed_at"],
        }


class SnapshotHorizonSensor(_SnapshotBase):
    """The horizon (9pm) value of the last nightly snapshot."""

    def __init__(self, coordinator: ForecastCoordinator, scenario: str) -> None:
        super().__init__(coordinator, f"snapshot_horizon_{scenario}", scenario)

    @property
    def native_value(self) -> float | None:
        return self._curve[-1]


class MassSensor(_Base):
    """The integration's own thermal-mass lag estimate, updated hourly."""

    def __init__(self, coordinator: ForecastCoordinator) -> None:
        super().__init__(coordinator, "thermal_mass")

    @property
    def available(self) -> bool:
        return self.coordinator.mass is not None

    @property
    def native_value(self) -> float:
        return round(self.coordinator.mass, 1)
