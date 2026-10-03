"""Step 3c: multi-week forecasts, and a cover-window model for the reorder decision.

Two problems with Step 3 that this module fixes.

**One week is not the decision.** Step 3 predicts next week only, but an order placed
today arrives after the lead time L and must last until the next review R weeks later.
The quantity that matters is total demand over the next L + R weeks, not next week's.

**Averaging the forecast throws it away.** Step 4 collapsed 27 weeks of quantiles into
one mean per medicine, so a monsoon spike and a dead week produced the same reorder
point. Worse, safety stock was scaled by sqrt(L + R), which assumes weekly demand is
independent and identically distributed — exactly what seasonality is not.

So two kinds of target are trained here, both *direct* (a model per horizon, no feeding
predictions back into themselves, so errors do not compound):

| Target | Meaning | Used for |
|---|---|---|
| `target_h1` … `target_h4` | demand in week t, t+1, t+2, t+3 | showing the weeks ahead |
| `target_cover` | **total** demand over weeks t … t+L+R-1 | the reorder point |

Because the cover model predicts the window total directly, its quantiles give the
spread of that total. Safety stock becomes `Z x sigma_cover` with no sqrt(L + R) term
and no independence assumption: the model learned the window.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .features_env import build_feature_panel, feature_columns
from .forecast_env_lgbm import time_split
from .metrics import mae, mase, wmape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"

QUANTILES = (0.50, 0.90, 0.95)
DEFAULT_HORIZONS = (1, 2, 3, 4)
VALID_WEEKS = 8


def build_horizon_panel(
    max_skus: int | None = None,
    seed: int = 42,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    cover_weeks: int = 2,
) -> pd.DataFrame:
    """Step 3's feature panel plus one target per horizon and the cover-window total.

    Row t carries features built from data up to week t-1, so every target below is
    strictly in the future relative to what the model can see.
    """
    panel = build_feature_panel(max_skus=max_skus, seed=seed)
    panel = panel.sort_values(["sku_id", "week_start"]).reset_index(drop=True)
    grouped = panel.groupby("sku_id", sort=False)["demand"]

    for h in horizons:
        # demand in week t + (h-1)
        panel[f"target_h{h}"] = grouped.shift(-(h - 1))

    # total demand over weeks t .. t+cover-1
    panel["target_cover"] = grouped.transform(
        lambda s: s.rolling(cover_weeks).sum().shift(-(cover_weeks - 1))
    )
    panel.attrs["cover_weeks"] = cover_weeks
    return panel


def _lgbm(alpha: float, seed: int):
    import lightgbm as lgb

    return lgb.LGBMRegressor(
        objective="quantile",
        alpha=alpha,
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
    )


def _fit_quantiles(
    fit_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    test_df: pd.DataFrame,
    features: list[str],
    target: str,
    seed: int,
) -> pd.DataFrame:
    """Train q50/q90/q95 for one target and return predictions on the test rows."""
    import lightgbm as lgb

    fit = fit_df.dropna(subset=[target])
    valid = valid_df.dropna(subset=[target])
    test = test_df.dropna(subset=[target])
    out = test[["sku_id", "week_start", target]].copy()
    out = out.rename(columns={target: "actual"})

    for q in QUANTILES:
        model = _lgbm(q, seed)
        fit_kwargs: dict[str, Any] = {}
        if len(valid):
            fit_kwargs["eval_set"] = [(valid[features], valid[target])]
            fit_kwargs["callbacks"] = [
                lgb.early_stopping(40, verbose=False),
                lgb.log_evaluation(period=0),
            ]
        model.fit(fit[features], fit[target], **fit_kwargs)
        out[f"q{int(q * 100):02d}"] = np.clip(model.predict(test[features]), 0.0, None)
    return out


def _mase_by_sku(frame: pd.DataFrame, train_panel: pd.DataFrame, pred_col: str) -> float:
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


def run_horizon_forecasts(
    max_skus: int | None = None,
    train_ratio: float = 0.75,
    seed: int = 42,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    lead_time_weeks: int = 1,
    review_period_weeks: int = 1,
) -> dict[str, Any]:
    """Train every horizon plus the cover window, score them, and write the outputs."""
    out = DATA_OUT
    out.mkdir(parents=True, exist_ok=True)
    cover_weeks = int(lead_time_weeks + review_period_weeks)

    print(f"Building panel with horizons {horizons} and a {cover_weeks}-week cover window...")
    panel = build_horizon_panel(
        max_skus=max_skus, seed=seed, horizons=horizons, cover_weeks=cover_weeks
    )
    features = feature_columns(include_env=True)
    train_df, test_df, _ = time_split(panel, train_ratio=train_ratio)

    train_weeks = np.sort(train_df["week_start"].unique())
    if len(train_weeks) > 2 * VALID_WEEKS:
        cut = train_weeks[-VALID_WEEKS]
        fit_df = train_df[train_df["week_start"] < cut]
        valid_df = train_df[train_df["week_start"] >= cut]
    else:
        fit_df, valid_df = train_df, train_df.iloc[:0]
    print(f"  rows fit={len(fit_df):,} valid={len(valid_df):,} test={len(test_df):,}")

    rows: list[dict[str, Any]] = []
    horizon_frames: list[pd.DataFrame] = []
    for h in horizons:
        target = f"target_h{h}"
        print(f"Training horizon h={h} ({target})...")
        pred = _fit_quantiles(fit_df, valid_df, test_df, features, target, seed)
        pred["horizon"] = h
        horizon_frames.append(pred)
        rows.append(
            {
                "target": f"h{h}",
                "description": f"demand {h} week(s) ahead",
                "n_test_rows": int(len(pred)),
                "global_wmape": round(wmape(pred["actual"], pred["q50"]), 4),
                "mean_mase": round(_mase_by_sku(pred, train_df, "q50"), 4),
                "global_mae": round(mae(pred["actual"], pred["q50"]), 4),
                "q95_coverage": round(float((pred["actual"] <= pred["q95"]).mean()), 4),
            }
        )

    print(f"Training the {cover_weeks}-week cover window (target_cover)...")
    cover = _fit_quantiles(fit_df, valid_df, test_df, features, "target_cover", seed)
    rows.append(
        {
            "target": "cover",
            "description": f"total demand over the next {cover_weeks} weeks (L+R)",
            "n_test_rows": int(len(cover)),
            "global_wmape": round(wmape(cover["actual"], cover["q50"]), 4),
            "mean_mase": float("nan"),  # a window total has no one-step naive baseline
            "global_mae": round(mae(cover["actual"], cover["q50"]), 4),
            "q95_coverage": round(float((cover["actual"] <= cover["q95"]).mean()), 4),
        }
    )

    horizons_df = pd.concat(horizon_frames, ignore_index=True)
    horizons_path = out / "step3c_horizon_forecasts.csv"
    horizons_df.to_csv(horizons_path, index=False)
    cover_path = out / "step3c_cover_forecasts.csv"
    cover.to_csv(cover_path, index=False)

    summary = pd.DataFrame(rows)
    summary_csv = out / "step3c_horizon_metrics.csv"
    summary.to_csv(summary_csv, index=False)

    payload = {
        "method": "direct multi-horizon quantile regression (one model per target)",
        "why_direct": (
            "A recursive forecaster feeds its own predictions back as inputs, so its "
            "errors compound with each step. Direct models never see their own output."
        ),
        "horizons": list(horizons),
        "cover_weeks": cover_weeks,
        "lead_time_weeks": lead_time_weeks,
        "review_period_weeks": review_period_weeks,
        "quantiles": list(QUANTILES),
        "metrics": summary.to_dict(orient="records"),
        "q95_coverage_note": (
            "Share of test rows where actual <= q95. It should land near 0.95; well "
            "above means the upper bound is too cautious, well below means it is unsafe."
        ),
        "data_note": "DEV SYNTHETIC data — not Bhagyashree Medical sales.",
    }
    summary_json = out / "step3c_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\nAccuracy by target (WMAPE lower is better; coverage should be near 0.95):")
    print(summary[["target", "description", "global_wmape", "q95_coverage"]].to_string(index=False))
    return {
        "horizons": horizons_path,
        "cover": cover_path,
        "metrics": summary_csv,
        "json": summary_json,
        "table": summary,
    }
