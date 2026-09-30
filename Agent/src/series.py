"""Build dense demand time series from sparse synthetic transactions."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"


def load_demand_events(
    transactions_path: Path | str | None = None,
    use_unmet: bool = True,
) -> pd.DataFrame:
    path = Path(transactions_path) if transactions_path else DATA_DIR / "transactions_synthetic.parquet"
    if not path.exists():
        path = DATA_DIR / "transactions_synthetic.csv"
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    demand = df["qty"].astype(float)
    if use_unmet and "unmet_qty" in df.columns:
        demand = demand + df["unmet_qty"].astype(float)
    out = df.assign(demand=demand)[["date", "sku_id", "demand", "qty", "stockout"]].copy()
    return out


def to_weekly_demand(
    events: pd.DataFrame,
    sku_ids: list[int] | np.ndarray | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """
    Dense weekly demand panel: one row per (sku_id, week_start).

    Missing weeks are filled with 0 (true intermittent zeros).
    """
    df = events.copy()
    if sku_ids is not None:
        sku_ids = list(map(int, sku_ids))
        df = df[df["sku_id"].isin(sku_ids)]

    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    weekly = (
        df.groupby(["sku_id", "week_start"], as_index=False)["demand"]
        .sum()
    )

    if start is None:
        start = str(df["date"].min().date())
    if end is None:
        end = str(df["date"].max().date())

    all_weeks = pd.date_range(
        pd.Timestamp(start) - pd.Timedelta(days=pd.Timestamp(start).weekday()),
        pd.Timestamp(end),
        freq="W-MON",
    )
    # Normalize to Monday week_start
    all_weeks = pd.DatetimeIndex([w.normalize() for w in all_weeks])

    skus = sorted(df["sku_id"].unique()) if sku_ids is None else sorted(sku_ids)
    idx = pd.MultiIndex.from_product([skus, all_weeks], names=["sku_id", "week_start"])
    panel = (
        weekly.set_index(["sku_id", "week_start"])
        .reindex(idx, fill_value=0.0)
        .reset_index()
    )
    panel["demand"] = panel["demand"].astype(float)
    return panel


def zero_inflation_stats(panel: pd.DataFrame) -> dict:
    y = panel["demand"].to_numpy()
    return {
        "n_rows": int(len(y)),
        "pct_zero": float(np.mean(y == 0) * 100),
        "mean_demand": float(np.mean(y)),
        "mean_nonzero": float(np.mean(y[y > 0])) if np.any(y > 0) else 0.0,
        "n_skus": int(panel["sku_id"].nunique()),
        "n_weeks": int(panel["week_start"].nunique()),
    }
