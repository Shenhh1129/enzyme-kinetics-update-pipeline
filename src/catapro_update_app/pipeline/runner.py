from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from catapro_update_app.config.settings import AppPaths, RunConfig
from catapro_update_app.io.loaders import discover_input_files, profile_input_file
from catapro_update_app.io.paths import PathCheck, describe_path, ensure_dir
from catapro_update_app.pipeline.conditions import ConditionAppendResult, ConditionExport, ConditionExportBundle, append_condition_history, export_condition_tables, write_condition_exports
from catapro_update_app.pipeline.deduplicate import DedupResult, filter_test_leakage, merge_and_deduplicate, write_dedup_outputs
from catapro_update_app.pipeline.formal import (
    canonical_business_key_from_row,
    classify_existing_logical_source,
    ensure_control_columns,
    ensure_formal_identities,
    ensure_formal_schema,
    has_auto_match_evidence,
    normalize_parameter_name,
    normalize_text,
    record_id_from_row,
    read_csv_or_empty,
)
from catapro_update_app.pipeline.importer import StandardizedBatch, StandardizedInput, standardize_input_batch, write_standardized_input
from catapro_update_app.pipeline.legacy import LegacyPipelineResult, run_legacy_pipeline
from catapro_update_app.pipeline.summary_outputs import build_summary_bundle, write_summary_bundle
from catapro_update_app.reports.manifest import count_columns, count_lines, ensure_header_csv, sha1_file, write_json
from catapro_update_app.rules.harmonize import HarmonizationReport, harmonize_profile
from catapro_update_app.rules.policy import SourceType
from catapro_update_app.rules.registry import (
    AUDIT_FILES,
    ALLOWED_OVERRIDE_ACTIONS,
    ALLOWED_OVERRIDE_MATCH_KEY_TYPES,
    BUSINESS_KEY_FIELDS,
    CONDITION_OUTPUT_FILES,
    FORMAL_ENRICHED_COLUMNS,
    MANIFEST_FILES,
    MASTER_OUTPUT_FILES,
    MERGED_OUTPUT_FILES,
    SUMMARY_OUTPUT_FILES,
)
from catapro_update_app.rules.stages import STAGES, StageSpec
from catapro_update_app.rules.validation import ValidationResult, validate_input_request


CURRENT_SWITCH_COLUMNS: tuple[str, ...] = (
    "release_id",
    "switch_time",
    "operator",
    "source_type",
    "snapshot_path",
    "output_path",
    "status",
    "notes",
)

ROW_HISTORY_COLUMNS: tuple[str, ...] = (
    "log_id",
    "release_id",
    "log_time",
    "table_scope",
    "dataset_key",
    "target_file",
    "change_type",
    "business_key",
    "record_id",
    "measurement_uid",
    "parameter_name",
    "old_row_json",
    "new_row_json",
    "source_type",
    "notes",
)


@dataclass(frozen=True)
class StagePlan:
    spec: StageSpec
    ready: bool


@dataclass(frozen=True)
class PipelinePlan:
    stages: list[StagePlan]
    checks: list[PathCheck]
    validation: ValidationResult | None
    harmonization: HarmonizationReport | None
    standardized: StandardizedInput | None
    standardized_batch: StandardizedBatch | None
    dedup: DedupResult | None
    conditions: ConditionExportBundle | None
    condition_history: tuple[ConditionAppendResult, ...]
    wrote_standardized: bool
    wrote_release_artifacts: bool
    plan_payload: dict[str, object]


@dataclass(frozen=True)
class RunResult:
    release_id: str
    status: str
    review_status: str
    current_switched: bool
    release_root: Path
    notes: tuple[str, ...]


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _stages_for_source(source_type: SourceType) -> tuple[StageSpec, ...]:
    if source_type == SourceType.RAW_SOURCE:
        return STAGES
    if source_type in {SourceType.EXTERNAL_SOURCE, SourceType.MANUAL_OVERRIDE}:
        return tuple(stage for stage in STAGES if stage.name >= "09_external_master")
    return STAGES


def _planned_workspace_dirs(source_type: SourceType) -> list[str]:
    if source_type == SourceType.RAW_SOURCE:
        return [f"workspace/raw_source/database_update_pipeline/{stage.name}" for stage in STAGES]
    if source_type == SourceType.MANUAL_OVERRIDE:
        return [
            "workspace/manual_override/standardized_instructions",
            "workspace/manual_override/matched_targets",
            "workspace/manual_override/applied_changes",
            "workspace/manual_override/reports",
        ]
    return [
        "workspace/external_source/standardized_inputs",
        "workspace/external_source/dedup",
        "workspace/external_source/conditions",
        "workspace/external_source/reports",
    ]


def _planned_output_dirs() -> list[str]:
    return [
        "outputs/master",
        "outputs/merged",
        "outputs/summary",
        "outputs/conditions",
    ]


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _required_paths(paths: AppPaths) -> list[Path]:
    return [
        paths.repo_root,
        paths.data_root,
        paths.database_root,
        paths.raw_root,
        paths.reference_root,
        paths.current_root,
        paths.current_master_root,
        paths.current_merged_root,
        paths.current_summary_root,
        paths.current_conditions_root,
    ]


def _build_plan_payload(paths: AppPaths, config: RunConfig, input_files: list[Path], batch: StandardizedBatch | None) -> dict[str, object]:
    detected_formats = sorted({path.suffix.lower().lstrip(".") for path in input_files})
    input_rows = []
    for path in input_files:
        estimate = None
        try:
            estimate = profile_input_file(path).row_count
        except Exception:
            estimate = None
        input_rows.append(
            {
                "file_name": path.name,
                "format": path.suffix.lower().lstrip("."),
                "row_count_estimate": estimate,
            }
        )
    return {
        "release_id": config.release_id,
        "plan_time": _iso_now(),
        "source_type": config.source_type.value,
        "input_mode": config.source_type.value,
        "input_path": str(config.input_path) if config.input_path else "",
        "detected_formats": detected_formats,
        "input_file_count": len(input_files),
        "input_files": input_rows,
        "pipeline_route": {
            "uses_legacy_pipeline": config.source_type == SourceType.RAW_SOURCE,
            "uses_external_pipeline": config.source_type == SourceType.EXTERNAL_SOURCE,
            "uses_manual_override_pipeline": config.source_type == SourceType.MANUAL_OVERRIDE,
        },
        "planned_outputs": {
            "workspace": _planned_workspace_dirs(config.source_type),
            "outputs": _planned_output_dirs(),
            "audits": [f"audits/{name}" for name in AUDIT_FILES],
        },
        "current_snapshot_required": True,
        "snapshot_target": f"database/history/snapshots/{config.release_id}-before",
        "can_proceed": True,
        "warnings": [],
        "standardized_file_count": len(batch.items) if batch is not None else 0,
    }


