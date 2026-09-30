"""Sales-export ingest adapter: POS "Customer wise sales Report" (xlsx/csv) -> MySQL.

Built so real Bhagyashree exports can be dropped in later. Current sample files are
synthetic, so rows default to source_system='dev_synthetic' (D3).

Privacy: only an allowlist of columns is kept. Patient / doctor / mobile / address
columns and the customer-name title row are never read into staging.

Historical import writes sales_transactions / sales_items / stock_movements (SALE)
only; it does NOT change medicine_batches.qty_on_hand (live stock is owned by the
inventory module / a stock export, not replayed history).
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from services.db import get_connection

INGEST_SOURCES = ("dev_synthetic", "sponsor")

# Normalised header -> canonical column. Anything not listed here is dropped.
COLUMN_ALIASES: dict[str, str] = {
    "vouno": "vou_no",
    "voucherno": "vou_no",
    "billno": "vou_no",
    "invoiceno": "vou_no",
    "type": "txn_type",
    "paymenttype": "txn_type",
    "date": "sold_at",
    "billdate": "sold_at",
    "product": "product",
    "productname": "product",
    "item": "product",
    "unit": "unit",
    "pack": "pack",
    "comp": "company",
    "company": "company",
    "qty": "qty",
    "quantity": "qty",
    "rate": "rate",
    "amount": "amount",
    "batch": "batch_no",
    "batchno": "batch_no",
    "expiry": "expiry",
    "exp": "expiry",
    "expirydate": "expiry",
}
REQUIRED = ("vou_no", "sold_at", "product", "qty", "amount")

_FORM_WORDS = {
    "TAB", "TABS", "TABLET", "TABLETS", "CAP", "CAPS", "CAPSULE", "CAPSULES",
    "SYP", "SYRUP", "SUSP", "SUSPENSION", "DROP", "DROPS", "INJ", "INJECTION",
    "CREAM", "GEL", "OINT", "OINTMENT", "S", "T", "DT",
}


def _norm_header(h: Any) -> str:
    return re.sub(r"[^a-z]", "", str(h).lower())


def normalize_product_name(name: str) -> str:
    """'PAN 20* TAB' / 'Pan 20mg Tablet' -> 'PAN 20' for matching."""
    s = str(name or "").upper()
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(MG|MCG|ML|GM|G|IU)\b", r"\1", s)
    tokens = [t for t in re.split(r"[^A-Z0-9.]+", s) if t and t not in _FORM_WORDS]
    return " ".join(tokens)


def parse_expiry(val: Any) -> date | None:
    """'12/27' (MM/YY) -> 2027-12-31; also accepts real dates."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
    m = re.fullmatch(r"\s*(\d{1,2})\s*[/-]\s*(\d{2}|\d{4})\s*", str(val))
    if not m:
        return None
    month, year = int(m.group(1)), int(m.group(2))
    if year < 100:
        year += 2000
    if not 1 <= month <= 12:
        return None
    return date(year, month, calendar.monthrange(year, month)[1])


def _find_header_row(raw: pd.DataFrame, scan: int = 15) -> int:
    for i in range(min(scan, len(raw))):
        cells = {_norm_header(c) for c in raw.iloc[i].tolist() if pd.notna(c)}
        if "product" in cells and ("vouno" in cells or "qty" in cells):
            return i
    raise ValueError("Header row not found (expected columns like Vou.No., Product, Qty.)")


