import pandas as pd

from src.config import (
    ACLED_RAW_FILE,
    ACLED_COUNTRY_FILE,
    START_YEAR,
    END_YEAR,
)


EVENT_TYPE_COLUMNS = {
    "Protests": "protest_events",
    "Riots": "riot_events",
    "Battles": "battle_events",
    "Explosions/Remote violence": "explosion_remote_violence_events",
    "Violence against civilians": "violence_against_civilians_events",
}


SUB_EVENT_TYPE_COLUMNS = {
    "Peaceful protest": "peaceful_protest_events",
    "Protest with intervention": "protest_with_intervention_events",
    "Excessive force against protesters": "excessive_force_against_protesters_events",
    "Mob violence": "mob_violence_events",
    "Armed clash": "armed_clash_events",
    "Attack": "attack_events",
    "Remote explosive/landmine/IED": "remote_explosive_ied_events",
    "Shelling/artillery/missile attack": "shelling_missile_attack_events",
}


EMPTY_ACLED_COLUMNS = [
    "country",
    "year",
    "total_acled_events",
    "total_fatalities",
    "protest_events",
    "riot_events",
    "battle_events",
    "explosion_remote_violence_events",
    "violence_against_civilians_events",
    "violent_political_events",
    "civil_unrest_events",
    "peaceful_protest_events",
    "protest_with_intervention_events",
    "excessive_force_against_protesters_events",
    "mob_violence_events",
    "armed_clash_events",
    "attack_events",
    "remote_explosive_ied_events",
    "shelling_missile_attack_events",
    "fatal_events",
    "high_fatality_events",
    "unique_admin1_locations",
    "unique_admin2_locations",
    "unique_event_locations",
    "unique_coordinate_pairs",
    "fatalities_per_event",
    "civil_unrest_share",
    "violent_event_share",
    "protest_share",
    "riot_share",
    "violence_against_civilians_share",
    "three_year_avg_events",
    "three_year_avg_fatalities",
    "recent_event_momentum",
    "recent_fatality_momentum",
    "acled_data_source",
]


def create_empty_acled_features() -> pd.DataFrame:
    """
    Create an empty ACLED feature file when ACLED data has not been added yet.

    This allows the pipeline to run in baseline mode without failing.
    """

    output = pd.DataFrame(columns=EMPTY_ACLED_COLUMNS)
    ACLED_COUNTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(ACLED_COUNTRY_FILE, index=False)

    print(
        f"No ACLED file found at {ACLED_RAW_FILE}. "
        f"Created empty placeholder: {ACLED_COUNTRY_FILE}"
    )

    return output


def load_acled_events() -> pd.DataFrame:
    """
    Load ACLED event data from the API-created or manually downloaded CSV.

    Expected location:
        data/raw/acled_events.csv
    """

    if not ACLED_RAW_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(ACLED_RAW_FILE, low_memory=False)

    required_columns = {
        "event_date",
        "year",
        "country",
        "event_type",
        "fatalities",
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(f"ACLED file is missing required columns: {missing}")

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0)

    df = df[(df["year"] >= START_YEAR) & (df["year"] <= END_YEAR)].copy()

    optional_columns = [
        "sub_event_type",
        "admin1",
        "admin2",
        "location",
        "latitude",
        "longitude",
    ]

    for column in optional_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df["country"] = df["country"].astype(str).str.strip()
    df["event_type"] = df["event_type"].astype(str).str.strip()
    df["sub_event_type"] = df["sub_event_type"].astype(str).str.strip()

    if "event_id_cnty" in df.columns:
        df = df.drop_duplicates(subset=["event_id_cnty"], keep="first")
    else:
        df = df.drop_duplicates()

    df = df.dropna(subset=["country", "year"]).copy()
    df["year"] = df["year"].astype(int)

    return df.reset_index(drop=True)


