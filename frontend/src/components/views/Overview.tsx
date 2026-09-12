"use client";

import Link from "next/link";
import { motion } from "motion/react";
import {
  ArrowUpRight, Award, Building2, Gauge, ShieldCheck, Sparkles, Target, TrendingUp,
} from "lucide-react";

import { EquityChart, MacroChart } from "@/components/charts";
import {
  Parallax, ScrollFade, Spotlight, Stagger, Tilt, WordReveal,
} from "@/components/motion";
import { WatchButton } from "@/components/WatchButton";
import {
  AnimatedNumber, Card, Meter, Reveal, ScoreRing, SectionTitle, Sparkline,
} from "@/components/ui";
import {
  bandClass, longDate, mult, num, pct, rupees, scoreColor, signedPct,
} from "@/lib/format";
import type { Dashboard } from "@/lib/types";

const BAND_ORDER = ["STRONG BUY", "BUY", "HOLD", "REDUCE", "AVOID"] as const;

export function Overview({ data }: { data: Dashboard }) {
  const { meta, recommendations, sectors, performance, equityCurve, bands, market } = data;
  const blended = performance.find((p) => p.key === "blended");
  const bench = performance.find((p) => p.key === "KSE100");
  const rule = performance.find((p) => p.key === "rule");

  const topPicks = recommendations.slice(0, 8);
  const totalBands = BAND_ORDER.reduce((a, b) => a + (bands[b] ?? 0), 0) || 1;

  const tiles = [
    {
      label: "Engine CAGR",
      value: blended?.cagr ?? 0,
      display: <AnimatedNumber value={(blended?.cagr ?? 0) * 100} decimals={2} suffix="%" />,
      foot: `KSE-100 returned ${pct(bench?.cagr, 2)} a year over the same window`,
      delta: (blended?.cagr ?? 0) - (bench?.cagr ?? 0),
      icon: TrendingUp,
    },
    {
      label: "Annual alpha",
      value: blended?.alpha_annual ?? 0,
      display: <AnimatedNumber value={(blended?.alpha_annual ?? 0) * 100} decimals={2} suffix="%" />,
      foot: `Beta ${num(blended?.beta, 2)} against the index, so this is selection, not gearing`,
      delta: blended?.alpha_annual ?? 0,
      icon: Sparkles,
    },
    {
      label: "Information ratio",
      value: blended?.information_ratio ?? 0,
      display: <AnimatedNumber value={blended?.information_ratio ?? 0} decimals={2} />,
      foot: `${pct(blended?.tracking_error, 1)} tracking error against the benchmark`,
      delta: blended?.information_ratio ?? 0,
      icon: Target,
    },
    {
      label: "Quarters ahead",
      value: blended?.hit_rate ?? 0,
      display: <AnimatedNumber value={(blended?.hit_rate ?? 0) * 100} decimals={0} suffix="%" />,
      foot: `Beat the index in ${blended?.quarters_beating_benchmark ?? 0} of ${blended?.quarters_evaluated ?? 0} rebalance periods`,
      delta: (blended?.hit_rate ?? 0) - 0.5,
      icon: Award,
    },
  ];

  return (
    <div className="flex flex-col gap-9">
      {/* ---------------- hero ---------------- */}
      <ScrollFade>
        <header className="relative">
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="pill" style={{ background: "var(--surface-2)", color: "var(--brand)" }}>
                <span className="pulse-dot h-1.5 w-1.5 rounded-full" style={{ background: "var(--brand)" }} />
                {meta.universe} · {meta.universeSize} companies
              </span>
              <span className="pill" style={{ background: "var(--surface)", color: "var(--text-muted)" }}>
                Scored {longDate(meta.asOf)}
              </span>
              <span className="pill" style={{ background: "var(--surface)", color: "var(--text-dim)" }}>
                Rebalanced {meta.rebalance.toLowerCase()}
              </span>
            </div>

            <h1 className="max-w-4xl text-[30px] font-semibold leading-[1.12] tracking-tight sm:text-[40px]">
              <WordReveal text="Every KSE-100 company, scored on its own accounts" />{" "}
              <WordReveal
                text="and explained in plain language."
                delay={0.5}
                className="gradient-pan block bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(94deg, var(--brand), var(--brand-2) 45%, var(--brand-3) 70%, var(--brand) 100%)",
                }}
              />
            </h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.95, duration: 0.7 }}
              className="max-w-2xl text-[14px] leading-relaxed"
              style={{ color: "var(--text-muted)" }}
            >
              The engine reads income statements, balance sheets and cash flows, converts them into
              sector-relative ratios, and ranks the market on five pillars. A machine-learning ranker
              is trained walk-forward alongside it. Nothing here is a black box: every recommendation
              opens onto the figures that produced it.
            </motion.p>
          </motion.div>
        </header>
      </ScrollFade>

      {/* ---------------- KPI tiles ---------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {tiles.map((t, i) => {
          const Icon = t.icon;
          const positive = t.delta >= 0;
          return (
            <Reveal key={t.label} delay={i * 0.07}>
              <Tilt max={8} className="h-full">
                <Card hover className="relative h-full overflow-hidden">
                  <div className="flex items-start justify-between gap-3">
                    <span className="label">{t.label}</span>
                    <motion.span
                      className="grid h-7 w-7 place-items-center rounded-lg"
                      style={{
                        background: positive ? "var(--pos-dim)" : "var(--neg-dim)",
                        color: positive ? "var(--pos)" : "var(--neg)",
                      }}
                      animate={{ y: [0, -3, 0] }}
                      transition={{
                        duration: 3.4,
                        repeat: Infinity,
                        ease: "easeInOut",
                        delay: i * 0.35,
                      }}
                    >
                      <Icon size={14} />
                    </motion.span>
                  </div>
                  <p className="num sheen relative mt-3 overflow-hidden text-[30px] font-semibold leading-none">
                    {t.display}
                  </p>
                  <p className="mt-2.5 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                    {t.foot}
                  </p>
                </Card>
              </Tilt>
            </Reveal>
          );
        })}
      </div>

      {/* ---------------- equity curve ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<Gauge size={16} />}
            title="Walk-forward performance against the KSE-100"
            subtitle={`Rs 100 invested at each strategy's first rebalance on ${longDate(meta.backtestStart)}, held through ${longDate(meta.backtestEnd)}. Costs of ${meta.costBps} basis points per round trip are charged at every rebalance.`}
            right={
              <Link
                href="/backtest"
                className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
                style={{ color: "var(--text-muted)" }}
              >
                Full backtest <ArrowUpRight size={12} />
              </Link>
            }
          />
          <EquityChart
            data={equityCurve as unknown as Record<string, number | string | null>[]}
            series={[
              { key: "blended", label: "Blended engine" },
              { key: "rule", label: "Rule-based score" },
              { key: "ml", label: "ML ranker" },
              { key: "KSE100", label: "KSE-100" },
            ]}
            height={340}
          />
          <div className="mt-5 grid gap-3 border-t pt-4 sm:grid-cols-3" style={{ borderColor: "var(--line)" }}>
            {[
              { k: "Blended engine", p: blended, c: "#6d8dff" },
              { k: "Rule-based only", p: rule, c: "#34d399" },
              { k: "KSE-100 benchmark", p: bench, c: "#8b95ad" },
            ].map(({ k, p, c }) => (
              <div key={k} className="flex items-center gap-3">
                <span className="h-8 w-[3px] rounded-full" style={{ background: c }} />
                <div>
                  <p className="text-[11.5px]" style={{ color: "var(--text-muted)" }}>{k}</p>
                  <p className="num text-[15px] font-semibold">
                    {pct(p?.cagr, 2)}{" "}
                    <span className="text-[11px] font-normal" style={{ color: "var(--text-dim)" }}>
                      a year · {pct(p?.max_drawdown, 0)} worst drawdown
                    </span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </Reveal>

      {/* ---------------- top picks ---------------- */}
      <section>
        <SectionTitle
          icon={<Sparkles size={16} />}
          title="Top-ranked names today"
          subtitle="The highest composite scores in the current cross-section. Open any card for the accounts, the screens and the reasoning behind the rank."
          right={
            <Link
              href="/screener"
              className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
              style={{ color: "var(--text-muted)" }}
            >
              All {meta.universeSize} names <ArrowUpRight size={12} />
            </Link>
          }
        />
        <Stagger className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" step={0.06}>
          {topPicks.map((r, i) => (
            <Spotlight key={r.ticker} className="h-full rounded-2xl">
              <Link href={`/company/${r.ticker}`} className="block h-full focus-ring rounded-2xl">
                <Card hover className="h-full">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="num flex items-center gap-1.5 text-[15px] font-semibold tracking-tight">
                        {r.ticker}
                        {i === 0 && (
                          <span
                            className="pill px-1.5 py-0 text-[9px]"
                            style={{ color: "var(--warn)", borderColor: "rgba(251,191,36,.3)" }}
                          >
                            #1
                          </span>
                        )}
                      </p>
                      <p className="truncate text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                        {r.name}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <span className={`pill ${bandClass(r.recommendation)}`}>{r.recommendation}</span>
                      <WatchButton ticker={r.ticker} size={13} />
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <ScoreRing score={r.finalScore} size={76} stroke={6}
                               color={scoreColor(r.finalScore)} label="score" />
                    <div className="flex-1">
                      <Sparkline data={r.spark} width={112} height={34} />
                      <p className="num mt-1 text-right text-[11px]"
                         style={{ color: (r.return12m ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
                        {signedPct(r.return12m, 1)} <span style={{ color: "var(--text-dim)" }}>1y</span>
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 grid grid-cols-3 gap-2 border-t pt-3 text-center"
                       style={{ borderColor: "var(--line)" }}>
                    {[
                      { l: "Price", v: rupees(r.price, 1) },
                      { l: "P/E", v: mult(r.pe, 1) },
                      { l: "ROE", v: pct(r.roe, 0) },
                    ].map((m) => (
                      <div key={m.l}>
                        <p className="label text-[9px]">{m.l}</p>
                        <p className="num mt-0.5 text-[12.5px]">{m.v}</p>
                      </div>
                    ))}
                  </div>

                  <p className="mt-3 line-clamp-2 text-[11.5px] leading-relaxed"
                     style={{ color: "var(--text-dim)" }}>
                    {r.summary}
                  </p>
                </Card>
              </Link>
            </Spotlight>
          ))}
        </Stagger>
      </section>

      {/* ---------------- bands + sectors ---------------- */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.45fr)]">
        <Reveal>
          <Card className="h-full">
            <SectionTitle
              icon={<ShieldCheck size={16} />}
              title="How the market splits"
              subtitle="Bands are percentile cut-offs of the composite score, so they always describe relative standing inside the index."
            />
            <div className="flex flex-col gap-3">
              {BAND_ORDER.map((b, i) => {
                const count = bands[b] ?? 0;
                const share = count / totalBands;
                const color =
                  b === "STRONG BUY" ? "#34d399" : b === "BUY" ? "#86efac"
                  : b === "HOLD" ? "#94a3b8" : b === "REDUCE" ? "#fbbf24" : "#fb7185";
                return (
                  <div key={b}>
                    <div className="mb-1.5 flex items-center justify-between text-[12px]">
                      <span className={`pill ${bandClass(b)}`}>{b}</span>
                      <span className="num" style={{ color: "var(--text-muted)" }}>
                        {count} <span style={{ color: "var(--text-dim)" }}>· {pct(share, 0)}</span>
                      </span>
                    </div>
                    <Meter value={share * 100} color={color} delay={i * 0.08} />
                  </div>
                );
              })}
            </div>
            <p className="mt-4 border-t pt-3 text-[11px] leading-relaxed"
               style={{ borderColor: "var(--line)", color: "var(--text-dim)" }}>
              A name in the distress zone of the Altman score, or with a Piotroski F-Score of three
              or less, has its composite capped regardless of how cheap it looks.
            </p>
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="h-full">
            <SectionTitle
              icon={<Building2 size={16} />}
              title="Sector standing"
              subtitle="Average composite score across the constituents of each sector, with the median valuation and profitability behind it."
            />
            <div className="-mx-1 overflow-x-auto">
              <table className="w-full min-w-[460px] text-[12.5px]">
                <thead>
                  <tr className="label" style={{ color: "var(--text-dim)" }}>
                    <th className="px-1 pb-2 text-left font-semibold">Sector</th>
                    <th className="px-1 pb-2 text-right font-semibold">Names</th>
                    <th className="px-1 pb-2 text-right font-semibold">Buys</th>
                    <th className="px-1 pb-2 text-right font-semibold">P/E</th>
                    <th className="px-1 pb-2 text-right font-semibold">ROE</th>
                    <th className="px-1 pb-2 pl-3 text-left font-semibold">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {sectors.slice(0, 11).map((s, i) => (
                    <tr key={s.sector} className="border-t" style={{ borderColor: "var(--line)" }}>
                      <td className="px-1 py-2 pr-3">
                        <span className="block truncate" style={{ maxWidth: 170 }}>{s.sector}</span>
                      </td>
                      <td className="num px-1 py-2 text-right" style={{ color: "var(--text-muted)" }}>{s.count}</td>
                      <td className="num px-1 py-2 text-right"
                          style={{ color: s.buys > 0 ? "var(--pos)" : "var(--text-dim)" }}>{s.buys}</td>
                      <td className="num px-1 py-2 text-right" style={{ color: "var(--text-muted)" }}>{num(s.medianPe, 1)}</td>
                      <td className="num px-1 py-2 text-right" style={{ color: "var(--text-muted)" }}>{pct(s.medianRoe, 0)}</td>
                      <td className="py-2 pl-3">
                        <div className="flex items-center gap-2">
                          <Meter value={s.avgScore} color={scoreColor(s.avgScore)} height={5} delay={i * 0.04} />
                          <span className="num w-7 text-right text-[11.5px]">{num(s.avgScore, 0)}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </Reveal>
      </div>

      {/* ---------------- macro ---------------- */}
      <Parallax distance={26}>
        <Reveal>
          <Card padding="p-5 sm:p-6">
            <SectionTitle
              icon={<TrendingUp size={16} />}
              title="The macro backdrop the scores sit inside"
              subtitle="The policy rate feeds directly into the model: a higher rate compresses the multiple a company deserves, and raises the hurdle every recommendation has to clear."
            />
            <MacroChart data={market.macro} height={250} />
          </Card>
        </Reveal>
      </Parallax>

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        {meta.disclaimer}
      </p>
    </div>
  );
}
