"""Writable pharmacy inventory — never mutates source_system='reference' catalog."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from services.db import get_connection

EDITABLE_SOURCES = frozenset({"pharmacy", "dev_synthetic", "sponsor"})
IMMUTABLE_SOURCE = "reference"

FORM_TYPES = (
    "TABLET",
    "CAPSULE",
    "SYRUP",
    "INJECTION",
    "CREAM",
    "DROPS",
    "INHALER",
    "POWDER",
    "OTHER",
    "UNKNOWN",
)

QTY_UNITS = (
    "TABLETS",
    "CAPSULES",
    "ML",
    "MG",
    "UNITS",
    "VIALS",
    "BOTTLES",
    "PACKS",
    "OTHER",
)

# Suggested unit per form
DEFAULT_UNIT_FOR_FORM = {
    "TABLET": "TABLETS",
    "CAPSULE": "CAPSULES",
    "SYRUP": "ML",
    "INJECTION": "VIALS",
    "CREAM": "UNITS",
    "DROPS": "ML",
    "INHALER": "UNITS",
    "POWDER": "MG",
    "OTHER": "UNITS",
    "UNKNOWN": "UNITS",
}


class InventoryGuardError(Exception):
    """Raised when an operation would mutate immutable catalog data."""


def _audit(cur, action: str, medicine_id: int | None, batch_id: int | None, detail: dict) -> None:
    cur.execute(
        """
        INSERT INTO inventory_audit (action_type, medicine_id, batch_id, detail_json)
        VALUES (%s,%s,%s,%s)
        """,
        (action, medicine_id, batch_id, json.dumps(detail)),
    )


def _get_medicine(cur, medicine_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT medicine_id, name, source_system, form_type, qty_unit,
               manufacturer_id, category_id, pack_size_label, unit_mrp,
               external_sku_id, cloned_from_medicine_id, sku_code
        FROM medicines WHERE medicine_id=%s
        """,
        (int(medicine_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def assert_editable(med: dict[str, Any] | None) -> dict[str, Any]:
    if not med:
        raise InventoryGuardError("Medicine not found.")
    if med.get("source_system") == IMMUTABLE_SOURCE:
        raise InventoryGuardError(
            "Cannot modify the immutable 250k+ reference catalog. "
            "Add a pharmacy working copy instead (clone from catalog)."
        )
    if med.get("source_system") not in EDITABLE_SOURCES:
        raise InventoryGuardError(f"Medicine source_system={med.get('source_system')!r} is not editable.")
    return med


def infer_form_from_text(text: str) -> tuple[str, str]:
    t = (text or "").lower()
    if any(x in t for x in ("syrup", " suspension", " ml", "ml ")):
        return "SYRUP", "ML"
    if any(x in t for x in ("injection", "inj.", " inj ", "ampoule", "vial")):
        return "INJECTION", "VIALS"
    if "capsule" in t:
        return "CAPSULE", "CAPSULES"
    if "tablet" in t or " tab" in t:
        return "TABLET", "TABLETS"
    if "cream" in t or "ointment" in t or "gel" in t:
        return "CREAM", "UNITS"
    if "drop" in t:
        return "DROPS", "ML"
    if "inhaler" in t:
        return "INHALER", "UNITS"
    if "powder" in t or "sachet" in t:
        return "POWDER", "MG"
    return "UNKNOWN", "UNITS"


def _ensure_mfr(cur, name: str | None) -> int | None:
    if not name or not str(name).strip():
        return None
    name = str(name).strip()[:255]
    cur.execute("SELECT manufacturer_id FROM manufacturers WHERE name=%s", (name,))
    row = cur.fetchone()
    if row:
        return int(row["manufacturer_id"])
    cur.execute("INSERT INTO manufacturers (name) VALUES (%s)", (name,))
    return int(cur.lastrowid)


def add_medicine_with_lot(
    *,
    name: str,
    form_type: str,
    qty_unit: str,
    quantity: float,
    mfg_date: date | str | None,
    expiry_date: date | str,
    batch_no: str | None = None,
    manufacturer_name: str | None = None,
    unit_mrp: float | None = None,
    pack_size_label: str | None = None,
    clone_from_medicine_id: int | None = None,
    unit_cost: float | None = None,
) -> dict[str, Any]:
    """
    Create a pharmacy working medicine + opening lot.
    If clone_from_medicine_id is set, copies catalog fields but inserts a NEW
    pharmacy row — the reference/catalog row is never updated.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Medicine name is required.")
    form_type = (form_type or "UNKNOWN").upper()
    qty_unit = (qty_unit or DEFAULT_UNIT_FOR_FORM.get(form_type, "UNITS")).upper()
    if form_type not in FORM_TYPES:
        raise ValueError(f"Invalid form_type: {form_type}")
    if qty_unit not in QTY_UNITS:
        raise ValueError(f"Invalid qty_unit: {qty_unit}")
    quantity = float(quantity)
    if quantity <= 0:
        raise ValueError("Quantity must be > 0.")

    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(expiry_date[:10])
    if isinstance(mfg_date, str) and mfg_date:
        mfg_date = date.fromisoformat(mfg_date[:10])
    elif not mfg_date:
        mfg_date = None
    if mfg_date and expiry_date <= mfg_date:
        raise ValueError("Expiry date must be after manufacturing date.")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cloned_from = None
            mfr_id = _ensure_mfr(cur, manufacturer_name)
            cat_id = None
            demand_cohort = None
            pack = pack_size_label

            if clone_from_medicine_id is not None:
                src = _get_medicine(cur, int(clone_from_medicine_id))
                if not src:
                    raise ValueError("Catalog medicine to clone was not found.")
                # Allowed to clone FROM reference; never mutate it
                cloned_from = int(src["medicine_id"])
                if not manufacturer_name:
                    cur.execute(
                        "SELECT name FROM manufacturers WHERE manufacturer_id=%s",
                        (src.get("manufacturer_id"),),
                    )
                    mrow = cur.fetchone()
                    if mrow:
                        mfr_id = src.get("manufacturer_id")
                cat_id = src.get("category_id")
                if not pack:
                    pack = src.get("pack_size_label")
                if unit_mrp is None:
                    unit_mrp = float(src["unit_mrp"]) if src.get("unit_mrp") is not None else None
                if name == src.get("name") or not name:
                    name = str(src["name"])
                # Prefer inferred form from catalog pack if user left UNKNOWN
                if form_type == "UNKNOWN":
                    ft, qu = infer_form_from_text(
                        f"{src.get('name','')} {src.get('pack_size_label') or ''}"
                    )
                    form_type, qty_unit = ft, qu

            cur.execute(
                """
                INSERT INTO medicines
                (sku_code, name, manufacturer_id, category_id, pack_size_label,
                 form_type, qty_unit, is_active, unit_mrp, demand_cohort,
                 source_system, external_sku_id, cloned_from_medicine_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s,'pharmacy',NULL,%s)
                """,
                (
                    None,  # set after insert
                    name[:512],
                    mfr_id,
                    cat_id,
                    (pack or "")[:128] or None,
                    form_type,
                    qty_unit,
                    unit_mrp,
                    demand_cohort,
                    cloned_from,
                ),
            )
            med_id = int(cur.lastrowid)
            sku_code = f"PHARM-{med_id}"
            cur.execute(
                "UPDATE medicines SET sku_code=%s WHERE medicine_id=%s",
                (sku_code, med_id),
            )

            bno = (batch_no or f"LOT-{med_id}-{expiry_date.isoformat()}").strip()[:64]
            cur.execute(
                """
                INSERT INTO medicine_batches
                (medicine_id, batch_no, mfg_date, expiry_date, qty_on_hand, qty_unit,
                 unit_cost, received_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    med_id,
                    bno,
                    mfg_date,
                    expiry_date,
                    quantity,
                    qty_unit,
                    unit_cost if unit_cost is not None else unit_mrp,
                    datetime.utcnow(),
                ),
            )
            batch_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO stock_movements
                (medicine_id, batch_id, movement_type, qty_delta, unit_price,
                 ref_table, ref_id, occurred_at)
                VALUES (%s,%s,'PURCHASE',%s,%s,'medicine_batches',%s,%s)
                """,
                (
                    med_id,
                    batch_id,
                    quantity,
                    unit_mrp,
                    batch_id,
                    datetime.utcnow(),
                ),
            )
            _audit(
                cur,
                "ADD_MEDICINE",
                med_id,
                batch_id,
                {
                    "name": name,
                    "form_type": form_type,
                    "qty_unit": qty_unit,
                    "quantity": quantity,
                    "mfg_date": str(mfg_date) if mfg_date else None,
                    "expiry_date": str(expiry_date),
                    "cloned_from_medicine_id": cloned_from,
                    "immutable_catalog_untouched": True,
                },
            )
            conn.commit()
            return {
                "medicine_id": med_id,
                "batch_id": batch_id,
                "sku_code": sku_code,
                "name": name,
                "form_type": form_type,
                "qty_unit": qty_unit,
                "quantity": quantity,
                "cloned_from_medicine_id": cloned_from,
            }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_lot_to_medicine(
    medicine_id: int,
    *,
    quantity: float,
    expiry_date: date | str,
    mfg_date: date | str | None = None,
    batch_no: str | None = None,
    qty_unit: str | None = None,
    unit_cost: float | None = None,
) -> dict[str, Any]:
    quantity = float(quantity)
    if quantity <= 0:
        raise ValueError("Quantity must be > 0.")
    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(expiry_date[:10])
    if isinstance(mfg_date, str) and mfg_date:
        mfg_date = date.fromisoformat(mfg_date[:10])
    elif not mfg_date:
        mfg_date = None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            med = assert_editable(_get_medicine(cur, medicine_id))
            unit = (qty_unit or med.get("qty_unit") or "UNITS").upper()
            bno = (batch_no or f"LOT-{medicine_id}-{expiry_date.isoformat()}").strip()[:64]
            cur.execute(
                """
                INSERT INTO medicine_batches
                (medicine_id, batch_no, mfg_date, expiry_date, qty_on_hand, qty_unit,
                 unit_cost, received_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(medicine_id),
                    bno,
                    mfg_date,
                    expiry_date,
                    quantity,
                    unit,
                    unit_cost,
                    datetime.utcnow(),
                ),
            )
            batch_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO stock_movements
                (medicine_id, batch_id, movement_type, qty_delta, unit_price,
                 ref_table, ref_id, occurred_at)
                VALUES (%s,%s,'PURCHASE',%s,%s,'medicine_batches',%s,%s)
                """,
                (int(medicine_id), batch_id, quantity, unit_cost, batch_id, datetime.utcnow()),
            )
            _audit(
                cur,
                "ADD_LOT",
                int(medicine_id),
                batch_id,
                {
                    "quantity": quantity,
                    "qty_unit": unit,
                    "mfg_date": str(mfg_date) if mfg_date else None,
                    "expiry_date": str(expiry_date),
                },
            )
            conn.commit()
            return {"medicine_id": int(medicine_id), "batch_id": batch_id, "qty_unit": unit}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _has_sales_history(cur, medicine_id: int) -> bool:
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM sales_items WHERE medicine_id=%s) AS h", (int(medicine_id),)
    )
    return bool(cur.fetchone()["h"])


def _deactivate_medicine(cur, med: dict[str, Any]) -> dict[str, Any]:
    """Soft delete: keep sales / movement history for forecasting, zero the shelf stock."""
    mid = int(med["medicine_id"])
    cur.execute(
        "SELECT batch_id, qty_on_hand FROM medicine_batches "
        "WHERE medicine_id=%s AND qty_on_hand > 0 FOR UPDATE",
        (mid,),
    )
    now = datetime.utcnow()
    units = 0.0
    for b in cur.fetchall():
        q = float(b["qty_on_hand"])
        cur.execute(
            "UPDATE medicine_batches SET qty_on_hand=0 WHERE batch_id=%s", (b["batch_id"],)
        )
        cur.execute(
            """
            INSERT INTO stock_movements
            (medicine_id, batch_id, movement_type, qty_delta, unit_price, ref_table, ref_id, occurred_at)
            VALUES (%s,%s,'ADJUST',%s,NULL,'medicines',%s,%s)
            """,
            (mid, b["batch_id"], -q, mid, now),
        )
        units += q
    cur.execute("UPDATE medicines SET is_active=0 WHERE medicine_id=%s", (mid,))
    _audit(
        cur,
        "DEACTIVATE_MEDICINE",
        mid,
        None,
        {
            "name": med.get("name"),
            "units_removed_from_shelf": units,
            "sales_history_kept": True,
            "reference_catalog_untouched": True,
        },
    )
    return {"removed_medicine_id": mid, "name": med.get("name"), "kept_history": True,
            "units_removed": units}


def get_medicine_details(medicine_id: int) -> dict[str, Any]:
    """Editable fields of a working-inventory medicine (for the edit dialog)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            med = assert_editable(_get_medicine(cur, medicine_id))
            cur.execute(
                "SELECT name FROM manufacturers WHERE manufacturer_id=%s",
                (med.get("manufacturer_id"),),
            )
            m = cur.fetchone()
            cur.execute(
                "SELECT COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches WHERE medicine_id=%s",
                (int(medicine_id),),
            )
            stock = float(cur.fetchone()["q"])
            return {
                "medicine_id": int(medicine_id),
                "sku_code": med.get("sku_code"),
                "name": med.get("name") or "",
                "form_type": med.get("form_type") or "UNKNOWN",
                "qty_unit": med.get("qty_unit") or "UNITS",
                "manufacturer_name": m["name"] if m else "",
                "pack_size_label": med.get("pack_size_label") or "",
                "unit_mrp": med.get("unit_mrp"),
                "source_system": med.get("source_system"),
                "stock_on_hand": stock,
            }
    finally:
        conn.close()


