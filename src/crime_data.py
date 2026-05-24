import pandas as pd

from src.config import (
    CRIME_FILE,
    CRIME_PROCESSED_FILE,
    WORLD_BANK_FILE,
    START_YEAR,
    END_YEAR,
)


CRIME_OUTPUT_COLUMNS = [
    "country",
    "country_code",
    "year",
    "homicide_rate_per_100k",
    "homicide_rate_per_100k_year",
    "crime_data_source",
    "crime_data_available",
    "crime_data_quality_flag",
]


def create_empty_crime_features() -> pd.DataFrame:
    """
    Create an empty crime feature file when no crime data source is available.
    """

    output = pd.DataFrame(columns=CRIME_OUTPUT_COLUMNS)
    CRIME_PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(CRIME_PROCESSED_FILE, index=False)

    print(f"Empty crime features saved to: {CRIME_PROCESSED_FILE}")

    return output


def normalize_country_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize country fields.
    """

    output = df.copy()

    if "country" not in output.columns:
        output["country"] = pd.NA

    if "country_code" not in output.columns:
        output["country_code"] = pd.NA

    output["country"] = output["country"].astype("string").str.strip()
    output["country_code"] = output["country_code"].astype("string").str.strip()

    output["country_code"] = output["country_code"].replace(
        {"": pd.NA, "nan": pd.NA, "None": pd.NA}
    )

    return output


def expand_latest_available_homicide(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a country-year panel using the latest available homicide value
    at or before each model year.

    Homicide data often lags. This function prevents the model from treating
    missing current-year values as unavailable when a recent historical value
    exists for the same country.
    """

    if df.empty:
        return df

    source = df.copy()

    source["year"] = pd.to_numeric(source["year"], errors="coerce")
    source["homicide_rate_per_100k"] = pd.to_numeric(
        source["homicide_rate_per_100k"], errors="coerce"
    )

    source = source.dropna(subset=["country", "year"]).copy()
    source["year"] = source["year"].astype(int)

    if source.empty:
        return source

    if "homicide_rate_per_100k_year" not in source.columns:
        source["homicide_rate_per_100k_year"] = source["year"]

    source["homicide_rate_per_100k_year"] = pd.to_numeric(
        source["homicide_rate_per_100k_year"], errors="coerce"
    ).fillna(source["year"])

    # Keep only useful rows before expanding.
    source = source[
        (source["year"] <= END_YEAR)
        & source["homicide_rate_per_100k"].notna()
    ].copy()

    if source.empty:
        return pd.DataFrame(columns=source.columns)

    country_key = "country_code"

    if "country_code" not in source.columns or not source["country_code"].notna().any():
        country_key = "country"

    rows = []

    for _, group in source.groupby(country_key, dropna=False):
        group = group.sort_values("year").copy()

        country = group["country"].dropna().iloc[-1] if group["country"].notna().any() else pd.NA
        country_code = (
            group["country_code"].dropna().iloc[-1]
            if "country_code" in group.columns and group["country_code"].notna().any()
            else pd.NA
        )

        for model_year in range(START_YEAR, END_YEAR + 1):
            historical = group[group["year"] <= model_year].copy()

            if historical.empty:
                value = pd.NA
                value_year = pd.NA
            else:
                latest = historical.sort_values("year").iloc[-1]
                value = latest["homicide_rate_per_100k"]
                value_year = latest["year"]

            rows.append(
                {
                    "country": country,
                    "country_code": country_code,
                    "year": model_year,
                    "homicide_rate_per_100k": value,
                    "homicide_rate_per_100k_year": value_year,
                }
            )

    output = pd.DataFrame(rows)

    return output


