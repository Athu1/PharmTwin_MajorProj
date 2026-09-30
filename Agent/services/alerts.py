"""Live alert generation from inventory (low stock / near expiry)."""

from __future__ import annotations

from typing import Any

from services.db import get_connection


def compute_live_alerts(
    expiry_days: int = 90,
    low_stock_units: float = 20.0,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Derive open-style alerts from current batches / stocked medicines.
    Does not require prior rows in the alerts table.
    """
    conn = get_connection()
    alerts: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  m.medicine_id, m.name, m.external_sku_id AS sku_id,
                  b.batch_id, b.batch_no, b.qty_on_hand, b.expiry_date,
                  DATEDIFF(b.expiry_date, CURDATE()) AS days_to_expiry
                FROM medicine_batches b
                JOIN medicines m ON m.medicine_id = b.medicine_id
                WHERE b.qty_on_hand > 0
                  AND DATEDIFF(b.expiry_date, CURDATE()) <= %s
                ORDER BY b.expiry_date ASC
                LIMIT %s
                """,
                (int(expiry_days), int(limit)),
            )
            for row in cur.fetchall():
                days = int(row["days_to_expiry"] or 0)
                severity = "CRITICAL" if days <= 30 else "WARN"
                alerts.append(
                    {
                        "alert_type": "EXPIRY",
                        "severity": severity,
                        "medicine_id": row["medicine_id"],
                        "sku_id": row["sku_id"],
                        "name": row["name"],
                        "batch_no": row["batch_no"],
                        "qty_on_hand": float(row["qty_on_hand"]),
                        "expiry_date": str(row["expiry_date"]),
                        "days_to_expiry": days,
                        "message": (
                            (
                                f"Expired {-days} day{'s' if days != -1 else ''} ago"
                                if days < 0
                                else f"Expires in {days} day{'s' if days != 1 else ''}"
                            )
                            + f" — {row['name']} batch {row['batch_no']} "
                            f"({float(row['qty_on_hand']):.0f} units)"
                        ),
                    }
                )

            cur.execute(
                """
                SELECT
                  m.medicine_id, m.name, m.external_sku_id AS sku_id,
                  COALESCE(SUM(b.qty_on_hand), 0) AS qty_on_hand
                FROM medicines m
                LEFT JOIN medicine_batches b ON b.medicine_id = m.medicine_id
                WHERE m.source_system IN ('dev_synthetic','pharmacy','sponsor')
                  AND m.is_active = 1
                GROUP BY m.medicine_id, m.name, m.external_sku_id
                HAVING qty_on_hand < %s
                ORDER BY qty_on_hand ASC, m.name
                LIMIT %s
                """,
                (float(low_stock_units), int(limit)),
            )
            for row in cur.fetchall():
                qty = float(row["qty_on_hand"])
                severity = "CRITICAL" if qty <= 0 else "WARN"
                alerts.append(
                    {
                        "alert_type": "LOW_STOCK" if qty > 0 else "STOCKOUT_RISK",
                        "severity": severity,
                        "medicine_id": row["medicine_id"],
                        "sku_id": row["sku_id"],
                        "name": row["name"],
                        "batch_no": None,
                        "qty_on_hand": qty,
                        "expiry_date": None,
                        "days_to_expiry": None,
                        "message": (
                            f"{'Stockout' if qty <= 0 else 'Low stock'}: "
                            f"{row['name']} — {qty:.0f} units on hand"
                        ),
                    }
                )
    finally:
        conn.close()

    order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    alerts.sort(key=lambda a: (order.get(a["severity"], 9), a["alert_type"], a["name"]))
    return alerts[:limit]
