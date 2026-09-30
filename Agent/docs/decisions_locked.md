# Locked Product Decisions — PharmTwinAI

**Locked on:** 2026-09-28  
**Project root:** `e:\MajorProject_4th_Yr\Agent` (evolve in place)

| ID | Decision | Choice |
|----|----------|--------|
| D1 | Layout | **A** — Keep evolving under `Agent`. Restructure into `app/`, `db/`, `services/` rather than a greenfield rewrite unless a hard design flaw appears. |
| D2 | UI | **Native desktop application** (not Streamlit/web-first). See counter-note below. Stack: **PySide6 (Qt)** + local Python services + MySQL. |
| D3 | Data | **No sponsor export yet.** Build **explicitly labeled synthetic** pharmacy data informed by published India / Navi Mumbai seasonal patterns. Acceptable for development and demos. |
| D4 | Substitutes | **A** — Pharmacist-reviewed inventory alternatives only (H1/AWaRe/CDSCO gated). Not clinical prescribing. |
| D5 | Env features | **A** — Weather/epi features for research/DEV; production claim only after association on real sales (when available). |
| D6 | Cloud | **A** — Local / college lab only for six months. |
| D7 | Anemia | **B** — Research docs allowed now; **no implementation** until core acceptance gate. |
| D8 | Other screening | Research-only until **explicit approval per condition**. |

---

## D2 counter-note (desktop vs web) — then commitment

**Why teams often pick web (Streamlit/Flask UI):**
- Faster charts/tables and remote demo on a LAN
- Easier multi-user access from another PC in the shop

**Why desktop is better for *this* pharmacy brief (we agree with you):**
- Feels like installable **pharmacy software**, not a notebook/dashboard
- Works offline on the counter PC without “open Chrome to localhost”
- Clearer offline security story (local MySQL, no public web surface)
- Matches “software not a web interface or agent”

**Compromise we will *not* take unless you ask later:** browser UI served only on `127.0.0.1`.

**Selected approach:** Local **desktop GUI** (tkinter now; optional PySide6 later) → in-process Python services → MySQL on localhost.

---

## Implications for build order

1. MySQL schema + migrations  
2. Trend-informed **labeled** synthetic generator → DB seed  
3. Inventory + twin services  
4. Desktop UI screens (stock, alerts, forecasts, recommendations, simulations)  
5. Wire existing Agent ML (`src/`) into services  
6. Anemia: research markdown only until gate  
