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

Full DDL: see `architecture.md` § Database schema.
