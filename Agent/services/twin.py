"""Digital twin summary + snapshot sync / stale detection against MySQL."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from services.db import get_connection

SYNTHETIC_LABEL = "SYNTHETIC DEV DATA — not Bhagyashree Medical sales"


def compute_live_fingerprint(cur) -> str:
    """
    sha256 over live inventory/sales state. Any inventory CRUD (audit row),
    lot qty change, sale or stock movement changes the fingerprint.
    """
    parts: list[str] = []
    cur.execute(
        "SELECT source_system, COUNT(*) AS n FROM medicines "
        "GROUP BY source_system ORDER BY source_system"
    )
    parts += [f"med:{r['source_system']}={int(r['n'])}" for r in cur.fetchall()]
    cur.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches"
    )
    b = cur.fetchone()
    parts.append(f"batches={int(b['n'])}:{float(b['q']):.3f}")
    for table, col in (
        ("inventory_audit", "audit_id"),
        ("sales_transactions", "sale_id"),
        ("stock_movements", "movement_id"),
    ):
        try:
            cur.execute(f"SELECT COALESCE(MAX({col}),0) AS m FROM {table}")
            parts.append(f"{table}={int(cur.fetchone()['m'])}")
        except Exception:  # noqa: BLE001 — e.g. inventory_audit before migration 002
            parts.append(f"{table}=na")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _latest_snapshot(cur) -> dict | None:
    cur.execute(
        "SELECT snapshot_id, synced_at, source_hash, is_stale, state_json "
        "FROM digital_twin_snapshots ORDER BY snapshot_id DESC LIMIT 1"
    )
    return cur.fetchone()


def _check_stale(cur) -> dict:
    snap = _latest_snapshot(cur)
    if not snap:
        return {"is_stale": True, "synced_at": None, "snapshot_id": None}
    stale = bool(snap["is_stale"]) or snap["source_hash"] != compute_live_fingerprint(cur)
    if stale and not snap["is_stale"]:
        cur.execute(
            "UPDATE digital_twin_snapshots SET is_stale=1 WHERE snapshot_id=%s",
            (snap["snapshot_id"],),
        )
    return {
        "is_stale": stale,
        "synced_at": str(snap["synced_at"]),
        "snapshot_id": int(snap["snapshot_id"]),
    }


def check_twin_stale() -> dict:
    """Mark latest snapshot stale if live inventory/sales changed since its sync."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            out = _check_stale(cur)
        conn.commit()
        return out
    finally:
        conn.close()


def refresh_twin_snapshot() -> dict:
    """Write a new snapshot from live tables (is_stale=0)."""
    summary = build_live_summary(check_stale=False)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT meta_value FROM app_meta WHERE meta_key='data_mode'")
            row = cur.fetchone()
            mode = row["meta_value"] if row else "dev_synthetic"
            label = summary["label"]
            if mode == "dev_synthetic" and "SYNTHETIC" not in label.upper():
                label = f"{SYNTHETIC_LABEL}. {label}"
            now = datetime.utcnow()
            state = {
                "mode": mode,
                "n_catalog": summary["n_catalog"],
                "n_stocked": summary["n_stocked"],
                "n_medicines": summary["n_catalog"],
                "n_batches": summary["n_batches"],
                "on_hand_units": summary["on_hand_units"],
                "label": label,
                "generated_at": now.isoformat() + "Z",
            }
            source_hash = compute_live_fingerprint(cur)
            cur.execute(
                """
                INSERT INTO digital_twin_snapshots (synced_at, source_hash, is_stale, state_json)
                VALUES (%s,%s,0,%s)
                """,
                (now, source_hash, json.dumps(state)),
            )
            snapshot_id = int(cur.lastrowid)
        conn.commit()
        return {"snapshot_id": snapshot_id, "synced_at": str(now), "is_stale": False}
    finally:
        conn.close()


def build_live_summary(check_stale: bool = True) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM medicines")
            n_catalog = cur.fetchone()["n"]
            cur.execute(
                "SELECT COUNT(*) AS n FROM medicines WHERE source_system IN "
                "('dev_synthetic','pharmacy','sponsor')"
            )
            n_stocked = cur.fetchone()["n"]
            cur.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches"
            )
            b = cur.fetchone()
            snap = _latest_snapshot(cur)
            stale = _check_stale(cur)["is_stale"] if check_stale else None
        if check_stale:
            conn.commit()
        label = SYNTHETIC_LABEL
        synced = None
        if snap:
            synced = str(snap["synced_at"])
            state = snap["state_json"]
            if isinstance(state, dict):
                label = state.get("label", label)
            elif isinstance(state, str):
                try:
                    parsed = json.loads(state)
                    if isinstance(parsed, dict):
                        label = parsed.get("label", label)
                except Exception:  # noqa: BLE001
                    pass
        return {
            "n_catalog": int(n_catalog),
            "n_stocked": int(n_stocked),
            "n_medicines": int(n_catalog),  # backward-compatible alias
            "n_batches": int(b["n"]),
            "on_hand_units": float(b["q"]),
            "synced_at": synced,
            "is_stale": stale,
            "label": label,
        }
    finally:
        conn.close()
