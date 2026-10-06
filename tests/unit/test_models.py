"""Models recover a KNOWN data-generating process (synthetic league)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from packages.calibration import metrics as mt
from packages.common.errors import ModelError
from packages.features.store import FeatureStore
from packages.markets.catalog import Period, StatKey
from packages.models.count_models import Family, ModelSpec, fit_model
from packages.models.team_ratings import RatingsConfig
from tests.helpers import COMP, synthetic_facts


@pytest.fixture(scope="module")
def facts() -> pd.DataFrame:
    return synthetic_facts(["2017-2018", "2018-2019", "2019-2020"], seed=11)


def _as_of(facts: pd.DataFrame) -> datetime:
    return facts[facts["season_label"] == "2019-2020"]["kickoff_at"].min().to_pydatetime() - timedelta(
        hours=1
    )


def test_insufficient_history_is_refused(facts: pd.DataFrame) -> None:
    spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, Family.POISSON, RatingsConfig(min_matches=60))
    early = facts.iloc[:10]
    with pytest.raises(ModelError):
        fit_model(
            spec, early, early["kickoff_at"].max().to_pydatetime() + timedelta(days=1), COMP.competition_key
        )


def test_home_advantage_and_mean_are_recovered(facts: pd.DataFrame) -> None:
    as_of = _as_of(facts)
    view = FeatureStore(facts).history(COMP.competition_key, as_of)
    spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, Family.POISSON, RatingsConfig(xi=0.0, ridge=1.0))
    fitted = fit_model(spec, view.frame, as_of, COMP.competition_key)
    assert fitted.ratings is not None
    assert fitted.ratings.home == pytest.approx(0.22, abs=0.08)  # true home advantage in the generator


def test_negbin_detects_corner_overdispersion(facts: pd.DataFrame) -> None:
    as_of = _as_of(facts)
    view = FeatureStore(facts).history(COMP.competition_key, as_of)
    spec = ModelSpec(StatKey.CORNERS, Period.FULL_TIME, Family.NEGBIN, RatingsConfig(xi=0.0))
    fitted = fit_model(spec, view.frame, as_of, COMP.competition_key)
    assert fitted.dispersion > 0.005


def test_team_model_beats_league_baseline_on_next_season(facts: pd.DataFrame) -> None:
    as_of = _as_of(facts)
    view = FeatureStore(facts).history(COMP.competition_key, as_of)
    nxt = facts[facts["season_label"] == "2019-2020"].iloc[:190]
    y = ((nxt["goals_ft_home"] + nxt["goals_ft_away"]) > 2.5).to_numpy().astype(int)
    losses = {}
    for family in (Family.LEAGUE_FREQ, Family.POISSON):
        spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, family, RatingsConfig(xi=0.0019))
        fitted = fit_model(spec, view.frame, as_of, COMP.competition_key)
        p = np.array(
            [
                fitted.predict(h, a).distribution.prob_over(2.5)
                for h, a in zip(nxt["home_team_id"], nxt["away_team_id"], strict=True)
            ]
        )
        losses[family] = mt.log_loss(p, y)
    assert losses[Family.POISSON] < losses[Family.LEAGUE_FREQ]


def test_dixon_coles_survives_lopsided_fixture_with_extreme_rho(facts: pd.DataFrame) -> None:
    as_of = _as_of(facts)
    view = FeatureStore(facts).history(COMP.competition_key, as_of)
    spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, Family.DIXON_COLES, RatingsConfig())
    fitted = fit_model(spec, view.frame, as_of, COMP.competition_key)
    assert fitted.ratings is not None
    strong, weak = "strong", "weak"
    fitted.ratings.attack[strong], fitted.ratings.defence[strong] = 1.5, 0.0
    fitted.ratings.attack[weak], fitted.ratings.defence[weak] = 0.0, -0.4
    fitted.rho = -0.245  # the in-sample bound of a league whose largest fitted lambda was ~4.07
    lam_h, lam_a = fitted.ratings.lambdas(strong, weak)
    assert lam_h > 4.07 > lam_a
    prediction = fitted.predict(strong, weak)  # used to raise ModelError
    assert prediction.distribution.pmf.sum() == pytest.approx(1.0)
    assert prediction.features["rho"] == -0.245
    assert -0.245 < prediction.features["rho_used"] < 0


def test_prediction_is_pure(facts: pd.DataFrame) -> None:
    as_of = _as_of(facts)
    view = FeatureStore(facts).history(COMP.competition_key, as_of)
    spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, Family.DIXON_COLES, RatingsConfig())
    fitted = fit_model(spec, view.frame, as_of, COMP.competition_key)
    home, away = facts["home_team_id"].iloc[0], facts["away_team_id"].iloc[0]
    a, b = fitted.predict(home, away), fitted.predict(home, away)
    assert np.array_equal(a.distribution.pmf, b.distribution.pmf)
    assert a.features == b.features
