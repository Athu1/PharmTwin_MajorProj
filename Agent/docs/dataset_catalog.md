# Dataset Catalog — PharmTwinAI

All entries distinguish **actual sales**, **proxies**, and **reference master data**.  
Do **not** merge proxy indicators as if they were pharmacy POS.

---

## A. Industry / project-local

| ID | Name | Type | Geo | Period | Granularity | Status | License / confidentiality |
|----|------|------|-----|--------|-------------|--------|---------------------------|
| IND-001 | Bhagyashree Medical operational export | Actual pharmacy sales + inventory | Juinagar, Navi Mumbai | TBD | TBD | **Not received** | Confidential — sponsor NDA |
| DEV-001 | `Extensive_A_Z_medicines_dataset_of_India.csv` | Medicine master / compositions | India | Static snapshot | SKU | Available on disk | Verify redistribution before publishing |
| DEV-002 | Agent synthetic transactions + batches + covariates | **Labeled synthetic POS** | Simulated Navi Mumbai | 2023–2024 daily | SKU-day | Generated in `data/processed/` | Internal DEV only — **not real sales** |

### DEV-002 fields (summary)

Transactions: `date, sku_id, qty, unmet_qty, unit_price, revenue, batch_ids, stockout, rain_*, pm25, aqi_category, health_alert_flag`  
Batches: `batch_id, sku_id, receipt_date, expiry_date, qty_* , unit_cost`  
Covariates: rain lags, PM2.5, alerts  

**Limitation:** Engineered demand with env multipliers — useful for pipeline tests, **not** industry validation.

---

## B. Authoritative reference (public)

| ID | Name | Type | Source | Use | Limitation |
|----|------|------|--------|-----|------------|
| REF-001 | WHO AWaRe antibiotic classification | Drug class labels | who.int / iris.who.int Excel | Stewardship filters | Not sales |
| REF-002 | CDSCO notices / Data Bank | Regulatory | cdsco.gov.in | Banned FDC / discontinuation checks | Often PDF/HTML, incomplete machine feeds |
| REF-003 | NHM Maharashtra NVBDCP tables | Disease incidence (state) | nhm.maharashtra.gov.in | Optional seasonal covariate research | State-level; not pharmacy sales |
| REF-004 | NMMC dengue/malaria bulletins | Local incidence (irregular) | Civic / press releases | Qualitative monsoon narrative | Incomplete, lagging, definitional caveats |
| REF-005 | Open-Meteo / IMD rainfall | Weather | Public APIs / IMD | Lagged rain features | Weather ≠ demand |
| REF-006 | CPCB / AQICN PM2.5 | Air quality | Public monitors | Winter respiratory features | Station coverage varies |

---

## C. Research / screening (deferred implementation)

| ID | Name | Type | Notes |
|----|------|------|-------|
| SCR-001 | Eyes Defy Anemia (Kaggle) | Conjunctiva images | Cite license; **patient-level** splits required; implement only after core acceptance |
| SCR-002 | HarshSaxena837 GitHub anemia project | Code reference | Educational; validate methods independently |

---

## D. Acquisition plan

| Priority | Action | Owner | Blocker |
|----------|--------|-------|---------|
| P0 | Obtain Bhagyashree CSV/Excel under privacy protocol | Team + sponsor | Awaiting data |
| P0 | Archive proposal PDF under `docs/proposal/` | Team | File not in repo |
| P1 | Scripted fetch + checksum for WHO AWaRe Excel → `data/reference/` | ML eng | Network + license note |
| P1 | Document DEV-001 redistribution rights | Team | Legal/check source |
| P2 | Prototype Open-Meteo pull for Juinagar lat/lon | Data eng | Optional until real sales |
| P3 | Anemia dataset download | Screening lead | **Gated** until core acceptance |

---

## E. Combining data safely

| Allowed | Forbidden |
|---------|-----------|
| Join sales ↔ medicine master on normalized name/SKU | Treat NVBDCP cases as pharmacy units sold |
| Use weather as **features** with disclosed uncertainty | Claim synthetic POS is Bhagyashree history |
| Use AWaRe/CDSCO for **gates / labels** | Auto-prescribe from screening images |
