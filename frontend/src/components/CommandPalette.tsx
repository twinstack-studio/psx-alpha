"use client";

import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, BookOpen, BrainCircuit, CornerDownLeft, GitCompareArrows, LayoutDashboard,
  LineChart, Search, Star,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { bandClass, num } from "@/lib/format";
import { useWatchlist } from "@/lib/watchlist";
import type { Band } from "@/lib/types";

export interface IndexEntry {
  ticker: string;
  name: string;
  sector: string;
  band: Band;
  score: number | null;
  rank: number;
}

/** Pages are reachable from the palette as well as the sidebar. */
const PAGES: { href: string; label: string; hint: string; icon: LucideIcon; keywords: string }[] = [
  { href: "/", label: "Overview", hint: "Today's ranking", icon: LayoutDashboard, keywords: "home dashboard top picks" },
  { href: "/screener", label: "Screener", hint: "Every name, your own weights", icon: Activity, keywords: "filter sort table rank weights" },
  { href: "/compare", label: "Compare", hint: "Up to four names side by side", icon: GitCompareArrows, keywords: "versus vs side by side radar" },
  { href: "/watchlist", label: "Watchlist", hint: "Your starred names", icon: Star, keywords: "starred saved shortlist favourites" },
  { href: "/backtest", label: "Backtest", hint: "Walk-forward evidence", icon: LineChart, keywords: "performance returns drawdown equity curve" },
  { href: "/model", label: "Model", hint: "ML diagnostics", icon: BrainCircuit, keywords: "xgboost features importance ic folds" },
  { href: "/method", label: "Method", hint: "How the engine works", icon: BookOpen, keywords: "methodology pillars piotroski altman explanation" },
];

type Result =
  | { kind: "page"; id: string; page: (typeof PAGES)[number] }
  | { kind: "company"; id: string; entry: IndexEntry };

/**
 * Ranks an exact ticker first, then prefix matches, then substring matches,
 * with pages interleaved by their own match strength. A bare palette shows
 * the pages plus the highest-ranked names, so it is useful before typing.
 */
function search(entries: IndexEntry[], q: string): Result[] {
  const query = q.trim().toLowerCase();

  if (!query) {
    return [
      ...PAGES.map((p): Result => ({ kind: "page", id: p.href, page: p })),
      ...entries.slice(0, 5).map((e): Result => ({ kind: "company", id: e.ticker, entry: e })),
    ];
  }

  const scored: { r: Result; s: number; tie: number }[] = [];

  for (const p of PAGES) {
    const l = p.label.toLowerCase();
    let s = -1;
    if (l === query) s = 0;
    else if (l.startsWith(query)) s = 1;
    else if (l.includes(query) || p.keywords.includes(query)) s = 3;
    if (s >= 0) scored.push({ r: { kind: "page", id: p.href, page: p }, s, tie: 0 });
  }

  for (const e of entries) {
    const t = e.ticker.toLowerCase();
    const n = e.name.toLowerCase();
    let s = -1;
    if (t === query) s = 0;
    else if (t.startsWith(query)) s = 1;
    else if (n.startsWith(query)) s = 2;
    else if (t.includes(query)) s = 3;
    else if (n.includes(query)) s = 4;
    else if (e.sector.toLowerCase().includes(query)) s = 5;
    if (s >= 0) scored.push({ r: { kind: "company", id: e.ticker, entry: e }, s, tie: e.rank });
  }

  scored.sort((a, b) => a.s - b.s || a.tie - b.tie);
  return scored.slice(0, 10).map((x) => x.r);
}

/**
 * The palette is mounted only while it is open, so opening it always starts
 * from an empty query with the cursor at the top. That is React's own answer
 * to "reset state when something changes": remount, rather than synchronise
 * with an effect. The parent supplies the exit animation.
 */
