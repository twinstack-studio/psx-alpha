"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import {
  ArrowDown, ArrowUp, Download, RotateCcw, Search, SlidersHorizontal, X,
} from "lucide-react";

import { Spotlight } from "@/components/motion";
import { Card, Meter, SectionTitle, Sparkline, Tabs } from "@/components/ui";
import { WatchButton } from "@/components/WatchButton";
import {
  bandClass, num, pct, pkrM, scoreColor, signedPct, PILLAR_SHORT,
} from "@/lib/format";
import type { Band, Dashboard, PillarKey } from "@/lib/types";

type SortKey =
  | "rank" | "ticker" | "score" | "pe" | "pb" | "roe" | "dividendYield"
  | "momentum12m" | "marketCap" | "fScore" | "return12m" | "debtToEquity";

const COLUMNS: { key: SortKey; label: string; align?: "right"; width?: string }[] = [
  { key: "rank", label: "#", width: "w-10" },
  { key: "ticker", label: "Company" },
  { key: "score", label: "Score", align: "right" },
  { key: "pe", label: "P/E", align: "right" },
  { key: "pb", label: "P/B", align: "right" },
  { key: "roe", label: "ROE", align: "right" },
  { key: "debtToEquity", label: "D/E", align: "right" },
  { key: "dividendYield", label: "Yield", align: "right" },
  { key: "return12m", label: "1Y", align: "right" },
  { key: "fScore", label: "F", align: "right" },
  { key: "marketCap", label: "Mkt cap", align: "right" },
];

const BANDS: Band[] = ["STRONG BUY", "BUY", "HOLD", "REDUCE", "AVOID"];

const DEFAULT_WEIGHTS: Record<PillarKey, number> = {
  quality: 30, value: 25, safety: 20, growth: 15, momentum: 10,
};

