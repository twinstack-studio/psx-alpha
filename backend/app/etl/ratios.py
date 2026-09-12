"""Ratio engine.

Turns the standardized quarterly panel into the ratio set the scorer consumes.

Two rules matter here:

* **Trailing twelve months.** Flow items (revenue, profit, cash flow) are summed
  over the last four quarters so a seasonal quarter never distorts a ratio.
  Stock items (assets, equity) use the average of the current and year-ago
  balance, which is what makes ROA/ROE comparable across a growing balance
  sheet.
* **Sector-relative.** A 12% net margin is excellent for an oil marketing
  company and poor for a pharmaceutical. Every ratio is therefore also stored
  as a winsorized z-score against sector peers *in the same period*, which is
  what the composite score actually ranks on.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from app.ingest.universe import BY_TICKER, FINANCIAL_SECTORS

FLOW_COLS = [
    "revenue", "cost_of_sales", "gross_profit", "operating_expenses",
    "operating_income", "depreciation", "finance_cost", "other_income",
    "profit_before_tax", "taxation", "net_income", "eps", "dividend_per_share",
    "cfo", "capex", "cfi", "cff", "free_cash_flow",
]
STOCK_COLS = [
    "cash", "receivables", "inventory", "current_assets", "fixed_assets",
    "total_assets", "payables", "short_term_debt", "current_liabilities",
    "long_term_debt", "total_liabilities", "total_equity", "retained_earnings",
    "shares_outstanding",
]

# Ratios where a lower value is better; their z-scores get flipped so that a
# positive z always means "better than peers".
LOWER_IS_BETTER = {
    "debt_to_equity", "debt_to_assets", "net_debt_to_ebitda", "receivable_days",
    "inventory_days", "cash_conversion_cycle", "capex_to_revenue",
    "accrual_ratio", "finance_cost_to_ebit",
}


def _safe(num, den, cap: float = 1e6):
    """Element-wise division that returns NaN instead of exploding on a zero
    or negative denominator."""
    num = pd.Series(num).astype(float)
    den = pd.Series(den).astype(float).replace(0.0, np.nan)
    out = num / den
    return out.replace([np.inf, -np.inf], np.nan).clip(-cap, cap)


def build_ttm(statements: pd.DataFrame) -> pd.DataFrame:
    """Add TTM flow columns and year-ago stock balances per ticker."""
    df = statements.sort_values(["ticker", "period_end"]).copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["report_date"] = pd.to_datetime(df["report_date"])
    g = df.groupby("ticker", group_keys=False)

    for col in FLOW_COLS:
        df[f"{col}_ttm"] = g[col].transform(lambda s: s.rolling(4, min_periods=4).sum())
        df[f"{col}_ttm_prev"] = g[f"{col}_ttm"].shift(4)
    for col in STOCK_COLS:
        df[f"{col}_prev"] = g[col].shift(4)
        df[f"{col}_avg"] = (df[col] + df[f"{col}_prev"]) / 2.0
    # three-year-ago TTM revenue for the CAGR
    df["revenue_ttm_3y"] = g["revenue_ttm"].shift(12)
    df["net_income_ttm_3y"] = g["net_income_ttm"].shift(12)
    return df


def compute_ratios(statements: pd.DataFrame) -> pd.DataFrame:
    """Return one row per (ticker, period_end) with the full ratio set."""
    df = build_ttm(statements)
    r = pd.DataFrame({
        "ticker": df["ticker"].values,
        "period_end": df["period_end"].values,
        "report_date": df["report_date"].values,
    })
    sector = df["ticker"].map(lambda t: BY_TICKER[t].sector if t in BY_TICKER else "Miscellaneous")
    r["sector"] = sector.values
    is_fin = sector.isin(FINANCIAL_SECTORS).values

    ebit = df["operating_income_ttm"]
    ebitda = ebit + df["depreciation_ttm"]
    total_debt = df["short_term_debt"] + df["long_term_debt"]
    net_debt = total_debt - df["cash"]
    invested_capital = df["total_equity_avg"] + (df["short_term_debt"] + df["long_term_debt"])

    # --- profitability ---------------------------------------------------
    r["gross_margin"] = _safe(df["gross_profit_ttm"], df["revenue_ttm"]).values
    r["operating_margin"] = _safe(ebit, df["revenue_ttm"]).values
    r["net_margin"] = _safe(df["net_income_ttm"], df["revenue_ttm"]).values
    r["ebitda_margin"] = _safe(ebitda, df["revenue_ttm"]).values
    r["roa"] = _safe(df["net_income_ttm"], df["total_assets_avg"]).values
    r["roe"] = _safe(df["net_income_ttm"], df["total_equity_avg"]).values
    r["roic"] = _safe(ebit * 0.71, invested_capital).values
    r["effective_tax_rate"] = _safe(df["taxation_ttm"], df["profit_before_tax_ttm"]).values

    # --- liquidity -------------------------------------------------------
    r["current_ratio"] = _safe(df["current_assets"], df["current_liabilities"]).values
    r["quick_ratio"] = _safe(df["current_assets"] - df["inventory"], df["current_liabilities"]).values
    r["cash_ratio"] = _safe(df["cash"], df["current_liabilities"]).values

    # --- leverage & solvency ---------------------------------------------
    r["debt_to_equity"] = _safe(total_debt, df["total_equity"]).values
    r["debt_to_assets"] = _safe(total_debt, df["total_assets"]).values
    r["equity_ratio"] = _safe(df["total_equity"], df["total_assets"]).values
    r["interest_coverage"] = _safe(ebit, df["finance_cost_ttm"]).clip(-50, 50).values
    r["net_debt_to_ebitda"] = _safe(net_debt, ebitda).clip(-20, 20).values
    r["finance_cost_to_ebit"] = _safe(df["finance_cost_ttm"], ebit).clip(-10, 10).values

    # --- efficiency ------------------------------------------------------
    r["asset_turnover"] = _safe(df["revenue_ttm"], df["total_assets_avg"]).values
    r["inventory_days"] = (_safe(df["inventory_avg"], df["cost_of_sales_ttm"]) * 365).values
    r["receivable_days"] = (_safe(df["receivables_avg"], df["revenue_ttm"]) * 365).values
    r["payable_days"] = (_safe(df["payables_avg"], df["cost_of_sales_ttm"]) * 365).values
    r["cash_conversion_cycle"] = (r["inventory_days"] + r["receivable_days"] - r["payable_days"]).values

    # --- cash quality ----------------------------------------------------
    r["cfo_to_net_income"] = _safe(df["cfo_ttm"], df["net_income_ttm"]).clip(-20, 20).values
    r["accrual_ratio"] = _safe(df["net_income_ttm"] - df["cfo_ttm"], df["total_assets_avg"]).values
    r["fcf_margin"] = _safe(df["free_cash_flow_ttm"], df["revenue_ttm"]).values
    r["capex_to_revenue"] = _safe(df["capex_ttm"], df["revenue_ttm"]).values

    # --- growth ----------------------------------------------------------
    r["revenue_growth"] = _safe(df["revenue_ttm"] - df["revenue_ttm_prev"], df["revenue_ttm_prev"].abs()).values
    r["earnings_growth"] = _safe(df["net_income_ttm"] - df["net_income_ttm_prev"], df["net_income_ttm_prev"].abs()).clip(-5, 5).values
    r["revenue_cagr_3y"] = (
        (_safe(df["revenue_ttm"], df["revenue_ttm_3y"]).clip(0.01, 50) ** (1 / 3)) - 1).values
    r["equity_growth"] = _safe(df["total_equity"] - df["total_equity_prev"], df["total_equity_prev"].abs()).values

    # --- per share -------------------------------------------------------
    sh = df["shares_outstanding"].replace(0, np.nan)
    r["eps_ttm"] = _safe(df["net_income_ttm"], sh).values
    r["bvps"] = _safe(df["total_equity"], sh).values
    r["dps_ttm"] = df["dividend_per_share_ttm"].values
    r["cfps"] = _safe(df["cfo_ttm"], sh).values
    r["sps"] = _safe(df["revenue_ttm"], sh).values
    r["payout_ratio"] = _safe(df["dividend_per_share_ttm"], r["eps_ttm"]).clip(-2, 3).values

    # --- absolutes the scorer needs --------------------------------------
    r["net_income_ttm"] = df["net_income_ttm"].values
    r["revenue_ttm"] = df["revenue_ttm"].values
    r["ebitda_ttm"] = ebitda.values
    r["ebit_ttm"] = ebit.values
    r["total_debt"] = total_debt.values
    r["net_debt"] = net_debt.values
    r["total_assets"] = df["total_assets"].values
    r["total_equity"] = df["total_equity"].values
    r["working_capital"] = (df["current_assets"] - df["current_liabilities"]).values
    r["retained_earnings"] = df["retained_earnings"].values
    r["shares_outstanding"] = df["shares_outstanding"].values
    r["cfo_ttm"] = df["cfo_ttm"].values
    r["is_financial"] = is_fin

    # Banks have no meaningful inventory or gross-margin concept.
    for col in ["gross_margin", "inventory_days", "cash_conversion_cycle",
                "current_ratio", "quick_ratio", "asset_turnover"]:
        r.loc[r["is_financial"], col] = np.nan

    return r


# --------------------------------------------------------------------------
RATIO_COLS: List[str] = [
    "gross_margin", "operating_margin", "net_margin", "ebitda_margin", "roa",
    "roe", "roic", "current_ratio", "quick_ratio", "cash_ratio",
    "debt_to_equity", "debt_to_assets", "equity_ratio", "interest_coverage",
    "net_debt_to_ebitda", "finance_cost_to_ebit", "asset_turnover",
    "inventory_days", "receivable_days", "cash_conversion_cycle",
    "cfo_to_net_income", "accrual_ratio", "fcf_margin", "capex_to_revenue",
    "revenue_growth", "earnings_growth", "revenue_cagr_3y", "equity_growth",
    "payout_ratio",
]

MIN_PEERS = 4


def _winsorized_z(s: pd.Series) -> pd.Series:
    v = s.astype(float)
    if v.notna().sum() < 2:
        return pd.Series(np.nan, index=s.index)
    lo, hi = v.quantile(0.05), v.quantile(0.95)
    v = v.clip(lo, hi)
    sd = v.std(ddof=0)
    if not sd or not np.isfinite(sd):
        return pd.Series(0.0, index=s.index)
    return (v - v.mean()) / sd


def add_sector_z(ratios: pd.DataFrame) -> pd.DataFrame:
    """Attach a `z_<ratio>` column for every ratio, computed against sector
    peers in the same period. Sectors with fewer than MIN_PEERS names that
    period fall back to a market-wide comparison."""
    df = ratios.copy()
    for col in RATIO_COLS:
        zname = f"z_{col}"
        df[zname] = np.nan
        for period, grp in df.groupby("period_end"):
            market_z = _winsorized_z(grp[col])
            for sec, sgrp in grp.groupby("sector"):
                if sgrp[col].notna().sum() >= MIN_PEERS:
                    z = _winsorized_z(sgrp[col])
                else:
                    z = market_z.reindex(sgrp.index)
                df.loc[sgrp.index, zname] = z.values
        if col in LOWER_IS_BETTER:
            df[zname] = -df[zname]
        df[zname] = df[zname].clip(-3.0, 3.0)
    return df


def run(statements: pd.DataFrame) -> pd.DataFrame:
    """Full ratio ETL: TTM -> ratios -> sector-relative z-scores."""
    return add_sector_z(compute_ratios(statements))
