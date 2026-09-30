"""Environment-conditioned LightGBM quantile forecasts for weekly pharmacy demand."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features_env import ENV_FEATURES, feature_columns

QUANTILES = (0.5, 0.9, 0.95)


@dataclass
class LGBMQuantileBundle:
    models: dict[float, lgb.LGBMRegressor]
    features: list[str]
    include_env: bool

    def predict(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        out = {}
        for q, model in self.models.items():
            pred = np.clip(model.predict(X[self.features]), 0.0, None)
            out[f"q{int(q * 100):02d}"] = pred
        out["point"] = out["q50"]
        return out


def _lgbm_params(alpha: float, seed: int = 42) -> dict:
    return {
        "objective": "quantile",
        "alpha": alpha,
        "n_estimators": 400,
        "learning_rate": 0.05,
        "num_leaves": 63,
        "min_child_samples": 40,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "random_state": seed,
        "n_jobs": -1,
        "verbosity": -1,
    }


def train_quantile_models(
    train_df: pd.DataFrame,
    include_env: bool = True,
    seed: int = 42,
    early_stopping_rounds: int = 40,
    valid_df: pd.DataFrame | None = None,
) -> LGBMQuantileBundle:
    features = feature_columns(include_env=include_env)
    X_train = train_df[features]
    y_train = train_df["demand"].to_numpy(dtype=float)

    models: dict[float, lgb.LGBMRegressor] = {}
    for q in QUANTILES:
        model = lgb.LGBMRegressor(**_lgbm_params(q, seed=seed))
        fit_kwargs: dict = {}
        if valid_df is not None and len(valid_df):
            fit_kwargs["eval_X"] = valid_df[features]
            fit_kwargs["eval_y"] = valid_df["demand"]
            fit_kwargs["callbacks"] = [
                lgb.early_stopping(early_stopping_rounds, verbose=False),
                lgb.log_evaluation(period=0),
            ]
        model.fit(X_train, y_train, **fit_kwargs)
        models[q] = model

    return LGBMQuantileBundle(models=models, features=features, include_env=include_env)


def time_split(
    panel: pd.DataFrame,
    train_ratio: float = 0.75,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    weeks = np.sort(panel["week_start"].unique())
    train_size = max(int(len(weeks) * train_ratio), 12)
    # Need lag history — drop first 8 weeks from training rows usable for fit
    cutoff = weeks[train_size - 1]
    train = panel[panel["week_start"] <= cutoff].copy()
    test = panel[panel["week_start"] > cutoff].copy()
    # Drop rows without enough lag cold-start in train
    min_week = weeks[min(8, len(weeks) - 1)]
    train = train[train["week_start"] >= min_week]
    return train, test, train_size


def importance_table(bundle: LGBMQuantileBundle, top_n: int = 25) -> pd.DataFrame:
    """Gain importance from the median (q50) model."""
    model = bundle.models[0.5]
    gain = model.booster_.feature_importance(importance_type="gain")
    names = bundle.features
    df = pd.DataFrame({"feature": names, "gain": gain}).sort_values("gain", ascending=False)
    df["is_env"] = df["feature"].isin(ENV_FEATURES)
    return df.head(top_n).reset_index(drop=True)