export function CommandPalette({
  onClose, index,
}: {
  onClose: () => void;
  index: IndexEntry[];
}) {
  const router = useRouter();
  const { has, toggle } = useWatchlist();
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => search(index, q), [index, q]);

  // Moving focus is a DOM side effect, which is what an effect is for.
  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 40);
    return () => clearTimeout(t);
  }, []);

  const run = (r: Result) => {
    onClose();
    router.push(r.kind === "page" ? r.page.href : `/company/${r.entry.ticker}`);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") return onClose();
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, results.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    }
    // Tab stars the highlighted company without leaving the palette, so a
    // shortlist can be built in one pass.
    if (e.key === "Tab") {
      const r = results[cursor];
      if (r?.kind === "company") {
        e.preventDefault();
        toggle(r.entry.ticker);
      }
    }
    if (e.key === "Enter" && results[cursor]) {
      e.preventDefault();
      run(results[cursor]);
    }
  };

  return (
    <>
      <motion.div
        className="fixed inset-0 z-[60]"
        style={{ background: "rgba(3,4,10,.72)", backdropFilter: "blur(6px)" }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="fixed inset-x-4 top-[12vh] z-[61] mx-auto max-w-xl overflow-hidden rounded-2xl border"
        style={{
          borderColor: "var(--line-strong)",
          background: "var(--surface-solid)",
          boxShadow: "0 40px 90px -30px rgba(0,0,0,.95)",
        }}
        initial={{ opacity: 0, y: -14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -10, scale: 0.985 }}
        transition={{ type: "spring", stiffness: 380, damping: 32 }}
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b px-4 py-3.5" style={{ borderColor: "var(--line)" }}>
          <Search size={16} style={{ color: "var(--text-dim)" }} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setCursor(0);
            }}
            placeholder="Jump to a page, ticker, company or sector…"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text)" }}
          />
          <kbd
            className="num rounded-md border px-1.5 py-0.5 text-[10px]"
            style={{ borderColor: "var(--line)", color: "var(--text-dim)" }}
          >
            ESC
          </kbd>
        </div>

        <div className="max-h-[54vh] overflow-y-auto p-1.5">
          {results.length === 0 && (
            <p className="px-3 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
              Nothing matches “{q}”.
            </p>
          )}

          {results.map((r, i) => {
            const active = i === cursor;
            if (r.kind === "page") {
              const Icon = r.page.icon;
              return (
                <button
                  key={r.id}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => run(r)}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors"
                  style={{ background: active ? "var(--surface-2)" : "transparent" }}
                >
                  <span
                    className="grid h-8 w-12 shrink-0 place-items-center rounded-lg border"
                    style={{ borderColor: "var(--line)", background: "var(--surface)", color: "var(--brand)" }}
                  >
                    <Icon size={15} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px]">{r.page.label}</span>
                    <span className="block truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                      {r.page.hint}
                    </span>
                  </span>
                  <span className="label text-[9px]">Page</span>
                  {active && <CornerDownLeft size={13} style={{ color: "var(--text-dim)" }} />}
                </button>
              );
            }

            const e = r.entry;
            const starred = has(e.ticker);
            return (
              <button
                key={r.id}
                onMouseEnter={() => setCursor(i)}
                onClick={() => run(r)}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors"
                style={{ background: active ? "var(--surface-2)" : "transparent" }}
              >
                <span
                  className="num grid h-8 w-12 shrink-0 place-items-center rounded-lg border text-[11px] font-semibold"
                  style={{ borderColor: "var(--line)", background: "var(--surface)" }}
                >
                  {e.ticker}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 truncate text-[13px]">
                    {e.name}
                    {starred && <Star size={10} fill="var(--warn)" style={{ color: "var(--warn)" }} />}
                  </span>
                  <span className="block truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                    {e.sector}
                  </span>
                </span>
                <span className={`pill ${bandClass(e.band)}`}>{e.band}</span>
                <span className="num w-9 text-right text-xs" style={{ color: "var(--text-muted)" }}>
                  {num(e.score, 0)}
                </span>
                {active && <CornerDownLeft size={13} style={{ color: "var(--text-dim)" }} />}
              </button>
            );
          })}
        </div>

        <div
          className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t px-4 py-2 text-[10.5px]"
          style={{ borderColor: "var(--line)", color: "var(--text-dim)" }}
        >
          <span>
            <kbd className="num">↑↓</kbd> move
          </span>
          <span>
            <kbd className="num">↵</kbd> open
          </span>
          <span>
            <kbd className="num">Tab</kbd> star
          </span>
          <span>
            <kbd className="num">Esc</kbd> close
          </span>
        </div>
      </motion.div>
    </>
  );
}
