"""Twin-isolated inventory what-if simulations (never mutate live batches)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from services.db import get_connection

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

POLICIES = (
    "fifo_static",
    "fefo_static",
    "fefo_ss",
    "fefo_ss_markdown",
)


def ensure_base_snapshot() -> int:
    """Return latest twin snapshot_id; create a lightweight one if missing."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT snapshot_id FROM digital_twin_snapshots "
                "ORDER BY snapshot_id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                return int(row["snapshot_id"])
            state = {
                "mode": "dev_synthetic",
                "label": "Auto snapshot for simulation base",
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }
            payload = json.dumps(state)
            cur.execute(
                """
                INSERT INTO digital_twin_snapshots (synced_at, source_hash, is_stale, state_json)
                VALUES (%s,%s,0,%s)
                """,
                (datetime.utcnow(), "sim-base", payload),
            )
            conn.commit()
            return int(cur.lastrowid)
    finally:
        conn.close()


def list_simulation_runs(limit: int = 50) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.run_id, r.title, r.scenario_json, r.created_at, r.base_snapshot_id,
                       (SELECT COUNT(*) FROM simulation_results s WHERE s.run_id = r.run_id) AS n_results
                FROM simulation_runs r
                ORDER BY r.run_id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = list(cur.fetchall())
            for r in rows:
                sj = r.get("scenario_json")
                if isinstance(sj, str):
                    try:
                        r["scenario_json"] = json.loads(sj)
                    except json.JSONDecodeError:
                        pass
            return rows
    finally:
        conn.close()


