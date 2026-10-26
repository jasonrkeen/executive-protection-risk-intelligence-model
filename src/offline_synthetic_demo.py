"""Deterministic, offline, entirely fictional vertical integration demonstration.

This runs real repository scoring/COA/evidence/PDF functions in an isolated
directory, NOT the network-enabled 27-stage src.main production pipeline.
It does not validate the completeness or truth of event reporting, model
calibration, or any operational protective decision.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pandas as pd
import reportlab
import sklearn
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate

from src.config import END_YEAR, MONTE_CARLO_RANDOM_SEED, START_YEAR
from src.preflight import (
    require_historical_baseline_coverage, require_preflight,
    verify_package_unchanged,
)
from src.residual_protective_risk import FIELDS, VERSION as RESIDUAL_VERSION
from src.intelligence_validation_layer import (
    VERSION as VALIDATION_VERSION, run_intelligence_validation_layer,
)
from src.acled_processing import (
    add_event_type_counts, add_sub_event_type_counts, add_location_features,
    add_fatality_features, add_share_features, add_momentum_features,
    enforce_output_schema,
)
from src.acled_city_processing import (
    aggregate_city_features, clean_acled_events, score_city_features,
    standardize_acled_columns,
)
from src.access_proxy_layer import (
    add_medical_capacity, calculate_access_adjusted_risk,
    calculate_airport_access,
)
from src.protective_intelligence_score import calculate_protective_intelligence_scores
from src.residual_protective_risk import score_residual_risk, validate_residual_scores
from src.protective_intelligence_decision_layer import (
    build_decision_support_layer, save_decision_support_outputs,
)
from src.risk_scoring import (
    calculate_civil_unrest_political_violence_score, calculate_governance_risk_score,
    calculate_crime_risk_score, calculate_energy_exposure_score,
    calculate_recent_momentum_score, calculate_composite_score,
)
from src.monte_carlo_risk_simulation import draw_random_weights, run_single_simulation
from src.intelligence_validation_views import add_intelligence_validation_section
from src.report_generator import (
    make_styles, add_protective_intelligence_decision_support_section,
    add_protective_intelligence_posture_section,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples" / "offline_synthetic"
DEMO_AS_OF = "2026-10-17"
DEMO_VERSION = "offline-synthetic-vertical-v1"
RUNS = 25
INPUTS = (
    "acled_events.csv",
    "protective_intelligence_trip_inputs.csv",
    "protective_capacity_inputs.csv",
    "country_indicators.csv",
    "airports.csv",
    "medical_reference.csv",
    "decision_rules.csv",
)
HASHED_INPUTS = {
    "events": "acled_events.csv",
    "trips": "protective_intelligence_trip_inputs.csv",
    "capacity": "protective_capacity_inputs.csv",
}
MODEL_SOURCE_FILES = (
    "src/offline_synthetic_demo.py",
    "src/acled_processing.py",
    "src/acled_city_processing.py",
    "src/access_proxy_layer.py",
    "src/risk_scoring.py",
    "src/protective_intelligence_score.py",
    "src/residual_protective_risk.py",
    "src/protective_intelligence_decision_layer.py",
    "src/intelligence_validation_layer.py",
    "src/intelligence_validation_views.py",
    "src/report_generator.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_evidence(raw: Path) -> dict:
    """Synthetic-only approval declarations for fixed, fake test data."""
    from src.preflight import TRIP_FIELDS

    trips = pd.read_csv(raw / HASHED_INPUTS["trips"], dtype=str, keep_default_na=False)
    if trips.empty or not trips["principal"].str.startswith("SYNTHETIC-").all():
        raise ValueError("Demo trip names must be explicitly marked SYNTHETIC")
    if set(trips["country"]) != {"Testland", "Example Republic"}:
        raise ValueError("Demo accepts only its two fictional countries")
    source = pd.read_csv(raw / HASHED_INPUTS["events"], dtype=str, keep_default_na=False)
    if (source.empty or not source["event_id_cnty"].str.startswith("SYN-").all()
            or not source["notes"].eq("SYNTHETIC").all()
            or not set(source["country"]).issubset({"Testland", "Example Republic"})):
        raise ValueError("Demo event data must consist solely of synthetic records")
    records = []
    for trip_id in trips["trip_id"]:
        for kind, fields in (("trip", TRIP_FIELDS), ("capacity", FIELDS)):
            records.append({
                "trip_id": trip_id,
                "kind": kind,
                "source_ref": "synthetic://offline-demo/fictional-inputs",
                "assessor_ref": "TEST-ONLY-ASSESSOR",
                "reviewer_ref": "TEST-ONLY-REVIEWER",
                "scope": "FAKE INPUTS; not a real review",
                "review_status": "approved",
                "covered_fields": list(fields),
                "assessed_on": "2026-10-16",
                "movement_on": "2026-10-18",
                "expires_on": "2026-10-19",
            })
    return {
        "schema_version": 1,
        "data_class": "synthetic",
        "contains_personal_data": False,
        "input_sha256": {
            key: sha256(raw / name) for key, name in HASHED_INPUTS.items()
        },
        "event_source": {
            "source_ref": "synthetic://offline-demo/events-NOT-ACLED",
            "reviewer_ref": "TEST-ONLY-REVIEWER",
            "review_status": "approved",
            "coverage_from": "2020-03-01",
            "coverage_through": "2026-10-16",
            "retrieved_on": DEMO_AS_OF,
        },
        "assessments": records,
    }


def country_features(events: pd.DataFrame) -> pd.DataFrame:
    """Reuse the actual 2020-2024 country-year event feature transforms."""
    data = events[events["year"].between(START_YEAR, END_YEAR)].copy()
    if data.empty:
        raise ValueError("Synthetic historical ACLED extract is empty")
    data["event_date"] = pd.to_datetime(data["event_date"], format="%Y-%m-%d")
    data["latitude"] = pd.to_numeric(data["latitude"], errors="raise")
    data["longitude"] = pd.to_numeric(data["longitude"], errors="raise")
    data["fatalities"] = pd.to_numeric(data["fatalities"], errors="raise")
    data = data.drop_duplicates(subset=["event_id_cnty"], keep="first")
    base = (data.groupby(["country", "year"])
            .agg(total_acled_events=("event_type", "size"),
                 total_fatalities=("fatalities", "sum")).reset_index())
    for fn in (
        lambda b: add_event_type_counts(b, data),
        lambda b: add_sub_event_type_counts(b, data),
        lambda b: add_location_features(b, data),
        lambda b: add_fatality_features(b, data),
        add_share_features, add_momentum_features, enforce_output_schema,
    ):
        base = fn(base)
    base["acled_data_source"] = "SYNTHETIC FIXTURE - NOT ACLED OBSERVATIONS"
    return base.sort_values(["country", "year"]).reset_index(drop=True)


def country_scores(yearly: pd.DataFrame, indicators: pd.DataFrame) -> pd.DataFrame:
    """Compute actual country score functions from fictional indicator inputs."""
    country = yearly[yearly["year"] == END_YEAR].copy()
    if country.empty or country["country"].duplicated().any():
        raise ValueError("Expected unique synthetic country baseline records")
    if (indicators["country"].duplicated().any()
            or set(indicators["country"]) != set(country["country"])):
        raise ValueError("Fictional indicator coverage does not match baseline countries")
    country = country.merge(indicators, on="country", validate="one_to_one")
    for fn in (
        calculate_civil_unrest_political_violence_score,
        calculate_governance_risk_score,
        calculate_crime_risk_score,
        calculate_energy_exposure_score,
        calculate_recent_momentum_score,
        calculate_composite_score,
    ):
        country = fn(country)
    country = country.sort_values(
        ["executive_protection_risk_score", "country"], ascending=[False, True],
    ).reset_index(drop=True)
    country.insert(0, "baseline_rank", country.index + 1)
    country["source_data_class"] = "SYNTHETIC_TEST_ONLY"
    return country


def city_and_access(events: pd.DataFrame, airports: pd.DataFrame,
                    medical: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exercise actual city, airport distance, medical proxy and access scoring."""
    raw = standardize_acled_columns(events.copy())
    clean = clean_acled_events(raw)
    city = score_city_features(aggregate_city_features(clean))
    city["source_data_class"] = "SYNTHETIC_TEST_ONLY"
    if city.empty:
        raise ValueError("No synthetic city features created")
    access = calculate_access_adjusted_risk(
        add_medical_capacity(calculate_airport_access(city, airports), medical)
    )
    if access["nearest_airport_km"].isna().any() or access["medical_capacity_score"].isna().any():
        raise ValueError("Synthetic support references are incomplete")
    return city, access


