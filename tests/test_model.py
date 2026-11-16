"""Tests for the pure model. These need only pytest, not Home Assistant."""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from backtest import replay
from custom_components.predictive_climate_control import model
from custom_components.predictive_climate_control.model import Coefficients, ForecastHour

ROOT = Path(__file__).resolve().parents[1]


def test_model_imports_without_home_assistant():
    code = ("import sys; from custom_components.predictive_climate_control import model; "
            "assert 'homeassistant' not in sys.modules")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def test_defaults_are_the_deployed_coefficients():
    c = Coefficients()
    assert (c.alpha_outdoor, c.alpha_mass_to_air, c.alpha_air_to_mass) == (0.05, 0.05, 0.10)
    assert (c.uv_coeff, c.solar_floor, c.solar_center_hour, c.solar_half_width_hours) == (0.13, 0.7, 11, 6)
    assert (c.skylight_vent_alpha, c.window_vent_alpha, c.vent_full_delta) == (0.005, 0.01, 15)


# --- backtest: reproduce the "Current formula" numbers from backtest/replay.py ---

def _closed_curve(d):
    """Free-run the closed scenario over a replay stretch using the integration's model."""
    start = d["start"]
    hours = [ForecastHour(temperature=d["out"][h - d["h0"]], cloud=d["cloud"][h - d["h0"]],
                          uv_index=d["uv"][h - d["h0"]], hour_of_day=h)
             for h in range(start, d["end"])]
    air = replay.actual_at(d, start)
    mass = d["mass"][start - d["h0"]]
    return model.simulate(model.CLOSED, air, mass, hours)


@pytest.mark.parametrize("day", list(replay.STRETCHES))
def test_matches_replay_hour_by_hour(day):
    d = replay.STRETCHES[day]
    expected = [p for _, p, _ in replay.simulate(d, **replay.CURRENT)]
    assert _closed_curve(d) == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("day, end_value, end_miss", [
    ("2026-11-07", 68.6, -2.4),
    ("2026-11-10", 73.0, 0.0),
    ("2026-11-15", 70.0, -2.1),
])
def test_end_values_from_findings_doc(day, end_value, end_miss):
    d = replay.STRETCHES[day]
    end = _closed_curve(d)[-1]
    assert round(end, 1) == end_value
    assert round(end - replay.actual_at(d, d["end"]), 1) == pytest.approx(end_miss)


def test_total_squared_error_from_findings_doc():
    total, points = 0.0, 0
    for d in replay.STRETCHES.values():
        for i, predicted in enumerate(_closed_curve(d)):
            total += (predicted - replay.actual_at(d, d["start"] + 1 + i)) ** 2
            points += 1
    assert points == 21
    assert round(total, 1) == 30.7


# --- parity with the live template sensors ---

def test_matches_live_sensors_2026_11_15_2045():
    """Inputs and outputs read from Home Assistant at 8:45pm on 2026-11-15 (one step)."""
    hours = [ForecastHour(temperature=53, cloud=0.945, uv_index=0, hour_of_day=21)]
    air, mass = 72.1399993896484, 70.9
    expected = {model.CLOSED: 71.1, model.SKYLIGHTS_OPEN: 71.0,
                model.SKYLIGHTS_AND_WINDOWS: 70.9, model.SKYLIGHTS_WINDOWS_FAN: 69.8}
    for scenario, value in expected.items():
        result = model.forecast(scenario, air, mass, hours)
        assert result.peak == value
        assert result.hourly == [value]


# --- formula pieces ---

def test_scenarios_equal_when_outside_is_warmer():
    hours = [ForecastHour(temperature=80, cloud=0, uv_index=0, hour_of_day=22)] * 3
    closed = model.simulate(model.CLOSED, 70, 70, hours)
    assert model.simulate(model.SKYLIGHTS_OPEN, 70, 70, hours) == closed
    assert model.simulate(model.SKYLIGHTS_AND_WINDOWS, 70, 70, hours) == closed


def test_fan_power_depends_on_starting_temperature():
    c = Coefficients()
    assert model.fan_alpha(73.0, c) == pytest.approx(0.04 + 36 / 53 * 0.10)
    assert model.fan_alpha(73.1, c) == pytest.approx(0.04 + 42 / 53 * 0.10)


def test_solar_is_larger_of_uv_term_and_floor():
    c = Coefficients()
    assert model.solar_gain(ForecastHour(60, 0.0, 0, 11), c) == pytest.approx(0.7)
    assert model.solar_gain(ForecastHour(60, 0.0, 0, 14), c) == pytest.approx(0.35)
    assert model.solar_gain(ForecastHour(60, 0.0, 0, 17), c) == 0
    assert model.solar_gain(ForecastHour(60, 0.5, 8, 17), c) == pytest.approx(0.52)


def test_forecast_peak_and_rounding():
    hours = [ForecastHour(75, 0, 3, 12), ForecastHour(60, 0, 0, 20), ForecastHour(55, 0, 0, 21)]
    result = model.forecast(model.CLOSED, 70, 70, hours)
    assert len(result.hourly) == 3
    assert result.peak == max(result.hourly)
    assert all(round(v, 1) == v for v in result.hourly)


def test_coefficients_from_mapping_ignores_other_keys():
    c = Coefficients.from_mapping({"alpha_outdoor": 0.01, "indoor_entity": "sensor.x", "uv_coeff": None})
    assert c.alpha_outdoor == 0.01
    assert c.uv_coeff == 0.13


def test_mass_step():
    assert model.mass_step(70, 72) == pytest.approx(70.2)


@pytest.mark.parametrize("now, steps, end", [
    (datetime(2026, 11, 15, 20, 45), 1, datetime(2026, 11, 15, 21, 0)),
    (datetime(2026, 11, 15, 12, 0), 9, datetime(2026, 11, 15, 21, 0)),
    (datetime(2026, 11, 15, 11, 59), 10, datetime(2026, 11, 15, 21, 0)),
    (datetime(2026, 11, 15, 21, 0), 24, datetime(2026, 11, 16, 21, 0)),
    (datetime(2026, 11, 15, 21, 2), 24, datetime(2026, 11, 16, 21, 0)),
    (datetime(2026, 11, 15, 20, 59, 59), 1, datetime(2026, 11, 15, 21, 0)),
])
def test_horizon(now, steps, end):
    assert model.horizon(now) == (end, steps)
