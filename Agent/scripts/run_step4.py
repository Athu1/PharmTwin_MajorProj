"""CLI entrypoint for Step 4: FEFO + probabilistic safety stock + OTC markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_inventory_sim import run_step4


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 4: FEFO inventory, SS=Z*σ*√(L+R), OTC markdowns"
    )
    parser.add_argument("--lead-time-weeks", type=float, default=1.0)
    parser.add_argument("--review-period-weeks", type=float, default=1.0)
    parser.add_argument("--service-level", type=float, default=0.95)
    parser.add_argument("--max-skus", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paths = run_step4(
        lead_time_weeks=args.lead_time_weeks,
        review_period_weeks=args.review_period_weeks,
        service_level=args.service_level,
        max_skus=args.max_skus,
        seed=args.seed,
    )
    print("\nOutput files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
