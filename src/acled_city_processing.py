"""
ACLED City-Level Processing Module

This module converts raw ACLED event data into city-level executive protection
risk features.

Input:
    data/raw/acled_events.csv

Output:
    data/processed/city_ep_risk_features.csv
    outputs/tables/top_25_city_ep_risk_rankings.csv

Run from project root:
    python -m src.acled_city_processing
"""

from pathlib import Path
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

ACLED_RAW_FILE = RAW_DATA_DIR / "acled_events.csv"
CITY_FEATURES_FILE = PROCESSED_DATA_DIR / "city_ep_risk_features.csv"
TOP_CITY_RANKINGS_FILE = OUTPUT_TABLES_DIR / "top_25_city_ep_risk_rankings.csv"


# ---------------------------------------------------------------------
# Event type definitions
# ---------------------------------------------------------------------

CIVIL_UNREST_EVENT_TYPES = {
    "Protests",
    "Riots",
}

POLITICAL_VIOLENCE_EVENT_TYPES = {
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
}

EP_RELEVANT_SUB_EVENT_KEYWORDS = [
    "Mob violence",
    "Excessive force against protesters",
    "Peaceful protest",
    "Protest with intervention",
    "Violent demonstration",
    "Attack",
    "Armed clash",
    "Remote explosive",
    "Shelling",
    "Abduction",
    "Disrupted weapons use",
]


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def minmax_score(series: pd.Series) -> pd.Series:
    """
    Convert a numeric series to a 0-100 min-max score.

    If all values are equal, returns 0 for every row.
    """
    series = pd.to_numeric(series, errors="coerce").fillna(0)

    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return pd.Series(0, index=series.index)

    return ((series - min_value) / (max_value - min_value)) * 100


def log_scaled_score(series: pd.Series) -> pd.Series:
    """
    Apply log1p transformation before min-max scoring.

    This reduces the effect of extreme outliers in event/fatality counts.
    """
    series = pd.to_numeric(series, errors="coerce").fillna(0)
    return minmax_score(np.log1p(series))


def assign_signal(score: float) -> str:
    """
    Convert a city EP risk score into an analyst-friendly signal.
    """
    if score >= 80:
        return "Severe"
    if score >= 65:
        return "High"
    if score >= 50:
        return "Elevated"
    if score >= 35:
        return "Moderate"
    return "Low"


def identify_primary_driver(row: pd.Series) -> str:
    """
    Identify the highest component score as the primary city risk driver.
    """
    components = {
        "Civil Unrest": row.get("civil_unrest_score", 0),
        "Political Violence": row.get("political_violence_score", 0),
        "Severity": row.get("severity_score", 0),
        "Recent Momentum": row.get("momentum_score", 0),
        "EP-Relevant Exposure": row.get("ep_relevance_score", 0),
    }

    return max(components, key=components.get)


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Find the first matching column from a list of possible column names.

    This makes the module more tolerant of slightly different ACLED exports.
    """
    lower_map = {col.lower(): col for col in df.columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


# ---------------------------------------------------------------------
# Core processing functions
# ---------------------------------------------------------------------

def load_acled_events(file_path: Path = ACLED_RAW_FILE) -> pd.DataFrame:
    """
    Load raw ACLED events from CSV.
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"Could not find ACLED file at: {file_path}\n"
            "Place your ACLED export at data/raw/acled_events.csv"
        )

    df = pd.read_csv(file_path, low_memory=False)

    # Normalize column names lightly.
    df.columns = [col.strip() for col in df.columns]

    return df


