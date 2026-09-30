"""WHO AWaRe antibiotic classification for substitution stewardship."""

from __future__ import annotations

import re
from typing import Literal

AwareGroup = Literal["Access", "Watch", "Reserve", "NotAntibiotic"]

# INN → AWaRe (WHO framework; common retail-pharmacy antibiotics)
ACCESS_INNS = {
    "amoxicillin",
    "amoxycillin",
    "ampicillin",
    "benzylpenicillin",
    "phenoxymethylpenicillin",
    "cloxacillin",
    "dicloxacillin",
    "flucloxacillin",
    "doxycycline",
    "tetracycline",
    "nitrofurantoin",
    "metronidazole",
    "gentamicin",
    "amikacin",
    "sulfamethoxazole",
    "trimethoprim",
    "co-trimoxazole",
    "cotrimoxazole",
    "chloramphenicol",
    "clindamycin",
    "spectinomycin",
    "cefalexin",
    "cephalexin",
    "cefazolin",
    "cefadroxil",
}

WATCH_INNS = {
    "azithromycin",
    "clarithromycin",
    "erythromycin",
    "roxithromycin",
    "ciprofloxacin",
    "levofloxacin",
    "ofloxacin",
    "norfloxacin",
    "moxifloxacin",
    "gatifloxacin",
    "cefuroxime",
    "ceftriaxone",
    "cefotaxime",
    "ceftazidime",
    "cefepime",
    "cefpodoxime",
    "cefixime",
    "cefdinir",
    "cefoperazone",
    "vancomycin",
    "teicoplanin",
    "piperacillin",
    "tazobactam",
    "clavulanic acid",  # often with amox — stewardship still watches combo use
}

RESERVE_INNS = {
    "colistin",
    "polymyxin",
    "linezolid",
    "daptomycin",
    "tigecycline",
    "ceftaroline",
    "cefiderocol",
    "plazomicin",
    "fosfomycin",  # IV reserve in many settings; oral UTI use varies — treat as Reserve for auto-OTC block
    "meropenem",
    "imipenem",
    "ertapenem",
    "aztreonam",
}

_INN_RE = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")


def extract_inns(text: str) -> set[str]:
    if not text:
        return set()
    # Prefer tokens before strength parentheses
    cleaned = re.sub(r"\([^)]*\)", " ", text)
    tokens = {t.lower() for t in _INN_RE.findall(cleaned)}
    # Normalize amoxycillin spelling
    if "amoxycillin" in tokens:
        tokens.add("amoxicillin")
    return tokens


def composition_inns(row) -> set[str]:
    blob = " ".join(
        str(row.get(c, "") or "")
        for c in ("short_composition1", "short_composition2", "name")
    )
    return extract_inns(blob)


def aware_group(row) -> AwareGroup:
    inns = composition_inns(row)
    if inns & RESERVE_INNS:
        return "Reserve"
    if inns & WATCH_INNS:
        return "Watch"
    if inns & ACCESS_INNS:
        return "Access"
    # Class-level hints
    chem = str(row.get("Chemical Class", "") or "").lower()
    action = str(row.get("Action Class", "") or "").lower()
    tc = str(row.get("Therapeutic Class", "") or "").upper()
    blob = chem + " " + action
    if "carbapenem" in blob or "oxazolidinone" in blob or "polymyxin" in blob:
        return "Reserve"
    if any(k in blob for k in ("fluoroquinolone", "macrolide", "cephalosporin", "quinolone")):
        return "Watch"
    if tc == "ANTI INFECTIVES" and inns:
        # Unknown antibiotic INN — treat as Watch for stewardship-safe auto-sub
        return "Watch"
    if tc == "ANTI INFECTIVES":
        return "Watch"
    return "NotAntibiotic"


def aware_allows_auto_substitute(group: AwareGroup) -> bool:
    """Access OK for stewardship-aligned suggest; Watch/Reserve blocked for OTC auto-path."""
    return group in ("Access", "NotAntibiotic")
