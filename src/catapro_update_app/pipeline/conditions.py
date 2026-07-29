from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.io.paths import ensure_dir
from catapro_update_app.pipeline.formal import ensure_formal_schema, normalize_text, read_csv_or_empty
from catapro_update_app.pipeline.deduplicate import DedupResult
from catapro_update_app.reports.manifest import write_manifest
from catapro_update_app.rules.registry import FORMAL_ENRICHED_COLUMNS


CONDITION_HISTORY_COLUMNS: tuple[str, ...] = (
    "log_id",
    "release_id",
    "log_time",
    "target_table",
    "condition_type",
    "action",
    "record_id",
    "record_key",
    "business_key",
    "measurement_uid",
    "parameter_name",
    "ec_number",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "substrate",
    "smiles",
    "field_name",
    "old_value",
    "new_value",
    "old_row_json",
    "new_row_json",
    "source_type",
    "source_file",
    "source_row",
    "operator",
    "reason",
    "notes",
)


@dataclass(frozen=True)
class ConditionExport:
    condition_name: str
    frame: pd.DataFrame
    output_path: Path | None = None
    manifest_path: Path | None = None


@dataclass(frozen=True)
class ConditionExportBundle:
    exports: tuple[ConditionExport, ...]


@dataclass(frozen=True)
class ConditionAppendResult:
    condition_name: str
    current_release: pd.DataFrame
    history_master: pd.DataFrame
    history_log: pd.DataFrame
    rejected_rows: pd.DataFrame
    conflicts: pd.DataFrame
    master_path: Path | None = None
    log_path: Path | None = None
    rejected_path: Path | None = None
    conflicts_path: Path | None = None


def _empty_history_log() -> pd.DataFrame:
    return pd.DataFrame(columns=CONDITION_HISTORY_COLUMNS)


def _filter_condition(frame: pd.DataFrame, column_name: str) -> pd.DataFrame:
    working = ensure_formal_schema(frame)
    mask = working[column_name].fillna("").astype(str).str.strip().ne("")
    return working.loc[mask].copy()


def export_condition_tables(dedup: DedupResult) -> ConditionExportBundle:
    ph_frame = _filter_condition(dedup.merged, "ph")
    temperature_frame = _filter_condition(dedup.merged, "temperature")
    return ConditionExportBundle(
        exports=(
            ConditionExport(condition_name="ph", frame=ph_frame),
            ConditionExport(condition_name="temperature", frame=temperature_frame),
        )
    )


def _append_history_rows(old_frame: pd.DataFrame, new_frame: pd.DataFrame, release_id: str, condition_name: str) -> pd.DataFrame:
    old_lookup = {row.get("record_id", ""): row for _, row in old_frame.iterrows()}
    rows: list[dict[str, object]] = []
    serial = 1
    for _, row in new_frame.iterrows():
        record_id = row.get("record_id", "")
        old_row = old_lookup.get(record_id)
        action = "append" if old_row is None else "replace"
        old_value = "" if old_row is None else old_row.get(condition_name, "")
        new_value = row.get(condition_name, "")
        if action == "replace" and str(old_value) == str(new_value):
            continue
        rows.append(
            {
                "log_id": f"log_{release_id}_{serial:06d}",
                "release_id": release_id,
                "log_time": "",
                "target_table": "conditions",
                "condition_type": condition_name,
                "action": action,
                "record_id": row.get("record_id", ""),
                "record_key": row.get("record_id", ""),
                "business_key": row.get("business_key", ""),
                "measurement_uid": row.get("measurement_uid", ""),
                "parameter_name": row.get("parameter_name", ""),
                "ec_number": row.get("ec_number", ""),
                "uniprot": row.get("uniprot", ""),
                "enzyme_type": row.get("enzyme_type", ""),
                "mutation": row.get("mutation", ""),
                "sequence": row.get("sequence", ""),
                "substrate": row.get("substrate", ""),
                "smiles": row.get("smiles", ""),
                "field_name": condition_name,
                "old_value": old_value,
                "new_value": new_value,
                "old_row_json": "" if old_row is None else old_row.to_json(force_ascii=False),
                "new_row_json": row.to_json(force_ascii=False),
                "source_type": row.get("source_db", ""),
                "source_file": row.get("source_file", ""),
                "source_row": row.get("source_row", ""),
                "operator": "system",
                "reason": f"{condition_name}_export_refresh",
                "notes": "",
            }
        )
        serial += 1
    return pd.DataFrame(rows, columns=CONDITION_HISTORY_COLUMNS)


