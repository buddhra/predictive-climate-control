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
# Evidence needed since the last change (owner, 2026-11-25: blocks of a few hours instead of
# five whole days). A block is BLOCK_HOURS whole clean hours between DAY_START and DAY_END,
# cut back from the end of a stretch and replayed from the real temperature at its start.
BLOCK_HOURS = 3
DAY_START, DAY_END = 7, 21
MIN_NEW_BLOCKS = 8        # new blocks recorded since the last change...
MIN_NEW_DATES = 2         # ...from at least this many dates: one day is not a pattern
EVENING_FROM = 19         # a block ending at or after this hour is an evening block
SLACK = 0.05              # squared error a check may rise by before it counts as worse
# An option may move only when the new data exercises it.
VENT_SCENARIOS = {
    "skylight_vent_alpha": {"skylights_open"},
    "window_vent_alpha": {"skylights_and_windows", "skylights_windows_fan"},
}
SOLAR_OPTIONS = {"solar_floor", "solar_center_hour", "uv_coeff"}
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


def blocks_of(d):
    """Non-overlapping daytime blocks of one stretch, cut back from its end."""
    out, end, first = [], min(d["end"], DAY_END), max(d["start"], DAY_START)
    while end - BLOCK_HOURS >= first:
        out.append(dict(d, start=end - BLOCK_HOURS, end=end))
        end -= BLOCK_HOURS
    return out[::-1]


def block_error(block, values):
    return sum((p - a) ** 2 for _, p, a in simulate(block, Coefficients(**values)))


def movable(new_stretches, new_blocks):
    """The options the new data exercises; the others stay where they are."""
    def sunlit(b):
        return any(v > 0 for v in b.get("uv", [])[b["start"] - b["h0"]:b["end"] - b["h0"] + 1])
    options = set()
    if new_blocks:
        options |= {"alpha_outdoor", "alpha_mass_to_air"}
    if any(sunlit(b) for b in new_blocks):
        options |= SOLAR_OPTIONS
    scenarios = {d["scenario"] for d in new_stretches}
    options |= {o for o, needed in VENT_SCENARIOS.items() if scenarios & needed}
    return options


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


def candidates(values, options=TUNABLE):
    """Every combination of one step down, no change, or one step up, kept inside the bounds.
    Only the options named may move."""
    choices = []
    for option, (step, low, high) in TUNABLE.items():
        now = values[option]
        if option in options:
            choices.append(sorted({round(min(high, max(low, now + k * step)), 4) for k in (-1, 0, 1)}))
        else:
            choices.append([now])
    for combo in itertools.product(*choices):
        yield dict(zip(TUNABLE, combo))


def decide(deployed, stretches, new_days):
    """Returns (verdict, reasons, best_values, tables)."""
    values = deployed["values"]
    current = score(values, stretches)
    recent = {d: n for d, n in new_days.items() if d > deployed["last_change"]}
    new_stretches = [stretches[n] for names in recent.values() for n in names]
    blocks = [b for d in new_stretches for b in blocks_of(d)]
    dates = [d for d, names in recent.items() if any(blocks_of(stretches[n]) for n in names)]
    evening = [b for b in blocks if b["end"] >= EVENING_FROM]
    before = [block_error(b, values) for b in blocks]

    def new_data(v):
        """(error on the new blocks, on the evening ones, blocks better, blocks worse)."""
        after = [block_error(b, v) for b in blocks]
        return (sum(after), sum(e for b, e in zip(blocks, after) if b["end"] >= EVENING_FROM),
                sum(a < e - 1e-9 for a, e in zip(after, before)),
                sum(a > e + 1e-9 for a, e in zip(after, before)))
    base = new_data(values)

    def acceptable(v, totals):
        if v == values:
            return True
        if any(totals[g] > current[g] * (1 + allowed) + SLACK for g, allowed in TOLERANCE.items()):
            return False
        if not blocks:
            return True
        total, late, better, worse = new_data(v)
        return total <= base[0] + SLACK and late <= base[1] + SLACK and better > worse

    # The best change among those that move only exercised options, leave no group worse
    # than its tolerance allows, and hold up on the new blocks (evening ones included).
    scored = ((v, score(v, stretches)) for v in candidates(values, movable(new_stretches, blocks)))
    best, proposed = min(((v, t) for v, t in scored if acceptable(v, t)),
                         key=lambda vt: objective(vt[1]))
    tables = dict(current=current, proposed=proposed, blocks=len(blocks), dates=len(dates),
                  evening=len(evening), new_before=base, new_after=new_data(best))
    reasons = []
    if not deployed.get("cutover"):
        reasons.append("cut-over has not been recorded, so refinement is off")
    if len(blocks) < MIN_NEW_BLOCKS or len(dates) < MIN_NEW_DATES:
        reasons.append(f"{len(blocks)} new {BLOCK_HOURS}-hour blocks from {len(dates)} dates since"
                       f" {deployed['last_change']}, need {MIN_NEW_BLOCKS} from {MIN_NEW_DATES}")
    if best == values:
        reasons.append("no acceptable neighbouring values score better")
    else:
        gain = 1 - objective(proposed) / objective(current)
        if gain < MIN_IMPROVEMENT:
            reasons.append(f"best change improves the objective by {gain:.1%}, need {MIN_IMPROVEMENT:.0%}")
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
    t = tables
    print(f"\nNew since {deployed['last_change']}: {t['blocks']} {BLOCK_HOURS}-hour blocks from {t['dates']} dates"
          f" ({t['evening']} evening). Squared error on them {t['new_before'][0]:.2f} -> {t['new_after'][0]:.2f}"
          f" (evening {t['new_before'][1]:.2f} -> {t['new_after'][1]:.2f});"
          f" {t['new_after'][2]} blocks better, {t['new_after'][3]} worse.")
    print("\nBest bounded change:", changes or "none")
    print(f"\nVERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    if verdict == "APPLY":
        print("  Set these option values in Home Assistant, verify, then run --record with today's date:")
        print("  " + json.dumps(changes and {k: v[1] for k, v in changes.items()}))


if __name__ == "__main__":
    main(sys.argv[1:])
