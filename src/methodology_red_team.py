"""Offline synthetic methodological red team; NOT external or operational validation.

Consumes a previously verified offline synthetic integration result. Produces
source-year presence tables, missingness and cohort-normalization probes,
weight-only component ablations, and a structural severity-overlap audit.
Historical data and analytic controls remain entirely fictional.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np
import pandas as pd

from src.config import END_YEAR, RISK_WEIGHTS, START_YEAR
from src.risk_scoring import (
    calculate_crime_risk_score, minmax_score, assign_risk_bucket,
)
from src.offline_synthetic_demo import ROOT as PROJECT_ROOT

AUDIT_VERSION = "methodology-red-team-synthetic-v1"
DEMO_STATUS = "PASS_SYNTHETIC_INTEGRATION_NOT_OPERATIONAL_VALIDATION"
AUDIT_STATUS = "RESEARCH_WARNINGS_NOT_EMPIRICAL_VALIDATION"
FICTIONAL_COUNTRIES = {"Testland", "Example Republic"}
UPLIFT_COMPONENTS = {
    "extreme_conflict_uplift": "political violence / civil unrest",
    "fatality_severity_uplift": "political violence / fatalities",
    "geographic_spread_uplift": "political violence / geographic spread",
    "compound_governance_violence_uplift": "governance + political violence",
    "strategic_energy_instability_uplift": "energy exposure + governance / conflict",
    "momentum_uplift": "event or fatality momentum",
}


class MethodologyAuditError(ValueError):
    """The source evidence, demo output, or scoring contract cannot be trusted."""


def file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _verified_path(root: Path, path: str) -> Path:
    rel = Path(path)
    if rel.is_absolute() or ".." in rel.parts or path.startswith("~"):
        raise MethodologyAuditError("Unsafe relative evidence path")
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise MethodologyAuditError(f"Referenced evidence file missing or unsafe: {path}")
    return target


def _check_hashes(root: Path, files: dict, prefix: str = "") -> None:
    if not isinstance(files, dict) or not files:
        raise MethodologyAuditError("Missing expected source/output fingerprint map")
    for rel, digest in files.items():
        if not isinstance(rel, str) or not isinstance(digest, str):
            raise MethodologyAuditError("Malformed evidence fingerprint entry")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise MethodologyAuditError(f"Invalid digest for {rel}")
        target = _verified_path(root, prefix + rel)
        if file_sha256(target) != digest:
            raise MethodologyAuditError(f"Evidence bytes no longer match receipt: {rel}")


def verify_demo(demo_dir: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Verify source receipt, source code and every saved output before analysis."""
    root = Path(demo_dir).resolve()
    receipt_path = _verified_path(root, "run_receipt.json")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (ValueError, TypeError) as exc:
        raise MethodologyAuditError("Unreadable synthetic run receipt") from exc
    if (receipt.get("status") != DEMO_STATUS
            or receipt.get("data_class") != "synthetic"
            or receipt.get("model_versions", {}).get("country_baseline_year") != END_YEAR):
        raise MethodologyAuditError("Only the dated synthetic research demo is supported")
    flags = receipt.get("quality_flags", {})
    if (flags.get("verified_incident_prediction") is not False
            or flags.get("verified_source_completeness") is not False):
        raise MethodologyAuditError("Synthetic receipt must not claim external validity")
    _check_hashes(root, receipt["input_sha256"], prefix="data/raw/")
    _check_hashes(root, {"rpr1_evidence.json": receipt["evidence_sha256"]},
                  prefix="data/raw/")
    _check_hashes(root, receipt["output_sha256"])
    _check_hashes(PROJECT_ROOT, receipt["model_source_sha256"])

    events = pd.read_csv(_verified_path(root, "data/raw/acled_events.csv"), dtype=str)
    country = pd.read_csv(_verified_path(root, "data/raw/country_indicators.csv"))
    ranking = pd.read_csv(_verified_path(root, "tables/executive_protection_risk_rankings.csv"))
    if (events.empty or events["event_id_cnty"].duplicated().any()
            or not events["event_id_cnty"].str.startswith("SYN-").all()
            or not events["notes"].eq("SYNTHETIC").all()
            or set(events["country"]) != FICTIONAL_COUNTRIES):
        raise MethodologyAuditError("Event sources are not the canonical synthetic sample")
    if (set(country["country"]) != FICTIONAL_COUNTRIES
            or country["country"].duplicated().any()
            or set(ranking["country"]) != FICTIONAL_COUNTRIES
            or ranking["country"].duplicated().any()
            or not ranking["source_data_class"].eq("SYNTHETIC_TEST_ONLY").all()):
        raise MethodologyAuditError("Country inputs/outputs are not synthetic or unique")

    event_dates = pd.to_datetime(events["event_date"], errors="coerce",
                                 format="%Y-%m-%d")
    years = pd.to_numeric(events["year"], errors="coerce")
    if (event_dates.isna().any() or years.isna().any()
            or not years.eq(event_dates.dt.year).all()):
        raise MethodologyAuditError("Invalid event-year provenance")
    recorded = receipt["source_windows"]
    if (recorded["historical_baseline"] != [START_YEAR, END_YEAR]
            or recorded["all_events_from"] != event_dates.min().date().isoformat()
            or recorded["all_events_through"] != event_dates.max().date().isoformat()
            or recorded["city_windows_anchored_to"] != event_dates.max().date().isoformat()
            or recorded["forward_2026_model"] != "NOT_RUN"):
        raise MethodologyAuditError("Source date windows do not reconcile to receipt")
    if event_dates.max().date() > date.fromisoformat(receipt["assessment_date"]):
        raise MethodologyAuditError("Future event observations present")
    for key, n in (
        ("raw_synthetic_events", len(events)),
        ("baseline_countries", len(ranking)),
    ):
        if receipt["record_counts"][key] != n:
            raise MethodologyAuditError(f"Recorded row count incorrect: {key}")
    return receipt, events, country, ranking


