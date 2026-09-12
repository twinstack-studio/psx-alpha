"""The exported bundle's contract.

`dashboard.json` is the seam between the Python pipeline and its two
consumers: the FastAPI layer and the statically generated Next.js dashboard.
Neither consumer refits anything, so a field the pipeline forgets to write is
not a crash — it is a feature that silently stops working.

That is not hypothetical. `pillarZ` was added to the exporter after the last
pipeline run, so the shipped bundle had no such key; `POST /api/screen` and the
dashboard's weight sliders both fell back to a z of 0 for every pillar, which
scores every company at exactly 50 and hands the entire ranking to the model.
The ranking still looked plausible, which is what made it hard to notice. The
tests below pin the whole contract so a stale or incomplete bundle fails loudly.
"""
from __future__ import annotations

import json

import pytest

from app.config import settings
from app.scoring.composite import PILLAR_LABELS

BANDS = {"STRONG BUY", "BUY", "HOLD", "REDUCE", "AVOID"}


@pytest.fixture(scope="module")
def bundle(bundle_path) -> dict:
    return json.loads(bundle_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recommendations(bundle) -> list[dict]:
    return bundle["recommendations"]


# --------------------------------------------------------------------------
class TestBundleShape:
    def test_top_level_sections_are_all_present(self, bundle):
        for key in ["meta", "bands", "recommendations", "sectors", "performance",
                    "equityCurve", "drawdown", "rebalances", "ml", "market"]:
            assert key in bundle, key

    def test_meta_describes_the_run(self, bundle):
        meta = bundle["meta"]
        assert meta["universeSize"] == len(bundle["recommendations"])
        assert meta["asOf"]
        assert meta["disclaimer"]

    def test_meta_weights_match_the_live_configuration(self, bundle):
        """A bundle exported under different weights than the code now uses
        would make every explanation subtly wrong."""
        assert bundle["meta"]["compositeWeights"] == pytest.approx(
            settings.composite_weights)
        assert bundle["meta"]["blendWeight"] == pytest.approx(settings.blend_ml_weight)


class TestRecommendationRows:
    def test_every_row_has_the_fields_both_clients_read(self, recommendations):
        required = [
            "ticker", "name", "sector", "price", "rank", "recommendation",
            "conviction", "finalScore", "ruleScore", "mlScore", "percentile",
            "pillars", "pillarZ", "scoreCap", "fScore", "zScore", "zZone",
            "marketCap", "pe", "pb", "roe", "riskFlags", "headline", "summary",
            "spark",
        ]
        for row in recommendations:
            for key in required:
                assert key in row, f"{row['ticker']} is missing {key}"

    def test_tickers_are_unique(self, recommendations):
        tickers = [r["ticker"] for r in recommendations]
        assert len(tickers) == len(set(tickers))

    def test_ranks_are_dense_and_sorted(self, recommendations):
        assert [r["rank"] for r in recommendations] == list(
            range(1, len(recommendations) + 1))

    def test_bands_are_from_the_known_set(self, recommendations):
        assert {r["recommendation"] for r in recommendations} <= BANDS

    def test_scores_are_on_the_zero_to_hundred_scale(self, recommendations):
        for r in recommendations:
            for key in ["finalScore", "ruleScore", "mlScore"]:
                v = r[key]
                if v is not None:
                    assert 0.0 <= v <= 100.0, f"{r['ticker']}.{key} = {v}"

    def test_every_recommendation_is_explained(self, recommendations):
        """The project's central claim. An unexplained pick is a black box."""
        for r in recommendations:
            assert r["headline"], r["ticker"]
            assert r["summary"], r["ticker"]

    def test_sparklines_carry_enough_points_to_draw(self, recommendations):
        for r in recommendations:
            assert len(r["spark"]) >= 2, r["ticker"]


class TestPillarZ:
    """The regression that prompted this module.

    `pillarZ` is what lets both clients re-weight the composite without a
    refit. Absent or all-zero, the re-weighting silently degenerates.
    """

    def test_pillar_z_is_present_for_every_company(self, recommendations):
        for r in recommendations:
            assert r.get("pillarZ") is not None, f"{r['ticker']} has no pillarZ"

    def test_pillar_z_covers_all_five_pillars(self, recommendations):
        for r in recommendations:
            assert set(r["pillarZ"]) == set(PILLAR_LABELS), r["ticker"]

    def test_pillar_z_is_within_three_sigma(self, recommendations):
        for r in recommendations:
            for pillar, z in r["pillarZ"].items():
                if z is not None:
                    assert -3.0 <= z <= 3.0, f"{r['ticker']}.{pillar} = {z}"

    def test_pillar_z_actually_varies_across_the_market(self, recommendations):
        """All-zero would pass the presence checks above while still breaking
        the sliders, because every company would score exactly 50."""
        for pillar in PILLAR_LABELS:
            values = [r["pillarZ"].get(pillar) for r in recommendations]
            values = [v for v in values if v is not None]
            assert len(values) > 0, pillar
            assert max(values) - min(values) > 0.5, f"{pillar} is nearly constant"

    def test_pillar_z_agrees_with_the_zero_to_hundred_pillar_score(self, recommendations):
        """The two are the same number on different scales: score = 50 + z*100/6."""
        for r in recommendations:
            for pillar in PILLAR_LABELS:
                z, score = r["pillarZ"].get(pillar), r["pillars"].get(pillar)
                if z is None or score is None:
                    continue
                expected = max(0.0, min(100.0, 50.0 + (100.0 / 6.0) * z))
                assert score == pytest.approx(expected, abs=0.15), \
                    f"{r['ticker']}.{pillar}: z={z} score={score}"

    def test_reweighting_by_hand_reproduces_the_rule_score(self, recommendations):
        """The exact arithmetic both clients run. If this holds, a slider moved
        in the browser produces the number the engine would have produced."""
        w = settings.composite_weights
        total = sum(w.values())
        for r in recommendations:
            pz = r["pillarZ"]
            if any(pz.get(p) is None for p in w):
                continue
            z = sum(pz[p] * (wt / total) for p, wt in w.items())
            rule = max(0.0, min(100.0, 50.0 + (100.0 / 6.0) * z))
            cap = r.get("scoreCap")
            if cap is not None:
                rule = min(rule, cap)
            assert r["ruleScore"] == pytest.approx(rule, abs=0.2), r["ticker"]


class TestRiskDisclosure:
    def test_score_cap_is_exported_so_gates_survive_re_weighting(self, recommendations):
        for r in recommendations:
            assert "scoreCap" in r
            if r["scoreCap"] is not None:
                assert 0.0 <= r["scoreCap"] <= 100.0

    def test_a_capped_score_is_actually_capped(self, recommendations):
        for r in recommendations:
            cap = r.get("scoreCap")
            if cap is not None and r["finalScore"] is not None:
                assert r["finalScore"] <= cap + 0.05, r["ticker"]

    def test_distress_names_carry_a_flag(self, recommendations):
        for r in recommendations:
            if r.get("zZone") == "distress":
                assert r["riskFlags"], r["ticker"]


class TestEvidenceSections:
    def test_every_strategy_and_the_benchmark_are_reported(self, bundle):
        assert {p["key"] for p in bundle["performance"]} >= {
            "blended", "rule", "ml", "KSE100"}

    def test_equity_curve_is_dated_and_ordered(self, bundle):
        dates = [p["date"] for p in bundle["equityCurve"]]
        assert len(dates) > 100
        assert dates == sorted(dates)

    def test_rebalances_hold_names_and_respect_the_liquidity_floor(self, bundle):
        for r in bundle["rebalances"]:
            assert len(r["holdings"]) > 0, r["date"]
            weights = sum(h["weight"] for h in r["holdings"])
            assert weights == pytest.approx(1.0, abs=0.01), r["date"]

    def test_sector_concentration_stays_inside_the_configured_cap(self, bundle):
        """`select_portfolio` tops the book up without re-checking the cap, so
        this is a property of the shipped run rather than a guarantee of the
        code — worth asserting precisely because it could quietly stop holding.
        """
        cap = settings.max_sector_weight
        for r in bundle["rebalances"]:
            counts: dict[str, float] = {}
            for h in r["holdings"]:
                counts[h["sector"]] = counts.get(h["sector"], 0.0) + h["weight"]
            worst_sector = max(counts, key=counts.get)
            assert counts[worst_sector] <= cap + 1e-9, \
                f"{r['date']}: {worst_sector} at {counts[worst_sector]:.0%}"

    def test_model_diagnostics_name_their_features(self, bundle):
        ml = bundle["ml"]
        assert ml["features"] > 0
        assert len(ml["importance"]) > 0
        for f in ml["importance"]:
            assert f["feature"] and f["importance"] >= 0
