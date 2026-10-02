"""Build MatchFacts frames in memory (no database) from the synthetic provider, using the SAME point-in-time
rules as the ingestion engine."""

from __future__ import annotations

from typing import Any

import pandas as pd

from packages.common.config import AppConfig, CompetitionConfig
from packages.common.ids import canonical_id
from packages.data_quality.engine import check_matches
from packages.ingestion.engine import HistoricalDataEngine
from packages.providers.base import Side
from packages.providers.synthetic import SyntheticProvider

COMP = CompetitionConfig(
    competition_key="SYN-1", name="Synthetic League", country="SYN", football_data_div="S1"
)


def synthetic_facts(seasons: list[str], seed: int = 3) -> pd.DataFrame:
    app = AppConfig(competitions=[COMP])
    rules = HistoricalDataEngine(None, app)  # type: ignore[arg-type]  # only the time rules are used
    provider = SyntheticProvider(seasons, seed=seed)
    rows: list[dict[str, Any]] = []
    for season in seasons:
        payload = provider.fetch_season(COMP, season)
        for m in check_matches(provider.parse(payload, COMP, season)).matches:
            kickoff, known = rules.kickoff_utc(m.local_date, m.local_time)
            home, away = canonical_id("team", "SYN", m.home_team), canonical_id("team", "SYN", m.away_team)
            row: dict[str, Any] = {
                "match_id": canonical_id("match", home, away, m.local_date.isoformat()),
                "competition_key": COMP.competition_key,
                "season_label": season,
                "kickoff_at": pd.Timestamp(kickoff),
                "kickoff_time_known": known,
                "home_team_id": home,
                "away_team_id": away,
                "available_at": pd.Timestamp(rules.result_available_at(kickoff)),
            }
            for (stat, period, side), value in m.stats.items():
                row[f"{stat}_{period.value.lower()}_{'home' if side is Side.HOME else 'away'}"] = value
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["kickoff_at", "match_id"]).reset_index(drop=True)
