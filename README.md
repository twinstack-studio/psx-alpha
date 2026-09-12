# PSX Alpha — AI-Driven Stock Recommendation System for the Pakistan Stock Exchange

A final-year-project implementation of a research engine that scores and ranks
KSE-100 companies from their published accounts, explains every recommendation in
plain language, and proves out the ranking with a walk-forward backtest against
the index.

```
                 ┌──────────────┐
  PSX filings ──▶│  Ingest      │  point-in-time: period_end + report_date
  PSX prices  ──▶│  + simulate  │
  SBP macro   ──▶└──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │  ETL         │  chart-of-accounts standardisation,
                 │  ratios      │  TTM aggregation, sector-relative z-scores
                 └──────┬───────┘
                        ▼
          ┌─────────────┴─────────────┐
          ▼                           ▼
   ┌─────────────┐            ┌──────────────┐
   │ Rule scorer │            │ XGBoost      │  walk-forward,
   │ 5 pillars   │            │ ranker       │  retrained each quarter
   │ Piotroski   │            └──────┬───────┘
   │ Altman Z''  │                   │
   └──────┬──────┘                   │
          └────────────┬─────────────┘
                       ▼
                ┌─────────────┐
                │  Blend      │ → explanation generator → REST API
                │  + risk     │ → walk-forward backtest vs KSE-100
                │  gates      │ → Next.js dashboard
                └─────────────┘
```

---

## Headline result

Walk-forward, quarterly rebalanced, 1 July 2016 to 31 December 2025, top 15 names
equal-weighted, 50 bps charged per round trip, 30% sector cap, illiquid names
excluded.

| Strategy | CAGR | Volatility | Sharpe | Max drawdown | Information ratio | Quarters ahead |
|---|---|---|---|---|---|---|
| **Blended engine** | **21.21%** | 17.6% | 0.56 | −53.3% | **0.83** | 63% |
| Rule-based score | 19.48% | 17.3% | 0.46 | −50.0% | 0.62 | 63% |
| ML ranker alone | 16.85% | 17.8% | 0.30 | −54.7% | 0.29 | 55% |
| KSE-100 benchmark | 14.34% | 16.1% | 0.18 | −55.5% | — | — |

Annual alpha of 6.98% at a beta of 0.96, so the excess return is selection rather
than gearing. The Sharpe ratios look modest because the risk-free rate is the
realised average SBP policy rate over the window, 11.43%.

**The interpretable baseline beat the machine-learning model on its own.** That is
reported rather than tuned away, and the reasoning is on the Model page of the
dashboard: a KSE-100 cross-section is about a hundred rows a quarter over roughly
thirty usable quarters, which is not enough signal for a flexible learner against
53 noisy features. The blend of the two still beat either alone, because their
errors are not the same errors.

---

## Running it

Prerequisites: Python 3.12 (3.13+ has no wheels for some dependencies yet) and
Node.js 20 or newer.

