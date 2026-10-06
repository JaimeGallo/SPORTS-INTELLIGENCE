"""EXP-001a runner: ingest -> point-in-time features -> models -> walk-forward calibration -> evaluation ->
market comparison (O/U 2.5) -> paper simulation -> persistence and report.

Deterministic: the same dataset version and configuration produce the same report (the report hash is
recorded). The backtest run id is derived from dataset version + config hash + code version.
"""

from __future__ import annotations

import itertools
import json
import logging
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from packages.backtesting import evaluation as ev
from packages.backtesting.market import load_odds, paper_flat, pick_quotes
from packages.backtesting.walk_forward import GenerationResult, generate_predictions
from packages.calibration import metrics as mt
from packages.common.config import PROJECT_ROOT, AppConfig, config_hash, read_yaml
from packages.common.ids import digest
from packages.common.secrets import get_secret
from packages.edge.engine import EdgeRules, SignalState, expected_value
from packages.features.store import FEATURE_VERSION, FeatureStore, load_match_facts
from packages.ingestion.engine import HistoricalDataEngine
from packages.markets.catalog import MarketDefinition, Period, StatKey, load_markets
from packages.models.count_models import Family, ModelSpec
from packages.models.team_ratings import RatingsConfig
from packages.providers.base import HistoricalMatchProvider
from packages.providers.football_data_csv import FootballDataCsvProvider
from packages.providers.footystats import FootyStatsProvider
from packages.providers.synthetic import SyntheticProvider
from packages.storage import schema as s

log = logging.getLogger(__name__)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetConfig(_Strict):
    stat: StatKey
    period: Period
    families: list[Family]


class GridConfig(_Strict):
    xi: list[float]
    window_days: list[int]
    ridge: list[float]
    min_matches: int = 60


class MarketConfig(_Strict):
    market_key: str
    line: float
    prematch_bookmakers: list[str]
    closing_bookmakers: list[str]
    min_edge: float = 0.03
    stake: float = 1.0


class BootstrapConfig(_Strict):
    n: int = 1000
    seed: int = 7


class ExperimentConfig(_Strict):
    experiment: str
    provider: str
    competitions: list[str]
    seasons: list[str]
    predict_seasons: list[str]
    validation_seasons: list[str]
    test_seasons: list[str]
    targets: list[TargetConfig]
    ratings_grid: GridConfig
    calibrators: list[str]
    calibration_min_rows: int = 300
    market: MarketConfig
    bootstrap: BootstrapConfig = Field(default_factory=BootstrapConfig)
    synthetic_seed: int = 7


def load_experiment_config(path: Path) -> ExperimentConfig:
    cfg = ExperimentConfig.model_validate(read_yaml(path))
    overlap = set(cfg.validation_seasons) & set(cfg.test_seasons)
    if overlap:
        raise ValueError(f"validation and test seasons overlap: {sorted(overlap)}")
    return cfg


def code_version() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "packages", "experiments"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_specs(cfg: ExperimentConfig) -> list[ModelSpec]:
    g = cfg.ratings_grid
    specs: list[ModelSpec] = []
    for target in cfg.targets:
        for family in target.families:
            for xi, window, ridge in itertools.product(g.xi, g.window_days, g.ridge):
                # ridge does not affect league_freq: keep a single variant of it
                if family is Family.LEAGUE_FREQ and ridge != g.ridge[0]:
                    continue
                rc = RatingsConfig(xi=xi, window_days=window, ridge=ridge, min_matches=g.min_matches)
                specs.append(ModelSpec(target.stat, target.period, family, rc))
    return specs


def make_provider(cfg: ExperimentConfig, app: AppConfig, allow_download: bool) -> HistoricalMatchProvider:
    if cfg.provider == "synthetic":
        return SyntheticProvider(cfg.seasons, seed=cfg.synthetic_seed)
    if cfg.provider == "footystats":
        return FootyStatsProvider(get_secret("FOOTYSTATS_API_KEY") or "")
    if cfg.provider == "football_data_csv":
        return FootballDataCsvProvider(
            PROJECT_ROOT / app.ingestion.raw_dir / "cache", allow_download=allow_download
        )
    raise ValueError(f"unknown provider {cfg.provider!r}")