def add_event_type_counts(base: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Add event-type counts to the country-year feature table.
    """

    output = base.copy()

    for event_type, column_name in EVENT_TYPE_COLUMNS.items():
        event_counts = (
            df[df["event_type"] == event_type]
            .groupby(["country", "year"])
            .size()
            .reset_index(name=column_name)
        )

        output = output.merge(event_counts, on=["country", "year"], how="left")

    for column in EVENT_TYPE_COLUMNS.values():
        output[column] = output[column].fillna(0)

    return output


def add_sub_event_type_counts(base: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Add selected ACLED sub-event-type counts.

    These give the model more executive-protection relevant detail than broad
    event categories alone.
    """

    output = base.copy()

    for sub_event_type, column_name in SUB_EVENT_TYPE_COLUMNS.items():
        sub_counts = (
            df[df["sub_event_type"] == sub_event_type]
            .groupby(["country", "year"])
            .size()
            .reset_index(name=column_name)
        )

        output = output.merge(sub_counts, on=["country", "year"], how="left")

    for column in SUB_EVENT_TYPE_COLUMNS.values():
        output[column] = output[column].fillna(0)

    return output


def add_location_features(base: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Add geographic spread features.

    These help distinguish countries with isolated incidents from countries with
    broader nationwide unrest or violence.
    """

    temp = df.copy()

    temp["coordinate_pair"] = (
        temp["latitude"].round(4).astype(str)
        + ","
        + temp["longitude"].round(4).astype(str)
    )

    temp.loc[
        temp["latitude"].isna() | temp["longitude"].isna(),
        "coordinate_pair",
    ] = pd.NA

    location_features = (
        temp.groupby(["country", "year"])
        .agg(
            unique_admin1_locations=("admin1", "nunique"),
            unique_admin2_locations=("admin2", "nunique"),
            unique_event_locations=("location", "nunique"),
            unique_coordinate_pairs=("coordinate_pair", "nunique"),
        )
        .reset_index()
    )

    output = base.merge(location_features, on=["country", "year"], how="left")

    for column in [
        "unique_admin1_locations",
        "unique_admin2_locations",
        "unique_event_locations",
        "unique_coordinate_pairs",
    ]:
        output[column] = output[column].fillna(0)

    return output


def add_fatality_features(base: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Add fatality intensity features.
    """

    temp = df.copy()
    temp["fatal_event_flag"] = (temp["fatalities"] > 0).astype(int)
    temp["high_fatality_event_flag"] = (temp["fatalities"] >= 5).astype(int)

    fatality_features = (
        temp.groupby(["country", "year"])
        .agg(
            fatal_events=("fatal_event_flag", "sum"),
            high_fatality_events=("high_fatality_event_flag", "sum"),
        )
        .reset_index()
    )

    output = base.merge(fatality_features, on=["country", "year"], how="left")

    output["fatal_events"] = output["fatal_events"].fillna(0)
    output["high_fatality_events"] = output["high_fatality_events"].fillna(0)

    output["fatalities_per_event"] = (
        output["total_fatalities"]
        / output["total_acled_events"].replace(0, pd.NA)
    ).fillna(0)

    return output


def add_share_features(base: pd.DataFrame) -> pd.DataFrame:
    """
    Add event composition shares.
    """

    output = base.copy()

    violent_columns = [
        "battle_events",
        "explosion_remote_violence_events",
        "violence_against_civilians_events",
    ]

    for column in violent_columns:
        if column not in output.columns:
            output[column] = 0

    output["violent_political_events"] = output[violent_columns].sum(axis=1)
    output["civil_unrest_events"] = output["protest_events"] + output["riot_events"]

    denominator = output["total_acled_events"].replace(0, pd.NA)

    output["civil_unrest_share"] = (
        output["civil_unrest_events"] / denominator
    ).fillna(0)

    output["violent_event_share"] = (
        output["violent_political_events"] / denominator
    ).fillna(0)

    output["protest_share"] = (
        output["protest_events"] / denominator
    ).fillna(0)

    output["riot_share"] = (
        output["riot_events"] / denominator
    ).fillna(0)

    output["violence_against_civilians_share"] = (
        output["violence_against_civilians_events"] / denominator
    ).fillna(0)

    return output


def add_momentum_features(base: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling three-year momentum features.

    Recent event momentum compares the current year to the trailing three-year
    event average. Recent fatality momentum does the same for fatalities.
    """

    output = base.sort_values(["country", "year"]).reset_index(drop=True)

    output["three_year_avg_events"] = (
        output.groupby("country")["total_acled_events"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    output["three_year_avg_fatalities"] = (
        output.groupby("country")["total_fatalities"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    output["recent_event_momentum"] = (
        output["total_acled_events"]
        / output["three_year_avg_events"].replace(0, pd.NA)
    ).fillna(1)

    output["recent_fatality_momentum"] = (
        output["total_fatalities"]
        / output["three_year_avg_fatalities"].replace(0, pd.NA)
    ).fillna(1)

    return output


def enforce_output_schema(base: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the ACLED feature table has a consistent schema.
    """

    output = base.copy()

    for column in EMPTY_ACLED_COLUMNS:
        if column not in output.columns:
            output[column] = 0

    output["acled_data_source"] = "ACLED API / data export"

    numeric_columns = [
        column
        for column in output.columns
        if column not in ["country", "acled_data_source"]
    ]

    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)

    ordered_columns = [
        column for column in EMPTY_ACLED_COLUMNS if column in output.columns
    ]

    extra_columns = [
        column for column in output.columns if column not in ordered_columns
    ]

    output = output[ordered_columns + extra_columns]

    return output


def build_acled_country_features() -> pd.DataFrame:
    """
    Convert ACLED event-level data into country-year risk features.
    """

    print("Processing ACLED event data...")

    df = load_acled_events()

    if df.empty:
        return create_empty_acled_features()

    base = (
        df.groupby(["country", "year"])
        .agg(
            total_acled_events=("event_type", "size"),
            total_fatalities=("fatalities", "sum"),
        )
        .reset_index()
    )

    base = add_event_type_counts(base, df)
    base = add_sub_event_type_counts(base, df)
    base = add_location_features(base, df)
    base = add_fatality_features(base, df)
    base = add_share_features(base)
    base = add_momentum_features(base)
    base = enforce_output_schema(base)

    base = base.sort_values(["country", "year"]).reset_index(drop=True)

    ACLED_COUNTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(ACLED_COUNTRY_FILE, index=False)

    print(f"ACLED country features saved to: {ACLED_COUNTRY_FILE}")
    print(f"Shape: {base.shape}")

    if not base.empty:
        print(f"Countries: {base['country'].nunique()}")
        print(f"Years: {int(base['year'].min())} to {int(base['year'].max())}")
        print(f"Total events processed: {int(base['total_acled_events'].sum()):,}")
        print(f"Total fatalities processed: {int(base['total_fatalities'].sum()):,}")

    return base


if __name__ == "__main__":
    build_acled_country_features()