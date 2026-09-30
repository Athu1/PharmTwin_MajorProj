"""Generate intermittent pharmacy sales + FEFO batches conditioned on covariates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from .catalog import load_catalog, sample_assortment
from .covariates import generate_covariates

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"


def _sku_base_params(assortment: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Per-SKU intermittent demand priors (probability + size)."""
    n = len(assortment)
    p_base = rng.beta(1.2, 18.0, size=n)
    cohort = assortment["demand_cohort"].to_numpy()
    p_base = np.where(cohort == "respiratory", np.clip(p_base * 1.8, 0.01, 0.45), p_base)
    p_base = np.where(cohort == "vector_borne", np.clip(p_base * 1.4, 0.01, 0.35), p_base)
    tc = assortment["Therapeutic Class"].to_numpy()
    for hot in ("RESPIRATORY", "ANTI INFECTIVES", "GASTRO INTESTINAL", "PAIN ANALGESICS"):
        p_base = np.where(tc == hot, np.clip(p_base * 1.25, 0.01, 0.5), p_base)

    size_mean = rng.uniform(1.0, 3.5, size=n)
    size_mean = np.where(
        assortment["price_inr"].to_numpy() > 500,
        np.clip(size_mean * 0.7, 1.0, 2.5),
        size_mean,
    )

    out = assortment[["sku_id", "name", "price_inr", "demand_cohort", "Therapeutic Class"]].copy()
    out["p_base"] = p_base
    out["size_mean"] = size_mean
    out["lead_time_days"] = rng.integers(2, 8, size=n)
    return out.reset_index(drop=True)