def _generate_one(
    args: tuple[pd.DataFrame, list[ModelSpec], list[MarketDefinition], str, list[str], int],
) -> GenerationResult:
    facts, specs, markets, competition, seasons, lead = args
    return generate_predictions(
        facts,
        FeatureStore(facts),
        specs,
        markets,
        competitions=[competition],
        seasons=seasons,
        lead_minutes=lead,
    )


def run(
    app: AppConfig,
    cfg: ExperimentConfig,
    engine: Engine,
    *,
    allow_download: bool = True,
    workers: int = 4,
    out_root: Path | None = None,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    competitions = [c for c in app.competitions if c.competition_key in cfg.competitions]
    missing = set(cfg.competitions) - {c.competition_key for c in competitions}
    if missing:
        raise ValueError(f"competitions not in app config: {sorted(missing)}")

    # 1) ingestion + dataset version
    provider = make_provider(cfg, app, allow_download)
    ingestion = HistoricalDataEngine(engine, app)
    stats = ingestion.ingest(provider, competitions, cfg.seasons)
    dataset_version = ingestion.snapshot(stats.payload_ids, label=cfg.experiment)
    log.info(
        "dataset ready",
        extra={"dataset_version": dataset_version, **asdict(stats) | {"payload_ids": len(stats.payload_ids)}},
    )

    # 2) point-in-time predictions (one process per competition)
    facts = load_match_facts(engine, cfg.competitions, provider.info.source_id)
    markets = [m for m in load_markets().values() if any((t.stat, t.period) == m.target for t in cfg.targets)]
    specs = build_specs(cfg)
    jobs = [
        (
            facts[facts["competition_key"] == c].copy(),
            specs,
            markets,
            c,
            cfg.predict_seasons,
            app.prediction.lead_minutes,
        )
        for c in cfg.competitions
    ]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_generate_one, jobs))
    else:
        results = [_generate_one(j) for j in jobs]
    predictions = pd.concat([r.predictions for r in results], ignore_index=True)
    snapshots = pd.concat([r.snapshots for r in results], ignore_index=True)
    skipped: dict[str, int] = {}
    for r in results:
        for k, v in r.skipped.items():
            skipped[k] = skipped.get(k, 0) + v
    coherence = ev.coherence_violations(predictions)

    # 3) walk-forward calibration
    calibrated = ev.calibrate_walk_forward(
        predictions, cfg.calibrators, cfg.predict_seasons, min_rows=cfg.calibration_min_rows
    )
    calibrated["split"] = np.select(
        [
            calibrated["season_label"].isin(cfg.validation_seasons),
            calibrated["season_label"].isin(cfg.test_seasons),
        ],
        ["validation", "test"],
        default="warmup",
    )

    # 4) selection on validation only: best (ratings config, calibrator) per (target, family)
    val = ev.score_table(
        calibrated[calibrated["split"] == "validation"], ["target", "family", "model_version", "calibrator"]
    )
    selected = (
        val.groupby(["target", "family", "model_version", "calibrator"], as_index=False)
        .agg(log_loss=("log_loss", "mean"), brier=("brier", "mean"), ece=("ece", "mean"), n=("n", "sum"))
        .sort_values(["target", "family", "log_loss"])
        .groupby(["target", "family"])
        .head(1)
    )
    chosen = {(r.model_version, r.calibrator) for r in selected.itertuples()}
    is_chosen = pd.Series(
        [
            (m, c) in chosen
            for m, c in zip(calibrated["model_version"], calibrated["calibrator"], strict=True)
        ],
        index=calibrated.index,
    )
    final = calibrated[is_chosen]

    # 5) test evaluation of the selected variants only
    test = final[final["split"] == "test"]
    test_scores = ev.score_table(
        test,
        ["target", "family", "model_version", "calibrator", "market_key", "line"],
        with_noise_reference=True,
    )
    comparisons: list[dict[str, Any]] = []
    for target, group in selected.groupby("target"):
        base = group[group["family"] == Family.LEAGUE_FREQ.value]
        if base.empty:
            continue
        b = base.iloc[0]
        for r in group[group["family"] != Family.LEAGUE_FREQ.value].itertuples():
            for c in ev.compare_to_baseline(
                test,
                r.model_version,
                b.model_version,
                r.calibrator,
                b.calibrator,
                n_boot=cfg.bootstrap.n,
                seed=cfg.bootstrap.seed,
            ):
                comparisons.append(
                    {
                        "target": target,
                        "family": r.family,
                        "market_key": c.market_key,
                        "line": c.line,
                        "n": c.n,
                        "log_loss_diff": asdict(c.log_loss_diff),
                        "brier_diff": asdict(c.brier_diff),
                    }
                )
    reliability = {}
    for (model_version, calibrator), g in test.groupby(["model_version", "calibrator"]):
        reliability[f"{model_version}|{calibrator}"] = [
            asdict(b) for b in mt.reliability(g["p"].to_numpy(), g["y"].to_numpy())
        ]

    # 6) market comparison and paper simulation on the market line
    market_report, paper_bets = _market_section(engine, cfg, final, selected)

    # 7) persistence + report
    cfg_hash = config_hash(cfg)
    code = code_version()
    run_id = f"bt_{digest(dataset_version, cfg_hash, code, length=16).lower()}"
    summary: dict[str, Any] = {
        "experiment": cfg.experiment,
        "backtest_run_id": run_id,
        "dataset_version": dataset_version,
        "config_hash": cfg_hash,
        "code_version": code,
        "provider": cfg.provider,
        "ingestion": {k: v for k, v in asdict(stats).items() if k != "payload_ids"},
        "n_predictions": len(predictions),
        "n_snapshots": len(snapshots),
        "skipped_for_insufficient_history": skipped,
        "coherence_violations": coherence,
        "max_history_available_vs_as_of_ok": bool(
            (
                snapshots["max_available_at"].isna() | (snapshots["max_available_at"] <= snapshots["as_of"])
            ).all()
        ),
        "selected": selected.to_dict(orient="records"),
        "test_scores": test_scores.to_dict(orient="records"),
        "comparisons_vs_baseline": comparisons,
        "reliability_test": reliability,
        "market": market_report,
    }
    _persist(
        engine,
        run_id,
        cfg,
        cfg_hash,
        code,
        dataset_version,
        started,
        summary,
        final,
        snapshots,
        selected,
        paper_bets,
    )
    out_dir = (out_root or PROJECT_ROOT / "experiments" / cfg.experiment / "results") / run_id
    _write_report(out_dir, summary)
    return summary


