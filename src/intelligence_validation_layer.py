"""Evidence-coverage and collection-requirements audit for the RPR-1 pipeline.

The coverage index measures availability of specified inputs, not source accuracy,
threat probability, or operational readiness. Unavailable evidence never earns
credit. Synthetic planning assumptions require independent analyst validation.
"""
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import (
    PROCESSED_DIR, TABLES_DIR, WGI_INDICATORS, FORWARD_2026_RISK_FILE,
)
from src.residual_protective_risk import validate_residual_scores

VERSION = "IV-2.1-rpr1"
RESIDUAL_FILE = PROCESSED_DIR / "residual_protective_risk_scores.csv"
CITY_FILE = PROCESSED_DIR / "city_ep_risk_features.csv"
WORLD_BANK_FILE = PROCESSED_DIR / "worldbank_ep_indicators.csv"
DECISION_FILE = TABLES_DIR / "protective_intelligence_decision_support.csv"
OUTPUTS = {
    "intelligence_confidence_scores": "intelligence_confidence_scores.csv",
    "source_coverage_gaps": "source_coverage_gaps.csv",
    "validation_requirements": "validation_requirements.csv",
    "analyst_collection_plan": "analyst_collection_plan.csv",
}
TRIP_FIELDS = (
    "scenario", "visibility_level", "travel_predictability", "venue_exposure",
    "hotel_airport_exposure", "online_visibility", "reputational_sensitivity",
    "business_sector_sensitivity",
)
GAP_DEFINITIONS = {
    "acled_stale": (
        "ACLED recency", "Update the underlying ACLED event extract and rebuild city features.",
        "Is the event extract current enough for the review date?",
    ),
    "city_context_missing": (
        "City context", "Resolve the city/location match; neutral risk defaults are not corroboration.",
        "Does the identified location match an actual ACLED city/location record?",
    ),
    "support_proxy_missing": (
        "Support access", "Verify airport and medical/support proxy inputs from current sources.",
        "Are airport access and medical/support assumptions populated and independently checked?",
    ),
    "trip_inputs_missing": (
        "Trip inputs", "Complete or explicitly qualify the exposure assumptions for this synthetic movement.",
        "Which exposure assumptions are missing or based only on default values?",
    ),
    "capacity_assessment_missing": (
        "Protective capacity", "Complete the RPR-1 protective capacity and task-load assessment.",
        "What independently supported capacity and task saturation inputs are available?",
    ),
    "wgi_unavailable": (
        "Governance indicators", "Verify World Bank WGI availability and rebuild governance inputs.",
        "Did the World Bank governance indicator fetch succeed for the analysis?",
    ),
    "coa_missing": (
        "Decision audit", "Regenerate COA decision-support outputs and confirm trip IDs align.",
        "Is the current movement included in the current COA decision rule audit?",
    ),
}


def _has_value(value) -> bool:
    return bool(pd.notna(value) and str(value).strip() != "")


def _numeric_present(value) -> bool:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return bool(pd.notna(numeric))


def _latest_city_event_date(path: Path):
    """Use actual event dates; 30/90-day ACLED windows are relative to dataset end."""
    if not path.is_file():
        return None
    try:
        values = pd.read_csv(path, usecols=["latest_event_date"])["latest_event_date"]
        dates = pd.to_datetime(values, errors="coerce")
        latest = dates.max()
        return latest.date() if pd.notna(latest) else None
    except (ValueError, KeyError, pd.errors.EmptyDataError):
        return None


def _wgi_status(path: Path) -> str:
    """Global source availability only; does not validate country-specific WGI rows."""
    if not path.is_file():
        return "Unavailable"
    try:
        wb = pd.read_csv(path, low_memory=False)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return "Unavailable"
    available = [
        col for col in WGI_INDICATORS.values()
        if col in wb.columns and wb[col].notna().any()
    ]
    if not available:
        return "Unavailable"
    if len(available) != len(WGI_INDICATORS):
        return "Partial"
    return "Available (global file only)"


def _forward_status(path: Path) -> str:
    """Forward source is informational, not a source of automatic evidence credit."""
    if not path.is_file():
        return "Unavailable"
    try:
        forward = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return "Unavailable"
    if forward.empty:
        return "Unavailable"
    if "target_year_data_status" in forward:
        if forward["target_year_data_status"].astype(str).str.contains(
            "Target-year ACLED data unavailable", case=False, regex=False,
        ).all():
            return "Baseline retained - target-year ACLED unavailable"
    return "Inspect target-year source coverage"


def _coverage_label(value: float) -> str:
    if value >= 90:
        return "Higher coverage (unverified)"
    if value >= 65:
        return "Partial coverage"
    if value >= 35:
        return "Limited coverage"
    return "Insufficient coverage"