def source_year_presence(events: pd.DataFrame, receipt: dict) -> pd.DataFrame:
    """Observation presence only; never asserts data completeness or quiet-area safety."""
    dates = pd.to_datetime(events["event_date"], format="%Y-%m-%d", errors="raise")
    as_of = date.fromisoformat(receipt["assessment_date"])
    rows = []
    for country in sorted(FICTIONAL_COUNTRIES):
        subset = events.loc[events["country"].eq(country)].copy()
        subset["parsed_date"] = dates.loc[subset.index]
        for year in range(START_YEAR, as_of.year + 1):
            period = subset[subset["parsed_date"].dt.year.eq(year)]
            latest = period["parsed_date"].max()
            rows.append({
                "country": country,
                "calendar_year": year,
                "model_period": (
                    "2024_structural_baseline" if year <= END_YEAR
                    else "later_observation_not_in_structural_baseline"
                ),
                "event_records_in_fixture": len(period),
                "latest_observed_event_date": (
                    latest.date().isoformat() if pd.notna(latest) else ""
                ),
                "observation_status": (
                    "PRESENCE_ONLY_NOT_COMPLETENESS" if len(period)
                    else "NO_RECORDED_EVENT_NOT_NO_RISK"
                ),
                "source_authenticity": "FICTIONAL_NOT_AUTHENTICATED",
            })
    return pd.DataFrame(rows)


