from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceType(str, Enum):
    RAW_SOURCE = "raw_source"
    EXTERNAL_SOURCE = "external_source"
    MANUAL_OVERRIDE = "manual_override"


class UpdateMode(str, Enum):
    FULL_REBUILD = "full_rebuild"
    INCREMENTAL_APPEND = "incremental_append"
    OVERRIDE_ONLY = "override_only"


class ConflictPolicy(str, Enum):
    RAW_FIRST = "raw_source > curated_external > manual_override"


@dataclass(frozen=True)
class RulePolicy:
    source_type: SourceType
    update_mode: UpdateMode
    conflict_policy: ConflictPolicy = ConflictPolicy.RAW_FIRST
    preserve_nulls: bool = True
    normalize_units: bool = True
    keep_raw_units: bool = True
    emit_audit_traces: bool = True