def build_validation_tables(
    residual: pd.DataFrame,
    decision: pd.DataFrame,
    *,
    latest_acled_date: date | None,
    review_date: date,
    wgi_status: str,
    forward_status: str,
    max_acled_age_days: int = 180,
) -> dict[str, pd.DataFrame]:
    """Build outputs with exactly one confidence record per distinct trip_id."""
    if max_acled_age_days < 1:
        raise ValueError("max_acled_age_days must be positive")
    if residual.empty:
        raise ValueError("Residual scores are empty")
    validate_residual_scores(residual)
    if "trip_id" not in residual or residual["trip_id"].isna().any():
        raise ValueError("trip_id is required")
    trip_ids = residual["trip_id"].astype(str).str.strip()
    if trip_ids.eq("").any() or trip_ids.duplicated().any():
        raise ValueError("trip_id must be nonblank and unique")

    if not decision.empty:
        if "trip_id" not in decision:
            raise ValueError("Decision table is missing trip_id")
        decision_ids = decision["trip_id"].astype(str).str.strip()
        if decision_ids.eq("").any() or decision_ids.duplicated().any():
            raise ValueError("Decision table trip_id must be nonblank and unique")
        if set(decision_ids) - set(trip_ids):
            raise ValueError("Decision table includes unknown trip_id")

    coa_by_id = (
        decision.assign(trip_id=decision["trip_id"].astype(str).str.strip())
        .set_index("trip_id")["coa_level"].to_dict()
        if not decision.empty and "coa_level" in decision else {}
    )
    age = (review_date - latest_acled_date).days if latest_acled_date else None
    acled_current = age is not None and 0 <= age <= max_acled_age_days
    records, gaps = [], []

    for _, row in residual.iterrows():
        trip_id = str(row["trip_id"]).strip()
        matched = str(row.get("city_context_match_flag", "")).startswith(
            "Matched city/location context"
        )
        support = (
            _numeric_present(row.get("nearest_airport_km"))
            and _numeric_present(row.get("medical_capacity_score"))
            and _numeric_present(row.get("support_gap_score"))
        )
        trip_complete = all(_has_value(row.get(field)) for field in TRIP_FIELDS)
        capacity_complete = str(row.get("capacity_input_status", "")) == "Complete"
        wgi_available = wgi_status == "Available (global file only)"
        coa_present = trip_id in coa_by_id and _has_value(coa_by_id[trip_id])
        flags = {
            "acled_stale": not acled_current,
            "city_context_missing": not matched,
            "support_proxy_missing": not support,
            "trip_inputs_missing": not trip_complete,
            "capacity_assessment_missing": not capacity_complete,
            "wgi_unavailable": not wgi_available,
            "coa_missing": not coa_present,
        }
        # Equal weights intentionally measure visible evidence coverage, not confidence in truth.
        index = round(100 * sum(not flagged for flagged in flags.values()) / len(flags), 2)
        problems = [GAP_DEFINITIONS[k][0] for k, flagged in flags.items() if flagged]
        description = (
            "Review required: " + "; ".join(problems) + "."
            if problems else "All specified coverage checks passed; analyst verification still required."
        )
        records.append({
            "trip_id": trip_id,
            "principal": row.get("principal"),
            "city": row.get("city"),
            "country": row.get("country"),
            "protective_intelligence_risk_score": row.get("protective_intelligence_risk_score"),
            "residual_risk_score": row.get("residual_risk_score"),
            "coa_level": coa_by_id.get(trip_id),
            "intelligence_confidence_score": index,
            "intelligence_confidence_label": _coverage_label(index),
            "validation_priority": "Priority validation" if index < 65 else (
                "Targeted validation" if index < 90 else "Routine analyst verification"
            ),
            "validation_summary": description,
            "acled_latest_event_date": latest_acled_date.isoformat() if latest_acled_date else None,
            "acled_age_days": age,
            "forward_target_data_status": forward_status,
            "wgi_coverage_status": wgi_status,
            "validation_model_version": VERSION,
            **{key + "_flag": value for key, value in flags.items()},
        })
        for code, flagged in flags.items():
            if flagged:
                label, requirement, question = GAP_DEFINITIONS[code]
                gaps.append({
                    "trip_id": trip_id,
                    "city": row.get("city"),
                    "country": row.get("country"),
                    "gap_code": code,
                    "gap_area": label,
                    "validation_requirement": requirement,
                    "validation_priority": "Priority validation" if index < 65 else "Targeted validation",
                    "collection_question": question,
                    "collection_purpose": requirement,
                })
    confidences = pd.DataFrame(records)
    gap_columns = [
        "trip_id", "city", "country", "gap_code", "gap_area",
        "validation_requirement", "validation_priority",
    ]
    plan_columns = [
        "trip_id", "city", "country", "gap_code", "validation_priority",
        "collection_question", "collection_purpose",
    ]
    gap_frame = pd.DataFrame(gaps)
    if gap_frame.empty:
        gap_frame = pd.DataFrame(columns=gap_columns + ["collection_question", "collection_purpose"])
    return {
        "intelligence_confidence_scores": confidences,
        "source_coverage_gaps": gap_frame[gap_columns],
        "validation_requirements": gap_frame[gap_columns].copy(),
        "analyst_collection_plan": gap_frame[plan_columns],
    }


def run_intelligence_validation_layer(
    processed_dir: Path = PROCESSED_DIR,
    outputs_dir: Path = TABLES_DIR,
    *,
    review_date: date | None = None,
) -> dict[str, Path]:
    """Consume validated RPR-1 output; save audit artifacts under outputs/tables."""
    processed_dir, outputs_dir = Path(processed_dir), Path(outputs_dir)
    residual_path = processed_dir / RESIDUAL_FILE.name
    decision_path = outputs_dir / DECISION_FILE.name
    if not residual_path.is_file():
        raise FileNotFoundError(f"Residual scores not found: {residual_path}")
    residual = pd.read_csv(residual_path, dtype={"trip_id": str})
    decision = (
        pd.read_csv(decision_path, dtype={"trip_id": str})
        if decision_path.is_file() else pd.DataFrame()
    )
    tables = build_validation_tables(
        residual,
        decision,
        latest_acled_date=_latest_city_event_date(processed_dir / CITY_FILE.name),
        review_date=review_date or date.today(),
        wgi_status=_wgi_status(processed_dir / WORLD_BANK_FILE.name),
        forward_status=_forward_status(outputs_dir / FORWARD_2026_RISK_FILE.name),
    )
    outputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: outputs_dir / basename for name, basename in OUTPUTS.items()}
    for name, frame in tables.items():
        frame.to_csv(paths[name], index=False)
    return paths


if __name__ == "__main__":
    for name, path in run_intelligence_validation_layer().items():
        print(f"{name}: {path}")
