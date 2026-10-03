"""CLI entrypoint for Step 6: stockout-risk classifier + false-positive analysis.

  py -3 scripts/run_step6.py                  # all SKUs
  py -3 scripts/run_step6.py --max-skus 400   # quick run
  py -3 scripts/run_step6.py --cost-ratio 10  # treat a missed stockout as 10x worse

Writes step6_classifier_models.csv, step6_threshold_sweep.csv and step6_summary.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.stockout_classifier import DEFAULT_COST_RATIO, run_stockout_classifier  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 6: stockout-risk classifier")
    ap.add_argument("--max-skus", type=int, default=None)
    ap.add_argument("--train-ratio", type=float, default=0.75)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--cost-ratio",
        type=float,
        default=DEFAULT_COST_RATIO,
        help="How many unnecessary reorders one missed stockout is worth (default 5)",
    )
    args = ap.parse_args()

    out = run_stockout_classifier(
        max_skus=args.max_skus,
        train_ratio=args.train_ratio,
        seed=args.seed,
        cost_ratio=args.cost_ratio,
    )
    print("\nOutput files:")
    for key in ("models", "sweep", "json"):
        print(f"  {key}: {out[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
