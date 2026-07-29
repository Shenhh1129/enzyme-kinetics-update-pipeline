# Step 08 `08_cata_master`

## Purpose

Convert the update-layer exports into the shared master schema for the CataPro branch.

## Inputs

- `input/catapro_update_kcat_v2.csv`
- `input/catapro_update_km_v2.csv`

## Outputs

- `output/CataPro_kcat_master_v2.csv`
- `output/CataPro_km_master_v2.csv`

## Repository Locations

- Source: `database_update_pipeline/08_cata_master/script/`
- Repository step directory only: `database_update_pipeline/08_cata_master/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/08_cata_master/output/`

## Scripts

- `script/build_catapro_master_v2.py`
  - reorders update-layer fields into the master schema
  - adds `dataset_name`, `source_db`, `source_release`, and `measurement_uid`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `CataPro_kcat_master_v2.csv`: `47624` rows
- `CataPro_km_master_v2.csv`: `87225` rows

## Notes

- This is the branch-local master build for BRENDA plus SABIO content.
- `measurement_uid` is generated here for stable downstream tracking.
