"""Market catalog and settlement rules.

A market family (e.g. `corners_ft_total`) is a count (`stat_key` over `period`) plus a kind. For `total`
markets every line is priced from ONE count distribution, so P(Over 8.5) >= P(Over 9.5) always holds.
"""

from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.common.config import PROJECT_ROOT, read_yaml
from packages.common.errors import ConfigError

MARKETS_PATH = PROJECT_ROOT / "config" / "markets.yaml"


class Period(StrEnum):
    FIRST_HALF = "1H"
    FULL_TIME = "FT"


class StatKey(StrEnum):
    GOALS = "goals"
    CORNERS = "corners"


class Selection(StrEnum):
    OVER = "over"
    UNDER = "under"


class Outcome(StrEnum):
    HIT = "hit"
    MISS = "miss"
    PUSH = "push"
    VOID = "void"


class MarketDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_key: str
    stat_key: StatKey
    period: Period
    kind: str
    lines: tuple[float, ...] = Field(min_length=1)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value != "total":
            raise ValueError(f"market kind '{value}' is not implemented yet")
        return value

    @property
    def target(self) -> tuple[StatKey, Period]:
        return (self.stat_key, self.period)


def load_markets(path: Path = MARKETS_PATH) -> dict[str, MarketDefinition]:
    raw = read_yaml(path).get("markets", [])
    markets = [MarketDefinition.model_validate(item) for item in raw]
    keys = [m.market_key for m in markets]
    if len(keys) != len(set(keys)):
        raise ConfigError("duplicate market_key in markets catalog")
    return {m.market_key: m for m in markets}


def settle_total(total: int | None, line: float, selection: Selection) -> Outcome:
    """Settle an over/under on a count. Half lines never push; integer lines push on equality."""
    if total is None:
        return Outcome.VOID
    if not math.isfinite(line) or line < 0:
        raise ValueError(f"invalid line {line}")
    if total == line:
        return Outcome.PUSH
    over = total > line
    hit = over if selection is Selection.OVER else not over
    return Outcome.HIT if hit else Outcome.MISS
