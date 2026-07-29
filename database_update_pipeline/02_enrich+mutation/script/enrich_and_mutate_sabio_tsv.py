from pathlib import Path

from local_enrich import build_sequence_map, build_smiles_map, enrich_file
from mutant_sequence_rebuild import rebuild_file


STEP_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = STEP_ROOT / "input"
OUTPUT_ROOT = STEP_ROOT / "output"


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    seq_map, seq_source = build_sequence_map()
    smiles_map, smiles_source = build_smiles_map()

    enriched_input = INPUT_ROOT / "sabio_tsv_raw_v1.csv"
    enriched_output = OUTPUT_ROOT / "sabio_tsv_raw_local_enriched_v1.csv"
    mutseq_output = OUTPUT_ROOT / "sabio_tsv_raw_mutseq_v1.csv"

    enrich_stats = enrich_file(
        enriched_input,
        enriched_output,
        seq_map,
        seq_source,
        smiles_map,
        smiles_source,
    )
    print("sabio_tsv_raw_local_enriched_v1.csv", dict(enrich_stats))

    mut_stats = rebuild_file(enriched_output, mutseq_output)
    print("sabio_tsv_raw_mutseq_v1.csv", dict(mut_stats))


if __name__ == "__main__":
    main()
