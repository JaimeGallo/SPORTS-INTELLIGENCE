"""Market models: each one turns point-in-time history into a COUNT DISTRIBUTION for one target
(stat, period). Over/Under probabilities for every line are derived from that single distribution.

Families:
- league_freq: recency-weighted empirical distribution of the league's totals (naive baseline, no teams);
- poisson:     team ratings, total ~ Poisson(lambda_home + lambda_away);
- dixon_coles: team ratings + low-score dependence (goals only);
- negbin:      team ratings, total ~ NegBin(mean, dispersion) (over-dispersed counts such as corners).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

from packages.common.errors import ModelError
from packages.features.store import target_columns
from packages.markets.catalog import Period, StatKey
from packages.models import distributions as dist
from packages.models.team_ratings import (
    RatingsConfig,
    TeamRatings,
    build_training_data,
    fit_dixon_coles_rho,
    fit_ratings,
    fit_total_dispersion,
)

MODEL_CODE_VERSION = "1"


class Family(StrEnum):
    LEAGUE_FREQ = "league_freq"
    POISSON = "poisson"
    DIXON_COLES = "dixon_coles"
    NEGBIN = "negbin"


@dataclass(frozen=True)
class ModelSpec:
    stat: StatKey
    period: Period
    family: Family
    ratings: RatingsConfig

    @property
    def model_version(self) -> str:
        r = self.ratings
        return (
            f"jevs-{self.stat.value}-{self.period.value.lower()}-{self.family.value}"
            f"-xi{r.xi:g}-w{r.window_days}-r{r.ridge:g}-v{MODEL_CODE_VERSION}"
        )

    @property
    def target(self) -> tuple[StatKey, Period]:
        return (self.stat, self.period)

    def hyperparameters(self) -> dict[str, Any]:
        return {"family": self.family.value, **self.ratings.__dict__}


@dataclass(frozen=True)
class Prediction:
    distribution: dist.CountDistribution
    features: dict[str, Any]


class FittedModel:
    """A model fitted at one `as_of`. `predict` is pure: same inputs, same output."""

    def __init__(
        self,
        spec: ModelSpec,
        as_of: datetime,
        *,
        ratings: TeamRatings | None = None,
        league: dist.CountDistribution | None = None,
        rho: float = 0.0,
        dispersion: float = 0.0,
        n_history: int = 0,
    ) -> None:
        self.spec = spec
        self.as_of = as_of
        self.ratings = ratings
        self.league = league
        self.rho = rho
        self.dispersion = dispersion
        self.n_history = n_history

    def predict(self, home_team: str, away_team: str) -> Prediction:
        family = self.spec.family
        if family is Family.LEAGUE_FREQ:
            assert self.league is not None
            return Prediction(
                self.league, {"n_history": self.n_history, "league_mean": round(self.league.mean, 4)}
            )
        assert self.ratings is not None
        lam_h, lam_a = self.ratings.lambdas(home_team, away_team)
        rho_used = self.rho
        if family is Family.POISSON:
            distribution = dist.poisson(lam_h + lam_a)
        elif family is Family.DIXON_COLES:
            low, high = dist.dixon_coles_rho_limits(lam_h, lam_a)
            rho_used = min(max(self.rho, low), high)
            distribution = dist.dixon_coles_total(lam_h, lam_a, rho_used)
        elif family is Family.NEGBIN:
            distribution = dist.negative_binomial(lam_h + lam_a, self.dispersion)
        else:  # pragma: no cover - exhaustive
            raise ModelError(f"unknown family {family}")
        r = self.ratings
        features = {
            "n_history": self.n_history,
            "effective_matches": round(r.effective_matches, 2),
            "home_known": r.known(home_team),
            "away_known": r.known(away_team),
            "home_team_matches": r.team_matches.get(home_team, 0),
            "away_team_matches": r.team_matches.get(away_team, 0),
            "mu": round(r.mu, 5),
            "home_adv": round(r.home, 5),
            "att_home": round(r.attack.get(home_team, 0.0), 5),
            "def_home": round(r.defence.get(home_team, 0.0), 5),
            "att_away": round(r.attack.get(away_team, 0.0), 5),
            "def_away": round(r.defence.get(away_team, 0.0), 5),
            "lambda_home": round(lam_h, 5),
            "lambda_away": round(lam_a, 5),
            "rho": round(self.rho, 5),
            "rho_used": round(rho_used, 5),
            "dispersion": round(self.dispersion, 5),
        }
        return Prediction(distribution, features)


class RatingsCache:
    """Shares ratings fits across families with the same target and ratings config at one as_of.

    Fits for the current as_of are all kept (families iterate over several ratings configs); they are dropped
    as soon as a later as_of is requested. The previous solution of the same configuration warm-starts the
    optimizer when the set of teams is unchanged.
    """

    def __init__(self) -> None:
        self._as_of: datetime | None = None
        self._fits: dict[tuple[Any, ...], TeamRatings] = {}
        self._warm: dict[tuple[Any, ...], tuple[tuple[str, ...], np.ndarray]] = {}

    def get(self, history: pd.DataFrame, spec: ModelSpec, as_of: datetime, competition: str) -> TeamRatings:
        if as_of != self._as_of:
            self._fits.clear()
            self._as_of = as_of
        key = (competition, spec.stat, spec.period, spec.ratings)
        if key not in self._fits:
            home_col, away_col = target_columns(spec.stat, spec.period)
            data = build_training_data(history, home_col, away_col, as_of, spec.ratings)
            start = None
            if key in self._warm and self._warm[key][0] == data.teams:
                start = self._warm[key][1]
            ratings, theta = fit_ratings(data, spec.ratings, start)
            self._warm[key] = (data.teams, theta)
            self._fits[key] = ratings
        return self._fits[key]


def fit_model(
    spec: ModelSpec,
    history: pd.DataFrame,
    as_of: datetime,
    competition: str,
    cache: RatingsCache | None = None,
) -> FittedModel:
    home_col, away_col = target_columns(spec.stat, spec.period)
    usable = history.dropna(subset=[home_col, away_col])
    if spec.family is Family.LEAGUE_FREQ:
        days = (pd.Timestamp(as_of) - usable["kickoff_at"]).dt.total_seconds().to_numpy() / 86400.0
        keep = days <= spec.ratings.window_days
        usable = usable.loc[keep]
        if len(usable) < spec.ratings.min_matches:
            raise ModelError(f"insufficient history: {len(usable)} matches")
        totals = (usable[home_col] + usable[away_col]).to_numpy()
        weights = np.exp(-spec.ratings.xi * days[keep])
        return FittedModel(spec, as_of, league=dist.empirical(totals, weights), n_history=len(usable))
    if spec.family is Family.DIXON_COLES and spec.stat is not StatKey.GOALS:
        raise ModelError("Dixon-Coles is only defined for goals")
    ratings = (cache or RatingsCache()).get(history, spec, as_of, competition)
    rho = fit_dixon_coles_rho(ratings) if spec.family is Family.DIXON_COLES else 0.0
    dispersion = fit_total_dispersion(ratings) if spec.family is Family.NEGBIN else 0.0
    return FittedModel(
        spec, as_of, ratings=ratings, rho=rho, dispersion=dispersion, n_history=ratings.n_matches
    )