def _market_section(
    engine: Engine, cfg: ExperimentConfig, final: pd.DataFrame, selected: pd.DataFrame
) -> tuple[dict[str, Any], pd.DataFrame]:
    mk = cfg.market
    on_line = final[
        (final["market_key"] == mk.market_key) & (final["line"] == mk.line) & (final["split"] == "test")
    ]
    if on_line.empty:
        return {"available": False, "reason": "no test predictions on the market line"}, pd.DataFrame()
    match_ids = sorted(on_line["match_id"].unique())
    odds = load_odds(engine, match_ids, mk.market_key, mk.line)
    if odds.empty:
        return {"available": False, "reason": "no odds for the market line"}, pd.DataFrame()
    as_of = on_line[["match_id", "as_of"]].drop_duplicates("match_id")
    pre = pick_quotes(odds, as_of, mk.prematch_bookmakers, closing=False)
    close = pick_quotes(odds, as_of, mk.closing_bookmakers, closing=True)
    rules = EdgeRules(min_edge=mk.min_edge)
    report: dict[str, Any] = {
        "available": True,
        "market_key": mk.market_key,
        "line": mk.line,
        "prematch_quotes": len(pre),
        "closing_quotes": len(close),
        "prematch_bookmakers": pre["bookmaker_id"].value_counts().to_dict(),
        "mean_prematch_overround": float(pre["overround"].mean()) if len(pre) else None,
        "models": {},
    }
    all_bets: list[pd.DataFrame] = []
    for (model_version, calibrator, family), g in on_line.groupby(["model_version", "calibrator", "family"]):
        entry: dict[str, Any] = {"family": family, "calibrator": calibrator}
        for name, quotes in (("prematch", pre), ("closing", close)):
            j = g.merge(quotes[["match_id", "q_over"]], on="match_id")
            if j.empty:
                continue
            y = j["y"].to_numpy()
            entry[f"vs_{name}"] = {
                "n": len(j),
                "model_log_loss": mt.log_loss(j["p"].to_numpy(), y),
                "market_log_loss": mt.log_loss(j["q_over"].to_numpy(), y),
                "model_brier": mt.brier(j["p"].to_numpy(), y),
                "market_brier": mt.brier(j["q_over"].to_numpy(), y),
                "log_loss_diff_model_minus_market": asdict(
                    mt.bootstrap_mean(
                        mt.per_obs_log_loss(j["p"].to_numpy(), y)
                        - mt.per_obs_log_loss(j["q_over"].to_numpy(), y),
                        n_boot=cfg.bootstrap.n,
                        seed=cfg.bootstrap.seed,
                    )
                ),
                "mean_abs_edge": float(np.mean(np.abs(j["p"] - j["q_over"]))),
            }
        paper = paper_flat(
            g,
            pre,
            close,
            rules,
            line=mk.line,
            stake=mk.stake,
            n_boot=cfg.bootstrap.n,
            seed=cfg.bootstrap.seed,
        )
        entry["paper"] = {
            "n_bets": paper.n_bets,
            "staked": paper.staked,
            "pnl": paper.pnl,
            "roi": asdict(paper.roi) if paper.roi else None,
            "hit_rate": paper.hit_rate,
            "mean_edge": paper.mean_edge,
            "mean_clv": paper.mean_clv,
            "max_drawdown": paper.max_drawdown,
        }
        report["models"][model_version] = entry
        if not paper.bets.empty:
            all_bets.append(paper.bets.assign(model_version=model_version, calibrator=calibrator))
    return report, (pd.concat(all_bets, ignore_index=True) if all_bets else pd.DataFrame())