def read_export(path: str | Path) -> pd.DataFrame:
    """Read one export into canonical staging columns (PII columns dropped)."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, header=None, dtype=object)
    else:
        raw = pd.read_csv(path, header=None, dtype=object)
    h = _find_header_row(raw)
    keep: dict[int, str] = {}
    for idx, col in enumerate(raw.iloc[h].tolist()):
        canon = COLUMN_ALIASES.get(_norm_header(col))
        if canon and canon not in keep.values():
            keep[idx] = canon
    missing = [c for c in REQUIRED if c not in keep.values()]
    if missing:
        raise ValueError(f"{path.name}: missing required columns {missing}")
    df = raw.iloc[h + 1 :, list(keep)].copy()
    df.columns = [keep[i] for i in keep]
    df["source_file"] = path.name
    df["source_row"] = df.index + 1  # 1-based spreadsheet row
    return df.reset_index(drop=True)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split staging rows into (valid, rejects[reason])."""
    df = df.copy()
    # Footer / blank rows ("Total" line, empty spacer rows)
    blank = df["product"].isna() & df["vou_no"].isna()
    df = df[~blank]
    df["product"] = df["product"].astype(str).str.strip()
    df["sold_at"] = pd.to_datetime(df["sold_at"], errors="coerce")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["expiry_date"] = df["expiry"].map(parse_expiry) if "expiry" in df else None
    df["vou_no"] = df["vou_no"].map(
        lambda v: str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()
    )
    if "txn_type" in df:
        df["txn_type"] = df["txn_type"].fillna("").astype(str).str.strip().str.upper()
    else:
        df["txn_type"] = ""

    reason = pd.Series("", index=df.index)
    reason[df["product"].isin(["", "nan", "None"])] = "missing product"
    reason[(reason == "") & df["sold_at"].isna()] = "bad date"
    reason[(reason == "") & ~(df["qty"] > 0)] = "qty must be > 0"
    reason[(reason == "") & ~(df["amount"] >= 0)] = "bad amount"
    if "expiry" in df:
        bad_exp = df["expiry"].notna() & df["expiry_date"].isna()
        reason[(reason == "") & bad_exp] = "unparseable expiry"
    rejects = df[reason != ""].assign(reject_reason=reason[reason != ""])
    valid = df[reason == ""].copy()
    valid["unit_price"] = (valid["amount"] / valid["qty"]).round(2)
    valid["norm_name"] = valid["product"].map(normalize_product_name)
    return valid, rejects


def _voucher_key(r: pd.Series) -> str:
    raw = f"{r['txn_type']}|{r['vou_no']}|{r['sold_at'].date().isoformat()}"
    return "export:" + hashlib.sha1(raw.encode()).hexdigest()[:24]  # fits channel(32)


def _name_index(cur, where: str) -> dict[str, int]:
    cur.execute(f"SELECT medicine_id, name FROM medicines WHERE {where} ORDER BY medicine_id")
    idx: dict[str, int] = {}
    for r in cur.fetchall():
        idx.setdefault(normalize_product_name(r["name"]), int(r["medicine_id"]))
    return idx


def match_products(cur, norm_names: set[str]) -> dict[str, dict[str, Any]]:
    """norm_name -> {'status': working|reference|unmatched, 'medicine_id': ...}."""
    working = _name_index(
        cur, "source_system IN ('dev_synthetic','pharmacy','sponsor') AND is_active = 1"
    )
    reference = _name_index(cur, "source_system='reference'")
    out: dict[str, dict[str, Any]] = {}
    for n in norm_names:
        if n in working:
            out[n] = {"status": "working", "medicine_id": working[n]}
        elif n in reference:
            out[n] = {"status": "reference", "medicine_id": reference[n]}
        else:
            out[n] = {"status": "unmatched", "medicine_id": None}
    return out


def _create_working_medicine(
    cur, product: str, source_system: str, clone_from: int | None
) -> int:
    """Insert a working-inventory row (never touches the reference row)."""
    src: dict[str, Any] = {}
    if clone_from is not None:
        cur.execute(
            "SELECT manufacturer_id, category_id, pack_size_label, unit_mrp, "
            "form_type, qty_unit FROM medicines WHERE medicine_id=%s",
            (clone_from,),
        )
        src = cur.fetchone() or {}
    cur.execute(
        """
        INSERT INTO medicines
        (name, manufacturer_id, category_id, pack_size_label, form_type, qty_unit,
         is_active, unit_mrp, source_system, cloned_from_medicine_id)
        VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s)
        """,
        (
            product[:512],
            src.get("manufacturer_id"),
            src.get("category_id"),
            src.get("pack_size_label"),
            src.get("form_type") or "UNKNOWN",
            src.get("qty_unit") or "UNITS",
            src.get("unit_mrp"),
            source_system,
            clone_from,
        ),
    )
    med_id = int(cur.lastrowid)
    cur.execute(
        "UPDATE medicines SET sku_code=%s WHERE medicine_id=%s",
        (f"IMP-{med_id}", med_id),
    )
    cur.execute(
        "INSERT INTO inventory_audit (action_type, medicine_id, batch_id, detail_json) "
        "VALUES ('ADD_MEDICINE',%s,NULL,%s)",
        (
            med_id,
            json.dumps(
                {
                    "via": "sales_ingest",
                    "name": product,
                    "source_system": source_system,
                    "cloned_from_medicine_id": clone_from,
                    "immutable_catalog_untouched": True,
                }
            ),
        ),
    )
    return med_id


