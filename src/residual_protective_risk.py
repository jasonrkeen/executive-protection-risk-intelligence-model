"""Replacement implementation RPR-1; analyst assumptions, not calibrated risk probabilities."""
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "RPR-1-replacement"
CAPACITY = ("driver_capacity", "close_protection_capacity", "advance_capacity",
            "intelligence_capacity", "medical_capacity", "communications_capacity",
            "local_support_capacity")
LOAD = ("combined_role_load", "concurrent_duty_load", "transition_load",
        "public_exposure_load", "schedule_compression_load")
FIELDS = CAPACITY + LOAD
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed/residual_protective_risk_scores.csv"


def _keys(frame):
    frame = frame.copy()
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names are not allowed")
    if "trip_id" not in frame:
        raise ValueError("trip_id is required")
    if frame.trip_id.isna().any():
        raise ValueError("trip_id cannot be missing")
    frame["trip_id"] = frame.trip_id.astype(str).str.strip()
    if frame.trip_id.eq("").any() or frame.trip_id.duplicated().any():
        raise ValueError("trip_id must be nonblank and unique")
    return frame


def score_residual_risk(trips, capacity=None):
    """One row per movement. Missing/partial capacity never earns mitigation credit."""
    out = _keys(trips)
    if out.empty:
        raise ValueError("trip scores cannot be empty")
    if "protective_intelligence_risk_score" not in out:
        raise ValueError("protective_intelligence_risk_score is required")
    score = pd.to_numeric(out["protective_intelligence_risk_score"], errors="coerce")
    if (~np.isfinite(score) | ~score.between(0, 100)).any():
        raise ValueError("PI scores must be finite numbers in [0, 100]")
    if set(FIELDS).intersection(out.columns) or "residual_risk_score" in out:
        raise ValueError("Expected baseline PI input, not previously enriched scores")
    if capacity is None:
        capacity = pd.DataFrame(columns=("trip_id",) + FIELDS)
    capacity = _keys(capacity)
    if set(capacity.trip_id) - set(out.trip_id):
        raise ValueError("Capacity contains trip IDs absent from PI input")
    for field in FIELDS:
        if field not in capacity:
            capacity[field] = np.nan
        raw = capacity[field].replace(r"^\s*$", np.nan, regex=True)
        numeric = pd.to_numeric(raw, errors="coerce")
        invalid = raw.notna() & (~np.isfinite(numeric) | ~numeric.between(0, 100))
        if invalid.any():
            raise ValueError(f"{field} must be blank or a finite number in [0, 100]")
        capacity[field] = numeric
    out = out.merge(capacity[["trip_id", *FIELDS]], on="trip_id", how="left", validate="one_to_one")
    complete = out[list(FIELDS)].notna().all(axis=1)
    out["capacity_input_status"] = np.where(complete, "Complete", "Unknown / incomplete")
    out["protective_capacity_score"] = out[list(CAPACITY)].mean(axis=1).where(complete)
    out["task_saturation_score"] = out[list(LOAD)].mean(axis=1).where(complete)
    out["effective_protective_capacity"] = out.protective_capacity_score * (1 - .35 * out.task_saturation_score / 100)
    out["protective_coverage_gap"] = 100 - out.effective_protective_capacity
    out["capacity_modifier"] = (1.25 - .005 * out.effective_protective_capacity).fillna(1.0)
    out["residual_risk_score"] = (pd.to_numeric(out.protective_intelligence_risk_score) * out.capacity_modifier).clip(0, 100)
    out["residual_risk_delta"] = out.residual_risk_score - pd.to_numeric(out.protective_intelligence_risk_score)
    out["residual_review_required"] = (~complete | out.protective_coverage_gap.ge(60) | out.task_saturation_score.ge(70) | out.residual_risk_score.ge(60))
    out["residual_review_state"] = np.where(~complete, "Capacity assessment required", np.where(out.residual_review_required, "Protective-planning review required", "No additional capacity review trigger"))
    out["residual_model_version"] = VERSION
    return out


def validate_residual_scores(scored):
    """Reject incomplete, stale-version or altered derived fields at consumption."""
    required = {"trip_id", "protective_intelligence_risk_score", *FIELDS}
    if not required.issubset(scored.columns):
        raise ValueError("Residual input is missing baseline or capacity columns")
    expected = score_residual_risk(
        scored[["trip_id", "protective_intelligence_risk_score"]],
        scored[["trip_id", *FIELDS]],
    )
    for column in expected.columns:
        if column in required:
            continue
        if column not in scored:
            raise ValueError(f"Residual input is missing {column}")
        actual = scored[column].reset_index(drop=True)
        target = expected[column]
        if pd.api.types.is_numeric_dtype(target) and target.dtype != bool:
            numeric = pd.to_numeric(actual, errors="coerce")
            matches = not (actual.notna() & numeric.isna()).any() and np.isclose(
                numeric, target, rtol=1e-10, atol=1e-10, equal_nan=True).all()
        else:
            matches = actual.eq(target).fillna(False).all()
        if not matches:
            raise ValueError(f"Residual input is inconsistent: {column}; regenerate RPR-1 output")


def build_residual_risk(input_path=None, capacity_path=None, output_path=None):
    if capacity_path is not None and not Path(capacity_path).is_file():
        raise FileNotFoundError(capacity_path)
    input_path = Path(input_path) if input_path is not None else ROOT / "data/processed/protective_intelligence_trip_scores.csv"
    capacity_path = Path(capacity_path) if capacity_path is not None else ROOT / "data/raw/protective_capacity_inputs.csv"
    output_path = Path(output_path) if output_path is not None else OUTPUT
    trips = pd.read_csv(input_path, dtype={"trip_id": str})
    capacity = pd.read_csv(capacity_path, dtype={"trip_id": str}) if capacity_path.exists() else None
    scored = score_residual_risk(trips, capacity)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    build_residual_risk()
