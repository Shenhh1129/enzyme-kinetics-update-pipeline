import csv
import re
from collections import Counter
from pathlib import Path

STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

SUB_PATTERN = re.compile(r"^([A-Z*])(\d+)([A-Z*])$")


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


def rebuild_file(input_path, output_path):
    stats = Counter()
    with input_path.open("r", encoding="utf-8-sig", errors="replace") as src, output_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        for extra in ["sequence_wildtype", "mutation_applied_sequence", "mutation_apply_status"]:
            if extra not in fieldnames:
                fieldnames.append(extra)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            stats["rows"] += 1
            row["sequence_wildtype"] = row.get("sequence", "")
            row["mutation_applied_sequence"] = ""
            row["mutation_apply_status"] = ""

            if row.get("enzyme_type") != "mutant":
                row["mutation_apply_status"] = "not_mutant"
            elif not row.get("mutation"):
                row["mutation_apply_status"] = "missing_mutation"
            elif not row.get("sequence"):
                row["mutation_apply_status"] = "missing_sequence"
            else:
                rebuilt, status = apply_substitutions(row["sequence"], row["mutation"])
                row["mutation_apply_status"] = status
                if status in {"success", "no_change"}:
                    row["mutation_applied_sequence"] = rebuilt
                    row["sequence"] = rebuilt
                    row["sequence_source"] = f"{row.get('sequence_source', '')}|mutation_applied".strip("|")
                    stats["sequence_mutated"] += 1

            stats[row["mutation_apply_status"]] += 1
            writer.writerow(row)

    return stats


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    tasks = [
        (
            OUTPUT_ROOT / "brenda_raw_local_enriched.csv",
            OUTPUT_ROOT / "brenda_raw_mutseq_v1.csv",
        ),
        (
            OUTPUT_ROOT / "sabio_tsv_raw_local_enriched_v1.csv",
            OUTPUT_ROOT / "sabio_tsv_raw_mutseq_v1.csv",
        ),
    ]
    for input_path, output_path in tasks:
        stats = rebuild_file(input_path, output_path)
        print(output_path.name, dict(stats))


if __name__ == "__main__":
    main()