def ingest(
    paths: list[Path],
    *,
    source_system: str = "dev_synthetic",
    commit: bool = False,
    create_missing: bool = False,
) -> dict[str, Any]:
    """
    Read + validate + match + (optionally) write. Dry-run unless commit=True.
    create_missing: add working-inventory rows for products found only in the
    reference catalog (cloned) or not found at all.
    """
    if source_system not in INGEST_SOURCES:
        raise ValueError(f"source_system must be one of {INGEST_SOURCES}")
    frames, file_errors = [], []
    for p in paths:
        try:
            frames.append(read_export(p))
        except Exception as exc:  # noqa: BLE001
            file_errors.append(f"{Path(p).name}: {exc}")
    if not frames:
        return {"ok": False, "file_errors": file_errors, "n_rows": 0}
    staging = pd.concat(frames, ignore_index=True)
    valid, rejects = validate(staging)
    valid["voucher_key"] = valid.apply(_voucher_key, axis=1) if len(valid) else []

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            matches = match_products(cur, set(valid["norm_name"]))
            valid["match_status"] = valid["norm_name"].map(lambda n: matches[n]["status"])

            keys = sorted(set(valid["voucher_key"]))
            existing: set[str] = set()
            for i in range(0, len(keys), 500):
                chunk = keys[i : i + 500]
                cur.execute(
                    "SELECT channel FROM sales_transactions WHERE channel IN ("
                    + ",".join(["%s"] * len(chunk))
                    + ")",
                    chunk,
                )
                existing |= {r["channel"] for r in cur.fetchall()}

            summary: dict[str, Any] = {
                "ok": True,
                "committed": False,
                "source_system": source_system,
                "files": len(frames),
                "file_errors": file_errors,
                "n_rows": int(len(staging)),
                "n_valid": int(len(valid)),
                "n_rejected": int(len(rejects)),
                "n_vouchers": len(keys),
                "n_vouchers_already_loaded": len(existing),
                "match_counts": valid["match_status"].value_counts().to_dict(),
                "rejects": rejects,
                "staging": valid,
            }
            if not commit:
                return summary

            resolved: dict[str, int] = {}
            n_created = 0
            for n, m in matches.items():
                if m["status"] == "working":
                    resolved[n] = m["medicine_id"]
                elif create_missing:
                    product = valid.loc[valid["norm_name"] == n, "product"].iloc[0]
                    resolved[n] = _create_working_medicine(
                        cur, product, source_system, m["medicine_id"]
                    )
                    n_created += 1

            n_sales = n_items = n_skipped_rows = 0
            for key, g in valid.groupby("voucher_key", sort=False):
                if key in existing:
                    continue
                g = g[g["norm_name"].isin(resolved)]
                if g.empty:
                    continue
                cur.execute(
                    "INSERT INTO sales_transactions (sold_at, channel, source_system) "
                    "VALUES (%s,%s,%s)",
                    (g["sold_at"].iloc[0].to_pydatetime(), key, source_system),
                )
                sale_id = int(cur.lastrowid)
                n_sales += 1
                for r in g.itertuples(index=False):
                    mid = resolved[r.norm_name]
                    batch_id = None
                    bno = getattr(r, "batch_no", None)
                    if bno is not None and pd.notna(bno):
                        cur.execute(
                            "SELECT batch_id FROM medicine_batches "
                            "WHERE medicine_id=%s AND batch_no=%s",
                            (mid, str(bno).strip()[:64]),
                        )
                        b = cur.fetchone()
                        batch_id = int(b["batch_id"]) if b else None
                    cur.execute(
                        "INSERT INTO sales_items "
                        "(sale_id, medicine_id, batch_id, qty, unmet_qty, unit_price) "
                        "VALUES (%s,%s,%s,%s,0,%s)",
                        (sale_id, mid, batch_id, float(r.qty), float(r.unit_price)),
                    )
                    cur.execute(
                        """
                        INSERT INTO stock_movements
                        (medicine_id, batch_id, movement_type, qty_delta, unit_price,
                         ref_table, ref_id, occurred_at)
                        VALUES (%s,%s,'SALE',%s,%s,'sales_transactions',%s,%s)
                        """,
                        (
                            mid,
                            batch_id,
                            -float(r.qty),
                            float(r.unit_price),
                            sale_id,
                            r.sold_at.to_pydatetime(),
                        ),
                    )
                    n_items += 1
            n_skipped_rows = int((~valid["norm_name"].isin(resolved)).sum())
        conn.commit()
        summary.update(
            {
                "committed": True,
                "n_medicines_created": n_created,
                "n_sales_written": n_sales,
                "n_items_written": n_items,
                "n_rows_skipped_unresolved": n_skipped_rows,
            }
        )
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
