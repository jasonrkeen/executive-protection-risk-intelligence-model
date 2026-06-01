"""
Protective Intelligence Exposure and Decision-Support Layer

This module converts city-level EP risk, support-access constraints, and
trip/principal exposure assumptions into a Protective Intelligence Risk Score.

Inputs:
    data/processed/city_ep_risk_features.csv
    data/processed/city_access_proxy_features.csv
    data/raw/protective_intelligence_trip_inputs.csv

Outputs:
    data/processed/protective_intelligence_trip_scores.csv
    outputs/tables/top_protective_intelligence_priorities.csv

Run from project root:
    python -m src.protective_intelligence_score
"""

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

CITY_RISK_FILE = PROCESSED_DATA_DIR / "city_ep_risk_features.csv"
CITY_ACCESS_FILE = PROCESSED_DATA_DIR / "city_access_proxy_features.csv"
TRIP_INPUT_FILE = RAW_DATA_DIR / "protective_intelligence_trip_inputs.csv"

PI_TRIP_SCORES_FILE = PROCESSED_DATA_DIR / "protective_intelligence_trip_scores.csv"
TOP_PI_PRIORITIES_FILE = OUTPUT_TABLES_DIR / "top_protective_intelligence_priorities.csv"


EXPOSURE_SCORE_MAP = {
    "none": 0,
    "low": 25,
    "medium": 50,
    "moderate": 50,
    "high": 75,
    "very high": 90,
    "severe": 100,
}


SCENARIO_MULTIPLIERS = {
    "routine executive travel": 1.00,
    "investor meeting": 1.05,
    "board meeting": 1.05,
    "private meeting": 1.05,
    "airport transfer": 1.10,
    "hotel-to-venue movement": 1.10,
    "site visit": 1.20,
    "energy site visit": 1.25,
    "public event": 1.30,
    "media event": 1.30,
    "government stakeholder meeting": 1.20,
    "high visibility executive visit": 1.35,
    "travel during civil unrest": 1.40,
}


BUSINESS_SECTOR_SENSITIVITY = {
    "energy": 75,
    "oil and gas": 80,
    "mining": 75,
    "defense": 85,
    "finance": 65,
    "technology": 60,
    "healthcare": 55,
    "manufacturing": 50,
    "retail": 40,
    "other": 40,
}


def read_csv_required(path: Path, guidance: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}\n{guidance}")

    return pd.read_csv(path, low_memory=False)


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_key(value) -> str:
    return normalize_text(value).lower()


def score_exposure_value(value) -> float:
    key = normalize_key(value)
    return float(EXPOSURE_SCORE_MAP.get(key, 50))


def score_business_sector(value) -> float:
    key = normalize_key(value)
    return float(BUSINESS_SECTOR_SENSITIVITY.get(key, BUSINESS_SECTOR_SENSITIVITY["other"]))


def scenario_multiplier(value) -> float:
    key = normalize_key(value)
    return float(SCENARIO_MULTIPLIERS.get(key, 1.10))


def assign_protective_posture(score: float) -> str:
    if score >= 85:
        return "Senior Security Review / Consider Postponement"
    if score >= 75:
        return "Route / Venue Redesign Recommended"
    if score >= 60:
        return "Protective Intelligence Watch"
    if score >= 45:
        return "Enhanced Advance Work"
    if score >= 30:
        return "Standard EP Coverage"
    return "Advisory / Routine Monitoring"


def assign_pi_signal(score: float) -> str:
    if score >= 85:
        return "Severe PI Priority"
    if score >= 75:
        return "High PI Priority"
    if score >= 60:
        return "Elevated PI Priority"
    if score >= 45:
        return "Moderate PI Priority"
    return "Routine PI Monitoring"


