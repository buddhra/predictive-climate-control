# Parallel run (plan step 2)

The integration's sensors run beside the legacy template sensors. Nothing reads the new ones. The run passes when the two families agree for about three days, including at least one sunny day (the UV part of the solar term is only exercised then).

## Setup on the instance

- Indoor sensor and weather entity: the same ones the legacy templates use. The weather entity must supply `uv_index` and `cloud_coverage`; the NWS integration does not.
- Mass sensor: the legacy thermal-mass sensor, so both families start from the same mass.
- Coefficients: defaults.

## What counts as a match

- **Live curves:** both families refresh on the quarter hour, a fraction of a second apart. Compare only refreshes made in the same minute. The bedroom sensor flickers by about 0.18 °F, so a difference up to 0.2 °F right after a reading change is input noise, not a formula difference.
- **Nightly snapshot:** both freeze a 24-hour curve at 21:02 from the same inputs. This is the cleanest daily comparison: 24 values per scenario.

## The check

Paste into Developer tools > Template (or run through the Home Assistant connector). Change the two prefixes to match the instance. Each line shows old/new.

```jinja
{%- set OLD_LIVE = 'sensor.live_forecasted_indoor_temp_' -%}
{%- set OLD_CURVE = 'sensor.forecasted_indoor_temp_curve_' -%}
{%- set OLD_9PM = 'sensor.forecasted_indoor_temp_' -%}
{%- set N = 'sensor.master_bedroom_predictive_climate_control_' -%}
now {{ now().strftime('%Y-%m-%d %H:%M') }}
{% for s in ['closed','skylights_open','skylights_and_windows','skylights_windows_fan'] -%}
{%- set pairs = [
  ('live', OLD_LIVE ~ s, N ~ 'live_forecast_' ~ s),
  ('snap', OLD_CURVE ~ s, N ~ 'snapshot_curve_' ~ s)] -%}
{%- for kind, o, n in pairs -%}
{%- set a = state_attr(o, 'hourly_forecast') -%}{%- set b = state_attr(n, 'hourly_forecast') -%}
{{ kind }} {{ s }}: {% if a is none or b is none %}missing (old {{ states(o) }}, new {{ states(n) }}){% else -%}
{%- set ns = namespace(d=0.0) -%}
{%- for i in range([a|length, b|length]|min) -%}{%- set ns.d = [ns.d, (a[i] - b[i])|abs]|max -%}{%- endfor -%}
len {{ a|length }}/{{ b|length }} maxdiff {{ ns.d|round(2) }} state {{ states(o) }}/{{ states(n) }} last {{ a[-1] }}/{{ b[-1] }} at {{ (state_attr(o,'computed_at')|string)[11:19] }}/{{ (state_attr(n,'computed_at')|string)[11:19] }}{% endif %}
{% endfor -%}
snap9pm {{ s }}: {{ states(OLD_9PM ~ s) }}/{{ states(N ~ 'snapshot_horizon_value_' ~ s) }}
{% endfor %}
```

## Log

| When | Check | Result |
|---|---|---|
| 2026-11-16 06:15 | Model run offline on the legacy sensors' inputs (bedroom 70.88 °F, mass 71.3 °F, met.no forecast), 15 hours × 4 scenarios | 60 of 60 values identical. Fully overcast, so the solar floor was exercised and the UV term was not. |
| 2026-11-16 06:17 | First live comparison | Curves differed by up to 1.5 °F at 9pm because the integration was set to the NWS weather entity. Switched to the met.no entity. |
| 2026-11-16 06:21 | Live, after the switch (new refreshed at 06:21, old at 06:15) | Max difference 0.2 °F, all from the bedroom reading moving 70.88 → 70.70 °F between the two refreshes. |
| 2026-11-16 21:02 | First nightly snapshot, all four scenarios | 96 of 96 curve values identical; the four 9pm values identical; both frozen at 21:02:00. One difference: until the first promotion at 22:01 the legacy curve sensor's state is the starting bedroom temperature (70.5), where the integration showed the first curve value (69.2 for closed). Fixed in 0.1.1, not yet installed. The live curves at 21:00 were also identical (24 values each). |
| 2026-11-16 21:11 | Thermal mass estimate | Legacy 71.0, integration's own 71.1. The integration's started this morning from the air temperature (70.7) while the legacy one was at 71.3, so they are still converging. It is not used as an input during the parallel run. |
| 2026-11-17 12:36 | Daily check 1 of 3: live curves (both computed 12:30:00) and last night's snapshot | Live: 9 of 9 values identical in all four scenarios. Snapshot: 96 of 96 curve values and the four 9pm values identical. Snapshot curve *state* differs: legacy 62.1 (the curve's 15th value), integration 0.1.0 62.7 (the 16th). 0.1.0 runs one value ahead of the legacy sensor from two minutes past each hour until one minute past the next; the 0.1.1 fix already on the branch gives 62.1 here. Thermal mass: 70.0 and 70.0. |
| 2026-11-17 12:36 | Was the UV term exercised? | No, and it cannot be this month. Current conditions were sunny (UV 3.1, cloud 1%), but the UV term only applies when 0.13 × UV × (1 − cloud) beats the solar floor, and the weather entity's forecast UV for mid-November (about 3 at noon, under 2.7 after 1pm) never does. Every solar step in the parallel run so far has used the floor. The UV term is covered only by the offline test against `backtest/replay.py`, not by a live comparison with the legacy sensors. |
