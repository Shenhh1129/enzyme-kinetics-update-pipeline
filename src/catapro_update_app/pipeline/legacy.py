from __future__ import annotations

import shutil
import subprocess
import sys
import csv
from dataclasses import dataclass
from pathlib import Path
import os

from catapro_update_app.config.settings import AppPaths
from catapro_update_app.io.loaders import discover_input_files
from catapro_update_app.io.paths import ensure_dir
from catapro_update_app.rules.registry import FORMAL_ENRICHED_COLUMNS, MERGED_OUTPUT_FILES


LEGACY_SCRIPT_ORDER: tuple[str, ...] = (
    "database_update_pipeline/01_new_raw/script/rebuild_brenda_raw.py",
    "database_update_pipeline/01_new_raw/script/rebuild_sabio_from_tsv.py",
    "database_update_pipeline/02_enrich+mutation/script/local_enrich.py",
    "database_update_pipeline/02_enrich+mutation/script/mutant_sequence_rebuild.py",
    "database_update_pipeline/03_subres/script/sabio_tsv_substrate_resolve.py",
    "database_update_pipeline/04_QC/script/build_raw_qc.py",
    "database_update_pipeline/05_qc_standardize/script/standardize_raw_qc.py",
    "database_update_pipeline/06_backfill_seq/6A_local_seqfill/script/backfill_sequence_post_standardized.py",
    "database_update_pipeline/06_backfill_seq/6B_UniProt_seq_cache/script/uniprot_sequence_cache_build.py",
    "database_update_pipeline/06_backfill_seq/6C_Uniprot_cache/script/backfill_sequence_with_uniprot_cache.py",
    "database_update_pipeline/07_cata_updata/script/export_catapro_update_v2.py",
    "database_update_pipeline/08_cata_master/script/build_catapro_master_v2.py",
    "database_update_pipeline/09_external_master/9A_ex_master/script/build_external_masters.py",
    "database_update_pipeline/09_external_master/9B_SKID_seqfill/script/backfill_skid_sequence_with_uniprot_cache.py",
    "database_update_pipeline/10_mut_status_repair/script/repair_dlkcat_mutation_status_v2.py",
    "database_update_pipeline/10_mut_status_repair/script/repair_skid_mutation_status_v2.py",
    "database_update_pipeline/11_merged_canonical_pool/candidate_pool/script/build_merged_training_v2.py",
    "database_update_pipeline/11_merged_canonical_pool/dedup-split/script/final_dedup_and_split_v2.py",
    "database_update_pipeline/12_status_fix/script/export_final_enriched_v6_statusfixed_all.py",
    "database_update_pipeline/13_final_data/script/export_masters_merges_enriched_v6.py",
    "database_update_pipeline/14_final_docs/conditions/script/build_conditions_v6.py",
    "database_update_pipeline/14_final_docs/summary/script/build_summary_v6.py",
    "database_update_pipeline/14_final_docs/drop/script/build_dropped_v6.py",
)

LEGACY_REFERENCE_FILENAMES: tuple[str, ...] = (
    "kcat-data_0.4simi-10fold.csv",
    "Km-data_0.4simi-10fold.csv",
    "kcat-over-Km-data_0.4simi-10fold.csv",
    "Kcat_combination_0918_wildtype_mutant.json",
    "Ligands_all_final_v1.csv",
    "db_matched_pairs_pH.csv",
    "kcat_all_data_logscale_final_v1.csv",
    "Km_all_data_logscale_final_v1.csv",
)

LEGACY_REFERENCE_INPUT_DIRS: tuple[str, ...] = (
    "database_update_pipeline/02_enrich+mutation/input",
    "database_update_pipeline/03_subres/input",
    "database_update_pipeline/06_backfill_seq/6A_local_seqfill/input",
    "database_update_pipeline/09_external_master/9A_ex_master/input",
)


@dataclass(frozen=True)
class LegacyScriptResult:
    script_path: Path
    return_code: int
    log_path: Path


