"""Intermittent demand forecasting: Croston, SBA, TSB (+ moving-average baseline)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class IntermittentState:
    method: str
    z: float  # smoothed demand size
    p: float  # smoothed interval (Croston/SBA) or unused
    pi: float  # demand probability (TSB)
    forecast: float
    periods_since_demand: int
    alpha: float
    beta: float


def fit_croston(y: np.ndarray, alpha: float = 0.1) -> IntermittentState:
    """Classic Croston — separate size (z) and interval (p); update only on demand."""
    y = np.asarray(y, dtype=float)
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0:
        return IntermittentState("croston", 0.0, float(max(len(y), 1)), 0.0, 0.0, len(y), alpha, alpha)

    first = int(nz[0])
    z = float(y[first])
    p = float(first + 1)
    since = 0
    for val in y[first + 1 :]:
        since += 1
        if val > 0:
            z = z + alpha * (val - z)
            p = p + alpha * (since - p)
            since = 0
    # periods since last demand through end of series
    if len(y) > first:
        trailing_zeros = 0
        for val in y[::-1]:
            if val > 0:
                break
            trailing_zeros += 1
        since = trailing_zeros
    fc = z / p if p > 0 else 0.0
    return IntermittentState("croston", z, p, z / p if p else 0.0, fc, since, alpha, alpha)


def fit_sba(y: np.ndarray, alpha: float = 0.1) -> IntermittentState:
    """Syntetos-Boylan Approximation — corrects Croston upward bias."""
    st = fit_croston(y, alpha=alpha)
    fc = (1.0 - alpha / 2.0) * (st.z / st.p) if st.p > 0 else 0.0
    return IntermittentState("sba", st.z, st.p, st.pi, fc, st.periods_since_demand, alpha, alpha)


def fit_tsb(y: np.ndarray, alpha: float = 0.1, beta: float = 0.1) -> IntermittentState:
    """Teunter-Syntetos-Babai — updates demand probability every period."""
    y = np.asarray(y, dtype=float)
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0:
        return IntermittentState("tsb", 0.0, 1e9, 0.0, 0.0, len(y), alpha, beta)

    first = int(nz[0])
    z = float(y[first])
    # initialize probability from occurrence rate up to first demand, then update online
    pi = 1.0 / float(first + 1)
    since = 0
    for val in y[first + 1 :]:
        since += 1
        demand_event = 1.0 if val > 0 else 0.0
        pi = pi + beta * (demand_event - pi)
        if val > 0:
            z = z + alpha * (val - z)
            since = 0
    trailing = 0
    for val in y[::-1]:
        if val > 0:
            break
        trailing += 1
    fc = pi * z
    return IntermittentState("tsb", z, 1.0 / pi if pi > 0 else 1e9, pi, fc, trailing, alpha, beta)


def update_state(state: IntermittentState, observation: float) -> IntermittentState:
    """Online update with one new observation; returns refreshed forecast."""
    alpha, beta = state.alpha, state.beta
    z, p, pi = state.z, state.p, state.pi
    since = state.periods_since_demand + 1
    val = float(observation)

    if state.method in ("croston", "sba"):
        if val > 0:
            z = z + alpha * (val - z)
            p = p + alpha * (since - p)
            since = 0
        raw = z / p if p > 0 else 0.0
        fc = (1.0 - alpha / 2.0) * raw if state.method == "sba" else raw
        return IntermittentState(state.method, z, p, raw, fc, since, alpha, beta)

    # TSB
    demand_event = 1.0 if val > 0 else 0.0
    pi = pi + beta * (demand_event - pi)
    if val > 0:
        z = z + alpha * (val - z)
        since = 0
    fc = pi * z
    return IntermittentState("tsb", z, 1.0 / pi if pi > 0 else p, pi, fc, since, alpha, beta)


def moving_average_forecast(y_train: np.ndarray, window: int = 8) -> float:
    """Simple MA baseline — chronically over-forecasts intermittent series."""
    y = np.asarray(y_train, dtype=float)
    if len(y) == 0:
        return 0.0
    w = min(window, len(y))
    return float(np.mean(y[-w:]))


def fit_method(y: np.ndarray, method: str, alpha: float = 0.1, beta: float = 0.1) -> IntermittentState | float:
    method = method.lower()
    if method == "croston":
        return fit_croston(y, alpha=alpha)
    if method == "sba":
        return fit_sba(y, alpha=alpha)
    if method == "tsb":
        return fit_tsb(y, alpha=alpha, beta=beta)
    if method in ("ma", "moving_average"):
        return moving_average_forecast(y)
    raise ValueError(f"Unknown method: {method}")


def rolling_forecast(
    y: np.ndarray,
    method: str,
    train_size: int,
    alpha: float = 0.1,
    beta: float = 0.1,
    ma_window: int = 8,
) -> np.ndarray:
    """
    One-step-ahead rolling forecasts for y[train_size:].

    Intermittent methods update online after each observation.
    MA uses trailing window of observed history.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if train_size >= n:
        return np.array([])

    preds = np.zeros(n - train_size)
    if method.lower() in ("ma", "moving_average"):
        for i, t in enumerate(range(train_size, n)):
            preds[i] = moving_average_forecast(y[:t], window=ma_window)
        return preds

    state = fit_method(y[:train_size], method, alpha=alpha, beta=beta)
    assert isinstance(state, IntermittentState)
    for i, t in enumerate(range(train_size, n)):
        preds[i] = state.forecast
        state = update_state(state, y[t])
    return preds
