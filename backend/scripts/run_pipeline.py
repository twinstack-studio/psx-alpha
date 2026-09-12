"""Run the full analysis pipeline and export the dashboard bundle.

    python -m scripts.run_pipeline [--start 2016-07-01] [--top-n 15]

Steps: load panel -> technicals -> walk-forward backtest (rule / ML / blended)
-> score the latest cross-section -> write JSON for the Next.js dashboard.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from app.backtest.engine import compute_metrics, run_backtest, yearly_returns
from app.config import EXPORT_DIR, settings
from app.db import repository as repo
from app.ml.ranker import WalkForwardRanker
from app.scoring import technicals as tech_mod
from app.scoring.composite import PILLAR_LABELS, score_cross_section
from app.scoring.explain import explain
from app.scoring.features import FeatureStore
from app.ingest.universe import BY_TICKER


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else round(float(o), 6)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, datetime, date)):
        return str(o)[:10]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float):
        return None if (np.isnan(o) or np.isinf(o)) else round(o, 6)
    raise TypeError(f"not serialisable: {type(o)}")


def write_json(path: Path, payload) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, default=_jsonable, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text)


def clean(v, digits: int = 4):
    """NaN-safe rounding for values headed into JSON."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(f) or np.isinf(f)) else round(f, digits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2016-07-01", help="backtest start date")
    ap.add_argument("--end", default=None)
    ap.add_argument("--top-n", type=int, default=settings.top_n)
    args = ap.parse_args()

    t0 = time.time()
    print("loading panel from the database ...")
    statements = repo.load_statements()
    prices = repo.load_prices()
    index_df = repo.load_index()
    macro = repo.load_macro()
    companies = repo.load_companies()
    if statements.empty or prices.empty:
        sys.exit("no data - run `python -m scripts.build_dataset --reset` first")
    print(f"  {len(companies)} companies | {len(statements)} filings | {len(prices):,} price bars")

    print("computing ratios and sector z-scores ...")
    from app.etl import ratios as ratio_etl
    ratios = ratio_etl.run(statements)

    print("computing price technicals ...")
    tech = tech_mod.run(prices, index_df)

    store = FeatureStore(ratios, tech, prices, index_df, macro)
    ranker = WalkForwardRanker()
    print(f"ML backend : {ranker.backend}")

    start = pd.Timestamp(args.start).date()
    end = pd.Timestamp(args.end).date() if args.end else settings.history_end

    # Sharpe and alpha need a risk-free rate that matches the test window, and
    # Pakistan's policy rate moved between 5.75% and 22% over it. Using the
    # realised average of the window rather than a fixed guess keeps the
    # risk-adjusted numbers honest.
    if macro is not None and len(macro):
        window = macro.loc[str(start):str(end), "policy_rate"]
        if len(window):
            settings.risk_free_rate = round(float(window.mean()) / 100.0, 4)
    print(f"risk-free  : {settings.risk_free_rate:.2%} (average policy rate over the window)")

    def progress(i, n, d):
        print(f"  rebalance {i + 1:>2}/{n}  {d.date()}", end="\r")

    print(f"walk-forward backtest {start} -> {end}, top {args.top_n} names ...")
    settings.top_n = args.top_n
    bt = run_backtest(store, ranker, start, end, progress=progress)
    print(" " * 60, end="\r")

    curves, metrics, books = bt["curves"], bt["metrics"], bt["books"]
    for k in ["blended", "rule", "ml", "KSE100"]:
        m = metrics.get(k, {})
        if m:
            print(f"  {k:<8} CAGR {m['cagr']:>7.2%}  Sharpe {m['sharpe']:>5.2f}  "
                  f"MaxDD {m['max_drawdown']:>7.2%}  IR {m.get('information_ratio', 0):>5.2f}")

    # --- score the latest cross-section ---------------------------------
    last_day = store.trading_days[-1]
    print(f"scoring the live cross-section as of {last_day.date()} ...")
    snap = store.snapshot(last_day)
    snap["universe_size"] = len(snap)
    ml_live = ranker.fit_predict(snap, last_day)
    scored = score_cross_section(snap, store, ml_live if len(ml_live) else None)
    scored["universe_size"] = len(scored)
    if "ml_score" not in scored or scored["ml_score"].isna().all():
        scored["ml_score"] = scored["rule_score"]

    explanations = {r["ticker"]: explain(r) for _, r in scored.iterrows()}
    repo.save_scores(scored, last_day, "v1", explanations)
    print(f"  saved {len(scored)} scores to the database")

    for key, book in books.items():
        if key in metrics:
            repo.save_backtest(
                name=f"walkforward-{key}", strategy=key, start=start, end=end,
                params={"top_n": args.top_n, "rebalance": settings.rebalance_freq,
                        "cost_bps": settings.transaction_cost_bps + settings.slippage_bps,
                        "max_sector_weight": settings.max_sector_weight},
                metrics=metrics[key], curve=curves[key],
                holdings={r.date: r.holdings for r in book.records})

    # --- exports ---------------------------------------------------------
    print("writing dashboard exports ...")
    export(scored, explanations, bt, store, ranker, ratios, statements,
           index_df, macro, companies, start, end, args.top_n)
    print(f"done in {time.time() - t0:.1f}s -> {EXPORT_DIR}")


