"use client";

import { motion } from "motion/react";
import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { compact, monthYear, num, pct, shortDate, signedPct, STRATEGY_COLOR } from "@/lib/format";
import { Tabs } from "./ui";

/* ==========================================================================
   Shared tooltip
   ========================================================================== */
function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-xl border px-3 py-2.5 text-[12px]"
      style={{
        borderColor: "var(--line-strong)",
        background: "rgba(10,13,24,.96)",
        backdropFilter: "blur(10px)",
        boxShadow: "0 18px 40px -16px rgba(0,0,0,.95)",
      }}
    >
      {children}
    </div>
  );
}

/**
 * Recharts types its tooltip payload loosely and as readonly, so the local
 * shape has to be a supertype of theirs for the `content` callback to be
 * assignable. Values are narrowed to a number at the point of use.
 */
type TipEntry = {
  name?: number | string;
  dataKey?: unknown;
  value?: number | string | readonly (number | string)[];
  color?: string;
};

type TipProps = {
  active?: boolean;
  payload?: readonly TipEntry[];
  label?: string | number;
};

const toNumber = (v: TipEntry["value"]): number | null => {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
};

function SeriesTip({ active, payload, label, fmt, heading }: TipProps & {
  fmt: (v: number) => string;
  heading?: (l: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <Panel>
      <p className="num mb-1.5 text-[10.5px]" style={{ color: "var(--text-dim)" }}>
        {heading ? heading(String(label)) : String(label)}
      </p>
      <div className="flex flex-col gap-1">
        {payload.map((p, i) => {
          const v = toNumber(p.value);
          return (
            <div key={`${String(p.dataKey)}-${i}`} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.color }} />
              <span className="flex-1" style={{ color: "var(--text-muted)" }}>{p.name}</span>
              <span className="num font-medium">{v === null ? "—" : fmt(v)}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/* ==========================================================================
   Equity curve: growth of PKR 100, strategies vs the KSE-100
   ========================================================================== */
export function EquityChart({
  data, series, height = 320, logScale = false,
}: {
  data: Record<string, number | string | null>[];
  series: { key: string; label: string }[];
  height?: number;
  logScale?: boolean;
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const toggle = (k: string) =>
    setHidden((h) => {
      const n = new Set(h);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  const visible = series.filter((s) => !hidden.has(s.key));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {series.map((s) => {
          const off = hidden.has(s.key);
          return (
            <button
              key={s.key}
              onClick={() => toggle(s.key)}
              className="flex items-center gap-1.5 text-[11.5px] transition-opacity focus-ring rounded"
              style={{ opacity: off ? 0.38 : 1, color: "var(--text-muted)" }}
            >
              <span
                className="h-[3px] w-4 rounded-full"
                style={{ background: STRATEGY_COLOR[s.key] ?? "var(--brand)" }}
              />
              {s.label}
            </button>
          );
        })}
        <span className="ml-auto text-[10.5px]" style={{ color: "var(--text-dim)" }}>
          Growth of Rs 100 · click a legend entry to isolate
        </span>
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`eq-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={STRATEGY_COLOR[s.key] ?? "var(--brand)"} stopOpacity={0.26} />
                <stop offset="100%" stopColor={STRATEGY_COLOR[s.key] ?? "var(--brand)"} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date" tickLine={false} axisLine={false} minTickGap={48}
            tickFormatter={(v: string) => monthYear(v)}
          />
          <YAxis
            tickLine={false} axisLine={false} width={54}
            scale={logScale ? "log" : "auto"}
            domain={logScale ? ["auto", "auto"] : [0, "auto"]}
            tickFormatter={(v: number) => compact(v)}
          />
          <Tooltip
            content={(p: TipProps) => (
              <SeriesTip {...p} fmt={(v) => `Rs ${num(v, 1)}`} heading={(l) => shortDate(l)} />
            )}
          />
          <ReferenceLine y={100} stroke="rgba(255,255,255,.14)" strokeDasharray="4 4" />
          {visible.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={STRATEGY_COLOR[s.key] ?? "var(--brand)"}
              strokeWidth={s.key === "KSE100" ? 1.6 : 2.1}
              strokeDasharray={s.key === "KSE100" ? "5 4" : undefined}
              fill={`url(#eq-${s.key})`}
              dot={false}
              activeDot={{ r: 3.5, strokeWidth: 0 }}
              isAnimationActive
              animationDuration={1100}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ==========================================================================
   Drawdown: strategy against benchmark, both negative
   ========================================================================== */
export function DrawdownChart({
  data, height = 200,
}: { data: { date: string; strategy: number | null; benchmark: number | null }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="dd-s" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fb7185" stopOpacity={0} />
            <stop offset="100%" stopColor="#fb7185" stopOpacity={0.3} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={48}
               tickFormatter={(v: string) => monthYear(v)} />
        <YAxis tickLine={false} axisLine={false} width={50}
               tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip content={(p: TipProps) => (
          <SeriesTip {...p} fmt={(v) => pct(v, 1)} heading={(l) => shortDate(l)} />
        )} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,.18)" />
        <Area type="monotone" dataKey="benchmark" name="KSE-100" stroke="#8b95ad"
              strokeWidth={1.3} strokeDasharray="5 4" fill="none" dot={false} />
        <Area type="monotone" dataKey="strategy" name="Blended engine" stroke="#fb7185"
              strokeWidth={1.9} fill="url(#dd-s)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ==========================================================================
   Yearly return bars, strategy vs benchmark
   ========================================================================== */
export function YearlyBars({
  data, height = 230,
}: { data: { year: number; strategy: number; benchmark: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 6, left: -18, bottom: 0 }} barGap={3}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="year" tickLine={false} axisLine={false} />
        <YAxis tickLine={false} axisLine={false} width={50}
               tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,.04)" }}
                 content={(p: TipProps) => <SeriesTip {...p} fmt={(v) => signedPct(v, 1)} />} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,.2)" />
        <Bar dataKey="strategy" name="Blended engine" radius={[3, 3, 0, 0]} isAnimationActive animationDuration={900}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.strategy >= 0 ? "#6d8dff" : "#fb7185"} />
          ))}
        </Bar>
        <Bar dataKey="benchmark" name="KSE-100" radius={[3, 3, 0, 0]} fill="#4b5468"
             isAnimationActive animationDuration={900} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ==========================================================================
   Price history with a range switcher
   ========================================================================== */
export function PriceChart({
  data, height = 280,
}: { data: { date: string; close: number }[]; height?: number }) {
  const [range, setRange] = useState("all");
  const sliced = useMemo(() => {
    // Price history is weekly, so these are weeks of data to keep.
    const weeks: Record<string, number> = { "1y": 52, "3y": 156, "5y": 260 };
    const keep = weeks[range] ?? data.length;
    return data.slice(Math.max(0, data.length - keep));
  }, [data, range]);
  const up = sliced.length > 1 && sliced[sliced.length - 1].close >= sliced[0].close;
  const color = up ? "#34d399" : "#fb7185";
  const change = sliced.length > 1 ? sliced[sliced.length - 1].close / sliced[0].close - 1 : 0;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="num text-[13px]" style={{ color: up ? "var(--pos)" : "var(--neg)" }}>
          {signedPct(change, 1)}{" "}
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>over this window</span>
        </span>
        <Tabs
          size="sm"
          value={range}
          onChange={setRange}
          tabs={[
            { id: "1y", label: "1Y" }, { id: "3y", label: "3Y" },
            { id: "5y", label: "5Y" }, { id: "all", label: "Max" },
          ]}
        />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={sliced} margin={{ top: 6, right: 6, left: -14, bottom: 0 }}>
          <defs>
            <linearGradient id="px-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={44}
                 tickFormatter={(v: string) => monthYear(v)} />
          <YAxis tickLine={false} axisLine={false} width={54} domain={["auto", "auto"]}
                 tickFormatter={(v: number) => compact(v)} />
          <Tooltip content={(p: TipProps) => (
            <SeriesTip {...p} fmt={(v) => `Rs ${num(v, 2)}`} heading={(l) => shortDate(l)} />
          )} />
          <Area type="monotone" dataKey="close" name="Close" stroke={color} strokeWidth={2}
                fill="url(#px-grad)" dot={false} activeDot={{ r: 3.5, strokeWidth: 0 }}
                isAnimationActive animationDuration={900} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ==========================================================================
   Macro: policy rate, inflation and the rupee on one switchable axis
   ========================================================================== */
export function MacroChart({
  data, height = 240,
}: {
  data: { date: string; policyRate: number | null; cpi: number | null; usdPkr: number | null }[];
  height?: number;
}) {
  const [view, setView] = useState("rates");
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Tabs
          size="sm" value={view} onChange={setView}
          tabs={[{ id: "rates", label: "Rate & inflation" }, { id: "fx", label: "USD/PKR" }]}
        />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 6, right: 6, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={50}
                 tickFormatter={(v: string) => monthYear(v)} />
          <YAxis tickLine={false} axisLine={false} width={48}
                 tickFormatter={(v: number) => (view === "fx" ? compact(v) : `${v}%`)} />
          <Tooltip content={(p: TipProps) => (
            <SeriesTip {...p} fmt={(v) => (view === "fx" ? num(v, 1) : `${num(v, 2)}%`)}
                       heading={(l) => monthYear(l)} />
          )} />
          {view === "rates" ? (
            <>
              <Line type="monotone" dataKey="policyRate" name="SBP policy rate" stroke="#6d8dff"
                    strokeWidth={2} dot={false} isAnimationActive animationDuration={900} />
              <Line type="monotone" dataKey="cpi" name="CPI year on year" stroke="#fbbf24"
                    strokeWidth={2} dot={false} isAnimationActive animationDuration={900} />
            </>
          ) : (
            <Line type="monotone" dataKey="usdPkr" name="USD/PKR" stroke="#22d3ee"
                  strokeWidth={2} dot={false} isAnimationActive animationDuration={900} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ==========================================================================
   Horizontal bars for model feature importance
   ========================================================================== */
export function ImportanceBars({
  data, height = 420,
}: { data: { label: string; value: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, left: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={false}
               tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
        <YAxis type="category" dataKey="label" width={186} tickLine={false} axisLine={false}
               tick={{ fontSize: 11 }} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,.04)" }}
                 content={(p: TipProps) => <SeriesTip {...p} fmt={(v) => pct(v, 1)} />} />
        <Bar dataKey="value" name="Share of model gain" radius={[0, 4, 4, 0]}
             isAnimationActive animationDuration={950}>
          {data.map((_, i) => (
            <Cell key={i} fill={`hsl(${228 - i * 3.4} 92% ${70 - i * 1.5}%)`} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ==========================================================================
   Information coefficient per walk-forward fold
   ========================================================================== */
export function IcChart({
  data, height = 240,
}: { data: { date: string; ic: number | null }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 6, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={36}
               tickFormatter={(v: string) => monthYear(v)} />
        <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => num(v, 2)} />
        <Tooltip cursor={{ fill: "rgba(255,255,255,.04)" }}
                 content={(p: TipProps) => (
                   <SeriesTip {...p} fmt={(v) => num(v, 3)} heading={(l) => shortDate(l)} />
                 )} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,.22)" />
        <Bar dataKey="ic" name="Rank correlation" radius={[3, 3, 0, 0]}
             isAnimationActive animationDuration={900}>
          {data.map((d, i) => (
            <Cell key={i} fill={(d.ic ?? 0) >= 0 ? "#34d399" : "#fb7185"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ==========================================================================
   Pillar radar, hand-drawn so it matches the rest of the surface
   ========================================================================== */
export function PillarRadar({
  pillars, size = 230,
}: { pillars: { label: string; score: number | null }[]; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 34;
  const n = pillars.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, v: number) => [
    cx + Math.cos(angle(i)) * r * v,
    cy + Math.sin(angle(i)) * r * v,
  ];

  const poly = pillars
    .map((p, i) => point(i, Math.max(0.04, (p.score ?? 0) / 100)))
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");

  return (
    <svg width={size} height={size} className="overflow-visible">
      <defs>
        <linearGradient id="radar-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6d8dff" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon
          key={ring}
          points={pillars
            .map((_, i) => point(i, ring))
            .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
            .join(" ")}
          fill="none"
          stroke="rgba(255,255,255,.07)"
        />
      ))}
      {pillars.map((_, i) => {
        const [x, y] = point(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(255,255,255,.07)" />;
      })}
      <polygon points={poly} fill="url(#radar-fill)" stroke="#6d8dff" strokeWidth={1.8}
               style={{ transformOrigin: "center", animation: "draw .9s ease-out" }} />
      {pillars.map((p, i) => {
        const [x, y] = point(i, 1.24);
        return (
          <g key={p.label}>
            <text x={x} y={y - 4} textAnchor="middle" fontSize="10"
                  fill="var(--text-muted)">{p.label}</text>
            <text x={x} y={y + 8} textAnchor="middle" fontSize="11"
                  fontWeight="600" fill="var(--text)"
                  className="num">{num(p.score, 0)}</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ==========================================================================
   MultiRadar: several companies' pillar profiles on one set of axes.

   Drawn by hand rather than with recharts' radar, because overlaying four
   translucent polygons needs control over paint order and stroke weight that
   the library does not give up easily. Each shape grows from the centre on
   reveal, staggered, so the profiles arrive one at a time and stay readable.
   ========================================================================== */
export function MultiRadar({
  axes, series, size = 300,
}: {
  axes: string[];
  series: { key: string; label: string; color: string; values: (number | null)[] }[];
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 42;
  const n = axes.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const point = (i: number, v: number): [number, number] => [
    cx + Math.cos(angle(i)) * r * v,
    cy + Math.sin(angle(i)) * r * v,
  ];
  const polygon = (vals: number[]) =>
    vals.map((v, i) => point(i, v)).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  return (
    <svg width={size} height={size} className="overflow-visible" role="img"
         aria-label={`Pillar profile for ${series.map((s) => s.label).join(", ")}`}>
      {/* web */}
      {[0.25, 0.5, 0.75, 1].map((ring) => (
        <polygon key={ring} points={polygon(axes.map(() => ring))}
                 fill="none" stroke="rgba(255,255,255,.07)" />
      ))}
      {axes.map((_, i) => {
        const [x, y] = point(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(255,255,255,.07)" />;
      })}

      {/* one polygon per company, scaled up from the centre on mount */}
      {series.map((s, si) => {
        const pts = polygon(s.values.map((v) => Math.max(0.04, (v ?? 0) / 100)));
        return (
          <motion.g
            key={s.key}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.7, delay: si * 0.09, ease: [0.22, 1, 0.36, 1] }}
            style={{ transformOrigin: `${cx}px ${cy}px` }}
          >
            <polygon points={pts} fill={s.color} fillOpacity={0.13}
                     stroke={s.color} strokeWidth={1.9} strokeLinejoin="round" />
            {s.values.map((v, i) => {
              const [x, y] = point(i, Math.max(0.04, (v ?? 0) / 100));
              return <circle key={i} cx={x} cy={y} r={2.4} fill={s.color} />;
            })}
          </motion.g>
        );
      })}

      {/* axis labels */}
      {axes.map((a, i) => {
        const [x, y] = point(i, 1.2);
        return (
          <text key={a} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
                fontSize="10.5" fill="var(--text-muted)">
            {a}
          </text>
        );
      })}
    </svg>
  );
}

/* ==========================================================================
   RebasedChart: several price paths rebased to 100 at their first common
   point, which is the only honest way to compare names trading at Rs 12 and
   Rs 1,400 on the same axis.
   ========================================================================== */
export function RebasedChart({
  series, height = 300,
}: {
  series: { key: string; label: string; color: string; values: (number | null)[] }[];
  height?: number;
}) {
  const rows = useMemo(() => {
    const len = Math.max(0, ...series.map((s) => s.values.length));
    const base = new Map<string, number>();
    for (const s of series) {
      const first = s.values.find((v): v is number => v !== null && Number.isFinite(v) && v !== 0);
      if (first !== undefined) base.set(s.key, first);
    }
    return Array.from({ length: len }, (_, i) => {
      const row: Record<string, number | string | null> = { i };
      for (const s of series) {
        const v = s.values[i];
        const b = base.get(s.key);
        row[s.key] = v !== null && v !== undefined && b ? (v / b) * 100 : null;
      }
      return row;
    });
  }, [series]);

  if (rows.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="i" tickLine={false} axisLine={false} tick={false} height={8} />
        <YAxis tickLine={false} axisLine={false} width={46}
               tickFormatter={(v: number) => num(v, 0)} />
        <ReferenceLine y={100} stroke="rgba(255,255,255,.2)" strokeDasharray="4 4" />
        <Tooltip content={<SeriesTip fmt={(v) => num(v, 1)} heading={() => "Rebased to 100"} />} />
        {series.map((s) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label}
                stroke={s.color} strokeWidth={2} dot={false} isAnimationActive
                animationDuration={900} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
