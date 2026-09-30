"""Probabilistic safety stock from forecast distributions / quantile spreads."""

from __future__ import annotations

import numpy as np
import pandas as pd

# Standard normal quantiles (avoid scipy dependency)
_Z = {0.90: 1.28155156554, 0.95: 1.64485362695, 0.975: 1.95996398454, 0.99: 2.32634787404}


def z_from_service_level(service_level: float) -> float:
    """Normal z-score for cycle-service level (e.g. 0.95 → ~1.645)."""
    if service_level in _Z:
        return _Z[service_level]
    # linear interp on known knots
    keys = sorted(_Z)
    if service_level <= keys[0]:
        return _Z[keys[0]]
    if service_level >= keys[-1]:
        return _Z[keys[-1]]
    for a, b in zip(keys, keys[1:]):
        if a <= service_level <= b:
            t = (service_level - a) / (b - a)
            return _Z[a] + t * (_Z[b] - _Z[a])
    return 1.64485362695


def sigma_from_quantiles(q50: np.ndarray, q90: np.ndarray, q95: np.ndarray | None = None) -> np.ndarray:
    """
    Approximate demand SD from LightGBM quantile forecasts.

    Prefer (q95 - q50) / z_0.95; blend with (q90 - q50) / z_0.90.
    """
    q50 = np.asarray(q50, dtype=float)
    q90 = np.asarray(q90, dtype=float)
    sig90 = np.maximum(q90 - q50, 0.0) / _Z[0.90]
    if q95 is None:
        return sig90
    q95 = np.asarray(q95, dtype=float)
    sig95 = np.maximum(q95 - q50, 0.0) / _Z[0.95]
    return np.where(np.isfinite(sig95), 0.6 * sig95 + 0.4 * sig90, sig90)


def safety_stock(
    sigma_lt: float | np.ndarray,
    lead_time: float,
    review_period: float,
    service_level: float = 0.95,
) -> float | np.ndarray:
    """
    SS = Z × σ_LT × √(L + R)

    L = lead time, R = review period (same time unit as σ_LT, e.g. weeks).
    """
    z = z_from_service_level(service_level)
    return z * np.asarray(sigma_lt, dtype=float) * np.sqrt(lead_time + review_period)


def reorder_point(
    mean_demand: float | np.ndarray,
    sigma_lt: float | np.ndarray,
    lead_time: float,
    review_period: float,
    service_level: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    """ROP = μ(L+R) + SS. Returns (rop, ss)."""
    cover = lead_time + review_period
    ss = np.asarray(safety_stock(sigma_lt, lead_time, review_period, service_level), dtype=float)
    rop = np.asarray(mean_demand, dtype=float) * cover + ss
    return rop, ss


def sku_stock_params_from_forecasts(
    forecasts: pd.DataFrame,
    lead_time: float = 1.0,
    review_period: float = 1.0,
    service_level: float = 0.95,
) -> pd.DataFrame:
    """
    Aggregate Step-3 weekly quantile forecasts to per-SKU inventory parameters.

    Expects columns: sku_id, q50, q90, q95.
    """
    g = forecasts.groupby("sku_id", as_index=False).agg(
        mu_weekly=("q50", "mean"),
        q50_mean=("q50", "mean"),
        q90_mean=("q90", "mean"),
        q95_mean=("q95", "mean"),
        n_weeks=("q50", "size"),
    )
    g["sigma_weekly"] = sigma_from_quantiles(
        g["q50_mean"].to_numpy(),
        g["q90_mean"].to_numpy(),
        g["q95_mean"].to_numpy(),
    )
    g["sigma_weekly"] = np.maximum(g["sigma_weekly"], 0.15 * np.maximum(g["mu_weekly"], 0.5))
    rop, ss = reorder_point(
        g["mu_weekly"].to_numpy(),
        g["sigma_weekly"].to_numpy(),
        lead_time=lead_time,
        review_period=review_period,
        service_level=service_level,
    )
    g["lead_time_weeks"] = lead_time
    g["review_period_weeks"] = review_period
    g["service_level"] = service_level
    g["z_score"] = z_from_service_level(service_level)
    g["safety_stock"] = ss
    g["reorder_point"] = rop
    g["order_up_to"] = rop + np.maximum(g["mu_weekly"] * lead_time, 1.0)
    return g
