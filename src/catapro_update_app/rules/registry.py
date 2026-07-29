from __future__ import annotations

from dataclasses import dataclass

from catapro_update_app.rules.policy import RulePolicy, SourceType, UpdateMode


@dataclass(frozen=True)
class InputFormatSpec:
    name: str
    extensions: tuple[str, ...]


@dataclass(frozen=True)
class FieldRule:
    name: str
    required: bool
    description: str


@dataclass(frozen=True)
class ConditionTableSpec:
    name: str
    required_fields: tuple[FieldRule, ...]


BUSINESS_KEY_FIELDS: tuple[str, ...] = (
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "substrate",
    "smiles",
)


MEASUREMENT_IDENTITY_FIELDS: tuple[str, ...] = (
    "parameter_name",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "substrate",
    "smiles",
    "value_normalized",
    "ph",
    "temperature",
)


FORMAL_ENRICHED_COLUMNS: tuple[str, ...] = (
    "dataset_name",
    "parameter_name",
    "source_db",
    "source_release",
    "source_record_id",
    "record_id",
    "measurement_uid",
    "ec_number",
    "organism",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "sequence_source",
    "substrate",
    "smiles",
    "value",
    "unit",
    "ph",
    "temperature",
    "ions",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "parse_status",
    "mutation_apply_status",
    "WT_sequence",
    "MUT_sequence",
    "value_normalized",
    "unit_normalized",
    "kcat_km_source_value",
    "kcat_km_source_unit",
    "kcat_km_computed_value",
    "kcat_km_computed_unit",
)


CONTROL_COLUMNS: tuple[str, ...] = (
    "record_key",
    "source",
    "source_file",
    "source_row",
    "release_id",
    "business_key",
    "logical_source_type",
    "import_dedup_key",
)


MERGED_OUTPUT_FILES: dict[str, str] = {
    "kcat": "merge_kcat_final_v6_enriched.csv",
    "km": "merge_km_final_v6_enriched.csv",
}


MASTER_OUTPUT_FILES: dict[str, str] = {
    "catapro_kcat": "CataPro_kcat_master_v6_enriched.csv",
    "catapro_km": "CataPro_km_master_v6_enriched.csv",
    "dlkcat_kcat": "DLKcat_kcat_master_v6_enriched.csv",
    "intenzy_kcat": "IntEnzy_kcat_master_v6_enriched.csv",
    "intenzy_km": "IntEnzy_km_master_v6_enriched.csv",
    "skid_kcat": "SKiD_kcat_master_v6_enriched.csv",
    "skid_km": "SKiD_km_master_v6_enriched.csv",
}


SUMMARY_OUTPUT_FILES: tuple[str, ...] = (
    "summary_v6.txt",
    "summary_v6_counts.csv",
    "mutation/kcat_mutation_rows_v6.csv",
    "mutation/km_mutation_rows_v6.csv",
    "ph_tem_empty/kcat_ph_temperature_empty_v6.csv",
    "ph_tem_empty/km_ph_temperature_empty_v6.csv",
    "unit/kcat_unit_audit_v6.csv",
    "unit/km_unit_audit_v6.csv",
)


CONDITION_OUTPUT_FILES: tuple[str, ...] = (
    "ph_long_table.csv",
    "temperature_long_table.csv",
)


MANIFEST_FILES: tuple[str, ...] = (
    "release_manifest.json",
    "input_manifest.json",
    "output_manifest.json",
    "file_inventory.csv",
    "run_summary.txt",
    "plan_preview.json",
    "plan_preview.txt",
    "validate_report.json",
    "validate_report.txt",
)


AUDIT_FILES: tuple[str, ...] = (
    "import_duplicate_rows.csv",
    "business_duplicate_rows.csv",
    "test_leakage_removed.csv",
    "rejected_rows.csv",
    "conflicts.csv",
    "validation_issues.csv",
    "override_applied.csv",
    "override_skipped.csv",
    "override_conflicts.csv",
)


REQUIRED_EXTERNAL_COLUMNS: tuple[str, ...] = (
    "parameter_name",
    "value",
)


REQUIRED_MANUAL_OVERRIDE_COLUMNS: tuple[str, ...] = (
    "operation_id",
    "target_table",
    "target_scope",
    "match_key_type",
    "field_name",
    "action",
    "reason",
    "approved_by",
    "approved_at",
)


