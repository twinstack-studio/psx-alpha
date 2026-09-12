"use client";

import { animate, motion, useInView, useMotionValue, useTransform } from "motion/react";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

/* ==========================================================================
   Reveal: fades content up the first time it enters the viewport.
   ========================================================================== */
export function Reveal({
  children, delay = 0, y = 14, className = "",
}: { children: ReactNode; delay?: number; y?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/* ==========================================================================
   AnimatedNumber: counts to its value once, then tracks prop changes.
   ========================================================================== */
/**
 * The motion value starts at the final number, so the server-rendered HTML and
 * the first client paint both carry the real figure - a reader with slow or
 * disabled JavaScript sees 21.21%, not 0.00%. A layout effect then resets it to
 * zero before the browser paints, so the count-up still runs without the true
 * value ever flashing on screen first.
 */
const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

export function AnimatedNumber({
  value, decimals = 0, prefix = "", suffix = "", duration = 1.1, delay = 0,
}: {
  value: number | null | undefined;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const valid = value !== null && value !== undefined && !Number.isNaN(value);
  const target = valid ? (value as number) : 0;

  const mv = useMotionValue(target);
  const text = useTransform(mv, (v) =>
    `${prefix}${v.toLocaleString("en-US", {
      minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    })}${suffix}`,
  );

  useIsomorphicLayoutEffect(() => {
    if (valid) mv.set(0);
    // Only on first mount: later prop changes should animate from where the
    // display already is, not restart from zero.
  }, []);

  useEffect(() => {
    if (!valid || !inView) return;
    const controls = animate(mv, target, { duration, delay, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [target, valid, inView, mv, duration, delay]);

  if (!valid) return <span ref={ref}>—</span>;
  return <motion.span ref={ref}>{text}</motion.span>;
}

/* ==========================================================================
   Card shell
   ========================================================================== */
export function Card({
  children, className = "", lit = true, hover = false, padding = "p-5",
}: {
  children: ReactNode; className?: string; lit?: boolean; hover?: boolean; padding?: string;
}) {
  return (
    <div className={`card ${lit ? "card-lit" : ""} ${hover ? "card-hover" : ""} ${padding} ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({
  title, subtitle, right, icon,
}: { title: string; subtitle?: string; right?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="flex items-start gap-2.5">
        {icon && <span className="mt-0.5" style={{ color: "var(--brand)" }}>{icon}</span>}
        <div>
          <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 max-w-2xl text-[12.5px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
      {right}
    </div>
  );
}

/* ==========================================================================
   Sparkline: a filled area with a drawn stroke, no library.
   ========================================================================== */
export function Sparkline({
  data, width = 110, height = 30, color, animateDraw = true, strokeWidth = 1.5,
}: {
  data: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
  animateDraw?: boolean;
  strokeWidth?: number;
}) {
  const pts = data.filter((d): d is number => d !== null && !Number.isNaN(d));
  // useId keeps the gradient id stable across renders and unique per
  // instance, without calling an impure function during render.
  const id = `sp${useId().replace(/[:«»]/g, "")}`;
  if (pts.length < 2) return <svg width={width} height={height} aria-hidden />;

  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1;
  const stroke = color ?? (pts[pts.length - 1] >= pts[0] ? "var(--pos)" : "var(--neg)");
  const step = width / (pts.length - 1);
  const xy = pts.map((v, i) => [i * step, height - ((v - min) / span) * (height - 3) - 1.5]);
  const d = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const area = `${d} L${width},${height} L0,${height} Z`;

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={
          animateDraw
            ? ({ strokeDasharray: 1400, "--len": 1400, animation: "draw 1.5s ease-out forwards" } as React.CSSProperties)
            : undefined
        }
      />
      <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r={2} fill={stroke} />
    </svg>
  );
}

/* ==========================================================================
   Meter: a labelled 0-100 bar that fills on reveal.
   ========================================================================== */
export function Meter({
  value, color, height = 6, delay = 0, track = "rgba(255,255,255,.07)",
}: { value: number | null; color: string; height?: number; delay?: number; track?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-30px" });
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div ref={ref} className="w-full overflow-hidden rounded-full" style={{ height, background: track }}>
      <motion.div
        className="h-full rounded-full"
        style={{ background: color }}
        initial={{ width: 0 }}
        animate={inView ? { width: `${v}%` } : {}}
        transition={{ duration: 0.85, delay, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  );
}

/* ==========================================================================
   ScoreRing: circular gauge for the headline composite score.
   ========================================================================== */
export function ScoreRing({
  score, size = 104, stroke = 8, color, label,
}: { score: number | null; size?: number; stroke?: number; color: string; label?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, score ?? 0));

  return (
    <div ref={ref} className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={inView ? { strokeDashoffset: c - (v / 100) * c } : {}}
          transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
          style={{ filter: `drop-shadow(0 0 7px ${color}66)` }}
        />
      </svg>
      <div className="absolute grid place-items-center text-center">
        <span className="num text-[22px] font-semibold leading-none" style={{ color }}>
          <AnimatedNumber value={score} decimals={0} />
        </span>
        {label && <span className="label mt-1 text-[9px]">{label}</span>}
      </div>
    </div>
  );
}

/* ==========================================================================
   Tabs
   ========================================================================== */
export function Tabs({
  tabs, value, onChange, size = "md",
}: {
  tabs: { id: string; label: string; count?: number }[];
  value: string;
  onChange: (id: string) => void;
  size?: "sm" | "md";
}) {
  const pad = size === "sm" ? "px-2.5 py-1.5 text-[11.5px]" : "px-3.5 py-2 text-[13px]";
  return (
    <div
      className="inline-flex flex-wrap gap-1 rounded-xl border p-1"
      style={{ borderColor: "var(--line)", background: "var(--surface)" }}
    >
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={`relative rounded-lg ${pad} font-medium transition-colors focus-ring`}
            style={{ color: active ? "var(--text)" : "var(--text-muted)" }}
          >
            {active && (
              <motion.span
                layoutId={`tab-${tabs.map((x) => x.id).join("")}`}
                className="absolute inset-0 rounded-lg border"
                style={{ background: "var(--surface-2)", borderColor: "var(--line-strong)" }}
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <span className="relative z-10">{t.label}</span>
            {t.count !== undefined && (
              <span className="num relative z-10 ml-1.5 text-[10px]" style={{ color: "var(--text-dim)" }}>
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ==========================================================================
   Tooltip on hover (title-style, but styled)
   ========================================================================== */
export function InfoDot({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
        aria-label={text}
        className="grid h-3.5 w-3.5 place-items-center rounded-full border text-[8px] focus-ring"
        style={{ borderColor: "var(--line-strong)", color: "var(--text-dim)" }}
      >
        i
      </button>
      {show && (
        <motion.span
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute bottom-full left-1/2 z-50 mb-1.5 w-56 -translate-x-1/2 rounded-lg border p-2.5 text-[11px] leading-relaxed"
          style={{
            borderColor: "var(--line-strong)", background: "var(--surface-solid)",
            color: "var(--text-muted)", boxShadow: "0 14px 34px -12px rgba(0,0,0,.9)",
          }}
        >
          {text}
        </motion.span>
      )}
    </span>
  );
}

/* ==========================================================================
   Empty state
   ========================================================================== */
export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="grid place-items-center gap-1 py-14 text-center">
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="text-[12px]" style={{ color: "var(--text-dim)" }}>{hint}</p>}
    </div>
  );
}
