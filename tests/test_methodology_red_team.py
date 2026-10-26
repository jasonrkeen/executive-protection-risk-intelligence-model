"""Scientific-interpretation guardrails for the fictional offline methodology audit."""
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.offline_synthetic_demo import run_demo
from src.methodology_red_team import (
    AUDIT_STATUS, MethodologyAuditError, cohort_dependence,
    missingness_stress, run_audit, severity_overlap, verify_demo,
    weight_only_ablation,
)


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    root = tmp_path_factory.mktemp("research-toy")
    demo_dir = root / "upstream-demo"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("A network request was attempted")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("A network socket was opened")):
        receipt = run_demo(demo_dir)
    assert receipt["record_counts"]["raw_synthetic_events"] == 20
    return demo_dir


def test_audit_reconciles_receipt_and_is_byte_reproducible(demo, tmp_path):
    first, second = tmp_path / "audit-first", tmp_path / "audit-second"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("Audit must never call network")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("Audit must never open sockets")):
        receipt_a = run_audit(demo, first)
        receipt_b = run_audit(demo, second)

    assert receipt_a == receipt_b
    assert receipt_a["status"] == AUDIT_STATUS
    assert receipt_a["summary"] == {
        "country_year_cells": 14,
        "country_year_cells_without_observations": 0,
        "ablation_rows": 10,
        "cohort_probe_rows": 3,
        "missingness_probe_rows": 6,
        "overlap_rows": 12,
        "correlation_estimate_status": "NOT_ESTIMATED_TINY_SYNTHETIC_COHORT",
        "source_completeness_verified": False,
        "external_predictive_validity_established": False,
    }
    assert len(receipt_a["output_sha256"]) == 6
    assert (first / "methodology_receipt.json").read_bytes() == (
        second / "methodology_receipt.json"
    ).read_bytes()
    for name in receipt_a["output_sha256"]:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    md = (first / "METHOD_REVIEW.md").read_text()
    assert "NEEDS INDEPENDENT VALIDATION" in md
    assert "not" in md.lower()
    assert "0.00" in md or "7.69" in md


def test_homicide_normalization_changes_with_fictional_cohort(demo):
    _, _, indicators, _ = verify_demo(demo)
    probe = cohort_dependence(indicators)
    row = probe.loc[probe["country"] == "Testland"].iloc[0]
    assert row["original_homicide_input"] == 12.0
    assert row["introduced_outlier_input"] == 120.0
    assert row["original_component_score"] == 100.0
    assert row["expanded_cohort_component_score"] == pytest.approx(900 / 117)
    assert row["full_model_rescored"] == False
    # Independent hand calculation, not a second call to the scoring helper:
    assert (12 - 3) / (120 - 3) * 100 == pytest.approx(900 / 117)


def test_missing_values_get_neutral_looking_index_not_evidence(demo):
    _, _, indicators, _ = verify_demo(demo)
    audit = missingness_stress(indicators)
    observed = audit[audit["scenario"] == "OBSERVED"]
    assert set(observed["resulting_crime_component_score"]) == {0.0, 100.0}
    partially_missing = audit[audit["scenario"] == "HIGHEST_RATE_MISSING"]
    assert partially_missing["source_missing"].sum() == 1
    assert set(partially_missing["resulting_crime_component_score"]) == {50.0}
    all_missing = audit[audit["scenario"] == "ALL_RATES_MISSING"]
    assert all_missing["source_missing"].all()
    assert set(all_missing["model_used_value"]) == {0.0}
    assert set(all_missing["resulting_crime_component_score"]) == {50.0}
    assert all_missing["meaning"].eq("INDEX_VALUE_NOT_VERIFIED_SAFETY").all()


def test_severity_decomposition_and_ablation_limits(demo):
    _, _, _, ranking = verify_demo(demo)
    overlap = severity_overlap(ranking)
    assert len(overlap) == 12
    assert not overlap["double_counting_magnitude_empirically_validated"].any()
    grouped = overlap.groupby("country")
    for _, rows in grouped:
        assert rows["points_before_aggregate_cap"].sum() == pytest.approx(
            rows["uplift_raw_total"].iloc[0]
        )
        assert rows["uplift_applied_capped"].iloc[0] == pytest.approx(
            min(25, rows["uplift_raw_total"].iloc[0])
        )
    ablations = weight_only_ablation(ranking)
    assert len(ablations) == 5 * len(ranking)
    assert ablations["not_full_construct_removal"].all()
    assert ablations["retained_severity_adjustments"].all()
    assert set(ablations["excluded_component"]) == {
        "civil_unrest_political_violence_score", "governance_risk_score",
        "violent_crime_score", "energy_exposure_score",
        "recent_risk_momentum_score",
    }
    assert np.isfinite(ablations["ablation_score"]).all()


def test_source_tampering_blocks_publication(demo, tmp_path):
    tampered = tmp_path / "tampered"
    shutil.copytree(demo, tampered)
    events = tampered / "data/raw/acled_events.csv"
    events.write_bytes(events.read_bytes() + b"\n")
    destination = tmp_path / "never-publish"
    with pytest.raises(MethodologyAuditError, match="no longer match receipt"):
        run_audit(tampered, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".methodology-incomplete-*"))


def test_output_tampering_blocks_publication(demo, tmp_path):
    tampered = tmp_path / "tampered-output"
    shutil.copytree(demo, tampered)
    pdf = tampered / "reports/synthetic_research_demo.pdf"
    pdf.write_bytes(pdf.read_bytes() + b"\n")
    destination = tmp_path / "never-publish"
    with pytest.raises(MethodologyAuditError, match="no longer match receipt"):
        run_audit(tampered, destination)
    assert not destination.exists()


def test_reject_existing_output_preserving_prior_results(demo, tmp_path):
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "immutable.txt"
    sentinel.write_text("Keep the old audit")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_audit(demo, existing)
    assert sentinel.read_text() == "Keep the old audit"


def test_falsely_claiming_source_truth_fails(demo, tmp_path):
    import json
    tampered = tmp_path / "tampered-receipt"
    shutil.copytree(demo, tampered)
    path = tampered / "run_receipt.json"
    d = json.loads(path.read_text())
    d["quality_flags"]["verified_incident_prediction"] = True
    path.write_text(json.dumps(d))
    with pytest.raises(MethodologyAuditError, match="external validity"):
        run_audit(tampered, tmp_path / "never-publish")


def test_baseline_receipt_records_synthetic_not_2026_predictions(demo):
    receipt, events, country, ranking = verify_demo(demo)
    assert receipt["source_windows"]["historical_baseline"] == [2020, 2024]
    assert receipt["source_windows"]["forward_2026_model"] == "NOT_RUN"
    assert set(country["country"]) == {"Example Republic", "Testland"}
    assert ranking["source_data_class"].eq("SYNTHETIC_TEST_ONLY").all()
    assert len(events) == 20
