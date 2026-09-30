"""TF-IDF + cosine similarity substitute recommender with regulatory gates."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from .catalog import composition_text
from .regulatory import (
    H1_BLOCK_MESSAGE,
    aware_allows_auto_substitute,
    aware_group,
    is_banned_fdc,
    is_schedule_h1,
    schedule_h1_hits,
)


@dataclass
class SubstituteResult:
    query_sku_id: int
    candidate_sku_id: int
    candidate_name: str
    score: float
    source: str  # explicit | tfidf
    aware: str
    schedule_h1: bool
    blocked: bool
    block_reason: str = ""
    price_inr: float = 0.0
    therapeutic_class: str = ""


@dataclass
class SubstituteEngine:
    catalog: pd.DataFrame
    vectorizer: TfidfVectorizer
    matrix: any  # scipy sparse
    sku_ids: np.ndarray
    index_by_sku: dict[int, int] = field(default_factory=dict)
    stock: dict[int, float] = field(default_factory=dict)
    min_cosine: float = 0.55

    @classmethod
    def fit(
        cls,
        catalog: pd.DataFrame,
        stock: dict[int, float] | None = None,
        min_cosine: float = 0.55,
    ) -> "SubstituteEngine":
        cat = catalog.copy().reset_index(drop=True)
        cat["sku_id"] = cat["sku_id"].astype(int)
        texts = cat.apply(composition_text, axis=1).fillna("").astype(str)
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
        )
        matrix = vectorizer.fit_transform(texts)
        matrix = normalize(matrix, norm="l2", axis=1)
        sku_ids = cat["sku_id"].to_numpy(dtype=int)
        index_by_sku = {int(s): i for i, s in enumerate(sku_ids)}
        return cls(
            catalog=cat,
            vectorizer=vectorizer,
            matrix=matrix,
            sku_ids=sku_ids,
            index_by_sku=index_by_sku,
            stock=stock or {},
            min_cosine=min_cosine,
        )

    def _row(self, sku_id: int) -> pd.Series:
        idx = self.index_by_sku[int(sku_id)]
        return self.catalog.iloc[idx]

    def _in_stock(self, sku_id: int) -> bool:
        if not self.stock:
            return True  # no stock filter → assume available
        return float(self.stock.get(int(sku_id), 0.0)) > 0

    def _gate(self, query_row: pd.Series, cand_row: pd.Series) -> tuple[bool, str, str, bool]:
        """
        Apply regulatory filters to a candidate.

        Returns (blocked, block_reason, aware_group, cand_is_h1).
        """
        # Query itself H1 → block entire auto-sub path
        if is_schedule_h1(query_row):
            return True, H1_BLOCK_MESSAGE, aware_group(cand_row), True

        if is_schedule_h1(cand_row):
            hits = ", ".join(schedule_h1_hits(cand_row)) or "H1 match"
            return (
                True,
                f"Candidate is Schedule H1 ({hits}). {H1_BLOCK_MESSAGE}",
                aware_group(cand_row),
                True,
            )

        banned, reason = is_banned_fdc(cand_row)
        if banned:
            return True, reason, aware_group(cand_row), False

        if bool(cand_row.get("Is_discontinued", False)):
            return True, "Candidate Is_discontinued=True", aware_group(cand_row), False

        if bool(cand_row.get("Habit Forming", False)):
            return (
                True,
                "Habit Forming=Yes — pharmacist/Rx path required; auto-substitute blocked",
                aware_group(cand_row),
                False,
            )

        ag = aware_group(cand_row)
        # If query is an antibiotic, enforce AWaRe on substitutes
        q_ag = aware_group(query_row)
        if q_ag != "NotAntibiotic" or ag != "NotAntibiotic":
            if not aware_allows_auto_substitute(ag):
                return (
                    True,
                    f"WHO AWaRe '{ag}' — restricted from automated OTC substitution "
                    f"(antimicrobial stewardship)",
                    ag,
                    False,
                )

        return False, "", ag, False

    def _explicit_candidates(self, row: pd.Series) -> list[tuple[int, str, float]]:
        """Map substitute0..4 brand names to in-assortment sku_ids when possible."""
        out = []
        name_to_id = {
            str(n).strip().lower(): int(s)
            for s, n in zip(self.catalog["sku_id"], self.catalog["name"])
            if str(n).strip()
        }
        for i in range(5):
            col = f"substitute{i}"
            if col not in row.index:
                continue
            name = str(row.get(col, "") or "").strip()
            if not name:
                continue
            sku = name_to_id.get(name.lower())
            if sku is None:
                # fuzzy: startswith / contains
                matches = self.catalog[
                    self.catalog["name"].str.lower() == name.lower()
                ]
                if matches.empty:
                    matches = self.catalog[
                        self.catalog["name"].str.lower().str.startswith(name.lower()[:20])
                    ]
                if matches.empty:
                    continue
                sku = int(matches.iloc[0]["sku_id"])
            if sku == int(row["sku_id"]):
                continue
            out.append((sku, "explicit", 1.0 - 0.02 * i))
        return out

    def _tfidf_candidates(self, sku_id: int, top_k: int = 25) -> list[tuple[int, str, float]]:
        idx = self.index_by_sku.get(int(sku_id))
        if idx is None:
            return []
        sims = cosine_similarity(self.matrix[idx], self.matrix).ravel()
        sims[idx] = -1.0
        order = np.argsort(-sims)[:top_k]
        out = []
        for j in order:
            score = float(sims[j])
            if score < self.min_cosine:
                break
            out.append((int(self.sku_ids[j]), "tfidf", score))
        return out

    def recommend(
        self,
        sku_id: int,
        top_n: int = 5,
        require_in_stock: bool = True,
        include_blocked: bool = False,
    ) -> list[SubstituteResult]:
        sku_id = int(sku_id)
        if sku_id not in self.index_by_sku:
            return []

        query = self._row(sku_id)
        # If query is H1, return a single blocked sentinel result
        if is_schedule_h1(query):
            return [
                SubstituteResult(
                    query_sku_id=sku_id,
                    candidate_sku_id=-1,
                    candidate_name="",
                    score=0.0,
                    source="blocked",
                    aware=aware_group(query),
                    schedule_h1=True,
                    blocked=True,
                    block_reason=H1_BLOCK_MESSAGE,
                    price_inr=float(query.get("price_inr") or 0),
                    therapeutic_class=str(query.get("Therapeutic Class") or ""),
                )
            ]

        seen: set[int] = set()
        ranked: list[tuple[int, str, float]] = []
        for item in self._explicit_candidates(query) + self._tfidf_candidates(sku_id):
            cid, source, score = item
            if cid in seen:
                continue
            seen.add(cid)
            ranked.append(item)

        # Prefer same therapeutic class slightly
        q_tc = str(query.get("Therapeutic Class") or "").strip()
        results: list[SubstituteResult] = []
        for cid, source, score in ranked:
            if require_in_stock and not self._in_stock(cid):
                continue
            cand = self._row(cid)
            # Soft boost same class for ranking before gates
            adj = score
            if q_tc and str(cand.get("Therapeutic Class") or "").strip() == q_tc:
                adj = min(1.0, score + 0.03)

            blocked, reason, ag, cand_h1 = self._gate(query, cand)
            if blocked and not include_blocked:
                continue
            results.append(
                SubstituteResult(
                    query_sku_id=sku_id,
                    candidate_sku_id=cid,
                    candidate_name=str(cand.get("name") or ""),
                    score=float(adj),
                    source=source,
                    aware=ag,
                    schedule_h1=cand_h1,
                    blocked=blocked,
                    block_reason=reason,
                    price_inr=float(cand.get("price_inr") or 0),
                    therapeutic_class=str(cand.get("Therapeutic Class") or ""),
                )
            )

        results.sort(key=lambda r: (-(not r.blocked), -r.score))
        return results[:top_n]
