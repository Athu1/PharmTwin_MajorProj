"""Does the forecast-driven reorder point actually order better?

Runs the SAME FEFO simulation twice over the same weeks and the same opening stock,
changing only where the reorder point came from:

  old  one fixed level per medicine: the mean of every forecast week, inflated by
       sqrt(L+R)                            (Step 4, sku_stock_params_from_forecasts)
  new  a level that moves week by week, from a model trained on the L+R week total
                                            (Step 3c, cover_params_by_week)

The week-by-week part is the whole point. A static snapshot of the new model is also
reported, to show how much of any gain comes from the better target and how much from
letting the level move.

Everything else — policy, demand, batches, seed — is held fixed, so any difference in
fill rate or stock held is attributable to the reorder parameters alone.

  py -3 scripts/run_step3c.py          # must run first (writes the cover forecasts)
  py -3 scripts/run_reorder_compare.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.inventory_fefo import is_otc_sku  # noqa: E402
from src.run_inventory_sim import _init_states, _load_inputs, simulate_policy  # noqa: E402
from src.safety_stock import (  # noqa: E402
    cover_params_by_week,
    sku_params_from_cover_forecasts,
    sku_stock_params_from_forecasts,
)

DATA = ROOT / "data" / "processed"


def _attach_meta(params: pd.DataFrame, assortment: pd.DataFrame) -> pd.DataFrame:
    cols = ["sku_id", "name", "price_inr", "Therapeutic Class", "demand_cohort", "is_otc"]
    return params.merge(assortment[cols], on="sku_id", how="left")


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare old vs forecast-driven reorder points")
    ap.add_argument("--policy", default="fefo_ss", help="Policy to hold fixed (default fefo_ss)")
    ap.add_argument("--max-skus", type=int, default=None)
    ap.add_argument("--lead-time-weeks", type=float, default=1.0)
    ap.add_argument("--review-period-weeks", type=float, default=1.0)
    ap.add_argument("--service-level", type=float, default=0.95)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cover_path = DATA / "step3c_cover_forecasts.csv"
    if not cover_path.exists():
        raise SystemExit(
            "Missing step3c_cover_forecasts.csv — run scripts/run_step3c.py first."
        )

    assortment, batches, forecasts, weekly = _load_inputs(DATA)
    assortment["is_otc"] = assortment.apply(is_otc_sku, axis=1)
    cover = pd.read_csv(cover_path, parse_dates=["week_start"])

    if args.max_skus is not None:
        rng = np.random.default_rng(args.seed)
        keep = set(
            rng.choice(
                assortment["sku_id"].to_numpy(),
                size=min(args.max_skus, len(assortment)),
                replace=False,
            )
        )
        assortment = assortment[assortment["sku_id"].isin(keep)]
        batches = batches[batches["sku_id"].isin(keep)]
        forecasts = forecasts[forecasts["sku_id"].isin(keep)]
        weekly = weekly[weekly["sku_id"].isin(keep)]
        cover = cover[cover["sku_id"].isin(keep)]

    old = _attach_meta(
        sku_stock_params_from_forecasts(
            forecasts,
            lead_time=args.lead_time_weeks,
            review_period=args.review_period_weeks,
            service_level=args.service_level,
        ),
        assortment,
    )
    new = _attach_meta(
        sku_params_from_cover_forecasts(
            cover,
            lead_time=args.lead_time_weeks,
            review_period=args.review_period_weeks,
            service_level=args.service_level,
        ),
        assortment,
    )
    # Only medicines both methods can price, so the comparison is on identical SKUs
    shared = sorted(set(old["sku_id"]) & set(new["sku_id"]))
    old = old[old["sku_id"].isin(shared)]
    new = new[new["sku_id"].isin(shared)]
    print(f"Comparing on {len(shared):,} medicines, policy '{args.policy}'.")
    print(
        f"  mean safety stock  old {old['safety_stock'].mean():8.2f}   "
        f"new {new['safety_stock'].mean():8.2f}"
    )
    print(
        f"  mean reorder point old {old['reorder_point'].mean():8.2f}   "
        f"new {new['reorder_point'].mean():8.2f}"
    )

    weeks = sorted(pd.to_datetime(forecasts["week_start"].unique()))
    weekly_sim = weekly[weekly["week_start"].isin(weeks)].copy()
    weekly_sim = weekly_sim[weekly_sim["sku_id"].isin(shared)]
    base_states = _init_states(
        assortment[assortment["sku_id"].isin(shared)],
        batches[batches["sku_id"].isin(shared)],
        as_of=weeks[0],
    )

    by_week = cover_params_by_week(
        cover,
        lead_time=args.lead_time_weeks,
        review_period=args.review_period_weeks,
        service_level=args.service_level,
    )
    weekly_lookup = {
        (int(r.sku_id), pd.Timestamp(r.week_start).normalize()): {
            "reorder_point": float(r.reorder_point),
            "order_up_to": float(r.order_up_to),
        }
        for r in by_week.itertuples(index=False)
    }
    print(f"  per-week reorder levels available for {len(weekly_lookup):,} (medicine, week) pairs")

    runs = (
        ("old_flat_average", old, None),
        ("new_cover_static", new, None),
        ("new_cover_by_week", new, weekly_lookup),
    )
    rows = []
    for label, params, wp in runs:
        print(f"\nSimulating with {label} reorder points...")
        _detail, summary = simulate_policy(
            policy=args.policy,
            base_states=base_states,
            weekly=weekly_sim,
            weeks=weeks,
            params=params,
            lead_time_weeks=int(max(1, round(args.lead_time_weeks))),
            seed=args.seed,
            show_progress=False,
            weekly_params=wp,
        )
        summary["reorder_params"] = label
        summary["mean_safety_stock"] = float(params["safety_stock"].mean())
        summary["mean_reorder_point"] = float(params["reorder_point"].mean())
        rows.append(summary)

    out = pd.DataFrame(rows)
    keep_cols = [
        "reorder_params",
        "fill_rate",
        "unmet_qty",
        "order_qty",
        "orders_placed",
        "stockout_sku_weeks",
        "waste_cost",
        "gross_margin",
        "mean_safety_stock",
        "mean_reorder_point",
    ]
    out = out[[c for c in keep_cols if c in out.columns]]
    path = DATA / "step4b_reorder_comparison.csv"
    out.to_csv(path, index=False)

    print("\nSame policy, same stock, same weeks — only the reorder point differs:")
    print(out.to_string(index=False))

    a, b = out.iloc[0], out.iloc[-1]
    verdict = {
        "policy": args.policy,
        "n_skus": len(shared),
        "fill_rate_old": float(a["fill_rate"]),
        "fill_rate_new": float(b["fill_rate"]),
        "fill_rate_change_pp": round((float(b["fill_rate"]) - float(a["fill_rate"])) * 100, 2),
        "units_ordered_old": float(a["order_qty"]),
        "units_ordered_new": float(b["order_qty"]),
        "units_ordered_change_pct": round(
            (float(b["order_qty"]) / float(a["order_qty"]) - 1) * 100, 2
        )
        if float(a["order_qty"])
        else None,
        "mean_safety_stock_old": float(a["mean_safety_stock"]),
        "mean_safety_stock_new": float(b["mean_safety_stock"]),
        "data_note": "DEV SYNTHETIC data — not Bhagyashree Medical sales.",
    }
    (DATA / "step4b_reorder_comparison.json").write_text(
        json.dumps(verdict, indent=2), encoding="utf-8"
    )
    print(
        f"\nFill rate {verdict['fill_rate_change_pp']:+.2f} pp, "
        f"units ordered {verdict['units_ordered_change_pct']:+.1f}%, "
        f"mean safety stock {a['mean_safety_stock']:.1f} -> {b['mean_safety_stock']:.1f}"
    )
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
