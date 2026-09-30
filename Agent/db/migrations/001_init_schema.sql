-- PharmTwinAI MySQL 8 schema
-- Apply: mysql -u root -p < db/migrations/001_init_schema.sql

CREATE DATABASE IF NOT EXISTS pharmtwinai
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pharmtwinai;

CREATE TABLE manufacturers (
  manufacturer_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  UNIQUE KEY uq_mfr_name (name)
) ENGINE=InnoDB;

CREATE TABLE medicine_categories (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  UNIQUE KEY uq_cat_name (name)
) ENGINE=InnoDB;

CREATE TABLE medicines (
  medicine_id INT AUTO_INCREMENT PRIMARY KEY,
  sku_code VARCHAR(64) NULL,
  name VARCHAR(512) NOT NULL,
  generic_name VARCHAR(512) NULL,
  manufacturer_id INT NULL,
  category_id INT NULL,
  pack_size_label VARCHAR(128) NULL,
  rx_schedule ENUM('OTC','H','H1','X','UNKNOWN') NOT NULL DEFAULT 'UNKNOWN',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  unit_mrp DECIMAL(12,2) NULL,
  demand_cohort VARCHAR(64) NULL,
  source_system ENUM('sponsor','dev_synthetic','reference') NOT NULL DEFAULT 'dev_synthetic',
  external_sku_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_external_sku (external_sku_id),
  KEY idx_med_name (name(191)),
  CONSTRAINT fk_med_mfr FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id),
  CONSTRAINT fk_med_cat FOREIGN KEY (category_id) REFERENCES medicine_categories(category_id)
) ENGINE=InnoDB;

CREATE TABLE suppliers (
  supplier_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  lead_time_days INT NOT NULL DEFAULT 3
) ENGINE=InnoDB;

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
  CONSTRAINT fk_batch_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
) ENGINE=InnoDB;

CREATE TABLE stock_movements (
  movement_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  medicine_id INT NOT NULL,
  batch_id BIGINT NULL,
  movement_type ENUM('SALE','PURCHASE','RETURN_IN','RETURN_OUT','ADJUST','WRITEOFF_EXPIRY','TRANSFER') NOT NULL,
  qty_delta DECIMAL(12,3) NOT NULL,
  unit_price DECIMAL(12,2) NULL,
  ref_table VARCHAR(64) NULL,
  ref_id BIGINT NULL,
  occurred_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_med_time (medicine_id, occurred_at),
  CONSTRAINT fk_mv_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
  CONSTRAINT fk_mv_batch FOREIGN KEY (batch_id) REFERENCES medicine_batches(batch_id)
) ENGINE=InnoDB;

CREATE TABLE sales_transactions (
  sale_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sold_at DATETIME NOT NULL,
  channel VARCHAR(32) NULL,
  source_system ENUM('sponsor','dev_synthetic') NOT NULL DEFAULT 'dev_synthetic',
  KEY idx_sold_at (sold_at)
) ENGINE=InnoDB;

CREATE TABLE sales_items (
  sale_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sale_id BIGINT NOT NULL,
  medicine_id INT NOT NULL,
  batch_id BIGINT NULL,
  qty DECIMAL(12,3) NOT NULL,
  unmet_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
  unit_price DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_si_sale FOREIGN KEY (sale_id) REFERENCES sales_transactions(sale_id),
  CONSTRAINT fk_si_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
  CONSTRAINT fk_si_batch FOREIGN KEY (batch_id) REFERENCES medicine_batches(batch_id)
) ENGINE=InnoDB;

CREATE TABLE demand_coverage (
  medicine_id INT NOT NULL,
  day DATE NOT NULL,
  status ENUM('OBSERVED','STORE_CLOSED','MISSING_EXPORT','STOCKOUT_UNMET') NOT NULL,
  PRIMARY KEY (medicine_id, day),
  CONSTRAINT fk_cov_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
) ENGINE=InnoDB;

CREATE TABLE purchase_orders (
  po_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  supplier_id INT NULL,
  status ENUM('DRAFT','ORDERED','PARTIAL','RECEIVED','CANCELLED') NOT NULL,
  ordered_at DATETIME NULL,
  expected_at DATE NULL,
  CONSTRAINT fk_po_sup FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
) ENGINE=InnoDB;

CREATE TABLE purchase_order_items (
  po_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  po_id BIGINT NOT NULL,
  medicine_id INT NOT NULL,
  qty_ordered DECIMAL(12,3) NOT NULL,
  qty_received DECIMAL(12,3) NOT NULL DEFAULT 0,
  CONSTRAINT fk_poi_po FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
  CONSTRAINT fk_poi_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
) ENGINE=InnoDB;

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
) ENGINE=InnoDB;

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
  CONSTRAINT fk_fc_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
) ENGINE=InnoDB;

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
  CONSTRAINT fk_rec_med FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
) ENGINE=InnoDB;

CREATE TABLE digital_twin_snapshots (
  snapshot_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  synced_at DATETIME NOT NULL,
  source_hash CHAR(64) NULL,
  is_stale BOOLEAN NOT NULL DEFAULT FALSE,
  state_json JSON NOT NULL
) ENGINE=InnoDB;

CREATE TABLE simulation_runs (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  base_snapshot_id BIGINT NOT NULL,
  title VARCHAR(255) NOT NULL,
  scenario_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sim_snap FOREIGN KEY (base_snapshot_id) REFERENCES digital_twin_snapshots(snapshot_id)
) ENGINE=InnoDB;

CREATE TABLE simulation_results (
  result_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id BIGINT NOT NULL,
  metrics_json JSON NOT NULL,
  narrative TEXT NULL,
  CONSTRAINT fk_sres_run FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
) ENGINE=InnoDB;

CREATE TABLE users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('OWNER','STAFF','ANALYST','ADMIN') NOT NULL,
  UNIQUE KEY uq_username (username)
) ENGINE=InnoDB;

CREATE TABLE app_meta (
  meta_key VARCHAR(64) PRIMARY KEY,
  meta_value VARCHAR(512) NOT NULL
) ENGINE=InnoDB;

INSERT INTO app_meta (meta_key, meta_value) VALUES
  ('schema_version', '001'),
  ('data_mode', 'dev_synthetic');
