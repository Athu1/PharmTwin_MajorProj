"""Day-to-day stock transactions (INV-02): sale, purchase receipt, returns, adjust, write-off.

Every operation runs in ONE database transaction:
  medicine_batches.qty_on_hand  <- updated (never below 0; DB CHECK from migration 003)
  stock_movements               <- one ledger row per batch touched
  sales_transactions/items      <- sales only (shortfall recorded as unmet_qty)
  inventory_audit               <- manual actions (purchase, returns, adjust, write-off)
  recommendations               <- action / on-hand recomputed for the medicine
Reference catalog rows are never touched (assert_editable).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from services.db import get_connection
from services.inventory_write import InventoryGuardError, _audit, _get_medicine, assert_editable
from services.recommendations import refresh_recommendations_for


class StockError(ValueError):
    """Invalid stock operation (bad qty, expired lot, more than available, …)."""


def _as_date(v: date | str | None) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v).strip()[:10])


def _positive(qty: Any, what: str = "Quantity") -> float:
    try:
        q = float(qty)
    except (TypeError, ValueError) as exc:
        raise StockError(f"{what} must be a number.") from exc
    if q <= 0:
        raise StockError(f"{what} must be more than 0.")
    return q


def _active_medicine(cur, medicine_id: int) -> dict[str, Any]:
    med = assert_editable(_get_medicine(cur, medicine_id))
    cur.execute("SELECT is_active FROM medicines WHERE medicine_id=%s", (int(medicine_id),))
    if not cur.fetchone()["is_active"]:
        raise InventoryGuardError("This medicine was removed from stock (inactive).")
    return med


def _sales_label(cur) -> str:
    cur.execute("SELECT meta_value FROM app_meta WHERE meta_key='data_mode'")
    row = cur.fetchone()
    return "sponsor" if row and row["meta_value"] == "sponsor" else "dev_synthetic"


def _lock_batch(cur, batch_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT b.batch_id, b.medicine_id, b.batch_no, b.expiry_date, b.qty_on_hand,
               b.unit_cost, DATEDIFF(b.expiry_date, CURDATE()) AS days_to_expiry
        FROM medicine_batches b WHERE b.batch_id=%s FOR UPDATE
        """,
        (int(batch_id),),
    )
    b = cur.fetchone()
    if not b:
        raise StockError(f"Batch {batch_id} not found.")
    assert_editable(_get_medicine(cur, int(b["medicine_id"])))
    return b


def _move(cur, medicine_id, batch_id, mtype, delta, price, ref_table, ref_id, when) -> None:
    cur.execute(
        """
        INSERT INTO stock_movements
        (medicine_id, batch_id, movement_type, qty_delta, unit_price, ref_table, ref_id, occurred_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (int(medicine_id), batch_id, mtype, float(delta), price, ref_table, ref_id, when),
    )


def _set_qty(cur, batch_id: int, delta: float) -> None:
    cur.execute(
        "UPDATE medicine_batches SET qty_on_hand = qty_on_hand + %s "
        "WHERE batch_id=%s AND qty_on_hand + %s >= 0",
        (float(delta), int(batch_id), float(delta)),
    )
    if cur.rowcount != 1:
        raise StockError(f"Batch {batch_id} would go below zero — nothing was saved.")


def _fefo_plan(cur, medicine_id: int, qty: float, lock: bool) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT batch_id, batch_no, expiry_date, qty_on_hand,
               DATEDIFF(expiry_date, CURDATE()) AS days_to_expiry
        FROM medicine_batches
        WHERE medicine_id=%s AND qty_on_hand > 0
        ORDER BY expiry_date ASC, batch_id ASC
        {'FOR UPDATE' if lock else ''}
        """,
        (int(medicine_id),),
    )
    remaining = qty
    allocations, expired_qty = [], 0.0
    for b in cur.fetchall():
        avail = float(b["qty_on_hand"])
        if int(b["days_to_expiry"]) < 0:
            expired_qty += avail  # never sell expired stock
            continue
        if remaining <= 0:
            continue
        take = min(avail, remaining)
        allocations.append(
            {
                "batch_id": int(b["batch_id"]),
                "batch_no": b["batch_no"],
                "expiry_date": str(b["expiry_date"]),
                "days_to_expiry": int(b["days_to_expiry"]),
                "available": avail,
                "take": take,
            }
        )
        remaining -= take
    return {
        "requested": qty,
        "allocations": allocations,
        "fulfilled": qty - max(remaining, 0.0),
        "short": max(remaining, 0.0),
        "expired_qty_skipped": expired_qty,
    }


