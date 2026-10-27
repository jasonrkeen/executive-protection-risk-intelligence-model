"""Fictional coverage metadata; tests do not authenticate provider evidence."""
from dataclasses import replace
from datetime import date
import csv
import hashlib
import json
from unittest.mock import patch

import pytest

import src.wgi_observation_policy as module
from src.wgi_observation_policy import Coverage, Policy, PolicyError, evaluate, json_hash, read_coverage, run

AS_OF = date(2026, 10, 26)
STRICT = Policy("strict", 0, ("PV", "RL", "CC", "GE"))
LAGGED = replace(STRICT, name="lagged", max_age_years=1)


def row(year, missing=()):
    return Coverage("AAA", year, frozenset(missing))


def decision(rows, target=2025, policy=STRICT):
    return evaluate(rows, "AAA", target, policy, AS_OF)


def test_same_year_complete_bundle_selected_without_numeric_values():
    result = decision([row(2024), row(2025)])
    assert result["selected_observation_year"] == 2025
    assert result["decision"] == "RESEARCH_ELIGIBLE_EXACT_YEAR"
    assert not result["production_use_authorized"]
    assert not result["point_in_time_backtest_validated"]
    assert not {"estimate", "risk_score", "standard_error"}.intersection(result)


@pytest.mark.parametrize("missing", [("PV",), ("RL",), ("CC",), ("GE",)])
def test_each_required_dimension_blocks_same_year(missing):
    r = decision([row(2024), row(2025, missing)])
    assert not r["policy_eligible"] and r["selected_observation_year"] is None
    assert r["latest_complete_candidate_year"] == 2024
    assert r["candidate_age_years"] == 1
    assert r["decision"] == "WITHHELD_STALE_COMMON_BUNDLE"


@pytest.mark.parametrize("missing", [("VA",), ("RQ",), ("VA", "RQ")])
def test_informational_gaps_are_visible_without_blocking_scored_dimensions(missing):
    r = decision([row(2025, missing)])
    assert r["policy_eligible"]
    assert set(r["target_missing_informational_dimensions"].split(";")) == set(missing)


def test_no_cross_year_splicing_even_when_every_dimension_exists_somewhere():
    r = decision([row(2024, ("PV",)), row(2025, ("GE",))], policy=LAGGED)
    assert r["decision"] == "WITHHELD_NO_COMMON_BUNDLE"
    assert r["selected_observation_year"] is None


@pytest.mark.parametrize("candidate,eligible", [(2025, True), (2024, True), (2023, False)])
def test_one_year_age_boundary(candidate, eligible):
    r = decision([row(candidate)], policy=LAGGED)
    assert r["policy_eligible"] == eligible
    assert r["selected_observation_year"] == (candidate if eligible else None)


def test_2026_target_preserves_2025_year_and_explicit_absence():
    r = decision([row(2025)], target=2026, policy=LAGGED)
    assert r["selected_observation_year"] == 2025 and r["candidate_age_years"] == 1
    assert not r["target_year_in_snapshot"]
    assert r["decision"] == "RESEARCH_ELIGIBLE_LAGGED"
    assert not decision([row(2025)], target=2026)["policy_eligible"]


def test_future_observation_cannot_rescue_missing_historical_bundle():
    r = decision([row(2024, ("PV",)), row(2025)], target=2024, policy=LAGGED)
    assert not r["policy_eligible"]
    assert r["latest_complete_candidate_year"] is None


def test_historical_target_age_is_not_current_data_freshness():
    r = decision([row(2024), row(2025)], target=2024)
    assert r["candidate_age_years"] == 0
    assert r["candidate_age_at_assessment_years"] == 2
    assert not r["point_in_time_backtest_validated"]


@pytest.mark.parametrize("target", [2027, True, "2025", 1990])
def test_bad_targets_rejected(target):
    with pytest.raises(PolicyError): decision([row(2025)], target=target)


def test_unknown_country_and_duplicate_year_rejected():
    with pytest.raises(PolicyError): evaluate([row(2025)], "BBB", 2025, STRICT, AS_OF)
    with pytest.raises(PolicyError): decision([row(2025), row(2025)])


