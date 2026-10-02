"""Data quality checks on raw matches, before anything reaches the canonical tables.

Each problem becomes a `QualityIssue` (persisted as a data_quality_event). Errors remove the affected data
(a match's statistics, or one odds pair); warnings keep it but are recorded. Nothing is fixed silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from packages.markets.catalog import Period, Selection, StatKey
from packages.providers.base import RawMatch, RawOdds, Side

AGGREGATE_BOOKMAKERS = frozenset({"market_max", "market_avg"})
MAX_PLAUSIBLE = {StatKey.GOALS: 15, StatKey.CORNERS: 35}
OVERROUND_RANGE = (0.98, 1.30)


class Severity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class QualityIssue:
    kind: str
    severity: Severity
    provider_match_ref: str | None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityReport:
    matches: list[RawMatch]
    issues: list[QualityIssue]

    def score(self, provider_match_ref: str) -> float:
        """1.0 = no issues; each warning costs 0.1 and each error 0.4 (floored at 0)."""
        penalty = sum(
            0.4 if i.severity is Severity.ERROR else 0.1
            for i in self.issues
            if i.provider_match_ref == provider_match_ref
        )
        return max(0.0, 1.0 - penalty)


def _check_stats(match: RawMatch, issues: list[QualityIssue]) -> RawMatch:
    ref = match.provider_match_ref
    if match.missing_fields:
        issues.append(
            QualityIssue("missing_fields", Severity.WARNING, ref, {"fields": list(match.missing_fields)})
        )
    stats = match.stats
    bad: list[str] = []
    for (stat, period, side), value in stats.items():
        if value < 0:
            bad.append(f"negative {stat} {period} {side}")
        limit = MAX_PLAUSIBLE.get(stat) if isinstance(stat, StatKey) else None
        if limit is not None and value > limit:
            issues.append(
                QualityIssue("implausible_value", Severity.WARNING, ref, {"stat": str(stat), "value": value})
            )
    for stat in (StatKey.GOALS, StatKey.CORNERS):
        for side in Side:
            first_half = stats.get((stat, Period.FIRST_HALF, side))
            full_time = stats.get((stat, Period.FULL_TIME, side))
            if first_half is not None and full_time is not None and first_half > full_time:
                bad.append(f"{stat} 1H > FT for {side}")
    if bad:
        issues.append(QualityIssue("inconsistent_stats", Severity.ERROR, ref, {"problems": bad}))
        return replace(match, stats={})
    return match


def _check_odds(match: RawMatch, issues: list[QualityIssue]) -> RawMatch:
    ref = match.provider_match_ref
    groups: dict[tuple[str, str, float, bool], dict[Selection, RawOdds]] = {}
    for quote in match.odds:
        groups.setdefault((quote.bookmaker, quote.market_key, quote.line, quote.is_closing), {})[
            quote.selection
        ] = quote
    kept: list[RawOdds] = []
    for key, pair in groups.items():
        prices = {sel: q.decimal_odds for sel, q in pair.items()}
        if any(price <= 1.0 for price in prices.values()):
            issues.append(
                QualityIssue("invalid_odds", Severity.ERROR, ref, {"group": str(key), "prices": str(prices)})
            )
            continue
        if len(pair) == 2 and key[0] not in AGGREGATE_BOOKMAKERS:
            overround = sum(1 / p for p in prices.values())
            low, high = OVERROUND_RANGE
            if not low <= overround <= high:
                issues.append(
                    QualityIssue(
                        "implausible_overround",
                        Severity.ERROR,
                        ref,
                        {"group": str(key), "overround": overround},
                    )
                )
                continue
        kept.extend(pair.values())
    return replace(match, odds=tuple(kept))


def check_matches(matches: list[RawMatch]) -> QualityReport:
    issues: list[QualityIssue] = []
    seen: set[str] = set()
    clean: list[RawMatch] = []
    for match in matches:
        ref = match.provider_match_ref
        if ref in seen:
            issues.append(QualityIssue("duplicate_match", Severity.ERROR, ref))
            continue
        seen.add(ref)
        if match.home_team == match.away_team:
            issues.append(QualityIssue("same_team", Severity.ERROR, ref))
            continue
        clean.append(_check_odds(_check_stats(match, issues), issues))
    return QualityReport(clean, issues)
