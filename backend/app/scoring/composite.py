"""Rule-based composite scorer.

Five pillars, each an average of sector-relative z-scores, each mapped onto a
0-100 scale, then combined with the weights in `settings.composite_weights`.

This is the interpretable baseline. It has no fitted parameters, so it cannot
overfit the backtest, and every number in it traces to a published accounting
figure or a price. The machine-learning ranker is judged against it, not the
other way round.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from app.config import settings
from app.scoring.fundamental import altman_z, piotroski

# Each pillar is the mean of these z-columns (missing columns are skipped).
PILLARS: Dict[str, List[str]] = {
    "quality": ["z_roe", "z_roa", "z_roic", "z_net_margin", "z_operating_margin",
                "z_cfo_to_net_income", "z_accrual_ratio", "z_fcf_margin"],
    "value": ["z_pe", "z_pb", "z_ev_ebitda", "z_earnings_yield", "z_fcf_yield",
              "z_dividend_yield", "z_ps"],
    "safety": ["z_debt_to_equity", "z_interest_coverage", "z_net_debt_to_ebitda",
               "z_current_ratio", "z_equity_ratio", "z_finance_cost_to_ebit"],
    "growth": ["z_revenue_growth", "z_earnings_growth", "z_revenue_cagr_3y",
               "z_equity_growth"],
    "momentum": ["z_momentum_12_1", "z_px_to_sma200", "z_rel_strength_6m",
                 "z_return_3m", "z_volatility_252d"],
}

# Human labels used in the explanation text.
PILLAR_LABELS = {
    "quality": "Profitability & earnings quality",
    "value": "Valuation",
    "safety": "Balance-sheet strength",
    "growth": "Growth",
    "momentum": "Price trend",
}


def z_to_score(z: float) -> float:
    """Map a z-score onto 0-100 so that the sector average sits at 50 and
    +/-3 sigma reaches the ends of the scale."""
    if z is None or (isinstance(float(z) if z is not None else np.nan, float) and np.isnan(z)):
        return np.nan
    return float(np.clip(50.0 + (100.0 / 6.0) * z, 0.0, 100.0))


def score_cross_section(snap: pd.DataFrame, store=None,
                        ml_scores: pd.Series | None = None) -> pd.DataFrame:
    """Score every company in one point-in-time snapshot.

    `ml_scores` is an optional 0-100 series indexed by ticker; when supplied,
    the final score blends rule and model per `settings.blend_ml_weight`.
    """
    if snap is None or snap.empty:
        return pd.DataFrame()
    df = snap.copy().set_index("ticker")

    # --- pillars ---------------------------------------------------------
    pillar_z: Dict[str, pd.Series] = {}
    for pillar, cols in PILLARS.items():
        present = [c for c in cols if c in df.columns]
        if not present:
            pillar_z[pillar] = pd.Series(0.0, index=df.index)
            continue
        block = df[present].astype(float)
        # A company must have at least a third of the pillar's inputs for the
        # pillar to be meaningful; otherwise it scores at the sector average.
        enough = block.notna().sum(axis=1) >= max(1, len(present) // 3)
        mean_z = block.mean(axis=1, skipna=True)
        pillar_z[pillar] = mean_z.where(enough, 0.0).fillna(0.0)

    # --- Piotroski and Altman -------------------------------------------
    f_scores, z_scores, z_zones, f_details, z_details = [], [], [], [], []
    for ticker, row in df.iterrows():
        prev = store.prev_row(ticker) if store is not None else None
        is_fin = bool(row.get("is_financial", False))
        f = piotroski(row, prev, is_fin)
        a = altman_z(row, float(row.get("market_cap") or 0.0), is_fin)
        f_scores.append(f["f_score"])
        f_details.append(f)
        z_scores.append(a["z_score"])
        z_zones.append(a["zone"])
        z_details.append(a)
    df["f_score"] = f_scores
    df["z_score"] = z_scores
    df["z_zone"] = z_zones
    df["_f_detail"] = f_details
    df["_z_detail"] = z_details

    # Fold the two classic scores into the pillars they belong to. F-Score is
    # a quality signal; Altman is a solvency signal.
    f_norm = (df["f_score"] - 4.5) / 2.2                       # ~z-scale
    pillar_z["quality"] = 0.72 * pillar_z["quality"] + 0.28 * f_norm.fillna(0.0)
    z_norm = ((df["z_score"] - 5.0) / 2.5).clip(-3, 3)
    pillar_z["safety"] = 0.70 * pillar_z["safety"] + 0.30 * z_norm.fillna(0.0)

    for pillar, z in pillar_z.items():
        df[pillar] = z.clip(-3, 3).map(z_to_score)
        df[f"{pillar}_z"] = z.clip(-3, 3)

    # --- composite -------------------------------------------------------
    w = settings.composite_weights
    total_w = sum(w.values())
    df["rule_score"] = sum(df[p] * (wt / total_w) for p, wt in w.items())

    # --- risk gates ------------------------------------------------------
    # Interpretable hard rules that override a flattering composite.
    flags: List[List[str]] = []
    caps: List[float] = []
    for ticker, row in df.iterrows():
        f: List[str] = []
        cap = 100.0
        if row.get("z_zone") == "distress":
            f.append("Altman Z in the distress zone")
            cap = min(cap, 45.0)
        if pd.notna(row.get("f_score")) and row["f_score"] <= 3:
            f.append("Piotroski F-Score of 3 or less")
            cap = min(cap, 50.0)
        if float(row.get("total_equity") or 0) <= 0:
            f.append("negative shareholders' equity")
            cap = min(cap, 25.0)
        if float(row.get("net_income_ttm") or 0) < 0:
            f.append("loss-making over the trailing twelve months")
            cap = min(cap, 55.0)
        ic = row.get("interest_coverage")
        if pd.notna(ic) and float(ic) < 1.5 and not row.get("is_financial"):
            f.append("operating profit barely covers finance cost")
            cap = min(cap, 50.0)
        liq = row.get("turnover_pkr_m")
        if pd.notna(liq) and float(liq) < 5.0:
            f.append("thin traded volume, hard to exit")
            cap = min(cap, 60.0)
        if pd.notna(row.get("accrual_ratio")) and float(row["accrual_ratio"]) > 0.10:
            f.append("profit running well ahead of cash generation")
        flags.append(f)
        caps.append(cap)
    df["risk_flags"] = flags
    df["score_cap"] = caps
    df["rule_score"] = np.minimum(df["rule_score"], df["score_cap"])

    # --- blend with the ML ranker ---------------------------------------
    if ml_scores is not None and len(ml_scores):
        ml = ml_scores.reindex(df.index)
        have_ml = ml.notna()
        df["ml_score"] = ml
        blend = settings.blend_ml_weight
        df["final_score"] = np.where(
            have_ml,
            (1 - blend) * df["rule_score"] + blend * ml.fillna(df["rule_score"]),
            df["rule_score"])
        df["final_score"] = np.minimum(df["final_score"], df["score_cap"])
    else:
        df["ml_score"] = np.nan
        df["final_score"] = df["rule_score"]

    # --- ranking and bands ----------------------------------------------
    df = df.sort_values("final_score", ascending=False)
    df["rank"] = np.arange(1, len(df) + 1)
    df["percentile"] = df["final_score"].rank(pct=True)
    df["recommendation"] = df["percentile"].map(settings.band_for)

    # Conviction reflects both standing and evidence quality.
    completeness = df[[c for c in df.columns if c.startswith("z_")]].notna().mean(axis=1)
    spread = (df["final_score"] - df["final_score"].mean()) / (df["final_score"].std() or 1)
    df["conviction"] = (0.55 * df["percentile"]
                        + 0.25 * completeness.fillna(0.5)
                        + 0.20 * (spread.clip(-2, 2) + 2) / 4).clip(0, 1).round(3)
    return df.reset_index()
