# Step 03 `03_subres`

## Purpose

Resolve SABIO multi-component substrate strings into a cleaner single-substrate view.

## Inputs

- `input/sabio_tsv_raw_mutseq_v1.csv`

Reference files for local SMILES refill:

- `input/kcat-data_0.4simi-10fold.csv`
- `input/Km-data_0.4simi-10fold.csv`
- `input/kcat-over-Km-data_0.4simi-10fold.csv`
- `input/Kcat_combination_0918_wildtype_mutant.json`
- `input/Ligands_all_final_v1.csv`

## Outputs

- `output/sabio_tsv_raw_subres_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/03_subres/script/`
- Repository step directory only: `database_update_pipeline/03_subres/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/03_subres/output/`

## Scripts

- `script/sabio_tsv_substrate_resolve.py`
  - splits multi-component substrate strings
  - filters water, ions, and common cofactors
  - keeps a single substrate when one candidate remains
  - adds `substrate_resolution_status`, `substrate_components_json`, and `substrate_resolved_from_multi`
  - retries local SMILES backfill after resolution

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- output rows: `110899`
- rows with nonblank `smiles`: `84260`

## Notes

- This step only affects the SABIO branch.
- It improves substrate cleanliness before QC but does not drop records directly.
