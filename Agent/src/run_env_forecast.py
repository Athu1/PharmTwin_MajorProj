"""Step 3: LightGBM env-conditioned quantile forecasting vs intermittent baselines."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from .features_env import build_feature_panel
from .forecast_env_lgbm import importance_table, time_split, train_quantile_models
from .forecast_intermittent import rolling_forecast
from .metrics import mae, mase, wmape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"


def _baseline_forecasts_on_test(
    panel: pd.DataFrame,
    train_size_weeks: int,
    methods: tuple[str, ...] = ("sba", "tsb", "ma"),
) -> pd.DataFrame:
    """Align Croston-family one-step forecasts to the same test week rows as LightGBM."""
    weeks = np.sort(panel["week_start"].unique())
    rows = []
    n_skus = int(panel["sku_id"].nunique())
    for sku_id, g in tqdm(panel.groupby("sku_id", sort=False), total=n_skus, desc="Baselines"):
        g = g.sort_values("week_start")
        y = g["demand"].to_numpy(dtype=float)
        if len(y) <= train_size_weeks or np.sum(y[:train_size_weeks] > 0) < 3:
            continue
        week_test = g["week_start"].iloc[train_size_weeks:].to_numpy()
        actual = y[train_size_weeks:]
        for method in methods:
            pred = rolling_forecast(y, method, train_size_weeks)
            for w, a, p in zip(week_test, actual, pred):
                rows.append(
                    {
                        "sku_id": int(sku_id),
                        "week_start": w,
                        "actual": float(a),
                        "forecast": float(p),
                        "method": method,
                    }
                )
    return pd.DataFrame(rows)


def _score_frame(df: pd.DataFrame, method_col: str = "method") -> pd.DataFrame:
    rows = []
    for method, sub in df.groupby(method_col):
        y = sub["actual"].to_numpy()
        p = sub["forecast"].to_numpy()
        # Per-SKU MASE then average
        mase_vals = []
        for _, g in sub.groupby("sku_id"):
            # approximate scale from all actuals of that sku in frame (test only) — weak;
            # better: skip per-sku and report global only + mae
            pass
        rows.append(
            {
                "method": method,
                "n_rows": int(len(sub)),
                "n_skus": int(sub["sku_id"].nunique()),
                "global_wmape": wmape(y, p),
                "global_mae": mae(y, p),
                "mean_pred": float(np.mean(p)),
                "mean_actual": float(np.mean(y)),
                "bias": float(np.mean(p) - np.mean(y)),
            }
        )
    return pd.DataFrame(rows).sort_values("global_wmape")


def _mase_by_sku_against_train(
    pred_df: pd.DataFrame,
    panel: pd.DataFrame,
    train_size_weeks: int,
) -> float:
    """Mean SKU-level MASE using training history as scale."""
    weeks = np.sort(panel["week_start"].unique())
    train_weeks = set(weeks[:train_size_weeks])
    scales = {}
    for sku_id, g in panel.groupby("sku_id"):
        y_train = g.loc[g["week_start"].isin(train_weeks), "demand"].to_numpy(dtype=float)
        if len(y_train) < 2:
            continue
        scale = float(np.mean(np.abs(np.diff(y_train))))
        if scale > 1e-12:
            scales[int(sku_id)] = scale
    vals = []
    for sku_id, g in pred_df.groupby("sku_id"):
        scale = scales.get(int(sku_id))
        if scale is None:
            continue
        vals.append(float(np.mean(np.abs(g["actual"] - g["forecast"])) / scale))
    return float(np.mean(vals)) if vals else float("nan")


def run_step3(
    train_ratio: float = 0.75,
    max_skus: int | None = None,
    seed: int = 42,
    out_dir: Path | str | None = None,
) -> dict[str, Path]:
    out = Path(out_dir) if out_dir else DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Building weekly feature panel (lags + Navi Mumbai covariates)...")
    panel = build_feature_panel(max_skus=max_skus, seed=seed)
    print(f"  Panel shape: {panel.shape} | SKUs: {panel['sku_id'].nunique()} | weeks: {panel['week_start'].nunique()}")

    train_df, test_df, train_size = time_split(panel, train_ratio=train_ratio)
    # Hold out last 8 train weeks as validation for early stopping
    train_weeks = np.sort(train_df["week_start"].unique())
    if len(train_weeks) > 16:
        val_cut = train_weeks[-8]
        valid_df = train_df[train_df["week_start"] >= val_cut]
        fit_df = train_df[train_df["week_start"] < val_cut]
    else:
        valid_df, fit_df = None, train_df

    print(f"  Fit rows: {len(fit_df):,} | Valid: {0 if valid_df is None else len(valid_df):,} | Test: {len(test_df):,}")

    print("Training LightGBM quantile models WITH env covariates...")
    bundle_env = train_quantile_models(fit_df, include_env=True, seed=seed, valid_df=valid_df)
    print("Training LightGBM ablation WITHOUT env covariates...")
    bundle_noenv = train_quantile_models(fit_df, include_env=False, seed=seed, valid_df=valid_df)

    pred_env = bundle_env.predict(test_df)
    pred_no = bundle_noenv.predict(test_df)

    lgbm_rows = test_df[["sku_id", "week_start", "demand", "demand_cohort", "pm25_max", "rain_gt20_lag7_any", "high_pm25_days", "health_alert_any"]].copy()
    lgbm_rows = lgbm_rows.rename(columns={"demand": "actual"})
    lgbm_rows["forecast"] = pred_env["point"]
    lgbm_rows["q50"] = pred_env["q50"]
    lgbm_rows["q90"] = pred_env["q90"]
    lgbm_rows["q95"] = pred_env["q95"]
    lgbm_rows["method"] = "lgbm_env"

    lgbm_no = lgbm_rows[["sku_id", "week_start", "actual"]].copy()
    lgbm_no["forecast"] = pred_no["point"]
    lgbm_no["method"] = "lgbm_noenv"

    print("Computing SBA / TSB / MA baselines on same test window...")
    baseline = _baseline_forecasts_on_test(panel, train_size_weeks=train_size)

    # Align baselines to test_df keys only
    test_keys = test_df[["sku_id", "week_start"]]
    baseline = baseline.merge(test_keys, on=["sku_id", "week_start"], how="inner")

    combined = pd.concat(
        [
            lgbm_rows[["sku_id", "week_start", "actual", "forecast", "method"]],
            lgbm_no,
            baseline,
        ],
        ignore_index=True,
    )

    summary = _score_frame(combined)
    summary["mase_mean"] = [
        _mase_by_sku_against_train(combined[combined["method"] == m], panel, train_size)
        for m in summary["method"]
    ]

    # Cohort / stress slices for env model
    slice_rows = []
    env_only = lgbm_rows.copy()
    slices = {
        "all": env_only,
        "respiratory": env_only[env_only["demand_cohort"] == "respiratory"],
        "vector_borne": env_only[env_only["demand_cohort"] == "vector_borne"],
        "high_pm25_week": env_only[env_only["pm25_max"] >= 90],
        "rain_lag7_alert": env_only[env_only["rain_gt20_lag7_any"] == 1],
        "health_alert": env_only[env_only["health_alert_any"] == 1],
    }
    for name, sub in slices.items():
        if len(sub) == 0:
            continue
        # Compare env vs noenv on same rows
        no = lgbm_no.merge(sub[["sku_id", "week_start"]], on=["sku_id", "week_start"], how="inner")
        slice_rows.append(
            {
                "slice": name,
                "method": "lgbm_env",
                "n_rows": int(len(sub)),
                "global_wmape": wmape(sub["actual"], sub["forecast"]),
                "global_mae": mae(sub["actual"], sub["forecast"]),
            }
        )
        slice_rows.append(
            {
                "slice": name,
                "method": "lgbm_noenv",
                "n_rows": int(len(no)),
                "global_wmape": wmape(no["actual"], no["forecast"]),
                "global_mae": mae(no["actual"], no["forecast"]),
            }
        )
        for method in ("sba", "tsb"):
            b = baseline[baseline["method"] == method].merge(
                sub[["sku_id", "week_start"]], on=["sku_id", "week_start"], how="inner"
            )
            if len(b):
                slice_rows.append(
                    {
                        "slice": name,
                        "method": method,
                        "n_rows": int(len(b)),
                        "global_wmape": wmape(b["actual"], b["forecast"]),
                        "global_mae": mae(b["actual"], b["forecast"]),
                    }
                )

    slice_df = pd.DataFrame(slice_rows)
    imp = importance_table(bundle_env, top_n=30)

    # Persist
    metrics_path = out / "step3_metrics_summary.csv"
    summary.to_csv(metrics_path, index=False)
    slice_path = out / "step3_metrics_by_slice.csv"
    slice_df.to_csv(slice_path, index=False)
    imp_path = out / "step3_feature_importance.csv"
    imp.to_csv(imp_path, index=False)

    fc_path = out / "step3_forecasts_weekly.parquet"
    # Full quantile forecast frame for env model (feeds Step 4 safety stock)
    qframe = lgbm_rows.copy()
    qframe.to_parquet(fc_path, index=False)
    qframe.to_csv(out / "step3_forecasts_weekly.csv", index=False)
    combined.to_parquet(out / "step3_all_methods_forecasts.parquet", index=False)

    # Save models
    model_dir = out / "models_step3"
    model_dir.mkdir(exist_ok=True)
    for q, model in bundle_env.models.items():
        model.booster_.save_model(str(model_dir / f"lgbm_env_q{int(q * 100):02d}.txt"))
    for q, model in bundle_noenv.models.items():
        model.booster_.save_model(str(model_dir / f"lgbm_noenv_q{int(q * 100):02d}.txt"))

    payload = {
        "n_skus": int(panel["sku_id"].nunique()),
        "n_weeks": int(panel["week_start"].nunique()),
        "train_weeks": int(train_size),
        "test_rows": int(len(test_df)),
        "quantiles": [0.5, 0.9, 0.95],
        "metrics_all": summary.to_dict(orient="records"),
        "metrics_slices": slice_df.to_dict(orient="records"),
        "top_features": imp.head(15).to_dict(orient="records"),
        "notes": (
            "LightGBM quantile objective (q50/q90/q95) conditioned on lagged rain, "
            "PM2.5, and public-health alerts. Ablation removes env features. "
            "Scored with WMAPE and MASE only (no MAPE)."
        ),
    }
    summary_json = out / "step3_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n=== Step 3 — all methods (lower WMAPE better) ===")
    print(summary.to_string(index=False))
    print("\n=== Env stress / cohort slices (lgbm_env vs baselines) ===")
    print(slice_df.to_string(index=False))
    print("\n=== Top feature gains (q50 env model) ===")
    print(imp.head(12).to_string(index=False))

    return {
        "metrics_summary": metrics_path,
        "metrics_slices": slice_path,
        "feature_importance": imp_path,
        "forecasts": fc_path,
        "summary": summary_json,
        "models": model_dir,
    }


if __name__ == "__main__":
    run_step3()