def append_condition_history(
    paths: AppPaths,
    condition_name: str,
    release_frame: pd.DataFrame,
    release_id: str,
    baseline_frame: pd.DataFrame | None = None,
) -> ConditionAppendResult:
    history_root = ensure_dir(paths.condition_history_root)
    log_path = history_root / f"{condition_name}_history_log.csv"
    rejected_path = history_root / f"{condition_name}_rejected_rows.csv"
    conflicts_path = history_root / f"{condition_name}_conflicts.csv"
    baseline_path = paths.current_conditions_root / f"{condition_name}_long_table.csv"

    current_frame = baseline_frame.copy() if baseline_frame is not None else read_csv_or_empty(baseline_path)
    history_log = pd.read_csv(log_path, dtype=str).fillna("") if log_path.exists() else _empty_history_log()
    working = release_frame.copy()
    if "record_key" not in working.columns and "record_id" in working.columns:
        working["record_key"] = working["record_id"]
    if "record_id" not in working.columns and "record_key" in working.columns:
        working["record_id"] = working["record_key"]
    if "parameter_name" not in working.columns:
        working["parameter_name"] = condition_name
    if "source_db" not in working.columns and "source" in working.columns:
        working["source_db"] = working["source"]
    if "source_db" not in working.columns:
        working["source_db"] = ""
    if "source_file" not in working.columns:
        working["source_file"] = working.get("record_id", pd.Series([""] * len(working), index=working.index)).astype(str)
    if "source_row" not in working.columns:
        working["source_row"] = pd.Series(range(1, len(working) + 1), index=working.index).astype(str)
    if "business_key" not in working.columns:
        working["business_key"] = (
            working.get("record_key", working.get("record_id", pd.Series([""] * len(working), index=working.index))).astype(str)
            + "|"
            + working.get("enzyme_id", working.get("uniprot", pd.Series([""] * len(working), index=working.index))).astype(str)
            + "|"
            + working.get("condition_type", pd.Series([condition_name] * len(working), index=working.index)).astype(str)
        )
    if "measurement_uid" not in working.columns:
        working["measurement_uid"] = ""
    if condition_name not in working.columns:
        working[condition_name] = working.get("value", "")
    if "value_normalized" not in working.columns and "normalized_value" in working.columns:
        working["value_normalized"] = working["normalized_value"]
    if "unit_normalized" not in working.columns and "normalized_unit" in working.columns:
        working["unit_normalized"] = working["normalized_unit"]
    if "value" not in working.columns:
        working["value"] = working.get(condition_name, "")
    if "source_type" not in working.columns:
        working["source_type"] = working.get("source_db", "")
    valid_mask = (
        working["record_id"].fillna("").astype(str).str.strip().ne("")
        & working["parameter_name"].fillna("").astype(str).str.strip().ne("")
        & working["source_db"].fillna("").astype(str).str.strip().ne("")
        & working["source_file"].fillna("").astype(str).str.strip().ne("")
        & working["source_row"].fillna("").astype(str).str.strip().ne("")
    )
    valid_mask &= working[condition_name].fillna("").astype(str).str.strip().ne("")
    valid_mask &= (working["value"].fillna("").astype(str).str.strip().ne("") | working["value_normalized"].fillna("").astype(str).str.strip().ne(""))
    valid_mask &= working["business_key"].fillna("").astype(str).str.strip().ne("")
    valid_frame = working.loc[valid_mask].copy()
    valid_frame["append_release_id"] = release_id
    rejected = working.loc[~valid_mask].copy()
    conflicts = release_frame.iloc[0:0].copy()
    if not current_frame.empty:
        join_key = "record_id" if "record_id" in current_frame.columns else "record_key"
        old_indexed = current_frame.set_index(join_key, drop=False) if join_key in current_frame.columns else current_frame
        conflict_rows: list[dict[str, object]] = []
        for _, row in valid_frame.iterrows():
            row_key = row.get("record_id", row.get("record_key", ""))
            if not row_key or row_key not in getattr(old_indexed, "index", []):
                continue
            old_row = old_indexed.loc[row_key]
            if isinstance(old_row, pd.DataFrame):
                old_row = old_row.iloc[0]
            for field_name in ("value", "normalized_value", "condition"):
                old_value = normalize_text(old_row.get(field_name, ""))
                new_value = normalize_text(row.get(field_name, ""))
                if old_value != new_value:
                    conflict = row.to_dict()
                    conflict["field_name"] = field_name
                    conflict["old_value"] = old_value
                    conflict["new_value"] = new_value
                    conflict_rows.append(conflict)
        conflicts = pd.DataFrame(conflict_rows)
    new_history_rows = _append_history_rows(current_frame, valid_frame, release_id, condition_name)
    combined_history = pd.concat([history_log, new_history_rows], ignore_index=True, sort=False)
    combined_history.to_csv(log_path, index=False)
    rejected.to_csv(rejected_path, index=False)
    conflicts.to_csv(conflicts_path, index=False)
    history_master = valid_frame.drop_duplicates(subset=["record_id"], keep="last").copy()
    return ConditionAppendResult(
        condition_name=condition_name,
        current_release=valid_frame,
        history_master=history_master,
        history_log=combined_history,
        rejected_rows=rejected,
        conflicts=conflicts,
        master_path=None,
        log_path=log_path,
        rejected_path=rejected_path,
        conflicts_path=conflicts_path,
    )


