import pandas as pd

from src.config import (
    STUDY_YEAR,
    WORLD_BANK_FILE,
    ACLED_COUNTRY_FILE,
    CRIME_PROCESSED_FILE,
    ENERGY_FILE,
    MASTER_DATA_FILE,
)


def load_csv_if_exists(path, name: str) -> pd.DataFrame:
    """
    Load a CSV file and provide a clear error if it does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"{name} file not found at {path}. "
            f"Run the required upstream module before data_processing.py."
        )

    return pd.read_csv(path, low_memory=False)


def standardize_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure year is numeric.
    """

    df = df.copy()

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    return df


def ensure_country_code(master: pd.DataFrame) -> pd.DataFrame:
    """
    Repair country_code if merges created country_code_x / country_code_y.
    """

    master = master.copy()

    if "country_code" not in master.columns:
        possible_code_columns = [
            column for column in master.columns if column.startswith("country_code")
        ]

        if possible_code_columns:
            master["country_code"] = master[possible_code_columns].bfill(axis=1).iloc[
                :, 0
            ]

    drop_columns = [
        column for column in master.columns if column.startswith("country_code_")
    ]

    if drop_columns:
        master = master.drop(columns=drop_columns)

    return master


def prepare_worldbank_data(study_year: int) -> pd.DataFrame:
    """
    Load World Bank data for the study year.
    """

    wb = load_csv_if_exists(WORLD_BANK_FILE, "World Bank")
    wb = standardize_year(wb)

    wb_year = wb[wb["year"] == study_year].copy()

    if wb_year.empty:
        raise ValueError(
            f"No World Bank rows found for study year {study_year}. "
            f"Check {WORLD_BANK_FILE}."
        )

    return wb_year


def prepare_acled_data(study_year: int) -> pd.DataFrame:
    """
    Load ACLED country-year features for the study year.
    """

    acled = load_csv_if_exists(ACLED_COUNTRY_FILE, "ACLED country features")
    acled = standardize_year(acled)

    acled_year = acled[acled["year"] == study_year].copy()

    if acled_year.empty:
        print(
            f"Warning: no ACLED rows found for {study_year}. "
            "ACLED risk features will be filled with zeros."
        )

    return acled_year


def prepare_crime_data(study_year: int) -> pd.DataFrame:
    """
    Load crime features for the study year.

    The updated crime_data.py includes country_code, data source, and quality flags.
    """

    crime = load_csv_if_exists(CRIME_PROCESSED_FILE, "Crime features")
    crime = standardize_year(crime)

    crime_year = crime[crime["year"] == study_year].copy()

    if crime_year.empty:
        print(
            f"Warning: no crime rows found for {study_year}. "
            "Crime risk will be filled with median or neutral values."
        )

    return crime_year


def prepare_energy_data(study_year: int) -> pd.DataFrame:
    """
    Load energy exposure features for the study year.
    """

    energy = load_csv_if_exists(ENERGY_FILE, "Energy exposure")
    energy = standardize_year(energy)

    energy_year = energy[energy["year"] == study_year].copy()

    if energy_year.empty:
        print(
            f"Warning: no energy rows found for {study_year}. "
            "Energy exposure will be filled with zeros."
        )

    return energy_year


def merge_acled(master: pd.DataFrame, acled_year: pd.DataFrame) -> pd.DataFrame:
    """
    Merge ACLED data by country and year.

    ACLED country-year features are currently keyed by country name and year.
    """

    if acled_year.empty:
        return master

    master = master.merge(
        acled_year,
        on=["country", "year"],
        how="left",
        suffixes=("", "_acled"),
    )

    return master


def merge_crime(master: pd.DataFrame, crime_year: pd.DataFrame) -> pd.DataFrame:
    """
    Merge crime data.

    Prefer country_code + year when country_code is available. This avoids issues
    caused by country-name differences.
    """

    if crime_year.empty:
        return master

    crime_columns = [column for column in crime_year.columns if column != "country"]
    crime_merge = crime_year[crime_columns].copy()

    if "country_code" in crime_merge.columns and "country_code" in master.columns:
        master = master.merge(
            crime_merge,
            on=["country_code", "year"],
            how="left",
            suffixes=("", "_crime"),
        )
    else:
        master = master.merge(
            crime_year,
            on=["country", "year"],
            how="left",
            suffixes=("", "_crime"),
        )

    master = ensure_country_code(master)

    return master


