import type { Band } from "./types";

const nf = (d: number) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

export const num = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : nf(d).format(v);

export const pct = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${nf(d).format(v * 100)}%`;

export const signedPct = (v: number | null | undefined, d = 1) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = `${nf(d).format(v * 100)}%`;
  return v > 0 ? `+${s}` : s;
};

export const mult = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${nf(d).format(v)}x`;

export const rupees = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `Rs ${nf(d).format(v)}`;

/** Values arrive in PKR millions from the pipeline. */
export const pkrM = (v: number | null | undefined) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1_000_000) return `Rs ${nf(2).format(v / 1_000_000)}tn`;
  if (a >= 1_000) return `Rs ${nf(1).format(v / 1_000)}bn`;
  return `Rs ${nf(0).format(v)}m`;
};

export const compact = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" });

export const monthYear = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { month: "short", year: "numeric" });

export const longDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

export const bandClass = (band: Band | string | null | undefined) => {
  switch (band) {
    case "STRONG BUY": return "band-strong-buy";
    case "BUY": return "band-buy";
    case "REDUCE": return "band-reduce";
    case "AVOID": return "band-avoid";
    default: return "band-hold";
  }
};

export const bandColor = (band: Band | string | null | undefined) => {
  switch (band) {
    case "STRONG BUY": return "#34d399";
    case "BUY": return "#86efac";
    case "REDUCE": return "#fbbf24";
    case "AVOID": return "#fb7185";
    default: return "#94a3b8";
  }
};

/** Green above the midpoint, amber around it, rose below. */
export const scoreColor = (score: number | null | undefined) => {
  if (score === null || score === undefined) return "#94a3b8";
  if (score >= 68) return "#34d399";
  if (score >= 56) return "#86efac";
  if (score >= 44) return "#94a3b8";
  if (score >= 32) return "#fbbf24";
  return "#fb7185";
};

export const deltaColor = (v: number | null | undefined) =>
  v === null || v === undefined ? "var(--text-muted)" : v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-muted)";

export const PILLAR_ORDER = ["quality", "value", "safety", "growth", "momentum"] as const;

export const PILLAR_SHORT: Record<string, string> = {
  quality: "Quality",
  value: "Value",
  safety: "Safety",
  growth: "Growth",
  momentum: "Trend",
};

export const STRATEGY_COLOR: Record<string, string> = {
  blended: "#6d8dff",
  rule: "#34d399",
  ml: "#a78bfa",
  KSE100: "#8b95ad",
};

/** Readable labels for the model's raw feature names. */
export function featureLabel(raw: string): string {
  const clean = raw.replace(/^z_/, "").replace(/^macro_/, "");
  const map: Record<string, string> = {
    roe: "Return on equity",
    roa: "Return on assets",
    roic: "Return on invested capital",
    net_margin: "Net margin",
    gross_margin: "Gross margin",
    operating_margin: "Operating margin",
    ebitda_margin: "EBITDA margin",
    current_ratio: "Current ratio",
    quick_ratio: "Quick ratio",
    cash_ratio: "Cash ratio",
    debt_to_equity: "Debt to equity",
    debt_to_assets: "Debt to assets",
    equity_ratio: "Equity to assets",
    interest_coverage: "Interest cover",
    net_debt_to_ebitda: "Net debt / EBITDA",
    finance_cost_to_ebit: "Finance cost / EBIT",
    asset_turnover: "Asset turnover",
    inventory_days: "Inventory days",
    receivable_days: "Receivable days",
    cash_conversion_cycle: "Cash conversion cycle",
    cfo_to_net_income: "Cash conversion",
    accrual_ratio: "Accrual ratio",
    fcf_margin: "Free cash flow margin",
    capex_to_revenue: "Capex intensity",
    revenue_growth: "Revenue growth",
    earnings_growth: "Earnings growth",
    revenue_cagr_3y: "3-year revenue CAGR",
    equity_growth: "Equity growth",
    payout_ratio: "Payout ratio",
    pe: "Price / earnings",
    pb: "Price / book",
    ps: "Price / sales",
    ev_ebitda: "EV / EBITDA",
    earnings_yield: "Earnings yield",
    dividend_yield: "Dividend yield",
    fcf_yield: "Free cash flow yield",
    book_yield: "Book yield",
    size: "Market cap",
    momentum_12_1: "12-1 momentum",
    return_3m: "3-month return",
    return_6m: "6-month return",
    px_to_sma200: "Price vs 200-day average",
    rel_strength_6m: "6-month relative strength",
    volatility_252d: "1-year volatility",
    drawdown_1y: "Drawdown from 1-year high",
    turnover_pkr_m: "Traded value",
    rsi_14: "RSI (14)",
    golden_cross: "50/200-day cross",
    beta_1y: "Beta",
    volume_surge: "Volume surge",
    policy_rate: "SBP policy rate",
    cycle: "Macro cycle",
  };
  const base = map[clean] ?? clean.replace(/_/g, " ");
  return raw.startsWith("z_") ? `${base} (vs sector)` : base;
}
