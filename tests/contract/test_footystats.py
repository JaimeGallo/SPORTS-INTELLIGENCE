"""FootyStats adapter contract tests on a HANDMADE response with fictional clubs.

The field names follow FootyStats' public documentation; they must be confirmed with a real response
(ADR-0008). When the spike runs, save a real (key-free) response next to this fixture and add it here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from packages.common.config import CompetitionConfig
from packages.common.errors import DataError
from packages.data_quality.engine import check_matches
from packages.markets.catalog import Period, Selection, StatKey
from packages.providers.base import Side
from packages.providers.footystats import FootyStatsProvider, first_half_from_timings, season_label_from_year
from packages.providers.http import HttpStatusError, RateLimiter

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "footystats_league_matches_sample.json").read_text()
)
COL = CompetitionConfig(
    competition_key="COL-PA", name="Primera A", country="COL", footystats_season_ids={"2024": 11111}
)
SECRET = "test-key-1234567890"


class FakeTransport:
    def __init__(self, pages: list[dict[str, object]], failures: int = 0) -> None:
        self.pages, self.failures, self.urls = pages, failures, []  # type: ignore[var-annotated]

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if self.failures:
            self.failures -= 1
            raise HttpStatusError(429, "<redacted>")
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return json.dumps(self.pages[page - 1]).encode()


def _provider(transport: FakeTransport) -> FootyStatsProvider:
    no_wait = RateLimiter(10_000, 1.0, sleep=lambda _s: None)
    provider = FootyStatsProvider(SECRET, transport=transport, limiter=no_wait)
    provider._http.sleep = lambda _s: None  # no real backoff in tests
    return provider


def test_fetch_paginates_and_never_stores_the_key() -> None:
    transport = FakeTransport(FIXTURE["league-matches"])
    provider = _provider(transport)
    payload = provider.fetch_season(COL, "2024")
    assert len(transport.urls) == 2
    assert all("key=" + SECRET in url for url in transport.urls)  # the key goes on the wire...
    stored = payload.content.decode() + payload.endpoint + json.dumps(payload.params)
    assert SECRET not in stored  # ...and nowhere else


def test_retries_on_rate_limit_then_succeeds() -> None:
    transport = FakeTransport(FIXTURE["league-matches"], failures=2)
    provider = _provider(transport)
    provider.fetch_season(COL, "2024")
    assert provider.request_stats["retries"] == 2


def test_errors_do_not_leak_the_key() -> None:
    def always_500(url: str) -> bytes:
        raise HttpStatusError(500, "<redacted>")

    provider = FootyStatsProvider(
        SECRET, transport=always_500, limiter=RateLimiter(100, 1.0, sleep=lambda _s: None)
    )
    provider._http.sleep = lambda _s: None
    with pytest.raises(DataError) as info:
        provider.fetch_season(COL, "2024")
    assert SECRET not in str(info.value)


def test_unknown_season_is_refused() -> None:
    with pytest.raises(DataError):
        _provider(FakeTransport([])).fetch_season(COL, "2019")


def test_parse_maps_fields_and_skips_unfinished_matches() -> None:
    provider = _provider(FakeTransport(FIXTURE["league-matches"]))
    matches = provider.parse(provider.fetch_season(COL, "2024"), COL, "2024")
    assert [m.provider_match_ref for m in matches] == ["9001", "9002", "9003"]  # 9004 is incomplete
    first = matches[0]
    assert first.kickoff_utc == datetime.fromtimestamp(1710086400, UTC)
    assert first.stats[(StatKey.CORNERS, Period.FIRST_HALF, Side.HOME)] == 4
    assert first.stats[(StatKey.GOALS, Period.FIRST_HALF, Side.HOME)] == 1
    assert first.missing_fields == ()
    odds = {(o.market_key, o.line, o.selection): o for o in first.odds}
    assert odds[("corners_ft_total", 9.5, Selection.OVER)].decimal_odds == 1.9
    assert all(o.bookmaker == "footystats_reference" and o.is_closing for o in first.odds)
    assert ("goals_1h_total", 0.5, Selection.UNDER) not in odds  # price 0 = no price


def test_first_half_corners_derived_only_from_complete_timings() -> None:
    provider = _provider(FakeTransport(FIXTURE["league-matches"]))
    matches = provider.parse(provider.fetch_season(COL, "2024"), COL, "2024")
    derived = matches[1]
    assert derived.stats[(StatKey.CORNERS, Period.FIRST_HALF, Side.HOME)] == 3  # 10, 33, 45+2
    assert derived.stats[(StatKey.CORNERS, Period.FIRST_HALF, Side.AWAY)] == 1
    assert "home_1h_corners_from_timings" in derived.notes
    incomplete = matches[2]
    assert (StatKey.CORNERS, Period.FIRST_HALF, Side.HOME) not in incomplete.stats
    assert "corners_1H_home" in incomplete.missing_fields


def test_reference_odds_pass_quality_checks_without_overround_rule() -> None:
    provider = _provider(FakeTransport(FIXTURE["league-matches"]))
    report = check_matches(provider.parse(provider.fetch_season(COL, "2024"), COL, "2024"))
    assert not [i for i in report.issues if i.kind in ("invalid_odds", "implausible_overround")]


@pytest.mark.parametrize(
    ("timings", "expected"),
    [(["1", "45", "45+3", "46", "90+2"], 3), ("", None), (["12", "x"], None), ([], 0)],
)
def test_first_half_from_timings(timings: object, expected: int | None) -> None:
    assert first_half_from_timings(timings) == expected


def test_season_labels() -> None:
    assert season_label_from_year(2024) == "2024"
    assert season_label_from_year(20232024) == "2023-2024"
    with pytest.raises(DataError):
        season_label_from_year(20232025)
