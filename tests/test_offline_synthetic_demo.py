"""Offline synthetic integration: reproducibility and failure isolation."""
import csv
import json
import shutil
from unittest.mock import patch

import pytest

from src.offline_synthetic_demo import FIXTURES, run_demo
from src.preflight import PreflightError


def test_repeated_real_scoring_is_deterministic_and_offline(tmp_path):
    first = tmp_path / "run-1"
    second = tmp_path / "run-2"
    # This check will fail on even an accidental request made by an imported
    # production helper. No credentials, outside data or network are needed.
    with patch("requests.sessions.Session.request",
               side_effect=AssertionError("Internet request in offline demo")), \
         patch("socket.socket.connect",
               side_effect=AssertionError("Socket connection in offline demo")):
        receipt_1 = run_demo(first)
        receipt_2 = run_demo(second)

    assert receipt_1 == receipt_2
    assert json.loads((first / "run_receipt.json").read_text()) == receipt_1
    assert receipt_1["status"] == "PASS_SYNTHETIC_INTEGRATION_NOT_OPERATIONAL_VALIDATION"
    assert receipt_1["model_versions"]["country_baseline_year"] == 2024
    assert receipt_1["source_windows"]["forward_2026_model"] == "NOT_RUN"
    assert receipt_1["record_counts"]["raw_synthetic_events"] == 20
    assert receipt_1["record_counts"]["baseline_countries"] == 2
    assert receipt_1["record_counts"]["cities"] == 2
    assert receipt_1["record_counts"]["synthetic_movements"] == 2
    assert receipt_1["record_counts"]["evidence_coverage_records"] == 2
    assert receipt_1["monte_carlo"] == {
        "seed": 42, "runs": 25,
        "interpretation": "Randomized uncalibrated weights, not predictive validation",
    }
    assert not receipt_1["quality_flags"]["verified_source_completeness"]
    assert not receipt_1["quality_flags"]["verified_incident_prediction"]
    assert receipt_1["quality_flags"]["acled_stale"] == 0
    assert receipt_1["quality_flags"]["city_context_missing"] == 0
    assert receipt_1["input_sha256"]["acled_events.csv"]
    assert receipt_1["evidence_sha256"]
    assert "reports/synthetic_research_demo.pdf" in receipt_1["output_sha256"]
    assert (first / "reports" / "synthetic_research_demo.pdf").read_bytes().startswith(b"%PDF")
    assert (first / "reports" / "synthetic_research_demo.pdf").stat().st_size > 1000

    for rel in receipt_1["output_sha256"]:
        assert (first / rel).read_bytes() == (second / rel).read_bytes()
    assert "SYNTHETIC" in (first / "data/raw/acled_events.csv").read_text()
    assert not (first / "data/raw").joinpath(".env").exists()


def altered_fixtures(tmp_path):
    target = tmp_path / "fixture-copy"
    return shutil.copytree(FIXTURES, target)


def test_missing_history_aborts_without_published_outputs(tmp_path):
    fixtures = altered_fixtures(tmp_path)
    event_path = fixtures / "acled_events.csv"
    with event_path.open(newline="", encoding="utf-8") as f:
        source = csv.DictReader(f)
        fields = source.fieldnames
        rows = [row for row in source if row["year"] == "2026"]
    with event_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    output = tmp_path / "should-not-exist"
    with pytest.raises(PreflightError, match="Historical ACLED baseline years missing"):
        run_demo(output, fixture_dir=fixtures)
    assert not output.exists()
    assert not list(tmp_path.glob(".offline-demo-incomplete-*"))


def test_missing_capacity_aborts_before_publication(tmp_path):
    fixtures = altered_fixtures(tmp_path)
    capacity = fixtures / "protective_capacity_inputs.csv"
    lines = capacity.read_text().splitlines()
    # Intentionally make an assessed field blank; hash the modified fixture
    # to ensure it fails on genuine content validation, not stale hashes.
    lines[1] = lines[1].replace(",75,80,", ",,80,", 1)
    capacity.write_text("\n".join(lines) + "\n")
    output = tmp_path / "should-not-exist"
    with pytest.raises(PreflightError, match="Missing or invalid capacity inputs"):
        run_demo(output, fixture_dir=fixtures)
    assert not output.exists()
    assert not list(tmp_path.glob(".offline-demo-incomplete-*"))


def test_refuse_overwrite_and_preserve_existing_results(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("original result must survive")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        run_demo(output)
    assert sentinel.read_text() == "original result must survive"


def test_reject_non_synthetic_event_rows(tmp_path):
    fixtures = altered_fixtures(tmp_path)
    event_path = fixtures / "acled_events.csv"
    event_path.write_text(event_path.read_text().replace(
        "SYN-001", "REAL-001", 1,
    ))
    output = tmp_path / "unpublished"
    with pytest.raises(ValueError, match="solely of synthetic"):
        run_demo(output, fixture_dir=fixtures)
    assert not output.exists()
