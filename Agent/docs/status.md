# Development Status — PharmTwinAI

Update this file at the end of each major phase.

| ID | Feature | Status | Notes |
|----|---------|--------|-------|
| DOC-01 | Research / architecture / roadmap docs | **Completed** | 2026-09-28 |
| DOC-02 | Academic proposal PDF archived | **Blocked** | Not found in repo |
| DOC-03 | Decisions locked | **Completed** | `docs/decisions_locked.md` |
| DATA-01 | Bhagyashree raw export | **Blocked** | Using labeled synthetic (D3) |
| DATA-02 | DEV synthetic pipeline (Steps 1–5) | **Completed** | 3,000 stocked SKUs; must stay labeled SYNTHETIC |
| DATA-03 | MySQL schema migration | **Completed** | `db/migrations/001_init_schema.sql` |
| DATA-04 | Seed MySQL from synthetic | **Completed** | Full catalog 253,973 + stocked 3,000 |
| INV-01 | Medicines / batches / movements UI+API | **In progress** | Add/remove working inventory (form, qty unit, mfg/expiry); reference catalog immutable |
| DATA-05 | Originals snapshot | **Completed** | `data/originals/` + `scripts/snapshot_originals.py` |
| INV-02 | Sales / purchases / returns transactional | **Planned** | |
| TWIN-01 | Snapshot sync + stale detection | **In progress** | Seed writes snapshot; UI reads summary |
| TWIN-02 | What-if simulations (isolated) | **In progress** | Desktop Simulations: cached Step 4 + demand-shock what-if; live stock fingerprint checked |
| FC-01 | Intermittent baselines | **Completed (offline)** | Step 2 on 3k SKUs |
| FC-02 | Env LightGBM quantiles | **In progress** | 81k forecast rows in MySQL; desktop Forecasts page live |
| REC-01 | Reorder / SS recommendations | **In progress** | 3k SS/ROP recommendations; desktop page live |
| ALT-01 | Low-stock / expiry alerts | **In progress** | Live Alerts page from batches (expiry + low stock) |
| UI-01 | Desktop app (tkinter) | **In progress** | All core nav pages live |
| UI-02 | Flask web UI | **Deferred** | Desktop-first (D2) |
| SUB-01 | H1/AWaRe/CDSCO substitutes | **In progress** | Desktop Substitutes page wraps Step 5 + live stock |
| TEST-01 | Core acceptance suite | **Completed** | `scripts/run_demo_acceptance.py` + `docs/acceptance_checklist.md` (21/21) |
| SCR-01 | Anemia screening MVP | **Gated** | Research placeholder only (D7=B) |
| SCR-02 | Other screening modules | **Requires approval** | D8 |

**Legend:** Completed · In progress · Planned · Blocked · Gated · Deferred
