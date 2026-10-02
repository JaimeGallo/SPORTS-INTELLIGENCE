"""FootyStats adapter (https://footystats.org/api, base https://api.football-data-api.com).

STATUS: built from FootyStats' public documentation as seen during the Phase 0 evaluation, WITHOUT a real
key or response. Every field name lives in `FIELDS` / `ODDS_FIELDS` below and must be confirmed in the
provider spike (ADR-0008) before trusting ingested data. Unknown or missing values are reported as missing,
never invented.

Point-in-time policy for FootyStats odds: the API does not say which bookmaker quoted them or when, so they
are stored under the pseudo-bookmaker `footystats_reference` with `is_closing=True` (available only at
kickoff). They can be used to EVALUATE the model against a market reference, never to decide a paper bet.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from packages.common.config import CompetitionConfig
from packages.common.errors import DataError
from packages.markets.catalog import Period, Selection, StatKey
from packages.providers.base import (
    Capability,
    HistoricalMatchProvider,
    ProviderInfo,
    RawMatch,
    RawOdds,
    RawPayload,
    Side,
    load_provider_info,
)
from packages.providers.http import RateLimiter, ResilientGetter, Transport, urllib_transport

log = logging.getLogger(__name__)

BASE_URL = "https://api.football-data-api.com"
MAX_PER_PAGE = 500
COMPLETE_STATUS = "complete"
REFERENCE_BOOKMAKER = "footystats_reference"

# (stat, period, side) <- field. [verify] all names against a real response.
FIELDS: dict[tuple[StatKey | str, Period, Side], str] = {
    (StatKey.GOALS, Period.FULL_TIME, Side.HOME): "homeGoalCount",
    (StatKey.GOALS, Period.FULL_TIME, Side.AWAY): "awayGoalCount",
    (StatKey.GOALS, Period.FIRST_HALF, Side.HOME): "ht_goals_team_a",
    (StatKey.GOALS, Period.FIRST_HALF, Side.AWAY): "ht_goals_team_b",
    (StatKey.CORNERS, Period.FULL_TIME, Side.HOME): "team_a_corners",
    (StatKey.CORNERS, Period.FULL_TIME, Side.AWAY): "team_b_corners",
    (StatKey.CORNERS, Period.FIRST_HALF, Side.HOME): "team_a_fh_corners",
    (StatKey.CORNERS, Period.FIRST_HALF, Side.AWAY): "team_b_fh_corners",
    ("shots", Period.FULL_TIME, Side.HOME): "team_a_shots",
    ("shots", Period.FULL_TIME, Side.AWAY): "team_b_shots",
    ("shots_on_target", Period.FULL_TIME, Side.HOME): "team_a_shotsOnTarget",
    ("shots_on_target", Period.FULL_TIME, Side.AWAY): "team_b_shotsOnTarget",
}
REQUIRED = (
    (StatKey.GOALS, Period.FULL_TIME),
    (StatKey.GOALS, Period.FIRST_HALF),
    (StatKey.CORNERS, Period.FULL_TIME),
    (StatKey.CORNERS, Period.FIRST_HALF),
)
# Minute-by-minute corner lists, used to DERIVE first-half corners when the explicit field is missing.
CORNER_TIMINGS = {Side.HOME: "team_a_corner_timings", Side.AWAY: "team_b_corner_timings"}


def _odds_fields() -> dict[str, tuple[str, float, Selection]]:
    """field -> (market_key, line, selection). [verify] names; FootyStats encodes 2.5 as '25'."""
    out: dict[str, tuple[str, float, Selection]] = {}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        code = f"{int(line * 10):02d}"
        out[f"odds_ft_over{code}"] = ("goals_ft_total", line, Selection.OVER)
        out[f"odds_ft_under{code}"] = ("goals_ft_total", line, Selection.UNDER)
    for line in (0.5, 1.5, 2.5):
        code = f"{int(line * 10):02d}"
        out[f"odds_1st_half_over{code}"] = ("goals_1h_total", line, Selection.OVER)
        out[f"odds_1st_half_under{code}"] = ("goals_1h_total", line, Selection.UNDER)
    for line in (7.5, 8.5, 9.5, 10.5, 11.5):
        code = f"{int(line * 10)}"
        out[f"odds_corners_over_{code}"] = ("corners_ft_total", line, Selection.OVER)
        out[f"odds_corners_under_{code}"] = ("corners_ft_total", line, Selection.UNDER)
    return out


ODDS_FIELDS = _odds_fields()
_MINUTE = re.compile(r"^\s*(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*'?\s*$")


def _count(value: Any) -> int | None:
    """FootyStats uses -1 (and sometimes empty values) for 'not available'."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or not number.is_integer():
        return None
    return int(number)


