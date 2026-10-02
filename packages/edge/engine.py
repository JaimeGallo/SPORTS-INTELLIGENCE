"""Edge Engine. Edge, expected value and signal state are DIFFERENT things:

- edge   = model probability - de-margined market probability (percentage points);
- EV     = model probability * (decimal odds - 1) - (1 - model probability), per unit staked, at the odds
           actually available (margin included);
- signal state is a documented rule on top of both, plus evidence requirements. It is never a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SignalState(StrEnum):
    NO_EDGE = "no_edge"
    POTENTIAL_EDGE = "potential_edge"
    VALIDATED_EDGE = "validated_edge"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class EdgeRules:
    min_edge: float = 0.03  # 3 percentage points
    min_ev: float = 0.0
    min_history_matches: int = 200  # model evidence for this league/market
    min_data_quality: float = 0.9


def edge(model_probability: float, market_probability: float) -> float:
    return model_probability - market_probability


def expected_value(model_probability: float, decimal_odds: float) -> float:
    return model_probability * (decimal_odds - 1) - (1 - model_probability)


def signal_state(
    model_probability: float,
    market_probability: float,
    decimal_odds: float,
    *,
    history_matches: int,
    data_quality: float,
    segment_validated: bool,
    rules: EdgeRules,
) -> SignalState:
    """VALIDATED only if the segment (league, market, line) showed out-of-sample value in a previous run."""
    if history_matches < rules.min_history_matches or data_quality < rules.min_data_quality:
        return SignalState.INSUFFICIENT_EVIDENCE
    e = edge(model_probability, market_probability)
    ev = expected_value(model_probability, decimal_odds)
    if e < rules.min_edge or ev <= rules.min_ev:
        return SignalState.NO_EDGE
    return SignalState.VALIDATED_EDGE if segment_validated else SignalState.POTENTIAL_EDGE
