from __future__ import annotations

import itertools

import numpy as np
import pytest
from scipy import stats

from packages.markets.catalog import Outcome, Selection, load_markets, settle_total
from packages.models import distributions as dist


def test_catalog_loads_mvp_markets() -> None:
    markets = load_markets()
    assert markets["corners_ft_total"].lines == (7.5, 8.5, 9.5, 10.5, 11.5)
    assert markets["goals_1h_total"].lines == (0.5, 1.5)


def test_settlement_rules() -> None:
    assert settle_total(3, 2.5, Selection.OVER) is Outcome.HIT
    assert settle_total(2, 2.5, Selection.OVER) is Outcome.MISS
    assert settle_total(2, 2.5, Selection.UNDER) is Outcome.HIT
    assert settle_total(10, 10.0, Selection.OVER) is Outcome.PUSH
    assert settle_total(None, 9.5, Selection.OVER) is Outcome.VOID


def test_poisson_over_matches_closed_form() -> None:
    d = dist.poisson(2.7)
    assert d.prob_over(2.5) == pytest.approx(1 - stats.poisson.cdf(2, 2.7), abs=1e-9)
    assert d.prob_over(2.5) + d.prob_under(2.5) == pytest.approx(1.0)
    assert d.mean == pytest.approx(2.7, abs=1e-6)


def test_lines_are_coherent() -> None:
    d = dist.negative_binomial(10.2, 0.05)
    probs = [d.prob_over(line) for line in (7.5, 8.5, 9.5, 10.5, 11.5)]
    assert all(a >= b for a, b in itertools.pairwise(probs))


def test_integer_line_excludes_push() -> None:
    d = dist.poisson(10.0)
    assert d.prob_over(10.0) + d.prob_under(10.0) + d.pmf[10] == pytest.approx(1.0)


def test_dixon_coles_with_zero_rho_is_poisson_total() -> None:
    dc = dist.dixon_coles_total(1.5, 1.1, 0.0)
    po = dist.poisson(2.6)
    assert dc.prob_over(2.5) == pytest.approx(po.prob_over(2.5), abs=1e-6)
    # negative rho (the usual estimate) moves mass towards 0-0 and 1-1
    assert dist.dixon_coles_total(1.5, 1.1, -0.1).pmf[0] > dc.pmf[0]


def test_negative_binomial_is_overdispersed_and_tends_to_poisson() -> None:
    nb = dist.negative_binomial(10.0, 0.1)
    var = float(np.dot((np.arange(len(nb.pmf)) - nb.mean) ** 2, nb.pmf))
    assert var == pytest.approx(10.0 + 0.1 * 100, rel=0.02)
    assert dist.negative_binomial(10.0, 0.0).prob_over(9.5) == pytest.approx(
        dist.poisson(10.0).prob_over(9.5)
    )


def test_empirical_is_a_valid_distribution() -> None:
    d = dist.empirical(np.array([0, 1, 1, 2, 3, 5]))
    assert d.pmf.sum() == pytest.approx(1.0)
    assert 0 < d.prob_over(2.5) < 1
