import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from parse_utils import (
    normalize_temperature_text,
    parse_mutation_and_type,
    parse_ph_value,
    parse_temperature_value,
)


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

DLKCAT_PATH = INPUT_ROOT / "Kcat_combination_0918_wildtype_mutant.json"
INTENZY_PATH = INPUT_ROOT / "db_matched_pairs_pH.csv"
SKID_KCAT_PATH = INPUT_ROOT / "kcat_all_data_logscale_final_v1.csv"
SKID_KM_PATH = INPUT_ROOT / "Km_all_data_logscale_final_v1.csv"
UNIPROT_CACHE_PATH = INPUT_ROOT / "uniprot_sequence_cache_v1.csv"
SKID_LIGAND_PATH = INPUT_ROOT / "Ligands_all_final_v1.csv"

CATA_FILES = [
    INPUT_ROOT / "kcat-data_0.4simi-10fold.csv",
    INPUT_ROOT / "Km-data_0.4simi-10fold.csv",
    INPUT_ROOT / "kcat-over-Km-data_0.4simi-10fold.csv",
]

MASTER_COLUMNS = [
    "dataset_name",
    "parameter_name",
    "source_db",
    "source_release",
    "source_record_id",
    "record_id",
    "measurement_uid",
    "ec_number",
    "organism",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "sequence_source",
    "substrate",
    "smiles",
    "value",
    "unit",
    "ph",
    "temperature",
    "ions",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "parse_status",
    "mutation_apply_status",
]

INTENZY_PAIR_COLUMNS = [
    "pair_index",
    "select_key",
    "select_key_1",
    "ec_number",
    "uniprot",
    "organism",
    "substrate_raw",
    "substrate_resolved",
    "substrate_resolution_status",
    "substrate_components_json",
    "smiles",
    "smiles_source",
    "temperature",
    "pH",
    "clean_mut_wt",
    "mutation",
    "wt_sequence",
    "wt_sequence_source",
    "mut_sequence",
    "mut_sequence_source",
    "mut_sequence_status",
    "kcat_wt",
    "kcat_mut",
    "Km_wt",
    "Km_mut",
    "Resolution",
    "PDB_ID",
    "chainID",
]

INTENZY_LONG_COLUMNS = [
    "pair_index",
    "parameter_name",
    "enzyme_side",
    "source_record_id",
    "record_id",
    "measurement_uid",
    "ec_number",
    "organism",
    "uniprot",
    "enzyme_type",
    "mutation",
    "sequence",
    "sequence_source",
    "substrate",
    "smiles",
    "value",
    "unit",
    "ph",
    "temperature",
    "ions",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "parse_status",
    "mutation_apply_status",
]

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

SUB_PATTERN = re.compile(r"^([A-Z*])(\d+)([A-Z*])$")


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_blank(value):
    text = normalize_text(value)
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def normalize_sequence(value):
    value = canonical_blank(value).replace(" ", "").upper()
    return "" if value in {"", "-", "-----"} else value


def normalize_smiles(value):
    value = canonical_blank(value)
    return "" if value in {"", "-", "-----"} else value


def normalize_unit(value):
    value = normalize_text(value)
    return value.replace("s^(-1)", "s^-1").replace("鎺矯", "C")


def normalize_parameter_name(value):
    text = normalize_text(value).lower().replace(" ", "").replace("-", "_").replace("/", "_")
    aliases = {
        "kcat": "kcat",
        "km": "km",
        "kcat_km": "kcat_km",
        "kcatoverkm": "kcat_km",
        "ph": "ph",
        "temperature": "temperature",
        "temp": "temperature",
    }
    return aliases.get(text, text)


def normalize_enzyme_type(value):
    text = normalize_text(value).lower().replace(" ", "_")
    aliases = {
        "wt": "wildtype",
        "wild": "wildtype",
        "wild_type": "wildtype",
        "wildtype": "wildtype",
        "mut": "mutant",
        "mutant": "mutant",
        "variant": "mutant",
        "ambiguous": "ambiguous",
    }
    return aliases.get(text, text)


def normalize_substrate_key(value):
    value = normalize_text(value)
    value = value.lower()
    value = value.replace("鎺?", "掳")
    value = value.replace("掳", "deg").replace("潞", "deg")
    value = re.sub(r"[\u2010-\u2015\u2212]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ;,")


