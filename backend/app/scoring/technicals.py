"""Price and volume features.

Everything here is computed from data strictly on or before the as-of date, so
a feature can never see a price the model would not have had. The panel is
built once per run and indexed by (date, ticker) for fast point-in-time lookup.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def build_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """Wide close/volume matrices plus every rolling technical, returned long."""
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"])
    close = df.pivot(index="date", columns="ticker", values="close").sort_index()
    volume = df.pivot(index="date", columns="ticker", values="volume").sort_index()
    high = df.pivot(index="date", columns="ticker", values="high").sort_index()
    low = df.pivot(index="date", columns="ticker", values="low").sort_index()

    ret1 = close.pct_change()
    logret = np.log(close).diff()

    feats: Dict[str, pd.DataFrame] = {}
    feats["close"] = close
    feats["return_1m"] = close.pct_change(21)
    feats["return_3m"] = close.pct_change(63)
    feats["return_6m"] = close.pct_change(126)
    feats["return_12m"] = close.pct_change(252)
    # 12-1 momentum: the standard academic definition skips the most recent
    # month to avoid the short-term reversal effect.
    feats["momentum_12_1"] = (close.shift(21) / close.shift(252)) - 1.0
    feats["volatility_60d"] = logret.rolling(60).std() * np.sqrt(TRADING_DAYS)
    feats["volatility_252d"] = logret.rolling(252).std() * np.sqrt(TRADING_DAYS)

    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    feats["px_to_sma50"] = close / sma50 - 1.0
    feats["px_to_sma200"] = close / sma200 - 1.0
    feats["golden_cross"] = (sma50 > sma200).astype(float)

    high52 = close.rolling(252, min_periods=60).max()
    low52 = close.rolling(252, min_periods=60).min()
    feats["pct_off_52w_high"] = close / high52 - 1.0
    feats["pct_above_52w_low"] = close / low52 - 1.0

    # Wilder's RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    feats["rsi_14"] = (100 - 100 / (1 + rs)).fillna(50.0)

    # Rolling maximum drawdown over one year
    roll_max = close.rolling(252, min_periods=60).max()
    feats["drawdown_1y"] = close / roll_max - 1.0

    # Liquidity: median daily traded value, in PKR millions
    feats["turnover_pkr_m"] = (close * volume / 1e6).rolling(60).median()
    feats["volume_surge"] = volume.rolling(20).mean() / volume.rolling(120).mean()

    # Average true range as a percentage of price
    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()]).groupby(level=0).max()
    feats["atr_pct"] = (tr.rolling(14).mean() / close)

    long = None
    for name, mat in feats.items():
        s = mat.stack(future_stack=True).rename(name)
        long = s.to_frame() if long is None else long.join(s, how="outer")
    long.index.names = ["date", "ticker"]
    return long.reset_index()


def add_beta(panel: pd.DataFrame, prices: pd.DataFrame, index_df: pd.DataFrame,
             window: int = 252) -> pd.DataFrame:
    """Rolling beta and annualised alpha against the KSE-100."""
    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"])
    close = px.pivot(index="date", columns="ticker", values="close").sort_index()
    idx = index_df.copy()
    idx["date"] = pd.to_datetime(idx["date"])
    bench = idx.set_index("date")["close"].reindex(close.index).ffill()

    r = np.log(close).diff()
    rb = np.log(bench).diff()
    cov = r.rolling(window).cov(rb)
    var = rb.rolling(window).var()
    beta = cov.div(var, axis=0)
    alpha = (r.rolling(window).mean() - beta.mul(rb.rolling(window).mean(), axis=0)) * TRADING_DAYS
    rel = (close.div(bench, axis=0))
    rel_strength = rel / rel.shift(126) - 1.0

    out = panel.set_index(["date", "ticker"])
    for name, mat in (("beta_1y", beta), ("alpha_1y", alpha),
                      ("rel_strength_6m", rel_strength)):
        out = out.join(mat.stack(future_stack=True).rename(name), how="left")
    return out.reset_index()


TECH_COLS = [
    "return_1m", "return_3m", "return_6m", "return_12m", "momentum_12_1",
    "volatility_60d", "volatility_252d", "px_to_sma50", "px_to_sma200",
    "golden_cross", "pct_off_52w_high", "pct_above_52w_low", "rsi_14",
    "drawdown_1y", "turnover_pkr_m", "volume_surge", "atr_pct",
    "beta_1y", "alpha_1y", "rel_strength_6m",
]


def run(prices: pd.DataFrame, index_df: pd.DataFrame) -> pd.DataFrame:
    return add_beta(build_panel(prices), prices, index_df)
