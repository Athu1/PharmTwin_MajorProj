"""CLI entrypoint for Step 3b: multi-model benchmark + stacking ensemble.

  py -3 scripts/run_benchmark.py                 # all SKUs (slow)
  py -3 scripts/run_benchmark.py --max-skus 400  # quick run for a demo

Compares LightGBM, XGBoost, random forest and a Poisson GLM on one time split,
then blends them. Writes step3b_model_benchmark.csv and step3b_summary.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.benchmark_models import run_benchmark  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 3b: model family benchmark + stacking")
    ap.add_argument("--max-skus", type=int, default=None, help="Subsample SKUs for a faster run")
    ap.add_argument("--train-ratio", type=float, default=0.75)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--no-env",
        action="store_true",
        help="Drop the weather / air-quality features (ablation)",
    )
    args = ap.parse_args()

    out = run_benchmark(
        max_skus=args.max_skus,
        train_ratio=args.train_ratio,
        seed=args.seed,
        include_env=not args.no_env,
    )
    print("\nOutput files:")
    for key in ("summary", "predictions", "json"):
        print(f"  {key}: {out[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