def get_run_results(run_id: int) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT result_id, metrics_json, narrative
                FROM simulation_results
                WHERE run_id = %s
                ORDER BY result_id
                """,
                (int(run_id),),
            )
            rows = list(cur.fetchall())
            out = []
            for r in rows:
                mj = r.get("metrics_json")
                if isinstance(mj, str):
                    try:
                        mj = json.loads(mj)
                    except json.JSONDecodeError:
                        mj = {}
                if isinstance(mj, dict) and "policies" in mj:
                    # expanded multi-policy payload
                    for p in mj["policies"]:
                        out.append(
                            {
                                "result_id": r["result_id"],
                                "narrative": r.get("narrative"),
                                **p,
                            }
                        )
                elif isinstance(mj, dict):
                    out.append(
                        {
                            "result_id": r["result_id"],
                            "narrative": r.get("narrative"),
                            **mj,
                        }
                    )
            return out
    finally:
        conn.close()


def _persist_run(
    title: str,
    scenario: dict[str, Any],
    policy_metrics: list[dict[str, Any]],
    narrative: str,
) -> int:
    snap_id = ensure_base_snapshot()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO simulation_runs (base_snapshot_id, title, scenario_json)
                VALUES (%s,%s,%s)
                """,
                (snap_id, title[:255], json.dumps(scenario)),
            )
            run_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO simulation_results (run_id, metrics_json, narrative)
                VALUES (%s,%s,%s)
                """,
                (
                    run_id,
                    json.dumps({"policies": policy_metrics, "mutates_live_stock": False}),
                    narrative,
                ),
            )
            conn.commit()
            return run_id
    finally:
        conn.close()


def import_cached_step4() -> dict[str, Any]:
    """Persist offline Step 4 policy comparison as a twin-isolated simulation run."""
    path = DATA / "step4_policy_comparison.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: py -3 scripts/run_step4.py"
        )
    df = pd.read_csv(path)
    policies = []
    for r in df.itertuples(index=False):
        policies.append(
            {
                "policy": str(r.policy),
                "fill_rate": float(r.fill_rate),
                "sold_qty": float(r.sold_qty),
                "unmet_qty": float(r.unmet_qty),
                "demand_qty": float(r.demand_qty),
                "waste_cost": float(r.waste_cost),
                "markdown_discount": float(r.markdown_discount),
                "gross_margin": float(r.gross_margin),
                "waste_reduction_vs_fifo_pct": float(
                    getattr(r, "waste_reduction_vs_fifo_pct", 0) or 0
                ),
                "orders_placed": float(r.orders_placed),
            }
        )
    best = max(policies, key=lambda p: (p["fill_rate"], -p["waste_cost"]))
    scenario = {
        "source": "step4_policy_comparison.csv",
        "demand_multiplier": 1.0,
        "lead_time_weeks": 1.0,
        "mutates_live_stock": False,
        "note": "Cached offline Step 4 results; live medicine_batches untouched.",
    }
    narrative = (
        f"Cached Step 4 FEFO comparison. Best by fill/waste: {best['policy']} "
        f"(fill={best['fill_rate']:.1%}). Live inventory was NOT modified."
    )
    run_id = _persist_run(
        title="Cached Step 4 policy comparison (isolated)",
        scenario=scenario,
        policy_metrics=policies,
        narrative=narrative,
    )
    return {"run_id": run_id, "n_policies": len(policies), "best": best["policy"]}


def run_whatif(
    demand_multiplier: float = 1.0,
    lead_time_weeks: float = 1.0,
    policies: list[str] | None = None,
    max_skus: int | None = 150,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Re-run FEFO/FIFO policies on cloned offline state with optional demand shock.
    Does not write to medicine_batches / stock_movements.
    """
    from src.inventory_fefo import is_otc_sku
    from src.run_inventory_sim import (
        _init_states,
        _load_inputs,
        simulate_policy,
    )
    from src.safety_stock import sku_stock_params_from_forecasts

    policies = policies or list(POLICIES)
    for p in policies:
        if p not in POLICIES:
            raise ValueError(f"Unknown policy: {p}")

    assortment, batches, forecasts, weekly = _load_inputs(DATA)
    if max_skus is not None and max_skus < len(assortment):
        import numpy as np

        rng = np.random.default_rng(seed)
        keep = set(
            rng.choice(
                assortment["sku_id"].to_numpy(),
                size=min(max_skus, len(assortment)),
                replace=False,
            )
        )
        assortment = assortment[assortment["sku_id"].isin(keep)].copy()
        batches = batches[batches["sku_id"].isin(keep)].copy()
        forecasts = forecasts[forecasts["sku_id"].isin(keep)].copy()
        weekly = weekly[weekly["sku_id"].isin(keep)].copy()

    if "is_otc" not in assortment.columns:
        assortment["is_otc"] = assortment.apply(is_otc_sku, axis=1)

    params = sku_stock_params_from_forecasts(
        forecasts,
        lead_time=lead_time_weeks,
        review_period=1.0,
        service_level=0.95,
    )
    params = params.merge(
        assortment[
            ["sku_id", "name", "price_inr", "Therapeutic Class", "demand_cohort", "is_otc"]
        ],
        on="sku_id",
        how="left",
    )

    weeks = sorted(pd.to_datetime(forecasts["week_start"].unique()))
    weekly_sim = weekly[weekly["week_start"].isin(weeks)].copy()
    weekly_sim["demand"] = weekly_sim["demand"].astype(float) * float(demand_multiplier)

    sim_start = weeks[0]
    base_states = _init_states(assortment, batches, as_of=sim_start)

    summaries = []
    for policy in policies:
        _detail, summary = simulate_policy(
            policy=policy,
            base_states=base_states,
            weekly=weekly_sim,
            weeks=weeks,
            params=params,
            lead_time_weeks=int(max(1, round(lead_time_weeks))),
            seed=seed,
            show_progress=False,
        )
        summaries.append(
            {
                "policy": summary["policy"],
                "fill_rate": float(summary["fill_rate"]),
                "sold_qty": float(summary["sold_qty"]),
                "unmet_qty": float(summary["unmet_qty"]),
                "demand_qty": float(summary["demand_qty"]),
                "waste_cost": float(summary["waste_cost"]),
                "markdown_discount": float(summary["markdown_discount"]),
                "gross_margin": float(summary["gross_margin"]),
                "orders_placed": float(summary["orders_placed"]),
            }
        )

    if summaries:
        fifo = next((s for s in summaries if s["policy"] == "fifo_static"), None)
        if fifo and fifo["waste_cost"] > 0:
            for s in summaries:
                s["waste_reduction_vs_fifo_pct"] = (
                    (fifo["waste_cost"] - s["waste_cost"]) / fifo["waste_cost"] * 100.0
                )
        else:
            for s in summaries:
                s["waste_reduction_vs_fifo_pct"] = 0.0

    best = max(summaries, key=lambda p: (p["fill_rate"], -p["waste_cost"]))
    scenario = {
        "source": "live_whatif",
        "demand_multiplier": float(demand_multiplier),
        "lead_time_weeks": float(lead_time_weeks),
        "max_skus": max_skus,
        "n_skus": int(assortment["sku_id"].nunique()),
        "n_weeks": len(weeks),
        "policies": policies,
        "mutates_live_stock": False,
        "seed": seed,
    }
    title = (
        f"What-if demand×{demand_multiplier:.2f} L={lead_time_weeks:.0f}w "
        f"({len(policies)} policies, {scenario['n_skus']} SKUs)"
    )
    narrative = (
        f"Isolated twin simulation. Demand×{demand_multiplier:.2f}, "
        f"lead time {lead_time_weeks:.0f} week(s), {scenario['n_skus']} SKUs, "
        f"{scenario['n_weeks']} weeks. Best: {best['policy']} "
        f"(fill={best['fill_rate']:.1%}). Live medicine_batches NOT modified."
    )
    run_id = _persist_run(title, scenario, summaries, narrative)
    return {
        "run_id": run_id,
        "n_policies": len(summaries),
        "best": best["policy"],
        "summaries": summaries,
        "scenario": scenario,
    }


def verify_live_stock_untouched(before_hash: str | None = None) -> dict[str, Any]:
    """Helper for demos: fingerprint batch qty sum (sim must not change it)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches"
            )
            row = cur.fetchone()
            fingerprint = f"{row['n']}:{float(row['q']):.3f}"
            return {
                "fingerprint": fingerprint,
                "unchanged": before_hash is None or before_hash == fingerprint,
                "n_batches": int(row["n"]),
                "on_hand": float(row["q"]),
            }
    finally:
        conn.close()
