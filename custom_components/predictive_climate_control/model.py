"""The indoor temperature forecast model.

This module is pure Python and must not import Home Assistant, so backtests
and tests can call it directly. The formula is documented in docs/model.md.
All temperatures are in degrees Fahrenheit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import datetime, timedelta

CLOSED = "closed"
SKYLIGHTS_OPEN = "skylights_open"
SKYLIGHTS_AND_WINDOWS = "skylights_and_windows"
SKYLIGHTS_WINDOWS_FAN = "skylights_windows_fan"
SCENARIOS = (CLOSED, SKYLIGHTS_OPEN, SKYLIGHTS_AND_WINDOWS, SKYLIGHTS_WINDOWS_FAN)

DEFAULT_HORIZON_HOUR = 21
MIN_STEPS = 1
MAX_STEPS = 24


@dataclass(frozen=True)
class Coefficients:
    """Every number in the formula. Defaults are the values deployed in November 2026."""

    # Outdoor coupling per hour with the house closed.
    alpha_outdoor: float = 0.05
    # Pull of the air toward the mass estimate, and of the mass toward the air, per hour.
    alpha_mass_to_air: float = 0.05
    alpha_air_to_mass: float = 0.10
    # Solar gain: the larger of uv_coeff * uv * (1 - cloud) and a triangular floor.
    uv_coeff: float = 0.13
    solar_floor: float = 0.7
    solar_center_hour: float = 11
    solar_half_width_hours: float = 6
    # Venting scales linearly up to this indoor-minus-outdoor difference.
    vent_full_delta: float = 15
    # Extra outdoor coupling at full venting.
    skylight_vent_alpha: float = 0.005
    window_vent_alpha: float = 0.01
    # Fan: fan_alpha = fan_alpha_min + min(power, fan_power_max) / fan_power_max * fan_alpha_span,
    # and the fan scenario adds (fan_alpha - fan_alpha_reference) to the window scenario.
    fan_alpha_min: float = 0.04
    fan_alpha_span: float = 0.10
    fan_alpha_reference: float = 0.05
    fan_power_max: float = 53
    fan_power_warm: float = 42
    fan_power_cool: float = 36
    # The fan is assumed to run at fan_power_warm when the starting indoor
    # temperature is above this, otherwise at fan_power_cool.
    fan_warm_threshold: float = 73

    @classmethod
    def from_mapping(cls, values) -> "Coefficients":
        """Build from a dict, ignoring unknown keys and falling back to defaults."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: float(v) for k, v in values.items() if k in known and v is not None})


@dataclass(frozen=True)
class ForecastHour:
    """One hourly weather forecast entry."""

    temperature: float  # outdoor, degrees F
    cloud: float  # cloud cover as a fraction, 0-1
    uv_index: float
    hour_of_day: int  # local hour of the entry


@dataclass(frozen=True)
class Forecast:
    """A forecast curve in the form the sensors expose."""

    peak: float  # highest value of the curve, one decimal
    hourly: list  # one value per step, one decimal; the last is the horizon value


def fan_alpha(start_air: float, c: Coefficients) -> float:
    """Outdoor coupling of the window fan, from its assumed power draw."""
    power = c.fan_power_warm if start_air > c.fan_warm_threshold else c.fan_power_cool
    return c.fan_alpha_min + (min(power, c.fan_power_max) / c.fan_power_max) * c.fan_alpha_span


def outdoor_alpha(scenario: str, vent: float, start_air: float, c: Coefficients) -> float:
    """Outdoor coupling for one step under `scenario`."""
    if scenario == CLOSED:
        return c.alpha_outdoor
    if scenario == SKYLIGHTS_OPEN:
        return c.alpha_outdoor + c.skylight_vent_alpha * vent
    if scenario == SKYLIGHTS_AND_WINDOWS:
        return c.alpha_outdoor + c.window_vent_alpha * vent
    if scenario == SKYLIGHTS_WINDOWS_FAN:
        return (c.alpha_outdoor + c.window_vent_alpha * vent
                + (fan_alpha(start_air, c) - c.fan_alpha_reference))
    raise ValueError(f"unknown scenario: {scenario}")


def solar_gain(hour: ForecastHour, c: Coefficients) -> float:
    """Solar gain in degrees F for one step."""
    from_uv = c.uv_coeff * hour.uv_index * (1 - hour.cloud)
    floor = c.solar_floor * max(
        0, 1 - abs(hour.hour_of_day - c.solar_center_hour) / c.solar_half_width_hours)
    return max(from_uv, floor)


def simulate(scenario: str, air: float, mass: float, hours, c: Coefficients | None = None) -> list:
    """Step the model once per forecast hour. Returns the unrounded air temperature after each step."""
    c = c or Coefficients()
    start_air = air
    curve = []
    for hour in hours:
        vent = min(max(0, air - hour.temperature) / c.vent_full_delta, 1)
        alpha = outdoor_alpha(scenario, vent, start_air, c)
        new_air = (air + alpha * (hour.temperature - air)
                   + c.alpha_mass_to_air * (mass - air) + solar_gain(hour, c))
        mass = mass + c.alpha_air_to_mass * (air - mass)
        air = new_air
        curve.append(air)
    return curve


def forecast(scenario: str, air: float, mass: float, hours, c: Coefficients | None = None) -> Forecast:
    """Run `simulate` and round to the sensor output contract. `hours` must not be empty."""
    curve = simulate(scenario, air, mass, hours, c)
    if not curve:
        raise ValueError("no forecast hours to step")
    return Forecast(peak=round(max(curve), 1), hourly=[round(v, 1) for v in curve])


def mass_step(mass: float, air: float, c: Coefficients | None = None) -> float:
    """Hourly update of the thermal-mass lag estimate."""
    c = c or Coefficients()
    return mass + c.alpha_air_to_mass * (air - mass)


def horizon(now: datetime, horizon_hour: int = DEFAULT_HORIZON_HOUR):
    """Return (horizon_end, n): the next `horizon_hour`:00 local and the number of steps to it.

    `now` must be in local time. n = ceil(hours remaining), clamped to 1-24.
    """
    end = now.replace(hour=horizon_hour, minute=0, second=0, microsecond=0)
    if end <= now:
        end += timedelta(days=1)
    steps = math.ceil((end - now).total_seconds() / 3600)
    return end, max(MIN_STEPS, min(MAX_STEPS, steps))