def suggest_fefo(medicine_id: int, qty: float) -> dict[str, Any]:
    """Which batches a sale would use: earliest expiry first, expired lots skipped."""
    qty = _positive(qty)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _active_medicine(cur, medicine_id)
            return _fefo_plan(cur, medicine_id, qty, lock=False)
    finally:
        conn.close()


def post_sale(
    medicine_id: int,
    qty: float,
    *,
    unit_price: float | None = None,
    sold_at: datetime | None = None,
    allow_partial: bool = True,
) -> dict[str, Any]:
    """Sell qty using FEFO. Shortfall (not enough sellable stock) -> unmet_qty, never negative."""
    qty = _positive(qty)
    when = sold_at or datetime.now()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            med = _active_medicine(cur, medicine_id)
            plan = _fefo_plan(cur, medicine_id, qty, lock=True)
            if plan["short"] > 0 and not allow_partial:
                raise StockError(
                    f"Only {plan['fulfilled']:.0f} sellable units in stock "
                    f"(asked {qty:.0f}). Nothing was saved."
                )
            price = float(unit_price) if unit_price is not None else float(med.get("unit_mrp") or 0)
            cur.execute(
                "INSERT INTO sales_transactions (sold_at, channel, source_system) "
                "VALUES (%s,'COUNTER',%s)",
                (when, _sales_label(cur)),
            )
            sale_id = int(cur.lastrowid)
            for a in plan["allocations"]:
                _set_qty(cur, a["batch_id"], -a["take"])
                cur.execute(
                    "INSERT INTO sales_items (sale_id, medicine_id, batch_id, qty, unmet_qty, unit_price) "
                    "VALUES (%s,%s,%s,%s,0,%s)",
                    (sale_id, int(medicine_id), a["batch_id"], a["take"], price),
                )
                _move(cur, medicine_id, a["batch_id"], "SALE", -a["take"], price,
                      "sales_transactions", sale_id, when)
            if plan["short"] > 0:
                # Lost sale: demand we could not serve (feeds forecasting, not stock)
                cur.execute(
                    "INSERT INTO sales_items (sale_id, medicine_id, batch_id, qty, unmet_qty, unit_price) "
                    "VALUES (%s,%s,NULL,0,%s,%s)",
                    (sale_id, int(medicine_id), plan["short"], price),
                )
            refresh_recommendations_for(cur, [int(medicine_id)])
        conn.commit()
        return {"sale_id": sale_id, "unit_price": price, **plan}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def receive_purchase(
    medicine_id: int,
    qty: float,
    *,
    expiry_date: date | str,
    batch_no: str | None = None,
    mfg_date: date | str | None = None,
    unit_cost: float | None = None,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Goods received from supplier: new batch, or top-up of the same batch number."""
    qty = _positive(qty)
    expiry = _as_date(expiry_date)
    mfg = _as_date(mfg_date)
    if expiry is None:
        raise StockError("Expiry date is required.")
    if expiry < date.today():
        raise StockError("Cannot receive stock that has already expired.")
    if mfg and expiry <= mfg:
        raise StockError("Expiry date must be after the manufacturing date.")
    when = received_at or datetime.now()
    bno = (batch_no or f"LOT-{medicine_id}-{expiry.isoformat()}").strip()[:64]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            med = _active_medicine(cur, medicine_id)
            cur.execute(
                "SELECT batch_id, expiry_date FROM medicine_batches "
                "WHERE medicine_id=%s AND batch_no=%s FOR UPDATE",
                (int(medicine_id), bno),
            )
            existing = cur.fetchone()
            if existing:
                if _as_date(existing["expiry_date"]) != expiry:
                    raise StockError(
                        f"Batch {bno} already exists with expiry {existing['expiry_date']}. "
                        "Check the batch number or expiry."
                    )
                batch_id = int(existing["batch_id"])
                _set_qty(cur, batch_id, qty)
                topped_up = True
            else:
                cur.execute(
                    """
                    INSERT INTO medicine_batches
                    (medicine_id, batch_no, mfg_date, expiry_date, qty_on_hand, qty_unit,
                     unit_cost, received_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (int(medicine_id), bno, mfg, expiry, qty, med.get("qty_unit"), unit_cost, when),
                )
                batch_id = int(cur.lastrowid)
                topped_up = False
            _move(cur, medicine_id, batch_id, "PURCHASE", qty, unit_cost,
                  "medicine_batches", batch_id, when)
            _audit(cur, "PURCHASE", int(medicine_id), batch_id, {
                "qty": qty, "batch_no": bno, "expiry_date": str(expiry),
                "unit_cost": unit_cost, "topped_up_existing_batch": topped_up,
            })
            refresh_recommendations_for(cur, [int(medicine_id)])
        conn.commit()
        return {"batch_id": batch_id, "batch_no": bno, "qty": qty, "topped_up": topped_up}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def customer_return(batch_id: int, qty: float, *, reason: str = "") -> dict[str, Any]:
    """Customer brings medicine back into sellable stock (not allowed for expired batches)."""
    qty = _positive(qty)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            b = _lock_batch(cur, batch_id)
            mid = int(b["medicine_id"])
            _active_medicine(cur, mid)
            if int(b["days_to_expiry"]) < 0:
                raise StockError("This batch has expired — returned stock cannot be resold.")
            cur.execute(
                "SELECT COALESCE(SUM(CASE WHEN movement_type='SALE' THEN -qty_delta END),0) AS sold, "
                "COALESCE(SUM(CASE WHEN movement_type='RETURN_IN' THEN qty_delta END),0) AS returned "
                "FROM stock_movements WHERE medicine_id=%s",
                (mid,),
            )
            m = cur.fetchone()
            returnable = float(m["sold"]) - float(m["returned"])
            if qty > returnable:
                raise StockError(
                    f"Only {returnable:.0f} units of this medicine were sold and not yet "
                    "returned — cannot accept more back."
                )
            _set_qty(cur, int(batch_id), qty)
            now = datetime.now()
            _move(cur, mid, int(batch_id), "RETURN_IN", qty, None, "medicine_batches",
                  int(batch_id), now)
            _audit(cur, "RETURN_IN", mid, int(batch_id), {"qty": qty, "reason": reason})
            refresh_recommendations_for(cur, [mid])
        conn.commit()
        return {"batch_id": int(batch_id), "qty": qty}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def return_to_supplier(batch_id: int, qty: float, *, reason: str = "") -> dict[str, Any]:
    """Send stock back to the supplier (damaged, recalled, near expiry…)."""
    qty = _positive(qty)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            b = _lock_batch(cur, batch_id)
            mid = int(b["medicine_id"])
            if qty > float(b["qty_on_hand"]):
                raise StockError(f"Batch has only {float(b['qty_on_hand']):.0f} units.")
            _set_qty(cur, int(batch_id), -qty)
            _move(cur, mid, int(batch_id), "RETURN_OUT", -qty, b["unit_cost"],
                  "medicine_batches", int(batch_id), datetime.now())
            _audit(cur, "RETURN_OUT", mid, int(batch_id), {"qty": qty, "reason": reason})
            refresh_recommendations_for(cur, [mid])
        conn.commit()
        return {"batch_id": int(batch_id), "qty": qty}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def adjust_batch_qty(batch_id: int, new_qty: float, *, reason: str) -> dict[str, Any]:
    """Stock count correction. A reason is mandatory and stored in the audit trail."""
    reason = (reason or "").strip()
    if not reason:
        raise StockError("Please give a reason for the correction (e.g. 'shelf count', 'damaged').")
    try:
        new_qty = float(new_qty)
    except (TypeError, ValueError) as exc:
        raise StockError("New quantity must be a number.") from exc
    if new_qty < 0:
        raise StockError("New quantity cannot be negative.")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            b = _lock_batch(cur, batch_id)
            mid = int(b["medicine_id"])
            old = float(b["qty_on_hand"])
            delta = new_qty - old
            if delta == 0:
                raise StockError("New quantity is the same as the current quantity.")
            _set_qty(cur, int(batch_id), delta)
            _move(cur, mid, int(batch_id), "ADJUST", delta, None, "medicine_batches",
                  int(batch_id), datetime.now())
            _audit(cur, "ADJUST", mid, int(batch_id),
                   {"old_qty": old, "new_qty": new_qty, "reason": reason})
            refresh_recommendations_for(cur, [mid])
        conn.commit()
        return {"batch_id": int(batch_id), "old_qty": old, "new_qty": new_qty}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def write_off_expired(batch_id: int | None = None) -> dict[str, Any]:
    """Remove expired stock from the shelf (one batch, or every expired batch if None)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if batch_id is not None:
                b = _lock_batch(cur, batch_id)
                if int(b["days_to_expiry"]) >= 0:
                    raise StockError("This batch has not expired yet.")
                rows = [b] if float(b["qty_on_hand"]) > 0 else []
            else:
                cur.execute(
                    """
                    SELECT b.batch_id, b.medicine_id, b.batch_no, b.expiry_date,
                           b.qty_on_hand, b.unit_cost
                    FROM medicine_batches b
                    JOIN medicines m ON m.medicine_id = b.medicine_id
                    WHERE b.expiry_date < CURDATE() AND b.qty_on_hand > 0
                      AND m.source_system <> 'reference'
                    FOR UPDATE
                    """
                )
                rows = list(cur.fetchall())
            now = datetime.now()
            units = 0.0
            for b in rows:
                q = float(b["qty_on_hand"])
                _set_qty(cur, int(b["batch_id"]), -q)
                _move(cur, b["medicine_id"], int(b["batch_id"]), "WRITEOFF_EXPIRY", -q,
                      b["unit_cost"], "medicine_batches", int(b["batch_id"]), now)
                _audit(cur, "WRITEOFF_EXPIRY", int(b["medicine_id"]), int(b["batch_id"]),
                       {"qty": q, "batch_no": b["batch_no"], "expiry_date": str(b["expiry_date"])})
                units += q
            refresh_recommendations_for(cur, sorted({int(b["medicine_id"]) for b in rows}))
        conn.commit()
        return {"batches": len(rows), "units": units}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_stock_consistency() -> dict[str, Any]:
    """No batch below zero and no sale line with a negative qty / unmet qty."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM medicine_batches WHERE qty_on_hand < 0")
            neg = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM sales_items WHERE qty < 0 OR unmet_qty < 0")
            bad_items = int(cur.fetchone()["n"])
            return {"negative_batches": neg, "bad_sale_items": bad_items,
                    "ok": neg == 0 and bad_items == 0}
    finally:
        conn.close()


__all__ = [
    "StockError",
    "suggest_fefo",
    "post_sale",
    "receive_purchase",
    "customer_return",
    "return_to_supplier",
    "adjust_batch_qty",
    "write_off_expired",
    "check_stock_consistency",
]
