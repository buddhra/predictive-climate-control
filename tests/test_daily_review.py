"""The daily review's evidence gate: blocks of a few hours instead of whole days."""
from backtest import daily_review as dr

VALUES = {"alpha_outdoor": 0.01, "alpha_mass_to_air": 0.0, "solar_floor": 0.4,
          "solar_center_hour": 16, "uv_coeff": 0.1, "skylight_vent_alpha": 0.0,
          "window_vent_alpha": 0.03}


def stretch(scenario="closed", h0=0, start=1, end=20, uv=1.0):
    n = end - h0 + 1
    return {"scenario": scenario, "h0": h0, "start": start, "end": end,
            "bed": [65.0] * n, "mass": [65.0] * n, "out": [55.0] * n,
            "uv": [uv] * n, "cloud": [0.5] * n, "fan": [0.0] * n}


def test_blocks_are_cut_back_from_the_end_inside_the_day():
    assert [(b["start"], b["end"]) for b in dr.blocks_of(stretch())] == [(8, 11), (11, 14), (14, 17), (17, 20)]
    # an overnight stretch gives none, and neither does one shorter than a block
    assert dr.blocks_of(stretch(h0=20, start=21, end=25)) == []
    assert dr.blocks_of(stretch(h0=16, start=17, end=19)) == []
    # hours after DAY_END are not used
    assert [(b["start"], b["end"]) for b in dr.blocks_of(stretch(h0=14, start=15, end=23))] == [(15, 18), (18, 21)]


def test_only_exercised_options_may_move():
    closed = stretch()
    assert dr.movable([closed], dr.blocks_of(closed)) == {
        "alpha_outdoor", "alpha_mass_to_air", "solar_floor", "solar_center_hour", "uv_coeff"}
    dark = stretch(uv=0)
    assert dr.movable([dark], dr.blocks_of(dark)) == {"alpha_outdoor", "alpha_mass_to_air"}
    night_open = stretch("skylights_and_windows", h0=20, start=21, end=27)
    assert dr.movable([night_open], []) == {"window_vent_alpha"}
    assert dr.movable([stretch("skylights_open")], []) == {"skylight_vent_alpha"}
    assert dr.movable([], []) == set()
    for v in dr.candidates(VALUES, {"alpha_outdoor"}):
        assert {k for k in v if v[k] != VALUES[k]} <= {"alpha_outdoor"}


def decide(dates):
    stretches = {f"{d} closed day": stretch() for d in dates}
    stretches["old"] = stretch()
    new_days = {d: [f"{d} closed day"] for d in dates}
    deployed = {"cutover": True, "last_change": "2026-01-01", "values": dict(VALUES)}
    return dr.decide(deployed, stretches, new_days)


def test_one_day_is_never_enough():
    verdict, reasons, _, tables = decide(["2026-01-02"])
    assert verdict == "HOLD" and tables["blocks"] == 4 and tables["dates"] == 1
    assert any("need 8 from 2" in r for r in reasons)


def test_two_closed_days_meet_the_evidence_gate():
    verdict, reasons, best, tables = decide(["2026-01-02", "2026-01-03"])
    assert tables["blocks"] == 8 and tables["dates"] == 2 and tables["evening"] == 2
    assert not any("need 8 from 2" in r for r in reasons)
    # no vent option moves on closed data, and a change must hold up on the new blocks
    assert best["skylight_vent_alpha"] == 0.0 and best["window_vent_alpha"] == 0.03
    if best != VALUES:
        assert verdict == "APPLY"
        assert tables["new_after"][0] <= tables["new_before"][0] + dr.SLACK
        assert tables["new_after"][1] <= tables["new_before"][1] + dr.SLACK
        assert tables["new_after"][2] > tables["new_after"][3]


def test_days_before_the_last_change_do_not_count():
    verdict, _, best, tables = decide(["2025-12-30", "2025-12-31"])
    assert verdict == "HOLD" and tables["blocks"] == 0 and best == VALUES
