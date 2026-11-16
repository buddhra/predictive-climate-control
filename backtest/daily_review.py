"""Daily review: validate the recorded stretches, score the deployed values, and decide
whether a bounded change to the option values passes the guardrails.

    python3 backtest/daily_review.py                 # report and verdict (changes nothing)
    python3 backtest/daily_review.py --record DATE   # after the verdict's values were applied in
                                                     # Home Assistant: write them to deployed.json

The procedure around this script is docs/daily-review.md. This script never talks to
Home Assistant; it only reads files in this repo.
"""
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.afternoon_stretches import AFTERNOON_STRETCHES, FAN_STRETCHES  # noqa: E402
from backtest.evaluate_open import simulate  # noqa: E402
from backtest.more_stretches import MORE_STRETCHES  # noqa: E402
from backtest.open_stretches import OPEN_STRETCHES  # noqa: E402
from backtest.replay import STRETCHES  # noqa: E402
from custom_components.predictive_climate_control.model import SCENARIOS, Coefficients  # noqa: E402

DATA_DIR = ROOT / "backtest" / "data"
DEPLOYED = ROOT / "backtest" / "deployed.json"

# option: (largest step per change, lowest allowed, highest allowed)
TUNABLE = {
    "alpha_outdoor": (0.005, 0.0, 0.05),
    "alpha_mass_to_air": (0.025, 0.0, 0.05),
    "solar_floor": (0.1, 0.2, 0.8),
    "solar_center_hour": (1, 11, 16),
    "uv_coeff": (0.02, 0.04, 0.13),
    "skylight_vent_alpha": (0.005, 0.0, 0.03),
    "window_vent_alpha": (0.01, 0.0, 0.06),
}
MIN_NEW_DAYS = 5          # clean days recorded since the last change
MIN_IMPROVEMENT = 0.05    # the objective must fall by at least this fraction
# How much worse (as a fraction) each group may get. Overnight matters least to the owner.
TOLERANCE = {"closed": 0.02, "open_day": 0.02, "night": 0.10, "fan": 0.10}
NIGHT_WEIGHT = 0.25
MIN_HOURS = 3


def group_of(d):
    if d["scenario"] == "skylights_windows_fan":
        return "fan"
    if d["scenario"] == "closed":
        return "closed"
    return "open_day" if d["end"] <= 22 else "night"


def validate(name, d):
    """Return a list of problems with one stretch (empty if it is usable)."""
    problems = []
    if d.get("scenario") not in SCENARIOS:
        return [f"{name}: unknown scenario {d.get('scenario')!r}"]
    n = len(d.get("bed", []))
    for key in ("bed", "mass", "out"):
        if len(d.get(key, [])) != n or any(not isinstance(v, (int, float)) for v in d.get(key, [])):
            problems.append(f"{name}: {key} must be {n} numbers")
    for key in ("uv", "cloud", "fan"):
        if key in d and len(d[key]) != n:
            problems.append(f"{name}: {key} has {len(d[key])} values, expected {n}")
    if problems:
        return problems
    h0, start, end = d["h0"], d["start"], d["end"]
    if not (h0 < start < end <= h0 + n - 1):
        problems.append(f"{name}: need h0 < start < end <= h0 + len - 1 (h0={h0}, start={start}, end={end})")
    if end - start < MIN_HOURS:
        problems.append(f"{name}: shorter than {MIN_HOURS} hours")
    if any(not 40 <= v <= 100 for v in d["bed"] + d["mass"]) or any(not 0 <= v <= 120 for v in d["out"]):
        problems.append(f"{name}: a temperature is outside the plausible range in F")
    if any(abs(a - b) > 3 for a, b in zip(d["bed"], d["bed"][1:])):
        problems.append(f"{name}: bedroom jumps more than 3 F between hours")
    if any(not 0 <= v <= 1 for v in d.get("cloud", [])):
        problems.append(f"{name}: cloud must be a fraction 0-1")
    if any(not 0 <= v <= 13 for v in d.get("uv", [])):
        problems.append(f"{name}: uv outside 0-13")
    fan = d.get("fan", [0] * n)[start - h0:end - h0]
    if d["scenario"] == "skylights_windows_fan":
        if any(v <= 10 for v in fan):
            problems.append(f"{name}: fan scenario but fan at or below 10 W in the stretch")
    elif any(v > 1 for v in fan):
        problems.append(f"{name}: fan running in a non-fan stretch")
    return problems


