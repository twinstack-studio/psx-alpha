"""Walk-forward portfolio backtest against the KSE-100.

Rules the engine enforces, because each one is a way a stock screen can look
better on paper than it would have been in practice:

* **No look-ahead.** Positions for a quarter are chosen from a snapshot dated
  the rebalance day, built only from filings already public and prices already
  printed.
* **Costs are charged.** Every rebalance pays commission plus slippage on the
  traded fraction of the book, at PSX-realistic rates.
* **Liquidity is respected.** A name whose median daily traded value is too
  small to build a position in is not investable, however well it scores.
* **Concentration is capped.** No sector may exceed `max_sector_weight`, so a
  single sector bet cannot masquerade as stock selection.
* **Weights drift.** Between rebalances the book is held, not silently
  re-equalised, so the reported return is what an investor would have earned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.scoring.composite import score_cross_section
from app.scoring.features import FeatureStore

TRADING_DAYS = 252


@dataclass
class Holding:
    ticker: str
    name: str
    sector: str
    weight: float
    score: float
    rank: int
    recommendation: str
    price: float


@dataclass
class RebalanceRecord:
    date: str
    holdings: List[dict]
    turnover: float
    cost_bps: float
    n_candidates: int
    n_excluded_liquidity: int
    period_return: Optional[float] = None
    benchmark_return: Optional[float] = None


def rebalance_dates(store: FeatureStore, start: date, end: date, freq: str = "Q") -> List[pd.Timestamp]:
    """First trading day on or after each period boundary."""
    bounds = pd.date_range(pd.Timestamp(start), pd.Timestamp(end),
                           freq={"Q": "QS", "M": "MS", "Y": "YS"}.get(freq, "QS"))
    days = store.trading_days
    out: List[pd.Timestamp] = []
    for b in bounds:
        later = days[days >= b]
        if len(later):
            d = later[0]
            if not out or d != out[-1]:
                out.append(d)
    return out


def select_portfolio(scored: pd.DataFrame, score_col: str, top_n: int,
                     min_turnover_pkr_m: float = 5.0,
                     max_sector_weight: float = 0.30,
                     exclude_bands=("AVOID",)) -> tuple[List[Holding], int, int]:
    """Equal-weight the best `top_n` investable names, subject to a sector cap."""
    df = scored.copy()
    n_all = len(df)
    liq = df["turnover_pkr_m"].fillna(0.0)
    investable = df[liq >= min_turnover_pkr_m]
    n_excluded = n_all - len(investable)
    if exclude_bands:
        investable = investable[~investable["recommendation"].isin(exclude_bands)]
    if investable.empty:
        return [], n_all, n_excluded

    investable = investable.sort_values(score_col, ascending=False)
    max_per_sector = max(1, int(np.floor(max_sector_weight * top_n)))
    picked: List[pd.Series] = []
    sector_count: Dict[str, int] = {}
    for _, row in investable.iterrows():
        if len(picked) >= top_n:
            break
        sec = row.get("sector", "Miscellaneous")
        if sector_count.get(sec, 0) >= max_per_sector:
            continue
        picked.append(row)
        sector_count[sec] = sector_count.get(sec, 0) + 1
    # If the sector cap left the book short, top it up with the next best names.
    if len(picked) < top_n:
        chosen = {p["ticker"] for p in picked}
        for _, row in investable.iterrows():
            if len(picked) >= top_n:
                break
            if row["ticker"] not in chosen:
                picked.append(row)
                chosen.add(row["ticker"])

    w = 1.0 / len(picked)
    return ([Holding(ticker=r["ticker"], name=r.get("name", r["ticker"]),
                     sector=r.get("sector", ""), weight=w,
                     score=float(r[score_col]), rank=int(r["rank"]),
                     recommendation=r["recommendation"],
                     price=float(r["price"]))
             for r in picked], n_all, n_excluded)


class Portfolio:
    """Tracks one strategy's book through the backtest."""

    def __init__(self, name: str, score_col: str):
        self.name = name
        self.score_col = score_col
        self.weights: Dict[str, float] = {}
        self.equity: List[tuple] = []      # (date, value)
        self.records: List[RebalanceRecord] = []
        self.value = 100.0

    def turnover_against(self, new_w: Dict[str, float]) -> float:
        keys = set(self.weights) | set(new_w)
        return 0.5 * sum(abs(new_w.get(k, 0.0) - self.weights.get(k, 0.0)) for k in keys)


