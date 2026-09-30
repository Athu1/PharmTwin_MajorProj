"""CDSCO banned / irrational FDC checks + discontinued flag."""

from __future__ import annotations

import re
from typing import Iterable

# Illustrative CDSCO-banned / irrational FDC composition signatures (INN sets).
# Matching is set-equality on normalized INN tokens extracted from compositions.
BANNED_FDC_INN_SETS: list[frozenset[str]] = [
    # Multiple NSAID combinations (irrational)
    frozenset({"diclofenac", "ibuprofen"}),
    frozenset({"diclofenac", "ibuprofen", "paracetamol"}),
    frozenset({"nimesulide", "paracetamol"}),
    frozenset({"nimesulide", "aceclofenac"}),
    frozenset({"nimesulide", "diclofenac"}),
    # Antibiotic + antibiotic irrational mixes (examples)
    frozenset({"amoxicillin", "cloxacillin", "lactobacillus"}),
    frozenset({"amoxycillin", "cloxacillin"}),
    frozenset({"ciprofloxacin", "tinidazole", "dicyclomine"}),
    frozenset({"ofloxacin", "ornidazole", "dicyclomine"}),
    # Steroid + NSAID + other (common ban theme)
    frozenset({"aceclofenac", "paracetamol", "chlorzoxazone"}),
    frozenset({"diclofenac", "paracetamol", "chlorzoxazone", "magnesium"}),
]

# Keyword patterns for known banned brand-style / combo phrases
BANNED_PHRASE_RE = re.compile(
    r"nimesulide\s*\+?\s*paracetamol|"
    r"diclofenac\s*\+?\s*ibuprofen|"
    r"gillian.*bane|"  # placeholder never matches
    r"fixed.dose.*banned",
    re.I,
)

_INN_RE = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")

# Normalize spelling variants for set matching
_INN_ALIASES = {
    "amoxycillin": "amoxicillin",
    "acetaminophen": "paracetamol",
}


def _norm_inn(tok: str) -> str:
    t = tok.lower()
    return _INN_ALIASES.get(t, t)


def extract_inn_set(text: str) -> frozenset[str]:
    cleaned = re.sub(r"\([^)]*\)", " ", text or "")
    toks = {_norm_inn(t) for t in _INN_RE.findall(cleaned)}
    # Drop very common excipient / salt noise
    noise = {
        "acid",
        "sodium",
        "potassium",
        "hydrate",
        "hydrous",
        "anhydrous",
        "maleate",
        "hydrochloride",
        "sulphate",
        "sulfate",
        "tablet",
        "syrup",
        "injection",
        "cream",
        "strip",
        "mg",
        "ml",
    }
    return frozenset(t for t in toks if t not in noise and len(t) > 3)


def composition_inn_set(row) -> frozenset[str]:
    blob = " ".join(
        str(row.get(c, "") or "")
        for c in ("short_composition1", "short_composition2")
    )
    return extract_inn_set(blob)


def is_banned_fdc(row) -> tuple[bool, str]:
    """
    Return (blocked, reason).

    Checks discontinued flag and banned FDC INN-set / phrase patterns.
    """
    if bool(row.get("Is_discontinued", False)):
        return True, "Is_discontinued=True (not available for substitution)"

    inns = composition_inn_set(row)
    for banned in BANNED_FDC_INN_SETS:
        # Ban if all banned INNs are present in the product (subset match)
        if banned.issubset(inns):
            return True, f"CDSCO banned/irrational FDC pattern: {sorted(banned)}"

    blob = " ".join(
        str(row.get(c, "") or "")
        for c in ("short_composition1", "short_composition2", "name")
    )
    if BANNED_PHRASE_RE.search(blob):
        return True, "CDSCO banned FDC phrase match"

    return False, ""


def annotate_catalog(df, inn_col: str = "inn_set"):
    """Add inn_set column for debugging (optional)."""
    out = df.copy()
    out[inn_col] = out.apply(composition_inn_set, axis=1)
    return out
