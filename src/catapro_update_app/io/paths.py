from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathCheck:
    path: Path
    exists: bool
    kind: str


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def describe_path(path: Path) -> PathCheck:
    if path.is_dir():
        kind = "dir"
    elif path.is_file():
        kind = "file"
    else:
        kind = "missing"
    return PathCheck(path=path, exists=path.exists(), kind=kind)
