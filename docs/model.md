# The forecast formula as deployed (November 2026)

This describes the Home Assistant template sensors the integration will replace. Port it exactly before changing anything.

## Inputs

- **Indoor air:** the bedroom temperature sensor, read when the forecast runs.
- **Mass estimate:** a lag sensor updated hourly: `mass = prev + 0.10 * (air - prev)`. It is a running average of the bedroom air, not a measurement of the structure.
- **Weather:** `weather.get_forecasts` (hourly) on the weather entity. Each hour supplies `temperature`, `cloud_coverage` (%), `uv_index`, and `datetime`.

## Horizon

From now to the next 21:00 local. `n = ceil(hours remaining)`, clamped to 1–24. The first `n` forecast entries are stepped in order.

## One step per forecast hour

```
vent     = min(max(0, air - t_out) / 15, 1)
solar    = max(0.13 * uv * (1 - cloud), 0.7 * max(0, 1 - |hour_of_day - 11| / 6))
new_air  = air + alpha_o * (t_out - air) + 0.05 * (mass - air) + solar
new_mass = mass + 0.10 * (air - mass)
```

`cloud` is a fraction (0–1). `hour_of_day` is the local hour of the forecast entry.

## Outdoor coupling `alpha_o` by scenario

| Scenario | `alpha_o` |
|---|---|
| Closed | `0.05` |
| Skylights open | `0.05 + 0.005 * vent` |
| Skylights + windows | `0.05 + 0.01 * vent` |
| Skylights + windows + fan | `0.05 + 0.01 * vent + (fan_alpha - 0.05)` |

`fan_alpha = 0.04 + (min(assumed_power, 53) / 53) * 0.10`, where `assumed_power` is 42 W if the starting indoor temperature is above 73 °F, otherwise 36 W.

## Outputs

- **State:** the peak of the curve, rounded to 0.1 °F.
- **`hourly_forecast`:** each `new_air`, rounded to 0.1 °F. The last value is the 9pm value.
- **`computed_at`, `horizon_end`:** ISO timestamps.

## How the automations use it

- Closed curve peak (max of `hourly_forecast`) and closed 9pm value (last element) drive skylight opening, the heat budget, and the overshoot guard.
- Each scenario's 9pm value is quoted in notifications and picks the 8pm bedtime suggestion.

## Calibration history (summary)

- Overnight passive cooling was fitted first, then the fan. Open-window nights cooled at about the same rate as the base, so the window and skylight bonuses were cut to 0.01 and 0.005. The closed scenario was never fitted separately.
- The fan part is a constant added to the vent-scaled window part.
- Summer checks: far-out forecasts ran about 3 °F warm; forecasts 1–2 hours out were within about 1 °F.
- Late September: the skylights + windows scenario ran 0.7–2.0 °F cool on two evenings at 1–2 hours' lead.
