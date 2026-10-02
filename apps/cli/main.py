"""`jevs` command line.

jevs db-upgrade
jevs experiment exp001a [--provider synthetic] [--no-download] [--workers 4]
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
from packages.common.logging import configure_logging
from packages.common.secrets import load_dotenv, sensitive_values
from packages.storage.db import describe, make_engine, upgrade


def main(argv: list[str] | None = None) -> int:
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
        "--provider", choices=["football_data_csv", "synthetic"], help="override the data provider"
    )
    exp.add_argument("--no-download", action="store_true", help="use only locally cached provider files")
    exp.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    app = load_config(args.config)
    configure_logging(app.logging.level, json_format=app.logging.json_format, secrets=sensitive_values())
    log = logging.getLogger("jevs")
    log.info("database", extra={"url": describe(app.database.url)})

    if args.command == "db-upgrade":
        upgrade(app.database.url)
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
