from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from catapro_update_app.io.loaders import detect_format, discover_input_files
from catapro_update_app.pipeline.formal import canonical_business_key_from_row, has_auto_match_evidence, normalize_text
from catapro_update_app.pipeline.importer import StandardizedBatch
from catapro_update_app.rules.policy import RulePolicy, SourceType
from catapro_update_app.rules.registry import ALLOWED_OVERRIDE_ACTIONS, ALLOWED_OVERRIDE_MATCH_KEY_TYPES, BUSINESS_KEY_FIELDS, REQUIRED_EXTERNAL_COLUMNS, REQUIRED_MANUAL_OVERRIDE_COLUMNS
from catapro_update_app.rules.registry import POLICY_BY_SOURCE


RECORD_ID_PATTERN = re.compile(r"^frid_[0-9a-f]{20}$")
MEASUREMENT_UID_PATTERN = re.compile(r"^muid_[0-9a-f]{20}$")


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    policy: RulePolicy
    status: str
    can_run: bool
    messages: list[ValidationMessage]
    file_checks: dict[str, object]
    schema_checks: dict[str, object]
    quality_checks: dict[str, object]
    summary: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.can_run


def _final_status(messages: list[ValidationMessage]) -> tuple[str, bool]:
    if any(item.level == "error" for item in messages):
        return "fail", False
    if any(item.level == "warning" for item in messages):
        return "pass_with_warning", True
    return "pass", True


def _add_message(messages: list[ValidationMessage], level: str, code: str, message: str) -> None:
    messages.append(ValidationMessage(level=level, code=code, message=message))


def _validate_manual_override_rows(messages: list[ValidationMessage], standardized_batch: StandardizedBatch) -> None:
    for item in standardized_batch.items:
        for row_number, (_, row) in enumerate(item.frame.iterrows(), start=1):
            row_prefix = f"{item.source_path.name} row {row_number}"
            action = normalize_text(row.get("action", "")).lower()
            target_scope = normalize_text(row.get("target_scope", "")).lower()
            target_table = normalize_text(row.get("target_table", "")).lower()
            match_key_type = normalize_text(row.get("match_key_type", "")).lower()

            if action not in ALLOWED_OVERRIDE_ACTIONS:
                _add_message(messages, "error", "manual_override_action", f"{row_prefix}: unsupported action `{action}`.")
            if target_scope not in {"current", "workspace"}:
                _add_message(messages, "error", "manual_override_scope", f"{row_prefix}: unsupported target_scope `{target_scope}`.")
            if target_table not in {"master", "merged", "conditions"}:
                _add_message(messages, "error", "manual_override_table", f"{row_prefix}: unsupported target_table `{target_table}`.")
            if match_key_type not in ALLOWED_OVERRIDE_MATCH_KEY_TYPES:
                _add_message(messages, "error", "manual_override_match_key_type", f"{row_prefix}: unsupported match_key_type `{match_key_type}`.")

            if action != "drop_row" and not normalize_text(row.get("field_name", "")):
                _add_message(messages, "error", "manual_override_field_name", f"{row_prefix}: field_name is required for non-drop actions.")

            if match_key_type == "record_id":
                record_id = normalize_text(row.get("record_id", ""))
                if not RECORD_ID_PATTERN.fullmatch(record_id):
                    _add_message(messages, "error", "manual_override_record_id", f"{row_prefix}: invalid record_id `{record_id}`.")
            elif match_key_type == "business_key":
                if not has_auto_match_evidence(row):
                    _add_message(messages, "error", "manual_override_business_key_evidence", f"{row_prefix}: business_key matching requires at least one of uniprot / sequence / substrate / smiles.")
                business_key = canonical_business_key_from_row(row)
                if not business_key or all(not token for token in business_key.split("|")):
                    _add_message(messages, "error", "manual_override_business_key", f"{row_prefix}: business_key matching requires a non-empty canonical key.")
            elif match_key_type == "record_key":
                if target_scope != "workspace":
                    _add_message(messages, "error", "manual_override_record_key_scope", f"{row_prefix}: record_key matching is allowed only for workspace scope.")
                if not normalize_text(row.get("record_key", "")):
                    _add_message(messages, "error", "manual_override_record_key", f"{row_prefix}: record_key is required when match_key_type=record_key.")


