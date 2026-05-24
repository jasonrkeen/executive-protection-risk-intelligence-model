import pandas as pd

from src.config import WORLD_BANK_FILE, ENERGY_FILE, START_YEAR, END_YEAR


ENERGY_COLUMNS = [
    "oil_rents_pct_gdp",
    "natural_gas_rents_pct_gdp",
    "fuel_exports_pct_merchandise_exports",
]


ENERGY_YEAR_COLUMNS = [
    "oil_rents_pct_gdp_year",
    "natural_gas_rents_pct_gdp_year",
    "fuel_exports_pct_merchandise_exports_year",
]


ENERGY_OUTPUT_COLUMNS = [
    "country",
    "country_code",
    "year",
    "oil_rents_pct_gdp",
    "oil_rents_pct_gdp_year",
    "natural_gas_rents_pct_gdp",
    "natural_gas_rents_pct_gdp_year",
    "fuel_exports_pct_merchandise_exports",
    "fuel_exports_pct_merchandise_exports_year",
    "energy_rents_pct_gdp",
    "energy_exposure_raw",
    "hydrocarbon_rent_share_of_energy_exposure",
    "fuel_export_share_of_energy_exposure",
    "has_oil_rents_data",
    "has_natural_gas_rents_data",
    "has_fuel_exports_data",
    "energy_data_coverage_score",
    "energy_data_coverage_flag",
    "energy_data_quality_flag",
]


def load_worldbank_data() -> pd.DataFrame:
    """
    Load the World Bank indicator dataset created by worldbank_api.py.
    """

    if not WORLD_BANK_FILE.exists():
        raise FileNotFoundError(
            f"World Bank file not found at {WORLD_BANK_FILE}. "
            "Run python -m src.worldbank_api first."
        )

    return pd.read_csv(WORLD_BANK_FILE, low_memory=False)


def normalize_country_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize country and country_code fields.
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


def ensure_energy_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure all required energy exposure columns exist and are numeric.

    If year-tracking columns do not exist, they are initialized from the row year
    when the corresponding indicator has a non-null value.
    """

    output = df.copy()

    if "year" not in output.columns:
        raise ValueError("World Bank energy input is missing required column: year")

    output["year"] = pd.to_numeric(output["year"], errors="coerce")

    for column in ENERGY_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA

        output[column] = pd.to_numeric(output[column], errors="coerce")

    for value_column, year_column in zip(ENERGY_COLUMNS, ENERGY_YEAR_COLUMNS):
        if year_column not in output.columns:
            output[year_column] = output["year"].where(output[value_column].notna())

        output[year_column] = pd.to_numeric(output[year_column], errors="coerce")

    return output


def expand_latest_available_energy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a country-year panel using the latest available energy indicator values
    at or before each model year.

    This prevents missing current-year World Bank values from being interpreted
    as zero exposure when a recent historical value exists.
    """

    if df.empty:
        return df

    source = df.copy()
    source = normalize_country_fields(source)
    source = ensure_energy_columns(source)

    source = source.dropna(subset=["country", "year"]).copy()
    source["year"] = source["year"].astype(int)

    source = source[source["year"] <= END_YEAR].copy()

    if source.empty:
        return pd.DataFrame(columns=ENERGY_OUTPUT_COLUMNS)

    country_key = "country_code"

    if "country_code" not in source.columns or not source["country_code"].notna().any():
        country_key = "country"

    rows = []

    for _, group in source.groupby(country_key, dropna=False):
        group = group.sort_values("year").copy()

        country = (
            group["country"].dropna().iloc[-1]
            if group["country"].notna().any()
            else pd.NA
        )

        country_code = (
            group["country_code"].dropna().iloc[-1]
            if "country_code" in group.columns and group["country_code"].notna().any()
            else pd.NA
        )

        for model_year in range(START_YEAR, END_YEAR + 1):
            row = {
                "country": country,
                "country_code": country_code,
                "year": model_year,
            }

            historical = group[group["year"] <= model_year].copy()

            for value_column, year_column in zip(ENERGY_COLUMNS, ENERGY_YEAR_COLUMNS):
                valid_history = historical[
                    historical[value_column].notna()
                ].copy()

                if valid_history.empty:
                    row[value_column] = 0
                    row[year_column] = pd.NA
                else:
                    latest = valid_history.sort_values("year").iloc[-1]
                    row[value_column] = latest[value_column]
                    row[year_column] = latest["year"]

            rows.append(row)

    output = pd.DataFrame(rows)

    return output