def weight_only_ablation(rankings: pd.DataFrame) -> pd.DataFrame:
    """Leave each component out and renormalize remaining weights, fixing uplift.

    IMPORTANT: Severity uplift depends on some of the excluded concepts, so
    this is NOT a complete causal ablation of the associated threat construct.
    """
    columns = set(RISK_WEIGHTS) | {
        "country", "baseline_rank", "weighted_ep_risk_score",
        "severity_uplift_total", "executive_protection_risk_score",
    }
    if not columns.issubset(rankings):
        raise MethodologyAuditError("Missing weighted baseline or component score")
    if abs(sum(RISK_WEIGHTS.values()) - 1.0) > 1e-9:
        raise MethodologyAuditError("Model component weights do not sum to one")
    for col in RISK_WEIGHTS:
        vals = pd.to_numeric(rankings[col], errors="coerce")
        if (~np.isfinite(vals) | ~vals.between(0, 100)).any():
            raise MethodologyAuditError(f"Unusable component values: {col}")

    baseline_calc = sum(
        pd.to_numeric(rankings[name]) * weight
        for name, weight in RISK_WEIGHTS.items()
    )
    if not np.allclose(
        baseline_calc, rankings["weighted_ep_risk_score"], atol=0.02, rtol=0
    ):
        raise MethodologyAuditError("Stored weighted score cannot be reconstructed")
    rows = []
    for excluded, removed_weight in RISK_WEIGHTS.items():
        new_weights = {
            name: value / (1 - removed_weight)
            for name, value in RISK_WEIGHTS.items() if name != excluded
        }
        score = sum(
            pd.to_numeric(rankings[name]) * weight
            for name, weight in new_weights.items()
        ) + pd.to_numeric(rankings["severity_uplift_total"])
        scored = rankings[["country", "baseline_rank",
                           "executive_protection_risk_score"]].copy()
        scored["counterfactual_score"] = score.clip(0, 100)
        scored = scored.sort_values(
            ["counterfactual_score", "country"], ascending=[False, True],
        ).reset_index(drop=True)
        scored["ablation_rank"] = scored.index + 1
        for item in scored.itertuples():
            rows.append({
                "country": item.country,
                "excluded_component": excluded,
                "method": "WEIGHT_REMOVED_RENORMALIZED_UPLIFT_FIXED",
                "original_score": round(float(item.executive_protection_risk_score), 4),
                "ablation_score": round(float(item.counterfactual_score), 4),
                "score_delta": round(
                    float(item.counterfactual_score - item.executive_protection_risk_score), 4
                ),
                "original_rank": int(item.baseline_rank),
                "ablation_rank": int(item.ablation_rank),
                "rank_delta": int(item.ablation_rank - item.baseline_rank),
                "retained_severity_adjustments": True,
                "not_full_construct_removal": True,
            })
    return pd.DataFrame(rows).sort_values(
        ["excluded_component", "country"]
    ).reset_index(drop=True)


def cohort_dependence(indicators: pd.DataFrame) -> pd.DataFrame:
    """Introduce an invented extreme homicide-rate comparator to one component.

    Does not recompute other components, severity adjustments or full rankings.
    """
    sorted_country = indicators.sort_values("country").reset_index(drop=True)
    raw = pd.to_numeric(sorted_country["homicide_rate_per_100k"], errors="coerce")
    if (len(raw) < 2 or raw.isna().any() or (raw < 0).any()
            or raw.nunique() < 2 or raw.max() <= 0):
        raise MethodologyAuditError("At least two distinct valid homicide inputs needed")
    extreme = float(raw.max()) * 10
    augmented = pd.concat([
        raw, pd.Series([extreme], dtype=float),
    ], ignore_index=True)
    initial = minmax_score(raw)
    adjusted = minmax_score(augmented)
    rows = []
    for i, row in sorted_country.iterrows():
        rows.append({
            "country": row["country"],
            "scenario": "ORIGINAL_VS_FICTIONAL_EXTREME_COMPARATOR",
            "original_homicide_input": float(raw.iloc[i]),
            "introduced_outlier_input": extreme,
            "original_component_score": round(float(initial.iloc[i]), 6),
            "expanded_cohort_component_score": round(float(adjusted.iloc[i]), 6),
            "score_delta": round(float(adjusted.iloc[i] - initial.iloc[i]), 6),
            "full_model_rescored": False,
        })
    rows.append({
        "country": "Fictional Extreme Comparator (not real)",
        "scenario": "NEW_SYNTHETIC_COMPARATOR_ONLY",
        "original_homicide_input": np.nan,
        "introduced_outlier_input": extreme,
        "original_component_score": np.nan,
        "expanded_cohort_component_score": round(float(adjusted.iloc[-1]), 6),
        "score_delta": np.nan,
        "full_model_rescored": False,
    })
    return pd.DataFrame(rows)


