"""The backtest numbers quoted in docs/findings-2026-11-16.md. Needs only pytest."""
import pytest

from backtest import evaluate, evaluate_open
from custom_components.predictive_climate_control.model import Coefficients


def test_closed_stretches():
    assert len(evaluate.ALL) == 9
    assert round(evaluate.sse(evaluate.CURRENT, evaluate.ALL), 1) == 109.0
    assert round(evaluate.sse(evaluate.CANDIDATE, evaluate.ALL), 1) == 21.3
    assert round(evaluate.sse(evaluate.REFIT, evaluate.ALL), 1) == 9.3


def test_replay_and_integration_models_agree_on_the_refit():
    """evaluate.py uses replay.py's simulation; the integration's model must give the same curve."""
    from tests.test_model import _closed_curve  # same stretch format
    from backtest import replay
    d = evaluate.ALL["2026-07-16"]
    expected = [p for _, p, _ in replay.simulate(d, **evaluate.REFIT)]
    start = d["start"]
    from custom_components.predictive_climate_control import model
    hours = [model.ForecastHour(d["out"][h - d["h0"]], d["cloud"][h - d["h0"]], d["uv"][h - d["h0"]], h)
             for h in range(start, d["end"])]
    got = model.simulate(model.CLOSED, replay.actual_at(d, start), d["mass"][start - d["h0"]], hours,
                         Coefficients(**evaluate_open.REFIT_BASE))
    assert got == pytest.approx(expected, abs=1e-9)
    assert _closed_curve(d) != pytest.approx(expected, abs=0.5)  # and it differs from the deployed formula


@pytest.mark.parametrize("group, current, proposed", [
    ("Afternoon and evening (to 9pm or 10pm)", 118.8, 13.9),
    ("Nights", 868.3, 169.7),
    ("Fan nights", 57.2, 34.0),
])
def test_open_stretches(group, current, proposed):
    stretches = evaluate_open.GROUPS[group]
    assert round(evaluate_open.sse(Coefficients(), stretches), 1) == current
    assert round(evaluate_open.sse(Coefficients(**evaluate_open.PROPOSED), stretches), 1) == proposed
