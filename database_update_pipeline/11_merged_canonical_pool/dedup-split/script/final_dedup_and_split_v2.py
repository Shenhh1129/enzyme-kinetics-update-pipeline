import csv
import hashlib
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


TRAIN_FILES = [
    ("merge_kcat_v2.csv", "IntEnzy_kcat_master_v1.csv", "merge_kcat_final_v2.csv", "IntEnzy_kcat_test_v1.csv"),
    ("merge_km_v2.csv", "IntEnzy_km_master_v1.csv", "merge_km_final_v2.csv", "IntEnzy_km_test_v1.csv"),
]


SOURCE_PRIORITY = {
    "CataPro": 0,
    "SKiD": 1,
    "DLKcat": 2,
    "BRENDA": 3,
    "SABIO-RK": 4,
}

NULL_TOKENS = {"", "na", "n/a", "null", "none", "nan", "-"}


def normalize_text(value):
    text = str(value or "").strip()
    return "" if text.lower() in NULL_TOKENS else text


def normalize_parameter_name(value):
    text = normalize_text(value).lower().replace(" ", "").replace("-", "_").replace("/", "_")
    aliases = {
        "kcat": "kcat",
        "km": "km",
        "kcat_km": "kcat_km",
        "kcatoverkm": "kcat_km",
        "ph": "ph",
        "temperature": "temperature",
        "temp": "temperature",
    }
    return aliases.get(text, text)


def normalize_enzyme_type(value):
    text = normalize_text(value).lower().replace(" ", "_")
    aliases = {
        "wt": "wildtype",
        "wild": "wildtype",
        "wild_type": "wildtype",
        "wildtype": "wildtype",
        "mut": "mutant",
        "mutant": "mutant",
        "variant": "mutant",
        "ambiguous": "ambiguous",
    }
    return aliases.get(text, text)


def normalize_sequence(value):
    return normalize_text(value).replace(" ", "").replace("\n", "").replace("\r", "").upper()


