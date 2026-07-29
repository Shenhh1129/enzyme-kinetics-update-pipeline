import csv
import re
from collections import Counter
from pathlib import Path

import pandas as pd


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

CATA_FILES = [
    INPUT_ROOT / "kcat-data_0.4simi-10fold.csv",
    INPUT_ROOT / "Km-data_0.4simi-10fold.csv",
    INPUT_ROOT / "kcat-over-Km-data_0.4simi-10fold.csv",
]

SUB_PATTERN = re.compile(r"^([A-Z*])(\d+)([A-Z*])$")


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_uniprot(value):
    value = normalize_text(value)
    return "" if value.lower() in {"", "nan", "none", "-"} else value.upper()


def normalize_sequence(value):
    value = normalize_text(value).replace(" ", "").upper()
    return "" if not value or value in {"NAN", "NONE", "-"} else value


def choose_single_sequence(current, new_value):
    if not new_value:
        return current
    if not current:
        return new_value
    return current if len(current) >= len(new_value) else new_value


def build_sequence_map():
    seq_map = {}
    seq_source = {}
    for path in CATA_FILES:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            uniprot = normalize_uniprot(row.get("UniProtID", ""))
            seq = normalize_sequence(row.get("Sequence", ""))
            if uniprot and seq:
                seq_map[uniprot] = choose_single_sequence(seq_map.get(uniprot, ""), seq)
                seq_source[uniprot] = "local_catapro"
    return seq_map, seq_source


def parse_mutation_tokens(text):
    tokens = []
    for part in str(text or "").split("|"):
        token = part.strip()
        if token:
            tokens.append(token)
    return tokens


def apply_substitutions(sequence, mutation_text):
    sequence = (sequence or "").strip().upper()
    if not sequence:
        return "", "missing_sequence"

    tokens = parse_mutation_tokens(mutation_text)
    if not tokens:
        return "", "missing_mutation"

    seq = list(sequence)
    for token in tokens:
        match = SUB_PATTERN.match(token)
        if not match:
            if token.startswith("ins:"):
                return "", "unsupported_insertion"
            if token.startswith("del:"):
                return "", "unsupported_deletion"
            return "", "unsupported_mutation_format"

        src, pos_text, dst = match.groups()
        pos = int(pos_text)
        if pos < 1 or pos > len(seq):
            return "", "position_out_of_range"
        current = seq[pos - 1]
        if src != "*" and current != src:
            return "", f"source_mismatch:{token}:{current}"
        if dst == "*":
            return "", "unsupported_stop_mutation"
        seq[pos - 1] = dst

    rebuilt = "".join(seq)
    if rebuilt == sequence:
        return rebuilt, "no_change"
    return rebuilt, "success"


def fill_and_retry(input_name, output_name):
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name
    seq_map, seq_source = build_sequence_map()

    stats = Counter()
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        if "sequence_backfill_stage" not in fieldnames:
            fieldnames.append("sequence_backfill_stage")
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            stats["rows"] += 1
            row["sequence_backfill_stage"] = ""
            uniprot = normalize_uniprot(row.get("uniprot_norm", "") or row.get("uniprot", ""))
            current_seq = normalize_sequence(row.get("sequence_final", ""))

            if not current_seq and uniprot:
                seq = seq_map.get(uniprot, "")
                if seq:
                    row["sequence"] = seq
                    row["sequence_final"] = seq
                    row["sequence_final_source"] = "post_standardized_uniprot_backfill"
                    row["sequence_source"] = seq_source.get(uniprot, "post_standardized_uniprot_backfill")
                    row["sequence_backfill_stage"] = "post_standardized_uniprot_backfill"
                    current_seq = seq
                    stats["sequence_backfilled"] += 1

            if row.get("enzyme_type") == "mutant" and row.get("mutation") and current_seq:
                if not normalize_sequence(row.get("mutation_applied_sequence", "")):
                    rebuilt, status = apply_substitutions(current_seq, row.get("mutation", ""))
                    if status in {"success", "no_change"}:
                        row["sequence"] = rebuilt
                        row["sequence_final"] = rebuilt
                        row["mutation_applied_sequence"] = rebuilt
                        row["mutation_apply_status"] = status
                        row["sequence_final_source"] = "post_standardized_mutation_applied"
                        stats["mutation_reapplied_success"] += 1
                    elif row.get("mutation_apply_status") in {"missing_sequence", "", "not_applied"}:
                        row["mutation_apply_status"] = status
                        stats[f"mutation_reapplied_{status}"] += 1

            writer.writerow(row)

    return stats


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    tasks = [
        ("brenda_raw_qc_standardized_v1.csv", "brenda_raw_qc_standardized_seqfilled_v1.csv"),
        ("sabio_tsv_raw_qc_standardized_v1.csv", "sabio_tsv_raw_qc_standardized_seqfilled_v1.csv"),
    ]
    for input_name, output_name in tasks:
        stats = fill_and_retry(input_name, output_name)
        print(output_name)
        for key, value in sorted(stats.items()):
            print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
