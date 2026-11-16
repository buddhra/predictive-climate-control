# Predictive Climate Control

A Home Assistant custom integration (in progress) that forecasts indoor temperature for a house cooled by skylights, windows, and a window fan, and heated by a furnace. Automations use the forecast to decide when to vent and when to store heat.

**Status:** planning. The model currently runs as Home Assistant template sensors; this repo will replace them with a tested Python integration. Nothing here is installable yet.

- `CLAUDE.md` — project context, plan, and working rules
- `docs/model.md` — the forecast formula as deployed today
- `docs/findings-2026-11.md` — why the formula misses in fall, with data
- `backtest/replay.py` — replays the formula against recorded history (`python3 backtest/replay.py`)
