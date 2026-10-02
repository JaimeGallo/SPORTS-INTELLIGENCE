"""Walk-forward prediction generation.

For every match to predict, `as_of = kickoff - lead`. Matches are grouped in weekly buckets per
competition; one model is fitted per bucket at the EARLIEST as_of of the bucket, so every match in it is
predicted with information that was available before its own as_of (conservative, never leaky). Nothing
is shuffled: time only moves forward.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from packages.common.errors import LeakageError, ModelError
from packages.features.store import FeatureStore, target_columns
from packages.markets.catalog import MarketDefinition
from packages.models.count_models import ModelSpec, RatingsCache, fit_model

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationResult:
    predictions: pd.DataFrame  # one row per (match, model_version, market_key, line)
    snapshots: pd.DataFrame  # one row per (match, model_version)
    skipped: dict[str, int]


def generate_predictions(
    facts: pd.DataFrame,
    store: FeatureStore,
    specs: Iterable[ModelSpec],
    markets: Iterable[MarketDefinition],
    *,
    competitions: Iterable[str],
    seasons: Iterable[str],
    lead_minutes: int,
    keep_features_for: set[str] | None = None,
) -> GenerationResult:
    spec_list = list(specs)
    market_list = list(markets)
    season_set = set(seasons)
    pred_rows: list[dict[str, object]] = []
    snap_rows: list[dict[str, object]] = []
    skipped: dict[str, int] = {}
    lead = timedelta(minutes=lead_minutes)

    for competition in competitions:
        targets = facts[(facts["competition_key"] == competition) & (facts["season_label"].isin(season_set))]
        if targets.empty:
            continue
        targets = targets.assign(as_of=targets["kickoff_at"] - lead)
        iso = targets["as_of"].dt.isocalendar()
        targets = targets.assign(bucket=iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2))
        cache = RatingsCache()
        for _, bucket in targets.groupby("bucket", sort=True):
            fit_as_of = bucket["as_of"].min().to_pydatetime()
            view = store.history(competition, fit_as_of)
            for spec in spec_list:
                home_col, away_col = target_columns(spec.stat, spec.period)
                rows = bucket.dropna(subset=[home_col, away_col]) if home_col in bucket else bucket.iloc[0:0]
                if rows.empty:
                    continue
                try:
                    fitted = fit_model(spec, view.frame, fit_as_of, competition, cache)
                except ModelError as exc:
                    skipped[spec.model_version] = skipped.get(spec.model_version, 0) + len(rows)
                    log.debug("skip bucket", extra={"model": spec.model_version, "reason": str(exc)})
                    continue
                spec_markets = [m for m in market_list if m.target == spec.target]
                for match in rows.itertuples(index=False):
                    if view.max_available_at is not None and view.max_available_at > match.as_of:
                        raise LeakageError(f"{match.match_id}: history max_available_at > as_of")
                    prediction = fitted.predict(match.home_team_id, match.away_team_id)
                    total = int(getattr(match, home_col) + getattr(match, away_col))
                    snapshot_id = f"fs_{match.match_id}_{spec.model_version}"
                    snap_rows.append(
                        {
                            "feature_snapshot_id": snapshot_id,
                            "match_id": match.match_id,
                            "model_version": spec.model_version,
                            "as_of": match.as_of,
                            "fit_as_of": fit_as_of,
                            "max_available_at": view.max_available_at,
                            "n_history": prediction.features.get("n_history", 0),
                            "features": prediction.features
                            if keep_features_for is None or spec.model_version in keep_features_for
                            else {"n_history": prediction.features.get("n_history", 0)},
                        }
                    )
                    for market in spec_markets:
                        for line in market.lines:
                            pred_rows.append(
                                {
                                    "match_id": match.match_id,
                                    "competition_key": competition,
                                    "season_label": match.season_label,
                                    "kickoff_at": match.kickoff_at,
                                    "as_of": match.as_of,
                                    "model_version": spec.model_version,
                                    "family": spec.family.value,
                                    "target": f"{spec.stat.value}_{spec.period.value}",
                                    "market_key": market.market_key,
                                    "line": float(line),
                                    "p_raw": prediction.distribution.prob_over(line),
                                    "actual_total": total,
                                    "y": int(total > line),
                                    "home_known": bool(prediction.features.get("home_known", True)),
                                    "away_known": bool(prediction.features.get("away_known", True)),
                                    "feature_snapshot_id": snapshot_id,
                                }
                            )
    predictions = pd.DataFrame(pred_rows)
    if not predictions.empty:
        predictions["p_raw"] = predictions["p_raw"].astype(float).clip(1e-6, 1 - 1e-6)
        assert np.all((predictions["as_of"] < predictions["kickoff_at"]).to_numpy())
    return GenerationResult(predictions, pd.DataFrame(snap_rows), skipped)
