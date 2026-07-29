from __future__ import annotations

import csv
import json
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StandardizedArtifactManifest:
    release_id: str
    source_type: str
    input_path: str
    output_path: str
    row_count: int
    column_count: int
    missing_required: tuple[str, ...]


@dataclass(frozen=True)
class BatchReleaseManifest:
    release_id: str
    source_type: str
    input_root: str
    standardized_files: tuple[str, ...]
    merged_output: str | None
    dedup_output: str | None
    audit_output: str | None
    row_count: int
    dedup_row_count: int
    duplicate_row_count: int


@dataclass(frozen=True)
class ConditionExportManifest:
    release_id: str
    condition_name: str
    source_type: str
    input_path: str
    output_path: str
    row_count: int
    column_count: int


def write_manifest(path: Path, manifest: StandardizedArtifactManifest | BatchReleaseManifest | ConditionExportManifest | dict[str, object]) -> Path:
    payload = asdict(manifest) if hasattr(manifest, "__dataclass_fields__") else manifest
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def count_columns(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            return len(row)
    return 0


def ensure_header_csv(path: Path, columns: Iterable[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(columns))
    return path


def write_csv_rows(path: Path, columns: Iterable[str], rows: Iterable[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames or []})
    return path