def _cohort_multiplier_arrays(cov: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Precompute daily (p_mult, size_mult) vectors per demand cohort."""
    n = len(cov)
    rain7 = cov["rain_gt20_lag7"].to_numpy(dtype=bool)
    rain14 = cov["rain_gt20_lag14"].to_numpy(dtype=bool)
    lept = cov["alert_leptospirosis"].to_numpy(dtype=bool)
    dengue = cov["alert_dengue"].to_numpy(dtype=bool)
    rain_cum = cov["rain_cum_lag7_7d"].to_numpy(dtype=float)
    high_pm = cov["high_pm25"].to_numpy(dtype=bool)
    aq_alert = cov["alert_air_quality"].to_numpy(dtype=bool)
    winter = cov["is_winter"].to_numpy(dtype=bool)
    monsoon = cov["is_monsoon"].to_numpy(dtype=bool)
    health = cov["health_alert_flag"].to_numpy(dtype=bool)
    pm25 = cov["pm25"].to_numpy(dtype=float)

    # vector_borne
    vb_p = np.ones(n)
    vb_s = np.ones(n)
    heavy = rain7 | rain14
    vb_p = np.where(heavy, vb_p * 1.9, vb_p)
    vb_s = np.where(heavy, vb_s * 1.35, vb_s)
    vb_p = np.where(lept, vb_p * 1.4, vb_p)
    vb_s = np.where(lept, vb_s * 1.2, vb_s)
    vb_p = np.where(dengue, vb_p * 1.5, vb_p)
    vb_s = np.where(dengue, vb_s * 1.25, vb_s)
    vb_p = np.where(rain_cum > 20, vb_p * 1.15, vb_p)

    # respiratory
    re_p = np.ones(n)
    re_s = np.ones(n)
    re_p = np.where(high_pm, re_p * 2.1, re_p)
    re_s = np.where(high_pm, re_s * 1.4, re_s)
    re_p = np.where(aq_alert, re_p * 1.5, re_p)
    re_s = np.where(aq_alert, re_s * 1.25, re_s)
    re_p = np.where(winter, re_p * 1.35, re_p)
    re_s = np.where(winter, re_s * 1.15, re_s)
    pm_boost = np.clip(1.0 + (pm25 - 60) / 100.0, 1.0, 1.8)
    re_p = np.where(pm25 >= 60, re_p * pm_boost, re_p)

    # other / general
    ot_p = np.ones(n)
    ot_s = np.ones(n)
    ot_p = np.where(monsoon, ot_p * 1.05, ot_p)
    ot_p = np.where(winter, ot_p * 1.08, ot_p)
    ot_p = np.where(health, ot_p * 1.05, ot_p)

    return {
        "vector_borne": (vb_p, vb_s),
        "respiratory": (re_p, re_s),
        "other": (ot_p, ot_s),
    }


def _fefo_allocate(
    batch_records: list[dict],
    batch_idxs: list[int],
    sale_date: pd.Timestamp,
    qty: int,
) -> tuple[int, int, list[str]]:
    """Allocate qty FEFO; returns (sold, unmet, batch_ids)."""
    remaining = qty
    allocated: list[str] = []
    ordered = sorted(batch_idxs, key=lambda i: batch_records[i]["expiry_date"])
    for bi in ordered:
        b = batch_records[bi]
        if b["receipt_date"] > sale_date or b["expiry_date"] < sale_date or b["qty_remaining"] <= 0:
            continue
        take = min(remaining, b["qty_remaining"])
        b["qty_remaining"] -= take
        remaining -= take
        allocated.append(b["batch_id"])
        if remaining == 0:
            break
    sold = qty - remaining
    return sold, remaining, allocated


def generate_sales_and_batches(
    assortment: pd.DataFrame,
    covariates: pd.DataFrame,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Demand-event sales (sparse) + batch ledger with FEFO-friendly expiry dates.

    Zero-sale days are omitted; rebuild dense series via calendar merge when forecasting.
    """
    rng = np.random.default_rng(seed)
    params = _sku_base_params(assortment, rng)
    cov = covariates.copy()
    cov["date"] = pd.to_datetime(cov["date"]).dt.normalize()
    dates = cov["date"].to_numpy()
    n_days = len(cov)
    mid_idx = n_days // 2
    mid_date = cov["date"].iloc[mid_idx]
    weekday = cov["date"].dt.weekday.to_numpy()

    mults = _cohort_multiplier_arrays(cov)
    # Map unknown cohorts to "other"
    for key in list(params["demand_cohort"].unique()):
        if key not in mults:
            mults[key] = mults["other"]

    rain_lag7 = cov["rain_cum_lag7_7d"].to_numpy()
    rain_gt7 = cov["rain_gt20_lag7"].to_numpy()
    rain_gt14 = cov["rain_gt20_lag14"].to_numpy()
    pm25 = cov["pm25"].to_numpy()
    aqi = cov["aqi_category"].to_numpy()
    alert = cov["health_alert_flag"].to_numpy()

    sales_records: list[dict] = []
    batch_records: list[dict] = []
    batch_seq = 0
    start_date = cov["date"].iloc[0]

    batches_by_sku: dict[int, list[int]] = {}
    for sku in params.itertuples(index=False):
        for wave in range(3):
            batch_seq += 1
            mfg = start_date - pd.Timedelta(days=int(rng.integers(30, 180)))
            expiry = mfg + pd.Timedelta(days=int(rng.integers(180, 720)))
            qty_in = int(rng.integers(40, 220))
            batch_records.append(
                {
                    "batch_id": f"B{batch_seq:07d}",
                    "sku_id": int(sku.sku_id),
                    "receipt_date": start_date + pd.Timedelta(days=wave * 120),
                    "mfg_date": mfg,
                    "expiry_date": expiry,
                    "qty_received": qty_in,
                    "qty_remaining": qty_in,
                    "unit_cost": round(float(sku.price_inr) * 0.72, 2),
                }
            )
            batches_by_sku.setdefault(int(sku.sku_id), []).append(len(batch_records) - 1)

    for sku in tqdm(params.itertuples(index=False), total=len(params), desc="Simulating SKUs"):
        sku_id = int(sku.sku_id)
        cohort = str(sku.demand_cohort)
        p_m, s_m = mults.get(cohort, mults["other"])
        p = np.minimum(0.85, float(sku.p_base) * p_m)
        if cohort == "respiratory":
            # mild weekend OTC uplift on probability
            p = np.where(weekday >= 5, np.minimum(0.9, p * 1.1), p)

        occur = rng.random(n_days) < p
        if not occur.any():
            continue

        day_idx = np.flatnonzero(occur)
        lam = float(sku.size_mean) * s_m[day_idx]
        qtys = np.maximum(1, rng.poisson(lam)).astype(int)
        if cohort == "respiratory":
            weekend_hits = weekday[day_idx] >= 5
            qtys[weekend_hits] += rng.integers(0, 2, size=int(weekend_hits.sum()))

        batch_idxs = batches_by_sku.get(sku_id, [])
        replenished = False
        price = float(sku.price_inr)

        for di, qty in zip(day_idx, qtys):
            sale_date = pd.Timestamp(dates[di])
            on_hand = sum(batch_records[i]["qty_remaining"] for i in batch_idxs)
            if not replenished and di >= mid_idx and on_hand < 25:
                batch_seq += 1
                mfg = mid_date - pd.Timedelta(days=int(rng.integers(10, 60)))
                expiry = mfg + pd.Timedelta(days=int(rng.integers(180, 540)))
                qty_in = int(rng.integers(60, 180))
                batch_records.append(
                    {
                        "batch_id": f"B{batch_seq:07d}",
                        "sku_id": sku_id,
                        "receipt_date": mid_date,
                        "mfg_date": mfg,
                        "expiry_date": expiry,
                        "qty_received": qty_in,
                        "qty_remaining": qty_in,
                        "unit_cost": round(price * 0.72, 2),
                    }
                )
                batch_idxs.append(len(batch_records) - 1)
                batches_by_sku[sku_id] = batch_idxs
                replenished = True

            sold, unmet, allocated = _fefo_allocate(batch_records, batch_idxs, sale_date, int(qty))
            sales_records.append(
                {
                    "date": sale_date,
                    "sku_id": sku_id,
                    "qty": sold,
                    "unmet_qty": unmet if sold > 0 else int(qty),
                    "unit_price": price,
                    "revenue": round(sold * price, 2),
                    "batch_ids": "|".join(allocated),
                    "stockout": int(sold < int(qty)),
                    "rain_mm_lag7_proxy": float(rain_lag7[di]),
                    "rain_gt20_lag7": int(rain_gt7[di]),
                    "rain_gt20_lag14": int(rain_gt14[di]),
                    "pm25": float(pm25[di]),
                    "aqi_category": str(aqi[di]),
                    "health_alert_flag": int(alert[di]),
                }
            )

    sales = pd.DataFrame(sales_records)
    batches = pd.DataFrame(batch_records)
    if len(sales):
        sales = sales.sort_values(["date", "sku_id"]).reset_index(drop=True)
    return sales, batches


def run_step1(
    catalog_path: str | Path | None = None,
    n_skus: int = 3000,
    start: str = "2023-01-01",
    end: str = "2024-12-31",
    seed: int = 42,
    out_dir: Path | str | None = None,
) -> dict[str, Path]:
    """End-to-end Step 1: catalog sample + covariates + sales + batches."""
    out = Path(out_dir) if out_dir else DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Loading catalog...")
    catalog = load_catalog(catalog_path) if catalog_path else load_catalog()
    catalog_deduped_path = out / "catalog_deduped.parquet"
    catalog.to_parquet(catalog_deduped_path, index=False)
    print(f"  Deduped catalog: {len(catalog):,} SKUs -> {catalog_deduped_path}")

    print(f"Sampling assortment (n={n_skus})...")
    assortment = sample_assortment(catalog, n_skus=n_skus, seed=seed)
    assortment_path = out / "assortment_3k.csv"
    assortment.to_csv(assortment_path, index=False)
    assortment.to_parquet(out / "assortment_3k.parquet", index=False)
    print(f"  Assortment cohorts:\n{assortment['demand_cohort'].value_counts().head(12)}")

    print(f"Generating covariates {start} -> {end}...")
    cov = generate_covariates(start=start, end=end, seed=seed)
    cov_path = out / "covariates_navi_mumbai.csv"
    cov.to_csv(cov_path, index=False)
    print(
        f"  Days: {len(cov):,} | heavy-rain days: {(cov['rain_mm'] > 20).sum()} | "
        f"health-alert days: {cov['health_alert_flag'].sum()}"
    )

    print("Simulating intermittent sales + FEFO batches...")
    sales, batches = generate_sales_and_batches(assortment, cov, seed=seed)
    sales_path = out / "transactions_synthetic.csv"
    batches_path = out / "batches_fefo.csv"
    sales.to_csv(sales_path, index=False)
    batches.to_csv(batches_path, index=False)
    sales.to_parquet(out / "transactions_synthetic.parquet", index=False)
    batches.to_parquet(out / "batches_fefo.parquet", index=False)

    summary = {
        "n_catalog_deduped": int(len(catalog)),
        "n_assortment": int(len(assortment)),
        "n_days": int(len(cov)),
        "n_transactions": int(len(sales)),
        "n_units_sold": int(sales["qty"].sum()) if len(sales) else 0,
        "n_stockout_events": int(sales["stockout"].sum()) if len(sales) else 0,
        "n_batches": int(len(batches)),
        "total_revenue_inr": float(sales["revenue"].sum()) if len(sales) else 0.0,
        "date_start": start,
        "date_end": end,
        "seed": seed,
    }
    summary_path = out / "step1_summary.json"
    pd.Series(summary).to_json(summary_path, indent=2)
    print("Step 1 complete:", summary)
    return {
        "catalog_deduped": catalog_deduped_path,
        "assortment": assortment_path,
        "covariates": cov_path,
        "transactions": sales_path,
        "batches": batches_path,
        "summary": summary_path,
    }


if __name__ == "__main__":
    run_step1()