### Backend

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate                     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.build_dataset --reset     # build the point-in-time panel (~35s)
python -m scripts.run_pipeline              # ratios, backtest, scores, exports (~90s)
```

`build_dataset` populates the database and the ratio table. `run_pipeline` runs the
walk-forward backtest, scores the live cross-section, writes the scores back to the
database and exports the JSON the dashboard reads.

Serve the REST API:

```bash
uvicorn app.main:app --reload --port 8000   # docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run sync-data       # copies backend/data/exports into public/data
npm run dev             # http://localhost:3000
```

Or from the project root on Windows, `./run.ps1` does all of it in one go.

`dev` and `build` run through webpack rather than Turbopack. Turbopack is faster,
but its PostCSS worker fails to spawn on memory-constrained Windows machines
(`STATUS_DLL_INIT_FAILED`), which is a hard build failure rather than a slow one.
`npm run dev:turbo` and `npm run build:turbo` use Turbopack when the machine has
the headroom.

---

## What each part does

### `backend/app/ingest`

`universe.py` holds the 101 KSE-100 constituents with their sector, free-float size
tier and index weight, plus the sector economics the rest of the system relies on.

`psx_client.py` implements the live clients against the real PSX Data Portal and
SBP EasyData endpoints — quotes, the end-of-day board, index levels, company
profiles and macro series.

`simulator.py` builds the decade of point-in-time panel data the backtest needs.
See *Data provenance* below for why.

### `backend/app/etl/ratios.py`

Twenty-nine ratios across profitability, liquidity, leverage, efficiency, cash
quality, growth and per-share measures. Flow items are summed over the trailing
four quarters so a seasonal quarter cannot distort a ratio; stock items use the
average of the current and year-ago balance. Every ratio is then stored again as a
winsorised z-score against sector peers in the same period, because a 12% net
margin is excellent for an oil marketing company and poor for a pharmaceutical.

### `backend/app/scoring`

- `fundamental.py` — Piotroski F-Score (all nine tests stored individually with the
  figures behind them) and Altman Z''-Score for emerging markets. Banks and
  insurers get a substituted F-Score template and are excluded from Altman, as
  Altman excluded financials from his own fitting sample.
- `technicals.py` — momentum, volatility, moving averages, RSI, drawdown, traded
  value and rolling beta, all computed strictly from data on or before the as-of
  date.
- `features.py` — the point-in-time cross-section builder. Fundamentals come from
  the newest filing whose `report_date` is on or before the as-of date, never the
  newest `period_end`.
- `composite.py` — five pillars (quality 30%, value 25%, safety 20%, growth 15%,
  momentum 10%) plus hard risk gates that cap the score for distress, weak
  F-Scores, negative equity, losses, thin interest cover and illiquidity.
- `explain.py` — turns the scored row into prose. Every sentence is generated from
  a specific figure in that row, so the explanation and the score cannot disagree.

### `backend/app/ml/ranker.py`

XGBoost `rank:pairwise` with one query group per rebalance date, averaged over a
five-seed ensemble. At rebalance *t* the model may only see snapshots whose
63-day label horizon had already closed. Every fold is recorded so the discipline
can be audited on the dashboard.

### `backend/app/backtest/engine.py`

Quarterly rebalances, equal weights that then drift, commission and slippage on the
traded fraction of the book, a liquidity floor and a sector cap. Reports CAGR,
volatility, Sharpe, Sortino, max drawdown, Calmar, beta, alpha, tracking error,
information ratio, hit rate and turnover.

### `backend/app/api`

FastAPI. `/api/recommendations`, `/api/companies/{ticker}`, `/api/backtest`,
`/api/model`, `/api/sectors`, `/api/market`, and `POST /api/screen` which re-scores
the cross-section under custom pillar weights without refitting anything.

### `frontend`

Next.js 16 App Router, TypeScript, Tailwind v4, Motion and Recharts. Seven routes,
plus a statically generated page for each of the 101 companies:

| Route | What it is for |
|---|---|
| `/` | Today's ranking, headline backtest figures, sector standing, macro backdrop |
| `/screener` | All 101 names, sortable, filterable, re-weightable, exportable as CSV |
| `/compare` | Up to four names on one set of axes: pillar radar, rebased prices, metric scoreboard |
| `/watchlist` | The reader's starred names, with equal-weighted aggregates over the set |
| `/backtest` | Walk-forward evidence: equity curves, drawdown, yearly bars, rebalance log |
| `/model` | ML diagnostics: feature importance, per-fold IC, why the baseline won |
| `/method` | How the engine works, end to end |

The screener's weight sliders re-score the market in the browser from the stored
pillar z-scores, risk caps included, and the CSV export writes out whatever the
current filter, sort and weighting produce. The compare page marks the best value
in every directional row — low wins a multiple, high wins a return — and tallies
the result as a scoreboard, kept deliberately separate from the engine's own call.

The watchlist is `localStorage` only; there are no accounts behind the dashboard.
It is shared across pages through a `useSyncExternalStore` store, so a star
toggled in the screener updates the sidebar count and the compare tray in the
same frame, and a change in another tab arrives through the `storage` event.

**Motion.** `src/components/motion.tsx` holds the primitives — scroll progress,
pointer tilt with a specular highlight, cursor spotlight, parallax, scroll-linked
fade, staggered reveals, word-by-word headline reveal, seamless marquee, magnetic
hover. Everything is scroll- or pointer-driven rather than time-driven, and every
primitive checks `prefers-reduced-motion` and degrades to a static render.
`AuroraCanvas` paints the ambient layer behind every page: drifting aurora blooms
and a node field that repels the cursor, with neighbour linking over a uniform
grid rather than an all-pairs sweep, node count scaled to viewport area and
hard-capped, and the loop stopped entirely when the tab is hidden.

Note there is no `app/loading.tsx`. A loading file at the root wraps every child
segment in one Suspense boundary, and once Next starts streaming, the status code
is already committed — which turns an unknown ticker into a 200 carrying 404
content. Each route that needs a skeleton declares its own; `/company/[ticker]`
has none, so `notFound()` there still answers with a real 404.

---

## Data provenance — read this before quoting any number

**This deployment runs on a simulated point-in-time history of the KSE-100.**

PSX publishes company accounts as PDFs and offers no free, survivorship-free bulk
history of standardised financial statements. A decade of clean panel data cannot
be assembled from its public endpoints, so rather than backtest on data that does
not exist, the project ships a structural simulator:

1. A Pakistan-shaped macro path — SBP policy rate from 5.75% to 22%, CPI peaking
   near 38% in 2023, the rupee from 105 to 286 — drives a common business cycle.
2. Each company carries persistent latent traits: management quality, excess
   growth, gearing appetite, accrual aggressiveness, idiosyncratic volatility.
3. Statements are built top-down and satisfy the accounting identities. Assets
   equal liabilities plus equity to the rupee, working capital is driven to targets
   expressed in days, and gearing reverts to a sector-typical level instead of
   compounding without limit.
4. Prices are pulled toward a fundamental fair value by a mean-reverting force,
   alongside a market factor shaped on the real KSE-100 arc, sector factors and
   idiosyncratic noise. A slow unobservable component shifts each firm's true worth
   away from its reported fundamentals, so the screen sees only part of the story.

Point 4 is what makes the exercise meaningful. Value, quality and momentum carry
genuine but modest predictive power, exactly as in a real market, so the backtest
can neither trivially win nor be pure noise. The resulting index has a 14.3% CAGR
at 15.6% volatility with a −55% worst drawdown, against the real KSE-100's
approximately 14% and 16% with a −49% drawdown over the same span.

Every figure on the dashboard is therefore a simulation result, not a claim about
any real company. What is real is the code: the ratio engine, the scorer, the
explanation generator, the walk-forward protocol and the API all run unchanged
against live data. What a production deployment still needs is the filing parser
that turns published PDFs into standardised statements.

---

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest            # the whole suite
.venv/Scripts/python -m pytest -k piotroski -v
```

