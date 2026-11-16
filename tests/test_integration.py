"""Tests for the Home Assistant side. Skipped unless the test harness is installed."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import SupportsResponse  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM  # noqa: E402
from pytest_homeassistant_custom_component.common import (  # noqa: E402
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.predictive_climate_control.const import DOMAIN  # noqa: E402

TZ = ZoneInfo("America/Los_Angeles")
INDOOR = "sensor.bedroom"
WEATHER = "weather.home"
MASS = "sensor.legacy_mass"
PREFIX = "sensor.predictive_climate_control_"
SCENARIOS = ["closed", "skylights_open", "skylights_and_windows", "skylights_windows_fan"]


def _weather_hours(first: datetime, count: int = 48) -> list:
    """Hourly entries starting at `first`; 53 F and overcast, like the evening of 2026-11-15."""
    return [{"datetime": (first + timedelta(hours=i)).astimezone(ZoneInfo("UTC")).isoformat(),
             "temperature": 53, "cloud_coverage": 94.5, "uv_index": 0} for i in range(count)]


@pytest.fixture
async def house(hass, freezer):
    """A Home Assistant with an indoor sensor, a legacy mass sensor, and a weather service."""
    await hass.config.async_set_time_zone("America/Los_Angeles")
    hass.config.units = US_CUSTOMARY_SYSTEM
    freezer.move_to(datetime(2026, 11, 15, 20, 45, tzinfo=TZ))
    hass.states.async_set(INDOOR, "72.1399993896484", {"unit_of_measurement": "°F"})
    hass.states.async_set(MASS, "70.9", {"unit_of_measurement": "°F"})
    hass.states.async_set(WEATHER, "cloudy", {"temperature_unit": "°F"})
    forecast = {"hours": _weather_hours(datetime(2026, 11, 15, 21, 0, tzinfo=TZ))}

    async def get_forecasts(call):
        return {WEATHER: {"forecast": forecast["hours"]}}

    hass.services.async_register("weather", "get_forecasts", get_forecasts,
                                 supports_response=SupportsResponse.ONLY)
    return forecast


async def _setup(hass, data=None, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Predictive Climate Control",
        data=data or {"indoor_entity": INDOOR, "weather_entity": WEATHER, "mass_entity": MASS},
        options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _tick(hass, freezer, when):
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def test_live_sensors_match_legacy_values(hass, house):
    """Same inputs as the live template sensors at 8:45pm on 2026-11-15, same outputs."""
    await _setup(hass)
    expected = {"closed": 71.1, "skylights_open": 71.0,
                "skylights_and_windows": 70.9, "skylights_windows_fan": 69.8}
    for scenario, value in expected.items():
        state = hass.states.get(f"{PREFIX}live_forecast_{scenario}")
        assert float(state.state) == value
        assert state.attributes["hourly_forecast"] == [value]
        assert state.attributes["computed_at"] == "2026-11-15T20:45:00-08:00"
        assert state.attributes["horizon_end"] == "2026-11-15T21:00:00-08:00"
        assert state.attributes["unit_of_measurement"] == "°F"


async def test_refreshes_on_the_quarter_hour_with_new_horizon(hass, house, freezer):
    await _setup(hass)
    hass.states.async_set(INDOOR, "70.0", {"unit_of_measurement": "°F"})
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "71.1"  # not yet refreshed

    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 0, tzinfo=TZ))
    state = hass.states.get(f"{PREFIX}live_forecast_closed")
    assert len(state.attributes["hourly_forecast"]) == 24
    assert state.attributes["horizon_end"] == "2026-11-16T21:00:00-08:00"
    assert float(state.state) == max(state.attributes["hourly_forecast"])


async def test_coefficient_option_applies_without_reload(hass, house):
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    hass.config_entries.async_update_entry(entry, options={"alpha_outdoor": 0.01})
    await hass.async_block_till_done()
    assert entry.runtime_data is coordinator  # not reloaded
    # 72.14 + 0.01 * (53 - 72.14) + 0.05 * (70.9 - 72.14) = 71.89
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "71.9"


async def test_own_mass_sensor_seeds_and_steps_hourly(hass, house, freezer):
    await _setup(hass)
    assert hass.states.get(f"{PREFIX}thermal_mass_estimate").state == "72.1"  # seeded from the air
    hass.states.async_set(INDOOR, "62.14", {"unit_of_measurement": "°F"})
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 0, tzinfo=TZ))
    # 72.14 + 0.10 * (62.14 - 72.14) = 71.14
    assert hass.states.get(f"{PREFIX}thermal_mass_estimate").state == "71.1"


async def test_uses_own_mass_when_no_mass_entity(hass, house):
    await _setup(hass, data={"indoor_entity": INDOOR, "weather_entity": WEATHER})
    # mass == air, so 72.14 + 0.05 * (53 - 72.14) = 71.18
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "71.2"


async def test_nightly_snapshot_freezes_and_promotes(hass, house, freezer):
    await _setup(hass)
    curve_id = f"{PREFIX}snapshot_curve_closed"
    horizon_id = f"{PREFIX}snapshot_horizon_value_closed"
    assert hass.states.get(curve_id).state == "unavailable"

    house["hours"] = _weather_hours(datetime(2026, 11, 15, 22, 0, tzinfo=TZ))
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 2, tzinfo=TZ))
    state = hass.states.get(curve_id)
    curve = state.attributes["hourly_forecast"]
    assert len(curve) == 24
    assert state.attributes["computed_at"] == "2026-11-15T21:02:00-08:00"
    assert float(state.state) == curve[0]
    assert float(hass.states.get(horizon_id).state) == curve[-1]

    # The frozen curve does not move when the live forecast refreshes with new inputs...
    hass.states.async_set(INDOOR, "60.0", {"unit_of_measurement": "°F"})
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 15, tzinfo=TZ))
    assert hass.states.get(curve_id).attributes["hourly_forecast"] == curve
    # ...and its state is promoted at one minute past each hour.
    await _tick(hass, freezer, datetime(2026, 11, 15, 23, 1, tzinfo=TZ))
    assert float(hass.states.get(curve_id).state) == curve[1]
    await _tick(hass, freezer, datetime(2026, 11, 16, 20, 1, tzinfo=TZ))
    assert float(hass.states.get(curve_id).state) == curve[22]
    await _tick(hass, freezer, datetime(2026, 11, 16, 20, 2, tzinfo=TZ))  # not the horizon hour
    await _tick(hass, freezer, datetime(2026, 11, 16, 21, 1, tzinfo=TZ))
    assert float(hass.states.get(curve_id).state) == curve[23]


async def test_snapshot_and_mass_survive_reload(hass, house, freezer):
    entry = await _setup(hass)
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 2, tzinfo=TZ))
    curve = hass.states.get(f"{PREFIX}snapshot_curve_closed").attributes["hourly_forecast"]
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 3, tzinfo=TZ))  # let the delayed save run
    hass.states.async_set(INDOOR, "60.0", {"unit_of_measurement": "°F"})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(f"{PREFIX}snapshot_curve_closed").attributes["hourly_forecast"] == curve
    assert hass.states.get(f"{PREFIX}thermal_mass_estimate").state != "60.0"


async def test_unavailable_when_inputs_missing_then_recovers(hass, house, freezer):
    hass.states.async_set(INDOOR, "unavailable")
    await _setup(hass)
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "unavailable"
    hass.states.async_set(INDOOR, "72.1399993896484", {"unit_of_measurement": "°F"})
    house["hours"] = []
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 0, tzinfo=TZ))
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "unavailable"
    house["hours"] = _weather_hours(datetime(2026, 11, 15, 22, 0, tzinfo=TZ))
    await _tick(hass, freezer, datetime(2026, 11, 15, 21, 15, tzinfo=TZ))
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state != "unavailable"


async def test_celsius_inputs_are_converted(hass, house):
    hass.states.async_set(INDOOR, "22.3", {"unit_of_measurement": "°C"})  # 72.14 F
    hass.states.async_set(MASS, "21.6111", {"unit_of_measurement": "°C"})  # 70.9 F
    hass.states.async_set(WEATHER, "cloudy", {"temperature_unit": "°C"})
    for hour in house["hours"]:
        hour["temperature"] = 11.6667  # 53 F
    await _setup(hass)
    state = hass.states.get(f"{PREFIX}live_forecast_closed")
    assert state.attributes["hourly_forecast"] == [71.1]


async def test_all_thirteen_entities_created(hass, house):
    await _setup(hass)
    ids = {s.entity_id for s in hass.states.async_all("sensor") if s.entity_id.startswith(PREFIX)}
    expected = {f"{PREFIX}thermal_mass_estimate"}
    for s in SCENARIOS:
        expected |= {f"{PREFIX}live_forecast_{s}", f"{PREFIX}snapshot_curve_{s}",
                     f"{PREFIX}snapshot_horizon_value_{s}"}
    assert ids == expected


async def test_setup_and_options_flows(hass, house):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"indoor_entity": INDOOR, "weather_entity": WEATHER, "mass_entity": MASS})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {"indoor_entity": INDOOR, "weather_entity": WEATHER, "mass_entity": MASS}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    defaults = {k.schema: k.default() for k in result["data_schema"].schema
                if getattr(k, "default", None) is not None and callable(k.default)
                and k.default() is not None}
    assert defaults["alpha_outdoor"] == 0.05 and defaults["horizon_hour"] == 21
    user_input = {**defaults, "indoor_entity": INDOOR, "weather_entity": WEATHER, "solar_floor": 0.5}
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["solar_floor"] == 0.5
    assert entry.options["mass_entity"] is None  # cleared in the form, so own mass is used
    assert entry.runtime_data.coefficients.solar_floor == 0.5
    assert hass.states.get(f"{PREFIX}live_forecast_closed").state == "71.2"
