# Step 12 `12_status_fix`

## Purpose

Enrich the final `v2` merged tables with normalized values, sequence status fields, and `kcat_km` companion fields.

## Inputs

- `input/merge_kcat_final_v2.csv`
- `input/merge_km_final_v2.csv`
- `input/CataPro_kcat_master_v2.csv`
- `input/CataPro_km_master_v2.csv`
- `input/DLKcat_kcat_master_v2.csv`
- `input/SKiD_kcat_master_seqfilled_v2.csv`
- `input/SKiD_km_master_seqfilled_v2.csv`
- `input/sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv`

## Outputs

- `output/merge_kcat_final_v6_statusfixed_all.csv`
- `output/merge_km_final_v6_statusfixed_all.csv`

## Repository Locations

- Source: `database_update_pipeline/12_status_fix/script/`
- Repository step directory only: `database_update_pipeline/12_status_fix/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/12_status_fix/output/`

## Scripts

- `script/export_final_enriched_v6_statusfixed_all.py`
  - injects `WT_sequence` and `MUT_sequence` from source masters
  - normalizes `value` and `unit`
  - attaches source or computed `kcat_km` companion fields

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `merge_kcat_final_v6_statusfixed_all.csv`: `72056` rows
- `merge_km_final_v6_statusfixed_all.csv`: `97074` rows
- `value_normalized` is fully populated in both outputs

## Notes

- This step enriches existing rows rather than changing the train/test composition.
- `unit_normalized` can remain blank when the original source truly has no unit.
