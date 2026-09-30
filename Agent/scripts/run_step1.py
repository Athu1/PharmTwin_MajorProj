"""CLI entrypoint for Step 1: synthetic Navi Mumbai pharmacy dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate_transactions import run_step1


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Step 1 synthetic pharmacy datasets")
    parser.add_argument("--n-skus", type=int, default=3000)
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--catalog",
        default=r"e:\MajorProject_4th_Yr\Data\A-Z medicines 2.5L+\Extensive_A_Z_medicines_dataset_of_India.csv",
    )
    args = parser.parse_args()
    paths = run_step1(
        catalog_path=args.catalog,
        n_skus=args.n_skus,
        start=args.start,
        end=args.end,
        seed=args.seed,
    )
    print("\nOutput files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
