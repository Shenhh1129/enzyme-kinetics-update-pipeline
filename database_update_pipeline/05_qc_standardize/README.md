# Step 05 `05_qc_standardize`

## Purpose

Standardize the QC-passed tables for downstream sequence fill, master export, and merge steps.

## Inputs

- `input/brenda_raw_qc_v1.csv`
- `input/sabio_tsv_raw_qc_v1.csv`

## Outputs

- `output/brenda_raw_qc_standardized_v1.csv`
- `output/sabio_tsv_raw_qc_standardized_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/05_qc_standardize/script/`
- Repository step directory only: `database_update_pipeline/05_qc_standardize/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/05_qc_standardize/output/`

## Scripts

- `script/standardize_raw_qc.py`
  - populates the legacy workspace `record_id` column
  - normalizes `parameter_name`, `value`, `unit`, `uniprot`, `smiles`, and sequence fields
  - prepares `sequence_final` and `sequence_final_source`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- BRENDA standardized rows: `78152`
- SABIO standardized rows: `72840`
- the legacy `record_id` column is fully populated in both outputs

## Notes

- No additional QC happens here.
- This step reorganizes fields without changing the kept row set.
