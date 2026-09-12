"""Persistence layer.

The property that matters here is that running the pipeline twice is safe.
`scripts/run_pipeline.py` is the documented way to refresh the analysis, and
`run.ps1` invokes it on every plain launch, so a second run has to replace the
day's scores rather than collide with them.
"""
from __future__ import annotations



import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import app.db.repository as repo
from app.db.models import Base, Score


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the repository at a throwaway SQLite file.

    The module binds `engine` and `SessionLocal` at import, so both have to be
    redirected — `save_scores` uses the session for the delete and the engine
    for the bulk insert.
    """
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    monkeypatch.setattr(repo, "engine", engine)
    monkeypatch.setattr(repo, "SessionLocal", Session)
    yield engine, Session
    engine.dispose()


def make_scored(tickers=("OGDC", "PPL", "MARI"), final=(70.0, 60.0, 50.0)):
    return pd.DataFrame({
        "ticker": list(tickers),
        "f_score": [7.0] * len(tickers),
        "z_score": [6.0] * len(tickers),
        "quality": [60.0] * len(tickers),
        "value": [55.0] * len(tickers),
        "safety": [58.0] * len(tickers),
        "growth": [52.0] * len(tickers),
        "momentum": [51.0] * len(tickers),
        "rule_score": list(final),
        "ml_score": list(final),
        "final_score": list(final),
        "percentile": [0.9, 0.6, 0.3][: len(tickers)],
        "rank": list(range(1, len(tickers) + 1)),
        "recommendation": ["BUY"] * len(tickers),
        "conviction": [0.8] * len(tickers),
    })


class TestSaveScores:
    def test_writes_one_row_per_company(self, temp_db):
        _, Session = temp_db
        n = repo.save_scores(make_scored(), "2025-12-31")
        assert n == 3
        with Session() as s:
            assert s.scalar(select(func.count()).select_from(Score)) == 3

    def test_rerunning_the_same_date_replaces_rather_than_collides(self, temp_db):
        """The regression that stopped the pipeline being re-runnable.

        `scores` is unique on (ticker, asof_date, model_version); a second
        append for the same date used to raise IntegrityError *after* the full
        walk-forward backtest had already completed.
        """
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-12-31")
        repo.save_scores(make_scored(final=(80.0, 70.0, 60.0)), "2025-12-31")

        with Session() as s:
            assert s.scalar(select(func.count()).select_from(Score)) == 3
            best = s.scalar(select(Score).where(Score.ticker == "OGDC"))
            assert best.final_score == pytest.approx(80.0)   # the newer run won

    def test_a_different_date_is_kept_alongside(self, temp_db):
        """Replacing must be scoped to the date, not wipe the history."""
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-09-30")
        repo.save_scores(make_scored(), "2025-12-31")
        with Session() as s:
            assert s.scalar(select(func.count()).select_from(Score)) == 6
            dates = {r.asof_date for r in s.scalars(select(Score))}
            assert len(dates) == 2

    def test_a_different_model_version_is_kept_alongside(self, temp_db):
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-12-31", model_version="v1")
        repo.save_scores(make_scored(), "2025-12-31", model_version="v2")
        with Session() as s:
            assert s.scalar(select(func.count()).select_from(Score)) == 6

    def test_a_shrinking_universe_leaves_no_stale_rows(self, temp_db):
        """If a name drops out of the index, its old score must not linger as
        though it were still being ranked."""
        _, Session = temp_db
        repo.save_scores(make_scored(("OGDC", "PPL", "MARI")), "2025-12-31")
        repo.save_scores(make_scored(("OGDC", "PPL"), final=(75.0, 65.0)), "2025-12-31")
        with Session() as s:
            tickers = {r.ticker for r in s.scalars(select(Score))}
            assert tickers == {"OGDC", "PPL"}

    def test_explanations_round_trip_through_the_json_column(self, temp_db):
        """`save_scores` pre-serialises with `json.dumps` because `to_sql`
        bypasses the ORM and knows nothing about the JSON type. Reading back
        through the ORM deserialises it again, so a dict goes in and a dict
        comes out."""
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-12-31",
                         explanations={"OGDC": {"headline": "cheap and solvent"}})
        with Session() as s:
            row = s.scalar(select(Score).where(Score.ticker == "OGDC"))
            assert row.explanation == {"headline": "cheap and solvent"}

    def test_a_company_without_an_explanation_stores_an_empty_object(self, temp_db):
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-12-31", explanations={})
        with Session() as s:
            row = s.scalar(select(Score).where(Score.ticker == "PPL"))
            assert row.explanation == {}

    def test_an_empty_frame_writes_nothing_and_deletes_nothing(self, temp_db):
        _, Session = temp_db
        repo.save_scores(make_scored(), "2025-12-31")
        assert repo.save_scores(pd.DataFrame(), "2025-12-31") == 0
        assert repo.save_scores(None, "2025-12-31") == 0
        with Session() as s:
            assert s.scalar(select(func.count()).select_from(Score)) == 3
