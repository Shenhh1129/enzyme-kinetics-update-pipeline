from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from catapro_update_app.rules.registry import (
    BUSINESS_KEY_FIELDS,
    CONTROL_COLUMNS,
    FORMAL_ENRICHED_COLUMNS,
    MEASUREMENT_IDENTITY_FIELDS,
    NULL_TOKENS,
)


FORMAL_PARAMETER_NAMES: tuple[str, ...] = ("kcat", "km", "kcat_km", "ph", "temperature")
FORMAL_RECORD_ID_PREFIX = "frid_"
MEASUREMENT_UID_PREFIX = "muid_"
AUTO_MATCH_EVIDENCE_FIELDS: tuple[str, ...] = ("uniprot", "sequence", "substrate", "smiles")
ENTRY_MATCH_PRIMARY_FIELDS: tuple[str, ...] = ("uniprot", "sequence")
ENTRY_MATCH_SECONDARY_FIELDS: tuple[str, ...] = ("substrate", "smiles")
RECORD_ID_DISAMBIGUATION_FIELDS: tuple[str, ...] = ("organism", "ions")


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in NULL_TOKENS:
        return ""
    return text


def normalize_parameter_name(value: object) -> str:
    text = normalize_text(value).lower().replace(" ", "").replace("-", "_").replace("/", "_")
    aliases = {
        "kcat": "kcat",
        "km": "km",
        "kcat_km": "kcat_km",
        "kcatoverkm": "kcat_km",
        "ph": "ph",
        "temperature": "temperature",
        "temp": "temperature",
    }
    return aliases.get(text, text)


def normalize_unit(value: object) -> str:
    text = normalize_text(value)
    aliases = {
        "c": "C",
        "掳c": "C",
        "degc": "C",
        "s-1": "s^-1",
        "sec^-1": "s^-1",
        "1/s": "s^-1",
        "m-1*s-1": "M^-1*s^-1",
        "m^-1 s^-1": "M^-1*s^-1",
        "m^-1*s^-1": "M^-1*s^-1",
    }
    return aliases.get(text.lower(), text)


def normalize_sequence(value: object) -> str:
    return normalize_text(value).replace(" ", "").replace("\n", "").replace("\r", "").upper()


def normalize_enzyme_type(value: object) -> str:
    text = normalize_text(value).lower().replace(" ", "_")
    aliases = {
        "wt": "wildtype",
        "wild": "wildtype",
        "wild_type": "wildtype",
        "wildtype": "wildtype",
        "mut": "mutant",
        "mutant": "mutant",
        "variant": "mutant",
        "ambiguous": "ambiguous",
    }
    return aliases.get(text, text)


def _has_any_nonempty(row: pd.Series | dict[str, object], fields: tuple[str, ...]) -> bool:
    return any(normalize_text(row.get(column, "")) for column in fields)


def has_auto_match_evidence(row: pd.Series | dict[str, object]) -> bool:
    return any(normalize_text(row.get(column, "")) for column in AUTO_MATCH_EVIDENCE_FIELDS)


def has_external_row_match_prerequisite(row: pd.Series | dict[str, object]) -> bool:
    return _has_any_nonempty(row, ENTRY_MATCH_PRIMARY_FIELDS) and _has_any_nonempty(row, ENTRY_MATCH_SECONDARY_FIELDS)


def external_source_row_requirement_issues(row: pd.Series | dict[str, object]) -> tuple[str, ...]:
    issues: list[str] = []
    if not normalize_parameter_name(row.get("parameter_name", "")):
        issues.append("missing_parameter_name")
    if not normalize_text(row.get("value", "")):
        issues.append("missing_value")
    if not _has_any_nonempty(row, ENTRY_MATCH_PRIMARY_FIELDS):
        issues.append("missing_uniprot_or_sequence")
    if not _has_any_nonempty(row, ENTRY_MATCH_SECONDARY_FIELDS):
        issues.append("missing_substrate_or_smiles")
    return tuple(issues)


