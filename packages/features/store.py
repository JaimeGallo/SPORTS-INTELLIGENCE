"""Point-in-time Feature Store (ADR-0003).

`MatchFacts` holds one row per match with its counts and the time at which they became knowable
(`available_at`). The FeatureStore is the ONLY way models see history: `history(competition, as_of)` returns
matches with `available_at <= as_of`, and every snapshot records `max_available_at`, which must not exceed
`as_of` (LeakageError otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import Engine, select

from packages.common.clock import ensure_utc
from packages.common.errors import DataError, LeakageError
from packages.markets.catalog import Period, StatKey
from packages.storage import schema as s

FEATURE_VERSION = "team-history/1"


def target_columns(stat: StatKey, period: Period) -> tuple[str, str]:
    base = f"{stat.value}_{period.value.lower()}"
    return f"{base}_home", f"{base}_away"


def load_match_facts(engine: Engine, competition_keys: list[str], source_id: str) -> pd.DataFrame:
    """Load finished matches with their counts from ONE source, one row per match, sorted by kickoff.

    Filtering by source keeps synthetic and real data apart even if they share a database.
    """
    m, se, c, st = s.matches, s.seasons, s.competitions, s.match_statistics
    with engine.connect() as conn:
        matches = pd.DataFrame(
            conn.execute(
                select(
                    m.c.match_id,
                    c.c.competition_key,
                    se.c.label.label("season_label"),
                    m.c.kickoff_at,
                    m.c.kickoff_time_known,
                    m.c.home_team_id,
                    m.c.away_team_id,
                )
                .join(se, se.c.season_id == m.c.season_id)
                .join(c, c.c.competition_id == se.c.competition_id)
                .where(c.c.competition_key.in_(competition_keys))
            ).all()
        )
        if matches.empty:
            return matches
        stats = pd.DataFrame(
            conn.execute(
                select(
                    st.c.match_id, st.c.team_id, st.c.period, st.c.stat_key, st.c.value, st.c.available_at
                ).where(
                    st.c.source_id == source_id,
                    st.c.match_id.in_(
                        select(m.c.match_id)
                        .join(se, se.c.season_id == m.c.season_id)
                        .join(c, c.c.competition_id == se.c.competition_id)
                        .where(c.c.competition_key.in_(competition_keys))
                    ),
                )
            ).all()
        )
    if stats.empty:
        return matches.iloc[0:0]
    matches = matches[matches["match_id"].isin(set(stats["match_id"]))]
    if stats.duplicated(["match_id", "team_id", "period", "stat_key"]).any():
        # Several sources/corrections for the same fact: needs source reconciliation (later phase).
        raise DataError("multiple versions of a statistic found; reconciliation is not implemented yet")
    stats = stats.merge(matches[["match_id", "home_team_id"]], on="match_id")
    stats["side"] = np.where(stats["team_id"] == stats["home_team_id"], "home", "away")
    stats["column"] = stats["stat_key"] + "_" + stats["period"].str.lower() + "_" + stats["side"]
    wide = stats.pivot(index="match_id", columns="column", values="value")
    available = stats.groupby("match_id")["available_at"].max().rename("available_at")
    facts = matches.merge(wide, left_on="match_id", right_index=True, how="left").merge(
        available, left_on="match_id", right_index=True, how="left"
    )
    facts["kickoff_at"] = pd.to_datetime(facts["kickoff_at"], utc=True)
    facts["available_at"] = pd.to_datetime(facts["available_at"], utc=True)
    return facts.sort_values(["kickoff_at", "match_id"]).reset_index(drop=True)


@dataclass(frozen=True)
class HistoryView:
    """Matches knowable at `as_of` for one competition."""

    competition_key: str
    as_of: datetime
    frame: pd.DataFrame
    max_available_at: datetime | None


class FeatureStore:
    def __init__(self, facts: pd.DataFrame) -> None:
        self._by_competition: dict[str, pd.DataFrame] = {}
        for key, frame in facts.groupby("competition_key"):
            known = frame[frame["available_at"].notna()].sort_values("available_at", kind="stable")
            self._by_competition[str(key)] = known.reset_index(drop=True)

    def history(self, competition_key: str, as_of: datetime) -> HistoryView:
        as_of = ensure_utc(as_of)
        frame = self._by_competition.get(competition_key)
        if frame is None or frame.empty:
            return HistoryView(competition_key, as_of, pd.DataFrame(), None)
        stamp = pd.Timestamp(as_of)
        end = int(frame["available_at"].searchsorted(stamp, side="right"))
        view = frame.iloc[:end]
        max_available = view["available_at"].max().to_pydatetime() if end else None
        result = HistoryView(competition_key, as_of, view, max_available)
        assert_no_leakage(result)
        return result


def assert_no_leakage(view: HistoryView) -> None:
    if view.frame.empty:
        return
    latest = view.frame["available_at"].max()
    if latest > pd.Timestamp(view.as_of):
        raise LeakageError(f"history contains data available at {latest} > as_of {view.as_of}")
    if (view.frame["kickoff_at"] >= pd.Timestamp(view.as_of)).any():
        raise LeakageError(f"history contains a match kicking off at or after as_of {view.as_of}")
