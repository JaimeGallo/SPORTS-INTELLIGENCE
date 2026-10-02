"""Walk-forward calibration and evaluation.

Calibrators for season S are fitted only on predictions from seasons < S (expanding window). Metrics are
reported per (model, calibrator, market, line) and split; differences against the baseline use paired
bootstrap intervals resampled by match.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from packages.calibration import metrics as mt
from packages.calibration.methods import make_calibrator

GROUP = ["model_version", "market_key", "line"]


def calibrate_walk_forward(
    predictions: pd.DataFrame,
    calibrators: Sequence[str],
    season_order: Sequence[str],
    *,
    min_rows: int = 300,
) -> pd.DataFrame:
    """Return predictions in long format with columns `calibrator` and `p` (calibrated probability).

    Rows of a season with fewer than `min_rows` prior predictions are kept uncalibrated and flagged with
    `calibrated = False` (they are excluded from the reported metrics of calibrated variants).
    """
    order = {s: i for i, s in enumerate(season_order)}
    pred = predictions.assign(season_idx=predictions["season_label"].map(order))
    out: list[pd.DataFrame] = []
    for _, group in pred.groupby(GROUP, sort=False):
        for name in calibrators:
            parts: list[pd.DataFrame] = []
            for season_idx, season_rows in group.groupby("season_idx", sort=True):
                past = group[group["season_idx"] < season_idx]
                calibrator = make_calibrator(name)
                enough = name == "identity" or len(past) >= min_rows
                if enough:
                    calibrator.fit(past["p_raw"].to_numpy(), past["y"].to_numpy())
                p = calibrator.transform(season_rows["p_raw"].to_numpy())
                parts.append(
                    season_rows.assign(calibrator=name, p=np.clip(p, 1e-6, 1 - 1e-6), calibrated=enough)
                )
            out.append(pd.concat(parts))
    return pd.concat(out, ignore_index=True) if out else pred.iloc[0:0]


def score_table(calibrated: pd.DataFrame, by: Sequence[str]) -> pd.DataFrame:
    rows = []
    for key, g in calibrated[calibrated["calibrated"]].groupby(list(by), sort=True):
        p, y = g["p"].to_numpy(), g["y"].to_numpy()
        rows.append(
            {
                **dict(zip(by, key if isinstance(key, tuple) else (key,), strict=True)),
                "n": len(g),
                "base_rate": float(y.mean()),
                "mean_p": float(p.mean()),
                "brier": mt.brier(p, y),
                "log_loss": mt.log_loss(p, y),
                "ece": mt.expected_calibration_error(p, y),
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class Comparison:
    model_version: str
    baseline_version: str
    market_key: str
    line: float
    n: int
    log_loss_diff: mt.Interval  # model - baseline (negative = model better)
    brier_diff: mt.Interval


def compare_to_baseline(
    calibrated: pd.DataFrame,
    model_version: str,
    baseline_version: str,
    calibrator: str,
    baseline_calibrator: str,
    *,
    n_boot: int,
    seed: int,
) -> list[Comparison]:
    keys = ["match_id", "market_key", "line"]
    a = calibrated[
        (calibrated["model_version"] == model_version)
        & (calibrated["calibrator"] == calibrator)
        & calibrated["calibrated"]
    ]
    b = calibrated[
        (calibrated["model_version"] == baseline_version)
        & (calibrated["calibrator"] == baseline_calibrator)
        & calibrated["calibrated"]
    ]
    joined = a[[*keys, "p", "y"]].merge(b[[*keys, "p"]], on=keys, suffixes=("", "_base"))
    out: list[Comparison] = []
    for (market_key, line), g in joined.groupby(["market_key", "line"], sort=True):
        y = g["y"].to_numpy()
        ll = mt.per_obs_log_loss(g["p"].to_numpy(), y) - mt.per_obs_log_loss(g["p_base"].to_numpy(), y)
        br = (g["p"].to_numpy() - y) ** 2 - (g["p_base"].to_numpy() - y) ** 2
        groups = g["match_id"].to_numpy()
        out.append(
            Comparison(
                model_version,
                baseline_version,
                str(market_key),
                float(line),
                len(g),
                mt.bootstrap_mean(ll, groups=groups, n_boot=n_boot, seed=seed),
                mt.bootstrap_mean(br, groups=groups, n_boot=n_boot, seed=seed),
            )
        )
    return out


def coherence_violations(predictions: pd.DataFrame) -> int:
    """P(Over L) must not increase with L for the same match, model and market."""
    ordered = predictions.sort_values(["model_version", "match_id", "market_key", "line"])
    diffs = ordered.groupby(["model_version", "match_id", "market_key"])["p_raw"].diff()
    return int((diffs > 1e-9).sum())
