from __future__ import annotations

from catapro_update_app.pipeline.importer import standardize_external_input
from catapro_update_app.rules.policy import SourceType
from conftest import make_test_dir


def test_external_source_standardization_maps_aliases_and_defaults() -> None:
    input_path = make_test_dir("importer") / "external_update.csv"
    input_path.write_text(
        "\n".join(
            [
                "Uniprot,parameter_name,value,unit,condition_note,organism,mutation_status",
                "P12345,Temperature,37,C,assay buffer,Escherichia coli,wildtype",
            ]
        ),
        encoding="utf-8",
    )

    result = standardize_external_input(input_path, SourceType.EXTERNAL_SOURCE, "rel-001")

    assert result.detected_format == "csv"
    assert result.missing_required == ()
    row = result.frame.iloc[0]
    assert row["enzyme_id"] == "P12345"
    assert row["condition_type"] == "temperature"
    assert str(row["raw_value"]) == "37"
    assert str(row["raw_unit"]) == "C"
    assert str(row["normalized_value"]) == "37"
    assert str(row["normalized_unit"]) == "C"
    assert row["condition"] == "assay buffer"
    assert row["species"] == "Escherichia coli"
    assert row["wildtype_mutant"] == "wildtype"
    assert row["source"] == "external_source"
    assert row["source_file"] == "external_update.csv"
    assert row["source_row"] == 1
    assert row["release_id"] == "rel-001"
    assert row["record_key"] == "external_update:1"
    assert str(row["measurement_uid"]).startswith("muid_")
    assert str(row["record_id"]).startswith("frid_")