def build_plan(paths: AppPaths, config: RunConfig) -> PipelinePlan:
    checks = [describe_path(path) for path in _required_paths(paths)]
    input_files = discover_input_files(config.input_path) if config.input_path and config.input_path.exists() else []
    standardized_batch = None
    harmonization = None
    standardized = None
    dedup = None
    conditions = None
    condition_history: tuple[ConditionAppendResult, ...] = ()

    if config.input_path and config.input_path.exists() and config.source_type != SourceType.RAW_SOURCE:
        standardized_batch = standardize_input_batch(config.input_path, config.source_type, config.release_id)
        if standardized_batch.items:
            standardized = standardized_batch.items[0]
            harmonization = harmonize_profile(profile_input_file(standardized.source_path), config.source_type)
            if config.source_type == SourceType.EXTERNAL_SOURCE:
                dedup = merge_and_deduplicate(standardized_batch)
                conditions = export_condition_tables(dedup)

    validation = validate_input_request(config.source_type, config.input_path, standardized_batch) if config.input_path else None
    stages = [
        StagePlan(spec=stage, ready=all((paths.data_root / rel_path).exists() for rel_path in stage.input_dirs))
        for stage in _stages_for_source(config.source_type)
    ]
    plan_payload = _build_plan_payload(paths, config, input_files, standardized_batch)
    return PipelinePlan(
        stages=stages,
        checks=checks,
        validation=validation,
        harmonization=harmonization,
        standardized=standardized,
        standardized_batch=standardized_batch,
        dedup=dedup,
        conditions=conditions,
        condition_history=condition_history,
        wrote_standardized=bool(config.write_standardized and standardized_batch and standardized_batch.items),
        wrote_release_artifacts=False,
        plan_payload=plan_payload,
    )


