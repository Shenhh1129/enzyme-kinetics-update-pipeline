import csv
import json
from collections import Counter
from pathlib import Path

from parse_utils import (
    combine_parse_status,
    normalize_space,
    parse_ions_value,
    parse_mutation_and_type,
    parse_ph_value,
    parse_temperature_value,
)


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

INPUT_PATH = INPUT_ROOT / "sabio_current_kcat_km_kcatkm.tsv"

TARGET_PARAMETERS = {"kcat", "km", "kcat_km"}

OUTPUT_COLUMNS = [
    "source_dataset",
    "source_table",
    "source_record_id",
    "source_record_label",
    "source_payload_json",
    "ec_number",
    "organism",
    "uniprot",
    "sequence",
    "sequence_source",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "substrate",
    "smiles_raw",
    "smiles",
    "kinetic_parameter",
    "kinetic_value_raw",
    "kinetic_value_num",
    "kinetic_unit",
    "enzyme_type",
    "mutation_raw",
    "mutation",
    "mutation_parse_status",
    "ph_raw",
    "ph",
    "ph_parse_status",
    "temperature_raw",
    "temperature",
    "temperature_parse_status",
    "ions_raw",
    "ions",
    "ions_parse_status",
    "parse_status",
]


def parse_numeric_value(text):
    text = normalize_space(text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_parameter_type(value):
    value = normalize_space(value)
    lower = value.lower()
    if lower == "km":
        return "km"
    if lower == "kcat":
        return "kcat"
    if lower == "kcat/km":
        return "kcat_km"
    return value


def format_value(row):
    start = normalize_space(row.get("parameter.startValue", ""))
    end = normalize_space(row.get("parameter.endValue", ""))
    if start and end and start != end:
        return f"{start}..{end}"
    return start or end


def choose_substrate(row):
    associated = normalize_space(row.get("parameter.associatedSpecies", ""))
    substrate = normalize_space(row.get("Substrate", ""))
    if associated and associated not in {"-", "--"}:
        return associated, "associated_species"
    return substrate, "substrate_field"


def normalize_row(row):
    parameter = normalize_parameter_type(row.get("parameter.type", ""))
    variant_text = normalize_space(row.get("Enzyme Variant", ""))
    enzyme_type, mutation_raw_token, mutation, mutation_parse_status = parse_mutation_and_type(variant_text)
    mutation_raw_value = mutation_raw_token or variant_text

    substrate, substrate_source = choose_substrate(row)
    ph_raw = normalize_space(row.get("pH", ""))
    temperature_raw = normalize_space(row.get("Temperature", ""))
    ph, ph_parse_status = parse_ph_value(ph_raw)
    temperature, temperature_parse_status = parse_temperature_value(temperature_raw)
    ions_raw = ""
    ions, ions_parse_status = parse_ions_value(ions_raw)

    commentary_parts = [
        normalize_space(row.get("Enzymename", "")),
        variant_text,
        f"substrate_source={substrate_source}",
        normalize_space(row.get("InsertDate", "")),
    ]
    commentary = normalize_space("; ".join(x for x in commentary_parts if x))
    value_raw = format_value(row)

    return {
        "source_dataset": "SABIO-RK",
        "source_table": "kineticlaw_tsv",
        "source_record_id": normalize_space(row.get("EntryID", "")),
        "source_record_label": parameter,
        "source_payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
        "ec_number": normalize_space(row.get("ECNumber", "")),
        "organism": normalize_space(row.get("Organism", "")),
        "uniprot": normalize_space(row.get("UniprotID", "")),
        "sequence": "",
        "sequence_source": "",
        "reaction_raw": normalize_space(row.get("Reaction", "")),
        "commentary": commentary,
        "substrate_raw": substrate,
        "substrate": substrate,
        "smiles_raw": "",
        "smiles": "",
        "kinetic_parameter": parameter,
        "kinetic_value_raw": value_raw,
        "kinetic_value_num": parse_numeric_value(value_raw),
        "kinetic_unit": normalize_space(row.get("parameter.unit", "")),
        "enzyme_type": enzyme_type,
        "mutation_raw": mutation_raw_value,
        "mutation": mutation,
        "mutation_parse_status": mutation_parse_status,
        "ph_raw": ph_raw,
        "ph": ph,
        "ph_parse_status": ph_parse_status,
        "temperature_raw": temperature_raw,
        "temperature": temperature,
        "temperature_parse_status": temperature_parse_status,
        "ions_raw": ions_raw,
        "ions": ions,
        "ions_parse_status": ions_parse_status,
        "parse_status": combine_parse_status(
            mutation_parse_status,
            ph_parse_status,
            temperature_parse_status,
            ions_parse_status,
        ),
    }


def main():
    output_path = OUTPUT_ROOT / "sabio_tsv_raw_v1.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src, delimiter="\t")
        writer = csv.DictWriter(dst, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in reader:
            parameter = normalize_parameter_type(row.get("parameter.type", ""))
            if parameter not in TARGET_PARAMETERS:
                stats["non_target_parameter"] += 1
                continue
            out = normalize_row(row)
            writer.writerow(out)
            stats["rows"] += 1
            stats[f"parameter:{out['kinetic_parameter']}"] += 1
            if out["uniprot"]:
                stats["rows_with_uniprot"] += 1
            if out["kinetic_value_num"] is None:
                stats["rows_missing_numeric_value"] += 1

    print(output_path.name)
    for key, value in sorted(stats.items()):
        print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
