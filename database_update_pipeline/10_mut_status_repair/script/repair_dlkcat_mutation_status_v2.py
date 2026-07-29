import csv
import re
from collections import Counter
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


INPUT_NAME = "DLKcat_kcat_master_v1.csv"
OUTPUT_NAME = "DLKcat_kcat_master_v2.csv"


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_sequence(value):
    return normalize_text(value).replace(" ", "").upper()


def repair_row(row):
    enzyme_type = normalize_text(row.get("enzyme_type", "")).lower()
    mutation = normalize_text(row.get("mutation", ""))
    sequence = normalize_sequence(row.get("sequence", ""))
    current_status = normalize_text(row.get("mutation_apply_status", ""))

    if enzyme_type != "mutant":
        row["mutation_apply_status"] = "not_mutant"
        if sequence:
            row["WT_sequence"] = sequence
        row["MUT_sequence"] = ""
        return current_status, row["mutation_apply_status"]

    if not mutation:
        row["mutation_apply_status"] = "missing_mutation"
        row["WT_sequence"] = ""
        row["MUT_sequence"] = ""
        return current_status, row["mutation_apply_status"]

    return current_status, current_status


def main():
    input_path = INPUT_ROOT / INPUT_NAME
    output_path = OUTPUT_ROOT / OUTPUT_NAME
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    transitions = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        for extra in ["WT_sequence", "MUT_sequence"]:
            if extra not in fieldnames:
                fieldnames.append(extra)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            old, new = repair_row(row)
            stats[new] += 1
            transitions[(old, new)] += 1
            writer.writerow(row)

    print(OUTPUT_NAME)
    for key, value in sorted(stats.items()):
        print(f"status\t{key}\t{value}")
    for (old, new), value in sorted(transitions.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"transition\t{old}\t{new}\t{value}")


if __name__ == "__main__":
    main()
