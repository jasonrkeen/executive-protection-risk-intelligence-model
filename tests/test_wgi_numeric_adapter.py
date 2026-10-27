"""Fictional numeric fixtures, not provider evidence or calibrated uncertainty."""
from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from unittest.mock import patch

import pytest

import src.wgi_numeric_adapter as module
from src.wgi_numeric_adapter import AdapterError, FIELDS, UNITS, build_bundles, load_values, run
from src.wgi_observation_policy import Coverage, Policy, json_hash
from src.provider_verification import WGIContract, VerificationError
from src.wgi_parity import ParityConfig, urls

AS_OF = date(2026, 10, 26)
STRICT = Policy("strict", 0, ("PV", "RL", "CC", "GE"))
LAGGED = replace(STRICT, name="lagged", max_age_years=1)
TOY = {"EST": -3.1, "SE": .23456789, "SR": 7, "SC": 12.3456789, "SC_LB": 0, "SC_UB": 25.6789012}


def values(year=2025):
    return {("AAA", year, f"GOV_WGI_{d}.{f}"): v for d in STRICT.required_dimensions for f, v in TOY.items()}


def adapt(v=None, year=2025, policy=STRICT, coverage=None):
    return build_bundles(values() if v is None else v, coverage or [Coverage("AAA", 2025, frozenset())], "AAA", year, policy, AS_OF)


def test_preserves_values_units_and_outside_typical_estimate_range():
    decision, bundles = adapt()
    assert len(bundles) == 4 and decision["policy_eligible"]
    for b in bundles:
        assert (b.estimate, b.estimate_standard_error, b.source_count, b.governance_score, b.score_ci90_lower, b.score_ci90_upper) == tuple(TOY[f] for f in FIELDS)
        assert b.target_year == b.observation_year == 2025
    assert UNITS["SE"] == UNITS["EST"] != UNITS["SC_LB"]
    assert UNITS["SC"] == UNITS["SC_LB"] == UNITS["SC_UB"]


def test_zero_estimate_and_boundary_score_are_valid():
    v = values()
    for d in STRICT.required_dimensions:
        for f, n in {"EST": 0, "SC": 0, "SC_LB": 0, "SC_UB": 100}.items():
            v[("AAA", 2025, f"GOV_WGI_{d}.{f}")] = n
    _, bundles = adapt(v)
    assert all(b.estimate == 0 and b.governance_score == 0 for b in bundles)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), True, "0.5"])
def test_each_field_rejects_missing_nonfinite_bool_and_strings(field, bad):
    v = values(); v[("AAA", 2025, f"GOV_WGI_PV.{field}")] = bad
    with pytest.raises(AdapterError): adapt(v)


@pytest.mark.parametrize("field,bad", [("SE", 0), ("SE", -.1), ("SR", 0), ("SR", 1.5), ("SC", 101), ("SC_LB", -1), ("SC_LB", 20), ("SC_UB", 10), ("SC_UB", 101)])
def test_uncertainty_and_scale_invariants(field, bad):
    v = values(); v[("AAA", 2025, f"GOV_WGI_PV.{field}")] = bad
    with pytest.raises(AdapterError): adapt(v)


def test_older_numeric_rows_cannot_patch_selected_bundle():
    v = {**values(2024), **values(2025)}
    del v[("AAA", 2025, "GOV_WGI_GE.SE")]
    with pytest.raises(AdapterError): adapt(v)


def test_withheld_case_emits_no_numbers_even_if_values_exist():
    decision, bundles = adapt(year=2026)
    assert not decision["policy_eligible"] and bundles == []


def test_lagged_target_keeps_original_year_and_uncertainty():
    _, bundles = adapt(year=2026, policy=LAGGED)
    assert all(b.observation_year == 2025 and b.target_year == 2026 for b in bundles)
    assert all(b.estimate_standard_error == TOY["SE"] for b in bundles)


def test_historical_target_does_not_select_future_values():
    v = {**values(2024), **values(2025)}
    v[("AAA", 2025, "GOV_WGI_PV.EST")] = 9
    _, bundles = adapt(v, year=2024, coverage=[Coverage("AAA", y, frozenset()) for y in (2024, 2025)])
    assert all(b.observation_year == 2024 and b.estimate == TOY["EST"] for b in bundles)


