"""CLI entrypoint for Step 3c: multi-week forecasts + the cover-window model.

  py -3 scripts/run_step3c.py                 # all SKUs (slow)
  py -3 scripts/run_step3c.py --max-skus 300  # quick run

Trains a direct quantile model per horizon (1-4 weeks ahead) and one for the total
demand over the next L+R weeks, which is what the reorder point actually needs.
Writes step3c_horizon_forecasts.csv, step3c_cover_forecasts.csv and step3c_summary.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecast_horizons import run_horizon_forecasts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 3c: multi-horizon + cover-window forecasts")
    ap.add_argument("--max-skus", type=int, default=None)
    ap.add_argument("--train-ratio", type=float, default=0.75)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lead-time-weeks", type=int, default=1)
    ap.add_argument("--review-period-weeks", type=int, default=1)
    ap.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4],
        help="Weeks ahead to forecast directly (default: 1 2 3 4)",
    )
    args = ap.parse_args()

    out = run_horizon_forecasts(
        max_skus=args.max_skus,
        train_ratio=args.train_ratio,
        seed=args.seed,
        horizons=tuple(args.horizons),
        lead_time_weeks=args.lead_time_weeks,
        review_period_weeks=args.review_period_weeks,
    )
    print("\nOutput files:")
    for key in ("horizons", "cover", "metrics", "json"):
        print(f"  {key}: {out[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