def build_analyst_note(row: pd.Series) -> str:
    drivers = []

    if row.get("local_threat_environment_score", 0) >= 60:
        drivers.append("elevated local threat environment")

    if row.get("support_gap_score", 0) >= 60:
        drivers.append("constrained support-access environment")

    if row.get("principal_exposure_score", 0) >= 70:
        drivers.append("high principal visibility")

    if row.get("movement_predictability_score", 0) >= 70:
        drivers.append("predictable movement pattern")

    if row.get("venue_airport_hotel_exposure_score", 0) >= 70:
        drivers.append("elevated venue/airport/hotel exposure")

    if row.get("online_information_leakage_score", 0) >= 70:
        drivers.append("online or itinerary exposure concern")

    if row.get("reputational_business_sensitivity_score", 0) >= 70:
        drivers.append("heightened reputational or sector sensitivity")

    if not drivers:
        return "Routine monitoring posture; no dominant exposure driver identified by the model."

    return "Priority drivers: " + "; ".join(drivers) + "."


def load_trip_inputs() -> pd.DataFrame:
    guidance = (
        "Create data/raw/protective_intelligence_trip_inputs.csv with columns: "
        "trip_id, principal, city, country, scenario, visibility_level, "
        "travel_predictability, venue_exposure, hotel_airport_exposure, "
        "online_visibility, reputational_sensitivity, business_sector_sensitivity."
    )

    df = read_csv_required(TRIP_INPUT_FILE, guidance)

    required_cols = [
        "trip_id",
        "principal",
        "city",
        "country",
        "scenario",
        "visibility_level",
        "travel_predictability",
        "venue_exposure",
        "hotel_airport_exposure",
        "online_visibility",
        "reputational_sensitivity",
        "business_sector_sensitivity",
    ]

    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Trip input file is missing required columns: {missing}")

    for col in required_cols:
        df[col] = df[col].apply(normalize_text)

    df["city_key"] = df["city"].str.lower()
    df["country_key"] = df["country"].str.lower()

    return df


def load_city_context() -> pd.DataFrame:
    city_risk = read_csv_required(
        CITY_RISK_FILE,
        "Run python -m src.acled_city_processing first.",
    )

    city_access = read_csv_required(
        CITY_ACCESS_FILE,
        "Run python -m src.access_proxy_layer first.",
    )

    city_risk = city_risk.copy()
    city_access = city_access.copy()

    city_risk["city_key"] = city_risk["city"].astype(str).str.strip().str.lower()
    city_risk["country_key"] = city_risk["country"].astype(str).str.strip().str.lower()

    city_access["city_key"] = city_access["city"].astype(str).str.strip().str.lower()
    city_access["country_key"] = city_access["country"].astype(str).str.strip().str.lower()

    city_cols = [
        "city_key",
        "country_key",
        "rank",
        "city_ep_risk_score",
        "signal",
        "primary_driver",
        "events_30d",
        "events_90d",
        "fatalities_90d",
        "civil_unrest_score",
        "political_violence_score",
        "severity_score",
        "momentum_score",
        "ep_relevance_score",
    ]

    city_cols = [col for col in city_cols if col in city_risk.columns]

    access_cols = [
        "city_key",
        "country_key",
        "operational_rank",
        "nearest_airport_name",
        "nearest_airport_iata",
        "nearest_airport_km",
        "airport_access_score",
        "airport_access_status",
        "medical_capacity_score",
        "medical_capacity_status",
        "support_access_score",
        "support_gap_score",
        "city_operational_ep_risk_score",
        "operational_ep_signal",
    ]

    access_cols = [col for col in access_cols if col in city_access.columns]

    context = city_risk[city_cols].merge(
        city_access[access_cols],
        on=["city_key", "country_key"],
        how="left",
    )

    return context


