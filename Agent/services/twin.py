"""Digital twin summary helpers (read-only against MySQL)."""

from __future__ import annotations

from services.db import get_connection


def build_live_summary() -> dict:
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
            cur.execute(
                "SELECT synced_at, state_json FROM digital_twin_snapshots "
                "ORDER BY snapshot_id DESC LIMIT 1"
            )
            snap = cur.fetchone()
        label = "SYNTHETIC DEV DATA — not Bhagyashree Medical sales"
        synced = None
        if snap:
            synced = str(snap["synced_at"])
            state = snap["state_json"]
            if isinstance(state, dict):
                label = state.get("label", label)
            elif isinstance(state, str):
                try:
                    import json

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
            "label": label,
        }
    finally:
        conn.close()
