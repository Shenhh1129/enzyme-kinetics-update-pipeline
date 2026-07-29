from __future__ import annotations

from catapro_update_app.io.paths import PathCheck
from catapro_update_app.pipeline.deduplicate import DedupResult
from catapro_update_app.pipeline.importer import StandardizedBatch, StandardizedInput
from catapro_update_app.pipeline.runner import PipelinePlan
from catapro_update_app.pipeline.conditions import ConditionAppendResult, ConditionExportBundle
from catapro_update_app.rules.harmonize import HarmonizationReport
from catapro_update_app.rules.validation import ValidationResult


def render_checks(checks: list[PathCheck]) -> str:
    lines = ["Path checks:"]
    for check in checks:
        state = "OK" if check.exists else "MISSING"
        lines.append(f"- [{state}] {check.path} ({check.kind})")
    return "\n".join(lines)


def render_validation(validation: ValidationResult | None) -> str:
    if validation is None:
        return "Input validation:\n- [SKIP] No input path was provided."

    lines = [
        "Input validation:",
        f"- [POLICY] source_type={validation.policy.source_type.value}",
        f"- [POLICY] update_mode={validation.policy.update_mode.value}",
        f"- [POLICY] conflict_policy={validation.policy.conflict_policy.value}",
    ]
    for item in validation.messages:
        lines.append(f"- [{item.level.upper()}] {item.code}: {item.message}")
    return "\n".join(lines)


def render_harmonization(report: HarmonizationReport | None) -> str:
    if report is None:
        return "Schema harmonization:\n- [SKIP] No external/manual input profile was generated."

    lines = [
        "Schema harmonization:",
        f"- [FILE] path={report.profile.path}",
        f"- [FILE] format={report.profile.format_name}",
        f"- [FILE] row_count={report.profile.row_count}",
        f"- [FILE] columns={', '.join(report.profile.columns) if report.profile.columns else '(none)'}",
    ]
    for match in report.matches:
        lines.append(f"- [MATCH] {match.canonical_name} <- {match.source_column}")
    for field_name in report.missing_required:
        lines.append(f"- [MISSING] required field not found: {field_name}")
    for warning in report.warnings:
        lines.append(f"- [WARN] {warning}")
    return "\n".join(lines)


def render_standardized_batch(batch: StandardizedBatch | None) -> str:
    if batch is None:
        return "Standardized batch:\n- [SKIP] No batch was generated."

    lines = [
        "Standardized batch:",
        f"- [FILES] count={len(batch.items)}",
        f"- [ROOT] {batch.source_root}",
    ]
    for item in batch.items[:5]:
        lines.append(f"- [ITEM] {item.source_path.name} rows={len(item.frame)} cols={len(item.frame.columns)}")
    if len(batch.items) > 5:
        lines.append(f"- [ITEM] ... {len(batch.items) - 5} more")
    return "\n".join(lines)


def render_standardized(standardized: StandardizedInput | None) -> str:
    if standardized is None:
        return "Standardized preview:\n- [SKIP] No standardized frame was generated."

    preview_columns = ", ".join(map(str, standardized.frame.columns[:20]))
    lines = [
        "Standardized preview:",
        f"- [FRAME] rows={len(standardized.frame)}",
        f"- [FRAME] columns={len(standardized.frame.columns)}",
        f"- [FRAME] detected_format={standardized.detected_format}",
        f"- [FRAME] preview_columns={preview_columns}",
    ]
    if standardized.output_path:
        lines.append(f"- [WRITE] output_path={standardized.output_path}")
    if standardized.manifest_path:
        lines.append(f"- [WRITE] manifest_path={standardized.manifest_path}")
    for field_name in standardized.missing_required:
        lines.append(f"- [MISSING] standardized frame still lacks required field: {field_name}")
    return "\n".join(lines)


def render_dedup(dedup: DedupResult | None) -> str:
    if dedup is None:
        return "Deduplication:\n- [SKIP] No dedup result was generated."

    lines = [
        "Deduplication:",
        f"- [COMBINED] rows={len(dedup.combined)}",
        f"- [MERGED] rows={len(dedup.merged)}",
        f"- [IMPORT_DUPLICATES] rows={len(dedup.import_duplicates)}",
        f"- [BUSINESS_DUPLICATES] rows={len(dedup.business_duplicates)}",
    ]
    if dedup.merged_path:
        lines.append(f"- [WRITE] merged_path={dedup.merged_path}")
    if dedup.import_duplicates_path:
        lines.append(f"- [WRITE] import_duplicates_path={dedup.import_duplicates_path}")
    if dedup.business_duplicates_path:
        lines.append(f"- [WRITE] business_duplicates_path={dedup.business_duplicates_path}")
    if dedup.leakage_removed_path:
        lines.append(f"- [WRITE] leakage_removed_path={dedup.leakage_removed_path}")
    if dedup.manifest_path:
        lines.append(f"- [WRITE] manifest_path={dedup.manifest_path}")
    return "\n".join(lines)


def render_conditions(bundle: ConditionExportBundle | None) -> str:
    if bundle is None:
        return "Condition exports:\n- [SKIP] No condition exports were generated."

    lines = ["Condition exports:"]
    for item in bundle.exports:
        lines.append(f"- [CONDITION] {item.condition_name} rows={len(item.frame)} cols={len(item.frame.columns)}")
        if item.output_path:
            lines.append(f"- [WRITE] {item.output_path}")
        if item.manifest_path:
            lines.append(f"- [WRITE] {item.manifest_path}")
    return "\n".join(lines)


def render_condition_history(results: tuple[ConditionAppendResult, ...]) -> str:
    if not results:
        return "Condition history:\n- [SKIP] No condition history updates were generated."

    lines = ["Condition history:"]
    for item in results:
        lines.append(
            f"- [HISTORY] {item.condition_name} current={len(item.current_release)} master={len(item.history_master)} log={len(item.history_log)} rejected={len(item.rejected_rows)} conflicts={len(item.conflicts)}"
        )
        if item.master_path:
            lines.append(f"- [WRITE] {item.master_path}")
        if item.log_path:
            lines.append(f"- [WRITE] {item.log_path}")
        if item.rejected_path:
            lines.append(f"- [WRITE] {item.rejected_path}")
        if item.conflicts_path:
            lines.append(f"- [WRITE] {item.conflicts_path}")
    return "\n".join(lines)


def render_plan(plan: PipelinePlan) -> str:
    lines = ["CataPro update plan:"]
    for stage in plan.stages:
        state = "READY" if stage.ready else "BLOCKED"
        lines.append(f"- [{state}] {stage.spec.name}: {stage.spec.description}")
    lines.append(f"- [FLAG] wrote_standardized={plan.wrote_standardized}")
    lines.append(f"- [FLAG] wrote_release_artifacts={plan.wrote_release_artifacts}")
    return "\n".join(lines)
