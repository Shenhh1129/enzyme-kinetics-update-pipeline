import csv
import json
import re
from pathlib import Path

from parse_utils import (
    combine_parse_status,
    normalize_space,
    parse_ions,
    parse_mutation_and_type,
    parse_ph,
    parse_temperature,
)

STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"

BRENDA_JSON_PATH = INPUT_ROOT / "brenda_2026_1.json"

COMMON_COLUMNS = [
    "source_dataset",
    "source_table",
    "source_record_id",
    "source_record_label",
    "source_payload_json",
    "ec_number",
    "organism",
    "uniprot",
    "sequence",
    "sequence_source",
    "reaction_raw",
    "commentary",
    "substrate_raw",
    "substrate",
    "smiles_raw",
    "smiles",
    "kinetic_parameter",
    "kinetic_value_raw",
    "kinetic_value_num",
    "kinetic_unit",
    "enzyme_type",
    "mutation_raw",
    "mutation",
    "mutation_parse_status",
    "ph_raw",
    "ph",
    "ph_parse_status",
    "temperature_raw",
    "temperature",
    "temperature_parse_status",
    "ions_raw",
    "ions",
    "ions_parse_status",
    "parse_status",
]


TARGET_TABLES = {
    "km_value": "km",
    "turnover_number": "kcat",
}

def _brace_delta(text, state):
    delta = 0
    for ch in text:
        if state["in_string"]:
            if state["escape"]:
                state["escape"] = False
            elif ch == "\\":
                state["escape"] = True
            elif ch == '"':
                state["in_string"] = False
            continue
        if ch == '"':
            state["in_string"] = True
        elif ch == "{":
            delta += 1
        elif ch == "}":
            delta -= 1
    return delta


def iter_ec_objects(path):
    in_data = False
    current_key = None
    current_lines = []
    brace_level = 0
    state = {"in_string": False, "escape": False}

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not in_data:
                if '"data": {' in line:
                    in_data = True
                continue

            stripped = line.lstrip()
            if current_key is None:
                if stripped == "}," or stripped == "}":
                    break
                match = re.match(r'^"([^"]+)":\s*\{\s*$', stripped)
                if not match:
                    continue
                current_key = match.group(1)
                current_lines = ["{\n"]
                brace_level = 1
                state = {"in_string": False, "escape": False}
                continue

            current_lines.append(line)
            brace_level += _brace_delta(line, state)
            if brace_level == 0:
                obj_text = "".join(current_lines)
                end = obj_text.rfind("}")
                obj_text = obj_text[: end + 1]
                yield current_key, json.loads(obj_text)
                current_key = None
                current_lines = []


def parse_value_and_substrate(raw_value):
    raw_value = normalize_space(raw_value)
    if not raw_value:
        return "", "", None

    match = re.match(r"^(.*?)\s*\{(.*)\}\s*$", raw_value)
    if match:
        kinetic_value_raw = match.group(1).strip()
        substrate = match.group(2).strip()
    else:
        kinetic_value_raw = raw_value
        substrate = ""

    numeric_match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", kinetic_value_raw)
    kinetic_value_num = float(numeric_match.group(0)) if numeric_match else None
    return kinetic_value_raw, substrate, kinetic_value_num


def stringify_reference_list(refs):
    return "|".join(str(x) for x in (refs or []))


def protein_uniprots(protein_record):
    if not isinstance(protein_record, dict):
        return ""
    accessions = protein_record.get("accessions") or []
    return "|".join(str(x) for x in accessions)


def protein_organism(protein_record):
    if not isinstance(protein_record, dict):
        return ""
    return normalize_space(protein_record.get("organism", ""))


def choose_reaction_raw(item, reactions):
    if not isinstance(reactions, list):
        return ""

    item_proteins = {str(x) for x in (item.get("proteins") or []) if str(x)}
    item_refs = {str(x) for x in (item.get("references") or []) if str(x)}

    scored = []
    for idx, reaction in enumerate(reactions):
        if not isinstance(reaction, dict):
            continue
        value = normalize_space(reaction.get("value", ""))
        if not value:
            continue
        reaction_proteins = {str(x) for x in (reaction.get("proteins") or []) if str(x)}
        reaction_refs = {str(x) for x in (reaction.get("references") or []) if str(x)}
        score = (
            1 if item_proteins and reaction_proteins and item_proteins & reaction_proteins else 0,
            1 if item_refs and reaction_refs and item_refs & reaction_refs else 0,
            -idx,
        )
        scored.append((score, value))

    if not scored:
        return ""
    scored.sort(reverse=True)
    return scored[0][1]


