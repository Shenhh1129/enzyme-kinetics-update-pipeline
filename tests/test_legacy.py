from __future__ import annotations

from pathlib import Path

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.pipeline import legacy
from conftest import make_test_dir


def _write_script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_raw_source_legacy_orchestration_stages_inputs_and_syncs_outputs(monkeypatch) -> None:
    tmp_path = make_test_dir("legacy")
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    paths = AppPaths(repo_root=repo_root, data_root=data_root)

    incoming_root = tmp_path / "incoming"
    incoming_root.mkdir(parents=True, exist_ok=True)
    incoming_file = incoming_root / "brenda_update.json"
    incoming_file.write_text('{"records": []}', encoding="utf-8")

    raw_root = paths.raw_root
    raw_root.mkdir(parents=True, exist_ok=True)
    reference_name = "reference.csv"
    (raw_root / reference_name).write_text("id,value\n1,x\n", encoding="utf-8")

    step1 = repo_root / "database_update_pipeline" / "01_new_raw" / "script" / "step1.py"
    step2 = repo_root / "database_update_pipeline" / "02_next_step" / "script" / "step2.py"

    _write_script(
        step1,
        (
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "input_root = root / 'input'\n"
            "assert (input_root / 'brenda_update.json').exists()\n"
            "assert (input_root / 'reference.csv').exists()\n"
            "output_root = root / 'output'\n"
            "output_root.mkdir(parents=True, exist_ok=True)\n"
            "(output_root / 'step1_result.txt').write_text('ok', encoding='utf-8')\n"
        ),
    )
    _write_script(
        step2,
        (
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "input_root = root / 'input'\n"
            "assert (input_root / 'step1_result.txt').exists()\n"
            "assert (input_root / 'reference.csv').exists()\n"
            "output_root = root / 'output'\n"
            "output_root.mkdir(parents=True, exist_ok=True)\n"
            "(output_root / 'step2_result.txt').write_text('done', encoding='utf-8')\n"
        ),
    )

    monkeypatch.setattr(
        legacy,
        "LEGACY_SCRIPT_ORDER",
        (
            "database_update_pipeline/01_new_raw/script/step1.py",
            "database_update_pipeline/02_next_step/script/step2.py",
        ),
    )
    monkeypatch.setattr(legacy, "LEGACY_REFERENCE_FILENAMES", (reference_name,))
    monkeypatch.setattr(
        legacy,
        "LEGACY_REFERENCE_INPUT_DIRS",
        (
            "database_update_pipeline/01_new_raw/input",
            "database_update_pipeline/02_next_step/input",
        ),
    )

    result = legacy.run_legacy_pipeline(paths, "rel-legacy", incoming_file)
    workspace_root = paths.release_workspace_raw_root("rel-legacy") / "database_update_pipeline"

    assert result.ok
    assert len(result.scripts) == 2
    assert (paths.raw_root / "brenda_update.json").exists()
    assert (workspace_root / "01_new_raw" / "input" / "brenda_update.json").exists()
    assert (workspace_root / "02_next_step" / "input" / "step1_result.txt").exists()
    assert (workspace_root / "02_next_step" / "output" / "step2_result.txt").exists()
    assert all(item.log_path.exists() for item in result.scripts)


def test_raw_source_legacy_workspace_is_refreshed_for_same_release_id(monkeypatch) -> None:
    tmp_path = make_test_dir("legacy-refresh")
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    paths = AppPaths(repo_root=repo_root, data_root=data_root)

    incoming_root = tmp_path / "incoming"
    incoming_root.mkdir(parents=True, exist_ok=True)
    incoming_file = incoming_root / "brenda_update.json"
    incoming_file.write_text('{"records": []}', encoding="utf-8")

    raw_root = paths.raw_root
    raw_root.mkdir(parents=True, exist_ok=True)

    step1 = repo_root / "database_update_pipeline" / "01_new_raw" / "script" / "step1.py"
    _write_script(
        step1,
        (
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "output_root = root / 'output'\n"
            "output_root.mkdir(parents=True, exist_ok=True)\n"
            "(output_root / 'version.txt').write_text('v1', encoding='utf-8')\n"
        ),
    )

    monkeypatch.setattr(
        legacy,
        "LEGACY_SCRIPT_ORDER",
        ("database_update_pipeline/01_new_raw/script/step1.py",),
    )
    monkeypatch.setattr(legacy, "LEGACY_REFERENCE_FILENAMES", ())
    monkeypatch.setattr(legacy, "LEGACY_REFERENCE_INPUT_DIRS", ())

    first = legacy.run_legacy_pipeline(paths, "rel-refresh", incoming_file)
    workspace_root = paths.release_workspace_raw_root("rel-refresh") / "database_update_pipeline"
    assert first.ok
    assert (workspace_root / "01_new_raw" / "output" / "version.txt").read_text(encoding="utf-8") == "v1"
    (workspace_root / "01_new_raw" / "output" / "stale.txt").write_text("stale", encoding="utf-8")

    _write_script(
        step1,
        (
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "output_root = root / 'output'\n"
            "output_root.mkdir(parents=True, exist_ok=True)\n"
            "assert not (output_root / 'stale.txt').exists()\n"
            "(output_root / 'version.txt').write_text('v2', encoding='utf-8')\n"
        ),
    )

    second = legacy.run_legacy_pipeline(paths, "rel-refresh", incoming_file)
    assert second.ok
    assert (workspace_root / "01_new_raw" / "script" / "step1.py").read_text(encoding="utf-8").endswith("write_text('v2', encoding='utf-8')\n")
    assert (workspace_root / "01_new_raw" / "output" / "version.txt").read_text(encoding="utf-8") == "v2"
    assert not (workspace_root / "01_new_raw" / "output" / "stale.txt").exists()