def merge_energy(master: pd.DataFrame, energy_year: pd.DataFrame) -> pd.DataFrame:
    """
    Merge energy exposure data.

    Prefer country_code + year because the energy file is built from World Bank data.
    """

    if energy_year.empty:
        return master

    energy_columns = [column for column in energy_year.columns if column != "country"]
    energy_merge = energy_year[energy_columns].copy()

    if "country_code" in energy_merge.columns and "country_code" in master.columns:
        master = master.merge(
            energy_merge,
            on=["country_code", "year"],
            how="left",
            suffixes=("", "_energy"),
        )
    else:
        master = master.merge(
            energy_year,
            on=["country", "year"],
            how="left",
            suffixes=("", "_energy"),
        )

    master = ensure_country_code(master)

    return master


def fill_required_model_columns(master: pd.DataFrame) -> pd.DataFrame:
    """
    Fill required model columns so downstream scoring does not fail.

    This includes the original core variables plus the stronger ACLED features
    added in the updated acled_processing.py.
    """

    master = master.copy()

    numeric_defaults = {
        # Core ACLED features
        "total_acled_events": 0,
        "total_fatalities": 0,
        "protest_events": 0,
        "riot_events": 0,
        "battle_events": 0,
        "explosion_remote_violence_events": 0,
        "violence_against_civilians_events": 0,
        "violent_political_events": 0,
        "civil_unrest_events": 0,

        # Enhanced ACLED sub-event features
        "peaceful_protest_events": 0,
        "protest_with_intervention_events": 0,
        "excessive_force_against_protesters_events": 0,
        "mob_violence_events": 0,
        "armed_clash_events": 0,
        "attack_events": 0,
        "remote_explosive_ied_events": 0,
        "shelling_missile_attack_events": 0,

        # ACLED fatality and spread features
        "fatal_events": 0,
        "high_fatality_events": 0,
        "unique_admin1_locations": 0,
        "unique_admin2_locations": 0,
        "unique_event_locations": 0,
        "unique_coordinate_pairs": 0,
        "fatalities_per_event": 0,

        # ACLED composition / momentum features
        "civil_unrest_share": 0,
        "violent_event_share": 0,
        "protest_share": 0,
        "riot_share": 0,
        "violence_against_civilians_share": 0,
        "three_year_avg_events": 0,
        "three_year_avg_fatalities": 0,
        "recent_event_momentum": 1,
        "recent_fatality_momentum": 1,

        # Crime features
        "homicide_rate_per_100k": None,
        "homicide_rate_per_100k_year": None,

        # Energy features
        "energy_exposure_raw": 0,
        "oil_rents_pct_gdp": 0,
        "natural_gas_rents_pct_gdp": 0,
        "fuel_exports_pct_merchandise_exports": 0,
        "energy_rents_pct_gdp": 0,
    }

    for column, default in numeric_defaults.items():
        if column not in master.columns:
            master[column] = default

    fill_zero_columns = [
        column for column, default in numeric_defaults.items() if default == 0
    ]

    for column in fill_zero_columns:
        master[column] = pd.to_numeric(master[column], errors="coerce").fillna(0)

    for column in ["recent_event_momentum", "recent_fatality_momentum"]:
        master[column] = pd.to_numeric(master[column], errors="coerce").fillna(1)

    master["homicide_rate_per_100k"] = pd.to_numeric(
        master["homicide_rate_per_100k"], errors="coerce"
    )

    original_homicide_available = master["homicide_rate_per_100k"].notna()

    if "crime_data_available" not in master.columns:
        master["crime_data_available"] = original_homicide_available
    else:
        master["crime_data_available"] = (
            master["crime_data_available"]
            .fillna(False)
            .astype(bool)
        )

    if "crime_data_quality_flag" not in master.columns:
        master["crime_data_quality_flag"] = "Homicide proxy missing"

    if "crime_data_source" not in master.columns:
        master["crime_data_source"] = "World Bank / fallback"

    if master["homicide_rate_per_100k"].notna().sum() > 0:
        median_homicide = master["homicide_rate_per_100k"].median()
        fill_mask = master["homicide_rate_per_100k"].isna()

        master.loc[fill_mask, "homicide_rate_per_100k"] = median_homicide

        master.loc[
            fill_mask,
            "crime_data_quality_flag",
        ] = "Median-filled homicide proxy"

        master.loc[
            fill_mask,
            "crime_data_available",
        ] = False
    else:
        master["homicide_rate_per_100k"] = 0
        master["crime_data_available"] = False
        master["crime_data_quality_flag"] = "Homicide proxy unavailable"

    if "acled_data_source" not in master.columns:
        master["acled_data_source"] = "ACLED unavailable or not matched"

    return master