def _drift(weights: Dict[str, float], close: pd.DataFrame,
           start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Series, Dict[str, float]]:
    """Daily portfolio value path over a holding period, and the weights the
    book has drifted to by the end of it."""
    window = close.loc[start:end]
    if window.empty or not weights:
        return pd.Series(dtype=float), weights
    tickers = [t for t in weights if t in window.columns]
    if not tickers:
        return pd.Series(dtype=float), weights
    px = window[tickers].ffill()
    base = px.iloc[0]
    rel = px.divide(base, axis=1).fillna(1.0)
    w = np.array([weights[t] for t in tickers])
    values = rel.values @ w
    path = pd.Series(values, index=px.index)
    final_rel = rel.iloc[-1].values * w
    total = final_rel.sum() or 1.0
    drifted = {t: float(v / total) for t, v in zip(tickers, final_rel)}
    return path, drifted


def run_backtest(store: FeatureStore, ranker, start: date, end: date,
                 strategies: Dict[str, str] | None = None,
                 top_n: int | None = None,
                 progress=None) -> dict:
    """Execute the walk-forward loop and return equity curves plus metrics.

    `strategies` maps a display name to the score column used for selection,
    e.g. {"rule": "rule_score", "ml": "ml_score", "blended": "final_score"}.
    """
    strategies = strategies or {
        "rule": "rule_score", "ml": "ml_score", "blended": "final_score"}
    top_n = top_n or settings.top_n
    dates = rebalance_dates(store, start, end, settings.rebalance_freq)
    if len(dates) < 2:
        raise ValueError("need at least two rebalance dates")

    books = {k: Portfolio(k, col) for k, col in strategies.items()}
    close = store.close
    bench = store.bench.reindex(close.index).ffill()
    cost_rate = (settings.transaction_cost_bps + settings.slippage_bps) / 10_000.0

    snapshots: Dict[str, pd.DataFrame] = {}
    all_scored: Dict[str, pd.DataFrame] = {}

    for i, d in enumerate(dates):
        if progress:
            progress(i, len(dates), d)
        snap = store.snapshot(d)
        if snap.empty:
            continue
        snap["universe_size"] = len(snap)

        # 1. model score for this date, trained only on closed horizons
        ml_scores = ranker.fit_predict(snap, d)
        # 2. rule score, and the blend
        scored = score_cross_section(snap, store, ml_scores if len(ml_scores) else None)
        scored["universe_size"] = len(scored)
        if "ml_score" not in scored.columns or scored["ml_score"].isna().all():
            scored["ml_score"] = scored["rule_score"]
        snapshots[str(d.date())] = snap
        all_scored[str(d.date())] = scored

        # 3. record the observation so a later fold can learn from it
        fwd = store.forward_return(d, settings.ml_label_horizon_days)
        ranker.add_observation(snap, d, fwd)
        if len(ml_scores):
            ranker.attach_scores(d, ml_scores)

        # 4. trade each book
        nxt = dates[i + 1] if i + 1 < len(dates) else close.index[-1]
        for key, book in books.items():
            holdings, n_all, n_excl = select_portfolio(
                scored, book.score_col, top_n,
                max_sector_weight=settings.max_sector_weight)
            if not holdings:
                continue
            new_w = {h.ticker: h.weight for h in holdings}
            turnover = book.turnover_against(new_w)
            book.value *= (1.0 - turnover * 2.0 * cost_rate)
            path, drifted = _drift(new_w, close, d, nxt)
            if not path.empty:
                curve = path * book.value
                book.equity.extend(zip(curve.index, curve.values))
                period_ret = float(path.iloc[-1] - 1.0)
                book.value = float(curve.iloc[-1])
                book.weights = drifted
            else:
                period_ret = None
            b0, b1 = bench.loc[d], bench.loc[:nxt].iloc[-1]
            book.records.append(RebalanceRecord(
                date=str(d.date()),
                holdings=[h.__dict__ for h in holdings],
                turnover=round(turnover, 4),
                cost_bps=round(turnover * 2.0 * cost_rate * 10_000, 2),
                n_candidates=n_all, n_excluded_liquidity=n_excl,
                period_return=period_ret,
                benchmark_return=float(b1 / b0 - 1.0),
            ))

    # --- assemble curves -------------------------------------------------
    first, last = dates[0], close.index[-1]
    bench_curve = (bench.loc[first:last] / bench.loc[first]) * 100.0
    out_curves: Dict[str, pd.Series] = {"KSE100": bench_curve}
    for key, book in books.items():
        if not book.equity:
            continue
        s = pd.Series(dict(book.equity)).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        out_curves[key] = s.reindex(bench_curve.index).ffill().bfill()

    metrics = {k: compute_metrics(v, bench_curve) for k, v in out_curves.items()}
    for k, book in books.items():
        if k in metrics:
            trn = [r.turnover for r in book.records]
            metrics[k]["avg_turnover"] = round(float(np.mean(trn)), 4) if trn else 0.0
            metrics[k]["total_cost_drag_pct"] = round(
                float(sum(r.cost_bps for r in book.records)) / 100.0, 3)
            metrics[k]["n_rebalances"] = len(book.records)
            wins = [1 for r in book.records
                    if r.period_return is not None and r.benchmark_return is not None
                    and r.period_return > r.benchmark_return]
            evaluated = [r for r in book.records if r.period_return is not None]
            metrics[k]["quarters_beating_benchmark"] = len(wins)
            metrics[k]["quarters_evaluated"] = len(evaluated)
            metrics[k]["hit_rate"] = round(len(wins) / len(evaluated), 3) if evaluated else 0.0

    return {
        "curves": out_curves,
        "metrics": metrics,
        "books": books,
        "scored": all_scored,
        "rebalance_dates": [str(d.date()) for d in dates],
    }


