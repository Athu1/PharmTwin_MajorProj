"""Inventory read helpers against MySQL (working stock only — not reference catalog)."""

from __future__ import annotations

from typing import Any

from services.db import get_connection

# Working pharmacy stock — never includes immutable reference catalog
STOCKED_SOURCES = ("dev_synthetic", "pharmacy", "sponsor")


def list_stocked_medicines(
    search: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Editable stocked SKUs with on-hand qty, form/unit, nearest expiry."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            params: list[Any] = list(STOCKED_SOURCES)
            placeholders = ",".join(["%s"] * len(STOCKED_SOURCES))
            where = f"m.source_system IN ({placeholders}) AND m.is_active = 1"
            if search.strip():
                where += " AND (m.name LIKE %s OR m.sku_code LIKE %s)"
                q = f"%{search.strip()}%"
                params.extend([q, q])
            params.append(int(limit))
            cur.execute(
                f"""
                SELECT
                  m.medicine_id,
                  m.external_sku_id AS sku_id,
                  m.sku_code,
                  m.name,
                  m.form_type,
                  m.qty_unit,
                  m.source_system,
                  m.demand_cohort,
                  m.unit_mrp,
                  m.cloned_from_medicine_id,
                  COALESCE(SUM(b.qty_on_hand), 0) AS qty_on_hand,
                  COUNT(b.batch_id) AS n_batches,
                  MIN(CASE WHEN b.qty_on_hand > 0 THEN b.expiry_date END) AS nearest_expiry
                FROM medicines m
                LEFT JOIN medicine_batches b ON b.medicine_id = m.medicine_id
                WHERE {where}
                GROUP BY m.medicine_id, m.external_sku_id, m.sku_code, m.name,
                         m.form_type, m.qty_unit, m.source_system, m.demand_cohort,
                         m.unit_mrp, m.cloned_from_medicine_id
                ORDER BY m.name
                LIMIT %s
                """,
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def list_batches_for_medicine(medicine_id: int) -> list[dict[str, Any]]:
    """FEFO-ordered batches for one medicine."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  batch_id, batch_no, mfg_date, expiry_date,
                  qty_on_hand, qty_unit, unit_cost, received_at,
                  DATEDIFF(expiry_date, CURDATE()) AS days_to_expiry
                FROM medicine_batches
                WHERE medicine_id = %s
                ORDER BY expiry_date ASC, batch_id ASC
                """,
                (int(medicine_id),),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def search_catalog(search: str, limit: int = 50) -> list[dict[str, Any]]:
    """Name search across full catalog knowledge base (read-only)."""
    if not search.strip():
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            q = f"%{search.strip()}%"
            cur.execute(
                """
                SELECT medicine_id, external_sku_id AS sku_id, sku_code, name,
                       source_system, unit_mrp, demand_cohort, pack_size_label,
                       form_type, qty_unit
                FROM medicines
                WHERE name LIKE %s OR sku_code LIKE %s
                ORDER BY
                  CASE
                    WHEN source_system='pharmacy' THEN 0
                    WHEN source_system='dev_synthetic' THEN 1
                    ELSE 2
                  END,
                  name
                LIMIT %s
                """,
                (q, q, int(limit)),
            )
            return list(cur.fetchall())
    finally:
        conn.close()