def trip_context(city: pd.DataFrame, access: pd.DataFrame) -> pd.DataFrame:
    """Mirror the production PI city/access join, limited to required columns."""
    core = city.copy()
    enriched = access.copy()
    for frame in (core, enriched):
        frame["city_key"] = frame["city"].astype(str).str.strip().str.lower()
        frame["country_key"] = frame["country"].astype(str).str.strip().str.lower()
    cols = [
        "city_key", "country_key", "nearest_airport_km", "medical_capacity_score",
        "support_gap_score", "city_operational_ep_risk_score",
        "airport_access_score", "support_access_score",
    ]
    return core.merge(
        enriched[cols], on=["city_key", "country_key"],
        how="left", validate="one_to_one",
    )


def produce_pdf(path: Path, pi: pd.DataFrame, decision: pd.DataFrame,
                audit: pd.DataFrame, validation: dict[str, pd.DataFrame]) -> None:
    """Use the actual model's protective and validation PDF presentation functions."""
    styles = make_styles()
    story = [
        Paragraph("SYNTHETIC - OFFLINE RESEARCH DEMONSTRATION", styles["title"]),
        Paragraph(
            "All countries, movements, locations, airports, and incidents are fictional. "
            "Country results are anchored to a 2024 historical baseline; city windows "
            "end at the synthetic 2026-10-16 extract date. The 2026 forward model, "
            "live-source fetching and the full 27-stage pipeline are NOT exercised.",
            styles["body"],
        ),
        Paragraph(
            "Scores are uncalibrated indices, not probabilities; review states "
            "are not operational protective or travel authorizations.",
            styles["body"],
        ),
    ]
    add_protective_intelligence_posture_section(story, styles, pi, pi.head(10))
    add_protective_intelligence_decision_support_section(
        story, styles, decision, decision.head(10), audit,
    )
    add_intelligence_validation_section(
        story, styles, validation["intelligence_confidence_scores"],
        validation["source_coverage_gaps"], validation["analyst_collection_plan"],
    )
    SimpleDocTemplate(
        str(path), pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36,
        invariant=1,
    ).build(story)


