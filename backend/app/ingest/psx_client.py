"""Live PSX and SBP data clients.

These target the real public endpoints:

* `dps.psx.com.pk/timeseries/int/<SYMBOL>` - intraday tick series
* `dps.psx.com.pk/historical` - end-of-day board for a given date
* `dps.psx.com.pk/company/<SYMBOL>` - profile, ratios and the filings list
* `dps.psx.com.pk/indices` - index levels including KSE100
* `easydata.sbp.org.pk` - State Bank macro series

PSX publishes accounts as PDFs rather than as structured data, so a production
deployment needs the filing parser in `filings.py` behind these calls. Each
function returns None rather than raising when the network or the endpoint is
unavailable, and `fetch_all` returns None if it cannot assemble a complete
panel, which is what makes the simulator the safe default for a reproducible
backtest.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

log = logging.getLogger(__name__)

BASE = "https://dps.psx.com.pk"
SBP_BASE = "https://easydata.sbp.org.pk/api/v1"
HEADERS = {
    "User-Agent": "PSX-FYP-Research/1.0 (academic project; contact via university)",
    "Accept": "application/json, text/html;q=0.9",
}
TIMEOUT = 20.0


def _client():
    try:
        import httpx
    except ImportError:                                  # pragma: no cover
        log.warning("httpx is not installed; live fetch disabled")
        return None
    return httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)


def fetch_quote(symbol: str) -> Optional[dict]:
    """Latest traded price and volume for one scrip."""
    c = _client()
    if c is None:
        return None
    try:
        with c:
            r = c.get(f"{BASE}/timeseries/int/{symbol}")
            r.raise_for_status()
            payload = r.json()
        series = payload.get("data") or []
        if not series:
            return None
        ts, price, volume = series[-1][:3]
        return {"ticker": symbol, "price": float(price),
                "volume": float(volume),
                "timestamp": datetime.fromtimestamp(int(ts)).isoformat()}
    except Exception as exc:
        log.debug("quote fetch failed for %s: %s", symbol, exc)
        return None


def fetch_eod_board(on: date) -> Optional[pd.DataFrame]:
    """End-of-day board for every scrip on a given trading date."""
    c = _client()
    if c is None:
        return None
    try:
        with c:
            r = c.post(f"{BASE}/historical", data={"date": on.isoformat()})
            r.raise_for_status()
            tables = pd.read_html(r.text)
        if not tables:
            return None
        df = tables[0]
        df.columns = [str(x).strip().lower() for x in df.columns]
        rename = {"symbol": "ticker", "ldcp": "prev_close", "current": "close"}
        df = df.rename(columns=rename)
        df["date"] = on
        keep = [c_ for c_ in ["ticker", "date", "open", "high", "low", "close", "volume"]
                if c_ in df.columns]
        return df[keep]
    except Exception as exc:
        log.debug("eod board failed for %s: %s", on, exc)
        return None


def fetch_index(symbol: str = "KSE100") -> Optional[dict]:
    c = _client()
    if c is None:
        return None
    try:
        with c:
            r = c.get(f"{BASE}/indices")
            r.raise_for_status()
            tables = pd.read_html(r.text)
        for t in tables:
            t.columns = [str(x).strip().upper() for x in t.columns]
            col = next((x for x in t.columns if "INDEX" in x), None)
            if col is None:
                continue
            hit = t[t[col].astype(str).str.upper().str.replace(" ", "") == symbol]
            if len(hit):
                row = hit.iloc[0]
                cur = next((x for x in t.columns if "CURRENT" in x or "CLOSE" in x), None)
                return {"symbol": symbol, "close": float(row[cur]),
                        "date": date.today().isoformat()}
    except Exception as exc:
        log.debug("index fetch failed: %s", exc)
    return None


def fetch_company_profile(symbol: str) -> Optional[dict]:
    """Sector, shares outstanding and the headline ratios PSX publishes."""
    c = _client()
    if c is None:
        return None
    try:
        with c:
            r = c.get(f"{BASE}/company/{symbol}")
            r.raise_for_status()
            tables = pd.read_html(r.text)
        out: Dict[str, str] = {"ticker": symbol}
        for t in tables:
            if t.shape[1] == 2:
                for _, row in t.iterrows():
                    key = str(row.iloc[0]).strip().lower().replace(" ", "_")
                    out[key] = str(row.iloc[1]).strip()
        return out or None
    except Exception as exc:
        log.debug("profile fetch failed for %s: %s", symbol, exc)
        return None


def fetch_sbp_macro(series_key: str = "TS_GP_IR_PRA_M.P00010") -> Optional[pd.DataFrame]:
    """SBP EasyData monthly series (policy rate by default)."""
    c = _client()
    if c is None:
        return None
    try:
        with c:
            r = c.get(f"{SBP_BASE}/series/{series_key}/data")
            r.raise_for_status()
            payload = r.json()
        rows = payload.get("data") or []
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df.iloc[:, 0])
        df["value"] = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        return df[["date", "value"]].dropna()
    except Exception as exc:
        log.debug("SBP fetch failed: %s", exc)
        return None


def fetch_all(*_args, **_kwargs) -> Optional[dict]:
    """Assemble the full historical panel from live sources.

    Returns None: PSX does not expose a free bulk history of standardized
    financial statements, so the decade of point-in-time fundamentals the
    backtest needs cannot be built from these endpoints alone. The live
    functions above cover current prices, index levels and company profiles,
    which is what a production deployment would refresh daily on top of a
    fundamentals database built by the filing parser.
    """
    log.info("live bulk history is not available from public PSX endpoints")
    return None


def health() -> dict:
    """Report which live endpoints are reachable right now."""
    out = {"psx_quote": False, "psx_index": False, "sbp_macro": False}
    try:
        out["psx_quote"] = fetch_quote("OGDC") is not None
        out["psx_index"] = fetch_index() is not None
        out["sbp_macro"] = fetch_sbp_macro() is not None
    except Exception:
        pass
    return out
