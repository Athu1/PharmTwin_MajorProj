"""CLI entrypoint for Step 5: regulated substitute recommendations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.run_substitutes import run_step5


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 5: TF-IDF substitutes + Schedule H1 / AWaRe / CDSCO gates"
    )
    parser.add_argument("--n-queries", type=int, default=200)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--min-cosine", type=float, default=0.55)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    paths = run_step5(
        n_queries=args.n_queries,
        top_n=args.top_n,
        min_cosine=args.min_cosine,
        seed=args.seed,
    )
    print("\nOutput files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