def missingness_stress(indicators: pd.DataFrame) -> pd.DataFrame:
    """Make inputs absent and record production's numerical defaults as warnings."""
    source = indicators.sort_values("country").reset_index(drop=True)
    raw = pd.to_numeric(source["homicide_rate_per_100k"], errors="coerce")
    if raw.isna().any() or raw.nunique() < 2:
        raise MethodologyAuditError("Missingness probe needs distinct observed inputs")
    out = []
    for scenario in ("OBSERVED", "HIGHEST_RATE_MISSING", "ALL_RATES_MISSING"):
        frame = source[["country", "homicide_rate_per_100k"]].copy()
        if scenario == "HIGHEST_RATE_MISSING":
            frame.loc[raw.idxmax(), "homicide_rate_per_100k"] = np.nan
        elif scenario == "ALL_RATES_MISSING":
            frame["homicide_rate_per_100k"] = np.nan
        unobserved = frame["homicide_rate_per_100k"].isna()
        transformed = calculate_crime_risk_score(frame)
        for i, row in transformed.iterrows():
            out.append({
                "country": row["country"],
                "scenario": scenario,
                "observed_input": (
                    float(frame.loc[i, "homicide_rate_per_100k"])
                    if not unobserved.loc[i] else np.nan
                ),
                "source_missing": bool(unobserved.loc[i]),
                "model_used_value": float(row["homicide_rate_per_100k"]),
                "resulting_crime_component_score": float(row["violent_crime_score"]),
                "policy": (
                    "ZERO_FILL_ALL_UNAVAILABLE" if scenario == "ALL_RATES_MISSING"
                    else "MEDIAN_FILL_MISSING_THEN_MINMAX"
                ),
                "meaning": "INDEX_VALUE_NOT_VERIFIED_SAFETY",
            })
    return pd.DataFrame(out)


def severity_overlap(rankings: pd.DataFrame) -> pd.DataFrame:
    """Expose the additive uplift decomposition and overlapping model constructs."""
    required = set(UPLIFT_COMPONENTS) | {
        "country", "severity_uplift_total", "severity_uplift_total_raw",
        "executive_protection_risk_score", "weighted_ep_risk_score",
    }
    if not required.issubset(rankings):
        raise MethodologyAuditError("Missing severity/uplift contract columns")
    rows = []
    for _, row in rankings.sort_values("country").iterrows():
        raw = sum(float(row[name]) for name in UPLIFT_COMPONENTS)
        if (not np.isclose(raw, float(row["severity_uplift_total_raw"]), atol=0.01)
                or not np.isclose(min(raw, 25),
                                   float(row["severity_uplift_total"]), atol=0.01)):
            raise MethodologyAuditError("Severity uplift cannot be reconciled")
        weighted = float(row["weighted_ep_risk_score"])
        final = float(row["executive_protection_risk_score"])
        if not np.isclose(min(100, weighted + float(row["severity_uplift_total"])),
                          final, atol=0.025):
            raise MethodologyAuditError("Final score does not match stored uplift")
        for field, overlap in UPLIFT_COMPONENTS.items():
            rows.append({
                "country": row["country"],
                "uplift_term": field,
                "overlapping_baseline_concept": overlap,
                "points_before_aggregate_cap": float(row[field]),
                "uplift_raw_total": float(row["severity_uplift_total_raw"]),
                "uplift_applied_capped": float(row["severity_uplift_total"]),
                "uplift_cap_triggered": bool(raw > 25),
                "weighted_score": weighted,
                "final_score": final,
                "overlap_identified": True,
                "double_counting_magnitude_empirically_validated": False,
            })
    return pd.DataFrame(rows)


