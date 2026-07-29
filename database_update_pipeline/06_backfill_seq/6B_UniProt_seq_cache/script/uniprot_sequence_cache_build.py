import csv
import re
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

INPUTS = [
    INPUT_ROOT / "brenda_raw_qc_standardized_seqfilled_v1.csv",
    INPUT_ROOT / "sabio_tsv_raw_qc_standardized_seqfilled_v1.csv",
]

OUTPUT_CACHE = OUTPUT_ROOT / "uniprot_sequence_cache_v1.csv"
BATCH_SIZE = 50


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


def collect_needed_uniprots():
    needed = Counter()
    for path in INPUTS:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("sequence_final", "").strip():
                    continue
                for token in split_uniprots(row.get("uniprot_norm", "") or row.get("uniprot", "")):
                    needed[token] += 1
    return needed


def fetch_fasta(accession, retries=3, sleep_sec=2):
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    for attempt in range(1, retries + 1):
        try:
            with urlopen(url, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines or not lines[0].startswith(">"):
                return ""
            return "".join(lines[1:]).strip().upper()
        except (HTTPError, URLError, TimeoutError):
            time.sleep(sleep_sec * attempt)
    return ""


def write_cache_rows(rows):
    with OUTPUT_CACHE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["uniprot", "sequence", "requested_rows"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    needed = collect_needed_uniprots()
    existing = {}
    if OUTPUT_CACHE.exists():
        with OUTPUT_CACHE.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                existing[row["uniprot"]] = row["sequence"]

    rows = []
    stats = Counter()
    pending_fetch = [u for u, _ in needed.most_common() if not existing.get(u, "")]
    pending_set = set(pending_fetch[:BATCH_SIZE])

    for idx, (uniprot, count) in enumerate(needed.most_common(), start=1):
        sequence = existing.get(uniprot, "")
        if uniprot in pending_set and not sequence:
            sequence = fetch_fasta(uniprot)
            if sequence:
                stats["fetched"] += 1
            else:
                stats["missing"] += 1
            existing[uniprot] = sequence
        elif sequence:
            stats["cache_hit"] += 1
        else:
            stats["deferred"] += 1
        rows.append({"uniprot": uniprot, "sequence": sequence, "requested_rows": count})
        stats["rows"] += 1
        if idx % 25 == 0:
            write_cache_rows(rows)

    write_cache_rows(rows)

    print(OUTPUT_CACHE.name)
    for key, value in sorted(stats.items()):
        print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
