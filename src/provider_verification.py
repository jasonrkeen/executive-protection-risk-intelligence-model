"""Isolated public WGI API verification; no scoring or ACLED data access.

Network is opt-in. Raw responses remain local; the public receipt contains only
metadata, hashes and field-presence results, never country observation values.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/provenance/wgi_api_contract.json"


class VerificationError(ValueError):
    """The provider response does not establish the requested evidence."""


@dataclass(frozen=True)
class WGIContract:
    source_id: str
    source_name: str
    dimensions: dict[str, str]
    fields: dict[str, str]
    sample_country: str
    observation_year: str

    @classmethod
    def load(cls) -> WGIContract:
        return cls(**json.loads(CONTRACT.read_text(encoding="utf-8")))

    @property
    def indicator_ids(self) -> set[str]:
        return {f"GOV_WGI_{d}.{f}" for d in self.dimensions for f in self.fields}


def unpack(payload: Any) -> tuple[dict, list[dict]]:
    """Reject API error envelopes, incomplete pages and malformed bodies."""
    if (not isinstance(payload, list) or len(payload) != 2
            or not isinstance(payload[0], dict) or not isinstance(payload[1], list)):
        raise VerificationError("Invalid API envelope (including provider errors)")
    meta, rows = payload
    try:
        complete = int(meta["pages"]) == 1 and int(meta["page"]) == 1 and int(meta["total"]) == len(rows)
    except (KeyError, ValueError, TypeError):
        complete = False
    if not complete or not rows or not all(isinstance(r, dict) for r in rows):
        raise VerificationError("Empty, malformed or paginated response; no completeness claim")
    return meta, rows


def verify_source(payload: Any, contract: WGIContract) -> dict:
    _, rows = unpack(payload)
    if len(rows) != 1 or rows[0].get("id") != contract.source_id or rows[0].get("name") != contract.source_name:
        raise VerificationError("Source identity mismatch")
    updated = rows[0].get("lastupdated")
    try:
        datetime.strptime(updated, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise VerificationError("Missing/invalid provider update date") from None
    return {k: rows[0].get(k) for k in ("id", "name", "lastupdated")}


def verify_indicators(payload: Any, contract: WGIContract) -> list[dict]:
    _, rows = unpack(payload)
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids) or set(ids) != contract.indicator_ids:
        raise VerificationError("Indicator inventory changed; review mapping before use")
    result = []
    for row in rows:
        code = row["id"]
        dimension, field = code.removeprefix("GOV_WGI_").split(".", 1)
        expected = f"{contract.dimensions[dimension]} - {contract.fields[field]}"
        if row.get("name") != expected or str(row.get("source", {}).get("id")) != contract.source_id:
            raise VerificationError(f"Indicator meaning/source mismatch: {code}")
        result.append({"id": code, "name": row["name"]})
    return sorted(result, key=lambda r: r["id"])


def verify_sample(payload: Any, contract: WGIContract, updated: str) -> dict:
    """Presence/scale smoke check for one country-year, not global validation."""
    meta, rows = unpack(payload)
    if meta.get("lastupdated") != updated:
        raise VerificationError("Source/sample update dates disagree")
    values = {}
    for row in rows:
        code = row.get("indicator", {}).get("id")
        if (code not in contract.indicator_ids or code in values
                or row.get("countryiso3code") != contract.sample_country
                or row.get("date") != contract.observation_year):
            raise VerificationError("Unexpected/duplicate country-year-indicator")
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise VerificationError("Missing or nonfinite sample value; do not impute")
        values[code] = value
    if set(values) != contract.indicator_ids:
        raise VerificationError("Missing sample uncertainty fields")
    for d in contract.dimensions:
        v = {f: values[f"GOV_WGI_{d}.{f}"] for f in contract.fields}
        if v["SE"] <= 0 or v["SR"] < 1 or v["SR"] != int(v["SR"]):
            raise VerificationError("Invalid standard error/source count")
        if not 0 <= v["SC_LB"] <= v["SC"] <= v["SC_UB"] <= 100:
            raise VerificationError("Score/confidence bounds inconsistent")
    return {"country": contract.sample_country, "observation_year": contract.observation_year,
            "non_null_fields": len(values), "status": "SAMPLE_SCHEMA_VERIFIED_NOT_GLOBAL_COVERAGE",
            "values_published": False}


def run_probe(output_dir: Path) -> dict:
    """Fixed public endpoints only; exclusive output directory prevents overwrite."""
    c = WGIContract.load()
    output_dir.mkdir(parents=True, exist_ok=False)
    raw = output_dir / "raw"
    raw.mkdir()
    base = "https://api.worldbank.org/v2"
    urls = {
        "source": f"{base}/source/{c.source_id}?format=json",
        "indicators": f"{base}/source/{c.source_id}/indicator?format=json&per_page=1000",
        "sample": f"{base}/country/{c.sample_country}/indicator/{';'.join(sorted(c.indicator_ids))}?source={c.source_id}&date={c.observation_year}&format=json&per_page=1000",
        "legacy_source": f"{base}/source/75?format=json",
        "legacy_request": f"{base}/country/{c.sample_country}/indicator/PV.EST?source=75&date={c.observation_year}&format=json",
    }
    payloads, evidence = {}, []
    for name, url in urls.items():
        with urlopen(url, timeout=45) as response:
            body = response.read()
            status = response.status
        (raw / f"{name}.json").write_bytes(body)
        payloads[name] = json.loads(body)
        evidence.append({"name": name, "url": url, "http_status": status,
                         "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                         "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
    source = verify_source(payloads["source"], c)
    inventory = verify_indicators(payloads["indicators"], c)
    sample = verify_sample(payloads["sample"], c, source["lastupdated"])
    _, legacy = unpack(payloads["legacy_source"])
    legacy_error = payloads["legacy_request"]
    # Record the observed error only if it is really the provider's error envelope.
    if not (isinstance(legacy_error, list) and len(legacy_error) == 1
            and isinstance(legacy_error[0], dict) and "message" in legacy_error[0]):
        raise VerificationError("Legacy behavior changed; review rather than assume failure")
    receipt = {"schema_version": 1, "data_class": "real_provider_metadata_verification",
               "release_attribution": "2026 release documented separately; API date is not a release ID",
               "source": source, "indicators": inventory, "sample": sample,
               "legacy_source": [{k: r.get(k) for k in ("id", "name", "lastupdated")} for r in legacy],
               "legacy_request_error": legacy_error,
               "acled": {"status": "DOCUMENTATION_ONLY_ENTITLEMENT_UNKNOWN", "data_requested": False},
               "operational_readiness": "NOT_ESTABLISHED", "requests": evidence}
    (output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt in to five public World Bank requests")
    parser.add_argument("--output-dir", type=Path, required=True, help="New local directory (keep raw/ out of Git)")
    args = parser.parse_args()
    if not args.live:
        parser.error("Network access requires --live; use pytest for offline checks")
    run_probe(args.output_dir)
    print("Public WGI metadata/sample verified. No operational readiness or ACLED access established.")


if __name__ == "__main__":
    main()
