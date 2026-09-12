"""Ratio ETL: TTM aggregation and sector-relative z-scores.

The fixture panel is deliberately flat — four identical quarters of 1,000 —
so every TTM figure and every margin has a value that can be checked by hand
rather than against the code's own output.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.etl.ratios import (
    LOWER_IS_BETTER,
    MIN_PEERS,
    RATIO_COLS,
    _winsorized_z,
    add_sector_z,
    build_ttm,
    compute_ratios,
    run,
)
from tests.conftest import make_statements


# --------------------------------------------------------------------------
class TestWinsorizedZ:
    def test_standardises_to_zero_mean_unit_sd(self):
        z = _winsorized_z(pd.Series(np.linspace(0, 100, 200)))
        assert z.mean() == pytest.approx(0.0, abs=1e-9)
        assert z.std(ddof=0) == pytest.approx(1.0, abs=1e-9)

    def test_constant_series_is_all_zero_not_nan(self):
        """A sector where every company reports the same ratio has no spread;
        the right answer is 'exactly average', not 'unknown'."""
        z = _winsorized_z(pd.Series([5.0] * 10))
        assert (z == 0.0).all()

    def test_outlier_is_clipped_at_the_5th_and_95th_percentile(self):
        """An extreme value must not be allowed to compress everyone else."""
        clean = pd.Series([10.0] * 19 + [11.0])
        dirty = pd.Series([10.0] * 19 + [1e9])
        assert _winsorized_z(dirty).max() < 10.0
        assert np.isfinite(_winsorized_z(dirty)).all()
        assert _winsorized_z(clean).std(ddof=0) == pytest.approx(1.0)

    def test_too_few_observations_gives_nan(self):
        assert _winsorized_z(pd.Series([1.0])).isna().all()
        assert _winsorized_z(pd.Series([np.nan, np.nan])).isna().all()

    def test_preserves_the_index(self):
        s = pd.Series([1.0, 2.0, 3.0], index=["a", "b", "c"])
        assert list(_winsorized_z(s).index) == ["a", "b", "c"]

    def test_ordering_is_preserved(self):
        s = pd.Series([3.0, 1.0, 2.0])
        z = _winsorized_z(s)
        assert z.iloc[1] < z.iloc[2] < z.iloc[0]


# --------------------------------------------------------------------------
class TestBuildTtm:
    def test_ttm_sums_exactly_four_quarters(self, statements):
        ttm = build_ttm(statements)
        row = ttm[ttm["ticker"] == "OGDC"].iloc[3]      # first complete window
        assert row["revenue_ttm"] == pytest.approx(4 * 1000.0)
        assert row["net_income_ttm"] == pytest.approx(4 * 150.0)
        assert row["cfo_ttm"] == pytest.approx(4 * 180.0)

    def test_first_three_quarters_have_no_ttm(self):
        """`min_periods=4` — three quarters is not a trailing year, and
        annualising it would overstate a seasonal business."""
        ttm = build_ttm(make_statements(["OGDC"]))
        head = ttm[ttm["ticker"] == "OGDC"].head(3)
        assert head["revenue_ttm"].isna().all()

    def test_growth_compounds_into_the_ttm_window(self):
        ttm = build_ttm(make_statements(["OGDC"], periods=8, growth=0.10))
        row = ttm[ttm["ticker"] == "OGDC"].iloc[3]
        expected = sum(1000.0 * 1.10 ** i for i in range(4))
        assert row["revenue_ttm"] == pytest.approx(expected)

    def test_stock_items_average_current_and_year_ago(self, statements):
        """ROA over a growing balance sheet is only comparable if the
        denominator is an average, not a closing balance."""
        ttm = build_ttm(make_statements(["OGDC"], periods=8, growth=0.10))
        row = ttm[ttm["ticker"] == "OGDC"].iloc[4]
        curr = 1000.0 * 1.10 ** 4 * 5.0
        prev = 1000.0 * 5.0
        assert row["total_assets_prev"] == pytest.approx(prev)
        assert row["total_assets_avg"] == pytest.approx((curr + prev) / 2.0)

    def test_tickers_do_not_bleed_into_each_other(self):
        """A rolling window must reset per company, not run across the frame."""
        stmts = pd.concat([
            make_statements(["OGDC"], periods=6, revenue=1000.0),
            make_statements(["PPL"], periods=6, revenue=50.0),
        ], ignore_index=True)
        ttm = build_ttm(stmts)
        ppl = ttm[ttm["ticker"] == "PPL"].iloc[3]
        assert ppl["revenue_ttm"] == pytest.approx(4 * 50.0)


# --------------------------------------------------------------------------
class TestComputeRatios:
    def test_one_row_per_ticker_period(self, statements):
        r = compute_ratios(statements)
        assert len(r) == len(statements)
        assert not r.duplicated(["ticker", "period_end"]).any()

    def test_margins_match_the_panel_by_hand(self, statements):
        r = compute_ratios(statements)
        row = r[(r["ticker"] == "OGDC") & r["net_margin"].notna()].iloc[0]
        assert row["net_margin"] == pytest.approx(0.15)
        assert row["gross_margin"] == pytest.approx(0.40)
        assert row["operating_margin"] == pytest.approx(0.25)

    def test_report_date_is_carried_through(self, statements):
        """The point-in-time filter downstream depends on this column, so it
        must survive the ETL rather than being rebuilt from period_end."""
        r = compute_ratios(statements)
        assert "report_date" in r.columns
        assert (pd.to_datetime(r["report_date"]) > pd.to_datetime(r["period_end"])).all()

    def test_banks_have_no_gross_margin_or_inventory_ratios(self):
        """These concepts do not exist for a lender; reporting a number would
        put banks on a scale they do not belong to."""
        r = compute_ratios(make_statements(["HBL", "MCB", "UBL", "BAFL"]))
        assert r["is_financial"].all()
        for col in ["gross_margin", "inventory_days", "current_ratio",
                    "quick_ratio", "asset_turnover", "cash_conversion_cycle"]:
            assert r[col].isna().all(), col

    def test_non_financials_do_keep_those_ratios(self, statements):
        r = compute_ratios(statements)
        assert not r["is_financial"].any()
        assert r["gross_margin"].notna().any()
        assert r["current_ratio"].notna().any()

    def test_every_declared_ratio_column_exists(self, statements):
        r = compute_ratios(statements)
        for col in RATIO_COLS:
            assert col in r.columns, col

    def test_unknown_ticker_falls_back_to_miscellaneous(self):
        r = compute_ratios(make_statements(["ZZZZ"]))
        assert (r["sector"] == "Miscellaneous").all()


# --------------------------------------------------------------------------
class TestSectorZ:
    def test_every_ratio_gets_a_z_column_bounded_at_three_sigma(self, statements):
        z = add_sector_z(compute_ratios(statements))
        for col in RATIO_COLS:
            zname = f"z_{col}"
            assert zname in z.columns, zname
            vals = z[zname].dropna()
            if len(vals):
                assert vals.between(-3.0, 3.0).all(), zname

    def test_lower_is_better_ratios_have_their_sign_flipped(self):
        """Positive z must always mean 'better than peers'. For gearing that
        means the least indebted name scores highest."""
        stmts = []
        for i, t in enumerate(["OGDC", "PPL", "MARI", "POL", "SNGP", "SSGC"]):
            s = make_statements([t], periods=6)
            # Spread the debt load across the peer group.
            s["long_term_debt"] = s["revenue"] * (0.2 + 0.3 * i)
            s["total_liabilities"] = s["short_term_debt"] + s["long_term_debt"]
            stmts.append(s)
        z = add_sector_z(compute_ratios(pd.concat(stmts, ignore_index=True)))
        last = z[z["period_end"] == z["period_end"].max()]
        least_geared = last.loc[last["debt_to_equity"].idxmin()]
        most_geared = last.loc[last["debt_to_equity"].idxmax()]
        assert least_geared["z_debt_to_equity"] > most_geared["z_debt_to_equity"]

    def test_lower_is_better_set_is_actually_applied(self, statements):
        assert "debt_to_equity" in LOWER_IS_BETTER
        assert "roe" not in LOWER_IS_BETTER

    def test_small_sector_falls_back_to_a_market_wide_comparison(self):
        """With fewer than MIN_PEERS names a sector z-score would be noise, so
        the ratio is ranked against the whole market instead."""
        # Refinery has 4 names in the universe; give it only 2 here.
        stmts = pd.concat([
            make_statements(["ATRL", "NRL"], periods=5),
            make_statements(["OGDC", "PPL", "MARI", "POL"], periods=5),
        ], ignore_index=True)
        z = add_sector_z(compute_ratios(stmts))
        refinery = z[z["sector"] == "Refinery"]
        assert len(refinery["ticker"].unique()) < MIN_PEERS
        # Fallback still produces a usable number rather than all-NaN.
        assert refinery["z_roe"].notna().any()

    def test_z_is_computed_within_a_period_not_across_history(self):
        """Comparing this quarter's margin against last year's peers would
        smuggle a time trend into a cross-sectional score."""
        stmts = pd.concat([
            make_statements(["OGDC", "PPL", "MARI", "POL"], periods=8, growth=0.15),
        ], ignore_index=True)
        z = add_sector_z(compute_ratios(stmts))
        # Every company grows identically, so within any period they are all
        # average — which only holds if the z is computed period by period.
        for _, grp in z.groupby("period_end"):
            vals = grp["z_revenue_growth"].dropna()
            if len(vals) >= MIN_PEERS:
                assert vals.abs().max() < 1e-6

    def test_run_is_the_full_pipeline(self, statements):
        out = run(statements)
        assert "z_roe" in out.columns
        assert "roe" in out.columns
        assert len(out) == len(statements)
