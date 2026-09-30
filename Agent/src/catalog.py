"""Load, dedupe, and stratified-sample the India medicines catalog."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CATALOG_PATH = Path(
    r"e:\MajorProject_4th_Yr\Data\A-Z medicines 2.5L+"
    r"\Extensive_A_Z_medicines_dataset_of_India.csv"
)

# Keyword tags for environmental demand cohorts
VECTOR_BORNE_RE = re.compile(
    r"leptospir|dengue|malaria|chikungunya|ors|oral rehydration|"
    r"doxycycline|ceftriaxone|platelet|mosquito|typhoid|fever",
    re.I,
)
RESPIRATORY_RE = re.compile(
    r"asthma|allergic rhinitis|sneezing|runny nose|cough|respirat|"
    r"montelukast|fexofenadine|levocetirizine|salbutamol|budesonide|"
    r"inhaler|antihistamin|bronch",
    re.I,
)


def _coerce_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
        .fillna(False)
    )


def _tag_cohort(row: pd.Series) -> str:
    blob = " ".join(
        str(row.get(c, "") or "")
        for c in (
            "Therapeutic Class",
            "use0",
            "use1",
            "use2",
            "short_composition1",
            "short_composition2",
            "name",
        )
    )
    if VECTOR_BORNE_RE.search(blob):
        return "vector_borne"
    if row.get("Therapeutic Class") == "RESPIRATORY" or RESPIRATORY_RE.search(blob):
        return "respiratory"
    tc = str(row.get("Therapeutic Class") or "").strip()
    return tc if tc else "other"


def load_catalog(path: Path | str = DEFAULT_CATALOG_PATH) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    price_col = "price(₹)" if "price(₹)" in df.columns else "price"
    if price_col != "price(₹)" and "price" not in df.columns:
        raise KeyError("Expected price(₹) column in catalog")
    df["price_inr"] = pd.to_numeric(df[price_col], errors="coerce")
    df["Is_discontinued"] = _coerce_bool(df["Is_discontinued"])
    df["Habit Forming"] = (
        df["Habit Forming"].astype(str).str.strip().str.lower().eq("yes")
        if "Habit Forming" in df.columns
        else False
    )
    # Deduplicate: keep first row per id (catalog has duplicate ids)
    df = df.sort_values("id").drop_duplicates(subset=["id"], keep="first")
    df["sku_id"] = df["id"].astype(int)
    for col in (
        "short_composition1",
        "short_composition2",
        "Chemical Class",
        "Therapeutic Class",
        "Action Class",
        "name",
        "manufacturer_name",
        "pack_size_label",
        "type",
    ):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    for i in range(5):
        for prefix in ("substitute", "use"):
            col = f"{prefix}{i}"
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
    df["demand_cohort"] = df.apply(_tag_cohort, axis=1)
    df["is_active"] = ~df["Is_discontinued"] & df["price_inr"].notna() & (df["price_inr"] > 0)
    return df.reset_index(drop=True)


def sample_assortment(
    catalog: pd.DataFrame,
    n_skus: int = 3000,
    seed: int = 42,
    active_only: bool = True,
) -> pd.DataFrame:
    """Stratified sample by Therapeutic Class for a realistic retail assortment."""
    rng = np.random.default_rng(seed)
    pool = catalog[catalog["is_active"]].copy() if active_only else catalog.copy()
    if len(pool) <= n_skus:
        return pool.reset_index(drop=True)

    # Ensure environmental cohorts are represented
    must_include = []
    for cohort, n in (("vector_borne", 200), ("respiratory", 400)):
        cohort_df = pool[pool["demand_cohort"] == cohort]
        take = min(n, len(cohort_df))
        if take:
            idx = rng.choice(cohort_df.index.to_numpy(), size=take, replace=False)
            must_include.append(pool.loc[idx])

    forced = pd.concat(must_include).drop_duplicates(subset=["sku_id"]) if must_include else pool.iloc[0:0]
    remaining_n = n_skus - len(forced)
    rest_pool = pool[~pool["sku_id"].isin(forced["sku_id"])]

    # Stratify remainder by Therapeutic Class
    classes = rest_pool["Therapeutic Class"].replace("", "UNKNOWN")
    strata = rest_pool.groupby(classes, group_keys=False)
    # Proportional allocation with at least 1 per class when possible
    sizes = strata.size()
    alloc = (sizes / sizes.sum() * remaining_n).round().astype(int).clip(lower=0)
    # Fix rounding drift
    drift = remaining_n - int(alloc.sum())
    if drift != 0 and len(alloc):
        order = alloc.sort_values(ascending=False).index
        for i in range(abs(drift)):
            key = order[i % len(order)]
            alloc[key] = max(0, alloc[key] + (1 if drift > 0 else -1))

    parts = [forced]
    for cls, k in alloc.items():
        if k <= 0:
            continue
        g = rest_pool[classes == cls]
        k = min(k, len(g))
        idx = rng.choice(g.index.to_numpy(), size=k, replace=False)
        parts.append(rest_pool.loc[idx])

    sample = pd.concat(parts).drop_duplicates(subset=["sku_id"])
    # Top up if short due to rounding
    if len(sample) < n_skus:
        need = n_skus - len(sample)
        leftover = rest_pool[~rest_pool["sku_id"].isin(sample["sku_id"])]
        if len(leftover):
            idx = rng.choice(leftover.index.to_numpy(), size=min(need, len(leftover)), replace=False)
            sample = pd.concat([sample, leftover.loc[idx]])

    return sample.sample(frac=1, random_state=seed).reset_index(drop=True).head(n_skus)


def composition_text(row: pd.Series) -> str:
    return " ".join(
        filter(
            None,
            [
                str(row.get("short_composition1", "") or ""),
                str(row.get("short_composition2", "") or ""),
                str(row.get("Chemical Class", "") or ""),
                str(row.get("Therapeutic Class", "") or ""),
            ],
        )
    )
