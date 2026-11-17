"""Gathers inputs, runs the model, and holds the mass estimate and nightly snapshot."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from . import model
from .const import (
    CONF_HORIZON_HOUR,
    CONF_INDOOR_ENTITY,
    CONF_MASS_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    PROMOTE_MINUTE,
    REFRESH_MINUTES,
    SNAPSHOT_MINUTE,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def make_store(hass: HomeAssistant, entry_id: str) -> Store:
    """Storage for the mass estimate and the nightly snapshot."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


@dataclass
class ForecastData:
    """One refresh of the live forecast."""

    computed_at: datetime
    horizon_end: datetime
    forecasts: dict  # scenario -> model.Forecast
    start_air: float = 0.0  # indoor temperature the forecast started from, F


class ForecastCoordinator(DataUpdateCoordinator[ForecastData]):
    """Refreshes the live forecast on the quarter hour."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None)
        self.entry = entry
        self.mass: float | None = None  # the integration's own lag estimate, unrounded
        # {"computed_at": iso, "curves": {scenario: [values]}} or None
        self.snapshot: dict | None = None
        self._store = make_store(hass, entry.entry_id)
        self._unsubs: list = []

    # --- settings -------------------------------------------------------

    @property
    def settings(self) -> dict:
        """Setup data overlaid with options, read fresh on every use."""
        return {**self.entry.data, **self.entry.options}

    @property
    def coefficients(self) -> model.Coefficients:
        return model.Coefficients.from_mapping(self.settings)

    @property
    def horizon_hour(self) -> int:
        return int(self.settings.get(CONF_HORIZON_HOUR, model.DEFAULT_HORIZON_HOUR))

    # --- lifecycle ------------------------------------------------------

    async def async_start(self) -> None:
        """Load stored state, start the timers, and do a first refresh."""
        stored = await self._store.async_load() or {}
        self.mass = stored.get("mass")
        self.snapshot = stored.get("snapshot")
        self._unsubs.append(async_track_time_change(
            self.hass, self._on_refresh_tick, minute=REFRESH_MINUTES, second=0))
        self._unsubs.append(async_track_time_change(
            self.hass, self._on_promote_tick, minute=PROMOTE_MINUTE, second=0))
        self._unsubs.append(async_track_time_change(
            self.hass, self._on_snapshot_tick, minute=SNAPSHOT_MINUTE, second=0))
        await self.async_refresh()

    @callback
    def async_stop(self) -> None:
        """Cancel the timers."""
        while self._unsubs:
            self._unsubs.pop()()

    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {"mass": self.mass, "snapshot": self.snapshot}, 1)

    # --- timers ---------------------------------------------------------

    async def _on_refresh_tick(self, now: datetime) -> None:
        if now.minute == 0:
            self._step_mass()
        await self.async_refresh()

    @callback
    def _on_promote_tick(self, now: datetime) -> None:
        self.async_update_listeners()

    async def _on_snapshot_tick(self, now: datetime) -> None:
        if dt_util.as_local(now).hour == self.horizon_hour:
            await self.async_take_snapshot()

    # --- inputs ---------------------------------------------------------

    def _read_temperature(self, entity_id: str | None) -> float | None:
        """Read a temperature sensor in degrees F, or None if it has no usable value."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return None
        try:
            value = float(state.state)
        except ValueError:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or UnitOfTemperature.FAHRENHEIT
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.FAHRENHEIT)

    def _step_mass(self) -> None:
        """Hourly update of the integration's own mass estimate."""
        air = self._read_temperature(self.settings.get(CONF_INDOOR_ENTITY))
        if air is None:
            return
        self.mass = air if self.mass is None else model.mass_step(self.mass, air, self.coefficients)
        self._save()
        self.async_update_listeners()

    async def _weather_hours(self) -> list:
        """Hourly forecast entries from the weather entity, as model.ForecastHour."""
        entity_id = self.settings[CONF_WEATHER_ENTITY]
        weather = self.hass.states.get(entity_id)
        unit = (weather.attributes.get("temperature_unit") if weather else None) \
            or self.hass.config.units.temperature_unit
        response = await self.hass.services.async_call(
            "weather", "get_forecasts", {"entity_id": entity_id, "type": "hourly"},
            blocking=True, return_response=True)
        hours = []
        for item in (response or {}).get(entity_id, {}).get("forecast") or []:
            when = dt_util.parse_datetime(str(item.get("datetime")))
            if when is None or item.get("temperature") is None:
                continue
            hours.append(model.ForecastHour(
                temperature=TemperatureConverter.convert(
                    float(item["temperature"]), unit, UnitOfTemperature.FAHRENHEIT),
                cloud=float(item.get("cloud_coverage") or 0) / 100,
                uv_index=float(item.get("uv_index") or 0),
                hour_of_day=dt_util.as_local(when).hour,
            ))
        return hours

    # --- forecast -------------------------------------------------------

    async def _compute(self) -> ForecastData:
        settings = self.settings
        air = self._read_temperature(settings.get(CONF_INDOOR_ENTITY))
        if air is None:
            raise UpdateFailed(f"{settings.get(CONF_INDOOR_ENTITY)} has no numeric state")
        if self.mass is None:
            self.mass = air  # seed the lag estimate the first time there is a reading
            self._save()
        mass = self.mass
        if settings.get(CONF_MASS_ENTITY):
            mass = self._read_temperature(settings[CONF_MASS_ENTITY])
            if mass is None:
                raise UpdateFailed(f"{settings[CONF_MASS_ENTITY]} has no numeric state")

        now = dt_util.now()
        horizon_end, steps = model.horizon(now, self.horizon_hour)
        try:
            hours = (await self._weather_hours())[:steps]
        except Exception as err:  # noqa: BLE001 - any service failure means no forecast
            raise UpdateFailed(f"weather forecast failed: {err}") from err
        if not hours:
            raise UpdateFailed("weather entity returned no hourly forecast")

        coefficients = self.coefficients
        return ForecastData(
            computed_at=now,
            horizon_end=horizon_end,
            forecasts={s: model.forecast(s, air, mass, hours, coefficients)
                       for s in model.SCENARIOS},
            start_air=air,
        )

    async def _async_update_data(self) -> ForecastData:
        return await self._compute()

    async def async_take_snapshot(self) -> None:
        """Freeze the full curve to the next horizon. The previous one is kept on failure."""
        try:
            data = await self._compute()
        except UpdateFailed as err:
            _LOGGER.warning("Nightly snapshot skipped: %s", err)
            return
        self.snapshot = {
            "computed_at": data.computed_at.isoformat(),
            "start": round(data.start_air, 1),
            "curves": {s: f.hourly for s, f in data.forecasts.items()},
        }
        self._save()
        self.async_update_listeners()

    def snapshot_value_now(self, scenario: str) -> float | None:
        """The frozen curve's value for the current hour.

        Until the first promotion (one minute past the next hour) this is the indoor
        temperature the curve started from; each promotion then moves one value along.
        """
        if not self.snapshot:
            return None
        curve = self.snapshot["curves"].get(scenario)
        computed_at = dt_util.parse_datetime(self.snapshot["computed_at"])
        if not curve or computed_at is None:
            return None
        first_promotion = computed_at.replace(minute=PROMOTE_MINUTE, second=0, microsecond=0)
        if first_promotion <= computed_at:
            first_promotion += timedelta(hours=1)
        promotions = int((dt_util.now() - first_promotion).total_seconds() // 3600) + 1
        if promotions <= 0:
            return self.snapshot.get("start", curve[0])
        return curve[min(len(curve), promotions) - 1]
