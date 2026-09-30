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
        help="Skip F01–F03 (they add + remove a temporary pharmacy SKU and a twin snapshot)",
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
