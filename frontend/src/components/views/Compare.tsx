"use client";

/**
 * Side-by-side comparison of up to four names.
 *
 * The screener answers "what does the market look like"; this answers "which
 * of these two". Everything on the page is drawn from the same cross-section
 * the engine scored, so a row here can always be traced back to a rank.
 *
 * The metric table marks the best cell in every row, which needs a direction
 * per metric — a low P/E is good, a low ROE is not — so each row declares
 * whether it is scored ascending or descending.
 */

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useMemo, useState } from "react";
import { ArrowUpRight, GitCompareArrows, Plus, Scale, Search, Trophy, X } from "lucide-react";

import { MultiRadar, RebasedChart } from "@/components/charts";
import { Spotlight, Stagger, Tilt } from "@/components/motion";
import { Card, Empty, Meter, SectionTitle } from "@/components/ui";
import { WatchButton } from "@/components/WatchButton";
import {
  bandClass, mult, num, pct, pkrM, rupees, scoreColor, signedPct, PILLAR_ORDER, PILLAR_SHORT,
} from "@/lib/format";
import { useWatchlist } from "@/lib/watchlist";
import type { Dashboard, PillarKey, Recommendation } from "@/lib/types";

const MAX = 4;

/** Distinct enough to tell four overlaid polygons apart at a glance. */
const SLOT_COLOR = ["#6d8dff", "#34d399", "#fbbf24", "#f472b6"];

type Dir = "high" | "low";
type Row = {
  label: string;
  dir: Dir | null;
  get: (r: Recommendation) => number | null;
  fmt: (v: number | null) => string;
  group: string;
};

const ROWS: Row[] = [
  { group: "Verdict", label: "Composite score", dir: "high", get: (r) => r.finalScore, fmt: (v) => num(v, 1) },
  { group: "Verdict", label: "Rank in index", dir: "low", get: (r) => r.rank, fmt: (v) => (v === null ? "—" : `#${num(v, 0)}`) },
  { group: "Verdict", label: "Rule score", dir: "high", get: (r) => r.ruleScore, fmt: (v) => num(v, 1) },
  { group: "Verdict", label: "ML score", dir: "high", get: (r) => r.mlScore, fmt: (v) => num(v, 1) },
  { group: "Verdict", label: "Conviction", dir: "high", get: (r) => r.conviction, fmt: (v) => pct(v, 0) },

  { group: "Valuation", label: "Price", dir: null, get: (r) => r.price, fmt: (v) => rupees(v, 2) },
  { group: "Valuation", label: "Market cap", dir: null, get: (r) => r.marketCap, fmt: (v) => pkrM(v) },
  { group: "Valuation", label: "P/E", dir: "low", get: (r) => r.pe, fmt: (v) => mult(v, 1) },
  { group: "Valuation", label: "P/B", dir: "low", get: (r) => r.pb, fmt: (v) => mult(v, 2) },
  { group: "Valuation", label: "EV/EBITDA", dir: "low", get: (r) => r.evEbitda, fmt: (v) => mult(v, 1) },
  { group: "Valuation", label: "Dividend yield", dir: "high", get: (r) => r.dividendYield, fmt: (v) => pct(v, 1) },

  { group: "Profitability", label: "Return on equity", dir: "high", get: (r) => r.roe, fmt: (v) => pct(v, 1) },
  { group: "Profitability", label: "Return on assets", dir: "high", get: (r) => r.roa, fmt: (v) => pct(v, 1) },
  { group: "Profitability", label: "Net margin", dir: "high", get: (r) => r.netMargin, fmt: (v) => pct(v, 1) },
  { group: "Profitability", label: "Revenue growth", dir: "high", get: (r) => r.revenueGrowth, fmt: (v) => signedPct(v, 1) },
  { group: "Profitability", label: "Earnings growth", dir: "high", get: (r) => r.earningsGrowth, fmt: (v) => signedPct(v, 1) },

  { group: "Risk", label: "Debt / equity", dir: "low", get: (r) => r.debtToEquity, fmt: (v) => num(v, 2) },
  { group: "Risk", label: "Piotroski F-Score", dir: "high", get: (r) => r.fScore, fmt: (v) => (v === null ? "—" : `${num(v, 0)} / 9`) },
  { group: "Risk", label: "Altman Z''", dir: "high", get: (r) => r.zScore, fmt: (v) => num(v, 2) },
  { group: "Risk", label: "Volatility", dir: "low", get: (r) => r.volatility, fmt: (v) => pct(v, 1) },
  { group: "Risk", label: "Beta", dir: null, get: (r) => r.beta, fmt: (v) => num(v, 2) },
  { group: "Risk", label: "Daily turnover", dir: "high", get: (r) => r.turnoverPkrM, fmt: (v) => pkrM(v) },

  { group: "Trend", label: "1-month return", dir: "high", get: (r) => r.return1m, fmt: (v) => signedPct(v, 1) },
  { group: "Trend", label: "3-month return", dir: "high", get: (r) => r.return3m, fmt: (v) => signedPct(v, 1) },
  { group: "Trend", label: "12-month return", dir: "high", get: (r) => r.return12m, fmt: (v) => signedPct(v, 1) },
  { group: "Trend", label: "RSI", dir: null, get: (r) => r.rsi, fmt: (v) => num(v, 0) },
];

