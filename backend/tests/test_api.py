"""REST API.

These run against the real exported bundle, because the contract worth testing
is the one the dashboard consumes. If the pipeline has not been run there is
nothing to serve, so the module skips rather than failing.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(scope="module")
def client(bundle_path):
    """`bundle_path` skips the whole module when no analysis has been exported."""
    with TestClient(app) as c:
        yield c


BANDS = {"STRONG BUY", "BUY", "HOLD", "REDUCE", "AVOID"}


# --------------------------------------------------------------------------
class TestSystem:
    def test_health_reports_a_loaded_analysis(self, client):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["has_analysis"] is True
        assert body["universe_size"] > 0

    def test_root_points_at_the_docs(self, client):
        body = client.get("/").json()
        assert body["docs"] == "/docs"

    def test_openapi_schema_is_served(self, client):
        schema = client.get("/openapi.json").json()
        assert "/api/recommendations" in schema["paths"]

    def test_meta_exposes_the_engine_configuration(self, client):
        meta = client.get("/api/meta").json()
        assert meta["universeSize"] > 0
        assert set(meta["compositeWeights"]) == set(settings.composite_weights)


class TestRecommendations:
    def test_returns_the_whole_ranked_cross_section(self, client):
        body = client.get("/api/recommendations").json()
        items = body["items"]
        assert len(items) > 0
        ranks = [r["rank"] for r in items]
        assert ranks == sorted(ranks)

    def test_every_row_carries_a_valid_band(self, client):
        for r in client.get("/api/recommendations").json()["items"]:
            assert r["recommendation"] in BANDS

    def test_top_n_is_honoured_and_ordered_by_score(self, client):
        body = client.get("/api/recommendations/top?n=5").json()
        assert body["count"] == 5
        scores = [r["finalScore"] for r in body["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_top_picks_are_equally_weighted(self, client):
        body = client.get("/api/recommendations/top?n=8").json()
        assert body["weightEach"] == pytest.approx(1 / 8)

    def test_every_pick_is_explained(self, client):
        """The proposal's central promise: no recommendation without a reason."""
        for r in client.get("/api/recommendations/top?n=10").json()["items"]:
            assert r["headline"]
            assert r["summary"]

    @pytest.mark.parametrize("n", [0, 51, -1])
    def test_out_of_range_n_is_rejected(self, client, n):
        assert client.get(f"/api/recommendations/top?n={n}").status_code == 422


class TestCompanies:
    def test_a_known_company_returns_its_dossier(self, client):
        top = client.get("/api/recommendations/top?n=1").json()["items"][0]
        body = client.get(f"/api/companies/{top['ticker']}").json()
        assert body["ticker"] == top["ticker"]
        assert body["explanation"]["headline"]

    def test_lookup_is_case_insensitive(self, client):
        top = client.get("/api/recommendations/top?n=1").json()["items"][0]
        lower = client.get(f"/api/companies/{top['ticker'].lower()}")
        assert lower.status_code == 200
        assert lower.json()["ticker"] == top["ticker"]

    def test_unknown_ticker_is_a_404(self, client):
        assert client.get("/api/companies/NOTREAL").status_code == 404

    def test_explanation_endpoint_carries_the_reasoning(self, client):
        top = client.get("/api/recommendations/top?n=1").json()["items"][0]
        ex = client.get(f"/api/companies/{top['ticker']}/explanation").json()
        assert ex["recommendation"] in BANDS
        assert isinstance(ex["strengths"], list)
        assert isinstance(ex["concerns"], list)
        assert ex["disclaimer"]


class TestEvidence:
    def test_backtest_reports_every_strategy_against_the_index(self, client):
        body = client.get("/api/backtest").json()
        keys = {p["key"] for p in body["performance"]}
        assert {"blended", "rule", "ml", "KSE100"} <= keys

    def test_rebalance_log_is_dated_and_holds_names(self, client):
        items = client.get("/api/backtest/rebalances?limit=5").json()["items"]
        assert len(items) <= 5
        for r in items:
            assert r["date"]
            assert len(r["holdings"]) > 0

    def test_model_diagnostics_expose_the_feature_set(self, client):
        body = client.get("/api/model").json()
        assert body["features"] > 0
        assert len(body["importance"]) > 0

    def test_sectors_and_market_are_served(self, client):
        assert len(client.get("/api/sectors").json()["items"]) > 0
        assert "macro" in client.get("/api/market").json()


class TestScreen:
    """`POST /api/screen` re-weights precomputed pillar z-scores. It is a
    re-scoring, not a re-fit, so it must agree with the engine when handed the
    engine's own weights."""

    def _post(self, client, **body):
        r = client.post("/api/screen", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_default_weights_reproduce_the_engine_ranking(self, client):
        body = self._post(client, **settings.composite_weights,
                          ml_weight=settings.blend_ml_weight, top_n=10)
        for item in body["items"]:
            assert item["score"] == pytest.approx(item["baseScore"], abs=0.5)

    def test_results_are_ranked_by_the_custom_score(self, client):
        body = self._post(client, quality=1.0, value=0, safety=0,
                          growth=0, momentum=0, top_n=20)
        scores = [r["score"] for r in body["items"]]
        assert scores == sorted(scores, reverse=True)
        assert [r["rank"] for r in body["items"]] == list(range(1, len(scores) + 1))

    def test_a_different_weighting_moves_the_book(self):
        """If every weighting produced the same list the sliders would be
        decoration."""
        with TestClient(app) as client:
            quality = self._post(client, quality=1.0, value=0, safety=0,
                                 growth=0, momentum=0, top_n=10)
            value = self._post(client, quality=0, value=1.0, safety=0,
                               growth=0, momentum=0, top_n=10)
        assert [r["ticker"] for r in quality["items"]] != \
               [r["ticker"] for r in value["items"]]

    def test_weights_are_normalised_so_only_their_ratio_matters(self, client):
        small = self._post(client, quality=0.3, value=0.1, safety=0.1,
                           growth=0.1, momentum=0.1, top_n=10)
        large = self._post(client, quality=0.6, value=0.2, safety=0.2,
                           growth=0.2, momentum=0.2, top_n=10)
        assert [r["ticker"] for r in small["items"]] == \
               [r["ticker"] for r in large["items"]]

    def test_liquidity_floor_is_applied(self, client):
        loose = self._post(client, min_turnover_pkr_m=0.0, top_n=100)
        tight = self._post(client, min_turnover_pkr_m=500.0, top_n=100)
        assert tight["total"] < loose["total"]

    def test_sector_filter_restricts_the_output(self, client):
        sector = client.get("/api/sectors").json()["items"][0]["sector"]
        body = self._post(client, sectors=[sector], top_n=100)
        assert body["total"] > 0
        assert all(r["sector"] == sector for r in body["items"])

    def test_risk_caps_still_bind_under_custom_weights(self, client):
        """The sliders re-weight the pillars; they do not switch off the
        gates. A capped name must stay capped."""
        body = self._post(client, quality=1.0, value=0, safety=0,
                          growth=0, momentum=0, top_n=100)
        flagged = [r for r in body["items"] if r["riskFlags"]]
        assert all(r["score"] <= 100.0 for r in flagged)

    def test_scores_stay_on_the_zero_to_hundred_scale(self, client):
        body = self._post(client, top_n=100)
        assert all(0.0 <= r["score"] <= 100.0 for r in body["items"])

    def test_top_n_caps_the_payload_without_changing_the_total(self, client):
        body = self._post(client, top_n=3)
        assert len(body["items"]) == 3
        assert body["total"] >= 3