def _summary_markdown(receipt: dict, coverage: pd.DataFrame,
                      ablation: pd.DataFrame, cohort: pd.DataFrame,
                      missing: pd.DataFrame, overlap: pd.DataFrame) -> str:
    country_rows = cohort[
        cohort["scenario"] == "ORIGINAL_VS_FICTIONAL_EXTREME_COMPARATOR"
    ]
    largest = country_rows.loc[country_rows["score_delta"].abs().idxmax()]
    largest_ablation = ablation.loc[ablation["score_delta"].abs().idxmax()]
    all_missing = missing[missing["scenario"] == "ALL_RATES_MISSING"]
    coverage_zeros = coverage["event_records_in_fixture"].eq(0).sum()
    uplifts = overlap[overlap["points_before_aggregate_cap"] > 0]
    n = int(receipt["record_counts"]["baseline_countries"])
    return (
        "# Synthetic methodology red-team findings\n\n"
        "**Verdict: NEEDS INDEPENDENT VALIDATION.** All examples are fictional.\n"
        "Neither passing this audit nor obtaining stable ranks establishes predictive "
        "accuracy, data completeness, effectiveness of protection, or travel clearance.\n\n"
        "## Scope and limitations\n\n"
        f"- Historical model year: {END_YEAR}; baseline event years {START_YEAR}-{END_YEAR}.\n"
        f"- Fictional baseline countries: {n}; cohort too small for meaningful "
        "country-level correlation estimates. No real outcomes or independent labels.\n"
        "- Sensitivity probes below target *mathematical behavior of the implemented model*, "
        "not empirical estimation of real threats.\n\n"
        "## Findings\n\n"
        "1. **Cohort dependence:** the min-max homicide component of "
        f"{largest['country']} changed from {largest['original_component_score']:.2f} "
        f"to {largest['expanded_cohort_component_score']:.2f} when an additional "
        "entirely fictional high-rate comparator was inserted, without altering "
        "either original country's inputs. This test does not recalculate the whole model.\n"
        "2. **Missingness can look neutral:** when both invented homicide inputs "
        "are absent, the existing risk-scoring function uses zero-valued proxies "
        f"and returns component score(s) {sorted(all_missing['resulting_crime_component_score'].unique().tolist())}. "
        "Those values are not verified safety measurements. A separate experiment "
        "removes only the highest input; inspect the missingness table for how "
        "scores of *both* countries change.\n"
        "3. **Component-weight dependence:** excluding one weighted component, "
        "renormalizing the remainder, and retaining the model's severity adjustment "
        f"produced a maximum synthetic absolute score shift of "
        f"{abs(largest_ablation['score_delta']):.2f} points "
        f"({largest_ablation['excluded_component']}; {largest_ablation['country']}). "
        "These are weight-only ablations, not complete construct removals.\n"
        "4. **Overlapping constructs:** severity uplift contains conflict, fatality, "
        "spread, governance, energy and momentum concepts already represented in "
        f"the baseline. {len(uplifts)} of {len(overlap)} uplift-term/country cells "
        "are positive in this toy case. This is structural overlap, not a quantified "
        "estimate of statistical double counting.\n"
        "5. **Provenance presence only:** "
        f"{coverage_zeros} of {len(coverage)} fictional country-year cells contain "
        "no event records. Nonzero counts prove only that fake observations were "
        "provided; absence is **not** zero risk. ACLED source reporting and WGI "
        "estimation uncertainty have **not** been validated by this example.\n\n"
        "## Required next gates\n\n"
        "- Validate licensed ACLED extract receipts, observed/revised vintages, "
        "event-date precision, country-year sampling, geographic reporting limitations "
        "and coverage against source documentation.\n"
        "- Retrieve country-level WGI estimate uncertainty, indicator year and "
        "revisions; treat close cross-country estimates as indistinguishable when "
        "their intervals overlap.\n"
        "- Run **whole-pipeline** source/component exclusions and cohort additions "
        "using frozen, reproducible data before interpreting stable country rankings.\n"
        "- Predefine practitioner-reviewed risk constructs and evaluation outcomes; "
        "independent validation requires real ground truth collected ethically.\n"
        "- Preserve CI receipts, versioned score assumptions and negative findings. "
        "Do not convert these indices into incident probabilities.\n\n"
        "## Documentation for source limitations\n\n"
        "- ACLED, Keeping Data Updated: "
        "https://acleddata.com/methodology/keeping-acled-data-updated\n"
        "- ACLED Codebook: https://acleddata.com/methodology/acled-codebook\n"
        "- World Bank WGI Documentation: "
        "https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation\n"
    )


