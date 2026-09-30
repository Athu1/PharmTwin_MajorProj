# Prioritized Development Backlog — PharmTwinAI

Ordered for dependency safety. Do not start SCR-* until core acceptance.

## P0 — Unblock data & foundation

1. **Obtain Bhagyashree export** (sales, stock, batches, purchases) under privacy protocol  
2. **Archive proposal PDF** to `docs/proposal/`  
3. **Create MySQL DB + apply schema migrations** from `architecture.md`  
4. ~~**Ingest adapter** CSV/Excel → staging → validated tables~~ — done (`scripts/ingest_sales_export.py`, sales report format)  
5. **Load DEV synthetic** with `source_system='dev_synthetic'` for CI demos  

## P1 — Inventory truth

6. Medicine + batch CRUD  
7. Stock movement ledger  
8. Post sale / purchase / return (transactions + FEFO allocation suggestion)  
9. Inventory consistency tests  

## P2 — Digital twin core

10. Twin snapshot builder from live tables  
11. ~~Twin sync timestamp + stale flag~~ — done (`services/twin.py`, Overview)  
12. Twin vs DB validation tests  

## P3 — Forecast & recommend

13. Demand coverage calendar (no silent zeros)  
14. Wire Agent Croston/SBA/TSB (+ optional LightGBM) to write `forecasts`  
15. Recommendation service (`SS = Z σ √(L+R)`) with explanation text  
16. Alert job: low stock, expiry, overstock  

## P4 — Simulation & UI

17. What-if simulation API (demand shock, lead-time delay, spike)  
18. Streamlit: inventory / forecast / recommendations / twin / sim  
19. Roles: OWNER / STAFF / ANALYST  

## P5 — Harden

20. E2E demo script + acceptance checklist automation  
21. Performance indexes + basic load test  
22. Industry pilot on sponsor data + recalibration  

## Gated — Screening

23. Anemia research doc + accessible references log  
24. Anemia MVP **only after** acceptance criteria 1–10 pass  
25. Other screening modules — **explicit user approval required**
