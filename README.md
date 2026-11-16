# Predictive Climate Control

A Home Assistant custom integration that forecasts indoor temperature for a house cooled by skylights, windows, and a window fan, and heated by a furnace. Automations use the forecast to decide when to vent and when to store heat.

**Status:** step 1 of the plan in `CLAUDE.md` is done. The integration reproduces the formula that runs today as template sensors, and creates new sensors beside them. It has not been installed on a live instance yet, and nothing reads the new sensors.

## Install

Requires Home Assistant 2026.2 or newer.

1. Settings > Marketplace > Add from link, and paste this repository's URL.
2. Install **Predictive Climate Control**. The setup flow opens without a restart.
3. Choose the indoor temperature sensor, a weather entity that provides an hourly forecast, and optionally an existing thermal-mass sensor.

Every coefficient is under the integration's **Configure** button. Changes apply at once, with no restart.

## Sensors

For each scenario (closed, skylights open, skylights and windows, skylights windows fan):

| Sensor | State | Attributes |
|---|---|---|
| Live forecast | peak of the curve to the next 9pm | `hourly_forecast` (last value is the 9pm value), `computed_at`, `horizon_end` |
| Snapshot curve | the curve frozen at 9:02pm; state is its value for the current hour | `hourly_forecast`, `computed_at` |
| Snapshot horizon value | the 9pm value of the frozen curve | |

Plus one **Thermal mass estimate** sensor, updated hourly. The live forecast refreshes at :00, :15, :30, and :45.

The model works in °F and the attributes are always °F. Inputs in °C are converted. On a metric Home Assistant the sensor states are shown in °C, so there the state and the attributes are in different units.

## Layout

- `custom_components/predictive_climate_control/model.py` — the formula, pure Python, importable without Home Assistant
- `custom_components/predictive_climate_control/` — the integration around it
- `docs/model.md` — the forecast formula
- `docs/findings-2026-11.md` — why the formula misses in fall, with data
- `backtest/replay.py` — replays the formula against recorded history (`python3 backtest/replay.py`)
- `CLAUDE.md` — project context, plan, and working rules

## Tests

```bash
pip install pytest
pytest
```

That runs the model tests, including the backtest that reproduces the "Current formula" numbers from `backtest/replay.py`. The Home Assistant tests are skipped unless the harness is installed:

```bash
pip install -r requirements-test.txt
pytest
```
