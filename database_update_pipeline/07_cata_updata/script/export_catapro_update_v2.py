import csv
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


INPUT_FILES = [
    INPUT_ROOT / "brenda_raw_qc_standardized_seqfilled_uniprot_v1.csv",
    INPUT_ROOT / "sabio_tsv_raw_qc_standardized_seqfilled_uniprot_v1.csv",
]


KCAT_OUTPUT = OUTPUT_ROOT / "catapro_update_kcat_v2.csv"
KM_OUTPUT = OUTPUT_ROOT / "catapro_update_km_v2.csv"


OUTPUT_COLUMNS = [
    "record_id",
    "source_dataset",
    "source_record_id",
    "parameter_name",
    "EC",
    "EnzymeType",
    "Organism",
    "Sequence",
    "Substrate",
    "Smiles",
    "UniProtID",
    "Value",
    "Unit",
    "Mutation",
    "sequence_final_source",
    "smiles_source",
    "ph",
    "temperature",
    "ions",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "parse_status",
    "mutation_apply_status",
]


def map_row(row):
    return {
        "record_id": row.get("record_id", ""),
        "source_dataset": row.get("source_dataset", ""),
        "source_record_id": row.get("source_record_id", ""),
        "parameter_name": row.get("parameter_name", ""),
        "EC": row.get("ec_number", ""),
        "EnzymeType": row.get("enzyme_type", ""),
        "Organism": row.get("organism", ""),
        "Sequence": row.get("sequence_final", ""),
        "Substrate": row.get("substrate", ""),
        "Smiles": row.get("smiles_norm", row.get("smiles", "")),
        "UniProtID": row.get("uniprot_norm", row.get("uniprot", "")),
        "Value": row.get("value", row.get("kinetic_value_num", "")),
        "Unit": row.get("unit", row.get("kinetic_unit", "")),
        "Mutation": row.get("mutation", ""),
        "sequence_final_source": row.get("sequence_final_source", ""),
        "smiles_source": row.get("smiles_source", ""),
        "ph": row.get("ph", row.get(" PH", "")),
        "temperature": row.get("temperature", ""),
        "ions": row.get("ions", ""),
        "reaction_raw": row.get("reaction_raw", ""),
        "commentary": row.get("commentary", ""),
        "substrate_raw": row.get("substrate_raw", ""),
        "parse_status": row.get("parse_status", ""),
        "mutation_apply_status": row.get("mutation_apply_status", ""),
    }


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    counts = {"kcat": 0, "km": 0}
    with KCAT_OUTPUT.open("w", encoding="utf-8-sig", newline="") as kcat_out, KM_OUTPUT.open(
        "w", encoding="utf-8-sig", newline=""
    ) as km_out:
        kcat_writer = csv.DictWriter(kcat_out, fieldnames=OUTPUT_COLUMNS)
        km_writer = csv.DictWriter(km_out, fieldnames=OUTPUT_COLUMNS)
        kcat_writer.writeheader()
        km_writer.writeheader()

        for path in INPUT_FILES:
            with path.open("r", encoding="utf-8-sig", newline="") as src:
                reader = csv.DictReader(src)
                for row in reader:
                    parameter_name = row.get("parameter_name", "")
                    mapped = map_row(row)
                    if parameter_name == "kcat":
                        kcat_writer.writerow(mapped)
                        counts["kcat"] += 1
                    elif parameter_name == "km":
                        km_writer.writerow(mapped)
                        counts["km"] += 1

    print(f"{KCAT_OUTPUT.name}\t{counts['kcat']}")
    print(f"{KM_OUTPUT.name}\t{counts['km']}")


if __name__ == "__main__":
    main()
