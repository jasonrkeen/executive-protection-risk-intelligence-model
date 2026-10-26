"""Fabricated API responses test contracts; they are NOT provider evidence."""
from copy import deepcopy
import json
import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.provider_verification import (
    WGIContract, VerificationError, unpack, verify_source,
    verify_indicators, verify_sample, run_probe,
)

C = WGIContract.load()


def envelope(rows, **extra):
    return [{"page": 1, "pages": 1, "total": len(rows), **extra}, rows]


def synthetic_inventory():
    return envelope([
        {"id": f"GOV_WGI_{d}.{f}", "name": f"{name} - {meaning}", "source": {"id": "3"}}
        for d, name in C.dimensions.items() for f, meaning in C.fields.items()
    ])


def synthetic_sample():
    toy = {"EST": 0, "SE": .2, "SR": 5, "SC": 50, "SC_LB": 40, "SC_UB": 60}
    return envelope([
        {"indicator": {"id": f"GOV_WGI_{d}.{f}"}, "countryiso3code": "USA",
         "date": "2025", "value": toy[f]}
        for d in C.dimensions for f in C.fields
    ], lastupdated="2026-09-25")


@pytest.mark.parametrize("payload", [None, [], [{"message": []}], [{}, None],
    [{"page": 1, "pages": 2, "total": 2}, [{}]], envelope([]),
    [{"page": 1, "pages": 1, "total": 2}, [{}]]])
def test_reject_error_empty_and_incomplete_pages(payload):
    with pytest.raises(VerificationError):
        unpack(payload)


def test_source_75_cannot_be_substituted_for_wgi():
    with pytest.raises(VerificationError):
        verify_source(envelope([{"id": "75", "name": "Environment, Social and Governance (ESG) Data"}]), C)


@pytest.mark.parametrize("change", ["legacy_id", "wrong_scale", "source", "duplicate", "missing"])
def test_inventory_rejects_mapping_drift(change):
    p = synthetic_inventory()
    if change == "legacy_id": p[1][0]["id"] = "CC.EST"
    if change == "wrong_scale": p[1][0]["name"] = "Control of Corruption - Percentile rank"
    if change == "source": p[1][0]["source"]["id"] = "75"
    if change == "duplicate": p[1][0] = deepcopy(p[1][1])
    if change == "missing": p[1].pop(); p[0]["total"] -= 1
    with pytest.raises(VerificationError):
        verify_indicators(p, C)


@pytest.mark.parametrize("change", ["null", "nan", "bool", "country", "year", "duplicate", "missing", "bounds", "se", "count", "vintage"])
def test_sample_fails_closed(change):
    p = synthetic_sample()
    if change == "null": p[1][0]["value"] = None
    if change == "nan": p[1][0]["value"] = float("nan")
    if change == "bool": p[1][0]["value"] = True
    if change == "country": p[1][0]["countryiso3code"] = "CAN"
    if change == "year": p[1][0]["date"] = "2024"
    if change == "duplicate": p[1][0] = deepcopy(p[1][1])
    if change == "missing": p[1].pop(); p[0]["total"] -= 1
    if change == "vintage": p[0]["lastupdated"] = "2025-09-25"
    field = {"bounds": "SC_LB", "se": "SE", "count": "SR"}.get(change)
    if field:
        next(r for r in p[1] if r["indicator"]["id"] == f"GOV_WGI_CC.{field}")["value"] = {"bounds": 101, "se": -1, "count": 1.5}[change]
    with pytest.raises(VerificationError):
        verify_sample(p, C, "2026-09-25")


def test_success_does_not_publish_sample_values_or_claim_global_readiness():
    with patch("socket.socket.connect", side_effect=AssertionError("offline test")):
        assert len(verify_indicators(synthetic_inventory(), C)) == 36
        result = verify_sample(synthetic_sample(), C, "2026-09-25")
    assert result["non_null_fields"] == 36
    assert result["values_published"] is False
    assert result["status"] == "SAMPLE_SCHEMA_VERIFIED_NOT_GLOBAL_COVERAGE"


def test_probe_refuses_overwrite_before_network(tmp_path):
    with patch("src.provider_verification.urlopen", side_effect=AssertionError("no request")):
        with pytest.raises(FileExistsError):
            run_probe(tmp_path)


def test_probe_receipt_binds_exact_bytes_and_keeps_values_local(tmp_path):
    bodies = [envelope([{"id": "3", "name": C.source_name, "lastupdated": "2026-09-25"}]),
              synthetic_inventory(), synthetic_sample(),
              envelope([{"id": "75", "name": "ESG", "lastupdated": "2026-06-24"}]),
              [{"message": [{"id": "120", "key": "Invalid value"}]}]]
    encoded = [json.dumps(p).encode() for p in bodies]

    def fake_open(url, timeout):
        assert url.startswith("https://api.worldbank.org/v2/")
        stream = BytesIO(encoded[fake_open.index])
        fake_open.index += 1
        stream.status = 200
        return stream

    fake_open.index = 0
    with patch("src.provider_verification.urlopen", side_effect=fake_open):
        result = run_probe(tmp_path / "new")
    for request, body in zip(result["requests"], encoded):
        assert request["sha256"] == hashlib.sha256(body).hexdigest()
        assert (tmp_path / "new/raw" / (request["name"] + ".json")).read_bytes() == body
    assert result["sample"]["values_published"] is False
    assert result["acled"]["data_requested"] is False
    assert "countryiso3code" not in json.dumps(result)


def test_network_failure_never_writes_success_receipt(tmp_path):
    with patch("src.provider_verification.urlopen", side_effect=TimeoutError):
        with pytest.raises(TimeoutError):
            run_probe(tmp_path / "failed")
    assert not (tmp_path / "failed/receipt.json").exists()


def test_committed_real_receipt_is_metadata_only_and_distinct_from_toys():
    receipt = json.loads((Path(__file__).resolve().parents[1] / "docs/provenance/wgi_api_receipt_20261026.json").read_text())
    assert receipt["data_class"] == "real_provider_metadata_verification"
    assert {r["id"] for r in receipt["indicators"]} == C.indicator_ids
    assert receipt["sample"]["non_null_fields"] == 36
    assert receipt["operational_readiness"] == "NOT_ESTABLISHED"
    assert receipt["acled"]["data_requested"] is False
    assert all(len(r["sha256"]) == 64 for r in receipt["requests"])
    assert "raw" not in receipt
