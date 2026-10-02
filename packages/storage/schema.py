"""PostgreSQL schema (SQLAlchemy Core). See docs/data-model.md.

Rules: canonical ids are deterministic text ids; provider ids live only in `provider_entity_map`; facts that
feed features carry `available_at` (ADR-0003); odds, statistics and predictions are append-only.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

TS = DateTime(timezone=True)

data_sources = Table(
    "data_sources",
    metadata,
    Column("source_id", Text, primary_key=True),
    Column("priority", SmallInteger, nullable=False),
    Column("license_note", Text, nullable=False),
    Column("capabilities", JSONB, nullable=False),
)

raw_payloads = Table(
    "raw_payloads",
    metadata,
    Column("raw_payload_id", Text, primary_key=True),
    Column("source_id", Text, ForeignKey("data_sources.source_id"), nullable=False),
    Column("endpoint", Text, nullable=False),
    Column("request_params", JSONB, nullable=False),
    Column("fetched_at", TS, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("storage_uri", Text, nullable=False),
)

competitions = Table(
    "competitions",
    metadata,
    Column("competition_id", Text, primary_key=True),
    Column("competition_key", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("country", Text, nullable=False),
)

seasons = Table(
    "seasons",
    metadata,
    Column("season_id", Text, primary_key=True),
    Column("competition_id", Text, ForeignKey("competitions.competition_id"), nullable=False),
    Column("label", Text, nullable=False),
    UniqueConstraint("competition_id", "label"),
)

teams = Table(
    "teams",
    metadata,
    Column("team_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("country", Text, nullable=False),
)

provider_entity_map = Table(
    "provider_entity_map",
    metadata,
    Column("source_id", Text, ForeignKey("data_sources.source_id"), primary_key=True),
    Column("entity_type", Text, primary_key=True),
    Column("provider_ref", Text, primary_key=True),
    Column("canonical_id", Text, nullable=False),
    Column("mapped_by", Text, nullable=False),
    Column("created_at", TS, nullable=False),
)

matches = Table(
    "matches",
    metadata,
    Column("match_id", Text, primary_key=True),
    Column("season_id", Text, ForeignKey("seasons.season_id"), nullable=False),
    Column("home_team_id", Text, ForeignKey("teams.team_id"), nullable=False),
    Column("away_team_id", Text, ForeignKey("teams.team_id"), nullable=False),
    Column("kickoff_at", TS, nullable=False),
    Column("kickoff_time_known", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    CheckConstraint("home_team_id <> away_team_id", name="ck_matches_distinct_teams"),
    UniqueConstraint("home_team_id", "away_team_id", "kickoff_at"),
)
Index("ix_matches_season_kickoff", matches.c.season_id, matches.c.kickoff_at)

match_statistics = Table(
    "match_statistics",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("match_id", Text, ForeignKey("matches.match_id"), nullable=False),
    Column("team_id", Text, ForeignKey("teams.team_id"), nullable=False),
    Column("period", Text, nullable=False),
    Column("stat_key", Text, nullable=False),
    Column("value", Integer, nullable=False),
    Column("source_id", Text, ForeignKey("data_sources.source_id"), nullable=False),
    Column("available_at", TS, nullable=False),
    Column("raw_payload_id", Text, ForeignKey("raw_payloads.raw_payload_id"), nullable=False),
    Column("supersedes_id", BigInteger, ForeignKey("match_statistics.id")),
    CheckConstraint("value >= 0", name="ck_match_statistics_non_negative"),
    UniqueConstraint("match_id", "team_id", "period", "stat_key", "source_id", "raw_payload_id"),
)
Index("ix_match_statistics_match", match_statistics.c.match_id, match_statistics.c.available_at)

bookmakers = Table(
    "bookmakers",
    metadata,
    Column("bookmaker_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("is_aggregate", Boolean, nullable=False, default=False),
    Column("is_sharp", Boolean, nullable=False, default=False),
)

markets = Table(
    "markets",
    metadata,
    Column("market_key", Text, primary_key=True),
    Column("stat_key", Text, nullable=False),
    Column("period", Text, nullable=False),
    Column("kind", Text, nullable=False),
)

odds_snapshots = Table(
    "odds_snapshots",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("match_id", Text, ForeignKey("matches.match_id"), nullable=False),
    Column("bookmaker_id", Text, ForeignKey("bookmakers.bookmaker_id"), nullable=False),
    Column("market_key", Text, ForeignKey("markets.market_key"), nullable=False),
    Column("line", Numeric(5, 2), nullable=False),
    Column("selection", Text, nullable=False),
    Column("decimal_odds", Numeric(8, 3), nullable=False),
    Column("is_closing", Boolean, nullable=False),
    Column("available_at", TS, nullable=False),
    Column("source_id", Text, ForeignKey("data_sources.source_id"), nullable=False),
    Column("raw_payload_id", Text, ForeignKey("raw_payloads.raw_payload_id"), nullable=False),
    CheckConstraint("decimal_odds > 1.0", name="ck_odds_above_one"),
    CheckConstraint("selection in ('over', 'under')", name="ck_odds_selection"),
    UniqueConstraint(
        "match_id", "bookmaker_id", "market_key", "line", "selection", "is_closing", "raw_payload_id"
    ),
)
Index("ix_odds_match_market", odds_snapshots.c.match_id, odds_snapshots.c.market_key, odds_snapshots.c.line)

data_quality_events = Table(
    "data_quality_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("match_id", Text),
    Column("source_id", Text, nullable=False),
    Column("raw_payload_id", Text),
    Column("kind", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("details", JSONB, nullable=False),
    Column("detected_at", TS, nullable=False),
)

dataset_versions = Table(
    "dataset_versions",
    metadata,
    Column("dataset_version", Text, primary_key=True),
    Column("created_at", TS, nullable=False),
    Column("content_hash", Text, nullable=False),
    Column("manifest", JSONB, nullable=False),
)

model_versions = Table(
    "model_versions",
    metadata,
    Column("model_version", Text, primary_key=True),
    Column("target", Text, nullable=False),
    Column("algorithm", Text, nullable=False),
    Column("hyperparameters", JSONB, nullable=False),
    Column("feature_version", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", TS, nullable=False),
)

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("backtest_run_id", Text, primary_key=True),
    Column("experiment", Text, nullable=False),
    Column("config", JSONB, nullable=False),
    Column("config_hash", Text, nullable=False),
    Column("dataset_version", Text, ForeignKey("dataset_versions.dataset_version"), nullable=False),
    Column("code_version", Text, nullable=False),
    Column("started_at", TS, nullable=False),
    Column("finished_at", TS),
    Column("status", Text, nullable=False),
    Column("metrics", JSONB),
)

feature_snapshots = Table(
    "feature_snapshots",
    metadata,
    Column("feature_snapshot_id", Text, primary_key=True),
    Column("match_id", Text, ForeignKey("matches.match_id"), nullable=False),
    Column("as_of", TS, nullable=False),
    Column("feature_version", Text, nullable=False),
    Column("n_history", Integer, nullable=False),
    Column("max_available_at", TS),
    Column("features", JSONB, nullable=False),
    CheckConstraint(
        "max_available_at IS NULL OR max_available_at <= as_of", name="ck_feature_snapshot_no_leakage"
    ),
)

predictions = Table(
    "predictions",
    metadata,
    Column("prediction_id", Text, primary_key=True),
    Column("backtest_run_id", Text, ForeignKey("backtest_runs.backtest_run_id")),
    Column("match_id", Text, ForeignKey("matches.match_id"), nullable=False),
    Column("mode", Text, nullable=False),
    Column("as_of", TS, nullable=False),
    Column("market_key", Text, ForeignKey("markets.market_key"), nullable=False),
    Column("line", Numeric(5, 2), nullable=False),
    Column("model_version", Text, ForeignKey("model_versions.model_version"), nullable=False),
    Column("calibrator", Text, nullable=False),
    Column("probability_raw", Float, nullable=False),
    Column("probability", Float, nullable=False),
    Column("fair_odds", Float),
    Column("market_bookmaker", Text),
    Column("market_odds", Float),
    Column("market_probability_raw", Float),
    Column("market_probability", Float),
    Column("edge", Float),
    Column("expected_value", Float),
    Column("signal_state", Text),
    Column("feature_snapshot_id", Text, ForeignKey("feature_snapshots.feature_snapshot_id"), nullable=False),
    Column("created_at", TS, nullable=False),
    CheckConstraint("probability >= 0 AND probability <= 1", name="ck_prediction_probability"),
)
Index(
    "ix_predictions_run_market", predictions.c.backtest_run_id, predictions.c.market_key, predictions.c.line
)

settlements = Table(
    "settlements",
    metadata,
    Column("prediction_id", Text, ForeignKey("predictions.prediction_id"), primary_key=True),
    Column("actual_total", Integer),
    Column("outcome", Text, nullable=False),
)

paper_bets = Table(
    "paper_bets",
    metadata,
    Column("paper_bet_id", Text, primary_key=True),
    Column("backtest_run_id", Text, ForeignKey("backtest_runs.backtest_run_id"), nullable=False),
    Column("prediction_id", Text, ForeignKey("predictions.prediction_id"), nullable=False),
    Column("selection", Text, nullable=False),
    Column("bookmaker_id", Text, nullable=False),
    Column("decimal_odds", Float, nullable=False),
    Column("stake", Float, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("pnl", Float, nullable=False),
    Column("closing_odds", Float),
)
