"""Step 6: stockout-risk classifier, and the false-positive analysis it makes possible.

Forecasting is regression, so it has no "false positive". This module adds the one
genuinely binary question in the system — *will this medicine run short next week?* —
which turns model error into a confusion matrix a pharmacist can reason about:

    predicted short   predicted fine
    +---------------+---------------+
    | true positive | false negative|  actually short  -> patient leaves empty-handed
    +---------------+---------------+
    | FALSE POSITIVE| true negative |  actually fine   -> money tied up, expiry risk
    +---------------+---------------+

The two mistakes do not cost the same, so a 0.5 threshold is an unjustified default.
`choose_threshold()` picks the cut-off that minimises expected cost for a stated
cost ratio, and the sweep table shows what every other choice would have cost.

Target: a stockout event recorded in that SKU-week (unmet demand > 0). Features are the
same lagged panel Step 3 uses, so nothing from week t leaks into predicting week t.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .features_env import build_feature_panel, feature_columns
from .forecast_env_lgbm import time_split
from .series import load_demand_events

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"

# How much worse a missed stockout is than an unnecessary reorder.
# A stockout costs the lost margin AND sends a patient elsewhere; an unnecessary
# reorder costs holding cost and some expiry risk on one batch. 5:1 is the project's
# working assumption and is a parameter, not a fact — the sweep shows other values.
DEFAULT_COST_RATIO = 5.0


def _weekly_stockout_labels() -> pd.DataFrame:
    """One row per SKU-week that had activity, with a 0/1 stockout flag."""
    events = load_demand_events(use_unmet=True)
    events["week_start"] = events["date"] - pd.to_timedelta(
        events["date"].dt.weekday, unit="D"
    )
    weekly = events.groupby(["sku_id", "week_start"], as_index=False).agg(
        stockout=("stockout", "max")
    )
    weekly["stockout"] = weekly["stockout"].astype(int)
    weekly["sku_id"] = weekly["sku_id"].astype(int)
    return weekly


def build_labelled_panel(max_skus: int | None = None, seed: int = 42) -> pd.DataFrame:
    """Step 3's feature panel plus the binary stockout target."""
    panel = build_feature_panel(max_skus=max_skus, seed=seed)
    labels = _weekly_stockout_labels()
    panel = panel.merge(labels, on=["sku_id", "week_start"], how="left")
    # Weeks with no transaction at all cannot have stocked out
    panel["stockout"] = panel["stockout"].fillna(0).astype(int)
    return panel


def _confusion(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    return {
        "true_positive": int(np.sum((y_pred == 1) & (y_true == 1))),
        "false_positive": int(np.sum((y_pred == 1) & (y_true == 0))),
        "false_negative": int(np.sum((y_pred == 0) & (y_true == 1))),
        "true_negative": int(np.sum((y_pred == 0) & (y_true == 0))),
    }


def _scores(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (proba >= threshold).astype(int)
    cm = _confusion(y_true, pred)
    tp, fp, fn = cm["true_positive"], cm["false_positive"], cm["false_negative"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": round(float(threshold), 3),
        **cm,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "alerts_raised": int(tp + fp),
        "alert_rate": round(float(np.mean(pred)), 4),
    }


# Denser at the low end: when stockouts get commoner than the model was trained for,
# the cost-optimal cut-off falls well below 0.1 and a uniform grid misses it.
THRESHOLD_GRID = np.round(
    np.concatenate([np.arange(0.01, 0.10, 0.01), np.arange(0.10, 0.96, 0.05)]), 3
)


def threshold_sweep(
    y_true: np.ndarray,
    proba: np.ndarray,
    cost_ratio: float = DEFAULT_COST_RATIO,
) -> pd.DataFrame:
    """Score every candidate cut-off, with the expected cost of each."""
    rows = []
    for t in THRESHOLD_GRID:
        row = _scores(y_true, proba, t)
        # Expected cost per 1,000 SKU-weeks, in "unnecessary reorder" units
        n = len(y_true)
        row["cost_per_1000"] = round(
            (row["false_positive"] + cost_ratio * row["false_negative"]) / n * 1000, 2
        )
        rows.append(row)
    return pd.DataFrame(rows)


def choose_threshold(sweep: pd.DataFrame) -> float:
    """The cut-off with the lowest expected cost in the sweep."""
    return float(sweep.loc[sweep["cost_per_1000"].idxmin(), "threshold"])


def _build_models(seed: int) -> dict[str, Any]:
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "lightgbm_clf": lgb.LGBMClassifier(
            objective="binary",
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=63,
            min_child_samples=40,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        ),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, C=1.0, random_state=seed),
        ),
    }


