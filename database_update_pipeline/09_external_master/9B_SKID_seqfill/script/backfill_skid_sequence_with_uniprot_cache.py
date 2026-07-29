import csv
import re
from collections import Counter
from pathlib import Path


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"
CACHE_PATH = INPUT_ROOT / "uniprot_sequence_cache_v1.csv"

SUB_PATTERN = re.compile(r"^([A-Z*])(\d+)([A-Z*])$")


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_uniprots(value):
    raw = normalize_text(value)
    if not raw:
        return []
    raw = raw.replace("|", " ")
    tokens = []
    for part in raw.split():
        token = normalize_text(part).upper()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


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


def load_cache():
    cache = {}
    with CACHE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            seq = normalize_text(row.get("sequence", "")).replace(" ", "").upper()
            if row.get("uniprot") and seq:
                cache[row["uniprot"]] = seq
    return cache


def fill_master(input_name, output_name):
    input_path = INPUT_ROOT / input_name
    output_path = OUTPUT_ROOT / output_name
    cache = load_cache()
    stats = Counter()

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
            stats["rows"] += 1
            row["WT_sequence"] = ""
            row["MUT_sequence"] = ""
            current_seq = normalize_text(row.get("sequence", "")).replace(" ", "").upper()
            if not current_seq:
                for accession in split_uniprots(row.get("uniprot", "")):
                    seq = cache.get(accession, "")
                    if seq:
                        row["sequence"] = seq
                        row["sequence_source"] = "uniprot_cache"
                        current_seq = seq
                        stats["sequence_backfilled"] += 1
                        break

            enzyme_type = row.get("enzyme_type")
            if enzyme_type in {"wild", "ambiguous"} and current_seq:
                row["WT_sequence"] = current_seq

            if enzyme_type == "mutant" and row.get("mutation") and current_seq:
                row["WT_sequence"] = current_seq
                rebuilt, status = apply_substitutions(current_seq, row.get("mutation", ""))
                row["mutation_apply_status"] = status
                if status in {"success", "no_change"}:
                    row["sequence"] = rebuilt
                    row["sequence_source"] = "uniprot_cache|mutation_applied"
                    row["MUT_sequence"] = rebuilt
                    stats["mutation_reapplied_success"] += 1
                else:
                    stats[f"mutation_reapplied_{status}"] += 1
            elif enzyme_type == "mutant" and current_seq:
                row["WT_sequence"] = current_seq

            writer.writerow(row)

    return stats


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    tasks = [
        ("SKiD_kcat_master_v1.csv", "SKiD_kcat_master_seqfilled_v1.csv"),
        ("SKiD_km_master_v1.csv", "SKiD_km_master_seqfilled_v1.csv"),
    ]
    for input_name, output_name in tasks:
        stats = fill_master(input_name, output_name)
        print(output_name)
        for key, value in sorted(stats.items()):
            print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
