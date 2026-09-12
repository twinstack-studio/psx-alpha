"""Rule-based composite scorer.

The properties worth pinning down are the ones a reader of a recommendation
would assume: the 0-100 scale means what it says, the risk gates actually bind,
the blend with the model uses the configured weight, and a cap survives the
blend rather than being quietly undone by it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.scoring.composite import PILLAR_LABELS, PILLARS, score_cross_section, z_to_score


# --------------------------------------------------------------------------
class TestZToScore:
    def test_sector_average_maps_to_fifty(self):
        assert z_to_score(0.0) == pytest.approx(50.0)

    def test_three_sigma_reaches_the_ends_of_the_scale(self):
        assert z_to_score(3.0) == pytest.approx(100.0)
        assert z_to_score(-3.0) == pytest.approx(0.0)

    def test_one_sigma_is_a_sixth_of_the_scale(self):
        assert z_to_score(1.0) == pytest.approx(50.0 + 100.0 / 6.0)

    @pytest.mark.parametrize("z", [4.0, 10.0, 100.0])
    def test_clipped_above(self, z):
        assert z_to_score(z) == 100.0

    @pytest.mark.parametrize("z", [-4.0, -10.0])
    def test_clipped_below(self, z):
        assert z_to_score(z) == 0.0

    def test_monotonic(self):
        grid = [-3, -1.5, -0.5, 0, 0.5, 1.5, 3]
        scores = [z_to_score(z) for z in grid]
        assert scores == sorted(scores)

    def test_nan_propagates(self):
        assert np.isnan(z_to_score(np.nan))
        assert np.isnan(z_to_score(None))


class TestPillarDefinitions:
    def test_five_pillars_match_the_configured_weights(self):
        assert set(PILLARS) == set(settings.composite_weights)

    def test_weights_sum_to_one(self):
        assert sum(settings.composite_weights.values()) == pytest.approx(1.0)

    def test_every_pillar_has_a_human_label(self):
        assert set(PILLAR_LABELS) == set(PILLARS)


# --------------------------------------------------------------------------
def make_snapshot(n: int = 12, **overrides) -> pd.DataFrame:
    """A healthy cross-section with a spread of pillar z-scores.

    Nothing here trips a risk gate, so a test can introduce exactly one problem
    and attribute the whole change in score to it.
    """
    rng = np.random.default_rng(3)
    rows = []
    for i in range(n):
        # A deterministic ladder from weak to strong.
        z = -2.0 + 4.0 * i / max(n - 1, 1)
        row = {
            "ticker": f"T{i:02d}",
            "name": f"Company {i}",
            "sector": ["Alpha", "Beta", "Gamma"][i % 3],
            "price": 100.0 + i,
            "is_financial": False,
            "market_cap": 10_000.0,
            "total_equity": 5_000.0,
            "net_income_ttm": 800.0,
            "cfo_ttm": 900.0,
            "roa": 0.10,
            "debt_to_assets": 0.2,
            "interest_coverage": 8.0,
            "turnover_pkr_m": 50.0,
            "accrual_ratio": -0.02,
            "total_assets": 20_000.0,
            "working_capital": 4_000.0,
            "retained_earnings": 6_000.0,
            "ebit_ttm": 2_000.0,
            "revenue_ttm": 12_000.0,
            "shares_outstanding": 100.0,
            "current_ratio": 2.0,
            "gross_margin": 0.4,
            "asset_turnover": 0.9,
        }
        for pillar, cols in PILLARS.items():
            for c in cols:
                row[c] = z + rng.normal(0, 0.05)
        rows.append(row)
    df = pd.DataFrame(rows)
    for k, v in overrides.items():
        df[k] = v
    return df


class TestScoreCrossSection:
    def test_empty_input_returns_empty_frame(self):
        assert score_cross_section(pd.DataFrame()).empty
        assert score_cross_section(None).empty

    def test_scores_stay_inside_the_scale(self):
        out = score_cross_section(make_snapshot())
        assert out["rule_score"].between(0, 100).all()
        assert out["final_score"].between(0, 100).all()

    def test_ranks_are_dense_and_ordered_by_score(self):
        out = score_cross_section(make_snapshot(10))
        assert list(out["rank"]) == list(range(1, 11))
        assert out["final_score"].is_monotonic_decreasing

    def test_better_z_scores_rank_higher(self):
        """The ladder in the fixture runs weak to strong, so the last row in
        must come out first."""
        snap = make_snapshot(10)
        out = score_cross_section(snap)
        assert out.iloc[0]["ticker"] == "T09"
        assert out.iloc[-1]["ticker"] == "T00"

    def test_every_pillar_is_reported_on_both_scales(self):
        out = score_cross_section(make_snapshot())
        for pillar in PILLARS:
            assert pillar in out.columns
            assert f"{pillar}_z" in out.columns
            assert out[pillar].between(0, 100).all()
            assert out[f"{pillar}_z"].between(-3, 3).all()

    def test_bands_follow_the_configured_percentile_cutoffs(self):
        out = score_cross_section(make_snapshot(40))
        for _, row in out.iterrows():
            assert row["recommendation"] == settings.band_for(row["percentile"])

    def test_top_of_the_book_is_a_buy_and_the_bottom_is_not(self):
        out = score_cross_section(make_snapshot(40))
        assert out.iloc[0]["recommendation"] in {"STRONG BUY", "BUY"}
        assert out.iloc[-1]["recommendation"] in {"AVOID", "REDUCE"}

    def test_conviction_is_a_probability(self):
        out = score_cross_section(make_snapshot(20))
        assert out["conviction"].between(0, 1).all()

    def test_a_pillar_with_no_inputs_falls_back_to_the_sector_average(self):
        snap = make_snapshot(8)
        snap = snap.drop(columns=PILLARS["growth"])
        out = score_cross_section(snap)
        assert out["growth_z"].eq(0.0).all()
        assert out["growth"].eq(50.0).all()


class TestRiskGates:
    """Each gate is an interpretable hard rule that overrides a flattering
    composite. A gate that does not bind is a gate that is not there."""

    def _top_row(self, **overrides):
        """Score a cross-section whose strongest name carries one problem."""
        snap = make_snapshot(12)
        idx = snap.index[-1]                       # the highest-scoring name
        for k, v in overrides.items():
            snap.loc[idx, k] = v
        out = score_cross_section(snap)
        return out[out["ticker"] == snap.loc[idx, "ticker"]].iloc[0]

    def test_clean_company_has_no_flags_and_no_cap(self):
        row = self._top_row()
        assert row["risk_flags"] == []
        assert row["score_cap"] == 100.0

    def test_negative_equity_caps_at_25(self):
        row = self._top_row(total_equity=-500.0)
        assert "negative shareholders' equity" in row["risk_flags"]
        assert row["score_cap"] == 25.0
        assert row["final_score"] <= 25.0

    def test_loss_making_caps_at_55(self):
        row = self._top_row(net_income_ttm=-100.0)
        assert "loss-making over the trailing twelve months" in row["risk_flags"]
        assert row["score_cap"] == 55.0

    def test_thin_liquidity_caps_at_60(self):
        row = self._top_row(turnover_pkr_m=1.0)
        assert "thin traded volume, hard to exit" in row["risk_flags"]
        assert row["score_cap"] == 60.0

    def test_weak_interest_cover_caps_at_50(self):
        row = self._top_row(interest_coverage=1.0)
        assert "operating profit barely covers finance cost" in row["risk_flags"]
        assert row["score_cap"] == 50.0

    def test_interest_cover_gate_does_not_apply_to_financials(self):
        row = self._top_row(interest_coverage=1.0, is_financial=True)
        assert "operating profit barely covers finance cost" not in row["risk_flags"]

    def test_altman_distress_caps_at_45(self):
        """Strip the balance sheet until Z'' falls into the distress zone."""
        row = self._top_row(working_capital=-8_000.0, retained_earnings=-9_000.0,
                            ebit_ttm=-500.0, total_equity=200.0)
        assert row["z_zone"] == "distress"
        assert "Altman Z in the distress zone" in row["risk_flags"]
        assert row["score_cap"] <= 45.0

    def test_accrual_flag_warns_without_capping(self):
        """Not every flag is a cap: aggressive accruals are disclosed, but the
        composite already penalises them through the quality pillar."""
        row = self._top_row(accrual_ratio=0.25)
        assert "profit running well ahead of cash generation" in row["risk_flags"]
        assert row["score_cap"] == 100.0

    def test_the_tightest_cap_wins_when_several_gates_trip(self):
        row = self._top_row(total_equity=-500.0, net_income_ttm=-100.0,
                            turnover_pkr_m=1.0)
        assert len(row["risk_flags"]) >= 3
        assert row["score_cap"] == 25.0

    def test_a_capped_name_can_still_be_ranked_and_banded(self):
        row = self._top_row(total_equity=-500.0)
        assert row["recommendation"] in {
            "STRONG BUY", "BUY", "HOLD", "REDUCE", "AVOID"}
        assert row["rank"] >= 1


class TestMlBlend:
    def test_no_ml_scores_leaves_the_rule_score_untouched(self):
        out = score_cross_section(make_snapshot(10))
        assert out["ml_score"].isna().all()
        pd.testing.assert_series_equal(
            out["final_score"], out["rule_score"], check_names=False)

    def test_blend_uses_the_configured_weight(self):
        snap = make_snapshot(10)
        ml = pd.Series(80.0, index=snap["ticker"])
        out = score_cross_section(snap, ml_scores=ml).set_index("ticker")
        w = settings.blend_ml_weight
        for ticker, row in out.iterrows():
            expected = (1 - w) * row["rule_score"] + w * 80.0
            assert row["final_score"] == pytest.approx(min(expected, row["score_cap"]))

    def test_a_missing_ml_score_falls_back_to_the_rule_score(self):
        snap = make_snapshot(10)
        ml = pd.Series(80.0, index=snap["ticker"])
        ml.iloc[0] = np.nan
        out = score_cross_section(snap, ml_scores=ml).set_index("ticker")
        missing = out.loc[snap["ticker"].iloc[0]]
        assert missing["final_score"] == pytest.approx(missing["rule_score"])

    def test_the_cap_survives_the_blend(self):
        """A flattering model score must not lift a name past its risk cap."""
        snap = make_snapshot(12)
        snap.loc[snap.index[-1], "total_equity"] = -500.0
        capped_ticker = snap["ticker"].iloc[-1]
        ml = pd.Series(100.0, index=snap["ticker"])
        out = score_cross_section(snap, ml_scores=ml).set_index("ticker")
        assert out.loc[capped_ticker, "final_score"] <= 25.0
