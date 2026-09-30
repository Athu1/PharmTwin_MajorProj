"""Ingest POS "Customer wise sales Report" exports (xlsx/csv) into MySQL.

Dry-run by default (validate + match report only):
  py -3 scripts/ingest_sales_export.py ..\\Data\\ExcelSheets
Write rows (labeled dev_synthetic unless --source-system sponsor):
  py -3 scripts/ingest_sales_export.py ..\\Data\\ExcelSheets --commit --create-missing

Real sponsor exports go under data/raw/sponsor/ (gitignored) and need
--source-system sponsor explicitly. Patient/doctor columns are never read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.sales_ingest import INGEST_SOURCES, ingest  # noqa: E402

OUT = ROOT / "data" / "processed"


def _collect(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for s in inputs:
        p = Path(s)
        if p.is_dir():
            paths += sorted(
                x for x in p.iterdir()
                if x.suffix.lower() in (".xlsx", ".xls", ".csv") and not x.name.startswith("~$")
            )
        elif p.exists():
            paths.append(p)
        else:
            print(f"WARN: not found: {p}")
    return paths


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest POS sales exports")
    ap.add_argument("inputs", nargs="+", help="Files or folders (xlsx/xls/csv)")
    ap.add_argument("--source-system", default="dev_synthetic", choices=INGEST_SOURCES)
    ap.add_argument("--commit", action="store_true", help="Write to MySQL (default: dry-run)")
    ap.add_argument(
        "--create-missing",
        action="store_true",
        help="Create working-inventory rows for products not in stock "
        "(cloned from reference catalog when matched; reference never modified)",
    )
    args = ap.parse_args()

    paths = _collect(args.inputs)
    if not paths:
        print("No input files.")
        return 1
    out = ingest(
        paths,
        source_system=args.source_system,
        commit=args.commit,
        create_missing=args.create_missing,
    )
    for err in out.get("file_errors", []):
        print(f"FILE ERROR: {err}")
    if not out.get("ok"):
        return 1

    print(f"Label (source_system): {out['source_system']}")
    print(f"Files: {out['files']} | rows: {out['n_rows']} | valid: {out['n_valid']} "
          f"| rejected: {out['n_rejected']}")
    print(f"Vouchers: {out['n_vouchers']} (already loaded: {out['n_vouchers_already_loaded']})")
    print(f"Product match: {out['match_counts']}  "
          "(working = in stock, reference = catalog only, unmatched = unknown)")

    OUT.mkdir(parents=True, exist_ok=True)
    if out["n_rejected"]:
        rej_path = OUT / "ingest_rejects.csv"
        out["rejects"].to_csv(rej_path, index=False)
        print(f"Rejects written: {rej_path}")
    unresolved = out["staging"][out["staging"]["match_status"] != "working"]
    if len(unresolved):
        um_path = OUT / "ingest_unmatched_products.csv"
        (
            unresolved.groupby(["product", "norm_name", "match_status"])
            .size()
            .rename("n_rows")
            .reset_index()
            .to_csv(um_path, index=False)
        )
        print(f"Products not in working inventory: {um_path}")

    if out["committed"]:
        print(
            f"COMMITTED: sales={out['n_sales_written']} items={out['n_items_written']} "
            f"medicines_created={out['n_medicines_created']} "
            f"rows_skipped_unresolved={out['n_rows_skipped_unresolved']}"
        )
        print("Twin is now stale — use 'Refresh twin snapshot' in the desktop app.")
    else:
        print("DRY RUN — nothing written. Add --commit to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
