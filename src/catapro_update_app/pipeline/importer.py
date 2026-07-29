from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.io.loaders import detect_format, discover_input_files, profile_input_file
from catapro_update_app.io.paths import ensure_dir
from catapro_update_app.pipeline.formal import (
    ensure_control_columns,
    ensure_formal_identities,
    ensure_formal_schema,
    normalize_enzyme_type,
    normalize_parameter_name,
    normalize_sequence,
    normalize_text,
    normalize_unit,
)
from catapro_update_app.reports.manifest import StandardizedArtifactManifest, write_manifest
from catapro_update_app.rules.mapping import FIELD_ALIASES, normalize_header
from catapro_update_app.rules.policy import SourceType
from catapro_update_app.rules.registry import BUSINESS_KEY_FIELDS, FORMAL_ENRICHED_COLUMNS, REQUIRED_EXTERNAL_COLUMNS, REQUIRED_MANUAL_OVERRIDE_COLUMNS


@dataclass(frozen=True)
class StandardizedInput:
    frame: pd.DataFrame
    source_type: SourceType
    source_path: Path
    detected_format: str
    missing_required: tuple[str, ...]
    output_path: Path | None = None
    manifest_path: Path | None = None


@dataclass(frozen=True)
class StandardizedBatch:
    items: tuple[StandardizedInput, ...]
    source_root: Path


def _read_frame(path: Path) -> pd.DataFrame:
    format_name = detect_format(path)
    if format_name == "excel":
        return pd.read_excel(path, dtype=str).fillna("")
    if format_name == "csv":
        return pd.read_csv(path, dtype=str).fillna("")
    if format_name == "tsv":
        return pd.read_csv(path, sep="\t", dtype=str).fillna("")
    if format_name == "json":
        return pd.read_json(path, dtype=str).fillna("")
    raise ValueError(f"Unsupported input format: {path}")


