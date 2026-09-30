# Core acceptance checklist — PharmTwinAI (TEST-01)

Automated runner:

```powershell
cd e:\MajorProject_4th_Yr\Agent
py -3 scripts/apply_migration_002.py
py -3 scripts/apply_migration_003.py   # stock transactions (G checks need it)
py -3 scripts/run_demo_acceptance.py
```

Exit code **0** = required checks green (demo-ready).

## Required checks

| ID | Check |
|----|--------|
| A01 | MySQL connects (`pharmtwinai`) |
| A02 | Catalog knowledge base ≥ ~250k medicines |
| A03 | Stocked assortment ≥ 500 (target 3000) |
| A04 | FEFO batches with on-hand qty |
| A05 | Synthetic sales present |
| A06 | Digital twin snapshot exists |
| A07 | `data_mode = dev_synthetic` |
| A08 | Forecasts loaded (Step 3 LightGBM) |
| A09 | Recommendations loaded (Step 4 SS/ROP) |
| B01–B06 | Twin / inventory / alerts / forecasts / recs / substitutes services |
| C01 | Simulations do **not** mutate live `medicine_batches` |
| D01–D02 | Offline artifacts + WMAPE/MASE (not MAPE) |
| E01 | Desktop `app.main` imports |
| F01 | Inventory add → remove leaves reference catalog count unchanged |
| F02 | Deleting a reference catalog medicine is blocked (`InventoryGuardError`) |
| F03 | Twin stale detection: refresh → not stale → CRUD → stale → refresh → not stale |

| G01 | A sale takes stock from the earliest-expiry batch first (FEFO) |
| G02 | Selling more than is in stock never makes stock negative; the shortfall is saved as a lost sale (`unmet_qty`) |
| G03 | "What to order" updates live: sale → REORDER, purchase → HOLD |
| G04 | Invalid actions are refused: correction without a reason, receiving expired stock, strict oversell |
| G05 | Removing a medicine that was sold keeps its sales history (soft delete, `is_active = 0`) |

F01–F03 and G01–G05 add and remove temporary pharmacy SKUs and write twin snapshots (self-cleaning). Skip them with `--skip-write-checks`.

## Optional

| ID | Check |
|----|--------|
| A03b | Stocked assortment ≥ 3000 |

## Manual desktop walkthrough (2–3 min)

1. `py -3 scripts/run_desktop.py`
2. **Overview** — catalog ~254k, stocked count, synthetic banner, **Twin status** (IN SYNC / STALE); after an inventory edit it shows STALE until **Refresh twin snapshot**
3. **Stock (Inventory)** — search + FEFO batches; **Add medicine**; Remove medicine/batch  
   - Reference 250k catalog stays read-only (`data/originals/` snapshot)  
   - **Daily work** row: select a medicine → **Sell…** (shows which batches, earliest expiry first) → confirm; **Receive stock (purchase)…**; select a batch → **Customer return…**, **Return to supplier…**, **Correct quantity (adjust)…** (reason required), **Write off expired batch** / **Write off ALL expired**  
   - After a sale, **What to order** for that medicine changes immediately; Overview shows STALE
4. **Forecasts** — pick SKU → weekly q50/q95
5. **Recommendations** — filter REORDER → SS formula in explanation
6. **Alerts** — expiry / low stock
7. **Simulations** — Import cached Step 4; confirm stock unchanged message
8. **Substitutes** — pick stocked SKU → gated alternatives or H1 block

## Expand assortment to 3k

```powershell
py -3 scripts/run_step1.py --n-skus 3000
py -3 scripts/run_step2.py
py -3 scripts/run_step3.py
py -3 scripts/run_step4.py
py -3 scripts/run_step5.py
py -3 scripts/seed_mysql.py
py -3 scripts/load_analytics.py
py -3 scripts/run_demo_acceptance.py
```
