# Step 04 `04_QC`

## Purpose

Apply the raw-layer hard filters shared by the BRENDA and SABIO branches.

## Inputs

- `input/brenda_raw_mutseq_v1.csv`
- `input/sabio_tsv_raw_subres_v1.csv`

## Outputs

- `output/brenda_raw_qc_v1.csv`
- `output/sabio_tsv_raw_qc_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/04_QC/script/`
- Repository step directory only: `database_update_pipeline/04_QC/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/04_QC/output/`

## Scripts

- `script/build_raw_qc.py`
  - keeps only rows with nonblank `kinetic_value_num`, `uniprot`, and `smiles`
  - reports drop counts by reason in the terminal

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- BRENDA kept: `78152`, dropped: `186090`
- SABIO kept: `72840`, dropped: `38059`

## Notes

- This step is intentionally simple.
- Standardization starts in Step 05, not here.
