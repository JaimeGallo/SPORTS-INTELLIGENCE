"""Leakage tests: predictions must be a function of information available at `as_of` only."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from packages.backtesting.walk_forward import generate_predictions
from packages.common.errors import LeakageError
from packages.features.store import FeatureStore, HistoryView, assert_no_leakage
from packages.markets.catalog import Period, StatKey, load_markets
from packages.models.count_models import Family, ModelSpec
from packages.models.team_ratings import RatingsConfig
from tests.helpers import COMP, synthetic_facts

SEASONS = ["2018-2019", "2019-2020"]


@pytest.fixture(scope="module")
def facts() -> pd.DataFrame:
    return synthetic_facts(SEASONS)


def test_history_only_contains_known_matches(facts: pd.DataFrame) -> None:
    store = FeatureStore(facts)
    as_of = facts["kickoff_at"].iloc[200].to_pydatetime() - timedelta(hours=1)
    view = store.history(COMP.competition_key, as_of)
    assert len(view.frame) > 0
    assert (view.frame["available_at"] <= pd.Timestamp(as_of)).all()
    assert (view.frame["kickoff_at"] < pd.Timestamp(as_of)).all()
    assert view.max_available_at is not None and view.max_available_at <= as_of


def test_injected_future_row_is_detected(facts: pd.DataFrame) -> None:
    as_of = facts["kickoff_at"].iloc[200].to_pydatetime()
    leaky = facts.iloc[:250]  # contains matches after as_of
    with pytest.raises(LeakageError):
        assert_no_leakage(HistoryView(COMP.competition_key, as_of, leaky, None))


def test_match_being_predicted_is_never_in_its_own_history(facts: pd.DataFrame) -> None:
    store = FeatureStore(facts)
    target = facts.iloc[300]
    view = store.history(COMP.competition_key, target["kickoff_at"].to_pydatetime() - timedelta(hours=1))
    assert target["match_id"] not in set(view.frame["match_id"])


@pytest.mark.parametrize("family", [Family.POISSON, Family.LEAGUE_FREQ])
def test_predictions_are_invariant_to_future_data(facts: pd.DataFrame, family: Family) -> None:
    """Corrupt every result after a cutoff: predictions made before the cutoff must not change at all."""
    spec = ModelSpec(StatKey.GOALS, Period.FULL_TIME, family, RatingsConfig(min_matches=60))
    markets = [load_markets()["goals_ft_total"]]
    cutoff = pd.Timestamp("2019-12-01", tz="UTC")
    corrupted = facts.copy()
    future = corrupted["kickoff_at"] >= cutoff
    corrupted.loc[future, ["goals_ft_home", "goals_ft_away"]] = 9

    def predict(frame: pd.DataFrame) -> pd.DataFrame:
        result = generate_predictions(
            frame,
            FeatureStore(frame),
            [spec],
            markets,
            competitions=[COMP.competition_key],
            seasons=["2019-2020"],
            lead_minutes=60,
        )
        before = result.predictions[result.predictions["kickoff_at"] < cutoff]
        return before.sort_values(["match_id", "line"]).reset_index(drop=True)

    clean, dirty = predict(facts), predict(corrupted)
    assert len(clean) > 100
    pd.testing.assert_series_equal(clean["p_raw"], dirty["p_raw"])


def test_every_snapshot_respects_as_of(facts: pd.DataFrame) -> None:
    spec = ModelSpec(StatKey.CORNERS, Period.FULL_TIME, Family.NEGBIN, RatingsConfig(min_matches=60))
    result = generate_predictions(
        facts,
        FeatureStore(facts),
        [spec],
        [load_markets()["corners_ft_total"]],
        competitions=[COMP.competition_key],
        seasons=["2019-2020"],
        lead_minutes=60,
    )
    snaps = result.snapshots
    assert len(snaps) > 300
    assert (snaps["max_available_at"] <= snaps["as_of"]).all()
    assert (snaps["fit_as_of"] <= snaps["as_of"]).all()
