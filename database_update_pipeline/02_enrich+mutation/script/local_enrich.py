import csv
import json
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
DLKCAT_FILE = INPUT_ROOT / "Kcat_combination_0918_wildtype_mutant.json"
SKID_LIGAND_FILE = INPUT_ROOT / "Ligands_all_final_v1.csv"


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_uniprot(value):
    value = normalize_text(value)
    return "" if value.lower() in {"", "nan", "none", "-"} else value.upper()


def normalize_sequence(value):
    value = normalize_text(value).replace(" ", "").upper()
    return "" if not value or value in {"NAN", "NONE", "-"} else value


def normalize_substrate_key(value):
    value = normalize_text(value)
    value = value.lower()
    value = value.replace("掳", "°")
    value = re.sub(r"[‐‑–—−]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ;,")


def choose_single_sequence(current, new_value):
    if not new_value:
        return current
    if not current:
        return new_value
    return current if len(current) >= len(new_value) else new_value


def existing_paths(paths):
    return [path for path in paths if path.exists()]


def build_sequence_map():
    seq_map = {}
    seq_source = {}

    for path in existing_paths(CATA_FILES):
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            uniprot = normalize_uniprot(row.get("UniProtID", ""))
            seq = normalize_sequence(row.get("Sequence", ""))
            if uniprot and seq:
                seq_map[uniprot] = choose_single_sequence(seq_map.get(uniprot, ""), seq)
                seq_source[uniprot] = "local_catapro"

    if DLKCAT_FILE.exists():
        with DLKCAT_FILE.open("r", encoding="utf-8") as handle:
            rows = json.load(handle)
        for row in rows:
            seq = normalize_sequence(row.get("Sequence", ""))
            if not seq:
                continue
            # DLKcat local json has no UniProt, so it is only retained as a local
            # enrichment reference for substrate/SMILES, not UniProt-keyed sequence fill.

    return seq_map, seq_source


def build_smiles_map():
    smiles_map = {}
    smiles_source = {}

    for path in existing_paths(CATA_FILES):
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_text(row.get("Smiles", ""))
            if substrate and smiles and substrate not in smiles_map:
                smiles_map[substrate] = smiles
                smiles_source[substrate] = "local_catapro"

    if DLKCAT_FILE.exists():
        with DLKCAT_FILE.open("r", encoding="utf-8") as handle:
            rows = json.load(handle)
        for row in rows:
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_text(row.get("Smiles", ""))
            if substrate and smiles and substrate not in smiles_map:
                smiles_map[substrate] = smiles
                smiles_source[substrate] = "local_dlkcat"

    if SKID_LIGAND_FILE.exists():
        df = pd.read_csv(SKID_LIGAND_FILE, sep="\t")
        for _, row in df.iterrows():
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_text(row.get("SMILES", ""))
            if substrate and smiles and substrate not in smiles_map:
                smiles_map[substrate] = smiles
                smiles_source[substrate] = "local_skid"

    return smiles_map, smiles_source


def enrich_file(input_path, output_path, seq_map, seq_source, smiles_map, smiles_source):
    stats = Counter()
    with input_path.open("r", encoding="utf-8-sig", errors="replace") as src, output_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames) + ["smiles_source"]
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            uniprots = [normalize_uniprot(x) for x in row.get("uniprot", "").split("|") if normalize_uniprot(x)]
            substrate_key = normalize_substrate_key(row.get("substrate", ""))

            if not row.get("sequence"):
                for uniprot in uniprots:
                    seq = seq_map.get(uniprot, "")
                    if seq:
                        row["sequence"] = seq
                        row["sequence_source"] = seq_source.get(uniprot, "local")
                        stats["sequence_filled"] += 1
                        break

            if not row.get("smiles"):
                smiles = smiles_map.get(substrate_key, "")
                if smiles:
                    row["smiles"] = smiles
                    row["smiles_source"] = smiles_source.get(substrate_key, "local")
                    stats["smiles_filled"] += 1
                else:
                    row["smiles_source"] = ""
            else:
                row["smiles_source"] = row.get("smiles_source", "")

            writer.writerow(row)
            stats["rows"] += 1

    return stats


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    seq_map, seq_source = build_sequence_map()
    smiles_map, smiles_source = build_smiles_map()
    print(f"sequence map: {len(seq_map)} uniprots")
    print(f"smiles map: {len(smiles_map)} substrates")

    tasks = [
        ("brenda_raw.csv", "brenda_raw_local_enriched.csv"),
        ("sabio_tsv_raw_v1.csv", "sabio_tsv_raw_local_enriched_v1.csv"),
    ]
    for input_name, output_name in tasks:
        stats = enrich_file(
            INPUT_ROOT / input_name,
            OUTPUT_ROOT / output_name,
            seq_map,
            seq_source,
            smiles_map,
            smiles_source,
        )
        print(output_name, dict(stats))


if __name__ == "__main__":
    main()
