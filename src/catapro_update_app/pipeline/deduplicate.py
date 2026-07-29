from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.io.paths import ensure_dir
from catapro_update_app.pipeline.formal import ensure_control_columns, has_auto_match_evidence, normalize_text
from catapro_update_app.pipeline.importer import StandardizedBatch
from catapro_update_app.reports.manifest import write_manifest
from catapro_update_app.rules.policy import SourceType
RESULT_PRIORITY = {
    SourceType.MANUAL_OVERRIDE.value: 0,
    SourceType.RAW_SOURCE.value: 1,
    SourceType.EXTERNAL_SOURCE.value: 2,
}


AUDIT_PREFIX_COLUMNS: tuple[str, ...] = (
    "audit_id",
    "release_id",
    "source_type",
    "audit_file",
    "audit_stage",
    "audit_reason",
    "source_file",
    "source_row",
)


@dataclass(frozen=True)
class DedupResult:
    combined: pd.DataFrame
    import_duplicates: pd.DataFrame
    business_duplicates: pd.DataFrame
    rejected_rows: pd.DataFrame
    conflicts: pd.DataFrame
    leakage_removed: pd.DataFrame
    merged: pd.DataFrame
    merged_path: Path | None = None
    import_duplicates_path: Path | None = None
    business_duplicates_path: Path | None = None
    rejected_rows_path: Path | None = None
    conflicts_path: Path | None = None
    leakage_removed_path: Path | None = None
    manifest_path: Path | None = None

    @property
    def duplicates(self) -> pd.DataFrame:
        return self.business_duplicates


