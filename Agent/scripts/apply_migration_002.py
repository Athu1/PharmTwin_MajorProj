"""Apply migration 002 (editable inventory columns) idempotently."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (table, column),
    )
    return int(cur.fetchone()[0]) > 0


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=%s
        """,
        (table,),
    )
    return int(cur.fetchone()[0]) > 0


def apply() -> None:
    import pymysql

    _load_dotenv()
    conn = pymysql.connect(
        host=os.getenv("PHARMTWIN_DB_HOST", "127.0.0.1"),
        user=os.getenv("PHARMTWIN_DB_USER", "root"),
        password=os.getenv("PHARMTWIN_DB_PASSWORD", ""),
        database=os.getenv("PHARMTWIN_DB_NAME", "pharmtwinai"),
        port=int(os.getenv("PHARMTWIN_DB_PORT", "3306")),
        charset="utf8mb4",
        autocommit=False,
    )
    cur = conn.cursor()
    try:
        print("Applying migration 002 (inventory editable)...")
        cur.execute(
            """
            ALTER TABLE medicines
            MODIFY COLUMN source_system
              ENUM('sponsor','dev_synthetic','reference','pharmacy')
              NOT NULL DEFAULT 'dev_synthetic'
            """
        )
        if not _column_exists(cur, "medicines", "form_type"):
            cur.execute(
                """
                ALTER TABLE medicines
                ADD COLUMN form_type
                  ENUM(
                    'TABLET','CAPSULE','SYRUP','INJECTION','CREAM','DROPS',
                    'INHALER','POWDER','OTHER','UNKNOWN'
                  ) NOT NULL DEFAULT 'UNKNOWN'
                  AFTER pack_size_label
                """
            )
            print("  + medicines.form_type")
        if not _column_exists(cur, "medicines", "qty_unit"):
            cur.execute(
                """
                ALTER TABLE medicines
                ADD COLUMN qty_unit
                  ENUM('TABLETS','CAPSULES','ML','MG','UNITS','VIALS','BOTTLES','PACKS','OTHER')
                  NOT NULL DEFAULT 'UNITS'
                  AFTER form_type
                """
            )
            print("  + medicines.qty_unit")
        if not _column_exists(cur, "medicines", "cloned_from_medicine_id"):
            cur.execute(
                """
                ALTER TABLE medicines
                ADD COLUMN cloned_from_medicine_id INT NULL
                  AFTER external_sku_id
                """
            )
            print("  + medicines.cloned_from_medicine_id")
        if not _column_exists(cur, "medicine_batches", "qty_unit"):
            cur.execute(
                """
                ALTER TABLE medicine_batches
                ADD COLUMN qty_unit
                  ENUM('TABLETS','CAPSULES','ML','MG','UNITS','VIALS','BOTTLES','PACKS','OTHER')
                  NULL
                  AFTER qty_on_hand
                """
            )
            print("  + medicine_batches.qty_unit")
        if not _table_exists(cur, "inventory_audit"):
            cur.execute(
                """
                CREATE TABLE inventory_audit (
                  audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                  action_type ENUM(
                    'ADD_MEDICINE','REMOVE_MEDICINE','ADD_LOT','REMOVE_LOT','UPDATE_LOT'
                  ) NOT NULL,
                  medicine_id INT NULL,
                  batch_id BIGINT NULL,
                  detail_json JSON NULL,
                  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  KEY idx_inv_audit_time (created_at)
                ) ENGINE=InnoDB
                """
            )
            print("  + inventory_audit")

        # Heuristic backfill for existing working stock (not reference)
        cur.execute(
            """
            UPDATE medicines SET form_type='SYRUP', qty_unit='ML'
            WHERE source_system <> 'reference'
              AND form_type='UNKNOWN'
              AND (
                LOWER(COALESCE(pack_size_label,'')) LIKE '%syrup%'
                OR LOWER(COALESCE(pack_size_label,'')) LIKE '%ml%'
                OR LOWER(name) LIKE '%syrup%'
              )
            """
        )
        cur.execute(
            """
            UPDATE medicines SET form_type='INJECTION', qty_unit='VIALS'
            WHERE source_system <> 'reference'
              AND form_type='UNKNOWN'
              AND (
                LOWER(COALESCE(pack_size_label,'')) LIKE '%inj%'
                OR LOWER(name) LIKE '%injection%'
                OR LOWER(name) LIKE '% inj %'
              )
            """
        )
        cur.execute(
            """
            UPDATE medicines SET form_type='TABLET', qty_unit='TABLETS'
            WHERE source_system <> 'reference'
              AND form_type='UNKNOWN'
              AND (
                LOWER(COALESCE(pack_size_label,'')) LIKE '%tablet%'
                OR LOWER(name) LIKE '%tablet%'
              )
            """
        )
        cur.execute(
            """
            UPDATE medicines SET form_type='CAPSULE', qty_unit='CAPSULES'
            WHERE source_system <> 'reference'
              AND form_type='UNKNOWN'
              AND (
                LOWER(COALESCE(pack_size_label,'')) LIKE '%capsule%'
                OR LOWER(name) LIKE '%capsule%'
              )
            """
        )
        cur.execute(
            """
            UPDATE medicine_batches b
            JOIN medicines m ON m.medicine_id = b.medicine_id
            SET b.qty_unit = m.qty_unit
            WHERE b.qty_unit IS NULL AND m.source_system <> 'reference'
            """
        )

        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('schema_version', '002') "
            "ON DUPLICATE KEY UPDATE meta_value='002'"
        )
        conn.commit()
        print("Migration 002 complete.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    apply()
