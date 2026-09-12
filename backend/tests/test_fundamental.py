"""Piotroski F-Score and Altman Z''-Score.

These two are the interpretable core of the engine, so they are tested against
the published definitions rather than against the code's own output: nine
named binary tests scaled to 0-9, and Altman's emerging-market variant with
its 3.25 constant and its 5.85 / 4.15 zone boundaries.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.scoring.fundamental import (
    BANK_SUBSTITUTIONS,
    PIOTROSKI_TESTS,
    altman_z,
    f_score_verdict,
    is_financial_ticker,
    piotroski,
    z_verdict,
)


# --------------------------------------------------------------------------
# Piotroski
# --------------------------------------------------------------------------
class TestPiotroski:
    def test_all_nine_tests_pass(self, perfect_piotroski):
        curr, prev = perfect_piotroski
        out = piotroski(curr, prev, is_financial=False)
        assert out["f_assessed"] == 9
        assert out["f_passed"] == 9
        assert out["f_score"] == pytest.approx(9.0)

    def test_every_named_test_is_reported(self, perfect_piotroski):
        curr, prev = perfect_piotroski
        out = piotroski(curr, prev, is_financial=False)
        assert set(out["tests"]) == {k for k, _, _ in PIOTROSKI_TESTS}
        for t in out["tests"].values():
            assert t["label"] and t["description"] and t["detail"]

    def test_all_nine_tests_fail(self):
        """Mirror image of the perfect company: every comparison reversed."""
        curr = pd.Series({
            "roa": -0.05, "cfo_ttm": -100.0, "net_income_ttm": 50.0,
            "debt_to_assets": 0.60, "current_ratio": 0.9, "gross_margin": 0.20,
            "asset_turnover": 0.40, "shares_outstanding": 150.0,
        })
        prev = pd.Series({
            "roa": 0.10, "cfo_ttm": 200.0, "net_income_ttm": 40.0,
            "debt_to_assets": 0.30, "current_ratio": 1.8, "gross_margin": 0.35,
            "asset_turnover": 0.70, "shares_outstanding": 100.0,
        })
        out = piotroski(curr, prev, is_financial=False)
        assert out["f_passed"] == 0
        assert out["f_score"] == pytest.approx(0.0)

    def test_accruals_test_compares_cash_against_profit(self):
        """The accrual test is CFO > net income, not CFO > 0."""
        base = {"roa": 0.1, "debt_to_assets": 0.2, "shares_outstanding": 100.0}
        cash_backed = piotroski(
            pd.Series({**base, "cfo_ttm": 500.0, "net_income_ttm": 300.0}), None, False)
        accrual_heavy = piotroski(
            pd.Series({**base, "cfo_ttm": 200.0, "net_income_ttm": 300.0}), None, False)
        assert cash_backed["tests"]["accruals_clean"]["passed"] is True
        assert accrual_heavy["tests"]["accruals_clean"]["passed"] is False
        # Both are cash generative; only the accrual test separates them.
        assert cash_backed["tests"]["cfo_positive"]["passed"] is True
        assert accrual_heavy["tests"]["cfo_positive"]["passed"] is True

    def test_missing_history_is_not_assessable_rather_than_passed(self):
        """Without a year-ago row the five change-based tests must record None.

        Treating an unknown as a pass would inflate every newly listed company,
        which is exactly the failure the docstring promises not to make.
        """
        curr = pd.Series({
            "roa": 0.12, "cfo_ttm": 500.0, "net_income_ttm": 300.0,
            "debt_to_assets": 0.20, "current_ratio": 2.0, "gross_margin": 0.42,
            "asset_turnover": 0.90, "shares_outstanding": 100.0,
        })
        out = piotroski(curr, None, is_financial=False)
        change_based = ["roa_improving", "leverage_falling", "liquidity_rising",
                        "margin_expanding", "turnover_rising", "no_dilution"]
        for key in change_based:
            assert out["tests"][key]["passed"] is None, key
        # Only the three level tests remain assessable.
        assert out["f_assessed"] == 3
        assert out["f_passed"] == 3

    def test_score_is_rescaled_to_nine_when_some_tests_are_unassessable(self):
        """Three of three passed must read as 9/9, not 3/9 — otherwise a short
        history looks like a weak company."""
        curr = pd.Series({
            "roa": 0.12, "cfo_ttm": 500.0, "net_income_ttm": 300.0,
            "shares_outstanding": 100.0,
        })
        out = piotroski(curr, None, is_financial=False)
        assert out["f_assessed"] == 3
        assert out["f_passed"] == 3
        assert out["f_score"] == pytest.approx(9.0)

    def test_half_of_assessable_tests_scores_midway(self):
        curr = pd.Series({"roa": 0.12, "cfo_ttm": -50.0, "net_income_ttm": 300.0})
        out = piotroski(curr, None, is_financial=False)
        # roa passes, cfo fails, accruals fails (cfo < ni) -> 1 of 3
        assert out["f_assessed"] == 3
        assert out["f_passed"] == 1
        assert out["f_score"] == pytest.approx(9.0 / 3.0)

    def test_no_data_at_all_gives_nan(self):
        out = piotroski(pd.Series(dtype=float), None, is_financial=False)
        assert out["f_assessed"] == 0
        assert np.isnan(out["f_score"])

    def test_dilution_tolerates_a_rounding_level_increase(self):
        """A 0.1% drift in share count is a rounding artefact, not an issue."""
        prev = pd.Series({"shares_outstanding": 100.0})
        assert piotroski(pd.Series({"shares_outstanding": 100.05}), prev, False) \
            ["tests"]["no_dilution"]["passed"] is True
        assert piotroski(pd.Series({"shares_outstanding": 105.0}), prev, False) \
            ["tests"]["no_dilution"]["passed"] is False

    def test_flat_leverage_counts_as_deleveraging(self):
        """The test is `<=`: unchanged gearing is not a deterioration."""
        curr = pd.Series({"debt_to_assets": 0.30})
        prev = pd.Series({"debt_to_assets": 0.30})
        assert piotroski(curr, prev, False)["tests"]["leverage_falling"]["passed"] is True


class TestPiotroskiForFinancials:
    """Banks have no gross margin, inventory or current ratio, so three tests
    are swapped for balance-sheet equivalents."""

    def test_bank_tests_are_relabelled(self, perfect_piotroski):
        curr, prev = perfect_piotroski
        bank = piotroski(curr, prev, is_financial=True)
        corp = piotroski(curr, prev, is_financial=False)
        for key, (label, desc) in BANK_SUBSTITUTIONS.items():
            assert bank["tests"][key]["label"] == label
            assert bank["tests"][key]["description"] == desc
            assert corp["tests"][key]["label"] != label

    def test_bank_uses_equity_ratio_not_current_ratio(self):
        """Current ratio improves, equity ratio deteriorates. A bank must read
        the second and ignore the first."""
        curr = pd.Series({"current_ratio": 3.0, "equity_ratio": 0.40})
        prev = pd.Series({"current_ratio": 1.0, "equity_ratio": 0.55})
        assert piotroski(curr, prev, True)["tests"]["liquidity_rising"]["passed"] is False
        assert piotroski(curr, prev, False)["tests"]["liquidity_rising"]["passed"] is True

    def test_bank_uses_net_margin_for_the_margin_test(self):
        curr = pd.Series({"gross_margin": 0.10, "net_margin": 0.30})
        prev = pd.Series({"gross_margin": 0.40, "net_margin": 0.20})
        assert piotroski(curr, prev, True)["tests"]["margin_expanding"]["passed"] is True
        assert piotroski(curr, prev, False)["tests"]["margin_expanding"]["passed"] is False

    def test_bank_turnover_uses_revenue_over_assets(self):
        curr = pd.Series({"revenue_ttm": 600.0, "total_assets": 1000.0})
        prev = pd.Series({"revenue_ttm": 400.0, "total_assets": 1000.0})
        assert piotroski(curr, prev, True)["tests"]["turnover_rising"]["passed"] is True


class TestFScoreVerdict:
    @pytest.mark.parametrize("score,expected", [
        (9.0, "very strong"), (8.0, "very strong"),
        (7.0, "strong"), (6.0, "strong"),
        (5.0, "mixed"), (4.0, "mixed"),
        (3.0, "weak"), (0.0, "weak"),
    ])
    def test_bands(self, score, expected):
        assert f_score_verdict(score) == expected

    def test_nan_is_reported_as_insufficient_history(self):
        assert f_score_verdict(float("nan")) == "insufficient history"


# --------------------------------------------------------------------------
# Altman
# --------------------------------------------------------------------------
class TestAltmanZ:
    def test_matches_the_published_z_em_formula(self, solvent_row):
        """6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4 + 3.25, computed by hand."""
        out = altman_z(solvent_row, market_cap=None, is_financial=False)
        ta, te = 1000.0, 700.0
        tl = ta - te                      # 300
        x1, x2, x3 = 300 / ta, 400 / ta, 150 / ta
        x4 = te / tl
        expected = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4 + 3.25
        assert out["z_score"] == pytest.approx(expected)
        assert out["z_variant"] == "Altman Z''-EM"

    def test_sales_to_assets_is_reported_but_not_scored(self, solvent_row):
        """Z''-EM drops the X5 term. It is still exposed as a component, so the
        dashboard can show it, but changing it must not move the score."""
        out = altman_z(solvent_row, None, False)
        louder = solvent_row.copy()
        louder["revenue_ttm"] = solvent_row["revenue_ttm"] * 10
        assert altman_z(louder, None, False)["z_score"] == pytest.approx(out["z_score"])
        assert out["components"]["sales_to_assets"] == pytest.approx(0.9)

    def test_all_zero_ratios_leave_only_the_constant(self):
        row = pd.Series({
            "total_assets": 1000.0, "total_equity": 0.0, "working_capital": 0.0,
            "retained_earnings": 0.0, "ebit_ttm": 0.0, "revenue_ttm": 0.0,
        })
        assert altman_z(row, None, False)["z_score"] == pytest.approx(3.25)

    @pytest.mark.parametrize("z,zone", [
        (6.0, "safe"), (5.86, "safe"),
        (5.85, "grey"), (5.0, "grey"), (4.15, "grey"),
        (4.14, "distress"), (1.0, "distress"),
    ])
    def test_zone_boundaries(self, z, zone):
        """Drive the score to a target by choosing retained earnings, which
        enters only through X2 at a known coefficient."""
        ta = 1000.0
        base = altman_z(pd.Series({
            "total_assets": ta, "total_equity": 500.0, "working_capital": 0.0,
            "retained_earnings": 0.0, "ebit_ttm": 0.0, "revenue_ttm": 0.0,
        }), None, False)["z_score"]
        re_needed = (z - base) / 3.26 * ta
        out = altman_z(pd.Series({
            "total_assets": ta, "total_equity": 500.0, "working_capital": 0.0,
            "retained_earnings": re_needed, "ebit_ttm": 0.0, "revenue_ttm": 0.0,
        }), None, False)
        assert out["z_score"] == pytest.approx(z)
        assert out["zone"] == zone

    def test_financials_are_excluded(self, solvent_row):
        """Altman excluded financials from his fitting sample, so the engine
        must report not-applicable rather than a misleading number."""
        out = altman_z(solvent_row, None, is_financial=True)
        assert np.isnan(out["z_score"])
        assert out["zone"] == "n/a"
        assert out["components"] == {}

    @pytest.mark.parametrize("assets", [0.0, -100.0, None])
    def test_missing_or_impossible_assets_give_nan(self, assets):
        row = pd.Series({"total_assets": assets, "total_equity": 100.0})
        out = altman_z(row, None, False)
        assert np.isnan(out["z_score"])
        assert out["zone"] == "n/a"

    def test_liabilities_floor_prevents_divide_by_zero(self):
        """Equity equal to assets means zero liabilities; X4 must stay finite."""
        row = pd.Series({
            "total_assets": 1000.0, "total_equity": 1000.0, "working_capital": 0.0,
            "retained_earnings": 0.0, "ebit_ttm": 0.0, "revenue_ttm": 0.0,
        })
        out = altman_z(row, None, False)
        assert np.isfinite(out["z_score"])

    def test_manufacturing_variant_only_with_a_market_cap(self, solvent_row):
        assert "z_score_manufacturing" not in altman_z(solvent_row, None, False)
        assert "z_score_manufacturing" not in altman_z(solvent_row, 0.0, False)
        assert "z_score_manufacturing" in altman_z(solvent_row, 5000.0, False)


class TestZVerdict:
    @pytest.mark.parametrize("z,expected", [
        (6.0, "financially sound"), (5.0, "watch zone"), (2.0, "distress risk"),
    ])
    def test_bands(self, z, expected):
        assert z_verdict(z) == expected

    def test_boundaries_match_the_zone_labels(self):
        assert z_verdict(5.85) == "watch zone"
        assert z_verdict(4.15) == "watch zone"
        assert z_verdict(4.14) == "distress risk"

    @pytest.mark.parametrize("z", [None, float("nan")])
    def test_missing_is_not_applicable(self, z):
        assert z_verdict(z) == "not applicable"


class TestSectorClassification:
    def test_banks_are_financial(self):
        assert is_financial_ticker("HBL") is True
        assert is_financial_ticker("MCB") is True

    def test_explorers_are_not(self):
        assert is_financial_ticker("OGDC") is False

    def test_unknown_ticker_is_not_financial(self):
        assert is_financial_ticker("NOT-A-TICKER") is False
