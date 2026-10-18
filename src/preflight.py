"""Fail-closed research input gate. Does not establish factual or operational validity."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.preflight_config import PREFLIGHT_POLICY, PreflightPolicy
from src.residual_protective_risk import FIELDS

ROOT = Path(__file__).resolve().parents[1]
TRIP_FIELDS = ("trip_id", "principal", "city", "country", "scenario", "visibility_level",
               "travel_predictability", "venue_exposure", "hotel_airport_exposure",
               "online_visibility", "reputational_sensitivity", "business_sector_sensitivity")


class PreflightError(ValueError):
    """Input package is not ready for the requested research run."""


@dataclass(frozen=True)
class PreflightResult:
    assessment_date: str
    mode: str
    trip_count: int
    event_data_through: str
    input_sha256: dict[str, str]
    evidence_sha256: str
    freshness_policy_days: dict[str, int]
    status: str = "PASS_EXPERIMENTAL_RESEARCH_ONLY"
    limitation: str = "Uncalibrated RPR-1; declarations and hashes do not verify facts or authorize travel."


def _date(value: Any, label: str) -> date:
    try:
        parsed = date.fromisoformat(str(value))
        if str(value) != parsed.isoformat():
            raise ValueError()
        return parsed
    except (TypeError, ValueError):
        raise PreflightError(f"{label} must be an explicit YYYY-MM-DD date") from None


def _read(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=columns)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise PreflightError(f"Cannot read required input {path.name}: {type(exc).__name__}") from None
    if frame.empty:
        raise PreflightError(f"Required input {path.name} has no records")
    return frame


def _hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _nonblank(record: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise PreflightError(f"{label}: missing {key}")


def _ids(frame: pd.DataFrame, label: str) -> list[str]:
    if "trip_id" not in frame:
        raise PreflightError(f"{label}: trip_id required")
    ids = frame.trip_id.str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise PreflightError(f"{label}: trip IDs must be unique and nonblank")
    frame["trip_id"] = ids
    return ids.tolist()


def require_unique_trip_context(trips: pd.DataFrame, context: pd.DataFrame) -> None:
    """Use the scorer's normalized city/country join key; reject zero or multiple matches."""
    for column in ("city_key", "country_key"):
        if column not in context or column not in trips:
            raise PreflightError(f"Location context missing {column}")
    counts = context.groupby(["city_key", "country_key"], dropna=False).size()
    for row in trips.itertuples():
        count = int(counts.get((row.city_key, row.country_key), 0))
        if count != 1:
            raise PreflightError(f"Trip {row.trip_id}: location join has {count} matches; exactly one required")


