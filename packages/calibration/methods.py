"""Probability calibrators. Always fitted on PAST predictions only (earlier seasons) and applied forward.

- identity: no calibration (reference);
- platt:    logistic regression on logit(p) (2 parameters, robust with little data);
- isotonic: monotone non-parametric mapping (flexible, needs more data).
Beta calibration is a planned addition.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

EPS = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


class Calibrator(ABC):
    name: str

    @abstractmethod
    def fit(self, p: np.ndarray, y: np.ndarray) -> Calibrator: ...

    @abstractmethod
    def transform(self, p: np.ndarray) -> np.ndarray: ...

    def describe(self) -> dict[str, float]:
        return {}


class IdentityCalibrator(Calibrator):
    name = "identity"

    def fit(self, p: np.ndarray, y: np.ndarray) -> IdentityCalibrator:
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(p, float), 0.0, 1.0)


class PlattCalibrator(Calibrator):
    name = "platt"

    def __init__(self) -> None:
        self._model = LogisticRegression(C=1e6)
        self._fitted = False

    def fit(self, p: np.ndarray, y: np.ndarray) -> PlattCalibrator:
        y = np.asarray(y, int)
        if len(np.unique(y)) < 2:
            return self  # degenerate sample: stay identity
        self._model.fit(_logit(p).reshape(-1, 1), y)
        self._fitted = True
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.clip(np.asarray(p, float), 0.0, 1.0)
        return self._model.predict_proba(_logit(p).reshape(-1, 1))[:, 1]

    def describe(self) -> dict[str, float]:
        if not self._fitted:
            return {}
        return {"slope": float(self._model.coef_[0][0]), "intercept": float(self._model.intercept_[0])}


class IsotonicCalibrator(Calibrator):
    name = "isotonic"

    def __init__(self) -> None:
        self._model = IsotonicRegression(y_min=EPS, y_max=1 - EPS, out_of_bounds="clip")
        self._fitted = False

    def fit(self, p: np.ndarray, y: np.ndarray) -> IsotonicCalibrator:
        if len(np.unique(np.asarray(y, int))) < 2:
            return self
        self._model.fit(np.asarray(p, float), np.asarray(y, float))
        self._fitted = True
        return self

    def transform(self, p: np.ndarray) -> np.ndarray:
        if not self._fitted:
            return np.clip(np.asarray(p, float), 0.0, 1.0)
        return np.asarray(self._model.predict(np.asarray(p, float)), float)


CALIBRATORS: dict[str, type[Calibrator]] = {
    IdentityCalibrator.name: IdentityCalibrator,
    PlattCalibrator.name: PlattCalibrator,
    IsotonicCalibrator.name: IsotonicCalibrator,
}


def make_calibrator(name: str) -> Calibrator:
    return CALIBRATORS[name]()
