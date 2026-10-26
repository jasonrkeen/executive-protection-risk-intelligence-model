"""Immutable, offline scoring-integrity *candidate* on fictional frozen data.

This is a separate research demonstration; no production model result, input,
threshold, posture rule or risk band is updated by executing this module.
"""
from __future__ import annotations

from dataclasses import replace
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pandas as pd

from src.offline_synthetic_demo import ROOT, FIXTURES
from src.methodology_red_team import verify_demo, cohort_dependence
from src.scoring_integrity_candidate import (
    FixedReference, VERSION, INDICATOR, load_fixed_reference,
    merge_fictional_evidence, score_frozen_homicide,
    shadow_country_comparison,
)
from src.scoring_integrity_views import build_candidate_pdf

DEMO_VERSION = "SCORING-INTEGRITY-FIXED-REFERENCE-SYNTHETIC-v1"
DEMO_STATUS = "PASS_SYNTHETIC_SHADOW_NOT_OPERATIONAL_VALIDATION"
REFERENCE_FILE = FIXTURES / "scoring_reference.json"
EVIDENCE_FILE = FIXTURES / "homicide_source_evidence.csv"
SOURCE_MODULES = (
    "src/scoring_integrity_candidate.py",
    "src/scoring_integrity_demo.py",
    "src/scoring_integrity_views.py",
)


