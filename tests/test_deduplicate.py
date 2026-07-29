from __future__ import annotations

from pathlib import Path

import pandas as pd

from catapro_update_app.pipeline.deduplicate import filter_test_leakage, merge_and_deduplicate
from catapro_update_app.pipeline.formal import ensure_control_columns, ensure_formal_identities
from catapro_update_app.pipeline.importer import StandardizedBatch, StandardizedInput
from catapro_update_app.rules.policy import SourceType
from conftest import make_test_dir


def _formal_item(row: dict[str, object], source_path: Path, source_type: SourceType) -> StandardizedInput:
    frame = ensure_formal_identities(
        pd.DataFrame(
            [row],
            columns=(
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
            ),
        )
    )
    frame = ensure_control_columns(frame)
    frame["record_key"] = [f"{source_path.stem}:1"]
    frame["source"] = source_type.value
    frame["logical_source_type"] = source_type.value
    frame["source_file"] = source_path.name
    frame["source_row"] = [1]
    frame["release_id"] = [row.get("source_release", "")]
    frame["import_dedup_key"] = [f"{source_type.value}|{source_path.stem}|{frame.iloc[0]['record_id']}"]
    frame["enzyme_id"] = frame["uniprot"]
    frame["condition_type"] = frame["parameter_name"]
    frame["raw_value"] = frame["value"]
    frame["raw_unit"] = frame["unit"]
    frame["normalized_value"] = frame["value_normalized"]
    frame["normalized_unit"] = frame["unit_normalized"]
    return StandardizedInput(
        frame=frame,
        source_type=source_type,
        source_path=source_path,
        detected_format="csv",
        missing_required=(),
    )


def _base_row(value: str, source_db: str, source_release: str, source_record_id: str) -> dict[str, object]:
    return {
        "dataset_name": source_db,
        "parameter_name": "kcat",
        "source_db": source_db,
        "source_release": source_release,
        "source_record_id": source_record_id,
        "record_id": "",
        "measurement_uid": "",
        "ec_number": "1.1.1.1",
        "organism": "Escherichia coli",
        "uniprot": "P1",
        "enzyme_type": "wildtype",
        "mutation": "",
        "sequence": "MSEQUENCE",
        "sequence_source": "",
        "substrate": "glucose",
        "smiles": "C(C1C(C(C(C(O1)O)O)O)O)O",
        "value": value,
        "unit": "s^-1",
        "ph": "7.0",
        "temperature": "30",
        "ions": "",
        "reaction_raw": "",
        "commentary": "",
        "substrate_raw": "glucose",
        "parse_status": "parsed",
        "mutation_apply_status": "",
        "WT_sequence": "",
        "MUT_sequence": "",
        "value_normalized": value,
        "unit_normalized": "s^-1",
        "kcat_km_source_value": "",
        "kcat_km_source_unit": "",
        "kcat_km_computed_value": "",
        "kcat_km_computed_unit": "",
    }


def test_dedup_prefers_higher_priority_source_for_same_business_key_and_same_measurement() -> None:
    tmp_path = make_test_dir("dedup")
    raw_item = _formal_item(_base_row("12", "raw_source", "20260723-001", "raw-001"), tmp_path / "raw.csv", SourceType.RAW_SOURCE)
    external_item = _formal_item(_base_row("12", "external_source", "20260723-999", "ext-001"), tmp_path / "ext.csv", SourceType.EXTERNAL_SOURCE)

    batch = StandardizedBatch(items=(external_item, raw_item), source_root=tmp_path)
    result = merge_and_deduplicate(batch)

    assert len(result.combined) == 2
    assert len(result.merged) == 1
    assert len(result.duplicates) == 1
    assert len(result.rejected_rows) == 0
    assert result.merged.iloc[0]["source"] == "raw_source"
    assert result.duplicates.iloc[0]["source"] == "external_source"


def test_dedup_keeps_multiple_measurements_under_same_business_key() -> None:
    tmp_path = make_test_dir("dedup-multi")
    item_a = _formal_item(_base_row("12", "external_source", "20260723-001", "ext-001"), tmp_path / "a.csv", SourceType.EXTERNAL_SOURCE)
    item_b = _formal_item(_base_row("15", "external_source", "20260723-002", "ext-002"), tmp_path / "b.csv", SourceType.EXTERNAL_SOURCE)

    batch = StandardizedBatch(items=(item_a, item_b), source_root=tmp_path)
    result = merge_and_deduplicate(batch)

    assert len(result.combined) == 2
    assert len(result.merged) == 2
    assert len(result.duplicates) == 0
    assert len(result.rejected_rows) == 0
    assert result.merged["business_key"].nunique() == 1
    assert result.merged["measurement_uid"].nunique() == 2


def test_filter_test_leakage_removes_rows_with_blocked_business_keys() -> None:
    tmp_path = make_test_dir("dedup-leakage")
    item_a = _formal_item(_base_row("12", "external_source", "20260723-001", "ext-001"), tmp_path / "a.csv", SourceType.EXTERNAL_SOURCE)
    row_b = _base_row("15", "external_source", "20260723-002", "ext-002")
    row_b["substrate"] = "fructose"
    row_b["substrate_raw"] = "fructose"
    row_b["smiles"] = "SMILES_F"
    item_b = _formal_item(row_b, tmp_path / "b.csv", SourceType.EXTERNAL_SOURCE)
    frame = pd.concat([item_a.frame, item_b.frame], ignore_index=True)
    blocked_key = {str(frame.iloc[0]["business_key"])}

    kept, removed = filter_test_leakage(frame, blocked_key)

    assert len(kept) == 1
    assert len(removed) == 1
    assert removed.iloc[0]["matched_test_key"] == removed.iloc[0]["business_key"]
