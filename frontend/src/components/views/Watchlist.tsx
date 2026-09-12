"use client";

/**
 * The reader's own shortlist.
 *
 * Nothing here is computed fresh: every figure is the one the engine already
 * published for that name. What the page adds is the aggregate — what the
 * starred set looks like as a portfolio, scored and weighted the way the
 * backtest weights its holdings, which is equally.
 */

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useMemo } from "react";
import { ArrowUpRight, GitCompareArrows, Star, Trash2 } from "lucide-react";

import { Spotlight, Stagger } from "@/components/motion";
import { AnimatedNumber, Card, Empty, Meter, ScoreRing, SectionTitle, Sparkline } from "@/components/ui";
import { WatchButton } from "@/components/WatchButton";
import { bandClass, mult, num, pct, rupees, scoreColor, signedPct } from "@/lib/format";
import { useWatchlist } from "@/lib/watchlist";
import type { Dashboard } from "@/lib/types";

export function Watchlist({ data }: { data: Dashboard }) {
  const { recommendations, meta } = data;
  const { tickers, clear } = useWatchlist();

  const rows = useMemo(() => {
    const set = new Set(tickers);
    return recommendations.filter((r) => set.has(r.ticker));
  }, [recommendations, tickers]);

  /** Equal-weighted aggregates, the same construction the backtest uses. */
  const agg = useMemo(() => {
    if (rows.length === 0) return null;
    const mean = (pick: (r: (typeof rows)[number]) => number | null) => {
      const vals = rows.map(pick).filter((v): v is number => v !== null && Number.isFinite(v));
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    };
    const sectors = new Map<string, number>();
    for (const r of rows) sectors.set(r.sector, (sectors.get(r.sector) ?? 0) + 1);
    const top = [...sectors.entries()].sort((a, b) => b[1] - a[1]);
    return {
      score: mean((r) => r.finalScore),
      pe: mean((r) => r.pe),
      roe: mean((r) => r.roe),
      yield: mean((r) => r.dividendYield),
      ret12: mean((r) => r.return12m),
      beta: mean((r) => r.beta),
      buys: rows.filter((r) => r.recommendation === "STRONG BUY" || r.recommendation === "BUY").length,
      flagged: rows.filter((r) => r.riskFlags.length > 0).length,
      sectors: top,
      concentration: top.length ? top[0][1] / rows.length : 0,
    };
  }, [rows]);

  return (
    <div className="flex flex-col gap-6">
      <SectionTitle
        icon={<Star size={16} />}
        title="Watchlist"
        subtitle="Stars are kept in this browser only — there is no account behind the dashboard. Clearing site data clears the list."
        right={
          rows.length > 0 ? (
            <div className="flex items-center gap-2">
              <Link
                href="/compare"
                className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
                style={{ color: "var(--text-muted)" }}
              >
                <GitCompareArrows size={12} /> Compare
              </Link>
              <button
                onClick={clear}
                className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
                style={{ color: "var(--neg)" }}
              >
                <Trash2 size={11} /> Clear all
              </button>
            </div>
          ) : undefined
        }
      />

      {rows.length === 0 ? (
        <Card padding="p-0">
          <div className="grid place-items-center gap-3 py-20 text-center">
            <span
              className="grid h-12 w-12 place-items-center rounded-full border"
              style={{ borderColor: "var(--line-strong)", color: "var(--text-dim)" }}
            >
              <Star size={20} />
            </span>
            <div>
              <p className="text-sm font-medium">Nothing starred yet</p>
              <p className="mt-1 text-[12px]" style={{ color: "var(--text-dim)" }}>
                Star a name anywhere in the dashboard and it collects here.
              </p>
            </div>
            <Link
              href="/screener"
              className="pill mt-1 focus-ring transition-colors hover:border-[var(--line-strong)]"
              style={{ color: "var(--text-muted)" }}
            >
              Browse all {meta.universeSize} names <ArrowUpRight size={12} />
            </Link>
          </div>
        </Card>
      ) : (
        <>
          {/* ---------------- aggregate ---------------- */}
          {agg && (
            <Card padding="p-5 sm:p-6">
              <SectionTitle
                title={`${rows.length} ${rows.length === 1 ? "name" : "names"}, equally weighted`}
                subtitle="Averages across the starred set, weighted the way the engine's own portfolio is weighted. Treat them as a sketch of the shortlist, not as a backtest of it."
              />
              <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
                {[
                  { l: "Avg score", v: agg.score, d: 1, s: "" },
                  { l: "Avg P/E", v: agg.pe, d: 1, s: "×" },
                  { l: "Avg ROE", v: (agg.roe ?? 0) * 100, d: 1, s: "%" },
                  { l: "Avg yield", v: (agg.yield ?? 0) * 100, d: 1, s: "%" },
                  { l: "Avg 1Y return", v: (agg.ret12 ?? 0) * 100, d: 1, s: "%" },
                  { l: "Avg beta", v: agg.beta, d: 2, s: "" },
                ].map((m, i) => (
                  <div key={m.l}>
                    <p className="label">{m.l}</p>
                    <p className="num mt-1 text-[20px] font-semibold leading-none">
                      <AnimatedNumber value={m.v} decimals={m.d} suffix={m.s} delay={i * 0.05} />
                    </p>
                  </div>
                ))}
              </div>

              <div
                className="mt-5 grid gap-4 border-t pt-4 sm:grid-cols-3"
                style={{ borderColor: "var(--line)" }}
              >
                <div>
                  <p className="label mb-1.5">Engine calls</p>
                  <p className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    <span className="num font-semibold" style={{ color: "var(--pos)" }}>
                      {agg.buys}
                    </span>{" "}
                    of {rows.length} sit in a buy band
                  </p>
                </div>
                <div>
                  <p className="label mb-1.5">Risk gates</p>
                  <p className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    <span
                      className="num font-semibold"
                      style={{ color: agg.flagged > 0 ? "var(--warn)" : "var(--pos)" }}
                    >
                      {agg.flagged}
                    </span>{" "}
                    {agg.flagged === 1 ? "name carries" : "names carry"} a flag
                  </p>
                </div>
                <div>
                  <p className="label mb-1.5">Concentration</p>
                  <p className="text-[12.5px]" style={{ color: "var(--text-muted)" }}>
                    <span
                      className="num font-semibold"
                      style={{ color: agg.concentration > 0.4 ? "var(--warn)" : "var(--text)" }}
                    >
                      {pct(agg.concentration, 0)}
                    </span>{" "}
                    in {agg.sectors[0]?.[0] ?? "—"}
                  </p>
                </div>
              </div>
            </Card>
          )}

          {/* ---------------- cards ---------------- */}
          <Stagger className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <AnimatePresence mode="popLayout">
              {rows.map((r) => (
                <motion.div
                  key={r.ticker}
                  layout
                  exit={{ opacity: 0, scale: 0.94 }}
                  transition={{ duration: 0.25 }}
                >
                  <Spotlight className="h-full rounded-2xl">
                    <Card hover className="h-full">
                      <div className="flex items-start justify-between gap-2">
                        <Link href={`/company/${r.ticker}`} className="min-w-0 focus-ring rounded">
                          <p className="num text-[15px] font-semibold tracking-tight">{r.ticker}</p>
                          <p
                            className="truncate text-[11.5px]"
                            style={{ color: "var(--text-muted)" }}
                          >
                            {r.name}
                          </p>
                        </Link>
                        <div className="flex shrink-0 items-center gap-1">
                          <span className={`pill ${bandClass(r.recommendation)}`}>
                            {r.recommendation}
                          </span>
                          <WatchButton ticker={r.ticker} />
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-between gap-3">
                        <ScoreRing
                          score={r.finalScore}
                          size={72}
                          stroke={6}
                          color={scoreColor(r.finalScore)}
                          label="score"
                        />
                        <div className="flex-1">
                          <Sparkline data={r.spark} width={110} height={32} />
                          <p
                            className="num mt-1 text-right text-[11px]"
                            style={{ color: (r.return12m ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}
                          >
                            {signedPct(r.return12m, 1)}{" "}
                            <span style={{ color: "var(--text-dim)" }}>1y</span>
                          </p>
                        </div>
                      </div>

                      <div
                        className="mt-4 grid grid-cols-4 gap-2 border-t pt-3 text-center"
                        style={{ borderColor: "var(--line)" }}
                      >
                        {[
                          { l: "Price", v: rupees(r.price, 1) },
                          { l: "P/E", v: mult(r.pe, 1) },
                          { l: "ROE", v: pct(r.roe, 0) },
                          { l: "F", v: num(r.fScore, 0) },
                        ].map((m) => (
                          <div key={m.l}>
                            <p className="label text-[9px]">{m.l}</p>
                            <p className="num mt-0.5 text-[12.5px]">{m.v}</p>
                          </div>
                        ))}
                      </div>

                      <div className="mt-3">
                        <Meter value={r.finalScore} color={scoreColor(r.finalScore)} height={4} />
                      </div>
                    </Card>
                  </Spotlight>
                </motion.div>
              ))}
            </AnimatePresence>
          </Stagger>

          {rows.length < tickers.length && (
            <Empty
              title="Some starred tickers are no longer in the index"
              hint="They were dropped from the KSE-100 between runs, so the engine has no current score for them."
            />
          )}
        </>
      )}

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        {meta.disclaimer}
      </p>
    </div>
  );
}
