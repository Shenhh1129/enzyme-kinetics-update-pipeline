# Step 14 `14_final_docs`

## Purpose

Generate documentation-facing derivative outputs from the final enriched datasets.

## Submodules

- `conditions`
  - condition-group pairing views for paired `kcat` and `km`
- `summary`
  - dataset counts, mutation subsets, blank-condition subsets, and unit audits
- `drop`
  - dropped-row inventories for raw QC and final dedup

## Run Order

1. `conditions`
2. `summary`
3. `drop`

## Main Outputs

- `conditions/output/conditions/*`
- `conditions/output/audit/*`
- `summary/output/*`
- `drop/output/*`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- formal conditions emitted in Step 13:
  - `ph_long_table.csv`: `129964`
  - `temperature_long_table.csv`: `122767`
- Step 14A pairing views:
  - `grouped_outerjoin`: `120981`
  - `collapsed_multivalue`: `105870`
  - `cartesian`: `137239`
- Step 14B summary outputs:
  - `mutation` rows: `23698 / 34011`
  - `ph_tem_empty` rows: `23044 / 11142`
  - `unit` audit rows: `30762 / 45072`
- Step 14C drop outputs:
  - raw QC drops: `186090 / 29764`
  - final dedup drops: `5444 / 7862`

## Repository Locations

- Source: `database_update_pipeline/14_final_docs/*/script/`
- Repository step directory only: `database_update_pipeline/14_final_docs/`
- Raw-source runtime output root: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/`

## Notes

- Formal `ph_long_table.csv` and `temperature_long_table.csv` are emitted in Step 13 under `13_final_data/output/conditions/`.
- Step 14A keeps only the three pairing-view variants and does not modify any upstream data table.
- In raw-source release runs, Step 14A outputs remain under the release workspace copy of `database_update_pipeline/14_final_docs/conditions/output/...`; only Step 13 formal condition tables are synchronized into `outputs/conditions/`.
- Current outputs are synchronized to the baseline release `20260724-initial-baseline` run on `2026-07-29`.
