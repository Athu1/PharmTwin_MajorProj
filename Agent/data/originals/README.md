# Immutable originals

These files are frozen snapshots of catalog / synthetic pipeline outputs.

- **Do not edit** files in this folder.
- MySQL rows with `source_system='reference'` are the 250k+ catalog knowledge base and must not be updated or deleted by inventory UI.
- Pharmacy working stock uses `source_system` in `('pharmacy','dev_synthetic','sponsor')` only.
- Re-run: `py -3 scripts/snapshot_originals.py` (add `--force` to refresh copies).
