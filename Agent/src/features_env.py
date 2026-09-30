"""Weekly feature matrix: demand lags + Navi Mumbai environmental covariates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .series import DATA_DIR, load_demand_events, to_weekly_demand

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_covariates(path: Path | str | None = None) -> pd.DataFrame:
    path = Path(path) if path else DATA_DIR / "covariates_navi_mumbai.csv"
    cov = pd.read_csv(path, parse_dates=["date"])
    cov["date"] = pd.to_datetime(cov["date"]).dt.normalize()
    return cov


def aggregate_covariates_weekly(cov: pd.DataFrame) -> pd.DataFrame:
    """Collapse daily env series to Monday-start weeks."""
    c = cov.copy()
    c["week_start"] = c["date"] - pd.to_timedelta(c["date"].dt.weekday, unit="D")
    agg = c.groupby("week_start", as_index=False).agg(
        rain_mm_sum=("rain_mm", "sum"),
        rain_mm_max=("rain_mm", "max"),
        rain_cum_7d_mean=("rain_cum_7d", "mean"),
        rain_cum_14d_mean=("rain_cum_14d", "mean"),
        rain_gt20_lag7_any=("rain_gt20_lag7", "max"),
        rain_gt20_lag14_any=("rain_gt20_lag14", "max"),
        rain_cum_lag7_mean=("rain_cum_lag7_7d", "mean"),
        rain_cum_lag14_mean=("rain_cum_lag14_7d", "mean"),
        pm25_mean=("pm25", "mean"),
        pm25_max=("pm25", "max"),
        high_pm25_days=("high_pm25", "sum"),
        alert_leptospirosis_any=("alert_leptospirosis", "max"),
        alert_dengue_any=("alert_dengue", "max"),
        alert_air_quality_any=("alert_air_quality", "max"),
        health_alert_any=("health_alert_flag", "max"),
        is_monsoon=("is_monsoon", "max"),
        is_winter=("is_winter", "max"),
        month=("month", "first"),
    )
    agg["rain_gt20_week"] = (agg["rain_mm_max"] > 20).astype(int)
    return agg


def _add_demand_lags(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["sku_id", "week_start"]).copy()
    g = panel.groupby("sku_id", sort=False)["demand"]
    panel["demand_lag1"] = g.shift(1)
    panel["demand_lag2"] = g.shift(2)
    panel["demand_lag4"] = g.shift(4)
    panel["demand_roll4"] = g.transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    panel["demand_roll8"] = g.transform(lambda s: s.shift(1).rolling(8, min_periods=1).mean())
    # Weeks since last positive demand (capped)
    def _weeks_since(s: pd.Series) -> pd.Series:
        out = np.zeros(len(s), dtype=float)
        last = -999
        vals = s.to_numpy()
        for i, v in enumerate(vals):
            if i == 0:
                out[i] = 99.0
            else:
                out[i] = min(i - last, 99) if last >= 0 else 99.0
            if v > 0:
                last = i
        # shift so feature at t uses history through t-1
        return pd.Series(out, index=s.index).shift(1)

    panel["weeks_since_demand"] = panel.groupby("sku_id", sort=False)["demand"].transform(_weeks_since)
    return panel


ENV_FEATURES = [
    "rain_mm_sum",
    "rain_mm_max",
    "rain_cum_7d_mean",
    "rain_cum_14d_mean",
    "rain_gt20_lag7_any",
    "rain_gt20_lag14_any",
    "rain_cum_lag7_mean",
    "rain_cum_lag14_mean",
    "pm25_mean",
    "pm25_max",
    "high_pm25_days",
    "alert_leptospirosis_any",
    "alert_dengue_any",
    "alert_air_quality_any",
    "health_alert_any",
    "is_monsoon",
    "is_winter",
    "rain_gt20_week",
]

LAG_FEATURES = [
    "demand_lag1",
    "demand_lag2",
    "demand_lag4",
    "demand_roll4",
    "demand_roll8",
    "weeks_since_demand",
]

STATIC_FEATURES = [
    "price_log",
    "cohort_code",
    "theraclass_code",
    "month",
    "weekofyear",
]


def build_feature_panel(
    assortment_path: Path | str | None = None,
    covariates_path: Path | str | None = None,
    max_skus: int | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Dense weekly panel with target `demand`, lag features, env covariates, SKU encodings.
    """
    events = load_demand_events(use_unmet=True)
    assortment = pd.read_csv(assortment_path or DATA_DIR / "assortment_3k.csv")
    sku_ids = assortment["sku_id"].astype(int).tolist()
    if max_skus is not None:
        rng = np.random.default_rng(seed)
        sku_ids = list(rng.choice(sku_ids, size=min(max_skus, len(sku_ids)), replace=False))
        assortment = assortment[assortment["sku_id"].isin(sku_ids)]

    panel = to_weekly_demand(events, sku_ids=sku_ids)
    panel = _add_demand_lags(panel)

    cov_w = aggregate_covariates_weekly(load_covariates(covariates_path))
    panel = panel.merge(cov_w, on="week_start", how="left")

    meta = assortment[
        ["sku_id", "price_inr", "demand_cohort", "Therapeutic Class"]
    ].copy()
    meta["sku_id"] = meta["sku_id"].astype(int)
    meta["price_log"] = np.log1p(meta["price_inr"].astype(float))
    meta["cohort_code"] = meta["demand_cohort"].astype("category").cat.codes.astype(int)
    meta["theraclass_code"] = (
        meta["Therapeutic Class"].fillna("UNKNOWN").astype("category").cat.codes.astype(int)
    )
    panel = panel.merge(
        meta[["sku_id", "price_log", "cohort_code", "theraclass_code", "demand_cohort"]],
        on="sku_id",
        how="left",
    )

    panel["weekofyear"] = panel["week_start"].dt.isocalendar().week.astype(int)
    panel["month"] = panel["month"].fillna(panel["week_start"].dt.month).astype(int)

    # Fill lag NaNs after shift
    for col in LAG_FEATURES:
        panel[col] = panel[col].fillna(0.0)
    for col in ENV_FEATURES:
        if col in panel.columns:
            panel[col] = panel[col].fillna(0.0)

    panel["demand"] = panel["demand"].astype(float)
    return panel.reset_index(drop=True)


def feature_columns(include_env: bool = True) -> list[str]:
    cols = list(LAG_FEATURES) + list(STATIC_FEATURES)
    if include_env:
        cols = cols + list(ENV_FEATURES)
    return cols
