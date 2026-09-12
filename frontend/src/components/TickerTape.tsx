"use client";

/**
 * The strip of running quotes along the top of the dashboard.
 *
 * It is the one piece of chrome that carries the whole universe at once: 101
 * names, their last price, their twelve-month move and the band the engine put
 * them in. Hovering pauses the run so a name can actually be read and clicked.
 */

import Link from "next/link";
import { ArrowDown, ArrowUp } from "lucide-react";

import { Marquee } from "./motion";
import { Sparkline } from "./ui";
import { bandColor, rupees, signedPct } from "@/lib/format";

export interface TickerItem {
  ticker: string;
  price: number | null;
  return12m: number | null;
  band: string;
  spark: (number | null)[];
}

export function TickerTape({ items }: { items: TickerItem[] }) {
  if (items.length === 0) return null;

  return (
    <div
      className="relative border-b"
      style={{
        borderColor: "var(--line)",
        background: "linear-gradient(180deg, rgba(9,11,22,.92), rgba(6,7,16,.72))",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Fades at both ends so names arrive and leave rather than popping. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16"
        style={{ background: "linear-gradient(90deg, var(--bg), transparent)" }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16"
        style={{ background: "linear-gradient(270deg, var(--bg), transparent)" }}
      />

      <Marquee speed={54} className="py-2">
        {items.map((it) => {
          const up = (it.return12m ?? 0) >= 0;
          const color = up ? "var(--pos)" : "var(--neg)";
          return (
            <Link
              key={it.ticker}
              href={`/company/${it.ticker}`}
              className="group flex shrink-0 items-center gap-2.5 border-r px-4 py-0.5 transition-colors focus-ring"
              style={{ borderColor: "var(--line)" }}
            >
              <span
                className="h-3.5 w-[2px] shrink-0 rounded-full"
                style={{ background: bandColor(it.band) }}
              />
              <span className="num text-[12px] font-semibold tracking-tight transition-colors group-hover:text-[var(--brand)]">
                {it.ticker}
              </span>
              <span className="num text-[11.5px]" style={{ color: "var(--text-muted)" }}>
                {rupees(it.price, 1)}
              </span>
              <span className="num inline-flex items-center gap-0.5 text-[11.5px]" style={{ color }}>
                {up ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                {signedPct(it.return12m, 1)}
              </span>
              <Sparkline
                data={it.spark}
                width={44}
                height={15}
                animateDraw={false}
                strokeWidth={1.2}
              />
            </Link>
          );
        })}
      </Marquee>
    </div>
  );
}
