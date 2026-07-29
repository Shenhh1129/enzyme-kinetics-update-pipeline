# Pipeline Overview

This directory contains the executable 14-step black-box workflow for updating `raw_source` data. The black-box tree stores only the step scripts and README files; runtime process files and results do not live in the repository copy of the black-box.

## Input And Output Locations

- Source scripts: `database_update_pipeline/<step>/script/`
- During real `raw_source` runs, every step-level input and output lives under `.external_data/releases/<release_id>/workspace/raw_source/database_update_pipeline/...`
- Approved formal release outputs are promoted into `.external_data/releases/<release_id>/outputs/...`

## Step Map

| step | purpose | baseline scale snapshot |
|---|---|---|
| `01_new_raw` | rebuild BRENDA and SABIO raw tables | BRENDA `264242`; SABIO `110899` |
| `02_enrich+mutation` | enrich local sequence/SMILES and rebuild mutants | rows stay the same; mutation success/no-change `18384` / `16848` |
| `03_subres` | resolve SABIO multi-component substrates | output `110899`; nonblank `smiles` `84260` |
| `04_QC` | apply raw-layer QC filters | BRENDA `78152` kept / `186090` dropped; SABIO `72840` kept / `38059` dropped |
| `05_qc_standardize` | standardize fields for downstream use | rows stay the same as Step 04 |
| `06_backfill_seq` | local and UniProt sequence backfill | `6A` BRENDA `71454 / 78152`; `6A` SABIO `65541 / 72840`; `6C` BRENDA `71824 / 78152`; `6C` SABIO `67700 / 72840`; UniProt cache `2684` |
| `07_cata_updata` | export CataPro update tables | `kcat` `47624`; `km` `87225` |
| `08_cata_master` | build CataPro master tables | rows stay the same as Step 07 |
| `09_external_master` | build DLKcat, SKiD, and IntEnzy masters | DLKcat `17010`; IntEnzy `1093 / 1093`; SKiD `12866 / 17711`; SKiD temperature recovered `9842 / 12872` |
| `10_mut_status_repair` | repair mutation-status fields | rows stay the same; SKiD mutation success/no-change `54 / 47` |
| `11_merged_canonical_pool` | merge and deduplicate training pool | candidate pool `77500 / 104936`; final train `72056 / 97074` |
| `12_status_fix` | add status-fixed final fields | rows stay the same as Step 11 final |
| `13_final_data` | export `v6_enriched` deliverables | final merged `72056 / 97074`; formal conditions `129964 / 122767` |
| `14_final_docs` | export conditions, summary, and drop audits | pairing views `120981 / 105870 / 137239`; summary and drop are derivative only |

## Dependency Chain

```text
.external_data/database/original
  -> 01_new_raw
  -> 02_enrich+mutation
  -> 03_subres
  -> 04_QC
  -> 05_qc_standardize
  -> 06_backfill_seq
  -> 07_cata_updata
  -> 08_cata_master

.external_data/database/original + 06_backfill_seq output
  -> 09_external_master
  -> 10_mut_status_repair

08_cata_master + 10_mut_status_repair
  -> 11_merged_canonical_pool
  -> 12_status_fix
  -> 13_final_data
  -> 14_final_docs
```

## Run Order

This is the reference script order of the legacy black-box. In formal `raw_source` runs, the application layer should drive the workspace copy instead of writing intermediate files back into the repository source tree.

```powershell
python .\database_update_pipeline\01_new_raw\script\rebuild_brenda_raw.py
python .\database_update_pipeline\01_new_raw\script\rebuild_sabio_from_tsv.py
python .\database_update_pipeline\02_enrich+mutation\script\local_enrich.py
python .\database_update_pipeline\02_enrich+mutation\script\mutant_sequence_rebuild.py
python .\database_update_pipeline\03_subres\script\sabio_tsv_substrate_resolve.py
python .\database_update_pipeline\04_QC\script\build_raw_qc.py
python .\database_update_pipeline\05_qc_standardize\script\standardize_raw_qc.py
python .\database_update_pipeline\06_backfill_seq\6A_local_seqfill\script\backfill_sequence_post_standardized.py
python .\database_update_pipeline\06_backfill_seq\6B_UniProt_seq_cache\script\uniprot_sequence_cache_build.py
python .\database_update_pipeline\06_backfill_seq\6C_Uniprot_cache\script\backfill_sequence_with_uniprot_cache.py
python .\database_update_pipeline\07_cata_updata\script\export_catapro_update_v2.py
python .\database_update_pipeline\08_cata_master\script\build_catapro_master_v2.py
python .\database_update_pipeline\09_external_master\9A_ex_master\script\build_external_masters.py
python .\database_update_pipeline\09_external_master\9B_SKID_seqfill\script\backfill_skid_sequence_with_uniprot_cache.py
python .\database_update_pipeline\10_mut_status_repair\script\repair_dlkcat_mutation_status_v2.py
python .\database_update_pipeline\10_mut_status_repair\script\repair_skid_mutation_status_v2.py
python .\database_update_pipeline\11_merged_canonical_pool\candidate_pool\script\build_merged_training_v2.py
python .\database_update_pipeline\11_merged_canonical_pool\dedup-split\script\final_dedup_and_split_v2.py
python .\database_update_pipeline\12_status_fix\script\export_final_enriched_v6_statusfixed_all.py
python .\database_update_pipeline\13_final_data\script\export_masters_merges_enriched_v6.py
python .\database_update_pipeline\14_final_docs\conditions\script\build_conditions_v6.py
python .\database_update_pipeline\14_final_docs\summary\script\build_summary_v6.py
python .\database_update_pipeline\14_final_docs\drop\script\build_dropped_v6.py
```

## Notes

- `.external_data/database/original` is immutable source input.
- Only `06_backfill_seq/6B_UniProt_seq_cache` requires network access.
- Intermediate merged tables are retained for traceability.
- For this release setup, large source snapshots and generated CSV/JSON assets live under `.external_data/` and stay out of git.
- Step 13 is the only place that writes the formal `outputs/conditions/ph_long_table.csv` and `outputs/conditions/temperature_long_table.csv`.
- Step 14A keeps auxiliary pairing views inside the workspace copy and does not promote them into release `outputs/conditions/`.
- The `scale effect` and `Current Snapshot` sections in step README files record only the baseline release `20260724-initial-baseline` run on `2026-07-29`. Later `raw_source` update deltas belong in release history, manifests, and run summaries rather than being rolled forward inside the black-box README files.
