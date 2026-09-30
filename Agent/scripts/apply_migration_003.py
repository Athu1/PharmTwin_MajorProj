"""Apply migration 003 (stock transactions audit types + non-negative stock) idempotently."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUDIT_ACTIONS = (
    "'ADD_MEDICINE','REMOVE_MEDICINE','ADD_LOT','REMOVE_LOT','UPDATE_LOT',"
    "'PURCHASE','RETURN_IN','RETURN_OUT','ADJUST','WRITEOFF_EXPIRY','DEACTIVATE_MEDICINE'"
)


def _constraint_exists(cur, table: str, name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_NAME=%s
        """,
        (table, name),
    )
    return int(cur.fetchone()["n"]) > 0


def apply() -> None:
    from services.db import get_connection

    conn = get_connection()
    cur = conn.cursor()
    try:
        print("Applying migration 003 (stock transactions)...")
        # MODIFY is idempotent; widening an ENUM keeps existing rows
        cur.execute(
            f"ALTER TABLE inventory_audit MODIFY COLUMN action_type ENUM({AUDIT_ACTIONS}) NOT NULL"
        )
        print("  = inventory_audit.action_type widened")
        if not _constraint_exists(cur, "medicine_batches", "chk_batch_qty_nonneg"):
            cur.execute("SELECT COUNT(*) AS n FROM medicine_batches WHERE qty_on_hand < 0")
            bad = int(cur.fetchone()["n"])
            if bad:
                raise SystemExit(
                    f"{bad} batches have negative qty_on_hand — fix them before applying 003."
                )
            cur.execute(
                "ALTER TABLE medicine_batches "
                "ADD CONSTRAINT chk_batch_qty_nonneg CHECK (qty_on_hand >= 0)"
            )
            print("  + medicine_batches CHECK qty_on_hand >= 0")
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('schema_version', '003') "
            "ON DUPLICATE KEY UPDATE meta_value='003'"
        )
        conn.commit()
        print("Migration 003 complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    apply()
