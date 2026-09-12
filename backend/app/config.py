"""Central configuration.

Every tunable the pipeline uses lives here so the backtest, the scorer and the
API can never drift apart. Override any value with an environment variable of
the same name (PSX_ prefix), e.g. PSX_DATABASE_URL=postgresql+psycopg://...
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = DATA_DIR / "exports"
RAW_DIR = DATA_DIR / "raw"
MODEL_DIR = DATA_DIR / "models"
for _d in (DATA_DIR, EXPORT_DIR, RAW_DIR, MODEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _env(key: str, default):
    raw = os.getenv(f"PSX_{key}")
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


@dataclass
class Settings:
    # --- storage ---------------------------------------------------------
    database_url: str = _env("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'psx.db').as_posix()}")

    # --- history window --------------------------------------------------
    history_start: date = date(2014, 1, 1)
    history_end: date = date(2025, 12, 31)

    # --- point-in-time discipline ---------------------------------------
    # PSX-listed companies must file annual accounts within 120 days and
    # quarterlies within 30 days of period end. We use the conservative end of
    # that window as the date a filing becomes usable by the model.
    annual_report_lag_days: int = 120
    quarter_report_lag_days: int = 45

    # --- portfolio construction -----------------------------------------
    top_n: int = 15                   # names held by the recommended portfolio
    rebalance_freq: str = "Q"         # Q = quarterly rebalance
    max_sector_weight: float = 0.30   # sector cap inside the portfolio
    transaction_cost_bps: float = 35.0   # PSX round-trip commission + FED + CVT
    slippage_bps: float = 15.0
    risk_free_rate: float = 0.145     # avg SBP policy-linked T-bill yield

    # --- rule-based composite weights (must sum to 1.0) ------------------
    composite_weights: dict = field(default_factory=lambda: {
        "quality": 0.30,    # Piotroski F-Score + ROE/ROA
        "value": 0.25,      # P/E, P/B, EV/EBITDA, dividend yield
        "safety": 0.20,     # Altman Z + leverage + interest cover
        "growth": 0.15,     # revenue / earnings growth
        "momentum": 0.10,   # 12-1 price momentum + trend
    })

    # --- ML ranker -------------------------------------------------------
    ml_label_horizon_days: int = 63   # one quarter forward return
    ml_min_train_periods: int = 8     # walk-forward warm-up
    ml_seed: int = 42
    blend_ml_weight: float = 0.35     # final = 0.65*rule + 0.35*ml

    # --- recommendation bands (percentile of composite) ------------------
    band_strong_buy: float = 0.90
    band_buy: float = 0.70
    band_hold: float = 0.35
    band_reduce: float = 0.15

    # --- simulation ------------------------------------------------------
    sim_seed: int = 20250911

    def band_for(self, pct: float) -> str:
        if pct >= self.band_strong_buy:
            return "STRONG BUY"
        if pct >= self.band_buy:
            return "BUY"
        if pct >= self.band_hold:
            return "HOLD"
        if pct >= self.band_reduce:
            return "REDUCE"
        return "AVOID"


settings = Settings()
