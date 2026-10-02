"""Time-weighted team ratings for count data (Maher 1982 / Dixon-Coles 1997 style).

log E[home count] = mu + home_adv + att[home] - def[away]
log E[away count] = mu + att[away] - def[home]

Fitted by weighted Poisson maximum likelihood with weights exp(-xi * days_ago) and an L2 penalty on team
parameters (shrinks teams with little history towards the league average and makes the model identifiable).
The same ratings serve goals (FT, 1H) and corners; only the target columns change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import optimize, special

from packages.common.errors import ModelError


@dataclass(frozen=True)
class RatingsConfig:
    xi: float = 0.0019  # decay per day (half-life ln2/xi ~ 365 days)
    window_days: int = 730
    ridge: float = 2.0
    min_matches: int = 60  # below this the fit is refused (insufficient history)


@dataclass(frozen=True)
class TrainingData:
    home_idx: np.ndarray
    away_idx: np.ndarray
    y_home: np.ndarray
    y_away: np.ndarray
    weights: np.ndarray
    teams: tuple[str, ...]


def build_training_data(
    history: pd.DataFrame, home_col: str, away_col: str, as_of: datetime, cfg: RatingsConfig
) -> TrainingData:
    frame = history.dropna(subset=[home_col, away_col])
    days = (pd.Timestamp(as_of) - frame["kickoff_at"]).dt.total_seconds().to_numpy() / 86400.0
    keep = days <= cfg.window_days
    frame, days = frame.loc[keep], days[keep]
    teams = tuple(sorted(set(frame["home_team_id"]) | set(frame["away_team_id"])))
    index = {t: i for i, t in enumerate(teams)}
    return TrainingData(
        home_idx=frame["home_team_id"].map(index).to_numpy(dtype=int),
        away_idx=frame["away_team_id"].map(index).to_numpy(dtype=int),
        y_home=frame[home_col].to_numpy(dtype=float),
        y_away=frame[away_col].to_numpy(dtype=float),
        weights=np.exp(-cfg.xi * days),
        teams=teams,
    )


@dataclass
class TeamRatings:
    mu: float
    home: float
    attack: dict[str, float]
    defence: dict[str, float]
    n_matches: int
    effective_matches: float
    team_matches: dict[str, int] = field(default_factory=dict)
    in_sample_means: np.ndarray | None = None  # (n, 2) fitted means, used to estimate dispersion
    in_sample_y: np.ndarray | None = None
    in_sample_w: np.ndarray | None = None

    def lambdas(self, home_team: str, away_team: str) -> tuple[float, float]:
        att_h, def_h = self.attack.get(home_team, 0.0), self.defence.get(home_team, 0.0)
        att_a, def_a = self.attack.get(away_team, 0.0), self.defence.get(away_team, 0.0)
        return (
            math.exp(self.mu + self.home + att_h - def_a),
            math.exp(self.mu + att_a - def_h),
        )

    def known(self, team: str) -> bool:
        return team in self.attack


def fit_ratings(
    data: TrainingData, cfg: RatingsConfig, start: np.ndarray | None = None
) -> tuple[TeamRatings, np.ndarray]:
    n_teams, n = len(data.teams), len(data.y_home)
    if n < cfg.min_matches:
        raise ModelError(f"insufficient history: {n} matches < {cfg.min_matches}")
    h, a, yh, ya, w = data.home_idx, data.away_idx, data.y_home, data.y_away, data.weights

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        mu, home = theta[0], theta[1]
        att, dfn = theta[2 : 2 + n_teams], theta[2 + n_teams :]
        eta_h = mu + home + att[h] - dfn[a]
        eta_a = mu + att[a] - dfn[h]
        lam_h, lam_a = np.exp(eta_h), np.exp(eta_a)
        nll = float(np.sum(w * (lam_h - yh * eta_h)) + np.sum(w * (lam_a - ya * eta_a)))
        nll += 0.5 * cfg.ridge * float(att @ att + dfn @ dfn)
        g_h, g_a = w * (lam_h - yh), w * (lam_a - ya)
        grad = np.empty_like(theta)
        grad[0] = g_h.sum() + g_a.sum()
        grad[1] = g_h.sum()
        grad[2 : 2 + n_teams] = np.bincount(h, g_h, n_teams) + np.bincount(a, g_a, n_teams) + cfg.ridge * att
        grad[2 + n_teams :] = -np.bincount(a, g_h, n_teams) - np.bincount(h, g_a, n_teams) + cfg.ridge * dfn
        return nll, grad

    if start is None or len(start) != 2 + 2 * n_teams:
        mean = max(float(np.average(np.concatenate([yh, ya]), weights=np.concatenate([w, w]))), 1e-3)
        start = np.zeros(2 + 2 * n_teams)
        start[0] = math.log(mean)
    result = optimize.minimize(objective, start, jac=True, method="L-BFGS-B")
    if not result.success and not np.isfinite(result.fun):
        raise ModelError(f"ratings fit failed: {result.message}")
    theta = result.x
    att, dfn = theta[2 : 2 + n_teams], theta[2 + n_teams :]
    eta_h = theta[0] + theta[1] + att[h] - dfn[a]
    eta_a = theta[0] + att[a] - dfn[h]
    counts = np.bincount(np.concatenate([h, a]), minlength=n_teams)
    ratings = TeamRatings(
        mu=float(theta[0]),
        home=float(theta[1]),
        attack={t: float(att[i]) for i, t in enumerate(data.teams)},
        defence={t: float(dfn[i]) for i, t in enumerate(data.teams)},
        n_matches=n,
        effective_matches=float(w.sum()),
        team_matches={t: int(counts[i]) for i, t in enumerate(data.teams)},
        in_sample_means=np.column_stack([np.exp(eta_h), np.exp(eta_a)]),
        in_sample_y=np.column_stack([yh, ya]),
        in_sample_w=w,
    )
    return ratings, theta


def fit_dixon_coles_rho(ratings: TeamRatings, bound: float = 0.25) -> float:
    """Profile-likelihood estimate of rho given the fitted lambdas (two-stage approximation)."""
    assert (
        ratings.in_sample_means is not None
        and ratings.in_sample_y is not None
        and ratings.in_sample_w is not None
    )
    lam_h, lam_a = ratings.in_sample_means[:, 0], ratings.in_sample_means[:, 1]
    yh, ya, w = ratings.in_sample_y[:, 0], ratings.in_sample_y[:, 1], ratings.in_sample_w
    m00 = (yh == 0) & (ya == 0)
    m01 = (yh == 0) & (ya == 1)
    m10 = (yh == 1) & (ya == 0)
    m11 = (yh == 1) & (ya == 1)
    upper = min(bound, 0.999 / float(np.max(lam_h * lam_a)), 0.999)
    lower = max(-bound, -0.999 / float(np.max(np.maximum(lam_h, lam_a))))

    def nll(rho: float) -> float:
        tau = np.ones_like(lam_h)
        tau[m00] = 1 - lam_h[m00] * lam_a[m00] * rho
        tau[m01] = 1 + lam_h[m01] * rho
        tau[m10] = 1 + lam_a[m10] * rho
        tau[m11] = 1 - rho
        return -float(np.sum(w * np.log(np.clip(tau, 1e-12, None))))

    result = optimize.minimize_scalar(nll, bounds=(lower, upper), method="bounded")
    return float(result.x)


def fit_total_dispersion(ratings: TeamRatings, upper: float = 1.0) -> float:
    """Weighted MLE of the NB dispersion of the TOTAL count given the fitted means (Var = m + d m^2)."""
    assert (
        ratings.in_sample_means is not None
        and ratings.in_sample_y is not None
        and ratings.in_sample_w is not None
    )
    mean = ratings.in_sample_means.sum(axis=1)
    y = ratings.in_sample_y.sum(axis=1)
    w = ratings.in_sample_w

    def nll(log_d: float) -> float:
        d = math.exp(log_d)
        size = 1 / d
        ll = (
            special.gammaln(y + size)
            - special.gammaln(size)
            - special.gammaln(y + 1)
            + size * np.log(size / (size + mean))
            + y * np.log(mean / (size + mean))
        )
        return -float(np.sum(w * ll))

    result = optimize.minimize_scalar(nll, bounds=(math.log(1e-6), math.log(upper)), method="bounded")
    dispersion = math.exp(float(result.x))
    return 0.0 if dispersion < 1e-4 else dispersion