def add_energy_exposure_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add energy-sector exposure scores and data-quality flags.
    """

    output = df.copy()

    for column in ENERGY_COLUMNS:
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)

    for column in ENERGY_YEAR_COLUMNS:
        output[column] = pd.to_numeric(output[column], errors="coerce")

    output["energy_rents_pct_gdp"] = (
        output["oil_rents_pct_gdp"] + output["natural_gas_rents_pct_gdp"]
    )

    output["has_oil_rents_data"] = output["oil_rents_pct_gdp"] > 0
    output["has_natural_gas_rents_data"] = output["natural_gas_rents_pct_gdp"] > 0
    output["has_fuel_exports_data"] = (
        output["fuel_exports_pct_merchandise_exports"] > 0
    )

    output["energy_data_coverage_score"] = (
        output["has_oil_rents_data"].astype(int)
        + output["has_natural_gas_rents_data"].astype(int)
        + output["has_fuel_exports_data"].astype(int)
    )

    output["energy_data_coverage_flag"] = output["energy_data_coverage_score"].map(
        {
            0: "No measurable energy exposure",
            1: "Partial energy exposure data",
            2: "Moderate energy exposure data",
            3: "Strong energy exposure data",
        }
    )

    output["energy_exposure_raw"] = (
        output["energy_rents_pct_gdp"] * 0.60
        + output["fuel_exports_pct_merchandise_exports"] * 0.40
    )

    output["hydrocarbon_rent_share_of_energy_exposure"] = (
        (output["energy_rents_pct_gdp"] * 0.60)
        / output["energy_exposure_raw"].replace(0, pd.NA)
    ).fillna(0)

    output["fuel_export_share_of_energy_exposure"] = (
        (output["fuel_exports_pct_merchandise_exports"] * 0.40)
        / output["energy_exposure_raw"].replace(0, pd.NA)
    ).fillna(0)

    latest_year_used = output[ENERGY_YEAR_COLUMNS].max(axis=1, skipna=True)

    output["energy_data_quality_flag"] = "No measurable energy exposure"

    output.loc[
        output["energy_exposure_raw"] > 0,
        "energy_data_quality_flag",
    ] = "Energy exposure populated"

    stale_mask = (
        (output["energy_exposure_raw"] > 0)
        & latest_year_used.notna()
        & ((output["year"] - latest_year_used) >= 3)
    )

    output.loc[
        stale_mask,
        "energy_data_quality_flag",
    ] = "Energy exposure populated from older available year"

    return output


def build_energy_exposure_features() -> pd.DataFrame:
    """
    Build energy-sector exposure features from World Bank indicators.

    Energy exposure captures the strategic relevance of oil, natural gas,
    hydrocarbon rents, and fuel exports in the country-level executive
    protection risk model.
    """

    print("Building energy exposure features...")

    df = load_worldbank_data()
    df = normalize_country_fields(df)
    df = ensure_energy_columns(df)
    df = expand_latest_available_energy(df)
    df = add_energy_exposure_scores(df)

    for column in ENERGY_OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    output = df[ENERGY_OUTPUT_COLUMNS].copy()

    output = output.sort_values(["country", "year"]).reset_index(drop=True)

    ENERGY_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(ENERGY_FILE, index=False)

    measurable = int((output["energy_exposure_raw"] > 0).sum())
    countries_measurable = int(
        output.loc[output["energy_exposure_raw"] > 0, "country_code"].nunique()
    )

    print(f"Energy exposure features saved to: {ENERGY_FILE}")
    print(f"Shape: {output.shape}")
    print(f"Rows with measurable energy exposure: {measurable}")
    print(f"Countries with measurable energy exposure: {countries_measurable}")

    return output


if __name__ == "__main__":
    build_energy_exposure_features()