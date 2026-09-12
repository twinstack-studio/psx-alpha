"""Interpretable fundamental scores: Piotroski F-Score and Altman Z-Score.

These are the transparent baseline the proposal calls for. Every one of the
nine Piotroski tests is stored as a named pass/fail, so a recommendation can
always be traced back to the exact accounting facts that produced it.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from app.ingest.universe import BY_TICKER, FINANCIAL_SECTORS

# --------------------------------------------------------------------------
# Piotroski F-Score
# --------------------------------------------------------------------------
PIOTROSKI_TESTS: List[tuple] = [
    ("roa_positive",      "Profitable on assets",        "ROA over the trailing year is positive"),
    ("cfo_positive",      "Cash generative",             "Operating cash flow is positive"),
    ("roa_improving",     "Returns improving",           "ROA is higher than a year ago"),
    ("accruals_clean",    "Earnings backed by cash",     "Operating cash flow exceeds reported profit"),
    ("leverage_falling",  "Deleveraging",                "Long-term debt to assets fell year on year"),
    ("liquidity_rising",  "Liquidity improving",         "Current ratio is higher than a year ago"),
    ("no_dilution",       "No shareholder dilution",     "Share count did not increase"),
    ("margin_expanding",  "Margin expanding",            "Gross margin is wider than a year ago"),
    ("turnover_rising",   "Assets working harder",       "Asset turnover improved year on year"),
]

# Banks have no gross margin, inventory or current ratio. The three tests that
# depend on them are replaced by equivalents that do apply to a balance-sheet
# lender.
BANK_SUBSTITUTIONS = {
    "liquidity_rising": ("Capital strengthening", "Equity-to-assets ratio improved year on year"),
    "margin_expanding": ("Spread widening", "Net margin is wider than a year ago"),
    "turnover_rising":  ("Balance sheet productivity", "Revenue per rupee of assets improved"),
}


def piotroski(curr: pd.Series, prev: pd.Series | None, is_financial: bool) -> dict:
    """Score one company for one period. `prev` is the same company four
    quarters earlier; without it the change-based tests cannot be evaluated
    and are recorded as not-assessable rather than silently passed."""
    def val(s, k, default=np.nan):
        if s is None:
            return np.nan
        v = s.get(k, default)
        return float(v) if v is not None and pd.notna(v) else np.nan

    tests: Dict[str, dict] = {}

    def record(key: str, passed, detail: str):
        label, desc = next((l, d) for k, l, d in PIOTROSKI_TESTS if k == key)
        if is_financial and key in BANK_SUBSTITUTIONS:
            label, desc = BANK_SUBSTITUTIONS[key]
        tests[key] = {
            "label": label,
            "description": desc,
            "passed": None if passed is None else bool(passed),
            "detail": detail,
        }

    roa, roa_p = val(curr, "roa"), val(prev, "roa")
    cfo = val(curr, "cfo_ttm")
    ni = val(curr, "net_income_ttm")
    record("roa_positive", None if np.isnan(roa) else roa > 0, f"ROA {roa:.1%}" if not np.isnan(roa) else "ROA unavailable")
    record("cfo_positive", None if np.isnan(cfo) else cfo > 0, f"CFO PKR {cfo:,.0f}m" if not np.isnan(cfo) else "CFO unavailable")
    record("roa_improving", None if (np.isnan(roa) or np.isnan(roa_p)) else roa > roa_p,
           f"ROA {roa:.1%} vs {roa_p:.1%} a year ago" if not (np.isnan(roa) or np.isnan(roa_p)) else "no year-ago comparison")
    record("accruals_clean", None if (np.isnan(cfo) or np.isnan(ni)) else cfo > ni,
           f"CFO PKR {cfo:,.0f}m vs profit PKR {ni:,.0f}m" if not (np.isnan(cfo) or np.isnan(ni)) else "not assessable")

    lev, lev_p = val(curr, "debt_to_assets"), val(prev, "debt_to_assets")
    record("leverage_falling", None if (np.isnan(lev) or np.isnan(lev_p)) else lev <= lev_p,
           f"debt/assets {lev:.2f} vs {lev_p:.2f}" if not (np.isnan(lev) or np.isnan(lev_p)) else "not assessable")

    if is_financial:
        eq, eq_p = val(curr, "equity_ratio"), val(prev, "equity_ratio")
        record("liquidity_rising", None if (np.isnan(eq) or np.isnan(eq_p)) else eq > eq_p,
               f"equity/assets {eq:.1%} vs {eq_p:.1%}" if not (np.isnan(eq) or np.isnan(eq_p)) else "not assessable")
        nm, nm_p = val(curr, "net_margin"), val(prev, "net_margin")
        record("margin_expanding", None if (np.isnan(nm) or np.isnan(nm_p)) else nm > nm_p,
               f"net margin {nm:.1%} vs {nm_p:.1%}" if not (np.isnan(nm) or np.isnan(nm_p)) else "not assessable")
        rev, assets = val(curr, "revenue_ttm"), val(curr, "total_assets")
        rev_p, assets_p = val(prev, "revenue_ttm"), val(prev, "total_assets")
        t_now = rev / assets if assets else np.nan
        t_prev = rev_p / assets_p if assets_p else np.nan
        record("turnover_rising", None if (np.isnan(t_now) or np.isnan(t_prev)) else t_now > t_prev,
               f"revenue/assets {t_now:.3f} vs {t_prev:.3f}" if not (np.isnan(t_now) or np.isnan(t_prev)) else "not assessable")
    else:
        cr, cr_p = val(curr, "current_ratio"), val(prev, "current_ratio")
        record("liquidity_rising", None if (np.isnan(cr) or np.isnan(cr_p)) else cr > cr_p,
               f"current ratio {cr:.2f} vs {cr_p:.2f}" if not (np.isnan(cr) or np.isnan(cr_p)) else "not assessable")
        gm, gm_p = val(curr, "gross_margin"), val(prev, "gross_margin")
        record("margin_expanding", None if (np.isnan(gm) or np.isnan(gm_p)) else gm > gm_p,
               f"gross margin {gm:.1%} vs {gm_p:.1%}" if not (np.isnan(gm) or np.isnan(gm_p)) else "not assessable")
        at, at_p = val(curr, "asset_turnover"), val(prev, "asset_turnover")
        record("turnover_rising", None if (np.isnan(at) or np.isnan(at_p)) else at > at_p,
               f"asset turnover {at:.2f}x vs {at_p:.2f}x" if not (np.isnan(at) or np.isnan(at_p)) else "not assessable")

    sh, sh_p = val(curr, "shares_outstanding"), val(prev, "shares_outstanding")
    record("no_dilution", None if (np.isnan(sh) or np.isnan(sh_p)) else sh <= sh_p * 1.001,
           f"{sh:,.0f}m shares vs {sh_p:,.0f}m" if not (np.isnan(sh) or np.isnan(sh_p)) else "not assessable")

    assessed = [t for t in tests.values() if t["passed"] is not None]
    passed = sum(1 for t in assessed if t["passed"])
    # Scale to the familiar 0-9 range when some tests could not be assessed.
    score = 9.0 * passed / len(assessed) if assessed else np.nan
    return {
        "f_score": score,
        "f_passed": passed,
        "f_assessed": len(assessed),
        "tests": tests,
    }


def f_score_verdict(f: float) -> str:
    if np.isnan(f):
        return "insufficient history"
    if f >= 8:
        return "very strong"
    if f >= 6:
        return "strong"
    if f >= 4:
        return "mixed"
    return "weak"


# --------------------------------------------------------------------------
# Altman Z-Score
# --------------------------------------------------------------------------
def altman_z(row: pd.Series, market_cap: float | None, is_financial: bool) -> dict:
    """Altman Z''-Score for emerging markets.

    The original 1968 Z-Score was fitted on US manufacturers. Altman's later
    Z''-EM variant drops the sales/assets term (which penalises asset-heavy
    emerging-market firms), uses book rather than market equity in X4 and adds
    a constant of 3.25 so the scale is comparable across markets. That is the
    variant used here; the manufacturing Z is reported alongside it when a
    market cap is available.

    Banks and insurers are excluded: their balance sheets make working capital
    and asset turnover meaningless, and Altman explicitly excluded financials
    from the fitting sample.
    """
    if is_financial:
        return {"z_score": np.nan, "z_variant": "not applicable to financials",
                "zone": "n/a", "components": {}}

    ta = float(row.get("total_assets") or np.nan)
    if not ta or np.isnan(ta) or ta <= 0:
        return {"z_score": np.nan, "z_variant": "unavailable", "zone": "n/a", "components": {}}

    tl = float(row.get("total_assets") or 0) - float(row.get("total_equity") or 0)
    tl = max(tl, 1.0)
    x1 = float(row.get("working_capital") or 0) / ta
    x2 = float(row.get("retained_earnings") or 0) / ta
    x3 = float(row.get("ebit_ttm") or 0) / ta
    x4 = float(row.get("total_equity") or 0) / tl
    x5 = float(row.get("revenue_ttm") or 0) / ta

    z_em = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4 + 3.25
    out = {
        "z_score": float(z_em),
        "z_variant": "Altman Z''-EM",
        "zone": "safe" if z_em > 5.85 else ("grey" if z_em >= 4.15 else "distress"),
        "components": {
            "working_capital_to_assets": x1,
            "retained_earnings_to_assets": x2,
            "ebit_to_assets": x3,
            "equity_to_liabilities": x4,
            "sales_to_assets": x5,
        },
    }
    if market_cap and market_cap > 0:
        z_mfg = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * (market_cap / tl) + 1.0 * x5
        out["z_score_manufacturing"] = float(z_mfg)
    return out


def z_verdict(z: float) -> str:
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return "not applicable"
    if z > 5.85:
        return "financially sound"
    if z >= 4.15:
        return "watch zone"
    return "distress risk"


def is_financial_ticker(ticker: str) -> bool:
    c = BY_TICKER.get(ticker)
    return bool(c and c.sector in FINANCIAL_SECTORS)