def make_id(prefix, *parts):
    payload = "|".join(normalize_text(x) for x in parts)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}", digest


def digest20(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def make_measurement_uid(row):
    payload = "|".join(
        [
            normalize_text(row.get("uniprot", "")),
            normalize_enzyme_type(row.get("enzyme_type", "")),
            normalize_text(row.get("mutation", "")),
            normalize_sequence(row.get("sequence", "")),
            normalize_text(row.get("substrate", "")),
            normalize_text(row.get("smiles", "")),
            normalize_parameter_name(row.get("parameter_name", "")),
            normalize_text(row.get("value", "")),
            normalize_text(row.get("ph", "")),
            normalize_text(row.get("temperature", "")),
        ]
    )
    return f"muid_{digest20(payload)}"


def make_record_id(row):
    payload = "|".join(
        [
            normalize_text(row.get("measurement_uid", "")),
            normalize_text(row.get("organism", "")),
            normalize_text(row.get("ions", "")),
        ]
    )
    return f"frid_{digest20(payload)}" if payload.strip("|") else ""


def finalize_master_row(row):
    finalized = dict(row)
    finalized["parameter_name"] = normalize_parameter_name(finalized.get("parameter_name", ""))
    finalized["enzyme_type"] = normalize_enzyme_type(finalized.get("enzyme_type", ""))
    finalized["sequence"] = normalize_sequence(finalized.get("sequence", ""))
    finalized["uniprot"] = canonical_blank(finalized.get("uniprot", ""))
    finalized["mutation"] = canonical_blank(finalized.get("mutation", ""))
    finalized["substrate"] = canonical_blank(finalized.get("substrate", ""))
    finalized["smiles"] = canonical_blank(finalized.get("smiles", ""))
    finalized["value"] = canonical_blank(finalized.get("value", ""))
    finalized["ph"] = canonical_blank(finalized.get("ph", ""))
    finalized["temperature"] = canonical_blank(finalized.get("temperature", ""))
    finalized["organism"] = canonical_blank(finalized.get("organism", ""))
    finalized["ions"] = canonical_blank(finalized.get("ions", ""))
    finalized["measurement_uid"] = make_measurement_uid(finalized)
    finalized["record_id"] = make_record_id(finalized)
    return finalized


def finalize_master_rows(rows):
    return [finalize_master_row(row) for row in rows]


def write_rows(path, fieldnames, rows):
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_uniprot_cache():
    cache = {}
    if not UNIPROT_CACHE_PATH.exists():
        return cache
    with UNIPROT_CACHE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            uniprot = canonical_blank(row.get("uniprot", "")).upper()
            sequence = normalize_sequence(row.get("sequence", ""))
            if uniprot and sequence:
                cache[uniprot] = sequence
    return cache


def build_sequence_map():
    seq_map = {}
    seq_source = {}

    for path in CATA_FILES:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        uniprot_col = ""
        sequence_col = ""
        for candidate in ["UniProtID", "uniprot", "UniProt_ID"]:
            if candidate in df.columns:
                uniprot_col = candidate
                break
        for candidate in ["Sequence", "sequence"]:
            if candidate in df.columns:
                sequence_col = candidate
                break
        if not uniprot_col or not sequence_col:
            continue
        for _, row in df.iterrows():
            uniprot = canonical_blank(row.get(uniprot_col, "")).upper()
            sequence = normalize_sequence(row.get(sequence_col, ""))
            if uniprot and sequence and uniprot not in seq_map:
                seq_map[uniprot] = sequence
                seq_source[uniprot] = "local_catapro"

    for uniprot, sequence in build_uniprot_cache().items():
        if uniprot not in seq_map:
            seq_map[uniprot] = sequence
            seq_source[uniprot] = "uniprot_cache"

    return seq_map, seq_source


def build_smiles_map():
    smiles_map = {}
    smiles_source = {}

    for path in CATA_FILES:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_smiles(row.get("Smiles", ""))
            if substrate and smiles and substrate not in smiles_map:
                smiles_map[substrate] = smiles
                smiles_source[substrate] = "local_catapro"

    if DLKCAT_PATH.exists():
        with DLKCAT_PATH.open("r", encoding="utf-8") as handle:
            rows = json.load(handle)
        for row in rows:
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_smiles(row.get("Smiles", ""))
            if substrate and smiles and substrate not in smiles_map:
                smiles_map[substrate] = smiles
                smiles_source[substrate] = "local_dlkcat"

    if SKID_LIGAND_PATH.exists():
        df = pd.read_csv(SKID_LIGAND_PATH, sep="\t")
        for _, row in df.iterrows():
            substrate = normalize_substrate_key(row.get("Substrate", ""))
            smiles = normalize_smiles(row.get("SMILES", ""))
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


def parse_uniprots(value):
    raw = canonical_blank(value).replace("|", " ")
    if not raw:
        return []
    tokens = []
    for part in raw.split():
        token = canonical_blank(part).upper()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def parse_mutation_value(clean_mut_wt):
    text = canonical_blank(clean_mut_wt)
    if not text:
        return ""
    _, _, mutation, _ = parse_mutation_and_type(text)
    return mutation or text


def apply_substitutions(sequence, mutation_text):
    sequence = normalize_sequence(sequence)
    mutation_text = canonical_blank(mutation_text)
    if not sequence:
        return "", "missing_sequence"
    if not mutation_text:
        return "", "missing_mutation"

    tokens = [part.strip() for part in mutation_text.split("|") if part.strip()]
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


def lookup_uniprot_sequence(uniprot_value, seq_map, seq_source):
    for accession in parse_uniprots(uniprot_value):
        sequence = seq_map.get(accession, "")
        if sequence:
            return sequence, seq_source.get(accession, "")
    return "", ""


def build_dlkcat_master():
    with DLKCAT_PATH.open("r", encoding="utf-8") as handle:
        records = json.load(handle)

    rows = []
    for idx, row in enumerate(records, start=1):
        record_id, measurement_uid = make_id(
            "DLKcat",
            row.get("ECNumber", ""),
            row.get("Organism", ""),
            row.get("Substrate", ""),
            row.get("Sequence", ""),
            row.get("Type", ""),
            row.get("Value", ""),
            row.get("Unit", ""),
        )
        rows.append(
            {
                "dataset_name": "DLKcat",
                "parameter_name": "kcat",
                "source_db": "DLKcat",
                "source_release": "legacy_json",
                "source_record_id": f"DLKcat_kcat_{idx}",
                "record_id": record_id,
                "measurement_uid": measurement_uid,
                "ec_number": normalize_text(row.get("ECNumber", "")),
                "organism": normalize_text(row.get("Organism", "")),
                "uniprot": "",
                "enzyme_type": "wild" if normalize_text(row.get("Type", "")).lower() == "wildtype" else "mutant",
                "mutation": "",
                "sequence": normalize_sequence(row.get("Sequence", "")),
                "sequence_source": "source_dataset",
                "substrate": normalize_text(row.get("Substrate", "")),
                "smiles": normalize_smiles(row.get("Smiles", "")),
                "value": normalize_text(row.get("Value", "")),
                "unit": normalize_unit(row.get("Unit", "")),
                "ph": "",
                "temperature": "",
                "ions": "",
                "reaction_raw": "",
                "commentary": "",
                "substrate_raw": normalize_text(row.get("Substrate", "")),
                "parse_status": "empty",
                "mutation_apply_status": "not_applicable",
            }
        )

    rows = finalize_master_rows(rows)
    write_rows(OUTPUT_ROOT / "DLKcat_kcat_master_v1.csv", MASTER_COLUMNS, rows)
    return len(rows)


def parse_skid_enzyme_type(mutant_value, mutation_value):
    mutant_value = normalize_text(mutant_value).lower()
    mutation_value = normalize_text(mutation_value)
    if mutant_value in {"no", "n", "wild", "wildtype"} or mutation_value in {"", "-", "-----"}:
        return "wild", ""
    _, _, mutation, _ = parse_mutation_and_type(mutation_value)
    if mutation:
        return "mutant", mutation
    return "mutant", ""


def build_skid_rows(path, parameter_name, value_column, unit):
    df = pd.read_csv(path, sep="\t", encoding="utf-8")
    rows = []
    for idx, row in df.iterrows():
        enzyme_type, mutation = parse_skid_enzyme_type(row.get("Mutant", ""), row.get("Mutation", ""))
        ph, _ = parse_ph_value(row.get("pH", ""))
        temperature_raw = normalize_temperature_text(row.get("Temperature", ""))
        temperature, _ = parse_temperature_value(temperature_raw)
        record_id, measurement_uid = make_id(
            "SKiD",
            idx,
            row.get("EC_number", ""),
            row.get("UniProt_ID", ""),
            row.get("Substrate", ""),
            row.get(value_column, ""),
        )
        rows.append(
            {
                "dataset_name": "SKiD",
                "parameter_name": parameter_name,
                "source_db": "SKiD",
                "source_release": "final_csv_v1",
                "source_record_id": f"SKiD_{parameter_name}_{idx+1}",
                "record_id": record_id,
                "measurement_uid": measurement_uid,
                "ec_number": normalize_text(row.get("EC_number", "")),
                "organism": normalize_text(row.get("Organism_name", "")),
                "uniprot": normalize_text(row.get("UniProt_ID", "")),
                "enzyme_type": enzyme_type,
                "mutation": mutation,
                "sequence": "",
                "sequence_source": "",
                "substrate": normalize_text(row.get("Substrate", "")),
                "smiles": normalize_smiles(row.get("Substrate_SMILES", "")),
                "value": normalize_text(row.get(value_column, "")),
                "unit": unit,
                "ph": ph,
                "temperature": temperature,
                "ions": "",
                "reaction_raw": "",
                "commentary": normalize_text(row.get("References", "")),
                "substrate_raw": normalize_text(row.get("Substrate", "")),
                "parse_status": "partial",
                "mutation_apply_status": "not_applied",
            }
        )
    return rows


def build_skid_masters():
    kcat_rows = build_skid_rows(SKID_KCAT_PATH, "kcat", "kcat_value", "s^-1")
    km_rows = build_skid_rows(SKID_KM_PATH, "km", "Km_value", "mM")
    kcat_rows = finalize_master_rows(kcat_rows)
    km_rows = finalize_master_rows(km_rows)
    write_rows(OUTPUT_ROOT / "SKiD_kcat_master_v1.csv", MASTER_COLUMNS, kcat_rows)
    write_rows(OUTPUT_ROOT / "SKiD_km_master_v1.csv", MASTER_COLUMNS, km_rows)
    return len(kcat_rows), len(km_rows)


def build_intenzy_pair_commentary(row):
    parts = []
    resolution = canonical_blank(row.get("Resolution", ""))
    mutation = canonical_blank(row.get("clean_mut_wt", ""))
    pdb_id = canonical_blank(row.get("PDB_ID", ""))
    chain_id = canonical_blank(row.get("chainID", ""))
    if resolution:
        parts.append(f"Resolution={resolution}")
    if pdb_id:
        parts.append(f"PDB_ID={pdb_id}")
    if chain_id:
        parts.append(f"chain={chain_id}")
    if mutation:
        parts.append(f"paired_mutation={mutation}")
    return "; ".join(parts)


def build_intenzy_pairs(df, seq_map, seq_source, smiles_map, smiles_source):
    stats = Counter()
    pair_rows = []

    for idx, row in df.iterrows():
        substrate_raw = canonical_blank(row.get("substrate_kinetics", ""))
        resolved_substrate, resolution_status, components = resolve_single_substrate(substrate_raw)
        stats[f"substrate_resolution:{resolution_status}"] += 1
        if resolution_status not in {"already_single", "resolved_single"}:
            stats["dropped_multi_or_non_small"] += 1
            continue

        substrate_final = resolved_substrate or substrate_raw
        substrate_key = normalize_substrate_key(substrate_final)
        smiles = smiles_map.get(substrate_key, "")
        if not smiles:
            stats["dropped_smiles_unresolved"] += 1
            continue

        ph = canonical_blank(row.get("pH", ""))
        temperature = canonical_blank(row.get("temperature", ""))
        clean_mut_wt = canonical_blank(row.get("clean_mut_wt", ""))
        mutation = parse_mutation_value(clean_mut_wt)
        wt_sequence, wt_source = lookup_uniprot_sequence(row.get("uniprot", ""), seq_map, seq_source)
        mut_sequence, mut_status = apply_substitutions(wt_sequence, mutation)
        mut_source = "uniprot_cache|mutation_applied" if mut_status in {"success", "no_change"} else ""

        pair_rows.append(
            {
                "pair_index": idx,
                "select_key": canonical_blank(row.get("select_key", "")),
                "select_key_1": canonical_blank(row.get("select_key_1", "")),
                "ec_number": canonical_blank(row.get("ec_number", "")),
                "uniprot": canonical_blank(row.get("uniprot", "")),
                "organism": canonical_blank(row.get("organism", "")),
                "substrate_raw": substrate_raw,
                "substrate_resolved": substrate_final,
                "substrate_resolution_status": resolution_status,
                "substrate_components_json": json.dumps(components, ensure_ascii=False),
                "smiles": smiles,
                "smiles_source": smiles_source.get(substrate_key, ""),
                "temperature": temperature,
                "pH": ph,
                "clean_mut_wt": clean_mut_wt,
                "mutation": mutation,
                "wt_sequence": wt_sequence,
                "wt_sequence_source": wt_source,
                "mut_sequence": mut_sequence if mut_status in {"success", "no_change"} else "",
                "mut_sequence_source": mut_source,
                "mut_sequence_status": mut_status,
                "kcat_wt": canonical_blank(row.get("kcat_wt", "")),
                "kcat_mut": canonical_blank(row.get("kcat_mut", "")),
                "Km_wt": canonical_blank(row.get("Km_wt", "")),
                "Km_mut": canonical_blank(row.get("Km_mut", "")),
                "Resolution": canonical_blank(row.get("Resolution", "")),
                "PDB_ID": canonical_blank(row.get("PDB_ID", "")),
                "chainID": canonical_blank(row.get("chainID", "")),
            }
        )
        stats["pairs_kept"] += 1
        if wt_sequence:
            stats["wt_sequence_filled"] += 1
        else:
            stats["wt_sequence_missing"] += 1
        stats[f"mut_sequence_status:{mut_status}"] += 1

    return pair_rows, stats


def build_intenzy_long_rows(pair_rows):
    kcat_rows = []
    km_rows = []

    for pair in pair_rows:
        commentary = build_intenzy_pair_commentary(pair)
        ph, _ = parse_ph_value(pair.get("pH", ""))
        temperature, _ = parse_temperature_value(pair.get("temperature", ""))

        tasks = [
            ("kcat", "kcat_wt", "kcat_mut", "s^-1", kcat_rows),
            ("km", "Km_wt", "Km_mut", "M", km_rows),
        ]

        for parameter_name, wt_col, mut_col, unit, bucket in tasks:
            wt_value = canonical_blank(pair.get(wt_col, ""))
            mut_value = canonical_blank(pair.get(mut_col, ""))

            if wt_value:
                bucket.append(
                    {
                        "pair_index": pair["pair_index"],
                        "parameter_name": parameter_name,
                        "enzyme_side": "wt",
                        "source_record_id": f"{pair['select_key_1']}|wt|{parameter_name}",
                        "record_id": f"IntEnzyDB:{parameter_name}:wt:{pair['pair_index']}",
                        "measurement_uid": f"IntEnzyDB|{parameter_name}|wt|{pair['pair_index']}",
                        "ec_number": pair["ec_number"],
                        "organism": pair["organism"],
                        "uniprot": pair["uniprot"],
                        "enzyme_type": "wild",
                        "mutation": "",
                        "sequence": pair["wt_sequence"],
                        "sequence_source": pair["wt_sequence_source"],
                        "substrate": pair["substrate_resolved"],
                        "smiles": pair["smiles"],
                        "value": wt_value,
                        "unit": unit,
                        "ph": ph,
                        "temperature": temperature,
                        "ions": "",
                        "reaction_raw": "",
                        "commentary": commentary,
                        "substrate_raw": pair["substrate_raw"],
                        "parse_status": "empty",
                        "mutation_apply_status": "not_applied",
                    }
                )

            if mut_value and pair["mut_sequence"]:
                bucket.append(
                    {
                        "pair_index": pair["pair_index"],
                        "parameter_name": parameter_name,
                        "enzyme_side": "mut",
                        "source_record_id": f"{pair['select_key']}|mut|{parameter_name}",
                        "record_id": f"IntEnzyDB:{parameter_name}:mut:{pair['pair_index']}",
                        "measurement_uid": f"IntEnzyDB|{parameter_name}|mut|{pair['pair_index']}",
                        "ec_number": pair["ec_number"],
                        "organism": pair["organism"],
                        "uniprot": pair["uniprot"],
                        "enzyme_type": "mutant",
                        "mutation": pair["mutation"],
                        "sequence": pair["mut_sequence"],
                        "sequence_source": pair["mut_sequence_source"],
                        "substrate": pair["substrate_resolved"],
                        "smiles": pair["smiles"],
                        "value": mut_value,
                        "unit": unit,
                        "ph": ph,
                        "temperature": temperature,
                        "ions": "",
                        "reaction_raw": "",
                        "commentary": commentary,
                        "substrate_raw": pair["substrate_raw"],
                        "parse_status": "partial",
                        "mutation_apply_status": pair["mut_sequence_status"],
                    }
                )

    return kcat_rows, km_rows


def map_long_rows_to_master(long_rows):
    master_rows = []
    for row in long_rows:
        master_rows.append(
            {
                "dataset_name": "IntEnzy",
                "parameter_name": row["parameter_name"],
                "source_db": "IntEnzyDB",
                "source_release": "db_matched_pairs_pH",
                "source_record_id": row["source_record_id"],
                "record_id": row["record_id"],
                "measurement_uid": row["measurement_uid"],
                "ec_number": row["ec_number"],
                "organism": row["organism"],
                "uniprot": row["uniprot"],
                "enzyme_type": row["enzyme_type"],
                "mutation": row["mutation"],
                "sequence": row["sequence"],
                "sequence_source": row["sequence_source"],
                "substrate": row["substrate"],
                "smiles": row["smiles"],
                "value": row["value"],
                "unit": row["unit"],
                "ph": row["ph"],
                "temperature": row["temperature"],
                "ions": row["ions"],
                "reaction_raw": row["reaction_raw"],
                "commentary": row["commentary"],
                "substrate_raw": row["substrate_raw"],
                "parse_status": row["parse_status"],
                "mutation_apply_status": row["mutation_apply_status"],
            }
        )
    return master_rows


def build_intenzy_masters():
    df = pd.read_csv(INTENZY_PATH)
    seq_map, seq_source = build_sequence_map()
    smiles_map, smiles_source = build_smiles_map()
    pair_rows, stats = build_intenzy_pairs(df, seq_map, seq_source, smiles_map, smiles_source)
    kcat_long_rows, km_long_rows = build_intenzy_long_rows(pair_rows)
    kcat_master_rows = map_long_rows_to_master(kcat_long_rows)
    km_master_rows = map_long_rows_to_master(km_long_rows)
    kcat_master_rows = finalize_master_rows(kcat_master_rows)
    km_master_rows = finalize_master_rows(km_master_rows)

    write_rows(OUTPUT_ROOT / "IntEnzy_pairs_filtered_v1.csv", INTENZY_PAIR_COLUMNS, pair_rows)
    write_rows(OUTPUT_ROOT / "IntEnzy_kcat_long_v1.csv", INTENZY_LONG_COLUMNS, kcat_long_rows)
    write_rows(OUTPUT_ROOT / "IntEnzy_km_long_v1.csv", INTENZY_LONG_COLUMNS, km_long_rows)
    write_rows(OUTPUT_ROOT / "IntEnzy_kcat_master_v1.csv", MASTER_COLUMNS, kcat_master_rows)
    write_rows(OUTPUT_ROOT / "IntEnzy_km_master_v1.csv", MASTER_COLUMNS, km_master_rows)
    return stats, len(kcat_master_rows), len(km_master_rows)


def main():
    dlk_rows = build_dlkcat_master()
    skid_kcat_rows, skid_km_rows = build_skid_masters()
    int_stats, int_kcat_rows, int_km_rows = build_intenzy_masters()

    print(f"DLKcat_kcat_master_v1.csv\t{dlk_rows}")
    print(f"SKiD_kcat_master_v1.csv\t{skid_kcat_rows}")
    print(f"SKiD_km_master_v1.csv\t{skid_km_rows}")
    print(f"IntEnzy_kcat_master_v1.csv\t{int_kcat_rows}")
    print(f"IntEnzy_km_master_v1.csv\t{int_km_rows}")
    for key, value in sorted(int_stats.items()):
        print(f"IntEnzy\t{key}\t{value}")


if __name__ == "__main__":
    main()
