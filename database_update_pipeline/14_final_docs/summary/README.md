# Step 14B `summary`

## Purpose

Export release counts, mutation subsets, blank-condition subsets, and unit audits from the final enriched datasets.

## Inputs

- `input/merge_kcat_final_v6_enriched.csv`
- `input/merge_km_final_v6_enriched.csv`

## Outputs

- `output/summary_v6.txt`
- `output/summary_v6_counts.csv`
- `output/mutation/*`
- `output/ph_tem_empty/*`
- `output/unit/*`

## Repository Locations

- Source: `database_update_pipeline/14_final_docs/summary/script/`
- Repository step directory only: `database_update_pipeline/14_final_docs/summary/`
- Raw-source runtime output path: `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/summary/output/`
- Formal release output: `.external_data/releases/<release_id>/outputs/summary/`

## Audit Rules

- `mutation/*`: rows with nonblank `mutation`
- `ph_tem_empty/*`: rows where both `ph` and `temperature` are blank
- `unit/*`: rows with
  - `missing_unit`, or
  - nonblank unit outside the expected set

Expected units:

- `kcat -> s^-1`
- `km -> mM` or `M`
- `kcat_km -> M^-1*s^-1`

## Current Snapshot

As of baseline release `20260724-initial-baseline` run on `2026-07-29`:

- final `kcat` rows: `72056`
- final `km` rows: `97074`
- mutation rows: `23698 / 34011`
- `ph_tem_empty` rows: `23044 / 11142`
- `kcat` unit-audit rows: `30762`
- `km` unit-audit rows: `45072`
- missing-unit rows:
  - `kcat`: `30706`
  - `km`: `44874`
- unexpected-unit rows:
  - `kcat`: `56`
  - `km`: `198`

## Notes

- BRENDA missing units are currently expected because the BRENDA source file does not supply explicit units for these records.
- This step still reads the split final outputs `merge_kcat_final_v6_enriched.csv` and `merge_km_final_v6_enriched.csv`; it does not mix standalone `ph` or `temperature` rows into the merged release tables.
