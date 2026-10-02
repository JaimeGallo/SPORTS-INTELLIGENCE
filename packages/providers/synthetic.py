"""Deterministic synthetic league in football-data.co.uk CSV format (mock provider).

It exists to test the whole pipeline offline with a KNOWN data-generating process: team strengths drift
over time, goals are Poisson, corners are Negative Binomial, first-half counts are binomial thinnings of
full-time counts, and Over/Under 2.5 odds are derived from the true probability plus margin and noise.
Results on synthetic data say nothing about real football.
"""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np
from scipy import stats

from packages.common.config import CompetitionConfig
from packages.providers.base import (
    HistoricalMatchProvider,
    ProviderInfo,
    RawMatch,
    RawPayload,
    load_provider_info,
)
from packages.providers.football_data_csv import decode_csv, parse_rows, season_code

COLUMNS = [
    "Div",
    "Date",
    "Time",
    "HomeTeam",
    "AwayTeam",
    "FTHG",
    "FTAG",
    "HTHG",
    "HTAG",
    "HS",
    "AS",
    "HST",
    "AST",
    "HC",
    "AC",
    "P>2.5",
    "P<2.5",
    "Avg>2.5",
    "Avg<2.5",
    "PC>2.5",
    "PC<2.5",
]


@dataclass(frozen=True)
class SyntheticWorldParams:
    n_teams: int = 20
    goals_mu: float = 0.12  # log baseline goals per team
    goals_home: float = 0.22
    goals_team_sd: float = 0.28
    corners_mu: float = 1.55  # log baseline corners per team (~4.7)
    corners_home: float = 0.12
    corners_team_sd: float = 0.18
    corners_dispersion: float = 0.06  # NB: var = mu + d * mu^2
    season_drift_sd: float = 0.10  # strengths random-walk between seasons
    match_drift_sd: float = 0.01  # and slightly within a season
    first_half_goal_share: float = 0.44
    first_half_corner_share: float = 0.47
    pinnacle_margin: float = 0.025
    avg_margin: float = 0.06
    prematch_noise: float = 0.10  # logit noise of the market's pre-match estimate
    closing_noise: float = 0.05


def _price(p_over: float, margin: float, noise: float, rng: np.random.Generator) -> tuple[float, float]:
    logit = math.log(p_over / (1 - p_over)) + rng.normal(0.0, noise)
    q = 1 / (1 + math.exp(-logit))
    over, under = q * (1 + margin), (1 - q) * (1 + margin)
    return max(1.01, round(1 / over, 2)), max(1.01, round(1 / under, 2))