def _write_plan_preview(paths: AppPaths, release_id: str, plan: PipelinePlan) -> None:
    manifest_root = ensure_dir(paths.release_manifest_root(release_id))
    write_json(manifest_root / "plan_preview.json", plan.plan_payload)
    lines = [
        f"Release ID: {plan.plan_payload['release_id']}",
        f"Source type: {plan.plan_payload['source_type']}",
        f"Input path: {plan.plan_payload['input_path']}",
        f"Detected formats: {', '.join(plan.plan_payload['detected_formats']) if plan.plan_payload['detected_formats'] else 'none'}",
        f"Input file count: {plan.plan_payload['input_file_count']}",
        "Planned route:",
        f"- Legacy 14-step pipeline: {'yes' if plan.plan_payload['pipeline_route']['uses_legacy_pipeline'] else 'no'}",
        f"- External incremental pipeline: {'yes' if plan.plan_payload['pipeline_route']['uses_external_pipeline'] else 'no'}",
        f"- Manual override pipeline: {'yes' if plan.plan_payload['pipeline_route']['uses_manual_override_pipeline'] else 'no'}",
        "Planned outputs:",
    ]
    lines.extend(f"- {entry}" for entry in plan.plan_payload["planned_outputs"]["outputs"])
    lines.append("Planned workspace:")
    lines.extend(f"- {entry}" for entry in plan.plan_payload["planned_outputs"]["workspace"])
    lines.append(f"Snapshot required: {'yes' if plan.plan_payload['current_snapshot_required'] else 'no'}")
    lines.append(f"Proceed recommendation: {'yes' if plan.plan_payload['can_proceed'] else 'no'}")
    lines.append(f"Warnings: {', '.join(plan.plan_payload['warnings']) if plan.plan_payload['warnings'] else 'none'}")
    (manifest_root / "plan_preview.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_validate_report(paths: AppPaths, release_id: str, config: RunConfig, validation: ValidationResult | None) -> None:
    manifest_root = ensure_dir(paths.release_manifest_root(release_id))
    if validation is None:
        payload = {
            "release_id": release_id,
            "validate_time": _iso_now(),
            "source_type": config.source_type.value,
            "input_path": str(config.input_path) if config.input_path else "",
            "status": "fail",
            "can_run": False,
            "file_checks": {},
            "schema_checks": {},
            "quality_checks": {},
            "issues": [{"level": "error", "code": "missing_input_path", "message": "No input path was provided."}],
            "summary": {"status": "fail", "can_run": False},
        }
    else:
        payload = {
            "release_id": release_id,
            "validate_time": _iso_now(),
            "source_type": config.source_type.value,
            "input_path": str(config.input_path) if config.input_path else "",
            "status": validation.status,
            "can_run": validation.can_run,
            "file_checks": validation.file_checks,
            "schema_checks": validation.schema_checks,
            "quality_checks": validation.quality_checks,
            "issues": [
                {"level": item.level, "code": item.code, "message": item.message}
                for item in validation.messages
            ],
            "summary": validation.summary,
        }
    write_json(manifest_root / "validate_report.json", payload)
    lines = [
        f"Release ID: {payload['release_id']}",
        f"Source type: {payload['source_type']}",
        f"Input path: {payload['input_path']}",
        f"Validation status: {payload['status']}",
        f"Can run: {'yes' if payload['can_run'] else 'no'}",
        f"File checks: {json.dumps(payload['file_checks'], ensure_ascii=False)}",
        f"Schema checks: {json.dumps(payload['schema_checks'], ensure_ascii=False)}",
        f"Quality checks: {json.dumps(payload['quality_checks'], ensure_ascii=False)}",
        "Issues:",
    ]
    issues = payload["issues"] or [{"level": "info", "code": "none", "message": "none"}]
    lines.extend(f"- {item['level']}: {item['code']} -> {item['message']}" for item in issues)
    lines.append(f"Summary: {json.dumps(payload['summary'], ensure_ascii=False)}")
    (manifest_root / "validate_report.txt").write_text("\n".join(lines), encoding="utf-8")


def write_plan_artifacts(paths: AppPaths, release_id: str, plan: PipelinePlan) -> None:
    ensure_dir(paths.release_root(release_id))
    ensure_dir(paths.release_manifest_root(release_id))
    _write_plan_preview(paths, release_id, plan)


def write_validate_artifacts(paths: AppPaths, release_id: str, config: RunConfig, validation: ValidationResult | None) -> None:
    ensure_dir(paths.release_root(release_id))
    ensure_dir(paths.release_manifest_root(release_id))
    _write_validate_report(paths, release_id, config, validation)


def _copy_tree_contents(source_root: Path, target_root: Path) -> None:
    ensure_dir(target_root)
    if not source_root.exists():
        return
    for item in source_root.rglob("*"):
        if item.is_file():
            destination = target_root / item.relative_to(source_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def _prepare_release_roots(paths: AppPaths, release_id: str) -> None:
    ensure_dir(paths.release_root(release_id))
    ensure_dir(paths.release_manifest_root(release_id))
    ensure_dir(paths.release_output_master_root(release_id))
    ensure_dir(paths.release_output_merged_root(release_id))
    ensure_dir(paths.release_output_summary_root(release_id))
    ensure_dir(paths.release_output_conditions_root(release_id))
    ensure_dir(paths.release_audit_root(release_id))
    ensure_dir(paths.release_log_root(release_id))
    ensure_dir(paths.release_workspace_root(release_id))


def _snapshot_current(paths: AppPaths, release_id: str) -> Path:
    snapshot_root = ensure_dir(paths.snapshot_root(release_id))
    _copy_tree_contents(paths.current_master_root, snapshot_root / "master")
    _copy_tree_contents(paths.current_merged_root, snapshot_root / "merged")
    _copy_tree_contents(paths.current_summary_root, snapshot_root / "summary")
    _copy_tree_contents(paths.current_conditions_root, snapshot_root / "conditions")
    return snapshot_root


def _write_empty_audit_files(paths: AppPaths, release_id: str) -> None:
    audit_root = ensure_dir(paths.release_audit_root(release_id))
    for file_name in AUDIT_FILES:
        ensure_header_csv(audit_root / file_name, ("audit_id", "release_id", "source_type", "audit_file", "audit_stage", "audit_reason", "source_file", "source_row"))


def _load_existing_frame(path: Path) -> pd.DataFrame:
    formal = ensure_formal_identities(read_csv_or_empty(path))
    working = ensure_control_columns(formal)
    working["source"] = [classify_existing_logical_source(row.get("dataset_name", ""), row.get("source_db", "")) for _, row in formal.iterrows()]
    working["source_file"] = path.name
    working["source_row"] = [str(index + 1) for index in range(len(working))]
    working["release_id"] = working.get("source_release", pd.Series([""] * len(working), index=working.index)).astype(str)
    working["logical_source_type"] = working["source"]
    working["record_key"] = [f"{path.stem}:{index + 1}" for index in range(len(working))]
    working["import_dedup_key"] = working.apply(lambda row: "|".join(normalize_text(row.get(column, "")) for column in FORMAL_ENRICHED_COLUMNS), axis=1) if not working.empty else ""
    return working


def _load_current_master_frames(paths: AppPaths) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for key, file_name in MASTER_OUTPUT_FILES.items():
        frames[key] = _load_existing_frame(paths.current_master_root / file_name)
    return frames


def _load_current_merged_frames(paths: AppPaths) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for key, file_name in MERGED_OUTPUT_FILES.items():
        frames[key] = _load_existing_frame(paths.current_merged_root / file_name)
    return frames


def _load_intenzy_test_business_keys(paths: AppPaths) -> dict[str, set[str]]:
    key_map = {"kcat": set(), "km": set()}
    source_files = {
        "kcat": paths.current_master_root / MASTER_OUTPUT_FILES["intenzy_kcat"],
        "km": paths.current_master_root / MASTER_OUTPUT_FILES["intenzy_km"],
    }
    for parameter_name, path in source_files.items():
        frame = _load_existing_frame(path)
        if frame.empty:
            continue
        mask = frame["parameter_name"].fillna("").astype(str).map(normalize_parameter_name).eq(parameter_name)
        keys = frame.loc[mask, "business_key"].fillna("").astype(str).str.strip()
        key_map[parameter_name] = {value for value in keys if value}
    return key_map


def _strip_control(frame: pd.DataFrame) -> pd.DataFrame:
    return ensure_formal_schema(ensure_formal_identities(frame))


def _append_or_write_csv(path: Path, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    if path.exists():
        existing = pd.read_csv(path, dtype=str).fillna("")
        frame = pd.concat([existing, frame], ignore_index=True, sort=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _write_frame_or_header(path: Path, frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame.empty and len(frame.columns) == 0:
        pd.DataFrame(columns=columns).to_csv(path, index=False)
        return
    frame.to_csv(path, index=False)


def _write_external_workspace_reports(
    paths: AppPaths,
    release_id: str,
    incoming: pd.DataFrame,
    kinetic_rows: pd.DataFrame,
    condition_rows: pd.DataFrame,
    dedup: DedupResult,
    conditions: ConditionExportBundle,
) -> None:
    report_root = ensure_dir(paths.release_workspace_external_root(release_id) / "reports")
    parameter_counts = (
        dedup.merged.groupby("parameter_name").size().reset_index(name="final_rows")
        if not dedup.merged.empty
        else pd.DataFrame(columns=("parameter_name", "final_rows"))
    )
    parameter_counts.to_csv(report_root / "parameter_counts.csv", index=False)

    condition_counts = {
        item.condition_name: len(item.frame)
        for item in conditions.exports
    }
    payload = {
        "release_id": release_id,
        "report_time": _iso_now(),
        "input_rows": len(incoming),
        "kinetic_input_rows": len(kinetic_rows),
        "condition_input_rows": len(condition_rows),
        "combined_rows": len(dedup.combined),
        "final_merged_rows": len(dedup.merged),
        "import_duplicate_rows": len(dedup.import_duplicates),
        "business_duplicate_rows": len(dedup.business_duplicates),
        "rejected_rows": len(dedup.rejected_rows),
        "test_leakage_removed_rows": len(dedup.leakage_removed),
        "condition_export_rows": condition_counts,
        "paths": {
            "standardized_inputs": str(paths.release_workspace_external_root(release_id) / "standardized_inputs"),
            "dedup": str(paths.release_workspace_external_root(release_id) / "dedup"),
            "conditions": str(paths.release_workspace_external_root(release_id) / "conditions"),
            "reports": str(report_root),
        },
    }
    write_json(report_root / "external_source_report.json", payload)
    lines = [
        f"Release ID: {release_id}",
        f"Generated at: {payload['report_time']}",
        f"Input rows: {payload['input_rows']}",
        f"Kinetic rows: {payload['kinetic_input_rows']}",
        f"Condition supplement rows: {payload['condition_input_rows']}",
        f"Final merged rows: {payload['final_merged_rows']}",
        f"Import duplicates: {payload['import_duplicate_rows']}",
        f"Business duplicates: {payload['business_duplicate_rows']}",
        f"Rejected rows: {payload['rejected_rows']}",
        f"Leakage removed rows: {payload['test_leakage_removed_rows']}",
        f"Condition rows: ph={condition_counts.get('ph', 0)}, temperature={condition_counts.get('temperature', 0)}",
    ]
    (report_root / "external_source_report.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_manual_override_workspace_reports(
    paths: AppPaths,
    release_id: str,
    instructions: pd.DataFrame,
    matched_targets: pd.DataFrame,
    applied_rows: pd.DataFrame,
    applied_changes: pd.DataFrame,
    skipped_rows: pd.DataFrame,
    conflict_rows: pd.DataFrame,
) -> None:
    matched_root = ensure_dir(paths.release_workspace_manual_root(release_id) / "matched_targets")
    applied_root = ensure_dir(paths.release_workspace_manual_root(release_id) / "applied_changes")
    report_root = ensure_dir(paths.release_workspace_manual_root(release_id) / "reports")

    base_columns = tuple(instructions.columns)
    _write_frame_or_header(
        matched_root / "matched_targets.csv",
        matched_targets,
        base_columns + ("target_frame", "target_record_id", "target_measurement_uid", "target_business_key", "target_parameter_name", "target_source_db", "matched_field_name", "matched_old_value", "target_row_json"),
    )
    _write_frame_or_header(
        applied_root / "applied_changes.csv",
        applied_changes,
        base_columns + ("target_frame", "target_record_id", "target_measurement_uid", "target_business_key", "change_type", "field_name", "old_value", "new_value", "old_row_json", "new_row_json"),
    )

    payload = {
        "release_id": release_id,
        "report_time": _iso_now(),
        "instruction_count": len(instructions),
        "matched_target_rows": len(matched_targets),
        "applied_instruction_rows": len(applied_rows),
        "applied_change_rows": len(applied_changes),
        "skipped_rows": len(skipped_rows),
        "conflict_rows": len(conflict_rows),
        "paths": {
            "matched_targets": str(matched_root / "matched_targets.csv"),
            "applied_changes": str(applied_root / "applied_changes.csv"),
        },
    }
    write_json(report_root / "manual_override_report.json", payload)
    lines = [
        f"Release ID: {release_id}",
        f"Generated at: {payload['report_time']}",
        f"Instruction rows: {payload['instruction_count']}",
        f"Matched target rows: {payload['matched_target_rows']}",
        f"Applied instruction rows: {payload['applied_instruction_rows']}",
        f"Applied change rows: {payload['applied_change_rows']}",
        f"Skipped rows: {payload['skipped_rows']}",
        f"Conflict rows: {payload['conflict_rows']}",
    ]
    (report_root / "manual_override_report.txt").write_text("\n".join(lines), encoding="utf-8")


def _seven_key_match_mask(frame: pd.DataFrame, patch: pd.Series) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column in BUSINESS_KEY_FIELDS:
        expected = normalize_text(patch.get(column, ""))
        if column == "enzyme_type":
            expected = normalize_text(expected).lower().replace(" ", "_")
        elif column == "sequence":
            expected = expected.replace(" ", "").upper()
        mask &= frame[column].fillna("").astype(str).map(normalize_text).eq(expected)
    return mask


def _build_batch(frame: pd.DataFrame, source_type: SourceType, release_id: str, source_name: str) -> StandardizedBatch:
    item = StandardizedInput(
        frame=ensure_control_columns(frame.copy()),
        source_type=source_type,
        source_path=Path(source_name),
        detected_format="csv",
        missing_required=(),
    )
    return StandardizedBatch(items=(item,), source_root=Path(source_name))


def _split_external_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    working = ensure_control_columns(frame.copy())
    condition_rows = working.loc[working["parameter_name"].isin(("ph", "temperature"))].copy()
    kinetic_rows = working.loc[working["parameter_name"].isin(("kcat", "km"))].copy()
    supported_index = condition_rows.index.union(kinetic_rows.index)
    rejected = working.loc[~working.index.isin(supported_index)].copy()
    return kinetic_rows, condition_rows, rejected


def _apply_external_condition_supplements(target_frames: dict[str, pd.DataFrame], patches: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    updated = {name: frame.copy() for name, frame in target_frames.items()}
    rejected_rows: list[dict[str, object]] = []
    conflict_rows: list[dict[str, object]] = []
    for _, patch in patches.iterrows():
        field_name = normalize_parameter_name(patch.get("parameter_name", ""))
        new_value = normalize_text(patch.get(field_name, "") or patch.get("value", ""))
        if field_name not in {"ph", "temperature"} or not new_value:
            rejected_rows.append(patch.to_dict())
            continue
        if not has_auto_match_evidence(patch):
            rejected = patch.to_dict()
            rejected["reject_reason"] = "insufficient_match_evidence"
            rejected_rows.append(rejected)
            continue
        matched_any = False
        for frame_name, frame in updated.items():
            target_record_id = normalize_text(patch.get("record_id", ""))
            if target_record_id:
                mask = frame["record_id"] == target_record_id
            else:
                mask = _seven_key_match_mask(frame, patch)
            if not mask.any():
                continue
            matched_any = True
            for row_index in frame.index[mask]:
                old_value = normalize_text(frame.at[row_index, field_name])
                if not old_value:
                    frame.at[row_index, field_name] = new_value
                elif old_value != new_value:
                    conflict = patch.to_dict()
                    conflict["target_frame"] = frame_name
                    conflict["conflict_type"] = "condition_value_conflict"
                    conflict["old_value"] = old_value
                    conflict["new_value"] = new_value
                    conflict_rows.append(conflict)
        if not matched_any:
            rejected_rows.append(patch.to_dict())
    return updated, pd.DataFrame(rejected_rows), pd.DataFrame(conflict_rows)


def _write_formal_outputs(paths: AppPaths, release_id: str, master_frames: dict[str, pd.DataFrame], merged_frames: dict[str, pd.DataFrame]) -> tuple[dict[str, Path], dict[str, Path]]:
    master_paths: dict[str, Path] = {}
    merged_paths: dict[str, Path] = {}
    for key, file_name in MASTER_OUTPUT_FILES.items():
        path = paths.release_output_master_root(release_id) / file_name
        _strip_control(master_frames[key]).to_csv(path, index=False)
        master_paths[key] = path
    for key, file_name in MERGED_OUTPUT_FILES.items():
        path = paths.release_output_merged_root(release_id) / file_name
        _strip_control(merged_frames[key]).to_csv(path, index=False)
        merged_paths[key] = path
    return master_paths, merged_paths


def _build_output_manifest(paths: AppPaths, release_id: str, source_type: SourceType) -> dict[str, object]:
    release_root = paths.release_root(release_id)

    def file_rows(root: Path) -> list[dict[str, object]]:
        if not root.exists():
            return []
        rows = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rows.append(
                {
                    "path": _relative(path, release_root),
                    "file_name": path.name,
                    "row_count": count_lines(path) if path.suffix.lower() == ".csv" else 0,
                    "column_count": count_columns(path) if path.suffix.lower() == ".csv" else 0,
                    "size_bytes": path.stat().st_size,
                    "sha1": sha1_file(path),
                }
            )
        return rows

    outputs = {}
    for name, root in {
        "master": paths.release_output_master_root(release_id),
        "merged": paths.release_output_merged_root(release_id),
        "summary": paths.release_output_summary_root(release_id),
        "conditions": paths.release_output_conditions_root(release_id),
    }.items():
        files = file_rows(root)
        outputs[name] = {"root": _relative(root, release_root), "file_count": len(files), "files": files}

    audit_root = paths.release_audit_root(release_id)
    audit_files = file_rows(audit_root)
    return {
        "release_id": release_id,
        "run_status": "completed",
        "source_type": source_type.value,
        "outputs": outputs,
        "audits": {"root": _relative(audit_root, release_root), "file_count": len(audit_files), "files": audit_files},
        "workspace": {
            "raw_source_used": source_type == SourceType.RAW_SOURCE,
            "external_source_used": source_type == SourceType.EXTERNAL_SOURCE,
            "manual_override_used": source_type == SourceType.MANUAL_OVERRIDE,
        },
    }


def _write_file_inventory(paths: AppPaths, release_id: str) -> Path:
    release_root = paths.release_root(release_id)
    manifest_root = paths.release_manifest_root(release_id)
    inventory_path = manifest_root / "file_inventory.csv"
    with inventory_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("release_id", "category", "subtype", "relative_path", "file_name", "row_count", "column_count", "size_bytes", "modified_time", "sha1"),
        )
        writer.writeheader()
        for path in sorted(release_root.rglob("*")):
            if not path.is_file():
                continue
            parts = path.relative_to(release_root).parts
            category = parts[0] if parts else ""
            subtype = parts[1] if len(parts) > 1 else ""
            writer.writerow(
                {
                    "release_id": release_id,
                    "category": category,
                    "subtype": subtype,
                    "relative_path": _relative(path, release_root),
                    "file_name": path.name,
                    "row_count": count_lines(path) if path.suffix.lower() == ".csv" else 0,
                    "column_count": count_columns(path) if path.suffix.lower() == ".csv" else 0,
                    "size_bytes": path.stat().st_size,
                    "modified_time": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                    "sha1": sha1_file(path),
                }
            )
    return inventory_path


def _write_input_manifest(paths: AppPaths, release_id: str, config: RunConfig, snapshot_path: Path | None) -> None:
    input_files = []
    if config.input_path and config.input_path.exists():
        for path in discover_input_files(config.input_path):
            if not path.is_file():
                continue
            input_files.append(
                {
                    "relative_path": _relative(path, paths.repo_root),
                    "format": path.suffix.lower().lstrip("."),
                    "size_bytes": path.stat().st_size,
                    "modified_time": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                    "sha1": sha1_file(path),
                }
            )
    reference_files = [
        _relative(path, paths.repo_root)
        for path in sorted(paths.reference_root.rglob("*"))
        if path.is_file()
    ]
    payload = {
        "release_id": release_id,
        "source_type": config.source_type.value,
        "input_root": str(config.input_path) if config.input_path else "",
        "input_files": input_files,
        "reference_files": reference_files,
        "current_baseline_root": _relative(paths.current_root, paths.repo_root),
        "snapshot_used": snapshot_path is not None,
        "snapshot_path": _relative(snapshot_path, paths.repo_root) if snapshot_path is not None else None,
        "input_file_count": len(input_files),
    }
    write_json(paths.release_manifest_root(release_id) / "input_manifest.json", payload)


def _review_release(paths: AppPaths, release_id: str, source_type: SourceType) -> tuple[str, list[str]]:
    issues: list[str] = []
    warnings: list[str] = []

    for file_name in MASTER_OUTPUT_FILES.values():
        if not (paths.release_output_master_root(release_id) / file_name).exists():
            issues.append(f"missing master output: {file_name}")
    for file_name in MERGED_OUTPUT_FILES.values():
        if not (paths.release_output_merged_root(release_id) / file_name).exists():
            issues.append(f"missing merged output: {file_name}")
    for file_name in CONDITION_OUTPUT_FILES:
        if not (paths.release_output_conditions_root(release_id) / file_name).exists():
            issues.append(f"missing condition output: {file_name}")

    old_total = 0
    new_total = 0
    for key, file_name in MERGED_OUTPUT_FILES.items():
        old_total += len(read_csv_or_empty(paths.current_merged_root / file_name))
        new_total += len(read_csv_or_empty(paths.release_output_merged_root(release_id) / file_name))

    if old_total:
        change_ratio = abs(new_total - old_total) / old_total
        if source_type == SourceType.MANUAL_OVERRIDE:
            if change_ratio > 0.02:
                issues.append("manual_override changed merged total rows by more than 2%")
            elif change_ratio > 0.005:
                warnings.append("manual_override changed merged total rows by more than 0.5%")
        elif source_type == SourceType.EXTERNAL_SOURCE:
            if new_total < old_total * 0.95:
                issues.append("external_source reduced merged total rows by more than 5%")
            elif new_total < old_total * 0.99:
                warnings.append("external_source reduced merged total rows by more than 1%")
            if new_total > old_total * 2:
                issues.append("external_source increased merged total rows by more than 100%")
            elif new_total > old_total * 1.5:
                warnings.append("external_source increased merged total rows by more than 50%")
        elif source_type == SourceType.RAW_SOURCE:
            if new_total < old_total * 0.8:
                issues.append("raw_source reduced merged total rows by more than 20%")
            elif new_total < old_total * 0.9:
                warnings.append("raw_source reduced merged total rows by more than 10%")

    if issues:
        return "fail", issues + warnings
    if warnings:
        return "pass_with_warning", warnings
    return "pass", []


def _append_current_switch_audit(paths: AppPaths, release_id: str, source_type: SourceType, snapshot_path: Path, status: str, notes: str) -> None:
    audit_root = ensure_dir(paths.history_audit_root)
    audit_path = audit_root / "current_switch_audit.csv"
    if audit_path.exists():
        frame = pd.read_csv(audit_path, dtype=str).fillna("")
    else:
        frame = pd.DataFrame(columns=CURRENT_SWITCH_COLUMNS)
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                [
                    {
                        "release_id": release_id,
                        "switch_time": _iso_now(),
                        "operator": "system",
                        "source_type": source_type.value,
                        "snapshot_path": str(snapshot_path),
                        "output_path": str(paths.release_output_root(release_id)),
                        "status": status,
                        "notes": notes,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    frame.to_csv(audit_path, index=False)


def _switch_current(paths: AppPaths, release_id: str) -> None:
    for current_root, release_root in (
        (paths.current_master_root, paths.release_output_master_root(release_id)),
        (paths.current_merged_root, paths.release_output_merged_root(release_id)),
        (paths.current_summary_root, paths.release_output_summary_root(release_id)),
        (paths.current_conditions_root, paths.release_output_conditions_root(release_id)),
    ):
        if current_root.exists():
            shutil.rmtree(current_root)
        _copy_tree_contents(release_root, current_root)


def _write_run_summary(paths: AppPaths, release_id: str, source_type: SourceType, status: str, warnings: list[str]) -> None:
    lines = [
        f"Release ID: {release_id}",
        f"Source type: {source_type.value}",
        f"Input mode: {source_type.value}",
        f"Status: {status}",
        f"Input files: {_relative(paths.release_manifest_root(release_id) / 'input_manifest.json', paths.release_root(release_id))}",
        "Outputs:",
        f"- {_relative(paths.release_output_master_root(release_id), paths.release_root(release_id))}",
        f"- {_relative(paths.release_output_merged_root(release_id), paths.release_root(release_id))}",
        f"- {_relative(paths.release_output_summary_root(release_id), paths.release_root(release_id))}",
        f"- {_relative(paths.release_output_conditions_root(release_id), paths.release_root(release_id))}",
        "Audits:",
        f"- {_relative(paths.release_audit_root(release_id), paths.release_root(release_id))}",
        f"Warnings: {', '.join(warnings) if warnings else 'none'}",
        "Notes: release completed by catapro_update_app",
    ]
    (paths.release_manifest_root(release_id) / "run_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def _write_release_manifest(paths: AppPaths, release_id: str, config: RunConfig, status: str) -> None:
    payload = {
        "release_id": release_id,
        "run_date": _iso_now(),
        "source_type": config.source_type.value,
        "input_mode": config.source_type.value,
        "status": status,
        "operator": "system",
        "software_version": "catapro_update_app_v1",
        "pipeline_mode": "legacy_black_box" if config.source_type == SourceType.RAW_SOURCE else "incremental_update",
        "repo_root": str(paths.repo_root),
        "data_root": str(paths.data_root),
        "notes": [],
    }
    write_json(paths.release_manifest_root(release_id) / "release_manifest.json", payload)


def _ensure_history_logs(paths: AppPaths) -> None:
    ensure_dir(paths.condition_history_root)
    ensure_dir(paths.history_logs_master_root)
    ensure_dir(paths.history_logs_merged_root)
    ensure_header_csv(paths.history_logs_master_root / "master_change_log.csv", ROW_HISTORY_COLUMNS)
    ensure_header_csv(paths.history_logs_merged_root / "merged_change_log.csv", ROW_HISTORY_COLUMNS)


def _row_history_lookup(frame: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, tuple[str, ...]]]:
    working = ensure_formal_identities(ensure_formal_schema(frame))
    if working.empty:
        return {}, {}
    working = working.drop_duplicates(subset=["record_id"], keep="last")
    row_lookup: dict[str, pd.Series] = {}
    signature_lookup: dict[str, tuple[str, ...]] = {}
    for _, row in working.iterrows():
        record_id = str(row.get("record_id", ""))
        if not record_id:
            continue
        row_lookup[record_id] = row
        signature_lookup[record_id] = tuple(normalize_text(row.get(column, "")) for column in FORMAL_ENRICHED_COLUMNS)
    return row_lookup, signature_lookup


def _append_row_history_log(
    log_path: Path,
    release_id: str,
    source_type: SourceType,
    table_scope: str,
    dataset_key: str,
    target_file: str,
    old_frame: pd.DataFrame,
    new_frame: pd.DataFrame,
) -> None:
    existing = pd.read_csv(log_path, dtype=str).fillna("") if log_path.exists() else pd.DataFrame(columns=ROW_HISTORY_COLUMNS)
    old_rows, old_signatures = _row_history_lookup(old_frame)
    new_rows, new_signatures = _row_history_lookup(new_frame)
    now = _iso_now()
    rows: list[dict[str, object]] = []
    serial = len(existing) + 1

    for record_id in sorted(set(old_rows) | set(new_rows)):
        old_row = old_rows.get(record_id)
        new_row = new_rows.get(record_id)
        if old_row is None:
            change_type = "append"
        elif new_row is None:
            change_type = "remove"
        elif old_signatures.get(record_id) != new_signatures.get(record_id):
            change_type = "replace"
        else:
            continue

        row = new_row if new_row is not None else old_row
        rows.append(
            {
                "log_id": f"log_{release_id}_{serial:08d}",
                "release_id": release_id,
                "log_time": now,
                "table_scope": table_scope,
                "dataset_key": dataset_key,
                "target_file": target_file,
                "change_type": change_type,
                "business_key": "" if row is None else row.get("business_key", ""),
                "record_id": record_id,
                "measurement_uid": "" if row is None else row.get("measurement_uid", ""),
                "parameter_name": "" if row is None else row.get("parameter_name", ""),
                "old_row_json": "" if old_row is None else old_row.to_json(force_ascii=False),
                "new_row_json": "" if new_row is None else new_row.to_json(force_ascii=False),
                "source_type": source_type.value,
                "notes": "",
            }
        )
        serial += 1

    if not rows:
        return

    updated = pd.concat([existing, pd.DataFrame(rows, columns=ROW_HISTORY_COLUMNS)], ignore_index=True)
    updated.to_csv(log_path, index=False)


def _append_master_and_merged_history_logs(paths: AppPaths, release_id: str, source_type: SourceType) -> None:
    master_log_path = paths.history_logs_master_root / "master_change_log.csv"
    merged_log_path = paths.history_logs_merged_root / "merged_change_log.csv"
    for dataset_key, file_name in MASTER_OUTPUT_FILES.items():
        _append_row_history_log(
            master_log_path,
            release_id,
            source_type,
            "master",
            dataset_key,
            file_name,
            read_csv_or_empty(paths.current_master_root / file_name),
            read_csv_or_empty(paths.release_output_master_root(release_id) / file_name),
        )
    for dataset_key, file_name in MERGED_OUTPUT_FILES.items():
        _append_row_history_log(
            merged_log_path,
            release_id,
            source_type,
            "merged",
            dataset_key,
            file_name,
            read_csv_or_empty(paths.current_merged_root / file_name),
            read_csv_or_empty(paths.release_output_merged_root(release_id) / file_name),
        )


def _append_condition_history_logs(paths: AppPaths, release_id: str) -> tuple[ConditionAppendResult, ...]:
    results: list[ConditionAppendResult] = []
    for condition_name in ("ph", "temperature"):
        release_path = paths.release_output_conditions_root(release_id) / f"{condition_name}_long_table.csv"
        release_frame = read_csv_or_empty(release_path)
        baseline_frame = read_csv_or_empty(paths.current_conditions_root / f"{condition_name}_long_table.csv")
        results.append(append_condition_history(paths, condition_name, release_frame, release_id, baseline_frame=baseline_frame))
    return tuple(results)


def _run_external_source(paths: AppPaths, config: RunConfig, batch: StandardizedBatch) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], DedupResult, ConditionExportBundle]:
    for item in batch.items:
        write_standardized_input(paths, item, config.release_id)

    current_master = _load_current_master_frames(paths)
    current_merged = _load_current_merged_frames(paths)
    leakage_test_keys = _load_intenzy_test_business_keys(paths)
    incoming = pd.concat([item.frame for item in batch.items], ignore_index=True) if batch.items else pd.DataFrame()
    kinetic_rows, condition_rows, rejected_rows = _split_external_rows(incoming)
    current_merged, supplement_rejected, supplement_conflicts = _apply_external_condition_supplements(current_merged, condition_rows)

    updated_master = {key: frame.copy() for key, frame in current_master.items()}
    updated_merged = {key: frame.copy() for key, frame in current_merged.items()}
    leakage_removed_frames: list[pd.DataFrame] = []
    for parameter_name in ("kcat", "km"):
        new_rows = kinetic_rows.loc[kinetic_rows["parameter_name"] == parameter_name].copy()
        dedup = merge_and_deduplicate(_build_batch(new_rows, SourceType.EXTERNAL_SOURCE, config.release_id, f"{parameter_name}.csv"), existing_frame=current_merged[parameter_name])
        merged_after_leakage, leakage_removed = filter_test_leakage(dedup.merged, leakage_test_keys.get(parameter_name, set()))
        updated_merged[parameter_name] = ensure_control_columns(merged_after_leakage)
        if not leakage_removed.empty:
            leakage_removed_frames.append(leakage_removed)
        catapro_key = f"catapro_{parameter_name}"
        master_dedup = merge_and_deduplicate(
            _build_batch(new_rows, SourceType.EXTERNAL_SOURCE, config.release_id, f"{parameter_name}_master.csv"),
            existing_frame=current_master[catapro_key],
        )
        master_after_leakage, _ = filter_test_leakage(master_dedup.merged, leakage_test_keys.get(parameter_name, set()))
        updated_master[catapro_key] = ensure_control_columns(master_after_leakage)

    master_paths, merged_paths = _write_formal_outputs(paths, config.release_id, updated_master, updated_merged)
    combined_batch = _build_batch(pd.concat([incoming], ignore_index=True), SourceType.EXTERNAL_SOURCE, config.release_id, "incoming.csv")
    full_dedup = merge_and_deduplicate(combined_batch, existing_frame=pd.concat([current_merged["kcat"], current_merged["km"]], ignore_index=True))
    final_merged_frame = pd.concat([updated_merged["kcat"], updated_merged["km"]], ignore_index=True)
    leakage_removed_frame = pd.concat(leakage_removed_frames, ignore_index=True, sort=False) if leakage_removed_frames else final_merged_frame.iloc[0:0].copy()
    if not leakage_removed_frame.empty and "matched_test_key" not in leakage_removed_frame.columns:
        leakage_removed_frame["matched_test_key"] = leakage_removed_frame["business_key"]
    full_dedup = DedupResult(
        combined=full_dedup.combined,
        import_duplicates=full_dedup.import_duplicates,
        business_duplicates=full_dedup.business_duplicates,
        rejected_rows=full_dedup.rejected_rows,
        conflicts=full_dedup.conflicts,
        leakage_removed=leakage_removed_frame,
        merged=final_merged_frame,
    )
    full_dedup = write_dedup_outputs(paths, combined_batch, full_dedup, config.release_id, SourceType.EXTERNAL_SOURCE, config.input_path or paths.data_root)

    audit_root = paths.release_audit_root(config.release_id)
    rejected_frames = [frame for frame in (rejected_rows, supplement_rejected, full_dedup.rejected_rows) if not frame.empty]
    if rejected_frames:
        _append_or_write_csv(audit_root / "rejected_rows.csv", pd.concat(rejected_frames, ignore_index=True, sort=False))
    conflict_frames = [frame for frame in (supplement_conflicts, full_dedup.conflicts) if not frame.empty]
    if conflict_frames:
        _append_or_write_csv(audit_root / "conflicts.csv", pd.concat(conflict_frames, ignore_index=True, sort=False))

    summary_bundle = build_summary_bundle(_strip_control(updated_merged["kcat"]), _strip_control(updated_merged["km"]))
    write_summary_bundle(paths.release_output_summary_root(config.release_id), summary_bundle)
    conditions = export_condition_tables(
        DedupResult(
            combined=full_dedup.combined,
            import_duplicates=full_dedup.import_duplicates,
            business_duplicates=full_dedup.business_duplicates,
            rejected_rows=full_dedup.rejected_rows,
            conflicts=full_dedup.conflicts,
            leakage_removed=full_dedup.leakage_removed,
            merged=pd.concat([_strip_control(updated_merged["kcat"]), _strip_control(updated_merged["km"])], ignore_index=True),
        )
    )
    conditions = write_condition_exports(paths, conditions, config.release_id, config.source_type.value, merged_paths["kcat"])
    _write_external_workspace_reports(paths, config.release_id, incoming, kinetic_rows, condition_rows, full_dedup, conditions)
    return updated_master, updated_merged, full_dedup, conditions


def _apply_manual_override(master_frames: dict[str, pd.DataFrame], merged_frames: dict[str, pd.DataFrame], instructions: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    updated_master = {key: frame.copy() for key, frame in master_frames.items()}
    updated_merged = {key: frame.copy() for key, frame in merged_frames.items()}
    rekey_fields = set(BUSINESS_KEY_FIELDS) | {"parameter_name", "value", "value_normalized", "ph", "temperature", "organism", "ions"}
    rows_requiring_new_record_id: dict[str, set[int]] = {}
    matched_target_rows: list[dict[str, object]] = []
    applied_rows: list[dict[str, object]] = []
    applied_change_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []
    conflict_rows: list[dict[str, object]] = []

    for _, instruction in instructions.iterrows():
        action = normalize_text(instruction.get("action", "")).lower()
        match_key_type = normalize_text(instruction.get("match_key_type", "")).lower()
        target_scope = normalize_text(instruction.get("target_scope", "")).lower()
        if action not in ALLOWED_OVERRIDE_ACTIONS or match_key_type not in ALLOWED_OVERRIDE_MATCH_KEY_TYPES:
            skipped = instruction.to_dict()
            skipped["skip_reason"] = "invalid_action_or_match_key_type"
            skipped_rows.append(skipped)
            continue
        if match_key_type == "record_key" and target_scope != "workspace":
            skipped = instruction.to_dict()
            skipped["skip_reason"] = "record_key_requires_workspace_scope"
            skipped_rows.append(skipped)
            continue

        target_table = normalize_text(instruction.get("target_table", "")).lower()
        target_frames = updated_master if target_table == "master" else updated_merged
        if target_table == "conditions":
            target_frames = updated_merged

        business_key = ""
        if match_key_type == "business_key":
            if not has_auto_match_evidence(instruction):
                skipped = instruction.to_dict()
                skipped["skip_reason"] = "insufficient_match_evidence"
                skipped_rows.append(skipped)
                continue
            business_key = canonical_business_key_from_row(pd.Series(instruction.to_dict()))

        matches: list[tuple[str, list[int]]] = []
        for frame_name, frame in target_frames.items():
            if match_key_type == "record_id":
                mask = frame["record_id"] == normalize_text(instruction.get("record_id", ""))
            elif match_key_type == "business_key":
                if "business_key" in frame.columns:
                    mask = frame["business_key"].fillna("").astype(str).eq(business_key)
                else:
                    recalculated = frame.apply(canonical_business_key_from_row, axis=1)
                    mask = recalculated.eq(business_key)
            else:
                record_key = normalize_text(instruction.get("record_key", ""))
                mask = frame["record_key"] == record_key if "record_key" in frame.columns else pd.Series(False, index=frame.index)
            if not mask.any():
                continue
            matches.append((frame_name, list(frame.index[mask])))

        total_hits = sum(len(indices) for _, indices in matches)
        if total_hits == 0:
            skipped = instruction.to_dict()
            skipped["skip_reason"] = "target_not_found"
            skipped_rows.append(skipped)
            continue
        if match_key_type in {"record_id", "business_key"} and total_hits != 1:
            conflict = instruction.to_dict()
            conflict["conflict_type"] = "multi_hit_match"
            conflict["conflict_detail"] = total_hits
            conflict_rows.append(conflict)
            continue

        field_name = normalize_text(instruction.get("field_name", ""))
        for frame_name, row_indices in matches:
            frame = target_frames[frame_name]
            for row_index in row_indices:
                target_row = frame.loc[row_index].copy()
                matched_target = instruction.to_dict()
                matched_target["target_frame"] = frame_name
                matched_target["target_record_id"] = target_row.get("record_id", "")
                matched_target["target_measurement_uid"] = target_row.get("measurement_uid", "")
                matched_target["target_business_key"] = target_row.get("business_key", "")
                matched_target["target_parameter_name"] = target_row.get("parameter_name", "")
                matched_target["target_source_db"] = target_row.get("source_db", "")
                matched_target["matched_field_name"] = field_name
                matched_target["matched_old_value"] = normalize_text(target_row.get(field_name, "")) if field_name in frame.columns else ""
                matched_target["target_row_json"] = target_row.to_json(force_ascii=False)
                matched_target_rows.append(matched_target)
            if action == "drop_row":
                for row_index in row_indices:
                    old_row = frame.loc[row_index].copy()
                    applied_change = instruction.to_dict()
                    applied_change["target_frame"] = frame_name
                    applied_change["target_record_id"] = old_row.get("record_id", "")
                    applied_change["target_measurement_uid"] = old_row.get("measurement_uid", "")
                    applied_change["target_business_key"] = old_row.get("business_key", "")
                    applied_change["change_type"] = "drop_row"
                    applied_change["field_name"] = field_name
                    applied_change["old_value"] = normalize_text(old_row.get(field_name, "")) if field_name in frame.columns else ""
                    applied_change["new_value"] = ""
                    applied_change["old_row_json"] = old_row.to_json(force_ascii=False)
                    applied_change["new_row_json"] = ""
                    applied_change_rows.append(applied_change)
                target_frames[frame_name] = frame.loc[~frame.index.isin(row_indices)].copy()
                applied = instruction.to_dict()
                applied["target_frame"] = frame_name
                applied_rows.append(applied)
                continue
            if field_name not in frame.columns:
                conflict = instruction.to_dict()
                conflict["conflict_type"] = "missing_field"
                conflict["conflict_detail"] = field_name
                conflict_rows.append(conflict)
                continue
            for row_index in row_indices:
                old_value = normalize_text(frame.at[row_index, field_name])
                new_value = normalize_text(instruction.get("new_value", ""))
                expected = normalize_text(instruction.get("old_value_expected", ""))
                if expected and old_value != expected:
                    skipped = instruction.to_dict()
                    skipped["skip_reason"] = "old_value_expected_mismatch"
                    skipped_rows.append(skipped)
                    continue
                if action == "fill_if_blank" and old_value:
                    skipped = instruction.to_dict()
                    skipped["skip_reason"] = "target_not_blank"
                    skipped_rows.append(skipped)
                    continue
                old_row = frame.loc[row_index].copy()
                if action == "clear":
                    new_value = ""
                frame.at[row_index, field_name] = new_value
                if field_name == "value":
                    frame.at[row_index, "value_normalized"] = new_value
                elif field_name == "unit":
                    frame.at[row_index, "unit_normalized"] = new_value
                new_row = frame.loc[row_index].copy()
                applied = instruction.to_dict()
                applied["target_frame"] = frame_name
                applied["old_value"] = old_value
                applied["new_value"] = new_value
                applied_rows.append(applied)
                applied_change = instruction.to_dict()
                applied_change["target_frame"] = frame_name
                applied_change["target_record_id"] = new_row.get("record_id", "")
                applied_change["target_measurement_uid"] = new_row.get("measurement_uid", "")
                applied_change["target_business_key"] = new_row.get("business_key", "")
                applied_change["change_type"] = action
                applied_change["field_name"] = field_name
                applied_change["old_value"] = old_value
                applied_change["new_value"] = new_value
                applied_change["old_row_json"] = old_row.to_json(force_ascii=False)
                applied_change["new_row_json"] = new_row.to_json(force_ascii=False)
                applied_change_rows.append(applied_change)
                if field_name in rekey_fields:
                    rows_requiring_new_record_id.setdefault(frame_name, set()).add(row_index)
            target_frames[frame_name] = frame

    for frame_name, frame in updated_master.items():
        refreshed = ensure_control_columns(ensure_formal_identities(frame))
        changed_rows = rows_requiring_new_record_id.get(frame_name, set())
        if changed_rows:
            refreshed.loc[list(changed_rows), "record_id"] = refreshed.loc[list(changed_rows)].apply(record_id_from_row, axis=1)
        updated_master[frame_name] = refreshed
    for frame_name, frame in updated_merged.items():
        refreshed = ensure_control_columns(ensure_formal_identities(frame))
        changed_rows = rows_requiring_new_record_id.get(frame_name, set())
        if changed_rows:
            refreshed.loc[list(changed_rows), "record_id"] = refreshed.loc[list(changed_rows)].apply(record_id_from_row, axis=1)
        updated_merged[frame_name] = refreshed

    return (
        updated_master,
        updated_merged,
        pd.DataFrame(matched_target_rows),
        pd.DataFrame(applied_rows),
        pd.DataFrame(applied_change_rows),
        pd.DataFrame(skipped_rows),
        pd.DataFrame(conflict_rows),
    )


def _run_manual_override(paths: AppPaths, config: RunConfig, batch: StandardizedBatch) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], ConditionExportBundle]:
    for item in batch.items:
        write_standardized_input(paths, item, config.release_id)
    current_master = _load_current_master_frames(paths)
    current_merged = _load_current_merged_frames(paths)
    instructions = pd.concat([item.frame for item in batch.items], ignore_index=True) if batch.items else pd.DataFrame()
    updated_master, updated_merged, matched_targets, applied, applied_changes, skipped, conflicts = _apply_manual_override(current_master, current_merged, instructions)
    audit_root = paths.release_audit_root(config.release_id)
    base_columns = tuple(instructions.columns)
    _write_frame_or_header(audit_root / "override_applied.csv", applied, base_columns + ("target_frame", "old_value", "new_value"))
    _write_frame_or_header(audit_root / "override_skipped.csv", skipped, base_columns + ("skip_reason",))
    _write_frame_or_header(audit_root / "override_conflicts.csv", conflicts, base_columns + ("conflict_type", "conflict_detail"))
    _write_manual_override_workspace_reports(paths, config.release_id, instructions, matched_targets, applied, applied_changes, skipped, conflicts)
    _write_formal_outputs(paths, config.release_id, updated_master, updated_merged)
    summary_bundle = build_summary_bundle(_strip_control(updated_merged["kcat"]), _strip_control(updated_merged["km"]))
    write_summary_bundle(paths.release_output_summary_root(config.release_id), summary_bundle)
    merged_combined = pd.concat([_strip_control(updated_merged["kcat"]), _strip_control(updated_merged["km"])], ignore_index=True)
    empty = merged_combined.iloc[0:0].copy()
    conditions = export_condition_tables(
        DedupResult(
            combined=merged_combined,
            import_duplicates=empty,
            business_duplicates=empty,
            rejected_rows=empty,
            conflicts=empty,
            leakage_removed=empty,
            merged=merged_combined,
        )
    )
    conditions = write_condition_exports(paths, conditions, config.release_id, config.source_type.value, paths.current_merged_root / MERGED_OUTPUT_FILES["kcat"], workspace_name="manual_override")
    return updated_master, updated_merged, conditions


def _run_raw_source(paths: AppPaths, config: RunConfig) -> tuple[LegacyPipelineResult, ConditionExportBundle | None]:
    result = run_legacy_pipeline(paths, config.release_id, config.input_path)
    if not result.ok:
        return result, None
    existing_ph_path = paths.release_output_conditions_root(config.release_id) / "ph_long_table.csv"
    existing_temperature_path = paths.release_output_conditions_root(config.release_id) / "temperature_long_table.csv"
    if existing_ph_path.exists() and existing_temperature_path.exists():
        bundle = ConditionExportBundle(
            exports=(
                ConditionExport("ph", read_csv_or_empty(existing_ph_path)),
                ConditionExport("temperature", read_csv_or_empty(existing_temperature_path)),
            )
        )
        conditions = write_condition_exports(
            paths,
            bundle,
            config.release_id,
            config.source_type.value,
            paths.release_output_merged_root(config.release_id) / MERGED_OUTPUT_FILES["kcat"],
            workspace_name="raw_source",
        )
        return result, conditions
    merged_kcat = read_csv_or_empty(paths.release_output_merged_root(config.release_id) / MERGED_OUTPUT_FILES["kcat"])
    merged_km = read_csv_or_empty(paths.release_output_merged_root(config.release_id) / MERGED_OUTPUT_FILES["km"])
    merged_combined = pd.concat([merged_kcat, merged_km], ignore_index=True)
    empty = merged_combined.iloc[0:0].copy()
    conditions = export_condition_tables(
        DedupResult(
            combined=merged_combined,
            import_duplicates=empty,
            business_duplicates=empty,
            rejected_rows=empty,
            conflicts=empty,
            leakage_removed=empty,
            merged=merged_combined,
        )
    )
    conditions = write_condition_exports(paths, conditions, config.release_id, config.source_type.value, paths.release_output_merged_root(config.release_id) / MERGED_OUTPUT_FILES["kcat"], workspace_name="raw_source")
    return result, conditions


def run_update(paths: AppPaths, config: RunConfig) -> RunResult:
    _prepare_release_roots(paths, config.release_id)
    _ensure_history_logs(paths)
    plan = build_plan(paths, config)
    write_plan_artifacts(paths, config.release_id, plan)
    write_validate_artifacts(paths, config.release_id, config, plan.validation)
    if plan.validation is None or not plan.validation.can_run:
        _write_release_manifest(paths, config.release_id, config, "failed")
        return RunResult(config.release_id, "failed", "fail", False, paths.release_root(config.release_id), ("validation failed",))

    snapshot_path = _snapshot_current(paths, config.release_id)
    _write_input_manifest(paths, config.release_id, config, snapshot_path)
    _write_empty_audit_files(paths, config.release_id)

    notes: list[str] = []
    condition_history: tuple[ConditionAppendResult, ...] = ()
    if config.source_type == SourceType.RAW_SOURCE:
        legacy_result, _ = _run_raw_source(paths, config)
        if not legacy_result.ok:
            _write_release_manifest(paths, config.release_id, config, "failed")
            _write_run_summary(paths, config.release_id, config.source_type, "failed", ["legacy pipeline failed"])
            return RunResult(config.release_id, "failed", "fail", False, paths.release_root(config.release_id), ("legacy pipeline failed",))
    elif config.source_type == SourceType.MANUAL_OVERRIDE:
        if plan.standardized_batch is None:
            _write_release_manifest(paths, config.release_id, config, "failed")
            return RunResult(config.release_id, "failed", "fail", False, paths.release_root(config.release_id), ("no manual override instructions found",))
        _run_manual_override(paths, config, plan.standardized_batch)
    else:
        if plan.standardized_batch is None:
            _write_release_manifest(paths, config.release_id, config, "failed")
            return RunResult(config.release_id, "failed", "fail", False, paths.release_root(config.release_id), ("no external input rows found",))
        _run_external_source(paths, config, plan.standardized_batch)

    output_manifest = _build_output_manifest(paths, config.release_id, config.source_type)
    write_json(paths.release_manifest_root(config.release_id) / "output_manifest.json", output_manifest)
    _write_file_inventory(paths, config.release_id)
    review_status, review_notes = _review_release(paths, config.release_id, config.source_type)
    notes.extend(review_notes)
    current_switched = False
    if review_status == "pass":
        _append_master_and_merged_history_logs(paths, config.release_id, config.source_type)
        condition_history = _append_condition_history_logs(paths, config.release_id)
        _switch_current(paths, config.release_id)
        _append_current_switch_audit(paths, config.release_id, config.source_type, snapshot_path, "completed", "review_passed_and_current_updated")
        current_switched = True
        release_status = "completed"
    elif review_status == "pass_with_warning":
        release_status = "completed_with_warning"
    else:
        release_status = "failed"
    if condition_history:
        notes.append(f"condition_history_updates={len(condition_history)}")
    _write_release_manifest(paths, config.release_id, config, release_status)
    _write_run_summary(paths, config.release_id, config.source_type, release_status, notes)
    return RunResult(config.release_id, release_status, review_status, current_switched, paths.release_root(config.release_id), tuple(notes))
