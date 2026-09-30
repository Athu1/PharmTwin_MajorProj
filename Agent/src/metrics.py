"""Forecast accuracy metrics for intermittent demand (no MAPE)."""

from __future__ import annotations

import numpy as np


def wmape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Weighted MAPE: sum(|e|) / sum(|y|). Safe with zero-sale periods."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.sum(np.abs(y_true))
    if denom <= 0:
        return float("nan")
    return float(np.sum(np.abs(y_true - y_pred)) / denom)


def mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
    seasonality: int = 1,
) -> float:
    """
    Mean Absolute Scaled Error.

    Scale = MAE of seasonal naive on training data (seasonality=1 → one-step naive).
    Never uses MAPE (undefined on zero-demand days).
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    y_train = np.asarray(y_train, dtype=float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    if len(y_train) <= seasonality:
        return float("nan")
    scale = float(np.mean(np.abs(y_train[seasonality:] - y_train[:-seasonality])))
    if scale <= 1e-12:
        # Flat / all-zero train series — undefined MASE
        return float("nan")
    return mae / scale


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))
