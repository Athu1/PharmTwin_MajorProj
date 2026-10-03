"""Step 4: FEFO inventory simulation, probabilistic safety stock, OTC markdowns."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from .inventory_fefo import (
    Batch,
    SkuState,
    allocate_demand,
    is_otc_sku,
    on_hand,
    receive_orders,
    write_off_expired,
)
from .safety_stock import sku_stock_params_from_forecasts
from .series import DATA_DIR, load_demand_events, to_weekly_demand

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"

POLICIES = (
    "fifo_static",
    "fefo_static",
    "fefo_ss",
    "fefo_ss_markdown",
)


def _load_inputs(out: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    assortment = pd.read_csv(out / "assortment_3k.csv")
    assortment["sku_id"] = assortment["sku_id"].astype(int)
    assortment["is_otc"] = assortment.apply(is_otc_sku, axis=1)

    batches = pd.read_csv(out / "batches_fefo.csv", parse_dates=["receipt_date", "mfg_date", "expiry_date"])
    # Reset to received qty for clean simulation
    batches["qty_remaining"] = batches["qty_received"].astype(float)

    fc_path = out / "step3_forecasts_weekly.parquet"
    if not fc_path.exists():
        fc_path = out / "step3_forecasts_weekly.csv"
    forecasts = (
        pd.read_parquet(fc_path)
        if fc_path.suffix == ".parquet"
        else pd.read_csv(fc_path, parse_dates=["week_start"])
    )
    forecasts["week_start"] = pd.to_datetime(forecasts["week_start"]).dt.normalize()
    forecasts["sku_id"] = forecasts["sku_id"].astype(int)

    events = load_demand_events(use_unmet=True)
    weekly = to_weekly_demand(events, sku_ids=assortment["sku_id"].tolist())
    return assortment, batches, forecasts, weekly


def _init_states(
    assortment: pd.DataFrame,
    batches: pd.DataFrame,
    as_of: pd.Timestamp,
) -> dict[int, SkuState]:
    price_map = assortment.set_index("sku_id")["price_inr"].astype(float).to_dict()
    otc_map = assortment.set_index("sku_id")["is_otc"].astype(bool).to_dict()
    states: dict[int, SkuState] = {}
    for sku_id in assortment["sku_id"].astype(int):
        states[sku_id] = SkuState(sku_id=sku_id)

    for row in batches.itertuples(index=False):
        sku_id = int(row.sku_id)
        if sku_id not in states:
            continue
        # Only batches already received by sim start
        if pd.Timestamp(row.receipt_date) > as_of:
            continue
        states[sku_id].batches.append(
            Batch(
                batch_id=str(row.batch_id),
                sku_id=sku_id,
                receipt_date=pd.Timestamp(row.receipt_date),
                expiry_date=pd.Timestamp(row.expiry_date),
                qty_remaining=float(row.qty_received),
                unit_cost=float(row.unit_cost),
                unit_price=float(price_map.get(sku_id, row.unit_cost / 0.72)),
                is_otc=bool(otc_map.get(sku_id, False)),
            )
        )
    return states


def _clone_states(states: dict[int, SkuState]) -> dict[int, SkuState]:
    out: dict[int, SkuState] = {}
    for sid, st in states.items():
        ns = SkuState(sku_id=sid, on_order=0.0)
        ns.batches = [
            Batch(
                batch_id=b.batch_id,
                sku_id=b.sku_id,
                receipt_date=b.receipt_date,
                expiry_date=b.expiry_date,
                qty_remaining=b.qty_remaining,
                unit_cost=b.unit_cost,
                unit_price=b.unit_price,
                is_otc=b.is_otc,
            )
            for b in st.batches
        ]
        out[sid] = ns
    return out


def simulate_policy(
    policy: str,
    base_states: dict[int, SkuState],
    weekly: pd.DataFrame,
    weeks: list[pd.Timestamp],
    params: pd.DataFrame,
    lead_time_weeks: int = 1,
    seed: int = 42,
    show_progress: bool = True,
    weekly_params: dict[tuple[int, pd.Timestamp], dict] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run weekly inventory simulation for one policy (cloned state — never mutates caller).

    `weekly_params` optionally supplies a reorder point and order-up-to level per
    (sku_id, week) instead of one fixed pair per SKU. That is what a forecast-driven
    reorder point needs: the level should move with the weeks it is covering. Any
    (sku, week) absent from the mapping falls back to the static row in `params`.
    """
    rng = np.random.default_rng(seed)
    states = _clone_states(base_states)
    param_map = params.set_index("sku_id").to_dict(orient="index")
    batch_seq = [10_000_000]

    use_fefo = policy.startswith("fefo")
    use_ss = "ss" in policy
    use_md = policy.endswith("markdown")
    pick = "fefo" if use_fefo else "fifo"

    demand_by = {
        (int(r.sku_id), pd.Timestamp(r.week_start).normalize()): float(r.demand)
        for r in weekly.itertuples(index=False)
    }

    rows = []
    totals = {
        "sold_qty": 0.0,
        "unmet_qty": 0.0,
        "demand_qty": 0.0,
        "revenue": 0.0,
        "cogs": 0.0,
        "markdown_discount": 0.0,
        "waste_qty": 0.0,
        "waste_cost": 0.0,
        "waste_retail": 0.0,
        "orders_placed": 0,
        "order_qty": 0.0,
        "stockout_sku_weeks": 0,
    }

    sku_ids = list(states.keys())
    week_iter = tqdm(weeks, desc=f"Sim {policy}", leave=False) if show_progress else weeks
    for week in week_iter:
        week = pd.Timestamp(week).normalize()
        for sku_id in sku_ids:
            state = states[sku_id]
            p = param_map.get(sku_id)
            if p is None:
                continue
            is_otc = bool(p.get("is_otc", False))
            price = float(p.get("price_inr") or 100.0)
            cost = price * 0.72

            receive_orders(state, week, batch_seq, is_otc=is_otc)

            waste = write_off_expired(state, week)
            totals["waste_qty"] += waste["waste_qty"]
            totals["waste_cost"] += waste["waste_cost"]
            totals["waste_retail"] += waste["waste_retail"]

            demand = demand_by.get((sku_id, week), 0.0)
            totals["demand_qty"] += demand
            alloc = allocate_demand(
                state,
                demand=demand,
                as_of=week,
                policy=pick,
                apply_markdown=use_md,
            )
            sold_vs_demand = min(alloc["sold"], demand)
            unmet = max(demand - sold_vs_demand, 0.0)
            totals["sold_qty"] += sold_vs_demand
            totals["unmet_qty"] += unmet
            # Revenue: scale if clearance sold beyond demand was counted
            if alloc["sold"] > 0 and demand > 0:
                totals["revenue"] += alloc["revenue"] * (sold_vs_demand / alloc["sold"])
                totals["cogs"] += alloc["cogs"] * (sold_vs_demand / alloc["sold"])
                totals["markdown_discount"] += alloc["markdown_discount"] * (
                    sold_vs_demand / alloc["sold"]
                )
            elif alloc["sold"] > 0:
                totals["revenue"] += alloc["revenue"]
                totals["cogs"] += alloc["cogs"]
                totals["markdown_discount"] += alloc["markdown_discount"]
            if unmet > 0:
                totals["stockout_sku_weeks"] += 1

            oh = on_hand(state, week)
            inventory_position = oh + state.on_order
            if use_ss:
                wp = weekly_params.get((sku_id, week)) if weekly_params else None
                if wp is not None:
                    target = float(wp["order_up_to"])
                    rop = float(wp["reorder_point"])
                else:
                    target = float(p["order_up_to"])
                    rop = float(p["reorder_point"])
            else:
                target = max(float(p["mu_weekly"]) * 4.0, 2.0)
                rop = max(float(p["mu_weekly"]) * 2.0, 1.0)

            if inventory_position <= rop:
                order_qty = float(np.ceil(max(target - inventory_position, 0.0)))
                if order_qty > 0:
                    arrival = week + pd.Timedelta(weeks=lead_time_weeks)
                    state.pending_receipts.append((arrival, order_qty, cost, price))
                    state.on_order += order_qty
                    totals["orders_placed"] += 1
                    totals["order_qty"] += order_qty

            rows.append(
                {
                    "policy": policy,
                    "week_start": week,
                    "sku_id": sku_id,
                    "demand": demand,
                    "sold": sold_vs_demand,
                    "unmet": unmet,
                    "on_hand": oh,
                    "waste_qty": waste["waste_qty"],
                    "revenue": alloc["revenue"],
                    "markdown_discount": alloc["markdown_discount"],
                }
            )

    fill_rate = 1.0 - (totals["unmet_qty"] / totals["demand_qty"]) if totals["demand_qty"] else 1.0
    summary = {
        "policy": policy,
        **{k: float(v) if not isinstance(v, str) else v for k, v in totals.items()},
        "fill_rate": float(fill_rate),
        "gross_margin": float(totals["revenue"] - totals["cogs"]),
        "waste_cost_pct_of_cogs": float(
            totals["waste_cost"] / totals["cogs"] if totals["cogs"] else 0.0
        ),
    }
    _ = rng  # reserved for stochastic lead-time extensions
    return pd.DataFrame(rows), summary


