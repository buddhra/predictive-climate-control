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
- Snapshot curve state: confirmed against the legacy sensor on 2026-11-16. From the freeze until 22:01 it is the starting indoor temperature; each promotion at one minute past the hour then moves one value along the curve (22:01 shows the first value, 21:01 the next day the last). Version 0.1.0 runs one value ahead of that for all but a minute of each hour (seen 2026-11-17: legacy 62.1, integration 62.7); 0.1.1 fixes it.
- The fan scenario subtracts a fixed 0.05 (`fan_alpha_reference`), not the closed rate. If step 4 lowers the closed rate, decide which was meant.

Step 2 started 2026-11-16; procedure and log are in `docs/parallel-run.md`. The integration is installed with the legacy mass sensor and `weather.home` (met.no) as inputs. Its entity IDs carry the area prefix: `sensor.master_bedroom_predictive_climate_control_*`. A full 15-hour curve matched the legacy sensors exactly in all four scenarios on an overcast morning, which confirms unrounded carry between steps. The UV term cannot be checked live in November: the weather entity's forecast UV is too low for it to beat the solar floor, so every solar step in the parallel run uses the floor. It is covered only by the offline test against `backtest/replay.py`.

Step 4 started 2026-11-16. Backtests on 25 clean stretches and a proposed set of option values are in `docs/findings-2026-11-16.md`; the owner chose to apply the proposal at cut-over without a forward test. Overnight accuracy matters least to the owner.

### Daily review

A scheduled Claude session reviews performance every evening, following `docs/daily-review.md`. The owner approved (2026-11-16) that it may change the integration's option values when `backtest/daily_review.py` says `APPLY`, and may merge its own data and log updates to `main`. Those two permissions are exceptions to "ask the owner before anything that changes live behaviour" and go no further: the guardrails are in that script and loosening them needs the owner.

### Merging

On 2026-11-18 the owner said: "don't wait for me to merge improvements. We can always roll back if needed." Sessions working on this repo may open and merge their own pull requests to `main` without asking, provided the tests pass and the pull request says what changed and why. Tell the owner afterwards what was merged. This is about the repository only. Changes in Home Assistant (cut-over, automations, installing an update, anything beyond the daily review's option values) still need the owner, and so does loosening the daily review's guardrails. A merged code change does not reach the installed integration until the owner updates it in the Marketplace and restarts.

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
- Heat budget: paused since 2026-11-17 by `input_boolean.heat_budget` (off) until cut-over; see `docs/findings-2026-11-17.md`. Decide at step 3 whether to turn it back on.
- Furnace timing: `sensor.hvac_action` is reliable only from 2026-11-16 5:44pm PST, when a one-minute refresh of the thermostat was added. Earlier start and stop times are approximate (`docs/findings-2026-11-17.md`).
