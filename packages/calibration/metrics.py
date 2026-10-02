"""Probability scoring and calibration diagnostics for binary events."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EPS = 1e-6


def _clip(p: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p, y = _clip(p), np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def per_obs_log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p, y = _clip(p), np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float


def reliability(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[ReliabilityBin]:
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    bins: list[ReliabilityBin] = []
    for b in range(n_bins):
        mask = idx == b
        count = int(mask.sum())
        bins.append(
            ReliabilityBin(
                lower=float(edges[b]),
                upper=float(edges[b + 1]),
                count=count,
                mean_predicted=float(p[mask].mean()) if count else float("nan"),
                observed_rate=float(y[mask].mean()) if count else float("nan"),
            )
        )
    return bins


def expected_calibration_error(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> float:
    """ECE with equal-width bins: sum_b (n_b / n) * |mean_pred_b - observed_b|."""
    total = len(p)
    if total == 0:
        return float("nan")
    return float(
        sum(
            b.count / total * abs(b.mean_predicted - b.observed_rate)
            for b in reliability(p, y, n_bins)
            if b.count
        )
    )


def ece_noise_reference(p: np.ndarray, n_bins: int = 10, n_sims: int = 200, seed: int = 0) -> float:
    """95th percentile of the ECE that a PERFECTLY calibrated model with these same probabilities would show
    on a sample of this size. An observed ECE below it is indistinguishable from sampling noise."""
    p = np.asarray(p, float)
    if len(p) == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    sims = [
        expected_calibration_error(p, (rng.uniform(size=len(p)) < p).astype(int), n_bins)
        for _ in range(n_sims)
    ]
    return float(np.quantile(sims, 0.95))


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def bootstrap_mean(
    values: np.ndarray,
    *,
    groups: np.ndarray | None = None,
    n_boot: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> Interval:
    """Percentile bootstrap CI of a mean. With `groups` (e.g. match ids) whole groups are resampled together,
    because several lines of the same match are not independent observations."""
    values = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    if groups is None:
        n = len(values)
        samples = rng.integers(0, n, size=(n_boot, n))
        means = values[samples].mean(axis=1)
    else:
        codes, inverse = np.unique(groups, return_inverse=True)
        sums = np.bincount(inverse, values, len(codes))
        counts = np.bincount(inverse, minlength=len(codes)).astype(float)
        picks = rng.integers(0, len(codes), size=(n_boot, len(codes)))
        means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    return Interval(
        estimate=float(values.mean()),
        low=float(np.quantile(means, alpha / 2)),
        high=float(np.quantile(means, 1 - alpha / 2)),
    )
