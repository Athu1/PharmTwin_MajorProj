"""CLI entrypoint for Step 3: env-conditioned LightGBM quantile forecasting."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_env_forecast import run_step3


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 3: LightGBM + rain/PM2.5 covariates (WMAPE/MASE)"
    )
    parser.add_argument("--train-ratio", type=float, default=0.75)
    parser.add_argument("--max-skus", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paths = run_step3(
        train_ratio=args.train_ratio,
        max_skus=args.max_skus,
        seed=args.seed,
    )
    print("\nOutput files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
