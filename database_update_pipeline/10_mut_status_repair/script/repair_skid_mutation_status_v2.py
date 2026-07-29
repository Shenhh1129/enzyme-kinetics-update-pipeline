import csv
import re
from collections import Counter
from pathlib import Path

STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


TASKS = [
    ("SKiD_kcat_master_seqfilled_v1.csv", "SKiD_kcat_master_seqfilled_v2.csv"),
    ("SKiD_km_master_seqfilled_v1.csv", "SKiD_km_master_seqfilled_v2.csv"),
]

SUB_PATTERN = re.compile(r"^([A-Z*])(\d+)([A-Z*])$")


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_sequence(value):
    return normalize_text(value).replace(" ", "").upper()


def parse_mutation_tokens(text):
    tokens = []
    for part in str(text or "").split("|"):
        token = part.strip()
        if token:
            tokens.append(token)
    return tokens


def apply_substitutions(sequence, mutation_text):
    sequence = normalize_sequence(sequence)
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
    return rebuilt, "no_change" if rebuilt == sequence else "success"


def repair_row(row):
    enzyme_type = normalize_text(row.get("enzyme_type", "")).lower()
    mutation = normalize_text(row.get("mutation", ""))
    current_seq = normalize_sequence(row.get("sequence", ""))
    wt_sequence = normalize_sequence(row.get("WT_sequence", ""))
    mut_sequence = normalize_sequence(row.get("MUT_sequence", ""))
    status = normalize_text(row.get("mutation_apply_status", ""))

    if enzyme_type != "mutant":
        row["mutation_apply_status"] = "not_mutant"
        if current_seq and not wt_sequence:
            row["WT_sequence"] = current_seq
        row["MUT_sequence"] = ""
        return row["mutation_apply_status"]

    if not mutation:
        row["mutation_apply_status"] = "missing_mutation"
        if current_seq and not wt_sequence:
            row["WT_sequence"] = current_seq
        row["MUT_sequence"] = ""
        return row["mutation_apply_status"]

    template_seq = wt_sequence or current_seq
    if not template_seq:
        row["mutation_apply_status"] = "missing_sequence"
        row["MUT_sequence"] = ""
        return row["mutation_apply_status"]

    rebuilt, repaired_status = apply_substitutions(template_seq, mutation)
    row["WT_sequence"] = template_seq
    row["mutation_apply_status"] = repaired_status
    if repaired_status in {"success", "no_change"}:
        row["MUT_sequence"] = rebuilt
        row["sequence"] = rebuilt
        source = normalize_text(row.get("sequence_source", ""))
        if "mutation_applied" not in source:
            row["sequence_source"] = f"{source}|mutation_applied".strip("|")
    else:
        row["MUT_sequence"] = ""
        if not current_seq:
            row["sequence"] = template_seq
    return status + " -> " + repaired_status if status and status != repaired_status else repaired_status


def repair_file(input_name, output_name):
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    transitions = Counter()
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            old_status = normalize_text(row.get("mutation_apply_status", ""))
            new_status = repair_row(row)
            stats[normalize_text(row.get("mutation_apply_status", ""))] += 1
            transitions[(old_status, normalize_text(row.get("mutation_apply_status", "")))] += 1
            writer.writerow(row)
    return stats, transitions


def main():
    for input_name, output_name in TASKS:
        stats, transitions = repair_file(input_name, output_name)
        print(output_name)
        for key, value in sorted(stats.items()):
            print(f"status\t{key}\t{value}")
        for (old, new), value in sorted(transitions.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"transition\t{old}\t{new}\t{value}")


if __name__ == "__main__":
    main()
