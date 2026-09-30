# Synthetic Data Design — Trend-Informed DEV Dataset

**Label:** `source_system = 'dev_synthetic'` — **not** Bhagyashree Medical sales.  
**Purpose:** Develop and demo PharmTwinAI until sponsor data arrives (D3).

---

## 1. External patterns used (proxies, not POS)

These inform **seasonal multipliers** only. They are **not** treated as units sold.

| Pattern | Evidence class | Synthetic effect |
|---------|----------------|------------------|
| Monsoon ↑ vector-borne / fever workups (Jun–Sep) | NMMC / NHM Maharashtra NVBDCP public reporting; civic monsoon fever narratives | ↑ demand for antimalarial / fever / ORS / selected anti-infective cohorts with **7–14 day rain lag** |
| Winter ↑ respiratory / allergy (Nov–Feb) | Common India retail pharmacy seasonality (respiratory OTC, antihistamines, inhalers) | ↑ RESPIRATORY cohort with **high PM2.5** same-week |
| Relatively stable chronic meds | Typical year-round cardiac / diabetic / thyroid retail base | Low seasonality, steadier intermittent demand |
| Antibiotics stewardship | WHO AWaRe | Generated for inventory realism; substitute engine still gates Watch/Reserve |

**Limitation:** Without Bhagyashree POS we cannot estimate true elasticities. Multipliers are **scenario assumptions** documented here for reproducibility (seed=42).

---

## 2. Assortment

- Sample ~3,000 active SKUs from India A–Z catalog (existing Step 1 logic).
- Force representation of `respiratory` and `vector_borne` cohorts.

## 3. Covariates (Navi Mumbai–like)

- Daily rainfall with monsoon mixture; heavy-rain >20 mm events.
- PM2.5 elevated in winter.
- Derived alerts: leptospirosis / dengue / air-quality flags (synthetic thresholds).

## 4. Demand process

Per SKU intermittent: \(P(D>0)\) × size, with cohort × env multipliers (existing generator, refined profiles below).

| Cohort | Base rate | Peak driver |
|--------|-----------|-------------|
| respiratory | Higher | Winter + PM2.5 |
| vector_borne | Medium | Rain lag 7–14d + monsoon alerts |
| chronic (cardiac, anti-diabetic, …) | Lower variance | Mild winter bump only |
| other | Sparse | Weak seasonality |

## 5. Batches / FEFO

Multiple lots per SKU, staggered expiry — enables twin expiry alerts and FEFO demos.

## 6. Regeneration

```powershell
py -3 scripts/run_step1.py --n-skus 3000
py -3 scripts/seed_mysql.py   # after MySQL is up
```

All rows must remain queryable as DEV synthetic in the desktop UI (badge / watermark).
