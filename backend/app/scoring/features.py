"""Point-in-time cross-section builder.

`snapshot(asof)` returns one row per company describing everything the engine
knew about it on that date and nothing it did not. Both the rule-based scorer
and the machine-learning ranker consume this same frame, which is what keeps
the two comparable.

The point-in-time guarantee rests on two filters:

* fundamentals use the newest filing whose `report_date` is on or before the
  as-of date, never the newest `period_end`;
* prices and technicals use the last trading day on or before the as-of date.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List

import numpy as np
import pandas as pd

from app.etl.ratios import RATIO_COLS, _winsorized_z
from app.ingest.universe import BY_TICKER, FINANCIAL_SECTORS
from app.scoring.technicals import TECH_COLS

# Valuation ratios computed at the as-of date from price x fundamentals.
MARKET_COLS = [
    "pe", "pb", "ps", "ev_ebitda", "earnings_yield", "dividend_yield",
    "fcf_yield", "book_yield", "market_cap",
]
# Cheap = high score, so these get their z flipped.
MARKET_LOWER_IS_BETTER = {"pe", "pb", "ps", "ev_ebitda"}


class FeatureStore:
    """Holds the full history once so snapshots are cheap to take."""

    def __init__(self, ratios: pd.DataFrame, tech: pd.DataFrame,
                 prices: pd.DataFrame, index_df: pd.DataFrame,
                 macro: pd.DataFrame | None = None):
        self.ratios = ratios.copy()
        self.ratios["report_date"] = pd.to_datetime(self.ratios["report_date"])
        self.ratios["period_end"] = pd.to_datetime(self.ratios["period_end"])
        self.ratios = self.ratios.sort_values(["ticker", "report_date"])

        self.tech = tech.copy()
        self.tech["date"] = pd.to_datetime(self.tech["date"])
        self.tech = self.tech.set_index("date").sort_index()

        px = prices.copy()
        px["date"] = pd.to_datetime(px["date"])
        self.close = px.pivot(index="date", columns="ticker", values="close").sort_index()

        idx = index_df.copy()
        idx["date"] = pd.to_datetime(idx["date"])
        self.bench = idx.set_index("date")["close"].sort_index()

        self.macro = macro
        if macro is not None:
            self.macro = macro.copy()
            self.macro.index = pd.to_datetime(self.macro.index)

        self.trading_days = self.close.index

    # -- helpers ----------------------------------------------------------
    def last_trading_day(self, asof) -> pd.Timestamp | None:
        asof = pd.Timestamp(asof)
        prior = self.trading_days[self.trading_days <= asof]
        return prior[-1] if len(prior) else None

    def latest_filings(self, asof) -> pd.DataFrame:
        """Newest filing per ticker that was public on or before `asof`,
        together with the same company's filing four quarters earlier."""
        asof = pd.Timestamp(asof)
        visible = self.ratios[self.ratios["report_date"] <= asof]
        if visible.empty:
            return pd.DataFrame()
        curr = visible.groupby("ticker", as_index=False).tail(1).set_index("ticker")
        # year-ago comparison row (4 quarters back in period terms)
        prev_rows = {}
        for ticker, g in visible.groupby("ticker"):
            if len(g) >= 5:
                prev_rows[ticker] = g.iloc[-5]
        prev = pd.DataFrame(prev_rows).T if prev_rows else pd.DataFrame()
        return curr, prev

    # -- the snapshot -----------------------------------------------------
    def snapshot(self, asof) -> pd.DataFrame:
        asof = pd.Timestamp(asof)
        day = self.last_trading_day(asof)
        if day is None:
            return pd.DataFrame()
        got = self.latest_filings(asof)
        if isinstance(got, pd.DataFrame) and got.empty:
            return pd.DataFrame()
        curr, prev = got

        px = self.close.loc[day]
        df = curr.copy()
        df["asof_date"] = asof.date()
        df["price_date"] = day.date()
        df["price"] = px.reindex(df.index).values
        df["days_since_filing"] = (asof - df["report_date"]).dt.days
        df = df[df["price"].notna() & (df["price"] > 0)]
        if df.empty:
            return df

        # --- valuation at today's price ---------------------------------
        shares = df["shares_outstanding"].replace(0, np.nan)
        mcap = df["price"] * shares                       # PKR millions
        df["market_cap"] = mcap
        df["pe"] = (mcap / df["net_income_ttm"]).where(df["net_income_ttm"] > 0)
        df["pb"] = (mcap / df["total_equity"]).where(df["total_equity"] > 0)
        df["ps"] = (mcap / df["revenue_ttm"]).where(df["revenue_ttm"] > 0)
        ev = mcap + df["net_debt"]
        df["ev_ebitda"] = (ev / df["ebitda_ttm"]).where(df["ebitda_ttm"] > 0)
        df["earnings_yield"] = df["net_income_ttm"] / mcap
        df["book_yield"] = df["total_equity"] / mcap
        df["dividend_yield"] = df["dps_ttm"] / df["price"]
        fcf = df["cfo_ttm"] - (df["capex_to_revenue"] * df["revenue_ttm"]).fillna(0)
        df["fcf_yield"] = fcf / mcap
        for c in ["pe", "pb", "ps", "ev_ebitda"]:
            df[c] = df[c].clip(0, 200)
        for c in ["earnings_yield", "book_yield", "fcf_yield"]:
            df[c] = df[c].clip(-1.5, 1.5)
        df["dividend_yield"] = df["dividend_yield"].clip(0, 0.6)

        # --- sector-relative z for the valuation ratios ------------------
        for col in MARKET_COLS:
            if col == "market_cap":
                continue
            z = pd.Series(np.nan, index=df.index)
            market_z = _winsorized_z(df[col])
            for sec, grp in df.groupby("sector"):
                if grp[col].notna().sum() >= 4:
                    z.loc[grp.index] = _winsorized_z(grp[col]).values
                else:
                    z.loc[grp.index] = market_z.reindex(grp.index).values
            if col in MARKET_LOWER_IS_BETTER:
                z = -z
            df[f"z_{col}"] = z.clip(-3, 3)
        df["log_market_cap"] = np.log(df["market_cap"].clip(lower=1.0))
        df["z_size"] = _winsorized_z(df["log_market_cap"]).clip(-3, 3)

        # --- technicals at the price date --------------------------------
        try:
            tech_day = self.tech.loc[[day]]
        except KeyError:
            tech_day = pd.DataFrame()
        if not tech_day.empty:
            tech_day = tech_day.set_index("ticker")
            for col in TECH_COLS:
                if col in tech_day.columns:
                    df[col] = tech_day[col].reindex(df.index).values
        for col in TECH_COLS:
            if col not in df.columns:
                df[col] = np.nan

        # sector-relative z for the technicals that the scorer ranks on
        for col in ["momentum_12_1", "return_3m", "return_6m", "px_to_sma200",
                    "rel_strength_6m", "volatility_252d", "drawdown_1y",
                    "turnover_pkr_m", "rsi_14"]:
            z = _winsorized_z(df[col])
            if col in {"volatility_252d"}:
                z = -z
            df[f"z_{col}"] = z.clip(-3, 3)

        # --- macro context ------------------------------------------------
        if self.macro is not None and len(self.macro):
            m = self.macro[self.macro.index <= asof]
            if len(m):
                last = m.iloc[-1]
                for k in ["policy_rate", "cpi_yoy", "usd_pkr", "cycle"]:
                    if k in last:
                        df[f"macro_{k}"] = float(last[k])

        df["prev_available"] = df.index.isin(prev.index if len(prev) else [])
        df = df.reset_index().rename(columns={"index": "ticker"})
        if "ticker" not in df.columns:
            df = df.rename(columns={df.columns[0]: "ticker"})
        df["name"] = df["ticker"].map(lambda t: BY_TICKER[t].name if t in BY_TICKER else t)
        df["is_financial"] = df["sector"].isin(FINANCIAL_SECTORS)
        self._last_prev = prev
        return df

    def prev_row(self, ticker: str) -> pd.Series | None:
        prev = getattr(self, "_last_prev", None)
        if prev is None or ticker not in prev.index:
            return None
        return prev.loc[ticker]

    def forward_return(self, asof, horizon_days: int) -> pd.Series:
        """Realised return over the next `horizon_days` trading days. Used only
        to build training labels and to evaluate the backtest."""
        day = self.last_trading_day(asof)
        if day is None:
            return pd.Series(dtype=float)
        i = self.trading_days.get_loc(day)
        j = min(i + horizon_days, len(self.trading_days) - 1)
        if j <= i:
            return pd.Series(dtype=float)
        return (self.close.iloc[j] / self.close.iloc[i] - 1.0).rename("fwd_return")


# Columns handed to the machine-learning ranker. Deliberately all
# cross-sectional z-scores or bounded ratios, so the model sees relative
# standing rather than a level that drifts with inflation.
ML_FEATURES: List[str] = (
    [f"z_{c}" for c in RATIO_COLS]
    + [f"z_{c}" for c in MARKET_COLS if c != "market_cap"]
    + ["z_size", "z_momentum_12_1", "z_return_3m", "z_return_6m",
       "z_px_to_sma200", "z_rel_strength_6m", "z_volatility_252d",
       "z_drawdown_1y", "z_turnover_pkr_m", "z_rsi_14",
       "rsi_14", "golden_cross", "beta_1y", "volume_surge",
       "macro_policy_rate", "macro_cycle"]
)
