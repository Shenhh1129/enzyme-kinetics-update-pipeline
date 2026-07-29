from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from catapro_update_app.rules.policy import SourceType


@dataclass(frozen=True)
class AppPaths:
    repo_root: Path
    data_root: Path

    @property
    def database_root(self) -> Path:
        return self.data_root / "database"

    @property
    def pipeline_root(self) -> Path:
        return self.repo_root / "database_update_pipeline"

    @property
    def raw_root(self) -> Path:
        return self.database_root / "original"

    @property
    def reference_root(self) -> Path:
        return self.database_root / "reference"

    @property
    def current_root(self) -> Path:
        return self.database_root / "current"

    @property
    def history_root(self) -> Path:
        return self.database_root / "history"

    @property
    def current_master_root(self) -> Path:
        return self.current_root / "master"

    @property
    def current_merged_root(self) -> Path:
        return self.current_root / "merged"

    @property
    def current_summary_root(self) -> Path:
        return self.current_root / "summary"

    @property
    def current_conditions_root(self) -> Path:
        return self.current_root / "conditions"

    @property
    def incoming_root(self) -> Path:
        return self.data_root / "incoming"

    @property
    def master_root(self) -> Path:
        return self.current_master_root

    @property
    def merged_root(self) -> Path:
        return self.current_merged_root

    @property
    def summary_root(self) -> Path:
        return self.current_summary_root

    @property
    def conditions_root(self) -> Path:
        return self.current_conditions_root

    def release_root(self, release_id: str) -> Path:
        return self.data_root / "releases" / release_id

    def release_manifest_root(self, release_id: str) -> Path:
        return self.release_root(release_id) / "manifest"

    def release_output_root(self, release_id: str) -> Path:
        return self.release_root(release_id) / "outputs"

    def release_output_master_root(self, release_id: str) -> Path:
        return self.release_output_root(release_id) / "master"

    def release_output_merged_root(self, release_id: str) -> Path:
        return self.release_output_root(release_id) / "merged"

    def release_output_summary_root(self, release_id: str) -> Path:
        return self.release_output_root(release_id) / "summary"

    def release_output_conditions_root(self, release_id: str) -> Path:
        return self.release_output_root(release_id) / "conditions"

    def release_intermediate_root(self, release_id: str) -> Path:
        return self.release_workspace_external_root(release_id)

    def release_audit_root(self, release_id: str) -> Path:
        return self.release_root(release_id) / "audits"

    def release_log_root(self, release_id: str) -> Path:
        return self.release_root(release_id) / "logs"

    def release_merged_root(self, release_id: str) -> Path:
        return self.release_output_merged_root(release_id)

    def release_summary_root(self, release_id: str) -> Path:
        return self.release_output_summary_root(release_id)

    @property
    def condition_history_root(self) -> Path:
        return self.history_root / "history_logs" / "conditions"

    @property
    def history_logs_master_root(self) -> Path:
        return self.history_root / "history_logs" / "master"

    @property
    def history_logs_merged_root(self) -> Path:
        return self.history_root / "history_logs" / "merged"

    @property
    def history_audit_root(self) -> Path:
        return self.history_root / "audits"

    def snapshot_root(self, release_id: str) -> Path:
        return self.history_root / "snapshots" / f"{release_id}-before"

    def release_workspace_root(self, release_id: str) -> Path:
        return self.release_root(release_id) / "workspace"

    def release_workspace_raw_root(self, release_id: str) -> Path:
        return self.release_workspace_root(release_id) / "raw_source"

    def release_workspace_external_root(self, release_id: str) -> Path:
        return self.release_workspace_root(release_id) / "external_source"

    def release_workspace_manual_root(self, release_id: str) -> Path:
        return self.release_workspace_root(release_id) / "manual_override"

    def incoming_source_root(self, batch_id: str, source_type: SourceType) -> Path:
        if source_type == SourceType.RAW_SOURCE:
            return self.incoming_root / batch_id / "raw"
        if source_type == SourceType.MANUAL_OVERRIDE:
            return self.incoming_root / batch_id / "manual_override"
        return self.incoming_root / batch_id / "external"


@dataclass(frozen=True)
class RunConfig:
    input_name: str = "default"
    output_name: str = "latest"
    dry_run: bool = True
    strict: bool = False
    source_type: SourceType = SourceType.EXTERNAL_SOURCE
    input_path: Path | None = None
    release_id: str = "draft"
    write_standardized: bool = False
    write_release_artifacts: bool = False
