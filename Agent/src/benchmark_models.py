"""Step 3b: benchmark several model families on one protocol, then stack them.

Answers the review point "only one model is used". Every model here sees the same
feature panel, the same time-based split and the same metrics (WMAPE / MASE, never
MAPE), so the comparison is like-for-like:

    fit weeks            validation weeks      test weeks
    |------------------| |----------------|   |------------------|
    base models trained   meta-model learns    everything scored
                          how to blend them    (never seen before)

Stacking is leak-free by construction: the meta-model only ever sees base-model
predictions for weeks the base models did not train on.

Caveat to report with any result: absolute-error objectives (LightGBM quantile 0.5,
XGBoost MAE) are favoured by WMAPE, while mean-optimal objectives (Poisson deviance,
random-forest squared error) are not. That is a property of the metric, not proof
that one family is better at pharmacy demand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .features_env import build_feature_panel, feature_columns
from .forecast_env_lgbm import time_split
from .metrics import mae, mase, wmape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"

VALID_WEEKS = 8  # last weeks of the training block, held out to fit the meta-model


@dataclass
class ModelSpec:
    """One entry in the benchmark."""

    name: str
    family: str
    objective: str  # what the learner minimises — explains its WMAPE standing
    build: Callable[[int], Any]
    notes: str = ""
    fitted: Any = field(default=None, repr=False)


def _lightgbm_median(seed: int):
    import lightgbm as lgb

    return lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.5,
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=40,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=-1,
        verbosity=-1,
    )


def _xgboost_mae(seed: int):
    import xgboost as xgb

    return xgb.XGBRegressor(
        objective="reg:absoluteerror",
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=-1,
        verbosity=0,
    )


def _random_forest(seed: int):
    from sklearn.ensemble import RandomForestRegressor

    return RandomForestRegressor(
        n_estimators=120,
        min_samples_leaf=20,
        max_features=0.5,
        random_state=seed,
        n_jobs=-1,
    )


def _poisson(seed: int):
    from sklearn.linear_model import PoissonRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    _ = seed
    return make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-3, max_iter=400))


def model_specs() -> list[ModelSpec]:
    """The benchmark line-up. Order is the order reported."""
    return [
        ModelSpec(
            "lightgbm_q50",
            "Gradient-boosted trees",
            "quantile (median)",
            _lightgbm_median,
            "The production model; same settings as Step 3.",
        ),
        ModelSpec(
            "xgboost_mae",
            "Gradient-boosted trees",
            "absolute error",
            _xgboost_mae,
            "Different boosting implementation and tree growth policy.",
        ),
        ModelSpec(
            "random_forest",
            "Bagged trees",
            "squared error (mean)",
            _random_forest,
            "Averages independent trees instead of correcting them in sequence.",
        ),
        ModelSpec(
            "poisson_glm",
            "Generalised linear model",
            "Poisson deviance",
            _poisson,
            "Counts model; no interactions unless the features carry them.",
        ),
    ]


def _blend_weights(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Blend weights on the simplex (w >= 0, sum w = 1) that minimise ABSOLUTE error.

    Fitted on the same loss the benchmark is scored with. A least-squares blend
    (the usual default) optimises squared error and then loses on WMAPE, because
    squared error chases the rare huge weeks that absolute error shrugs off.
    Non-negative weights keep the result readable: each one is a share of the final
    number, so no model is used to subtract from another.
    """
    from scipy.optimize import minimize, nnls

    n_models = P.shape[1]
    start, _ = nnls(P, y)  # least-squares solution as a starting point
    if start.sum() <= 0:
        start = np.full(n_models, 1.0 / n_models)
    else:
        start = start / start.sum()

    result = minimize(
        lambda w: float(np.mean(np.abs(y - P @ w))),
        start,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_models,
        constraints=[{"type": "eq", "fun": lambda w: float(w.sum() - 1.0)}],
        options={"maxiter": 300, "ftol": 1e-8},
    )
    w = result.x if result.success else start
    w = np.clip(w, 0.0, None)
    total = float(w.sum())
    return w / total if total > 0 else np.full(n_models, 1.0 / n_models)


def _mase_by_sku(frame: pd.DataFrame, train_panel: pd.DataFrame, pred_col: str) -> float:
    """Mean per-SKU MASE, scaled by each SKU's own training history."""
    train_by_sku = {
        int(sku): g.sort_values("week_start")["demand"].to_numpy(dtype=float)
        for sku, g in train_panel.groupby("sku_id", sort=False)
    }
    vals: list[float] = []
    for sku, g in frame.groupby("sku_id", sort=False):
        y_train = train_by_sku.get(int(sku))
        if y_train is None or len(y_train) < 2:
            continue
        score = mase(g["actual"].to_numpy(), g[pred_col].to_numpy(), y_train, seasonality=1)
        if np.isfinite(score):
            vals.append(score)
    return float(np.mean(vals)) if vals else float("nan")


