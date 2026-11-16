"""Score coefficient sets on the recorded open nights, using the integration's model.

Run:  python3 backtest/evaluate_open.py

Each night is free-run from its start under the scenario that really held.
"actual" and "model" are the bedroom's change over the stretch in F.
Nothing here is deployed; see docs/findings-2026-11-16.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.open_stretches import OPEN_STRETCHES  # noqa: E402
from custom_components.predictive_climate_control import model  # noqa: E402
from custom_components.predictive_climate_control.model import Coefficients  # noqa: E402

# The closed-scenario refit from evaluate.py, in the integration's option names.
REFIT_BASE = dict(alpha_outdoor=0.015, alpha_mass_to_air=0, solar_floor=0.5,
                  solar_center_hour=15, uv_coeff=0.08)


def actual_at(d, hour):
    i = hour - d["h0"]
    return (d["bed"][i - 1] + d["bed"][i]) / 2


def simulate(d, c, scenario=None):
    """Returns [(hour, predicted, actual)] for one night."""
    hours = [model.ForecastHour(d["out"][h - d["h0"]], 0, 0, h % 24) for h in range(d["start"], d["end"])]
    curve = model.simulate(scenario or d["scenario"], actual_at(d, d["start"]),
                           d["mass"][d["start"] - d["h0"]], hours, c)
    return [(d["start"] + 1 + i, p, actual_at(d, d["start"] + 1 + i)) for i, p in enumerate(curve)]


def sse(c, names):
    return sum((p - a) ** 2 for n in names for _, p, a in simulate(OPEN_STRETCHES[n], c))


def show(label, c):
    print(f"\n{label}")
    for name, d in OPEN_STRETCHES.items():
        rows = simulate(d, c)
        start = actual_at(d, d["start"])
        print(f"  {name:17} {d['scenario']:22} {len(rows):2} h  actual {rows[-1][2] - start:+.1f}"
              f"  model {rows[-1][1] - start:+.1f}  end miss {rows[-1][1] - rows[-1][2]:+.1f}")
    print(f"  squared error {sse(c, OPEN_STRETCHES):.1f}")


def best(option, names, base):
    values = [v / 1000 for v in range(-15, 80)]
    return min(values, key=lambda v: sse(Coefficients(**base, **{option: v}), names))


if __name__ == "__main__":
    skylight = [n for n, d in OPEN_STRETCHES.items() if d["scenario"] == model.SKYLIGHTS_OPEN]
    window = [n for n, d in OPEN_STRETCHES.items() if d["scenario"] == model.SKYLIGHTS_AND_WINDOWS]

    show("Current formula", Coefficients())
    show("Closed refit, venting amounts unchanged", Coefficients(**REFIT_BASE))
    show("Closed refit, venting amounts raised by 0.035 to keep the old totals",
         Coefficients(**REFIT_BASE, skylight_vent_alpha=0.04, window_vent_alpha=0.045))

    s = best("skylight_vent_alpha", skylight, REFIT_BASE)
    w = best("window_vent_alpha", window, REFIT_BASE)
    show(f"Closed refit, venting fitted to these nights (skylight {s}, window {w})",
         Coefficients(**REFIT_BASE, skylight_vent_alpha=s, window_vent_alpha=w))
    print("\nBest window venting amount for each window night on its own (closed refit base):")
    for n in window:
        print(f"  {n}: {best('window_vent_alpha', [n], REFIT_BASE)}")