def clean_crime_output(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Standardize crime feature output for the rest of the pipeline.
    """

    output = df.copy()
    output = normalize_country_fields(output)

    required_columns = [
        "country",
        "country_code",
        "year",
        "homicide_rate_per_100k",
        "homicide_rate_per_100k_year",
    ]

    for column in required_columns:
        if column not in output.columns:
            output[column] = pd.NA

    output["year"] = pd.to_numeric(output["year"], errors="coerce")
    output["homicide_rate_per_100k"] = pd.to_numeric(
        output["homicide_rate_per_100k"], errors="coerce"
    )
    output["homicide_rate_per_100k_year"] = pd.to_numeric(
        output["homicide_rate_per_100k_year"], errors="coerce"
    )

    output = output[
        (output["year"] >= START_YEAR)
        & (output["year"] <= END_YEAR)
        & output["country"].notna()
    ].copy()

    # Prefer ISO3 deduplication when available.
    if "country_code" in output.columns and output["country_code"].notna().any():
        output = (
            output.sort_values(
                ["country_code", "year", "homicide_rate_per_100k_year"],
                ascending=[True, True, False],
            )
            .drop_duplicates(subset=["country_code", "year"], keep="first")
            .reset_index(drop=True)
        )
    else:
        output = (
            output.sort_values(
                ["country", "year", "homicide_rate_per_100k_year"],
                ascending=[True, True, False],
            )
            .drop_duplicates(subset=["country", "year"], keep="first")
            .reset_index(drop=True)
        )

    output["crime_data_source"] = source_name
    output["crime_data_available"] = output["homicide_rate_per_100k"].notna()

    output["crime_data_quality_flag"] = "Homicide proxy missing"

    output.loc[
        output["crime_data_available"],
        "crime_data_quality_flag",
    ] = "Homicide proxy populated"

    stale_mask = (
        output["crime_data_available"]
        & output["homicide_rate_per_100k_year"].notna()
        & ((output["year"] - output["homicide_rate_per_100k_year"]) >= 3)
    )

    output.loc[
        stale_mask,
        "crime_data_quality_flag",
    ] = "Homicide proxy populated from older available year"

    output = output[CRIME_OUTPUT_COLUMNS].copy()

    return output


def build_crime_features_from_worldbank() -> pd.DataFrame:
    """
    Build violent-crime proxy features from the World Bank dataset.

    The updated worldbank_api.py pulls:
        VC.IHR.PSRC.P5 -> homicide_rate_per_100k

    This function extracts that column and saves it into the standard
    crime_features.csv file used by the rest of the pipeline.
    """

    if not WORLD_BANK_FILE.exists():
        print(f"World Bank file not found at {WORLD_BANK_FILE}.")
        return pd.DataFrame()

    wb = pd.read_csv(WORLD_BANK_FILE, low_memory=False)

    required_columns = {
        "country",
        "country_code",
        "year",
        "homicide_rate_per_100k",
    }

    missing = required_columns.difference(wb.columns)

    if missing:
        print(
            "World Bank file exists, but homicide data is not available. "
            f"Missing columns: {missing}"
        )
        return pd.DataFrame()

    output = wb[
        [
            "country",
            "country_code",
            "year",
            "homicide_rate_per_100k",
        ]
    ].copy()

    output["homicide_rate_per_100k_year"] = output["year"]

    output = normalize_country_fields(output)
    output = expand_latest_available_homicide(output)

    output = clean_crime_output(
        output,
        source_name="World Bank VC.IHR.PSRC.P5 latest available",
    )

    if output.empty:
        print("World Bank homicide data was available but produced zero usable rows.")
        return pd.DataFrame()

    CRIME_PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(CRIME_PROCESSED_FILE, index=False)

    populated = output["homicide_rate_per_100k"].notna().sum()
    total = len(output)

    print("Crime features built from World Bank homicide indicator.")
    print(f"Crime features saved to: {CRIME_PROCESSED_FILE}")
    print(f"Shape: {output.shape}")
    print(f"Homicide proxy populated: {populated}/{total}")

    return output


def build_crime_features_from_manual_csv() -> pd.DataFrame:
    """
    Load homicide-rate data from a manual CSV as a fallback.

    Expected CSV:
        data/raw/homicide_rate.csv

    Expected columns:
        country, year, homicide_rate_per_100k

    Optional columns:
        country_code, homicide_rate_per_100k_year
    """

    if not CRIME_FILE.exists():
        print(
            f"No manual homicide-rate file found at {CRIME_FILE}. "
            "Creating empty crime feature file."
        )

        return create_empty_crime_features()

    df = pd.read_csv(CRIME_FILE, low_memory=False)

    required_columns = {"country", "year", "homicide_rate_per_100k"}
    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(f"Crime file is missing required columns: {missing}")

    if "country_code" not in df.columns:
        df["country_code"] = pd.NA

    if "homicide_rate_per_100k_year" not in df.columns:
        df["homicide_rate_per_100k_year"] = df["year"]

    df = normalize_country_fields(df)
    df = expand_latest_available_homicide(df)

    output = clean_crime_output(
        df,
        source_name="Manual homicide_rate.csv latest available",
    )

    CRIME_PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(CRIME_PROCESSED_FILE, index=False)

    populated = output["homicide_rate_per_100k"].notna().sum()
    total = len(output)

    print("Crime features built from manual homicide-rate CSV.")
    print(f"Crime features saved to: {CRIME_PROCESSED_FILE}")
    print(f"Shape: {output.shape}")
    print(f"Homicide proxy populated: {populated}/{total}")

    return output


def build_crime_features() -> pd.DataFrame:
    """
    Build violent-crime proxy features.

    Priority order:
        1. World Bank homicide indicator from worldbank_ep_indicators.csv
        2. Manual homicide_rate.csv fallback
        3. Empty placeholder if neither source is available
    """

    print("Processing violent-crime proxy data...")

    worldbank_output = build_crime_features_from_worldbank()

    if not worldbank_output.empty:
        return worldbank_output

    manual_output = build_crime_features_from_manual_csv()

    return manual_output


if __name__ == "__main__":
    build_crime_features()