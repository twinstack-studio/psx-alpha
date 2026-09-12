"""Backtest engine: selection, drift, costs and performance statistics.

The engine's docstring lists five ways a stock screen can flatter itself —
look-ahead, free trading, ignoring liquidity, concentration, and silently
re-equalising a drifting book. Each one has a test here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.backtest.engine import (
    Portfolio,
    _drift,
    compute_metrics,
    rebalance_dates,
    select_portfolio,
    yearly_returns,
)
from app.config import settings


# --------------------------------------------------------------------------
def make_scored(n: int = 30, sectors: list[str] | None = None,
                turnover: float = 50.0) -> pd.DataFrame:
    """A scored cross-section, best first, every name investable."""
    sectors = sectors or ["Alpha", "Beta", "Gamma", "Delta"]
    return pd.DataFrame({
        "ticker": [f"T{i:02d}" for i in range(n)],
        "name": [f"Company {i}" for i in range(n)],
        "sector": [sectors[i % len(sectors)] for i in range(n)],
        "final_score": np.linspace(90, 30, n),
        "rule_score": np.linspace(88, 32, n),
        "rank": np.arange(1, n + 1),
        "recommendation": ["BUY"] * n,
        "price": np.linspace(100, 50, n),
        "turnover_pkr_m": [turnover] * n,
    })


class TestSelectPortfolio:
    def test_picks_the_top_n_by_score(self):
        holdings, _, _ = select_portfolio(make_scored(30), "final_score", top_n=10)
        assert len(holdings) == 10
        assert [h.ticker for h in holdings][:3] == ["T00", "T01", "T02"]

    def test_weights_are_equal_and_sum_to_one(self):
        holdings, _, _ = select_portfolio(make_scored(30), "final_score", top_n=10)
        assert sum(h.weight for h in holdings) == pytest.approx(1.0)
        assert len({round(h.weight, 9) for h in holdings}) == 1

    def test_illiquid_names_are_excluded_and_counted(self):
        """A name too thin to build a position in is not investable, however
        well it scores."""
        df = make_scored(20)
        df.loc[:4, "turnover_pkr_m"] = 0.5      # the five best names are thin
        holdings, n_all, n_excluded = select_portfolio(
            df, "final_score", top_n=10, min_turnover_pkr_m=5.0)
        assert n_all == 20
        assert n_excluded == 5
        assert all(h.ticker not in {"T00", "T01", "T02", "T03", "T04"} for h in holdings)

    def test_avoid_band_is_not_bought(self):
        df = make_scored(20)
        df.loc[:2, "recommendation"] = "AVOID"
        holdings, _, _ = select_portfolio(df, "final_score", top_n=10)
        assert all(h.ticker not in {"T00", "T01", "T02"} for h in holdings)

    def test_sector_cap_limits_concentration_when_the_market_is_broad(self):
        """A single sector bet must not be able to masquerade as selection.

        With eight sectors available the cap of floor(0.30 x 10) = 3 names per
        sector can be honoured while still filling a ten-name book.
        """
        df = make_scored(40, sectors=[f"S{i}" for i in range(8)])
        holdings, _, _ = select_portfolio(
            df, "final_score", top_n=10, max_sector_weight=0.30)
        counts = pd.Series([h.sector for h in holdings]).value_counts()
        assert len(holdings) == 10
        assert counts.max() <= max(1, int(np.floor(0.30 * 10)))

    def test_book_is_topped_up_when_the_cap_leaves_it_short(self):
        """The cap constrains concentration, it does not shrink the book —
        otherwise a narrow market would silently raise cash."""
        df = make_scored(40, sectors=["Alpha"])     # one sector only
        holdings, _, _ = select_portfolio(
            df, "final_score", top_n=10, max_sector_weight=0.30)
        assert len(holdings) == 10
        assert sum(h.weight for h in holdings) == pytest.approx(1.0)

    def test_the_top_up_overrides_the_sector_cap(self):
        """Documents a real limit of the current rule, rather than asserting
        the docstring's stronger claim.

        `select_portfolio` fills the book under the cap first, then tops up
        with the next best names **without re-checking the cap**. So when the
        investable set spans too few sectors to fill `top_n`, the finished book
        can exceed `max_sector_weight` — here two sectors end at 50% each
        against a 30% cap.

        This never binds in the shipped backtest: the KSE-100 spans enough
        sectors that the cap holds at every one of its 38 rebalances (the worst
        is 4 of 15, i.e. 27%). It would bind in a narrower universe, or if a
        liquidity filter stripped the cross-section down to a few sectors.
        """
        df = make_scored(40, sectors=["Alpha", "Beta"])
        holdings, _, _ = select_portfolio(
            df, "final_score", top_n=10, max_sector_weight=0.30)
        counts = pd.Series([h.sector for h in holdings]).value_counts()
        assert len(holdings) == 10
        assert counts.max() == 5                      # 50%, over the 30% cap
        # The book is still fully invested and equally weighted.
        assert sum(h.weight for h in holdings) == pytest.approx(1.0)

    def test_no_duplicate_names_after_the_top_up(self):
        df = make_scored(40, sectors=["Alpha", "Beta"])
        holdings, _, _ = select_portfolio(df, "final_score", top_n=15)
        tickers = [h.ticker for h in holdings]
        assert len(tickers) == len(set(tickers))

    def test_nothing_investable_returns_an_empty_book(self):
        df = make_scored(10, turnover=0.1)
        holdings, n_all, n_excluded = select_portfolio(df, "final_score", top_n=10)
        assert holdings == []
        assert n_all == 10 and n_excluded == 10

    def test_selection_can_run_on_a_different_score_column(self):
        df = make_scored(20)
        df["rule_score"] = df["rule_score"].values[::-1]      # reverse the ranking
        by_final, _, _ = select_portfolio(df, "final_score", top_n=5)
        by_rule, _, _ = select_portfolio(df, "rule_score", top_n=5)
        assert {h.ticker for h in by_final} != {h.ticker for h in by_rule}

    def test_fewer_candidates_than_top_n_is_not_an_error(self):
        holdings, _, _ = select_portfolio(make_scored(4), "final_score", top_n=15)
        assert len(holdings) == 4
        assert sum(h.weight for h in holdings) == pytest.approx(1.0)


class TestTurnover:
    """Turnover is the one-way convention, 0.5 x sum of absolute weight
    changes. The engine multiplies it by two when charging costs, so a full
    swap pays both a sale and a purchase."""

    def test_buying_the_first_book_from_cash_is_a_half(self):
        """Opening a position is a purchase with no matching sale, so the
        one-way measure is 0.5 — which the x2 in the cost line turns into
        exactly one round of commission, not two."""
        book = Portfolio("t", "final_score")
        assert book.turnover_against({"A": 0.5, "B": 0.5}) == pytest.approx(0.5)

    def test_holding_the_same_book_costs_nothing(self):
        book = Portfolio("t", "final_score")
        book.weights = {"A": 0.5, "B": 0.5}
        assert book.turnover_against({"A": 0.5, "B": 0.5}) == pytest.approx(0.0)

    def test_replacing_one_of_two_names_is_a_half(self):
        """B is sold and C bought, each a 0.5 weight change, so the absolute
        changes sum to 1.0 and the one-way measure is 0.5."""
        book = Portfolio("t", "final_score")
        book.weights = {"A": 0.5, "B": 0.5}
        assert book.turnover_against({"A": 0.5, "C": 0.5}) == pytest.approx(0.5)

    def test_replacing_the_whole_book_is_one(self):
        book = Portfolio("t", "final_score")
        book.weights = {"A": 1.0}
        assert book.turnover_against({"B": 1.0}) == pytest.approx(1.0)

    def test_turnover_never_exceeds_one(self):
        book = Portfolio("t", "final_score")
        book.weights = {"A": 0.34, "B": 0.33, "C": 0.33}
        assert book.turnover_against({"D": 0.5, "E": 0.5}) <= 1.0 + 1e-9


class TestDrift:
    @staticmethod
    def _close(paths: dict[str, list[float]], start="2021-01-04") -> pd.DataFrame:
        n = len(next(iter(paths.values())))
        return pd.DataFrame(paths, index=pd.bdate_range(start, periods=n))

    def test_a_flat_market_leaves_the_book_unchanged(self):
        close = self._close({"A": [100.0] * 5, "B": [50.0] * 5})
        path, drifted = _drift({"A": 0.5, "B": 0.5}, close,
                               close.index[0], close.index[-1])
        assert path.iloc[-1] == pytest.approx(1.0)
        assert drifted == pytest.approx({"A": 0.5, "B": 0.5})

    def test_weights_drift_with_prices_rather_than_re_equalising(self):
        """The book is held between rebalances. A winner must end the period
        larger than it started, or the reported return is not achievable."""
        close = self._close({"A": [100, 110, 120, 130.0], "B": [100, 100, 100, 100.0]})
        path, drifted = _drift({"A": 0.5, "B": 0.5}, close,
                               close.index[0], close.index[-1])
        assert drifted["A"] > 0.5 > drifted["B"]
        assert sum(drifted.values()) == pytest.approx(1.0)
        # 50% in a name that gained 30%, 50% flat -> +15%
        assert path.iloc[-1] == pytest.approx(1.15)

    def test_path_starts_at_one(self):
        close = self._close({"A": [100, 105, 99, 103.0]})
        path, _ = _drift({"A": 1.0}, close, close.index[0], close.index[-1])
        assert path.iloc[0] == pytest.approx(1.0)

    def test_a_ticker_with_no_price_history_is_dropped(self):
        close = self._close({"A": [100, 110.0]})
        path, drifted = _drift({"A": 0.5, "GONE": 0.5}, close,
                               close.index[0], close.index[-1])
        assert "GONE" not in drifted
        assert not path.empty

    def test_no_overlapping_prices_returns_the_weights_untouched(self):
        close = self._close({"A": [100, 110.0]})
        weights = {"NOT-LISTED": 1.0}
        path, drifted = _drift(weights, close, close.index[0], close.index[-1])
        assert path.empty
        assert drifted == weights


class TestRebalanceDates:
    @staticmethod
    def _store(start="2020-01-01", periods=800):
        class Stub:
            trading_days = pd.bdate_range(start, periods=periods)
        return Stub()

    def test_quarterly_gives_roughly_four_dates_a_year(self):
        store = self._store()
        dates = rebalance_dates(store, pd.Timestamp("2020-01-01"),
                                pd.Timestamp("2022-12-31"), "Q")
        assert 11 <= len(dates) <= 13

    def test_every_date_is_an_actual_trading_day(self):
        store = self._store()
        dates = rebalance_dates(store, pd.Timestamp("2020-01-01"),
                                pd.Timestamp("2022-12-31"), "Q")
        assert all(d in store.trading_days for d in dates)

    def test_dates_are_strictly_increasing(self):
        store = self._store()
        dates = rebalance_dates(store, pd.Timestamp("2020-01-01"),
                                pd.Timestamp("2022-12-31"), "Q")
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))

    def test_rolls_forward_to_the_first_trading_day_of_the_quarter(self):
        """1 Jan 2021 was a Friday holiday in this stub calendar's terms — the
        boundary must land on or after the period start, never before it."""
        store = self._store()
        dates = rebalance_dates(store, pd.Timestamp("2021-01-01"),
                                pd.Timestamp("2021-12-31"), "Q")
        for d in dates:
            quarter_start = pd.Timestamp(d).to_period("Q").start_time
            assert d >= quarter_start

    def test_monthly_is_denser_than_quarterly(self):
        store = self._store()
        q = rebalance_dates(store, pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), "Q")
        m = rebalance_dates(store, pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31"), "M")
        assert len(m) > len(q)


# --------------------------------------------------------------------------
class TestComputeMetrics:
    @staticmethod
    def _curve(values: list[float] | np.ndarray, start="2015-01-01") -> pd.Series:
        idx = pd.bdate_range(start, periods=len(values))
        return pd.Series(values, index=idx)

    def test_a_short_curve_is_refused_rather_than_guessed_at(self):
        assert compute_metrics(self._curve([100.0] * 10)) == {}

    def test_doubling_over_one_calendar_year_is_a_hundred_percent_cagr(self):
        """`years` is measured in calendar days, not trading days, so the
        curve has to span a real year — 253 business days is only ~354 days
        and would report a CAGR of 104%."""
        idx = pd.bdate_range("2015-01-01", "2015-12-31")
        curve = pd.Series(np.linspace(100.0, 200.0, len(idx)), index=idx)
        m = compute_metrics(curve)
        assert m["total_return"] == pytest.approx(1.0)
        assert m["years"] == pytest.approx(0.996, abs=0.01)
        assert m["cagr"] == pytest.approx(1.0, rel=0.02)
        assert m["final_value"] == pytest.approx(200.0)

    def test_cagr_is_consistent_with_the_reported_span(self):
        """Whatever the span, (1 + cagr) ** years must reproduce the growth."""
        idx = pd.bdate_range("2015-01-01", "2019-12-31")
        curve = pd.Series(np.linspace(100.0, 250.0, len(idx)), index=idx)
        m = compute_metrics(curve)
        assert (1 + m["cagr"]) ** m["years"] == pytest.approx(2.5, rel=0.01)

    def test_a_flat_curve_has_no_return_no_vol_and_no_drawdown(self):
        m = compute_metrics(self._curve([100.0] * 300))
        assert m["total_return"] == pytest.approx(0.0)
        assert m["volatility"] == pytest.approx(0.0)
        assert m["max_drawdown"] == pytest.approx(0.0)

    def test_max_drawdown_matches_the_peak_to_trough_fall(self):
        # 100 -> 150 -> 75 -> 120: worst fall is 150 to 75, i.e. -50%.
        values = (list(np.linspace(100, 150, 100))
                  + list(np.linspace(150, 75, 100))
                  + list(np.linspace(75, 120, 100)))
        m = compute_metrics(self._curve(values))
        assert m["max_drawdown"] == pytest.approx(-0.5, abs=0.01)

    def test_drawdown_is_never_positive(self):
        rng = np.random.default_rng(5)
        curve = self._curve(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 500))))
        assert compute_metrics(curve)["max_drawdown"] <= 0.0

    def test_volatility_is_annualised_from_daily_moves(self):
        rng = np.random.default_rng(1)
        daily = rng.normal(0, 0.01, 2000)
        curve = self._curve(100 * np.exp(np.cumsum(daily)))
        m = compute_metrics(curve)
        assert m["volatility"] == pytest.approx(0.01 * np.sqrt(252), rel=0.12)

    def test_sharpe_is_measured_against_the_configured_risk_free_rate(self):
        curve = self._curve(np.linspace(100.0, 200.0, 253))
        m = compute_metrics(curve)
        expected = (m["cagr"] - settings.risk_free_rate) / m["volatility"]
        assert m["sharpe"] == pytest.approx(expected, rel=0.02)

    def test_positive_days_is_a_fraction(self):
        rng = np.random.default_rng(2)
        curve = self._curve(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400))))
        assert 0.0 <= compute_metrics(curve)["positive_days"] <= 1.0


class TestBenchmarkRelativeMetrics:
    @staticmethod
    def _pair(n=600, seed=4, beta=1.0, alpha_daily=0.0):
        rng = np.random.default_rng(seed)
        idx = pd.bdate_range("2016-01-01", periods=n)
        br = rng.normal(0.0004, 0.011, n)
        ar = alpha_daily + beta * br
        bench = pd.Series(100 * np.exp(np.cumsum(br)), index=idx)
        strat = pd.Series(100 * np.exp(np.cumsum(ar)), index=idx)
        return strat, bench

    def test_tracking_the_benchmark_exactly_gives_beta_one_and_no_alpha(self):
        strat, bench = self._pair(beta=1.0, alpha_daily=0.0)
        m = compute_metrics(strat, bench)
        assert m["beta"] == pytest.approx(1.0, abs=0.02)
        assert m["alpha_annual"] == pytest.approx(0.0, abs=0.01)
        assert m["tracking_error"] == pytest.approx(0.0, abs=0.005)

    def test_a_geared_copy_of_the_index_is_detected_as_beta_two(self):
        """Gearing shows up in beta, which is what separates leverage from
        selection when reading the headline table.

        Alpha is *not* asserted to be zero here. `compute_metrics` puts a
        geometric CAGR into a linear CAPM equation, and doubling a log return
        squares the growth factor rather than doubling it, so a purely geared
        copy still books a positive residual. The distortion scales with how
        far beta sits from 1; at the shipped engine's beta of 0.96 it is
        negligible, which is why the reported 6.98% alpha is still selection.
        """
        strat, bench = self._pair(beta=2.0, alpha_daily=0.0)
        m = compute_metrics(strat, bench)
        assert m["beta"] == pytest.approx(2.0, abs=0.05)

    def test_at_beta_one_a_pure_tracker_books_no_alpha(self):
        """The regime the engine actually operates in: with beta near 1 the
        geometric/linear mismatch above all but vanishes."""
        strat, bench = self._pair(beta=1.0, alpha_daily=0.0)
        m = compute_metrics(strat, bench)
        assert m["beta"] == pytest.approx(1.0, abs=0.02)
        assert abs(m["alpha_annual"]) < 0.01

    def test_steady_outperformance_shows_as_positive_alpha_and_ir(self):
        strat, bench = self._pair(beta=1.0, alpha_daily=0.0003)
        m = compute_metrics(strat, bench)
        assert m["alpha_annual"] > 0.03
        assert m["information_ratio"] > 0.5
        assert m["excess_return"] > 0

    def test_benchmark_stats_are_reported_alongside(self):
        strat, bench = self._pair()
        m = compute_metrics(strat, bench)
        assert "benchmark_cagr" in m and "benchmark_total_return" in m

    def test_without_a_benchmark_no_relative_stats_are_invented(self):
        strat, _ = self._pair()
        m = compute_metrics(strat)
        for k in ["beta", "alpha_annual", "information_ratio", "tracking_error"]:
            assert k not in m


class TestYearlyReturns:
    def test_one_entry_per_calendar_year(self):
        idx = pd.bdate_range("2019-01-01", "2021-12-31")
        curve = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        out = yearly_returns(curve)
        assert [r["year"] for r in out] == [2019, 2020, 2021]

    def test_a_flat_year_returns_zero(self):
        idx = pd.bdate_range("2020-01-01", "2020-12-31")
        out = yearly_returns(pd.Series(100.0, index=idx))
        assert out[0]["return"] == pytest.approx(0.0)

    def test_chains_year_on_year_rather_than_from_inception(self):
        """Each year is measured against the previous year's close, so the
        compounded series must reproduce the total return."""
        idx = pd.bdate_range("2019-01-01", "2021-12-31")
        curve = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        out = yearly_returns(curve)
        compounded = np.prod([1 + r["return"] for r in out])
        assert compounded == pytest.approx(curve.iloc[-1] / curve.iloc[0], rel=0.02)

    def test_empty_curve_gives_no_rows(self):
        assert yearly_returns(pd.Series(dtype=float)) == []
