#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"
CONDITIONS_ROOT = OUTPUT_ROOT / "conditions"
AUDIT_ROOT = OUTPUT_ROOT / "audit"

KCAT_PATH = INPUT_ROOT / "merge_kcat_final_v6_enriched.csv"
KM_PATH = INPUT_ROOT / "merge_km_final_v6_enriched.csv"

PAIR_FIELDS = [
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "substrate",
    "smiles",
    "ph",
    "temperature",
]

GROUP_FIELDS = [
    "dataset_name",
    "source_db",
    *PAIR_FIELDS,
]

DETAIL_FIELDS = [
    "dataset_name",
    "source_db",
    "source_release",
    "source_record_id",
    "record_id",
    "measurement_uid",
    "parameter_name",
    "organism",
    "substrate",
    "substrate_raw",
    "value",
    "unit",
    "value_normalized",
    "unit_normalized",
    "sequence_source",
    "parse_status",
    "mutation_apply_status",
    "WT_sequence",
    "MUT_sequence",
    "kcat_km_source_value",
    "kcat_km_source_unit",
    "kcat_km_computed_value",
    "kcat_km_computed_unit",
    "commentary",
    "reaction_raw",
    "ions",
]


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


def build_group_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(norm(row.get(field)) for field in PAIR_FIELDS)


def collect_scope_value(rows: list[dict[str, str]], field: str) -> str:
    values = sorted({norm(row.get(field)) for row in rows if norm(row.get(field))})
    return "|".join(values)


def split_scope_value(value: object) -> list[str]:
    return [token for token in norm(value).split("|") if token]


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda r: (
            norm(r.get("source_record_id")),
            norm(r.get("record_id")),
            norm(r.get("measurement_uid")),
            norm(r.get("value")),
        ),
    )


def prefixed_block(row: dict[str, str] | None, prefix: str) -> dict[str, str]:
    if not row:
        return {f"{prefix}_{field}": "" for field in DETAIL_FIELDS}
    return {f"{prefix}_{field}": norm(row.get(field)) for field in DETAIL_FIELDS}


