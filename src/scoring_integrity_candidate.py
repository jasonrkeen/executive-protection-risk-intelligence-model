"""Experimental fixed-reference source-integrity scoring (research-only, no live data).

No production scoring or thresholds are changed. Missing/old/imputed/conflicting
measurements never receive a numeric candidate component score or shadow composite.
The frozen reference is fictional: it does not define real-country risk or a
validated safety threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any

import numpy as np
import pandas as pd

from src.config import RISK_WEIGHTS

VERSION = "SCORING-INTEGRITY-SHADOW-v1"
INDICATOR = "homicide_rate_per_100k"
UNIT = "per_100k_population"
STATUSES = frozenset({"observed", "observed_zero", "unavailable", "imputed", "conflicting"})
REQUIRED = frozenset({"country", INDICATOR, "source_status", "source_year", "source_ref", "unit"})
LEGACY_COMPONENT = "violent_crime_score"


class ScoringContractError(ValueError):
    """A malformed reference, dataset or join cannot yield a scored result."""


def _finite(value: Any) -> float | None:
    if value is None or pd.isna(value) or (
        isinstance(value, str) and not value.strip()
    ):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _strict_year(value: Any) -> int | None:
    numeric = _finite(value)
    if numeric is None or not numeric.is_integer():
        return None
    year = int(numeric)
    return year if 1900 <= year <= 2100 else None


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScoringContractError(f"Duplicate reference key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class FixedReference:
    reference_id: str
    indicator: str
    unit: str
    baseline_year: int
    assessment_year: int
    reference_min: float
    reference_max: float
    max_source_age_years: int
    direction: str
    data_class: str
    anchor_scope: str
    source_vintage_policy: str
    outcome_validation: str

    def __post_init__(self) -> None:
        if (
            not self.reference_id.strip()
            or self.indicator != INDICATOR
            or self.unit != UNIT
            or self.direction != "higher_value_higher_index"
            or self.data_class != "synthetic"
            or self.outcome_validation != "NONE"
            or type(self.baseline_year) is not int
            or type(self.assessment_year) is not int
            or type(self.max_source_age_years) is not int
            or self.max_source_age_years < 0
            or not 1900 <= self.baseline_year <= self.assessment_year <= 2100
            or not isinstance(self.reference_min, (int, float))
            or not isinstance(self.reference_max, (int, float))
            or not math.isfinite(self.reference_min)
            or not math.isfinite(self.reference_max)
            or not 0 <= self.reference_min < self.reference_max
            or not self.anchor_scope.strip()
            or not self.source_vintage_policy.strip()
        ):
            raise ScoringContractError("Invalid fictional fixed-reference scoring contract")


def load_fixed_reference(path: Path) -> FixedReference:
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
        if not isinstance(obj, dict):
            raise ScoringContractError("Reference must be a JSON object")
        return FixedReference(**obj)
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, ScoringContractError):
            raise
        raise ScoringContractError("Cannot load fictional fixed-reference policy") from exc


def score_frozen_homicide(frame: pd.DataFrame, reference: FixedReference) -> pd.DataFrame:
    """Withhold numeric outputs for every unverified source state.

    Observed evidence is only a *declared synthetic source observation*. An
    observed, in-range numeric index is not proof of source authenticity or
    risk accuracy, and remains a research-only component score.
    """
    if frame.empty or not REQUIRED.issubset(frame):
        raise ScoringContractError("Missing required homicide-source evidence columns")
    if frame.columns.duplicated().any():
        raise ScoringContractError("Duplicate homicide-source evidence headers")
    keys = frame["country"].astype(str).str.strip()
    if keys.eq("").any() or keys.duplicated().any():
        raise ScoringContractError("Country grain must be nonblank and unique")
    if (frame["unit"].fillna("").astype(str).str.strip() != reference.unit).any():
        raise ScoringContractError("Homicide units do not match the frozen reference")
    statuses = frame["source_status"].fillna("").astype(str).str.strip().str.lower()
    if not statuses.isin(STATUSES).all():
        raise ScoringContractError("Unknown homicide source status is not permitted")
    records = []
    for idx, country in zip(frame.index, keys):
        row = frame.loc[idx]
        status = str(row["source_status"]).strip().lower()
        value = _finite(row[INDICATOR])
        year = _strict_year(row["source_year"])
        source_ref = "" if pd.isna(row["source_ref"]) else str(row["source_ref"]).strip()
        result = "BLOCKED_UNKNOWN"
        reason = "Unverified measurement"
        risk_index = np.nan

        if status == "unavailable":
            result = "BLOCKED_SOURCE_UNAVAILABLE"
            reason = "Source unavailable; no value is treated as observed"
        elif status == "imputed":
            result = "BLOCKED_IMPUTED"
            reason = "Imputed values do not establish a measured homicide rate"
        elif status == "conflicting":
            result = "BLOCKED_CONFLICTING_SOURCES"
            reason = "Conflicting evidence requires independent source reconciliation"
        elif not source_ref:
            result = "BLOCKED_NO_SOURCE_REFERENCE"
            reason = "Observed input has no source reference"
        elif year is None:
            result = "BLOCKED_NO_VALID_SOURCE_YEAR"
            reason = "Observed input lacks a valid calendar year"
        elif year > reference.assessment_year:
            result = "BLOCKED_FUTURE_VINTAGE"
            reason = "Source observation is later than the assessment year"
        elif reference.assessment_year - year > reference.max_source_age_years:
            result = "BLOCKED_STALE"
            reason = "Source vintage exceeds the provisional research freshness policy"
        elif value is None or value < 0:
            result = "BLOCKED_MISSING_OR_INVALID_VALUE"
            reason = "Homicide input is absent, invalid or negative"
        elif status == "observed_zero" and value != 0:
            result = "BLOCKED_STATUS_VALUE_CONFLICT"
            reason = "Observed-zero declaration is inconsistent with the numeric input"
        elif status == "observed" and value == 0:
            result = "BLOCKED_ZERO_NOT_ATTESTED"
            reason = "Reported zero requires explicit observed_zero status"
        elif not reference.reference_min <= value <= reference.reference_max:
            result = "BLOCKED_OUTSIDE_REFERENCE"
            reason = "Measurement outside the frozen toy reference; do not silently clip"
        else:
            result = (
                "RESEARCH_OBSERVED_ZERO" if status == "observed_zero"
                else "RESEARCH_OBSERVED_IN_RANGE"
            )
            reason = "Declared synthetic observation, NOT externally verified"
            risk_index = round(
                100 * (value - reference.reference_min)
                / (reference.reference_max - reference.reference_min), 2
            )
        records.append({
            "country": country,
            "homicide_input": value if value is not None else np.nan,
            "source_status": status,
            "source_year": year if year is not None else np.nan,
            "source_ref": source_ref,
            "unit": reference.unit,
            "source_age_years": (
                reference.assessment_year - year if year is not None else np.nan
            ),
            "reference_id": reference.reference_id,
            "candidate_component_score": risk_index,
            "candidate_score_status": result,
            "candidate_review_required": True,
            "candidate_score_reason": reason,
            "source_authenticity_verified": False,
            "model_validity_established": False,
        })
    return pd.DataFrame(records)


def shadow_country_comparison(
    original: pd.DataFrame, candidate: pd.DataFrame
) -> pd.DataFrame:
    """Recompose a **research-only** score, keeping historical severity uplift fixed.

    No risk bucket/posture is issued; this is not a complete recalculation of
    all model constructs or a source-verified replacement.
    """
    needed = {
        "country", LEGACY_COMPONENT, "weighted_ep_risk_score",
        "severity_uplift_total", "executive_protection_risk_score",
        *RISK_WEIGHTS,
    }
    if original.empty or not needed.issubset(original):
        raise ScoringContractError("Original baseline needs all five scoring components")
    expected_c = {
        "country", "candidate_component_score", "candidate_score_status",
        "candidate_review_required",
    }
    if candidate.empty or not expected_c.issubset(candidate):
        raise ScoringContractError("Candidate scoring records are required")
    for data, label in ((original, "baseline"), (candidate, "candidate")):
        if data["country"].isna().any() or data["country"].duplicated().any():
            raise ScoringContractError(f"Ambiguous {label} country join")
    if set(original["country"]) != set(candidate["country"]):
        raise ScoringContractError("Candidate and baseline have different country cohorts")
    if not math.isclose(sum(RISK_WEIGHTS.values()), 1.0, abs_tol=1e-9):
        raise ScoringContractError("Historical component weights have changed")

    components = original[list(RISK_WEIGHTS)].apply(pd.to_numeric, errors="coerce")
    if (~np.isfinite(components) | ~components.between(0, 100)).any().any():
        raise ScoringContractError("Invalid original component scores")
    recomputed = sum(components[k] * v for k, v in RISK_WEIGHTS.items())
    if not np.allclose(
        recomputed, original["weighted_ep_risk_score"], atol=0.02, rtol=0
    ):
        raise ScoringContractError("Cannot reconstruct frozen historical weighted scores")

    merged = original[[
        "country", LEGACY_COMPONENT, "weighted_ep_risk_score",
        "severity_uplift_total", "executive_protection_risk_score",
    ]].merge(candidate, on="country", validate="one_to_one", sort=False)
    if merged["candidate_review_required"].ne(True).any():
        raise ScoringContractError("No candidate result is an operational approval")
    available = merged["candidate_score_status"].isin({
        "RESEARCH_OBSERVED_ZERO", "RESEARCH_OBSERVED_IN_RANGE",
    })
    if not merged["candidate_component_score"].notna().eq(available).all():
        raise ScoringContractError("Blocked numeric scores must be withheld")
    new_weighted = (
        merged["weighted_ep_risk_score"] - RISK_WEIGHTS[LEGACY_COMPONENT]
        * merged[LEGACY_COMPONENT]
        + RISK_WEIGHTS[LEGACY_COMPONENT] * merged["candidate_component_score"]
    )
    merged["candidate_shadow_weighted_score"] = new_weighted.where(available).round(2)
    merged["candidate_shadow_composite"] = (
        merged["candidate_shadow_weighted_score"] + merged["severity_uplift_total"]
    ).clip(0, 100).where(available).round(2)
    merged["candidate_shadow_delta"] = (
        merged["candidate_shadow_composite"] - merged["executive_protection_risk_score"]
    ).where(available).round(2)
    merged["candidate_disposition"] = np.where(
        available, "SHADOW_RESEARCH_ONLY_NOT_VALIDATED",
        "WITHHELD_REQUIRED_SOURCE_EVIDENCE",
    )
    merged["candidate_risk_bucket"] = "NOT_ISSUED"
    merged["candidate_protective_posture"] = "NOT_ISSUED"
    merged["severity_reestimated"] = False
    merged["underlying_other_components_verified"] = False
    return merged


def merge_fictional_evidence(
    indicators: pd.DataFrame, source: pd.DataFrame
) -> pd.DataFrame:
    """Join exact country-grain source declarations; reject silent NA/many-to-many."""
    for frame, label in ((indicators, "indicators"), (source, "source declarations")):
        if ("country" not in frame or frame["country"].isna().any()
                or frame["country"].duplicated().any()):
            raise ScoringContractError(f"Duplicate or missing country in {label}")
    needed = {"country", "source_status", "source_year", "source_ref", "unit"}
    if not needed.issubset(source) or INDICATOR not in indicators:
        raise ScoringContractError("Fictional evidence contract is incomplete")
    if set(source.country) != set(indicators.country):
        raise ScoringContractError("Evidence must cover every candidate country exactly")
    return indicators[["country", INDICATOR]].merge(
        source[list(needed)], on="country", validate="one_to_one", sort=False,
    ).sort_values("country").reset_index(drop=True)