def generate_league_csv(
    competition: CompetitionConfig,
    seasons: list[str],
    *,
    seed: int,
    params: SyntheticWorldParams | None = None,
) -> dict[str, str]:
    """Return {season_label: csv_text} for consecutive seasons of one synthetic league."""
    p = params or SyntheticWorldParams()
    rng = np.random.default_rng(
        [seed, int(hashlib.sha256(competition.competition_key.encode()).hexdigest()[:8], 16)]
    )
    teams = [f"{competition.country} Team {chr(65 + i)}" for i in range(p.n_teams)]
    attack = rng.normal(0, p.goals_team_sd, p.n_teams)
    defence = rng.normal(0, p.goals_team_sd, p.n_teams)
    c_for = rng.normal(0, p.corners_team_sd, p.n_teams)
    c_against = rng.normal(0, p.corners_team_sd, p.n_teams)
    out: dict[str, str] = {}
    for season in seasons:
        start_year = int(season[:4])
        for arr in (attack, defence, c_for, c_against):
            arr += rng.normal(0, p.season_drift_sd, p.n_teams)
            arr -= arr.mean()
        fixtures = [(h, a) for h in range(p.n_teams) for a in range(p.n_teams) if h != a]
        rng.shuffle(fixtures)
        per_round = p.n_teams // 2
        first_day = date(start_year, 8, 10)
        has_time = start_year >= 2019
        buffer = io.StringIO()
        buffer.write(",".join(COLUMNS) + "\n")
        for index, (h, a) in enumerate(fixtures):
            round_no = index // per_round
            day = first_day + timedelta(days=7 * round_no + (index % 2))
            for arr in (attack, defence, c_for, c_against):
                arr += rng.normal(0, p.match_drift_sd / per_round, p.n_teams)
            lam_h = math.exp(p.goals_mu + p.goals_home + attack[h] - defence[a])
            lam_a = math.exp(p.goals_mu + attack[a] - defence[h])
            gh, ga = int(rng.poisson(lam_h)), int(rng.poisson(lam_a))
            hgh = int(rng.binomial(gh, p.first_half_goal_share))
            hga = int(rng.binomial(ga, p.first_half_goal_share))
            mu_ch = math.exp(p.corners_mu + p.corners_home + c_for[h] + c_against[a])
            mu_ca = math.exp(p.corners_mu + c_for[a] + c_against[h])
            ch, ca = (_nb_draw(mu, p.corners_dispersion, rng) for mu in (mu_ch, mu_ca))
            sh, sa = int(rng.poisson(4.5 * lam_h + 6)), int(rng.poisson(4.5 * lam_a + 6))
            sth, sta = int(rng.binomial(sh, 0.35)), int(rng.binomial(sa, 0.35))
            p_over = float(1 - stats.poisson.cdf(2, lam_h + lam_a))
            p_o, p_u = _price(p_over, p.pinnacle_margin, p.prematch_noise, rng)
            a_o, a_u = _price(p_over, p.avg_margin, p.prematch_noise, rng)
            c_o, c_u = _price(p_over, p.pinnacle_margin, p.closing_noise, rng)
            row = [
                competition.football_data_div or "SYN",
                day.strftime("%d/%m/%Y"),
                "15:00" if has_time else "",
                teams[h],
                teams[a],
                gh,
                ga,
                hgh,
                hga,
                sh,
                sa,
                sth,
                sta,
                ch,
                ca,
                p_o,
                p_u,
                a_o,
                a_u,
                *((c_o, c_u) if has_time else ("", "")),
            ]
            buffer.write(",".join(str(v) for v in row) + "\n")
        out[season] = buffer.getvalue()
    return out


def _nb_draw(mu: float, dispersion: float, rng: np.random.Generator) -> int:
    if dispersion <= 0:
        return int(rng.poisson(mu))
    shape = 1 / dispersion
    return int(rng.poisson(rng.gamma(shape, mu / shape)))


class SyntheticProvider(HistoricalMatchProvider):
    def __init__(self, seasons: list[str], *, seed: int = 7, params: SyntheticWorldParams | None = None):
        self.info: ProviderInfo = load_provider_info("synthetic")
        self._seasons = seasons
        self._seed = seed
        self._params = params
        self._cache: dict[str, dict[str, str]] = {}

    def fetch_season(self, competition: CompetitionConfig, season_label: str) -> RawPayload:
        key = competition.competition_key
        if key not in self._cache:
            self._cache[key] = generate_league_csv(
                competition, self._seasons, seed=self._seed, params=self._params
            )
        text = self._cache[key][season_label]
        return RawPayload(
            source_id=self.info.source_id,
            endpoint=f"synthetic://{key}/{season_code(season_label)}",
            params={"competition": key, "season": season_label, "seed": str(self._seed)},
            content=text.encode("utf-8"),
            fetched_at=datetime(2000, 1, 1, tzinfo=UTC),  # fixed: synthetic payloads are reproducible
        )

    def parse(self, payload: RawPayload, competition: CompetitionConfig, season_label: str) -> list[RawMatch]:
        return parse_rows(
            decode_csv(payload.content),
            source_id=self.info.source_id,
            competition_key=competition.competition_key,
            season_label=season_label,
            division=competition.football_data_div or "SYN",
        )
