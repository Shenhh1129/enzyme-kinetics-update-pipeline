from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from catapro_update_app.rules.mapping import normalize_header
from catapro_update_app.rules.registry import SUPPORTED_INPUT_FORMATS


@dataclass(frozen=True)
class InputFileProfile:
    path: Path
    format_name: str
    columns: tuple[str, ...]
    row_count: int | None


def detect_format(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for spec in SUPPORTED_INPUT_FORMATS:
        if suffix in spec.extensions:
            return spec.name
    return None


def discover_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob("*") if path.is_file())


def _load_columns_from_json(path: Path) -> tuple[tuple[str, ...], int | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return tuple(str(key) for key in first.keys()), len(payload)
        return (), len(payload)
    if isinstance(payload, dict):
        return tuple(str(key) for key in payload.keys()), 1
    return (), None


def profile_input_file(path: Path) -> InputFileProfile:
    format_name = detect_format(path)
    if format_name is None:
        raise ValueError(f"Unsupported input format: {path}")

    if format_name == "excel":
        frame = pd.read_excel(path, nrows=5)
        return InputFileProfile(path=path, format_name=format_name, columns=tuple(map(str, frame.columns)), row_count=None)
    if format_name == "csv":
        frame = pd.read_csv(path, nrows=5)
        total = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore")) - 1
        return InputFileProfile(path=path, format_name=format_name, columns=tuple(map(str, frame.columns)), row_count=max(total, 0))
    if format_name == "tsv":
        frame = pd.read_csv(path, sep="\t", nrows=5)
        total = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore")) - 1
        return InputFileProfile(path=path, format_name=format_name, columns=tuple(map(str, frame.columns)), row_count=max(total, 0))

    columns, row_count = _load_columns_from_json(path)
    return InputFileProfile(path=path, format_name=format_name, columns=columns, row_count=row_count)


def normalized_columns(columns: tuple[str, ...]) -> dict[str, str]:
    return {normalize_header(column): column for column in columns}