@dataclass(frozen=True)
class LegacyPipelineResult:
    staged_inputs: tuple[Path, ...]
    scripts: tuple[LegacyScriptResult, ...]

    @property
    def ok(self) -> bool:
        return all(item.return_code == 0 for item in self.scripts)


def legacy_script_paths(workspace_root: Path) -> tuple[Path, ...]:
    return tuple(workspace_root / rel_path for rel_path in LEGACY_SCRIPT_ORDER)


def _copy_if_needed(source: Path, target: Path) -> None:
    if source.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)


def _managed_source_files(root: Path) -> dict[Path, Path]:
    managed: dict[Path, Path] = {}
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel_path = item.relative_to(root)
        if any(part in {"input", "output", "__pycache__"} for part in rel_path.parts):
            continue
        if item.suffix.lower() == ".pyc":
            continue
        managed[rel_path] = item
    return managed


def _sync_pipeline_source_tree(source_root: Path, target_root: Path) -> None:
    source_files = _managed_source_files(source_root)
    target_files = _managed_source_files(target_root) if target_root.exists() else {}

    for rel_path, source_file in source_files.items():
        _copy_if_needed(source_file, target_root / rel_path)

    for rel_path, target_file in target_files.items():
        if rel_path not in source_files and target_file.exists():
            target_file.unlink()


def _clear_legacy_caches(target_root: Path) -> None:
    for folder in target_root.rglob("__pycache__"):
        if folder.is_dir():
            shutil.rmtree(folder)
    for pyc in target_root.rglob("*.pyc"):
        if pyc.is_file():
            pyc.unlink()


def _clear_legacy_runtime_dirs(target_root: Path) -> None:
    for folder_name in ("input", "output"):
        for folder in target_root.rglob(folder_name):
            if folder.is_dir():
                shutil.rmtree(folder)


def _prepare_legacy_workspace(paths: AppPaths, release_id: str) -> Path:
    workspace_root = ensure_dir(paths.release_workspace_raw_root(release_id))
    source_root = paths.pipeline_root
    target_root = workspace_root / "database_update_pipeline"

    if not target_root.exists():
        shutil.copytree(
            source_root,
            target_root,
            ignore=shutil.ignore_patterns("input", "output", "__pycache__", "*.pyc"),
        )
    else:
        _clear_legacy_runtime_dirs(target_root)
        _sync_pipeline_source_tree(source_root, target_root)

    _clear_legacy_caches(target_root)
    return workspace_root


def seed_legacy_reference_inputs(paths: AppPaths, workspace_root: Path) -> tuple[Path, ...]:
    available_by_name = {
        path.name: path
        for path in paths.raw_root.rglob("*")
        if path.is_file() and path.name in LEGACY_REFERENCE_FILENAMES
    }

    staged: list[Path] = []
    for rel_dir in LEGACY_REFERENCE_INPUT_DIRS:
        input_root = ensure_dir(workspace_root / rel_dir)
        for name, source in available_by_name.items():
            target = input_root / name
            _copy_if_needed(source, target)
            staged.append(target)
    return tuple(staged)


def stage_raw_inputs(paths: AppPaths, workspace_root: Path, input_path: Path | None) -> tuple[Path, ...]:
    raw_root = ensure_dir(paths.raw_root)
    legacy_input_root = ensure_dir(workspace_root / "database_update_pipeline" / "01_new_raw" / "input")
    staged: list[Path] = []

    default_candidates = [path for path in raw_root.iterdir() if path.is_file() and path.suffix.lower() in {".json", ".tsv"}] if raw_root.exists() else []
    override_candidates = []
    if input_path is not None and input_path.exists():
        override_candidates = discover_input_files(input_path) if input_path.is_dir() else [input_path]

    chosen_by_name: dict[str, Path] = {item.name: item for item in default_candidates}
    for item in override_candidates:
        chosen_by_name[item.name] = item

    for item in chosen_by_name.values():
        if item.suffix.lower() not in {".json", ".tsv"}:
            continue
        targets = (raw_root / item.name, legacy_input_root / item.name)
        for target in targets:
            _copy_if_needed(item, target)
        staged.append(targets[-1])
    return tuple(staged)


