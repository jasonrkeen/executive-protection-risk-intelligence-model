"""Contract and presentation tests for missingness-aware *synthetic* shadow model."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.offline_synthetic_demo import ROOT, run_demo
from src.methodology_red_team import MethodologyAuditError, verify_demo
from src.scoring_integrity_candidate import (
    INDICATOR, UNIT, ScoringContractError, load_fixed_reference,
    merge_fictional_evidence, score_frozen_homicide, shadow_country_comparison,
)
from src.scoring_integrity_demo import (
    DEMO_STATUS, REFERENCE_FILE, EVIDENCE_FILE,
    compare_legacy_and_frozen_outlier, evidence_scenario, run_candidate,
)
from src.scoring_integrity_views import format_candidate_for_display, show_candidate_integrity_tab


@pytest.fixture(scope="module")
def frozen_demo(tmp_path_factory):
    output = tmp_path_factory.mktemp("candidate-upstream") / "synthetic"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("No provider data may be retrieved")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("No network connections permitted")):
        run_demo(output)
    return output


@pytest.fixture
def src_case(frozen_demo):
    _, _, indicators, rankings = verify_demo(frozen_demo)
    source = pd.read_csv(EVIDENCE_FILE, dtype=str, keep_default_na=False)
    ref = load_fixed_reference(REFERENCE_FILE)
    return indicators, rankings, source, ref


def test_candidate_is_deterministic_and_only_uses_fictional_sources(frozen_demo, tmp_path):
    first, second = tmp_path / "candidate-first", tmp_path / "candidate-second"
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("Offline candidate must not fetch")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("Offline candidate must not connect")):
        one = run_candidate(frozen_demo, first)
        two = run_candidate(frozen_demo, second)
    assert one == two
    assert one["status"] == DEMO_STATUS
    assert one["original_model_not_modified"]
    assert one["original_2024_baseline_preserved"]
    assert one["evidence_review"]["all_missing_numeric_scores_issued"] == 0
    assert one["evidence_review"]["all_missing_risk_bands_issued"] == 0
    assert not one["evidence_review"]["source_authenticity_verified"]
    assert one["record_counts"]["observed_rows"] == 2
    assert one["record_counts"]["all_missing_rows"] == 2
    assert one["record_counts"]["stress_scenarios"] == 6
    assert one["record_counts"]["stress_records"] == 12
    assert (first / "scoring_integrity_receipt.json").read_bytes() == (
        second / "scoring_integrity_receipt.json"
    ).read_bytes()
    for filename in one["output_sha256"]:
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
    pdf = first / "SYNTHETIC_CANDIDATE_SCORING_REVIEW.pdf"
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert pdf.stat().st_size > 1600
    observed = pd.read_csv(first / "candidate_shadow_comparison.csv")
    withheld = pd.read_csv(first / "candidate_all_missing_shadow.csv")
    assert observed["candidate_shadow_composite"].notna().all()
    assert not withheld["candidate_shadow_composite"].notna().any()
    assert withheld["candidate_risk_bucket"].eq("NOT_ISSUED").all()
    assert withheld["candidate_disposition"].eq("WITHHELD_REQUIRED_SOURCE_EVIDENCE").all()
    assert "WITHHELD" in format_candidate_for_display(withheld).to_string()
    decision = (first / "SCORING_DECISION_RECORD.md").read_text()
    assert "not adopted as the live model" in decision
    assert "No risk bucket" not in decision or "risk" in decision


def test_two_country_reference_anchor_matches_frozen_inputs(src_case):
    indicators, rankings, source, reference = src_case
    assert reference.data_class == "synthetic"
    assert reference.reference_min == 3
    assert reference.reference_max == 12
    assert reference.baseline_year == 2024
    values = score_frozen_homicide(merge_fictional_evidence(indicators, source), reference)
    assert dict(zip(values.country, values.candidate_component_score)) == {
        "Example Republic": 0.0, "Testland": 100.0,
    }
    assert values["candidate_review_required"].all()
    assert not values["source_authenticity_verified"].any()
    comparison = shadow_country_comparison(rankings, values)
    assert (comparison["candidate_shadow_delta"].abs() <= 0.03).all()
    assert comparison["candidate_risk_bucket"].eq("NOT_ISSUED").all()
    assert comparison["candidate_protective_posture"].eq("NOT_ISSUED").all()
    assert not comparison["underlying_other_components_verified"].any()


def test_all_missing_cannot_be_replaced_with_legacy_fifty(src_case):
    indicators, rankings, source, reference = src_case
    missing = evidence_scenario(indicators, source, reference, "ALL_MISSING")
    assert missing["candidate_component_score"].isna().all()
    assert missing["candidate_score_status"].eq("BLOCKED_SOURCE_UNAVAILABLE").all()
    comparison = shadow_country_comparison(rankings, missing)
    assert comparison["candidate_shadow_composite"].isna().all()
    assert comparison["candidate_shadow_delta"].isna().all()
    assert comparison["candidate_risk_bucket"].eq("NOT_ISSUED").all()
    assert set(format_candidate_for_display(comparison)["Research-only homicide index"]) == {"WITHHELD"}


@pytest.mark.parametrize("scenario,expected", [
    ("ONE_MISSING", "BLOCKED_SOURCE_UNAVAILABLE"),
    ("ONE_STALE", "BLOCKED_STALE"),
    ("ONE_CONFLICTING", "BLOCKED_CONFLICTING_SOURCES"),
    ("ONE_IMPUTED", "BLOCKED_IMPUTED"),
    ("ONE_INVALID_NEGATIVE", "BLOCKED_MISSING_OR_INVALID_VALUE"),
])
def test_quality_states_block_and_do_not_publish_assessments(src_case, scenario, expected):
    indicators, rankings, source, reference = src_case
    result = evidence_scenario(indicators, source, reference, scenario)
    blocked = result.loc[result.country.eq("Testland")].iloc[0]
    assert blocked["candidate_score_status"] == expected
    assert pd.isna(blocked["candidate_component_score"])
    assert blocked["candidate_review_required"]
    shadow = shadow_country_comparison(rankings, result)
    withheld = shadow.loc[shadow.country.eq("Testland")].iloc[0]
    assert pd.isna(withheld["candidate_shadow_composite"])
    assert withheld["candidate_risk_bucket"] == "NOT_ISSUED"
    assert withheld["candidate_disposition"] == "WITHHELD_REQUIRED_SOURCE_EVIDENCE"


def test_source_freshness_is_explicit_and_boundary_is_inclusive(src_case):
    indicators, _, source, ref = src_case
    source = source.copy()
    source.loc[source.country.eq("Testland"), "source_year"] = "2023"
    current = score_frozen_homicide(merge_fictional_evidence(indicators, source), ref)
    assert current.loc[current.country.eq("Testland"), "candidate_component_score"].notna().all()
    source.loc[source.country.eq("Testland"), "source_year"] = str(ref.assessment_year-ref.max_source_age_years)
    boundary = score_frozen_homicide(merge_fictional_evidence(indicators, source), ref)
    assert boundary.loc[boundary.country.eq("Testland"), "candidate_component_score"].notna().all()
    source.loc[source.country.eq("Testland"), "source_year"] = str(ref.assessment_year+1)
    future = score_frozen_homicide(merge_fictional_evidence(indicators, source), ref)
    assert future.loc[future.country.eq("Testland"), "candidate_score_status"].iloc[0] == "BLOCKED_FUTURE_VINTAGE"


def test_source_zero_is_distinct_from_missing_or_unverified(src_case):
    indicators, _, source, ref = src_case
    fixture = merge_fictional_evidence(indicators, source)
    fixture.loc[fixture.country.eq("Testland"), INDICATOR] = 0
    zero = replace(ref, reference_min=0)
    blocked = score_frozen_homicide(fixture, zero)
    assert blocked.loc[blocked.country.eq("Testland"), "candidate_score_status"].iloc[0] == "BLOCKED_ZERO_NOT_ATTESTED"
    fixture.loc[fixture.country.eq("Testland"), "source_status"] = "observed_zero"
    accepted = score_frozen_homicide(fixture, zero)
    row = accepted.loc[accepted.country.eq("Testland")].iloc[0]
    assert row["candidate_score_status"] == "RESEARCH_OBSERVED_ZERO"
    assert row["candidate_component_score"] == 0
    fixture.loc[fixture.country.eq("Testland"), INDICATOR] = 1
    conflict = score_frozen_homicide(fixture, zero)
    assert conflict.loc[conflict.country.eq("Testland"), "candidate_score_status"].iloc[0] == "BLOCKED_STATUS_VALUE_CONFLICT"


def test_frozen_reference_is_not_refit_for_added_extreme_comparator(src_case):
    indicators, _, source, ref = src_case
    table = compare_legacy_and_frozen_outlier(indicators, source, ref)
    out = table.loc[table.country.eq("Testland")].iloc[0]
    assert out["original_component_score"] == 100
    assert out["expanded_cohort_component_score"] == pytest.approx(900 / 117, abs=1e-5)
    assert out["candidate_component_score"] == 100
    assert out["fixed_reference_score_after_expansion"] == 100
    assert out["fixed_reference_score_change"] == 0
    assert out["new_extreme_comparator_score_status"] == "BLOCKED_OUTSIDE_REFERENCE"
    assert not out["full_composite_recomputed"]


def test_malformed_units_status_duplicate_grain_and_extra_country_block(src_case):
    indicators, _, source, ref = src_case
    valid = merge_fictional_evidence(indicators, source)
    bad_units = valid.copy()
    bad_units.loc[0, "unit"] = "percent"
    with pytest.raises(ScoringContractError, match="units"):
        score_frozen_homicide(bad_units, ref)
    unknown = valid.copy()
    unknown.loc[0, "source_status"] = "probably"
    with pytest.raises(ScoringContractError, match="Unknown"):
        score_frozen_homicide(unknown, ref)
    duplicate = pd.concat([valid, valid.iloc[[0]]], ignore_index=True)
    with pytest.raises(ScoringContractError, match="unique"):
        score_frozen_homicide(duplicate, ref)
    lost = source.iloc[:1]
    with pytest.raises(ScoringContractError, match="exactly"):
        merge_fictional_evidence(indicators, lost)


def test_reference_policy_rejects_inverted_range_duplicate_json_and_nonfinite(tmp_path):
    f = json.loads(Path(REFERENCE_FILE).read_text())
    f["reference_min"] = 100
    p = tmp_path / "wrong.json"
    p.write_text(json.dumps(f))
    with pytest.raises(ScoringContractError):
        load_fixed_reference(p)
    p.write_text('{"reference_id":"first","reference_id":"second"}')
    with pytest.raises(ScoringContractError, match="Duplicate"):
        load_fixed_reference(p)
    f = json.loads(Path(REFERENCE_FILE).read_text())
    f["reference_max"] = float("inf")
    p.write_text(json.dumps(f))
    with pytest.raises(ScoringContractError):
        load_fixed_reference(p)


def test_frozen_legacy_score_cannot_be_changed_silently(src_case):
    indicators, baseline, source, ref = src_case
    candidates = score_frozen_homicide(merge_fictional_evidence(indicators, source), ref)
    corrupted = baseline.copy()
    corrupted["weighted_ep_risk_score"] += 10
    with pytest.raises(ScoringContractError, match="reconstruct"):
        shadow_country_comparison(corrupted, candidates)


def test_candidate_displays_withheld_status_in_streamlit(src_case):
    indicators, baseline, source, ref = src_case
    missing = evidence_scenario(indicators, source, ref, "ALL_MISSING")
    shadow = shadow_country_comparison(baseline, missing)
    from streamlit.testing.v1 import AppTest

    # Exercise the presentation helper itself; it is intentionally not
    # installed in the live protective dashboard.
    code = (
        "import pandas as pd\n"
        "from src.scoring_integrity_views import show_candidate_integrity_tab\n"
        "from src.scoring_integrity_candidate import shadow_country_comparison\n"
        f"frame=pd.DataFrame({shadow.to_dict('records')!r})\n"
        "show_candidate_integrity_tab(frame)\n"
    )
    app = AppTest.from_string(code).run()
    assert len(app.exception) == 0
    assert len(app.warning) >= 1
    assert "WITHHELD" in app.warning[0].message
    assert len(app.dataframe) >= 1


def test_tampered_upstream_or_existing_outputs_fail_without_publication(frozen_demo, tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "protected.txt"
    marker.write_text("Existing evidence remains unchanged")
    with pytest.raises(FileExistsError):
        run_candidate(frozen_demo, target)
    assert marker.read_text() == "Existing evidence remains unchanged"

    edited = tmp_path / "corrupted-origin"
    shutil.copytree(frozen_demo, edited)
    path = edited / "tables" / "executive_protection_risk_rankings.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(MethodologyAuditError, match="no longer match receipt"):
        run_candidate(edited, tmp_path / "should-not-publish")
    assert not (tmp_path / "should-not-publish").exists()
    assert not list(tmp_path.glob(".scoring-candidate-incomplete-*"))
