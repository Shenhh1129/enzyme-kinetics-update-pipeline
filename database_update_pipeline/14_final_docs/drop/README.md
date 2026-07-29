# Step 14C `drop`

## Purpose

Publish dropped-row inventories for raw QC and final training dedup.

## Inputs

- `input/merge_kcat_v2.csv`
- `input/merge_km_v2.csv`
- `input/IntEnzy_kcat_master_v1.csv`
- `input/IntEnzy_km_master_v1.csv`
- `input/brenda_raw_mutseq_v1.csv`
- `input/brenda_raw_qc_v1.csv`
- `input/sabio_tsv_raw_subres_v1.csv`
- `input/sabio_tsv_raw_qc_v1.csv`

## Outputs

- `output/dropped/raw_qc/*`
- `output/dropped/final_dedup/*`
- `output/drop_summary_v6.csv`
- `output/drop_file_inventory_v6.csv`
- `output/drop_build_manifest_v6.csv`

## Repository Locations

- Source: `database_update_pipeline/14_final_docs/drop/script/`
- Repository step directory only: `database_update_pipeline/14_final_docs/drop/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/drop/output/`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- BRENDA raw QC drops:
  - `missing_uniprot = 162025`
  - `missing_smiles = 24065`
- SABIO raw QC drops:
  - `missing_kinetic_value_num = 1192`
  - `missing_uniprot = 12613`
  - `missing_smiles = 15959`
- final train drops:
  - `kcat duplicate_training_key = 5343`
  - `kcat overlap_with_IntEnzy_test = 101`
  - `km duplicate_training_key = 7717`
  - `km overlap_with_IntEnzy_test = 145`

## Notes

- This step documents removals; it does not change upstream datasets.
- Release-level drop files are exposed as top-level audits in `.external_data/releases/<release_id>/audits/`; there is no separate promoted `audits/drop/` folder.
