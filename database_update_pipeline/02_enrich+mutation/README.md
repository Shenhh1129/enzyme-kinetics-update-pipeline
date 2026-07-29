# Step 02 `02_enrich+mutation`

## Purpose

Apply local enrichment to Step 01 raw tables and rebuild mutant sequences where possible.

## Inputs

- `input/brenda_raw.csv`
- `input/sabio_tsv_raw_v1.csv`

Reference files for local backfill:

- `input/kcat-data_0.4simi-10fold.csv`
- `input/Km-data_0.4simi-10fold.csv`
- `input/kcat-over-Km-data_0.4simi-10fold.csv`
- `input/Kcat_combination_0918_wildtype_mutant.json`
- `input/Ligands_all_final_v1.csv`

## Outputs

- `output/brenda_raw_local_enriched.csv`
- `output/sabio_tsv_raw_local_enriched_v1.csv`
- `output/brenda_raw_mutseq_v1.csv`
- `output/sabio_tsv_raw_mutseq_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/02_enrich+mutation/script/`
- Repository step directory only: `database_update_pipeline/02_enrich+mutation/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/02_enrich+mutation/output/`

## Scripts

- `script/local_enrich.py`
  - builds local `uniprot -> sequence` and `substrate -> smiles` maps
  - backfills missing `sequence` and `smiles`
- `script/mutant_sequence_rebuild.py`
  - rebuilds mutant sequences from wild-type sequences plus parsed mutation rules
  - writes `sequence_wildtype`, `mutation_applied_sequence`, and `mutation_apply_status`
- `script/enrich_and_mutate_sabio_tsv.py`
  - SABIO-only convenience wrapper

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- BRENDA enriched rows: `264242`
- SABIO enriched rows: `110899`
- BRENDA mutant rebuild success or no-change: `18384`
- SABIO mutant rebuild success or no-change: `16848`

## Notes

- This step does not filter records.
- The mutant rebuild logic is rule-based and will keep failures explicit in `mutation_apply_status`.
