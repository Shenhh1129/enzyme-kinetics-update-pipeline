# Step 06 `06_backfill_seq`

## Purpose

Run the three-stage sequence backfill chain after standardization.

## Substeps

- `6A_local_seqfill`
  - local `uniprot -> sequence` backfill
  - retry mutant rebuild after local fill
- `6B_UniProt_seq_cache`
  - collect unresolved UniProt accessions
  - build a local UniProt sequence cache
- `6C_Uniprot_cache`
  - backfill sequences from the cache
  - retry mutant rebuild again

## Inputs

### `6A_local_seqfill`

- `input/brenda_raw_qc_standardized_v1.csv`
- `input/sabio_tsv_raw_qc_standardized_v1.csv`

### `6B_UniProt_seq_cache`

- `input/brenda_raw_qc_standardized_seqfilled_v1.csv`
- `input/sabio_tsv_raw_qc_standardized_seqfilled_v1.csv`

### `6C_Uniprot_cache`

- `input/brenda_raw_qc_standardized_seqfilled_v1.csv`
- `input/sabio_tsv_raw_qc_standardized_seqfilled_v1.csv`
- `input/uniprot_sequence_cache_v1.csv`

## Outputs

- `6A_local_seqfill/output/brenda_raw_qc_standardized_seqfilled_v1.csv`
- `6A_local_seqfill/output/sabio_tsv_raw_qc_standardized_seqfilled_v1.csv`
- `6B_UniProt_seq_cache/output/uniprot_sequence_cache_v1.csv`
- `6C_Uniprot_cache/output/brenda_raw_qc_standardized_seqfilled_uniprot_v1.csv`
- `6C_Uniprot_cache/output/sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/06_backfill_seq/*/script/`
- Repository step directory only: `database_update_pipeline/06_backfill_seq/`
- Raw-source runtime output root: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/06_backfill_seq/`

## Scripts

- `6A_local_seqfill/script/backfill_sequence_post_standardized.py`
- `6B_UniProt_seq_cache/script/uniprot_sequence_cache_build.py`
- `6C_Uniprot_cache/script/backfill_sequence_with_uniprot_cache.py`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `6A` sequence-filled BRENDA rows: `71454 / 78152`
- `6A` sequence-filled SABIO rows: `65541 / 72840`
- UniProt cache rows: `2684`
- `6C` sequence-filled BRENDA rows: `71824 / 78152`
- `6C` sequence-filled SABIO rows: `67700 / 72840`

## Notes

- `6B` is the only network-dependent substep in the full repository.
- `6A` and `6C` keep the main raw-table row counts stable; only sequence completeness changes.
- `6B` emits the separate UniProt cache table used by `6C`.
