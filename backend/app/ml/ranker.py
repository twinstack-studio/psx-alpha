"""Machine-learning ranking model.

The task is not "predict the return of PSO" but "order the KSE-100 so the names
that outperform over the next quarter sit at the top". That is a
learning-to-rank problem, so the default model is XGBoost's `rank:pairwise`
objective with one query group per rebalance date.

Training is strictly walk-forward. At rebalance date *t* the model may only see
snapshots whose label horizon closed on or before *t*; a snapshot taken a month
ago has not finished its quarter, so it is excluded. This is the single most
common way a stock-picking backtest fools its author, and the `Fold` records
returned here exist so that the discipline can be audited.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.scoring.features import ML_FEATURES

warnings.filterwarnings("ignore", category=UserWarning)

try:
    import xgboost as xgb
    HAS_XGB = True
except Exception:                                   # pragma: no cover
    HAS_XGB = False

try:
    from sklearn.ensemble import GradientBoostingRegressor
    HAS_SKLEARN = True
except Exception:                                   # pragma: no cover
    HAS_SKLEARN = False


N_BUCKETS = 5          # quintile relevance labels for the pairwise ranker
SEED_ENSEMBLE = (0, 7, 13, 57, 101)   # averaged to stabilise a small panel


class _Ensemble:
    """Averages the rank produced by each seed rather than the raw scores,
    because pairwise ranker outputs are not on a comparable scale."""

    def __init__(self, models):
        self.models = models

    def predict(self, X):
        ranks = [pd.Series(m.predict(X)).rank(pct=True).values for m in self.models]
        return np.mean(ranks, axis=0)


@dataclass
class Fold:
    """One walk-forward step, kept for the audit trail."""
    asof: str
    train_rows: int
    train_periods: int
    train_end: str
    n_predicted: int
    spearman_ic: Optional[float] = None
    top_decile_fwd: Optional[float] = None
    bottom_decile_fwd: Optional[float] = None


def _spearman(a: pd.Series, b: pd.Series) -> float:
    """Rank correlation without pulling in scipy."""
    m = a.notna() & b.notna()
    if m.sum() < 5:
        return float("nan")
    ra, rb = a[m].rank(), b[m].rank()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / denom) if denom else float("nan")


def make_labels(fwd: pd.Series) -> pd.Series:
    """Cross-sectional quintile of the forward return, 0 (worst) to 4 (best)."""
    valid = fwd.dropna()
    if len(valid) < N_BUCKETS:
        return pd.Series(index=fwd.index, dtype=float)
    try:
        q = pd.qcut(valid.rank(method="first"), N_BUCKETS, labels=False)
    except ValueError:
        return pd.Series(index=fwd.index, dtype=float)
    return q.reindex(fwd.index).astype(float)


class WalkForwardRanker:
    """Trains a fresh model at every rebalance date on data available then."""

    def __init__(self, features: List[str] | None = None, seed: int | None = None):
        self.features = features or ML_FEATURES
        self.seed = seed if seed is not None else settings.ml_seed
        self.history: List[pd.DataFrame] = []     # labelled snapshots, oldest first
        self.folds: List[Fold] = []
        self.model = None
        self.last_importance: Dict[str, float] = {}

    # -- data ------------------------------------------------------------
    def add_observation(self, snap: pd.DataFrame, asof, fwd_return: pd.Series) -> None:
        """Record one snapshot together with the return that followed it.

        `label_ready_on` is when the horizon closes; only observations whose
        horizon has closed may be used for training at a later date.
        """
        if snap is None or snap.empty:
            return
        obs = snap.copy()
        obs["asof_date"] = pd.Timestamp(asof)
        obs["fwd_return"] = obs["ticker"].map(fwd_return)
        obs["fwd_excess"] = obs["fwd_return"] - obs["fwd_return"].mean()
        obs["label"] = make_labels(obs["fwd_return"])
        obs["label_ready_on"] = pd.Timestamp(asof) + pd.Timedelta(
            days=int(settings.ml_label_horizon_days * 7 / 5) + 3)
        self.history.append(obs)

    def _training_frame(self, asof) -> pd.DataFrame:
        asof = pd.Timestamp(asof)
        usable = [h for h in self.history
                  if h["label_ready_on"].iloc[0] <= asof and h["label"].notna().any()]
        if not usable:
            return pd.DataFrame()
        return pd.concat(usable, ignore_index=True)

    # -- model -----------------------------------------------------------
    def _matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Feature matrix in a fixed column order; a feature absent from this
        snapshot becomes 0, which is the cross-sectional mean for a z-score."""
        return (df.reindex(columns=self.features)
                  .apply(pd.to_numeric, errors="coerce")
                  .fillna(0.0).values.astype(float))

    def _fit(self, train: pd.DataFrame):
        X = self._matrix(train)
        groups = train.groupby("asof_date").size().values

        if HAS_XGB:
            # A KSE-100 cross-section gives roughly 100 rows per quarter, so a
            # deep tree memorises noise. Depth 3 with a heavy minimum child
            # weight and strong L2 was the best of the configurations tested
            # walk-forward; the seed ensemble then averages away the residual
            # variance from subsampling, which on a panel this small is the
            # difference between a stable ranking and a random one.
            models = []
            importances = np.zeros(len(self.features))
            for offset in SEED_ENSEMBLE:
                m = xgb.XGBRanker(
                    objective="rank:pairwise",
                    n_estimators=120,
                    learning_rate=0.05,
                    max_depth=3,
                    min_child_weight=20,
                    subsample=0.80,
                    colsample_bytree=0.60,
                    reg_lambda=6.0,
                    reg_alpha=0.2,
                    random_state=self.seed + offset,
                    n_jobs=2,
                    tree_method="hist",
                    verbosity=0,
                )
                m.fit(X, train["label"].astype(int).values, group=groups)
                models.append(m)
                imp = getattr(m, "feature_importances_", None)
                if imp is not None:
                    importances += np.asarray(imp, dtype=float)
            importances /= max(len(models), 1)
            self.last_importance = {
                f: float(v) for f, v in sorted(
                    zip(self.features, importances), key=lambda kv: -kv[1])
            }
            return _Ensemble(models)

        if HAS_SKLEARN:                              # graceful degradation
            model = GradientBoostingRegressor(
                n_estimators=220, learning_rate=0.05, max_depth=3,
                subsample=0.85, random_state=self.seed)
            model.fit(X, train["fwd_excess"].fillna(0.0).values)
            imp = getattr(model, "feature_importances_", None)
            if imp is not None:
                self.last_importance = {
                    f: float(v) for f, v in sorted(
                        zip(self.features, imp), key=lambda kv: -kv[1])
                }
            return model

        raise RuntimeError("Neither xgboost nor scikit-learn is available")

    def fit_predict(self, snap: pd.DataFrame, asof) -> pd.Series:
        """Return a 0-100 model score per ticker, or an empty series while the
        walk-forward window is still warming up."""
        train = self._training_frame(asof)
        n_periods = train["asof_date"].nunique() if len(train) else 0
        if n_periods < settings.ml_min_train_periods:
            self.folds.append(Fold(str(pd.Timestamp(asof).date()), len(train),
                                   n_periods, "-", 0))
            return pd.Series(dtype=float)

        train = train.dropna(subset=["label"])
        train = train.sort_values("asof_date")
        self.model = self._fit(train)
        raw = self.model.predict(self._matrix(snap))
        s = pd.Series(raw, index=snap["ticker"].values)
        # Ranker output has no natural scale, so convert to a cross-sectional
        # percentile and put it on the same 0-100 axis as the rule score.
        score = s.rank(pct=True) * 100.0

        self.folds.append(Fold(
            asof=str(pd.Timestamp(asof).date()),
            train_rows=len(train),
            train_periods=int(n_periods),
            train_end=str(train["asof_date"].max().date()),
            n_predicted=len(score),
        ))
        return score

    # -- evaluation -------------------------------------------------------
    def score_folds(self) -> pd.DataFrame:
        """Attach out-of-sample rank correlation to each fold once the
        realised returns for that date are known."""
        by_date = {pd.Timestamp(h["asof_date"].iloc[0]).date(): h for h in self.history}
        for f in self.folds:
            h = by_date.get(pd.Timestamp(f.asof).date())
            if h is None or "ml_score" not in h.columns:
                continue
            f.spearman_ic = _spearman(h["ml_score"], h["fwd_return"])
            n = max(1, len(h) // 10)
            ordered = h.sort_values("ml_score", ascending=False)
            f.top_decile_fwd = float(ordered["fwd_return"].head(n).mean())
            f.bottom_decile_fwd = float(ordered["fwd_return"].tail(n).mean())
        return pd.DataFrame([f.__dict__ for f in self.folds])

    def attach_scores(self, asof, scores: pd.Series) -> None:
        """Store the model's own scores back onto the observation so the
        information coefficient can be measured out of sample."""
        for h in self.history:
            if pd.Timestamp(h["asof_date"].iloc[0]) == pd.Timestamp(asof):
                h["ml_score"] = h["ticker"].map(scores)
                return

    def importance_table(self, top: int = 20) -> List[dict]:
        items = list(self.last_importance.items())[:top]
        total = sum(v for _, v in self.last_importance.items()) or 1.0
        return [{"feature": k, "importance": round(v / total, 5)} for k, v in items]

    @property
    def backend(self) -> str:
        if HAS_XGB:
            return "xgboost.XGBRanker(rank:pairwise)"
        if HAS_SKLEARN:
            return "sklearn.GradientBoostingRegressor(fallback)"
        return "unavailable"
