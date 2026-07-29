from __future__ import annotations

from dataclasses import dataclass

from catapro_update_app.io.loaders import InputFileProfile, normalized_columns
from catapro_update_app.rules.mapping import FIELD_ALIASES, normalize_header
from catapro_update_app.rules.policy import SourceType
from catapro_update_app.rules.registry import CANONICAL_FIELDS


@dataclass(frozen=True)
class FieldMatch:
    canonical_name: str
    source_column: str


@dataclass(frozen=True)
class HarmonizationReport:
    profile: InputFileProfile
    matches: tuple[FieldMatch, ...]
    missing_required: tuple[str, ...]
    warnings: tuple[str, ...]


def harmonize_profile(profile: InputFileProfile, source_type: SourceType) -> HarmonizationReport:
    columns_by_token = normalized_columns(profile.columns)
    matches: list[FieldMatch] = []

    for canonical_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            token = normalize_header(alias)
            if token in columns_by_token:
                matches.append(FieldMatch(canonical_name=canonical_name, source_column=columns_by_token[token]))
                break

    matched_names = {item.canonical_name for item in matches}
    missing_required = tuple(
        field.name for field in CANONICAL_FIELDS if field.required and field.name not in matched_names
    )

    warnings: list[str] = []
    if source_type.name == "EXTERNAL_SOURCE" and "condition_type" not in matched_names:
        warnings.append("External inputs should provide condition_type so pH and temperature records can be routed correctly.")
    if "raw_value" not in matched_names and "value" not in matched_names:
        warnings.append("No value-like column was detected.")
    if "enzyme_id" not in matched_names:
        warnings.append("No enzyme identifier column was detected.")

    return HarmonizationReport(
        profile=profile,
        matches=tuple(matches),
        missing_required=missing_required,
        warnings=tuple(warnings),
    )