def digest20(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def business_key(row):
    parts = [
        normalize_text(row.get("uniprot", "")),
        normalize_enzyme_type(row.get("enzyme_type", "")),
        normalize_text(row.get("mutation", "")),
        normalize_sequence(row.get("sequence", "")),
        normalize_text(row.get("substrate", "")),
        normalize_text(row.get("smiles", "")),
    ]
    return "|".join(parts)


def measurement_uid(row):
    payload = "|".join(
        [
            normalize_text(row.get("uniprot", "")),
            normalize_enzyme_type(row.get("enzyme_type", "")),
            normalize_text(row.get("mutation", "")),
            normalize_sequence(row.get("sequence", "")),
            normalize_text(row.get("substrate", "")),
            normalize_text(row.get("smiles", "")),
            normalize_parameter_name(row.get("parameter_name", "")),
            normalize_text(row.get("value_normalized", "") or row.get("value", "")),
            normalize_text(row.get("ph", "")),
            normalize_text(row.get("temperature", "")),
        ]
    )
    return f"muid_{digest20(payload)}"


def record_id(row):
    payload = "|".join(
        [
            normalize_text(row.get("measurement_uid", "")),
            normalize_text(row.get("organism", "")),
            normalize_text(row.get("ions", "")),
        ]
    )
    return f"frid_{digest20(payload)}" if payload.strip("|") else ""


def has_auto_match_evidence(row):
    return any(normalize_text(row.get(column, "")) for column in ("uniprot", "sequence", "substrate", "smiles"))


def hydrate_row(row):
    hydrated = dict(row)
    hydrated["parameter_name"] = normalize_parameter_name(hydrated.get("parameter_name", ""))
    hydrated["enzyme_type"] = normalize_enzyme_type(hydrated.get("enzyme_type", ""))
    hydrated["sequence"] = normalize_sequence(hydrated.get("sequence", ""))
    for column in (
        "source_db",
        "source_release",
        "source_record_id",
        "ec_number",
        "organism",
        "uniprot",
        "mutation",
        "substrate",
        "smiles",
        "value",
        "unit",
        "ph",
        "temperature",
        "ions",
        "value_normalized",
        "unit_normalized",
    ):
        if column in hydrated:
            hydrated[column] = normalize_text(hydrated.get(column, ""))
    if not hydrated.get("value_normalized", ""):
        hydrated["value_normalized"] = hydrated.get("value", "")
    if not hydrated.get("unit_normalized", ""):
        hydrated["unit_normalized"] = hydrated.get("unit", "")
    hydrated["business_key"] = business_key(hydrated)
    hydrated["measurement_uid"] = measurement_uid(hydrated)
    hydrated["record_id"] = record_id(hydrated)
    return hydrated


def sort_key(row):
    return (
        SOURCE_PRIORITY.get(row.get("source_db", ""), 999),
        row.get("source_record_id", ""),
        row.get("record_id", ""),
    )


def merged_fieldnames(fieldnames, rows):
    merged = list(fieldnames)
    seen = set(merged)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                merged.append(key)
                seen.add(key)
    return merged


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [hydrate_row(row) for row in reader]
        return merged_fieldnames(reader.fieldnames or [], rows), rows


def write_rows(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_identity(row, fieldnames):
    return tuple(normalize_text(row.get(field, "")) for field in fieldnames)


def dedup_exact_rows(rows, fieldnames):
    seen = set()
    kept = []
    dropped = 0
    for row in rows:
        identity = row_identity(row, fieldnames)
        if identity in seen:
            dropped += 1
            continue
        seen.add(identity)
        kept.append(row)
    return kept, dropped


def dedup_business_rows(rows):
    grouped = {}
    for row in rows:
        if not has_auto_match_evidence(row):
            grouped.setdefault(("insufficient", row.get("record_id", "")), []).append(row)
            continue
        key = (row.get("business_key", ""), row.get("parameter_name", ""), row.get("measurement_uid", ""))
        grouped.setdefault(key, []).append(row)

    kept = []
    dropped = 0
    for key, group in grouped.items():
        if key[0] == "insufficient":
            kept.extend(group)
            continue
        pair_groups = {}
        for row in group:
            pair_key = (normalize_text(row.get("organism", "")), normalize_text(row.get("ions", "")))
            pair_groups.setdefault(pair_key, []).append(row)
        for pair_group in pair_groups.values():
            pair_group = sorted(pair_group, key=sort_key)
            kept.append(pair_group[0])
            dropped += max(0, len(pair_group) - 1)
    kept = sorted(kept, key=sort_key)
    return kept, dropped


def remove_test_overlap(train_rows, test_rows):
    test_keys = {row.get("business_key", "") for row in test_rows if row.get("business_key", "")}
    kept = []
    dropped = 0
    for row in train_rows:
        if row.get("business_key", "") in test_keys:
            dropped += 1
            continue
        kept.append(row)
    return kept, dropped


def main():
    for train_name, test_name, final_train_name, final_test_name in TRAIN_FILES:
        train_fields, train_rows = read_rows(INPUT_ROOT / train_name)
        test_fields, test_rows = read_rows(INPUT_ROOT / test_name)
        exact_deduped_train, exact_dropped = dedup_exact_rows(train_rows, train_fields)
        deduped_train, business_dropped = dedup_business_rows(exact_deduped_train)
        filtered_train, leakage_dropped = remove_test_overlap(deduped_train, test_rows)
        write_rows(OUTPUT_ROOT / final_train_name, train_fields, filtered_train)
        write_rows(OUTPUT_ROOT / final_test_name, test_fields, test_rows)
        print(
            f"{final_train_name}\tinput={len(train_rows)}\texact_drop={exact_dropped}\tbusiness_drop={business_dropped}\tleakage_drop={leakage_dropped}\tfinal={len(filtered_train)}"
        )


if __name__ == "__main__":
    main()
