"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "motion/react";
import {
  AlertTriangle, ArrowLeft, Check, CircleSlash, Gauge, GitCompareArrows, Minus,
  ScrollText, ShieldCheck, Sparkles, TrendingUp, Users,
} from "lucide-react";

import { PillarRadar, PriceChart } from "@/components/charts";
import { Spotlight, Tilt } from "@/components/motion";
import { WatchButton } from "@/components/WatchButton";
import {
  AnimatedNumber, Card, Meter, Reveal, ScoreRing, SectionTitle, Tabs,
} from "@/components/ui";
import {
  bandClass, longDate, mult, num, pct, pkrM, rupees, scoreColor, signedPct,
} from "@/lib/format";
import type { CompanyDetail, Recommendation } from "@/lib/types";

const Z_COMPONENT_LABELS: Record<string, string> = {
  working_capital_to_assets: "Working capital / assets",
  retained_earnings_to_assets: "Retained earnings / assets",
  ebit_to_assets: "Operating profit / assets",
  equity_to_liabilities: "Equity / liabilities",
  sales_to_assets: "Sales / assets",
};

export function Company({
  detail, row, universeSize,
}: {
  detail: CompanyDetail;
  row: Recommendation;
  universeSize: number;
}) {
  const ex = detail.explanation;
  const [statement, setStatement] = useState("income");

  const fTests = Object.values(ex.f_tests ?? {});
  const passed = fTests.filter((t) => t.passed === true).length;
  const assessed = fTests.filter((t) => t.passed !== null).length;

  const financials = [...detail.financials].reverse();
  const ratios = [...detail.ratioHistory].reverse();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/screener"
          className="inline-flex w-fit items-center gap-1.5 text-[12.5px] transition-colors focus-ring rounded"
          style={{ color: "var(--text-dim)" }}
        >
          <ArrowLeft size={13} /> Back to the screener
        </Link>
        <div className="flex items-center gap-2">
          <Link
            href="/compare"
            className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
            style={{ color: "var(--text-muted)" }}
          >
            <GitCompareArrows size={12} /> Compare
          </Link>
          <span
            className="pill gap-1.5"
            style={{ background: "var(--surface)", color: "var(--text-muted)" }}
          >
            <WatchButton ticker={detail.ticker} size={12} className="-ml-1 p-0" /> Watch
          </span>
        </div>
      </div>

      {/* ---------------- header ---------------- */}
      <Reveal y={10}>
        <Tilt max={3.5} glare scale={1}>
        <Card padding="p-5 sm:p-6">
          <div className="flex flex-wrap items-start gap-x-8 gap-y-5">
            <div className="min-w-[220px] flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="num text-[26px] font-semibold tracking-tight">{detail.ticker}</h1>
                <span className={`pill ${bandClass(ex.recommendation)}`}>{ex.recommendation}</span>
                {row.zZone === "distress" && (
                  <span className="pill" style={{ color: "var(--neg)", background: "var(--neg-dim)", borderColor: "transparent" }}>
                    <AlertTriangle size={11} /> Distress zone
                  </span>
                )}
              </div>
              <p className="mt-1 text-[15px]">{detail.name}</p>
              <p className="mt-0.5 text-[12px]" style={{ color: "var(--text-dim)" }}>
                {detail.sector}
                {detail.indexWeight !== null && ` · ${pct(detail.indexWeight, 2)} of the KSE-100`}
              </p>

              <div className="mt-5 flex flex-wrap gap-x-7 gap-y-3">
                {[
                  { l: "Price", v: rupees(row.price, 2) },
                  { l: "Market cap", v: pkrM(row.marketCap) },
                  { l: "12-month return", v: signedPct(row.return12m, 1),
                    c: (row.return12m ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" },
                  { l: "Rank", v: `${row.rank} of ${universeSize}` },
                ].map((m) => (
                  <div key={m.l}>
                    <p className="label">{m.l}</p>
                    <p className="num mt-0.5 text-[15px] font-medium" style={{ color: m.c }}>{m.v}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-6">
              <ScoreRing score={row.finalScore} size={108} stroke={9}
                         color={scoreColor(row.finalScore)} label="composite" />
              <div className="flex flex-col gap-2.5">
                {[
                  { l: "Rule-based", v: row.ruleScore, c: "#34d399" },
                  { l: "ML ranker", v: row.mlScore, c: "#a78bfa" },
                  { l: "Conviction", v: (row.conviction ?? 0) * 100, c: "#6d8dff" },
                ].map((s, i) => (
                  <div key={s.l} className="w-[132px]">
                    <div className="mb-1 flex items-center justify-between text-[11px]">
                      <span style={{ color: "var(--text-muted)" }}>{s.l}</span>
                      <span className="num">{num(s.v, 0)}</span>
                    </div>
                    <Meter value={s.v} color={s.c} height={4} delay={i * 0.1} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
        </Tilt>
      </Reveal>

      {/* ---------------- the explanation ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<Sparkles size={16} />} title="Why the engine ranks it here" />
          <p className="text-[15px] leading-relaxed">{ex.headline}</p>
          <p className="mt-3 text-[13.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
            {ex.summary}
          </p>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="label mb-2.5" style={{ color: "var(--pos)" }}>What it does well</p>
              <div className="flex flex-col gap-2">
                {ex.strengths.length === 0 && (
                  <p className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                    Nothing stands out against its sector on the upside.
                  </p>
                )}
                {ex.strengths.map((s, i) => (
                  <motion.div
                    key={s.metric}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    className="flex gap-2.5 rounded-xl border p-3"
                    style={{ borderColor: "rgba(52,211,153,.2)", background: "rgba(52,211,153,.045)" }}
                  >
                    <Check size={14} className="mt-0.5 shrink-0" style={{ color: "var(--pos)" }} />
                    <div>
                      <p className="text-[12.5px] leading-relaxed">{s.text}</p>
                      <p className="label mt-1 text-[9px]">{s.pillar}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            <div>
              <p className="label mb-2.5" style={{ color: "var(--neg)" }}>What holds it back</p>
              <div className="flex flex-col gap-2">
                {ex.concerns.length === 0 && (
                  <p className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                    No metric sits materially below its sector.
                  </p>
                )}
                {ex.concerns.map((c, i) => (
                  <motion.div
                    key={`${c.metric}-${i}`}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    className="flex gap-2.5 rounded-xl border p-3"
                    style={{ borderColor: "rgba(251,113,133,.2)", background: "rgba(251,113,133,.045)" }}
                  >
                    <Minus size={14} className="mt-0.5 shrink-0" style={{ color: "var(--neg)" }} />
                    <div>
                      <p className="text-[12.5px] leading-relaxed">{c.text}</p>
                      <p className="label mt-1 text-[9px]">{c.pillar}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-xl border p-4" style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
            <p className="label mb-2">What would change this view</p>
            <ul className="flex flex-col gap-1.5">
              {ex.what_would_change_this.map((t) => (
                <li key={t} className="flex gap-2 text-[12.5px] leading-relaxed"
                    style={{ color: "var(--text-muted)" }}>
                  <span style={{ color: "var(--brand)" }}>→</span> {t}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </Reveal>

      {/* ---------------- pillars + screens ---------------- */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]">
        <Reveal>
          <Card className="h-full" padding="p-5">
            <SectionTitle icon={<Gauge size={16} />} title="Five-pillar breakdown"
                          subtitle="Each pillar scores the company against sector peers, where 50 is the sector average." />
            <div className="flex justify-center py-2">
              <PillarRadar
                pillars={ex.pillars.map((p) => ({ label: p.label.split(" ")[0], score: p.score }))}
                size={236}
              />
            </div>
            <div className="mt-4 flex flex-col gap-2.5">
              {ex.pillars.map((p, i) => (
                <div key={p.key}>
                  <div className="mb-1 flex items-center justify-between text-[12px]">
                    <span style={{ color: "var(--text-muted)" }}>
                      {p.label}
                      <span className="num ml-1.5 text-[10px]" style={{ color: "var(--text-dim)" }}>
                        {pct(p.weight, 0)} weight
                      </span>
                    </span>
                    <span className="num font-medium" style={{ color: scoreColor(p.score) }}>
                      {num(p.score, 0)}
                    </span>
                  </div>
                  <Meter value={p.score} color={scoreColor(p.score)} height={5} delay={i * 0.07} />
                </div>
              ))}
            </div>
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="h-full" padding="p-5">
            <SectionTitle
              icon={<ShieldCheck size={16} />}
              title="The classic screens"
              subtitle="Piotroski tests nine accounting facts about improvement; Altman scores the distance from financial distress."
            />

            <div className="mb-4 flex flex-wrap gap-3">
              <div className="flex-1 rounded-xl border p-3.5" style={{ borderColor: "var(--line)" }}>
                <p className="label">Piotroski F-Score</p>
                <p className="num mt-1 text-[26px] font-semibold leading-none"
                   style={{ color: scoreColor(((ex.f_score ?? 0) / 9) * 100) }}>
                  <AnimatedNumber value={ex.f_score} decimals={0} />
                  <span className="text-[14px]" style={{ color: "var(--text-dim)" }}> / 9</span>
                </p>
                <p className="mt-1 text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                  {ex.f_score_verdict} · {passed} of {assessed} tests passed
                </p>
              </div>
              <div className="flex-1 rounded-xl border p-3.5" style={{ borderColor: "var(--line)" }}>
                <p className="label">Altman Z&apos;&apos;-Score</p>
                <p className="num mt-1 text-[26px] font-semibold leading-none"
                   style={{
                     color: ex.z_score === null ? "var(--text-dim)"
                       : ex.z_zone === "safe" ? "var(--pos)"
                       : ex.z_zone === "grey" ? "var(--warn)" : "var(--neg)",
                   }}>
                  {ex.z_score === null ? "n/a" : <AnimatedNumber value={ex.z_score} decimals={2} />}
                </p>
                <p className="mt-1 text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                  {ex.z_score === null
                    ? "Not applicable to banks and insurers"
                    : `${ex.z_zone} zone · safe above 5.85`}
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-1">
              {fTests.map((t, i) => (
                <motion.div
                  key={t.label}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-start gap-2.5 rounded-lg px-2.5 py-2"
                  style={{ background: i % 2 ? "var(--surface)" : "transparent" }}
                >
                  <span
                    className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full"
                    style={{
                      background: t.passed === null ? "rgba(148,163,184,.15)"
                        : t.passed ? "var(--pos-dim)" : "var(--neg-dim)",
                      color: t.passed === null ? "var(--text-dim)"
                        : t.passed ? "var(--pos)" : "var(--neg)",
                    }}
                  >
                    {t.passed === null ? <CircleSlash size={9} /> : t.passed ? <Check size={10} /> : <Minus size={10} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px]">{t.label}</p>
                    <p className="text-[11px]" style={{ color: "var(--text-dim)" }}>{t.detail}</p>
                  </div>
                </motion.div>
              ))}
            </div>

            {Object.keys(ex.z_components ?? {}).length > 0 && (
              <div className="mt-4 border-t pt-3" style={{ borderColor: "var(--line)" }}>
                <p className="label mb-2">Altman components</p>
                <div className="grid gap-x-5 gap-y-1.5 sm:grid-cols-2">
                  {Object.entries(ex.z_components).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between text-[11.5px]">
                      <span style={{ color: "var(--text-dim)" }}>{Z_COMPONENT_LABELS[k] ?? k}</span>
                      <span className="num">{num(v, 3)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </Reveal>
      </div>

      {/* ---------------- risk flags ---------------- */}
      {ex.risk_flags.length > 0 && (
        <Reveal>
          <Card padding="p-5" className="border-l-2" >
            <SectionTitle icon={<AlertTriangle size={16} />} title="Risk flags"
                          subtitle="Hard rules that cap the composite score regardless of how the pillars read." />
            <div className="flex flex-wrap gap-2">
              {ex.risk_flags.map((f) => (
                <span key={f} className="pill"
                      style={{ color: "var(--warn)", background: "var(--warn-dim)", borderColor: "rgba(251,191,36,.3)" }}>
                  {f}
                </span>
              ))}
            </div>
          </Card>
        </Reveal>
      )}

      {/* ---------------- price ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<TrendingUp size={16} />} title="Price history"
                        subtitle={`Weekly closes. Beta ${num(row.beta, 2)} against the index, annualised volatility ${pct(row.volatility, 0)}, RSI ${num(row.rsi, 0)}.`} />
          <PriceChart data={detail.priceHistory} height={300} />
        </Card>
      </Reveal>

      {/* ---------------- financials ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            icon={<ScrollText size={16} />}
            title="Reported accounts"
            subtitle="The last twelve quarters as filed, in PKR millions. The publication date is what the engine uses to decide when a figure became knowable."
            right={
              <Tabs size="sm" value={statement} onChange={setStatement}
                    tabs={[
                      { id: "income", label: "Income" },
                      { id: "balance", label: "Balance sheet" },
                      { id: "cash", label: "Cash flow" },
                      { id: "ratios", label: "Ratios" },
                    ]} />
            }
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[12.5px]">
              <thead>
                <tr className="label" style={{ color: "var(--text-dim)" }}>
                  <th className="px-2 pb-2.5 text-left font-semibold">Quarter</th>
                  {statement === "income" && (
                    <>
                      <th className="px-2 pb-2.5 text-right font-semibold">Revenue</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Gross profit</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Operating</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Net income</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">EPS</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Filed</th>
                    </>
                  )}
                  {statement === "balance" && (
                    <>
                      <th className="px-2 pb-2.5 text-right font-semibold">Total assets</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Liabilities</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Equity</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Equity / assets</th>
                    </>
                  )}
                  {statement === "cash" && (
                    <>
                      <th className="px-2 pb-2.5 text-right font-semibold">Operating cash</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Capex</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Free cash flow</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Cash / profit</th>
                    </>
                  )}
                  {statement === "ratios" && (
                    <>
                      <th className="px-2 pb-2.5 text-right font-semibold">ROE</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">ROA</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Net margin</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Current</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">D/E</th>
                      <th className="px-2 pb-2.5 text-right font-semibold">Interest cover</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {statement === "ratios"
                  ? ratios.map((r) => (
                      <tr key={r.period} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="num px-2 py-2">{r.period}</td>
                        <td className="num px-2 py-2 text-right">{pct(r.roe, 1)}</td>
                        <td className="num px-2 py-2 text-right">{pct(r.roa, 1)}</td>
                        <td className="num px-2 py-2 text-right">{pct(r.netMargin, 1)}</td>
                        <td className="num px-2 py-2 text-right">{num(r.currentRatio, 2)}</td>
                        <td className="num px-2 py-2 text-right">{num(r.debtToEquity, 2)}</td>
                        <td className="num px-2 py-2 text-right">{mult(r.interestCoverage, 1)}</td>
                      </tr>
                    ))
                  : financials.map((f) => (
                      <tr key={f.period} className="border-t" style={{ borderColor: "var(--line)" }}>
                        <td className="num px-2 py-2">
                          {f.fiscalYear} Q{f.quarter}
                        </td>
                        {statement === "income" && (
                          <>
                            <td className="num px-2 py-2 text-right">{pkrM(f.revenue)}</td>
                            <td className="num px-2 py-2 text-right">{pkrM(f.grossProfit)}</td>
                            <td className="num px-2 py-2 text-right">{pkrM(f.operatingIncome)}</td>
                            <td className="num px-2 py-2 text-right"
                                style={{ color: (f.netIncome ?? 0) >= 0 ? "var(--text)" : "var(--neg)" }}>
                              {pkrM(f.netIncome)}
                            </td>
                            <td className="num px-2 py-2 text-right">{num(f.eps, 2)}</td>
                            <td className="num px-2 py-2 text-right" style={{ color: "var(--text-dim)" }}>
                              {f.reportDate}
                            </td>
                          </>
                        )}
                        {statement === "balance" && (
                          <>
                            <td className="num px-2 py-2 text-right">{pkrM(f.totalAssets)}</td>
                            <td className="num px-2 py-2 text-right">{pkrM(f.totalLiabilities)}</td>
                            <td className="num px-2 py-2 text-right">{pkrM(f.totalEquity)}</td>
                            <td className="num px-2 py-2 text-right">
                              {pct((f.totalEquity ?? 0) / (f.totalAssets || 1), 1)}
                            </td>
                          </>
                        )}
                        {statement === "cash" && (
                          <>
                            <td className="num px-2 py-2 text-right">{pkrM(f.cfo)}</td>
                            <td className="num px-2 py-2 text-right">{pkrM(f.capex)}</td>
                            <td className="num px-2 py-2 text-right"
                                style={{ color: (f.freeCashFlow ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
                              {pkrM(f.freeCashFlow)}
                            </td>
                            <td className="num px-2 py-2 text-right">
                              {f.netIncome ? mult((f.cfo ?? 0) / f.netIncome, 2) : "—"}
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </Card>
      </Reveal>

      {/* ---------------- peers ---------------- */}
      <Reveal>
        <Spotlight className="rounded-2xl" size={420} color="rgba(109,141,255,.14)">
        <Card padding="p-5 sm:p-6">
          <SectionTitle icon={<Users size={16} />} title={`Ranked against ${detail.sector}`}
                        subtitle="Every peer in the same sector, ordered by composite score. These are the companies whose ratios set this one's z-scores." />
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {detail.peers.map((p) => {
              const self = p.ticker === detail.ticker;
              return (
                <Link key={p.ticker} href={`/company/${p.ticker}`}
                      className="focus-ring rounded-xl">
                  <div className="flex items-center gap-2.5 rounded-xl border p-3 transition-colors hover:bg-[var(--surface-2)]"
                       style={{
                         borderColor: self ? "var(--brand)" : "var(--line)",
                         background: self ? "rgba(109,141,255,.07)" : "transparent",
                       }}>
                    <span className="num text-[13px] font-semibold">{p.ticker}</span>
                    <span className="min-w-0 flex-1 truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                      {p.name}
                    </span>
                    <span className="num text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                      {num(p.pe, 1)}x
                    </span>
                    <span className="num text-[13px] font-semibold" style={{ color: scoreColor(p.finalScore) }}>
                      {num(p.finalScore, 0)}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </Card>
        </Spotlight>
      </Reveal>

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        Scored as of {longDate(ex.as_of)}. {ex.disclaimer}
      </p>
    </div>
  );
}