def clean_duplicate_columns(master: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate merge artifacts where possible.
    """

    master = ensure_country_code(master)

    columns_to_drop = []

    for column in master.columns:
        if (
            column.endswith("_crime")
            or column.endswith("_energy")
            or column.endswith("_acled")
        ):
            base_column = (
                column.replace("_crime", "")
                .replace("_energy", "")
                .replace("_acled", "")
            )

            if base_column in master.columns:
                columns_to_drop.append(column)

    if columns_to_drop:
        master = master.drop(columns=columns_to_drop)

    return master


def add_data_quality_flags(master: pd.DataFrame) -> pd.DataFrame:
    """
    Add high-level data coverage flags for diagnostics and reporting.
    """

    master = master.copy()

    master["has_acled_data"] = master["total_acled_events"].fillna(0) > 0
    master["has_energy_exposure_data"] = master["energy_exposure_raw"].fillna(0) > 0

    if "crime_data_available" in master.columns:
        master["has_homicide_data"] = (
            master["crime_data_available"]
            .fillna(False)
            .astype(bool)
        )
    else:
        master["has_homicide_data"] = master["homicide_rate_per_100k"].notna()

    master["data_coverage_score"] = (
        master["has_acled_data"].astype(int)
        + master["has_energy_exposure_data"].astype(int)
        + master["has_homicide_data"].astype(int)
    )

    master["data_coverage_flag"] = master["data_coverage_score"].map(
        {
            0: "Low data coverage",
            1: "Partial data coverage",
            2: "Moderate data coverage",
            3: "Strong data coverage",
        }
    )

    return master


def build_master_dataset(study_year: int = STUDY_YEAR) -> pd.DataFrame:
    """
    Merge World Bank, ACLED, crime, and energy features into one country-level
    executive protection risk dataset.
    """

    print("Building master executive protection dataset...")

    wb_year = prepare_worldbank_data(study_year)
    acled_year = prepare_acled_data(study_year)
    crime_year = prepare_crime_data(study_year)
    energy_year = prepare_energy_data(study_year)

    master = wb_year.copy()

    master = merge_acled(master, acled_year)
    master = ensure_country_code(master)

    master = merge_crime(master, crime_year)
    master = ensure_country_code(master)

    master = merge_energy(master, energy_year)
    master = ensure_country_code(master)

    master = clean_duplicate_columns(master)
    master = fill_required_model_columns(master)
    master = add_data_quality_flags(master)

    if "country_code" not in master.columns:
        raise KeyError(
            "country_code is still missing after merges. "
            "Check World Bank, crime, and energy input files."
        )

    master = master.sort_values("country").reset_index(drop=True)

    MASTER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(MASTER_DATA_FILE, index=False)

    print(f"Master dataset saved to: {MASTER_DATA_FILE}")
    print(f"Shape: {master.shape}")
    print(f"Countries / economies: {master['country_code'].nunique()}")
    print(f"Countries with ACLED data: {int(master['has_acled_data'].sum())}")
    print(f"Countries with homicide data: {int(master['has_homicide_data'].sum())}")
    print(
        "Countries with energy exposure data: "
        f"{int(master['has_energy_exposure_data'].sum())}"
    )

    return master


if __name__ == "__main__":
    build_master_dataset()