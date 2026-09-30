"""Read inventory recommendations from MySQL."""

from __future__ import annotations

import json
from typing import Any

from services.db import get_connection


def list_recommendations(
    action: str | None = None,
    search: str = "",
    limit: int = 400,
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            where = ["1=1"]
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
                "SELECT action_type, COUNT(*) AS n FROM recommendations GROUP BY action_type"
            )
            out = {r["action_type"]: int(r["n"]) for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM recommendations")
            out["ALL"] = int(cur.fetchone()["n"])
            return out
    finally:
        conn.close()
