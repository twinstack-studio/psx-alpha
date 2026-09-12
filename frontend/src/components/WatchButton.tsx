"use client";

import { AnimatePresence, motion } from "motion/react";
import { Star } from "lucide-react";
import { useState } from "react";

import { useWatchlist } from "@/lib/watchlist";

/**
 * The star that adds a name to the watchlist. Starring fires a short burst of
 * rays — the one place in the dashboard where a decorative flourish is the
 * point, because it is the only control that records what the reader thinks
 * rather than what the engine thinks.
 */
export function WatchButton({
  ticker,
  size = 14,
  className = "",
}: {
  ticker: string;
  size?: number;
  className?: string;
}) {
  const { has, toggle } = useWatchlist();
  const [burst, setBurst] = useState(0);
  const on = has(ticker);

  return (
    <button
      type="button"
      aria-label={on ? `Remove ${ticker} from watchlist` : `Add ${ticker} to watchlist`}
      aria-pressed={on}
      onClick={(e) => {
        // Stars usually sit inside a link to the company page.
        e.preventDefault();
        e.stopPropagation();
        if (!on) setBurst((b) => b + 1);
        toggle(ticker);
      }}
      className={`relative grid place-items-center rounded-md p-1 transition-colors focus-ring ${className}`}
      style={{ color: on ? "var(--warn)" : "var(--text-dim)" }}
    >
      <motion.span
        className="grid place-items-center"
        animate={on ? { scale: [1, 1.38, 1], rotate: [0, 14, 0] } : { scale: 1, rotate: 0 }}
        transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
      >
        <Star size={size} fill={on ? "var(--warn)" : "none"} strokeWidth={on ? 1.6 : 1.8} />
      </motion.span>

      <AnimatePresence>
        {burst > 0 && on && (
          <motion.span
            key={burst}
            className="pointer-events-none absolute inset-0"
            initial={{ opacity: 1 }}
            animate={{ opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.55 }}
          >
            {Array.from({ length: 6 }).map((_, i) => {
              const a = (Math.PI * 2 * i) / 6;
              return (
                <motion.span
                  key={i}
                  className="absolute left-1/2 top-1/2 h-[2px] w-[2px] rounded-full"
                  style={{ background: "var(--warn)" }}
                  initial={{ x: 0, y: 0, opacity: 1 }}
                  animate={{ x: Math.cos(a) * 13, y: Math.sin(a) * 13, opacity: 0 }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              );
            })}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}
