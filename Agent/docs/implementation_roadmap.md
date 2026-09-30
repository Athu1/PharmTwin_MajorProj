# Six-Month Implementation Roadmap — PharmTwinAI

**Team size:** 4 students  
**Sponsor:** Bhagyashree Medical, Juinagar  
**Constraint:** Core (priorities 1–9) before anemia screening implementation.

If Bhagyashree data arrives late, Months 1–2 use labeled DEV data + import pipeline; industry validation shifts right but schema/API still advance.

---

## Month 1 — Research, architecture, data foundation

| Week | Focus | Deliverables |
|------|-------|--------------|
| 1 | Spec lock, privacy, dataset catalog | `docs/*` (this pack), sponsor data request |
| 2 | MySQL schema + migrations | Alembic/Flyway or raw SQL migrations |
| 3 | Ingestion skeleton (CSV/Excel) | Staging tables, validation report |
| 4 | Seed DEV synthetic → MySQL | Labeled `source_system=dev_synthetic` |

**Exit criteria:** Empty or DEV-filled DB creatable from docs; privacy rules agreed.

---

## Month 2 — Inventory + digital twin sync

| Week | Focus |
|------|-------|
| 1 | Medicines, batches, stock movements API |
| 2 | Sales / purchase / return posting with transactional integrity |
| 3 | Twin snapshot builder + stale flag |
| 4 | Twin sync tests vs DB |

**Exit criteria:** Sale/purchase/return keep batch qty consistent; twin `synced_at` visible.

---

## Month 3 — Forecasting & seasonality

| Week | Focus |
|------|-------|
| 1 | Demand coverage calendar (no silent zeros) |
| 2 | Port Croston/SBA/TSB + metrics into services |
| 3 | LightGBM/env features **only if** sponsor or DEV association supports |
| 4 | Holdout evaluation dashboard section |

**Exit criteria:** Chronological backtest reports WAPE/MASE; forecasts stored in MySQL.

---

## Month 4 — Recommendations, alerts, simulations

| Week | Focus |
|------|-------|
| 1 | Safety stock / ROP recommendations + explanation text |
| 2 | Low-stock / expiry / overstock alerts |
| 3 | What-if engine (demand +20%, lead-time +7d, etc.) |
| 4 | FEFO suggestions on dispense/allocate |

**Exit criteria:** Simulations never mutate inventory tables; recommendations cite inputs.

---

## Month 5 — Dashboard, security, hardening

| Week | Focus |
|------|-------|
| 1 | Streamlit: inventory + forecast + recommendations + twin |
| 2 | RBAC, audit logs, export CSV |
| 3 | Performance indexes, load tests on key queries |
| 4 | Integration / E2E tests; bug bash |

**Exit criteria:** Demo script runnable from README; core acceptance checklist green or nearly green.

---

## Month 6 — Industry validation + polish; screening only if ready

| Week | Focus |
|------|-------|
| 1 | Sponsor data validation / calibration |
| 2 | Fix defects from industry pilot |
| 3 | Documentation, video demo, handover |
| 4 | **If and only if** acceptance criteria met: start anemia module research→MVP |

**Trade-off if behind:** Drop Power BI, defer LightGBM (keep intermittent baselines), keep Streamlit-only UI, postpone substitute NLP polish — **never** start screening before core gate.

---

## Parallel (research-only) track

- Secondary screening literature notes (`medical_screening_candidates.md` — create when research starts)
- Anemia references listed in brief — document accessible vs inaccessible
- **No model training in prod path** until Month 6 gate

---

## Team swimlanes (suggested)

| Member | Primary | Secondary |
|--------|---------|-----------|
| A | MySQL + ingestion | Twin sync |
| B | Inventory APIs + FEFO | Alerts |
| C | Forecasting + evaluation | Recommendations |
| D | Streamlit + auth + docs | Simulation UI |

Rotate for bus-factor coverage on twin + inventory integrity.
