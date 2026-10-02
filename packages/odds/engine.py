"""Odds Engine: format conversion, implied probability and margin removal.

Internally everything is decimal odds. The raw implied probability (1/odds) includes the bookmaker margin
and is NOT a probability estimate; `fair_probabilities` removes the margin.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction

from scipy import optimize

from packages.common.errors import InvalidOdds


def validate_decimal(odds: float) -> float:
    if not isinstance(odds, int | float) or not math.isfinite(odds) or odds <= 1.0:
        raise InvalidOdds(f"invalid decimal odds {odds!r}")
    return float(odds)


def american_to_decimal(american: float) -> float:
    if not math.isfinite(american) or -100 < american < 100:
        raise InvalidOdds(f"invalid American odds {american!r}")
    return 1 + (american / 100 if american > 0 else 100 / -american)


def decimal_to_american(decimal: float) -> float:
    decimal = validate_decimal(decimal)
    return (decimal - 1) * 100 if decimal >= 2 else -100 / (decimal - 1)


def fractional_to_decimal(fractional: str) -> float:
    try:
        value = Fraction(fractional.strip())
    except (ValueError, ZeroDivisionError) as exc:
        raise InvalidOdds(f"invalid fractional odds {fractional!r}") from exc
    if value <= 0:
        raise InvalidOdds(f"invalid fractional odds {fractional!r}")
    return 1 + float(value)


def implied_probability(decimal: float) -> float:
    return 1 / validate_decimal(decimal)


def overround(prices: Sequence[float]) -> float:
    return sum(implied_probability(p) for p in prices)


def fair_probabilities(prices: Sequence[float], method: str = "proportional") -> list[float]:
    """Remove the margin from a complete set of mutually exclusive outcomes.

    - proportional: q_i = (1/o_i) / sum_j (1/o_j)  (the simple, standard normalisation);
    - power:        q_i = (1/o_i)^k with k solving sum q_i = 1 (accounts for favourite/longshot bias).
    """
    raw = [implied_probability(p) for p in prices]
    if len(raw) < 2:
        raise InvalidOdds("margin removal needs every outcome of the market")
    total = sum(raw)
    if method == "proportional":
        return [r / total for r in raw]
    if method == "power":
        if abs(total - 1) < 1e-12:
            return raw
        k = optimize.brentq(lambda k: sum(r**k for r in raw) - 1, 0.2, 5.0)
        return [r**k for r in raw]
    raise ValueError(f"unknown margin removal method {method!r}")


def fair_odds(probability: float) -> float:
    if not 0 < probability <= 1:
        raise ValueError(f"probability out of range: {probability}")
    return 1 / probability
