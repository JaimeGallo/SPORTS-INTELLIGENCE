"""Comparison against the market and paper (simulated) flat-stake betting. No real money (ADR-0006).

Only odds with `available_at <= as_of` can be used to decide a paper bet. Closing odds (known only at
kickoff) are used for EVALUATION: market benchmark log loss and closing line value (CLV).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import Engine, select

from packages.calibration import metrics as mt
from packages.edge.engine import EdgeRules, edge, expected_value
from packages.markets.catalog import Outcome, Selection, settle_total
from packages.odds.engine import fair_probabilities
from packages.storage import schema as s


def load_odds(engine: Engine, match_ids: list[str], market_key: str, line: float) -> pd.DataFrame:
    o = s.odds_snapshots
    frames = []
    with engine.connect() as conn:
        for start in range(0, len(match_ids), 5000):
            chunk = match_ids[start : start + 5000]
            frames.append(
                pd.DataFrame(
                    conn.execute(
                        select(
                            o.c.match_id,
                            o.c.bookmaker_id,
                            o.c.selection,
                            o.c.decimal_odds,
                            o.c.is_closing,
                            o.c.available_at,
                        ).where(o.c.match_id.in_(chunk), o.c.market_key == market_key, o.c.line == line)
                    ).all()
                )
            )
    odds = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if odds.empty:
        return odds
    odds["decimal_odds"] = odds["decimal_odds"].astype(float)
    odds["available_at"] = pd.to_datetime(odds["available_at"], utc=True)
    wide = odds.pivot_table(
        index=["match_id", "bookmaker_id", "is_closing", "available_at"],
        columns="selection",
        values="decimal_odds",
    ).reset_index()
    return wide.dropna(subset=["over", "under"])


def pick_quotes(
    odds: pd.DataFrame, as_of: pd.DataFrame, preference: list[str], closing: bool
) -> pd.DataFrame:
    """One quote per match: first bookmaker in `preference` with a quote usable at the match's as_of
    (pre-match), or its closing quote (closing=True, evaluation only)."""
    sub = odds[odds["is_closing"] == closing].merge(as_of[["match_id", "as_of"]], on="match_id")
    if not closing:
        sub = sub[sub["available_at"] <= sub["as_of"]]
    rank = {b: i for i, b in enumerate(preference)}
    sub = sub[sub["bookmaker_id"].isin(rank)].assign(rank=lambda d: d["bookmaker_id"].map(rank))
    # best-ranked bookmaker first; within it, its latest usable quote
    sub = sub.sort_values(["match_id", "rank", "available_at"], ascending=[True, True, False])
    sub = sub.groupby("match_id").head(1)
    fair = [fair_probabilities([o, u]) for o, u in zip(sub["over"], sub["under"], strict=True)]
    sub = sub.assign(
        q_over=[f[0] for f in fair],
        raw_over=1 / sub["over"],
        overround=1 / sub["over"] + 1 / sub["under"],
    )
    return sub.drop(columns=["rank"])


@dataclass(frozen=True)
class PaperResult:
    bets: pd.DataFrame
    n_bets: int
    staked: float
    pnl: float
    roi: mt.Interval | None
    hit_rate: float | None
    mean_edge: float | None
    mean_clv: float | None
    max_drawdown: float


def paper_flat(
    preds: pd.DataFrame,
    quotes: pd.DataFrame,
    closing: pd.DataFrame | None,
    rules: EdgeRules,
    *,
    line: float,
    stake: float = 1.0,
    n_boot: int = 1000,
    seed: int = 0,
) -> PaperResult:
    """Bet 1 unit on the side with the larger positive EV when edge >= min_edge. Chronological order."""
    df = preds.merge(quotes[["match_id", "bookmaker_id", "over", "under", "q_over"]], on="match_id")
    rows = []
    for r in df.sort_values("kickoff_at").itertuples(index=False):
        options = [
            (Selection.OVER, r.p, r.q_over, r.over),
            (Selection.UNDER, 1 - r.p, 1 - r.q_over, r.under),
        ]
        best = max(options, key=lambda o: expected_value(o[1], o[3]))
        selection, p_sel, q_sel, price = best
        e, ev = edge(p_sel, q_sel), expected_value(p_sel, price)
        if e < rules.min_edge or ev <= rules.min_ev:
            continue
        outcome = settle_total(int(r.actual_total), line, selection)
        pnl = stake * (price - 1) if outcome is Outcome.HIT else (0.0 if outcome is Outcome.PUSH else -stake)
        rows.append(
            {
                "match_id": r.match_id,
                "kickoff_at": r.kickoff_at,
                "selection": selection.value,
                "bookmaker_id": r.bookmaker_id,
                "decimal_odds": price,
                "p": p_sel,
                "q": q_sel,
                "edge": e,
                "ev": ev,
                "outcome": outcome.value,
                "pnl": pnl,
                "stake": stake,
            }
        )
    bets = pd.DataFrame(rows)
    if bets.empty:
        return PaperResult(bets, 0, 0.0, 0.0, None, None, None, None, 0.0)
    if closing is not None and not closing.empty:
        c = closing[["match_id", "q_over"]].rename(columns={"q_over": "q_close_over"})
        bets = bets.merge(c, on="match_id", how="left")
        q_close = np.where(bets["selection"] == "over", bets["q_close_over"], 1 - bets["q_close_over"])
        bets["clv"] = bets["decimal_odds"] * q_close - 1  # > 0: we beat the de-margined closing price
    equity = bets["pnl"].cumsum()
    drawdown = float((equity.cummax() - equity).max())
    return PaperResult(
        bets=bets,
        n_bets=len(bets),
        staked=float(bets["stake"].sum()),
        pnl=float(bets["pnl"].sum()),
        roi=mt.bootstrap_mean(bets["pnl"].to_numpy() / stake, n_boot=n_boot, seed=seed),
        hit_rate=float((bets["outcome"] == "hit").mean()),
        mean_edge=float(bets["edge"].mean()),
        mean_clv=float(bets["clv"].mean()) if "clv" in bets and bets["clv"].notna().any() else None,
        max_drawdown=drawdown,
    )
