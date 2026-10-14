# PSX Alpha

[![License: All rights reserved](https://img.shields.io/badge/License-All_rights_reserved-4f46e5.svg)](./LICENSE)
[![Live Dashboard](https://img.shields.io/badge/Live_Dashboard-Open-4f46e5.svg)](https://psxalpha.twinstackstudio.com)

An AI-driven stock research engine for the Pakistan Stock Exchange. PSX Alpha
reads the published accounts of every KSE-100 company, scores and ranks them,
explains each recommendation in plain language, and tests the ranking against
the index with a walk-forward backtest.

[**Open the live dashboard**](https://psxalpha.twinstackstudio.com) ·
[**Work with TwinStack Studio**](https://twinstackstudio.com/contact)

![PSX Alpha dashboard overview](./assets/psx-alpha.png)

> **Note:** The dashboard runs on a simulated ten-year history of the KSE-100,
> not on real company filings. PSX publishes accounts as PDFs and offers no free
> bulk history, so every figure shown is a simulation result and not a claim
> about any real company. This is a research project and **not investment
> advice**.

## Results

Walk-forward backtest from July 2016 to December 2025. The 15 top-ranked
companies are bought in equal weights and rebalanced every quarter, with 50
basis points charged per round trip, a 30% cap per sector and illiquid names
excluded.

| Strategy | Yearly return (CAGR) | Sharpe | Max drawdown | Information ratio |
| --- | --- | --- | --- | --- |
| **Blended engine** | **21.21%** | 0.56 | −53.3% | **0.83** |
| Rule-based score | 19.48% | 0.46 | −50.0% | 0.62 |
| Machine-learning ranker alone | 16.85% | 0.30 | −54.7% | 0.29 |
| KSE-100 index | 14.34% | 0.18 | −55.5% | — |

The blended engine beat the index by 6.98% a year at a beta of 0.96, so the
extra return comes from stock selection and not from extra market risk. The
rule-based score beat the machine-learning model on its own; the Model page of
the dashboard explains why.

## What the product delivers

### Dashboard

- **Overview:** today's ranking, headline backtest figures, sector standings and the macro backdrop
- **Screener:** all 101 companies, sortable and filterable, with sliders that re-weight the score live in the browser and a CSV export
- **Company pages:** a page for each company with its score, the five pillars behind it and a plain-language explanation
- **Compare:** up to four companies side by side on a radar chart, price history and a metric scoreboard
- **Watchlist:** starred companies saved in the browser, with totals for the set
- **Backtest:** equity curves, drawdowns, yearly returns and every rebalance
- **Model and Method:** how the engine works and how the machine-learning model performed in each period

### Research engine

- **Five scoring pillars:** quality 30%, value 25%, safety 20%, growth 15% and momentum 10%, each measured against sector peers
- **Established credit and quality tests:** Piotroski F-Score and Altman Z''-Score for emerging markets, with separate rules for banks and insurers
- **Risk gates:** cap the score of companies with signs of distress, negative equity, losses, weak interest cover or thin trading
- **Machine-learning ranker:** XGBoost, retrained every quarter using only data available at the time, then blended 65/35 with the rule-based score
- **Plain-language explanations:** every sentence is generated from a specific figure, so the explanation always matches the score
- **REST API:** FastAPI endpoints for recommendations, companies, sectors, the backtest, the model and custom screening

### Engineering highlights

- **No look-ahead:** the model sees a company's accounts only after their filing date, not after the period they cover. A test plants a late restatement and checks it stays hidden until it is filed
- **Twenty-nine financial ratios:** built from trailing twelve-month figures, then compared within each sector, because a good margin for an oil marketer is a poor one for a drug maker
- **Realistic costs:** the backtest charges commission and slippage on every trade and lets weights drift between rebalances
- **Fast dashboard:** it reads a pre-computed analysis bundle and is fully static, so it loads fast and a page view never retrains a model
- **241 automated tests:** fixtures are small hand-built datasets, so expected values can be checked by hand; CI rebuilds the dataset and runs the full pipeline before testing

## Technology

| Layer | Stack |
| --- | --- |
| Dashboard | Next.js 16 (App Router), React 19, TypeScript |
| Styling and charts | Tailwind CSS 4, Motion, Recharts |
| API | Python 3.12, FastAPI |
| Analysis | pandas, NumPy, SciPy, scikit-learn, XGBoost |
| Data | SQLAlchemy with SQLite (PostgreSQL supported) |
| Tests | pytest |
| Hosting | Vercel |

## Limitations

- **Simulated data:** the results describe one simulated history. Running live needs a parser that turns PSX's PDF filings into standard statements
- **Fixed company list:** the universe is today's KSE-100. Companies that joined or left the index over time are not modelled
- **Simple trading assumptions:** every order fills at the closing price, and large trades are assumed not to move the market
- **Quarterly horizon only:** nothing here speaks to holding periods shorter than a quarter
- **Regulation:** offering personal investment advice in Pakistan needs an SECP licence, so this project ranks companies for research only

## Architecture

```mermaid
flowchart LR
  D[Company accounts<br/>simulated 10-year KSE-100] --> E[ETL<br/>29 TTM ratios, sector-relative]
  E --> R[Rule score<br/>5 pillars · Piotroski · Altman · risk gates]
  E --> X[XGBoost ranker<br/>retrained quarterly, no look-ahead]
  R --> B[Blend 65/35]
  X --> B
  B --> BT[Walk-forward backtest<br/>costs · sector caps]
  B --> API[FastAPI REST]
  BT --> BUN[Analysis bundle]
  BUN --> UI[Next.js static dashboard]
```

## Source code

This is the public showcase. The source code is kept in a private repository. Try the live demo above, and [contact TwinStack Studio](https://twinstackstudio.com/contact) for a walkthrough or a similar project.

## Built by TwinStack Studio

TwinStack Studio builds full-stack websites, web applications, dashboards,
portals, automation, and AI-powered products.

[GitHub](https://github.com/twinstack-studio) ·
[Website](https://twinstackstudio.com) ·
[Email](mailto:hello@twinstackstudio.com)

© 2026 TwinStack Studio. All rights reserved. See [LICENSE](./LICENSE).