def _persist(
    engine: Engine,
    run_id: str,
    cfg: ExperimentConfig,
    cfg_hash: str,
    code: str,
    dataset_version: str,
    started: datetime,
    summary: dict[str, Any],
    final: pd.DataFrame,
    snapshots: pd.DataFrame,
    selected: pd.DataFrame,
    paper_bets: pd.DataFrame,
) -> None:
    now = datetime.now(UTC)
    specs = {spec.model_version: spec for spec in build_specs(cfg)}
    final = final.copy()
    final["prediction_id"] = [
        f"pred_{digest(run_id, m, v, k, line, c, length=16).lower()}"
        for m, v, k, line, c in zip(
            final["match_id"],
            final["model_version"],
            final["market_key"],
            final["line"],
            final["calibrator"],
            strict=True,
        )
    ]
    keep_snaps = snapshots[snapshots["model_version"].isin(set(final["model_version"]))]
    mk = cfg.market
    with engine.begin() as conn:
        conn.execute(delete(s.paper_bets).where(s.paper_bets.c.backtest_run_id == run_id))
        old_preds = s.predictions.c.backtest_run_id == run_id
        conn.execute(
            delete(s.settlements).where(
                s.settlements.c.prediction_id.in_(
                    s.predictions.select().with_only_columns(s.predictions.c.prediction_id).where(old_preds)
                )
            )
        )
        conn.execute(delete(s.predictions).where(old_preds))
        conn.execute(delete(s.backtest_runs).where(s.backtest_runs.c.backtest_run_id == run_id))
        conn.execute(
            s.backtest_runs.insert(),
            [
                {
                    "backtest_run_id": run_id,
                    "experiment": cfg.experiment,
                    "config": cfg.model_dump(mode="json"),
                    "config_hash": cfg_hash,
                    "dataset_version": dataset_version,
                    "code_version": code,
                    "started_at": started,
                    "finished_at": now,
                    "status": "finished",
                    "metrics": json.loads(json.dumps(_jsonable(summary))),
                }
            ],
        )
        conn.execute(
            pg_insert(s.model_versions).on_conflict_do_nothing(),
            [
                {
                    "model_version": v,
                    "target": f"{specs[v].stat.value}_{specs[v].period.value}",
                    "algorithm": specs[v].family.value,
                    "hyperparameters": specs[v].hyperparameters(),
                    "feature_version": FEATURE_VERSION,
                    "status": "candidate",
                    "created_at": now,
                }
                for v in sorted(set(final["model_version"]))
            ],
        )
        snap_rows = [
            {
                "feature_snapshot_id": r.feature_snapshot_id,
                "match_id": r.match_id,
                "as_of": r.as_of,
                "feature_version": FEATURE_VERSION,
                "n_history": int(r.n_history),
                "max_available_at": None if pd.isna(r.max_available_at) else r.max_available_at,
                "features": {
                    **r.features,
                    "model_version": r.model_version,
                    "fit_as_of": r.fit_as_of.isoformat(),
                },
            }
            for r in keep_snaps.itertuples(index=False)
        ]
        for start in range(0, len(snap_rows), 5000):
            conn.execute(
                pg_insert(s.feature_snapshots).on_conflict_do_nothing(), snap_rows[start : start + 5000]
            )
        pred_rows = [
            {
                "prediction_id": r.prediction_id,
                "backtest_run_id": run_id,
                "match_id": r.match_id,
                "mode": "backtest",
                "as_of": r.as_of,
                "market_key": r.market_key,
                "line": r.line,
                "model_version": r.model_version,
                "calibrator": r.calibrator,
                "probability_raw": float(r.p_raw),
                "probability": float(r.p),
                "fair_odds": float(1 / r.p),
                "feature_snapshot_id": r.feature_snapshot_id,
                "created_at": now,
            }
            for r in final.itertuples(index=False)
        ]
        settle_rows = [
            {
                "prediction_id": r.prediction_id,
                "actual_total": int(r.actual_total),
                "outcome": "hit" if r.y == 1 else "miss",
            }
            for r in final.itertuples(index=False)
        ]
        for start in range(0, len(pred_rows), 5000):
            conn.execute(s.predictions.insert(), pred_rows[start : start + 5000])
            conn.execute(s.settlements.insert(), settle_rows[start : start + 5000])
        if not paper_bets.empty:
            ids = final.set_index(["match_id", "model_version", "calibrator", "market_key", "line"])[
                "prediction_id"
            ]
            bet_rows = []
            for b in paper_bets.itertuples(index=False):
                pid = ids.get((b.match_id, b.model_version, b.calibrator, mk.market_key, mk.line))
                bet_rows.append(
                    {
                        "paper_bet_id": f"pb_{digest(run_id, pid, length=16).lower()}",
                        "backtest_run_id": run_id,
                        "prediction_id": pid,
                        "selection": b.selection,
                        "bookmaker_id": b.bookmaker_id,
                        "decimal_odds": float(b.decimal_odds),
                        "stake": float(b.stake),
                        "outcome": b.outcome,
                        "pnl": float(b.pnl),
                        "closing_odds": None,
                    }
                )
            conn.execute(s.paper_bets.insert(), bet_rows)
            # record market fields on the predictions that triggered a paper bet
            for b in paper_bets.itertuples(index=False):
                pid = ids.get((b.match_id, b.model_version, b.calibrator, mk.market_key, mk.line))
                conn.execute(
                    s.predictions.update()
                    .where(s.predictions.c.prediction_id == pid)
                    .values(
                        market_bookmaker=b.bookmaker_id,
                        market_odds=float(b.decimal_odds),
                        market_probability=float(b.q),
                        edge=float(b.edge),
                        expected_value=float(expected_value(b.p, b.decimal_odds)),
                        signal_state=SignalState.POTENTIAL_EDGE.value,
                    )
                )


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating | float):
        value = float(obj)
        return None if not np.isfinite(value) else round(value, 6)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _write_report(out_dir: Path, summary: dict[str, Any]) -> None:
    from packages.experiments.report import render_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    data = _jsonable(summary)
    payload = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    (out_dir / "summary.json").write_text(payload, encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(data), encoding="utf-8")
