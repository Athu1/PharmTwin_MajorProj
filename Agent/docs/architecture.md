# Architecture — PharmTwinAI

Aligned with the attached architecture diagram: inputs → **Pharmacy Digital Twin** → operational outputs; secondary screening is dashed / gated.

---

## 1. High-level view

```text
┌─────────────────────────────── INPUTS ───────────────────────────────┐
│ Pharmacy data (MySQL) │ Medicine knowledge │ Historical sales      │
│ External disease/weather trends (features only, disclosed)           │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────── CORE SYSTEM ─────────────────────────────────────┐
│                     Pharmacy Digital Twin                             │
│  Inventory state │ Demand forecasting │ Simulations │ Rec. engine   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   ▼
┌──────────────────── OUTPUTS ─────────────────────────────────────────┐
│ Inventory dashboard │ Reorder recommendations │ Expiry & stock alerts│
│ What-if simulations │ (Optional Power BI)                             │
└──────────────────────────────────────────────────────────────────────┘

┌ · · · · AFTER CORE ACCEPTANCE · · · · · · · · · · · · · · · · · · · ┐
│ Secondary medical screening (Anemia first; others need approval)     │
└ · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · ┘
```

---

## 2. Technology choices (locked 2026-09-28)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| DB | **MySQL 8** (localhost) | Spec + transactional inventory |
| UI | **Desktop app** (`app/main.py`, tkinter stdlib; optional PySide6 later) | Installable pharmacy software — not Streamlit/web-first (D2) |
| Services | In-process Python (`services/`) | Called by desktop UI; no public HTTP surface required for v1 |
| ML | Existing Agent `src/` (Croston/SBA/TSB/LightGBM) | Reuse offline pipeline; wire into services |
| Data mode (now) | **Labeled `dev_synthetic`** | Sponsor POS not available (D3) |
| Deploy | Local / college lab only | D6 — no paid cloud |

Optional later: thin local Flask API **only if** multi-PC LAN access is required — not the default UX.

---

## 3. Logical components

| Component | Responsibility |
|-----------|----------------|
| **Ingestion** | CSV/Excel → validated staging → MySQL |
| **Inventory service** | Sales/purchases/returns → stock_movements → batch qty |
| **Twin service** | Build snapshot JSON; stale detection; sync clock |
| **Forecast service** | Train/evaluate; write `forecasts` |
| **Recommendation service** | ROP/SS/FEFO-aware purchase suggestions + explanation text |
| **Alert service** | Threshold scanners → `alerts` |
| **Simulation service** | Clone snapshot; apply scenario; persist results only |
| **Knowledge service** | Normalization, AWaRe/H1 tags, pharmacist-reviewed alts |
| **API + Streamlit** | Role-aware UX |

---

## 4. MySQL schema (DDL sketch)

