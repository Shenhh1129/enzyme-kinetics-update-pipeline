from __future__ import annotations

import json
import random

import pandas as pd

from catapro_update_app.cli.main import main as cli_main
from catapro_update_app.config.settings import AppPaths, RunConfig
from catapro_update_app.pipeline import runner
from catapro_update_app.pipeline.formal import ensure_formal_identities
from catapro_update_app.pipeline.legacy import LegacyPipelineResult, LegacyScriptResult
from catapro_update_app.pipeline.runner import run_update
from catapro_update_app.pipeline.summary_outputs import build_summary_bundle, write_summary_bundle
from catapro_update_app.pipeline.importer import standardize_input_batch
from catapro_update_app.rules.policy import SourceType
from catapro_update_app.rules.registry import FORMAL_ENRICHED_COLUMNS, MASTER_OUTPUT_FILES, MERGED_OUTPUT_FILES
from conftest import make_test_dir


def _empty_formal_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FORMAL_ENRICHED_COLUMNS)


def _seed_empty_current(paths: AppPaths) -> None:
    paths.current_master_root.mkdir(parents=True, exist_ok=True)
    paths.current_merged_root.mkdir(parents=True, exist_ok=True)
    paths.current_summary_root.mkdir(parents=True, exist_ok=True)
    paths.current_conditions_root.mkdir(parents=True, exist_ok=True)
    for file_name in MASTER_OUTPUT_FILES.values():
        _empty_formal_frame().to_csv(paths.current_master_root / file_name, index=False)
    for file_name in MERGED_OUTPUT_FILES.values():
        _empty_formal_frame().to_csv(paths.current_merged_root / file_name, index=False)


def _formal_row(
    parameter_name: str,
    index: int,
    value: str,
    *,
    source_db: str = "CataPro",
    source_release: str = "baseline",
    ph: str = "7.0",
    temperature: str = "30",
    commentary: str = "",
) -> dict[str, object]:
    return {
        "dataset_name": source_db,
        "parameter_name": parameter_name,
        "source_db": source_db,
        "source_release": source_release,
        "source_record_id": f"{source_db.lower()}-{parameter_name}-{index:03d}",
        "record_id": "",
        "measurement_uid": "",
        "ec_number": f"1.1.{(index % 7) + 1}.1",
        "organism": "Escherichia coli" if index % 2 == 0 else "Bacillus subtilis",
        "uniprot": f"P{index:05d}",
        "enzyme_type": "wildtype" if index % 3 else "mutant",
        "mutation": "" if index % 3 else f"A{index}V",
        "sequence": f"MSEQUENCE{index:03d}",
        "sequence_source": "uniprot",
        "substrate": f"substrate_{index % 4}",
        "smiles": f"SMILES_{index % 4}",
        "value": value,
        "unit": "s^-1" if parameter_name == "kcat" else "mM",
        "ph": ph,
        "temperature": temperature,
        "ions": "",
        "reaction_raw": "",
        "commentary": commentary,
        "substrate_raw": f"substrate_{index % 4}",
        "parse_status": "parsed",
        "mutation_apply_status": "",
        "WT_sequence": "",
        "MUT_sequence": "",
        "value_normalized": value,
        "unit_normalized": "s^-1" if parameter_name == "kcat" else "mM",
        "kcat_km_source_value": "",
        "kcat_km_source_unit": "",
        "kcat_km_computed_value": "",
        "kcat_km_computed_unit": "",
    }


