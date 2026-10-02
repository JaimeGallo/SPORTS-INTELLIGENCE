from __future__ import annotations

import numpy as np
import pytest

from packages.calibration import metrics as mt
from packages.calibration.methods import make_calibrator


def _sample(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.1, 0.9, n)
    return true_p, (rng.uniform(size=n) < true_p).astype(int)


def test_scores_on_known_cases() -> None:
    y = np.array([1, 0, 1, 0])
    assert mt.brier(y.astype(float), y) == 0.0
    assert mt.brier(np.full(4, 0.5), y) == pytest.approx(0.25)
    assert mt.log_loss(np.full(4, 0.5), y) == pytest.approx(np.log(2))


def test_calibrated_probabilities_have_small_ece() -> None:
    p, y = _sample(20_000, 1)
    assert mt.expected_calibration_error(p, y) < 0.015


@pytest.mark.parametrize("name", ["platt", "isotonic"])
def test_calibrators_repair_overconfidence_out_of_sample(name: str) -> None:
    p, y = _sample(20_000, 2)
    overconfident = 1 / (1 + np.exp(-2.5 * np.log(p / (1 - p))))
    calibrator = make_calibrator(name).fit(overconfident[:10_000], y[:10_000])
    fixed = calibrator.transform(overconfident[10_000:])
    raw_ece = mt.expected_calibration_error(overconfident[10_000:], y[10_000:])
    assert mt.expected_calibration_error(fixed, y[10_000:]) < raw_ece / 3
    assert mt.log_loss(fixed, y[10_000:]) < mt.log_loss(overconfident[10_000:], y[10_000:])


def test_bootstrap_interval_contains_estimate_and_groups_are_resampled_together() -> None:
    values = np.random.default_rng(3).normal(0.1, 1.0, 2000)
    ci = mt.bootstrap_mean(values, n_boot=500, seed=1)
    assert ci.low < ci.estimate < ci.high
    grouped = mt.bootstrap_mean(values, groups=np.repeat(np.arange(500), 4), n_boot=500, seed=1)
    assert grouped.low < grouped.estimate < grouped.high