def package(tmp_path):
    """Construct a small synthetic API package with real-schema envelopes."""
    raw = tmp_path / "raw"; raw.mkdir()
    contract = WGIContract.load()
    expected = urls(ParityConfig.load(), contract)
    source = {"id": "3", "name": contract.source_name, "lastupdated": "2026-09-25"}
    def envelope(rows, **extra):
        return [{"page": 1, "pages": 1, "total": len(rows), **extra}, rows]
    bodies = {"workbook.xlsx": b"FICTIONAL UNUSED WORKBOOK BYTES",
        "source.json": envelope([source]),
        "indicators.json": envelope([{"id": f"GOV_WGI_{d}.{f}", "name": f"{name} - {meaning}", "source": {"id": "3"}}
                                      for d, name in contract.dimensions.items() for f, meaning in contract.fields.items()]),
        "countries.json": {"page": 1, "pages": 1, "total": 1, "source": [{"id": "3", "concept": [{"id": "country", "variable": [{"id": "AAA", "value": "Fictional A"}]}]}]}}
    for i in contract.indicator_ids:
        field = i.split(".")[1]
        bodies[f"{i}.json"] = envelope([{"countryiso3code": "AAA", "country": {"value": "Fictional A"}, "date": "2025", "indicator": {"id": i}, "value": TOY[field]}], sourceid="3", lastupdated=source["lastupdated"])
    manifest = []
    for filename, url in expected.items():
        body = bodies[filename]
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        (raw / filename).write_bytes(b)
        manifest.append({"file": filename, "url": url, "sha256": hashlib.sha256(b).hexdigest(), "retrieved_at_utc": "2026-10-26T12:00:00+00:00"})
    (raw / "manifest.json").write_text(json.dumps(manifest))
    coverage = tmp_path / "coverage.csv"
    coverage.write_text("country_code,year,matched,missing_dimensions,complete_36_field_parity\nAAA,2025,36,,True\n")
    receipt = {"source": source, "requests": manifest, "country_count": 1, "years": [2025, 2025],
               "coverage_csv_sha256": hashlib.sha256(coverage.read_bytes()).hexdigest(), "status": "PARITY_ON_AVAILABLE_CELLS", "exceptions": [],
               "data_class": "REAL_PUBLIC_AGGREGATE_COMPARISON_METADATA", "release_label": "FICTIONAL_TEST_RELEASE"}
    rp = tmp_path / "parity.json"; rp.write_text(json.dumps(receipt))
    pc = {"assessment_date": "2026-10-26", "target_years": [2025, 2026], "required_dimensions": list(STRICT.required_dimensions),
          "policies": [{"name": p.name, "max_age_years": p.max_age_years} for p in (STRICT, LAGGED)], "parity_receipt_canonical_sha256": json_hash(receipt)}
    pp = tmp_path / "policy.json"; pp.write_text(json.dumps(pc))
    ap = tmp_path / "adapter.json"; ap.write_text(json.dumps({"implementation_date": "2026-10-27", "policy_config_canonical_sha256": json_hash(pc)}))
    return raw, coverage, receipt, {"CONFIG": ap, "POLICY_CONFIG": pp, "PARITY_RECEIPT": rp, "PRIVATE_ROOT": tmp_path}


def test_end_to_end_offline_output_is_lossless_deterministic_and_private(tmp_path):
    raw, coverage, _, settings = package(tmp_path)
    with patch.multiple(module, **settings), patch("socket.socket.connect", side_effect=AssertionError("offline only")):
        a = run(raw, coverage, tmp_path / "a")
        assert a == run(raw, coverage, tmp_path / "b")
        assert a["numeric_dimension_bundles"] == 12
        assert a["country_policy_decisions"] == 4
        records = [json.loads(s) for s in (tmp_path / "a/numeric_bundles.jsonl").read_text().splitlines()]
        for r in records:
            assert r["estimate"] == TOY["EST"] and r["estimate_standard_error"] == TOY["SE"]
            assert r["units"] == UNITS and r["confidence_interval_scale"] == "score"
            assert not r["production_use_authorized"]
            assert r["observation_year"] == 2025
            assert len(r["source_payload_sha256"]) == 6
        assert not any(r["policy"] == "strict" and r["target_year"] == 2026 for r in records)
        assert (tmp_path / "a/numeric_bundles.jsonl").read_bytes() == (tmp_path / "b/numeric_bundles.jsonl").read_bytes()
        assert "estimate" not in a and not a["numeric_values_published_in_receipt"]
        with pytest.raises(FileExistsError): run(raw, coverage, tmp_path / "a")
        with pytest.raises(AdapterError, match="ignored"): run(raw, coverage, tmp_path.parent / "public-output")


@pytest.mark.parametrize("change", ["payload", "manifest", "policy", "receipt", "coverage"])
def test_tampering_fails_before_creating_any_output(tmp_path, change):
    raw, coverage, _, settings = package(tmp_path)
    p = {"payload": raw / "GOV_WGI_PV.SE.json", "manifest": raw / "manifest.json",
         "policy": settings["POLICY_CONFIG"], "receipt": settings["PARITY_RECEIPT"], "coverage": coverage}[change]
    if change == "coverage": p.write_text(p.read_text() + "\n")
    else:
        obj = json.loads(p.read_text())
        if change == "payload": obj[1][0]["value"] = 1.0
        if change == "manifest": obj.pop()
        if change == "policy": obj["policies"][0]["max_age_years"] = 10
        if change == "receipt": obj["source"]["id"] = "75"
        p.write_text(json.dumps(obj))
    with patch.multiple(module, **settings):
        with pytest.raises(ValueError): run(raw, coverage, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_metadata_scale_substitution_is_rejected_even_in_test_manifest(tmp_path):
    raw, _, receipt, _ = package(tmp_path)
    path = raw / "indicators.json"; p = json.loads(path.read_text())
    p[1][0]["name"] = "Wrong scale: percentile rank"
    path.write_text(json.dumps(p))
    next(r for r in receipt["requests"] if r["file"] == path.name)["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (raw / "manifest.json").write_text(json.dumps(receipt["requests"]))
    with pytest.raises(VerificationError): load_values(raw, receipt)
