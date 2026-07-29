from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARSE_UTILS_PATHS = [
    ROOT / "database_update_pipeline" / "01_new_raw" / "script" / "parse_utils.py",
    ROOT / "database_update_pipeline" / "09_external_master" / "9A_ex_master" / "script" / "parse_utils.py",
]


def _load_parse_utils(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem + "_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_temperature_handles_celsius_variants() -> None:
    for path in PARSE_UTILS_PATHS:
        parse_utils = _load_parse_utils(path)
        assert parse_utils.parse_temperature("pH 8.8, 45°C, mutant enzyme G211S") == ("45°C", "success")
        assert parse_utils.parse_temperature("pH 7.50, 25ºC, 5K mutant") == ("25ºC", "success")
        assert parse_utils.parse_temperature("over the temperature range 30-45 degrees C") == ("30-45 degrees C", "success")
        assert parse_utils.parse_temperature("optimal temperature was 25｡紊") == ("25°C", "success")
        assert parse_utils.parse_temperature("measured at 21-23｡紊") == ("21-23°C", "success")


def test_parse_temperature_rejects_mutation_like_kelvin_tokens() -> None:
    for path in PARSE_UTILS_PATHS:
        parse_utils = _load_parse_utils(path)
        assert parse_utils.parse_temperature("69K enzyme, reduced methyl viologen as electron donor") == ("", "fail")
        assert parse_utils.parse_temperature("recombinant enzyme variant 239K") == ("", "fail")
        assert parse_utils.parse_temperature("pH 7.06, 25°C, 5K mutant") == ("25°C", "success")
