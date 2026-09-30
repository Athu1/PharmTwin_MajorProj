# Data Dictionary — PharmTwinAI (Target MySQL Model)

This dictionary describes the **intended production schema**.  
Bhagyashree columns will be mapped into these entities after inspection of the real export.

Status legend: **Target** = designed; **Mapped (DEV)** = filled from current Agent synthetic/catalog; **Unmapped** = awaiting sponsor data.

---

## 1. Entity overview

| Entity | Purpose |
|--------|---------|
| `medicines` | SKU / product master |
| `medicine_categories` | Therapeutic / operational categories |
| `manufacturers` | Marketing authorization holders |
| `suppliers` | Wholesalers / distributors |
| `medicine_batches` | Lot + expiry + cost |
| `inventory_balances` | Current on-hand by batch (or derived view) |
| `sales_transactions` / `sales_items` | POS header/lines |
| `purchase_orders` / `purchase_order_items` | Inbound supply |
| `stock_movements` | Auditable ledger |
| `returns` | Customer / supplier returns |
| `expiry_writeoffs` | Expired stock disposal |
| `alerts` | Low stock / expiry / overstock |
| `forecasts` | Model outputs per medicine × horizon |
| `recommendations` | Purchasing suggestions + explanations |
| `digital_twin_snapshots` | Serialized twin state + sync metadata |
| `simulation_runs` / `simulation_results` | What-if scenarios (isolated) |
| `users` / `roles` | RBAC |

---

## 2. Core fields (selected)

### medicines
| Column | Type | Notes | Status |
|--------|------|-------|--------|
| medicine_id | PK INT | Surrogate | Target |
| sku_code | VARCHAR | External/barcode if any | Unmapped |
| name | VARCHAR | Brand display name | Mapped (DEV) from catalog `name` |
| generic_name | VARCHAR | Normalized INN | Partial (parse composition) |
| manufacturer_id | FK | | Mapped (DEV) name→id |
| category_id | FK | Therapeutic class | Mapped (DEV) |
| pack_size_label | VARCHAR | | Mapped (DEV) |
| rx_flag | ENUM | OTC / H / H1 / X (curated) | Partial (H1 rules exist) |
| is_active | BOOL | | Mapped (DEV) `Is_discontinued` |
| unit_mrp | DECIMAL | Selling price | Mapped (DEV) `price_inr` |

### medicine_batches
| Column | Type | Notes | Status |
|--------|------|-------|--------|
| batch_id | PK | | Mapped (DEV) |
| medicine_id | FK | | Mapped (DEV) |
| batch_no | VARCHAR | Manufacturer batch | DEV synthetic id |
| mfg_date | DATE | | Mapped (DEV) |
| expiry_date | DATE | FEFO key | Mapped (DEV) |
| qty_on_hand | DECIMAL | | Mapped (DEV) |
| unit_cost | DECIMAL | | Mapped (DEV) |

### sales_items
| Column | Type | Notes | Status |
|--------|------|-------|--------|
| sale_item_id | PK | | Target |
| sale_id | FK | | Target |
| medicine_id | FK | | Mapped (DEV) `sku_id` |
| batch_id | FK NULL | FEFO allocation | Mapped (DEV) |
| qty | DECIMAL | Sold qty | Mapped (DEV) |
| unit_price | DECIMAL | | Mapped (DEV) |
| sale_datetime | DATETIME | | Mapped (DEV) `date` |
| demand_flag | ENUM | `observed` / `unmet` / `unknown_gap` | Critical — see rules |

### Demand semantics (non-negotiable)

| Situation | Representation |
|-----------|----------------|
| Documented sale of 0 on an open day | `qty=0`, `demand_flag=observed` |
| No row / closed / missing export day | **No invented zero** — gap table or NULL coverage |
| Stockout unmet demand | Separate `unmet_qty` / movement type — not silent zero sales |

---

## 3. Forecast / recommendation outputs

### forecasts
`medicine_id, horizon_start, horizon_end, grain (D/W/M), yhat, yhat_lower, yhat_upper, model_name, trained_through, metrics_json, created_at`

### recommendations
`medicine_id, action_type (reorder|hold|review_expiry), qty_suggested, current_stock, forecast_demand, incoming_po_qty, safety_stock, reorder_point, explanation_text, assumptions_json, created_at`

---

## 4. Digital twin

