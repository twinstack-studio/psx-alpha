"""Bulk load and query helpers sitting between pandas and the database."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Iterable, List, Optional

import pandas as pd
from sqlalchemy import delete, select, text

from app.db.models import (
    BacktestRun, Company, FinancialStatement, IndexPrice, MacroSeries, Price,
    Ratio, Score, SessionLocal, engine, init_db,
)
from app.ingest.universe import UNIVERSE, index_weights, FINANCIAL_SECTORS

CHUNK = 5_000


def _to_sql(df: pd.DataFrame, table: str, cols: List[str]) -> int:
    """Append a frame to a table, keeping only the mapped columns."""
    if df is None or df.empty:
        return 0
    out = df[[c for c in cols if c in df.columns]].copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.date
    out.to_sql(table, engine, if_exists="append", index=False, chunksize=CHUNK)
    return len(out)


def save_companies(shares: dict | None = None) -> int:
    weights = index_weights()
    rows = []
    for c in UNIVERSE:
        rows.append(dict(
            ticker=c.ticker, name=c.name, sector=c.sector, size_tier=c.size_tier,
            listed_year=c.listed_year,
            shares_outstanding=float((shares or {}).get(c.ticker, 0.0)),
            index_weight=float(weights[c.ticker]),
            is_financial=c.sector in FINANCIAL_SECTORS,
        ))
    df = pd.DataFrame(rows)
    return _to_sql(df, "companies", list(df.columns))


STMT_COLS = [
    "ticker", "period_end", "report_date", "fiscal_year", "fiscal_quarter",
    "revenue", "cost_of_sales", "gross_profit", "operating_expenses",
    "operating_income", "depreciation", "finance_cost", "other_income",
    "profit_before_tax", "taxation", "net_income", "eps", "dividend_per_share",
    "cash", "receivables", "inventory", "current_assets", "fixed_assets",
    "total_assets", "payables", "short_term_debt", "current_liabilities",
    "long_term_debt", "total_liabilities", "total_equity", "retained_earnings",
    "cfo", "capex", "cfi", "cff", "free_cash_flow", "shares_outstanding", "source",
]


def save_statements(df: pd.DataFrame) -> int:
    return _to_sql(df, "financial_statements", STMT_COLS)


def save_prices(df: pd.DataFrame) -> int:
    return _to_sql(df, "prices", ["ticker", "date", "open", "high", "low", "close", "volume"])


def save_index(df: pd.DataFrame) -> int:
    return _to_sql(df, "index_prices", ["symbol", "date", "close", "volume"])


def save_macro(df: pd.DataFrame) -> int:
    m = df.reset_index().rename(columns={"index": "date"})
    return _to_sql(m, "macro_series",
                   ["date", "policy_rate", "cpi_yoy", "usd_pkr",
                    "fx_reserves_usd_bn", "gdp_growth", "cycle"])


def save_ratios(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    value_cols = [c for c in df.columns
                  if not c.startswith("z_") and c not in
                  {"ticker", "period_end", "report_date", "sector"}]
    z_cols = [c for c in df.columns if c.startswith("z_")]
    rows = []
    for _, r in df.iterrows():
        rows.append(dict(
            ticker=r["ticker"],
            period_end=pd.Timestamp(r["period_end"]).date(),
            report_date=pd.Timestamp(r["report_date"]).date(),
            sector=r["sector"],
            values=json.dumps({c: _clean(r[c]) for c in value_cols}),
            sector_z=json.dumps({c: _clean(r[c]) for c in z_cols}),
        ))
    pd.DataFrame(rows).to_sql("ratios", engine, if_exists="append",
                              index=False, chunksize=CHUNK)
    return len(rows)


def _clean(v):
    if v is None or (isinstance(v, float) and (pd.isna(v) or not pd.notna(v))):
        return None
    if isinstance(v, (pd.Timestamp, date)):
        return str(v)
    try:
        f = float(v)
        return None if pd.isna(f) else round(f, 6)
    except (TypeError, ValueError):
        return str(v)


def save_scores(scored: pd.DataFrame, asof, model_version: str = "v1",
                explanations: dict | None = None) -> int:
    """Store one dated cross-section, replacing any run already held for it.

    `scores` is unique on (ticker, asof_date, model_version), so a blind append
    makes the pipeline single-use: the second `run_pipeline` for the same as-of
    date dies on the constraint after the whole backtest has already run.
    Re-scoring a date is a legitimate thing to do — it is what happens every
    time the pipeline is re-run — and the right semantics are replace, not
    duplicate, so the day's rows are cleared first.
    """
    if scored is None or scored.empty:
        return 0

    asof_date = pd.Timestamp(asof).date()
    with SessionLocal() as s:
        s.execute(delete(Score).where(Score.asof_date == asof_date,
                                      Score.model_version == model_version))
        s.commit()

    rows = []
    for _, r in scored.iterrows():
        rows.append(dict(
            ticker=r["ticker"], asof_date=pd.Timestamp(asof).date(),
            model_version=model_version,
            f_score=_num(r.get("f_score")), z_score=_num(r.get("z_score")),
            quality=_num(r.get("quality")), value=_num(r.get("value")),
            safety=_num(r.get("safety")), growth=_num(r.get("growth")),
            momentum=_num(r.get("momentum")),
            rule_score=_num(r.get("rule_score")), ml_score=_num(r.get("ml_score")),
            final_score=_num(r.get("final_score")),
            percentile=_num(r.get("percentile")), rank=int(r.get("rank") or 0),
            recommendation=r.get("recommendation", "HOLD"),
            conviction=_num(r.get("conviction")),
            explanation=json.dumps((explanations or {}).get(r["ticker"], {})),
            created_at=datetime.utcnow(),
        ))
    pd.DataFrame(rows).to_sql("scores", engine, if_exists="append",
                              index=False, chunksize=CHUNK)
    return len(rows)


def _num(v) -> float:
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0


def save_backtest(name: str, strategy: str, start, end, params: dict,
                  metrics: dict, curve: pd.Series, holdings: dict) -> int:
    with SessionLocal() as s:
        run = BacktestRun(
            name=name, strategy=strategy,
            start_date=pd.Timestamp(start).date(), end_date=pd.Timestamp(end).date(),
            params=params, metrics=metrics,
            equity_curve={str(pd.Timestamp(k).date()): round(float(v), 4)
                          for k, v in curve.items()},
            holdings=holdings,
        )
        s.add(run)
        s.commit()
        return run.id


# --- reads ---------------------------------------------------------------
def load_statements() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM financial_statements", engine)


def load_prices() -> pd.DataFrame:
    return pd.read_sql("SELECT ticker, date, open, high, low, close, volume FROM prices", engine)


def load_index() -> pd.DataFrame:
    return pd.read_sql("SELECT symbol, date, close, volume FROM index_prices", engine)


def load_macro() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM macro_series", engine)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").drop(columns=["id"], errors="ignore")


def load_companies() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM companies", engine)


def latest_scores(model_version: str = "v1") -> pd.DataFrame:
    q = """
        SELECT * FROM scores
        WHERE model_version = :mv
          AND asof_date = (SELECT MAX(asof_date) FROM scores WHERE model_version = :mv)
        ORDER BY rank
    """
    return pd.read_sql(text(q), engine, params={"mv": model_version})


def reset_database() -> None:
    init_db(drop=True)
