from __future__ import annotations

import pandas as pd

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.pipeline.conditions import append_condition_history
from conftest import make_test_dir


def test_condition_history_append_updates_master_log_and_conflicts() -> None:
    tmp_path = make_test_dir("conditions")
    paths = AppPaths(repo_root=tmp_path / "repo", data_root=tmp_path / "data")

    first_release = pd.DataFrame(
        [
            {
                "record_key": "rk1",
                "enzyme_id": "P1",
                "condition_type": "temperature",
                "value": "37",
                "unit": "C",
                "normalized_value": "37",
                "normalized_unit": "C",
                "condition": "initial",
                "species": "E. coli",
                "wildtype_mutant": "wildtype",
                "source": "external_source",
                "source_file": "batch1.csv",
                "source_row": 1,
                "release_id": "rel-001",
                "quality_flag": "",
            }
        ]
    )
    second_release = pd.DataFrame(
        [
            {
                "record_key": "rk1",
                "enzyme_id": "P1",
                "condition_type": "temperature",
                "value": "40",
                "unit": "C",
                "normalized_value": "40",
                "normalized_unit": "C",
                "condition": "updated",
                "species": "E. coli",
                "wildtype_mutant": "wildtype",
                "source": "external_source",
                "source_file": "batch2.csv",
                "source_row": 1,
                "release_id": "rel-002",
                "quality_flag": "",
            },
            {
                "record_key": "",
                "enzyme_id": "P2",
                "condition_type": "temperature",
                "value": "25",
                "unit": "C",
                "normalized_value": "25",
                "normalized_unit": "C",
                "condition": "",
                "species": "",
                "wildtype_mutant": "",
                "source": "external_source",
                "source_file": "batch2.csv",
                "source_row": 2,
                "release_id": "rel-002",
                "quality_flag": "",
            },
        ]
    )

    first = append_condition_history(paths, "temperature", first_release, "rel-001")
    second = append_condition_history(paths, "temperature", second_release, "rel-002", baseline_frame=first.history_master)

    assert len(first.history_master) == 1
    assert len(second.current_release) == 1
    assert len(second.rejected_rows) == 1
    assert len(second.history_log) == 2
    assert len(second.history_master) == 1
    assert str(second.history_master.iloc[0]["normalized_value"]) == "40"
    assert second.history_master.iloc[0]["append_release_id"] == "rel-002"
    assert not second.conflicts.empty
    assert {"value", "normalized_value", "condition"} <= set(second.conflicts["field_name"])
    assert not (paths.current_conditions_root / "temperature_long_table.csv").exists()