_KEEP: Any = object()  # update_medicine: argument not given -> keep current value


def _apply_medicine_update(
    cur,
    medicine_id: int,
    *,
    name: Any = _KEEP,
    form_type: Any = _KEEP,
    qty_unit: Any = _KEEP,
    manufacturer_name: Any = _KEEP,
    pack_size_label: Any = _KEEP,
    unit_mrp: Any = _KEEP,
) -> dict[str, Any]:
    """Validate + apply one medicine edit inside the caller's transaction."""
    cur.execute(
        "SELECT medicine_id FROM medicines WHERE medicine_id=%s FOR UPDATE", (int(medicine_id),)
    )
    med = assert_editable(_get_medicine(cur, medicine_id))
    mid = int(medicine_id)
    label = med.get("name") or f"#{mid}"
    cur.execute("SELECT is_active FROM medicines WHERE medicine_id=%s", (mid,))
    if not cur.fetchone()["is_active"]:
        raise InventoryGuardError(f"{label}: removed from stock (inactive), cannot edit.")
    cur.execute(
        "SELECT name FROM manufacturers WHERE manufacturer_id=%s", (med.get("manufacturer_id"),)
    )
    m = cur.fetchone()
    old_mfr = m["name"] if m else ""
    before = {
        "name": med.get("name"),
        "form_type": med.get("form_type"),
        "qty_unit": med.get("qty_unit"),
        "manufacturer": old_mfr,
        "pack_size_label": med.get("pack_size_label"),
        "unit_mrp": float(med["unit_mrp"]) if med.get("unit_mrp") is not None else None,
    }
    after = dict(before)
    if name is not _KEEP:
        name = (name or "").strip()
        if not name:
            raise ValueError("Medicine name is required.")
        after["name"] = name[:512]
    if form_type is not _KEEP:
        form_type = (form_type or "UNKNOWN").upper()
        if form_type not in FORM_TYPES:
            raise ValueError(f"Invalid form_type: {form_type}")
        after["form_type"] = form_type
    if qty_unit is not _KEEP:
        qty_unit = (qty_unit or "UNITS").upper()
        if qty_unit not in QTY_UNITS:
            raise ValueError(f"Invalid qty_unit: {qty_unit}")
        after["qty_unit"] = qty_unit
    if manufacturer_name is not _KEEP:
        after["manufacturer"] = (manufacturer_name or "").strip()
    if pack_size_label is not _KEEP:
        after["pack_size_label"] = (pack_size_label or "").strip()[:128] or None
    if unit_mrp is not _KEEP:
        if unit_mrp is not None and unit_mrp != "":
            unit_mrp = float(unit_mrp)
            if unit_mrp < 0:
                raise ValueError("MRP cannot be negative.")
            after["unit_mrp"] = unit_mrp
        else:
            after["unit_mrp"] = None

    changes = {k: {"old": before[k], "new": after[k]} for k in after if before[k] != after[k]}
    if not changes:
        return {"medicine_id": mid, "name": label, "changes": {}}

    if "qty_unit" in changes:
        cur.execute(
            "SELECT COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches WHERE medicine_id=%s",
            (mid,),
        )
        stock = float(cur.fetchone()["q"])
        if stock > 0:
            raise InventoryGuardError(
                f"{label}: cannot change the counting unit from {before['qty_unit']} to "
                f"{after['qty_unit']} while {stock:.0f} units are in stock — the quantities "
                "would be misread. Sell, write off or correct the stock to 0 first."
            )
    mfr_id = (
        med.get("manufacturer_id")
        if after["manufacturer"] == old_mfr
        else _ensure_mfr(cur, after["manufacturer"])
    )
    cur.execute(
        """
        UPDATE medicines
        SET name=%s, form_type=%s, qty_unit=%s, manufacturer_id=%s,
            pack_size_label=%s, unit_mrp=%s
        WHERE medicine_id=%s AND source_system <> %s
        """,
        (after["name"], after["form_type"], after["qty_unit"], mfr_id,
         after["pack_size_label"], after["unit_mrp"], mid, IMMUTABLE_SOURCE),
    )
    if "qty_unit" in changes:
        cur.execute(
            "UPDATE medicine_batches SET qty_unit=%s WHERE medicine_id=%s", (after["qty_unit"], mid)
        )
    _audit(cur, "UPDATE_MEDICINE", mid, None,
           {"changes": changes, "reference_catalog_untouched": True})
    return {"medicine_id": mid, "name": after["name"], "changes": changes}