@pytest.mark.parametrize("age,dims", [(-1, ("PV",)), (True, ("PV",)), (1.5, ("PV",)), (0, ()), (0, ("XX",)), (0, ("PV", "PV"))])
def test_invalid_policy_rejected(age, dims):
    with pytest.raises(PolicyError): Policy("invalid", age, dims)


def package(tmp_path, *, missing=()):
    path = tmp_path / "coverage.csv"
    headers = ["country_code", "year", "matched", "missing_dimensions", "complete_36_field_parity"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers); w.writeheader()
        for year in (2024, 2025):
            w.writerow({"country_code": "AAA", "year": year, "matched": 6 * (6 - len(missing)),
                        "missing_dimensions": ";".join(missing), "complete_36_field_parity": not missing})
    receipt = {"coverage_csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "status": "PARITY_ON_AVAILABLE_CELLS", "exceptions": [],
        "data_class": "REAL_PUBLIC_AGGREGATE_COMPARISON_METADATA",
        "source": {"id": "3", "lastupdated": "2026-09-25"},
        "requests": [{"retrieved_at_utc": "2026-10-26T12:00:00+00:00"}],
        "years": [2024, 2025], "country_count": 1}
    return path, receipt


@pytest.mark.parametrize("change", ["bytes", "receipt_status", "exceptions", "source", "future_retrieval", "future_update", "empty_dates", "country_count", "missing_year"])
def test_evidence_gates(tmp_path, change):
    path, r = package(tmp_path)
    if change == "bytes": path.write_bytes(path.read_bytes() + b"\n")
    if change == "receipt_status": r["status"] = "PARITY_EXCEPTIONS"
    if change == "exceptions": r["exceptions"] = [{"status": "MISMATCH"}]
    if change == "source": r["source"]["id"] = "75"
    if change == "future_retrieval": r["requests"][0]["retrieved_at_utc"] = "2026-10-27T12:00:00+00:00"
    if change == "future_update": r["source"]["lastupdated"] = "2026-10-27"
    if change == "empty_dates": r["requests"] = []
    if change == "country_count": r["country_count"] = 2
    if change == "missing_year": r["years"] = [2023, 2025]
    with pytest.raises(PolicyError): read_coverage(path, r, AS_OF)


def test_retrospective_release_not_available_for_2024_as_of(tmp_path):
    path, r = package(tmp_path)
    with pytest.raises(PolicyError): read_coverage(path, r, date(2024, 12, 31))


@pytest.mark.parametrize("original,replacement", [("AAA,2024", "AAA,2025"), ("36,,True", "30,,True"), ("36,,True", "30,XX,False"), ("36,,True", "36,,False")])
def test_coverage_schema_rejected_even_with_matching_test_hash(tmp_path, original, replacement):
    path, r = package(tmp_path)
    path.write_text(path.read_text().replace(original, replacement))
    r["coverage_csv_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(PolicyError): read_coverage(path, r, AS_OF)


def test_offline_run_determinism_receipt_binding_and_no_overwrite(tmp_path):
    path, receipt = package(tmp_path)
    rp = tmp_path / "receipt.json"; rp.write_text(json.dumps(receipt))
    config = {"assessment_date": AS_OF.isoformat(), "target_years": [2024, 2025, 2026],
        "required_dimensions": list(STRICT.required_dimensions),
        "policies": [{"name": "strict", "max_age_years": 0}, {"name": "lagged", "max_age_years": 1}],
        "parity_receipt_canonical_sha256": json_hash(receipt)}
    cp = tmp_path / "config.json"; cp.write_text(json.dumps(config))
    with patch.object(module, "CONFIG", cp), patch.object(module, "RECEIPT", rp), patch("socket.socket.connect", side_effect=AssertionError("no network")):
        first = run(path, tmp_path / "first")
        assert first == run(path, tmp_path / "second")
        assert not first["production_use_authorized"]
        assert not first["numeric_governance_values_exported"]
        with pytest.raises(FileExistsError): run(path, tmp_path / "first")
        receipt["country_count"] = 2; rp.write_text(json.dumps(receipt))
        with pytest.raises(PolicyError, match="receipt differs"): run(path, tmp_path / "third")
        assert not (tmp_path / "third").exists()
