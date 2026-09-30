"""Schedule H1 hard-block for automated pharmacy substitution (India)."""

from __future__ import annotations

import re

# Representative Schedule H1 INNs / class keywords (CDSCO Schedule H1 focus areas).
# Automated OTC substitution is hard-blocked; RMP Rx + 3-year register required.
SCHEDULE_H1_PATTERNS: list[str] = [
    # 3rd / 4th generation cephalosporins
    r"\bceftriaxone\b",
    r"\bcefotaxime\b",
    r"\bceftazidime\b",
    r"\bcefepime\b",
    r"\bcefoperazone\b",
    r"\bcefpirome\b",
    r"\bcefpodoxime\b",
    r"\bcefixime\b",
    r"\bcefdinir\b",
    r"\bcefuroxime\b",
    # Fluoroquinolones (many H1)
    r"\blevofloxacin\b",
    r"\bmoxifloxacin\b",
    r"\bgatifloxacin\b",
    r"\bofloxacin\b",
    r"\bciprofloxacin\b",
    r"\bnorfloxacin\b",
    # Anti-TB
    r"\brifampicin\b",
    r"\brifampin\b",
    r"\bisoniazid\b",
    r"\bpyrazinamide\b",
    r"\bethambutol\b",
    r"\bstreptomycin\b",
    r"\bcycloserine\b",
    r"\bethionamide\b",
    # Psychotropics / habit-risk (illustrative H1 / closely controlled)
    r"\balprazolam\b",
    r"\bclonazepam\b",
    r"\bdiazepam\b",
    r"\blorazepam\b",
    r"\bnitrazepam\b",
    r"\bzolpidem\b",
    r"\btramadol\b",
    r"\bpentazocine\b",
    r"\bcodeine\b",
    r"\bdextropropoxyphene\b",
    # Other H1-listed antibiotics commonly flagged
    r"\bmeropenem\b",
    r"\bimipenem\b",
    r"\bertapenem\b",
    r"\bvancomycin\b",
    r"\blinezolid\b",
    r"\bteicoplanin\b",
    r"\bcolistin\b",
    r"\btigecycline\b",
]

SCHEDULE_H1_RE = re.compile("|".join(SCHEDULE_H1_PATTERNS), re.I)

H1_BLOCK_MESSAGE = (
    "Schedule H1 hard-block: automated substitution is not permitted. "
    "Requires a valid Registered Medical Practitioner (RMP) prescription. "
    "A separate Schedule H1 dispensing register must be maintained for three years."
)


def composition_blob(row) -> str:
    parts = [
        str(row.get("short_composition1", "") or ""),
        str(row.get("short_composition2", "") or ""),
        str(row.get("Chemical Class", "") or ""),
        str(row.get("Action Class", "") or ""),
        str(row.get("name", "") or ""),
    ]
    return " ".join(parts)


def is_schedule_h1(row) -> bool:
    """True if SKU composition/name matches Schedule H1 watchlist."""
    return bool(SCHEDULE_H1_RE.search(composition_blob(row)))


def schedule_h1_hits(row) -> list[str]:
    return sorted({m.group(0).lower() for m in SCHEDULE_H1_RE.finditer(composition_blob(row))})