def standardize_acled_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize expected ACLED column names.
    """
    column_map = {}

    expected_columns = {
        "event_date": ["event_date", "event date", "date"],
        "country": ["country"],
        "admin1": ["admin1", "admin_1", "region"],
        "admin2": ["admin2", "admin_2", "district"],
        "location": ["location", "city", "place"],
        "latitude": ["latitude", "lat"],
        "longitude": ["longitude", "lon", "lng"],
        "event_type": ["event_type", "event type"],
        "sub_event_type": ["sub_event_type", "sub event type", "sub_event"],
        "fatalities": ["fatalities", "fatality_count"],
        "notes": ["notes", "description"],
    }

    for standard_name, candidates in expected_columns.items():
        matched_col = find_column(df, candidates)
        if matched_col is not None:
            column_map[matched_col] = standard_name

    df = df.rename(columns=column_map)

    required = [
        "event_date",
        "country",
        "location",
        "event_type",
        "fatalities",
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(
            "The ACLED file is missing required columns: "
            f"{missing}\nAvailable columns: {list(df.columns)}"
        )

    # Add optional fields if missing.
    for optional_col in ["admin1", "admin2", "latitude", "longitude", "sub_event_type", "notes"]:
        if optional_col not in df.columns:
            df[optional_col] = np.nan

    return df


def clean_acled_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and enrich raw ACLED event rows.
    """
    df = df.copy()

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df.dropna(subset=["event_date", "country", "location"])

    df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    text_cols = ["country", "admin1", "admin2", "location", "event_type", "sub_event_type", "notes"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # City key: ACLED "location" is not always a formal city,
    # but it is the best available event-location field for this first model.
    df["city"] = df["location"]

    df["is_civil_unrest"] = df["event_type"].isin(CIVIL_UNREST_EVENT_TYPES).astype(int)
    df["is_political_violence"] = df["event_type"].isin(POLITICAL_VIOLENCE_EVENT_TYPES).astype(int)
    df["is_fatal_event"] = (df["fatalities"] > 0).astype(int)
    df["is_high_fatality_event"] = (df["fatalities"] >= 5).astype(int)

    df["is_protest"] = (df["event_type"] == "Protests").astype(int)
    df["is_riot"] = (df["event_type"] == "Riots").astype(int)
    df["is_battle"] = (df["event_type"] == "Battles").astype(int)
    df["is_explosion_remote_violence"] = (
        df["event_type"] == "Explosions/Remote violence"
    ).astype(int)
    df["is_violence_against_civilians"] = (
        df["event_type"] == "Violence against civilians"
    ).astype(int)

    pattern = "|".join(EP_RELEVANT_SUB_EVENT_KEYWORDS)
    df["is_ep_relevant_event"] = (
        df["sub_event_type"].str.contains(pattern, case=False, na=False)
        | df["notes"].str.contains(
            "executive|VIP|convoy|airport|hotel|embassy|government|minister|energy|oil|gas|pipeline|facility",
            case=False,
            na=False,
        )
    ).astype(int)

    latest_date = df["event_date"].max()
    df["days_from_latest"] = (latest_date - df["event_date"]).dt.days

    df["is_30d"] = (df["days_from_latest"] <= 30).astype(int)
    df["is_60d"] = (df["days_from_latest"] <= 60).astype(int)
    df["is_90d"] = (df["days_from_latest"] <= 90).astype(int)
    df["is_180d"] = (df["days_from_latest"] <= 180).astype(int)

    return df


def aggregate_city_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate event-level ACLED data into city-level risk features.
    """
    df = df.copy()

    group_cols = ["country", "admin1", "admin2", "city"]

    # Core all-period city aggregation.
    base = (
        df.groupby(group_cols, dropna=False)
        .agg(
            total_events=("event_type", "size"),
            first_event_date=("event_date", "min"),
            latest_event_date=("event_date", "max"),
            total_fatalities=("fatalities", "sum"),
            fatal_events=("is_fatal_event", "sum"),
            high_fatality_events=("is_high_fatality_event", "sum"),
            civil_unrest_events=("is_civil_unrest", "sum"),
            political_violence_events=("is_political_violence", "sum"),
            protest_events=("is_protest", "sum"),
            riot_events=("is_riot", "sum"),
            battle_events=("is_battle", "sum"),
            explosion_remote_violence_events=("is_explosion_remote_violence", "sum"),
            violence_against_civilians_events=("is_violence_against_civilians", "sum"),
            ep_relevant_events=("is_ep_relevant_event", "sum"),
            unique_event_types=("event_type", "nunique"),
            unique_sub_event_types=("sub_event_type", "nunique"),
            avg_latitude=("latitude", "mean"),
            avg_longitude=("longitude", "mean"),
        )
        .reset_index()
    )

    # Window-specific aggregations.
    for window in [30, 60, 90, 180]:
        temp = df[df[f"is_{window}d"] == 1]

        window_features = (
            temp.groupby(group_cols, dropna=False)
            .agg(
                **{
                    f"events_{window}d": ("event_type", "size"),
                    f"fatalities_{window}d": ("fatalities", "sum"),
                    f"civil_unrest_{window}d": ("is_civil_unrest", "sum"),
                    f"political_violence_{window}d": ("is_political_violence", "sum"),
                    f"protests_{window}d": ("is_protest", "sum"),
                    f"riots_{window}d": ("is_riot", "sum"),
                    f"violence_against_civilians_{window}d": (
                        "is_violence_against_civilians",
                        "sum",
                    ),
                    f"ep_relevant_events_{window}d": ("is_ep_relevant_event", "sum"),
                    f"fatal_events_{window}d": ("is_fatal_event", "sum"),
                    f"high_fatality_events_{window}d": ("is_high_fatality_event", "sum"),
                }
            )
            .reset_index()
        )

        base = base.merge(window_features, on=group_cols, how="left")

    # Fill missing window values.
    count_cols = [
        col for col in base.columns
        if any(token in col for token in ["events_", "fatalities_", "protests_", "riots_", "violence_"])
    ]
    base[count_cols] = base[count_cols].fillna(0)

    # Rate and share features.
    base["fatalities_per_event"] = np.where(
        base["total_events"] > 0,
        base["total_fatalities"] / base["total_events"],
        0,
    )

    base["civil_unrest_share"] = np.where(
        base["total_events"] > 0,
        base["civil_unrest_events"] / base["total_events"],
        0,
    )

    base["violent_event_share"] = np.where(
        base["total_events"] > 0,
        base["political_violence_events"] / base["total_events"],
        0,
    )

    base["ep_relevant_share"] = np.where(
        base["total_events"] > 0,
        base["ep_relevant_events"] / base["total_events"],
        0,
    )

    # Momentum: compare recent 30-day activity to 90-day average pace.
    # Example: if 90d events = 9, average 30d pace = 3.
    base["expected_30d_events_from_90d"] = base["events_90d"] / 3
    base["event_momentum_ratio"] = np.where(
        base["expected_30d_events_from_90d"] > 0,
        base["events_30d"] / base["expected_30d_events_from_90d"],
        np.where(base["events_30d"] > 0, 2.0, 0),
    )

    base["expected_30d_fatalities_from_90d"] = base["fatalities_90d"] / 3
    base["fatality_momentum_ratio"] = np.where(
        base["expected_30d_fatalities_from_90d"] > 0,
        base["fatalities_30d"] / base["expected_30d_fatalities_from_90d"],
        np.where(base["fatalities_30d"] > 0, 2.0, 0),
    )

    return base


def score_city_features(city_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create city-level component scores and final city EP risk score.
    """
    df = city_df.copy()

    # Component scores.
    df["civil_unrest_score"] = (
        0.45 * log_scaled_score(df["civil_unrest_90d"])
        + 0.25 * log_scaled_score(df["protests_90d"])
        + 0.25 * log_scaled_score(df["riots_90d"])
        + 0.05 * minmax_score(df["civil_unrest_share"])
    )

    df["political_violence_score"] = (
        0.40 * log_scaled_score(df["political_violence_90d"])
        + 0.25 * log_scaled_score(df["violence_against_civilians_90d"])
        + 0.20 * log_scaled_score(df["battle_events"])
        + 0.15 * log_scaled_score(df["explosion_remote_violence_events"])
    )

    df["severity_score"] = (
        0.45 * log_scaled_score(df["fatalities_90d"])
        + 0.30 * log_scaled_score(df["fatal_events_90d"])
        + 0.25 * log_scaled_score(df["high_fatality_events_90d"])
    )

    df["momentum_score"] = (
        0.60 * minmax_score(df["event_momentum_ratio"].clip(upper=5))
        + 0.40 * minmax_score(df["fatality_momentum_ratio"].clip(upper=5))
    )

    df["ep_relevance_score"] = (
        0.65 * log_scaled_score(df["ep_relevant_events_90d"])
        + 0.35 * minmax_score(df["ep_relevant_share"])
    )

    # Final weighted score.
    df["city_ep_risk_score"] = (
        0.25 * df["civil_unrest_score"]
        + 0.25 * df["political_violence_score"]
        + 0.20 * df["severity_score"]
        + 0.20 * df["momentum_score"]
        + 0.10 * df["ep_relevance_score"]
    ).clip(0, 100)

    df["city_ep_risk_score"] = df["city_ep_risk_score"].round(2)

    component_cols = [
        "civil_unrest_score",
        "political_violence_score",
        "severity_score",
        "momentum_score",
        "ep_relevance_score",
    ]

    for col in component_cols:
        df[col] = df[col].round(2)

    df["signal"] = df["city_ep_risk_score"].apply(assign_signal)
    df["primary_driver"] = df.apply(identify_primary_driver, axis=1)

    df = df.sort_values("city_ep_risk_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    return df


def build_city_ep_risk_features() -> pd.DataFrame:
    """
    Full city-level ACLED processing pipeline.
    """
    print("Loading raw ACLED events...")
    raw = load_acled_events()

    print(f"Raw ACLED rows loaded: {len(raw):,}")

    print("Standardizing ACLED columns...")
    raw = standardize_acled_columns(raw)

    print("Cleaning ACLED event data...")
    events = clean_acled_events(raw)

    latest_date = events["event_date"].max().date()
    earliest_date = events["event_date"].min().date()

    print(f"ACLED date range: {earliest_date} to {latest_date}")
    print(f"Cleaned ACLED rows: {len(events):,}")

    print("Aggregating city-level features...")
    city_features = aggregate_city_features(events)

    print(f"City/location rows created: {len(city_features):,}")

    print("Scoring city-level EP risk...")
    scored = score_city_features(city_features)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES_DIR.mkdir(parents=True, exist_ok=True)

    scored.to_csv(CITY_FEATURES_FILE, index=False)
    scored.head(25).to_csv(TOP_CITY_RANKINGS_FILE, index=False)

    print(f"City EP risk features saved to: {CITY_FEATURES_FILE}")
    print(f"Top 25 city rankings saved to: {TOP_CITY_RANKINGS_FILE}")

    print("\nTop 10 City EP Risk Rankings")
    print("-" * 80)

    display_cols = [
        "rank",
        "city",
        "country",
        "admin1",
        "events_90d",
        "fatalities_90d",
        "city_ep_risk_score",
        "signal",
        "primary_driver",
    ]

    available_display_cols = [col for col in display_cols if col in scored.columns]
    print(scored[available_display_cols].head(10).to_string(index=False))

    return scored


if __name__ == "__main__":
    build_city_ep_risk_features()