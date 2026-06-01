"""
Airport and Medical Access Proxy Layer

This module adds a support-access layer to the city-level ACLED protective
intelligence model.

Inputs:
    data/processed/city_ep_risk_features.csv
    data/raw/airports.csv  optional, from OurAirports
    World Bank API medical indicators

Outputs:
    data/processed/city_access_proxy_features.csv
    outputs/tables/top_25_city_operational_risk_rankings.csv

Run from project root:
    python -m src.access_proxy_layer
"""

from pathlib import Path
import math
import warnings

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

CITY_RISK_FILE = PROCESSED_DATA_DIR / "city_ep_risk_features.csv"
AIRPORTS_FILE = RAW_DATA_DIR / "airports.csv"

CITY_ACCESS_FEATURES_FILE = PROCESSED_DATA_DIR / "city_access_proxy_features.csv"
TOP_OPERATIONAL_RISK_FILE = OUTPUT_TABLES_DIR / "top_25_city_operational_risk_rankings.csv"


WORLD_BANK_MEDICAL_INDICATORS = {
    "hospital_beds_per_1000": "SH.MED.BEDS.ZS",
    "physicians_per_1000": "SH.MED.PHYS.ZS",
}


def minmax_score(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce").fillna(0)

    min_value = series.min()
    max_value = series.max()

    if max_value == min_value:
        return pd.Series(0, index=series.index)

    return ((series - min_value) / (max_value - min_value)) * 100


def inverse_minmax_score(series: pd.Series) -> pd.Series:
    return 100 - minmax_score(series)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """
    Calculate great-circle distance between two points in kilometers.
    """
    radius_km = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_km * c


def normalize_country_name(value: str) -> str:
    """
    Basic country-name normalization for merging ACLED names to World Bank names.
    """
    if pd.isna(value):
        return ""

    value = str(value).strip().lower()

    replacements = {
        "united states": "united states",
        "usa": "united states",
        "u.s.": "united states",
        "russia": "russian federation",
        "iran": "iran, islamic rep.",
        "syria": "syrian arab republic",
        "venezuela": "venezuela, rb",
        "yemen": "yemen, rep.",
        "congo, dem. rep.": "congo, dem. rep.",
        "democratic republic of congo": "congo, dem. rep.",
        "dr congo": "congo, dem. rep.",
        "cote d'ivoire": "cote d'ivoire",
        "ivory coast": "cote d'ivoire",
        "turkiye": "turkiye",
        "turkey": "turkiye",
        "egypt": "egypt, arab rep.",
        "slovakia": "slovak republic",
        "kyrgyzstan": "kyrgyz republic",
        "laos": "lao pdr",
    }

    return replacements.get(value, value)


def load_city_risk_features() -> pd.DataFrame:
    if not CITY_RISK_FILE.exists():
        raise FileNotFoundError(
            f"Could not find city risk file at: {CITY_RISK_FILE}\n"
            "Run this first:\n"
            "python -m src.acled_city_processing"
        )

    return pd.read_csv(CITY_RISK_FILE, low_memory=False)


def load_airports() -> pd.DataFrame:
    """
    Load OurAirports airport reference file if available.

    Expected file:
        data/raw/airports.csv

    Useful columns from OurAirports:
        type
        name
        latitude_deg
        longitude_deg
        municipality
        iata_code
    """
    if not AIRPORTS_FILE.exists():
        warnings.warn(
            f"Airport file not found at {AIRPORTS_FILE}. "
            "Airport access fields will be set to neutral defaults."
        )
        return pd.DataFrame()

    airports = pd.read_csv(AIRPORTS_FILE, low_memory=False)

    required_cols = ["type", "name", "latitude_deg", "longitude_deg"]
    missing = [col for col in required_cols if col not in airports.columns]

    if missing:
        warnings.warn(
            f"Airport file is missing columns: {missing}. "
            "Airport access fields will be set to neutral defaults."
        )
        return pd.DataFrame()

    airports = airports.copy()
    airports["latitude_deg"] = pd.to_numeric(
        airports["latitude_deg"],
        errors="coerce",
    )
    airports["longitude_deg"] = pd.to_numeric(
        airports["longitude_deg"],
        errors="coerce",
    )

    airports = airports.dropna(subset=["latitude_deg", "longitude_deg"])

    airport_types = ["large_airport", "medium_airport"]
    airports = airports[airports["type"].isin(airport_types)].copy()

    if "municipality" not in airports.columns:
        airports["municipality"] = ""

    if "iata_code" not in airports.columns:
        airports["iata_code"] = ""

    return airports


def calculate_airport_access(city_df: pd.DataFrame, airports: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate nearest airport distance and airport counts within distance bands.
    """
    df = city_df.copy()

    required_city_cols = ["avg_latitude", "avg_longitude"]

    missing = [col for col in required_city_cols if col not in df.columns]
    if missing:
        raise ValueError(f"City file is missing required coordinate columns: {missing}")

    df["avg_latitude"] = pd.to_numeric(df["avg_latitude"], errors="coerce")
    df["avg_longitude"] = pd.to_numeric(df["avg_longitude"], errors="coerce")

    df["nearest_airport_km"] = np.nan
    df["nearest_airport_name"] = ""
    df["nearest_airport_type"] = ""
    df["nearest_airport_iata"] = ""
    df["airports_within_50km"] = 0
    df["airports_within_100km"] = 0
    df["airports_within_150km"] = 0

    if airports.empty:
        df["nearest_airport_km"] = 250
        df["airport_access_score"] = 50
        df["airport_access_status"] = "Airport reference unavailable"
        return df

    airport_records = airports[
        [
            "type",
            "name",
            "latitude_deg",
            "longitude_deg",
            "municipality",
            "iata_code",
        ]
    ].to_dict("records")

    results = []

    for _, row in df.iterrows():
        city_lat = row.get("avg_latitude")
        city_lon = row.get("avg_longitude")

        if pd.isna(city_lat) or pd.isna(city_lon):
            results.append(
                {
                    "nearest_airport_km": np.nan,
                    "nearest_airport_name": "",
                    "nearest_airport_type": "",
                    "nearest_airport_iata": "",
                    "airports_within_50km": 0,
                    "airports_within_100km": 0,
                    "airports_within_150km": 0,
                }
            )
            continue

        distances = []

        for airport in airport_records:
            distance = haversine_km(
                city_lat,
                city_lon,
                airport["latitude_deg"],
                airport["longitude_deg"],
            )

            distances.append(
                {
                    "distance_km": distance,
                    "name": airport.get("name", ""),
                    "type": airport.get("type", ""),
                    "iata_code": airport.get("iata_code", ""),
                }
            )

        distance_df = pd.DataFrame(distances)

        nearest = distance_df.sort_values("distance_km").iloc[0]

        results.append(
            {
                "nearest_airport_km": nearest["distance_km"],
                "nearest_airport_name": nearest["name"],
                "nearest_airport_type": nearest["type"],
                "nearest_airport_iata": nearest["iata_code"],
                "airports_within_50km": int((distance_df["distance_km"] <= 50).sum()),
                "airports_within_100km": int((distance_df["distance_km"] <= 100).sum()),
                "airports_within_150km": int((distance_df["distance_km"] <= 150).sum()),
            }
        )

    access_df = pd.DataFrame(results)

    for col in access_df.columns:
        df[col] = access_df[col].values

    df["airport_distance_score"] = inverse_minmax_score(
        df["nearest_airport_km"].fillna(df["nearest_airport_km"].median())
    )

    df["airport_density_score"] = (
        0.50 * minmax_score(df["airports_within_50km"])
        + 0.30 * minmax_score(df["airports_within_100km"])
        + 0.20 * minmax_score(df["airports_within_150km"])
    )

    df["airport_access_score"] = (
        0.65 * df["airport_distance_score"]
        + 0.35 * df["airport_density_score"]
    ).clip(0, 100)

    df["airport_access_score"] = df["airport_access_score"].round(2)

    df["airport_access_status"] = np.select(
        [
            df["nearest_airport_km"] <= 50,
            df["nearest_airport_km"] <= 100,
            df["nearest_airport_km"] <= 150,
        ],
        [
            "Strong airport access",
            "Moderate airport access",
            "Limited airport access",
        ],
        default="Remote airport access",
    )

    return df


def fetch_worldbank_indicator(indicator_code: str, indicator_name: str) -> pd.DataFrame:
    """
    Fetch World Bank indicator data and keep the most recent available value by country.
    """
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/{indicator_code}"
        "?format=json&per_page=20000"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list) or len(payload) < 2:
        return pd.DataFrame(columns=["country", "country_normalized", indicator_name])

    rows = []

    for item in payload[1]:
        country_info = item.get("country") or {}
        country_name = country_info.get("value")
        year = item.get("date")
        value = item.get("value")

        if country_name is None or value is None:
            continue

        rows.append(
            {
                "country": country_name,
                "country_normalized": normalize_country_name(country_name),
                "year": int(year),
                indicator_name: float(value),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["country", "country_normalized", indicator_name])

    df = df.sort_values(["country_normalized", "year"], ascending=[True, False])
    df = df.drop_duplicates(subset=["country_normalized"], keep="first")

    return df[["country_normalized", indicator_name]]


def build_medical_capacity_reference() -> pd.DataFrame:
    """
    Fetch medical capacity proxy indicators from World Bank.
    """
    frames = []

    for indicator_name, indicator_code in WORLD_BANK_MEDICAL_INDICATORS.items():
        try:
            print(f"Fetching World Bank medical indicator: {indicator_name}")
            indicator_df = fetch_worldbank_indicator(indicator_code, indicator_name)
            frames.append(indicator_df)
        except Exception as exc:
            warnings.warn(
                f"Could not fetch {indicator_name} from World Bank. Reason: {exc}"
            )

    if not frames:
        return pd.DataFrame()

    medical = frames[0]

    for frame in frames[1:]:
        medical = medical.merge(frame, on="country_normalized", how="outer")

    return medical


def add_medical_capacity(city_df: pd.DataFrame, medical_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add country-level medical capacity proxies to city records.
    """
    df = city_df.copy()

    df["country_normalized"] = df["country"].apply(normalize_country_name)

    if medical_df.empty:
        df["hospital_beds_per_1000"] = np.nan
        df["physicians_per_1000"] = np.nan
        df["medical_capacity_score"] = 50
        df["medical_capacity_status"] = "Medical reference unavailable"
        return df

    df = df.merge(medical_df, on="country_normalized", how="left")

    for col in ["hospital_beds_per_1000", "physicians_per_1000"]:
        if col not in df.columns:
            df[col] = np.nan

        median_value = df[col].median()
        df[col] = df[col].fillna(median_value)

    df["hospital_bed_score"] = minmax_score(df["hospital_beds_per_1000"])
    df["physician_score"] = minmax_score(df["physicians_per_1000"])

    df["medical_capacity_score"] = (
        0.50 * df["hospital_bed_score"]
        + 0.50 * df["physician_score"]
    ).clip(0, 100)

    df["medical_capacity_score"] = df["medical_capacity_score"].round(2)

    df["medical_capacity_status"] = np.select(
        [
            df["medical_capacity_score"] >= 70,
            df["medical_capacity_score"] >= 50,
            df["medical_capacity_score"] >= 30,
        ],
        [
            "Stronger medical capacity proxy",
            "Moderate medical capacity proxy",
            "Limited medical capacity proxy",
        ],
        default="Low medical capacity proxy",
    )

    return df


def assign_operational_signal(score: float) -> str:
    if score >= 80:
        return "Severe Operational Concern"
    if score >= 65:
        return "High Operational Concern"
    if score >= 50:
        return "Elevated Operational Concern"
    if score >= 35:
        return "Moderate Operational Concern"
    return "Lower Operational Concern"


def calculate_access_adjusted_risk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combine city risk with support-access gap.
    """
    out = df.copy()

    out["support_access_score"] = (
        0.60 * out["airport_access_score"]
        + 0.40 * out["medical_capacity_score"]
    ).clip(0, 100)

    out["support_gap_score"] = 100 - out["support_access_score"]

    out["city_operational_ep_risk_score"] = (
        0.75 * out["city_ep_risk_score"]
        + 0.25 * out["support_gap_score"]
    ).clip(0, 100)

    score_cols = [
        "support_access_score",
        "support_gap_score",
        "city_operational_ep_risk_score",
    ]

    for col in score_cols:
        out[col] = out[col].round(2)

    out["operational_ep_signal"] = out["city_operational_ep_risk_score"].apply(
        assign_operational_signal
    )

    out = out.sort_values(
        "city_operational_ep_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    out.insert(0, "operational_rank", out.index + 1)

    return out


def build_access_proxy_layer() -> pd.DataFrame:
    """
    Full airport and medical access proxy pipeline.
    """
    print("Loading city EP risk features...")
    city_df = load_city_risk_features()
    print(f"City rows loaded: {len(city_df):,}")

    print("Loading airport reference data...")
    airports = load_airports()
    print(f"Airport records loaded: {len(airports):,}")

    print("Calculating airport access proxy features...")
    city_with_airports = calculate_airport_access(city_df, airports)

    print("Fetching medical capacity proxy indicators...")
    medical_df = build_medical_capacity_reference()
    print(f"Medical reference rows loaded: {len(medical_df):,}")

    print("Adding medical capacity proxy features...")
    city_with_medical = add_medical_capacity(city_with_airports, medical_df)

    print("Calculating access-adjusted operational EP risk...")
    final = calculate_access_adjusted_risk(city_with_medical)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES_DIR.mkdir(parents=True, exist_ok=True)

    final.to_csv(CITY_ACCESS_FEATURES_FILE, index=False)
    final.head(25).to_csv(TOP_OPERATIONAL_RISK_FILE, index=False)

    print(f"City access proxy features saved to: {CITY_ACCESS_FEATURES_FILE}")
    print(f"Top 25 operational city rankings saved to: {TOP_OPERATIONAL_RISK_FILE}")

    print("\nTop 10 Access-Adjusted City Operational EP Risk Rankings")
    print("-" * 90)

    display_cols = [
        "operational_rank",
        "city",
        "country",
        "admin1",
        "city_ep_risk_score",
        "airport_access_score",
        "medical_capacity_score",
        "support_gap_score",
        "city_operational_ep_risk_score",
        "operational_ep_signal",
    ]

    display_cols = [col for col in display_cols if col in final.columns]

    print(final[display_cols].head(10).to_string(index=False))

    return final


if __name__ == "__main__":
    build_access_proxy_layer()