ALLOWED_OVERRIDE_MATCH_KEY_TYPES: tuple[str, ...] = (
    "record_id",
    "business_key",
    "record_key",
)


ALLOWED_OVERRIDE_ACTIONS: tuple[str, ...] = (
    "replace",
    "fill_if_blank",
    "clear",
    "drop_row",
)


NULL_TOKENS: tuple[str, ...] = ("", "na", "n/a", "null", "none", "nan", "-")


SUPPORTED_INPUT_FORMATS: tuple[InputFormatSpec, ...] = (
    InputFormatSpec("excel", (".xlsx", ".xls")),
    InputFormatSpec("csv", (".csv",)),
    InputFormatSpec("json", (".json",)),
    InputFormatSpec("tsv", (".tsv",)),
)


POLICY_BY_SOURCE: dict[SourceType, RulePolicy] = {
    SourceType.RAW_SOURCE: RulePolicy(
        source_type=SourceType.RAW_SOURCE,
        update_mode=UpdateMode.FULL_REBUILD,
    ),
    SourceType.EXTERNAL_SOURCE: RulePolicy(
        source_type=SourceType.EXTERNAL_SOURCE,
        update_mode=UpdateMode.INCREMENTAL_APPEND,
    ),
    SourceType.MANUAL_OVERRIDE: RulePolicy(
        source_type=SourceType.MANUAL_OVERRIDE,
        update_mode=UpdateMode.OVERRIDE_ONLY,
    ),
}


CANONICAL_FIELDS: tuple[FieldRule, ...] = (
    FieldRule("record_key", True, "Stable record identifier used for deduplication."),
    FieldRule("source", True, "Logical source name."),
    FieldRule("source_file", True, "Original input file path or name."),
    FieldRule("source_row", True, "Original row number or JSON path."),
    FieldRule("release_id", True, "Release version identifier."),
    FieldRule("enzyme_id", True, "Canonical enzyme identifier."),
    FieldRule("condition_type", True, "Condition type such as ph or temperature."),
    FieldRule("raw_value", False, "Unnormalized source value."),
    FieldRule("normalized_value", False, "Normalized comparison value."),
    FieldRule("raw_unit", False, "Source unit before normalization."),
    FieldRule("normalized_unit", False, "Standardized unit after normalization."),
    FieldRule("quality_flag", False, "Validation and quality marker."),
)


CONDITION_TABLE_SPECS: tuple[ConditionTableSpec, ...] = (
    ConditionTableSpec(
        "ph",
        (
            FieldRule("record_key", True, "Stable record identifier."),
            FieldRule("enzyme_id", True, "Canonical enzyme identifier."),
            FieldRule("condition_type", True, "Must be ph."),
            FieldRule("value", False, "Raw or direct numeric pH value."),
            FieldRule("unit", False, "Usually blank for pH but kept for consistency."),
            FieldRule("normalized_value", False, "Normalized pH value."),
            FieldRule("normalized_unit", False, "Standard unit representation."),
            FieldRule("condition", False, "Condition notes."),
            FieldRule("species", False, "Species or host name."),
            FieldRule("wildtype_mutant", False, "Wildtype or mutant status."),
            FieldRule("source", True, "Logical source name."),
            FieldRule("source_file", True, "Original input file path or name."),
            FieldRule("source_row", True, "Original row number or JSON path."),
            FieldRule("release_id", True, "Release version identifier."),
            FieldRule("quality_flag", False, "Validation and quality marker."),
        ),
    ),
    ConditionTableSpec(
        "temperature",
        (
            FieldRule("record_key", True, "Stable record identifier."),
            FieldRule("enzyme_id", True, "Canonical enzyme identifier."),
            FieldRule("condition_type", True, "Must be temperature."),
            FieldRule("value", False, "Raw or direct numeric temperature value."),
            FieldRule("unit", False, "Temperature source unit."),
            FieldRule("normalized_value", False, "Normalized temperature value."),
            FieldRule("normalized_unit", False, "Standard unit representation."),
            FieldRule("condition", False, "Condition notes."),
            FieldRule("species", False, "Species or host name."),
            FieldRule("wildtype_mutant", False, "Wildtype or mutant status."),
            FieldRule("source", True, "Logical source name."),
            FieldRule("source_file", True, "Original input file path or name."),
            FieldRule("source_row", True, "Original row number or JSON path."),
            FieldRule("release_id", True, "Release version identifier."),
            FieldRule("quality_flag", False, "Validation and quality marker."),
        ),
    ),
)
