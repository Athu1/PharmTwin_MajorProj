"""Read demand forecasts from MySQL."""

from __future__ import annotations

import json
from typing import Any

from services.db import get_connection


def list_forecast_summary(limit: int = 300) -> list[dict[str, Any]]:
    """Per-medicine latest forecast horizon + average yhat over stored weeks."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  m.medicine_id,
                  m.external_sku_id AS sku_id,
                  m.name,
                  m.demand_cohort,
                  f.model_name,
                  COUNT(*) AS n_weeks,
                  ROUND(AVG(f.yhat), 3) AS avg_yhat,
                  ROUND(AVG(f.yhat_lower), 3) AS avg_q50,
                  ROUND(AVG(f.yhat_upper), 3) AS avg_q95,
                  MIN(f.horizon_start) AS from_week,
                  MAX(f.horizon_start) AS to_week,
                  MAX(f.trained_through) AS trained_through
                FROM forecasts f
                JOIN medicines m ON m.medicine_id = f.medicine_id
                GROUP BY m.medicine_id, m.external_sku_id, m.name, m.demand_cohort, f.model_name
                ORDER BY avg_yhat DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def list_forecast_weeks(medicine_id: int, limit: int = 40) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT horizon_start, horizon_end, yhat, yhat_lower, yhat_upper,
                       model_name, metrics_json
                FROM forecasts
                WHERE medicine_id = %s
                ORDER BY horizon_start
                LIMIT %s
                """,
                (int(medicine_id), int(limit)),
            )
            rows = list(cur.fetchall())
            for r in rows:
                mj = r.get("metrics_json")
                if isinstance(mj, str):
                    try:
                        r["metrics_json"] = json.loads(mj)
                    except json.JSONDecodeError:
                        pass
            return rows
    finally:
        conn.close()


def forecast_counts() -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM forecasts")
            n = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(DISTINCT medicine_id) AS n FROM forecasts")
            n_med = cur.fetchone()["n"]
            cur.execute(
                "SELECT model_name, COUNT(*) AS n FROM forecasts GROUP BY model_name"
            )
            models = {r["model_name"]: int(r["n"]) for r in cur.fetchall()}
            return {"n_rows": int(n), "n_medicines": int(n_med), "models": models}
    finally:
        conn.close()