def run_stockout_classifier(
    max_skus: int | None = None,
    train_ratio: float = 0.75,
    seed: int = 42,
    cost_ratio: float = DEFAULT_COST_RATIO,
) -> dict[str, Any]:
    """Train, evaluate and pick an operating threshold from the cost of each error."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    out = DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Building labelled panel (Step 3 features + stockout target)...")
    panel = build_labelled_panel(max_skus=max_skus, seed=seed)
    features = feature_columns(include_env=True)
    train_df, test_df, _ = time_split(panel, train_ratio=train_ratio)
    y_train = train_df["stockout"].to_numpy()
    y_test = test_df["stockout"].to_numpy()
    base_rate = float(y_test.mean())
    print(
        f"  train={len(train_df):,} test={len(test_df):,} | "
        f"stockout rate: train {y_train.mean():.1%}, test {base_rate:.1%}"
    )

    results: list[dict[str, Any]] = []
    probas: dict[str, np.ndarray] = {}
    for name, model in _build_models(seed).items():
        print(f"Training {name}...")
        model.fit(train_df[features], y_train)
        proba = model.predict_proba(test_df[features])[:, 1]
        probas[name] = proba
        results.append(
            {
                "model": name,
                "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
                "pr_auc": round(float(average_precision_score(y_test, proba)), 4),
                "baseline_pr_auc": round(base_rate, 4),
                **_scores(y_test, proba, 0.5),
            }
        )

    model_table = pd.DataFrame(results).sort_values("pr_auc", ascending=False)
    best_model = str(model_table.iloc[0]["model"])
    best_proba = probas[best_model]

    sweep = threshold_sweep(y_test, best_proba, cost_ratio=cost_ratio)
    chosen = choose_threshold(sweep)
    chosen_row = _scores(y_test, best_proba, chosen)
    default_row = _scores(y_test, best_proba, 0.5)

    # Health warnings: a result can be arithmetically correct and still not safe to use
    warnings: list[str] = []
    drift = abs(float(y_train.mean()) - base_rate)
    if drift > 0.05:
        warnings.append(
            f"DISTRIBUTION SHIFT: stockouts were {y_train.mean():.1%} of training weeks "
            f"but {base_rate:.1%} of test weeks. The model's probabilities are "
            "calibrated for the wrong world, so the threshold below is compensating for "
            "drift rather than reflecting true risk. Retrain on a rolling recent window "
            "before trusting it operationally."
        )
    if chosen <= float(THRESHOLD_GRID.min()) or chosen >= float(THRESHOLD_GRID.max()):
        warnings.append(
            f"THRESHOLD AT GRID EDGE: the cost-optimal cut-off ({chosen}) is the lowest "
            "(or highest) value searched, which means the optimum lies outside the grid. "
            "Read it as 'alert on nearly everything', i.e. the model is not separating "
            "the classes well enough at this cost ratio — not as a tuned setting."
        )
    if chosen_row["alert_rate"] > 0.2:
        warnings.append(
            f"ALERT FATIGUE RISK: this cut-off raises an alert on "
            f"{chosen_row['alert_rate']:.0%} of SKU-weeks. Beyond roughly 20%, staff stop "
            "reading alerts and real recall collapses regardless of the measured recall."
        )

    sweep_path = out / "step6_threshold_sweep.csv"
    sweep.to_csv(sweep_path, index=False)
    models_path = out / "step6_classifier_models.csv"
    model_table.to_csv(models_path, index=False)

    payload = {
        "task": "Will this medicine have unmet demand (a stockout) in the coming week?",
        "protocol": {
            "rows_train": int(len(train_df)),
            "rows_test": int(len(test_df)),
            "features": len(features),
            "split": "time-based, same as Step 3",
            "seed": seed,
        },
        "class_balance": {
            "train_stockout_rate": round(float(y_train.mean()), 4),
            "test_stockout_rate": round(base_rate, 4),
        },
        "models": model_table.to_dict(orient="records"),
        "best_model": best_model,
        "cost_assumption": {
            "cost_ratio_fn_over_fp": cost_ratio,
            "meaning": (
                "One missed stockout is treated as costing the same as "
                f"{cost_ratio:g} unnecessary reorders. A working assumption, not a "
                "measured figure — the sweep shows what other ratios would choose."
            ),
        },
        "threshold": {
            "chosen": chosen,
            "chosen_scores": chosen_row,
            "default_0.5_scores": default_row,
        },
        "warnings": warnings,
        "data_note": "DEV SYNTHETIC data — not Bhagyashree Medical sales.",
    }
    summary_path = out / "step6_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nModels (ranked by PR-AUC; random guessing would score the base rate):")
    print(
        model_table[["model", "roc_auc", "pr_auc", "baseline_pr_auc", "precision", "recall"]]
        .to_string(index=False)
    )
    print(f"\nCost-optimal threshold for a {cost_ratio:g}:1 cost ratio: {chosen}")
    print(
        f"  at {chosen}: recall {chosen_row['recall']:.1%}, precision "
        f"{chosen_row['precision']:.1%}, {chosen_row['false_positive']:,} false alarms, "
        f"{chosen_row['false_negative']:,} missed stockouts"
    )
    print(
        f"  at 0.5 : recall {default_row['recall']:.1%}, precision "
        f"{default_row['precision']:.1%}, {default_row['false_positive']:,} false alarms, "
        f"{default_row['false_negative']:,} missed stockouts"
    )
    for w in warnings:
        print(f"\n  !! {w}")
    return {
        "warnings": warnings,
        "models": models_path,
        "sweep": sweep_path,
        "json": summary_path,
        "table": model_table,
        "chosen_threshold": chosen,
    }
