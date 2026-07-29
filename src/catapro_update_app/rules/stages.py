from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    name: str
    description: str
    input_dirs: tuple[str, ...] = ()
    output_dirs: tuple[str, ...] = ()


STAGES: tuple[StageSpec, ...] = (
    StageSpec("01_new_raw", "Rebuild raw source tables.", ("database/original",), ("database/current/summary",)),
    StageSpec("02_enrich+mutation", "Enrich local sequence and mutation fields.", ("database/original",), ("database/current/summary",)),
    StageSpec("03_subres", "Resolve SABIO substrate components.", ("database/original",), ("database/current/summary",)),
    StageSpec("04_QC", "Apply raw-layer QC filters.", ("database/original",), ("database/current/summary",)),
    StageSpec("05_qc_standardize", "Standardize fields for downstream processing.", ("database/current/summary",), ("database/current/summary",)),
    StageSpec("06_backfill_seq", "Backfill sequences from local and UniProt sources.", ("database/current/summary",), ("database/current/summary",)),
    StageSpec("07_cata_updata", "Export CataPro update tables.", ("database/current/summary",), ("database/current/summary",)),
    StageSpec("08_cata_master", "Build CataPro master tables.", ("database/current/summary",), ("database/current/master",)),
    StageSpec("09_external_master", "Build external masters and SKiD sequence fill.", ("database/original", "database/reference"), ("database/current/master",)),
    StageSpec("10_mut_status_repair", "Repair mutation-status fields.", ("database/current/master",), ("database/current/master",)),
    StageSpec("11_merged_canonical_pool", "Merge and deduplicate the canonical training pool.", ("database/current/master",), ("database/current/merged",)),
    StageSpec("12_status_fix", "Add status-fixed final fields.", ("database/current/merged",), ("database/current/merged",)),
    StageSpec("13_final_data", "Export final enriched deliverables.", ("database/current/merged",), ("database/current/merged",)),
    StageSpec("14_final_docs", "Export final conditions, summary, and audits.", ("database/current/merged",), ("database/current/summary", "database/current/conditions")),
)
