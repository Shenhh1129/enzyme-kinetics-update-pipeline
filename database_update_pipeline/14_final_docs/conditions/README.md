# Step 14A `conditions`

## Purpose

Build three condition-level pairing views from the final `kcat` and `km` releases.

## Inputs

- `input/merge_kcat_final_v6_enriched.csv`
- `input/merge_km_final_v6_enriched.csv`

## Outputs

- `output/conditions/grouped_outerjoin/*`
- `output/conditions/collapsed_multivalue/*`
- `output/conditions/cartesian/*`
- `output/audit/*`

## Repository Locations

- Source: `database_update_pipeline/14_final_docs/conditions/script/`
- Repository step directory only: `database_update_pipeline/14_final_docs/conditions/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/conditions/output/`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- `grouped_outerjoin`: `120981`
- `collapsed_multivalue`: `105870`
- `cartesian`: `137239`
- formal Step 13 condition tables feeding this step:
  - `ph_long_table.csv`: `129964`
  - `temperature_long_table.csv`: `122767`

## Pairing Modes

- `grouped_outerjoin`: pair rows by sorted position inside each condition group
- `collapsed_multivalue`: collapse each condition group into one row with `|`-joined detail fields
- `cartesian`: expand every `kcat x km` combination inside a condition group

## Notes

- Step 13 already emits the formal long-table conditions:
  - `13_final_data/output/conditions/ph_long_table.csv`
  - `13_final_data/output/conditions/temperature_long_table.csv`
- This Step 14A module only emits the three pairing-view variants under `output/conditions/`.
- During a raw-source release run, these Step 14A pairing views stay inside the legacy workspace:
  - `releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/conditions/output/conditions/*`
- They are auxiliary analysis outputs and are not promoted into formal `outputs/conditions/`.
- Condition groups are keyed by the standardized entry fields `uniprot + enzyme_type + mutation + sequence + substrate + smiles` plus `ph + temperature`.
- Top-level `dataset_name` and `source_db` may contain `|`-joined values when one condition group spans multiple surviving sources.
- All per-source `__brenda`, `__sabio-rk`, `__skid`, and `__dlkcat` files are filtered views of the same outputs.