Eight modules, no mocking of the engine itself. The fixtures build small panels
by hand - four identical quarters of 1,000 - so an expected TTM figure or margin
is arithmetic a reader can check, not a value copied back out of the code.

| Module | What it pins down |
|---|---|
| `test_fundamental.py` | Piotroski's nine tests and the bank substitutions; Altman Z''-EM against the published coefficients and zone boundaries |
| `test_composite.py` | The 0-100 scale, every risk gate, the band cut-offs, and the rule/model blend |
| `test_ratios.py` | TTM aggregation, averaged stock balances, winsorized sector-relative z-scores |
| `test_features.py` | **Point-in-time discipline** - the guarantee the whole backtest rests on |
| `test_backtest.py` | Selection, liquidity exclusion, the sector cap, weight drift, turnover, and every performance statistic |
| `test_export.py` | The `dashboard.json` contract shared by the API and the dashboard |
| `test_api.py` | Every endpoint, and that `POST /api/screen` agrees with the engine under the engine's own weights |
| `test_repository.py` | That re-running the pipeline replaces a dated cross-section instead of colliding with it |

`test_export.py` and `test_api.py` read the real exported bundle and skip cleanly
if `scripts.run_pipeline` has not been run.

Three of these test claims the project makes about itself, rather than
implementation details:

- **No look-ahead.** `test_picks_the_newest_report_date_not_the_newest_period_end`
  plants a restated quarter filed eight months late and asserts the snapshot
  refuses it until its filing date passes. Selecting on `period_end` instead would
  hand the model accounts nobody had yet seen.
- **A missing year-ago row is not a pass.** Piotroski's five change-based tests
  record `None`, not `False` and certainly not `True`, and the score is rescaled
  over the tests that could actually be assessed - so a newly listed company is
  not flattered by its own short history.
- **Risk caps survive the blend.** A flattering model score cannot lift a name
  with negative equity past its cap, in the scorer or through the API.

### What the suite caught

