# Step 01 `01_new_raw`

## Purpose

Rebuild frozen source files into the shared raw schema.

- `BRENDA JSON -> brenda_raw.csv`
- `SABIO TSV -> sabio_tsv_raw_v1.csv`

## Inputs

- `input/brenda_2026_1.json`
- `input/sabio_current_kcat_km_kcatkm.tsv`

## Outputs

- `output/brenda_raw.csv`
- `output/sabio_tsv_raw_v1.csv`

## Repository Locations

- Source: `database_update_pipeline/01_new_raw/script/`
- Repository step directory only: `database_update_pipeline/01_new_raw/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/01_new_raw/output/`

## Scripts

- `script/rebuild_brenda_raw.py`
  - streams the BRENDA JSON by EC number
  - exports `kcat` and `Km` rows in the raw schema
  - parses mutation, pH, temperature, and ions from commentary
  - keeps BRENDA `unit` blank when the source does not provide it
- `script/rebuild_sabio_from_tsv.py`
  - reads the SABIO snapshot TSV
  - keeps `kcat`, `Km`, and `kcat/Km`
  - maps fields into the shared raw schema
- `script/parse_utils.py`
  - shared parsers for text cleanup, mutation recognition, pH, temperature, ions, and parse status

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `brenda_raw.csv`: `264242` rows
- `sabio_tsv_raw_v1.csv`: `110899` rows

## Notes

- This step only rebuilds raw tables. It does not enrich, filter, or deduplicate records.
- BRENDA `organism` and `reaction_raw` are recovered here from the source JSON.
