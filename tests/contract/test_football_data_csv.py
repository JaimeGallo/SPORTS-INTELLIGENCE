"""Parser contract tests on HANDMADE files that follow football-data.co.uk's column layout (fictional teams).

When network access to football-data.co.uk is enabled, real files should be added here as fixtures.
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest

from packages.common.config import CompetitionConfig
from packages.data_quality.engine import check_matches
from packages.markets.catalog import Period, Selection, StatKey
from packages.providers.base import RawPayload, Side
from packages.providers.football_data_csv import FootballDataCsvProvider, season_code

FIXTURES = Path(__file__).parent / "fixtures"
ENG = CompetitionConfig(
    competition_key="ENG-PL", name="Premier League", country="ENG", football_data_div="E0"
)
ESP = CompetitionConfig(competition_key="ESP-LL", name="La Liga", country="ESP", football_data_div="SP1")


def _parse(name: str, competition: CompetitionConfig, season: str):  # type: ignore[no-untyped-def]
    provider = FootballDataCsvProvider(FIXTURES, allow_download=False)
    payload = RawPayload("football_data_csv", "test", {}, (FIXTURES / name).read_bytes(), date(2024, 1, 1))  # type: ignore[arg-type]
    return provider.parse(payload, competition, season)


def test_season_code() -> None:
    assert season_code("2023-2024") == "2324"
    assert season_code("1999-2000") == "9900"
    with pytest.raises(ValueError):
        season_code("2023-2025")


def test_modern_file_with_bom_blank_rows_and_closing_odds() -> None:
    matches = _parse("football_data_2023_sample.csv", ENG, "2023-2024")
    assert len(matches) == 3  # the trailing empty row is ignored
    first = matches[0]
    assert first.home_team == "Team Alpha" and first.local_date == date(2023, 8, 11)
    assert first.local_time == time(20, 0)
    assert first.stats[(StatKey.GOALS, Period.FULL_TIME, Side.AWAY)] == 3
    assert first.stats[(StatKey.GOALS, Period.FIRST_HALF, Side.AWAY)] == 2
    assert first.stats[(StatKey.CORNERS, Period.FULL_TIME, Side.HOME)] == 2
    closing = {(o.bookmaker, o.selection): o.decimal_odds for o in first.odds if o.is_closing}
    assert closing[("pinnacle", Selection.OVER)] == 1.47
    prematch = {(o.bookmaker, o.selection) for o in first.odds if not o.is_closing}
    assert ("market_avg", Selection.UNDER) in prematch
    assert all(o.market_key == "goals_ft_total" and o.line == 2.5 for o in first.odds)


def test_missing_values_are_reported_not_invented() -> None:
    third = _parse("football_data_2023_sample.csv", ENG, "2023-2024")[2]
    assert set(third.missing_fields) == {"HTHG", "HTAG", "HC", "AC"}
    assert (StatKey.CORNERS, Period.FULL_TIME, Side.HOME) not in third.stats


def test_old_file_two_digit_year_no_time_and_betbrain_columns() -> None:
    matches = _parse("football_data_2015_sample.csv", ESP, "2015-2016")
    assert matches[0].local_date == date(2015, 8, 21)
    assert matches[0].local_time is None
    books = {o.bookmaker for o in matches[0].odds}
    assert books == {"market_max", "market_avg"}
    assert not any(o.is_closing for o in matches[0].odds)


def test_quality_engine_rejects_bad_odds_and_inconsistent_stats() -> None:
    report = check_matches(
        _parse("football_data_2023_sample.csv", ENG, "2023-2024")
        + _parse("football_data_2015_sample.csv", ESP, "2015-2016")
    )
    kinds = [i.kind for i in report.issues]
    assert "invalid_odds" in kinds  # B365 over 0.95
    assert "inconsistent_stats" in kinds  # first-half goals > full-time goals
    assert "missing_fields" in kinds
    third = report.matches[2]
    assert {o.bookmaker for o in third.odds} == {"pinnacle"}
    kappa = next(m for m in report.matches if m.away_team == "Team Kappa")
    assert kappa.stats == {}