### digital_twin_snapshots
`snapshot_id, synced_at, source_hash, is_stale, state_json`  

`state_json` includes stock, batches, velocity, open POs, risks, inventory value.

### simulation_runs
`run_id, base_snapshot_id, scenario_json, created_by, created_at` — **never writes** to inventory tables.

---

## 5. Mapping from current Agent files

| Agent artifact | Target entity |
|----------------|---------------|
| `assortment_3k.csv` | medicines (+ categories, manufacturers) |
| `batches_fefo.csv` | medicine_batches |
| `transactions_synthetic.csv` | sales_items (DEV label) |
| `step3_forecasts_weekly.*` | forecasts |
| `step4_safety_stock_params.csv` | recommendations inputs |
| `step5_*` | knowledge / substitute audit (not clinical Rx) |
| POS "Customer wise sales Report" xlsx/csv | sales_transactions / sales_items / stock_movements via `scripts/ingest_sales_export.py` |

---

## 6. Sales export format (ingest adapter)

`services/sales_ingest.py` reads the POS "Customer wise sales Report" (title row, customer row, then header row — auto-detected).

| Export column | Canonical | Stored in |
|---------------|-----------|-----------|
| Vou.No. + Type + Date | voucher key (sha1 → `sales_transactions.channel = export:<hash>`) | idempotency: re-runs skip loaded vouchers |
| Date | `sold_at` | `sales_transactions.sold_at` |
| Product | `product` → normalised name match | `sales_items.medicine_id` |
| Qty. | units sold | `sales_items.qty`, `stock_movements.qty_delta` (negative) |
| Amount / Qty. | per-unit price (Rate is per pack; Amount = Qty/Unit × Rate) | `sales_items.unit_price` |
| Batch | lot match on (medicine_id, batch_no) if present | `sales_items.batch_id` (else NULL) |
| Unit, Pack, Comp., Expiry | staging / validation only | — |
| **Doct Name, Doct Add, Pat Name, Pat Add, Mobile**, customer title row | **never read** (column allowlist) | — |

Rules: dry-run by default; `--commit` writes. Label defaults to `dev_synthetic`; real exports require `--source-system sponsor` and belong in `data/raw/sponsor/` (gitignored). `--create-missing` adds working-inventory rows (cloned from the reference catalog when the name matches; the reference row is never modified). Historical import does **not** change `medicine_batches.qty_on_hand`. Rejects → `data/processed/ingest_rejects.csv`; unmatched products → `data/processed/ingest_unmatched_products.csv`.

Full DDL: see `architecture.md` § Database schema.

---

## 7. Stock transactions (INV-02) and demo dates

**Movement types** (`stock_movements.movement_type`, `qty_delta` sign):

| Action in app | movement_type | qty_delta | Other rows written |
|---------------|---------------|-----------|--------------------|
| Sell | `SALE` | − per batch (FEFO) | `sales_transactions` (channel `COUNTER`), `sales_items` per batch; shortfall → extra `sales_items` row with `qty=0`, `unmet_qty>0`, `batch_id NULL` |
| Receive stock | `PURCHASE` | + | new batch or top-up of same batch no.; audit `PURCHASE` |
| Customer return | `RETURN_IN` | + | only non-expired batch, only up to units sold; audit `RETURN_IN` |
| Return to supplier | `RETURN_OUT` | − | audit `RETURN_OUT` |
| Correct quantity | `ADJUST` | ± | reason required; audit `ADJUST` (old/new qty) |
| Write off expired | `WRITEOFF_EXPIRY` | − | audit `WRITEOFF_EXPIRY` |
| Remove sold medicine | `ADJUST` | − remaining | `medicines.is_active = 0`, audit `DEACTIVATE_MEDICINE`; history kept |

Rules: `medicine_batches.qty_on_hand >= 0` is enforced by a DB CHECK (migration 003). Expired stock is never sold. After each action the medicine's `recommendations` row is recomputed from sellable stock (`SS = Z × σ_LT × √(L + R)` parameters unchanged).

**Demo dates** (`app_meta`): `date_shift_days` — whole weeks added to synthetic sales and forecast weeks so history ends today; `batch_date_shift_days` — batches anchored on their own last receipt. Source files are not changed. Forecast weeks are a **backtest** on the last 26 weeks (each has an actual), not a future forecast.