def collapse_block(rows: list[dict[str, str]], prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not rows:
        for field in DETAIL_FIELDS:
            out[f"{prefix}_{field}"] = ""
        return out
    for field in DETAIL_FIELDS:
        vals = [norm(r.get(field)) for r in rows if norm(r.get(field))]
        out[f"{prefix}_{field}"] = "|".join(vals)
    return out


def source_safe_name(source_db: str) -> str:
    return source_db.lower().replace("/", "_").replace(" ", "_")


def build_grouped(kcat_rows: list[dict[str, str]], km_rows: list[dict[str, str]]) -> None:
    output_root = CONDITIONS_ROOT / "grouped_outerjoin"
    out_path = output_root / "kcat_km_conditions_grouped_v6.csv"
    audit_path = AUDIT_ROOT / "kcat_km_conditions_grouped_audit_v6.csv"
    summary_path = AUDIT_ROOT / "kcat_km_conditions_grouped_summary_v6.csv"

    kcat_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    km_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in kcat_rows:
        kcat_groups[build_group_key(row)].append(row)
    for row in km_rows:
        km_groups[build_group_key(row)].append(row)

    out_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    all_keys = sorted(set(kcat_groups) | set(km_groups))

    out_fields = [
        "condition_group_id",
        "group_pair_index",
        "pair_status",
        *GROUP_FIELDS,
        "kcat_group_size",
        "km_group_size",
        *[f"kcat_{field}" for field in DETAIL_FIELDS],
        *[f"km_{field}" for field in DETAIL_FIELDS],
    ]

    for idx, key in enumerate(all_keys, start=1):
        k_group = sort_rows(kcat_groups.get(key, []))
        m_group = sort_rows(km_groups.get(key, []))
        scope_rows = k_group + m_group
        dataset_name = collect_scope_value(scope_rows, "dataset_name")
        source_db = collect_scope_value(scope_rows, "source_db")
        k_n = len(k_group)
        m_n = len(m_group)
        max_n = max(k_n, m_n)
        if k_n and m_n:
            group_status = "paired_equal" if k_n == m_n else "paired_uneven"
        elif k_n:
            group_status = "kcat_only"
        else:
            group_status = "km_only"

        audit_rows.append(
            {
                "condition_group_id": f"cond_group_{idx}",
                "group_status": group_status,
                "kcat_group_size": k_n,
                "km_group_size": m_n,
                "dataset_name": dataset_name,
                "source_db": source_db,
                **{field: value for field, value in zip(PAIR_FIELDS, key)},
            }
        )

        for pair_index in range(max_n):
            k_row = k_group[pair_index] if pair_index < k_n else None
            m_row = m_group[pair_index] if pair_index < m_n else None
            if k_row and m_row:
                pair_status = "paired"
            elif k_row:
                pair_status = "kcat_only"
            else:
                pair_status = "km_only"
            out_row: dict[str, object] = {
                "condition_group_id": f"cond_group_{idx}",
                "group_pair_index": pair_index + 1,
                "pair_status": pair_status,
                "kcat_group_size": k_n,
                "km_group_size": m_n,
                "dataset_name": dataset_name,
                "source_db": source_db,
            }
            for field, value in zip(PAIR_FIELDS, key):
                out_row[field] = value
            out_row.update(prefixed_block(k_row, "kcat"))
            out_row.update(prefixed_block(m_row, "km"))
            out_rows.append(out_row)

    write_rows(out_path, out_fields, out_rows)
    source_values = sorted({token for row in out_rows for token in split_scope_value(row.get("source_db"))})
    for source_db in source_values:
        rows = [r for r in out_rows if source_db in split_scope_value(r.get("source_db"))]
        write_rows(output_root / f"kcat_km_conditions_grouped_v6__{source_safe_name(source_db)}.csv", out_fields, rows)

    audit_fields = ["condition_group_id", "group_status", "kcat_group_size", "km_group_size", *GROUP_FIELDS]
    write_rows(audit_path, audit_fields, audit_rows)

    summary_rows = [{"metric": "output_rows", "rows": len(out_rows)}]
    summary_rows.extend({"metric": f"group_status:{k}", "rows": v} for k, v in sorted(Counter(r["group_status"] for r in audit_rows).items()))
    summary_rows.extend({"metric": f"pair_status:{k}", "rows": v} for k, v in sorted(Counter(r["pair_status"] for r in out_rows).items()))
    write_rows(summary_path, ["metric", "rows"], summary_rows)


def build_collapsed(kcat_rows: list[dict[str, str]], km_rows: list[dict[str, str]]) -> None:
    output_root = CONDITIONS_ROOT / "collapsed_multivalue"
    out_path = output_root / "kcat_km_conditions_collapsed_v6.csv"
    audit_path = AUDIT_ROOT / "kcat_km_conditions_collapsed_audit_v6.csv"
    summary_path = AUDIT_ROOT / "kcat_km_conditions_collapsed_summary_v6.csv"

    kcat_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    km_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in kcat_rows:
        kcat_groups[build_group_key(row)].append(row)
    for row in km_rows:
        km_groups[build_group_key(row)].append(row)

    out_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    all_keys = sorted(set(kcat_groups) | set(km_groups))

    out_fields = [
        "condition_group_id",
        "pair_status",
        *GROUP_FIELDS,
        "kcat_group_size",
        "km_group_size",
        *[f"kcat_{field}" for field in DETAIL_FIELDS],
        *[f"km_{field}" for field in DETAIL_FIELDS],
    ]

    for idx, key in enumerate(all_keys, start=1):
        k_group = sort_rows(kcat_groups.get(key, []))
        m_group = sort_rows(km_groups.get(key, []))
        scope_rows = k_group + m_group
        dataset_name = collect_scope_value(scope_rows, "dataset_name")
        source_db = collect_scope_value(scope_rows, "source_db")
        k_n = len(k_group)
        m_n = len(m_group)
        if k_n and m_n:
            pair_status = "paired"
        elif k_n:
            pair_status = "kcat_only"
        else:
            pair_status = "km_only"

        row: dict[str, object] = {
            "condition_group_id": f"cond_group_collapsed_{idx}",
            "pair_status": pair_status,
            "kcat_group_size": k_n,
            "km_group_size": m_n,
            "dataset_name": dataset_name,
            "source_db": source_db,
        }
        for field, value in zip(PAIR_FIELDS, key):
            row[field] = value
        row.update(collapse_block(k_group, "kcat"))
        row.update(collapse_block(m_group, "km"))
        out_rows.append(row)

        audit_rows.append(
            {
                "condition_group_id": row["condition_group_id"],
                "pair_status": pair_status,
                "kcat_group_size": k_n,
                "km_group_size": m_n,
                "dataset_name": dataset_name,
                "source_db": source_db,
                **{field: value for field, value in zip(PAIR_FIELDS, key)},
            }
        )

    write_rows(out_path, out_fields, out_rows)
    source_values = sorted({token for row in out_rows for token in split_scope_value(row.get("source_db"))})
    for source_db in source_values:
        rows = [r for r in out_rows if source_db in split_scope_value(r.get("source_db"))]
        write_rows(output_root / f"kcat_km_conditions_collapsed_v6__{source_safe_name(source_db)}.csv", out_fields, rows)

    audit_fields = ["condition_group_id", "pair_status", "kcat_group_size", "km_group_size", *GROUP_FIELDS]
    write_rows(audit_path, audit_fields, audit_rows)

    summary_rows = [{"metric": "output_rows", "rows": len(out_rows)}]
    summary_rows.extend({"metric": f"pair_status:{k}", "rows": v} for k, v in sorted(Counter(r["pair_status"] for r in out_rows).items()))
    write_rows(summary_path, ["metric", "rows"], summary_rows)


def build_cartesian(kcat_rows: list[dict[str, str]], km_rows: list[dict[str, str]]) -> None:
    output_root = CONDITIONS_ROOT / "cartesian"
    out_path = output_root / "kcat_km_conditions_cartesian_v6.csv"
    audit_path = AUDIT_ROOT / "kcat_km_conditions_cartesian_audit_v6.csv"
    summary_path = AUDIT_ROOT / "kcat_km_conditions_cartesian_summary_v6.csv"

    kcat_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    km_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in kcat_rows:
        kcat_groups[build_group_key(row)].append(row)
    for row in km_rows:
        km_groups[build_group_key(row)].append(row)

    out_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    all_keys = sorted(set(kcat_groups) | set(km_groups))

    out_fields = [
        "condition_group_id",
        "group_pair_index",
        "pair_status",
        *GROUP_FIELDS,
        "kcat_group_size",
        "km_group_size",
        "cartesian_size",
        *[f"kcat_{field}" for field in DETAIL_FIELDS],
        *[f"km_{field}" for field in DETAIL_FIELDS],
    ]

    for idx, key in enumerate(all_keys, start=1):
        k_group = sort_rows(kcat_groups.get(key, []))
        m_group = sort_rows(km_groups.get(key, []))
        scope_rows = k_group + m_group
        dataset_name = collect_scope_value(scope_rows, "dataset_name")
        source_db = collect_scope_value(scope_rows, "source_db")
        k_n = len(k_group)
        m_n = len(m_group)
        if k_n and m_n:
            pair_status = "paired"
            cartesian_size = k_n * m_n
        elif k_n:
            pair_status = "kcat_only"
            cartesian_size = k_n
        else:
            pair_status = "km_only"
            cartesian_size = m_n

        audit_rows.append(
            {
                "condition_group_id": f"cond_group_cartesian_{idx}",
                "pair_status": pair_status,
                "kcat_group_size": k_n,
                "km_group_size": m_n,
                "cartesian_size": cartesian_size,
                "dataset_name": dataset_name,
                "source_db": source_db,
                **{field: value for field, value in zip(PAIR_FIELDS, key)},
            }
        )

        pair_index = 0
        if k_n and m_n:
            for k_row in k_group:
                for m_row in m_group:
                    pair_index += 1
                    out_row: dict[str, object] = {
                        "condition_group_id": f"cond_group_cartesian_{idx}",
                        "group_pair_index": pair_index,
                        "pair_status": "paired",
                        "kcat_group_size": k_n,
                        "km_group_size": m_n,
                        "cartesian_size": cartesian_size,
                        "dataset_name": dataset_name,
                        "source_db": source_db,
                    }
                    for field, value in zip(PAIR_FIELDS, key):
                        out_row[field] = value
                    out_row.update(prefixed_block(k_row, "kcat"))
                    out_row.update(prefixed_block(m_row, "km"))
                    out_rows.append(out_row)
        elif k_n:
            for k_row in k_group:
                pair_index += 1
                out_row = {
                    "condition_group_id": f"cond_group_cartesian_{idx}",
                    "group_pair_index": pair_index,
                    "pair_status": "kcat_only",
                    "kcat_group_size": k_n,
                    "km_group_size": 0,
                    "cartesian_size": cartesian_size,
                    "dataset_name": dataset_name,
                    "source_db": source_db,
                }
                for field, value in zip(PAIR_FIELDS, key):
                    out_row[field] = value
                out_row.update(prefixed_block(k_row, "kcat"))
                out_row.update(prefixed_block(None, "km"))
                out_rows.append(out_row)
        else:
            for m_row in m_group:
                pair_index += 1
                out_row = {
                    "condition_group_id": f"cond_group_cartesian_{idx}",
                    "group_pair_index": pair_index,
                    "pair_status": "km_only",
                    "kcat_group_size": 0,
                    "km_group_size": m_n,
                    "cartesian_size": cartesian_size,
                    "dataset_name": dataset_name,
                    "source_db": source_db,
                }
                for field, value in zip(PAIR_FIELDS, key):
                    out_row[field] = value
                out_row.update(prefixed_block(None, "kcat"))
                out_row.update(prefixed_block(m_row, "km"))
                out_rows.append(out_row)

    write_rows(out_path, out_fields, out_rows)
    source_values = sorted({token for row in out_rows for token in split_scope_value(row.get("source_db"))})
    for source_db in source_values:
        rows = [r for r in out_rows if source_db in split_scope_value(r.get("source_db"))]
        write_rows(output_root / f"kcat_km_conditions_cartesian_v6__{source_safe_name(source_db)}.csv", out_fields, rows)

    audit_fields = ["condition_group_id", "pair_status", "kcat_group_size", "km_group_size", "cartesian_size", *GROUP_FIELDS]
    write_rows(audit_path, audit_fields, audit_rows)

    summary_rows = [{"metric": "output_rows", "rows": len(out_rows)}]
    summary_rows.extend({"metric": f"pair_status:{k}", "rows": v} for k, v in sorted(Counter(r["pair_status"] for r in out_rows).items()))
    summary_rows.append({"metric": "paired_cartesian_rows", "rows": sum(int(r["cartesian_size"]) for r in audit_rows if r["pair_status"] == "paired")})
    write_rows(summary_path, ["metric", "rows"], summary_rows)


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    kcat_rows = read_rows(KCAT_PATH)
    km_rows = read_rows(KM_PATH)
    build_grouped(kcat_rows, km_rows)
    build_collapsed(kcat_rows, km_rows)
    build_cartesian(kcat_rows, km_rows)
    print(str(OUTPUT_ROOT))


if __name__ == "__main__":
    main()
