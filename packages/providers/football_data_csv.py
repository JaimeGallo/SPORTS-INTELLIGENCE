"""football-data.co.uk CSV adapter.

Files: https://www.football-data.co.uk/mmz4281/{yyYY}/{DIV}.csv (e.g. 2324/E0.csv). Column reference:
https://www.football-data.co.uk/notes.txt. Dates and times are UK local time. Kickoff time exists from
2019/20 onwards. Over/Under odds exist only for the 2.5 goals line:
- pre-match odds (collected 1-3 days before kickoff): B365, P (Pinnacle), Max/Avg (2019/20+) or BbMx/BbAv
  (older, Betbrain aggregates);
- closing odds (2019/20+): B365C, PC, MaxC, AvgC.
Per-half statistics (e.g. first-half corners) are NOT available from this source.
"""

from __future__ import annotations

import csv
import io
import math
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, time
from pathlib import Path

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

BASE_URL = "https://www.football-data.co.uk/mmz4281"
ALLOWLIST_HINT = (
    "If outbound hosts are restricted, allow both www.football-data.co.uk and football-data.co.uk "
    "(the first redirects to the second), or put the files in the cache and run with --no-download."
)

# (stat key, period, side) <- column
STAT_COLUMNS: dict[str, tuple[StatKey | str, Period, Side]] = {
    "FTHG": (StatKey.GOALS, Period.FULL_TIME, Side.HOME),
    "FTAG": (StatKey.GOALS, Period.FULL_TIME, Side.AWAY),
    "HTHG": (StatKey.GOALS, Period.FIRST_HALF, Side.HOME),
    "HTAG": (StatKey.GOALS, Period.FIRST_HALF, Side.AWAY),
    "HC": (StatKey.CORNERS, Period.FULL_TIME, Side.HOME),
    "AC": (StatKey.CORNERS, Period.FULL_TIME, Side.AWAY),
    "HS": ("shots", Period.FULL_TIME, Side.HOME),
    "AS": ("shots", Period.FULL_TIME, Side.AWAY),
    "HST": ("shots_on_target", Period.FULL_TIME, Side.HOME),
    "AST": ("shots_on_target", Period.FULL_TIME, Side.AWAY),
}
REQUIRED_STATS = ("FTHG", "FTAG", "HTHG", "HTAG", "HC", "AC")

# column prefix -> (canonical bookmaker key, is_closing)
OU25_BOOKMAKERS: dict[str, tuple[str, bool]] = {
    "B365": ("bet365", False),
    "P": ("pinnacle", False),
    "Max": ("market_max", False),
    "Avg": ("market_avg", False),
    "BbMx": ("market_max", False),
    "BbAv": ("market_avg", False),
    "B365C": ("bet365", True),
    "PC": ("pinnacle", True),
    "MaxC": ("market_max", True),
    "AvgC": ("market_avg", True),
}


def season_code(season_label: str) -> str:
    """'2023-2024' -> '2324'."""
    start, end = season_label.split("-")
    if int(end) != int(start) + 1:
        raise ValueError(f"invalid season label {season_label!r}")
    return f"{start[2:]}{end[2:]}"


def decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DataError("cannot decode CSV")  # pragma: no cover - latin-1 decodes anything


def _parse_date(raw: str) -> date:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise DataError(f"unparseable date {raw!r}")


def _parse_time(raw: str | None) -> time | None:
    if not raw or not raw.strip():
        return None
    try:
        return datetime.strptime(raw.strip(), "%H:%M").time()
    except ValueError as exc:
        raise DataError(f"unparseable time {raw!r}") from exc


def _parse_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    value = float(raw)
    if not value.is_integer():
        raise DataError(f"non-integer count {raw!r}")
    return int(value)


def _parse_odds(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_rows(
    text: str, *, source_id: str, competition_key: str, season_label: str, division: str
) -> list[RawMatch]:
    reader = csv.DictReader(io.StringIO(text))
    matches: list[RawMatch] = []
    for row in reader:
        row = {(k or "").strip(): (v or "") for k, v in row.items()}
        if not row.get("HomeTeam") or not row.get("Date"):
            continue  # trailing blank lines are common in these files
        missing: list[str] = []
        stats: dict[tuple[StatKey | str, Period, Side], int] = {}
        for column, key in STAT_COLUMNS.items():
            value = _parse_int(row.get(column))
            if value is None:
                if column in REQUIRED_STATS:
                    missing.append(column)
                continue
            stats[key] = value
        odds: list[RawOdds] = []
        for prefix, (bookmaker, closing) in OU25_BOOKMAKERS.items():
            over = _parse_odds(row.get(f"{prefix}>2.5"))
            under = _parse_odds(row.get(f"{prefix}<2.5"))
            if over is None or under is None:
                continue  # a one-sided quote cannot be de-margined: skip the pair
            for selection, price in ((Selection.OVER, over), (Selection.UNDER, under)):
                odds.append(RawOdds(bookmaker, "goals_ft_total", 2.5, selection, price, closing))
        local_date = _parse_date(row["Date"])
        home, away = row["HomeTeam"].strip(), row["AwayTeam"].strip()
        matches.append(
            RawMatch(
                source_id=source_id,
                provider_match_ref=f"{division}:{season_code(season_label)}:{local_date.isoformat()}:{home}:{away}",
                competition_key=competition_key,
                season_label=season_label,
                home_team=home,
                away_team=away,
                local_date=local_date,
                local_time=_parse_time(row.get("Time")),
                stats=stats,
                odds=tuple(odds),
                missing_fields=tuple(missing),
            )
        )
    return matches


class FootballDataCsvProvider(HistoricalMatchProvider):
    """Reads football-data.co.uk CSVs from a local cache directory, downloading missing files if allowed."""

    def __init__(self, cache_dir: Path, *, allow_download: bool = True, source_id: str = "football_data_csv"):
        self.info: ProviderInfo = load_provider_info(source_id)
        self._cache_dir = cache_dir
        self._allow_download = allow_download

    def _path(self, division: str, season_label: str) -> Path:
        return self._cache_dir / self.info.source_id / season_code(season_label) / f"{division}.csv"

    def fetch_season(self, competition: CompetitionConfig, season_label: str) -> RawPayload:
        self.info.require(Capability.RESULTS)
        division = competition.football_data_div
        if not division:
            raise DataError(f"competition {competition.competition_key} has no football-data.co.uk division")
        path = self._path(division, season_label)
        endpoint = f"{BASE_URL}/{season_code(season_label)}/{division}.csv"
        if path.exists():
            content = path.read_bytes()
            fetched_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        elif self._allow_download:
            request = urllib.request.Request(endpoint, headers={"User-Agent": "jev-sports-intelligence/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read()
            except (urllib.error.URLError, OSError) as exc:
                raise DataError(
                    f"cannot download {endpoint}: {getattr(exc, 'reason', exc)}. {ALLOWLIST_HINT}"
                ) from None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            fetched_at = datetime.now(UTC)
        else:
            raise DataError(f"{path} not in cache and downloads are disabled")
        return RawPayload(
            source_id=self.info.source_id,
            endpoint=endpoint,
            params={"division": division, "season": season_label},
            content=content,
            fetched_at=fetched_at,
        )

    def parse(self, payload: RawPayload, competition: CompetitionConfig, season_label: str) -> list[RawMatch]:
        return parse_rows(
            decode_csv(payload.content),
            source_id=self.info.source_id,
            competition_key=competition.competition_key,
            season_label=season_label,
            division=competition.football_data_div or "",
        )
