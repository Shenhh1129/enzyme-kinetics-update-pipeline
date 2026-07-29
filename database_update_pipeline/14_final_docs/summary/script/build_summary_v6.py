#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"
MUTATION_ROOT = OUTPUT_ROOT / "mutation"
EMPTY_ROOT = OUTPUT_ROOT / "ph_tem_empty"
UNIT_ROOT = OUTPUT_ROOT / "unit"

KCAT_PATH = INPUT_ROOT / "merge_kcat_final_v6_enriched.csv"
KM_PATH = INPUT_ROOT / "merge_km_final_v6_enriched.csv"

EXPECTED_UNITS = {
    "kcat": {"s^-1"},
    "km": {"mM", "M"},
    "kcat_km": {"M^-1*s^-1"},
}


def norm(value: object) -> str:
    return str(value or "").strip()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_subsets(rows: list[dict[str, str]], prefix: str) -> dict[str, int]:
    mutation_rows = [row for row in rows if norm(row.get("mutation"))]
    empty_rows = [row for row in rows if not norm(row.get("ph")) and not norm(row.get("temperature"))]

    fieldnames = list(rows[0].keys()) if rows else []
    write_rows(MUTATION_ROOT / f"{prefix}_mutation_rows_v6.csv", fieldnames, mutation_rows)
    write_rows(EMPTY_ROOT / f"{prefix}_ph_temperature_empty_v6.csv", fieldnames, empty_rows)
    return {
        "mutation_rows": len(mutation_rows),
        "ph_temperature_empty_rows": len(empty_rows),
    }


def export_unit_audit(rows: list[dict[str, str]], prefix: str) -> dict[str, int]:
    out_rows: list[dict[str, object]] = []
    missing_unit = 0
    unexpected_unit = 0
    fieldnames = list(rows[0].keys()) if rows else []
    for extra in ["unit_audit_status", "unit_audit_reason"]:
        if extra not in fieldnames:
            fieldnames.append(extra)

    for row in rows:
        parameter = norm(row.get("parameter_name"))
        unit = norm(row.get("unit_normalized") or row.get("unit"))
        expected = EXPECTED_UNITS.get(parameter, set())
        if not unit:
            new_row = dict(row)
            new_row["unit_audit_status"] = "flagged"
            new_row["unit_audit_reason"] = "missing_unit"
            out_rows.append(new_row)
            missing_unit += 1
        elif unit in expected:
            continue
        else:
            new_row = dict(row)
            new_row["unit_audit_status"] = "flagged"
            new_row["unit_audit_reason"] = f"unexpected_unit:{unit}"
            out_rows.append(new_row)
            unexpected_unit += 1

    write_rows(UNIT_ROOT / f"{prefix}_unit_audit_v6.csv", fieldnames, out_rows)
    return {
        "unit_audit_rows": len(out_rows),
        "missing_unit_rows": missing_unit,
        "unexpected_unit_rows": unexpected_unit,
    }


def write_summary(count_rows: list[dict[str, object]]) -> None:
    write_rows(OUTPUT_ROOT / "summary_v6_counts.csv", ["section", "metric", "value"], count_rows)
    lines = ["# CataPro V6 Summary", ""]
    current_section = ""
    for row in count_rows:
        section = str(row["section"])
        metric = str(row["metric"])
        value = str(row["value"])
        if section != current_section:
            if current_section:
                lines.append("")
            lines.append(f"## {section}")
            current_section = section
        lines.append(f"- {metric}: {value}")
    (OUTPUT_ROOT / "summary_v6.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    kcat_rows = read_rows(KCAT_PATH)
    km_rows = read_rows(KM_PATH)

    count_rows: list[dict[str, object]] = []
    count_rows.append({"section": "inputs", "metric": "kcat_final_v6_rows", "value": len(kcat_rows)})
    count_rows.append({"section": "inputs", "metric": "km_final_v6_rows", "value": len(km_rows)})

    for prefix, rows in [("kcat", kcat_rows), ("km", km_rows)]:
        subset_stats = export_subsets(rows, prefix)
        for metric, value in subset_stats.items():
            count_rows.append({"section": f"{prefix}_subsets", "metric": metric, "value": value})
        unit_stats = export_unit_audit(rows, prefix)
        for metric, value in unit_stats.items():
            count_rows.append({"section": f"{prefix}_unit_audit", "metric": metric, "value": value})

    write_summary(count_rows)
    print(str(OUTPUT_ROOT))


if __name__ == "__main__":
    main()
