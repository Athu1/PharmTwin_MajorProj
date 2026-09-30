"""Move DEV synthetic dates forward so the demo history ends 'today'.

The synthetic files cover 2023-01-01 .. 2024-12-31. Loaded as-is, a 2026 demo shows
forecasts for 2024 and batches that expired years ago. Every synthetic date is
shifted by a whole number of weeks (weekdays and weekly forecast buckets stay
aligned). Files under data/originals/ and data/processed/ are not modified — only
the rows written to MySQL.

- Sales + forecast weeks: anchored so sales history ends today
  (app_meta.date_shift_days).
- Batches: batches_fefo.csv is an opening-stock snapshot whose receipts end
  2024-01-01, so lots are anchored on their own last receipt
  (app_meta.batch_date_shift_days). Anchoring them on the sales end would leave
  ~99.9% of units expired.
"""

from __future__ import annotations

from datetime import date

META_KEY = "date_shift_days"


def compute_shift_days(last_history_day: date, today: date | None = None) -> int:
    """Whole weeks between the last synthetic sales day and today (never negative)."""
    today = today or date.today()
    days = (today - last_history_day).days
    return max(0, days // 7 * 7)


def read_shift_days(cur) -> int:
    """Offset recorded by the last seed (0 if never shifted). Works with any cursor type."""
    cur.execute("SELECT meta_value FROM app_meta WHERE meta_key=%s", (META_KEY,))
    row = cur.fetchone()
    if not row:
        return 0
    val = row["meta_value"] if isinstance(row, dict) else row[0]
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
