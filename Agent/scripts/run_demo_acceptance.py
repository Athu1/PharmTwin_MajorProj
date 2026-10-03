"""PharmTwinAI core acceptance / demo checklist (TEST-01).

Run after MySQL is seeded and analytics loaded:
  py -3 scripts/run_demo_acceptance.py

Exit code 0 = all required checks passed.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "processed"


@dataclass
class CheckResult:
    id: str
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, *args, **kwargs) -> None:
        self.results.append(CheckResult(*args, **kwargs))

    @property
    def failed_required(self) -> list[CheckResult]:
        return [r for r in self.results if r.required and not r.ok]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)


def _check_db(report: Report) -> None:
    from services.db import get_connection, probe_database

    ok, msg = probe_database()
    report.add("A01", "MySQL connection", ok, msg)
    if not ok:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM medicines")
            n_cat = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT COUNT(*) AS n FROM medicines WHERE source_system IN "
                "('dev_synthetic','pharmacy','sponsor')"
            )
            n_stock = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT COUNT(*) AS n FROM medicines WHERE source_system='reference'"
            )
            n_ref = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM medicine_batches")
            n_batch = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT COALESCE(SUM(qty_on_hand),0) AS q FROM medicine_batches"
            )
            on_hand = float(cur.fetchone()["q"])
            cur.execute("SELECT COUNT(*) AS n FROM sales_transactions")
            n_sales = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM forecasts")
            n_fc = int(cur.fetchone()["n"])
            cur.execute("SELECT COUNT(*) AS n FROM recommendations")
            n_rec = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT COUNT(*) AS n FROM digital_twin_snapshots"
            )
            n_snap = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT meta_value FROM app_meta WHERE meta_key='data_mode'"
            )
            row = cur.fetchone()
            data_mode = row["meta_value"] if row else ""
    finally:
        conn.close()

    report.add(
        "A02",
        "Full catalog knowledge base (~254k)",
        n_cat >= 250_000,
        f"medicines={n_cat:,} (reference={n_ref:,}, stocked={n_stock:,})",
    )
    report.add(
        "A03",
        "Stocked pharmacy assortment",
        n_stock >= 500,
        f"stocked SKUs={n_stock:,} (target 3000 after expansion)",
        required=True,
    )
    report.add(
        "A03b",
        "Stocked assortment at demo scale (>=3000)",
        n_stock >= 3000,
        f"stocked SKUs={n_stock:,}",
        required=False,
    )
    report.add(
        "A04",
        "FEFO batches present",
        n_batch > 0 and on_hand > 0,
        f"batches={n_batch:,}, on_hand={on_hand:,.0f}",
    )
    report.add(
        "A05",
        "Synthetic sales loaded",
        n_sales > 0,
        f"sales_transactions={n_sales:,}",
    )
    report.add(
        "A06",
        "Digital twin snapshot exists",
        n_snap > 0,
        f"snapshots={n_snap}",
    )
    report.add(
        "A07",
        "Data labeled DEV synthetic",
        data_mode == "dev_synthetic",
        f"data_mode={data_mode!r}",
    )
    report.add(
        "A08",
        "Forecasts table populated (Step 3)",
        n_fc > 0,
        f"forecast rows={n_fc:,}",
    )
    report.add(
        "A09",
        "Recommendations table populated (Step 4)",
        n_rec > 0,
        f"recommendation rows={n_rec:,}",
    )


def _check_services(report: Report) -> None:
    from services.alerts import compute_live_alerts
    from services.forecasts import forecast_counts, list_forecast_summary
    from services.inventory import list_stocked_medicines
    from services.recommendations import list_recommendations, recommendation_counts
    from services.substitutes import list_query_medicines, recommend_for_sku
    from services.twin import build_live_summary

    try:
        summary = build_live_summary()
        report.add(
            "B01",
            "Twin live summary",
            summary.get("n_catalog", 0) > 0,
            f"catalog={summary.get('n_catalog')}, stocked={summary.get('n_stocked')}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("B01", "Twin live summary", False, str(exc))

    try:
        inv = list_stocked_medicines(limit=5)
        report.add(
            "B02",
            "Inventory service",
            len(inv) > 0,
            f"sample={inv[0]['name'] if inv else 'none'}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("B02", "Inventory service", False, str(exc))

    try:
        alerts = compute_live_alerts(limit=20)
        report.add(
            "B03",
            "Alerts service (expiry/low stock)",
            len(alerts) > 0,
            f"n_alerts={len(alerts)}, first={alerts[0]['alert_type'] if alerts else '-'}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("B03", "Alerts service", False, str(exc))

    try:
        fc = forecast_counts()
        sample = list_forecast_summary(limit=1)
        report.add(
            "B04",
            "Forecasts service",
            fc.get("n_rows", 0) > 0 and len(sample) > 0,
            f"rows={fc.get('n_rows')}, models={fc.get('models')}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("B04", "Forecasts service", False, str(exc))

    try:
        counts = recommendation_counts()
        recs = list_recommendations(action="REORDER", limit=3)
        report.add(
            "B05",
            "Recommendations service + explanations",
            counts.get("ALL", 0) > 0
            and (not recs or "SS =" in (recs[0].get("explanation_text") or "")),
            f"counts={counts}, reorder_sample={len(recs)}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("B05", "Recommendations service", False, str(exc))

    try:
        queries = list_query_medicines(limit=5)
        if not queries:
            report.add("B06", "Substitutes service", False, "no stocked query SKUs")
        else:
            out = recommend_for_sku(int(queries[0]["sku_id"]), top_n=3)
            ok = bool(out.get("ok")) and (
                out.get("h1_blocked") or out.get("n_allowed", 0) >= 0
            )
            report.add(
                "B06",
                "Substitutes (H1/AWaRe/CDSCO gated)",
                ok,
                f"sku={queries[0]['sku_id']}, h1={out.get('h1_blocked')}, "
                f"allowed={out.get('n_allowed')}",
            )
    except Exception as exc:  # noqa: BLE001
        report.add("B06", "Substitutes service", False, str(exc))


def _check_sim_isolation(report: Report) -> None:
    from services.simulations import (
        get_run_results,
        import_cached_step4,
        list_simulation_runs,
        verify_live_stock_untouched,
    )

    before = verify_live_stock_untouched()
    try:
        # Prefer existing run; else import cached Step 4
        runs = list_simulation_runs(limit=1)
        if not runs:
            if not (DATA / "step4_policy_comparison.csv").exists():
                report.add(
                    "C01",
                    "Simulation isolation (cached Step 4)",
                    False,
                    "No runs and missing step4_policy_comparison.csv",
                )
                return
            out = import_cached_step4()
            run_id = out["run_id"]
        else:
            run_id = int(runs[0]["run_id"])
        after = verify_live_stock_untouched(before["fingerprint"])
        results = get_run_results(run_id)
        report.add(
            "C01",
            "Simulation does not mutate live stock",
            after["unchanged"] and len(results) > 0,
            f"run_id={run_id}, unchanged={after['unchanged']}, "
            f"fingerprint={after['fingerprint']}, n_policy_rows={len(results)}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("C01", "Simulation isolation", False, str(exc))


def _check_inventory_crud(report: Report) -> None:
    """F01–F03: working-inventory CRUD, reference immutability, twin stale flag.

    Writes a temporary pharmacy medicine and removes it again (self-cleaning).
    """
    from services.db import get_connection
    from services.inventory_write import (
        InventoryGuardError,
        add_medicine_with_lot,
        remove_medicine,
        search_reference_catalog,
        update_medicine,
    )
    from services.twin import check_twin_stale, refresh_twin_snapshot

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

    added_id: int | None = None
    stale_steps: list[bool] = []
    try:
        n_ref = ref_count()
        refs = search_reference_catalog("paracetamol", limit=1) or search_reference_catalog(
            "a", limit=1
        )
        refresh_twin_snapshot()
        stale_steps.append(check_twin_stale()["is_stale"])  # expect False

        out = add_medicine_with_lot(
            name="ACCEPTANCE TEMP SKU (auto-removed)",
            form_type="TABLET",
            qty_unit="TABLETS",
            quantity=10,
            mfg_date="2025-01-01",
            expiry_date="2027-12-31",
            clone_from_medicine_id=int(refs[0]["medicine_id"]) if refs else None,
        )
        added_id = int(out["medicine_id"])

        # F04: edit details; unit change refused while stock exists; reference edit refused
        edit = update_medicine(
            added_id, name="ACCEPTANCE TEMP SKU (edited)", form_type="TABLET",
            qty_unit="TABLETS", manufacturer_name="Acceptance Labs", unit_mrp=12.5,
        )
        unit_blocked = ref_blocked = False
        try:
            update_medicine(added_id, name="x", form_type="SYRUP", qty_unit="ML")
        except InventoryGuardError:
            unit_blocked = True
        if refs:
            try:
                update_medicine(int(refs[0]["medicine_id"]), name="x", form_type="TABLET",
                                qty_unit="TABLETS")
            except InventoryGuardError:
                ref_blocked = True
        report.add(
            "F04",
            "Edit medicine details (audited); unit locked with stock; reference read-only",
            set(edit["changes"]) == {"name", "manufacturer", "unit_mrp"}
            and unit_blocked and ref_blocked,
            f"changed={sorted(edit['changes'])}, unit_blocked={unit_blocked}, "
            f"reference_blocked={ref_blocked}",
        )

        remove_medicine(added_id)
        added_id = None
        stale_steps.append(check_twin_stale()["is_stale"])  # expect True

        n_ref_after = ref_count()
        report.add(
            "F01",
            "Inventory add/remove leaves reference catalog unchanged",
            n_ref_after == n_ref,
            f"reference before={n_ref:,}, after={n_ref_after:,}",
        )

        if not refs:
            report.add("F02", "Reference catalog delete blocked", False, "no reference rows")
        else:
            try:
                remove_medicine(int(refs[0]["medicine_id"]))
                report.add(
                    "F02", "Reference catalog delete blocked", False, "delete was allowed!"
                )
            except InventoryGuardError as exc:
                report.add("F02", "Reference catalog delete blocked", True, str(exc)[:80])

        refresh_twin_snapshot()
        stale_steps.append(check_twin_stale()["is_stale"])  # expect False
        report.add(
            "F03",
            "Twin stale detection (sync -> CRUD -> stale -> refresh)",
            stale_steps == [False, True, False],
            f"is_stale sequence={stale_steps} (expected [False, True, False])",
        )
    except Exception as exc:  # noqa: BLE001
        report.add("F01", "Inventory CRUD / twin stale checks", False, str(exc))
    finally:
        if added_id is not None:
            try:
                remove_medicine(added_id)
            except Exception:  # noqa: BLE001
                pass


def _purge_test_medicine(medicine_id: int) -> None:
    """Hard-delete an acceptance-test medicine and everything it created (test only)."""
    from services.db import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            mid = int(medicine_id)
            cur.execute("SELECT DISTINCT sale_id FROM sales_items WHERE medicine_id=%s", (mid,))
            sale_ids = [r["sale_id"] for r in cur.fetchall()]
            for table in ("recommendations", "sales_items", "stock_movements", "inventory_audit"):
                cur.execute(f"DELETE FROM {table} WHERE medicine_id=%s", (mid,))
            for sid in sale_ids:
                cur.execute("DELETE FROM sales_transactions WHERE sale_id=%s", (sid,))
            cur.execute("DELETE FROM medicine_batches WHERE medicine_id=%s", (mid,))
            cur.execute(
                "DELETE FROM medicines WHERE medicine_id=%s AND source_system <> 'reference'",
                (mid,),
            )
        conn.commit()
    finally:
        conn.close()


def _check_stock_ops(report: Report) -> None:
    """G01–G05: sale / purchase / return / adjust / soft delete on a temporary medicine."""
    import json as _json
    from datetime import date, timedelta

    from services.db import get_connection
    from services.inventory_write import add_medicine_with_lot, remove_medicine
    from services.stock_ops import (
        StockError,
        adjust_batch_qty,
        bulk_update_batches,
        check_stock_consistency,
        get_batch_details,
        post_sale,
        receive_purchase,
        suggest_fefo,
        update_batch,
    )

    today = date.today()
    mid: int | None = None
    try:
        first = add_medicine_with_lot(
            name="ACCEPTANCE STOCK-OPS SKU (auto-removed)",
            form_type="TABLET",
            qty_unit="TABLETS",
            quantity=10,
            mfg_date=None,
            expiry_date=str(today + timedelta(days=400)),
            batch_no="ACC-LATE",
        )
        mid = int(first["medicine_id"])
        early = receive_purchase(
            mid, 5, expiry_date=str(today + timedelta(days=60)), batch_no="ACC-EARLY"
        )
        # Rec row with known Step 4 parameters so the live rule can be checked
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recommendations
                    (medicine_id, action_type, qty_suggested, current_stock, forecast_demand,
                     incoming_po_qty, safety_stock, reorder_point, explanation_text,
                     assumptions_json)
                    VALUES (%s,'HOLD',NULL,15,4,0,2,6,'SS = test',%s)
                    """,
                    (
                        mid,
                        _json.dumps(
                            {"order_up_to": 12, "lead_time_weeks": 1, "review_period_weeks": 1,
                             "z_score": 1.645, "sigma_weekly": 1, "service_level": 0.95}
                        ),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        plan = suggest_fefo(mid, 7)
        order = [a["batch_id"] for a in plan["allocations"]]
        report.add(
            "G01",
            "Sale uses earliest-expiry batch first (FEFO)",
            order == [early["batch_id"], first["batch_id"]]
            and plan["allocations"][0]["take"] == 5,
            f"allocation={[(a['batch_no'], a['take']) for a in plan['allocations']]}",
        )

        sale = post_sale(mid, 20)  # only 15 in stock
        consistency = check_stock_consistency()
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(qty_on_hand),0) AS q, MIN(qty_on_hand) AS mn "
                    "FROM medicine_batches WHERE medicine_id=%s",
                    (mid,),
                )
                q = cur.fetchone()
                cur.execute(
                    "SELECT SUM(unmet_qty) AS u FROM sales_items WHERE sale_id=%s",
                    (sale["sale_id"],),
                )
                unmet = float(cur.fetchone()["u"] or 0)
                cur.execute(
                    "SELECT action_type FROM recommendations WHERE medicine_id=%s", (mid,)
                )
                action_after_sale = cur.fetchone()["action_type"]
        finally:
            conn.close()
        report.add(
            "G02",
            "Overselling never goes negative; shortfall saved as lost sale (unmet_qty)",
            float(q["q"]) == 0 and float(q["mn"]) >= 0 and unmet == 5 and consistency["ok"],
            f"on_hand={float(q['q']):.0f}, unmet={unmet:.0f}, consistency={consistency}",
        )

        receive_purchase(mid, 8, expiry_date=str(today + timedelta(days=300)), batch_no="ACC-NEW")
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT action_type FROM recommendations WHERE medicine_id=%s", (mid,)
                )
                action_after_buy = cur.fetchone()["action_type"]
        finally:
            conn.close()
        report.add(
            "G03",
            "Order suggestion updates live (sale -> REORDER, purchase -> HOLD)",
            action_after_sale == "REORDER" and action_after_buy == "HOLD",
            f"after sale={action_after_sale}, after purchase={action_after_buy}",
        )

        blocked = []
        for fn in (
            lambda: adjust_batch_qty(first["batch_id"], 3, reason=""),
            lambda: receive_purchase(mid, 1, expiry_date=str(today - timedelta(days=1))),
            lambda: post_sale(mid, 100, allow_partial=False),
        ):
            try:
                fn()
                blocked.append(False)
            except StockError:
                blocked.append(True)
        report.add(
            "G04",
            "Invalid stock actions refused (no reason / expired receipt / strict oversell)",
            all(blocked),
            f"refused={blocked}",
        )

        # G06: edit expiry -> FEFO order follows; bulk edit is all-or-nothing
        # ACC-NEW (expiry +300d) has stock; a new far-dated batch is edited to expire sooner
        g6 = receive_purchase(mid, 4, expiry_date=str(today + timedelta(600)), batch_no="ACC-G6")
        update_batch(g6["batch_id"], expiry_date=str(today + timedelta(20)))
        new_first = suggest_fefo(mid, 1)["allocations"]
        cost_before = get_batch_details(early["batch_id"])["unit_cost"]
        bulk_refused = False
        try:
            bulk_update_batches(
                [early["batch_id"], g6["batch_id"]],
                unit_cost=9.99,
                mfg_date=str(today + timedelta(days=3)),  # future mfg -> must fail
            )
        except StockError:
            bulk_refused = True
        cost_after = get_batch_details(early["batch_id"])["unit_cost"]
        report.add(
            "G06",
            "Batch edit (expiry) changes which batch sells first; failed bulk edit saves nothing",
            bool(new_first) and new_first[0]["batch_id"] == g6["batch_id"]
            and bulk_refused and cost_before == cost_after,
            f"first batch now={new_first[0]['batch_no'] if new_first else None}, "
            f"bulk_refused={bulk_refused}, cost unchanged={cost_before == cost_after}",
        )

        out = remove_medicine(mid)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.is_active, (SELECT COUNT(*) FROM sales_items s "
                    "WHERE s.medicine_id=m.medicine_id) AS n_sales "
                    "FROM medicines m WHERE m.medicine_id=%s",
                    (mid,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        report.add(
            "G05",
            "Removing a sold medicine keeps its sales history (soft delete)",
            bool(out.get("kept_history")) and row and not row["is_active"] and row["n_sales"] > 0,
            f"kept_history={out.get('kept_history')}, is_active={row and row['is_active']}, "
            f"sales rows={row and row['n_sales']}",
        )
    except Exception as exc:  # noqa: BLE001
        report.add(
            "G01",
            "Stock transactions",
            False,
            f"{exc} (did you run scripts/apply_migration_003.py?)",
        )
    finally:
        if mid is not None:
            try:
                _purge_test_medicine(mid)
            except Exception:  # noqa: BLE001
                pass


def _check_offline_artifacts(report: Report) -> None:
    needed = [
        "catalog_deduped.parquet",
        "assortment_3k.csv",
        "batches_fefo.csv",
        "covariates_navi_mumbai.csv",
        "step3_forecasts_weekly.csv",
        "step4_safety_stock_params.csv",
        "step4_policy_comparison.csv",
    ]
    missing = [f for f in needed if not (DATA / f).exists()]
    report.add(
        "D01",
        "Offline processed artifacts present",
        len(missing) == 0,
        "ok" if not missing else f"missing={missing}",
    )

    # Metrics must not use MAPE as a scored metric (WMAPE/MASE only)
    import re

    bad = []
    for name in ("step2_summary.json", "step3_summary.json", "step2_metrics_summary.csv"):
        path = DATA / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Flag bare mape metric keys/tokens, ignore wmape and "mape excluded" notes
        if re.search(r'(?i)(?<!w)["\']?mape["\']?\s*[:=]', text):
            bad.append(name)
            continue
        if re.search(r'(?i)\bMAPE\b', text) and not re.search(
            r'(?i)(MAPE excluded|no MAPE|never MAPE|not MAPE)', text
        ):
            bad.append(name)
    report.add(
        "D02",
        "Forecast metrics use WMAPE/MASE (not MAPE)",
        len(bad) == 0,
        "clean" if not bad else f"suspicious MAPE metric in {bad}",
    )

    assort = DATA / "assortment_3k.csv"
    if assort.exists():
        import pandas as pd

        n = len(pd.read_csv(assort, usecols=["sku_id"]))
        report.add(
            "D03",
            "Assortment file size",
            n >= 500,
            f"assortment_3k.csv rows={n:,}",
        )


def _check_desktop_import(report: Report) -> None:
    try:
        import app.main  # noqa: F401

        report.add("E01", "Desktop app module imports", True, "app.main OK")
    except Exception as exc:  # noqa: BLE001
        report.add("E01", "Desktop app module imports", False, str(exc))


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--skip-write-checks",
        action="store_true",
        help="Skip F01–F03 and G01–G05 (they add + remove temporary pharmacy SKUs)",
    )
    args = p.parse_args()

    print("=" * 64)
    print("PharmTwinAI — Core acceptance / demo checklist (TEST-01)")
    print("=" * 64)
    print("DATA MODE expectation: DEV SYNTHETIC (not Bhagyashree live sales)\n")

    report = Report()
    _check_db(report)
    # Only run service checks if DB is up
    if any(r.id == "A01" and r.ok for r in report.results):
        _check_services(report)
        _check_sim_isolation(report)
        if not args.skip_write_checks:
            _check_inventory_crud(report)
            _check_stock_ops(report)
    _check_offline_artifacts(report)
    _check_desktop_import(report)

    print(f"{'ID':<6} {'STATUS':<7} {'CHECK'}")
    print("-" * 64)
    for r in report.results:
        status = "PASS" if r.ok else ("FAIL" if r.required else "WARN")
        flag = "" if r.required else " (optional)"
        print(f"{r.id:<6} {status:<7} {r.name}{flag}")
        print(f"       {r.detail}")

    failed = report.failed_required
    print("-" * 64)
    print(
        f"Result: {report.passed}/{len(report.results)} checks OK | "
        f"required failures: {len(failed)}"
    )
    if failed:
        print("Failed required:")
        for r in failed:
            print(f"  - {r.id} {r.name}: {r.detail}")
        print("\nDemo NOT ready. Fix failures, then re-run.")
        return 1

    print("\nDemo READY — core acceptance required checks passed.")
    print("Desktop: py -3 scripts/run_desktop.py")
    out = DATA / "acceptance_last_run.json"
    payload = [
        {
            "id": r.id,
            "name": r.name,
            "ok": r.ok,
            "required": r.required,
            "detail": r.detail,
        }
        for r in report.results
    ]
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
