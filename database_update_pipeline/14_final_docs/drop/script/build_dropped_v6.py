#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"
DROPPED_ROOT = OUTPUT_ROOT / "dropped"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_row_id(row: dict[str, str]) -> str:
    return row.get("record_id") or row.get("measurement_uid") or row.get("source_record_id") or ""


def export_raw_qc_drops() -> list[dict[str, object]]:
    tasks = [
        (
            "brenda_raw_qc_v6_dropped.csv",
            INPUT_ROOT / "brenda_raw_mutseq_v1.csv",
            INPUT_ROOT / "brenda_raw_qc_v1.csv",
        ),
        (
            "sabio_tsv_raw_qc_v6_dropped.csv",
            INPUT_ROOT / "sabio_tsv_raw_subres_v1.csv",
            INPUT_ROOT / "sabio_tsv_raw_qc_v1.csv",
        ),
    ]

    summary_rows: list[dict[str, object]] = []
    for output_name, input_path, kept_path in tasks:
        fieldnames, input_rows = read_rows(input_path)
        _, kept_rows = read_rows(kept_path)
        kept_ids = {get_row_id(row) for row in kept_rows}
        dropped_rows: list[dict[str, object]] = []
        reason_counter = Counter()

        for row in input_rows:
            if get_row_id(row) in kept_ids:
                continue
            if not (row.get("kinetic_value_num", "") or "").strip():
                reason = "missing_kinetic_value_num"
            elif not (row.get("uniprot", "") or "").strip():
                reason = "missing_uniprot"
            elif not (row.get("smiles", "") or "").strip():
                reason = "missing_smiles"
            else:
                reason = "filtered_out"
            new_row = dict(row)
            new_row["drop_reason"] = reason
            dropped_rows.append(new_row)
            reason_counter[reason] += 1

        out_path = DROPPED_ROOT / "raw_qc" / output_name
        write_rows(out_path, fieldnames + ["drop_reason"], dropped_rows)

        summary_rows.append(
            {
                "stage": "raw_qc",
                "file_name": output_name,
                "rows_total": len(dropped_rows),
                "drop_reasons": "; ".join(f"{k}:{v}" for k, v in sorted(reason_counter.items())),
            }
        )
    return summary_rows


SOURCE_PRIORITY = {
    "CataPro": 0,
    "SKiD": 1,
    "DLKcat": 2,
    "BRENDA": 3,
    "SABIO-RK": 4,
}


def duplicate_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("uniprot", ""),
        row.get("enzyme_type", ""),
        row.get("mutation", ""),
        row.get("sequence", ""),
        row.get("substrate", ""),
        row.get("smiles", ""),
        row.get("parameter_name", ""),
        row.get("value_normalized", "") or row.get("value", ""),
        row.get("ph", ""),
        row.get("temperature", ""),
        row.get("organism", ""),
        row.get("ions", ""),
    )


def business_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        row.get("uniprot", ""),
        row.get("enzyme_type", ""),
        row.get("mutation", ""),
        row.get("sequence", ""),
        row.get("substrate", ""),
        row.get("smiles", ""),
    )


def sort_key(row: dict[str, str]) -> tuple[object, ...]:
    return (
        SOURCE_PRIORITY.get(row.get("source_db", ""), 999),
        row.get("source_record_id", ""),
        row.get("record_id", ""),
    )


def export_final_dedup_drops() -> list[dict[str, object]]:
    tasks = [
        (
            "merge_kcat_final_v6_dropped.csv",
            INPUT_ROOT / "merge_kcat_v2.csv",
            INPUT_ROOT / "IntEnzy_kcat_master_v1.csv",
        ),
        (
            "merge_km_final_v6_dropped.csv",
            INPUT_ROOT / "merge_km_v2.csv",
            INPUT_ROOT / "IntEnzy_km_master_v1.csv",
        ),
    ]

    summary_rows: list[dict[str, object]] = []
    for output_name, merged_path, test_path in tasks:
        fieldnames, merged_rows = read_rows(merged_path)
        _, test_rows = read_rows(test_path)
        test_keys = {business_key(row) for row in test_rows}

        grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
        for row in merged_rows:
            grouped[duplicate_key(row)].append(row)

        dropped_rows: list[dict[str, object]] = []
        reason_counter = Counter()

        for key, group in grouped.items():
            group = sorted(group, key=sort_key)
            kept = group[0]
            for row in group[1:]:
                new_row = dict(row)
                new_row["drop_reason"] = "duplicate_training_key"
                new_row["drop_stage_detail"] = "dedup_within_training"
                dropped_rows.append(new_row)
                reason_counter[new_row["drop_reason"]] += 1

            if business_key(kept) in test_keys:
                new_row = dict(kept)
                new_row["drop_reason"] = "overlap_with_IntEnzy_test"
                new_row["drop_stage_detail"] = "test_leakage_filter"
                dropped_rows.append(new_row)
                reason_counter[new_row["drop_reason"]] += 1

        out_path = DROPPED_ROOT / "final_dedup" / output_name
        write_rows(out_path, fieldnames + ["drop_reason", "drop_stage_detail"], dropped_rows)

        summary_rows.append(
            {
                "stage": "final_dedup",
                "file_name": output_name,
                "rows_total": len(dropped_rows),
                "drop_reasons": "; ".join(f"{k}:{v}" for k, v in sorted(reason_counter.items())),
            }
        )
    return summary_rows


def export_inventory_and_summary(all_summary_rows: list[dict[str, object]]) -> None:
    inventory_rows: list[dict[str, object]] = []
    reason_rows: list[dict[str, object]] = []
    for stage_dir in ["raw_qc", "final_dedup"]:
        for path in sorted((DROPPED_ROOT / stage_dir).glob("*.csv")):
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            total = len(rows)
            reason_counter = Counter((row.get("drop_reason", "") or "").strip() for row in rows)
            inventory_rows.append(
                {
                    "stage": stage_dir,
                    "file_name": path.name,
                    "file_path": str(path.relative_to(STEP_ROOT)),
                    "rows_total": total,
                    "reason_kinds": len([k for k in reason_counter if k]),
                }
            )
            for reason, count in sorted(reason_counter.items()):
                reason_rows.append(
                    {
                        "stage": stage_dir,
                        "file_name": path.name,
                        "drop_reason": reason,
                        "rows": count,
                    }
                )

    write_rows(OUTPUT_ROOT / "drop_file_inventory_v6.csv", ["stage", "file_name", "file_path", "rows_total", "reason_kinds"], inventory_rows)
    write_rows(OUTPUT_ROOT / "drop_summary_v6.csv", ["stage", "file_name", "drop_reason", "rows"], reason_rows)
    write_rows(OUTPUT_ROOT / "drop_build_manifest_v6.csv", ["stage", "file_name", "rows_total", "drop_reasons"], all_summary_rows)


def main() -> None:
    ensure_dir(OUTPUT_ROOT)
    summary_rows = []
    summary_rows.extend(export_raw_qc_drops())
    summary_rows.extend(export_final_dedup_drops())
    export_inventory_and_summary(summary_rows)
    print(str(OUTPUT_ROOT))


if __name__ == "__main__":
    main()