def require_preflight(assessment_date: str | None, mode: str = "current", root: Path = ROOT,
                      policy: PreflightPolicy = PREFLIGHT_POLICY) -> PreflightResult:
    """Validate staged inputs without network requests, imports of data, or output writes."""
    as_of = _date(assessment_date, "assessment_date")
    if mode not in {"current", "synthetic"}:
        raise PreflightError("mode must be current or synthetic")
    if policy.max_event_age_days < 0 or policy.max_assessment_age_days < 0:
        raise PreflightError("Freshness limits cannot be negative")
    raw = root / "data/raw"
    names = {"trips": "protective_intelligence_trip_inputs.csv",
             "capacity": "protective_capacity_inputs.csv", "events": "acled_events.csv"}
    paths = {key: raw / name for key, name in names.items()}
    try:
        evidence_bytes = (raw / "rpr1_evidence.json").read_bytes()
        evidence = json.loads(evidence_bytes)
        hashes = {key: _hash(path) for key, path in paths.items()}
    except (OSError, ValueError):
        raise PreflightError("Required evidence, trip, capacity, or event file is missing/unreadable") from None
    if not isinstance(evidence, dict) or evidence.get("schema_version") != 1:
        raise PreflightError("Evidence schema_version must be 1")
    expected_class = "synthetic" if mode == "synthetic" else "deidentified_research"
    if evidence.get("data_class") != expected_class:
        raise PreflightError(f"This mode requires data_class={expected_class}")
    if evidence.get("contains_personal_data") is not False:
        raise PreflightError("Evidence must declare contains_personal_data=false; use deidentified IDs")
    if evidence.get("input_sha256") != hashes:
        raise PreflightError("Input hashes do not match the reviewed evidence package")
    source = evidence.get("event_source")
    if not isinstance(source, dict):
        raise PreflightError("event_source is required")
    _nonblank(source, ("source_ref", "reviewer_ref"), "event_source")
    if source.get("review_status") != "approved":
        raise PreflightError("Event source review must be approved")
    through = _date(source.get("coverage_through"), "coverage_through")
    retrieved = _date(source.get("retrieved_on"), "retrieved_on")
    start = _date(source.get("coverage_from"), "coverage_from")
    if not start <= through <= retrieved <= as_of:
        raise PreflightError("Source dates are future-dated or inconsistent")
    if (as_of - through).days > policy.max_event_age_days:
        raise PreflightError("Stale event coverage; retrieval date cannot substitute for event coverage")
    trips, capacity = (_read(paths[key]) for key in ("trips", "capacity"))
    events = _read(paths["events"], ["country", "location", "admin1", "admin2", "event_date"])
    if not set(TRIP_FIELDS).issubset(trips):
        raise PreflightError("Trip input is missing required planning columns")
    if trips[list(TRIP_FIELDS)].apply(lambda col: col.str.strip().eq("")).any().any():
        raise PreflightError("Trip planning fields cannot be blank")
    ids = _ids(trips, "trips")
    if set(_ids(capacity, "capacity")) != set(ids):
        raise PreflightError("Capacity must cover exactly the reviewed trip IDs")
    if not set(FIELDS).issubset(capacity):
        raise PreflightError("Missing capacity/workload columns")
    values = capacity[list(FIELDS)].apply(pd.to_numeric, errors="coerce")
    if not ((values >= 0) & (values <= 100)).all().all():
        raise PreflightError("Missing or invalid capacity inputs; all 12 assessments must be in [0,100]")
    records = evidence.get("assessments")
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise PreflightError("Evidence assessments must be a list of records")
    seen: set[tuple[str, str]] = set()
    for rec in records:
        _nonblank(rec, ("trip_id", "kind", "source_ref", "assessor_ref", "reviewer_ref", "scope"), "assessment")
        key = (rec["trip_id"], rec["kind"])
        if key in seen or key[0] not in ids or key[1] not in {"trip", "capacity"}:
            raise PreflightError("Duplicate, orphan, or invalid assessment record")
        seen.add(key)
        if rec.get("review_status") != "approved":
            raise PreflightError("Every trip and capacity assessment requires approved review")
        observed = _date(rec.get("assessed_on"), "assessed_on")
        expires = _date(rec.get("expires_on"), "expires_on")
        movement = _date(rec.get("movement_on"), "movement_on")
        if not observed <= as_of <= movement <= expires:
            raise PreflightError("Assessment is expired, future-dated, or does not cover movement date")
        if (as_of - observed).days > policy.max_assessment_age_days:
            raise PreflightError("Stale trip/capacity assessment")
    if seen != {(trip_id, kind) for trip_id in ids for kind in ("trip", "capacity")}:
        raise PreflightError("Missing trip or capacity evidence records")
    for trip_id in ids:
        dates = {r["movement_on"] for r in records if r["trip_id"] == trip_id}
        if len(dates) != 1:
            raise PreflightError("Trip and capacity evidence disagree on movement date")
    required = {"country", "location", "admin1", "admin2", "event_date"}
    if not required.issubset(events):
        raise PreflightError("Event schema lacks dates or administrative location identity")
    dates = pd.to_datetime(events.event_date, format="%Y-%m-%d", errors="coerce")
    if dates.isna().any() or dates.min().date() < start or dates.max().date() > through:
        raise PreflightError("Event dates are invalid or outside declared coverage")
    if (as_of - dates.max().date()).days > policy.max_event_age_days:
        raise PreflightError("Stale event observations despite the declared coverage date")
    locations = events[["country", "location", "admin1", "admin2"]].drop_duplicates().copy()
    locations["city_key"] = locations.location.str.strip().str.lower()
    locations["country_key"] = locations.country.str.strip().str.lower()
    trips["city_key"] = trips.city.str.strip().str.lower()
    trips["country_key"] = trips.country.str.strip().str.lower()
    require_unique_trip_context(trips, locations)
    return PreflightResult(as_of.isoformat(), mode, len(ids), dates.max().date().isoformat(), hashes,
                           hashlib.sha256(evidence_bytes).hexdigest(), asdict(policy))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment-date", required=True)
    parser.add_argument("--mode", choices=["current", "synthetic"], default="current")
    args = parser.parse_args()
    try:
        print(json.dumps(asdict(require_preflight(args.assessment_date, args.mode)), indent=2))
    except PreflightError as exc:
        parser.exit(2, f"PREFLIGHT BLOCKED: {exc}\n")


if __name__ == "__main__":
    main()
