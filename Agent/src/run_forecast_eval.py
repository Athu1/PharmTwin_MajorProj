"""Step 2: intermittent demand forecast evaluation (Croston / SBA / TSB vs MA)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from .forecast_intermittent import rolling_forecast
from .metrics import mae, mase, wmape
from .series import load_demand_events, to_weekly_demand, zero_inflation_stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"

METHODS = ("croston", "sba", "tsb", "ma")


def demand_pattern(y: np.ndarray) -> dict[str, float | str]:
    """Syntetos–Boylan ADI / CV² demand classification."""
    y = np.asarray(y, dtype=float)
    nz = y[y > 0]
    n = len(y)
    n_nz = len(nz)
    adi = float(n / n_nz) if n_nz > 0 else float(n)
    if n_nz >= 2 and float(np.mean(nz)) > 0:
        cv2 = float((np.std(nz, ddof=1) / np.mean(nz)) ** 2)
    else:
        cv2 = 0.0
    if adi > 1.32 and cv2 <= 0.49:
        klass = "intermittent"
    elif adi <= 1.32 and cv2 <= 0.49:
        klass = "smooth"
    elif adi > 1.32 and cv2 > 0.49:
        klass = "lumpy"
    else:
        klass = "erratic"
    return {"adi": adi, "cv2": cv2, "demand_pattern": klass}


def _summarize_slice(
    sub_metrics: pd.DataFrame,
    sub_fc: pd.DataFrame,
    slice_name: str,
) -> list[dict]:
    rows = []
    for method in METHODS:
        msub = sub_metrics[sub_metrics["method"] == method]
        fsub = sub_fc[sub_fc["method"] == method]
        if msub.empty or fsub.empty:
            continue
        valid = msub.dropna(subset=["wmape"])
        w = valid["mean_actual"].clip(lower=0).to_numpy()
        if len(valid) and float(w.sum()) > 0:
            w_wmape = float(np.average(valid["wmape"].to_numpy(), weights=w))
        else:
            w_wmape = float("nan")
        rows.append(
            {
                "slice": slice_name,
                "method": method,
                "n_skus": int(msub["sku_id"].nunique()),
                "wmape_mean": float(valid["wmape"].mean()) if len(valid) else float("nan"),
                "wmape_demand_weighted": w_wmape,
                "global_wmape": wmape(fsub["actual"].to_numpy(), fsub["forecast"].to_numpy()),
                "mase_mean": float(msub["mase"].mean(skipna=True)),
                "mase_median": float(msub["mase"].median(skipna=True)),
                "mae_mean": float(msub["mae"].mean()),
                "bias_mean": float(msub["bias"].mean()),
                "mean_pred": float(msub["mean_pred"].mean()),
                "mean_actual": float(msub["mean_actual"].mean()),
            }
        )
    return rows


def run_step2(
    train_ratio: float = 0.75,
    max_skus: int | None = None,
    min_train_nonzero: int = 3,
    alpha: float = 0.1,
    beta: float = 0.1,
    seed: int = 42,
    out_dir: Path | str | None = None,
) -> dict[str, Path]:
    """
    Build weekly intermittent series, roll one-step forecasts, score with WMAPE/MASE.

    MAPE is intentionally not computed (undefined on zero-sale weeks).
    """
    out = Path(out_dir) if out_dir else DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Loading demand events (qty + unmet)...")
    events = load_demand_events(use_unmet=True)
    assortment = pd.read_csv(out / "assortment_3k.csv")
    sku_ids = assortment["sku_id"].astype(int).tolist()
    if max_skus is not None:
        rng = np.random.default_rng(seed)
        sku_ids = list(rng.choice(sku_ids, size=min(max_skus, len(sku_ids)), replace=False))

    print(f"Building dense weekly panel for {len(sku_ids)} SKUs...")
    panel = to_weekly_demand(events, sku_ids=sku_ids)
    zstats = zero_inflation_stats(panel)
    print(
        f"  Zero-inflation: {zstats['pct_zero']:.1f}% zeros | "
        f"{zstats['n_weeks']} weeks | mean demand {zstats['mean_demand']:.3f}"
    )

    weeks = np.sort(panel["week_start"].unique())
    n_weeks = len(weeks)
    train_size = max(int(n_weeks * train_ratio), 12)
    test_size = n_weeks - train_size
    print(f"  Train weeks: {train_size} | Test weeks: {test_size}")

    per_sku_rows: list[dict] = []
    forecast_frames: list[pd.DataFrame] = []
    grouped = {sid: g.sort_values("week_start") for sid, g in panel.groupby("sku_id")}

    for sku_id, g in tqdm(grouped.items(), total=len(grouped), desc="Forecasting SKUs"):
        y = g["demand"].to_numpy(dtype=float)
        if np.sum(y[:train_size] > 0) < min_train_nonzero:
            continue

        pattern = demand_pattern(y[:train_size])
        y_test = y[train_size:]
        if len(y_test) == 0:
            continue

        preds_by_method = {
            method: rolling_forecast(y, method, train_size, alpha=alpha, beta=beta)
            for method in METHODS
        }

        for method, pred in preds_by_method.items():
            per_sku_rows.append(
                {
                    "sku_id": int(sku_id),
                    "method": method,
                    "wmape": wmape(y_test, pred),
                    "mase": mase(y_test, pred, y[:train_size], seasonality=1),
                    "mae": mae(y_test, pred),
                    "mean_pred": float(np.mean(pred)),
                    "mean_actual": float(np.mean(y_test)),
                    "bias": float(np.mean(pred) - np.mean(y_test)),
                    "adi": pattern["adi"],
                    "cv2": pattern["cv2"],
                    "demand_pattern": pattern["demand_pattern"],
                }
            )
            forecast_frames.append(
                pd.DataFrame(
                    {
                        "sku_id": int(sku_id),
                        "week_start": g["week_start"].iloc[train_size:].to_numpy(),
                        "actual": y_test,
                        "forecast": pred,
                        "method": method,
                        "demand_pattern": pattern["demand_pattern"],
                    }
                )
            )

    metrics_sku = pd.DataFrame(per_sku_rows)
    metrics_path = out / "step2_metrics_by_sku.csv"
    metrics_sku.to_csv(metrics_path, index=False)

    forecasts = pd.concat(forecast_frames, ignore_index=True) if forecast_frames else pd.DataFrame()
    forecasts_path = out / "step2_forecasts_weekly.parquet"
    forecasts.to_parquet(forecasts_path, index=False)
    forecasts.to_csv(out / "step2_forecasts_weekly.csv", index=False)

    summary_rows = _summarize_slice(metrics_sku, forecasts, "all")
    for klass in ("intermittent", "lumpy", "erratic", "smooth"):
        msub = metrics_sku[metrics_sku["demand_pattern"] == klass]
        fsub = forecasts[forecasts["demand_pattern"] == klass]
        if len(msub):
            summary_rows.extend(_summarize_slice(msub, fsub, klass))

    summary_df = pd.DataFrame(summary_rows)
    summary_df["rank_in_slice"] = summary_df.groupby("slice")["global_wmape"].rank(method="min")
    summary_csv = out / "step2_metrics_summary.csv"
    summary_df.to_csv(summary_csv, index=False)

    pattern_counts = (
        metrics_sku.drop_duplicates("sku_id")["demand_pattern"].value_counts().to_dict()
        if len(metrics_sku)
        else {}
    )
    all_slice = summary_df[summary_df["slice"] == "all"].sort_values("global_wmape")
    inter_slice = summary_df[summary_df["slice"] == "intermittent"].sort_values("global_wmape")

    payload = {
        "zero_inflation": zstats,
        "train_weeks": train_size,
        "test_weeks": test_size,
        "n_skus_evaluated": int(metrics_sku["sku_id"].nunique()) if len(metrics_sku) else 0,
        "demand_pattern_counts": pattern_counts,
        "methods": list(METHODS),
        "metrics_all": all_slice.to_dict(orient="records"),
        "metrics_intermittent_slice": inter_slice.to_dict(orient="records"),
        "notes": (
            "Evaluated with WMAPE and MASE only (MAPE excluded). "
            "Demand = qty + unmet_qty. Weekly aggregation. Rolling one-step-ahead. "
            "Demand patterns use Syntetos-Boylan ADI/CV2 cutoffs (1.32 / 0.49)."
        ),
    }
    summary_json = out / "step2_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cols = [
        "method",
        "n_skus",
        "global_wmape",
        "wmape_demand_weighted",
        "mase_mean",
        "mase_median",
        "bias_mean",
    ]
    print("\n=== Zero-inflation / demand patterns ===")
    print(f"Zeros: {zstats['pct_zero']:.1f}% | pattern counts: {pattern_counts}")
    print("\n=== All SKUs (lower global WMAPE / MASE is better) ===")
    print(all_slice[cols].to_string(index=False))
    if len(inter_slice):
        print("\n=== Intermittent SKUs only (ADI>1.32, CV2<=0.49) ===")
        print(inter_slice[cols].to_string(index=False))
        best_i = inter_slice.iloc[0]
        ma_i = inter_slice[inter_slice["method"] == "ma"]
        print(
            f"\nBest on intermittent slice: {best_i['method']} "
            f"(WMAPE={best_i['global_wmape']:.3f})"
        )
        if len(ma_i):
            print(f"MA on intermittent slice: WMAPE={ma_i.iloc[0]['global_wmape']:.3f}")

    return {
        "metrics_by_sku": metrics_path,
        "metrics_summary": summary_csv,
        "forecasts": forecasts_path,
        "summary": summary_json,
    }


if __name__ == "__main__":
    run_step2()
