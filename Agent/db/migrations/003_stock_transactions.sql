-- 003: Stock transactions (sale / purchase / return / adjust / write-off) + soft delete
--      + medicine detail edits (UPDATE_MEDICINE audit)
-- Apply via: py -3 scripts/apply_migration_003.py  (idempotent)

USE pharmtwinai;

-- Audit trail names every manual stock action explicitly
ALTER TABLE inventory_audit
  MODIFY COLUMN action_type ENUM(
    'ADD_MEDICINE','REMOVE_MEDICINE','ADD_LOT','REMOVE_LOT','UPDATE_LOT',
    'PURCHASE','RETURN_IN','RETURN_OUT','ADJUST','WRITEOFF_EXPIRY','DEACTIVATE_MEDICINE',
    'UPDATE_MEDICINE'
  ) NOT NULL;

-- Stock can never go negative (shortfalls are recorded as sales_items.unmet_qty)
ALTER TABLE medicine_batches
  ADD CONSTRAINT chk_batch_qty_nonneg CHECK (qty_on_hand >= 0);