def _rename_to_canonical(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    normalized_lookup = {normalize_header(column): column for column in frame.columns}

    for canonical_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            token = normalize_header(alias)
            if token in normalized_lookup:
                source_column = normalized_lookup[token]
                if source_column not in rename_map:
                    rename_map[source_column] = canonical_name
                break

    return frame.rename(columns=rename_map)


def _pick(frame: pd.DataFrame, *candidates: str, default: str = "") -> pd.Series:
    for candidate in candidates:
        if candidate in frame.columns:
            return frame[candidate].map(normalize_text)
    return pd.Series([default] * len(frame), index=frame.index, dtype="object")


def _build_external_frame(frame: pd.DataFrame, path: Path, source_type: SourceType, release_id: str) -> pd.DataFrame:
    working = frame.copy()
    row_numbers = pd.Series(range(1, len(working) + 1), index=working.index, dtype="int64")
    parameter_name = _pick(working, "parameter_name").map(normalize_parameter_name)
    value = _pick(working, "value", "raw_value")
    unit = _pick(working, "unit", "raw_unit").map(normalize_unit)
    value_normalized = _pick(working, "value_normalized", "normalized_value", "value", "raw_value")
    unit_normalized = _pick(working, "unit_normalized", "normalized_unit", "unit", "raw_unit").map(normalize_unit)
    source_record_id = _pick(working, "source_record_id", default="")
    default_source_record_id = pd.Series([f"{path.stem}:{n}" for n in row_numbers], index=working.index, dtype="object")
    base = pd.DataFrame(
        {
            "dataset_name": [source_type.value] * len(working),
            "parameter_name": parameter_name,
            "source_db": _pick(working, "source_db", "source", default=source_type.value),
            "source_release": _pick(working, "source_release", default=release_id),
            "source_record_id": source_record_id.mask(source_record_id.eq(""), default_source_record_id),
            "record_id": "",
            "measurement_uid": "",
            "ec_number": _pick(working, "ec_number"),
            "organism": _pick(working, "organism", "species"),
            "uniprot": _pick(working, "uniprot", "enzyme_id"),
            "enzyme_type": _pick(working, "enzyme_type", "wildtype_mutant").map(normalize_enzyme_type),
            "mutation": _pick(working, "mutation"),
            "sequence": _pick(working, "sequence").map(normalize_sequence),
            "sequence_source": _pick(working, "sequence_source"),
            "substrate": _pick(working, "substrate"),
            "smiles": _pick(working, "smiles"),
            "value": value,
            "unit": unit,
            "ph": _pick(working, "ph"),
            "temperature": _pick(working, "temperature"),
            "ions": _pick(working, "ions"),
            "reaction_raw": _pick(working, "reaction_raw"),
            "commentary": _pick(working, "commentary", "condition"),
            "substrate_raw": _pick(working, "substrate_raw", "substrate"),
            "parse_status": _pick(working, "parse_status", default="parsed"),
            "mutation_apply_status": _pick(working, "mutation_apply_status"),
            "WT_sequence": _pick(working, "WT_sequence"),
            "MUT_sequence": _pick(working, "MUT_sequence"),
            "value_normalized": value_normalized,
            "unit_normalized": unit_normalized,
            "kcat_km_source_value": _pick(working, "kcat_km_source_value"),
            "kcat_km_source_unit": _pick(working, "kcat_km_source_unit"),
            "kcat_km_computed_value": _pick(working, "kcat_km_computed_value"),
            "kcat_km_computed_unit": _pick(working, "kcat_km_computed_unit"),
        }
    )

    ph_from_parameter = parameter_name.eq("ph")
    temperature_from_parameter = parameter_name.eq("temperature")
    base.loc[ph_from_parameter & base["ph"].eq(""), "ph"] = value.loc[ph_from_parameter]
    base.loc[temperature_from_parameter & base["temperature"].eq(""), "temperature"] = value.loc[temperature_from_parameter]
    base = ensure_formal_identities(base, refresh_record_id=True)
    base["enzyme_id"] = base["uniprot"]
    base["condition_type"] = base["parameter_name"]
    base["record_key"] = base["source_record_id"]
    base["raw_value"] = base["value"]
    base["raw_unit"] = base["unit"]
    base["normalized_value"] = base["value_normalized"]
    base["normalized_unit"] = base["unit_normalized"]
    base["condition"] = base["commentary"]
    base["species"] = base["organism"]
    base["wildtype_mutant"] = base["enzyme_type"]
    base["source"] = source_type.value
    base["source_file"] = path.name
    base["source_row"] = row_numbers.astype(int)
    base["release_id"] = release_id
    base["logical_source_type"] = source_type.value
    base["import_dedup_key"] = base.apply(lambda row: "|".join(normalize_text(row.get(column, "")) for column in FORMAL_ENRICHED_COLUMNS), axis=1)
    return ensure_control_columns(base)


def _build_manual_override_frame(frame: pd.DataFrame, path: Path, release_id: str) -> pd.DataFrame:
    working = frame.copy()
    if "record_id" not in working.columns and "formal_record_id" in working.columns:
        working["record_id"] = working["formal_record_id"]
    if "operation_id" not in working.columns:
        working["operation_id"] = [f"{path.stem}:{index}" for index in range(1, len(working) + 1)]
    for column in ("record_id", "record_key", "old_value_expected", "new_value"):
        if column not in working.columns:
            working[column] = ""
    for column in BUSINESS_KEY_FIELDS:
        if column not in working.columns:
            working[column] = ""
    working["source_file"] = path.name
    working["source_row"] = range(1, len(working) + 1)
    working["release_id"] = release_id
    for column in REQUIRED_MANUAL_OVERRIDE_COLUMNS:
        if column not in working.columns:
            working[column] = ""
    working = working.fillna("").apply(lambda column: column.map(normalize_text))
    for column in ("target_table", "target_scope", "match_key_type", "field_name", "action"):
        if column in working.columns:
            working[column] = working[column].map(lambda value: normalize_text(value).lower())
    return working


def _standardize_frame(path: Path, source_type: SourceType, release_id: str) -> StandardizedInput:
    profile = profile_input_file(path)
    frame = _rename_to_canonical(_read_frame(path))

    if source_type == SourceType.MANUAL_OVERRIDE:
        standardized_frame = _build_manual_override_frame(frame, path, release_id)
        missing_required = tuple(column for column in REQUIRED_MANUAL_OVERRIDE_COLUMNS if column not in standardized_frame.columns or standardized_frame[column].eq("").all())
        return StandardizedInput(
            frame=standardized_frame,
            source_type=source_type,
            source_path=path,
            detected_format=profile.format_name,
            missing_required=missing_required,
        )

    standardized_frame = _build_external_frame(frame, path, source_type, release_id)
    missing_required = tuple(column for column in REQUIRED_EXTERNAL_COLUMNS if standardized_frame[column].eq("").all())
    return StandardizedInput(
        frame=standardized_frame,
        source_type=source_type,
        source_path=path,
        detected_format=profile.format_name,
        missing_required=missing_required,
    )


def standardize_external_input(path: Path, source_type: SourceType, release_id: str) -> StandardizedInput:
    return _standardize_frame(path, source_type, release_id)


def standardize_input_batch(input_root: Path, source_type: SourceType, release_id: str) -> StandardizedBatch:
    files = discover_input_files(input_root)
    items = tuple(_standardize_frame(path, source_type, release_id) for path in files if detect_format(path))
    return StandardizedBatch(items=items, source_root=input_root)


def write_standardized_input(paths: AppPaths, standardized: StandardizedInput, release_id: str) -> StandardizedInput:
    if standardized.source_type == SourceType.MANUAL_OVERRIDE:
        output_root = ensure_dir(paths.release_workspace_manual_root(release_id) / "standardized_instructions")
    else:
        output_root = ensure_dir(paths.release_workspace_external_root(release_id) / "standardized_inputs")
    output_path = output_root / f"{standardized.source_path.stem}__standardized.csv"
    standardized.frame.to_csv(output_path, index=False)

    manifest = StandardizedArtifactManifest(
        release_id=release_id,
        source_type=standardized.source_type.value,
        input_path=str(standardized.source_path),
        output_path=str(output_path),
        row_count=len(standardized.frame),
        column_count=len(standardized.frame.columns),
        missing_required=standardized.missing_required,
    )
    manifest_path = write_manifest(output_root / f"{standardized.source_path.stem}__manifest.json", manifest)

    return StandardizedInput(
        frame=standardized.frame,
        source_type=standardized.source_type,
        source_path=standardized.source_path,
        detected_format=standardized.detected_format,
        missing_required=standardized.missing_required,
        output_path=output_path,
        manifest_path=manifest_path,
    )