const GROUPS = ["Verdict", "Valuation", "Profitability", "Risk", "Trend"];

export function Compare({ data }: { data: Dashboard }) {
  const { recommendations, meta } = data;
  const { tickers: watched } = useWatchlist();

  const [picked, setPicked] = useState<string[]>(() =>
    recommendations.slice(0, 2).map((r) => r.ticker),
  );
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");

  const byTicker = useMemo(
    () => new Map(recommendations.map((r) => [r.ticker, r])),
    [recommendations],
  );

  const chosen = useMemo(
    () => picked.map((t) => byTicker.get(t)).filter((r): r is Recommendation => Boolean(r)),
    [picked, byTicker],
  );

  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase();
    return recommendations
      .filter((r) => !picked.includes(r.ticker))
      .filter((r) =>
        !q || r.ticker.toLowerCase().includes(q) || r.name.toLowerCase().includes(q),
      )
      .slice(0, 60);
  }, [recommendations, picked, query]);

  const add = (t: string) => {
    setPicked((p) => (p.includes(t) || p.length >= MAX ? p : [...p, t]));
    setQuery("");
  };
  const remove = (t: string) => setPicked((p) => p.filter((x) => x !== t));

  /** Best cell per row, or null where the metric has no natural direction. */
  const winners = useMemo(() => {
    const out = new Map<string, string | null>();
    for (const row of ROWS) {
      if (!row.dir || chosen.length < 2) {
        out.set(row.label, null);
        continue;
      }
      let best: { t: string; v: number } | null = null;
      for (const r of chosen) {
        const v = row.get(r);
        if (v === null || v === undefined || !Number.isFinite(v)) continue;
        // A non-positive multiple is not "cheap", it is meaningless, so it
        // never wins a low-is-better row.
        if (row.dir === "low" && v <= 0) continue;
        if (!best || (row.dir === "high" ? v > best.v : v < best.v)) best = { t: r.ticker, v };
      }
      out.set(row.label, best?.t ?? null);
    }
    return out;
  }, [chosen]);

  /** Rows won, as a headline tally across the directional metrics. */
  const tally = useMemo(() => {
    const counts = new Map<string, number>(chosen.map((r) => [r.ticker, 0]));
    winners.forEach((t) => {
      if (t) counts.set(t, (counts.get(t) ?? 0) + 1);
    });
    return counts;
  }, [winners, chosen]);

  const leader = useMemo(() => {
    let best: { t: string; n: number } | null = null;
    tally.forEach((n, t) => {
      if (!best || n > best.n) best = { t, n };
    });
    return best as { t: string; n: number } | null;
  }, [tally]);

  const colorOf = (ticker: string) => SLOT_COLOR[picked.indexOf(ticker) % SLOT_COLOR.length];

  return (
    <div className="flex flex-col gap-6">
      <SectionTitle
        icon={<GitCompareArrows size={16} />}
        title="Compare"
        subtitle={`Put up to ${MAX} KSE-100 names on the same axes. Every figure is the one the engine scored on ${meta.asOf}, and the best value in each row is marked — a low multiple wins the valuation rows, a high one wins the returns.`}
        right={
          <Link
            href="/screener"
            className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
            style={{ color: "var(--text-muted)" }}
          >
            Open screener <ArrowUpRight size={12} />
          </Link>
        }
      />

      {/* ---------------- slots ---------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: MAX }).map((_, slot) => {
          const r = chosen[slot];
          if (!r) {
            return (
              <button
                key={`empty-${slot}`}
                onClick={() => setPicking(true)}
                className="group grid min-h-[188px] place-items-center rounded-2xl border border-dashed text-[12.5px] transition-colors focus-ring"
                style={{ borderColor: "var(--line-strong)", color: "var(--text-dim)" }}
              >
                <span className="flex flex-col items-center gap-2">
                  <span
                    className="grid h-9 w-9 place-items-center rounded-full border transition-transform group-hover:scale-110"
                    style={{ borderColor: "var(--line-strong)" }}
                  >
                    <Plus size={16} />
                  </span>
                  Add a company
                </span>
              </button>
            );
          }
          const color = colorOf(r.ticker);
          const won = tally.get(r.ticker) ?? 0;
          return (
            <motion.div key={r.ticker} layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
              <Tilt max={6}>
                <Card className="relative h-full overflow-hidden" hover>
                  <span
                    aria-hidden
                    className="absolute inset-x-0 top-0 h-[3px]"
                    style={{ background: color }}
                  />
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <Link href={`/company/${r.ticker}`} className="focus-ring rounded">
                        <p className="num text-[15px] font-semibold tracking-tight">{r.ticker}</p>
                      </Link>
                      <p className="truncate text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                        {r.name}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5">
                      <WatchButton ticker={r.ticker} />
                      <button
                        onClick={() => remove(r.ticker)}
                        aria-label={`Remove ${r.ticker}`}
                        className="rounded-md p-1 transition-colors focus-ring hover:text-[var(--neg)]"
                        style={{ color: "var(--text-dim)" }}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="num text-[26px] font-semibold leading-none" style={{ color: scoreColor(r.finalScore) }}>
                      {num(r.finalScore, 1)}
                    </span>
                    <span className={`pill ${bandClass(r.recommendation)}`}>{r.recommendation}</span>
                  </div>

                  <div className="mt-3">
                    <Meter value={r.finalScore} color={color} delay={slot * 0.06} />
                  </div>

                  <p className="mt-3 truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                    {r.sector}
                  </p>

                  {chosen.length > 1 && (
                    <p className="num mt-2 flex items-center gap-1.5 text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                      <Trophy size={11} style={{ color: won > 0 ? "var(--warn)" : "var(--text-dim)" }} />
                      wins {won} of {winners.size} metrics
                    </p>
                  )}
                </Card>
              </Tilt>
            </motion.div>
          );
        })}
      </div>

      {/* ---------------- picker ---------------- */}
      <AnimatePresence initial={false}>
        {picking && picked.length < MAX && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <Card>
              <div className="flex items-center gap-2.5">
                <div className="relative flex-1">
                  <Search
                    size={14}
                    className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--text-dim)" }}
                  />
                  <input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search a ticker or company…"
                    className="w-full rounded-lg border bg-transparent py-2 pl-9 pr-3 text-[13px] outline-none focus-ring"
                    style={{ borderColor: "var(--line)" }}
                  />
                </div>
                <button
                  onClick={() => setPicking(false)}
                  className="rounded-lg p-2 focus-ring"
                  style={{ color: "var(--text-dim)" }}
                  aria-label="Close picker"
                >
                  <X size={15} />
                </button>
              </div>

              {watched.length > 0 && !query && (
                <div className="mt-3">
                  <p className="label mb-1.5">From your watchlist</p>
                  <div className="flex flex-wrap gap-1.5">
                    {watched
                      .filter((t) => !picked.includes(t) && byTicker.has(t))
                      .map((t) => (
                        <button
                          key={t}
                          onClick={() => add(t)}
                          className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
                          style={{ color: "var(--warn)" }}
                        >
                          {t}
                        </button>
                      ))}
                  </div>
                </div>
              )}

              <div className="mt-3 max-h-64 overflow-y-auto">
                <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
                  {candidates.map((r) => (
                    <button
                      key={r.ticker}
                      onClick={() => add(r.ticker)}
                      className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors focus-ring hover:bg-[var(--surface-2)]"
                    >
                      <span
                        className="num w-9 shrink-0 text-[11px]"
                        style={{ color: "var(--text-dim)" }}
                      >
                        #{r.rank}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="num block text-[12.5px] font-semibold">{r.ticker}</span>
                        <span
                          className="block truncate text-[10.5px]"
                          style={{ color: "var(--text-dim)" }}
                        >
                          {r.name}
                        </span>
                      </span>
                      <span
                        className="num shrink-0 text-[12px] font-semibold"
                        style={{ color: scoreColor(r.finalScore) }}
                      >
                        {num(r.finalScore, 0)}
                      </span>
                    </button>
                  ))}
                </div>
                {candidates.length === 0 && (
                  <Empty title="No match" hint="Try a different ticker or company name." />
                )}
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {chosen.length < 2 ? (
        <Card>
          <Empty
            title="Pick at least two companies"
            hint="Add a second name and the pillar profiles, rebased prices and metric table appear here."
          />
        </Card>
      ) : (
        <>
          {/* ---------------- radar + rebased prices ---------------- */}
          <div className="grid gap-3 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
            <Card className="h-full">
              <SectionTitle
                icon={<Scale size={16} />}
                title="Pillar profiles"
                subtitle="Each axis is the sector-relative score out of 100. Shape matters more than size: a spike on value with a dent on safety is a cheap balance sheet worth checking."
              />
              <div className="grid place-items-center py-2">
                <MultiRadar
                  size={300}
                  axes={PILLAR_ORDER.map((k) => PILLAR_SHORT[k])}
                  series={chosen.map((r) => ({
                    key: r.ticker,
                    label: r.ticker,
                    color: colorOf(r.ticker),
                    values: PILLAR_ORDER.map((k) => r.pillars?.[k as PillarKey] ?? null),
                  }))}
                />
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-3">
                {chosen.map((r) => (
                  <span key={r.ticker} className="flex items-center gap-1.5 text-[11.5px]">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: colorOf(r.ticker) }}
                    />
                    <span className="num">{r.ticker}</span>
                  </span>
                ))}
              </div>
            </Card>

            <Card className="h-full">
              <SectionTitle
                title="Price paths, rebased to 100"
                subtitle="The last 60 trading points for each name, each divided by its own starting price. Levels are stripped out so only the relative move is left."
              />
              <RebasedChart
                height={320}
                series={chosen.map((r) => ({
                  key: r.ticker,
                  label: r.ticker,
                  color: colorOf(r.ticker),
                  values: r.spark,
                }))}
              />
            </Card>
          </div>

          {/* ---------------- verdict strip ---------------- */}
          {leader && leader.n > 0 && (
            <Card padding="p-4">
              <p className="text-[13px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                <Trophy size={13} className="mr-1.5 inline" style={{ color: "var(--warn)" }} />
                <span className="num font-semibold" style={{ color: colorOf(leader.t) }}>
                  {leader.t}
                </span>{" "}
                takes {leader.n} of the {winners.size} directional metrics below. That is a
                scoreboard, not a recommendation — the engine&apos;s own call is the band on each
                card, which weights these figures rather than counting them.
              </p>
            </Card>
          )}

          {/* ---------------- metric table ---------------- */}
          <Card padding="p-0" className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-[12.5px]">
                <thead>
                  <tr style={{ background: "var(--surface)" }}>
                    <th className="label px-4 py-3 text-left">Metric</th>
                    {chosen.map((r) => (
                      <th key={r.ticker} className="px-4 py-3 text-right">
                        <span className="flex items-center justify-end gap-1.5">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: colorOf(r.ticker) }}
                          />
                          <span className="num text-[12.5px] font-semibold">{r.ticker}</span>
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {GROUPS.map((g) => (
                    <Fragment key={g}>
                      <tr>
                        <td
                          colSpan={chosen.length + 1}
                          className="label border-t px-4 pb-1.5 pt-4"
                          style={{ borderColor: "var(--line)", color: "var(--brand)" }}
                        >
                          {g}
                        </td>
                      </tr>
                      {ROWS.filter((row) => row.group === g).map((row) => {
                        const win = winners.get(row.label);
                        return (
                          <tr
                            key={row.label}
                            className="border-t transition-colors hover:bg-[var(--surface)]"
                            style={{ borderColor: "var(--line)" }}
                          >
                            <td className="px-4 py-2.5" style={{ color: "var(--text-muted)" }}>
                              {row.label}
                            </td>
                            {chosen.map((r) => {
                              const isWin = win === r.ticker;
                              return (
                                <td key={r.ticker} className="px-4 py-2.5 text-right">
                                  <span
                                    className="num inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5"
                                    style={
                                      isWin
                                        ? {
                                            background: "rgba(52,211,153,.12)",
                                            color: "var(--pos)",
                                            fontWeight: 600,
                                          }
                                        : undefined
                                    }
                                  >
                                    {row.fmt(row.get(r))}
                                  </span>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* ---------------- risk flags ---------------- */}
          <Stagger className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {chosen.map((r) => (
              <Spotlight key={r.ticker} className="h-full rounded-2xl">
                <Card className="h-full">
                  <p className="num mb-2 text-[13px] font-semibold" style={{ color: colorOf(r.ticker) }}>
                    {r.ticker}
                  </p>
                  {r.riskFlags.length === 0 ? (
                    <p className="text-[12px]" style={{ color: "var(--pos)" }}>
                      No risk gate triggered.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-1.5">
                      {r.riskFlags.map((f) => (
                        <li
                          key={f}
                          className="text-[11.5px] leading-relaxed"
                          style={{ color: "var(--warn)" }}
                        >
                          • {f}
                        </li>
                      ))}
                    </ul>
                  )}
                  <p
                    className="mt-3 line-clamp-4 border-t pt-2.5 text-[11.5px] leading-relaxed"
                    style={{ borderColor: "var(--line)", color: "var(--text-dim)" }}
                  >
                    {r.summary}
                  </p>
                </Card>
              </Spotlight>
            ))}
          </Stagger>
        </>
      )}

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        {meta.disclaimer}
      </p>
    </div>
  );
}