def _price(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None  # 0 = no price; prices <= 1 are rejected by the quality engine


def first_half_from_timings(timings: Any) -> int | None:
    """Count corners up to 45+x from a list (or comma-separated string) of minute marks.
    Returns None when any mark is unparseable: a partial count would be silently wrong."""
    if timings is None or timings == "" or timings == -1:
        return None
    items = timings.split(",") if isinstance(timings, str) else list(timings)
    total = 0
    for item in items:
        match = _MINUTE.match(str(item))
        if match is None:
            return None
        if int(match.group(1)) <= 45:  # '45+2' is first-half stoppage time; second half starts at 46
            total += 1
    return total


def season_label_from_year(year: Any) -> str:
    """FootyStats years: 2024 -> '2024'; 20232024 -> '2023-2024'."""
    text = str(year)
    if len(text) == 4 and text.isdigit():
        return text
    if len(text) == 8 and text.isdigit() and int(text[4:]) == int(text[:4]) + 1:
        return f"{text[:4]}-{text[4:]}"
    raise DataError(f"unrecognised FootyStats season year {year!r}")


def parse_matches(
    matches: Iterable[dict[str, Any]],
    *,
    source_id: str,
    competition: CompetitionConfig,
    season_label: str,
    timezone: ZoneInfo,
) -> list[RawMatch]:
    out: list[RawMatch] = []
    for m in matches:
        if str(m.get("status", "")).lower() != COMPLETE_STATUS:
            continue  # fixtures, postponed and abandoned matches are not results
        try:
            kickoff = datetime.fromtimestamp(int(m["date_unix"]), UTC)
            home, away = str(m["home_name"]).strip(), str(m["away_name"]).strip()
            match_ref = str(m["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(f"FootyStats match without id/date/teams: {exc}") from None
        stats: dict[tuple[StatKey | str, Period, Side], int] = {}
        for key, name in FIELDS.items():
            value = _count(m.get(name))
            if value is not None:
                stats[key] = value
        derived: list[str] = []
        for side, name in CORNER_TIMINGS.items():
            key = (StatKey.CORNERS, Period.FIRST_HALF, side)
            full = stats.get((StatKey.CORNERS, Period.FULL_TIME, side))
            if key in stats or full is None:
                continue
            first_half = first_half_from_timings(m.get(name))
            timings = m.get(name)
            n_marks = len(timings.split(",") if isinstance(timings, str) else timings or [])
            # only trust timings that account for every corner of the match
            if first_half is not None and n_marks == full:
                stats[key] = first_half
                derived.append(f"{side.value}_1h_corners_from_timings")
        missing = [
            f"{stat}_{period.value}_{side.value}"
            for stat, period in REQUIRED
            for side in Side
            if (stat, period, side) not in stats
        ]
        odds = tuple(
            RawOdds(REFERENCE_BOOKMAKER, market_key, line, selection, price, is_closing=True)
            for name, (market_key, line, selection) in ODDS_FIELDS.items()
            if (price := _price(m.get(name))) is not None
        )
        local = kickoff.astimezone(timezone)
        out.append(
            RawMatch(
                source_id=source_id,
                provider_match_ref=match_ref,
                competition_key=competition.competition_key,
                season_label=season_label,
                home_team=home,
                away_team=away,
                local_date=local.date(),
                local_time=local.time().replace(second=0, microsecond=0),
                kickoff_utc=kickoff,
                stats=stats,
                odds=odds,
                missing_fields=tuple(missing),
                notes=tuple(derived),
            )
        )
    return out


class FootyStatsProvider(HistoricalMatchProvider):
    def __init__(
        self,
        api_key: str,
        *,
        transport: Transport | None = None,
        limiter: RateLimiter | None = None,
        timezone: str = "America/Bogota",
        source_id: str = "footystats",
    ) -> None:
        if not api_key:
            raise DataError("FOOTYSTATS_API_KEY is not set")
        self.info: ProviderInfo = load_provider_info(source_id)
        self._key = api_key
        self._tz = ZoneInfo(timezone)
        # FootyStats documents 1,800 requests/hour; stay well below it. [verify] for the contracted plan.
        self._http = ResilientGetter(transport or urllib_transport(), limiter or RateLimiter(1500, 3600.0))

    @property
    def request_stats(self) -> dict[str, int]:
        return dict(self._http.stats)

    def _get(self, endpoint: str, **params: Any) -> dict[str, Any]:
        safe_query = urlencode(sorted(params.items()))
        safe_url = f"{BASE_URL}/{endpoint}?{safe_query}"
        url = f"{BASE_URL}/{endpoint}?{urlencode([('key', self._key), *sorted(params.items())])}"
        body = self._http.get(url, safe_url=safe_url)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DataError(f"invalid JSON from {safe_url}") from exc
        if not isinstance(data, dict) or data.get("success") is False:
            raise DataError(f"FootyStats error from {safe_url}: {str(data)[:200]}")
        return data

    def list_leagues(self, country: str | None = None) -> list[dict[str, Any]]:
        """League seasons available to this key: [{'name', 'country', 'season_label', 'season_id'}]."""
        data = self._get("league-list", chosen_leagues_only="true")
        rows = []
        for league in data.get("data", []):
            if country and str(league.get("country", "")).lower() != country.lower():
                continue
            for season in league.get("season", []):
                rows.append(
                    {
                        "name": league.get("name") or league.get("league_name"),
                        "country": league.get("country"),
                        "season_label": season_label_from_year(season.get("year")),
                        "season_id": season.get("id"),
                    }
                )
        return rows

    def fetch_season(self, competition: CompetitionConfig, season_label: str) -> RawPayload:
        self.info.require(Capability.RESULTS)
        season_id = competition.footystats_season_ids.get(season_label)
        if season_id is None:
            raise DataError(f"no FootyStats season id for {competition.competition_key} {season_label}")
        pages: list[dict[str, Any]] = []
        page, max_page = 1, 1
        while page <= max_page:
            data = self._get("league-matches", season_id=season_id, page=page, max_per_page=MAX_PER_PAGE)
            pages.append(data)
            pager = data.get("pager") or {}
            max_page = int(pager.get("max_page", 1) or 1)
            page += 1
        content = json.dumps({"season_id": season_id, "pages": pages}, sort_keys=True).encode("utf-8")
        return RawPayload(
            source_id=self.info.source_id,
            endpoint=f"{BASE_URL}/league-matches",
            params={"season_id": str(season_id), "season": season_label},  # never the key
            content=content,
            fetched_at=datetime.now(UTC),
        )

    def parse(self, payload: RawPayload, competition: CompetitionConfig, season_label: str) -> list[RawMatch]:
        document = json.loads(payload.content)
        matches = [m for page in document.get("pages", []) for m in page.get("data", [])]
        return parse_matches(
            matches,
            source_id=self.info.source_id,
            competition=competition,
            season_label=season_label,
            timezone=self._tz,
        )
