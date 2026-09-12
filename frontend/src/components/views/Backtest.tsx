"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, CalendarClock, LineChart, ShieldAlert, Wallet } from "lucide-react";

import { DrawdownChart, EquityChart, YearlyBars } from "@/components/charts";
import { AnimatedNumber, Card, Reveal, SectionTitle, Tabs } from "@/components/ui";
import { bandClass, longDate, num, pct, shortDate, signedPct, STRATEGY_COLOR } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

const METRIC_ROWS: {
  key: string;
  label: string;
  fmt: (v: number | undefined) => string;
  hint?: string;
  higherBetter?: boolean;
}[] = [
  { key: "cagr", label: "Compound annual return", fmt: (v) => pct(v, 2), higherBetter: true },
  { key: "total_return", label: "Total return", fmt: (v) => pct(v, 1), higherBetter: true },
  { key: "volatility", label: "Annualised volatility", fmt: (v) => pct(v, 1), higherBetter: false },
  { key: "sharpe", label: "Sharpe ratio", fmt: (v) => num(v, 2), higherBetter: true },
  { key: "sortino", label: "Sortino ratio", fmt: (v) => num(v, 2), higherBetter: true },
  { key: "max_drawdown", label: "Worst drawdown", fmt: (v) => pct(v, 1), higherBetter: true },
  { key: "calmar", label: "Calmar ratio", fmt: (v) => num(v, 2), higherBetter: true },
  { key: "beta", label: "Beta vs KSE-100", fmt: (v) => num(v, 2) },
  { key: "alpha_annual", label: "Annual alpha", fmt: (v) => pct(v, 2), higherBetter: true },
  { key: "tracking_error", label: "Tracking error", fmt: (v) => pct(v, 1), higherBetter: false },
  { key: "information_ratio", label: "Information ratio", fmt: (v) => num(v, 2), higherBetter: true },
  { key: "hit_rate", label: "Quarters ahead of the index", fmt: (v) => pct(v, 0), higherBetter: true },
  { key: "avg_turnover", label: "Average turnover per rebalance", fmt: (v) => pct(v, 0), higherBetter: false },
];

