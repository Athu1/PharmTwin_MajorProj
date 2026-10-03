"""Copy immutable originals so working inventory never edits source datasets."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROCESSED = ROOT / "data" / "processed"
ORIGINALS = ROOT / "data" / "originals"

# Files that must remain unchanged by inventory CRUD / pharmacy edits
FREEZE = [
    "catalog_deduped.parquet",
    "assortment_3k.csv",
    "batches_fefo.csv",
    "covariates_navi_mumbai.csv",
    "transactions_synthetic.csv",
    "step1_summary.json",
    # Model-comparison evidence (small summaries only; per-SKU detail stays local)
    "step2_summary.json",
    "step2_metrics_summary.csv",
    "step3_forecasts_weekly.csv",
    "step3_forecasts_weekly.parquet",
    "step4_safety_stock_params.csv",
    "step4_policy_comparison.csv",
    "step5_summary.json",
    "step5_audit_counts.csv",
    "step3b_model_benchmark.csv",
    "step3b_summary.json",
    "step6_classifier_models.csv",
    "step6_threshold_sweep.csv",
    "step6_summary.json",
]


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_originals(force: bool = False) -> dict:
    ORIGINALS.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "READ-ONLY originals. Inventory add/remove must never modify these files "
            "or medicines.source_system='reference' rows in MySQL."
        ),
        "files": {},
    }
    copied = 0
    skipped = 0
    for name in FREEZE:
        src = PROCESSED / name
        dst = ORIGINALS / name
        if not src.exists():
            manifest["files"][name] = {"status": "missing_source"}
            continue
        if dst.exists() and not force:
            skipped += 1
            manifest["files"][name] = {
                "status": "already_present",
                "sha256": _sha256(dst),
                "bytes": dst.stat().st_size,
            }
            continue
        shutil.copy2(src, dst)
        copied += 1
        manifest["files"][name] = {
            "status": "copied",
            "sha256": _sha256(dst),
            "bytes": dst.stat().st_size,
            "source": str(src),
        }

    readme = ORIGINALS / "README.md"
    readme.write_text(
        "# Immutable originals\n\n"
        "These files are frozen snapshots of catalog / synthetic pipeline outputs.\n\n"
        "- **Do not edit** files in this folder.\n"
        "- MySQL rows with `source_system='reference'` are the 250k+ catalog knowledge base "
        "and must not be updated or deleted by inventory UI.\n"
        "- Pharmacy working stock uses `source_system` in "
        "`('pharmacy','dev_synthetic','sponsor')` only.\n"
        "- Re-run: `py -3 scripts/snapshot_originals.py` (add `--force` to refresh copies).\n",
        encoding="utf-8",
    )
    (ORIGINALS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"copied": copied, "skipped": skipped, "dir": str(ORIGINALS)}


def main() -> int:
    force = "--force" in sys.argv
    out = snapshot_originals(force=force)
    print(f"Originals snapshot → {out['dir']}")
    print(f"  copied={out['copied']} skipped_existing={out['skipped']}")
    print("Inventory CRUD must not modify data/originals/ or reference medicines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