def run_benchmark(
    max_skus: int | None = None,
    train_ratio: float = 0.75,
    seed: int = 42,
    include_env: bool = True,
) -> dict[str, Any]:
    """Train every family, blend them, and score all of it on the same test weeks."""
    out = DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Building weekly feature panel (same builder as Step 3)...")
    panel = build_feature_panel(max_skus=max_skus, seed=seed)
    features = feature_columns(include_env=include_env)
    train_df, test_df, _ = time_split(panel, train_ratio=train_ratio)

    train_weeks = np.sort(train_df["week_start"].unique())
    if len(train_weeks) > 2 * VALID_WEEKS:
        cut = train_weeks[-VALID_WEEKS]
        fit_df = train_df[train_df["week_start"] < cut]
        valid_df = train_df[train_df["week_start"] >= cut]
    else:  # tiny panel (smoke test) — fall back to fitting on everything
        fit_df, valid_df = train_df, train_df
    print(
        f"  rows fit={len(fit_df):,} valid={len(valid_df):,} test={len(test_df):,} | "
        f"features={len(features)}"
    )

    X_fit, y_fit = fit_df[features], fit_df["demand"].to_numpy(dtype=float)
    X_valid, X_test = valid_df[features], test_df[features]

    specs = model_specs()
    valid_preds: dict[str, np.ndarray] = {}
    test_preds: dict[str, np.ndarray] = {}
    for spec in specs:
        print(f"Training {spec.name} ({spec.family}, {spec.objective})...")
        model = spec.build(seed)
        model.fit(X_fit, y_fit)
        spec.fitted = model
        # Demand cannot be negative; clip like the production model does
        valid_preds[spec.name] = np.clip(model.predict(X_valid), 0.0, None)
        test_preds[spec.name] = np.clip(model.predict(X_test), 0.0, None)

    names = [s.name for s in specs]
    P_valid = np.column_stack([valid_preds[n] for n in names])
    P_test = np.column_stack([test_preds[n] for n in names])
    weights = _blend_weights(P_valid, valid_df["demand"].to_numpy(dtype=float))
    test_preds["stacked_mae"] = np.clip(P_test @ weights, 0.0, None)
    blend = {n: round(float(w), 4) for n, w in zip(names, weights)}
    print(f"Blend weights (validation weeks, non-negative, sum 1): {blend}")

    scored = test_df[["sku_id", "week_start", "demand", "demand_cohort"]].copy()
    scored = scored.rename(columns={"demand": "actual"})
    for name, pred in test_preds.items():
        scored[name] = pred

    rows = []
    for name in [*names, "stacked_mae"]:
        spec = next((s for s in specs if s.name == name), None)
        rows.append(
            {
                "model": name,
                "family": spec.family if spec else "Ensemble",
                "objective": spec.objective if spec else "absolute-error blend on the simplex",
                "global_wmape": wmape(scored["actual"], scored[name]),
                "mean_mase": _mase_by_sku(scored, train_df, name),
                "global_mae": mae(scored["actual"], scored[name]),
                "bias": float(scored[name].mean() - scored["actual"].mean()),
                "blend_weight": blend.get(name),
                "notes": spec.notes if spec else "Weights fitted on validation weeks only.",
            }
        )
    summary = pd.DataFrame(rows).sort_values("global_wmape").reset_index(drop=True)
    summary["rank"] = np.arange(1, len(summary) + 1)

    summary_csv = out / "step3b_model_benchmark.csv"
    summary.to_csv(summary_csv, index=False)
    preds_path = out / "step3b_benchmark_predictions.parquet"
    scored.to_parquet(preds_path, index=False)

    payload = {
        "protocol": {
            "panel_rows": int(len(panel)),
            "n_skus": int(panel["sku_id"].nunique()),
            "n_weeks": int(panel["week_start"].nunique()),
            "fit_rows": int(len(fit_df)),
            "valid_rows": int(len(valid_df)),
            "test_rows": int(len(test_df)),
            "validation_weeks_for_stacking": VALID_WEEKS,
            "features": features,
            "include_env": include_env,
            "seed": seed,
        },
        "results": summary.to_dict(orient="records"),
        "blend_weights": blend,
        "metric_note": (
            "WMAPE and MASE only (never MAPE: many weeks have zero demand). "
            "Absolute-error objectives are favoured by WMAPE; mean-optimal "
            "objectives (Poisson, random forest) are not."
        ),
        "data_note": "DEV SYNTHETIC data — not Bhagyashree Medical sales.",
    }
    summary_json = out / "step3b_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nBenchmark (lower WMAPE is better):")
    print(
        summary[["rank", "model", "family", "global_wmape", "mean_mase", "blend_weight"]]
        .to_string(index=False)
    )
    return {
        "summary": summary_csv,
        "predictions": preds_path,
        "json": summary_json,
        "table": summary,
        "weights": blend,
    }
