import csv
from collections import defaultdict
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"
CONDITION_OUTPUT_ROOT = OUTPUT_ROOT / "conditions"


MASTER_INPUTS = [
    ("CataPro_kcat_master_v2.csv", "CataPro_kcat_master_v6_enriched.csv"),
    ("CataPro_km_master_v2.csv", "CataPro_km_master_v6_enriched.csv"),
    ("DLKcat_kcat_master_v2.csv", "DLKcat_kcat_master_v6_enriched.csv"),
    ("SKiD_kcat_master_seqfilled_v2.csv", "SKiD_kcat_master_v6_enriched.csv"),
    ("SKiD_km_master_seqfilled_v2.csv", "SKiD_km_master_v6_enriched.csv"),
    ("IntEnzy_kcat_master_v1.csv", "IntEnzy_kcat_master_v6_enriched.csv"),
    ("IntEnzy_km_master_v1.csv", "IntEnzy_km_master_v6_enriched.csv"),
]

MERGE_INPUTS = [
    ("merge_kcat_v2.csv", "merge_kcat_v6_enriched.csv"),
    ("merge_km_v2.csv", "merge_km_v6_enriched.csv"),
]

FINAL_INPUTS = [
    ("merge_kcat_final_v6_statusfixed_all.csv", "merge_kcat_final_v6_enriched.csv"),
    ("merge_km_final_v6_statusfixed_all.csv", "merge_km_final_v6_enriched.csv"),
]


def normalize_text(value):
    return str(value or "").strip()


def normalize_unit(unit):
    unit = normalize_text(unit)
    replacements = {
        "s^(-1)": "s^-1",
        "M^(-1)*s^(-1)": "M^-1*s^-1",
        "mol*s^(-1)*g^(-1)": "mol*s^-1*g^-1",
        "mol*s^(-1)*mol^(-1)": "mol*s^-1*mol^-1",
    }
    return replacements.get(unit, unit)


def normalize_value_and_unit(parameter_name, value, unit):
    unit_norm = normalize_unit(unit)
    value_text = normalize_text(value)
    try:
        value_num = float(value_text)
    except Exception:
        return value_text, unit_norm
    if parameter_name == "km" and unit_norm == "M":
        return str(value_num * 1000.0), "mM"
    return value_text, unit_norm


def make_pair_key(row):
    return "|".join(
        [
            normalize_text(row.get("uniprot", "")),
            normalize_text(row.get("enzyme_type", "")).lower().replace(" ", "_"),
            normalize_text(row.get("mutation", "")),
            normalize_text(row.get("sequence", "")).replace(" ", "").upper(),
            normalize_text(row.get("substrate", "")),
            normalize_text(row.get("smiles", "")),
            normalize_text(row.get("ph", "")),
            normalize_text(row.get("temperature", "")),
        ]
    )


def load_source_kcatkm():
    path = INPUT_ROOT / "sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv"
    values = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if normalize_text(row.get("parameter_name", "")) != "kcat_km":
                continue
            values[make_pair_key(row)].append(
                {
                    "value": normalize_text(row.get("value", "")),
                    "unit": normalize_unit(row.get("unit", "")),
                }
            )
    return values


def load_rows_by_record_id(paths):
    data = {}
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row["record_id"]] = row
    return data


def build_maps(paths):
    kcat_map = defaultdict(list)
    km_map = defaultdict(list)
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parameter_name = normalize_text(row.get("parameter_name", ""))
                key = make_pair_key(row)
                if parameter_name == "kcat":
                    kcat_map[key].append(row)
                elif parameter_name == "km":
                    km_map[key].append(row)
    return kcat_map, km_map