def validate_input_request(source_type: SourceType, input_path: Path, standardized_batch: StandardizedBatch | None = None) -> ValidationResult:
    messages: list[ValidationMessage] = []
    policy = POLICY_BY_SOURCE[source_type]

    if not input_path.exists():
        _add_message(messages, "error", "input_missing", f"Input path does not exist: {input_path}")
        status, can_run = _final_status(messages)
        return ValidationResult(policy, status, can_run, messages, {}, {}, {}, {"input_file_count": 0})

    input_files = [path for path in discover_input_files(input_path) if detect_format(path) is not None]
    if not input_files:
        _add_message(messages, "error", "no_supported_files", "No supported input files were found.")

    allowed_extensions = {
        SourceType.RAW_SOURCE: {".json", ".tsv"},
        SourceType.EXTERNAL_SOURCE: {".xlsx", ".xls", ".csv", ".json", ".tsv"},
        SourceType.MANUAL_OVERRIDE: {".csv", ".json", ".xlsx"},
    }[source_type]
    bad_extensions = [path.suffix.lower() for path in input_files if path.suffix.lower() not in allowed_extensions]
    if bad_extensions:
        _add_message(messages, "error", "unsupported_extension", f"Unsupported extensions for {source_type.value}: {sorted(set(bad_extensions))}")

    if source_type == SourceType.MANUAL_OVERRIDE and input_path.is_dir():
        _add_message(messages, "info", "manual_override_dir", "Manual override directory accepted; all contained files will be interpreted as patch instruction tables.")

    required_columns = {
        SourceType.RAW_SOURCE: (),
        SourceType.EXTERNAL_SOURCE: REQUIRED_EXTERNAL_COLUMNS,
        SourceType.MANUAL_OVERRIDE: REQUIRED_MANUAL_OVERRIDE_COLUMNS,
    }[source_type]

    standardized_row_count = 0
    standardized_success_count = 0
    insufficient_match_evidence_count = 0
    missing_required_files: list[str] = []
    if standardized_batch is not None:
        for item in standardized_batch.items:
            standardized_row_count += len(item.frame)
            missing_required_here = list(item.missing_required)
            if missing_required_here:
                missing_required_files.append(f"{item.source_path.name}: {', '.join(missing_required_here)}")
            else:
                standardized_success_count += len(item.frame)
            if source_type == SourceType.EXTERNAL_SOURCE:
                insufficient_match_evidence_count += int((~item.frame.apply(has_auto_match_evidence, axis=1)).sum())

    if missing_required_files:
        for message in missing_required_files:
            _add_message(messages, "error", "missing_required_columns", f"Missing required columns after standardization: {message}")

    if standardized_row_count:
        success_rate = standardized_success_count / standardized_row_count
        if source_type == SourceType.EXTERNAL_SOURCE:
            if success_rate < 0.90:
                _add_message(messages, "error", "low_standardization_success", f"External source standardization success rate is {success_rate:.2%}, below 90%.")
            elif success_rate < 0.95:
                _add_message(messages, "warning", "standardization_success_warning", f"External source standardization success rate is {success_rate:.2%}.")
            if insufficient_match_evidence_count / standardized_row_count > 0.05:
                _add_message(messages, "error", "insufficient_match_evidence_fail", "More than 5% of external rows have no automatic match evidence.")
            elif insufficient_match_evidence_count / standardized_row_count > 0.01:
                _add_message(messages, "warning", "insufficient_match_evidence_warning", "More than 1% of external rows have no automatic match evidence.")
        if source_type == SourceType.MANUAL_OVERRIDE and standardized_success_count != standardized_row_count:
            _add_message(messages, "error", "invalid_manual_override_rows", "Manual override instructions must have all required columns present.")

    if source_type == SourceType.RAW_SOURCE and input_path.is_dir():
        _add_message(messages, "info", "raw_directory", "Raw source directory accepted; the legacy 14-step pipeline will run as a black-box rebuild.")
    elif source_type == SourceType.RAW_SOURCE and input_path.is_file() and input_path.suffix.lower() not in {".json", ".tsv"}:
        _add_message(messages, "error", "raw_file_type", "Raw source updates must be BRENDA JSON or SABIO TSV files.")

    if source_type == SourceType.EXTERNAL_SOURCE:
        _add_message(messages, "info", "preserve_nulls", "External source updates preserve existing non-null values when resolving plain condition supplements.")
    if source_type == SourceType.MANUAL_OVERRIDE:
        _add_message(messages, "info", "manual_override_precise", "Manual override inputs are treated as precise patch instructions and will rebuild formal outputs after applying patches.")
        if standardized_batch is not None:
            _validate_manual_override_rows(messages, standardized_batch)

    status, can_run = _final_status(messages)
    file_checks = {
        "input_file_count": len(input_files),
        "allowed_extensions": sorted(allowed_extensions),
        "bad_extensions": sorted(set(bad_extensions)),
    }
    schema_checks = {
        "required_columns": list(required_columns),
        "missing_required_files": missing_required_files,
    }
    quality_checks = {
        "standardized_row_count": standardized_row_count,
        "standardized_success_count": standardized_success_count,
        "insufficient_match_evidence_count": insufficient_match_evidence_count,
    }
    summary = {
        "input_file_count": len(input_files),
        "status": status,
        "can_run": can_run,
    }
    return ValidationResult(policy, status, can_run, messages, file_checks, schema_checks, quality_checks, summary)
