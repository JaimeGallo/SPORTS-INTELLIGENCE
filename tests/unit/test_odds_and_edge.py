from __future__ import annotations

import math

import pytest

from packages.common.errors import InvalidOdds
from packages.edge.engine import EdgeRules, SignalState, edge, expected_value, signal_state
from packages.odds import engine as oe


@pytest.mark.parametrize("bad", [1.0, 0.5, -2.0, math.nan, math.inf])
def test_invalid_decimal_odds_rejected(bad: float) -> None:
    with pytest.raises(InvalidOdds):
        oe.implied_probability(bad)


def test_conversions_round_trip() -> None:
    assert oe.american_to_decimal(150) == pytest.approx(2.5)
    assert oe.american_to_decimal(-200) == pytest.approx(1.5)
    assert oe.decimal_to_american(2.5) == pytest.approx(150)
    assert oe.decimal_to_american(1.5) == pytest.approx(-200)
    assert oe.fractional_to_decimal("5/2") == pytest.approx(3.5)
    with pytest.raises(InvalidOdds):
        oe.american_to_decimal(50)
    with pytest.raises(InvalidOdds):
        oe.fractional_to_decimal("abc")


@pytest.mark.parametrize("method", ["proportional", "power"])
def test_fair_probabilities_remove_margin(method: str) -> None:
    prices = [1.80, 2.05]
    assert oe.overround(prices) > 1
    fair = oe.fair_probabilities(prices, method)
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] > fair[1]


def test_edge_ev_and_signal_states_are_distinct() -> None:
    assert edge(0.72, 0.64) == pytest.approx(0.08)
    assert expected_value(0.5, 2.1) == pytest.approx(0.05)
    rules = EdgeRules(min_edge=0.03, min_history_matches=100, min_data_quality=0.9)
    common = {"history_matches": 500, "data_quality": 0.97, "rules": rules}
    assert signal_state(0.70, 0.62, 1.55, segment_validated=False, **common) is SignalState.POTENTIAL_EDGE
    assert signal_state(0.70, 0.62, 1.55, segment_validated=True, **common) is SignalState.VALIDATED_EDGE
    # positive edge but the available price gives negative EV -> no edge
    assert signal_state(0.70, 0.62, 1.40, segment_validated=True, **common) is SignalState.NO_EDGE
    low = {**common, "history_matches": 10}
    assert signal_state(0.90, 0.50, 3.0, segment_validated=True, **low) is SignalState.INSUFFICIENT_EVIDENCE
