# Predictive Climate Control — project context

## What this is

A Home Assistant custom integration that forecasts a bedroom's temperature hour by hour to the next 9pm under four scenarios (closed, skylights open, skylights + windows, skylights + windows + fan). Two automations in the owner's Home Assistant consume the forecast:

- **Home Climate Control** opens and closes motorized skylights and sends cooling notifications.
- **Thermostat Control** runs the furnace, including a "heat budget" that stores heat during the day when the closed 9pm forecast is short of a 70 °F target.

The house has no central AC. A portable AC is used on hot nights. The model has no furnace term and no AC term.

## Why this repo exists

The model was built as Jinja template sensors (YAML in the Home Assistant config). That had three problems:

1. The loop is duplicated eight times (state + attribute for each of four sensors), which has caused bugs.
2. It can't be tested against history before a change is deployed.
3. It was tuned through the summer and misses badly in fall (see `docs/findings-2026-11.md`).

Decision (2026-11-15): move the model into a Python integration in this repo, installed through the Home Assistant Marketplace, with coefficients as live options and the formula covered by backtests.

## Plan

1. **Port as-is.** Implement today's formula (`docs/model.md`) as one pure Python function plus an integration that exposes it. Use today's coefficients. Add a test that reproduces the "Current formula" numbers from `backtest/replay.py`.
2. **Run in parallel.** The integration creates NEW sensors beside the existing template sensors. Compare curves for a few days. Nothing live changes.
3. **Cut over.** Point the two automations at the new sensors, then retire the YAML.
4. **Fix fall behaviour** as a separate, tested change. The leading hypothesis is in the findings doc. Backtest it on more closed stretches first, including a summer day (2026-07-16, closed 8:50am–5:42pm, actual peak 76.8 °F at 5pm) so the fix doesn't break summer.

Later candidates: a furnace term, a real mass state instead of an air average, scoring forecasts automatically.

### Status

Step 1 was done on 2026-11-15 from `docs/model.md`, because the legacy YAML was not readable in that session. One live check matched: at 8:45pm that day the model reproduced all four live sensors to 0.1 °F (a single step, at night, so the solar term was not exercised). These details were assumed and should be confirmed against the YAML or during step 2:

- Air is carried between steps unrounded; only outputs are rounded.
- The mass sensor updates at the top of the hour from its unrounded previous value, and starts at the current air temperature.
- The fan's assumed power depends only on the starting indoor temperature.
- Missing `cloud_coverage` or `uv_index` in a forecast entry counts as 0.
- Snapshot curve state = the frozen curve's value at index `floor(hours since 21:02)`. This matches the legacy sensor at 8:01pm on 2026-11-15 (index 22).
- The fan scenario subtracts a fixed 0.05 (`fan_alpha_reference`), not the closed rate. If step 4 lowers the closed rate, decide which was meant.

For step 2, set the integration's optional mass entity to the legacy `sensor.indoor_thermal_mass_estimate` so the curves are comparable from the first refresh.

## Design requirements

- **No house-specific values in code.** Entity IDs, setpoints, and coefficients belong in the config entry and its options. This repo is public.
- **Coefficients are options that apply without a restart.** Only changes to the formula's structure should need a release.
- **Keep the output contract** so the automations need only an entity rename:
  - sensor state = the curve's peak (°F, one decimal)
  - attribute `hourly_forecast` = list of hourly values, last one is the 9pm value
  - attributes `computed_at` and `horizon_end` (ISO timestamps)
  - refresh every 15 minutes; horizon = now to the next 21:00, `n = ceil(hours)` clamped 1–24
- **Also port** the thermal-mass lag sensor and the nightly snapshot (at 21:02 the 24-hour curve is frozen and promoted hourly; it is a scoreboard for accuracy, not a control input).
- The model function must be importable without Home Assistant so backtests and tests can call it directly.

## Home Assistant Marketplace requirements

Verified 2026-11-15 against the Home Assistant docs. The target instance runs 2026.11.1 with the Marketplace loaded.

- HACS became the built-in **Marketplace** in Home Assistant 2026.11 (Settings > Marketplace). The standalone HACS integration is blocked.
- A custom repository must be **public** on GitHub and is added with "Add from link". That needs the Marketplace's GitHub connection.
- The repo needs a **`hacs.json`**; without it the Marketplace can install but not update.
- A first install opens the setup flow without a restart. **Updates still need a restart.**
- Custom repositories are checked for updates every 48 hours.

Not yet confirmed: whether an update check can be forced sooner, and whether the ha-mcp connector's HACS tool works with the Marketplace.

## Working rules

- **One day of data is not a pattern.** Don't change coefficients or thresholds from a single day. Say how many days back a claim.
- **Test before deploying.** Every formula or coefficient change gets a backtest result in the PR.
- **Score only clean stretches.** A forecast is scored only when the real configuration (skylights, windows, fan) matched the scenario, and never over hours when the furnace or AC ran.
- **Fit against the weather entity's values**, since that is what the forecast can see. Note that the house's own outside sensor disagrees with it (findings doc).
- **Convert times carefully.** Home Assistant statistics are epoch milliseconds in UTC; state history and logbook are local time.
- **Prefer the smallest change that fixes the problem.**
- Ask the owner before anything that changes live behaviour.

## Where the live pieces are

- Legacy template YAML: in the Home Assistant config under `templates/` (`trigger_climate_live_forecast.yaml`, `trigger_climate_forecast.yaml`, `trigger_forecast_summary.yaml`). The owner keeps a copy, with calibration notes and an accuracy log, in the references folder of their `home-climate-control` skill. Read those for the exact Jinja and the history behind each coefficient.
- Live data: through the Home Assistant MCP connector for the home instance (the one that has `cover.skylights`).
