import csv
from collections import Counter
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

REQUIRED_FIELDS = [
    "kinetic_value_num",
    "uniprot",
    "smiles",
]

TASKS = [
    ("brenda_raw_mutseq_v1.csv", "brenda_raw_qc_v1.csv"),
    ("sabio_tsv_raw_subres_v1.csv", "sabio_tsv_raw_qc_v1.csv"),
]


def first_drop_reason(row):
    if not str(row.get("kinetic_value_num", "")).strip():
        return "missing_kinetic_value_num"
    if not str(row.get("uniprot", "")).strip():
        return "missing_uniprot"
    if not str(row.get("smiles", "")).strip():
        return "missing_smiles"
    return ""


def run_qc(input_path, output_path):
    stats = Counter()
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            stats["input_rows"] += 1
            reason = first_drop_reason(row)
            if reason:
                stats["dropped_rows"] += 1
                stats[f"drop_reason:{reason}"] += 1
                continue

            writer.writerow(row)
            stats["kept_rows"] += 1

    return stats


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for input_name, output_name in TASKS:
        input_path = INPUT_ROOT / input_name
        output_path = OUTPUT_ROOT / output_name
        stats = run_qc(input_path, output_path)
        print(output_name)
        for key, value in sorted(stats.items()):
            print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
