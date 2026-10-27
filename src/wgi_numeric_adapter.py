"""Offline numeric research adapter. No live access, scoring or ACLED integration."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math
from pathlib import Path

from src.provider_verification import WGIContract, verify_indicators, verify_source
from src.wgi_parity import ParityConfig, country_registry, parse_api, urls
from src.wgi_observation_policy import (
    ROOT, CONFIG as POLICY_CONFIG, RECEIPT as PARITY_RECEIPT,
    Coverage, Policy, evaluate, json_hash, read_coverage,
)

CONFIG = ROOT / "docs/provenance/wgi_numeric_adapter.json"
PRIVATE_ROOT = ROOT / "data/raw"
FIELDS = ("EST", "SE", "SR", "SC", "SC_LB", "SC_UB")
UNITS = {"EST": "governance_estimate", "SE": "governance_estimate",
         "SR": "source_count", "SC": "fixed_reference_score_0_100",
         "SC_LB": "fixed_reference_score_0_100", "SC_UB": "fixed_reference_score_0_100"}


class AdapterError(ValueError):
    """Do not emit numerical data when evidence or bundle validation fails."""


@dataclass(frozen=True)
class NumericBundle:
    country_code: str
    dimension: str
    target_year: int
    observation_year: int
    policy: str
    policy_decision: str
    estimate: float
    estimate_standard_error: float
    source_count: int | float
    governance_score: float
    score_ci90_lower: float
    score_ci90_upper: float


def build_bundles(values: dict, coverage: list[Coverage], country: str, target: int,
                  policy: Policy, assessment: date) -> tuple[dict, list[NumericBundle]]:
    """Recompute policy, then build all required dimensions atomically in memory."""
    decision = evaluate(coverage, country, target, policy, assessment)
    if not decision["policy_eligible"]:
        return decision, []
    year = decision["selected_observation_year"]
    bundles = []
    for dimension in policy.required_dimensions:
        numeric = []
        for field in FIELDS:
            value = values.get((country, year, f"GOV_WGI_{dimension}.{field}"))
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise AdapterError("Selected policy bundle lacks a finite numeric field")
            numeric.append(value)
        est, se, count, score, lower, upper = numeric
        if se <= 0 or count < 1 or count != int(count):
            raise AdapterError("Invalid estimate standard error or source count")
        if not 0 <= lower <= score <= upper <= 100:
            raise AdapterError("Invalid score-space confidence bounds")
        # Estimate values need not lie in [-2.5, 2.5]; never clip or normalize.
        bundles.append(NumericBundle(country, dimension, target, year, policy.name,
                                     decision["decision"], est, se, count, score, lower, upper))
    return decision, bundles


def load_values(raw: Path, receipt: dict) -> tuple[dict, dict]:
    """Bind exact retained response bytes to the already pinned parity receipt."""
    contract, config = WGIContract.load(), ParityConfig.load()
    expected = urls(config, contract)
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    if (json_hash(manifest) != json_hash(receipt["requests"])
            or len(manifest) != len(expected) or {r["file"] for r in manifest} != set(expected)):
        raise AdapterError("Acquisition manifest differs from frozen parity evidence")
    for record in manifest:
        path = raw / record["file"]
        if (record["url"] != expected[record["file"]]
                or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]):
            raise AdapterError("Retained response URL or bytes changed")
    def read(name: str) -> object:
        return json.loads((raw / name).read_text(encoding="utf-8"))
    source = verify_source(read("source.json"), contract)
    if source != receipt["source"]:
        raise AdapterError("Source update metadata changed")
    verify_indicators(read("indicators.json"), contract)
    countries = country_registry(read("countries.json"))
    if len(countries) != receipt["country_count"]:
        raise AdapterError("Country universe changed")
    values = {}
    for indicator in sorted(contract.indicator_ids):
        rows, _ = parse_api(read(f"{indicator}.json"), indicator, countries, source["lastupdated"], config)
        values.update(rows)
    return values, {r["file"]: r for r in manifest}


def run(raw: Path, coverage_csv: Path, output: Path) -> dict:
    if not output.resolve().is_relative_to(PRIVATE_ROOT.resolve()):
        raise AdapterError("Numeric outputs must remain under ignored data/raw")
    if output.exists():
        raise FileExistsError(output)
    adapter = json.loads(CONFIG.read_text(encoding="utf-8"))
    policy_config = json.loads(POLICY_CONFIG.read_text(encoding="utf-8"))
    receipt = json.loads(PARITY_RECEIPT.read_text(encoding="utf-8"))
    if json_hash(policy_config) != adapter["policy_config_canonical_sha256"]:
        raise AdapterError("Policy configuration differs from reviewed adapter input")
    if json_hash(receipt) != policy_config["parity_receipt_canonical_sha256"]:
        raise AdapterError("Parity receipt differs from frozen policy input")
    assessment = date.fromisoformat(policy_config["assessment_date"])
    coverage = read_coverage(coverage_csv, receipt, assessment)
    values, requests = load_values(raw, receipt)
    policies = [Policy(p["name"], p["max_age_years"], tuple(policy_config["required_dimensions"])) for p in policy_config["policies"]]
    decisions, numeric = [], []
    for policy in policies:
        for target in policy_config["target_years"]:
            for country in sorted({r.country for r in coverage}):
                decision, bundles = build_bundles(values, coverage, country, target, policy, assessment)
                decisions.append(decision)
                for bundle in bundles:
                    ids = {f: f"GOV_WGI_{bundle.dimension}.{f}" for f in FIELDS}
                    numeric.append({**asdict(bundle), "data_class": "REAL_WGI_AGGREGATES_RESEARCH_ONLY",
                        "units": UNITS, "confidence_level": 0.90, "confidence_interval_scale": "score",
                        "indicator_ids": ids,
                        "source_payload_sha256": {f: requests[f"{i}.json"]["sha256"] for f, i in ids.items()},
                        "source_id": receipt["source"]["id"], "source_lastupdated": receipt["source"]["lastupdated"],
                        "release_label": receipt["release_label"], "assessment_date": assessment.isoformat(),
                        "parity_receipt_canonical_sha256": json_hash(receipt),
                        "point_in_time_backtest_validated": False, "production_use_authorized": False})
    result = {"data_class": "NUMERIC_ADAPTER_VALIDATION_METADATA_ONLY", "implementation_date": adapter["implementation_date"],
        "policy_assessment_date": assessment.isoformat(), "units": UNITS,
        "policy_config_canonical_sha256": json_hash(policy_config), "parity_receipt_canonical_sha256": json_hash(receipt),
        "coverage_sha256": receipt["coverage_csv_sha256"], "manifest_canonical_sha256": json_hash(receipt["requests"]),
        "adapter_module_sha256_lf": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest(),
        "summary": [{"policy": p.name, "target_year": y,
                     "decisions": dict(Counter(r["decision"] for r in decisions if r["policy"] == p.name and r["target_year"] == y)),
                     "numeric_dimension_bundles": sum(r["policy"] == p.name and r["target_year"] == y for r in numeric)}
                    for p in policies for y in policy_config["target_years"]],
        "numeric_dimension_bundles": len(numeric), "country_policy_decisions": len(decisions),
        "numeric_values_published_in_receipt": False, "production_use_authorized": False,
        "point_in_time_backtest_validated": False, "acled": "DOCUMENTATION_ONLY_NO_REQUESTS"}
    # All source/policy/numeric checks complete before any output is created.
    output.mkdir(parents=True, exist_ok=False)
    for filename, rows in [("numeric_bundles.jsonl", numeric), ("policy_decisions.jsonl", decisions)]:
        with (output / filename).open("w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        result[filename + "_sha256"] = hashlib.sha256((output / filename).read_bytes()).hexdigest()
    (output / "adapter_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--coverage-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.raw_dir, args.coverage_csv, args.output_dir)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
