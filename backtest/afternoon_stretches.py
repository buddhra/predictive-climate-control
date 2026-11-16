"""Clean open stretches in the afternoon and evening, and fan nights.

Built from the raw pulls in afternoon_raw.py. `scenario` is the configuration that
really held from `start` to `end`, taken from the skylight, window and fan history.
Hours run on past midnight (24 = midnight). Furnace idle throughout.

`uncertain` marks stretches where the owner thinks the bedroom window may have been
only cracked (it stayed in one position from the evening of Nov 13 to the morning of
Nov 15). They are reported but never used for fitting.
"""
from backtest.afternoon_raw import RAW


def _stretch(key, scenario, start, end, **extra):
    return dict(RAW[key], scenario=scenario, start=start, end=end, **extra)


AFTERNOON_STRETCHES = {
    # Skylights open, all windows shut, fan off.
    "2026-10-21 day": _stretch("2026-10-21", "skylights_open", 13, 21),
    "2026-10-22 day": _stretch("2026-10-22", "skylights_open", 13, 20),
    "2026-11-01 day": _stretch("2026-11-01", "skylights_open", 13, 18),
    "2026-11-12 day": _stretch("2026-11-12", "skylights_open", 13, 19),
    "2026-11-13 day": _stretch("2026-11-13", "skylights_open", 13, 19),
    # Skylights and bedroom window open, fan off.
    "2026-10-27 eve": _stretch("2026-10-27", "skylights_and_windows", 17, 21),
    "2026-10-29 day": _stretch("2026-10-29", "skylights_and_windows", 13, 21),
    "2026-11-14 day": _stretch("2026-11-14", "skylights_and_windows", 13, 22, uncertain=True),
}

FAN_STRETCHES = {
    # Skylights and bedroom window open, fan running at about 35 W.
    "2026-10-29 fan": _stretch("2026-10-29 fan", "skylights_windows_fan", 22, 31),
    "2026-11-02 fan": _stretch("2026-11-02 fan", "skylights_windows_fan", 24, 28),
}
