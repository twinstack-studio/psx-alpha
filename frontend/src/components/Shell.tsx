"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity, BookOpen, BrainCircuit, GitCompareArrows, LayoutDashboard, LineChart, Menu,
  Search, Star, X,
} from "lucide-react";

import { CommandPalette, type IndexEntry } from "./CommandPalette";
import { ScrollProgress } from "./motion";
import { TickerTape, type TickerItem } from "./TickerTape";
import { shortDate } from "@/lib/format";
import { useWatchlist } from "@/lib/watchlist";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard, hint: "Today's ranking" },
  { href: "/screener", label: "Screener", icon: Activity, hint: "All 101 names" },
  { href: "/compare", label: "Compare", icon: GitCompareArrows, hint: "Side by side" },
  { href: "/watchlist", label: "Watchlist", icon: Star, hint: "Your shortlist" },
  { href: "/backtest", label: "Backtest", icon: LineChart, hint: "Evidence" },
  { href: "/model", label: "Model", icon: BrainCircuit, hint: "Diagnostics" },
  { href: "/method", label: "Method", icon: BookOpen, hint: "How it works" },
];

export function Shell({
  children, asOf, universeSize, index, ticker,
}: {
  children: React.ReactNode;
  asOf: string;
  universeSize: number;
  index: IndexEntry[];
  ticker: TickerItem[];
}) {
  const { count: watchCount } = useWatchlist();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {NAV.map((item) => {
        const active = isActive(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            className="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors focus-ring"
            style={{ color: active ? "var(--text)" : "var(--text-muted)" }}
          >
            {active && (
              <motion.span
                layoutId="nav-active"
                className="absolute inset-0 rounded-xl border"
                style={{
                  background: "linear-gradient(100deg, rgba(109,141,255,.17), rgba(167,139,250,.07))",
                  borderColor: "rgba(109,141,255,.28)",
                }}
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <Icon
              size={16}
              className="relative z-10 shrink-0 transition-transform group-hover:scale-110"
              style={{ color: active ? "var(--brand)" : "currentColor" }}
            />
            <span className="relative z-10 font-medium">{item.label}</span>

            {/* The watchlist count replaces the hover hint when it is non-zero,
                so the sidebar always says how many names are starred. */}
            {item.href === "/watchlist" && watchCount > 0 ? (
              <motion.span
                key={watchCount}
                initial={{ scale: 0.5, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 520, damping: 24 }}
                className="num relative z-10 ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                style={{ background: "rgba(251,191,36,.15)", color: "var(--warn)" }}
              >
                {watchCount}
              </motion.span>
            ) : (
              <span
                className="relative z-10 ml-auto text-[10px] opacity-0 transition-opacity group-hover:opacity-100"
                style={{ color: "var(--text-dim)" }}
              >
                {item.hint}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  const brand = (
    <Link href="/" className="flex items-center gap-3 focus-ring rounded-lg">
      <motion.span
        className="grid h-9 w-9 place-items-center rounded-xl text-[13px] font-bold"
        style={{
          background: "linear-gradient(135deg, var(--brand), var(--brand-2))",
          color: "#080a14",
          boxShadow: "0 6px 22px -8px rgba(109,141,255,.85)",
        }}
        whileHover={{ rotate: [0, -9, 9, 0], scale: 1.08 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      >
        PX
      </motion.span>
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold tracking-tight">PSX Alpha</span>
        <span className="block text-[10.5px]" style={{ color: "var(--text-dim)" }}>
          KSE-100 research engine
        </span>
      </span>
    </Link>
  );

  return (
    <>
      <ScrollProgress />
      <div className="min-h-screen lg:grid lg:grid-cols-[264px_1fr]">
      {/* ---------- desktop sidebar ---------- */}
      <aside
        className="sticky top-0 hidden h-screen flex-col justify-between border-r px-4 py-6 lg:flex"
        style={{ borderColor: "var(--line)", background: "rgba(6,7,16,.55)", backdropFilter: "blur(18px)" }}
      >
        <div className="flex flex-col gap-7">
          {brand}
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2.5 rounded-xl border px-3 py-2 text-left text-[13px] transition-colors focus-ring"
            style={{ borderColor: "var(--line)", background: "var(--surface)", color: "var(--text-dim)" }}
          >
            <Search size={14} />
            <span className="flex-1">Search a company…</span>
            <kbd
              className="num rounded-md border px-1.5 py-0.5 text-[10px]"
              style={{ borderColor: "var(--line)", color: "var(--text-dim)" }}
            >
              ⌘K
            </kbd>
          </button>
          {nav}
        </div>

        <div className="flex flex-col gap-3">
          <div className="divider" />
          <div className="flex items-center gap-2 text-[11px]" style={{ color: "var(--text-dim)" }}>
            <span className="pulse-dot h-1.5 w-1.5 rounded-full" style={{ background: "var(--pos)" }} />
            <span>
              Data as of <span className="num" style={{ color: "var(--text-muted)" }}>{shortDate(asOf)}</span>
            </span>
          </div>
          <p className="text-[10.5px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
            {universeSize} KSE-100 constituents. Research and educational project, not investment advice.
          </p>
        </div>
      </aside>

      {/* ---------- mobile top bar ---------- */}
      <header
        className="sticky top-0 z-40 flex items-center justify-between border-b px-4 py-3 lg:hidden"
        style={{ borderColor: "var(--line)", background: "rgba(6,7,16,.86)", backdropFilter: "blur(16px)" }}
      >
        {brand}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPaletteOpen(true)}
            aria-label="Search"
            className="rounded-lg p-2 focus-ring"
            style={{ color: "var(--text-muted)" }}
          >
            <Search size={18} />
          </button>
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 focus-ring"
            style={{ color: "var(--text-muted)" }}
          >
            <Menu size={18} />
          </button>
        </div>
      </header>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-50 lg:hidden"
              style={{ background: "rgba(3,4,10,.7)", backdropFilter: "blur(4px)" }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="fixed right-0 top-0 z-50 flex h-full w-[264px] flex-col gap-6 border-l p-5 lg:hidden"
              style={{ borderColor: "var(--line)", background: "var(--bg-2)" }}
              initial={{ x: 300 }}
              animate={{ x: 0 }}
              exit={{ x: 300 }}
              transition={{ type: "spring", stiffness: 380, damping: 38 }}
            >
              <div className="flex items-center justify-between">
                <span className="label">Navigate</span>
                <button
                  onClick={() => setMobileOpen(false)}
                  aria-label="Close menu"
                  className="rounded-lg p-1.5 focus-ring"
                  style={{ color: "var(--text-muted)" }}
                >
                  <X size={18} />
                </button>
              </div>
              {nav}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ---------- content ---------- */}
      <main className="min-w-0">
        <TickerTape items={ticker} />
        <AnimatePresence mode="wait">
          <motion.div
            key={pathname}
            initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto w-full max-w-[1360px] px-4 py-7 sm:px-6 lg:px-9 lg:py-10"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {paletteOpen && (
          <CommandPalette onClose={() => setPaletteOpen(false)} index={index} />
        )}
      </AnimatePresence>
      </div>
    </>
  );
}
