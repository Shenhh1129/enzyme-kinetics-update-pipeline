# Step 07 `07_cata_updata`

## Purpose

Export the sequence-complete BRENDA and SABIO records into the CataPro-style update layer.

## Inputs

- `input/brenda_raw_qc_standardized_seqfilled_uniprot_v1.csv`
- `input/sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv`

## Outputs

- `output/catapro_update_kcat_v2.csv`
- `output/catapro_update_km_v2.csv`

## Repository Locations

- Source: `database_update_pipeline/07_cata_updata/script/`
- Repository step directory only: `database_update_pipeline/07_cata_updata/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/07_cata_updata/output/`

## Scripts

- `script/export_catapro_update_v2.py`
  - maps standardized fields into the update-layer schema
  - splits output by `parameter_name`
  - keeps only `kcat` and `km`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `catapro_update_kcat_v2.csv`: `47624` rows
- `catapro_update_km_v2.csv`: `87225` rows

## Notes

- `kcat_km` does not flow into this step's outputs.
- This step is a schema export step, not a new filtering step.