def load():
    """Returns (stretches, new_days, problems). new_days maps date -> stretch names from data/."""
    stretches = {}
    for name, d in {**STRETCHES, **MORE_STRETCHES}.items():
        stretches[name] = dict(d, scenario="closed")
    for source in (OPEN_STRETCHES, AFTERNOON_STRETCHES, FAN_STRETCHES):
        stretches.update(source)
    new_days, problems = {}, []
    for path in sorted(DATA_DIR.glob("*.json")):
        date = path.stem
        for item in json.loads(path.read_text()):
            name = f"{date} {item.get('label', item.get('scenario'))}"
            bad = validate(name, item)
            if name in stretches:
                bad.append(f"{name}: duplicate name")
            if bad:
                problems += bad
                continue
            stretches[name] = item
            if not item.get("uncertain"):
                new_days.setdefault(date, []).append(name)
    return stretches, new_days, problems


def score(values, stretches, names=None):
    """Squared error per group for a set of option values."""
    c = Coefficients(**values)
    totals = {g: 0.0 for g in TOLERANCE}
    for name, d in stretches.items():
        if d.get("uncertain") or (names is not None and name not in names):
            continue
        totals[group_of(d)] += sum((p - a) ** 2 for _, p, a in simulate(d, c))
    return totals


def objective(totals):
    return totals["closed"] + totals["open_day"] + NIGHT_WEIGHT * totals["night"]


def candidates(values):
    """Every combination of one step down, no change, or one step up, kept inside the bounds."""
    choices = []
    for option, (step, low, high) in TUNABLE.items():
        now = values[option]
        choices.append(sorted({round(min(high, max(low, now + k * step)), 4) for k in (-1, 0, 1)}))
    for combo in itertools.product(*choices):
        yield dict(zip(TUNABLE, combo))


def decide(deployed, stretches, new_days):
    """Returns (verdict, reasons, best_values, tables)."""
    values = deployed["values"]
    current = score(values, stretches)
    recent = {d: n for d, n in new_days.items() if d > deployed["last_change"]}
    recent_names = {n for names in recent.values() for n in names}
    def within_tolerance(totals):
        return all(totals[g] <= current[g] * (1 + allowed) + 0.05 for g, allowed in TOLERANCE.items())

    # The best change among those that leave no group worse than its tolerance allows.
    scored = ((v, score(v, stretches)) for v in candidates(values))
    best, proposed = min(((v, t) for v, t in scored if within_tolerance(t)),
                         key=lambda vt: objective(vt[1]))
    tables = dict(current=current, proposed=proposed)
    reasons = []
    if not deployed.get("cutover"):
        reasons.append("cut-over has not been recorded, so refinement is off")
    if len(recent) < MIN_NEW_DAYS:
        reasons.append(f"{len(recent)} new clean days since {deployed['last_change']}, need {MIN_NEW_DAYS}")
    if best == values:
        reasons.append("no neighbouring values score better")
    else:
        gain = 1 - objective(proposed) / objective(current)
        if gain < MIN_IMPROVEMENT:
            reasons.append(f"best change improves the objective by {gain:.1%}, need {MIN_IMPROVEMENT:.0%}")
        if recent_names:
            before = objective(score(values, stretches, recent_names))
            after = objective(score(best, stretches, recent_names))
            tables["recent"] = (before, after)
            if after > before:
                reasons.append(f"worse on the new days alone ({before:.1f} -> {after:.1f})")
    return ("HOLD" if reasons else "APPLY"), reasons, best, tables


def main(argv):
    deployed = json.loads(DEPLOYED.read_text())
    stretches, new_days, problems = load()
    verdict, reasons, best, tables = decide(deployed, stretches, new_days)
    if problems:
        verdict, reasons = "HOLD", ["data problems must be fixed first"] + reasons

    if len(argv) == 2 and argv[0] == "--record":
        if verdict != "APPLY":
            sys.exit("Refusing to record: the verdict is HOLD.")
        deployed["history"].append(dict(until=argv[1], values=deployed["values"]))
        deployed["values"], deployed["last_change"] = best, argv[1]
        DEPLOYED.write_text(json.dumps(deployed, indent=2) + "\n")
        print(f"Recorded new values as deployed from {argv[1]}.")
        return

    used = [d for d in stretches.values() if not d.get("uncertain")]
    print(f"{len(used)} stretches scored ({len(stretches) - len(used)} uncertain ones left out);"
          f" {len(new_days)} days recorded by the daily review.")
    for p in problems:
        print(f"DATA PROBLEM: {p}")
    print("\nSquared error by group (deployed values -> best bounded change):")
    for group in TOLERANCE:
        print(f"  {group:9} {tables['current'][group]:7.1f} -> {tables['proposed'][group]:7.1f}")
    print(f"  objective {objective(tables['current']):7.1f} -> {objective(tables['proposed']):7.1f}")
    changes = {k: (deployed["values"][k], v) for k, v in best.items() if v != deployed["values"][k]}
    print("\nBest bounded change:", changes or "none")
    print(f"\nVERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    if verdict == "APPLY":
        print("  Set these option values in Home Assistant, verify, then run --record with today's date:")
        print("  " + json.dumps(changes and {k: v[1] for k, v in changes.items()}))


if __name__ == "__main__":
    main(sys.argv[1:])
