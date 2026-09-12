"""Point-in-time discipline.

This is the module the whole backtest rests on. If `snapshot(asof)` can see a
filing that was not public on `asof`, or a price that had not printed, then
every performance figure the project reports is fiction. The tests below try
to catch exactly that, by planting data the snapshot must refuse to use.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.etl.ratios import run as run_ratios
from app.scoring.features import ML_FEATURES, FeatureStore
from app.scoring.technicals import run as run_tech
from tests.conftest import make_prices, make_statements

TICKERS = ["OGDC", "PPL", "MARI", "POL", "SNGP", "SSGC"]


@pytest.fixture(scope="module")
def store() -> FeatureStore:
    """One store for the module: building the ratio panel is the slow part."""
    stmts = make_statements(TICKERS, periods=14, start="2019-03-31")
    ratios = run_ratios(stmts)
    prices = make_prices(TICKERS, days=900, start="2019-01-01")
    index_df = pd.DataFrame({
        "date": pd.bdate_range("2019-01-01", periods=900),
        "close": np.linspace(40_000, 70_000, 900),
    })
    tech = run_tech(prices, index_df)
    return FeatureStore(ratios, tech, prices, index_df)


# --------------------------------------------------------------------------
class TestLastTradingDay:
    def test_returns_the_day_itself_when_it_is_a_trading_day(self, store):
        day = store.trading_days[300]
        assert store.last_trading_day(day) == day

    def test_rolls_back_over_a_weekend(self, store):
        """A Sunday as-of date must resolve to the preceding Friday, never to
        the following Monday."""
        friday = pd.Timestamp("2021-06-04")
        sunday = pd.Timestamp("2021-06-06")
        assert friday.dayofweek == 4 and sunday.dayofweek == 6
        assert store.last_trading_day(sunday) == friday

    def test_never_looks_forward(self, store):
        for offset in range(0, 400, 37):
            asof = store.trading_days[0] + pd.Timedelta(days=offset)
            day = store.last_trading_day(asof)
            if day is not None:
                assert day <= asof

    def test_before_history_starts_there_is_no_day(self, store):
        assert store.last_trading_day(pd.Timestamp("1990-01-01")) is None


class TestLatestFilings:
    def test_never_returns_a_filing_published_after_the_asof_date(self, store):
        """The core guarantee, swept across the history."""
        for asof in pd.date_range("2020-01-01", "2022-06-30", freq="45D"):
            got = store.latest_filings(asof)
            if isinstance(got, pd.DataFrame) and got.empty:
                continue
            curr, _ = got
            assert (curr["report_date"] <= asof).all(), asof

    def test_picks_the_newest_report_date_not_the_newest_period_end(self):
        """A period that ended earlier but was filed later is the one the
        engine may use. Selecting on period_end instead would hand the model a
        set of accounts nobody had yet seen.
        """
        stmts = make_statements(["OGDC", "PPL", "MARI", "POL"], periods=10)
        # Q1-2021 was restated and filed very late, after the Q2 accounts.
        mask = (stmts["ticker"] == "OGDC") & (stmts["period_end"] == pd.Timestamp("2021-03-31"))
        stmts.loc[mask, "report_date"] = pd.Timestamp("2021-11-30")
        stmts.loc[mask, "revenue"] = 999_999.0

        ratios = run_ratios(stmts)
        prices = make_prices(["OGDC", "PPL", "MARI", "POL"], days=900)
        index_df = pd.DataFrame({"date": pd.bdate_range("2019-01-01", periods=900),
                                 "close": np.linspace(40_000, 70_000, 900)})
        st = FeatureStore(ratios, run_tech(prices, index_df), prices, index_df)

        # On 30 Sep 2021 the restated Q1 is not public yet.
        curr, _ = st.latest_filings(pd.Timestamp("2021-09-30"))
        assert curr.loc["OGDC", "report_date"] <= pd.Timestamp("2021-09-30")
        assert curr.loc["OGDC", "period_end"] != pd.Timestamp("2021-03-31")

        # Once it is filed it becomes the newest visible row.
        curr_after, _ = st.latest_filings(pd.Timestamp("2021-12-15"))
        assert curr_after.loc["OGDC", "period_end"] == pd.Timestamp("2021-03-31")

    def test_year_ago_row_is_four_quarters_back(self, store):
        curr, prev = store.latest_filings(pd.Timestamp("2022-06-30"))
        for ticker in prev.index:
            gap = (pd.Timestamp(curr.loc[ticker, "period_end"])
                   - pd.Timestamp(prev.loc[ticker, "period_end"])).days
            assert 355 <= gap <= 375, ticker

    def test_before_any_filing_is_public_the_result_is_empty(self, store):
        got = store.latest_filings(pd.Timestamp("2019-01-02"))
        assert isinstance(got, pd.DataFrame) and got.empty


class TestSnapshot:
    def test_one_row_per_company(self, store):
        snap = store.snapshot(pd.Timestamp("2022-06-30"))
        assert not snap.empty
        assert not snap["ticker"].duplicated().any()

    def test_price_is_the_last_close_on_or_before_the_asof_date(self, store):
        asof = pd.Timestamp("2021-09-15")
        snap = store.snapshot(asof)
        day = store.last_trading_day(asof)
        for _, row in snap.iterrows():
            assert row["price"] == pytest.approx(store.close.loc[day, row["ticker"]])
            assert pd.Timestamp(row["price_date"]) <= asof

    def test_filings_in_the_snapshot_were_all_public(self, store):
        asof = pd.Timestamp("2021-09-15")
        snap = store.snapshot(asof)
        assert (pd.to_datetime(snap["report_date"]) <= asof).all()
        assert (snap["days_since_filing"] >= 0).all()

    def test_a_later_snapshot_never_loses_information(self, store):
        """Filings accumulate, so a later as-of date can only see more."""
        early = store.snapshot(pd.Timestamp("2021-03-31"))
        late = store.snapshot(pd.Timestamp("2022-06-30"))
        assert set(early["ticker"]) <= set(late["ticker"])

    def test_valuation_multiples_are_built_from_the_snapshot_price(self, store):
        snap = store.snapshot(pd.Timestamp("2022-06-30")).set_index("ticker")
        for ticker, row in snap.iterrows():
            if pd.isna(row["pe"]) or row["net_income_ttm"] <= 0:
                continue
            mcap = row["price"] * row["shares_outstanding"]
            assert row["market_cap"] == pytest.approx(mcap)
            assert row["pe"] == pytest.approx(min(mcap / row["net_income_ttm"], 200))

    def test_negative_earnings_leave_pe_undefined(self, store):
        """A negative P/E is not a cheap stock, it is a meaningless number."""
        snap = store.snapshot(pd.Timestamp("2022-06-30"))
        loss_makers = snap[snap["net_income_ttm"] <= 0]
        assert loss_makers["pe"].isna().all()

    def test_valuation_z_scores_are_bounded(self, store):
        snap = store.snapshot(pd.Timestamp("2022-06-30"))
        for col in ["z_pe", "z_pb", "z_ps", "z_ev_ebitda", "z_dividend_yield", "z_size"]:
            vals = snap[col].dropna()
            if len(vals):
                assert vals.between(-3, 3).all(), col

    def test_cheap_is_a_high_z_for_lower_is_better_multiples(self, store):
        """z_pe must reward a low P/E, otherwise the value pillar is inverted."""
        snap = store.snapshot(pd.Timestamp("2022-06-30")).dropna(subset=["pe", "z_pe"])
        if len(snap) >= 4:
            cheapest = snap.loc[snap["pe"].idxmin()]
            dearest = snap.loc[snap["pe"].idxmax()]
            assert cheapest["z_pe"] >= dearest["z_pe"]

    def test_technical_columns_are_attached(self, store):
        snap = store.snapshot(pd.Timestamp("2022-06-30"))
        for col in ["momentum_12_1", "rsi_14", "volatility_252d", "turnover_pkr_m"]:
            assert col in snap.columns, col
        assert snap["rsi_14"].between(0, 100).all()

    def test_names_and_sector_flags_are_resolved(self, store):
        snap = store.snapshot(pd.Timestamp("2022-06-30")).set_index("ticker")
        assert snap.loc["OGDC", "name"] == "Oil & Gas Development Company"
        assert snap.loc["OGDC", "is_financial"] == False  # noqa: E712

    def test_snapshot_before_any_price_is_empty(self, store):
        assert store.snapshot(pd.Timestamp("1995-01-01")).empty

    def test_prev_row_is_exposed_for_the_piotroski_comparison(self, store):
        store.snapshot(pd.Timestamp("2022-06-30"))
        prev = store.prev_row("OGDC")
        assert prev is not None
        assert store.prev_row("NOT-A-TICKER") is None


class TestForwardReturn:
    def test_looks_forward_by_the_requested_horizon(self, store):
        asof = store.trading_days[400]
        fwd = store.forward_return(asof, 63)
        i = store.trading_days.get_loc(asof)
        expected = store.close.iloc[i + 63] / store.close.iloc[i] - 1.0
        pd.testing.assert_series_equal(fwd, expected.rename("fwd_return"))

    def test_is_a_label_not_a_feature(self, store):
        """Forward return must never appear in the feature list handed to the
        model; it is the thing being predicted."""
        assert "fwd_return" not in ML_FEATURES
        assert not any(f.startswith("fwd") for f in ML_FEATURES)

    def test_truncates_at_the_end_of_history_rather_than_raising(self, store):
        near_end = store.trading_days[-10]
        fwd = store.forward_return(near_end, 63)
        assert len(fwd) > 0
        assert fwd.notna().any()

    def test_at_the_very_end_there_is_no_forward_window(self, store):
        assert store.forward_return(store.trading_days[-1], 63).empty


class TestMlFeatureList:
    def test_has_no_duplicates(self):
        assert len(ML_FEATURES) == len(set(ML_FEATURES))

    def test_is_entirely_relative_or_bounded(self):
        """The docstring promises the model sees relative standing, not levels
        that drift with inflation. Anything not a z-score must be a bounded
        ratio, a flag, or explicit macro context."""
        allowed_non_z = {
            "rsi_14", "golden_cross", "beta_1y", "volume_surge",
            "macro_policy_rate", "macro_cycle",
        }
        for f in ML_FEATURES:
            assert f.startswith("z_") or f in allowed_non_z, f

    def test_excludes_raw_price_and_market_cap_levels(self):
        for banned in ["price", "close", "market_cap", "revenue_ttm", "net_income_ttm"]:
            assert banned not in ML_FEATURES
