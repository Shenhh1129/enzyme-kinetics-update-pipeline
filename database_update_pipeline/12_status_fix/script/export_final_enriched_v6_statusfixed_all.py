import csv
from collections import defaultdict
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


INPUTS = [
    ("merge_kcat_final_v2.csv", "merge_kcat_final_v6_statusfixed_all.csv"),
    ("merge_km_final_v2.csv", "merge_km_final_v6_statusfixed_all.csv"),
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


def load_kcatkm_source_values():
    path = INPUT_ROOT / "sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv"
    values = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if normalize_text(row.get("parameter_name")) != "kcat_km":
                continue
            values[make_pair_key(row)].append(
                {
                    "value": normalize_text(row.get("value", "")),
                    "unit": normalize_unit(row.get("unit", "")),
                }
            )
    return values


def load_master_rows():
    masters = {}
    for name in [
        "CataPro_kcat_master_v2.csv",
        "CataPro_km_master_v2.csv",
        "DLKcat_kcat_master_v2.csv",
        "SKiD_kcat_master_seqfilled_v2.csv",
        "SKiD_km_master_seqfilled_v2.csv",
    ]:
        path = INPUT_ROOT / name
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                masters[row["record_id"]] = row
    return masters


def build_kcat_km_maps():
    kcat_map = defaultdict(list)
    km_map = defaultdict(list)
    for input_name, _ in INPUTS:
        path = INPUT_ROOT / input_name
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = make_pair_key(row)
                parameter_name = normalize_text(row.get("parameter_name", ""))
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


def choose_sequence_fields(row, master_row):
    enzyme_type = normalize_text(row.get("enzyme_type", ""))
    sequence = normalize_text(row.get("sequence", ""))
    wt_sequence = normalize_text(master_row.get("WT_sequence", "")) if master_row else ""
    mut_sequence = normalize_text(master_row.get("MUT_sequence", "")) if master_row else ""
    mutation_status = normalize_text(master_row.get("mutation_apply_status", "") or row.get("mutation_apply_status", ""))

    if master_row:
        row["mutation_apply_status"] = normalize_text(master_row.get("mutation_apply_status", ""))
        if normalize_text(master_row.get("sequence_source", "")):
            row["sequence_source"] = normalize_text(master_row.get("sequence_source", ""))
        if normalize_text(master_row.get("sequence", "")):
            row["sequence"] = normalize_text(master_row.get("sequence", ""))
            sequence = row["sequence"]

    if enzyme_type == "mutant":
        if mut_sequence and mutation_status in {"success", "no_change"}:
            return wt_sequence, mut_sequence
        return wt_sequence, ""
    if sequence:
        wt_sequence = sequence
    return wt_sequence, ""


def enrich_file(input_name, output_name, masters, source_kcatkm, kcat_map, km_map):
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
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
            master_row = masters.get(row.get("record_id", ""), {})
            wt_sequence, mut_sequence = choose_sequence_fields(row, master_row)
            row["WT_sequence"] = wt_sequence
            row["MUT_sequence"] = mut_sequence
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
                        if km_value and km_unit == "mM":
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

            writer.writerow(row)


def main():
    masters = load_master_rows()
    source_kcatkm = load_kcatkm_source_values()
    kcat_map, km_map = build_kcat_km_maps()
    for input_name, output_name in INPUTS:
        enrich_file(input_name, output_name, masters, source_kcatkm, kcat_map, km_map)
        print(output_name)


if __name__ == "__main__":
    main()