def build_row(ec_number, table_name, item, proteins, reactions):
    commentary = normalize_space(item.get("comment", ""))
    enzyme_type, mutation_raw_token, mutation, mutation_parse_status = parse_mutation_and_type(commentary)
    mutation_raw_value = mutation_raw_token
    if mutation_parse_status == "fail" and commentary:
        mutation_raw_value = commentary
    ph, ph_parse_status = parse_ph(commentary)
    temperature, temperature_parse_status = parse_temperature(commentary)
    ions, ions_parse_status = parse_ions(commentary)

    protein_ids = item.get("proteins") or []
    protein_id = str(protein_ids[0]) if protein_ids else ""

    protein_record = proteins.get(protein_id, {})
    kinetic_value_raw, substrate, kinetic_value_num = parse_value_and_substrate(item.get("value", ""))
    source_record_id = (
        f"{ec_number}:{table_name}:{protein_id or 'noprotein'}:"
        f"{stringify_reference_list(item.get('references'))}:{kinetic_value_raw}:{substrate}"
    )

    return {
        "source_dataset": "BRENDA",
        "source_table": table_name,
        "source_record_id": source_record_id,
        "source_record_label": TARGET_TABLES[table_name],
        "source_payload_json": json.dumps(item, ensure_ascii=False, sort_keys=True),
        "ec_number": ec_number,
        "organism": protein_organism(protein_record),
        "uniprot": protein_uniprots(protein_record),
        "sequence": "",
        "sequence_source": "",
        "reaction_raw": choose_reaction_raw(item, reactions),
        "commentary": commentary,
        "substrate_raw": substrate,
        "substrate": substrate,
        "smiles_raw": "",
        "smiles": "",
        "kinetic_parameter": TARGET_TABLES[table_name],
        "kinetic_value_raw": kinetic_value_raw,
        "kinetic_value_num": kinetic_value_num,
        "kinetic_unit": "",
        "enzyme_type": enzyme_type,
        "mutation_raw": mutation_raw_value or commentary,
        "mutation": mutation,
        "mutation_parse_status": mutation_parse_status,
        "ph_raw": commentary,
        "ph": ph,
        "ph_parse_status": ph_parse_status,
        "temperature_raw": commentary,
        "temperature": temperature,
        "temperature_parse_status": temperature_parse_status,
        "ions_raw": commentary,
        "ions": ions,
        "ions_parse_status": ions_parse_status,
        "parse_status": combine_parse_status(
            mutation_parse_status,
            ph_parse_status,
            temperature_parse_status,
            ions_parse_status,
        ),
    }


def rebuild_brenda_raw(output_path, max_rows=None, progress_every=100):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output_path = output_path.with_suffix(output_path.suffix + ".tmp")
    total_rows = 0
    ec_count = 0
    with tmp_output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMMON_COLUMNS)
        writer.writeheader()

        for ec_number, ec_object in iter_ec_objects(BRENDA_JSON_PATH):
            ec_count += 1
            proteins = ec_object.get("protein", {}) or ec_object.get("proteins", {})
            reactions = ec_object.get("reaction", []) or ec_object.get("reactions", [])
            for table_name in TARGET_TABLES:
                for item in ec_object.get(table_name, []) or []:
                    writer.writerow(build_row(ec_number, table_name, item, proteins, reactions))
                    total_rows += 1
                    if max_rows and total_rows >= max_rows:
                        tmp_output_path.replace(output_path)
                        return total_rows
            if progress_every and ec_count % progress_every == 0:
                print(f"BRENDA processed {ec_count} EC objects, wrote {total_rows} rows")
    tmp_output_path.replace(output_path)
    return total_rows


def main():
    output_path = OUTPUT_ROOT / "brenda_raw.csv"
    total_rows = rebuild_brenda_raw(output_path)
    print(f"Wrote {total_rows} rows to {output_path}")


if __name__ == "__main__":
    main()
