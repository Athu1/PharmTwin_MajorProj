"""Seed MySQL pharmtwinai from labeled DEV synthetic Agent outputs.

Loads the full India medicines catalog (~254k) as the reference knowledge base,
then attaches stock/sales only for the active pharmacy assortment subset.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "processed"
CHUNK = 2_000


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


def _connect(
    host: str,
    user: str,
    password: str,
    database: str | None,
    port: int,
):
    try:
        import pymysql
        from pymysql.err import OperationalError
    except ImportError as e:
        raise SystemExit("Install pymysql: py -3 -m pip install pymysql") from e
    try:
        kwargs = {
            "host": host,
            "user": user,
            "password": password,
            "port": port,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        if database:
            kwargs["database"] = database
        return pymysql.connect(**kwargs)
    except OperationalError as exc:
        errno = exc.args[0] if exc.args else None
        if errno == 1045:
            raise SystemExit(
                "\nMySQL access denied (wrong user/password).\n\n"
                "Your MySQL80 service is running, but root needs a password.\n\n"
                "Fix (pick one):\n"
                "  1) Pass password on the command line:\n"
                "       py -3 scripts/seed_mysql.py --apply-schema --password YOUR_PASSWORD\n"
                "  2) Create e:\\MajorProject_4th_Yr\\Agent\\.env from .env.example and set:\n"
                "       PHARMTWIN_DB_PASSWORD=YOUR_PASSWORD\n"
                "  3) Or run without --password and type it when prompted.\n"
            ) from exc
        if errno == 1049:
            raise SystemExit(
                f"Database '{database}' does not exist yet. Re-run with --apply-schema."
            ) from exc
        raise


def _ensure_schema(cur, migration_path: Path) -> None:
    sql = migration_path.read_text(encoding="utf-8")
    for stmt in sql.split(";"):
        s = stmt.strip()
        if not s or s.startswith("--"):
            continue
        if s.upper().startswith("CREATE DATABASE") or s.upper().startswith("USE "):
            continue
        cur.execute(s)


def _chunks(seq, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _load_catalog() -> pd.DataFrame:
    parquet = DATA / "catalog_deduped.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    csv_path = DATA / "catalog_deduped.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise SystemExit(
        "Missing data/processed/catalog_deduped.parquet — run scripts/run_step1.py first"
    )


def seed(
    host: str,
    user: str,
    password: str,
    database: str,
    port: int,
    apply_schema: bool,
    date_shift: bool = True,
) -> None:
    print("Loading full catalog + assortment + ops files...")
    catalog = _load_catalog()
    assortment = pd.read_csv(DATA / "assortment_3k.csv")
    batches = pd.read_csv(
        DATA / "batches_fefo.csv", parse_dates=["receipt_date", "mfg_date", "expiry_date"]
    )
    tx_path = DATA / "transactions_synthetic.parquet"
    if tx_path.exists():
        tx = pd.read_parquet(tx_path)
    else:
        tx = pd.read_csv(DATA / "transactions_synthetic.csv", parse_dates=["date"])

    stocked_skus = {int(x) for x in assortment["sku_id"].dropna().astype(int)}

    # Demo dates: move synthetic history forward so it ends today (whole weeks)
    from services.demo_dates import compute_shift_days

    tx["date"] = pd.to_datetime(tx["date"])
    # Sales end today. Batches are a Step 1 opening-stock snapshot (receipts end
    # 2024-01-01), so they are anchored on their own last receipt instead.
    shift_days = compute_shift_days(tx["date"].max().date()) if date_shift else 0
    batch_shift_days = (
        compute_shift_days(pd.to_datetime(batches["receipt_date"]).max().date())
        if date_shift
        else 0
    )
    if shift_days:
        tx["date"] = tx["date"] + pd.Timedelta(days=shift_days)
        print(
            f"  demo dates: sales shifted +{shift_days} days -> "
            f"{tx['date'].min().date()} .. {tx['date'].max().date()}"
        )
    if batch_shift_days:
        for col in ("receipt_date", "mfg_date", "expiry_date"):
            batches[col] = pd.to_datetime(batches[col]) + pd.Timedelta(days=batch_shift_days)
        print(
            f"  demo dates: batches shifted +{batch_shift_days} days -> received "
            f"{batches['receipt_date'].min().date()} .. {batches['receipt_date'].max().date()}"
        )
    print(
        f"  catalog rows: {len(catalog):,} | "
        f"active assortment (stocked): {len(stocked_skus):,} | "
        f"batches: {len(batches):,}"
    )

    conn = _connect(host, user, password, None if apply_schema else database, port)
    cur = conn.cursor()
    try:
        if apply_schema:
            print("Applying schema migration 001...")
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cur.execute(f"USE `{database}`")
            _ensure_schema(cur, ROOT / "db" / "migrations" / "001_init_schema.sql")
            conn.commit()
        else:
            cur.execute(f"USE `{database}`")

        print("Clearing DEV tables (safe truncate order)...")
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for table in (
            "simulation_results",
            "simulation_runs",
            "digital_twin_snapshots",
            "recommendations",
            "forecasts",
            "alerts",
            "purchase_order_items",
            "purchase_orders",
            "demand_coverage",
            "sales_items",
            "sales_transactions",
            "stock_movements",
            "medicine_batches",
            "medicines",
            "medicine_categories",
            "manufacturers",
            "suppliers",
        ):
            cur.execute(f"DELETE FROM {table}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

        # Manufacturers / categories from FULL catalog (not just assortment)
        mfrs = sorted(
            {
                str(x).strip()
                for x in catalog["manufacturer_name"].fillna("UNKNOWN")
                if str(x).strip() and str(x).strip().lower() != "nan"
            }
            or {"UNKNOWN"}
        )
        cats = sorted(
            {
                str(x).strip()
                for x in catalog["Therapeutic Class"].fillna("UNKNOWN")
                if str(x).strip() and str(x).strip().lower() != "nan"
            }
            or {"UNKNOWN"}
        )
        print(f"Inserting {len(mfrs):,} manufacturers and {len(cats):,} categories...")
        mfr_id: dict[str, int] = {}
        cat_id: dict[str, int] = {}
        for name in mfrs:
            cur.execute("INSERT INTO manufacturers (name) VALUES (%s)", (name[:255],))
            mfr_id[name] = cur.lastrowid
        for name in cats:
            cur.execute("INSERT INTO medicine_categories (name) VALUES (%s)", (name[:128],))
            cat_id[name] = cur.lastrowid
        conn.commit()

        # Full catalog → medicines (reference KB); assortment SKUs tagged as stocked/ops
        print(f"Inserting {len(catalog):,} medicines (full Kaggle catalog)...")
        insert_sql = """
            INSERT INTO medicines
            (sku_code, name, manufacturer_id, category_id, pack_size_label, is_active,
             unit_mrp, demand_cohort, source_system, external_sku_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        rows = []
        sku_order: list[int] = []
        for row in catalog.itertuples(index=False):
            sku = int(row.sku_id)
            mfr = str(getattr(row, "manufacturer_name", "UNKNOWN") or "UNKNOWN").strip()
            cat = str(getattr(row, "Therapeutic Class", "UNKNOWN") or "UNKNOWN").strip()
            if not mfr or mfr.lower() == "nan":
                mfr = "UNKNOWN"
            if not cat or cat.lower() == "nan":
                cat = "UNKNOWN"
            src = "dev_synthetic" if sku in stocked_skus else "reference"
            # Stocked assortment stays active; full catalog also active for search/substitutes
            is_active = True
            price = getattr(row, "price_inr", None)
            rows.append(
                (
                    str(sku)[:64],
                    str(row.name)[:512],
                    mfr_id.get(mfr),
                    cat_id.get(cat),
                    str(getattr(row, "pack_size_label", "") or "")[:128],
                    is_active,
                    float(price) if pd.notna(price) else None,
                    str(getattr(row, "demand_cohort", "") or "")[:64],
                    src,
                    sku,
                )
            )
            sku_order.append(sku)

        sku_to_med: dict[int, int] = {}
        inserted = 0
        for chunk in _chunks(rows, CHUNK):
            cur.executemany(insert_sql, chunk)
            # Map sku → medicine_id: fetch ids for this chunk by external_sku_id
            chunk_skus = [r[9] for r in chunk]
            placeholders = ",".join(["%s"] * len(chunk_skus))
            cur.execute(
                f"SELECT medicine_id, external_sku_id FROM medicines "
                f"WHERE external_sku_id IN ({placeholders})",
                chunk_skus,
            )
            for med_id, ext in cur.fetchall():
                sku_to_med[int(ext)] = int(med_id)
            inserted += len(chunk)
            if inserted % 20_000 == 0 or inserted == len(rows):
                conn.commit()
                print(f"  medicines inserted: {inserted:,}/{len(rows):,}")
        conn.commit()
        print(f"  medicines mapped: {len(sku_to_med):,}")

        print(f"Inserting {len(batches):,} batches (assortment only)...")
        batch_map = {}
        batch_rows = []
        for row in batches.itertuples(index=False):
            mid = sku_to_med.get(int(row.sku_id))
            if mid is None:
                continue
            batch_rows.append(
                (
                    mid,
                    str(row.batch_id)[:64],
                    row.mfg_date.date() if pd.notna(row.mfg_date) else None,
                    pd.Timestamp(row.expiry_date).date(),
                    float(row.qty_remaining),
                    float(row.unit_cost),
                    pd.Timestamp(row.receipt_date).to_pydatetime()
                    if pd.notna(row.receipt_date)
                    else None,
                )
            )
        batch_sql = """
            INSERT INTO medicine_batches
            (medicine_id, batch_no, mfg_date, expiry_date, qty_on_hand, unit_cost, received_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """
        for chunk in _chunks(batch_rows, CHUNK):
            cur.executemany(batch_sql, chunk)
        conn.commit()
        cur.execute("SELECT batch_id, batch_no FROM medicine_batches")
        for bid, bno in cur.fetchall():
            batch_map[str(bno)] = bid
        print(f"  batches inserted: {len(batch_map):,}")

        print("Inserting sales (aggregated by date+sku from synthetic events)...")
        tx = tx.copy()
        tx["date"] = pd.to_datetime(tx["date"])
        n = 0
        for day, day_df in tx.groupby(tx["date"].dt.normalize()):
            cur.execute(
                "INSERT INTO sales_transactions (sold_at, channel, source_system) "
                "VALUES (%s,%s,'dev_synthetic')",
                (day.to_pydatetime(), "DEV_SYNTHETIC"),
            )
            sale_id = cur.lastrowid
            g = day_df.groupby("sku_id", as_index=False).agg(
                qty=("qty", "sum"),
                unmet_qty=("unmet_qty", "sum"),
                unit_price=("unit_price", "mean"),
            )
            item_rows = []
            move_rows = []
            for r in g.itertuples(index=False):
                mid = sku_to_med.get(int(r.sku_id))
                if mid is None:
                    continue
                item_rows.append(
                    (sale_id, mid, float(r.qty), float(r.unmet_qty), float(r.unit_price))
                )
                if float(r.qty) > 0:
                    move_rows.append(
                        (
                            mid,
                            -float(r.qty),
                            float(r.unit_price),
                            sale_id,
                            day.to_pydatetime(),
                        )
                    )
                n += 1
            if item_rows:
                cur.executemany(
                    """
                    INSERT INTO sales_items (sale_id, medicine_id, batch_id, qty, unmet_qty, unit_price)
                    VALUES (%s,%s,NULL,%s,%s,%s)
                    """,
                    item_rows,
                )
            if move_rows:
                cur.executemany(
                    """
                    INSERT INTO stock_movements
                    (medicine_id, batch_id, movement_type, qty_delta, unit_price, ref_table, ref_id, occurred_at)
                    VALUES (%s,NULL,'SALE',%s,%s,'sales_transactions',%s,%s)
                    """,
                    move_rows,
                )
        print(f"  sales_item rows: {n:,}")

        cur.execute(
            "INSERT INTO suppliers (name, lead_time_days) VALUES (%s,%s)",
            ("DEV Local Wholesaler (Navi Mumbai)", 3),
        )

        state = {
            "mode": "dev_synthetic",
            "n_catalog": len(sku_to_med),
            "n_stocked": len(stocked_skus),
            "n_medicines": len(sku_to_med),
            "n_batches": len(batch_map),
            "label": (
                "SYNTHETIC DEV DATA — not Bhagyashree Medical sales. "
                f"Full catalog knowledge base: {len(sku_to_med):,} SKUs; "
                f"pharmacy assortment with stock: {len(stocked_skus):,} SKUs."
            ),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        payload = json.dumps(state)
        # Live fingerprint (not payload hash) so Overview stale detection starts in sync
        import pymysql

        from services.twin import compute_live_fingerprint

        with conn.cursor(pymysql.cursors.DictCursor) as dcur:
            source_hash = compute_live_fingerprint(dcur)
        cur.execute(
            """
            INSERT INTO digital_twin_snapshots (synced_at, source_hash, is_stale, state_json)
            VALUES (%s,%s,0,%s)
            """,
            (datetime.utcnow(), source_hash, payload),
        )

        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('last_seed_at', %s) "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
            (datetime.utcnow().isoformat(),),
        )
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('data_mode', 'dev_synthetic') "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)"
        )
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('n_catalog', %s) "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
            (str(len(sku_to_med)),),
        )
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('n_stocked', %s) "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
            (str(len(stocked_skus)),),
        )
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('date_shift_days', %s) "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
            (str(shift_days),),
        )
        cur.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES ('batch_date_shift_days', %s) "
            "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
            (str(batch_shift_days),),
        )
        conn.commit()

        # Optional: Step 3–4 analytics if offline outputs exist
        if (DATA / "step3_forecasts_weekly.csv").exists() or (
            DATA / "step4_safety_stock_params.csv"
        ).exists():
            print("Loading Step 3–4 forecasts + recommendations...")
            from scripts.load_analytics import load_forecasts_and_recommendations

            stats = load_forecasts_and_recommendations(cur, conn)
            print(
                f"  forecasts={stats['forecasts']:,} | "
                f"recommendations={stats['recommendations']:,}"
            )

        print(
            f"Seed complete.\n"
            f"  Catalog (medicines table): {len(sku_to_med):,}\n"
            f"  Stocked assortment:        {len(stocked_skus):,}\n"
            f"  Batches:                   {len(batch_map):,}"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main() -> None:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Seed PharmTwinAI MySQL from DEV synthetic files")
    p.add_argument("--host", default=os.getenv("PHARMTWIN_DB_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("PHARMTWIN_DB_PORT", "3306")))
    p.add_argument("--user", default=os.getenv("PHARMTWIN_DB_USER", "root"))
    p.add_argument("--password", default=None, help="MySQL password (or set PHARMTWIN_DB_PASSWORD)")
    p.add_argument("--database", default=os.getenv("PHARMTWIN_DB_NAME", "pharmtwinai"))
    p.add_argument("--apply-schema", action="store_true", help="Run 001_init_schema.sql first")
    p.add_argument(
        "--no-date-shift",
        action="store_true",
        help="Keep original 2023-2024 synthetic dates (default: shift so history ends today)",
    )
    args = p.parse_args()

    if not (DATA / "assortment_3k.csv").exists():
        raise SystemExit("Missing data/processed/assortment_3k.csv — run scripts/run_step1.py first")
    if not (DATA / "catalog_deduped.parquet").exists() and not (DATA / "catalog_deduped.csv").exists():
        raise SystemExit("Missing catalog_deduped — run scripts/run_step1.py first")

    password = args.password
    if password is None:
        password = os.getenv("PHARMTWIN_DB_PASSWORD", "")
    if password == "":
        password = getpass.getpass(f"MySQL password for {args.user}@{args.host}: ")

    print(f"Connecting as {args.user}@{args.host}:{args.port} ...")
    seed(
        args.host,
        args.user,
        password,
        args.database,
        args.port,
        args.apply_schema,
        date_shift=not args.no_date_shift,
    )


if __name__ == "__main__":
    main()
