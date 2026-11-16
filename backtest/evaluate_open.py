"""Score coefficient sets on the recorded open stretches, using the integration's model.

Run:  python3 backtest/evaluate_open.py

Each stretch is free-run from its start under the scenario that really held.
"actual" and "model" are the bedroom's change over the stretch in F.
Stretches marked uncertain are shown but never used for fitting.
Nothing here is deployed; see docs/findings-2026-11-16.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.afternoon_stretches import AFTERNOON_STRETCHES, FAN_STRETCHES  # noqa: E402
from backtest.open_stretches import OPEN_STRETCHES  # noqa: E402
from custom_components.predictive_climate_control import model  # noqa: E402
from custom_components.predictive_climate_control.model import Coefficients  # noqa: E402

# The closed-scenario refit from evaluate.py, in the integration's option names.
REFIT_BASE = dict(alpha_outdoor=0.015, alpha_mass_to_air=0, solar_floor=0.5,
                  solar_center_hour=15, uv_coeff=0.08)
# The proposal: the closed refit, plus a larger window amount. The skylight amount and
# the fan are left as deployed because the data does not pin them down (see findings).
PROPOSED = dict(REFIT_BASE, window_vent_alpha=0.02)

GROUPS = {
    "Afternoon and evening (to 9pm or 10pm)": AFTERNOON_STRETCHES,
    "Nights": OPEN_STRETCHES,
    "Fan nights": FAN_STRETCHES,
}


def actual_at(d, hour):
    i = hour - d["h0"]
    return (d["bed"][i - 1] + d["bed"][i]) / 2


def simulate(d, c, scenario=None):
    """Returns [(hour, predicted, actual)] for one night."""
    def at(name, h):
        return d[name][h - d["h0"]] if name in d else 0
    hours = [model.ForecastHour(at("out", h), at("cloud", h), at("uv", h), h % 24)
             for h in range(d["start"], d["end"])]
    curve = model.simulate(scenario or d["scenario"], actual_at(d, d["start"]),
                           d["mass"][d["start"] - d["h0"]], hours, c)
    return [(d["start"] + 1 + i, p, actual_at(d, d["start"] + 1 + i)) for i, p in enumerate(curve)]


def sse(c, stretches, fitting=False):
    return sum((p - a) ** 2 for d in stretches.values() if not (fitting and d.get("uncertain"))
               for _, p, a in simulate(d, c))


def show(label, c):
    print(f"\n=== {label}")
    for group, stretches in GROUPS.items():
        print(f"  {group}: squared error {sse(c, stretches):.1f}")
        for name, d in stretches.items():
            rows = simulate(d, c)
            start = actual_at(d, d["start"])
            print(f"    {name:17} {d['scenario']:22} {len(rows):2} h  actual {rows[-1][2] - start:+.1f}"
                  f"  model {rows[-1][1] - start:+.1f}  end miss {rows[-1][1] - rows[-1][2]:+.1f}"
                  f"{'  (uncertain)' if d.get('uncertain') else ''}")


def only(stretches, scenario):
    return {n: d for n, d in stretches.items() if d["scenario"] == scenario}


def best(option, stretches, base, low=-15, high=120):
    values = [v / 1000 for v in range(low, high)]
    return min(values, key=lambda v: sse(Coefficients(**{**base, option: v}), stretches, fitting=True))


if __name__ == "__main__":
    show("Current formula", Coefficients())
    show("Closed refit, venting amounts as deployed", Coefficients(**REFIT_BASE))
    show("Closed refit, venting amounts raised by 0.035 to keep the old totals",
         Coefficients(**REFIT_BASE, skylight_vent_alpha=0.04, window_vent_alpha=0.045))
    show("Proposed", Coefficients(**PROPOSED))

    print("\n=== Best single value per group, on the closed refit base (uncertain stretches excluded)")
    for group in ("Afternoon and evening (to 9pm or 10pm)", "Nights"):
        s = best("skylight_vent_alpha", only(GROUPS[group], model.SKYLIGHTS_OPEN), REFIT_BASE)
        w = best("window_vent_alpha", only(GROUPS[group], model.SKYLIGHTS_AND_WINDOWS), REFIT_BASE)
        print(f"  {group}: skylight {s}, window {w}")
    print("  Best value for each stretch on its own:")
    for group in ("Afternoon and evening (to 9pm or 10pm)", "Nights"):
        for name, d in GROUPS[group].items():
            if d.get("uncertain"):
                continue
            option = "skylight_vent_alpha" if d["scenario"] == model.SKYLIGHTS_OPEN else "window_vent_alpha"
            print(f"    {name:17} {option:20} {best(option, {name: d}, REFIT_BASE)}")
    ref = best("fan_alpha_reference", FAN_STRETCHES, PROPOSED)
    c = Coefficients(**{**PROPOSED, "fan_alpha_reference": ref})
    print(f"  Fan nights: best fan_alpha_reference {ref} (deployed 0.05), which makes the fan add"
          f" {model.fan_alpha(70, c) - ref:.3f} per hour instead of {model.fan_alpha(70, c) - 0.05:.3f};"
          f" squared error {sse(c, FAN_STRETCHES):.1f}")
