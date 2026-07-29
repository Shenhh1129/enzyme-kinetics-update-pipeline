# Step 11 `11_merged_canonical_pool`

## Purpose

Merge the branch-local masters into the candidate training pool, then deduplicate it and remove overlap with the IntEnzy external test set.

## Substeps

- `candidate_pool`
  - merges CataPro, DLKcat, and SKiD masters
- `dedup-split`
  - removes duplicate training keys
  - drops rows overlapping the IntEnzy test set
  - preserves the IntEnzy test outputs

## Inputs

### `candidate_pool`

- `input/CataPro_kcat_master_v2.csv`
- `input/CataPro_km_master_v2.csv`
- `input/DLKcat_kcat_master_v2.csv`
- `input/SKiD_kcat_master_seqfilled_v2.csv`
- `input/SKiD_km_master_seqfilled_v2.csv`

### `dedup-split`

- `input/merge_kcat_v2.csv`
- `input/merge_km_v2.csv`
- `input/IntEnzy_kcat_master_v1.csv`
- `input/IntEnzy_km_master_v1.csv`

## Outputs

### `candidate_pool`

- `output/merge_kcat_v2.csv`
- `output/merge_km_v2.csv`

### `dedup-split`

- `output/merge_kcat_final_v2.csv`
- `output/merge_km_final_v2.csv`
- `output/IntEnzy_kcat_test_v1.csv`
- `output/IntEnzy_km_test_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/11_merged_canonical_pool/*/script/`
- Repository step directory only: `database_update_pipeline/11_merged_canonical_pool/`
- Raw-source runtime output root: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/11_merged_canonical_pool/`

## Scripts

- `candidate_pool/script/build_merged_training_v2.py`
- `dedup-split/script/final_dedup_and_split_v2.py`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- candidate pool:
  - `merge_kcat_v2.csv`: `77500`
  - `merge_km_v2.csv`: `104936`
- final train after dedup and leakage removal:
  - `merge_kcat_final_v2.csv`: `72056`
  - `merge_km_final_v2.csv`: `97074`
- rows removed from candidate pool:
  - `kcat`: `5444`
  - `km`: `7862`
- preserved IntEnzy test outputs:
  - `IntEnzy_kcat_test_v1.csv`: `1093`
  - `IntEnzy_km_test_v1.csv`: `1093`

## Notes

- This is the main dataset-size reduction step before final enrichment.
- IntEnzy is treated as an external test set here, not as training data.
- Dedup runs in this order: exact row dedup, then formal business/measurement dedup, then IntEnzy leakage filtering.
- The formal 6-key entry identity is `uniprot + enzyme_type + mutation + sequence + substrate + smiles`.