export function Backtest({ data }: { data: Dashboard }) {
  const { meta, performance, equityCurve, drawdown, rebalances } = data;
  const [scale, setScale] = useState("linear");
  const [openReb, setOpenReb] = useState<string | null>(
    rebalances.length ? rebalances[rebalances.length - 1].date : null,
  );

  const blended = performance.find((p) => p.key === "blended");
  const bench = performance.find((p) => p.key === "KSE100");

  const yearly = useMemo(() => {
    const b = new Map(bench?.yearly.map((y) => [y.year, y.return]));
    return (blended?.yearly ?? []).map((y) => ({
      year: y.year,
      strategy: y.return,
      benchmark: b.get(y.year) ?? 0,
    }));
  }, [blended, bench]);

  const wins = yearly.filter((y) => y.strategy > y.benchmark).length;

  return (
    <div className="flex flex-col gap-7">
      <SectionTitle
        icon={<LineChart size={16} />}
        title="Walk-forward backtest"
        subtitle={`Positions at each rebalance were chosen only from filings already published and prices already printed. Costs of ${meta.costBps} basis points per round trip are charged on the traded fraction of the book, no sector may exceed ${pct(meta.maxSectorWeight, 0)} of the portfolio, and illiquid names are excluded however well they score.`}
      />

      {/* ---------------- headline ---------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { l: "Engine compound return", v: (blended?.cagr ?? 0) * 100, d: 2, s: "%",
            f: `vs ${pct(bench?.cagr, 2)} for the KSE-100` },
          { l: "Years tested", v: blended?.years ?? 0, d: 1, s: "",
            f: `${blended?.n_rebalances ?? 0} quarterly rebalances from ${longDate(meta.backtestStart)}` },
          { l: "Calendar years ahead", v: wins, d: 0, s: `/${yearly.length}`,
            f: "Full calendar years where the engine beat the index" },
          { l: "Cost drag paid", v: blended?.total_cost_drag_pct ?? 0, d: 2, s: "%",
            f: "Total commission and slippage charged across the test" },
        ].map((t, i) => (
          <Reveal key={t.l} delay={i * 0.06}>
            <Card hover className="h-full">
              <p className="label">{t.l}</p>
              <p className="num mt-2.5 text-[28px] font-semibold leading-none">
                <AnimatedNumber value={t.v} decimals={t.d} suffix={t.s} />
              </p>
              <p className="mt-2.5 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                {t.f}
              </p>
            </Card>
          </Reveal>
        ))}
      </div>

      {/* ---------------- equity curve ---------------- */}
      <Reveal>
        <Card padding="p-5 sm:p-6">
          <SectionTitle
            title="Growth of Rs 100"
            subtitle="Each strategy holds the top-ranked names under its own score. The benchmark is the cap-weighted KSE-100."
            right={
              <Tabs size="sm" value={scale} onChange={setScale}
                    tabs={[{ id: "linear", label: "Linear" }, { id: "log", label: "Log" }]} />
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
            height={380}
            logScale={scale === "log"}
          />
        </Card>
      </Reveal>

      {/* ---------------- metric table ---------------- */}
      <Reveal>
        <Card padding="p-0" className="overflow-hidden">
          <div className="p-5 pb-0">
            <SectionTitle
              title="Every strategy, side by side"
              subtitle="The rule-based score has no fitted parameters, so it cannot overfit. The machine-learning ranker is retrained at every rebalance on data that was available then. The blend is what the dashboard reports as the engine."
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[13px]">
              <thead>
                <tr style={{ background: "var(--surface)" }}>
                  <th className="label px-5 py-3 text-left">Measure</th>
                  {performance.map((p) => (
                    <th key={p.key} className="label px-4 py-3 text-right">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full"
                              style={{ background: STRATEGY_COLOR[p.key] }} />
                        {p.label}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRIC_ROWS.map((row) => {
                  const values = performance.map(
                    (p) => (p as unknown as Record<string, number | undefined>)[row.key],
                  );
                  const defined = values.filter((v): v is number => v !== undefined);
                  const best = row.higherBetter === undefined
                    ? null
                    : row.higherBetter ? Math.max(...defined) : Math.min(...defined);
                  return (
                    <tr key={row.key} className="border-t" style={{ borderColor: "var(--line)" }}>
                      <td className="px-5 py-2.5" style={{ color: "var(--text-muted)" }}>{row.label}</td>
                      {performance.map((p, i) => {
                        const v = values[i];
                        const isBest = best !== null && v !== undefined && v === best && defined.length > 1;
                        return (
                          <td key={p.key} className="num px-4 py-2.5 text-right"
                              style={{
                                color: isBest ? "var(--pos)" : "var(--text)",
                                fontWeight: isBest ? 600 : 400,
                              }}>
                            {row.fmt(v)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </Reveal>

      {/* ---------------- drawdown + yearly ---------------- */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Reveal>
          <Card className="h-full" padding="p-5">
            <SectionTitle
              icon={<ShieldAlert size={16} />}
              title="Drawdown"
              subtitle="How far the book sat below its own high-water mark, against the same measure for the index."
            />
            <DrawdownChart data={drawdown} height={230} />
            <p className="mt-3 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
              The engine is a long-only equity strategy, so it falls with the market. Its worst
              drawdown of {pct(blended?.max_drawdown, 1)} against the index&apos;s{" "}
              {pct(bench?.max_drawdown, 1)} is a difference of degree, not of kind.
            </p>
          </Card>
        </Reveal>

        <Reveal delay={0.08}>
          <Card className="h-full" padding="p-5">
            <SectionTitle
              icon={<CalendarClock size={16} />}
              title="Calendar year returns"
              subtitle="Where the excess return actually came from, year by year."
            />
            <YearlyBars data={yearly} height={230} />
            <p className="mt-3 text-[11.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
              The engine finished ahead of the KSE-100 in {wins} of {yearly.length} calendar years.
              Losing years matter: a strategy that never lags the index over a decade is usually a
              sign of look-ahead leaking into the test.
            </p>
          </Card>
        </Reveal>
      </div>

      {/* ---------------- rebalance log ---------------- */}
      <Reveal>
        <Card padding="p-5">
          <SectionTitle
            icon={<Wallet size={16} />}
            title="Rebalance log"
            subtitle="Every quarterly trade the blended engine made, with the book it held and how that book performed against the index over the following quarter."
          />
          <div className="flex flex-col gap-1.5">
            {[...rebalances].reverse().map((r) => {
              const open = openReb === r.date;
              const ahead = (r.excess ?? 0) >= 0;
              return (
                <div key={r.date} className="overflow-hidden rounded-xl border"
                     style={{ borderColor: open ? "var(--line-strong)" : "var(--line)" }}>
                  <button
                    onClick={() => setOpenReb(open ? null : r.date)}
                    className="flex w-full flex-wrap items-center gap-x-5 gap-y-1.5 px-4 py-3 text-left transition-colors hover:bg-[var(--surface-2)]"
                  >
                    <span className="num text-[13px] font-medium">{shortDate(r.date)}</span>
                    <span className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                      {r.holdings.length} holdings · {pct(r.turnover, 0)} turnover
                    </span>
                    <span className="ml-auto flex items-center gap-4 text-[12px]">
                      <span className="num" style={{ color: "var(--text-muted)" }}>
                        idx {signedPct(r.benchmarkReturn, 1)}
                      </span>
                      <span className="num font-semibold"
                            style={{ color: ahead ? "var(--pos)" : "var(--neg)" }}>
                        {signedPct(r.periodReturn, 1)}
                      </span>
                      <span className="pill"
                            style={{
                              color: ahead ? "var(--pos)" : "var(--neg)",
                              background: ahead ? "var(--pos-dim)" : "var(--neg-dim)",
                              borderColor: "transparent",
                            }}>
                        {signedPct(r.excess, 1)}
                      </span>
                    </span>
                  </button>

                  {open && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                      className="overflow-hidden border-t"
                      style={{ borderColor: "var(--line)", background: "var(--surface)" }}
                    >
                      <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
                        {r.holdings.map((h) => (
                          <div key={h.ticker}
                               className="flex items-center gap-2.5 rounded-lg border px-3 py-2"
                               style={{ borderColor: "var(--line)" }}>
                            <span className="num text-[12.5px] font-semibold">{h.ticker}</span>
                            <span className="min-w-0 flex-1 truncate text-[11px]"
                                  style={{ color: "var(--text-dim)" }}>
                              {h.sector}
                            </span>
                            <span className="num text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                              {num(h.score, 0)}
                            </span>
                            <span className={`pill ${bandClass(h.recommendation)}`}
                                  style={{ fontSize: 9.5, padding: "2px 6px" }}>
                              {h.recommendation}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="px-4 pb-4 text-[11px]" style={{ color: "var(--text-dim)" }}>
                        {r.nCandidates} names were scored; {r.nExcludedLiquidity} were excluded for
                        thin traded volume before selection. Equal weight, {pct(1 / (r.holdings.length || 1), 1)} each.
                      </p>
                    </motion.div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      </Reveal>

      <Card padding="p-4" className="flex items-start gap-3">
        <AlertTriangle size={15} className="mt-0.5 shrink-0" style={{ color: "var(--warn)" }} />
        <p className="text-[11.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
          A backtest is evidence about a rule, not a forecast. It assumes every order filled at the
          closing price on the rebalance day, ignores the market impact of scaling the book, and is
          measured on a single simulated history of the KSE-100. {meta.disclaimer}
        </p>
      </Card>
    </div>
  );
}
