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

COFACTOR_TOKENS = {
    "h2o",
    "h+",
    "o2",
    "atp",
    "adp",
    "amp",
    "gtp",
    "gdp",
    "ctp",
    "udp",
    "ump",
    "utp",
    "pi",
    "ppi",
    "co2",
    "nh3",
    "nad+",
    "nadh",
    "nadp+",
    "nadph",
    "fadh2",
    "fad",
    "fmn",
    "coa",
    "acetyl-coa",
    "succinyl-coa",
    "reduced glutathione",
    "oxidized glutathione",
    "glutathione",
    "isopentenyl diphosphate",
}


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_substrate_key(value):
    value = normalize_text(value)
    value = value.lower()
    value = value.replace("°", "deg")
    value = value.replace("º", "deg")
    value = re.sub(r"[\u2010-\u2015\u2212]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ;,")


def existing_paths(paths):
    return [path for path in paths if path.exists()]


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


def split_components(substrate_text):
    parts = [normalize_text(x) for x in str(substrate_text or "").split(";")]
    return [x for x in parts if x]


def is_ion_or_simple_inorganic(token):
    key = normalize_substrate_key(token)
    if key in COFACTOR_TOKENS:
        return True
    if re.fullmatch(r"[a-z0-9+\-()]+", key):
        if any(ch.isdigit() for ch in key) and ("+" in key or "-" in key):
            return True
    return False


def resolve_single_substrate(substrate_text):
    parts = split_components(substrate_text)
    if not parts:
        return "", "empty", []
    if len(parts) == 1:
        return parts[0], "already_single", parts

    filtered = [x for x in parts if not is_ion_or_simple_inorganic(x)]
    filtered = [x for x in filtered if normalize_substrate_key(x) not in COFACTOR_TOKENS]

    unique = []
    seen = set()
    for item in filtered:
        key = normalize_substrate_key(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if len(unique) == 1:
        return unique[0], "resolved_single", parts
    if len(unique) == 0:
        return "", "all_filtered", parts
    return "", "multi_remaining", parts


def main():
    input_path = INPUT_ROOT / "sabio_tsv_raw_mutseq_v1.csv"
    output_path = OUTPUT_ROOT / "sabio_tsv_raw_subres_v1.csv"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    smiles_map, smiles_source = build_smiles_map()
    stats = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as src, output_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames)
        for extra in ["substrate_components_json", "substrate_resolution_status", "substrate_resolved_from_multi"]:
            if extra not in fieldnames:
                fieldnames.append(extra)
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            original_substrate = row.get("substrate", "")
            resolved_substrate, status, parts = resolve_single_substrate(original_substrate)
            row["substrate_components_json"] = json.dumps(parts, ensure_ascii=False)
            row["substrate_resolution_status"] = status
            row["substrate_resolved_from_multi"] = resolved_substrate if status == "resolved_single" else ""

            if status == "resolved_single":
                row["substrate"] = resolved_substrate

            if not row.get("smiles", "").strip() and row.get("substrate", "").strip():
                substrate_key = normalize_substrate_key(row["substrate"])
                smiles = smiles_map.get(substrate_key, "")
                if smiles:
                    row["smiles"] = smiles
                    row["smiles_source"] = smiles_source.get(substrate_key, "local")
                    stats["smiles_filled_after_resolution"] += 1

            writer.writerow(row)
            stats["rows"] += 1
            stats[f"substrate_resolution_status:{status}"] += 1
            if row.get("smiles", "").strip():
                stats["smiles_nonempty_final"] += 1

    print(output_path.name)
    for key, value in sorted(stats.items()):
        print(f"{key}\t{value}")


if __name__ == "__main__":
    main()
