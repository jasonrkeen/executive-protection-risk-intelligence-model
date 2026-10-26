"""Reproducible no-network, synthetic WGI uncertainty and event-lineage exercise.

Runs actual baseline country scoring and severity functions for toy perturbations
of fictional, unverified WGI standard errors. Not a 27-stage pipeline, validated
source-uncertainty model, source-completeness test, or protective decision tool.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from src.offline_synthetic_demo import ROOT, FIXTURES
from src.methodology_red_team import verify_demo
from src.source_uncertainty import (
    AS_OF, RELEASE, SOURCE_STATUS,
    full_country_reruns, require_event_source_ledger, require_wgi_source_matrix,
)

VERSION = "SYNTHETIC_SOURCE_UNCERTAINTY_V1"
STATUS = "PASS_FICTIONAL_UNCERTAINTY_EXERCISE_NOT_REAL_VALIDATION"
WGI_PATH = FIXTURES / "wgi_uncertainty_panel.csv"
EVENT_PATH = FIXTURES / "acled_provenance_sidecar.csv"
SEED = 42
DRAWS = 24


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def findings_note(
    matrix: pd.DataFrame, readiness: pd.DataFrame, sidecar: pd.DataFrame,
    country_year: pd.DataFrame, sims: pd.DataFrame, summary: pd.DataFrame,
    incomplete: pd.DataFrame,
) -> str:
    spread = summary.groupby("country").agg(
        smallest=("minimum_rerun_score", "min"),
        largest=("maximum_rerun_score", "max"),
        band_changes=("toy_risk_band_changes", "sum"),
    )
    text = [
        "# Synthetic Country Source-Uncertainty and Model-Rerun Findings",
        "",
        "**Disposition: NOT externally validated; this work is a frozen, fictional sensitivity exercise.**",
        "No confidence in protective outcomes, actual source completeness, or travel clearance is established.",
        "",
        "## WGI 2026 version / scale integrity",
        "",
        "The World Bank's 2026 WGI release covers 1996-2025, revised historical values,",
        "standard-normal estimates and a distinct fixed-reference 0-100 score.",
        "The project's 2024 structural baseline uses standard-normal governance",
        "estimates with a second, cohort-relative min-max transform. **Do not",
        "mix the two WGI scales or release revisions without version controls.**",
        "",
        f"- Fictional release: {RELEASE}; not a real World Bank export.",
        f"- Country/dimension cells: {len(matrix)}, four scored dimensions plus one informational dimension per country.",
        f"- Countries passing declared toy scored-dimension coverage: {int(readiness.source_ready_for_toy_sensitivity.sum())} of {len(readiness)}.",
        f"- Withheld after deleting one scored-dimension source record: {int((~incomplete.source_ready_for_toy_sensitivity).sum())} country(s).",
        "- WGI source standard errors, data-source counts and source dates are completely invented.",
        "- The 2026 release date is later than the 2024 modeled observation year:",
        "  this is a *release vintage*, not proof that a 2024 indicator was known in 2024.",
        "",
        "## ACLED-shaped event source lineage",
        "",
        f"- Invented events with unique source IDs and a consistent snapshot: {len(sidecar)}.",
        f"- Time-precision value >1 (less than precise event date): {int(sidecar.time_precision.gt(1).sum())}.",
        f"- Events marked as synthetic source-revision examples: {int(sidecar.revision_state.eq('synthetic_revision_example').sum())}.",
        f"- Country/year cells in 2020-2026: {len(country_year)}; missing-event cells: {int(country_year.event_records.eq(0).sum())}.",
        "- Presence and matching source IDs do not verify sampling or area coverage.",
        "- ACLED real-world event dates can have lower precision, fatality estimates",
        "  are indicative, and historical events may be revised retrospectively.",
        "",
        "## Rerunning the complete *country-scoring* chain under invented WGI perturbations",
        "",
        f"- Total simulated model output rows: {len(sims)}.",
        f"- Independent-marginal toy draws per scenario: {DRAWS};",
        "  scenarios use 1x or 3x fictional standard errors; seed 42.",
        "- All five scoring components and the capped severity uplift are",
        "  **recomputed** for each synthetic perturbation using repository functions.",
        "- ACLED observations, crime/energy inputs, baseline years and cohort",
        "  remain fixed; the 27-stage production pipeline and other data layers are",
        "  not run. This is not a complete real-world full-model validation.",
    ]
    for country, row in spread.sort_index().iterrows():
        text.append(
            f"- {country}: toy rerun country-index range "
            f"{float(row.smallest):.2f}-{float(row.largest):.2f}; "
            f"{int(row.band_changes)} model-band changes across all toy draws."
        )
    text.extend([
        "- Reported scenario values are *not* statistical confidence intervals;",
        "  governance dimensions may be dependent and actual WGI covariance was",
        "  neither sourced nor estimated. Bands are legacy research labels, never",
        "  travel, itinerary, personnel or clearance recommendations.",
        "",
        "## Required external and methodological gates",
        "",
        "1. Verify real WGI 2026 estimates, standard errors, country-specific coverage,",
        "   code mapping, historical revisions and release licenses before ingesting",
        "   any live data. Check the scale separately from the WGI absolute 0-100 score.",
        "2. Obtain authorized dated ACLED extracts with source identifiers, event",
        "   time precision, reporting scope and revision provenance; test join keys",
        "   and geographic completeness separately.",
        "3. Design a defensible uncertainty model including source covariance and",
        "   missingness; reconcile new-vs-old WGI methodology before comparisons.",
        "4. Validate risk constructs on frozen authentic inputs, retest the full",
        "   27-stage pipeline, conduct independent practitioner interpretation",
        "   exercises, and preregister useful outcome criteria.",
        "",
        "### Official methodological references",
        "",
        "- World Bank WGI 2026: https://www.worldbank.org/en/publication/worldwide-governance-indicators",
        "- World Bank WGI standard errors: https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation",
        "- World Bank data catalog: https://datacatalog.worldbank.org/search/dataset/0038026/worldwide-governance-indicators",
        "- ACLED codebook: https://acleddata.com/methodology/acled-codebook",
        "",
    ])
    return "\n".join(text)


def run_source_uncertainty(
    demo_dir: Path, output_dir: Path, *, draws: int = DRAWS, seed: int = SEED
) -> dict:
    """Stage, verify source lineage, rerun actual scoring and publish atomically."""
    output = Path(output_dir).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite a prior source-uncertainty audit")
    source_receipt, events, indicators, original = verify_demo(demo_dir)
    yearly_path = Path(demo_dir).resolve() / "data/processed/acled_country_risk_features.csv"
    yearly = pd.read_csv(yearly_path)
    wgi = pd.read_csv(WGI_PATH)
    provenance = pd.read_csv(EVENT_PATH, dtype={
        "event_id_cnty": str, "time_precision": str
    })
    matrix, readiness = require_wgi_source_matrix(wgi, indicators, as_of=AS_OF)
    sidecar, country_year = require_event_source_ledger(
        events, provenance, as_of=AS_OF,
    )
    if not readiness.source_ready_for_toy_sensitivity.all():
        raise ValueError("Incomplete fake WGI source evidence must block uncertainty scoring")
    simulations, summary = full_country_reruns(
        yearly, indicators, matrix, readiness, original,
        draws=draws, seed=seed,
    )
    # Audit that country-specific missing source evidence becomes WITHHELD.
    missing = wgi[
        ~(
            wgi.country.eq("Testland")
            & wgi.indicator.eq("rule_of_law")
        )
    ].copy()
    missing_matrix, missing_readiness = require_wgi_source_matrix(
        missing, indicators, as_of=AS_OF
    )
    if missing_readiness.source_ready_for_toy_sensitivity.all():
        raise ValueError("Deleting a scored dimension must fail country-level readiness")
    if not missing_matrix.evidence_status.eq(
        "BLOCKED_MISSING_COUNTRY_DIMENSION"
    ).any():
        raise ValueError("Missing source cell did not survive country audit")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".source-uncertainty-incomplete-", dir=output.parent,
    ) as stage_path:
        stage = Path(stage_path)
        results = {
            "wgi_country_dimension_coverage.csv": matrix,
            "wgi_country_scoring_readiness.csv": readiness,
            "wgi_missing_dimension_stress.csv": missing_matrix,
            "wgi_missing_country_readiness.csv": missing_readiness,
            "event_provenance_integrity.csv": sidecar,
            "event_country_year_presence.csv": country_year,
            "governance_uncertainty_country_reruns.csv": simulations,
            "governance_uncertainty_summary.csv": summary,
        }
        for path, df in results.items():
            df.to_csv(stage / path, index=False, float_format="%.6f")
        (stage / "SOURCE_UNCERTAINTY_FINDINGS.md").write_text(
            findings_note(matrix, readiness, sidecar, country_year,
                          simulations, summary, missing_readiness),
            encoding="utf-8",
        )
        receipt = {
            "status": STATUS,
            "version": VERSION,
            "model_baseline_year": 2024,
            "assessment_as_of": AS_OF.isoformat(),
            "declared_data_class": "synthetic",
            "release_id": RELEASE,
            "wgi_unit": "standard_normal_estimate_not_fixed_0_to_100_score",
            "event_snapshot_id": "SYN-ACLED-STYLE-2026-10-17",
            "country_count": len(readiness),
            "source_dimension_cells": len(matrix),
            "event_source_records": len(sidecar),
            "missing_scored_dimension_countries_withheld": int(
                (~missing_readiness.source_ready_for_toy_sensitivity).sum()
            ),
            "full_country_scorer_rerun": True,
            "complete_live_27_stage_pipeline_rerun": False,
            "toy_uncertainty_scenarios": ["DECLARED_MARGINAL_SE", "AMPLIFIED_STRESS_3X_SE"],
            "toy_draws_per_scenario": draws,
            "random_seed": seed,
            "toy_simulated_score_rows": len(simulations),
            "raw_inputs_sha256": {
                "wgi_uncertainty_panel.csv": file_hash(WGI_PATH),
                "acled_provenance_sidecar.csv": file_hash(EVENT_PATH),
            },
            "upstream_receipt_sha256": file_hash(
                Path(demo_dir).resolve() / "run_receipt.json"
            ),
            "method_modules_sha256": {
                name: file_hash(ROOT / name)
                for name in (
                    "src/source_uncertainty.py",
                    "src/source_uncertainty_demo.py",
                )
            },
            "source_completeness_authenticated": False,
            "real_wgi_standard_errors_verified": False,
            "wgi_covariance_available": False,
            "external_outcome_validation": False,
            "output_sha256": {
                p.name: file_hash(p) for p in sorted(stage.iterdir()) if p.is_file()
            },
        }
        (stage / "source_uncertainty_receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if output.exists():
            raise FileExistsError("Output target appeared during source audit")
        os.replace(stage, output)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=DRAWS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    receipt = run_source_uncertainty(
        args.demo_dir, args.output_dir, draws=args.draws, seed=args.seed,
    )
    print(json.dumps({
        "status": receipt["status"], "toy_draws_per_scenario": receipt["toy_draws_per_scenario"],
        "toy_simulated_score_rows": receipt["toy_simulated_score_rows"],
        "missing_scored_dimension_countries_withheld": receipt[
            "missing_scored_dimension_countries_withheld"
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