```sql
-- Core master
CREATE TABLE manufacturers (
  manufacturer_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE medicine_categories (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE
);

CREATE TABLE medicines (
  medicine_id INT AUTO_INCREMENT PRIMARY KEY,
  sku_code VARCHAR(64) NULL,
  name VARCHAR(512) NOT NULL,
  generic_name VARCHAR(512) NULL,
  manufacturer_id INT NULL,
  category_id INT NULL,
  pack_size_label VARCHAR(128) NULL,
  rx_schedule ENUM('OTC','H','H1','X','UNKNOWN') DEFAULT 'UNKNOWN',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  unit_mrp DECIMAL(12,2) NULL,
  source_system VARCHAR(32) NOT NULL DEFAULT 'sponsor', -- sponsor|dev_synthetic|reference
  UNIQUE KEY uq_med_name_mfr (name, manufacturer_id),
  FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id),
  FOREIGN KEY (category_id) REFERENCES medicine_categories(category_id)
);

CREATE TABLE suppliers (
  supplier_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  lead_time_days INT NOT NULL DEFAULT 3
);

CREATE TABLE medicine_batches (
  batch_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  batch_no VARCHAR(64) NOT NULL,
  mfg_date DATE NULL,
  expiry_date DATE NOT NULL,
  qty_on_hand DECIMAL(12,3) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(12,2) NULL,
  received_at DATETIME NULL,
  UNIQUE KEY uq_batch (medicine_id, batch_no),
  KEY idx_expiry (expiry_date),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE stock_movements (
  movement_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  batch_id BIGINT NULL,
  movement_type ENUM('SALE','PURCHASE','RETURN_IN','RETURN_OUT','ADJUST','WRITEOFF_EXPIRY','TRANSFER') NOT NULL,
  qty_delta DECIMAL(12,3) NOT NULL, -- signed
  unit_price DECIMAL(12,2) NULL,
  ref_table VARCHAR(64) NULL,
  ref_id BIGINT NULL,
  occurred_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_med_time (medicine_id, occurred_at),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
  FOREIGN KEY (batch_id) REFERENCES medicine_batches(batch_id)
);

CREATE TABLE sales_transactions (
  sale_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sold_at DATETIME NOT NULL,
  channel VARCHAR(32) NULL,
  KEY idx_sold_at (sold_at)
);

CREATE TABLE sales_items (
  sale_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sale_id BIGINT NOT NULL,
  medicine_id INT NOT NULL,
  batch_id BIGINT NULL,
  qty DECIMAL(12,3) NOT NULL,
  unit_price DECIMAL(12,2) NOT NULL,
  FOREIGN KEY (sale_id) REFERENCES sales_transactions(sale_id),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
  FOREIGN KEY (batch_id) REFERENCES medicine_batches(batch_id)
);

-- Coverage calendar: distinguish missing vs zero
CREATE TABLE demand_coverage (
  medicine_id INT NOT NULL,
  day DATE NOT NULL,
  status ENUM('OBSERVED','STORE_CLOSED','MISSING_EXPORT','STOCKOUT_UNMET') NOT NULL,
  PRIMARY KEY (medicine_id, day),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE purchase_orders (
  po_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id INT NULL,
  status ENUM('DRAFT','ORDERED','PARTIAL','RECEIVED','CANCELLED') NOT NULL,
  ordered_at DATETIME NULL,
  expected_at DATE NULL,
  FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE purchase_order_items (
  po_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  po_id BIGINT NOT NULL,
  medicine_id INT NOT NULL,
  qty_ordered DECIMAL(12,3) NOT NULL,
  qty_received DECIMAL(12,3) NOT NULL DEFAULT 0,
  FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE alerts (
  alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NULL,
  batch_id BIGINT NULL,
  alert_type ENUM('LOW_STOCK','OVERSTOCK','EXPIRY','STOCKOUT_RISK','STALE_TWIN') NOT NULL,
  severity ENUM('INFO','WARN','CRITICAL') NOT NULL,
  message VARCHAR(1024) NOT NULL,
  is_open BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_open (is_open, alert_type)
);

CREATE TABLE forecasts (
  forecast_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  grain ENUM('D','W','M') NOT NULL,
  horizon_start DATE NOT NULL,
  horizon_end DATE NOT NULL,
  yhat DECIMAL(12,4) NOT NULL,
  yhat_lower DECIMAL(12,4) NULL,
  yhat_upper DECIMAL(12,4) NULL,
  model_name VARCHAR(64) NOT NULL,
  trained_through DATE NOT NULL,
  metrics_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_fc (medicine_id, horizon_start),
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE recommendations (
  recommendation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  action_type ENUM('REORDER','HOLD','REVIEW_EXPIRY','REVIEW_OVERSTOCK') NOT NULL,
  qty_suggested DECIMAL(12,3) NULL,
  current_stock DECIMAL(12,3) NULL,
  forecast_demand DECIMAL(12,3) NULL,
  incoming_po_qty DECIMAL(12,3) NULL,
  safety_stock DECIMAL(12,3) NULL,
  reorder_point DECIMAL(12,3) NULL,
  explanation_text TEXT NOT NULL,
  assumptions_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
);

CREATE TABLE digital_twin_snapshots (
  snapshot_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  synced_at DATETIME NOT NULL,
  source_hash CHAR(64) NULL,
  is_stale BOOLEAN NOT NULL DEFAULT FALSE,
  state_json JSON NOT NULL
);

CREATE TABLE simulation_runs (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  base_snapshot_id BIGINT NOT NULL,
  title VARCHAR(255) NOT NULL,
  scenario_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (base_snapshot_id) REFERENCES digital_twin_snapshots(snapshot_id)
);

CREATE TABLE simulation_results (
  result_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  metrics_json JSON NOT NULL,
  narrative TEXT NULL,
  FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

CREATE TABLE users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('OWNER','STAFF','ANALYST','ADMIN') NOT NULL
);
```

Indexes emphasize `(medicine_id, occurred_at)`, expiry, and open alerts.

---

## 5. API sketch (Flask)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/ingest/upload` | Sponsor file ingest |
| GET | `/api/twin/state` | Latest snapshot + `synced_at` |
| POST | `/api/twin/sync` | Rebuild snapshot from DB |
| POST | `/api/simulations` | What-if (no inventory writes) |
| GET | `/api/forecasts/{medicine_id}` | Forecast series |
| GET | `/api/recommendations` | Open purchase suggestions |
| GET | `/api/alerts` | Active alerts |
| POST | `/api/sales` | Record sale (updates movements + batches) |

---

## 6. Security

- Secrets in `.env` (gitignored)
- Password hashing (bcrypt/argon2)
- Role checks on mutating routes
- Sponsor raw files never in public remotes (`data_privacy.md`)

---

## 7. Integration of existing Agent ML

| Agent module | PharmTwinAI service |
|--------------|---------------------|
| `forecast_intermittent` + `forecast_env_lgbm` | Forecast service |
| `safety_stock` + `inventory_fefo` | Recommendation + simulation |
| `regulatory/*` + `substitutes_nlp` | Knowledge / pharmacist-reviewed alternatives (not auto-Rx) |
| Synthetic generator | DEV seed only (`source_system='dev_synthetic'`) |
