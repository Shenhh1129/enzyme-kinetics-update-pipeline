# Step 13 `13_final_data`

## Purpose

Export the release-facing `v6_enriched` master, merged, and final merged datasets.

## Inputs

- `input/CataPro_kcat_master_v2.csv`
- `input/CataPro_km_master_v2.csv`
- `input/DLKcat_kcat_master_v2.csv`
- `input/SKiD_kcat_master_seqfilled_v2.csv`
- `input/SKiD_km_master_seqfilled_v2.csv`
- `input/IntEnzy_kcat_master_v1.csv`
- `input/IntEnzy_km_master_v1.csv`
- `input/merge_kcat_v2.csv`
- `input/merge_km_v2.csv`
- `input/merge_kcat_final_v6_statusfixed_all.csv`
- `input/merge_km_final_v6_statusfixed_all.csv`
- `input/sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv`

## Outputs

- `output/CataPro_kcat_master_v6_enriched.csv`
- `output/CataPro_km_master_v6_enriched.csv`
- `output/DLKcat_kcat_master_v6_enriched.csv`
- `output/SKiD_kcat_master_v6_enriched.csv`
- `output/SKiD_km_master_v6_enriched.csv`
- `output/IntEnzy_kcat_master_v6_enriched.csv`
- `output/IntEnzy_km_master_v6_enriched.csv`
- `output/merge_kcat_v6_enriched.csv`
- `output/merge_km_v6_enriched.csv`
- `output/merge_kcat_final_v6_enriched.csv`
- `output/merge_km_final_v6_enriched.csv`
- `output/conditions/ph_long_table.csv`
- `output/conditions/temperature_long_table.csv`

## Repository Locations

- Source: `database_update_pipeline/13_final_data/script/`
- Raw-source workspace step output: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/13_final_data/output/`
- Formal release outputs:
  - `.external_data/releases/<release_id>/outputs/master/`
  - `.external_data/releases/<release_id>/outputs/merged/`
  - `.external_data/releases/<release_id>/outputs/conditions/`

## Scripts

- `script/export_masters_merges_enriched_v6.py`
  - exports the final release views
  - adds `WT_sequence`, `MUT_sequence`, normalized value/unit fields, and `kcat_km` companion fields across outputs

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `merge_kcat_final_v6_enriched.csv`: `72056` rows
- `merge_km_final_v6_enriched.csv`: `97074` rows
- `conditions/ph_long_table.csv`: `129964` rows
- `conditions/temperature_long_table.csv`: `122767` rows
- nonblank `WT_sequence`:
  - final `kcat`: `32918`
  - final `km`: `48328`

## Notes

- These are the release-facing data tables that are later promoted into `.external_data/database/current/master/` and `.external_data/database/current/merged/` after a release is approved.
- This step keeps row counts stable relative to Step 12 and enriches the final fields.
- The final merged outputs remain split into `kcat` and `km` tables. `kcat_km` is carried as companion fields, not as a third merged release table, and `ph` / `temperature` remain condition columns rather than separate merged-table parameter rows.
- The formal long-table conditions are emitted here at the same time as the final merged outputs by filtering nonblank `ph` and `temperature` from the final merged release tables.