def fingerprint(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence_scenario(
    inputs: pd.DataFrame, metadata: pd.DataFrame,
    reference: FixedReference, scenario: str,
) -> pd.DataFrame:
    """Hold the frozen reference constant and introduce one intentional fault."""
    values = inputs.copy()
    source = metadata.copy()
    affected = source.loc[source["country"].eq("Testland")].index
    if len(affected) != 1:
        raise ValueError("Expected one fictional Testland source declaration")
    index = affected[0]
    country_mask = values["country"].eq("Testland")
    if scenario == "ALL_MISSING":
        values[INDICATOR] = np.nan
        source["source_status"] = "unavailable"
        source["source_year"] = np.nan
        source["source_ref"] = ""
    elif scenario == "ONE_MISSING":
        values.loc[country_mask, INDICATOR] = np.nan
        source.at[index, "source_status"] = "unavailable"
        source.at[index, "source_year"] = np.nan
        source.at[index, "source_ref"] = ""
    elif scenario == "ONE_STALE":
        source.at[index, "source_year"] = reference.assessment_year - reference.max_source_age_years - 1
    elif scenario == "ONE_CONFLICTING":
        source.at[index, "source_status"] = "conflicting"
    elif scenario == "ONE_IMPUTED":
        source.at[index, "source_status"] = "imputed"
    elif scenario == "ONE_INVALID_NEGATIVE":
        values.loc[country_mask, INDICATOR] = -1
    else:
        raise ValueError(f"Unknown synthetic fault scenario: {scenario}")
    return score_frozen_homicide(
        merge_fictional_evidence(values, source), reference
    )


def compare_legacy_and_frozen_outlier(
    inputs: pd.DataFrame, metadata: pd.DataFrame,
    reference: FixedReference,
) -> pd.DataFrame:
    """Contrast cohort-dependent legacy min-max with fixed-range candidate."""
    legacy = cohort_dependence(inputs)
    selected = legacy.loc[
        legacy["scenario"].eq("ORIGINAL_VS_FICTIONAL_EXTREME_COMPARATOR")
    ].copy()
    known = score_frozen_homicide(
        merge_fictional_evidence(inputs, metadata), reference
    )
    extreme = float(pd.to_numeric(inputs[INDICATOR]).max()) * 10
    extra = pd.DataFrame([{
        "country": "Fictional Extreme Comparator (not real)",
        INDICATOR: extreme,
        "source_status": "observed",
        "source_year": reference.baseline_year,
        "source_ref": "synthetic://homicide-fixture/EXTRA",
        "unit": reference.unit,
    }])
    combined = pd.concat([
        merge_fictional_evidence(inputs, metadata), extra
    ], ignore_index=True)
    scored = score_frozen_homicide(combined, reference)
    original_fixed = scored[scored["country"].isin(known["country"])]
    assert original_fixed["candidate_component_score"].notna().all()
    for row in known.itertuples(index=False):
        new = original_fixed.loc[
            original_fixed["country"].eq(row.country), "candidate_component_score"
        ].iloc[0]
        if new != row.candidate_component_score:
            raise ValueError("Fixed-scoring change under fictional cohort expansion")
    combined_table = selected.merge(
        known[["country", "candidate_component_score", "candidate_score_status"]],
        on="country", validate="one_to_one",
    ).sort_values("country").reset_index(drop=True)
    combined_table["fixed_reference_score_after_expansion"] = (
        combined_table["candidate_component_score"]
    )
    combined_table["fixed_reference_score_change"] = 0.0
    combined_table["new_extreme_comparator_score_status"] = (
        scored.loc[
            scored["country"].eq("Fictional Extreme Comparator (not real)"),
            "candidate_score_status"
        ].iloc[0]
    )
    combined_table["full_composite_recomputed"] = False
    return combined_table


def decision_record(
    reference: FixedReference,
    legacy: pd.DataFrame,
    observed: pd.DataFrame,
    missing: pd.DataFrame,
    outlier: pd.DataFrame,
) -> str:
    observed_score = outlier.loc[outlier["country"].eq("Testland")].iloc[0]
    missing_cases = int(missing["candidate_score_status"].str.startswith("BLOCKED_").sum())
    return (
        "# Synthetic Scoring-Integrity Candidate - Decision Record\n\n"
        "**Status: RESEARCH SHADOW ONLY; candidate is not adopted as the live model.**\n"
        "The current historical risk model and public baseline are unchanged.\n\n"
        "## Issue\n\n"
        "The legacy homicide index can appear neutral when evidence is wholly "
        "absent and changes when the min-max comparison population changes. "
        "Neither an imputed value nor cohort-relative normalization is a "
        "measured safety improvement.\n\n"
        "## Compared options\n\n"
        "| Option | Benefit | Material limitation | Disposition |\n"
        "| --- | --- | --- | --- |\n"
        "| Retain existing rolling min-max and implicit fills | Historical backward compatibility | New countries remap existing values; missing can yield 50 | Preserve old outputs, but **do not certify** |\n"
        "| Fixed fictional reference with observed-only inputs | No score drift when cohort changes; missing evidence withheld | Chosen anchors are toy-only; real calibration unknown | **Research candidate** |\n"
        "| Fixed reference with silent clipping or imputed 50 | Convenient uninterrupted numeric output | Hides out-of-range data and missingness | **Rejected** |\n\n"
        "## Frozen synthetic reference\n\n"
        f"- ID: \`{reference.reference_id}\`; assessment year {reference.assessment_year}; "
        f"toy baseline {reference.baseline_year}.\n"
        f"- Homicide indicator range: {reference.reference_min:g} to "
        f"{reference.reference_max:g} per 100,000 (two fictional countries).\n"
        f"- Provisional source age allowance: {reference.max_source_age_years} "
        "calendar years, **not** an externally validated source policy.\n"
        "- Sources must carry status, observation year, units and a reference. "
        "Unavailable, stale, imputed, conflicting, missing or out-of-range "
        "readings yield **WITHHELD**, no candidate numerical score, no risk band.\n\n"
        "## Reproducible toy findings\n\n"
        f"- Adding an invented outlier changed Testland's legacy homicide "
        f"index from {observed_score['original_component_score']:.2f} to "
        f"{observed_score['expanded_cohort_component_score']:.2f}; the "
        f"fixed-reference score remained {observed_score['candidate_component_score']:.2f}. "
        "The added comparator is blocked as outside the toy reference.\n"
        f"- In the all-missing test, {missing_cases} of {len(missing)} fictional "
        "observations produced blocked candidate scores. The historical code "
        "might still produce a numerical index of 50 for those absent measures.\n"
        f"- The historical country-score table has {len(legacy)} rows, all retained "
        "for comparison; the candidate issues **no** calibrated risk bands, "
        "postures or travel decisions.\n\n"
        "## Integrity rules and non-claims\n\n"
        "- No data-dependent reference refitting during scenario runs; comparison "
        "cohort changes cannot change in-range observed-country scores.\n"
        "- Original component scores and severity uplift are frozen. The numerical "
        "shadow composite is **not** a whole-model recalculation and contains "
        "unverified other components; it must not be published as a risk estimate.\n"
        "- The candidate rejects unsourced zero, missing source vintages, future "
        "observations, invalid units, duplicate country keys and malformed source status.\n"
        "- A synthetic source declaration is not an authenticated provider record. "
        "No real ACLED/WGI provenance or true predictive validity is established.\n\n"
        "## Gates before proposing any production change\n\n"
        "1. Independently review and approve a real-world normalization reference "
        "population and freeze its source data, collection period and source limits.\n"
        "2. Validate source-specific coverage, extraction receipt, country-year "
        "vintage and WGI uncertainty; agree a reasonable maximum age for each measure.\n"
        "3. Recompute *all* score components, severity and downstream outputs on "
        "frozen source vintages, compare historical and candidate results country "
        "by country, and predefine rejection criteria.\n"
        "4. Obtain an independent practitioner review of source interpretation "
        "and any proposed escalation rules. No travel clearance or protection "
        "staffing inference is authorized from this experiment.\n\n"
        "Supporting issue: https://github.com/jasonrkeen/"
        "executive-protection-risk-intelligence-model/issues/9\n"
    )


def run_candidate(demo_dir: Path, output_dir: Path) -> dict:
    """Verify frozen upstream evidence; stage then publish only complete outputs."""
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Candidate output already exists: {output_dir}")
    original_receipt, _events, indicators, rankings = verify_demo(demo_dir)
    reference = load_fixed_reference(REFERENCE_FILE)
    declarations = pd.read_csv(
        EVIDENCE_FILE, dtype=str, keep_default_na=False,
    )
    if (not declarations["source_ref"].str.startswith("synthetic://").all()
            or set(indicators["country"]) != {"Testland", "Example Republic"}
            or set(declarations["country"]) != set(indicators["country"])
            or set(indicators[INDICATOR]) != {
                reference.reference_min, reference.reference_max
            }):
        raise ValueError("Fictional reference/source data do not match baseline")
    baseline_evidence = merge_fictional_evidence(indicators, declarations)
    observed = score_frozen_homicide(baseline_evidence, reference)
    observed_shadow = shadow_country_comparison(rankings, observed)
    all_missing = evidence_scenario(
        indicators, declarations, reference, "ALL_MISSING"
    )
    missing_shadow = shadow_country_comparison(rankings, all_missing)
    if missing_shadow["candidate_shadow_composite"].notna().any():
        raise ValueError("Missing source evidence resulted in a candidate composite")
    if not observed_shadow["candidate_shadow_composite"].notna().all():
        raise ValueError("Reference has no evaluable fictional country")

    scenarios = {
        scenario: evidence_scenario(indicators, declarations, reference, scenario)
        for scenario in (
            "ALL_MISSING", "ONE_MISSING", "ONE_STALE", "ONE_CONFLICTING",
            "ONE_IMPUTED", "ONE_INVALID_NEGATIVE",
        )
    }
    stress = pd.concat([
        table.assign(scenario=scenario)
        for scenario, table in scenarios.items()
    ], ignore_index=True).sort_values(
        ["scenario", "country"]
    ).reset_index(drop=True)
    outlier = compare_legacy_and_frozen_outlier(
        indicators, declarations, reference
    )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".scoring-candidate-incomplete-", dir=output_dir.parent
    ) as staging:
        stage = Path(staging)
        outputs = {
            "candidate_homicide_baseline.csv": observed,
            "candidate_shadow_comparison.csv": observed_shadow,
            "candidate_all_missing_shadow.csv": missing_shadow,
            "candidate_evidence_stress.csv": stress,
            "frozen_reference_cohort_probe.csv": outlier,
        }
        for filename, frame in outputs.items():
            frame.to_csv(stage / filename, index=False, float_format="%.4f")
        (stage / "SCORING_DECISION_RECORD.md").write_text(
            decision_record(reference, rankings, observed, all_missing, outlier),
            encoding="utf-8",
        )
        build_candidate_pdf(
            stage / "SYNTHETIC_CANDIDATE_SCORING_REVIEW.pdf",
            observed_shadow, missing_shadow,
        )
        receipt = {
            "status": DEMO_STATUS,
            "version": DEMO_VERSION,
            "candidate_score_contract_version": VERSION,
            "data_class": "synthetic",
            "original_model_not_modified": True,
            "original_2024_baseline_preserved": True,
            "reference_id": reference.reference_id,
            "reference_sha256": fingerprint(REFERENCE_FILE),
            "source_declarations_sha256": fingerprint(EVIDENCE_FILE),
            "source_modules_sha256": {
                src: fingerprint(ROOT / src) for src in SOURCE_MODULES
            },
            "upstream_receipt_sha256": fingerprint(
                Path(demo_dir).resolve() / "run_receipt.json"
            ),
            "baseline_country_count": len(rankings),
            "record_counts": {
                "observed_rows": len(observed),
                "all_missing_rows": len(all_missing),
                "stress_scenarios": len(scenarios),
                "stress_records": len(stress),
                "cohort_probe_rows": len(outlier),
            },
            "evidence_review": {
                "all_missing_numeric_scores_issued": int(
                    all_missing["candidate_component_score"].notna().sum()
                ),
                "all_missing_risk_bands_issued": int(
                    missing_shadow["candidate_risk_bucket"].ne("NOT_ISSUED").sum()
                ),
                "out_of_reference_country_scores_issued": 0,
                "source_authenticity_verified": False,
                "other_components_independently_validated": False,
            },
            "output_sha256": {
                p.name: fingerprint(p)
                for p in sorted(stage.iterdir()) if p.is_file()
            },
            "limitations": [
                "Toy fixed reference is neither representative nor calibrated.",
                "Legacy risk, severity and other component calculations remain frozen.",
                "Candidate shadow scores are nonoperational mathematical examples.",
                "Missing or unreliable source evidence withholds candidate numeric output.",
                "No confidential, live source, itinerary or identifiable person is used.",
                "No risk bucket, risk probability, posture or travel approval is issued.",
            ],
        }
        (stage / "scoring_integrity_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            raise FileExistsError("Output target appeared during candidate scoring")
        os.replace(stage, output_dir)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_candidate(args.demo_dir, args.output_dir)
    print(json.dumps({
        "status": receipt["status"],
        "candidate_score_contract_version": receipt["candidate_score_contract_version"],
        "record_counts": receipt["record_counts"],
        "evidence_review": receipt["evidence_review"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
