"use client";

import {
  BookOpen, Calculator, Database, GitBranch, Landmark, Scale, ShieldAlert, Workflow,
} from "lucide-react";

import { Card, Meter, Reveal, SectionTitle } from "@/components/ui";
import { pct, PILLAR_SHORT } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

const PIPELINE = [
  { k: "Ingest", d: "PSX filings and end-of-day prices, SBP macro series. Every filing is stored with both the period it describes and the date it was published." },
  { k: "Standardise", d: "Line items are mapped onto one chart of accounts so a bank, a cement maker and a refinery can be compared without pretending they are the same business." },
  { k: "Derive", d: "Twenty-nine ratios on a trailing-twelve-month basis, then a winsorised z-score of each against sector peers in the same period." },
  { k: "Score", d: "Five pillars combine into a 0-100 composite. Piotroski and Altman fold into quality and safety, and hard risk rules cap the result." },
  { k: "Rank", d: "A gradient-boosted ranker is retrained walk-forward on the same features and blended into the composite." },
  { k: "Explain", d: "The metrics that moved the score the most are turned into sentences, with the figures that produced them attached." },
  { k: "Validate", d: "The whole thing is replayed quarter by quarter against the KSE-100, paying costs and respecting liquidity." },
];

const PILLAR_DETAIL: Record<string, { what: string; inputs: string }> = {
  quality: {
    what: "Whether the business earns a real return on the capital it employs, and whether the profit it reports turns into cash.",
    inputs: "Return on equity, assets and invested capital, net and operating margin, cash conversion, accrual ratio, free cash flow margin, Piotroski F-Score.",
  },
  value: {
    what: "What you pay for that stream of earnings relative to what sector peers cost.",
    inputs: "P/E, P/B, P/S, EV/EBITDA, earnings yield, free cash flow yield, dividend yield.",
  },
  safety: {
    what: "Whether the balance sheet can survive a bad year without diluting or defaulting.",
    inputs: "Debt to equity, interest cover, net debt to EBITDA, current ratio, equity to assets, Altman Z''-Score.",
  },
  growth: {
    what: "Whether the business is getting bigger, and whether the growth reaches the bottom line.",
    inputs: "Trailing revenue and earnings growth, three-year revenue CAGR, equity growth.",
  },
  momentum: {
    what: "Whether the market has already started agreeing, which historically persists over months.",
    inputs: "12-1 month momentum, price against the 200-day average, six-month relative strength, three-month return, one-year volatility.",
  },
};

