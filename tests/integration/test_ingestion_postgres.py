"""Integration tests against a real PostgreSQL (TEST_DATABASE_URL). Skipped when it is not set."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text

from packages.common.config import AppConfig
from packages.features.store import load_match_facts
from packages.ingestion.engine import HistoricalDataEngine
from packages.providers.synthetic import SyntheticProvider
from packages.storage import schema as s
from packages.storage.db import make_engine, upgrade
from tests.helpers import COMP

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")]
SEASONS = ["2018-2019", "2019-2020"]


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    assert URL
    eng = make_engine(URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    upgrade(URL)
    yield eng
    eng.dispose()


def _count(engine: Engine, table: s.Table) -> int:  # type: ignore[name-defined]
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def test_ingestion_is_idempotent_and_point_in_time(engine: Engine, tmp_path: Path) -> None:
    app = AppConfig(competitions=[COMP])
    ingestion = HistoricalDataEngine(engine, app, raw_root=tmp_path)
    provider = SyntheticProvider(SEASONS, seed=5)
    first = ingestion.ingest(provider, [COMP], SEASONS)
    counts = {t.name: _count(engine, t) for t in (s.matches, s.match_statistics, s.odds_snapshots)}
    assert counts["matches"] == 2 * 380
    ingestion.ingest(provider, [COMP], SEASONS)
    assert {t.name: _count(engine, t) for t in (s.matches, s.match_statistics, s.odds_snapshots)} == counts

    version_a = ingestion.snapshot(first.payload_ids)
    version_b = ingestion.snapshot(list(reversed(first.payload_ids)))
    assert version_a == version_b  # the dataset version depends only on content

    with engine.connect() as conn:
        rows = conn.execute(
            select(s.matches.c.kickoff_at, s.match_statistics.c.available_at)
            .join(s.match_statistics, s.match_statistics.c.match_id == s.matches.c.match_id)
            .limit(500)
        ).all()
        assert all(available > kickoff for kickoff, available in rows)
        closing_ok = conn.execute(
            select(func.bool_and(s.odds_snapshots.c.available_at >= s.matches.c.kickoff_at))
            .join(s.matches, s.matches.c.match_id == s.odds_snapshots.c.match_id)
            .where(s.odds_snapshots.c.is_closing.is_(True))
        ).scalar_one()
        assert closing_ok in (True, None)

    facts = load_match_facts(engine, [COMP.competition_key], "synthetic")
    assert len(facts) == 2 * 380
    assert facts["goals_ft_home"].notna().all()
    assert load_match_facts(engine, [COMP.competition_key], "football_data_csv").empty


def test_database_rejects_impossible_odds(engine: Engine) -> None:
    from sqlalchemy.exc import IntegrityError

    with engine.connect() as conn:
        match_id, raw_id = conn.execute(
            select(s.odds_snapshots.c.match_id, s.odds_snapshots.c.raw_payload_id)
        ).first()  # type: ignore[misc]
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            s.odds_snapshots.insert().values(
                match_id=match_id,
                bookmaker_id="pinnacle",
                market_key="goals_ft_total",
                line=2.5,
                selection="over",
                decimal_odds=0.9,
                is_closing=False,
                available_at=func.now(),
                source_id="synthetic",
                raw_payload_id=raw_id,
            )
        )


def test_footystats_ingestion_uses_exact_kickoff_and_reference_odds(engine: Engine, tmp_path: Path) -> None:
    from tests.contract.test_footystats import COL, FIXTURE, FakeTransport, _provider

    app = AppConfig(competitions=[COL])
    ingestion = HistoricalDataEngine(engine, app, raw_root=tmp_path)
    stats = ingestion.ingest(_provider(FakeTransport(FIXTURE["league-matches"])), [COL], ["2024"])
    assert stats.matches == 3
    facts = load_match_facts(engine, [COL.competition_key], "footystats")
    assert len(facts) == 3
    assert facts["corners_1h_home"].isna().sum() == 1  # the match with incomplete corner timings
    with engine.connect() as conn:
        rows = conn.execute(
            select(s.odds_snapshots.c.available_at, s.matches.c.kickoff_at, s.odds_snapshots.c.bookmaker_id)
            .join(s.matches, s.matches.c.match_id == s.odds_snapshots.c.match_id)
            .where(s.odds_snapshots.c.source_id == "footystats")
        ).all()
    assert rows and all(
        available == kickoff and book == "footystats_reference" for available, kickoff, book in rows
    )