def update_medicine(medicine_id: int, **fields: Any) -> dict[str, Any]:
    """Edit one working-inventory medicine. Reference catalog rows are refused.

    Fields: name, form_type, qty_unit, manufacturer_name, pack_size_label, unit_mrp.
    Fields left out are kept; pass None or "" to clear manufacturer / pack / MRP.
    The counting unit cannot change while stock exists (100 TABLETS would silently
    become 100 ML). Every change is written to inventory_audit with before/after.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            out = _apply_medicine_update(cur, medicine_id, **fields)
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def bulk_update_medicines(medicine_ids: list[int], **fields: Any) -> dict[str, Any]:
    """Apply the same field changes to several medicines — all or nothing.

    Name is not allowed in bulk (every medicine would get the same name).
    """
    if "name" in fields:
        raise ValueError("Name cannot be changed for several medicines at once.")
    if not medicine_ids:
        raise ValueError("Select at least one medicine.")
    if not fields:
        raise ValueError("Choose at least one field to change.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            results = [_apply_medicine_update(cur, int(mid), **fields) for mid in medicine_ids]
        conn.commit()
        return {
            "updated": [r for r in results if r["changes"]],
            "unchanged": [r for r in results if not r["changes"]],
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_medicine(medicine_id: int) -> dict[str, Any]:
    """Remove a working-inventory medicine. Never deletes reference.

    With sales history: soft delete (is_active=0, history kept for forecasting).
    Without (e.g. added by mistake): hard delete of the medicine and its lots.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            med = assert_editable(_get_medicine(cur, medicine_id))
            mid = int(medicine_id)
            if _has_sales_history(cur, mid):
                out = _deactivate_medicine(cur, med)
                conn.commit()
                return out
            cur.execute("DELETE FROM recommendations WHERE medicine_id=%s", (mid,))
            cur.execute("DELETE FROM forecasts WHERE medicine_id=%s", (mid,))
            cur.execute("DELETE FROM alerts WHERE medicine_id=%s", (mid,))
            cur.execute("DELETE FROM sales_items WHERE medicine_id=%s", (mid,))
            cur.execute("DELETE FROM stock_movements WHERE medicine_id=%s", (mid,))
            try:
                cur.execute("DELETE FROM demand_coverage WHERE medicine_id=%s", (mid,))
            except Exception:  # noqa: BLE001
                pass
            try:
                cur.execute("DELETE FROM purchase_order_items WHERE medicine_id=%s", (mid,))
            except Exception:  # noqa: BLE001
                pass
            cur.execute("DELETE FROM medicine_batches WHERE medicine_id=%s", (mid,))
            cur.execute(
                "DELETE FROM medicines WHERE medicine_id=%s AND source_system <> %s",
                (mid, IMMUTABLE_SOURCE),
            )
            if cur.rowcount != 1:
                raise InventoryGuardError(
                    "Delete blocked — medicine may be reference or already gone."
                )
            _audit(
                cur,
                "REMOVE_MEDICINE",
                mid,
                None,
                {
                    "name": med.get("name"),
                    "source_system": med.get("source_system"),
                    "reference_catalog_untouched": True,
                },
            )
            conn.commit()
            return {"removed_medicine_id": mid, "name": med.get("name"), "kept_history": False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_lot(batch_id: int) -> dict[str, Any]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.batch_id, b.medicine_id, b.batch_no, m.source_system, m.name
                FROM medicine_batches b
                JOIN medicines m ON m.medicine_id = b.medicine_id
                WHERE b.batch_id=%s
                """,
                (int(batch_id),),
            )
            row = cur.fetchone()
            if not row:
                raise InventoryGuardError("Lot not found.")
            assert_editable(dict(row))
            bid = int(row["batch_id"])
            mid = int(row["medicine_id"])
            # Only a batch that was received and never used may be deleted (typo fix);
            # otherwise the sales ledger would lose history.
            cur.execute(
                "SELECT (SELECT COUNT(*) FROM sales_items WHERE batch_id=%s) + "
                "(SELECT COUNT(*) FROM stock_movements WHERE batch_id=%s "
                " AND movement_type <> 'PURCHASE') AS n",
                (bid, bid),
            )
            if int(cur.fetchone()["n"]) > 0:
                raise InventoryGuardError(
                    "This batch has sales or returns recorded, so it cannot be deleted. "
                    "Use 'Correct quantity' or 'Write off expired' instead."
                )
            cur.execute("DELETE FROM stock_movements WHERE batch_id=%s", (bid,))
            cur.execute("DELETE FROM medicine_batches WHERE batch_id=%s", (bid,))
            _audit(
                cur,
                "REMOVE_LOT",
                mid,
                bid,
                {"batch_no": row.get("batch_no"), "name": row.get("name")},
            )
            conn.commit()
            return {"removed_batch_id": bid, "medicine_id": mid}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def search_reference_catalog(search: str, limit: int = 40) -> list[dict[str, Any]]:
    """Search immutable catalog only (for clone-into-pharmacy flow)."""
    if not search.strip():
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            q = f"%{search.strip()}%"
            cur.execute(
                """
                SELECT medicine_id, external_sku_id AS sku_id, sku_code, name,
                       pack_size_label, unit_mrp, form_type, qty_unit
                FROM medicines
                WHERE source_system='reference'
                  AND (name LIKE %s OR sku_code LIKE %s)
                ORDER BY name
                LIMIT %s
                """,
                (q, q, int(limit)),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def count_by_source() -> dict[str, int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_system, COUNT(*) AS n FROM medicines GROUP BY source_system"
            )
            return {r["source_system"]: int(r["n"]) for r in cur.fetchall()}
    finally:
        conn.close()