def run_step4(
    lead_time_weeks: float = 1.0,
    review_period_weeks: float = 1.0,
    service_level: float = 0.95,
    max_skus: int | None = None,
    seed: int = 42,
    out_dir: Path | str | None = None,
) -> dict[str, Path]:
    out = Path(out_dir) if out_dir else DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Loading assortment, batches, Step-3 quantiles, weekly demand...")
    assortment, batches, forecasts, weekly = _load_inputs(out)
    if max_skus is not None:
        rng = np.random.default_rng(seed)
        keep = set(rng.choice(assortment["sku_id"].to_numpy(), size=min(max_skus, len(assortment)), replace=False))
        assortment = assortment[assortment["sku_id"].isin(keep)]
        batches = batches[batches["sku_id"].isin(keep)]
        forecasts = forecasts[forecasts["sku_id"].isin(keep)]
        weekly = weekly[weekly["sku_id"].isin(keep)]

    print(f"  SKUs: {assortment['sku_id'].nunique()} | OTC-eligible: {int(assortment['is_otc'].sum())}")

    params = sku_stock_params_from_forecasts(
        forecasts,
        lead_time=lead_time_weeks,
        review_period=review_period_weeks,
        service_level=service_level,
    )
    params = params.merge(
        assortment[["sku_id", "name", "price_inr", "Therapeutic Class", "demand_cohort", "is_otc"]],
        on="sku_id",
        how="left",
    )
    params_path = out / "step4_safety_stock_params.csv"
    params.to_csv(params_path, index=False)
    print(
        f"  SS formula: SS = Z*sigma*sqrt(L+R) | Z={params['z_score'].iloc[0]:.3f} "
        f"L={lead_time_weeks} R={review_period_weeks} | mean SS={params['safety_stock'].mean():.2f}"
    )

    # Simulate over Step-3 test weeks (where quantiles exist)
    weeks = sorted(pd.to_datetime(forecasts["week_start"].unique()))
    sim_start = weeks[0]
    # Restrict weekly demand to sim window
    weekly_sim = weekly[weekly["week_start"].isin(weeks)].copy()

    print(f"Initializing inventory states as of {sim_start.date()}...")
    base_states = _init_states(assortment, batches, as_of=sim_start)

    detail_frames = []
    summaries = []
    for policy in POLICIES:
        detail, summary = simulate_policy(
            policy=policy,
            base_states=base_states,
            weekly=weekly_sim,
            weeks=weeks,
            params=params,
            lead_time_weeks=int(max(1, round(lead_time_weeks))),
            seed=seed,
        )
        detail_frames.append(detail)
        summaries.append(summary)
        print(
            f"  {policy}: fill={summary['fill_rate']:.3f} "
            f"waste_cost=Rs{summary['waste_cost']:,.0f} "
            f"markdown=Rs{summary['markdown_discount']:,.0f} "
            f"margin=Rs{summary['gross_margin']:,.0f}"
        )

    summary_df = pd.DataFrame(summaries)
    # Relative waste reduction vs FIFO static
    fifo_waste = float(summary_df.loc[summary_df["policy"] == "fifo_static", "waste_cost"].iloc[0])
    summary_df["waste_reduction_vs_fifo_pct"] = (
        (fifo_waste - summary_df["waste_cost"]) / fifo_waste * 100.0 if fifo_waste > 0 else 0.0
    )

    summary_path = out / "step4_policy_comparison.csv"
    summary_df.to_csv(summary_path, index=False)

    detail = pd.concat(detail_frames, ignore_index=True)
    # Aggregate weekly policy KPIs (lighter than full sku-week dump for CSV)
    weekly_kpi = (
        detail.groupby(["policy", "week_start"], as_index=False)
        .agg(
            demand=("demand", "sum"),
            sold=("sold", "sum"),
            unmet=("unmet", "sum"),
            waste_qty=("waste_qty", "sum"),
            revenue=("revenue", "sum"),
            markdown_discount=("markdown_discount", "sum"),
        )
    )
    weekly_path = out / "step4_weekly_kpis.csv"
    weekly_kpi.to_csv(weekly_path, index=False)
    detail.to_parquet(out / "step4_sim_detail.parquet", index=False)

    best = summary_df.sort_values(["waste_cost", "fill_rate"], ascending=[True, False]).iloc[0]
    payload = {
        "n_skus": int(assortment["sku_id"].nunique()),
        "n_otc": int(assortment["is_otc"].sum()),
        "n_weeks": len(weeks),
        "sim_start": str(weeks[0].date()),
        "sim_end": str(weeks[-1].date()),
        "lead_time_weeks": lead_time_weeks,
        "review_period_weeks": review_period_weeks,
        "service_level": service_level,
        "formula": "SS = Z * sigma_LT * sqrt(L + R)",
        "policies": summary_df.to_dict(orient="records"),
        "best_policy_by_waste_then_fill": best["policy"],
        "notes": (
            "FEFO vs FIFO pick logic; probabilistic SS from LightGBM q50/q90/q95; "
            "OTC near-expiry markdown tiers (10/25/40/50%) with clearance uplift. "
            "Schedule H1 / anti-infectives excluded from auto-markdown."
        ),
    }
    summary_json = out / "step4_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("\n=== Step 4 policy comparison ===")
    cols = [
        "policy",
        "fill_rate",
        "waste_cost",
        "waste_reduction_vs_fifo_pct",
        "markdown_discount",
        "gross_margin",
        "stockout_sku_weeks",
    ]
    print(summary_df[cols].to_string(index=False))
    print(f"\nBest policy: {best['policy']}")

    return {
        "safety_stock_params": params_path,
        "policy_comparison": summary_path,
        "weekly_kpis": weekly_path,
        "summary": summary_json,
    }


if __name__ == "__main__":
    run_step4()