# --------------------------------------------------------------------------
def compute_metrics(curve: pd.Series, bench: pd.Series | None = None) -> dict:
    """Standard performance statistics for one equity curve."""
    c = curve.dropna()
    if len(c) < 20:
        return {}
    rets = c.pct_change().dropna()
    years = max((c.index[-1] - c.index[0]).days / 365.25, 1e-9)
    total = float(c.iloc[-1] / c.iloc[0] - 1.0)
    cagr = float((c.iloc[-1] / c.iloc[0]) ** (1 / years) - 1.0)
    vol = float(rets.std() * np.sqrt(TRADING_DAYS))
    rf = settings.risk_free_rate
    sharpe = (cagr - rf) / vol if vol else 0.0
    downside = rets[rets < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = (cagr - rf) / downside if downside else 0.0
    running_max = c.cummax()
    dd = c / running_max - 1.0
    max_dd = float(dd.min())
    calmar = cagr / abs(max_dd) if max_dd else 0.0

    out = {
        "total_return": round(total, 4),
        "cagr": round(cagr, 4),
        "volatility": round(vol, 4),
        "sharpe": round(float(sharpe), 3),
        "sortino": round(float(sortino), 3),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(float(calmar), 3),
        "best_day": round(float(rets.max()), 4),
        "worst_day": round(float(rets.min()), 4),
        "positive_days": round(float((rets > 0).mean()), 4),
        "years": round(years, 2),
        "final_value": round(float(c.iloc[-1]), 2),
    }

    if bench is not None:
        b = bench.reindex(c.index).ffill()
        br = b.pct_change().dropna()
        joined = pd.concat([rets, br], axis=1, join="inner").dropna()
        if len(joined) > 30:
            ra, rb = joined.iloc[:, 0], joined.iloc[:, 1]
            var = rb.var()
            beta = float(ra.cov(rb) / var) if var else 0.0
            b_cagr = float((b.iloc[-1] / b.iloc[0]) ** (1 / years) - 1.0)
            alpha = cagr - (rf + beta * (b_cagr - rf))
            active = ra - rb
            te = float(active.std() * np.sqrt(TRADING_DAYS))
            out.update({
                "beta": round(beta, 3),
                "alpha_annual": round(float(alpha), 4),
                "excess_return": round(cagr - b_cagr, 4),
                "tracking_error": round(te, 4),
                "information_ratio": round(float((cagr - b_cagr) / te), 3) if te else 0.0,
                "benchmark_cagr": round(b_cagr, 4),
                "benchmark_total_return": round(float(b.iloc[-1] / b.iloc[0] - 1.0), 4),
            })
    return out


def yearly_returns(curve: pd.Series) -> List[dict]:
    c = curve.dropna()
    if c.empty:
        return []
    yearly = c.resample("YE").last()
    first = c.iloc[0]
    prev = first
    out = []
    for ts, v in yearly.items():
        out.append({"year": int(ts.year), "return": round(float(v / prev - 1.0), 4)})
        prev = v
    return out
