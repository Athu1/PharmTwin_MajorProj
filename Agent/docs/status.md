# Development Status — PharmTwinAI

Update this file at the end of each major phase.

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| DOC-01 | Research / architecture / roadmap docs | **Completed** | 2026-09-28 |
| DOC-02 | Academic proposal PDF archived | **Blocked** | Not found in repo |
| DOC-03 | Decisions locked | **Completed** | `docs/decisions_locked.md` |
| DATA-01 | Bhagyashree raw export | **Blocked** | Using labeled synthetic (D3). Ingest adapter ready: `scripts/ingest_sales_export.py` (POS sales report xlsx; PII columns never read; default label `dev_synthetic`) |
| DATA-02 | DEV synthetic pipeline (Steps 1–5) | **Completed** | 3,000 stocked SKUs; must stay labeled SYNTHETIC. Seed shifts dates so history ends today (`--no-date-shift` to keep 2023–24). Known issue: `batches_fefo.csv` is a 2023 opening-stock snapshot (some lots expire before receipt) — fix needs Steps 1–5 rerun |
| DATA-03 | MySQL schema migration | **Completed** | `db/migrations/001_init_schema.sql` |
| DATA-04 | Seed MySQL from synthetic | **Completed** | Full catalog 253,973 + stocked 3,000 |
| INV-01 | Medicines / batches / movements UI+API | **Completed** | Add/remove working inventory; reference catalog immutable; removing a sold medicine is a soft delete (history kept); batches with sales cannot be deleted |
| DATA-05 | Originals snapshot | **Completed** | `data/originals/` + `scripts/snapshot_originals.py` |
| INV-02 | Sales / purchases / returns transactional | **Completed** | `services/stock_ops.py` + Stock page *Daily work*: FEFO sale (lost sales → `unmet_qty`), purchase receipt, customer / supplier returns, quantity correction with reason, expired write-off; DB CHECK stock ≥ 0 (migration 003); acceptance G01–G05. Purchase orders (PO → receive) still planned |
| TWIN-01 | Snapshot sync + stale detection | **Completed** | Live fingerprint in `services/twin.py`; Overview shows IN SYNC / STALE; *Refresh twin snapshot* button |
| TWIN-02 | What-if simulations (isolated) | **In progress** | Desktop Simulations: cached Step 4 + demand-shock what-if; live stock fingerprint checked |
| FC-01 | Intermittent baselines | **Completed (offline)** | Step 2 on 3k SKUs |
| FC-02 | Env LightGBM quantiles | **In progress** | 81k forecast rows in MySQL; desktop Forecasts page live |
| REC-01 | Reorder / SS recommendations | **In progress** | 3k SS/ROP recommendations; action + on-hand recomputed live after every stock transaction (sellable, non-expired stock); Step 4 parameters not retrained |
| ALT-01 | Low-stock / expiry alerts | **In progress** | Live Alerts page from batches (expiry + low stock) |
| UI-01 | Desktop app (tkinter) | **In progress** | All core nav pages live |
| UI-02 | Flask web UI | **Deferred** | Desktop-first (D2) |
| SUB-01 | H1/AWaRe/CDSCO substitutes | **In progress** | Desktop Substitutes page wraps Step 5 + live stock |
| TEST-01 | Core acceptance suite | **Completed** | `scripts/run_demo_acceptance.py` + `docs/acceptance_checklist.md` (24/24 incl. F01–F03 inventory CRUD + twin stale) |
| SCR-01 | Anemia screening MVP | **Gated** | Research placeholder only (D7=B) |
| SCR-02 | Other screening modules | **Requires approval** | D8 |

**Legend:** Completed · In progress · Planned · Blocked · Gated · Deferred
