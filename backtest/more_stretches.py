"""More clean closed stretches, pulled 2026-11-16 from Home Assistant hourly statistics.

Same format and caveats as STRETCHES in replay.py. `out`, `uv`, and `cloud` are
hourly means of the sensors that record the weather entity's current conditions.
Each stretch had skylights and all windows shut, the fan at 0 W, and the furnace idle.
Portable AC use is not recorded in history this far back for 2026-07-16; the owner
supplied that day's closed times.
"""

MORE_STRETCHES = {
    # Summer, clear, outside high 87 F. Closed 8:50am-5:42pm.
    "2026-07-16": dict(
        h0=7, start=9, end=17,
        out=[66.75, 71.0, 78.5, 84.0, 87.0, 86.25, 83.5, 82.0, 81.75, 80.5, 78.5, 76.5, 75.0, 72.0, 67.0],
        uv=[.075, .525, 1.6, 3.375, 5.7, 7.95, 9.475, 9.85, 8.95, 7.0, 4.625, 2.475, 1.2, .3, 0],
        cloud=[0] * 15,
        mass=[70.5, 70.3, 70.4, 70.6, 70.8, 71.1, 71.4, 71.7, 72.0, 72.4, 72.8, 73.1, 73.3, 73.4, 73.3],
        bed=[68.07, 70.21, 71.66, 72.47, 73.07, 73.68, 74.25, 74.84, 75.56, 75.95, 76.46, 75.41, 74.38, 73.22, 72.16],
    ),
    # Fall, overcast (57-98% cloud), outside high 73.5 F. Closed 12:05pm-5:06pm.
    "2026-10-20": dict(
        h0=11, start=13, end=17,
        out=[67.5, 71.0, 73.0, 73.5, 72.5, 72.0, 70.5],
        uv=[3.05, 4.3, 4.85, 4.5, 3.4, 2.0, .85],
        cloud=[.851, .953, .980, .945, .770, .656, .567],
        mass=[67.5, 67.6, 67.7, 67.9, 68.1, 68.4, 68.7],
        bed=[68.19, 68.78, 69.26, 69.86, 70.58, 71.22, 71.69],
    ),
    # Fall, clear, outside high 83 F. Closed 11:15am-5:47pm.
    "2026-11-08": dict(
        h0=10, start=12, end=17,
        out=[73.0, 77.5, 79.75, 82.25, 83.0, 83.0, 82.0, 79.0],
        uv=[2.4, 3.45, 3.925, 3.825, 3.025, 2.2, 1.0, .2],
        cloud=[0] * 8,
        mass=[66.9, 67.0, 67.1, 67.3, 67.5, 67.7, 68.0, 68.3],
        bed=[67.46, 68.01, 68.49, 68.91, 69.46, 70.10, 70.62, 71.11],
    ),
    # Fall, clear, outside high 82 F. Closed 12:36pm-4:30pm.
    "2026-11-09": dict(
        h0=11, start=13, end=16,
        out=[76.0, 80.5, 82.0, 81.25, 78.75, 76.0],
        uv=[2.8, 3.475, 3.175, 2.25, 1.175, .55],
        cloud=[0, .012, .004, 0, 0, .023],
        mass=[70.3, 70.3, 70.4, 70.5, 70.6, 70.7],
        bed=[69.96, 70.57, 70.92, 71.23, 71.68, 71.92],
    ),
    # Fall, clear, outside high 81 F. Closed 11:23am-5:15pm.
    "2026-11-11": dict(
        h0=10, start=12, end=17,
        out=[74.0, 80.25, 81.0, 80.5, 79.0, 77.5, 75.5, 69.0],
        uv=[2.025, 3.225, 3.925, 3.65, 2.7, 1.5, .375, .05],
        cloud=[0] * 8,
        mass=[69.6, 69.6, 69.7, 69.8, 69.9, 70.1, 70.3, 70.5],
        bed=[69.81, 70.31, 70.65, 71.05, 71.41, 71.81, 72.13, 72.55],
    ),
    # Fall, night, outside 53-56 F, mostly cloudy. Continues the 2026-11-15 stretch in
    # replay.py until the bedroom window opened at 10:04pm.
    "2026-11-15 evening": dict(
        h0=18, start=19, end=22,
        out=[58.5, 56.5, 54.5, 53.25, 53.0],
        uv=[0] * 5,
        cloud=[.98, .838, .772, .900, .906],
        mass=[70.6, 70.8, 70.9, 71.0, 71.1],
        bed=[72.13, 71.99, 72.08, 72.28, 72.25],
    ),
}
