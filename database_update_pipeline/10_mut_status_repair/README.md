# Step 10 `10_mut_status_repair`

## Purpose

Repair mutation-status fields and sequence columns for DLKcat and SKiD master tables.

## Inputs

- `input/DLKcat_kcat_master_v1.csv`
- `input/SKiD_kcat_master_seqfilled_v1.csv`
- `input/SKiD_km_master_seqfilled_v1.csv`

## Outputs

- `output/DLKcat_kcat_master_v2.csv`
- `output/SKiD_kcat_master_seqfilled_v2.csv`
- `output/SKiD_km_master_seqfilled_v2.csv`

## Repository Locations

- Source: `database_update_pipeline/10_mut_status_repair/script/`
- Repository step directory only: `database_update_pipeline/10_mut_status_repair/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/10_mut_status_repair/output/`

## Scripts

- `script/repair_dlkcat_mutation_status_v2.py`
  - normalizes `mutation_apply_status`
  - fills `WT_sequence` for non-mutants
  - clears meaningless `MUT_sequence`
- `script/repair_skid_mutation_status_v2.py`
  - reapplies mutation rules to `WT_sequence`
  - rewrites `mutation_apply_status`
  - updates `sequence` and `MUT_sequence` when rebuild succeeds

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `DLKcat_kcat_master_v2.csv`: `17010` rows
- `SKiD_kcat_master_seqfilled_v2.csv`: `12866` rows
- `SKiD_km_master_seqfilled_v2.csv`: `17711` rows
- SKiD mutation rebuild success or no-change:
  - `kcat`: `54`
  - `Km`: `47`

## Notes

- This step repairs derived status fields without changing source semantics.
- The output row counts stay the same as Step 09.