def calculate_protective_intelligence_scores(trips: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    df = trips.merge(context, on=["city_key", "country_key"], how="left")

    # Defaults if a city/country does not match the ACLED city output exactly.
    df["city_ep_risk_score"] = pd.to_numeric(
        df.get("city_ep_risk_score"),
        errors="coerce",
    ).fillna(50)

    df["support_gap_score"] = pd.to_numeric(
        df.get("support_gap_score"),
        errors="coerce",
    ).fillna(50)

    df["city_operational_ep_risk_score"] = pd.to_numeric(
        df.get("city_operational_ep_risk_score"),
        errors="coerce",
    ).fillna(df["city_ep_risk_score"])

    df["local_threat_environment_score"] = df["city_ep_risk_score"]

    df["principal_exposure_score"] = df["visibility_level"].apply(score_exposure_value)

    df["movement_predictability_score"] = df["travel_predictability"].apply(
        score_exposure_value
    )

    df["venue_exposure_score"] = df["venue_exposure"].apply(score_exposure_value)
    df["hotel_airport_exposure_score"] = df["hotel_airport_exposure"].apply(
        score_exposure_value
    )

    df["venue_airport_hotel_exposure_score"] = (
        0.60 * df["venue_exposure_score"]
        + 0.40 * df["hotel_airport_exposure_score"]
    )

    df["online_information_leakage_score"] = df["online_visibility"].apply(
        score_exposure_value
    )

    df["reputational_sensitivity_score"] = df["reputational_sensitivity"].apply(
        score_exposure_value
    )

    df["business_sector_score"] = df["business_sector_sensitivity"].apply(
        score_business_sector
    )

    df["reputational_business_sensitivity_score"] = (
        0.55 * df["reputational_sensitivity_score"]
        + 0.45 * df["business_sector_score"]
    )

    df["scenario_multiplier"] = df["scenario"].apply(scenario_multiplier)

    base_score = (
        0.25 * df["local_threat_environment_score"]
        + 0.20 * df["principal_exposure_score"]
        + 0.15 * df["movement_predictability_score"]
        + 0.15 * df["venue_airport_hotel_exposure_score"]
        + 0.10 * df["online_information_leakage_score"]
        + 0.10 * df["support_gap_score"]
        + 0.05 * df["reputational_business_sensitivity_score"]
    )

    df["protective_intelligence_base_score"] = base_score.clip(0, 100)

    df["protective_intelligence_risk_score"] = (
        df["protective_intelligence_base_score"] * df["scenario_multiplier"]
    ).clip(0, 100)

    score_cols = [
        "local_threat_environment_score",
        "principal_exposure_score",
        "movement_predictability_score",
        "venue_airport_hotel_exposure_score",
        "online_information_leakage_score",
        "support_gap_score",
        "reputational_business_sensitivity_score",
        "protective_intelligence_base_score",
        "protective_intelligence_risk_score",
    ]

    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    df["protective_intelligence_signal"] = df[
        "protective_intelligence_risk_score"
    ].apply(assign_pi_signal)

    df["protective_posture_recommendation"] = df[
        "protective_intelligence_risk_score"
    ].apply(assign_protective_posture)

    df["analyst_priority_note"] = df.apply(build_analyst_note, axis=1)

    df["city_context_match_flag"] = np.where(
        df["rank"].notna(),
        "Matched city/location context",
        "No exact city/location match; neutral defaults used",
    )

    df = df.sort_values(
        "protective_intelligence_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    df.insert(0, "pi_priority_rank", df.index + 1)

    return df


def build_protective_intelligence_scores() -> pd.DataFrame:
    print("Loading protective intelligence trip inputs...")
    trips = load_trip_inputs()
    print(f"Trip rows loaded: {len(trips):,}")

    print("Loading city risk and access context...")
    context = load_city_context()
    print(f"City context rows loaded: {len(context):,}")

    print("Calculating Protective Intelligence Risk Scores...")
    scored = calculate_protective_intelligence_scores(trips, context)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES_DIR.mkdir(parents=True, exist_ok=True)

    scored.to_csv(PI_TRIP_SCORES_FILE, index=False)
    scored.head(25).to_csv(TOP_PI_PRIORITIES_FILE, index=False)

    print(f"Protective intelligence trip scores saved to: {PI_TRIP_SCORES_FILE}")
    print(f"Top PI priorities saved to: {TOP_PI_PRIORITIES_FILE}")

    display_cols = [
        "pi_priority_rank",
        "trip_id",
        "principal",
        "city",
        "country",
        "scenario",
        "protective_intelligence_risk_score",
        "protective_intelligence_signal",
        "protective_posture_recommendation",
        "city_context_match_flag",
    ]

    display_cols = [col for col in display_cols if col in scored.columns]

    print("\nTop Protective Intelligence Priorities")
    print("-" * 90)
    print(scored[display_cols].head(10).to_string(index=False))

    return scored


if __name__ == "__main__":
    build_protective_intelligence_scores()