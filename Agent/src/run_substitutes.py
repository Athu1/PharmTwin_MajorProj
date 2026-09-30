"""Step 5: substitute recommendations with H1 / AWaRe / CDSCO gates."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from .regulatory import aware_group, is_banned_fdc, is_schedule_h1
from .substitutes_nlp import SubstituteEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_OUT = PROJECT_ROOT / "data" / "processed"


def _estimate_stock(assortment: pd.DataFrame, batches_path: Path, seed: int = 42) -> dict[int, float]:
    """On-hand proxy from FEFO batches (qty_remaining), with random OOS for demo."""
    rng = np.random.default_rng(seed)
    stock = {int(s): 0.0 for s in assortment["sku_id"]}
    if batches_path.exists():
        batches = pd.read_csv(batches_path)
        for sku, qty in batches.groupby("sku_id")["qty_remaining"].sum().items():
            stock[int(sku)] = float(qty)
    # Force ~12% random stockouts for recommendation stress-test
    skus = list(stock.keys())
    n_oos = max(1, int(0.12 * len(skus)))
    for sid in rng.choice(skus, size=n_oos, replace=False):
        stock[int(sid)] = 0.0
    return stock


def _stockout_queries(
    assortment: pd.DataFrame,
    stock: dict[int, float],
    transactions_path: Path,
    n_queries: int = 200,
    seed: int = 42,
) -> list[int]:
    """Prefer real stockout SKUs from synthetic transactions; fall back to zero-stock."""
    rng = np.random.default_rng(seed)
    oos = [int(s) for s, q in stock.items() if q <= 0]
    tx_path = transactions_path
    if tx_path.with_suffix(".parquet").exists():
        tx_path = tx_path.with_suffix(".parquet")
    try:
        tx = (
            pd.read_parquet(tx_path)
            if tx_path.suffix == ".parquet"
            else pd.read_csv(tx_path, usecols=["sku_id", "stockout"])
        )
        hit = (
            tx.loc[tx["stockout"] == 1, "sku_id"]
            .astype(int)
            .value_counts()
            .index.tolist()
        )
        hit = [s for s in hit if s in set(assortment["sku_id"].astype(int))]
    except Exception:
        hit = []

    ordered = []
    for s in hit + oos:
        if s not in ordered:
            ordered.append(s)
    if len(ordered) < n_queries:
        extra = [int(s) for s in assortment["sku_id"] if int(s) not in ordered]
        ordered.extend(list(rng.choice(extra, size=min(n_queries - len(ordered), len(extra)), replace=False)))
    return ordered[:n_queries]


def run_step5(
    n_queries: int = 200,
    top_n: int = 5,
    min_cosine: float = 0.55,
    seed: int = 42,
    out_dir: Path | str | None = None,
) -> dict[str, Path]:
    out = Path(out_dir) if out_dir else DATA_OUT
    out.mkdir(parents=True, exist_ok=True)

    print("Loading assortment...")
    assortment = pd.read_csv(out / "assortment_3k.csv")
    assortment["sku_id"] = assortment["sku_id"].astype(int)

    # Annotate regulatory labels for audit
    print("Annotating Schedule H1 / AWaRe / CDSCO flags...")
    assortment["schedule_h1"] = assortment.apply(is_schedule_h1, axis=1)
    assortment["aware_group"] = assortment.apply(aware_group, axis=1)
    banned_flags = assortment.apply(lambda r: is_banned_fdc(r), axis=1)
    assortment["cdsco_banned"] = [b for b, _ in banned_flags]
    assortment["cdsco_reason"] = [reason for _, reason in banned_flags]

    annot_path = out / "step5_assortment_regulatory.csv"
    assortment.to_csv(annot_path, index=False)
    print(
        f"  H1={int(assortment['schedule_h1'].sum())} | "
        f"AWaRe Watch/Reserve="
        f"{int(assortment['aware_group'].isin(['Watch', 'Reserve']).sum())} | "
        f"CDSCO banned/discontinued={int(assortment['cdsco_banned'].sum())}"
    )

    stock = _estimate_stock(assortment, out / "batches_fefo.csv", seed=seed)
    stock_path = out / "step5_stock_snapshot.csv"
    pd.DataFrame({"sku_id": list(stock.keys()), "on_hand": list(stock.values())}).to_csv(
        stock_path, index=False
    )

    print("Fitting TF-IDF substitute engine...")
    engine = SubstituteEngine.fit(assortment, stock=stock, min_cosine=min_cosine)

    queries = _stockout_queries(
        assortment,
        stock,
        out / "transactions_synthetic.csv",
        n_queries=n_queries,
        seed=seed,
    )
    print(f"Running recommendations for {len(queries)} stockout / OOS queries...")

    rows = []
    audit = {
        "n_queries": 0,
        "n_with_any_allowed": 0,
        "n_h1_query_blocked": 0,
        "n_candidates_considered": 0,
        "n_blocked_h1": 0,
        "n_blocked_aware": 0,
        "n_blocked_cdsco": 0,
        "n_blocked_habit": 0,
        "n_allowed_recommendations": 0,
        "n_explicit": 0,
        "n_tfidf": 0,
    }

    for sku_id in tqdm(queries, desc="Substitutes"):
        audit["n_queries"] += 1
        # Include blocked for audit counts
        all_cands = engine.recommend(
            sku_id, top_n=20, require_in_stock=True, include_blocked=True
        )
        allowed = [r for r in all_cands if not r.blocked and r.candidate_sku_id > 0]
        blocked = [r for r in all_cands if r.blocked]

        if all_cands and all_cands[0].source == "blocked" and all_cands[0].schedule_h1:
            audit["n_h1_query_blocked"] += 1
            rows.append(
                {
                    "query_sku_id": sku_id,
                    "query_name": engine._row(sku_id)["name"],
                    "query_aware": aware_group(engine._row(sku_id)),
                    "query_schedule_h1": True,
                    "rank": 0,
                    "candidate_sku_id": None,
                    "candidate_name": None,
                    "score": 0.0,
                    "source": "blocked",
                    "aware": all_cands[0].aware,
                    "blocked": True,
                    "block_reason": all_cands[0].block_reason,
                    "allowed": False,
                }
            )
            continue

        if allowed:
            audit["n_with_any_allowed"] += 1

        for r in blocked:
            audit["n_candidates_considered"] += 1
            reason = r.block_reason.lower()
            if "schedule h1" in reason:
                audit["n_blocked_h1"] += 1
            elif "aware" in reason:
                audit["n_blocked_aware"] += 1
            elif "cdsco" in reason or "discontinued" in reason:
                audit["n_blocked_cdsco"] += 1
            elif "habit" in reason:
                audit["n_blocked_habit"] += 1

        for rank, r in enumerate(allowed[:top_n], start=1):
            audit["n_allowed_recommendations"] += 1
            audit["n_candidates_considered"] += 1
            if r.source == "explicit":
                audit["n_explicit"] += 1
            else:
                audit["n_tfidf"] += 1
            qrow = engine._row(sku_id)
            rows.append(
                {
                    "query_sku_id": sku_id,
                    "query_name": qrow["name"],
                    "query_aware": aware_group(qrow),
                    "query_schedule_h1": bool(is_schedule_h1(qrow)),
                    "rank": rank,
                    "candidate_sku_id": r.candidate_sku_id,
                    "candidate_name": r.candidate_name,
                    "score": r.score,
                    "source": r.source,
                    "aware": r.aware,
                    "blocked": False,
                    "block_reason": "",
                    "allowed": True,
                    "candidate_price_inr": r.price_inr,
                    "candidate_therapeutic_class": r.therapeutic_class,
                }
            )

        if not allowed and not (all_cands and all_cands[0].source == "blocked"):
            qrow = engine._row(sku_id)
            rows.append(
                {
                    "query_sku_id": sku_id,
                    "query_name": qrow["name"],
                    "query_aware": aware_group(qrow),
                    "query_schedule_h1": bool(is_schedule_h1(qrow)),
                    "rank": 0,
                    "candidate_sku_id": None,
                    "candidate_name": None,
                    "score": 0.0,
                    "source": "none",
                    "aware": "",
                    "blocked": False,
                    "block_reason": "No in-stock substitute passed regulatory gates",
                    "allowed": False,
                }
            )

    rec_df = pd.DataFrame(rows)
    rec_path = out / "step5_substitute_recommendations.csv"
    rec_df.to_csv(rec_path, index=False)

    # Worked examples for the report
    examples = []
    # 1) Respiratory OTC-like success
    resp = assortment[assortment["demand_cohort"] == "respiratory"]["sku_id"].tolist()
    for sid in resp[:50]:
        if stock.get(int(sid), 1) > 0:
            # invent OOS for example
            pass
        recs = engine.recommend(int(sid), top_n=3, require_in_stock=True)
        if recs and not recs[0].blocked and recs[0].candidate_sku_id > 0:
            examples.append(
                {
                    "case": "respiratory_otc_ok",
                    "query_sku_id": int(sid),
                    "query_name": engine._row(int(sid))["name"],
                    "recommendations": [
                        {
                            "sku_id": r.candidate_sku_id,
                            "name": r.candidate_name,
                            "score": r.score,
                            "source": r.source,
                            "aware": r.aware,
                        }
                        for r in recs
                        if not r.blocked
                    ],
                }
            )
            break

    # 2) H1 block example
    h1_skus = assortment.loc[assortment["schedule_h1"], "sku_id"].tolist()
    if h1_skus:
        sid = int(h1_skus[0])
        recs = engine.recommend(sid, top_n=3, include_blocked=True)
        examples.append(
            {
                "case": "schedule_h1_block",
                "query_sku_id": sid,
                "query_name": engine._row(sid)["name"],
                "block_reason": recs[0].block_reason if recs else "",
                "recommendations": [],
            }
        )

    # 3) Watch antibiotic block
    watch = assortment.loc[assortment["aware_group"] == "Watch", "sku_id"].tolist()
    for sid in watch[:80]:
        # Find a Watch query that has TF-IDF neighbors but all blocked
        recs = engine.recommend(int(sid), top_n=5, require_in_stock=False, include_blocked=True)
        blocked_aware = [r for r in recs if r.blocked and "AWaRe" in r.block_reason]
        if blocked_aware:
            examples.append(
                {
                    "case": "aware_watch_block",
                    "query_sku_id": int(sid),
                    "query_name": engine._row(int(sid))["name"],
                    "blocked_examples": [
                        {
                            "sku_id": r.candidate_sku_id,
                            "name": r.candidate_name,
                            "aware": r.aware,
                            "reason": r.block_reason,
                        }
                        for r in blocked_aware[:3]
                    ],
                }
            )
            break

    audit["pct_queries_with_allowed_sub"] = (
        100.0 * audit["n_with_any_allowed"] / audit["n_queries"] if audit["n_queries"] else 0.0
    )
    audit["aware_distribution"] = assortment["aware_group"].value_counts().to_dict()
    audit["examples"] = examples
    audit["notes"] = (
        "TF-IDF + cosine on composition/chemical/therapeutic text; "
        "explicit substitute0-4 preferred when in-stock; "
        "Schedule H1 hard-block; WHO AWaRe Watch/Reserve blocked for OTC auto-path; "
        "CDSCO banned FDC + Is_discontinued + Habit Forming gated."
    )

    summary_path = out / "step5_summary.json"
    summary_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    audit_csv = out / "step5_audit_counts.csv"
    pd.DataFrame(
        [{k: v for k, v in audit.items() if not isinstance(v, (dict, list))}]
    ).to_csv(audit_csv, index=False)

    print("\n=== Step 5 substitute audit ===")
    for k in (
        "n_queries",
        "n_with_any_allowed",
        "n_h1_query_blocked",
        "n_allowed_recommendations",
        "n_blocked_h1",
        "n_blocked_aware",
        "n_blocked_cdsco",
        "n_explicit",
        "n_tfidf",
        "pct_queries_with_allowed_sub",
    ):
        print(f"  {k}: {audit[k]}")
    print(f"  AWaRe distribution: {audit['aware_distribution']}")
    if examples:
        print(f"  Worked examples: {[e['case'] for e in examples]}")

    return {
        "recommendations": rec_path,
        "regulatory_annotations": annot_path,
        "stock_snapshot": stock_path,
        "audit": audit_csv,
        "summary": summary_path,
    }


if __name__ == "__main__":
    run_step5()
