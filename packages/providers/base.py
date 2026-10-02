"""Provider abstraction (ADR-0002).

Adapters return RAW records carrying the provider's own references. Only the normalization layer assigns
canonical ids and writes to the database. Capabilities come from config/providers.yaml, never from code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
from pathlib import Path

from packages.common.config import PROJECT_ROOT, CompetitionConfig, read_yaml
from packages.common.errors import CapabilityNotSupported, ConfigError
from packages.markets.catalog import Period, Selection, StatKey

PROVIDERS_PATH = PROJECT_ROOT / "config" / "providers.yaml"


class Capability(StrEnum):
    FIXTURES = "fixtures"
    RESULTS = "results"
    HALFTIME_SCORE = "halftime_score"
    MATCH_STATS = "match_stats"
    MATCH_STATS_BY_HALF = "match_stats_by_half"
    CORNERS = "corners"
    LINEUPS = "lineups"
    LIVE_EVENTS = "live_events"
    ODDS_PREMATCH = "odds_prematch"
    ODDS_CLOSING = "odds_closing"
    ODDS_LIVE = "odds_live"
    ODDS_HISTORICAL = "odds_historical"


@dataclass(frozen=True)
class ProviderInfo:
    source_id: str
    priority: int
    license_note: str
    capabilities: frozenset[Capability]

    def require(self, capability: Capability) -> None:
        if capability not in self.capabilities:
            raise CapabilityNotSupported(self.source_id, capability.value)


def load_provider_info(source_id: str, path: Path = PROVIDERS_PATH) -> ProviderInfo:
    providers = read_yaml(path).get("providers", {})
    if source_id not in providers:
        raise ConfigError(f"provider '{source_id}' is not declared in {path}")
    entry = providers[source_id]
    declared = entry.get("capabilities", {})
    unknown = set(declared) - {c.value for c in Capability}
    if unknown:
        raise ConfigError(f"unknown capabilities for '{source_id}': {sorted(unknown)}")
    return ProviderInfo(
        source_id=source_id,
        priority=int(entry["priority"]),
        license_note=str(entry["license_note"]),
        capabilities=frozenset(Capability(k) for k, v in declared.items() if v),
    )


class Side(StrEnum):
    HOME = "home"
    AWAY = "away"


@dataclass(frozen=True)
class RawOdds:
    bookmaker: str  # provider's bookmaker code mapped to a canonical bookmaker key
    market_key: str
    line: float
    selection: Selection
    decimal_odds: float
    is_closing: bool


@dataclass(frozen=True)
class RawMatch:
    source_id: str
    provider_match_ref: str
    competition_key: str
    season_label: str  # canonical season label, e.g. '2023-2024'
    home_team: str  # provider's team name: mapped, never used as an identifier
    away_team: str
    local_date: date
    local_time: time | None  # None when the source has no kickoff time
    stats: dict[tuple[StatKey | str, Period, Side], int] = field(default_factory=dict)
    odds: tuple[RawOdds, ...] = ()
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawPayload:
    """One raw file/response, stored verbatim so every ingestion is reproducible offline."""

    source_id: str
    endpoint: str
    params: dict[str, str]  # never contains secrets
    content: bytes
    fetched_at: datetime


class HistoricalMatchProvider(ABC):
    """A source of finished matches with results, statistics and (optionally) odds."""

    info: ProviderInfo

    @abstractmethod
    def fetch_season(self, competition: CompetitionConfig, season_label: str) -> RawPayload:
        """Retrieve the raw payload for one competition season (network or local cache)."""

    @abstractmethod
    def parse(self, payload: RawPayload, competition: CompetitionConfig, season_label: str) -> list[RawMatch]:
        """Parse a raw payload into raw matches. Pure: no I/O."""
