from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from catapro_update_app.config.defaults import default_data_root, default_repo_root
from catapro_update_app.config.settings import AppPaths, RunConfig
from catapro_update_app.pipeline.runner import build_plan, run_update, write_plan_artifacts, write_validate_artifacts
from catapro_update_app.reports.summary import render_checks, render_condition_history, render_conditions, render_dedup, render_harmonization, render_plan, render_standardized, render_standardized_batch, render_validation
from catapro_update_app.rules.policy import SourceType


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--data-root", type=Path, default=default_data_root())
    shared.add_argument("--repo-root", type=Path, default=default_repo_root())
    shared.add_argument("--input-name", default="default")
    shared.add_argument("--output-name", default="latest")
    shared.add_argument("--release-id", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    shared.add_argument("--input-path", type=Path)
    shared.add_argument("--write-standardized", action="store_true")
    shared.add_argument("--write-release-artifacts", action="store_true")
    shared.add_argument(
        "--source-type",
        choices=[item.value for item in SourceType],
        default=SourceType.EXTERNAL_SOURCE.value,
    )

    parser = argparse.ArgumentParser(prog="catapro-update", parents=[shared])
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", parents=[shared], add_help=False, help="Show the planned pipeline without executing it.")
    subparsers.add_parser("validate", parents=[shared], add_help=False, help="Validate the input and show schema checks.")
    subparsers.add_parser("run", parents=[shared], add_help=False, help="Execute the selected pipeline.")
    return parser


def _build_config(args: argparse.Namespace) -> RunConfig:
    return RunConfig(
        input_name=args.input_name,
        output_name=args.output_name,
        release_id=args.release_id,
        write_standardized=args.write_standardized,
        write_release_artifacts=args.write_release_artifacts,
        strict=False,
        source_type=SourceType(args.source_type),
        input_path=args.input_path,
    )


def _print_plan(plan) -> None:
    print(render_checks(plan.checks))
    print(render_validation(plan.validation))
    print(render_harmonization(plan.harmonization))
    print(render_standardized_batch(plan.standardized_batch))
    print(render_standardized(plan.standardized))
    print(render_dedup(plan.dedup))
    print(render_conditions(plan.conditions))
    print(render_condition_history(plan.condition_history))
    print(render_plan(plan))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "plan"

    paths = AppPaths(repo_root=args.repo_root, data_root=args.data_root)
    config = _build_config(args)

    if command == "run":
        config = RunConfig(
            input_name=config.input_name,
            output_name=config.output_name,
            release_id=config.release_id,
            write_standardized=True,
            write_release_artifacts=True,
            strict=config.strict,
            source_type=config.source_type,
            input_path=config.input_path,
        )
        result = run_update(paths, config)
        print(f"release_id={result.release_id}")
        print(f"status={result.status}")
        print(f"review_status={result.review_status}")
        print(f"current_switched={result.current_switched}")
        print(f"release_root={result.release_root}")
        for note in result.notes:
            print(f"note={note}")
        return 0 if result.status != "failed" else 1

    plan = build_plan(paths, config)
    write_plan_artifacts(paths, config.release_id, plan)
    if command == "validate":
        write_validate_artifacts(paths, config.release_id, config, plan.validation)
    _print_plan(plan)
    print(f"repo_root={paths.repo_root}")
    print(f"data_root={paths.data_root}")
    print(f"input_name={config.input_name}")
    print(f"output_name={config.output_name}")
    print(f"release_id={config.release_id}")
    print(f"source_type={config.source_type.value}")
    print(f"input_path={config.input_path}")
    print(f"write_standardized={config.write_standardized}")
    print(f"write_release_artifacts={config.write_release_artifacts}")
    print(f"plan_preview={paths.release_manifest_root(config.release_id) / 'plan_preview.json'}")
    if command == "validate":
        print(f"validate_report={paths.release_manifest_root(config.release_id) / 'validate_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
