"""CLI entrypoint for Step 2: intermittent demand forecasting evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_forecast_eval import run_step2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 2: Croston / SBA / TSB vs MA with WMAPE & MASE"
    )
    parser.add_argument("--train-ratio", type=float, default=0.75)
    parser.add_argument("--max-skus", type=int, default=None, help="Optional subsample for smoke tests")
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paths = run_step2(
        train_ratio=args.train_ratio,
        max_skus=args.max_skus,
        alpha=args.alpha,
        beta=args.beta,
        seed=args.seed,
    )
    print("\nOutput files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
