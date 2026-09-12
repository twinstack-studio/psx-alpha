"""Shared fixtures.

The suite is built on hand-made frames rather than on the simulated database,
so a test asserts against arithmetic someone can check by hand. Where a test
does need the real artefacts — the API tests read the exported bundle — it
skips cleanly rather than failing when the pipeline has not been run.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import EXPORT_DIR


# --------------------------------------------------------------------------
# Statement panels
# --------------------------------------------------------------------------
def make_statements(
    tickers: list[str],
    periods: int = 12,
    start: str = "2019-03-31",
    revenue: float = 1000.0,
    growth: float = 0.0,
    report_lag_days: int = 45,
) -> pd.DataFrame:
    """A clean quarterly panel that satisfies the accounting identities.

    Every flow is a fixed fraction of revenue and every stock a fixed multiple
    of it, so a TTM sum or a margin has an obvious expected value: four equal
    quarters of 1,000 must give a TTM revenue of exactly 4,000.
    """
    rows = []
    period_ends = pd.date_range(start, periods=periods, freq="QE")
    for ticker in tickers:
        for i, pe in enumerate(period_ends):
            rev = revenue * ((1 + growth) ** i)
            rows.append({
                "ticker": ticker,
                "period_end": pe,
                "report_date": pe + pd.Timedelta(days=report_lag_days),
                "fiscal_year": pe.year,
                "quarter": (pe.month - 1) // 3 + 1,
                "revenue": rev,
                "cost_of_sales": rev * 0.60,
                "gross_profit": rev * 0.40,
                "operating_expenses": rev * 0.15,
                "operating_income": rev * 0.25,
                "depreciation": rev * 0.05,
                "finance_cost": rev * 0.03,
                "other_income": 0.0,
                "profit_before_tax": rev * 0.22,
                "taxation": rev * 0.07,
                "net_income": rev * 0.15,
                "eps": rev * 0.15 / 100.0,
                "dividend_per_share": rev * 0.05 / 100.0,
                "cfo": rev * 0.18,
                "capex": rev * 0.06,
                "cfi": -rev * 0.06,
                "cff": -rev * 0.04,
                "free_cash_flow": rev * 0.12,
                "cash": rev * 0.5,
                "receivables": rev * 0.8,
                "inventory": rev * 0.6,
                "current_assets": rev * 2.0,
                "fixed_assets": rev * 3.0,
                "total_assets": rev * 5.0,
                "payables": rev * 0.7,
                "short_term_debt": rev * 0.3,
                "current_liabilities": rev * 1.2,
                "long_term_debt": rev * 0.8,
                "total_liabilities": rev * 2.0,
                "total_equity": rev * 3.0,
                "retained_earnings": rev * 1.5,
                "shares_outstanding": 100.0,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def statements() -> pd.DataFrame:
    """Four non-financial names from the real universe, so sector lookups and
    the financial/non-financial split behave as they do in production."""
    return make_statements(["OGDC", "PPL", "MARI", "POL"])


# --------------------------------------------------------------------------
# Price panels
# --------------------------------------------------------------------------
def make_prices(
    tickers: list[str],
    days: int = 900,
    start: str = "2019-01-01",
    drift: float = 0.0003,
    seed: int = 7,
) -> pd.DataFrame:
    """Business-day OHLCV with a deterministic random walk."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=days)
    rows = []
    for k, ticker in enumerate(tickers):
        steps = rng.normal(drift, 0.015, size=days)
        close = 100.0 * np.exp(np.cumsum(steps)) * (1 + 0.1 * k)
        rows.append(pd.DataFrame({
            "date": dates,
            "ticker": ticker,
            "open": close * 0.995,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": rng.integers(200_000, 2_000_000, size=days).astype(float),
        }))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture
def prices() -> pd.DataFrame:
    return make_prices(["OGDC", "PPL", "MARI", "POL"])


@pytest.fixture
def index_df() -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-01", periods=900)
    rng = np.random.default_rng(11)
    close = 40_000.0 * np.exp(np.cumsum(rng.normal(0.00025, 0.011, size=900)))
    return pd.DataFrame({"date": dates, "close": close})


# --------------------------------------------------------------------------
# Scoring inputs
# --------------------------------------------------------------------------
@pytest.fixture
def perfect_piotroski() -> tuple[pd.Series, pd.Series]:
    """A company that passes all nine tests, and its year-ago row."""
    curr = pd.Series({
        "roa": 0.12, "cfo_ttm": 500.0, "net_income_ttm": 300.0,
        "debt_to_assets": 0.20, "current_ratio": 2.0, "gross_margin": 0.42,
        "asset_turnover": 0.90, "shares_outstanding": 100.0,
        "equity_ratio": 0.55, "net_margin": 0.18,
        "revenue_ttm": 4000.0, "total_assets": 5000.0,
    })
    prev = pd.Series({
        "roa": 0.08, "cfo_ttm": 400.0, "net_income_ttm": 250.0,
        "debt_to_assets": 0.30, "current_ratio": 1.5, "gross_margin": 0.38,
        "asset_turnover": 0.80, "shares_outstanding": 100.0,
        "equity_ratio": 0.50, "net_margin": 0.15,
        "revenue_ttm": 3600.0, "total_assets": 5000.0,
    })
    return curr, prev


@pytest.fixture
def solvent_row() -> pd.Series:
    """Balance sheet comfortably inside the Altman safe zone."""
    return pd.Series({
        "total_assets": 1000.0, "total_equity": 700.0,
        "working_capital": 300.0, "retained_earnings": 400.0,
        "ebit_ttm": 150.0, "revenue_ttm": 900.0,
    })


# --------------------------------------------------------------------------
# Exported artefacts (API tests)
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def bundle_path() -> Path:
    path = EXPORT_DIR / "dashboard.json"
    if not path.exists():
        pytest.skip("no dashboard.json; run `python -m scripts.run_pipeline` first")
    return path
