"""Load Step 2–4 offline analytics into MySQL (forecasts + recommendations).

Safe to run after seed without reloading the 254k catalog.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timedelta
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


def _chunks(seq, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _sku_map(cur) -> dict[int, int]:
    cur.execute(
        "SELECT external_sku_id, medicine_id FROM medicines "
        "WHERE external_sku_id IS NOT NULL"
    )
    return {int(sku): int(mid) for sku, mid in cur.fetchall()}


def _stock_by_sku(cur) -> dict[int, float]:
    from services.recommendations import SELLABLE_QTY_SQL

    cur.execute(
        f"""
        SELECT m.external_sku_id AS sku_id, {SELLABLE_QTY_SQL} AS qty
        FROM medicines m
        LEFT JOIN medicine_batches b ON b.medicine_id = m.medicine_id
        WHERE m.source_system = 'dev_synthetic' AND m.external_sku_id IS NOT NULL
        GROUP BY m.external_sku_id
        """
    )
    return {int(r[0]): float(r[1]) for r in cur.fetchall()}


def _cover_window_params() -> "pd.DataFrame | None":
    """Reorder parameters from the Step 3c cover-window model, if it has been run.

    More correct than the Step 4 defaults: quantiles do not add, so (mean weekly q50)
    x (L+R) is not the median of the L+R week total. The cover model estimates that
    total directly. See docs/model_card.md.
    """
    cover_path = DATA / "step3c_cover_forecasts.csv"
    ss_path = DATA / "step4_safety_stock_params.csv"
    if not cover_path.exists() or not ss_path.exists():
        return None
    from src.safety_stock import sku_params_from_cover_forecasts

    cover = pd.read_csv(cover_path, parse_dates=["week_start"])
    params = sku_params_from_cover_forecasts(cover)
    # Carry over the descriptive columns the recommendation text needs
    base = pd.read_csv(ss_path)
    meta_cols = [
        c
        for c in ("sku_id", "name", "price_inr", "demand_cohort", "Therapeutic Class")
        if c in base.columns
    ]
    return params.merge(base[meta_cols], on="sku_id", how="left")


def load_forecasts_and_recommendations(cur, conn, use_cover_params: bool = False) -> dict[str, int]:
    """Insert Step-3 weekly forecasts and Step-4 reorder recommendations."""
    sku_to_med = _sku_map(cur)
    stock = _stock_by_sku(cur)
    stats = {"forecasts": 0, "recommendations": 0, "skipped_sku": 0}

    fc_path = DATA / "step3_forecasts_weekly.parquet"
    if not fc_path.exists():
        fc_path = DATA / "step3_forecasts_weekly.csv"
    if not fc_path.exists():
        print("  skip forecasts — missing step3_forecasts_weekly.(parquet|csv)")
    else:
        print("Clearing forecasts table...")
        cur.execute("DELETE FROM forecasts")
        fc = (
            pd.read_parquet(fc_path)
            if fc_path.suffix == ".parquet"
            else pd.read_csv(fc_path, parse_dates=["week_start"])
        )
        fc["week_start"] = pd.to_datetime(fc["week_start"])
        # Same whole-week offset the seed applied to sales/batches (0 if none)
        from services.demo_dates import read_shift_days

        shift = read_shift_days(cur)
        if shift:
            fc["week_start"] = fc["week_start"] + pd.Timedelta(days=shift)
            print(f"  forecast weeks shifted by {shift} days (demo dates)")
        if "method" in fc.columns:
            preferred = fc[fc["method"].astype(str) == "lgbm_env"]
            if len(preferred):
                fc = preferred
        metrics_path = DATA / "step3_summary.json"
        metrics_blob = None
        if metrics_path.exists():
            metrics_blob = json.loads(metrics_path.read_text(encoding="utf-8"))
            # keep compact: global metrics only
            metrics_blob = {
                "global": metrics_blob.get("metrics_all", [])[:3],
                "notes": metrics_blob.get("notes"),
            }
        trained_through = (fc["week_start"].min() - pd.Timedelta(days=7)).date()
        rows = []
        for r in fc.itertuples(index=False):
            mid = sku_to_med.get(int(r.sku_id))
            if mid is None:
                stats["skipped_sku"] += 1
                continue
            start = pd.Timestamp(r.week_start).date()
            end = start + timedelta(days=6)
            yhat = float(getattr(r, "forecast", getattr(r, "q50", 0)) or 0)
            q50 = float(getattr(r, "q50", yhat) or yhat)
            q95 = float(getattr(r, "q95", yhat) or yhat)
            method = str(getattr(r, "method", "lgbm_env"))[:64]
            rows.append(
                (
                    mid,
                    "W",
                    start,
                    end,
                    yhat,
                    q50,
                    q95,
                    method,
                    trained_through,
                    json.dumps(
                        {
                            "actual": float(getattr(r, "actual", 0) or 0),
                            "q90": float(getattr(r, "q90", 0) or 0),
                            "demand_cohort": str(getattr(r, "demand_cohort", "") or ""),
                        }
                    ),
                )
            )
        sql = """
            INSERT INTO forecasts
            (medicine_id, grain, horizon_start, horizon_end, yhat, yhat_lower, yhat_upper,
             model_name, trained_through, metrics_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        print(f"Inserting {len(rows):,} forecast rows (Step 3 LightGBM)...")
        for chunk in _chunks(rows, CHUNK):
            cur.executemany(sql, chunk)
        conn.commit()
        stats["forecasts"] = len(rows)
        if metrics_blob:
            compact = json.dumps(
                {
                    "global_wmape_lgbm_env": (
                        metrics_blob.get("global", [{}])[0].get("global_wmape")
                        if metrics_blob.get("global")
                        else None
                    ),
                    "notes": (metrics_blob.get("notes") or "")[:400],
                }
            )
            cur.execute(
                "INSERT INTO app_meta (meta_key, meta_value) VALUES ('step3_metrics', %s) "
                "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
                (compact[:500],),
            )

    ss_path = DATA / "step4_safety_stock_params.csv"
    cover_params = _cover_window_params() if use_cover_params else None
    if cover_params is not None:
        print(f"Using Step 3c cover-window reorder parameters ({len(cover_params):,} SKUs)")
    elif use_cover_params:
        print("  --use-cover-params asked for, but step3c_cover_forecasts.csv is missing")
    if not ss_path.exists():
        print(f"  skip recommendations — missing {ss_path.name}")
    else:
        print("Clearing recommendations table...")
        cur.execute("DELETE FROM recommendations")
        ss = cover_params if cover_params is not None else pd.read_csv(ss_path)
        from services.recommendations import build_explanation, decide_action

        rows = []
        for r in ss.itertuples(index=False):
            sku = int(r.sku_id)
            mid = sku_to_med.get(sku)
            if mid is None:
                stats["skipped_sku"] += 1
                continue
            current = float(stock.get(sku, 0.0))
            rop = float(r.reorder_point)
            ss_qty = float(r.safety_stock)
            mu = float(r.mu_weekly)
            cover = float(r.lead_time_weeks) + float(r.review_period_weeks)
            forecast_demand = mu * cover
            order_up = float(r.order_up_to)
            name = str(getattr(r, "name", f"SKU {sku}"))
            action, qty = decide_action(current, rop, order_up)
            assumptions = {
                "sku_id": sku,
                "lead_time_weeks": float(r.lead_time_weeks),
                "review_period_weeks": float(r.review_period_weeks),
                "service_level": float(r.service_level),
                "z_score": float(r.z_score),
                "sigma_weekly": float(r.sigma_weekly),
                "order_up_to": order_up,
                "demand_cohort": str(getattr(r, "demand_cohort", "") or ""),
                "formula": "SS = Z * sigma_LT * sqrt(L + R)",
                "source": (
                    "step3c_cover_window" if cover_params is not None
                    else "step4_safety_stock_params"
                ),
            }
            explanation = build_explanation(
                action, name, current, rop, ss_qty, assumptions, mu, forecast_demand
            )
            rows.append(
                (
                    mid,
                    action,
                    qty,
                    current,
                    forecast_demand,
                    0.0,
                    ss_qty,
                    rop,
                    explanation,
                    json.dumps(assumptions),
                )
            )
        sql = """
            INSERT INTO recommendations
            (medicine_id, action_type, qty_suggested, current_stock, forecast_demand,
             incoming_po_qty, safety_stock, reorder_point, explanation_text, assumptions_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        print(f"Inserting {len(rows):,} recommendation rows (Step 4 SS/ROP)...")
        for chunk in _chunks(rows, CHUNK):
            cur.executemany(sql, chunk)
        conn.commit()
        stats["recommendations"] = len(rows)

    cur.execute(
        "INSERT INTO app_meta (meta_key, meta_value) VALUES ('last_analytics_at', %s) "
        "ON DUPLICATE KEY UPDATE meta_value=VALUES(meta_value)",
        (datetime.utcnow().isoformat(),),
    )
    conn.commit()
    return stats


def main() -> None:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Load forecasts + recommendations into MySQL")
    p.add_argument("--host", default=os.getenv("PHARMTWIN_DB_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("PHARMTWIN_DB_PORT", "3306")))
    p.add_argument("--user", default=os.getenv("PHARMTWIN_DB_USER", "root"))
    p.add_argument("--password", default=None)
    p.add_argument("--database", default=os.getenv("PHARMTWIN_DB_NAME", "pharmtwinai"))
    p.add_argument(
        "--use-cover-params",
        action="store_true",
        help="Reorder points from the Step 3c cover-window model instead of the Step 4 "
        "flat average (run scripts/run_step3c.py first)",
    )
    args = p.parse_args()

    password = args.password if args.password is not None else os.getenv("PHARMTWIN_DB_PASSWORD", "")
    if password == "":
        password = getpass.getpass(f"MySQL password for {args.user}@{args.host}: ")

    import pymysql

    conn = pymysql.connect(
        host=args.host,
        user=args.user,
        password=password,
        database=args.database,
        port=args.port,
        charset="utf8mb4",
        autocommit=False,
    )
    cur = conn.cursor()
    try:
        print("Loading analytics into MySQL...")
        stats = load_forecasts_and_recommendations(
            cur, conn, use_cover_params=args.use_cover_params
        )
        print(
            f"Done. forecasts={stats['forecasts']:,} | "
            f"recommendations={stats['recommendations']:,} | "
            f"skipped_sku_refs={stats['skipped_sku']:,}"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
