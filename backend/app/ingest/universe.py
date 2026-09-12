"""KSE-100 investable universe.

Ticker, company name, sector and a free-float size tier for every constituent
used by the engine. The list mirrors the PSX KSE-100 recomposition universe;
SECTOR_PROFILES carries the sector economics that the simulator and the
sector-relative ratio engine both rely on.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    sector: str
    size_tier: int          # 1 = mega cap, 4 = small cap -> drives index weight
    listed_year: int = 2005

    def to_dict(self) -> dict:
        return asdict(self)


# --- KSE-100 constituents -------------------------------------------------
_RAW: List[tuple] = [
    ("OGDC", "Oil & Gas Development Company", "Oil & Gas Exploration", 1),
    ("PPL", "Pakistan Petroleum Limited", "Oil & Gas Exploration", 1),
    ("MARI", "Mari Petroleum Company", "Oil & Gas Exploration", 1),
    ("POL", "Pakistan Oilfields Limited", "Oil & Gas Exploration", 2),
    ("PSO", "Pakistan State Oil Company", "Oil & Gas Marketing", 1),
    ("APL", "Attock Petroleum Limited", "Oil & Gas Marketing", 2),
    ("SHEL", "Shell Pakistan Limited", "Oil & Gas Marketing", 3),
    ("HTL", "Hi-Tech Lubricants", "Oil & Gas Marketing", 4),
    ("SNGP", "Sui Northern Gas Pipelines", "Gas Distribution", 2),
    ("SSGC", "Sui Southern Gas Company", "Gas Distribution", 3),
    ("ATRL", "Attock Refinery Limited", "Refinery", 2),
    ("NRL", "National Refinery Limited", "Refinery", 3),
    ("PRL", "Pakistan Refinery Limited", "Refinery", 3),
    ("CNERGY", "Cnergyico PK Limited", "Refinery", 4),
    ("HBL", "Habib Bank Limited", "Commercial Banks", 1),
    ("UBL", "United Bank Limited", "Commercial Banks", 1),
    ("MCB", "MCB Bank Limited", "Commercial Banks", 1),
    ("MEBL", "Meezan Bank Limited", "Commercial Banks", 1),
    ("NBP", "National Bank of Pakistan", "Commercial Banks", 2),
    ("BAFL", "Bank Alfalah Limited", "Commercial Banks", 2),
    ("BAHL", "Bank AL Habib Limited", "Commercial Banks", 2),
    ("AKBL", "Askari Bank Limited", "Commercial Banks", 3),
    ("FABL", "Faysal Bank Limited", "Commercial Banks", 3),
    ("BOP", "The Bank of Punjab", "Commercial Banks", 3),
    ("JSBL", "JS Bank Limited", "Commercial Banks", 4),
    ("SNBL", "Soneri Bank Limited", "Commercial Banks", 4),
    ("FFC", "Fauji Fertilizer Company", "Fertilizer", 1),
    ("EFERT", "Engro Fertilizers Limited", "Fertilizer", 1),
    ("FATIMA", "Fatima Fertilizer Company", "Fertilizer", 2),
    ("AGL", "Agritech Limited", "Fertilizer", 4),
    ("ENGRO", "Engro Corporation", "Conglomerate", 1),
    ("PKGS", "Packages Limited", "Paper & Board", 3),
    ("LUCK", "Lucky Cement Limited", "Cement", 1),
    ("DGKC", "D.G. Khan Cement Company", "Cement", 2),
    ("MLCF", "Maple Leaf Cement Factory", "Cement", 3),
    ("FCCL", "Fauji Cement Company", "Cement", 3),
    ("CHCC", "Cherat Cement Company", "Cement", 3),
    ("PIOC", "Pioneer Cement Limited", "Cement", 3),
    ("KOHC", "Kohat Cement Company", "Cement", 3),
    ("ACPL", "Attock Cement Pakistan", "Cement", 3),
    ("BWCL", "Bestway Cement Limited", "Cement", 2),
    ("GWLC", "Gharibwal Cement Limited", "Cement", 4),
    ("HUBC", "The Hub Power Company", "Power Generation", 1),
    ("KAPCO", "Kot Addu Power Company", "Power Generation", 3),
    ("NPL", "Nishat Power Limited", "Power Generation", 4),
    ("NCPL", "Nishat Chunian Power", "Power Generation", 4),
    ("KEL", "K-Electric Limited", "Power Generation", 3),
    ("INDU", "Indus Motor Company", "Automobile Assembler", 2),
    ("HCAR", "Honda Atlas Cars Pakistan", "Automobile Assembler", 3),
    ("PSMC", "Pak Suzuki Motor Company", "Automobile Assembler", 3),
    ("MTL", "Millat Tractors Limited", "Automobile Assembler", 3),
    ("AGTL", "Al-Ghazi Tractors Limited", "Automobile Assembler", 4),
    ("GHNI", "Ghandhara Industries", "Automobile Assembler", 4),
    ("ATLH", "Atlas Honda Limited", "Automobile Assembler", 3),
    ("THALL", "Thal Limited", "Auto Parts", 3),
    ("NML", "Nishat Mills Limited", "Textile Composite", 2),
    ("ILP", "Interloop Limited", "Textile Composite", 2),
    ("GATM", "Gul Ahmed Textile Mills", "Textile Composite", 3),
    ("KTML", "Kohinoor Textile Mills", "Textile Composite", 4),
    ("NCL", "Nishat Chunian Limited", "Textile Composite", 4),
    ("FML", "Feroze1888 Mills", "Textile Composite", 4),
    ("ICI", "ICI Pakistan Limited", "Chemicals", 2),
    ("LOTCHEM", "Lucky Core Industries Chemical", "Chemicals", 2),
    ("EPCL", "Engro Polymer & Chemicals", "Chemicals", 2),
    ("BERG", "Berger Paints Pakistan", "Chemicals", 4),
    ("ARPL", "Archroma Pakistan Limited", "Chemicals", 4),
    ("SITC", "Sitara Chemical Industries", "Chemicals", 4),
    ("SEARL", "The Searle Company", "Pharmaceuticals", 3),
    ("GLAXO", "GlaxoSmithKline Pakistan", "Pharmaceuticals", 3),
    ("ABOT", "Abbott Laboratories Pakistan", "Pharmaceuticals", 2),
    ("HINOON", "Highnoon Laboratories", "Pharmaceuticals", 3),
    ("AGP", "AGP Limited", "Pharmaceuticals", 3),
    ("FEROZ", "Ferozsons Laboratories", "Pharmaceuticals", 4),
    ("NESTLE", "Nestle Pakistan Limited", "Food & Personal Care", 1),
    ("NATF", "National Foods Limited", "Food & Personal Care", 3),
    ("FCEPL", "FrieslandCampina Engro Pakistan", "Food & Personal Care", 3),
    ("UNITY", "Unity Foods Limited", "Food & Personal Care", 4),
    ("FFL", "Fauji Foods Limited", "Food & Personal Care", 4),
    ("PAKT", "Pakistan Tobacco Company", "Tobacco", 2),
    ("SYS", "Systems Limited", "Technology & Communication", 2),
    ("TRG", "TRG Pakistan Limited", "Technology & Communication", 3),
    ("NETSOL", "NetSol Technologies", "Technology & Communication", 4),
    ("AVN", "Avanceon Limited", "Technology & Communication", 4),
    ("TPLP", "TPL Properties Limited", "Technology & Communication", 4),
    ("PTC", "Pakistan Telecommunication Company", "Technology & Communication", 3),
    ("AIRLINK", "Air Link Communication", "Technology & Communication", 4),
    ("PAEL", "Pak Elektron Limited", "Cable & Electrical Goods", 4),
    ("TGL", "Tariq Glass Industries", "Glass & Ceramics", 4),
    ("GHGL", "Ghani Glass Limited", "Glass & Ceramics", 4),
    ("MUGHAL", "Mughal Iron & Steel Industries", "Engineering", 4),
    ("ASTL", "Amreli Steels Limited", "Engineering", 4),
    ("ISL", "International Steels Limited", "Engineering", 3),
    ("ITTEFAQ", "Ittefaq Iron Industries", "Engineering", 4),
    ("AICL", "Adamjee Insurance Company", "Insurance", 3),
    ("EFUG", "EFU General Insurance", "Insurance", 3),
    ("IGIHL", "IGI Holdings Limited", "Insurance", 4),
    ("JDWS", "JDW Sugar Mills", "Sugar & Allied", 4),
    ("SRVI", "Service Industries Limited", "Leather & Tanneries", 4),
    ("PNSC", "Pakistan National Shipping Corp", "Transport", 4),
    ("PSEL", "Pakistan Services Limited", "Miscellaneous", 4),
    ("BNWM", "Bannu Woollen Mills", "Miscellaneous", 4),
]

UNIVERSE: List[Company] = [Company(t, n, s, w) for t, n, s, w in _RAW]
BY_TICKER: Dict[str, Company] = {c.ticker: c for c in UNIVERSE}
SECTORS: List[str] = sorted({c.sector for c in UNIVERSE})

# Banks and insurers report a different chart of accounts (no gross profit,
# no inventory, no cost of sales) and are scored on a financial-sector template.
FINANCIAL_SECTORS = {"Commercial Banks", "Insurance"}


def is_financial(ticker: str) -> bool:
    c = BY_TICKER.get(ticker)
    return bool(c and c.sector in FINANCIAL_SECTORS)


# --- Sector economics -----------------------------------------------------
# base_margin    : typical net margin
# asset_turnover : revenue / assets
# leverage       : assets / equity
# growth         : annualised revenue growth
# cyclicality    : reaction to the macro cycle
# beta           : sensitivity to the market factor
SECTOR_PROFILES: Dict[str, dict] = {
    "Oil & Gas Exploration": dict(base_margin=0.34, asset_turnover=0.42, leverage=1.45, growth=0.11, cyclicality=1.25, beta=1.05, payout=0.45),
    "Oil & Gas Marketing":   dict(base_margin=0.028, asset_turnover=2.60, leverage=2.90, growth=0.16, cyclicality=1.30, beta=1.15, payout=0.35),
    "Gas Distribution":      dict(base_margin=0.022, asset_turnover=1.40, leverage=3.60, growth=0.14, cyclicality=0.95, beta=0.95, payout=0.20),
    "Refinery":              dict(base_margin=0.030, asset_turnover=2.20, leverage=3.40, growth=0.18, cyclicality=1.70, beta=1.40, payout=0.15),
    "Commercial Banks":      dict(base_margin=0.30, asset_turnover=0.10, leverage=11.5, growth=0.17, cyclicality=0.85, beta=1.00, payout=0.55),
    "Insurance":             dict(base_margin=0.13, asset_turnover=0.38, leverage=3.20, growth=0.12, cyclicality=0.80, beta=0.85, payout=0.45),
    "Fertilizer":            dict(base_margin=0.17, asset_turnover=0.85, leverage=2.40, growth=0.13, cyclicality=0.70, beta=0.80, payout=0.70),
    "Conglomerate":          dict(base_margin=0.12, asset_turnover=0.55, leverage=2.60, growth=0.12, cyclicality=1.00, beta=1.00, payout=0.40),
    "Cement":                dict(base_margin=0.14, asset_turnover=0.60, leverage=2.10, growth=0.12, cyclicality=1.55, beta=1.30, payout=0.25),
    "Power Generation":      dict(base_margin=0.16, asset_turnover=0.45, leverage=3.10, growth=0.07, cyclicality=0.60, beta=0.75, payout=0.60),
    "Automobile Assembler":  dict(base_margin=0.075, asset_turnover=1.55, leverage=2.20, growth=0.11, cyclicality=1.75, beta=1.35, payout=0.55),
    "Auto Parts":            dict(base_margin=0.085, asset_turnover=1.20, leverage=1.80, growth=0.10, cyclicality=1.45, beta=1.15, payout=0.40),
    "Textile Composite":     dict(base_margin=0.062, asset_turnover=1.05, leverage=2.70, growth=0.13, cyclicality=1.20, beta=1.10, payout=0.25),
    "Chemicals":             dict(base_margin=0.095, asset_turnover=1.10, leverage=2.20, growth=0.12, cyclicality=1.25, beta=1.05, payout=0.35),
    "Pharmaceuticals":       dict(base_margin=0.105, asset_turnover=1.05, leverage=1.75, growth=0.14, cyclicality=0.55, beta=0.70, payout=0.35),
    "Food & Personal Care":  dict(base_margin=0.082, asset_turnover=1.45, leverage=2.30, growth=0.15, cyclicality=0.50, beta=0.65, payout=0.45),
    "Tobacco":               dict(base_margin=0.20, asset_turnover=1.70, leverage=1.90, growth=0.16, cyclicality=0.45, beta=0.60, payout=0.85),
    "Technology & Communication": dict(base_margin=0.155, asset_turnover=0.95, leverage=1.60, growth=0.26, cyclicality=0.90, beta=1.25, payout=0.15),
    "Cable & Electrical Goods":  dict(base_margin=0.055, asset_turnover=0.95, leverage=2.80, growth=0.11, cyclicality=1.50, beta=1.30, payout=0.15),
    "Glass & Ceramics":      dict(base_margin=0.115, asset_turnover=0.95, leverage=1.85, growth=0.13, cyclicality=1.30, beta=1.10, payout=0.30),
    "Engineering":           dict(base_margin=0.065, asset_turnover=1.15, leverage=2.60, growth=0.12, cyclicality=1.60, beta=1.30, payout=0.20),
    "Paper & Board":         dict(base_margin=0.085, asset_turnover=0.80, leverage=2.30, growth=0.11, cyclicality=1.15, beta=1.00, payout=0.30),
    "Sugar & Allied":        dict(base_margin=0.055, asset_turnover=1.10, leverage=3.00, growth=0.09, cyclicality=1.10, beta=0.95, payout=0.20),
    "Leather & Tanneries":   dict(base_margin=0.070, asset_turnover=1.30, leverage=2.40, growth=0.12, cyclicality=1.25, beta=1.05, payout=0.25),
    "Transport":             dict(base_margin=0.135, asset_turnover=0.50, leverage=2.00, growth=0.10, cyclicality=1.35, beta=1.10, payout=0.25),
    "Miscellaneous":         dict(base_margin=0.070, asset_turnover=0.85, leverage=2.30, growth=0.10, cyclicality=1.10, beta=1.00, payout=0.25),
}

# Index weight multiplier by size tier (free-float proxy).
TIER_WEIGHT = {1: 30.0, 2: 8.0, 3: 2.5, 4: 1.0}


def index_weights() -> Dict[str, float]:
    """Free-float-capped weights summing to 1.0, mirroring the KSE-100
    single-scrip cap of 12%."""
    raw = {c.ticker: float(TIER_WEIGHT[c.size_tier]) for c in UNIVERSE}
    total = sum(raw.values())
    w = {k: v / total for k, v in raw.items()}
    for _ in range(8):
        excess = sum(max(0.0, v - 0.12) for v in w.values())
        if excess < 1e-9:
            break
        under_pool = sum(v for v in w.values() if v < 0.12) or 1.0
        w = {k: (0.12 if v >= 0.12 else v + excess * v / under_pool)
             for k, v in w.items()}
    return w
