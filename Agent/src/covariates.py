"""Synthetic Navi Mumbai environmental covariates for demand conditioning."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _aqi_category(pm25: float) -> str:
    # India NAAQS-style bands (approx) from PM2.5 µg/m³
    if pm25 <= 30:
        return "Good"
    if pm25 <= 60:
        return "Satisfactory"
    if pm25 <= 90:
        return "Moderate"
    if pm25 <= 120:
        return "Poor"
    if pm25 <= 250:
        return "Very Poor"
    return "Severe"


def generate_covariates(
    start: str = "2023-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Daily weather / AQI / public-health alert series for Navi Mumbai.

    Rain: monsoon Jun–Sep with heavy-rain events (>20 mm).
    PM2.5: elevated in winter Nov–Feb.
    Alerts: derived from lag rainfall and AQI thresholds.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    rows = []

    for d in dates:
        month = d.month
        is_monsoon = month in (6, 7, 8, 9)
        is_winter = month in (11, 12, 1, 2)

        if is_monsoon:
            # Mixture: many wet days, occasional heavy dumps
            if rng.random() < 0.55:
                rain = float(rng.gamma(2.2, 8.0))  # often 10–30+ mm
            else:
                rain = float(rng.exponential(2.0))
            if rng.random() < 0.08:
                rain += float(rng.uniform(25, 80))  # extreme event
        elif month in (5, 10):
            rain = float(rng.exponential(3.0)) if rng.random() < 0.25 else 0.0
        else:
            rain = float(rng.exponential(1.5)) if rng.random() < 0.08 else 0.0

        if is_winter:
            pm25 = float(rng.normal(95, 28))
        elif is_monsoon:
            pm25 = float(rng.normal(35, 12))
        else:
            pm25 = float(rng.normal(55, 18))
        pm25 = float(np.clip(pm25, 8, 320))

        rows.append(
            {
                "date": d.normalize(),
                "rain_mm": round(rain, 2),
                "pm25": round(pm25, 1),
                "month": month,
                "is_monsoon": is_monsoon,
                "is_winter": is_winter,
            }
        )

    cov = pd.DataFrame(rows)
    cov["rain_cum_7d"] = cov["rain_mm"].rolling(7, min_periods=1).sum().round(2)
    cov["rain_cum_14d"] = cov["rain_mm"].rolling(14, min_periods=1).sum().round(2)
    # Lagged heavy-rain indicators (1–2 week lag for vector-borne signal)
    heavy = (cov["rain_mm"] > 20).astype(int)
    cov["rain_gt20_lag7"] = heavy.shift(7, fill_value=0).astype(int)
    cov["rain_gt20_lag14"] = heavy.shift(14, fill_value=0).astype(int)
    # Cumulative lag windows used by demand model
    cov["rain_cum_lag7_7d"] = cov["rain_cum_7d"].shift(7, fill_value=0)
    cov["rain_cum_lag14_7d"] = cov["rain_cum_7d"].shift(14, fill_value=0)

    cov["aqi_category"] = cov["pm25"].map(_aqi_category)
    cov["high_pm25"] = (cov["pm25"] >= 90).astype(int)

    # Public health alerts (synthetic, threshold-driven)
    cov["alert_leptospirosis"] = (
        (cov["rain_cum_lag7_7d"] > 40) | (cov["rain_gt20_lag7"] == 1)
    ).astype(int)
    cov["alert_dengue"] = (
        (cov["rain_cum_lag14_7d"] > 60) & cov["is_monsoon"]
    ).astype(int)
    cov["alert_air_quality"] = (cov["pm25"] >= 120).astype(int)
    cov["health_alert_flag"] = (
        (cov["alert_leptospirosis"] + cov["alert_dengue"] + cov["alert_air_quality"]) > 0
    ).astype(int)

    return cov