def maybe_float(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def choose_sequences(row, source_row):
    enzyme_type = normalize_text(row.get("enzyme_type", ""))
    sequence = normalize_text(row.get("sequence", ""))
    wt_sequence = normalize_text(source_row.get("WT_sequence", "")) if source_row else ""
    mut_sequence = normalize_text(source_row.get("MUT_sequence", "")) if source_row else ""
    mutation_status = normalize_text(source_row.get("mutation_apply_status", "") or row.get("mutation_apply_status", ""))

    if source_row:
        row["mutation_apply_status"] = normalize_text(source_row.get("mutation_apply_status", ""))
        if normalize_text(source_row.get("sequence_source", "")):
            row["sequence_source"] = normalize_text(source_row.get("sequence_source", ""))
        if normalize_text(source_row.get("sequence", "")):
            row["sequence"] = normalize_text(source_row.get("sequence", ""))
            sequence = row["sequence"]

    if enzyme_type == "mutant":
        if mut_sequence and mutation_status in {"success", "no_change"}:
            return wt_sequence, mut_sequence
        return wt_sequence, ""
    if sequence:
        wt_sequence = sequence
    return wt_sequence, ""


def enrich_row(row, source_row, source_kcatkm, kcat_map, km_map):
    wt, mut = choose_sequences(row, source_row)
    row["WT_sequence"] = wt
    row["MUT_sequence"] = mut
    value_normalized, unit_normalized = normalize_value_and_unit(
        normalize_text(row.get("parameter_name", "")),
        row.get("value", ""),
        row.get("unit", ""),
    )
    row["value_normalized"] = value_normalized
    row["unit_normalized"] = unit_normalized
    key = make_pair_key(row)
    source_vals = source_kcatkm.get(key, [])
    row["kcat_km_source_value"] = source_vals[0]["value"] if source_vals else ""
    row["kcat_km_source_unit"] = source_vals[0]["unit"] if source_vals else ""
    row["kcat_km_computed_value"] = ""
    row["kcat_km_computed_unit"] = ""

    if not row["kcat_km_source_value"]:
        parameter_name = normalize_text(row.get("parameter_name", ""))
        own_value = maybe_float(row.get("value_normalized", ""))
        own_unit = row["unit_normalized"]
        if parameter_name == "kcat" and own_value is not None and own_unit == "s^-1":
            for other in km_map.get(key, []):
                km_value, km_unit = normalize_value_and_unit(
                    normalize_text(other.get("parameter_name", "")),
                    other.get("value", ""),
                    other.get("unit", ""),
                )
                km_value = maybe_float(km_value)
                if km_value and km_value > 0 and km_unit == "mM":
                    row["kcat_km_computed_value"] = str(own_value / (km_value / 1000.0))
                    row["kcat_km_computed_unit"] = "M^-1*s^-1"
                    break
        elif parameter_name == "km" and own_value is not None and own_unit == "mM":
            for other in kcat_map.get(key, []):
                kcat_value, kcat_unit = normalize_value_and_unit(
                    normalize_text(other.get("parameter_name", "")),
                    other.get("value", ""),
                    other.get("unit", ""),
                )
                kcat_value = maybe_float(kcat_value)
                if kcat_value is not None and own_value > 0 and kcat_unit == "s^-1":
                    row["kcat_km_computed_value"] = str(kcat_value / (own_value / 1000.0))
                    row["kcat_km_computed_unit"] = "M^-1*s^-1"
                    break
    return row


def enrich_file(input_path, output_path, source_rows, source_kcatkm, kcat_map, km_map):
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        for extra in [
            "WT_sequence",
            "MUT_sequence",
            "value_normalized",
            "unit_normalized",
            "kcat_km_source_value",
            "kcat_km_source_unit",
            "kcat_km_computed_value",
            "kcat_km_computed_unit",
        ]:
            if extra not in fieldnames:
                fieldnames.append(extra)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            source_row = source_rows.get(row.get("record_id", ""), {})
            writer.writerow(enrich_row(row, source_row, source_kcatkm, kcat_map, km_map))


def export_formal_condition_tables(final_output_names):
    combined_rows = []
    fieldnames = []
    for output_name in final_output_names:
        current_fieldnames, rows = read_rows(OUTPUT_ROOT / output_name)
        if not fieldnames and current_fieldnames:
            fieldnames = current_fieldnames
        combined_rows.extend(rows)

    ph_rows = [row for row in combined_rows if normalize_text(row.get("ph", ""))]
    temperature_rows = [row for row in combined_rows if normalize_text(row.get("temperature", ""))]
    write_rows(CONDITION_OUTPUT_ROOT / "ph_long_table.csv", fieldnames, ph_rows)
    write_rows(CONDITION_OUTPUT_ROOT / "temperature_long_table.csv", fieldnames, temperature_rows)
    return len(ph_rows), len(temperature_rows)


def main():
    source_kcatkm = load_source_kcatkm()
    latest_master_paths = [INPUT_ROOT / name for name, _ in MASTER_INPUTS]
    source_rows = load_rows_by_record_id(latest_master_paths)
    merge_paths = [INPUT_ROOT / name for name, _ in MERGE_INPUTS]
    final_paths = [INPUT_ROOT / name for name, _ in FINAL_INPUTS]
    kcat_map, km_map = build_maps(latest_master_paths + merge_paths + final_paths)
    final_output_names = []

    for input_name, output_name in MASTER_INPUTS:
        enrich_file(INPUT_ROOT / input_name, OUTPUT_ROOT / output_name, source_rows, source_kcatkm, kcat_map, km_map)
        print(output_name)
    for input_name, output_name in MERGE_INPUTS:
        enrich_file(INPUT_ROOT / input_name, OUTPUT_ROOT / output_name, source_rows, source_kcatkm, kcat_map, km_map)
        print(output_name)
    for input_name, output_name in FINAL_INPUTS:
        enrich_file(INPUT_ROOT / input_name, OUTPUT_ROOT / output_name, source_rows, source_kcatkm, kcat_map, km_map)
        final_output_names.append(output_name)
        print(output_name)
    ph_rows, temperature_rows = export_formal_condition_tables(final_output_names)
    print(f"conditions/ph_long_table.csv\t{ph_rows}")
    print(f"conditions/temperature_long_table.csv\t{temperature_rows}")


if __name__ == "__main__":
    main()
