"""Smoke test: inventory CRUD never touches reference catalog."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.db import get_connection
from services.inventory_write import (
    InventoryGuardError,
    add_medicine_with_lot,
    count_by_source,
    remove_medicine,
    search_reference_catalog,
)


def ref_count() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM medicines WHERE source_system='reference'"
            )
            return int(cur.fetchone()["n"])
    finally:
        conn.close()


def main() -> int:
    before = count_by_source()
    nref = ref_count()
    print("sources before:", before)
    print("reference count:", nref)
    ref = search_reference_catalog("paracetamol", limit=3)
    print("catalog search hits:", len(ref), "-", ref[0]["name"] if ref else None)
    out = add_medicine_with_lot(
        name="Demo Cough Syrup",
        form_type="SYRUP",
        qty_unit="ML",
        quantity=120,
        mfg_date="2025-06-01",
        expiry_date="2027-06-01",
        manufacturer_name="Demo Labs",
        clone_from_medicine_id=int(ref[0]["medicine_id"]) if ref else None,
    )
    print("added:", out)
    assert ref_count() == nref, "reference count changed on add!"
    print("sources after add:", count_by_source())
    rm = remove_medicine(out["medicine_id"])
    print("removed:", rm)
    assert ref_count() == nref, "reference count changed on remove!"
    print("sources after remove:", count_by_source())
    if ref:
        try:
            remove_medicine(int(ref[0]["medicine_id"]))
            print("FAIL: reference delete was allowed")
            return 1
        except InventoryGuardError as exc:
            print("reference protected OK:", str(exc)[:100])
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
