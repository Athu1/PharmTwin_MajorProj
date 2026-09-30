# PharmTwinAI — Research Notes

**Industry partner:** Bhagyashree Medical, Juinagar, Navi Mumbai  
**Status:** Phase 1 research (docs only; no screening implementation)  
**Last updated:** 2026-09-28  

**Limitation:** A separate academic proposal PDF was not found under `e:\MajorProject_4th_Yr`. This document interprets the Cursor project brief and the attached PharmTwinAI architecture diagram as the primary specification.

---

## 1. Requirement interpretation (concise)

PharmTwinAI is an **AI-powered digital twin** of a retail pharmacy. It must:

1. Mirror **real operational state** (stock, batches, expiry, purchases, sales).
2. **Forecast** medicine demand with chronological validation.
3. Produce **explainable purchasing / inventory recommendations**.
4. Raise **low-stock, overstock, expiry** alerts.
5. Run **what-if simulations** that never mutate live inventory.
6. Expose results via **dashboard + APIs**, optionally Power BI.
7. Treat **anemia (and other) screening as a separate extension** only after core acceptance tests pass.

It is **not** a conventional stock ledger alone, and **not** an autonomous clinical prescribing system.

---

## 2. Existing repository findings

Current code lives in `e:\MajorProject_4th_Yr\Agent` (analytics prototype, not full PharmTwinAI).

| Area | Present? | Notes |
|------|----------|-------|
| India medicine catalog (A–Z) | Yes (external CSV) | ~254k SKUs after dedupe |
| Synthetic Navi Mumbai POS + covariates | Yes | **Labeled development data** — not Bhagyashree sales |
| Intermittent forecasting (Croston/SBA/TSB) | Yes | WMAPE/MASE |
| Env-conditioned LightGBM (q50/q90/q95) | Yes | Rain / PM2.5 features |
| FEFO + safety stock + OTC markdown sim | Yes | Offline simulation |
| TF-IDF substitutes + H1/AWaRe/CDSCO gates | Yes | Decision-support only |
| MySQL schema / migrations | **No** | |
| Flask / Streamlit / auth | **No** | |
| Live digital twin sync | **No** | |
| Import pipeline for sponsor Excel/CSV | **No** | |
| What-if UI | **No** | Logic partially reusable from Step 4 sim |
| Anemia screening | **No** (correctly deferred) | |

**Critical labeling rule:** All current `data/processed/transactions_synthetic.*` must remain tagged **DEV / SYNTHETIC**. Never present them as Bhagyashree Medical sales.

---

## 3. Industry data status (Bhagyashree Medical)

| Item | Status |
|------|--------|
| Historical sales export | **Not yet in repository** |
| Current stock / batches | **Not yet in repository** |
| Purchase / supplier files | **Not yet in repository** |
| Access method | Awaiting sponsor handoff (CSV/Excel/DB dump) |

### When data arrives — inspect checklist

- Columns present vs missing (see `data_dictionary.md` target entities)
- Date formats, encoding, medicine name variants
- Whether stockouts vs missing days can be distinguished
- Batch/expiry coverage
- PII / customer identifiers (must be stripped or hashed)

Until then, development continues on **explicitly labeled** synthetic + public reference datasets only.

---

## 4. Seasonal / epidemiological context (Navi Mumbai / Maharashtra)

Public signals support **monsoon vector-borne pressure** (malaria, dengue, fever workups) as a *possible* external feature family — **not** as direct proof of pharmacy SKU sales.

| Source | Coverage | Use in PharmTwinAI | Limitation |
|--------|----------|--------------------|------------|
| NMMC civic reports (news / bulletins) | Navi Mumbai case counts (often lagging, sometimes incomplete) | Qualitative validation of monsoon hypothesis | Not machine-friendly; confirmation rules (e.g. NIV for dengue) matter |
| NHM Maharashtra NVBDCP | State malaria / dengue tables | Aggregate seasonal covariates | State ≠ Juinagar pharmacy demand |
| IMD / Open-Meteo rainfall | Local weather | Lagged rain features (already prototyped) | Weather ≠ disease ≠ sales |
| CPCB / AQICN PM2.5 | Local air quality | Winter respiratory covariates (prototyped) | Not patient-level |

**Rule:** External epi/weather features enter models only after association checks on **sponsor sales** (or remain exploratory on DEV data).

---

## 5. Public pharmaceutical reference sources (for knowledge base)

| Source | Role | License / access note |
|--------|------|------------------------|
| WHO AWaRe classification (2021/2023/2025 Excel) | Antibiotic stewardship tags | WHO publications — download and cite |
| CDSCO Data Bank / Drugs@CDSCO | Regulatory context, discontinued / FDC notices | Scrape/API limited; manual curation often required |
| Existing A–Z India medicines CSV | Brand/composition/therapeutic fields | Already used; verify redistribution rights before public repos |
| openFDA / PubChem / NIH | Ingredient normalization research | US-centric; map carefully to Indian brands |
| Kaggle pharmacy / anemia image sets | Research / screening later | Check each dataset license; anemia only post–core gate |

---

## 6. Research gaps / blocked items

1. **Sponsor raw files not received** → cannot complete real data dictionary or quality report.
2. **Proposal PDF not in tree** → confirm with team if a signed copy should be archived under `docs/proposal/`.
3. Some academic papers behind paywalls — document as inaccessible when reviewing anemia (deferred).
4. No free, complete India retail pharmacy POS open dataset equivalent to Bhagyashree’s private ledger.

---

## 7. Immediate research next actions

1. Request Bhagyashree export (sales, stock, batches, purchases) under NDA / privacy protocol (`data_privacy.md`).
2. Build import adapters against **sample schema** using labeled DEV data.
3. Download WHO AWaRe Excel into `data/reference/` (not public git if license unclear — prefer documented fetch script).
4. Keep screening research in notes only until core acceptance.