**A stale bundle had silently disabled both screeners.** `pillarZ` - the raw
pillar z-scores both clients need in order to re-weight the composite - was added
to the exporter *after* the last pipeline run, so the shipped `dashboard.json` had
no such key. Both consumers fell back to a z of zero for every pillar, which
scores every company at exactly 50 and hands the whole ranking to the model.
`POST /api/screen` and the dashboard's weight sliders were therefore inert, and
the output still looked plausible, which is what made it hard to notice.
`test_export.py` now pins the whole bundle contract, including that the z-scores
actually vary across the market and that re-weighting them by hand reproduces the
engine's own rule score.

**The pipeline could only be run once.** Regenerating the bundle then surfaced a
second fault: `save_scores` appended blindly into a table that is unique on
(ticker, asof_date, model_version), so the second `run_pipeline` for the same
as-of date died on the constraint - after the full walk-forward backtest had
already run. Since `run.ps1` calls the pipeline on every plain launch, the
documented way to start the project failed the second time anyone used it.
Re-scoring a date now replaces that date's rows, which is what the operation
always meant; `test_repository.py` covers it.

### Two properties narrower than they look

Both are asserted as they behave, rather than as the docstrings describe them:

- **The sector cap is soft.** `select_portfolio` fills the book under the cap, then
  tops it up with the next best names *without re-checking the cap*. If the
  investable set spans too few sectors to fill `top_n`, the finished book can
  exceed `max_sector_weight`. It never binds in the shipped run - the worst of the
  38 rebalances is 4 of 15, i.e. 27% against a 30% cap, which `test_export.py`
  asserts - but it would bind in a narrower universe.
- **Alpha uses a geometric CAGR in a linear CAPM equation.** A purely geared copy
  of the index books a positive residual, because doubling a log return squares the
  growth factor rather than doubling it. The distortion scales with distance from
  beta 1; at the engine's beta of 0.96 it is negligible.

## Honest limitations

- **One simulated history.** The metrics describe one path. A defensible extension
  is to run the whole pipeline over many seeds and report the distribution of the
  information ratio rather than a point estimate.
- **No survivorship modelling.** The universe is the KSE-100 as it stands; real
  index recomposition adds and drops names over time.
- **Fills are assumed.** Every order fills at the rebalance day's close. Market
  impact from scaling the book is not modelled.
- **Quarterly horizon only.** Nothing here says anything about a holding period
  shorter than a quarter or longer than a year.
- **Macro and news are not inputs yet.** The policy rate reaches the model only
  through the fair-value multiple and two features. Sentiment analysis remains a
  stretch goal.

## Regulatory position

Distributing personalised investment recommendations in Pakistan falls under the
SECP's investment-advisory framework, including its Securities Managers and digital
advisory regimes. This is an academic research prototype: a mechanical ranking with
its reasoning attached, not tailored to anyone's circumstances and not offered as
advice. Distribution through broker platforms would need to be licensed first,
which is future work rather than an implementation step.

**Not investment advice.**

---

## Layout

```
psx-advisor/
├── backend/
│   ├── app/
│   │   ├── api/routes.py            REST endpoints
│   │   ├── backtest/engine.py       walk-forward portfolio simulation
│   │   ├── db/                      SQLAlchemy schema + bulk load helpers
│   │   ├── etl/ratios.py            TTM ratios + sector-relative z-scores
│   │   ├── ingest/                  universe, live PSX/SBP clients, simulator
│   │   ├── ml/ranker.py             walk-forward XGBoost ranker
│   │   ├── scoring/                 Piotroski, Altman, technicals, composite, explain
│   │   ├── config.py                every tunable in one place
│   │   └── main.py                  FastAPI app
│   ├── scripts/
│   │   ├── build_dataset.py         build the panel into the database
│   │   └── run_pipeline.py          analyse, backtest, score, export
│   └── data/
│       ├── psx.db                   SQLite (set PSX_DATABASE_URL for PostgreSQL)
│       └── exports/                 dashboard.json + companies/*.json
└── frontend/
    ├── src/app/                     overview, screener, compare, watchlist,
    │                                backtest, model, method, company/[ticker]
    ├── src/components/              shell, ticker tape, charts, UI primitives,
    │   │                            motion primitives, aurora canvas, page views
    │   ├── motion.tsx               tilt, spotlight, parallax, stagger, marquee
    │   └── AuroraCanvas.tsx         the animated ambient layer
    ├── src/lib/watchlist.ts         localStorage store shared across pages
    └── public/data/                 the exported analysis the pages read
```

## Switching to PostgreSQL

```bash
set PSX_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/psx
python -m scripts.build_dataset --reset
```

Nothing else changes; the schema is declared once in `app/db/models.py`.
