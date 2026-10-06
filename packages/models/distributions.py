"""Count distributions. Every market probability is derived from one of these."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

from packages.common.errors import ModelError

DEFAULT_MAX_COUNT = 40


@dataclass(frozen=True)
class CountDistribution:
    """P(total = k) for k = 0..K. The tail mass beyond K is folded into the last bucket."""

    pmf: np.ndarray

    def __post_init__(self) -> None:
        if self.pmf.ndim != 1 or len(self.pmf) < 2:
            raise ModelError("pmf must be a 1-D array with at least two buckets")
        if not np.all(np.isfinite(self.pmf)) or np.any(self.pmf < -1e-12):
            raise ModelError("pmf contains invalid probabilities")
        total = float(self.pmf.sum())
        if abs(total - 1.0) > 1e-6:
            raise ModelError(f"pmf sums to {total}, expected 1")

    @property
    def mean(self) -> float:
        return float(np.dot(np.arange(len(self.pmf)), self.pmf))

    def prob_over(self, line: float) -> float:
        """P(total > line): the Over probability for half lines; for integer lines pushes are excluded."""
        threshold = math.floor(line)  # total > line  <=>  total >= floor(line) + 1
        return float(np.clip(self.pmf[threshold + 1 :].sum(), 0.0, 1.0))

    def prob_under(self, line: float) -> float:
        threshold = math.ceil(line)  # total < line  <=>  total <= ceil(line) - 1
        return float(np.clip(self.pmf[:threshold].sum(), 0.0, 1.0))


def _finalize(pmf: np.ndarray) -> CountDistribution:
    pmf = np.clip(pmf, 0.0, None)
    return CountDistribution(pmf / pmf.sum())


def poisson(mean: float, max_count: int = DEFAULT_MAX_COUNT) -> CountDistribution:
    if not math.isfinite(mean) or mean <= 0:
        raise ModelError(f"invalid Poisson mean {mean}")
    k = np.arange(max_count + 1)
    pmf = stats.poisson.pmf(k, mean)
    pmf[-1] += stats.poisson.sf(max_count, mean)
    return _finalize(pmf)


def negative_binomial(
    mean: float, dispersion: float, max_count: int = DEFAULT_MAX_COUNT
) -> CountDistribution:
    """NB with Var = mean + dispersion * mean^2. dispersion -> 0 recovers the Poisson."""
    if dispersion <= 1e-9:
        return poisson(mean, max_count)
    if not math.isfinite(mean) or mean <= 0:
        raise ModelError(f"invalid NB mean {mean}")
    size = 1.0 / dispersion
    prob = size / (size + mean)
    k = np.arange(max_count + 1)
    pmf = stats.nbinom.pmf(k, size, prob)
    pmf[-1] += stats.nbinom.sf(max_count, size, prob)
    return _finalize(pmf)


def dixon_coles_rho_limits(lam_home: float, lam_away: float) -> tuple[float, float]:
    """Interval of rho for which the four low-score factors stay positive for these lambdas.

    The factors are 1 - l_h*l_a*rho (0-0), 1 + l_h*rho (0-1), 1 + l_a*rho (1-0) and 1 - rho (1-1). A rho
    fitted on the training matches only respects the lambdas seen there; a lopsided fixture can fall outside.
    """
    lower = -0.999 / max(lam_home, lam_away)
    upper = min(0.999, 0.999 / (lam_home * lam_away))
    return lower, upper


def dixon_coles_total(lam_home: float, lam_away: float, rho: float, max_goals: int = 15) -> CountDistribution:
    """Total goals under Dixon-Coles (1997): independent Poissons with a low-score correction."""
    k = np.arange(max_goals + 1)
    home = stats.poisson.pmf(k, lam_home)
    away = stats.poisson.pmf(k, lam_away)
    joint = np.outer(home, away)
    joint[0, 0] *= 1 - lam_home * lam_away * rho
    joint[0, 1] *= 1 + lam_home * rho
    joint[1, 0] *= 1 + lam_away * rho
    joint[1, 1] *= 1 - rho
    if np.any(joint < 0):
        raise ModelError(f"rho={rho} gives negative probabilities for lambdas {lam_home:.3f}, {lam_away:.3f}")
    totals = np.zeros(2 * max_goals + 1)
    for i in range(max_goals + 1):
        totals[i : i + max_goals + 1] += joint[i]
    return _finalize(totals)


def empirical(
    counts: np.ndarray,
    weights: np.ndarray | None = None,
    *,
    max_count: int = DEFAULT_MAX_COUNT,
    smoothing: float = 0.5,
) -> CountDistribution:
    """Weighted histogram with additive smoothing over 0..max(observed)+3, clipped to max_count."""
    counts = np.clip(counts.astype(int), 0, max_count)
    w = np.ones(len(counts)) if weights is None else weights
    upper = min(max_count, int(counts.max()) + 3) if len(counts) else 5
    pmf = np.bincount(counts, weights=w, minlength=upper + 1)[: upper + 1].astype(float)
    pmf = pmf + smoothing * (w.sum() / max(len(w), 1)) / (upper + 1)
    full = np.zeros(max_count + 1)
    full[: upper + 1] = pmf
    return _finalize(full)
