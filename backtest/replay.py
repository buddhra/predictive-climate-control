"""Replay the closed-house forecast formula against recorded history.

Run:  python3 backtest/replay.py

Each stretch below is a period when the house was fully closed (skylights and
windows shut, fan off) and the furnace and AC were not running, so the "closed"
scenario is the one that applies. Data was pulled from Home Assistant hourly
statistics in November 2026.

Caveats on the data:
- `bed` holds hourly MEANS of the bedroom sensor. The temperature at the top of
  an hour is approximated as the average of the two adjacent hourly means.
- `out`, `uv`, and `cloud` are the weather entity's recorded current conditions
  for each hour, not the forecast the live model saw at the time.
- `mass` is the recorded hourly value of the thermal-mass lag sensor.
"""
import itertools

# h0 = clock hour of the first element in each list.
# start/end = first and last top-of-hour of the clean closed stretch.
STRETCHES = {
    "2026-11-07": dict(
        h0=10, start=12, end=21,
        out=[71.0, 77.0, 79.25, 80.75, 80.25, 77.75, 75.0, 69.0, 63.5, 61.0, 59.75, 58.5],
        uv=[1.8, 3.1, 3.85, 3.575, 2.5, 1.3, 0.6, 0.1, 0, 0, 0, 0],
        cloud=[0, 0, 0, 0, 0, 0, .31, .75, .92, .92, .88, .88],
        mass=[64.4, 64.6, 64.9, 65.2, 65.5, 65.9, 66.3, 66.7, 67.1, 67.5, 67.8, 68.1],
        bed=[65.53, 66.74, 67.54, 68.20, 68.82, 69.42, 69.93, 70.31, 70.58, 70.83, 71.01, 70.95],
    ),
    "2026-11-10": dict(
        h0=10, start=11, end=19,
        out=[70, 75, 78.5, 80.5, 82, 81.5, 79, 72.5, 63.5, 59.75],
        uv=[1.7, 2.9, 3.82, 3.73, 2.93, 1.5, .55, .1, 0, 0],
        cloud=[0] * 10,
        mass=[69.3, 69.4, 69.5, 69.6, 69.7, 69.9, 70.1, 70.3, 70.5, 70.7],
        bed=[69.44, 69.90, 70.31, 70.70, 71.17, 71.69, 72.17, 72.51, 72.81, 73.14, 73.15],
    ),
    "2026-11-15": dict(
        h0=9, start=15, end=19,
        out=[58.5, 64, 66.5, 67.75, 68, 67.25, 66.25, 64.5, 61, 58.5, 56.5],
        uv=[1.35, 2.42, 3.37, 3.67, 3.25, 2.28, 1.18, .38, .05, 0, 0],
        cloud=[.68, .57, .63, .87, .97, .99, .99, .98, .98, .98, .84],
        mass=[69.6, 69.6, 69.6, 69.6, 69.7, 69.9, 70.1, 70.2, 70.4, 70.6, 70.8],
        bed=[None] * 5 + [71.41, 71.60, 71.70, 71.88, 72.13, 71.99],
    ),
}

# The formula as deployed in the Home Assistant template sensors (closed scenario).
CURRENT = dict(alpha_o=0.05, solar_floor=0.7, solar_center=11, solar_width=6,
               uv_coeff=0.13, alpha_ma=0.05, alpha_am=0.10)


def actual_at(d, hour):
    """Approximate bedroom temperature at the top of `hour`."""
    i = hour - d["h0"]
    return (d["bed"][i - 1] + d["bed"][i]) / 2


def simulate(d, alpha_o, solar_floor, solar_center, solar_width, uv_coeff, alpha_ma, alpha_am):
    """Free-run the model from the stretch start. Returns [(hour, predicted, actual)]."""
    hour = d["start"]
    air = actual_at(d, hour)
    mass = d["mass"][hour - d["h0"]]
    rows = []
    while hour < d["end"]:
        i = hour - d["h0"]
        solar = max(uv_coeff * d["uv"][i] * (1 - d["cloud"][i]),
                    solar_floor * max(0, 1 - abs(hour - solar_center) / solar_width))
        new_air = air + alpha_o * (d["out"][i] - air) + alpha_ma * (mass - air) + solar
        mass = mass + alpha_am * (air - mass)
        air = new_air
        hour += 1
        rows.append((hour, air, actual_at(d, hour)))
    return rows


def sse(params):
    return sum((p - a) ** 2 for d in STRETCHES.values() for _, p, a in simulate(d, **params))


def show(label, params):
    print(f"\n{label}: {params}")
    for name, d in STRETCHES.items():
        rows = simulate(d, **params)
        print(f"  {name}  " + "  ".join(f"{h}:00 {p:.1f}/{a:.1f}" for h, p, a in rows))
        print(f"  {'':10}  end miss {rows[-1][1] - rows[-1][2]:+.1f} F")
    print(f"  total squared error {sse(params):.1f}")


if __name__ == "__main__":
    print("Columns are predicted/actual bedroom temperature in F.")
    show("Current formula", CURRENT)

    print("\nChanging only the outdoor rate (alpha_o):")
    for ao in (.05, .04, .03, .02, .015, .01):
        p = dict(CURRENT, alpha_o=ao)
        ends = [round(simulate(d, **p)[-1][1] - simulate(d, **p)[-1][2], 1) for d in STRETCHES.values()]
        print(f"  alpha_o={ao:<5}  squared error {sse(p):5.1f}  end misses {ends}")

    grid = itertools.product([0, .005, .01, .015, .02, .03, .04, .05],   # alpha_o
                             [.3, .4, .5, .6, .7, .8, 1.0],               # solar_floor
                             [11, 12, 13, 14],                            # solar_center
                             [0, .025, .05])                              # alpha_ma
    scored = sorted((sse(dict(CURRENT, alpha_o=ao, solar_floor=fl, solar_center=c, alpha_ma=ma)),
                     ao, fl, c, ma) for ao, fl, c, ma in grid)
    print("\nBest grid fits (squared error, alpha_o, solar_floor, solar_center, alpha_ma):")
    for row in scored[:5]:
        print("  ", [round(x, 3) for x in row])
    _, ao, fl, c, ma = scored[0]
    show("Best candidate (hypothesis only, 3 days of data)",
         dict(CURRENT, alpha_o=ao, solar_floor=fl, solar_center=c, alpha_ma=ma))
