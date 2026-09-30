-- 002: Editable pharmacy inventory (working copy) — never mutate reference catalog rows
-- Apply via: py -3 scripts/apply_migration_002.py

USE pharmtwinai;

-- Allow pharmacy-owned working copies distinct from immutable reference catalog
ALTER TABLE medicines
  MODIFY COLUMN source_system
    ENUM('sponsor','dev_synthetic','reference','pharmacy')
    NOT NULL DEFAULT 'dev_synthetic';

ALTER TABLE medicines
  ADD COLUMN IF NOT EXISTS form_type
    ENUM(
      'TABLET','CAPSULE','SYRUP','INJECTION','CREAM','DROPS',
      'INHALER','POWDER','OTHER','UNKNOWN'
    ) NOT NULL DEFAULT 'UNKNOWN'
    AFTER pack_size_label;

ALTER TABLE medicines
  ADD COLUMN IF NOT EXISTS qty_unit
    ENUM('TABLETS','CAPSULES','ML','MG','UNITS','VIALS','BOTTLES','PACKS','OTHER')
    NOT NULL DEFAULT 'UNITS'
    AFTER form_type;

ALTER TABLE medicines
  ADD COLUMN IF NOT EXISTS cloned_from_medicine_id INT NULL
    AFTER external_sku_id;

ALTER TABLE medicine_batches
  ADD COLUMN IF NOT EXISTS qty_unit
    ENUM('TABLETS','CAPSULES','ML','MG','UNITS','VIALS','BOTTLES','PACKS','OTHER')
    NULL
    AFTER qty_on_hand;

-- Audit log for inventory mutations (working inventory only)
CREATE TABLE IF NOT EXISTS inventory_audit (
  audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  action_type ENUM('ADD_MEDICINE','REMOVE_MEDICINE','ADD_LOT','REMOVE_LOT','UPDATE_LOT') NOT NULL,
  medicine_id INT NULL,
  batch_id BIGINT NULL,
  detail_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_inv_audit_time (created_at)
) ENGINE=InnoDB;