def run_demo(output_dir: Path, fixture_dir: Path = FIXTURES) -> dict:
    """Run a complete *vertical* synthetic scoring→COA→audit→PDF integration.

    Work is staged on the output filesystem and only published once all
    validations, source-hash rechecks and renderers succeed. Existing output
    directories are NEVER overwritten or silently reused.
    """
    output_dir = Path(output_dir).resolve()
    fixture_dir = Path(fixture_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing demo output: {output_dir}")
    for name in INPUTS:
        if not (fixture_dir / name).is_file():
            raise FileNotFoundError(f"Synthetic fixture missing: {name}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".offline-demo-incomplete-", dir=output_dir.parent,
    ) as staging:
        stage = Path(staging)
        raw = stage / "data" / "raw"
        processed = stage / "data" / "processed"
        tables = stage / "tables"
        reports = stage / "reports"
        for directory in (raw, processed, tables, reports):
            directory.mkdir(parents=True, exist_ok=True)
        for name in INPUTS:
            shutil.copyfile(fixture_dir / name, raw / name)

        evidence = synthetic_evidence(raw)
        (raw / "rpr1_evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        # The production preflight uses an explicit past date in synthetic
        # read-only mode, never current/real-run authorizations.
        preflight = require_preflight(DEMO_AS_OF, mode="synthetic", root=stage)
        baseline = require_historical_baseline_coverage(
            raw / "acled_events.csv",
            baseline_start_year=START_YEAR, baseline_end_year=END_YEAR,
        )

        events = pd.read_csv(raw / "acled_events.csv", dtype={"event_id_cnty": str})
        yearly = country_features(events)
        indicators = pd.read_csv(raw / "country_indicators.csv")
        indicators["source_data_class"] = "SYNTHETIC_NOT_WORLD_BANK"
        rankings = country_scores(yearly, indicators)
        airports = pd.read_csv(raw / "airports.csv")
        medical = pd.read_csv(raw / "medical_reference.csv")
        if (not airports["name"].astype(str).str.startswith("Synthetic ").all()
                or set(medical["country_normalized"])
                != {"testland", "example republic"}):
            raise ValueError("Support references must be explicitly fictional")
        city, access = city_and_access(events, airports, medical)

        # The production residual/COA and validation readers use these names.
        yearly.to_csv(processed / "acled_country_risk_features.csv", index=False)
        city.to_csv(processed / "city_ep_risk_features.csv", index=False)
        access.to_csv(processed / "city_access_proxy_features.csv", index=False)
        indicators.to_csv(processed / "worldbank_ep_indicators.csv", index=False)
        rankings.to_csv(tables / "executive_protection_risk_rankings.csv", index=False)

        trips = pd.read_csv(
            raw / "protective_intelligence_trip_inputs.csv",
            dtype=str, keep_default_na=False,
        )
        trips["city_key"] = trips["city"].str.strip().str.lower()
        trips["country_key"] = trips["country"].str.strip().str.lower()
        pi = calculate_protective_intelligence_scores(trips, trip_context(city, access))
        pi.to_csv(processed / "protective_intelligence_trip_scores.csv", index=False)
        capacity = pd.read_csv(
            raw / "protective_capacity_inputs.csv", dtype={"trip_id": str},
        )
        residual = score_residual_risk(pi, capacity)
        validate_residual_scores(residual)
        residual.to_csv(processed / "residual_protective_risk_scores.csv", index=False)
        rule_path = raw / "decision_rules.csv"
        decision = build_decision_support_layer(residual, rules_path=rule_path)
        saved = save_decision_support_outputs(
            decision, output_dir=tables, rules_path=rule_path,
        )
        audit = pd.read_csv(saved["decision_rule_audit"])
        validation_paths = run_intelligence_validation_layer(
            processed_dir=processed, outputs_dir=tables,
            review_date=date.fromisoformat(DEMO_AS_OF),
        )
        validation = {
            name: pd.read_csv(path, dtype={"trip_id": str})
            for name, path in validation_paths.items()
        }
        if (validation["intelligence_confidence_scores"]
                ["acled_stale_flag"].astype(str).str.lower().eq("true").any()):
            raise ValueError("Synthetic city source is stale")
        if validation["intelligence_confidence_scores"]["wgi_unavailable_flag"].astype(str).str.lower().eq("true").any():
            raise ValueError("Synthetic governance reference is missing")

        # Fixed-seed Monte Carlo checks internal weight sensitivity only.
        rng = np.random.default_rng(MONTE_CARLO_RANDOM_SEED)
        simulations = pd.concat([
            run_single_simulation(rankings, draw_random_weights(rng), i + 1)
            for i in range(RUNS)
        ], ignore_index=True)
        simulations.to_csv(tables / "synthetic_weight_sensitivity.csv", index=False)
        produce_pdf(
            reports / "synthetic_research_demo.pdf", pi, decision, audit, validation,
        )

        # All key outputs are built from real, network-free project functions.
        verify_package_unchanged(preflight, root=stage)
        source_hashes = {
            name: sha256(raw / name) for name in sorted(INPUTS)
        }
        output_hashes = {
            str(path.relative_to(stage)): sha256(path)
            for path in sorted(stage.rglob("*"))
            if path.is_file() and (
                path.is_relative_to(processed)
                or path.is_relative_to(tables)
                or path.is_relative_to(reports)
            )
        }
        receipt = {
            "status": "PASS_SYNTHETIC_INTEGRATION_NOT_OPERATIONAL_VALIDATION",
            "demo_version": DEMO_VERSION,
            "model_versions": {
                "country_baseline_year": END_YEAR,
                "residual": RESIDUAL_VERSION,
                "evidence_audit": VALIDATION_VERSION,
            },
            "data_class": "synthetic",
            "environment": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "reportlab": reportlab.Version,
                "scikit_learn": sklearn.__version__,
            },
            "model_source_sha256": {
                path: sha256(ROOT / path) for path in MODEL_SOURCE_FILES
            },
            "fictional_countries_only": sorted(set(trips["country"])),
            "assessment_date": DEMO_AS_OF,
            "source_windows": {
                "historical_baseline": [START_YEAR, END_YEAR],
                "all_events_from": events["event_date"].min(),
                "all_events_through": events["event_date"].max(),
                "city_windows_anchored_to": events["event_date"].max(),
                "forward_2026_model": "NOT_RUN",
            },
            "baseline_year_presence": baseline,
            "preflight_status": preflight.status,
            "preflight_policy": asdict(preflight)["freshness_policy_days"],
            "record_counts": {
                "raw_synthetic_events": int(len(events)),
                "country_years": int(len(yearly)),
                "baseline_countries": int(len(rankings)),
                "cities": int(len(city)),
                "synthetic_movements": int(len(pi)),
                "residual_scores": int(len(residual)),
                "decisions": int(len(decision)),
                "evidence_coverage_records": int(len(validation["intelligence_confidence_scores"])),
            },
            "quality_flags": {
                "city_context_missing": int(
                    validation["intelligence_confidence_scores"]["city_context_missing_flag"]
                    .astype(str).str.lower().eq("true").sum()
                ),
                "acled_stale": int(
                    validation["intelligence_confidence_scores"]["acled_stale_flag"]
                    .astype(str).str.lower().eq("true").sum()
                ),
                "provisional_weights": True,
                "verified_source_completeness": False,
                "verified_incident_prediction": False,
            },
            "monte_carlo": {
                "seed": MONTE_CARLO_RANDOM_SEED,
                "runs": RUNS,
                "interpretation": "Randomized uncalibrated weights, not predictive validation",
            },
            "input_sha256": source_hashes,
            "evidence_sha256": sha256(raw / "rpr1_evidence.json"),
            "output_sha256": output_hashes,
            "limitations": [
                "Only the offline vertical scoring/COA/evidence/PDF slice is run.",
                "The network-dependent 27-stage live pipeline is NOT run.",
                "Fictional events and approved test declarations do not authenticate real sources.",
                "Country scores remain structurally anchored to the 2024 baseline.",
                "Risk scores and evidence coverage are not incident probabilities.",
                "No travel or protective operation may be authorized by these outputs.",
            ],
        }
        (stage / "run_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            raise FileExistsError(f"Refusing to overwrite existing demo output: {output_dir}")
        os.replace(stage, output_dir)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "outputs" / "synthetic_offline_demo",
    )
    args = parser.parse_args()
    receipt = run_demo(args.output_dir)
    print(json.dumps({
        "status": receipt["status"], "output_dir": str(args.output_dir),
        "record_counts": receipt["record_counts"],
        "source_windows": receipt["source_windows"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
