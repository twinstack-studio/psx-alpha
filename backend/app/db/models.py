"""SQLAlchemy schema.

Runs on SQLite out of the box and on PostgreSQL unchanged by pointing
PSX_DATABASE_URL at a Postgres DSN. Every fundamentals row carries both
`period_end` (what the numbers describe) and `report_date` (when the filing
became public), which is what keeps the backtest free of look-ahead bias.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON,
    String, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    sector: Mapped[str] = mapped_column(String(64), index=True)
    size_tier: Mapped[int] = mapped_column(Integer)
    listed_year: Mapped[int] = mapped_column(Integer, default=2005)
    shares_outstanding: Mapped[float] = mapped_column(Float, default=0.0)  # millions
    index_weight: Mapped[float] = mapped_column(Float, default=0.0)
    is_financial: Mapped[bool] = mapped_column(Boolean, default=False)

    statements: Mapped[list["FinancialStatement"]] = relationship(back_populates="company")


class FinancialStatement(Base):
    """One standardized quarterly filing (income statement + balance sheet +
    cash flow) in PKR millions."""
    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint("ticker", "period_end", name="uq_stmt_ticker_period"),
        Index("ix_stmt_report_date", "report_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(ForeignKey("companies.ticker"), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    report_date: Mapped[date] = mapped_column(Date)      # point-in-time availability
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_quarter: Mapped[int] = mapped_column(Integer)

    # --- income statement ---
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cost_of_sales: Mapped[float] = mapped_column(Float, default=0.0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0.0)
    operating_expenses: Mapped[float] = mapped_column(Float, default=0.0)
    operating_income: Mapped[float] = mapped_column(Float, default=0.0)
    depreciation: Mapped[float] = mapped_column(Float, default=0.0)
    finance_cost: Mapped[float] = mapped_column(Float, default=0.0)
    other_income: Mapped[float] = mapped_column(Float, default=0.0)
    profit_before_tax: Mapped[float] = mapped_column(Float, default=0.0)
    taxation: Mapped[float] = mapped_column(Float, default=0.0)
    net_income: Mapped[float] = mapped_column(Float, default=0.0)
    eps: Mapped[float] = mapped_column(Float, default=0.0)
    dividend_per_share: Mapped[float] = mapped_column(Float, default=0.0)

    # --- balance sheet ---
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    receivables: Mapped[float] = mapped_column(Float, default=0.0)
    inventory: Mapped[float] = mapped_column(Float, default=0.0)
    current_assets: Mapped[float] = mapped_column(Float, default=0.0)
    fixed_assets: Mapped[float] = mapped_column(Float, default=0.0)
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    payables: Mapped[float] = mapped_column(Float, default=0.0)
    short_term_debt: Mapped[float] = mapped_column(Float, default=0.0)
    current_liabilities: Mapped[float] = mapped_column(Float, default=0.0)
    long_term_debt: Mapped[float] = mapped_column(Float, default=0.0)
    total_liabilities: Mapped[float] = mapped_column(Float, default=0.0)
    total_equity: Mapped[float] = mapped_column(Float, default=0.0)
    retained_earnings: Mapped[float] = mapped_column(Float, default=0.0)

    # --- cash flow ---
    cfo: Mapped[float] = mapped_column(Float, default=0.0)
    capex: Mapped[float] = mapped_column(Float, default=0.0)
    cfi: Mapped[float] = mapped_column(Float, default=0.0)
    cff: Mapped[float] = mapped_column(Float, default=0.0)
    free_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)

    shares_outstanding: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="simulated")

    company: Mapped[Company] = relationship(back_populates="statements")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_ticker_date"),
        Index("ix_price_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)


class IndexPrice(Base):
    __tablename__ = "index_prices"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_index_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), default="KSE100", index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)


class MacroSeries(Base):
    """SBP / PBS monthly macro indicators."""
    __tablename__ = "macro_series"
    __table_args__ = (UniqueConstraint("date", name="uq_macro_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    policy_rate: Mapped[float] = mapped_column(Float)
    cpi_yoy: Mapped[float] = mapped_column(Float)
    usd_pkr: Mapped[float] = mapped_column(Float)
    fx_reserves_usd_bn: Mapped[float] = mapped_column(Float)
    gdp_growth: Mapped[float] = mapped_column(Float)
    cycle: Mapped[float] = mapped_column(Float, default=0.0)


class Ratio(Base):
    """Derived ratios for one company at one filing period, plus the
    sector-relative z-score of each."""
    __tablename__ = "ratios"
    __table_args__ = (
        UniqueConstraint("ticker", "period_end", name="uq_ratio_ticker_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    sector: Mapped[str] = mapped_column(String(64), index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)      # raw ratios
    sector_z: Mapped[dict] = mapped_column(JSON, default=dict)    # z vs sector peers


class Score(Base):
    """A dated recommendation for one company."""
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("ticker", "asof_date", "model_version", name="uq_score_key"),
        Index("ix_score_asof", "asof_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    asof_date: Mapped[date] = mapped_column(Date)
    model_version: Mapped[str] = mapped_column(String(32), default="v1")

    f_score: Mapped[float] = mapped_column(Float, default=0.0)     # Piotroski 0-9
    z_score: Mapped[float] = mapped_column(Float, default=0.0)     # Altman
    quality: Mapped[float] = mapped_column(Float, default=0.0)     # 0-100 pillars
    value: Mapped[float] = mapped_column(Float, default=0.0)
    safety: Mapped[float] = mapped_column(Float, default=0.0)
    growth: Mapped[float] = mapped_column(Float, default=0.0)
    momentum: Mapped[float] = mapped_column(Float, default=0.0)
    rule_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    ml_score: Mapped[float] = mapped_column(Float, default=0.0)    # 0-100
    final_score: Mapped[float] = mapped_column(Float, default=0.0) # 0-100
    percentile: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[str] = mapped_column(String(16), default="HOLD")
    conviction: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(32))     # rule | ml | blended | benchmark
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    equity_curve: Mapped[dict] = mapped_column(JSON, default=dict)
    holdings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- engine / session -----------------------------------------------------
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db(drop: bool = False) -> None:
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