def _sort_for_survivor(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    logical_source = working.get("logical_source_type", pd.Series([""] * len(working), index=working.index)).astype(str)
    fallback_source = working.get("source", pd.Series([""] * len(working), index=working.index)).astype(str)
    effective_source = logical_source.where(logical_source.str.strip().ne(""), fallback_source)
    working["result_priority"] = effective_source.map(lambda value: RESULT_PRIORITY.get(str(value), 99))
    working["release_sort"] = working.get("release_id", pd.Series([""] * len(working), index=working.index)).astype(str)
    working["source_file"] = working.get("source_file", pd.Series([""] * len(working), index=working.index)).astype(str)
    working["source_row"] = working.get("source_row", pd.Series([""] * len(working), index=working.index)).astype(str)
    return working.sort_values(
        by=["result_priority", "release_sort", "source_file", "source_row"],
        ascending=[True, False, True, True],
        kind="mergesort",
    )


def _import_dedup(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        empty = frame.iloc[0:0].copy()
        return empty, empty
    working = frame.copy()
    if "import_dedup_key" not in working.columns or working["import_dedup_key"].fillna("").astype(str).str.strip().eq("").all():
        working["import_dedup_key"] = working.apply(lambda row: "|".join(normalize_text(row.get(col, "")) for col in working.columns), axis=1)
    duplicated_mask = working.duplicated("import_dedup_key", keep="first")
    duplicates = working.loc[duplicated_mask].copy()
    kept = working.loc[~duplicated_mask].copy()
    return kept, duplicates


def _business_dedup(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        empty = frame.iloc[0:0].copy()
        return empty, empty, empty, empty
    working = _sort_for_survivor(frame)
    if "business_key" not in working.columns:
        working["business_key"] = ""
    if "measurement_uid" not in working.columns:
        working["measurement_uid"] = ""
    if "parameter_name" not in working.columns:
        working["parameter_name"] = ""
    working["organism"] = working.get("organism", pd.Series([""] * len(working), index=working.index)).map(normalize_text)
    working["ions"] = working.get("ions", pd.Series([""] * len(working), index=working.index)).map(normalize_text)

    evidence_mask = working.apply(has_auto_match_evidence, axis=1)
    insufficient = working.loc[~evidence_mask].copy()
    if not insufficient.empty:
        insufficient["conflict_type"] = "insufficient_match_evidence"
        insufficient["conflict_detail"] = "uniprot_sequence_substrate_smiles_all_blank"

    valid = working.loc[evidence_mask].copy()
    if valid.empty:
        empty = working.iloc[0:0].copy()
        return insufficient.copy(), empty, empty, insufficient.copy()

    kept_groups: list[pd.DataFrame] = []
    duplicate_groups: list[pd.DataFrame] = []
    conflict_groups: list[pd.DataFrame] = [insufficient] if not insufficient.empty else []
    group_columns = ["business_key", "parameter_name", "measurement_uid"]

    for _, group in valid.groupby(group_columns, sort=False, dropna=False):
        subgroup = group.copy()
        subgroup["organism_ions_key"] = subgroup["organism"].astype(str) + "|" + subgroup["ions"].astype(str)
        distinct_pairs = subgroup["organism_ions_key"].drop_duplicates().tolist()
        if len(distinct_pairs) > 1:
            conflict = subgroup.copy()
            conflict["conflict_type"] = "organism_or_ions_conflict"
            conflict["conflict_detail"] = "|".join(distinct_pairs)
            conflict_groups.append(conflict.drop(columns=["organism_ions_key"]))
        for _, pair_group in subgroup.groupby("organism_ions_key", sort=False, dropna=False):
            pair_group = pair_group.drop(columns=["organism_ions_key"])
            kept_groups.append(pair_group.iloc[[0]].copy())
            if len(pair_group) > 1:
                duplicate_groups.append(pair_group.iloc[1:].copy())

    kept = pd.concat(kept_groups, ignore_index=True, sort=False) if kept_groups else working.iloc[0:0].copy()
    duplicates = pd.concat(duplicate_groups, ignore_index=True, sort=False) if duplicate_groups else working.iloc[0:0].copy()
    conflicts = pd.concat(conflict_groups, ignore_index=True, sort=False) if conflict_groups else working.iloc[0:0].copy()
    rejected = working.iloc[0:0].copy()
    return kept, duplicates, rejected, conflicts


def _build_audit_rows(frame: pd.DataFrame, release_id: str, source_type: SourceType, file_name: str, stage: str, reason: str) -> pd.DataFrame:
    if frame.empty:
        columns = AUDIT_PREFIX_COLUMNS + tuple(column for column in frame.columns if column not in AUDIT_PREFIX_COLUMNS)
        return pd.DataFrame(columns=columns)
    rows = frame.copy()
    rows["audit_id"] = [f"{stage}_{release_id}_{index + 1}" for index in range(len(rows))]
    rows["release_id"] = release_id
    rows["source_type"] = source_type.value
    rows["audit_file"] = file_name
    rows["audit_stage"] = stage
    rows["audit_reason"] = reason
    if "source_file" not in rows.columns:
        rows["source_file"] = ""
    if "source_row" not in rows.columns:
        rows["source_row"] = ""
    ordered_columns = list(AUDIT_PREFIX_COLUMNS) + [column for column in rows.columns if column not in AUDIT_PREFIX_COLUMNS]
    return rows.loc[:, ordered_columns]


def filter_test_leakage(frame: pd.DataFrame, blocked_business_keys: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty or not blocked_business_keys:
        empty = frame.iloc[0:0].copy()
        if "matched_test_key" not in empty.columns:
            empty["matched_test_key"] = ""
        return frame.copy(), empty

    working = frame.copy()
    business_keys = working.get("business_key", pd.Series([""] * len(working), index=working.index)).fillna("").astype(str).str.strip()
    leakage_mask = business_keys.isin(blocked_business_keys)
    removed = working.loc[leakage_mask].copy()
    kept = working.loc[~leakage_mask].copy()
    if "matched_test_key" not in removed.columns:
        removed["matched_test_key"] = ""
    removed.loc[:, "matched_test_key"] = removed.get("business_key", pd.Series([""] * len(removed), index=removed.index)).astype(str)
    return kept, removed


def merge_and_deduplicate(batch: StandardizedBatch, existing_frame: pd.DataFrame | None = None) -> DedupResult:
    incoming = pd.concat([item.frame for item in batch.items], ignore_index=True) if batch.items else pd.DataFrame()
    incoming = ensure_control_columns(incoming)
    incoming_kept, import_duplicates = _import_dedup(incoming)

    existing = ensure_control_columns(existing_frame.copy()) if existing_frame is not None else pd.DataFrame(columns=incoming_kept.columns)
    if existing.empty:
        combined = incoming_kept.copy()
    elif incoming_kept.empty:
        combined = existing.copy()
    else:
        combined = pd.concat([existing, incoming_kept], ignore_index=True, sort=False)
    combined = ensure_control_columns(combined)
    merged, business_duplicates, rejected_rows, conflicts = _business_dedup(combined)
    leakage_removed = merged.iloc[0:0].copy()
    return DedupResult(
        combined=combined,
        import_duplicates=import_duplicates,
        business_duplicates=business_duplicates,
        rejected_rows=rejected_rows,
        conflicts=conflicts,
        leakage_removed=leakage_removed,
        merged=merged,
    )


def write_dedup_outputs(paths: AppPaths, batch: StandardizedBatch, dedup: DedupResult, release_id: str, source_type: SourceType, input_root: Path) -> DedupResult:
    workspace_root = ensure_dir(paths.release_workspace_external_root(release_id) / "dedup")
    audit_root = ensure_dir(paths.release_audit_root(release_id))
    manifest_root = ensure_dir(paths.release_manifest_root(release_id))

    merged_path = workspace_root / "business_dedup_survivors.csv"
    import_duplicates_path = audit_root / "import_duplicate_rows.csv"
    business_duplicates_path = audit_root / "business_duplicate_rows.csv"
    rejected_rows_path = audit_root / "rejected_rows.csv"
    conflicts_path = audit_root / "conflicts.csv"
    leakage_removed_path = audit_root / "test_leakage_removed.csv"
    manifest_path = manifest_root / "dedup_batch_manifest.json"

    dedup.merged.to_csv(merged_path, index=False)
    _build_audit_rows(dedup.import_duplicates, release_id, source_type, import_duplicates_path.name, "import_dedup", "fully_duplicated_row").to_csv(import_duplicates_path, index=False)
    _build_audit_rows(dedup.business_duplicates, release_id, source_type, business_duplicates_path.name, "business_dedup", "business_key_survivor_kept").to_csv(business_duplicates_path, index=False)
    _build_audit_rows(dedup.rejected_rows, release_id, source_type, rejected_rows_path.name, "business_dedup", "missing_business_or_measurement_identity").to_csv(rejected_rows_path, index=False)
    _build_audit_rows(dedup.conflicts, release_id, source_type, conflicts_path.name, "business_dedup", "conflict_requires_audit").to_csv(conflicts_path, index=False)
    _build_audit_rows(dedup.leakage_removed, release_id, source_type, leakage_removed_path.name, "test_leakage_filter", "matched_test_key").to_csv(leakage_removed_path, index=False)

    manifest = {
        "release_id": release_id,
        "source_type": source_type.value,
        "input_root": str(input_root),
        "standardized_files": [str(item.output_path) for item in batch.items if item.output_path],
        "combined_row_count": len(dedup.combined),
        "merged_row_count": len(dedup.merged),
        "import_duplicate_row_count": len(dedup.import_duplicates),
        "business_duplicate_row_count": len(dedup.business_duplicates),
        "rejected_row_count": len(dedup.rejected_rows),
        "conflict_row_count": len(dedup.conflicts),
        "test_leakage_removed_row_count": len(dedup.leakage_removed),
    }
    write_manifest(manifest_path, manifest)

    return DedupResult(
        combined=dedup.combined,
        import_duplicates=dedup.import_duplicates,
        business_duplicates=dedup.business_duplicates,
        rejected_rows=dedup.rejected_rows,
        conflicts=dedup.conflicts,
        leakage_removed=dedup.leakage_removed,
        merged=dedup.merged,
        merged_path=merged_path,
        import_duplicates_path=import_duplicates_path,
        business_duplicates_path=business_duplicates_path,
        rejected_rows_path=rejected_rows_path,
        conflicts_path=conflicts_path,
        leakage_removed_path=leakage_removed_path,
        manifest_path=manifest_path,
    )
