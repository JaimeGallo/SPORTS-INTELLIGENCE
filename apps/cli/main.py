"""`jevs` command line.

jevs db-upgrade
jevs experiment exp001a [--provider synthetic] [--no-download] [--workers 4]
jevs footystats leagues [--country Colombia]
jevs ingest --provider footystats --competition COL-PA --seasons 2023 2024
"""

from __future__ import annotations

import os

# One BLAS/OpenMP thread per process: the experiment already runs one process per competition, and nested
# thread pools only oversubscribe the CPUs. Must be set before numpy/scipy are imported.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import logging
import sys
from pathlib import Path

from packages.common.config import PROJECT_ROOT, load_config
from packages.common.errors import JEVSError
from packages.common.logging import configure_logging
from packages.common.secrets import get_secret, load_dotenv, sensitive_values
from packages.ingestion.engine import HistoricalDataEngine
from packages.providers.base import HistoricalMatchProvider
from packages.providers.football_data_csv import FootballDataCsvProvider
from packages.providers.footystats import FootyStatsProvider
from packages.providers.synthetic import SyntheticProvider
from packages.storage.db import describe, make_engine, upgrade


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except JEVSError as exc:  # expected operational errors: clean message, no traceback
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _main(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="jevs", description="JEV Sports Intelligence (research, no real money)"
    )
    parser.add_argument("--config", type=Path, help="profile YAML merged over config/default.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("db-upgrade", help="apply database migrations")
    exp = sub.add_parser("experiment", help="run an experiment")
    exp.add_argument("name", choices=["exp001a"])
    exp.add_argument("--experiment-config", type=Path, help="defaults to experiments/<name>/config.yaml")
    exp.add_argument(
        "--provider",
        choices=["football_data_csv", "footystats", "synthetic"],
        help="override the data provider",
    )
    exp.add_argument("--no-download", action="store_true", help="use only locally cached provider files")
    exp.add_argument("--workers", type=int, default=4)
    fs = sub.add_parser("footystats", help="FootyStats helpers (needs FOOTYSTATS_API_KEY)")
    fs_sub = fs.add_subparsers(dest="action", required=True)
    leagues = fs_sub.add_parser("leagues", help="list league seasons and their ids available to the key")
    leagues.add_argument("--country")
    ing = sub.add_parser("ingest", help="ingest competition seasons into the database")
    ing.add_argument("--provider", required=True, choices=["football_data_csv", "footystats", "synthetic"])
    ing.add_argument("--competition", required=True, action="append", help="competition_key (repeatable)")
    ing.add_argument("--seasons", required=True, nargs="+")
    ing.add_argument("--no-download", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    app = load_config(args.config)
    configure_logging(app.logging.level, json_format=app.logging.json_format, secrets=sensitive_values())
    log = logging.getLogger("jevs")
    log.info("database", extra={"url": describe(app.database.url)})

    if args.command == "db-upgrade":
        upgrade(app.database.url)
        return 0

    if args.command == "footystats":
        provider = FootyStatsProvider(get_secret("FOOTYSTATS_API_KEY") or "")
        for row in provider.list_leagues(args.country):
            print(f"{row['country']} | {row['name']} | {row['season_label']} | season_id={row['season_id']}")
        return 0

    if args.command == "ingest":
        selected = [c for c in app.competitions if c.competition_key in set(args.competition)]
        unknown = set(args.competition) - {c.competition_key for c in selected}
        if unknown:
            parser.error(f"unknown competitions: {sorted(unknown)}")
        source: HistoricalMatchProvider
        if args.provider == "footystats":
            source = FootyStatsProvider(get_secret("FOOTYSTATS_API_KEY") or "")
        elif args.provider == "synthetic":
            source = SyntheticProvider(args.seasons)
        else:
            source = FootballDataCsvProvider(
                PROJECT_ROOT / app.ingestion.raw_dir / "cache", allow_download=not args.no_download
            )
        upgrade(app.database.url)
        ingestion = HistoricalDataEngine(make_engine(app.database.url), app)
        stats = ingestion.ingest(source, selected, args.seasons)
        version = ingestion.snapshot(stats.payload_ids, label=f"ingest:{args.provider}")
        print(
            f"{version}: {stats.payloads} payloads, {stats.matches} matches, {stats.statistics} statistics, "
            f"{stats.odds} odds, {stats.issues} quality issues"
        )
        return 0

    if args.command == "experiment":
        from packages.experiments.exp001a import load_experiment_config, run

        path = args.experiment_config or PROJECT_ROOT / "experiments" / args.name / "config.yaml"
        cfg = load_experiment_config(path)
        if args.provider:
            cfg = cfg.model_copy(update={"provider": args.provider})
        upgrade(app.database.url)
        summary = run(
            app, cfg, make_engine(app.database.url), allow_download=not args.no_download, workers=args.workers
        )
        print(
            f"run {summary['backtest_run_id']} on {summary['dataset_version']}: "
            f"{summary['n_predictions']} predictions"
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
