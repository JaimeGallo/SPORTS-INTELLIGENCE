"""HistoricalDataEngine: ingest -> validate -> normalize -> persist -> snapshot (dataset manifest).

Idempotent: canonical ids are deterministic and every insert is ON CONFLICT DO NOTHING, so re-ingesting the
same payload changes nothing. Raw payloads are stored content-addressed so the dataset can be rebuilt
without calling any external API (prompt section 34).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, Table, select
from sqlalchemy.dialects.postgresql import insert

from packages.common.config import PROJECT_ROOT, AppConfig, CompetitionConfig
from packages.common.ids import canonical_id, digest, sha256_bytes
from packages.data_quality.engine import QualityReport, check_matches
from packages.markets.catalog import load_markets
from packages.providers.base import HistoricalMatchProvider, RawPayload, Side
from packages.storage import schema as s

log = logging.getLogger(__name__)

PARSER_VERSION = "football-data-csv/1"
BOOKMAKERS = {
    "bet365": ("Bet365", False, False),
    "pinnacle": ("Pinnacle", False, True),
    "market_max": ("Market maximum (aggregate)", True, False),
    "market_avg": ("Market average (aggregate)", True, False),
}


@dataclass
class IngestionStats:
    payloads: int = 0
    matches: int = 0
    statistics: int = 0
    odds: int = 0
    issues: int = 0
    payload_ids: list[str] = field(default_factory=list)


def _insert_ignore(conn: Any, table: Table, rows: Sequence[dict[str, Any]], batch: int = 5000) -> None:
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        if chunk:
            conn.execute(insert(table).on_conflict_do_nothing(), list(chunk))


class HistoricalDataEngine:
    def __init__(self, engine: Engine, config: AppConfig, *, raw_root: Path | None = None) -> None:
        self._engine = engine
        self._config = config
        self._raw_root = raw_root or PROJECT_ROOT / config.ingestion.raw_dir
        self._tz = ZoneInfo(config.ingestion.provider_timezone)

    # ------------------------------------------------------------------ point-in-time rules (ADR-0003)
    def kickoff_utc(self, local_date: date, local_time: time | None) -> tuple[datetime, bool]:
        if local_time is None:
            hh, mm = (int(x) for x in self._config.ingestion.unknown_kickoff_local_time.split(":"))
            local_time, known = time(hh, mm), False
        else:
            known = True
        return datetime.combine(local_date, local_time, tzinfo=self._tz).astimezone(UTC), known

    def result_available_at(self, kickoff: datetime) -> datetime:
        return kickoff + timedelta(hours=self._config.ingestion.result_delay_hours)

    def odds_available_at(self, kickoff: datetime, is_closing: bool) -> datetime:
        # Closing odds are, by definition, only known at kickoff.
        if is_closing:
            return kickoff
        return kickoff - timedelta(hours=self._config.ingestion.prematch_odds_lead_hours)

    # ------------------------------------------------------------------ reference data
    def seed_reference(self, providers: Iterable[HistoricalMatchProvider]) -> None:
        with self._engine.begin() as conn:
            _insert_ignore(
                conn,
                s.data_sources,
                [
                    {
                        "source_id": p.info.source_id,
                        "priority": p.info.priority,
                        "license_note": p.info.license_note,
                        "capabilities": sorted(c.value for c in p.info.capabilities),
                    }
                    for p in providers
                ],
            )
            _insert_ignore(
                conn,
                s.bookmakers,
                [
                    {"bookmaker_id": k, "name": n, "is_aggregate": agg, "is_sharp": sharp}
                    for k, (n, agg, sharp) in BOOKMAKERS.items()
                ],
            )
            _insert_ignore(
                conn,
                s.markets,
                [
                    {
                        "market_key": m.market_key,
                        "stat_key": m.stat_key.value,
                        "period": m.period.value,
                        "kind": m.kind,
                    }
                    for m in load_markets().values()
                ],
            )
            _insert_ignore(
                conn,
                s.competitions,
                [
                    {
                        "competition_id": canonical_id("competition", c.competition_key),
                        "competition_key": c.competition_key,
                        "name": c.name,
                        "country": c.country,
                    }
                    for c in self._config.competitions
                ],
            )

    # ------------------------------------------------------------------ ingestion
    def _store_payload(self, payload: RawPayload) -> tuple[str, dict[str, Any]]:
        content_hash = sha256_bytes(payload.content)
        raw_id = f"raw_{content_hash[:24]}"
        path = self._raw_root / payload.source_id / f"{content_hash}.bin"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload.content)
        row = {
            "raw_payload_id": raw_id,
            "source_id": payload.source_id,
            "endpoint": payload.endpoint,
            "request_params": payload.params,
            "fetched_at": payload.fetched_at,
            "content_hash": content_hash,
            "size_bytes": len(payload.content),
            "storage_uri": str(path.relative_to(self._raw_root)),
        }
        return raw_id, row

    def ingest(
        self,
        provider: HistoricalMatchProvider,
        competitions: Iterable[CompetitionConfig],
        seasons: Iterable[str],
    ) -> IngestionStats:
        self.seed_reference([provider])
        totals = IngestionStats()
        season_list = list(seasons)
        for competition in competitions:
            for season in season_list:
                payload = provider.fetch_season(competition, season)
                raw_id, raw_row = self._store_payload(payload)
                report = check_matches(provider.parse(payload, competition, season))
                counts = self._persist(provider, competition, season, raw_id, raw_row, report)
                totals.payloads += 1
                totals.matches += counts["matches"]
                totals.statistics += counts["statistics"]
                totals.odds += counts["odds"]
                totals.issues += len(report.issues)
                totals.payload_ids.append(raw_id)
                log.info(
                    "ingested",
                    extra={
                        "competition": competition.competition_key,
                        "season": season,
                        "raw_payload_id": raw_id,
                        **counts,
                    },
                )
        return totals

    def _persist(
        self,
        provider: HistoricalMatchProvider,
        competition: CompetitionConfig,
        season: str,
        raw_id: str,
        raw_row: dict[str, Any],
        report: QualityReport,
    ) -> dict[str, int]:
        source = provider.info.source_id
        now = datetime.now(UTC)
        competition_id = canonical_id("competition", competition.competition_key)
        season_id = canonical_id("season", competition.competition_key, season)
        teams: dict[str, dict[str, Any]] = {}
        mappings: list[dict[str, Any]] = []
        match_rows: list[dict[str, Any]] = []
        stat_rows: list[dict[str, Any]] = []
        odds_rows: list[dict[str, Any]] = []

        def team_id(name: str) -> str:
            ref = f"{competition.country}:{name}"
            tid = canonical_id("team", competition.country, name)
            if tid not in teams:
                teams[tid] = {"team_id": tid, "name": name, "country": competition.country}
                mappings.append(_mapping(source, "team", ref, tid, now))
            return tid

        for m in report.matches:
            home, away = team_id(m.home_team), team_id(m.away_team)
            kickoff, known = self.kickoff_utc(m.local_date, m.local_time)
            match_id = canonical_id("match", home, away, m.local_date.isoformat())
            match_rows.append(
                {
                    "match_id": match_id,
                    "season_id": season_id,
                    "home_team_id": home,
                    "away_team_id": away,
                    "kickoff_at": kickoff,
                    "kickoff_time_known": known,
                    "status": "finished",
                }
            )
            mappings.append(_mapping(source, "match", m.provider_match_ref, match_id, now))
            available = self.result_available_at(kickoff)
            for (stat, period, side), value in m.stats.items():
                stat_rows.append(
                    {
                        "match_id": match_id,
                        "team_id": home if side is Side.HOME else away,
                        "period": period.value,
                        "stat_key": str(stat),
                        "value": value,
                        "source_id": source,
                        "available_at": available,
                        "raw_payload_id": raw_id,
                    }
                )
            for q in m.odds:
                odds_rows.append(
                    {
                        "match_id": match_id,
                        "bookmaker_id": q.bookmaker,
                        "market_key": q.market_key,
                        "line": q.line,
                        "selection": q.selection.value,
                        "decimal_odds": q.decimal_odds,
                        "is_closing": q.is_closing,
                        "available_at": self.odds_available_at(kickoff, q.is_closing),
                        "source_id": source,
                        "raw_payload_id": raw_id,
                    }
                )
        quality_rows = [
            {
                "match_id": None,
                "source_id": source,
                "raw_payload_id": raw_id,
                "kind": issue.kind,
                "severity": issue.severity.value,
                "details": {"provider_match_ref": issue.provider_match_ref, **issue.details},
                "detected_at": now,
            }
            for issue in report.issues
        ]
        with self._engine.begin() as conn:
            already = conn.execute(
                select(s.raw_payloads.c.raw_payload_id).where(s.raw_payloads.c.raw_payload_id == raw_id)
            ).first()
            _insert_ignore(conn, s.raw_payloads, [raw_row])
            _insert_ignore(
                conn, s.seasons, [{"season_id": season_id, "competition_id": competition_id, "label": season}]
            )
            _insert_ignore(conn, s.teams, list(teams.values()))
            _insert_ignore(conn, s.provider_entity_map, mappings)
            _insert_ignore(conn, s.matches, match_rows)
            _insert_ignore(conn, s.match_statistics, stat_rows)
            _insert_ignore(conn, s.odds_snapshots, odds_rows)
            if already is None:  # quality events are recorded once per payload
                _insert_ignore(conn, s.data_quality_events, quality_rows)
        return {"matches": len(match_rows), "statistics": len(stat_rows), "odds": len(odds_rows)}

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, payload_ids: Sequence[str], *, label: str = "") -> str:
        """Register a dataset version: a manifest of the exact raw payloads it is built from."""
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(
                    s.raw_payloads.c.raw_payload_id,
                    s.raw_payloads.c.source_id,
                    s.raw_payloads.c.endpoint,
                    s.raw_payloads.c.request_params,
                    s.raw_payloads.c.content_hash,
                ).where(s.raw_payloads.c.raw_payload_id.in_(list(payload_ids)))
            ).all()
            payloads = sorted(
                (
                    {
                        "raw_payload_id": r.raw_payload_id,
                        "source_id": r.source_id,
                        "endpoint": r.endpoint,
                        "params": r.request_params,
                        "content_hash": r.content_hash,
                    }
                    for r in rows
                ),
                key=lambda p: p["raw_payload_id"],
            )
            manifest = {
                "parser_version": PARSER_VERSION,
                "point_in_time_rules": self._config.ingestion.model_dump(
                    include={
                        "provider_timezone",
                        "result_delay_hours",
                        "unknown_kickoff_local_time",
                        "prematch_odds_lead_hours",
                    }
                ),
                "payloads": payloads,
                "label": label,
            }
            content_hash = digest(json.dumps(manifest, sort_keys=True), length=16)
            version = f"dataset-{content_hash.lower()}"
            _insert_ignore(
                conn,
                s.dataset_versions,
                [
                    {
                        "dataset_version": version,
                        "created_at": datetime.now(UTC),
                        "content_hash": content_hash,
                        "manifest": manifest,
                    }
                ],
            )
        manifests_dir = PROJECT_ROOT / self._config.ingestion.manifests_dir
        manifests_dir.mkdir(parents=True, exist_ok=True)
        (manifests_dir / f"{version}.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        return version


def _mapping(source: str, entity_type: str, ref: str, canonical: str, now: datetime) -> dict[str, Any]:
    return {
        "source_id": source,
        "entity_type": entity_type,
        "provider_ref": ref,
        "canonical_id": canonical,
        "mapped_by": "rule",
        "created_at": now,
    }
