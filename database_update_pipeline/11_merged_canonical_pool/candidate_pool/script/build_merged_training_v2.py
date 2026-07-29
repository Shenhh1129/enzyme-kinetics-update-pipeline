import csv
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


KCAT_INPUTS = [
    INPUT_ROOT / "CataPro_kcat_master_v2.csv",
    INPUT_ROOT / "DLKcat_kcat_master_v2.csv",
    INPUT_ROOT / "SKiD_kcat_master_seqfilled_v2.csv",
]

KM_INPUTS = [
    INPUT_ROOT / "CataPro_km_master_v2.csv",
    INPUT_ROOT / "SKiD_km_master_seqfilled_v2.csv",
]


def merge_files(input_paths, output_path):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    total_rows = 0
    fieldnames = []
    rows_by_path = []

    for path in input_paths:
        with path.open("r", encoding="utf-8-sig", newline="") as src:
            reader = csv.DictReader(src)
            rows = list(reader)
            rows_by_path.append((path, reader.fieldnames or [], rows))
            for name in reader.fieldnames or []:
                if name not in fieldnames:
                    fieldnames.append(name)

    with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for _, source_fields, rows in rows_by_path:
            for row in rows:
                normalized = {name: row.get(name, "") for name in fieldnames}
                for name in source_fields:
                    normalized[name] = row.get(name, "")
                writer.writerow(normalized)
                total_rows += 1
    return total_rows


def main():
    kcat_output = OUTPUT_ROOT / "merge_kcat_v2.csv"
    km_output = OUTPUT_ROOT / "merge_km_v2.csv"
    print(f"{kcat_output.name}\t{merge_files(KCAT_INPUTS, kcat_output)}")
    print(f"{km_output.name}\t{merge_files(KM_INPUTS, km_output)}")


if __name__ == "__main__":
    main()
