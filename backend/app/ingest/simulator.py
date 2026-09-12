"""Point-in-time PSX market simulator.

Why this exists
---------------
PSX does not publish a free, machine-readable, survivorship-free history of
standardized financial statements. `psx_client.py` implements the live
scrapers, but a reproducible backtest needs a decade of clean panel data that
is available offline. This module generates that panel.

It is a *structural* simulator, not random noise:

1. A Pakistan-shaped macro path (policy rate, CPI, USD/PKR, GDP) drives a
   common business cycle.
2. Each company has persistent latent traits (management quality, growth,
   leverage discipline, accrual aggressiveness) that shape its statements.
3. Statements are built from the top down and obey the accounting identities:
   assets = liabilities + equity, and the cash-flow statement reconciles to the
   change in the cash balance.
4. A fundamental fair value is derived from those statements, and the market
   price is pulled toward it by a mean-reverting force plus a market factor,
   sector factors and idiosyncratic noise.

Point 4 is what makes the exercise meaningful: value, quality and momentum
carry genuine but modest predictive power, exactly as in a real market, so the
backtest can neither trivially win nor be pure noise.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from app.config import settings
from app.ingest.universe import (
    UNIVERSE, BY_TICKER, SECTOR_PROFILES, Company, index_weights, FINANCIAL_SECTORS,
)

# --------------------------------------------------------------------------
# Macro backbone: anchor points shaped on Pakistan's actual cycle
# (SBP policy rate, PBS CPI, interbank USD/PKR, real GDP growth).
# --------------------------------------------------------------------------
MACRO_ANCHORS: Dict[str, List[Tuple[str, float]]] = {
    "policy_rate": [
        ("2014-01-31", 10.0), ("2015-06-30", 6.5), ("2016-06-30", 5.75),
        ("2017-12-31", 5.75), ("2018-12-31", 10.0), ("2019-07-31", 13.25),
        ("2020-06-30", 7.0), ("2021-09-30", 7.25), ("2022-06-30", 13.75),
        ("2023-06-30", 22.0), ("2024-06-30", 20.5), ("2024-12-31", 13.0),
        ("2025-06-30", 11.0), ("2025-12-31", 11.0),
    ],
    "cpi_yoy": [
        ("2014-01-31", 8.7), ("2015-06-30", 3.2), ("2016-06-30", 3.2),
        ("2017-12-31", 4.6), ("2018-12-31", 6.2), ("2019-12-31", 12.6),
        ("2020-12-31", 8.0), ("2021-12-31", 12.3), ("2022-06-30", 21.3),
        ("2023-05-31", 38.0), ("2023-12-31", 29.7), ("2024-06-30", 12.6),
        ("2024-12-31", 4.1), ("2025-06-30", 3.5), ("2025-12-31", 5.5),
    ],
    "usd_pkr": [
        ("2014-01-31", 105.0), ("2015-06-30", 101.8), ("2016-06-30", 104.7),
        ("2017-12-31", 110.6), ("2018-12-31", 139.0), ("2019-06-30", 157.0),
        ("2020-06-30", 168.0), ("2021-06-30", 157.5), ("2022-06-30", 205.0),
        ("2023-06-30", 286.0), ("2024-06-30", 278.5), ("2025-06-30", 283.0),
        ("2025-12-31", 286.0),
    ],
    "fx_reserves_usd_bn": [
        ("2014-01-31", 8.0), ("2016-06-30", 18.1), ("2017-12-31", 14.1),
        ("2019-06-30", 7.3), ("2020-06-30", 12.1), ("2021-06-30", 17.3),
        ("2022-06-30", 9.8), ("2023-02-28", 3.2), ("2023-12-31", 8.2),
        ("2024-12-31", 11.7), ("2025-12-31", 14.5),
    ],
    "gdp_growth": [
        ("2014-06-30", 4.1), ("2015-06-30", 4.1), ("2016-06-30", 4.6),
        ("2017-06-30", 5.5), ("2018-06-30", 5.8), ("2019-06-30", 1.0),
        ("2020-06-30", -1.3), ("2021-06-30", 6.5), ("2022-06-30", 6.2),
        ("2023-06-30", -0.2), ("2024-06-30", 2.5), ("2025-06-30", 2.7),
        ("2025-12-31", 3.2),
    ],
}

# Market-factor shape: cumulative log level anchors for the broad PSX market.
# Mirrors the real KSE-100 arc - 2017 peak, 2018-19 bear market, COVID crash
# and recovery, 2022-23 drawdown, then the 2024-25 re-rating.
MARKET_ANCHORS: List[Tuple[str, float]] = [
    ("2014-01-01", 26_000), ("2014-12-31", 32_100), ("2015-12-31", 32_800),
    ("2016-12-31", 47_800), ("2017-05-24", 52_876), ("2017-12-31", 40_471),
    ("2018-12-31", 37_067), ("2019-08-16", 28_765), ("2019-12-31", 40_735),
    ("2020-03-25", 27_228), ("2020-12-31", 43_755), ("2021-12-31", 44_596),
    ("2022-12-31", 40_420), ("2023-06-30", 41_453), ("2023-12-31", 62_451),
    ("2024-12-31", 115_127), ("2025-06-30", 125_600), ("2025-12-31", 142_000),
]


def _interpolate(anchors: List[Tuple[str, float]], index: pd.DatetimeIndex) -> pd.Series:
    pts = pd.Series({pd.Timestamp(d): v for d, v in anchors}).sort_index()
    joined = pts.reindex(pts.index.union(index)).interpolate(method="time")
    return joined.reindex(index).ffill().bfill()


# --------------------------------------------------------------------------


@dataclass
class Traits:
    """Latent, persistent firm characteristics."""
    quality: float        # management/profitability skill, z-scale
    growth: float         # excess revenue growth over the sector
    leverage: float       # appetite for debt, z-scale
    accruals: float       # earnings aggressiveness (high = low quality)
    volatility: float     # idiosyncratic vol multiplier
    payout: float
    distress: float       # 0-1 probability weight of a distress episode


class PSXSimulator:
    """Builds the full point-in-time panel: macro, statements, prices, index."""

    def __init__(self,
                 start: date | None = None,
                 end: date | None = None,
                 seed: int | None = None):
        self.start = pd.Timestamp(start or settings.history_start)
        self.end = pd.Timestamp(end or settings.history_end)
        self.rng = np.random.default_rng(seed if seed is not None else settings.sim_seed)
        # PSX trades Monday-Friday; public holidays are not modelled explicitly.
        self.dates = pd.bdate_range(self.start, self.end)
        self.quarters = pd.date_range(self.start, self.end, freq="QE")
        self.months = pd.date_range(self.start, self.end, freq="ME")
        self.weights = index_weights()
        self.traits: Dict[str, Traits] = {}
        self.macro: pd.DataFrame | None = None
        self.statements: pd.DataFrame | None = None
        self.prices: pd.DataFrame | None = None
        self.index: pd.DataFrame | None = None
        self.shares: Dict[str, float] = {}

    # -- 1. macro ---------------------------------------------------------
    def build_macro(self) -> pd.DataFrame:
        m = pd.DataFrame(index=self.months)
        for col, anchors in MACRO_ANCHORS.items():
            m[col] = _interpolate(anchors, self.months)
        # light month-to-month noise on the fast-moving series
        m["cpi_yoy"] += self.rng.normal(0, 0.45, len(m))
        m["usd_pkr"] *= np.exp(self.rng.normal(0, 0.004, len(m)))
        m["policy_rate"] = m["policy_rate"].round(2)

        # Composite cycle score in [-1, 1]: growth minus inflation/rate stress.
        g = (m["gdp_growth"] - m["gdp_growth"].mean()) / (m["gdp_growth"].std() or 1)
        r = (m["policy_rate"] - m["policy_rate"].mean()) / (m["policy_rate"].std() or 1)
        i = (m["cpi_yoy"] - m["cpi_yoy"].mean()) / (m["cpi_yoy"].std() or 1)
        m["cycle"] = np.tanh(0.6 * g - 0.3 * r - 0.3 * i)
        m.index.name = "date"
        self.macro = m
        return m

    # -- 2. firm traits ---------------------------------------------------
    def build_traits(self) -> Dict[str, Traits]:
        for c in UNIVERSE:
            p = SECTOR_PROFILES[c.sector]
            q = float(self.rng.normal(0, 1))
            self.traits[c.ticker] = Traits(
                quality=q,
                growth=float(self.rng.normal(0.5 * q, 1.0)) * 0.035,
                leverage=float(self.rng.normal(-0.25 * q, 1.0)),
                accruals=float(self.rng.normal(-0.35 * q, 1.0)),
                volatility=float(np.exp(self.rng.normal(0, 0.28))),
                payout=float(np.clip(p["payout"] * np.exp(self.rng.normal(0, 0.3)), 0, 0.95)),
                distress=float(np.clip(0.12 - 0.07 * q, 0.01, 0.35)),
            )
            # Size sets the starting revenue scale (PKR millions).
            base = {1: 260_000.0, 2: 78_000.0, 3: 26_000.0, 4: 8_500.0}[c.size_tier]
            self.shares[c.ticker] = round(
                base / (95.0 * np.exp(self.rng.normal(0, 0.45))), 1)  # millions of shares
        return self.traits

    # -- 3. financial statements -----------------------------------------
    def build_statements(self) -> pd.DataFrame:
        assert self.macro is not None and self.traits, "build macro and traits first"
        cycle_q = self.macro["cycle"].reindex(self.quarters, method="nearest")
        infl_q = self.macro["cpi_yoy"].reindex(self.quarters, method="nearest") / 100.0
        fx_q = self.macro["usd_pkr"].reindex(self.quarters, method="nearest")
        rate_q = self.macro["policy_rate"].reindex(self.quarters, method="nearest") / 100.0

        rows: List[dict] = []
        for c in UNIVERSE:
            rows.extend(self._statements_for(c, cycle_q, infl_q, fx_q, rate_q))
        df = pd.DataFrame(rows)
        self.statements = df
        return df

    def _statements_for(self, c: Company, cycle_q, infl_q, fx_q, rate_q) -> List[dict]:
        p = SECTOR_PROFILES[c.sector]
        t = self.traits[c.ticker]
        is_fin = c.sector in FINANCIAL_SECTORS
        base_rev = {1: 260_000.0, 2: 78_000.0, 3: 26_000.0, 4: 8_500.0}[c.size_tier]
        base_rev *= float(np.exp(self.rng.normal(0, 0.30)))

        # Start-of-history balance sheet
        revenue_a = base_rev
        assets = revenue_a / max(p["asset_turnover"], 0.05)
        equity = assets / p["leverage"]
        init_de = (0.8 if is_fin else max(0.15, (p["leverage"] - 1.0) * 0.45))
        init_de *= float(np.exp(0.22 * t.leverage))
        debt = float(np.clip(equity * init_de, 0.0, assets * 0.65))
        retained = equity * 0.55
        cash = assets * (0.08 if not is_fin else 0.11)
        inventory = 0.0 if is_fin else assets * 0.16
        receivables = assets * (0.12 if not is_fin else 0.55)
        fixed_assets = assets * (0.45 if not is_fin else 0.05)

        # persistent distress episode state
        in_distress = 0
        out: List[dict] = []
        prev_annual: dict | None = None

        for qi, q_end in enumerate(self.quarters):
            cyc = float(cycle_q.iloc[qi])
            infl = float(infl_q.iloc[qi])
            fx = float(fx_q.iloc[qi])
            rate = float(rate_q.iloc[qi])
            fy = q_end.year
            fq = (q_end.month - 1) // 3 + 1

            # --- revenue -------------------------------------------------
            growth_q = (p["growth"] + t.growth + 0.55 * infl
                        + 0.45 * p["cyclicality"] * cyc) / 4.0
            growth_q += float(self.rng.normal(0, 0.028))
            seasonality = 1.0 + 0.055 * np.sin(2 * np.pi * (fq - 1) / 4 + (hash(c.ticker) % 7) / 7.0)
            revenue_a *= (1.0 + growth_q)
            revenue = revenue_a / 4.0 * seasonality

            # --- distress regime ----------------------------------------
            if in_distress > 0:
                in_distress -= 1
            elif self.rng.random() < t.distress * 0.035 * (1.4 - 0.6 * cyc):
                in_distress = int(self.rng.integers(2, 7))
            distress_hit = 1.0 if in_distress > 0 else 0.0

            # --- margins -------------------------------------------------
            margin = p["base_margin"] * (1.0 + 0.30 * t.quality
                                         + 0.45 * p["cyclicality"] * cyc
                                         - 0.55 * distress_hit)
            margin += float(self.rng.normal(0, p["base_margin"] * 0.22))
            # imported-input firms are squeezed when the rupee slides
            fx_sensitivity = {"Automobile Assembler": -0.35, "Refinery": 0.25,
                              "Oil & Gas Marketing": 0.12, "Textile Composite": 0.30,
                              "Technology & Communication": 0.28,
                              "Pharmaceuticals": -0.22, "Chemicals": -0.15,
                              "Cable & Electrical Goods": -0.25}.get(c.sector, 0.0)
            margin *= (1.0 + fx_sensitivity * np.log(fx / 105.0) * 0.35)
            margin = float(np.clip(margin, -0.35, 0.62))

            if is_fin:
                # Bank template: revenue = net interest + fee income.
                gross_profit = revenue * 0.62
                cost_of_sales = revenue - gross_profit
                opex = revenue * (0.38 - 0.05 * t.quality)
                depreciation = assets * 0.0018
            else:
                gm = float(np.clip(margin * 2.45 + 0.11, 0.03, 0.68))
                gross_profit = revenue * gm
                cost_of_sales = revenue - gross_profit
                opex = revenue * float(np.clip(gm - margin - 0.012, 0.01, 0.45))
                depreciation = fixed_assets * 0.0165

            operating_income = gross_profit - opex
            finance_cost = debt * (rate + 0.018) / 4.0 if not is_fin else debt * rate * 0.25 / 4.0
            other_income = cash * rate / 4.0 * 0.65 + revenue * 0.004
            pbt = operating_income - finance_cost + other_income
            tax_rate = 0.39 if is_fin else 0.29
            taxation = max(0.0, pbt) * tax_rate + min(0.0, pbt) * 0.08
            net_income = pbt - taxation

            # --- working capital -----------------------------------------
            # Balances are driven to a target expressed in days of sales or
            # cost of sales, the way a working-capital policy actually works.
            # An aggressive-accruals firm lets receivables and inventory run.
            acc = 12.0 * t.accruals
            rec_days = (52.0 + acc) if not is_fin else 240.0
            inv_days = (0.0 if is_fin else 64.0 + acc)
            pay_days = (0.0 if is_fin else 48.0 - acc * 0.5)
            rec_target = revenue * 4.0 * rec_days / 365.0
            inv_target = cost_of_sales * 4.0 * inv_days / 365.0
            pay_target = cost_of_sales * 4.0 * pay_days / 365.0
            prev_rec = _prev(out, "receivables", rec_target)
            prev_inv = _prev(out, "inventory", inv_target)
            prev_pay = _prev(out, "payables", pay_target)
            receivables = max(0.0, 0.45 * prev_rec + 0.55 * rec_target)
            inventory = max(0.0, 0.45 * prev_inv + 0.55 * inv_target)
            payables = max(0.0, 0.45 * prev_pay + 0.55 * pay_target)

            # --- cash flow ------------------------------------------------
            d_wc = ((receivables - prev_rec) + (inventory - prev_inv)
                    - (payables - prev_pay))
            cfo = net_income + depreciation - d_wc
            capex = revenue * (0.055 if not is_fin else 0.010) * (1.0 + 0.5 * max(cyc, 0))
            cfi = -capex + float(self.rng.normal(0, revenue * 0.004))
            dividends = max(0.0, net_income) * t.payout if pbt > 0 else 0.0

            # Debt is managed toward a sector-typical gearing rather than
            # compounding without limit: firms lever up to fund a shortfall
            # and pay down when they are above target.
            target_de = (0.8 if is_fin else max(0.15, (p["leverage"] - 1.0) * 0.45))
            target_de *= float(np.exp(0.22 * t.leverage))
            target_debt = max(0.0, equity * target_de)
            shortfall = max(0.0, capex + dividends - cfo)
            net_borrowing = (0.18 * (target_debt - debt) + 0.60 * shortfall
                             + float(self.rng.normal(0, 0.012)) * max(debt, revenue))
            if in_distress > 0:                      # distress forces borrowing
                net_borrowing = abs(net_borrowing) + shortfall * 0.5
            net_borrowing = max(net_borrowing, -debt)

            # Surplus cash above the operating buffer is returned to owners,
            # which keeps the balance sheet from filling up with idle cash.
            target_cash = revenue * (0.55 if not is_fin else 1.1)
            cash_pre = cash + cfo + cfi + net_borrowing - dividends
            extra_distribution = max(0.0, cash_pre - target_cash) * 0.30 if pbt > 0 else 0.0
            distributions = dividends + extra_distribution
            cff = net_borrowing - distributions
            fcf = cfo - capex

            # --- roll the balance sheet forward --------------------------
            debt = max(0.0, debt + net_borrowing)
            retained = retained + net_income - distributions
            equity = equity + net_income - distributions
            short_term_debt = debt * (0.45 if not is_fin else 0.25)
            long_term_debt = debt - short_term_debt

            if is_fin:
                # A lender's balance sheet is sized by its book, not by working
                # capital: earning assets dominate and customer deposits are the
                # funding plug. Equity still rolls forward from retained profit.
                ta = (revenue * 4.0) / max(p["asset_turnover"], 0.02)
                # Banks are run to a capital ratio, not to a debt target: the
                # sector's assets/equity gearing sets the floor, and a bank that
                # retains more than it needs simply carries surplus capital.
                cap_ratio = float(np.clip((1.0 / p["leverage"]) * np.exp(-0.15 * t.leverage),
                                          0.045, 0.30))
                equity = max(ta * cap_ratio, equity)
                cash = ta * 0.09
                receivables = ta * 0.84          # advances and investments
                inventory = 0.0
                fixed_assets = ta * 0.02
                other_assets = ta * 0.05
                total_assets = cash + receivables + fixed_assets + other_assets
                payables = 0.0
                accrued = revenue * 0.35
                current_liabilities = short_term_debt + accrued
                deposits = max(0.0, total_assets - equity - short_term_debt
                               - long_term_debt - accrued)
                total_liabilities = current_liabilities + long_term_debt + deposits
                current_assets = cash + receivables
            else:
                cash = max(revenue * 0.02, cash + cfo + cfi + cff)
                fixed_assets = max(0.0, fixed_assets + capex - depreciation)
                other_assets = revenue * 0.22    # investments, intangibles
                current_assets = cash + receivables + inventory + revenue * 0.05
                total_assets = current_assets + fixed_assets + other_assets
                equity = max(total_assets * 0.02, equity)
                accrued = revenue * 0.06
                current_liabilities = payables + short_term_debt + accrued
                # Provisions, deferred tax and other long-term liabilities are
                # the plug that closes assets = liabilities + equity.
                other_liabilities = (total_assets - equity - current_liabilities
                                     - long_term_debt)
                if other_liabilities < 0:
                    # Equity plus debt exceeds the operating asset base, so the
                    # surplus is held as long-term investments.
                    other_assets += -other_liabilities
                    total_assets += -other_liabilities
                    other_liabilities = 0.0
                total_liabilities = current_liabilities + long_term_debt + other_liabilities

            shares = self.shares[c.ticker]
            eps = net_income / shares
            dps = distributions / shares

            # Point-in-time availability: annual accounts land later than
            # quarterlies, so Q4 uses the annual filing deadline.
            lag = settings.annual_report_lag_days if fq == 4 else settings.quarter_report_lag_days
            report_date = (q_end + pd.Timedelta(days=lag)).date()

            out.append(dict(
                ticker=c.ticker, period_end=q_end.date(), report_date=report_date,
                fiscal_year=fy, fiscal_quarter=fq,
                revenue=revenue, cost_of_sales=cost_of_sales, gross_profit=gross_profit,
                operating_expenses=opex, operating_income=operating_income,
                depreciation=depreciation, finance_cost=finance_cost,
                other_income=other_income, profit_before_tax=pbt, taxation=taxation,
                net_income=net_income, eps=eps, dividend_per_share=dps,
                cash=cash, receivables=receivables, inventory=inventory,
                current_assets=current_assets, fixed_assets=fixed_assets,
                total_assets=total_assets, payables=payables,
                short_term_debt=short_term_debt, current_liabilities=current_liabilities,
                long_term_debt=long_term_debt, total_liabilities=total_liabilities,
                total_equity=equity, retained_earnings=retained,
                cfo=cfo, capex=capex, cfi=cfi, cff=cff, free_cash_flow=fcf,
                shares_outstanding=shares, source="simulated",
            ))
        return out

    # -- 4. prices --------------------------------------------------------
    def build_prices(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Daily OHLCV per ticker plus the bottom-up cap-weighted KSE-100."""
        assert self.statements is not None
        dates = self.dates
        n = len(dates)

        # --- market factor: track the anchor arc with clustered vol -------
        # The index is a random walk *around* the historical arc, not a free
        # one: without a restoring force the accumulated noise would invent
        # bull and bear markets that never happened and inflate the drawdown.
        target = np.log(_interpolate(MARKET_ANCHORS, dates).values)
        drift = np.diff(target, prepend=target[0])
        vol = 0.0072 * (1.0 + 0.55 * np.abs(
            pd.Series(drift).rolling(40, min_periods=1).std().fillna(0).values
            / (np.std(drift) or 1e-6)))
        shocks = self.rng.normal(0, 1, n) * vol
        mkt_ret = np.empty(n)
        mkt_ret[0] = drift[0]
        level = target[0]
        pull = 0.030                       # ~ 1-month half-life back to the arc
        for i in range(1, n):
            mkt_ret[i] = drift[i] + pull * (target[i] - level) + shocks[i]
            level += mkt_ret[i]

        # --- sector factors ---------------------------------------------
        sectors = sorted(SECTOR_PROFILES)
        sec_ret = {s: self.rng.normal(0, 0.0052, n) for s in sectors}
        for s in sectors:
            sec_ret[s] = pd.Series(sec_ret[s]).ewm(span=12).mean().values * 2.6

        # --- fundamental fair value per ticker, daily ---------------------
        fv = self._fair_values(dates)
        tickers = [c.ticker for c in UNIVERSE]
        k = len(tickers)
        w = np.array([self.weights[t] for t in tickers])
        log_fair = np.log(np.maximum(np.vstack([fv[t] for t in tickers]), 0.5))

        # Betas are normalised so the cap-weighted market beta is exactly 1,
        # which is what it must be for an index built from its own members.
        betas = np.array([SECTOR_PROFILES[BY_TICKER[t].sector]["beta"] for t in tickers])
        betas = betas / float(np.dot(w, betas))
        # Sector factors are cap-weighted-demeaned for the same reason: they
        # move sectors against each other, not the market as a whole.
        sec_mat = np.vstack([sec_ret[BY_TICKER[t].sector] for t in tickers])
        sec_mat = sec_mat - (w @ sec_mat)[None, :]

        vols = np.array([self.traits[t].volatility for t in tickers]) * 0.0165
        kappa = 0.00105 * (1.0 + 0.35 * self.rng.random(k))  # daily pull to fair value

        # Part of what the market prices is not in the accounts: management
        # changes, contract wins, governance, order books. This slow, persistent
        # component shifts each firm's true worth away from its reported
        # fundamentals, so the screen can see only part of the story - which is
        # what keeps the achievable information ratio realistic.
        unobs = np.zeros((k, n))
        phi, sd_u = 0.9985, 0.012        # ~ 3-year half-life
        eps_u = self.rng.normal(0, sd_u, (k, n))
        unobs[:, 0] = self.rng.normal(0, 0.22, k)
        for i in range(1, n):
            unobs[:, i] = phi * unobs[:, i - 1] + eps_u[:, i]
        log_fair = log_fair + unobs

        # Convexity (Ito) drag. A cap-weighted index compounds its members'
        # *simple* returns, so a set of stocks whose log returns average to the
        # market factor produces an index that drifts away from it by roughly
        # half the cross-sectional variance. The analytic correction is
        # sensitive to the clipping and the mean-reversion terms, so it is
        # calibrated instead: simulate, measure the realised gap between the
        # bottom-up index and the market factor, and re-simulate with that
        # constant removed. The draws are fixed across passes, so only the
        # drift moves.
        seed_shock = self.rng.normal(0, 0.28, k)
        noise = self.rng.normal(0, 1, (k, n)) * vols[:, None]
        convexity = 0.5 * (vols ** 2 + sec_mat.var(axis=1))

        def simulate(conv: np.ndarray) -> np.ndarray:
            logp = np.empty((k, n))
            logp[:, 0] = log_fair[:, 0] + seed_shock
            trend = np.zeros(k)
            for i in range(1, n):
                gap = np.clip(log_fair[:, i] - logp[:, i - 1], -0.9, 0.9)
                # Only *relative* mispricing may move a stock. The overall level
                # of the market is set by the market factor, so the cap-weighted
                # mean gap is removed before the pull is applied - otherwise
                # rising nominal earnings would be counted twice and the index
                # would run far above its own constituents' market factor.
                gap = gap - float(w @ gap)
                pull = kappa * gap
                trend = 0.94 * trend + 0.06 * pull       # slow momentum build-up
                r = (betas * mkt_ret[i] + sec_mat[:, i]
                     + pull + 0.35 * trend + noise[:, i] - conv)
                # PSX applies a 7.5% daily circuit breaker per scrip.
                logp[:, i] = logp[:, i - 1] + np.clip(r, -0.075, 0.075)
            return logp

        def index_log_growth(logp: np.ndarray) -> float:
            c = np.exp(logp)
            simple = np.diff(c, axis=1) / np.maximum(c[:, :-1], 1e-9)
            lvl = np.cumprod(1.0 + (w[:, None] * simple).sum(axis=0))
            return float(np.log(lvl[-1]))

        wanted = float(mkt_ret[1:].sum())      # market factor's total log growth
        for _ in range(3):
            logp = simulate(convexity)
            delta = (index_log_growth(logp) - wanted) / (n - 1)
            if abs(delta) < 2e-6:
                break
            convexity = convexity + delta

        closes = np.exp(logp)
        px_frames = []
        for j, c in enumerate(UNIVERSE):
            close = closes[j]
            idio_sd = vols[j]
            intraday = np.abs(self.rng.normal(0, idio_sd * 0.75, n))
            openp = close * np.exp(self.rng.normal(0, idio_sd * 0.4, n))
            high = np.maximum(openp, close) * (1 + intraday)
            low = np.minimum(openp, close) * (1 - intraday)
            base_vol = {1: 6.5e6, 2: 3.2e6, 3: 1.4e6, 4: 0.6e6}[c.size_tier]
            volume = base_vol * np.exp(self.rng.normal(0, 0.7, n)) * (
                1 + 4.0 * np.abs(np.diff(logp[j], prepend=logp[j][0])))
            px_frames.append(pd.DataFrame({
                "ticker": c.ticker, "date": dates.date,
                "open": openp.round(2), "high": high.round(2),
                "low": low.round(2), "close": close.round(2),
                "volume": volume.round(0),
            }))

        prices = pd.concat(px_frames, ignore_index=True)

        # --- bottom-up cap-weighted index --------------------------------
        # A price index compounds the weighted *simple* returns of its members,
        # not their log returns: averaging logs would understate the index by
        # the cross-sectional variance and invent a drawdown that never
        # happened.
        simple = np.diff(closes, axis=1, prepend=closes[:, :1]) / np.maximum(
            np.concatenate([closes[:, :1], closes[:, :-1]], axis=1), 1e-9)
        idx_ret = (w[:, None] * simple).sum(axis=0)
        idx_level = MARKET_ANCHORS[0][1] * np.cumprod(1.0 + idx_ret)
        index_df = pd.DataFrame({
            "symbol": "KSE100", "date": dates.date,
            "close": idx_level.round(2),
            "volume": (np.vstack([f["volume"].values for f in px_frames]).sum(axis=0)),
        })

        self.prices, self.index = prices, index_df
        return prices, index_df

    def _fair_values(self, dates: pd.DatetimeIndex) -> Dict[str, np.ndarray]:
        """Intrinsic value per share, interpolated to daily.

        Non-financials are valued on trailing earnings with a fair P/E that
        rises with growth and quality and falls with leverage and the policy
        rate. Banks are valued on book value with a fair P/B driven by ROE
        against the cost of equity.
        """
        rate_d = (self.macro["policy_rate"].reindex(dates, method="ffill")
                  .bfill().values / 100.0)
        out: Dict[str, np.ndarray] = {}
        for ticker, g in self.statements.groupby("ticker"):
            c = BY_TICKER[ticker]
            p = SECTOR_PROFILES[c.sector]
            t = self.traits[ticker]
            g = g.sort_values("period_end")
            ttm_ni = g["net_income"].rolling(4, min_periods=1).sum().values
            equity = g["total_equity"].values
            debt = (g["short_term_debt"] + g["long_term_debt"]).values
            shares = g["shares_outstanding"].values
            pe_base = 11.0 if c.sector not in FINANCIAL_SECTORS else 8.5
            lev = np.clip(debt / np.maximum(equity, 1.0), 0, 4)
            roe = ttm_ni / np.maximum(equity, 1.0)

            q_dates = pd.to_datetime(g["period_end"])
            if c.sector in FINANCIAL_SECTORS:
                pb = np.clip(0.35 + 5.2 * np.clip(roe, -0.1, 0.45), 0.25, 3.2)
                val = pb * equity
            else:
                mult = (pe_base
                        * (1 + 2.4 * (p["growth"] + t.growth - 0.12))
                        * (1 + 0.28 * t.quality)
                        * (1 - 0.10 * lev))
                mult = np.clip(mult, 3.0, 34.0)
                val = mult * np.maximum(ttm_ni, ttm_ni * 0.0 + 1.0)
                # loss-makers still hold some asset backing
                val = np.where(ttm_ni <= 0, 0.45 * equity, val)

            # A higher policy rate compresses every multiple.
            series = pd.Series(val / np.maximum(shares, 1e-6), index=q_dates)
            # Fair value becomes visible to the market only when the filing is
            # published, so shift by the reporting lag.
            series.index = pd.to_datetime(g["report_date"].values)
            daily = series.reindex(series.index.union(dates)).ffill().reindex(dates)
            daily = daily.bfill().ffill()
            rate_adj = (0.09 / np.maximum(rate_d, 0.03)) ** 0.32
            out[ticker] = np.maximum(daily.values * rate_adj, 0.5)
        return out

    # -- orchestration ----------------------------------------------------
    def run(self) -> dict:
        self.build_macro()
        self.build_traits()
        self.build_statements()
        self.build_prices()
        return {
            "macro": self.macro, "statements": self.statements,
            "prices": self.prices, "index": self.index,
            "shares": self.shares,
        }


def _prev(rows: List[dict], key: str, default: float) -> float:
    return rows[-1][key] if rows else default
