"""Synthetic tests for WGI scale/vintage and ACLED-style event-source uncertainty."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.offline_synthetic_demo import run_demo
from src.methodology_red_team import MethodologyAuditError, verify_demo
from src.source_uncertainty import (
    AS_OF, SourceEvidenceError, full_country_reruns,
    require_wgi_source_matrix, require_event_source_ledger,
)
from src.source_uncertainty_demo import (
    WGI_PATH, EVENT_PATH, STATUS, run_source_uncertainty,
)


@pytest.fixture(scope="module")
def synthetic_upstream(tmp_path_factory):
    output = tmp_path_factory.mktemp("source-fixtures") / "demo"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("Synthetic audit attempted HTTP")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("Synthetic audit attempted network")):
        run_demo(output)
    return output


@pytest.fixture()
def source_inputs(synthetic_upstream):
    _, events, indicators, baseline = verify_demo(synthetic_upstream)
    panel = pd.read_csv(WGI_PATH)
    provenance = pd.read_csv(EVENT_PATH, dtype={"event_id_cnty": str})
    yearly = pd.read_csv(
        Path(synthetic_upstream) / "data/processed/acled_country_risk_features.csv"
    )
    return events, indicators, baseline, panel, provenance, yearly


def test_country_level_coverage_and_evidence_status(source_inputs):
    _, indicators, _, panel, _, _ = source_inputs
    matrix, readiness = require_wgi_source_matrix(panel, indicators)
    assert len(matrix) == 10
    assert len(readiness) == 2
    assert readiness["scored_dimensions_covered"].eq(4).all()
    assert readiness["supplemental_dimensions_covered"].eq(1).all()
    assert readiness["source_ready_for_toy_sensitivity"].all()
    assert not readiness["actual_wgi_country_coverage_verified"].any()
    assert matrix["source_release_2026_on_2024_model"].all()
    assert matrix["evidence_status"].eq("SYNTHETIC_ESTIMATE_AND_ERROR_PRESENT").all()
    assert not matrix["source_authenticated"].any()


def test_one_country_missing_required_dimension_blocks_country_readiness(source_inputs):
    _, indicators, _, panel, _, _ = source_inputs
    partial = panel[~(panel.country.eq("Testland") & panel.indicator.eq("rule_of_law"))]
    matrix, readiness = require_wgi_source_matrix(partial, indicators)
    affected = readiness.set_index("country")
    assert not bool(affected.loc["Testland", "source_ready_for_toy_sensitivity"])
    assert bool(affected.loc["Example Republic", "source_ready_for_toy_sensitivity"])
    assert affected.loc["Testland", "risk_output_policy"] == (
        "WITHHELD_MISSING_OR_INCOMPATIBLE_SOURCE"
    )
    row = matrix[
        matrix.country.eq("Testland") & matrix.indicator.eq("rule_of_law")
    ].iloc[0]
    assert row["evidence_status"] == "BLOCKED_MISSING_COUNTRY_DIMENSION"
    assert pd.isna(row["standard_error"])


@pytest.mark.parametrize("fault,pattern", [
    ("absolute_scale", "scales"),
    ("mismatched_release", "Mixed"),
    ("future_year", "source year"),
    ("future_retrieval", "retrieval"),
    ("negative_standard_error", "standard error"),
    ("zero_source_count", "source_count"),
    ("duplicate_country_dimension", "Duplicate"),
    ("wrong_country", "outside frozen"),
])
def test_incompatible_wgi_source_contract_rejected(source_inputs, fault, pattern):
    _, indicators, _, panel, _, _ = source_inputs
    bad = panel.copy()
    if fault == "absolute_scale":
        bad.loc[0, "estimate_unit"] = "absolute_0_100_score"
    elif fault == "mismatched_release":
        bad.loc[0, "release_id"] = "ANOTHER_SYNTHETIC_RELEASE"
    elif fault == "future_year":
        bad.loc[0, "source_year"] = 2025
    elif fault == "future_retrieval":
        bad.loc[0, "retrieved_on"] = "2026-10-18"
    elif fault == "negative_standard_error":
        bad.loc[0, "standard_error"] = -1
    elif fault == "zero_source_count":
        bad.loc[0, "source_count"] = 0
    elif fault == "duplicate_country_dimension":
        bad = pd.concat([bad, bad.iloc[[0]]], ignore_index=True)
    elif fault == "wrong_country":
        bad.loc[0, "country"] = "Not In Toy Baseline"
    with pytest.raises(SourceEvidenceError, match=pattern):
        require_wgi_source_matrix(bad, indicators)


def test_wgi_release_vintage_is_distinct_from_source_observation_year(source_inputs):
    _, indicators, _, panel, _, _ = source_inputs
    matrix, _ = require_wgi_source_matrix(panel, indicators)
    assert set(matrix["source_year"]) == {2024}
    assert set(matrix["release_date"]) == {"2026-09-18"}
    assert set(matrix["retrieved_on"]) == {"2026-10-17"}
    assert matrix["source_vintage_after_baseline"].all()


def test_event_lineage_unique_precise_and_revision_flagged(source_inputs):
    events, _, _, _, provenance, _ = source_inputs
    details, years = require_event_source_ledger(events, provenance)
    assert len(details) == 20
    assert details["event_id_cnty"].is_unique
    assert len(years) == 14
    assert years["year"].dtype.kind in ("i", "u")
    # Exact numeric year grain matters: string years previously produced
    # fourteen false 'zero-event' cells when reindexed with integer years.
    assert years["event_records"].sum() == 20
    assert years["event_records"].gt(0).all()
    assert years["status"].eq("SYNTHETIC_OBSERVATION_PRESENT_NOT_COVERAGE").all()
    assert (details.time_precision > 1).any()
    assert details["revision_state"].eq("synthetic_revision_example").sum() == 2
    assert not years["reporting_completeness_verified"].any()
    assert not details["source_completeness_verified"].any()


@pytest.mark.parametrize("fault,pattern", [
    ("missing_event", "orphaned"),
    ("duplicate", "duplicate|Duplicate"),
    ("bad_precision", "precision"),
    ("bad_snapshot", "Mixed"),
    ("bad_date", "disagreement"),
    ("future_extract", "Future"),
])
def test_event_lineage_invalid_or_changed_version_fails(source_inputs, fault, pattern):
    events, _, _, _, ledger, _ = source_inputs
    bad = ledger.copy()
    if fault == "missing_event":
        bad = bad.iloc[:-1]
    elif fault == "duplicate":
        bad = pd.concat([bad, bad.iloc[[0]]], ignore_index=True)
    elif fault == "bad_precision":
        bad.loc[0, "time_precision"] = 4
    elif fault == "bad_snapshot":
        bad.loc[0, "snapshot_id"] = "DIFFERENT_SNAPSHOT"
    elif fault == "bad_date":
        bad.loc[0, "event_date"] = "2020-03-02"
    elif fault == "future_extract":
        bad.loc[0, "observed_at"] = "2026-10-18"
    with pytest.raises(SourceEvidenceError, match=pattern):
        require_event_source_ledger(events, bad)


def test_governance_uncertainty_reruns_full_country_formula_with_severity(source_inputs):
    _, indicators, original, panel, _, yearly = source_inputs
    quality, ready = require_wgi_source_matrix(panel, indicators)
    runs, summary = full_country_reruns(
        yearly, indicators, quality, ready, original, draws=4, seed=42,
    )
    assert len(runs) == 16
    assert len(summary) == 4
    assert runs["severity_was_recalculated"].all()
    assert runs["wgi_correlation_assumed_independent"].all()
    assert not runs["actual_world_bank_uncertainty_verified"].any()
    assert runs["real_outcome_probability"].eq("NOT_ESTIMATED").all()
    assert set(runs["country"]) == {"Testland", "Example Republic"}
    assert summary["interpretation"].eq(
        "TOY_SENSITIVITY_NOT_STATISTICAL_RISK_CI"
    ).all()
    repeat, repeat_summary = full_country_reruns(
        yearly, indicators, quality, ready, original, draws=4, seed=42,
    )
    pd.testing.assert_frame_equal(runs, repeat)
    pd.testing.assert_frame_equal(summary, repeat_summary)


def test_missing_governance_prevents_simulated_country_scores(source_inputs):
    _, indicators, original, panel, _, yearly = source_inputs
    reduced = panel[~(
        panel.country.eq("Testland") & panel.indicator.eq("government_effectiveness")
    )]
    matrix, readiness = require_wgi_source_matrix(reduced, indicators)
    with pytest.raises(SourceEvidenceError, match="withhold"):
        full_country_reruns(yearly, indicators, matrix, readiness, original, draws=2)


def test_synthetic_evidence_releases_reproduce_without_network(synthetic_upstream, tmp_path):
    a, b = tmp_path / "audit-a", tmp_path / "audit-b"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("HTTP not allowed")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("Network not allowed")):
        first = run_source_uncertainty(synthetic_upstream, a, draws=3, seed=42)
        second = run_source_uncertainty(synthetic_upstream, b, draws=3, seed=42)
    assert first == second
    assert first["status"] == STATUS
    assert first["source_dimension_cells"] == 10
    assert first["event_source_records"] == 20
    assert first["missing_scored_dimension_countries_withheld"] == 1
    assert first["full_country_scorer_rerun"]
    assert not first["complete_live_27_stage_pipeline_rerun"]
    assert not first["source_completeness_authenticated"]
    assert not first["real_wgi_standard_errors_verified"]
    assert first["toy_simulated_score_rows"] == 12
    assert first["toy_draws_per_scenario"] == 3
    assert len(first["output_sha256"]) == 9
    assert (a / "source_uncertainty_receipt.json").read_bytes() == (
        b / "source_uncertainty_receipt.json"
    ).read_bytes()
    for rel in first["output_sha256"]:
        assert (a / rel).read_bytes() == (b / rel).read_bytes()
    memo = (a / "SOURCE_UNCERTAINTY_FINDINGS.md").read_text()
    assert "NOT externally validated" in memo
    assert "NOT_ISSUED" not in memo or "protection" in memo.lower()
    assert "2026" in memo and "2024" in memo


def test_upstream_tampering_blocks_and_original_is_untouched(synthetic_upstream, tmp_path):
    existing = tmp_path / "old"
    existing.mkdir()
    (existing / "keep.txt").write_text("preserved")
    with pytest.raises(FileExistsError):
        run_source_uncertainty(synthetic_upstream, existing, draws=1)
    assert (existing / "keep.txt").read_text() == "preserved"

    compromised = tmp_path / "compromised"
    shutil.copytree(synthetic_upstream, compromised)
    file = compromised / "data/raw/acled_events.csv"
    file.write_bytes(file.read_bytes() + b"\n")
    target = tmp_path / "should-not-exist"
    with pytest.raises(MethodologyAuditError, match="no longer match receipt"):
        run_source_uncertainty(compromised, target, draws=1)
    assert not target.exists()
    assert not list(tmp_path.glob(".source-uncertainty-incomplete-*"))
