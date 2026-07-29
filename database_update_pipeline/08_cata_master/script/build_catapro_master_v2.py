import csv
import hashlib
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


INPUT_OUTPUT = [
    ("catapro_update_kcat_v2.csv", "CataPro_kcat_master_v2.csv"),
    ("catapro_update_km_v2.csv", "CataPro_km_master_v2.csv"),
]


SOURCE_RELEASE_MAP = {
    "BRENDA": "2026.1",
    "SABIO-RK": "current_tsv_snapshot",
}


MASTER_COLUMNS = [
    "dataset_name",
    "parameter_name",
    "source_db",
    "source_release",
    "source_record_id",
    "record_id",
    "measurement_uid",
    "ec_number",
    "organism",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "sequence_source",
    "substrate",
    "smiles",
    "value",
    "unit",
    "ph",
    "temperature",
    "ions",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "parse_status",
    "mutation_apply_status",
]

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


def make_business_key(row):
    parts = [
        normalize_text(row.get("uniprot", "")),
        normalize_enzyme_type(row.get("enzyme_type", "")),
        normalize_text(row.get("mutation", "")),
        normalize_sequence(row.get("sequence", "")),
        normalize_text(row.get("substrate", "")),
        normalize_text(row.get("smiles", "")),
    ]
    return "|".join(parts)


def make_measurement_uid(row):
    parts = [
        normalize_text(row.get("uniprot", "")),
        normalize_enzyme_type(row.get("enzyme_type", "")),
        normalize_text(row.get("mutation", "")),
        normalize_sequence(row.get("sequence", "")),
        normalize_text(row.get("substrate", "")),
        normalize_text(row.get("smiles", "")),
        normalize_parameter_name(row.get("parameter_name", "")),
        normalize_text(row.get("value", "")),
        normalize_text(row.get("ph", "")),
        normalize_text(row.get("temperature", "")),
    ]
    return f"muid_{digest20('|'.join(parts))}"


def make_record_id(row):
    payload = "|".join(
        [
            normalize_text(row.get("measurement_uid", "")),
            normalize_text(row.get("organism", "")),
            normalize_text(row.get("ions", "")),
        ]
    )
    return f"frid_{digest20(payload)}" if payload.strip("|") else ""


def map_row(row):
    mapped = {
        "dataset_name": "CataPro",
        "parameter_name": normalize_parameter_name(row.get("parameter_name", "")),
        "source_db": normalize_text(row.get("source_dataset", "")),
        "source_release": SOURCE_RELEASE_MAP.get(row.get("source_dataset", ""), ""),
        "source_record_id": normalize_text(row.get("source_record_id", "")),
        "record_id": "",
        "measurement_uid": "",
        "ec_number": normalize_text(row.get("EC", "")),
        "organism": normalize_text(row.get("Organism", "")),
        "uniprot": normalize_text(row.get("UniProtID", "")),
        "enzyme_type": normalize_enzyme_type(row.get("EnzymeType", "")),
        "mutation": normalize_text(row.get("Mutation", "")),
        "sequence": normalize_sequence(row.get("Sequence", "")),
        "sequence_source": normalize_text(row.get("sequence_final_source", "")),
        "substrate": normalize_text(row.get("Substrate", "")),
        "smiles": normalize_text(row.get("Smiles", "")),
        "value": normalize_text(row.get("Value", "")),
        "unit": normalize_text(row.get("Unit", "")),
        "ph": normalize_text(row.get("ph", "")),
        "temperature": normalize_text(row.get("temperature", "")),
        "ions": normalize_text(row.get("ions", "")),
        "reaction_raw": normalize_text(row.get("reaction_raw", "")),
        "commentary": normalize_text(row.get("commentary", "")),
        "substrate_raw": normalize_text(row.get("substrate_raw", "")),
        "parse_status": normalize_text(row.get("parse_status", "")),
        "mutation_apply_status": normalize_text(row.get("mutation_apply_status", "")),
    }
    mapped["measurement_uid"] = make_measurement_uid(mapped)
    mapped["record_id"] = make_record_id(mapped)
    return mapped


def build_master(input_name, output_name):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name
    rows = 0
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        for row in reader:
            writer.writerow(map_row(row))
            rows += 1
    return rows


def main():
    for input_name, output_name in INPUT_OUTPUT:
        rows = build_master(input_name, output_name)
        print(f"{output_name}\t{rows}")


if __name__ == "__main__":
    main()