# --------------------------------------------------------------------------
def export(scored, explanations, bt, store, ranker, ratios, statements,
           index_df, macro, companies, start, end, top_n) -> None:
    curves, metrics, books = bt["curves"], bt["metrics"], bt["books"]
    last_day = store.trading_days[-1]

    # -- equity curves, weekly to keep the payload light -----------------
    curve_df = pd.DataFrame({k: v for k, v in curves.items()}).dropna(how="all")
    weekly = curve_df.resample("W-FRI").last().dropna(how="all")
    curve_rows = [{"date": str(idx.date()),
                   **{k: clean(v, 2) for k, v in row.items()}}
                  for idx, row in weekly.iterrows()]

    # -- drawdown series for the blended book ----------------------------
    dd_rows = []
    if "blended" in curve_df:
        c = curve_df["blended"].dropna()
        b = curve_df["KSE100"].reindex(c.index).ffill()
        dd = (c / c.cummax() - 1.0).resample("W-FRI").last().dropna()
        ddb = (b / b.cummax() - 1.0).resample("W-FRI").last().dropna()
        dd_rows = [{"date": str(i.date()), "strategy": clean(v, 4),
                    "benchmark": clean(ddb.get(i), 4)} for i, v in dd.items()]

    strategy_labels = {
        "rule": "Rule-based score",
        "ml": "ML ranker (XGBoost)",
        "blended": "Blended engine",
        "KSE100": "KSE-100 benchmark",
    }
    perf = []
    for key in ["blended", "rule", "ml", "KSE100"]:
        if key not in metrics:
            continue
        m = dict(metrics[key])
        m["key"] = key
        m["label"] = strategy_labels.get(key, key)
        m["yearly"] = yearly_returns(curves[key])
        perf.append(m)

    # -- rebalance history -------------------------------------------------
    reb = []
    book = books.get("blended")
    if book:
        for r in book.records:
            reb.append({
                "date": r.date,
                "turnover": clean(r.turnover, 4),
                "costBps": clean(r.cost_bps, 2),
                "periodReturn": clean(r.period_return, 4),
                "benchmarkReturn": clean(r.benchmark_return, 4),
                "excess": clean((r.period_return or 0) - (r.benchmark_return or 0), 4),
                "nCandidates": r.n_candidates,
                "nExcludedLiquidity": r.n_excluded_liquidity,
                "holdings": [{"ticker": h["ticker"], "name": h["name"],
                              "sector": h["sector"], "weight": clean(h["weight"], 4),
                              "score": clean(h["score"], 2),
                              "recommendation": h["recommendation"]}
                             for h in r.holdings],
            })

    # -- ML diagnostics ----------------------------------------------------
    folds = ranker.score_folds()
    fold_rows = []
    if len(folds):
        for _, f in folds.iterrows():
            fold_rows.append({
                "date": f["asof"], "trainRows": int(f["train_rows"]),
                "trainPeriods": int(f["train_periods"]),
                "ic": clean(f.get("spearman_ic"), 4),
                "topDecile": clean(f.get("top_decile_fwd"), 4),
                "bottomDecile": clean(f.get("bottom_decile_fwd"), 4),
            })
    ics = [f["ic"] for f in fold_rows if f["ic"] is not None]

    # -- market context ----------------------------------------------------
    idx = index_df.copy()
    idx["date"] = pd.to_datetime(idx["date"])
    idx_weekly = idx.set_index("date")["close"].resample("W-FRI").last().dropna()
    market_rows = [{"date": str(i.date()), "close": clean(v, 2)}
                   for i, v in idx_weekly.items()]

    macro_rows = []
    if macro is not None and len(macro):
        for i, row in macro.iterrows():
            macro_rows.append({
                "date": str(pd.Timestamp(i).date()),
                "policyRate": clean(row.get("policy_rate"), 2),
                "cpi": clean(row.get("cpi_yoy"), 2),
                "usdPkr": clean(row.get("usd_pkr"), 2),
                "reserves": clean(row.get("fx_reserves_usd_bn"), 2),
                "gdp": clean(row.get("gdp_growth"), 2),
            })

    # -- recommendation rows ----------------------------------------------
    px = store.close
    spark_from = px.index[max(0, len(px.index) - 180)]
    recs = []
    for _, r in scored.iterrows():
        t = r["ticker"]
        ex = explanations.get(t, {})
        spark = px[t].loc[spark_from:]
        spark = spark.iloc[:: max(1, len(spark) // 60)]
        recs.append({
            "ticker": t,
            "name": r.get("name"),
            "sector": r.get("sector"),
            "price": clean(r.get("price"), 2),
            "rank": int(r.get("rank") or 0),
            "recommendation": r.get("recommendation"),
            "conviction": clean(r.get("conviction"), 3),
            "finalScore": clean(r.get("final_score"), 1),
            "ruleScore": clean(r.get("rule_score"), 1),
            "mlScore": clean(r.get("ml_score"), 1),
            "percentile": clean(r.get("percentile"), 3),
            "pillars": {p: clean(r.get(p), 1) for p in PILLAR_LABELS},
            # Raw pillar z-scores plus the risk cap let the dashboard re-weight
            # the composite live, without a round trip to the server.
            "pillarZ": {p: clean(r.get(f"{p}_z"), 3) for p in PILLAR_LABELS},
            "scoreCap": clean(r.get("score_cap"), 1),
            "fScore": clean(r.get("f_score"), 1),
            "zScore": clean(r.get("z_score"), 2),
            "zZone": r.get("z_zone"),
            "marketCap": clean(r.get("market_cap"), 0),
            "pe": clean(r.get("pe"), 2),
            "pb": clean(r.get("pb"), 2),
            "evEbitda": clean(r.get("ev_ebitda"), 2),
            "dividendYield": clean(r.get("dividend_yield"), 4),
            "roe": clean(r.get("roe"), 4),
            "roa": clean(r.get("roa"), 4),
            "netMargin": clean(r.get("net_margin"), 4),
            "debtToEquity": clean(r.get("debt_to_equity"), 3),
            "revenueGrowth": clean(r.get("revenue_growth"), 4),
            "earningsGrowth": clean(r.get("earnings_growth"), 4),
            "momentum12m": clean(r.get("momentum_12_1"), 4),
            "return1m": clean(r.get("return_1m"), 4),
            "return3m": clean(r.get("return_3m"), 4),
            "return12m": clean(r.get("return_12m"), 4),
            "volatility": clean(r.get("volatility_252d"), 4),
            "beta": clean(r.get("beta_1y"), 3),
            "turnoverPkrM": clean(r.get("turnover_pkr_m"), 2),
            "rsi": clean(r.get("rsi_14"), 1),
            "riskFlags": list(r.get("risk_flags") or []),
            "headline": ex.get("headline"),
            "summary": ex.get("summary"),
            "spark": [clean(v, 2) for v in spark.tolist()],
        })

    # -- sector aggregates --------------------------------------------------
    sdf = scored.copy()
    sectors = []
    for sec, g in sdf.groupby("sector"):
        sectors.append({
            "sector": sec,
            "count": int(len(g)),
            "avgScore": clean(g["final_score"].mean(), 1),
            "medianPe": clean(g["pe"].median(), 2),
            "medianRoe": clean(g["roe"].median(), 4),
            "medianDebtToEquity": clean(g["debt_to_equity"].median(), 3),
            "avgMomentum": clean(g["momentum_12_1"].mean(), 4),
            "buys": int((g["recommendation"].isin(["BUY", "STRONG BUY"])).sum()),
            "totalMarketCap": clean(g["market_cap"].sum(), 0),
        })
    sectors.sort(key=lambda s: -(s["avgScore"] or 0))

    band_counts = scored["recommendation"].value_counts().to_dict()

    payload = {
        "meta": {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "asOf": str(last_day.date()),
            "universe": "KSE-100",
            "universeSize": int(len(scored)),
            "historyStart": str(settings.history_start),
            "historyEnd": str(settings.history_end),
            "backtestStart": str(start),
            "backtestEnd": str(end),
            "topN": int(top_n),
            "rebalance": "Quarterly",
            "costBps": settings.transaction_cost_bps + settings.slippage_bps,
            "maxSectorWeight": settings.max_sector_weight,
            "mlBackend": ranker.backend,
            "blendWeight": settings.blend_ml_weight,
            "compositeWeights": settings.composite_weights,
            "pillarLabels": PILLAR_LABELS,
            "dataSource": str(statements["source"].iloc[0]) if "source" in statements else "simulated",
            "disclaimer": ("Research and educational project. Not investment advice. "
                           "Figures are produced by a point-in-time simulation of the "
                           "KSE-100 built for reproducible backtesting."),
        },
        "bands": {k: int(v) for k, v in band_counts.items()},
        "recommendations": recs,
        "sectors": sectors,
        "performance": perf,
        "equityCurve": curve_rows,
        "drawdown": dd_rows,
        "rebalances": reb,
        "ml": {
            "backend": ranker.backend,
            "features": len(ranker.features),
            "importance": ranker.importance_table(18),
            "folds": fold_rows,
            "meanIC": clean(np.mean(ics) if ics else None, 4),
            "icHitRate": clean(np.mean([1.0 if i > 0 else 0.0 for i in ics]) if ics else None, 3),
            "labelHorizonDays": settings.ml_label_horizon_days,
        },
        "market": {"index": market_rows, "macro": macro_rows},
    }
    size = write_json(EXPORT_DIR / "dashboard.json", payload)
    print(f"  dashboard.json  {size / 1024:,.0f} KB")

    # -- per-company detail files -----------------------------------------
    stm = statements.copy()
    stm["period_end"] = pd.to_datetime(stm["period_end"])
    rat = ratios.copy()
    rat["period_end"] = pd.to_datetime(rat["period_end"])
    total = 0
    for _, r in scored.iterrows():
        t = r["ticker"]
        hist = px[t].dropna()
        hist_w = hist.resample("W-FRI").last().dropna()
        s_hist = stm[stm["ticker"] == t].sort_values("period_end").tail(12)
        r_hist = rat[rat["ticker"] == t].sort_values("period_end").tail(12)
        peers = scored[scored["sector"] == r["sector"]]
        detail = {
            "ticker": t,
            "name": r.get("name"),
            "sector": r.get("sector"),
            "indexWeight": clean(float(companies.set_index("ticker").loc[t, "index_weight"]), 5)
            if t in set(companies["ticker"]) else None,
            "explanation": explanations.get(t, {}),
            "priceHistory": [{"date": str(i.date()), "close": clean(v, 2)}
                             for i, v in hist_w.items()],
            "financials": [{
                "period": str(pd.Timestamp(row["period_end"]).date()),
                "fiscalYear": int(row["fiscal_year"]), "quarter": int(row["fiscal_quarter"]),
                "revenue": clean(row["revenue"], 0), "grossProfit": clean(row["gross_profit"], 0),
                "operatingIncome": clean(row["operating_income"], 0),
                "netIncome": clean(row["net_income"], 0), "eps": clean(row["eps"], 2),
                "totalAssets": clean(row["total_assets"], 0),
                "totalEquity": clean(row["total_equity"], 0),
                "totalLiabilities": clean(row["total_liabilities"], 0),
                "cfo": clean(row["cfo"], 0), "capex": clean(row["capex"], 0),
                "freeCashFlow": clean(row["free_cash_flow"], 0),
                "reportDate": str(pd.Timestamp(row["report_date"]).date()),
            } for _, row in s_hist.iterrows()],
            "ratioHistory": [{
                "period": str(pd.Timestamp(row["period_end"]).date()),
                "roe": clean(row.get("roe"), 4), "roa": clean(row.get("roa"), 4),
                "netMargin": clean(row.get("net_margin"), 4),
                "grossMargin": clean(row.get("gross_margin"), 4),
                "currentRatio": clean(row.get("current_ratio"), 2),
                "debtToEquity": clean(row.get("debt_to_equity"), 3),
                "interestCoverage": clean(row.get("interest_coverage"), 2),
                "revenueGrowth": clean(row.get("revenue_growth"), 4),
            } for _, row in r_hist.iterrows()],
            "peers": [{"ticker": p["ticker"], "name": p["name"],
                       "finalScore": clean(p["final_score"], 1),
                       "pe": clean(p["pe"], 2), "roe": clean(p["roe"], 4),
                       "recommendation": p["recommendation"]}
                      for _, p in peers.sort_values("final_score", ascending=False).iterrows()],
        }
        total += write_json(EXPORT_DIR / "companies" / f"{t}.json", detail)
    print(f"  companies/      {len(scored)} files, {total / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
