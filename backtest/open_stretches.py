"""Clean open stretches (nights), pulled 2026-11-16 from Home Assistant hourly statistics.

Same layout as replay.py: `h0` is the clock hour of the first list element and hours
run on past midnight (hour 25 = 1am the next day). `scenario` is the configuration
that really held from `start` to `end`: skylights open, and for the window scenario
the bedroom window sensor open as well. Fan at 0 W and furnace idle throughout.
UV is zero at night, so only the outdoor temperature is recorded.
"""

OPEN_STRETCHES = {
    # Skylights open, all windows shut.
    "2026-11-01 night": dict(
        scenario="skylights_open", h0=18, start=19, end=30,
        out=[57.0, 55.5, 54.5, 52.75, 51.75, 50.5, 49.0, 47.0, 46.0, 45.0, 45.75, 46.0, 45.25, 45.75],
        mass=[71.8, 71.9, 71.9, 72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 71.9, 71.8],
        bed=[72.31, 72.17, 72.33, 72.51, 72.50, 72.49, 72.33, 72.20, 72.06, 71.88, 71.68, 71.48, 71.27, 70.52],
    ),
    "2026-11-08 night": dict(
        scenario="skylights_open", h0=17, start=19, end=30,
        out=[79.0, 71.0, 65.0, 59.0, 55.5, 54.25, 53.25, 53.0, 53.0, 53.0, 52.5, 51.75, 50.75, 50.0, 50.0],
        mass=[68.3, 68.6, 68.9, 69.2, 69.5, 69.7, 69.9, 70.1, 70.3, 70.4, 70.5, 70.6, 70.6, 70.6, 70.6],
        bed=[71.11, 71.52, 71.66, 71.86, 71.97, 72.12, 72.14, 72.06, 71.91, 71.70, 71.36, 71.08, 70.78, 70.46, 69.64],
    ),
    # Skylights open and the bedroom window open.
    "2026-11-07 night": dict(
        scenario="skylights_and_windows", h0=20, start=22, end=31,
        out=[59.75, 58.5, 56.75, 56.25, 57.0, 56.0, 54.0, 53.0, 50.75, 50.0, 50.0, 50.0, 54.0],
        mass=[67.8, 68.1, 68.4, 68.5, 68.5, 68.5, 68.4, 68.3, 68.1, 67.9, 67.6, 67.3, 67.0],
        bed=[71.01, 70.95, 70.24, 69.38, 68.61, 67.87, 67.19, 66.51, 65.87, 65.25, 64.69, 64.31, 64.84],
    ),
    "2026-11-09 night": dict(
        scenario="skylights_and_windows", h0=18, start=20, end=30,
        out=[64.5, 62.0, 58.75, 56.5, 54.5, 54.0, 54.0, 53.75, 52.75, 52.0, 52.0, 52.0, 52.0, 52.75],
        mass=[71.0, 71.1, 71.3, 71.4, 71.5, 71.5, 71.5, 71.4, 71.3, 71.1, 70.8, 70.5, 70.2, 69.7],
        bed=[72.09, 72.39, 72.63, 72.61, 72.14, 71.60, 70.85, 70.26, 69.47, 68.79, 68.04, 67.42, 66.27, 66.26],
    ),
    "2026-11-10 night": dict(
        scenario="skylights_and_windows", h0=19, start=20, end=29,
        out=[59.75, 56.75, 56.0, 54.0, 52.5, 50.75, 49.75, 49.0, 49.0, 49.0, 48.25],
        mass=[70.7, 71.0, 71.2, 71.3, 71.4, 71.4, 71.3, 71.1, 70.9, 70.6, 70.3],
        bed=[73.14, 73.15, 72.74, 72.14, 71.47, 70.76, 70.05, 69.27, 68.49, 67.65, 67.12],
    ),
    # The owner thinks the window may have been only cracked this night.
    "2026-11-13 night": dict(
        scenario="skylights_and_windows", h0=19, start=20, end=31, uncertain=True,
        out=[58.0, 56.5, 54.5, 54.0, 54.0, 54.0, 53.75, 52.75, 51.75, 50.5, 48.5, 46.75, 45.75],
        mass=[72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 72.0, 71.9, 71.8, 71.7, 71.6, 71.4, 71.2],
        bed=[72.52, 72.32, 72.29, 72.10, 71.86, 71.67, 71.38, 71.06, 70.79, 70.47, 70.18, 69.84, 69.36],
    ),
}
