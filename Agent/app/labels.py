"""Plain-language labels for the desktop UI.

Pharmacy staff see everyday words first; the original technical term stays in
parentheses so the report / viva can still point at the exact metric or code.
Display-only: database values and service outputs are unchanged.
"""

from __future__ import annotations

import re
from typing import Any

ACTION = {
    "REORDER": "Order now (REORDER)",
    "HOLD": "Enough stock (HOLD)",
    "REVIEW_OVERSTOCK": "Too much stock (REVIEW_OVERSTOCK)",
    "REVIEW_EXPIRY": "Check expiry (REVIEW_EXPIRY)",
    "ALL": "Show all (ALL)",
}

ALERT_TYPE = {
    "EXPIRY": "Expiring soon (EXPIRY)",
    "LOW_STOCK": "Running low (LOW_STOCK)",
    "STOCKOUT_RISK": "Out of stock (STOCKOUT_RISK)",
    "OVERSTOCK": "Too much stock (OVERSTOCK)",
    "STALE_TWIN": "Snapshot out of date (STALE_TWIN)",
}

SEVERITY = {
    "CRITICAL": "Urgent (CRITICAL)",
    "WARN": "Check soon (WARN)",
    "INFO": "For info (INFO)",
}

SOURCE = {
    "dev_synthetic": "Demo data (dev_synthetic)",
    "pharmacy": "Added in shop (pharmacy)",
    "sponsor": "Shop records (sponsor)",
    "reference": "Reference list (reference)",
}

POLICY = {
    "fifo_static": "Oldest stock first, fixed order (fifo_static)",
    "fefo_static": "Earliest expiry first, fixed order (fefo_static)",
    "fefo_ss": "Earliest expiry first + safety buffer (fefo_ss)",
    "fefo_ss_markdown": "Earliest expiry first + safety buffer + discount near expiry "
    "(fefo_ss_markdown)",
}

MODEL = {
    "lgbm_env": "AI prediction using season & weather (lgbm_env)",
}

SUB_SOURCE = {
    "explicit": "Known equivalent (explicit)",
    "tfidf": "Similar composition (tfidf)",
    "blocked": "Not allowed (blocked)",
}

AWARE = {
    "Access": "First-choice antibiotic (Access)",
    "Watch": "Use with care – resistance risk (Watch)",
    "Reserve": "Last-resort antibiotic (Reserve)",
    "NotAntibiotic": "Not an antibiotic (NotAntibiotic)",
}


def alert_type_label(alert_type: Any, days_to_expiry: Any) -> str:
    """EXPIRY rows split into 'already expired' vs 'expiring soon'."""
    if alert_type == "EXPIRY" and days_to_expiry is not None and int(days_to_expiry) < 0:
        return "Already expired (EXPIRY)"
    return plain(ALERT_TYPE, alert_type)


def plain(mapping: dict[str, str], code: Any) -> str:
    """Friendly label for a code; unknown codes are shown unchanged."""
    if code is None:
        return ""
    return mapping.get(str(code), str(code))


def code_for(mapping: dict[str, str], label: str) -> str:
    """Reverse lookup for comboboxes that display friendly labels."""
    for code, text in mapping.items():
        if text == label:
            return code
    return label


def plain_text(text: str) -> str:
    """Swap policy codes inside free text (simulation summaries) for friendly names."""
    pattern = "|".join(re.escape(c) for c in sorted(POLICY, key=len, reverse=True))
    return re.sub(rf"\b({pattern})\b", lambda m: POLICY[m.group(1)], text or "")


def recommendation_story(r: dict[str, Any]) -> str:
    """Plain explanation of a reorder suggestion, followed by the technical line."""
    action = str(r.get("action_type") or "")
    on_hand = float(r.get("current_stock") or 0)
    rop = float(r.get("reorder_point") or 0)
    ss = float(r.get("safety_stock") or 0)
    demand = float(r.get("forecast_demand") or 0)
    qty = r.get("qty_suggested")
    lines = [f"What to do: {plain(ACTION, action)}", ""]
    lines.append(f"• In stock now: {on_hand:.0f} units.")
    lines.append(
        f"• Expected sales until the next delivery arrives: about {demand:.0f} units "
        "(cover demand)."
    )
    lines.append(
        f"• Extra stock kept aside for busy days / late deliveries: {ss:.0f} units "
        "(safety stock, SS)."
    )
    lines.append(
        f"• Place an order when stock drops to {rop:.0f} units (reorder point, ROP)."
    )
    if action == "REORDER":
        msg = "Stock is at or below the reorder level, so order now."
        if qty is not None:
            msg += f" Suggested order: about {float(qty):.0f} units."
        lines.append("")
        lines.append(msg)
    elif action == "REVIEW_OVERSTOCK":
        lines.append("")
        lines.append(
            "Stock is well above what is likely to sell soon — avoid re-ordering and "
            "watch expiry dates."
        )
    elif action == "HOLD":
        lines.append("")
        lines.append("Stock is fine for now — no order needed.")
    lines.append("")
    lines.append(
        "How the safety stock is worked out: it grows when sales go up and down a lot, "
        "and when deliveries take longer "
        "(SS = Z × σ × √(L + R); Z = service-level factor, σ = weekly sales variation, "
        "L = supplier delivery time in weeks, R = weeks between stock checks)."
    )
    tech = r.get("explanation_text")
    if tech:
        lines.append("")
        lines.append(f"(Technical details: {tech})")
    return "\n".join(lines)