def sync_outputs_to_downstream(script_paths: tuple[Path, ...], current_index: int) -> None:
    current_step_root = script_paths[current_index].resolve().parents[1]
    output_root = current_step_root / "output"
    if not output_root.exists():
        return

    output_files = [path for path in output_root.iterdir() if path.is_file()]
    if not output_files:
        return

    for downstream_script in script_paths[current_index + 1 :]:
        input_root = ensure_dir(downstream_script.resolve().parents[1] / "input")
        for source in output_files:
            _copy_if_needed(source, input_root / source.name)


def _sync_directory_tree(source_root: Path, target_root: Path) -> None:
    if not source_root.exists():
        return
    for item in source_root.rglob("*"):
        if item.is_file():
            _copy_if_needed(item, target_root / item.relative_to(source_root))


def _rewrite_formal_csv(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("r", encoding="utf-8-sig", newline="") as src, target.open("w", encoding="utf-8-sig", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=list(FORMAL_ENRICHED_COLUMNS))
        writer.writeheader()
        for row in reader:
            writer.writerow({column: row.get(column, "") for column in FORMAL_ENRICHED_COLUMNS})


def _sync_legacy_release_outputs(paths: AppPaths, release_id: str, workspace_root: Path) -> None:
    final_data_root = workspace_root / "database_update_pipeline" / "13_final_data" / "output"
    final_conditions_root = final_data_root / "conditions"
    summary_root = workspace_root / "database_update_pipeline" / "14_final_docs" / "summary" / "output"
    allowed_merged = set(MERGED_OUTPUT_FILES.values())

    master_root = ensure_dir(paths.release_output_master_root(release_id))
    merged_root = ensure_dir(paths.release_output_merged_root(release_id))
    output_summary_root = ensure_dir(paths.release_output_summary_root(release_id))
    output_conditions_root = ensure_dir(paths.release_output_conditions_root(release_id))

    if final_data_root.exists():
        for item in final_data_root.glob("*.csv"):
            if item.name.startswith(("CataPro_", "DLKcat_", "SKiD_", "IntEnzy_")):
                _rewrite_formal_csv(item, master_root / item.name)
            elif item.name in allowed_merged:
                _rewrite_formal_csv(item, merged_root / item.name)

    _sync_directory_tree(final_conditions_root, output_conditions_root)
    _sync_directory_tree(summary_root, output_summary_root)


def run_legacy_pipeline(paths: AppPaths, release_id: str, input_path: Path | None) -> LegacyPipelineResult:
    workspace_root = _prepare_legacy_workspace(paths, release_id)
    staged_inputs = stage_raw_inputs(paths, workspace_root, input_path)
    _ = seed_legacy_reference_inputs(paths, workspace_root)
    log_root = ensure_dir(paths.release_log_root(release_id) / "raw_source")
    script_paths = legacy_script_paths(workspace_root)

    results: list[LegacyScriptResult] = []
    for index, script_path in enumerate(script_paths, start=1):
        script_path_abs = script_path.resolve()
        ensure_dir(script_path_abs.parents[1] / "output")
        log_path = log_root / f"{index:02d}_{script_path.stem}.log"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import csv, runpy, sys; "
                    "csv.field_size_limit(sys.maxsize); "
                    f"sys.path.insert(0, r'{script_path_abs.parent}'); "
                    f"runpy.run_path(r'{script_path_abs}', run_name='__main__')"
                ),
            ],
            cwd=workspace_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        log_path.write_text(completed.stdout, encoding="utf-8")
        results.append(LegacyScriptResult(script_path=script_path, return_code=completed.returncode, log_path=log_path))
        if completed.returncode != 0:
            break
        sync_outputs_to_downstream(script_paths, index - 1)

    if results and all(item.return_code == 0 for item in results):
        _sync_legacy_release_outputs(paths, release_id, workspace_root)

    _clear_legacy_caches(workspace_root / "database_update_pipeline")
    return LegacyPipelineResult(staged_inputs=staged_inputs, scripts=tuple(results))
