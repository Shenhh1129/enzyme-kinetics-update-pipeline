import csv
import hashlib
import re
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_uniprot(value):
    value = normalize_text(value).upper()
    return "" if value.lower() in {"", "nan", "none", "-"} else value


def normalize_substrate_key(value):
    value = normalize_text(value).lower()
    value = value.replace("°", "deg")
    value = value.replace("º", "deg")
    value = re.sub(r"[\u2010-\u2015\u2212]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ;,")


def normalize_smiles(value):
    return normalize_text(value)


def normalize_parameter_name(value):
    value = normalize_text(value)
    lower = value.lower()
    if lower == "km":
        return "km"
    if lower == "kcat":
        return "kcat"
    if lower in {"kcat/km", "kcat / km", "kcat per km"}:
        return "kcat_km"
    return value


def choose_final_sequence(row):
    mutation_seq = normalize_text(row.get("mutation_applied_sequence", "")).replace(" ", "").upper()
    sequence = normalize_text(row.get("sequence", "")).replace(" ", "").upper()
    wildtype = normalize_text(row.get("sequence_wildtype", "")).replace(" ", "").upper()

    if mutation_seq:
        return mutation_seq, "mutation_applied_sequence"
    if sequence:
        return sequence, "sequence"
    if wildtype:
        return wildtype, "sequence_wildtype"
    return "", ""


def build_record_id(row):
    parts = [
        normalize_text(row.get("source_dataset", "")),
        normalize_text(row.get("source_record_id", "")),
        normalize_parameter_name(row.get("kinetic_parameter", "")),
        normalize_uniprot(row.get("uniprot", "")),
        normalize_substrate_key(row.get("substrate", "")),
        normalize_text(row.get("mutation", "")),
        normalize_text(row.get("kinetic_value_raw", "")),
    ]
    payload = "|".join(parts)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]
    return f"{parts[0]}:{digest}"


STANDARDIZED_APPEND_COLUMNS = [
    "record_id",
    "parameter_name",
    "value",
    "unit",
    "uniprot_norm",
    "substrate_norm_key",
    "smiles_norm",
    "sequence_final",
    "sequence_final_source",
]

TASKS = [
    ("brenda_raw_qc_v1.csv", "brenda_raw_qc_standardized_v1.csv"),
    ("sabio_tsv_raw_qc_v1.csv", "sabio_tsv_raw_qc_standardized_v1.csv"),
]


def standardize_file(input_name, output_name):
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name

    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames) + STANDARDIZED_APPEND_COLUMNS
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        rows = 0
        for row in reader:
            sequence_final, sequence_final_source = choose_final_sequence(row)
            row["record_id"] = build_record_id(row)
            row["parameter_name"] = normalize_parameter_name(row.get("kinetic_parameter", ""))
            row["value"] = row.get("kinetic_value_num", "")
            row["unit"] = normalize_text(row.get("kinetic_unit", ""))
            row["uniprot_norm"] = normalize_uniprot(row.get("uniprot", ""))
            row["substrate_norm_key"] = normalize_substrate_key(row.get("substrate", ""))
            row["smiles_norm"] = normalize_smiles(row.get("smiles", ""))
            row["sequence_final"] = sequence_final
            row["sequence_final_source"] = sequence_final_source
            writer.writerow(row)
            rows += 1

    return rows


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for input_name, output_name in TASKS:
        rows = standardize_file(input_name, output_name)
        print(f"{output_name}\t{rows}")


if __name__ == "__main__":
    main()
