"""FEFO / FIFO inventory operations and near-expiry OTC markdown rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

PickPolicy = Literal["fefo", "fifo"]

# OTC-eligible therapeutic classes for automated markdown (not Rx-heavy / H1-risk classes)
OTC_THERAPEUTIC = {
    "RESPIRATORY",
    "PAIN ANALGESICS",
    "GASTRO INTESTINAL",
    "VITAMINS MINERALS NUTRIENTS",
    "DERMA",
}


@dataclass
class Batch:
    batch_id: str
    sku_id: int
    receipt_date: pd.Timestamp
    expiry_date: pd.Timestamp
    qty_remaining: float
    unit_cost: float
    unit_price: float
    is_otc: bool = False

    def days_to_expiry(self, as_of: pd.Timestamp) -> int:
        return int((self.expiry_date.normalize() - as_of.normalize()).days)


@dataclass
class SkuState:
    sku_id: int
    batches: list[Batch] = field(default_factory=list)
    on_order: float = 0.0
    pending_receipts: list[tuple[pd.Timestamp, float, float, float]] = field(default_factory=list)
    # pending: (arrival_week, qty, unit_cost, unit_price)


def markdown_rate(days_to_expiry: int, is_otc: bool) -> float:
    """
    Fractional price cut for near-expiry OTC. Rx / non-OTC → 0 (no auto-markdown).

    >90d: 0 | 61–90: 10% | 31–60: 25% | 15–30: 40% | <15: 50% clearance
    """
    if not is_otc or days_to_expiry > 90:
        return 0.0
    if days_to_expiry > 60:
        return 0.10
    if days_to_expiry > 30:
        return 0.25
    if days_to_expiry >= 15:
        return 0.40
    return 0.50


def clearance_demand_uplift(days_to_expiry: int, is_otc: bool) -> float:
    """Extra sell-through multiplier when OTC is marked down (clearance traffic)."""
    rate = markdown_rate(days_to_expiry, is_otc)
    if rate <= 0:
        return 1.0
    # Up to +35% demand capture at deepest markdown
    return 1.0 + 0.7 * rate


def is_otc_sku(row: pd.Series) -> bool:
    if bool(row.get("Habit Forming", False)):
        return False
    tc = str(row.get("Therapeutic Class", "") or "").strip().upper()
    cohort = str(row.get("demand_cohort", "") or "").strip().lower()
    if tc in OTC_THERAPEUTIC:
        return True
    if cohort == "respiratory" and "ANTI INFECTIVES" not in tc:
        return True
    return False


def sort_batches(batches: list[Batch], policy: PickPolicy, as_of: pd.Timestamp) -> list[Batch]:
    alive = [b for b in batches if b.qty_remaining > 0 and b.expiry_date >= as_of]
    if policy == "fefo":
        return sorted(alive, key=lambda b: (b.expiry_date, b.receipt_date, b.batch_id))
    return sorted(alive, key=lambda b: (b.receipt_date, b.expiry_date, b.batch_id))


def allocate_demand(
    state: SkuState,
    demand: float,
    as_of: pd.Timestamp,
    policy: PickPolicy,
    apply_markdown: bool,
) -> dict:
    """
    Pick units under FEFO/FIFO. Returns sold qty, revenue, cost, unmet, markdown ₹.
    """
    remaining = float(max(demand, 0.0))
    sold = 0.0
    revenue = 0.0
    cogs = 0.0
    markdown_discount = 0.0
    batches_used: list[str] = []

    # Optional clearance uplift: increase effective demand we try to fill from near-expiry OTC
    if apply_markdown and remaining > 0:
        # Uplift based on soonest-expiring OTC batch
        otc_batches = [b for b in state.batches if b.is_otc and b.qty_remaining > 0 and b.expiry_date >= as_of]
        if otc_batches:
            soonest = min(otc_batches, key=lambda b: b.expiry_date)
            remaining *= clearance_demand_uplift(soonest.days_to_expiry(as_of), True)

    ordered = sort_batches(state.batches, policy, as_of)
    for b in ordered:
        if remaining <= 1e-9:
            break
        take = min(remaining, b.qty_remaining)
        dte = b.days_to_expiry(as_of)
        md = markdown_rate(dte, b.is_otc) if apply_markdown else 0.0
        price = b.unit_price * (1.0 - md)
        sold += take
        revenue += take * price
        cogs += take * b.unit_cost
        markdown_discount += take * b.unit_price * md
        b.qty_remaining -= take
        remaining -= take
        batches_used.append(b.batch_id)

    unmet = max(float(demand) - sold, 0.0)  # unmet vs original demand (not uplifted)
    # If uplift caused extra sales beyond original demand, count as clearance bonus
    clearance_extra = max(sold - float(demand), 0.0)
    return {
        "sold": sold,
        "unmet": unmet if sold <= demand else 0.0,
        "revenue": revenue,
        "cogs": cogs,
        "markdown_discount": markdown_discount,
        "clearance_extra": clearance_extra,
        "batches_used": batches_used,
    }


def write_off_expired(state: SkuState, as_of: pd.Timestamp) -> dict:
    """Remove expired stock; return waste units and cost."""
    waste_qty = 0.0
    waste_cost = 0.0
    waste_retail = 0.0
    kept: list[Batch] = []
    for b in state.batches:
        if b.expiry_date < as_of and b.qty_remaining > 0:
            waste_qty += b.qty_remaining
            waste_cost += b.qty_remaining * b.unit_cost
            waste_retail += b.qty_remaining * b.unit_price
            b.qty_remaining = 0.0
        elif b.qty_remaining > 0:
            kept.append(b)
    state.batches = kept
    return {"waste_qty": waste_qty, "waste_cost": waste_cost, "waste_retail": waste_retail}


def on_hand(state: SkuState, as_of: pd.Timestamp) -> float:
    return float(
        sum(b.qty_remaining for b in state.batches if b.expiry_date >= as_of and b.qty_remaining > 0)
    )


def receive_orders(
    state: SkuState,
    as_of: pd.Timestamp,
    batch_seq: list[int],
    is_otc: bool = False,
) -> None:
    still_pending = []
    for arrival, qty, cost, price in state.pending_receipts:
        if arrival <= as_of:
            batch_seq[0] += 1
            state.batches.append(
                Batch(
                    batch_id=f"R{batch_seq[0]:07d}",
                    sku_id=state.sku_id,
                    receipt_date=as_of,
                    expiry_date=as_of + pd.Timedelta(days=int(np.random.randint(180, 540))),
                    qty_remaining=qty,
                    unit_cost=cost,
                    unit_price=price,
                    is_otc=is_otc,
                )
            )
            state.on_order = max(0.0, state.on_order - qty)
        else:
            still_pending.append((arrival, qty, cost, price))
    state.pending_receipts = still_pending