def _write_current_frame(path, rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = ensure_formal_identities(pd.DataFrame(rows, columns=FORMAL_ENRICHED_COLUMNS))
    frame.to_csv(path, index=False)
    return frame


def test_run_update_external_source_randomized_batch_writes_expected_outputs() -> None:
    rng = random.Random(20260727)
    tmp_path = make_test_dir("run-external-random")
    paths = AppPaths(repo_root=tmp_path / "repo", data_root=tmp_path / "data")
    paths.reference_root.mkdir(parents=True, exist_ok=True)
    _seed_empty_current(paths)

    input_root = tmp_path / "incoming_external"
    input_root.mkdir(parents=True, exist_ok=True)
    rows = [
        "parameter_name,ec_number,uniprot,enzyme_type,mutation,sequence,substrate,smiles,value,unit,organism,commentary,source_record_id,ph,temperature",
    ]
    generated_records: list[dict[str, str]] = []
    for index in range(1, 7):
        parameter_name = "kcat" if index % 2 else "km"
        ec_number = f"1.1.{index}.1"
        uniprot = f"P{10000 + index}"
        enzyme_type = "wildtype" if index % 3 else "mutant"
        mutation = "" if enzyme_type == "wildtype" else f"A{index}V"
        sequence = f"MSEQ{index:03d}"
        substrate = f"substrate_{index % 3}"
        smiles = f"SMILES_{index % 3}"
        value = str(10 + rng.randint(1, 20))
        unit = "s^-1" if parameter_name == "kcat" else "mM"
        organism = "Escherichia coli" if index % 2 else "Bacillus subtilis"
        commentary = f"row_{index}"
        source_record_id = f"ext-{index:03d}"
        ph = f"{6.5 + (index / 10):.1f}"
        temperature = str(25 + index)
        record = {
            "parameter_name": parameter_name,
            "ec_number": ec_number,
            "uniprot": uniprot,
            "enzyme_type": enzyme_type,
            "mutation": mutation,
            "sequence": sequence,
            "substrate": substrate,
            "smiles": smiles,
            "value": value,
            "unit": unit,
            "organism": organism,
            "commentary": commentary,
            "source_record_id": source_record_id,
            "ph": ph,
            "temperature": temperature,
        }
        generated_records.append(record)
        rows.append(",".join(record[column] for column in record))

    duplicate = generated_records[0] | {"source_record_id": "ext-dup-001", "commentary": "duplicate_measurement"}
    rows.append(",".join(duplicate[column] for column in duplicate))
    alternative_measurement = generated_records[1] | {"source_record_id": "ext-alt-001", "value": str(int(generated_records[1]["value"]) + 5)}
    rows.append(",".join(alternative_measurement[column] for column in alternative_measurement))

    (input_root / "external_update.csv").write_text("\n".join(rows), encoding="utf-8")

    standardized_batch = standardize_input_batch(input_root, SourceType.EXTERNAL_SOURCE, "20260727-ext-random")
    standardized_frame = pd.concat([item.frame for item in standardized_batch.items], ignore_index=True)
    blocked_key = str(standardized_frame.loc[standardized_frame["parameter_name"] == "kcat"].iloc[0]["business_key"])
    leakage_seed = standardized_frame.loc[standardized_frame["parameter_name"] == "kcat"].iloc[[0]].copy()
    leakage_seed = leakage_seed.loc[:, FORMAL_ENRICHED_COLUMNS]
    leakage_seed["dataset_name"] = "IntEnzy"
    leakage_seed["source_db"] = "IntEnzy"
    leakage_seed["source_release"] = "baseline_intenzy"
    leakage_seed.to_csv(paths.current_master_root / "IntEnzy_kcat_master_v6_enriched.csv", index=False)
    expected = standardized_frame.loc[standardized_frame["parameter_name"].isin(("kcat", "km"))].copy()
    expected["dedup_key"] = expected["business_key"] + "|" + expected["measurement_uid"]
    expected = expected.drop_duplicates("dedup_key")
    expected = expected.loc[~((expected["parameter_name"] == "kcat") & expected["business_key"].eq(blocked_key))].copy()
    expected_counts = expected.groupby("parameter_name").size().to_dict()

    result = run_update(
        paths,
        RunConfig(
            release_id="20260727-ext-random",
            source_type=SourceType.EXTERNAL_SOURCE,
            input_path=input_root,
            write_standardized=True,
            write_release_artifacts=True,
        ),
    )

    assert result.status == "completed"
    assert result.current_switched is True
    merged_kcat = pd.read_csv(paths.current_merged_root / "merge_kcat_final_v6_enriched.csv")
    merged_km = pd.read_csv(paths.current_merged_root / "merge_km_final_v6_enriched.csv")
    assert len(merged_kcat) == expected_counts.get("kcat", 0)
    assert len(merged_km) == expected_counts.get("km", 0)
    assert merged_kcat["record_id"].str.startswith("frid_").all()
    assert merged_km["measurement_uid"].str.startswith("muid_").all()
    ph_table = pd.read_csv(paths.current_conditions_root / "ph_long_table.csv")
    temperature_table = pd.read_csv(paths.current_conditions_root / "temperature_long_table.csv")
    assert len(ph_table) == len(merged_kcat) + len(merged_km)
    assert len(temperature_table) == len(merged_kcat) + len(merged_km)
    business_dupes = pd.read_csv(paths.release_audit_root("20260727-ext-random") / "business_duplicate_rows.csv")
    leakage_removed = pd.read_csv(paths.release_audit_root("20260727-ext-random") / "test_leakage_removed.csv")
    assert (paths.release_workspace_external_root("20260727-ext-random") / "reports" / "external_source_report.json").exists()
    assert (paths.release_workspace_external_root("20260727-ext-random") / "reports" / "parameter_counts.csv").exists()
    assert len(business_dupes) == 1
    assert len(leakage_removed) == 1
    assert leakage_removed.iloc[0]["matched_test_key"] == blocked_key


def test_run_update_manual_override_randomized_batch_applies_precise_patches() -> None:
    tmp_path = make_test_dir("run-manual-random")
    paths = AppPaths(repo_root=tmp_path / "repo", data_root=tmp_path / "data")
    paths.reference_root.mkdir(parents=True, exist_ok=True)
    _seed_empty_current(paths)

    kcat_rows = [_formal_row("kcat", index, str(10 + index), commentary=f"kcat_{index}") for index in range(1, 4)]
    km_rows = [_formal_row("km", index + 10, str(2 + index), commentary=f"km_{index}", ph="", temperature="") for index in range(1, 3)]
    current_kcat = _write_current_frame(paths.current_master_root / "CataPro_kcat_master_v6_enriched.csv", kcat_rows)
    _write_current_frame(paths.current_merged_root / "merge_kcat_final_v6_enriched.csv", kcat_rows)
    current_km = _write_current_frame(paths.current_master_root / "CataPro_km_master_v6_enriched.csv", km_rows)
    _write_current_frame(paths.current_merged_root / "merge_km_final_v6_enriched.csv", km_rows)
    for file_name in ("DLKcat_kcat_master_v6_enriched.csv", "IntEnzy_kcat_master_v6_enriched.csv", "IntEnzy_km_master_v6_enriched.csv", "SKiD_kcat_master_v6_enriched.csv", "SKiD_km_master_v6_enriched.csv"):
        _empty_formal_frame().to_csv(paths.current_master_root / file_name, index=False)

    target_record_id = current_kcat.iloc[0]["record_id"]
    km_business_target = current_km.iloc[0]

    input_root = tmp_path / "incoming_manual"
    input_root.mkdir(parents=True, exist_ok=True)
    manual_override = pd.DataFrame(
        [
            {
                "operation_id": "op-001",
                "target_table": "conditions",
                "target_scope": "current",
                "match_key_type": "record_id",
                "record_id": target_record_id,
                "field_name": "temperature",
                "old_value_expected": "30",
                "new_value": "37",
                "action": "replace",
                "reason": "manual_review",
                "approved_by": "reviewer_a",
                "approved_at": "2026-07-27T09:00:00+08:00",
            },
            {
                "operation_id": "op-002",
                "target_table": "conditions",
                "target_scope": "current",
                "match_key_type": "business_key",
                "parameter_name": km_business_target["parameter_name"],
                "ec_number": km_business_target["ec_number"],
                "uniprot": km_business_target["uniprot"],
                "enzyme_type": km_business_target["enzyme_type"],
                "mutation": km_business_target["mutation"],
                "sequence": km_business_target["sequence"],
                "substrate": km_business_target["substrate"],
                "smiles": km_business_target["smiles"],
                "field_name": "ph",
                "old_value_expected": "",
                "new_value": "7.4",
                "action": "fill_if_blank",
                "reason": "fill_blank_ph",
                "approved_by": "reviewer_b",
                "approved_at": "2026-07-27T09:05:00+08:00",
            },
            {
                "operation_id": "op-003",
                "target_table": "merged",
                "target_scope": "current",
                "match_key_type": "business_key",
                "parameter_name": km_business_target["parameter_name"],
                "ec_number": km_business_target["ec_number"],
                "uniprot": km_business_target["uniprot"],
                "enzyme_type": km_business_target["enzyme_type"],
                "mutation": km_business_target["mutation"],
                "sequence": km_business_target["sequence"],
                "substrate": km_business_target["substrate"],
                "smiles": km_business_target["smiles"],
                "field_name": "commentary",
                "old_value_expected": "",
                "new_value": "manual_override_note",
                "action": "replace",
                "reason": "update_commentary",
                "approved_by": "reviewer_c",
                "approved_at": "2026-07-27T09:10:00+08:00",
            },
        ]
    )
    manual_override.to_csv(input_root / "manual_override.csv", index=False)

    result = run_update(
        paths,
        RunConfig(
            release_id="20260727-manual-random",
            source_type=SourceType.MANUAL_OVERRIDE,
            input_path=input_root,
            write_standardized=True,
            write_release_artifacts=True,
        ),
    )

    assert result.status == "completed"
    assert result.current_switched is True
    merged_kcat = pd.read_csv(paths.current_merged_root / "merge_kcat_final_v6_enriched.csv")
    merged_km = pd.read_csv(paths.current_merged_root / "merge_km_final_v6_enriched.csv")
    patched_kcat = merged_kcat.loc[merged_kcat["source_record_id"] == current_kcat.iloc[0]["source_record_id"]].iloc[0]
    assert str(patched_kcat["temperature"]) == "37"
    assert str(patched_kcat["record_id"]).startswith("frid_")
    assert str(patched_kcat["record_id"]) != target_record_id
    matched_km = merged_km.loc[merged_km["ec_number"] == km_business_target["ec_number"]].iloc[0]
    assert str(matched_km["ph"]) == "7.4"
    assert str(matched_km["commentary"]) == "manual_override_note"
    applied = pd.read_csv(paths.release_audit_root("20260727-manual-random") / "override_applied.csv")
    conflicts = pd.read_csv(paths.release_audit_root("20260727-manual-random") / "override_conflicts.csv")
    assert (paths.release_workspace_manual_root("20260727-manual-random") / "matched_targets" / "matched_targets.csv").exists()
    assert (paths.release_workspace_manual_root("20260727-manual-random") / "applied_changes" / "applied_changes.csv").exists()
    assert (paths.release_workspace_manual_root("20260727-manual-random") / "reports" / "manual_override_report.json").exists()
    assert len(applied) == 3
    assert conflicts.empty


def test_run_update_raw_source_randomized_black_box_outputs_switch_current(monkeypatch) -> None:
    rng = random.Random(20260727)
    tmp_path = make_test_dir("run-raw-random")
    paths = AppPaths(repo_root=tmp_path / "repo", data_root=tmp_path / "data")
    paths.reference_root.mkdir(parents=True, exist_ok=True)
    _seed_empty_current(paths)

    input_root = tmp_path / "incoming_raw"
    input_root.mkdir(parents=True, exist_ok=True)
    (input_root / "brenda_update.json").write_text('{"records": []}', encoding="utf-8")

    def fake_run_legacy_pipeline(fake_paths: AppPaths, release_id: str, input_path) -> LegacyPipelineResult:
        kcat_rows = [ _formal_row("kcat", index, str(20 + rng.randint(1, 10)), source_db="raw_source", source_release=release_id) for index in range(1, 4) ]
        km_rows = [ _formal_row("km", index + 20, str(3 + rng.randint(1, 5)), source_db="raw_source", source_release=release_id) for index in range(1, 3) ]
        kcat_frame = ensure_formal_identities(pd.DataFrame(kcat_rows, columns=FORMAL_ENRICHED_COLUMNS))
        km_frame = ensure_formal_identities(pd.DataFrame(km_rows, columns=FORMAL_ENRICHED_COLUMNS))
        for key, file_name in MASTER_OUTPUT_FILES.items():
            if key == "catapro_kcat":
                kcat_frame.to_csv(fake_paths.release_output_master_root(release_id) / file_name, index=False)
            elif key == "catapro_km":
                km_frame.to_csv(fake_paths.release_output_master_root(release_id) / file_name, index=False)
            else:
                _empty_formal_frame().to_csv(fake_paths.release_output_master_root(release_id) / file_name, index=False)
        kcat_frame.to_csv(fake_paths.release_output_merged_root(release_id) / MERGED_OUTPUT_FILES["kcat"], index=False)
        km_frame.to_csv(fake_paths.release_output_merged_root(release_id) / MERGED_OUTPUT_FILES["km"], index=False)
        write_summary_bundle(fake_paths.release_output_summary_root(release_id), build_summary_bundle(kcat_frame, km_frame))
        log_path = fake_paths.release_log_root(release_id) / "raw_source" / "fake_legacy.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        return LegacyPipelineResult(staged_inputs=tuple(), scripts=(LegacyScriptResult(script_path=log_path, return_code=0, log_path=log_path),))

    monkeypatch.setattr(runner, "run_legacy_pipeline", fake_run_legacy_pipeline)

    result = run_update(
        paths,
        RunConfig(
            release_id="20260727-raw-random",
            source_type=SourceType.RAW_SOURCE,
            input_path=input_root,
            write_standardized=True,
            write_release_artifacts=True,
        ),
    )

    assert result.status == "completed"
    assert result.current_switched is True
    assert (paths.current_merged_root / "merge_kcat_final_v6_enriched.csv").exists()
    assert (paths.current_merged_root / "merge_km_final_v6_enriched.csv").exists()
    assert (paths.current_conditions_root / "ph_long_table.csv").exists()
    assert (paths.current_conditions_root / "temperature_long_table.csv").exists()
    raw_manifest = json.loads((paths.release_manifest_root("20260727-raw-random") / "release_manifest.json").read_text(encoding="utf-8"))
    assert raw_manifest["pipeline_mode"] == "legacy_black_box"


def test_validate_command_writes_plan_and_validate_artifacts() -> None:
    tmp_path = make_test_dir("validate-cli")
    paths = AppPaths(repo_root=tmp_path / "repo", data_root=tmp_path / "data")
    paths.repo_root.mkdir(parents=True, exist_ok=True)

    input_root = tmp_path / "incoming_validate"
    input_root.mkdir(parents=True, exist_ok=True)
    (input_root / "external_update.csv").write_text(
        "\n".join(
            [
                "parameter_name,ec_number,uniprot,enzyme_type,mutation,sequence,substrate,smiles,value,unit,organism,commentary,source_record_id",
                "kcat,1.1.1.1,P12345,wildtype,,,glucose,C(C1C(C(C(C(O1)O)O)O)O)O,37,s^-1,Escherichia coli,external add,ext-validate-001",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = cli_main(
        [
            "validate",
            "--data-root",
            str(paths.data_root),
            "--repo-root",
            str(paths.repo_root),
            "--source-type",
            "external_source",
            "--input-path",
            str(input_root),
            "--release-id",
            "20260727-ext002",
        ]
    )

    assert exit_code == 0
    manifest_root = paths.release_manifest_root("20260727-ext002")
    assert (manifest_root / "plan_preview.json").exists()
    assert (manifest_root / "validate_report.json").exists()
    validate_payload = json.loads((manifest_root / "validate_report.json").read_text(encoding="utf-8"))
    assert validate_payload["source_type"] == "external_source"