def write_condition_exports(paths: AppPaths, bundle: ConditionExportBundle, release_id: str, source_type: str, merged_input_path: Path | None, workspace_name: str = "external_source") -> ConditionExportBundle:
    if workspace_name == "manual_override":
        workspace_root = ensure_dir(paths.release_workspace_manual_root(release_id) / "conditions")
    elif workspace_name == "raw_source":
        workspace_root = ensure_dir(
            paths.release_workspace_raw_root(release_id)
            / "database_update_pipeline"
            / "13_final_data"
            / "output"
            / "conditions"
        )
    else:
        workspace_root = ensure_dir(paths.release_workspace_external_root(release_id) / "conditions")
    output_root = ensure_dir(paths.release_output_conditions_root(release_id))
    manifest_root = ensure_dir(paths.release_manifest_root(release_id))
    exports: list[ConditionExport] = []
    for item in bundle.exports:
        frame = ensure_formal_schema(item.frame)
        workspace_path = workspace_root / f"{item.condition_name}_long_table.csv"
        output_path = output_root / f"{item.condition_name}_long_table.csv"
        frame.to_csv(workspace_path, index=False)
        frame.to_csv(output_path, index=False)
        manifest = {
            "release_id": release_id,
            "condition_name": item.condition_name,
            "source_type": source_type,
            "input_path": str(merged_input_path) if merged_input_path else "",
            "output_path": str(output_path),
            "row_count": len(frame),
            "column_count": len(frame.columns),
            "schema_columns": list(FORMAL_ENRICHED_COLUMNS),
        }
        manifest_path = write_manifest(manifest_root / f"{item.condition_name}_long_table_manifest.json", manifest)
        exports.append(ConditionExport(item.condition_name, frame, output_path, manifest_path))
    return ConditionExportBundle(exports=tuple(exports))
