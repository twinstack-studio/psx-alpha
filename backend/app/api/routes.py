"""REST API.

Serves the ranked, explained recommendations the proposal calls for, plus the
backtest evidence behind them. The heavy artefacts (scores, backtests) are
produced offline by `scripts/run_pipeline.py`; this layer reads them, so a
request never triggers a model fit.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import EXPORT_DIR, settings
from app.db import repository as repo
from app.ingest import psx_client
from app.scoring.composite import PILLAR_LABELS

router = APIRouter()


# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _bundle() -> dict:
    path = EXPORT_DIR / "dashboard.json"
    if not path.exists():
        raise HTTPException(
            503, "No analysis bundle yet. Run `python -m scripts.run_pipeline`.")
    return json.loads(path.read_text(encoding="utf-8"))


def _company_file(ticker: str) -> dict:
    path = EXPORT_DIR / "companies" / f"{ticker.upper()}.json"
    if not path.exists():
        raise HTTPException(404, f"No analysis for {ticker.upper()}")
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_cache() -> None:
    _bundle.cache_clear()


# --------------------------------------------------------------------------
class Health(BaseModel):
    status: str
    database: str
    has_analysis: bool
    as_of: Optional[str] = None
    universe_size: Optional[int] = None


@router.get("/health", response_model=Health, tags=["system"])
def health():
    try:
        b = _bundle()
        return Health(status="ok", database=settings.database_url,
                      has_analysis=True, as_of=b["meta"]["asOf"],
                      universe_size=b["meta"]["universeSize"])
    except HTTPException:
        return Health(status="degraded", database=settings.database_url,
                      has_analysis=False)


@router.get("/meta", tags=["system"])
def meta():
    """Model configuration, data window and the weights in force."""
    b = _bundle()
    return {**b["meta"], "bands": b["bands"],
            "pillarLabels": PILLAR_LABELS}


@router.get("/live/status", tags=["system"])
def live_status():
    """Which live PSX and SBP endpoints are reachable from this host."""
    return psx_client.health()


# --------------------------------------------------------------------------
@router.get("/recommendations", tags=["recommendations"])
def recommendations(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sector: Optional[str] = None,
    band: Optional[str] = Query(None, description="STRONG BUY, BUY, HOLD, REDUCE or AVOID"),
    search: Optional[str] = None,
    min_score: Optional[float] = Query(None, ge=0, le=100),
    sort: Literal["rank", "score", "ticker", "momentum", "value", "dividend"] = "rank",
):
    """The ranked KSE-100 with the plain-language headline for each name."""
    rows: List[dict] = list(_bundle()["recommendations"])
    if sector:
        rows = [r for r in rows if (r.get("sector") or "").lower() == sector.lower()]
    if band:
        rows = [r for r in rows if (r.get("recommendation") or "").upper() == band.upper()]
    if search:
        q = search.lower()
        rows = [r for r in rows
                if q in (r.get("ticker") or "").lower() or q in (r.get("name") or "").lower()]
    if min_score is not None:
        rows = [r for r in rows if (r.get("finalScore") or 0) >= min_score]

    keys = {
        "rank": lambda r: r.get("rank") or 9999,
        "score": lambda r: -(r.get("finalScore") or 0),
        "ticker": lambda r: r.get("ticker") or "",
        "momentum": lambda r: -(r.get("momentum12m") or -9),
        "value": lambda r: (r.get("pe") or 9999),
        "dividend": lambda r: -(r.get("dividendYield") or 0),
    }
    rows.sort(key=keys[sort])
    return {"total": len(rows), "offset": offset, "limit": limit,
            "asOf": _bundle()["meta"]["asOf"],
            "items": rows[offset: offset + limit]}


@router.get("/recommendations/top", tags=["recommendations"])
def top_picks(n: int = Query(10, ge=1, le=50)):
    """The names the engine would hold today, after the liquidity and sector
    rules the backtest applies."""
    rows = sorted(_bundle()["recommendations"], key=lambda r: r.get("rank") or 9999)
    picked, per_sector = [], {}
    cap = max(1, int(settings.max_sector_weight * n))
    for r in rows:
        if len(picked) >= n:
            break
        if (r.get("turnoverPkrM") or 0) < 5.0:
            continue
        if r.get("recommendation") == "AVOID":
            continue
        sec = r.get("sector") or ""
        if per_sector.get(sec, 0) >= cap:
            continue
        picked.append(r)
        per_sector[sec] = per_sector.get(sec, 0) + 1
    weight = round(1.0 / len(picked), 4) if picked else 0.0
    return {"asOf": _bundle()["meta"]["asOf"], "count": len(picked),
            "weightEach": weight,
            "items": [{**r, "suggestedWeight": weight} for r in picked]}


@router.get("/companies/{ticker}", tags=["companies"])
def company(ticker: str):
    """Full dossier: explanation, statements, ratio history and peers."""
    return _company_file(ticker)


@router.get("/companies/{ticker}/explanation", tags=["companies"])
def explanation(ticker: str):
    return _company_file(ticker).get("explanation", {})


@router.get("/sectors", tags=["market"])
def sectors():
    return {"asOf": _bundle()["meta"]["asOf"], "items": _bundle()["sectors"]}


@router.get("/backtest", tags=["backtest"])
def backtest():
    """Walk-forward performance of every strategy against the KSE-100."""
    b = _bundle()
    return {"meta": {k: b["meta"][k] for k in
                     ["backtestStart", "backtestEnd", "topN", "rebalance",
                      "costBps", "maxSectorWeight"]},
            "performance": b["performance"],
            "equityCurve": b["equityCurve"],
            "drawdown": b["drawdown"]}


@router.get("/backtest/rebalances", tags=["backtest"])
def rebalances(limit: int = Query(40, ge=1, le=200)):
    return {"items": _bundle()["rebalances"][-limit:]}


@router.get("/model", tags=["model"])
def model_diagnostics():
    """Feature importance and out-of-sample information coefficients."""
    return _bundle()["ml"]


@router.get("/market", tags=["market"])
def market():
    return _bundle()["market"]


# --------------------------------------------------------------------------
class ScreenRequest(BaseModel):
    """Re-weight the composite without refitting anything."""
    quality: float = Field(0.30, ge=0, le=1)
    value: float = Field(0.25, ge=0, le=1)
    safety: float = Field(0.20, ge=0, le=1)
    growth: float = Field(0.15, ge=0, le=1)
    momentum: float = Field(0.10, ge=0, le=1)
    ml_weight: float = Field(settings.blend_ml_weight, ge=0, le=1)
    top_n: int = Field(15, ge=1, le=100)
    exclude_distress: bool = True
    min_turnover_pkr_m: float = 5.0
    sectors: Optional[List[str]] = None


@router.post("/screen", tags=["recommendations"])
def screen(req: ScreenRequest):
    """Score the live cross-section under custom pillar weights.

    The pillar z-scores are precomputed, so this is a re-weighting rather than
    a re-fit: the same numbers the dashboard's sliders produce, available to
    any client.
    """
    rows = _bundle()["recommendations"]
    weights = {"quality": req.quality, "value": req.value, "safety": req.safety,
               "growth": req.growth, "momentum": req.momentum}
    total = sum(weights.values()) or 1.0
    out = []
    for r in rows:
        pz = r.get("pillarZ") or {}
        if req.sectors and r.get("sector") not in req.sectors:
            continue
        if (r.get("turnoverPkrM") or 0) < req.min_turnover_pkr_m:
            continue
        if req.exclude_distress and r.get("zZone") == "distress":
            continue
        z = sum((pz.get(k) or 0.0) * (w / total) for k, w in weights.items())
        rule = max(0.0, min(100.0, 50.0 + (100.0 / 6.0) * z))
        blended = (1 - req.ml_weight) * rule + req.ml_weight * (r.get("mlScore") or rule)
        cap = r.get("scoreCap")
        if cap is not None:
            blended = min(blended, cap)
        out.append({"ticker": r["ticker"], "name": r["name"], "sector": r["sector"],
                    "price": r["price"], "score": round(blended, 2),
                    "baseScore": r.get("finalScore"),
                    "pe": r.get("pe"), "roe": r.get("roe"),
                    "dividendYield": r.get("dividendYield"),
                    "riskFlags": r.get("riskFlags", [])})
    out.sort(key=lambda r: -r["score"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
        r["recommendation"] = settings.band_for(1.0 - (i - 1) / max(len(out), 1))
    return {"weights": {**weights, "mlWeight": req.ml_weight},
            "total": len(out), "items": out[: req.top_n]}


@router.get("/scores/history", tags=["model"])
def score_history(ticker: str, limit: int = Query(40, ge=1, le=200)):
    """Every dated score stored for one company."""
    df = pd.read_sql(
        "SELECT asof_date, rule_score, ml_score, final_score, rank, recommendation "
        "FROM scores WHERE ticker = ? ORDER BY asof_date DESC LIMIT ?",
        repo.engine, params=(ticker.upper(), limit))
    if df.empty:
        raise HTTPException(404, f"No stored scores for {ticker.upper()}")
    return {"ticker": ticker.upper(), "items": df.to_dict("records")}
