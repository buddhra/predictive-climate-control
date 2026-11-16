"""Score coefficient sets for the closed scenario on every recorded closed stretch.

Run:  python3 backtest/evaluate.py

Uses the same free-run simulation as replay.py. Columns are end-of-stretch misses
(predicted minus actual, F). Nothing here is deployed; see docs/findings-2026-11.md.
"""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.more_stretches import MORE_STRETCHES  # noqa: E402
from backtest.replay import CURRENT, STRETCHES, simulate  # noqa: E402

ALL = {**STRETCHES, **MORE_STRETCHES}
FALL = {k: v for k, v in ALL.items() if not k.startswith("2026-07")}
SUMMER = {k: v for k, v in ALL.items() if k.startswith("2026-07")}

# The findings-doc hypothesis (fitted to the three stretches in replay.py only).
CANDIDATE = dict(CURRENT, alpha_o=0.01, solar_floor=0.5, solar_center=14, alpha_ma=0)
# Best grid fit on all stretches (see refit() below).
REFIT = dict(CURRENT, alpha_o=0.015, solar_floor=0.5, solar_center=15, alpha_ma=0, uv_coeff=0.08)

GRID = list(itertools.product(
    [0, .005, .01, .015, .02, .03, .05],   # alpha_o
    [.3, .4, .5, .6, .7],                  # solar_floor
    [11, 12, 13, 14, 15],                  # solar_center
    [0, .025, .05],                        # alpha_ma
    [.04, .06, .08, .10, .13]))            # uv_coeff


def params(t):
    return dict(CURRENT, alpha_o=t[0], solar_floor=t[1], solar_center=t[2], alpha_ma=t[3], uv_coeff=t[4])


def sse(p, stretches):
    return sum((pred - act) ** 2 for d in stretches.values() for _, pred, act in simulate(d, **p))


def refit(stretches):
    return min(GRID, key=lambda t: sse(params(t), stretches))


def show(label, p):
    rows = {n: simulate(d, **p) for n, d in ALL.items()}
    worst = max(abs(pred - act) for r in rows.values() for _, pred, act in r)
    print(f"\n{label}")
    print(f"  squared error: all {sse(p, ALL):.1f}, fall {sse(p, FALL):.1f}, summer {sse(p, SUMMER):.1f};"
          f" worst hour {worst:.1f} F")
    for n, r in rows.items():
        print(f"  {n:20} {len(r)} h  end {r[-1][1]:.1f}/{r[-1][2]:.1f}  miss {r[-1][1] - r[-1][2]:+.1f}")


if __name__ == "__main__":
    points = sum(len(simulate(d, **CURRENT)) for d in ALL.values())
    print(f"{len(ALL)} closed stretches, {points} hourly points. End columns are predicted/actual F.")
    show("Current formula", CURRENT)
    show("Findings-doc candidate", CANDIDATE)
    show("Candidate with uv_coeff 0.10", dict(CANDIDATE, uv_coeff=0.10))
    show("Refit on all stretches (alpha_o, solar_floor, solar_center, alpha_ma, uv_coeff)", REFIT)
    assert params(refit(ALL)) == REFIT

    print("\nLeave one stretch out, refit on the rest, score the one left out:")
    for held in ALL:
        t = refit({k: v for k, v in ALL.items() if k != held})
        r = simulate(ALL[held], **params(t))
        print(f"  {held:20} fit {t}  end miss {r[-1][1] - r[-1][2]:+.1f}")
