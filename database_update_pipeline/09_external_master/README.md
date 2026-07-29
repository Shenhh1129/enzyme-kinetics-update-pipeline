# Step 09 `09_external_master`

## Purpose

Import DLKcat, SKiD, and IntEnzy into the shared master schema.

## Substeps

- `9A_ex_master`
  - builds master tables for DLKcat, SKiD, and IntEnzy
  - reshapes IntEnzy pair data into long-form master tables
- `9B_SKID_seqfill`
  - backfills SKiD sequences from the UniProt cache
  - attempts mutant-sequence construction for SKiD rows

## Inputs

### `9A_ex_master`

- `input/Kcat_combination_0918_wildtype_mutant.json`
- `input/db_matched_pairs_pH.csv`
- `input/kcat_all_data_logscale_final_v1.csv`
- `input/Km_all_data_logscale_final_v1.csv`
- `input/uniprot_sequence_cache_v1.csv`
- `input/Ligands_all_final_v1.csv`
- `input/kcat-data_0.4simi-10fold.csv`
- `input/Km-data_0.4simi-10fold.csv`
- `input/kcat-over-Km-data_0.4simi-10fold.csv`

### `9B_SKID_seqfill`

- `input/SKiD_kcat_master_v1.csv`
- `input/SKiD_km_master_v1.csv`
- `input/uniprot_sequence_cache_v1.csv`

## Outputs

### `9A_ex_master`

- `output/DLKcat_kcat_master_v1.csv`
- `output/SKiD_kcat_master_v1.csv`
- `output/SKiD_km_master_v1.csv`
- `output/IntEnzy_pairs_filtered_v1.csv`
- `output/IntEnzy_kcat_long_v1.csv`
- `output/IntEnzy_km_long_v1.csv`
- `output/IntEnzy_kcat_master_v1.csv`
- `output/IntEnzy_km_master_v1.csv`

### `9B_SKID_seqfill`

- `output/SKiD_kcat_master_seqfilled_v1.csv`
- `output/SKiD_km_master_seqfilled_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/09_external_master/*/script/`
- Repository step directory only: `database_update_pipeline/09_external_master/`
- Raw-source runtime output root: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/09_external_master/`

## Scripts

- `9A_ex_master/script/build_external_masters.py`
- `9A_ex_master/script/parse_utils.py`
- `9B_SKID_seqfill/script/backfill_skid_sequence_with_uniprot_cache.py`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `DLKcat_kcat_master_v1.csv`: `17010` rows
- `IntEnzy_kcat_master_v1.csv`: `1093` rows
- `IntEnzy_km_master_v1.csv`: `1093` rows
- SKiD temperature recovered in `9A`:
  - `kcat`: `9842 / 12866`
  - `Km`: `12872 / 17711`

## Notes

- SKiD temperature parsing was repaired in the original Step 09 scripts.
- `9B` improves sequence completeness for SKiD but keeps the same row counts.