export function Screener({ data }: { data: Dashboard }) {
  const { recommendations, sectors, meta } = data;

  const [query, setQuery] = useState("");
  const [sector, setSector] = useState<string>("all");
  const [band, setBand] = useState<string>("all");
  const [sort, setSort] = useState<SortKey>("rank");
  const [dir, setDir] = useState<1 | -1>(1);
  const [tuning, setTuning] = useState(false);
  const [weights, setWeights] = useState<Record<PillarKey, number>>(DEFAULT_WEIGHTS);
  const [mlWeight, setMlWeight] = useState(Math.round(meta.blendWeight * 100));

  const customised =
    (Object.keys(DEFAULT_WEIGHTS) as PillarKey[]).some((k) => weights[k] !== DEFAULT_WEIGHTS[k]) ||
    mlWeight !== Math.round(meta.blendWeight * 100);

  /**
   * Re-score locally from the stored pillar z-scores. This is the same
   * arithmetic the Python scorer runs, so moving a slider shows exactly what
   * the engine would have produced under those weights - including the risk
   * caps, which still bind.
   */
  const scored = useMemo(() => {
    const total = Object.values(weights).reduce((a, b) => a + b, 0) || 1;
    const ml = mlWeight / 100;
    const rows = recommendations.map((r) => {
      if (!customised) return { ...r, customScore: r.finalScore ?? 0 };
      const z = (Object.keys(weights) as PillarKey[]).reduce(
        (acc, k) => acc + (r.pillarZ?.[k] ?? 0) * (weights[k] / total), 0,
      );
      const rule = Math.max(0, Math.min(100, 50 + (100 / 6) * z));
      let score = (1 - ml) * rule + ml * (r.mlScore ?? rule);
      if (r.scoreCap !== null && r.scoreCap !== undefined) score = Math.min(score, r.scoreCap);
      return { ...r, customScore: score };
    });
    rows.sort((a, b) => b.customScore - a.customScore);
    return rows.map((r, i) => ({ ...r, customRank: i + 1 }));
  }, [recommendations, weights, mlWeight, customised]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = scored.filter((r) => {
      if (sector !== "all" && r.sector !== sector) return false;
      if (band !== "all" && r.recommendation !== band) return false;
      if (q && !r.ticker.toLowerCase().includes(q) && !r.name.toLowerCase().includes(q)) return false;
      return true;
    });
    const get = (r: (typeof rows)[number]): number | string => {
      switch (sort) {
        case "rank": return r.customRank;
        case "ticker": return r.ticker;
        case "score": return -(r.customScore ?? 0);
        case "pe": return r.pe ?? 1e9;
        case "pb": return r.pb ?? 1e9;
        case "roe": return -(r.roe ?? -9);
        case "debtToEquity": return r.debtToEquity ?? 1e9;
        case "dividendYield": return -(r.dividendYield ?? -1);
        case "momentum12m": return -(r.momentum12m ?? -9);
        case "return12m": return -(r.return12m ?? -9);
        case "fScore": return -(r.fScore ?? -1);
        case "marketCap": return -(r.marketCap ?? -1);
        default: return r.customRank;
      }
    };
    rows = [...rows].sort((a, b) => {
      const x = get(a), y = get(b);
      const c = typeof x === "string" ? String(x).localeCompare(String(y)) : (x as number) - (y as number);
      return c * dir;
    });
    return rows;
  }, [scored, query, sector, band, sort, dir]);

  const toggleSort = (k: SortKey) => {
    if (k === sort) setDir((d) => (d === 1 ? -1 : 1));
    else {
      setSort(k);
      setDir(1);
    }
  };

  const reset = () => {
    setWeights(DEFAULT_WEIGHTS);
    setMlWeight(Math.round(meta.blendWeight * 100));
  };

  /**
   * Export exactly what is on screen — the current filter, sort and weighting
   * — so a table pasted into a write-up can be reproduced from the controls
   * above it. Raw ratios go out unrounded; formatting is the reader's job once
   * the numbers are in a spreadsheet.
   */
  const exportCsv = () => {
    const cols: [string, (r: (typeof filtered)[number]) => string | number | null][] = [
      ["rank", (r) => r.customRank],
      ["ticker", (r) => r.ticker],
      ["name", (r) => r.name],
      ["sector", (r) => r.sector],
      ["recommendation", (r) => r.recommendation],
      ["score", (r) => Number(r.customScore.toFixed(4))],
      ["rule_score", (r) => r.ruleScore],
      ["ml_score", (r) => r.mlScore],
      ["price", (r) => r.price],
      ["market_cap_pkr_m", (r) => r.marketCap],
      ["pe", (r) => r.pe],
      ["pb", (r) => r.pb],
      ["ev_ebitda", (r) => r.evEbitda],
      ["dividend_yield", (r) => r.dividendYield],
      ["roe", (r) => r.roe],
      ["roa", (r) => r.roa],
      ["net_margin", (r) => r.netMargin],
      ["debt_to_equity", (r) => r.debtToEquity],
      ["revenue_growth", (r) => r.revenueGrowth],
      ["earnings_growth", (r) => r.earningsGrowth],
      ["return_12m", (r) => r.return12m],
      ["volatility", (r) => r.volatility],
      ["beta", (r) => r.beta],
      ["f_score", (r) => r.fScore],
      ["z_score", (r) => r.zScore],
      ["risk_flags", (r) => r.riskFlags.join("; ")],
    ];

    // Quote every field and double any embedded quote: company names carry
    // commas, and risk flags carry both.
    const esc = (v: string | number | null) =>
      v === null || v === undefined ? "" : `"${String(v).replace(/"/g, '""')}"`;

    const csv = [
      cols.map(([h]) => esc(h)).join(","),
      ...filtered.map((r) => cols.map(([, get]) => esc(get(r))).join(",")),
    ].join("\r\n");

    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `psx-alpha-screen-${meta.asOf}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-6">
      <SectionTitle
        icon={<SlidersHorizontal size={16} />}
        title="Screener"
        subtitle={`All ${meta.universeSize} KSE-100 constituents, ranked by the composite. Open the weighting panel to re-run the score under your own priorities: the ranking updates instantly because every pillar's sector-relative z-score is precomputed.`}
        right={
          <Tabs
            size="sm"
            value={tuning ? "on" : "off"}
            onChange={(v) => setTuning(v === "on")}
            tabs={[{ id: "off", label: "Engine weights" }, { id: "on", label: "My weights" }]}
          />
        }
      />

      {/* ---------------- weight panel ---------------- */}
      <AnimatePresence initial={false}>
        {tuning && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <Card>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                  Weights are normalised, so only their ratio matters.
                </p>
                <button
                  onClick={reset}
                  className="pill focus-ring transition-colors hover:border-[var(--line-strong)]"
                  style={{ color: "var(--text-muted)" }}
                >
                  <RotateCcw size={11} /> Reset to engine defaults
                </button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {(Object.keys(DEFAULT_WEIGHTS) as PillarKey[]).map((k) => (
                  <label key={k} className="block">
                    <span className="mb-1.5 flex items-center justify-between text-[12.5px]">
                      <span>{meta.pillarLabels[k] ?? PILLAR_SHORT[k]}</span>
                      <span className="num" style={{ color: "var(--brand)" }}>{weights[k]}%</span>
                    </span>
                    <input
                      type="range" min={0} max={60} step={1} value={weights[k]}
                      onChange={(e) => setWeights((w) => ({ ...w, [k]: Number(e.target.value) }))}
                      className="w-full accent-[var(--brand)]"
                    />
                  </label>
                ))}
                <label className="block">
                  <span className="mb-1.5 flex items-center justify-between text-[12.5px]">
                    <span>Machine-learning ranker share</span>
                    <span className="num" style={{ color: "var(--brand-2)" }}>{mlWeight}%</span>
                  </span>
                  <input
                    type="range" min={0} max={100} step={5} value={mlWeight}
                    onChange={(e) => setMlWeight(Number(e.target.value))}
                    className="w-full accent-[var(--brand-2)]"
                  />
                </label>
              </div>
              {customised && (
                <p className="mt-4 border-t pt-3 text-[11.5px]"
                   style={{ borderColor: "var(--line)", color: "var(--warn)" }}>
                  Showing your weighting. Risk caps still apply, so a name in the Altman distress
                  zone cannot climb regardless of the sliders.
                </p>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---------------- filters ---------------- */}
      <Card padding="p-3.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative min-w-[200px] flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--text-dim)" }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter by ticker or company…"
              className="w-full rounded-lg border bg-transparent py-2 pl-9 pr-8 text-[13px] outline-none focus-ring"
              style={{ borderColor: "var(--line)" }}
            />
            {query && (
              <button onClick={() => setQuery("")} aria-label="Clear"
                      className="absolute right-2.5 top-1/2 -translate-y-1/2"
                      style={{ color: "var(--text-dim)" }}>
                <X size={13} />
              </button>
            )}
          </div>

          <select
            value={sector} onChange={(e) => setSector(e.target.value)}
            className="rounded-lg border bg-transparent px-3 py-2 text-[13px] outline-none focus-ring"
            style={{ borderColor: "var(--line)", background: "var(--surface-solid)" }}
          >
            <option value="all">All sectors</option>
            {sectors.map((s) => (
              <option key={s.sector} value={s.sector}>{s.sector} ({s.count})</option>
            ))}
          </select>

          <select
            value={band} onChange={(e) => setBand(e.target.value)}
            className="rounded-lg border bg-transparent px-3 py-2 text-[13px] outline-none focus-ring"
            style={{ borderColor: "var(--line)", background: "var(--surface-solid)" }}
          >
            <option value="all">Every band</option>
            {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>

          <span className="num ml-auto text-[12px]" style={{ color: "var(--text-dim)" }}>
            {filtered.length} of {recommendations.length}
          </span>

          <button
            onClick={exportCsv}
            disabled={filtered.length === 0}
            className="pill focus-ring transition-colors hover:border-[var(--line-strong)] disabled:opacity-40"
            style={{ color: "var(--text-muted)" }}
            title="Download the rows as filtered, sorted and weighted right now"
          >
            <Download size={11} /> CSV
          </button>
        </div>
      </Card>

      {/* ---------------- table ---------------- */}
      <Spotlight className="rounded-2xl" size={420} color="rgba(109,141,255,.16)">
      <Card padding="p-0" className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-[12.5px]">
            <thead>
              <tr style={{ background: "var(--surface)" }}>
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className={`label cursor-pointer select-none px-3 py-3 ${
                      c.align === "right" ? "text-right" : "text-left"
                    } ${c.width ?? ""}`}
                    style={{ color: sort === c.key ? "var(--brand)" : "var(--text-dim)" }}
                  >
                    <span className="inline-flex items-center gap-1">
                      {c.label}
                      {sort === c.key && (dir === 1 ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                    </span>
                  </th>
                ))}
                <th className="label px-3 py-3 text-left">Trend</th>
                <th className="label px-3 py-3 text-left">Call</th>
                <th className="label px-3 py-3 text-center" title="Watchlist">
                  <span className="sr-only">Watchlist</span>★
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <motion.tr
                  key={r.ticker}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.25, delay: Math.min(i * 0.006, 0.3) }}
                  className="border-t transition-colors hover:bg-[var(--surface-2)]"
                  style={{ borderColor: "var(--line)" }}
                >
                  <td className="num px-3 py-2.5" style={{ color: "var(--text-dim)" }}>
                    {r.customRank}
                  </td>
                  <td className="px-3 py-2.5">
                    <Link href={`/company/${r.ticker}`} className="group block focus-ring rounded">
                      <span className="num block text-[13px] font-semibold transition-colors group-hover:text-[var(--brand)]">
                        {r.ticker}
                      </span>
                      <span className="block max-w-[210px] truncate text-[11px]"
                            style={{ color: "var(--text-dim)" }}>
                        {r.name}
                      </span>
                    </Link>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center justify-end gap-2">
                      <Meter value={r.customScore} color={scoreColor(r.customScore)} height={4} />
                      <span className="num w-7 text-right font-semibold"
                            style={{ color: scoreColor(r.customScore) }}>
                        {num(r.customScore, 0)}
                      </span>
                    </div>
                  </td>
                  <td className="num px-3 py-2.5 text-right">{num(r.pe, 1)}</td>
                  <td className="num px-3 py-2.5 text-right">{num(r.pb, 2)}</td>
                  <td className="num px-3 py-2.5 text-right">{pct(r.roe, 0)}</td>
                  <td className="num px-3 py-2.5 text-right">{num(r.debtToEquity, 2)}</td>
                  <td className="num px-3 py-2.5 text-right">{pct(r.dividendYield, 1)}</td>
                  <td className="num px-3 py-2.5 text-right"
                      style={{ color: (r.return12m ?? 0) >= 0 ? "var(--pos)" : "var(--neg)" }}>
                    {signedPct(r.return12m, 0)}
                  </td>
                  <td className="num px-3 py-2.5 text-right"
                      style={{ color: (r.fScore ?? 0) >= 7 ? "var(--pos)" : (r.fScore ?? 9) <= 3 ? "var(--neg)" : "var(--text-muted)" }}>
                    {num(r.fScore, 0)}
                  </td>
                  <td className="num px-3 py-2.5 text-right" style={{ color: "var(--text-muted)" }}>
                    {pkrM(r.marketCap)}
                  </td>
                  <td className="px-3 py-2.5">
                    <Sparkline data={r.spark} width={68} height={22} animateDraw={false} strokeWidth={1.3} />
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`pill ${bandClass(r.recommendation)}`}>{r.recommendation}</span>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="grid place-items-center">
                      <WatchButton ticker={r.ticker} size={13} />
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <p className="py-14 text-center text-sm" style={{ color: "var(--text-dim)" }}>
            No company matches these filters.
          </p>
        )}
      </Card>
      </Spotlight>

      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
        Scores are relative to the KSE-100 on {meta.asOf}. {meta.disclaimer}
      </p>
    </div>
  );
}