export function Method({ data }: { data: Dashboard }) {
  const { meta } = data;
  const weights = meta.compositeWeights;

  return (
    <div className="flex flex-col gap-7">
      <SectionTitle
        icon={<BookOpen size={16} />}
        title="How the engine works"
        subtitle="Everything the dashboard shows is produced by the pipeline described here. No step is hidden, and each one can be re-run from the command line."
      />

      {/* ---------------- problem ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <h3 className="text-[15px] font-semibold">The problem this addresses</h3>
          <p className="mt-2.5 max-w-3xl text-[13.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Around 527 companies list on the Pakistan Stock Exchange, and all of them publish audited
            accounts. Almost none of that information reaches a retail investor in a usable form. The
            gap is filled by brokers, whose revenue comes from commission on trades rather than from
            the outcome of those trades, so the incentive to recommend activity is structural rather
            than personal.
          </p>
          <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            The engine is an attempt to close that gap mechanically: read the accounts every company
            already files, rank the market on the evidence, and say in plain language why each name
            sits where it does. It is scoped to the KSE-100 rather than the full market because index
            constituents have the cleanest, most complete filings and enough traded volume for a
            recommendation to be actionable.
          </p>
        </Card>
      </Reveal>

      {/* ---------------- pipeline ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<Workflow size={16} />} title="The pipeline" />
          <div className="flex flex-col gap-2">
            {PIPELINE.map((s, i) => (
              <div key={s.k} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <span
                    className="num grid h-8 w-8 shrink-0 place-items-center rounded-full border text-[11px] font-semibold"
                    style={{
                      borderColor: "var(--line-strong)",
                      background: "var(--surface-2)",
                      color: "var(--brand)",
                    }}
                  >
                    {i + 1}
                  </span>
                  {i < PIPELINE.length - 1 && (
                    <span className="w-px flex-1" style={{ background: "var(--line)" }} />
                  )}
                </div>
                <div className="pb-5">
                  <p className="text-[13.5px] font-medium">{s.k}</p>
                  <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    {s.d}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>

      {/* ---------------- point in time ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<GitBranch size={16} />}
            title="Point-in-time discipline"
            subtitle="The single assumption that separates a real backtest from a flattering one."
          />
          <p className="max-w-3xl text-[13.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            A company&apos;s December quarter describes December, but nobody could read it until the
            accounts were filed. Scoring December using December&apos;s numbers on the first of January
            would hand the model information it could not have had, and it is the most common reason a
            stock screen looks brilliant on paper and disappoints in practice.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {[
              { l: "Annual accounts", v: "120 days", d: "Filing deadline used as the date an annual report becomes usable." },
              { l: "Quarterly accounts", v: "45 days", d: "The equivalent lag applied to interim filings." },
              { l: "Label horizon", v: `${data.ml.labelHorizonDays} days`, d: "The model may only train on a quarter whose return had already been realised." },
            ].map((x) => (
              <div key={x.l} className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
                <p className="label">{x.l}</p>
                <p className="num mt-1.5 text-[19px] font-semibold" style={{ color: "var(--brand)" }}>{x.v}</p>
                <p className="mt-1.5 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>{x.d}</p>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>

      {/* ---------------- pillars ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<Calculator size={16} />}
            title="The five pillars"
            subtitle="Each pillar is the mean of its sector-relative z-scores, mapped so that 50 is the sector average and three standard deviations reaches either end of the scale."
          />
          <div className="flex flex-col gap-4">
            {(Object.keys(weights) as (keyof typeof weights)[]).map((k, i) => (
              <div key={k} className="rounded-xl border p-4" style={{ borderColor: "var(--line)" }}>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[13.5px] font-medium">{meta.pillarLabels[k] ?? PILLAR_SHORT[k]}</p>
                  <span className="num text-[12px]" style={{ color: "var(--brand)" }}>
                    {pct(weights[k], 0)} of the composite
                  </span>
                </div>
                <Meter value={weights[k] * 100 * 3} color="var(--brand)" height={4} delay={i * 0.07} />
                <p className="mt-3 text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                  {PILLAR_DETAIL[k]?.what}
                </p>
                <p className="mt-1.5 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                  {PILLAR_DETAIL[k]?.inputs}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>

      {/* ---------------- screens ---------------- */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Reveal>
          <Card className="h-full" padding="p-5">
            <SectionTitle icon={<Scale size={16} />} title="Piotroski F-Score" />
            <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Nine binary tests of whether a business improved on itself over the past year: is it
              profitable, is it cash generative, are returns rising, is profit backed by cash, is
              leverage falling, is liquidity improving, has it avoided issuing shares, is the margin
              widening, and are assets working harder.
            </p>
            <p className="mt-3 text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Banks and insurers have no gross margin, no inventory and no meaningful current ratio,
              so the three tests that depend on them are replaced with lender equivalents: capital
              strengthening, spread widening and balance-sheet productivity. Where a test cannot be
              assessed at all, it is recorded as such rather than silently counted as a pass.
            </p>
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="h-full" padding="p-5">
            <SectionTitle icon={<ShieldAlert size={16} />} title="Altman Z''-Score" />
            <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              The original 1968 Z-Score was fitted on US manufacturers. The engine uses Altman&apos;s
              later emerging-market variant, which drops the sales-to-assets term that penalises
              asset-heavy firms, uses book rather than market equity, and adds a constant so the
              scale is comparable across markets. Above 5.85 is sound, below 4.15 is distress.
            </p>
            <p className="mt-3 text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Financial companies are excluded from the Altman score entirely, as Altman himself
              excluded them: working capital and asset turnover do not describe a balance-sheet
              lender. Those names are assessed on capital adequacy and interest cover instead.
            </p>
          </Card>
        </Reveal>
      </div>

      {/* ---------------- risk gates ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<ShieldAlert size={16} />}
            title="Risk gates"
            subtitle="Rules that override a flattering composite. A statistically cheap company in trouble is not a buy, and the score is not allowed to say otherwise."
          />
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              ["Altman Z in the distress zone", "capped at 45"],
              ["Piotroski F-Score of 3 or less", "capped at 50"],
              ["Negative shareholders' equity", "capped at 25"],
              ["Loss-making over the trailing year", "capped at 55"],
              ["Operating profit below 1.5x finance cost", "capped at 50"],
              ["Median traded value under Rs 5m a day", "capped at 60"],
            ].map(([rule, cap]) => (
              <div key={rule} className="flex items-center gap-3 rounded-xl border px-4 py-3"
                   style={{ borderColor: "var(--line)" }}>
                <span className="flex-1 text-[12.5px]">{rule}</span>
                <span className="pill" style={{ color: "var(--warn)", background: "var(--warn-dim)", borderColor: "transparent" }}>
                  {cap}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>

      {/* ---------------- data provenance ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<Database size={16} />} title="Where the numbers come from" />
          <div className="rounded-xl border p-4"
               style={{ borderColor: "rgba(251,191,36,.28)", background: "rgba(251,191,36,.05)" }}>
            <p className="text-[13px] font-semibold" style={{ color: "var(--warn)" }}>
              This deployment runs on a simulated point-in-time history of the KSE-100.
            </p>
            <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              PSX publishes company accounts as PDFs and offers no free, survivorship-free bulk
              history of standardised financial statements, so a decade of clean panel data cannot
              be assembled from its public endpoints. Rather than backtest on data that does not
              exist, the project ships a structural simulator: a Pakistan-shaped macro path drives
              a business cycle, each company carries persistent latent traits, statements are built
              to satisfy the accounting identities, and prices are pulled toward a fundamental fair
              value by a mean-reverting force alongside market and sector factors.
            </p>
            <p className="mt-2 text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              That makes every figure on this dashboard a simulation result, not a claim about any
              real company. What is real is the code: the ratio engine, the scorer, the explanation
              generator, the walk-forward protocol and the API all run unchanged against live data.
              The live PSX and SBP clients are implemented and cover quotes, index levels and
              company profiles; what a production deployment still needs is the filing parser that
              turns published PDFs into the standardised statements this pipeline consumes.
            </p>
          </div>
        </Card>
      </Reveal>

      {/* ---------------- regulation ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<Landmark size={16} />} title="Regulatory position" />
          <p className="max-w-3xl text-[13.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Distributing personalised investment recommendations to the public in Pakistan falls
            under the SECP&apos;s investment-advisory framework, including its Securities Managers and
            digital advisory regimes. This project is an academic research prototype: it produces a
            mechanical ranking with its reasoning attached, it is not tailored to any individual&apos;s
            circumstances, and it is not offered as advice. Any move toward distribution through
            broker platforms would need to be licensed first, which sits outside the scope of the
            final year project and is noted here as future work rather than an implementation step.
          </p>
        </Card>
      </Reveal>

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        {meta.disclaimer} Generated {meta.generatedAt.replace("T", " ")} · universe {meta.universe} ·
        history {meta.historyStart} to {meta.historyEnd} · model {meta.mlBackend}.
      </p>
    </div>
  );
}
