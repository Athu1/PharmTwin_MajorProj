"""Desktop substitute recommendations — wraps Step 5 engine + live MySQL stock."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from services.db import get_connection

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

_engine = None


def _stock_from_db() -> dict[int, float]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.external_sku_id AS sku_id, COALESCE(SUM(b.qty_on_hand), 0) AS qty
                FROM medicines m
                LEFT JOIN medicine_batches b ON b.medicine_id = m.medicine_id
                WHERE m.source_system IN ('dev_synthetic','pharmacy','sponsor')
                  AND m.is_active = 1
                  AND m.external_sku_id IS NOT NULL
                GROUP BY m.external_sku_id
                """
            )
            return {int(r["sku_id"]): float(r["qty"]) for r in cur.fetchall()}
    finally:
        conn.close()


def get_engine(min_cosine: float = 0.55):
    """Lazy-fit TF-IDF engine on pharmacy assortment (stocked SKUs)."""
    global _engine
    if _engine is not None:
        _engine.stock = _stock_from_db()
        return _engine

    from src.substitutes_nlp import SubstituteEngine

    path = DATA / "assortment_3k.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing assortment file: {path}")
    assortment = pd.read_csv(path)
    assortment["sku_id"] = assortment["sku_id"].astype(int)
    stock = _stock_from_db()
    _engine = SubstituteEngine.fit(assortment, stock=stock, min_cosine=min_cosine)
    return _engine


def list_query_medicines(search: str = "", limit: int = 40) -> list[dict[str, Any]]:
    """Stocked medicines available as substitute query targets."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            params: list[Any] = []
            # Rows without external_sku_id (Inventory-UI / imported additions) are
            # not in the Step 5 index; querying catalog clones is backlog P4.
            where = (
                "source_system IN ('dev_synthetic','pharmacy','sponsor') AND is_active = 1 "
                "AND external_sku_id IS NOT NULL"
            )
            if search.strip():
                where += " AND (name LIKE %s OR sku_code LIKE %s)"
                q = f"%{search.strip()}%"
                params.extend([q, q])
            params.append(int(limit))
            cur.execute(
                f"""
                SELECT medicine_id, external_sku_id AS sku_id, sku_code, name, unit_mrp
                FROM medicines
                WHERE {where}
                ORDER BY name
                LIMIT %s
                """,
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def recommend_for_sku(sku_id: int, top_n: int = 5) -> dict[str, Any]:
    """
    Pharmacist-reviewed substitute suggestions for a stocked SKU.
    Returns structured payload for the desktop UI.
    """
    engine = get_engine()
    sku_id = int(sku_id)
    if sku_id not in engine.index_by_sku:
        return {
            "ok": False,
            "error": f"SKU {sku_id} is not in the active assortment used for substitutes.",
            "results": [],
        }

    query = engine._row(sku_id)
    results = engine.recommend(
        sku_id, top_n=top_n, require_in_stock=True, include_blocked=False
    )
    # Also surface blocked reasons for transparency when nothing allowed
    # Probe wider than the allowed list: the candidates a rule removed sit BELOW the
    # ones that survived, so a same-size probe would only return the same rows back.
    blocked_probe = engine.recommend(
        sku_id, top_n=max(top_n * 4, 20), require_in_stock=False, include_blocked=True
    )
    h1_block = (
        blocked_probe
        and blocked_probe[0].source == "blocked"
        and blocked_probe[0].schedule_h1
    )

    def _row_payload(r) -> dict[str, Any]:
        return {
            "candidate_sku_id": r.candidate_sku_id,
            "candidate_name": r.candidate_name,
            "score": round(float(r.score), 4),
            "source": r.source,
            "aware": r.aware,
            "schedule_h1": r.schedule_h1,
            "blocked": r.blocked,
            "block_reason": r.block_reason,
            "price_inr": r.price_inr,
            "therapeutic_class": r.therapeutic_class,
            "on_hand": float(engine.stock.get(r.candidate_sku_id, 0.0)),
        }

    # Candidates the safety rules removed. Showing WHY one was withheld is more useful
    # to a pharmacist than silently offering a shorter list (docs/false_positives.md).
    allowed_ids = {r.candidate_sku_id for r in results}
    withheld = [
        _row_payload(r)
        for r in blocked_probe
        if r.candidate_sku_id > 0
        and r.candidate_sku_id not in allowed_ids
        and (r.blocked or float(engine.stock.get(r.candidate_sku_id, 0.0)) <= 0)
    ]
    for row in withheld:
        if not row["block_reason"] and row["on_hand"] <= 0:
            row["block_reason"] = "Not in stock"

    payload_results = [
        {
            "candidate_sku_id": r.candidate_sku_id,
            "candidate_name": r.candidate_name,
            "score": round(float(r.score), 4),
            "source": r.source,
            "aware": r.aware,
            "schedule_h1": r.schedule_h1,
            "blocked": r.blocked,
            "block_reason": r.block_reason,
            "price_inr": r.price_inr,
            "therapeutic_class": r.therapeutic_class,
            "on_hand": float(engine.stock.get(r.candidate_sku_id, 0.0)),
        }
        for r in results
        if r.candidate_sku_id > 0
    ]

    return {
        "ok": True,
        "query_sku_id": sku_id,
        "query_name": str(query.get("name") or ""),
        "query_class": str(query.get("Therapeutic Class") or ""),
        "h1_blocked": bool(h1_block),
        "h1_message": blocked_probe[0].block_reason if h1_block else "",
        "n_allowed": len(payload_results),
        "results": payload_results,
        "n_withheld": len(withheld),
        "withheld": withheld,
        "disclaimer": (
            "Pharmacist-reviewed inventory alternatives only — "
            "not automatic clinical prescribing. "
            "Schedule H1 / WHO AWaRe / CDSCO gates applied."
        ),
    }


@lru_cache(maxsize=1)
def engine_ready() -> bool:
    try:
        get_engine()
        return True
    except Exception:  # noqa: BLE001
        return False