def normalize_frame_text(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    working = frame.copy()
    for column in columns:
        if column in working.columns:
            working[column] = working[column].map(normalize_text)
    return working


def _identity_token(column: str, value: object) -> str:
    if column == "parameter_name":
        return normalize_parameter_name(value)
    if column == "sequence":
        return normalize_sequence(value)
    if column == "enzyme_type":
        return normalize_enzyme_type(value)
    if column in {"unit", "unit_normalized"}:
        return normalize_unit(value)
    return normalize_text(value)


def _digest20(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def _is_blank_key(text: str) -> bool:
    return all(not token for token in text.split("|"))


def canonical_business_key_from_row(row: pd.Series) -> str:
    parts: list[str] = []
    for column in BUSINESS_KEY_FIELDS:
        parts.append(_identity_token(column, row.get(column, "")))
    return "|".join(parts)


def add_business_keys(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in BUSINESS_KEY_FIELDS:
        if column not in working.columns:
            working[column] = ""
    if "parameter_name" in working.columns:
        working["parameter_name"] = working["parameter_name"].map(normalize_parameter_name)
    working["enzyme_type"] = working["enzyme_type"].map(normalize_enzyme_type)
    working["sequence"] = working["sequence"].map(normalize_sequence)
    for column in ("uniprot", "mutation", "substrate", "smiles"):
        working[column] = working[column].map(normalize_text)
    working["business_key"] = working.apply(canonical_business_key_from_row, axis=1)
    return working


def canonical_measurement_identity_from_row(row: pd.Series) -> str:
    parts: list[str] = []
    for column in MEASUREMENT_IDENTITY_FIELDS:
        if column == "value_normalized":
            parts.append(normalize_text(row.get("value_normalized", "")) or normalize_text(row.get("value", "")))
        else:
            parts.append(_identity_token(column, row.get(column, "")))
    return "|".join(parts)


def measurement_uid_from_row(row: pd.Series) -> str:
    seed = canonical_measurement_identity_from_row(row)
    if not seed or _is_blank_key(seed):
        return ""
    return f"{MEASUREMENT_UID_PREFIX}{_digest20(seed)}"

def canonical_record_identity_from_row(row: pd.Series) -> str:
    measurement_uid = normalize_text(row.get("measurement_uid", "")) or measurement_uid_from_row(row)
    if not measurement_uid:
        return ""
    parts = [measurement_uid]
    for column in RECORD_ID_DISAMBIGUATION_FIELDS:
        parts.append(normalize_text(row.get(column, "")))
    return "|".join(parts)


def record_id_from_row(row: pd.Series, source_type: object | None = None) -> str:
    del source_type
    seed = canonical_record_identity_from_row(row)
    if not seed:
        return ""
    return f"{FORMAL_RECORD_ID_PREFIX}{_digest20(seed)}"


def ensure_formal_schema(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in FORMAL_ENRICHED_COLUMNS:
        if column not in working.columns:
            working[column] = ""
    return working.loc[:, list(FORMAL_ENRICHED_COLUMNS)]


def ensure_formal_identities(frame: pd.DataFrame, refresh_record_id: bool = False) -> pd.DataFrame:
    working = ensure_formal_schema(frame)
    working["parameter_name"] = working["parameter_name"].map(normalize_parameter_name)
    working["enzyme_type"] = working["enzyme_type"].map(normalize_enzyme_type)
    working["sequence"] = working["sequence"].map(normalize_sequence)
    for column in (
        "dataset_name",
        "source_db",
        "source_release",
        "source_record_id",
        "ec_number",
        "organism",
        "uniprot",
        "mutation",
        "sequence_source",
        "substrate",
        "smiles",
        "value",
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
        "kcat_km_source_value",
        "kcat_km_source_unit",
        "kcat_km_computed_value",
        "kcat_km_computed_unit",
    ):
        working[column] = working[column].map(normalize_text)
    working["unit"] = working["unit"].map(normalize_unit)
    working["value_normalized"] = working["value_normalized"].map(normalize_text)
    working["unit_normalized"] = working["unit_normalized"].map(normalize_unit)
    working.loc[working["value_normalized"].eq(""), "value_normalized"] = working.loc[working["value_normalized"].eq(""), "value"]
    working.loc[working["unit_normalized"].eq(""), "unit_normalized"] = working.loc[working["unit_normalized"].eq(""), "unit"]

    ph_mask = working["parameter_name"].eq("ph") & working["ph"].eq("")
    temperature_mask = working["parameter_name"].eq("temperature") & working["temperature"].eq("")
    working.loc[ph_mask, "ph"] = working.loc[ph_mask, "value"]
    working.loc[temperature_mask, "temperature"] = working.loc[temperature_mask, "value"]

    working = add_business_keys(working)
    working["measurement_uid"] = working.apply(measurement_uid_from_row, axis=1)
    computed_record_ids = working.apply(record_id_from_row, axis=1)
    if refresh_record_id:
        working["record_id"] = computed_record_ids
    else:
        existing_record_ids = working["record_id"].map(normalize_text)
        working["record_id"] = existing_record_ids.where(existing_record_ids.ne(""), computed_record_ids)
    return working


def ensure_control_columns(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in CONTROL_COLUMNS:
        if column not in working.columns:
            working[column] = ""
    return working


def empty_formal_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FORMAL_ENRICHED_COLUMNS)


def empty_formal_with_control_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FORMAL_ENRICHED_COLUMNS + CONTROL_COLUMNS)


def read_csv_or_empty(path: Path, columns: tuple[str, ...] = FORMAL_ENRICHED_COLUMNS) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype=str).fillna("")
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, list(columns)]


def classify_existing_logical_source(dataset_name: str, source_db: str) -> str:
    text = normalize_text(source_db or dataset_name).lower()
    if text in {"manual_override"}:
        return "manual_override"
    if text in {"external_source"}:
        return "external_source"
    return "raw_source"
