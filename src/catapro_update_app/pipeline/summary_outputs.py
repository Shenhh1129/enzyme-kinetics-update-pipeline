from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from catapro_update_app.io.paths import ensure_dir
from catapro_update_app.pipeline.formal import ensure_formal_schema, normalize_text
from catapro_update_app.rules.registry import FORMAL_ENRICHED_COLUMNS


@dataclass(frozen=True)
class SummaryBundle:
    counts: pd.DataFrame
    summary_text: str
    mutation_kcat: pd.DataFrame
    mutation_km: pd.DataFrame
    empty_kcat: pd.DataFrame
    empty_km: pd.DataFrame
    unit_kcat: pd.DataFrame
    unit_km: pd.DataFrame


def _filter_parameter(frame: pd.DataFrame, parameter_name: str) -> pd.DataFrame:
    working = ensure_formal_schema(frame)
    return working.loc[working["parameter_name"].fillna("").astype(str).str.lower() == parameter_name].copy()


def _mutation_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame["mutation"].fillna("").astype(str).str.strip().ne("")].copy()


def _ph_temperature_empty_rows(frame: pd.DataFrame) -> pd.DataFrame:
    ph_blank = frame["ph"].fillna("").astype(str).str.strip().eq("")
    temp_blank = frame["temperature"].fillna("").astype(str).str.strip().eq("")
    return frame.loc[ph_blank & temp_blank].copy()


def _unit_audit_rows(frame: pd.DataFrame, parameter_name: str) -> pd.DataFrame:
    working = frame.copy()
    expected = {
        "kcat": {"s^-1"},
        "km": {"mM", "M"},
        "kcat_km": {"M^-1*s^-1"},
    }.get(parameter_name, set())

    statuses: list[str] = []
    reasons: list[str] = []
    for _, row in working.iterrows():
        unit = normalize_text(row.get("unit", ""))
        if not unit:
            statuses.append("flagged")
            reasons.append("missing_unit")
        elif unit not in expected:
            statuses.append("flagged")
            reasons.append("unexpected_unit")
        else:
            statuses.append("ok")
            reasons.append("")
    working["unit_audit_status"] = statuses
    working["unit_audit_reason"] = reasons
    return working.loc[working["unit_audit_status"] != "ok"].copy()


def build_summary_bundle(merged_kcat: pd.DataFrame, merged_km: pd.DataFrame) -> SummaryBundle:
    kcat = _filter_parameter(merged_kcat, "kcat")
    km = _filter_parameter(merged_km, "km")
    mutation_kcat = _mutation_rows(kcat)
    mutation_km = _mutation_rows(km)
    empty_kcat = _ph_temperature_empty_rows(kcat)
    empty_km = _ph_temperature_empty_rows(km)
    unit_kcat = _unit_audit_rows(kcat, "kcat")
    unit_km = _unit_audit_rows(km, "km")

    counts_rows = [
        {"section": "inputs", "metric": "kcat_final_v6_rows", "value": len(kcat)},
        {"section": "inputs", "metric": "km_final_v6_rows", "value": len(km)},
        {"section": "kcat_subsets", "metric": "mutation_rows", "value": len(mutation_kcat)},
        {"section": "kcat_subsets", "metric": "ph_temperature_empty_rows", "value": len(empty_kcat)},
        {"section": "kcat_unit_audit", "metric": "unit_audit_rows", "value": len(unit_kcat)},
        {"section": "kcat_unit_audit", "metric": "missing_unit_rows", "value": int((unit_kcat["unit_audit_reason"] == "missing_unit").sum())},
        {"section": "kcat_unit_audit", "metric": "unexpected_unit_rows", "value": int((unit_kcat["unit_audit_reason"] == "unexpected_unit").sum())},
        {"section": "km_subsets", "metric": "mutation_rows", "value": len(mutation_km)},
        {"section": "km_subsets", "metric": "ph_temperature_empty_rows", "value": len(empty_km)},
        {"section": "km_unit_audit", "metric": "unit_audit_rows", "value": len(unit_km)},
        {"section": "km_unit_audit", "metric": "missing_unit_rows", "value": int((unit_km["unit_audit_reason"] == "missing_unit").sum())},
        {"section": "km_unit_audit", "metric": "unexpected_unit_rows", "value": int((unit_km["unit_audit_reason"] == "unexpected_unit").sum())},
    ]
    counts = pd.DataFrame(counts_rows, columns=("section", "metric", "value"))
    summary_text = "\n".join(
        [
            "# CataPro V6 Summary",
            "",
            "## inputs",
            f"- kcat_final_v6_rows: {len(kcat)}",
            f"- km_final_v6_rows: {len(km)}",
            "",
            "## kcat_subsets",
            f"- mutation_rows: {len(mutation_kcat)}",
            f"- ph_temperature_empty_rows: {len(empty_kcat)}",
            "",
            "## kcat_unit_audit",
            f"- unit_audit_rows: {len(unit_kcat)}",
            f"- missing_unit_rows: {int((unit_kcat['unit_audit_reason'] == 'missing_unit').sum())}",
            f"- unexpected_unit_rows: {int((unit_kcat['unit_audit_reason'] == 'unexpected_unit').sum())}",
            "",
            "## km_subsets",
            f"- mutation_rows: {len(mutation_km)}",
            f"- ph_temperature_empty_rows: {len(empty_km)}",
            "",
            "## km_unit_audit",
            f"- unit_audit_rows: {len(unit_km)}",
            f"- missing_unit_rows: {int((unit_km['unit_audit_reason'] == 'missing_unit').sum())}",
            f"- unexpected_unit_rows: {int((unit_km['unit_audit_reason'] == 'unexpected_unit').sum())}",
        ]
    )
    return SummaryBundle(counts, summary_text, mutation_kcat, mutation_km, empty_kcat, empty_km, unit_kcat, unit_km)


def write_summary_bundle(output_root: Path, bundle: SummaryBundle) -> tuple[Path, ...]:
    mutation_root = ensure_dir(output_root / "mutation")
    empty_root = ensure_dir(output_root / "ph_tem_empty")
    unit_root = ensure_dir(output_root / "unit")
    written = (
        output_root / "summary_v6_counts.csv",
        output_root / "summary_v6.txt",
        mutation_root / "kcat_mutation_rows_v6.csv",
        mutation_root / "km_mutation_rows_v6.csv",
        empty_root / "kcat_ph_temperature_empty_v6.csv",
        empty_root / "km_ph_temperature_empty_v6.csv",
        unit_root / "kcat_unit_audit_v6.csv",
        unit_root / "km_unit_audit_v6.csv",
    )
    bundle.counts.to_csv(written[0], index=False)
    written[1].write_text(bundle.summary_text, encoding="utf-8")
    bundle.mutation_kcat.to_csv(written[2], index=False)
    bundle.mutation_km.to_csv(written[3], index=False)
    bundle.empty_kcat.to_csv(written[4], index=False)
    bundle.empty_km.to_csv(written[5], index=False)
    bundle.unit_kcat.to_csv(written[6], index=False)
    bundle.unit_km.to_csv(written[7], index=False)
    return written
