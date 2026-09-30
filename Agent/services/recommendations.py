"""Read inventory recommendations from MySQL."""

from __future__ import annotations

import json
from typing import Any

from services.db import get_connection

# Stock that can still be sold (expired lots excluded)
SELLABLE_QTY_SQL = (
    "COALESCE(SUM(CASE WHEN b.expiry_date >= CURDATE() THEN b.qty_on_hand ELSE 0 END), 0)"
)


def decide_action(current: float, rop: float, order_up_to: float) -> tuple[str, float | None]:
    """Reorder rule shared by the Step 4 loader and the live refresh."""
    if current <= 0:
        return "REORDER", max(order_up_to, 1.0)
    if current < rop:
        return "REORDER", max(order_up_to - current, 1.0)
    if current > order_up_to * 2.5:
        return "REVIEW_OVERSTOCK", None
    return "HOLD", None


def build_explanation(
    action: str,
    name: str,
    current: float,
    rop: float,
    ss_qty: float,
    a: dict[str, Any],
    mu: float,
    forecast_demand: float,
) -> str:
    return (
        f"{action} for {name}: on-hand={current:.1f}, "
        f"ROP={rop:.1f}, SS={ss_qty:.1f} "
        f"(SS = Z×σ×√(L+R), Z={float(a['z_score']):.3f}, "
        f"σ={float(a['sigma_weekly']):.2f}, L={float(a['lead_time_weeks']):.0f}w, "
        f"R={float(a['review_period_weeks']):.0f}w, SL={float(a['service_level']):.0%}). "
        f"μ_weekly={mu:.2f}; cover demand≈{forecast_demand:.1f}."
    )


def refresh_recommendations_for(cur, medicine_ids: list[int]) -> int:
    """Recompute action / qty / on-hand for these medicines from live sellable stock.

    Uses the stored Step 4 parameters (ROP, SS, order-up-to); does not retrain.
    Caller commits.
    """
    if not medicine_ids:
        return 0
    ph = ",".join(["%s"] * len(medicine_ids))
    cur.execute(
        f"""
        SELECT r.recommendation_id, r.medicine_id, r.reorder_point, r.safety_stock,
               r.forecast_demand, r.assumptions_json, m.name,
               (SELECT {SELLABLE_QTY_SQL} FROM medicine_batches b
                 WHERE b.medicine_id = r.medicine_id) AS sellable
        FROM recommendations r
        JOIN medicines m ON m.medicine_id = r.medicine_id
        WHERE r.medicine_id IN ({ph})
        """,
        [int(x) for x in medicine_ids],
    )
    n = 0
    for r in cur.fetchall():
        a = r["assumptions_json"]
        if isinstance(a, str):
            a = json.loads(a)
        if not a or "order_up_to" not in a:
            continue
        current = float(r["sellable"] or 0)
        rop = float(r["reorder_point"] or 0)
        ss_qty = float(r["safety_stock"] or 0)
        demand = float(r["forecast_demand"] or 0)
        cover = float(a["lead_time_weeks"]) + float(a["review_period_weeks"])
        mu = demand / cover if cover else 0.0
        action, qty = decide_action(current, rop, float(a["order_up_to"]))
        cur.execute(
            "UPDATE recommendations SET action_type=%s, qty_suggested=%s, current_stock=%s, "
            "explanation_text=%s WHERE recommendation_id=%s",
            (
                action,
                qty,
                current,
                build_explanation(action, r["name"], current, rop, ss_qty, a, mu, demand),
                r["recommendation_id"],
            ),
        )
        n += 1
    return n


def list_recommendations(
    action: str | None = None,
    search: str = "",
    limit: int = 400,
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where = ["m.is_active = 1"]
            params: list[Any] = []
            if action and action.upper() != "ALL":
                where.append("r.action_type = %s")
                params.append(action.upper())
            if search.strip():
                where.append("(m.name LIKE %s OR CAST(m.external_sku_id AS CHAR) LIKE %s)")
                q = f"%{search.strip()}%"
                params.extend([q, q])
            params.append(int(limit))
            cur.execute(
                f"""
                SELECT
                  r.recommendation_id,
                  m.medicine_id,
                  m.external_sku_id AS sku_id,
                  m.name,
                  m.demand_cohort,
                  r.action_type,
                  r.qty_suggested,
                  r.current_stock,
                  r.forecast_demand,
                  r.safety_stock,
                  r.reorder_point,
                  r.explanation_text,
                  r.assumptions_json,
                  r.created_at
                FROM recommendations r
                JOIN medicines m ON m.medicine_id = r.medicine_id
                WHERE {' AND '.join(where)}
                ORDER BY
                  FIELD(r.action_type, 'REORDER', 'REVIEW_EXPIRY', 'REVIEW_OVERSTOCK', 'HOLD'),
                  r.qty_suggested DESC,
                  m.name
                LIMIT %s
                """,
                params,
            )
            rows = list(cur.fetchall())
            for r in rows:
                aj = r.get("assumptions_json")
                if isinstance(aj, str):
                    try:
                        r["assumptions_json"] = json.loads(aj)
                    except json.JSONDecodeError:
                        pass
            return rows
    finally:
        conn.close()


def recommendation_counts() -> dict[str, int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.action_type, COUNT(*) AS n FROM recommendations r "
                "JOIN medicines m ON m.medicine_id = r.medicine_id "
                "WHERE m.is_active = 1 GROUP BY r.action_type"
            )
            out = {r["action_type"]: int(r["n"]) for r in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) AS n FROM recommendations r "
                "JOIN medicines m ON m.medicine_id = r.medicine_id WHERE m.is_active = 1"
            )
            out["ALL"] = int(cur.fetchone()["n"])
            return out
    finally:
        conn.close()
