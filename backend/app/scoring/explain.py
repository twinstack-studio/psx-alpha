"""Plain-language explanation for every recommendation.

The proposal's core promise is that no recommendation arrives as a bare number.
This module turns the scored row into text a retail investor can act on: what
the company does well, what it does badly, how it is priced, what the classic
screens say, and what would change the verdict.

Every sentence is generated from a specific figure in the row, so the
explanation and the score can never disagree.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from app.scoring.composite import PILLAR_LABELS, PILLARS
from app.scoring.fundamental import f_score_verdict, z_verdict


def _pct(v, digits=1):
    return "n/a" if v is None or pd.isna(v) else f"{float(v) * 100:.{digits}f}%"


def _num(v, digits=2, suffix=""):
    return "n/a" if v is None or pd.isna(v) else f"{float(v):,.{digits}f}{suffix}"


def _pkr_m(v):
    if v is None or pd.isna(v):
        return "n/a"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"PKR {v / 1_000_000:.2f}tn"
    if abs(v) >= 1_000:
        return f"PKR {v / 1_000:.1f}bn"
    return f"PKR {v:.0f}m"


# metric -> (display label, formatter, strength phrasing, weakness phrasing)
METRIC_PHRASES: Dict[str, tuple] = {
    "roe": ("Return on equity", _pct,
            "earns {v} on shareholders' money, well ahead of its {sector} peers",
            "earns only {v} on shareholders' money, behind its {sector} peers"),
    "roa": ("Return on assets", _pct,
            "converts its asset base into profit efficiently at {v}",
            "generates just {v} on its asset base"),
    "roic": ("Return on invested capital", _pct,
            "returns {v} on invested capital",
            "returns only {v} on invested capital"),
    "net_margin": ("Net margin", _pct,
                   "keeps {v} of every rupee of sales as profit, above the sector norm",
                   "keeps only {v} of every rupee of sales as profit"),
    "operating_margin": ("Operating margin", _pct,
                         "runs a {v} operating margin",
                         "runs a thin {v} operating margin"),
    "gross_margin": ("Gross margin", _pct,
                     "holds a {v} gross margin",
                     "holds a narrow {v} gross margin"),
    "cfo_to_net_income": ("Cash conversion", lambda v: _num(v, 2, "x"),
                          "backs its reported profit with {v} of operating cash",
                          "converts profit to cash at only {v}"),
    "accrual_ratio": ("Accrual ratio", _pct,
                      "reports conservative accruals at {v} of assets",
                      "books {v} of assets as accruals, so profit is running ahead of cash"),
    "fcf_margin": ("Free cash flow margin", _pct,
                   "turns {v} of sales into free cash flow",
                   "free cash flow is {v} of sales"),
    "debt_to_equity": ("Debt to equity", lambda v: _num(v, 2, "x"),
                       "carries modest debt at {v} of equity",
                       "carries heavy debt at {v} of equity"),
    "interest_coverage": ("Interest cover", lambda v: _num(v, 1, "x"),
                          "covers its finance cost {v} over",
                          "covers its finance cost only {v} over"),
    "net_debt_to_ebitda": ("Net debt / EBITDA", lambda v: _num(v, 1, "x"),
                           "sits at {v} net debt to EBITDA",
                           "is stretched at {v} net debt to EBITDA"),
    "current_ratio": ("Current ratio", lambda v: _num(v, 2, "x"),
                      "holds {v} of current assets against current liabilities",
                      "holds only {v} of current assets against current liabilities"),
    "equity_ratio": ("Equity / assets", _pct,
                     "funds {v} of assets with equity",
                     "funds only {v} of assets with equity"),
    "revenue_growth": ("Revenue growth", _pct,
                       "grew revenue {v} over the last year",
                       "revenue moved {v} over the last year"),
    "earnings_growth": ("Earnings growth", _pct,
                        "grew earnings {v} year on year",
                        "earnings moved {v} year on year"),
    "revenue_cagr_3y": ("3-year revenue CAGR", _pct,
                        "has compounded revenue at {v} a year over three years",
                        "has compounded revenue at only {v} a year over three years"),
    "pe": ("P/E", lambda v: _num(v, 1, "x"),
           "trades on {v} earnings, cheap against its sector",
           "trades on {v} earnings, expensive against its sector"),
    "pb": ("P/B", lambda v: _num(v, 2, "x"),
           "trades at {v} book value, below peers",
           "trades at {v} book value, above peers"),
    "ev_ebitda": ("EV/EBITDA", lambda v: _num(v, 1, "x"),
                  "is valued at {v} EV/EBITDA",
                  "is valued richly at {v} EV/EBITDA"),
    "dividend_yield": ("Dividend yield", _pct,
                       "pays a {v} dividend yield",
                       "pays little income at a {v} yield"),
    "earnings_yield": ("Earnings yield", _pct,
                       "offers a {v} earnings yield",
                       "offers only a {v} earnings yield"),
    "fcf_yield": ("Free cash flow yield", _pct,
                  "throws off a {v} free cash flow yield",
                  "free cash flow yield is {v}"),
    "momentum_12_1": ("12-month momentum", _pct,
                      "is up {v} over the last year excluding the latest month",
                      "has fallen {v} over the last year excluding the latest month"),
    "px_to_sma200": ("Price vs 200-day average", _pct,
                     "trades {v} above its 200-day average",
                     "trades {v} relative to its 200-day average"),
    "rel_strength_6m": ("6-month relative strength", _pct,
                        "has beaten the KSE-100 by {v} over six months",
                        "has lagged the KSE-100 by {v} over six months"),
    "volatility_252d": ("1-year volatility", _pct,
                        "is unusually steady at {v} annualised volatility",
                        "is volatile at {v} annualised"),
}

BAND_OPENERS = {
    "STRONG BUY": "screens as one of the most attractive names in the KSE-100 right now",
    "BUY": "screens as attractive relative to the rest of the KSE-100",
    "HOLD": "screens as fairly valued against the rest of the KSE-100",
    "REDUCE": "screens poorly against the rest of the KSE-100",
    "AVOID": "screens as one of the least attractive names in the KSE-100",
}


def _top_contributors(row: pd.Series, n: int = 3, best: bool = True) -> List[tuple]:
    """Pick the metrics where this company stands furthest from its sector."""
    scored = []
    for pillar, cols in PILLARS.items():
        for zcol in cols:
            metric = zcol[2:]
            if metric not in METRIC_PHRASES:
                continue
            z = row.get(zcol)
            raw = row.get(metric)
            if z is None or pd.isna(z) or raw is None or pd.isna(raw):
                continue
            scored.append((float(z), metric, float(raw), pillar))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[0] if best else x[0])
    return scored[:n]


def _phrase(metric: str, z: float, raw: float, sector: str, positive: bool) -> str:
    label, fmt, good, bad = METRIC_PHRASES[metric]
    template = good if positive else bad
    return template.format(v=fmt(raw), sector=sector)


def explain(row: pd.Series) -> dict:
    """Build the full explanation object for one scored company."""
    ticker = row.get("ticker", "")
    name = row.get("name", ticker)
    sector = row.get("sector", "its sector")
    band = row.get("recommendation", "HOLD")
    score = float(row.get("final_score") or 0)
    rank = int(row.get("rank") or 0)
    f = row.get("f_score")
    z = row.get("z_score")
    fdet = row.get("_f_detail") or {}
    zdet = row.get("_z_detail") or {}

    strengths_raw = _top_contributors(row, 3, best=True)
    weaknesses_raw = _top_contributors(row, 3, best=False)
    # Do not present a below-average metric as a strength, or vice versa.
    strengths_raw = [s for s in strengths_raw if s[0] > 0.25]
    weaknesses_raw = [w for w in weaknesses_raw if w[0] < -0.25]

    strengths = [{
        "metric": m, "label": METRIC_PHRASES[m][0], "value": raw, "z": zv,
        "pillar": PILLAR_LABELS.get(p, p),
        "text": f"{ticker} {_phrase(m, zv, raw, sector, True)}.",
    } for zv, m, raw, p in strengths_raw]

    concerns = [{
        "metric": m, "label": METRIC_PHRASES[m][0], "value": raw, "z": zv,
        "pillar": PILLAR_LABELS.get(p, p),
        "text": f"{ticker} {_phrase(m, zv, raw, sector, False)}.",
    } for zv, m, raw, p in weaknesses_raw]

    for flag in (row.get("risk_flags") or []):
        concerns.append({"metric": "risk_flag", "label": "Risk flag",
                         "value": None, "z": None, "pillar": "Risk",
                         "text": f"Risk flag: {flag}."})

    # --- pillar table ----------------------------------------------------
    pillars = [{
        "key": p, "label": PILLAR_LABELS[p],
        "score": None if pd.isna(row.get(p)) else round(float(row.get(p)), 1),
        "z": None if pd.isna(row.get(f"{p}_z")) else round(float(row.get(f"{p}_z")), 2),
        "weight": None,
    } for p in PILLARS]
    from app.config import settings as _s
    tw = sum(_s.composite_weights.values())
    for p in pillars:
        p["weight"] = round(_s.composite_weights[p["key"]] / tw, 3)
    best_pillar = max(pillars, key=lambda p: p["score"] if p["score"] is not None else -1)
    worst_pillar = min(pillars, key=lambda p: p["score"] if p["score"] is not None else 999)

    # --- headline and summary -------------------------------------------
    headline = (f"{name} ({ticker}) {BAND_OPENERS.get(band, 'screens neutrally')}, "
                f"ranking {rank} of {int(row.get('universe_size') or 100)} on a composite score of {score:.0f}/100.")

    val_bits = []
    if pd.notna(row.get("pe")):
        val_bits.append(f"a P/E of {row['pe']:.1f}x")
    if pd.notna(row.get("pb")):
        val_bits.append(f"{row['pb']:.2f}x book")
    if pd.notna(row.get("dividend_yield")) and float(row["dividend_yield"]) > 0.001:
        val_bits.append(f"a {float(row['dividend_yield'])*100:.1f}% dividend yield")
    valuation_note = (f"At PKR {float(row.get('price') or 0):,.2f} the shares trade on "
                      + ", ".join(val_bits) + ".") if val_bits else \
        f"The shares trade at PKR {float(row.get('price') or 0):,.2f}."

    fv = f_score_verdict(float(f) if f is not None and pd.notna(f) else np.nan)
    zv = z_verdict(float(z) if z is not None and pd.notna(z) else np.nan)
    screens_note = (
        f"The Piotroski F-Score is {'n/a' if pd.isna(f) else f'{float(f):.0f} of 9'} "
        f"({fv}) and the Altman Z''-Score is "
        f"{'not applicable to financials' if pd.isna(z) else f'{float(z):.2f} ({zv})'}."
    )

    summary = " ".join([
        f"{name} sits in the {sector} sector and scores best on "
        f"{best_pillar['label'].lower()} ({best_pillar['score']:.0f}/100), "
        f"weakest on {worst_pillar['label'].lower()} ({worst_pillar['score']:.0f}/100).",
        valuation_note,
        screens_note,
    ])

    # --- what would change the view --------------------------------------
    triggers: List[str] = []
    if worst_pillar["key"] == "value":
        triggers.append("a pull-back in the share price, or earnings catching up with the current multiple")
    if worst_pillar["key"] == "growth":
        triggers.append("two consecutive quarters of revenue growth above the sector median")
    if worst_pillar["key"] == "safety":
        triggers.append("a reduction in net debt or a visible improvement in interest cover")
    if worst_pillar["key"] == "quality":
        triggers.append("margin recovery, and operating cash flow catching up with reported profit")
    if worst_pillar["key"] == "momentum":
        triggers.append("the price reclaiming its 200-day average on rising volume")
    if row.get("z_zone") == "distress":
        triggers.append("the Altman Z-Score moving back out of the distress zone")
    if not triggers:
        triggers.append("a material change in the next quarterly filing")

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "recommendation": band,
        "headline": headline,
        "summary": summary,
        "valuation_note": valuation_note,
        "screens_note": screens_note,
        "strengths": strengths,
        "concerns": concerns,
        "pillars": pillars,
        "f_score": None if pd.isna(f) else round(float(f), 1),
        "f_score_verdict": fv,
        "f_tests": fdet.get("tests", {}),
        "z_score": None if pd.isna(z) else round(float(z), 2),
        "z_zone": row.get("z_zone"),
        "z_components": zdet.get("components", {}),
        "risk_flags": row.get("risk_flags") or [],
        "what_would_change_this": triggers,
        "as_of": str(row.get("asof_date")),
        "disclaimer": ("Generated by an automated screen for research and educational "
                       "use. Not investment advice, and not a substitute for a "
                       "SECP-licensed adviser."),
    }
