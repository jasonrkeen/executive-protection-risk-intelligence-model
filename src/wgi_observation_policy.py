"""Offline research policy over hash-verified WGI coverage, never a score feed."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "docs/provenance/wgi_observation_policy.json"
RECEIPT = ROOT / "docs/provenance/wgi_parity_receipt_20261026.json"
DIMENSIONS = frozenset({"PV", "RL", "CC", "GE", "VA", "RQ"})


class PolicyError(ValueError):
    """Evidence or policy is incomplete/incompatible."""


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class Policy:
    name: str
    max_age_years: int
    required_dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not self.name or type(self.max_age_years) is not int or self.max_age_years < 0
                or not self.required_dimensions or len(set(self.required_dimensions)) != len(self.required_dimensions)
                or not set(self.required_dimensions) <= DIMENSIONS):
            raise PolicyError("Invalid policy age/dimensions")


@dataclass(frozen=True)
class Coverage:
    country: str
    year: int
    missing: frozenset[str]

    def __post_init__(self) -> None:
        if (not isinstance(self.country, str) or len(self.country) != 3
                or type(self.year) is not int or self.year < 1996
                or not isinstance(self.missing, frozenset) or not self.missing <= DIMENSIONS):
            raise PolicyError("Invalid coverage record")


def read_coverage(path: Path, receipt: dict, assessment: date) -> list[Coverage]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["coverage_csv_sha256"]:
        raise PolicyError("Coverage hash differs from frozen parity evidence")
    if (receipt.get("status") != "PARITY_ON_AVAILABLE_CELLS" or receipt.get("exceptions") != []
            or receipt.get("data_class") != "REAL_PUBLIC_AGGREGATE_COMPARISON_METADATA"
            or receipt.get("source", {}).get("id") != "3"):
        raise PolicyError("Unverified/incompatible parity evidence")
    try:
        dates = [datetime.fromisoformat(r["retrieved_at_utc"]).date() for r in receipt["requests"]]
        if not dates or max(dates) > assessment or date.fromisoformat(receipt["source"]["lastupdated"]) > assessment:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise PolicyError("Evidence unavailable at assessment date") from None
    rows, seen = [], set()
    start, end = receipt["years"]
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                country, year = r["country_code"], int(r["year"])
                parts = r["missing_dimensions"].split(";") if r["missing_dimensions"] else []
                missing = frozenset(parts)
                if (not country or len(country) != 3 or not start <= year <= end
                        or len(parts) != len(missing) or not missing <= DIMENSIONS
                        or (country, year) in seen):
                    raise ValueError
                matched = int(r["matched"])
                # This frozen snapshot has all-or-none six-field dimension bundles.
                # Do not generalize that assumption to another provider snapshot.
                if matched != 6 * (6 - len(missing)):
                    raise ValueError
                if r["complete_36_field_parity"] != str(not missing):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise PolicyError("Coverage schema, duplicate, bundle or domain mismatch") from None
            seen.add((country, year))
            rows.append(Coverage(country, year, missing))
    countries = {r.country for r in rows}
    if (len(countries) != receipt["country_count"]
            or seen != {(c, y) for c in countries for y in range(start, end + 1)}):
        raise PolicyError("Incomplete country-year grid")
    return rows


def evaluate(rows: list[Coverage], country: str, target_year: int, policy: Policy,
             assessment: date) -> dict:
    """Select one coherent year for all required dimensions; never splice years."""
    if type(target_year) is not int or target_year > assessment.year:
        raise PolicyError("Invalid/future target year")
    selected = [r for r in rows if r.country == country]
    if not selected or target_year < min(r.year for r in selected):
        raise PolicyError("Country/year outside supported evidence window")
    if len({r.year for r in selected}) != len(selected):
        raise PolicyError("Duplicate country-year")
    prior = [r for r in selected if r.year <= target_year]
    complete = [r for r in prior if not r.missing.intersection(policy.required_dimensions)]
    latest = max(complete, key=lambda r: r.year) if complete else None
    age = target_year - latest.year if latest else None
    accepted = latest is not None and age <= policy.max_age_years
    target = next((r for r in selected if r.year == target_year), None)
    status = ("RESEARCH_ELIGIBLE_EXACT_YEAR" if age == 0 else "RESEARCH_ELIGIBLE_LAGGED") if accepted else (
        "WITHHELD_STALE_COMMON_BUNDLE" if latest else "WITHHELD_NO_COMMON_BUNDLE")
    return {"country_code": country, "target_year": target_year, "policy": policy.name,
        "required_dimensions": ";".join(policy.required_dimensions), "max_age_years": policy.max_age_years,
        "decision": status, "policy_eligible": accepted,
        "selected_observation_year": latest.year if accepted else None,
        "latest_complete_candidate_year": latest.year if latest else None, "candidate_age_years": age,
        "candidate_age_at_assessment_years": assessment.year - latest.year if latest else None,
        "target_year_in_snapshot": target is not None,
        "target_missing_required_dimensions": ";".join(sorted(set(policy.required_dimensions) if target is None else target.missing.intersection(policy.required_dimensions))),
        "target_missing_informational_dimensions": ";".join(sorted(DIMENSIONS - set(policy.required_dimensions) if target is None else target.missing - set(policy.required_dimensions))),
        "assessment_date": assessment.isoformat(), "point_in_time_backtest_validated": False,
        "production_use_authorized": False}


def run(coverage_path: Path, output: Path) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if json_hash(receipt) != config["parity_receipt_canonical_sha256"]:
        raise PolicyError("Parity receipt differs from frozen policy input")
    assessment = date.fromisoformat(config["assessment_date"])
    rows = read_coverage(coverage_path, receipt, assessment)
    policies = [Policy(p["name"], p["max_age_years"], tuple(config["required_dimensions"])) for p in config["policies"]]
    if (not policies or len({p.name for p in policies}) != len(policies)
            or not config["target_years"] or len(set(config["target_years"])) != len(config["target_years"])):
        raise PolicyError("Empty/duplicate policy or target-year configuration")
    decisions = [evaluate(rows, c, y, p, assessment) for p in policies for y in config["target_years"] for c in sorted({r.country for r in rows})]
    summaries = [{"policy": p.name, "target_year": y, "decisions": dict(Counter(r["decision"] for r in decisions if r["policy"] == p.name and r["target_year"] == y))} for p in policies for y in config["target_years"]]
    result = {"data_class": "RESEARCH_POLICY_ON_REAL_COVERAGE_METADATA", "policy_status": "PROPOSED_NOT_PROVIDER_RULE_OR_PRODUCTION_APPROVAL",
        "assessment_date": assessment.isoformat(), "policies": [asdict(p) for p in policies],
        "summary": summaries, "parity_receipt_canonical_sha256": json_hash(receipt),
        "coverage_sha256": receipt["coverage_csv_sha256"], "config_canonical_sha256": json_hash(config),
        "module_sha256_lf": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest(),
        "point_in_time_backtest_validated": False, "acled": "DOCUMENTATION_ONLY_NO_REQUESTS",
        "numeric_governance_values_exported": False, "production_use_authorized": False}
    output.mkdir(parents=True, exist_ok=False)
    with (output / "country_policy_decisions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(decisions[0]))
        writer.writeheader(); writer.writerows(decisions)
    result["decision_csv_sha256"] = hashlib.sha256((output / "country_policy_decisions.csv").read_bytes()).hexdigest()
    compact = []
    for country in sorted({r["country_code"] for r in decisions}):
        entry = {"country_code": country}
        for r in decisions:
            if r["country_code"] != country:
                continue
            prefix = f"{r['policy']}_{r['target_year']}"
            entry[f"{prefix}_decision"] = r["decision"]
            entry[f"{prefix}_selected_year"] = r["selected_observation_year"]
        compact.append(entry)
    with (output / "country_policy_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(compact[0]))
        writer.writeheader(); writer.writerows(compact)
    result["summary_csv_sha256"] = hashlib.sha256((output / "country_policy_summary.csv").read_bytes()).hexdigest()
    (output / "policy_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.coverage_csv, args.output_dir)["summary"], indent=2))


if __name__ == "__main__":
    main()