def run_audit(demo_dir: Path, output_dir: Path) -> dict:
    """Verify first; publish only a complete, explicitly nonoperational audit."""
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError("Refusing to overwrite an existing methodology audit")
    upstream, events, indicators, rankings = verify_demo(demo_dir)
    coverage = source_year_presence(events, upstream)
    ablations = weight_only_ablation(rankings)
    cohort = cohort_dependence(indicators)
    missing = missingness_stress(indicators)
    overlap = severity_overlap(rankings)
    tables = {
        "country_year_observation_presence.csv": coverage,
        "component_weight_ablation.csv": ablations,
        "homicide_cohort_dependence.csv": cohort,
        "homicide_missingness_stress.csv": missing,
        "severity_construct_overlap.csv": overlap,
    }
    source_receipt_hash = file_sha256(
        Path(demo_dir).resolve() / "run_receipt.json"
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".methodology-incomplete-", dir=output_dir.parent
    ) as stage_str:
        stage = Path(stage_str)
        for name, table in tables.items():
            table.to_csv(stage / name, index=False, float_format="%.6f")
        (stage / "METHOD_REVIEW.md").write_text(
            _summary_markdown(upstream, coverage, ablations, cohort, missing, overlap),
            encoding="utf-8",
        )
        receipt = {
            "status": AUDIT_STATUS,
            "audit_version": AUDIT_VERSION,
            "data_class": "synthetic",
            "upstream_receipt_sha256": source_receipt_hash,
            "audit_source_sha256": file_sha256(
                PROJECT_ROOT / "src" / "methodology_red_team.py"
            ),
            "source_model_baseline": END_YEAR,
            "baseline_country_count": int(len(rankings)),
            "summary": {
                "country_year_cells": int(len(coverage)),
                "country_year_cells_without_observations": int(
                    coverage["event_records_in_fixture"].eq(0).sum()
                ),
                "ablation_rows": int(len(ablations)),
                "cohort_probe_rows": int(len(cohort)),
                "missingness_probe_rows": int(len(missing)),
                "overlap_rows": int(len(overlap)),
                "correlation_estimate_status": (
                    "NOT_ESTIMATED_TINY_SYNTHETIC_COHORT"
                ),
                "source_completeness_verified": False,
                "external_predictive_validity_established": False,
            },
            "output_sha256": {
                name: file_sha256(stage / name)
                for name in sorted([*tables, "METHOD_REVIEW.md"])
            },
            "limitations": [
                "Fictional input population of two countries; not statistical validation.",
                "Only a single homicide component is perturbed in cohort/missingness tests.",
                "Weight ablations retain severity, including overlapping concepts.",
                "Year presence cannot verify event reporting completeness.",
                "No independent practitioner assessments or real outcome labels.",
                "Not an operational go/no-go or individual security assessment.",
            ],
        }
        (stage / "methodology_receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            raise FileExistsError("Methodology audit target appeared during processing")
        os.replace(stage, output_dir)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.demo_dir, args.output_dir)
    print(json.dumps({
        "status": result["status"],
        "audit_version": result["audit_version"],
        "summary": result["summary"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
