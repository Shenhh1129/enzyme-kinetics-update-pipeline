from pathlib import Path


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_data_root() -> Path:
    return default_repo_root() / ".external_data"
