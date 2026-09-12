export type Band = "STRONG BUY" | "BUY" | "HOLD" | "REDUCE" | "AVOID";

export type PillarKey = "quality" | "value" | "safety" | "growth" | "momentum";

export interface Meta {
  generatedAt: string;
  asOf: string;
  universe: string;
  universeSize: number;
  historyStart: string;
  historyEnd: string;
  backtestStart: string;
  backtestEnd: string;
  topN: number;
  rebalance: string;
  costBps: number;
  maxSectorWeight: number;
  mlBackend: string;
  blendWeight: number;
  compositeWeights: Record<PillarKey, number>;
  pillarLabels: Record<PillarKey, string>;
  dataSource: string;
  disclaimer: string;
}

export interface Recommendation {
  ticker: string;
  name: string;
  sector: string;
  price: number | null;
  rank: number;
  recommendation: Band;
  conviction: number | null;
  finalScore: number | null;
  ruleScore: number | null;
  mlScore: number | null;
  percentile: number | null;
  pillars: Record<PillarKey, number | null>;
  pillarZ: Record<PillarKey, number | null>;
  scoreCap: number | null;
  fScore: number | null;
  zScore: number | null;
  zZone: string | null;
  marketCap: number | null;
  pe: number | null;
  pb: number | null;
  evEbitda: number | null;
  dividendYield: number | null;
  roe: number | null;
  roa: number | null;
  netMargin: number | null;
  debtToEquity: number | null;
  revenueGrowth: number | null;
  earningsGrowth: number | null;
  momentum12m: number | null;
  return1m: number | null;
  return3m: number | null;
  return12m: number | null;
  volatility: number | null;
  beta: number | null;
  turnoverPkrM: number | null;
  rsi: number | null;
  riskFlags: string[];
  headline: string | null;
  summary: string | null;
  spark: (number | null)[];
}

export interface SectorRow {
  sector: string;
  count: number;
  avgScore: number | null;
  medianPe: number | null;
  medianRoe: number | null;
  medianDebtToEquity: number | null;
  avgMomentum: number | null;
  buys: number;
  totalMarketCap: number | null;
}

export interface Performance {
  key: "blended" | "rule" | "ml" | "KSE100";
  label: string;
  total_return: number;
  cagr: number;
  volatility: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  calmar: number;
  positive_days: number;
  years: number;
  final_value: number;
  beta?: number;
  alpha_annual?: number;
  excess_return?: number;
  tracking_error?: number;
  information_ratio?: number;
  benchmark_cagr?: number;
  avg_turnover?: number;
  total_cost_drag_pct?: number;
  n_rebalances?: number;
  hit_rate?: number;
  quarters_beating_benchmark?: number;
  quarters_evaluated?: number;
  yearly: { year: number; return: number }[];
}

export interface CurvePoint {
  date: string;
  KSE100?: number;
  rule?: number;
  ml?: number;
  blended?: number;
}

export interface Holding {
  ticker: string;
  name: string;
  sector: string;
  weight: number;
  score: number;
  recommendation: Band;
}

export interface Rebalance {
  date: string;
  turnover: number | null;
  costBps: number | null;
  periodReturn: number | null;
  benchmarkReturn: number | null;
  excess: number | null;
  nCandidates: number;
  nExcludedLiquidity: number;
  holdings: Holding[];
}

export interface MlDiagnostics {
  backend: string;
  features: number;
  importance: { feature: string; importance: number }[];
  folds: {
    date: string;
    trainRows: number;
    trainPeriods: number;
    ic: number | null;
    topDecile: number | null;
    bottomDecile: number | null;
  }[];
  meanIC: number | null;
  icHitRate: number | null;
  labelHorizonDays: number;
}

export interface MacroPoint {
  date: string;
  policyRate: number | null;
  cpi: number | null;
  usdPkr: number | null;
  reserves: number | null;
  gdp: number | null;
}

export interface Dashboard {
  meta: Meta;
  bands: Partial<Record<Band, number>>;
  recommendations: Recommendation[];
  sectors: SectorRow[];
  performance: Performance[];
  equityCurve: CurvePoint[];
  drawdown: { date: string; strategy: number | null; benchmark: number | null }[];
  rebalances: Rebalance[];
  ml: MlDiagnostics;
  market: {
    index: { date: string; close: number }[];
    macro: MacroPoint[];
  };
}

export interface PillarDetail {
  key: PillarKey;
  label: string;
  score: number | null;
  z: number | null;
  weight: number;
}

export interface FTest {
  label: string;
  description: string;
  passed: boolean | null;
  detail: string;
}

export interface Explanation {
  ticker: string;
  name: string;
  sector: string;
  recommendation: Band;
  headline: string;
  summary: string;
  valuation_note: string;
  screens_note: string;
  strengths: { metric: string; label: string; value: number | null; z: number | null; pillar: string; text: string }[];
  concerns: { metric: string; label: string; value: number | null; z: number | null; pillar: string; text: string }[];
  pillars: PillarDetail[];
  f_score: number | null;
  f_score_verdict: string;
  f_tests: Record<string, FTest>;
  z_score: number | null;
  z_zone: string | null;
  z_components: Record<string, number>;
  risk_flags: string[];
  what_would_change_this: string[];
  as_of: string;
  disclaimer: string;
}

export interface CompanyDetail {
  ticker: string;
  name: string;
  sector: string;
  indexWeight: number | null;
  explanation: Explanation;
  priceHistory: { date: string; close: number }[];
  financials: {
    period: string;
    fiscalYear: number;
    quarter: number;
    revenue: number | null;
    grossProfit: number | null;
    operatingIncome: number | null;
    netIncome: number | null;
    eps: number | null;
    totalAssets: number | null;
    totalEquity: number | null;
    totalLiabilities: number | null;
    cfo: number | null;
    capex: number | null;
    freeCashFlow: number | null;
    reportDate: string;
  }[];
  ratioHistory: {
    period: string;
    roe: number | null;
    roa: number | null;
    netMargin: number | null;
    grossMargin: number | null;
    currentRatio: number | null;
    debtToEquity: number | null;
    interestCoverage: number | null;
    revenueGrowth: number | null;
  }[];
  peers: { ticker: string; name: string; finalScore: number | null; pe: number | null; roe: number | null; recommendation: Band }[];
}
