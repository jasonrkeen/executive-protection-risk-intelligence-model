import time
from typing import Optional

import pandas as pd
import requests

from src.config import (
    START_YEAR,
    END_YEAR,
    WGI_SOURCE,
    WGI_INDICATORS,
    ECONOMIC_INDICATORS,
    CRIME_INDICATORS,
    WORLD_BANK_FILE,
)


def build_worldbank_url(
    indicator_code: str,
    source: Optional[int] = None,
    page: int = 1,
) -> str:
    """
    Build a World Bank API URL for one indicator.
    """

    base_url = (
        f"https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator_code}?format=json&per_page=20000&page={page}"
    )

    if source is not None:
        base_url += f"&source={source}"

    return base_url


def request_worldbank_json(url: str, indicator_code: str) -> list:
    """
    Request World Bank API JSON with a small retry loop.
    """

    last_error = None

    for attempt in range(1, 4):
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            print(
                f"  Warning: request failed for {indicator_code} "
                f"(attempt {attempt}/3): {exc}"
            )
            time.sleep(1.5 * attempt)

    raise RuntimeError(
        f"World Bank request failed for {indicator_code} after 3 attempts: "
        f"{last_error}"
    )


def parse_worldbank_response(payload, indicator_code: str) -> tuple[dict, list]:
    """
    Validate and parse a World Bank API response.
    """

    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError(f"Unexpected World Bank response for {indicator_code}")

    metadata = payload[0] or {}
    records = payload[1] or []

    if not isinstance(records, list):
        raise ValueError(f"Unexpected World Bank records format for {indicator_code}")

    return metadata, records


def fetch_worldbank_indicator(
    indicator_code: str,
    indicator_name: str,
    source: Optional[int] = None,
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
) -> pd.DataFrame:
    """
    Fetch one World Bank indicator for all countries and years.
    """

    rows = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        url = build_worldbank_url(
            indicator_code=indicator_code,
            source=source,
            page=page,
        )

        payload = request_worldbank_json(url, indicator_code)

        metadata, records = parse_worldbank_response(
            payload,
            indicator_code=indicator_code,
        )

        total_pages = int(metadata.get("pages", 1))

        for item in records:
            country = item.get("country", {}).get("value")
            country_code = item.get("countryiso3code")
            value = item.get("value")

            try:
                year = int(item.get("date"))
            except (TypeError, ValueError):
                continue

            if not country or not country_code:
                continue

            if start_year <= year <= end_year:
                rows.append(
                    {
                        "country": country,
                        "country_code": country_code,
                        "year": year,
                        indicator_name: value,
                        f"{indicator_name}_indicator_code": indicator_code,
                    }
                )

        page += 1

    df = pd.DataFrame(rows)

    if df.empty:
        print(f"  Warning: no records returned for {indicator_code}: {indicator_name}")
        return pd.DataFrame(
            columns=[
                "country",
                "country_code",
                "year",
                indicator_name,
                f"{indicator_name}_indicator_code",
            ]
        )

    return df


def latest_available_by_country(
    df: pd.DataFrame,
    indicator_name: str,
    end_year: int = END_YEAR,
) -> pd.DataFrame:
    """
    Convert a country-year indicator panel into the latest available observation
    for each ISO3 country code up to END_YEAR.

    This preserves the exact data year used for transparency.
    """

    output_columns = [
        "country",
        "country_code",
        indicator_name,
        f"{indicator_name}_year",
        f"{indicator_name}_indicator_code",
        f"{indicator_name}_data_available",
    ]

    if df.empty:
        return pd.DataFrame(columns=output_columns)

    clean = df.copy()

    clean["country"] = clean["country"].astype("string").str.strip()
    clean["country_code"] = clean["country_code"].astype("string").str.strip()
    clean["country_code"] = clean["country_code"].replace(
        {"": pd.NA, "nan": pd.NA, "None": pd.NA}
    )

    clean["year"] = pd.to_numeric(clean["year"], errors="coerce")
    clean[indicator_name] = pd.to_numeric(clean[indicator_name], errors="coerce")

    clean = clean[
        (clean["year"] <= end_year)
        & clean["country_code"].notna()
        & clean[indicator_name].notna()
    ].copy()

    if clean.empty:
        print(f"  Warning: all values missing for {indicator_name}")
        return pd.DataFrame(columns=output_columns)

    if f"{indicator_name}_indicator_code" not in clean.columns:
        clean[f"{indicator_name}_indicator_code"] = pd.NA

    clean = clean.sort_values(
        ["country_code", "year", "country"],
        ascending=[True, True, True],
    )

    latest = (
        clean.groupby("country_code", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )

    latest = latest[
        [
            "country",
            "country_code",
            "year",
            indicator_name,
            f"{indicator_name}_indicator_code",
        ]
    ].rename(columns={"year": f"{indicator_name}_year"})

    latest[f"{indicator_name}_data_available"] = latest[indicator_name].notna()

    return latest


def fetch_latest_indicator(
    indicator_code: str,
    indicator_name: str,
    source: Optional[int] = None,
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
) -> pd.DataFrame:
    """
    Fetch a World Bank indicator and keep the latest available value by country.
    """

    panel = fetch_worldbank_indicator(
        indicator_code=indicator_code,
        indicator_name=indicator_name,
        source=source,
        start_year=start_year,
        end_year=end_year,
    )

    latest = latest_available_by_country(
        df=panel,
        indicator_name=indicator_name,
        end_year=end_year,
    )

    return latest


def coalesce_country_columns(master: pd.DataFrame) -> pd.DataFrame:
    """
    Coalesce country name columns created during country_code-only merges.

    Critical fix:
    Do not treat country_code as a country-name column. country_code is the
    merge key and must be preserved.
    """

    output = master.copy()

    country_columns = [
        column
        for column in output.columns
        if column == "country"
        or (
            column.startswith("country_")
            and column != "country_code"
        )
    ]

    if not country_columns:
        output["country"] = pd.NA
        return output

    output["country"] = output[country_columns].bfill(axis=1).iloc[:, 0]

    drop_columns = [
        column
        for column in country_columns
        if column != "country"
    ]

    if drop_columns:
        output = output.drop(columns=drop_columns)

    return output


def consolidate_duplicate_country_codes(master: pd.DataFrame) -> pd.DataFrame:
    """
    Consolidate duplicate ISO3 country codes after merging indicators.

    Some World Bank endpoints can return overlapping economy labels for the same
    ISO3 code. The model should use one row per country_code.
    """

    if master.empty:
        return master

    master = coalesce_country_columns(master)

    if "country_code" not in master.columns:
        raise KeyError(
            "country_code is missing before duplicate consolidation. "
            "Check coalesce_country_columns() and merge_indicator_frames()."
        )

    duplicate_codes = (
        master.loc[master["country_code"].duplicated(), "country_code"]
        .dropna()
        .unique()
        .tolist()
    )

    if duplicate_codes:
        print(
            "\nWarning: duplicate country codes detected after merge. "
            "Consolidating duplicates:"
        )
        print(f"  {duplicate_codes}")

    aggregation_rules = {}

    for column in master.columns:
        if column == "country_code":
            continue

        if column == "country":
            aggregation_rules[column] = (
                lambda x: x.dropna().iloc[0] if x.notna().any() else None
            )
        elif column.endswith("_data_available"):
            aggregation_rules[column] = "max"
        else:
            aggregation_rules[column] = (
                lambda x: x.dropna().iloc[0] if x.notna().any() else None
            )

    consolidated = (
        master.sort_values(["country_code", "country"])
        .groupby("country_code", as_index=False)
        .agg(aggregation_rules)
    )

    column_order = ["country", "country_code"]
    remaining_columns = [
        column for column in consolidated.columns if column not in column_order
    ]

    consolidated = consolidated[column_order + remaining_columns]

    return consolidated


def merge_indicator_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Merge latest-available indicator frames into one country-level dataset.

    Merge is performed on country_code only. Country names are coalesced after
    each merge to avoid losing rows when World Bank labels vary by source.
    """

    master = None

    for frame in frames:
        if frame.empty:
            continue

        frame = frame.copy()

        if "country_code" not in frame.columns:
            print("  Warning: indicator frame missing country_code. Skipping frame.")
            continue

        frame["country_code"] = frame["country_code"].astype("string").str.strip()
        frame["country_code"] = frame["country_code"].replace(
            {"": pd.NA, "nan": pd.NA, "None": pd.NA}
        )

        frame = frame[frame["country_code"].notna()].copy()

        if frame.empty:
            continue

        if master is None:
            master = frame.copy()
        else:
            master = master.merge(
                frame,
                on="country_code",
                how="outer",
                suffixes=("", "_new"),
            )
            master = coalesce_country_columns(master)

            if "country_code" not in master.columns:
                raise KeyError(
                    "country_code was dropped during World Bank indicator merge. "
                    "Check coalesce_country_columns()."
                )

    if master is None:
        raise ValueError("No World Bank indicator frames were available to merge.")

    master = consolidate_duplicate_country_codes(master)
    master = master.sort_values("country").reset_index(drop=True)

    return master


def add_model_year(master: pd.DataFrame) -> pd.DataFrame:
    """
    Add a model year column to align with the rest of the pipeline.

    The World Bank data uses latest available values up to END_YEAR. The 'year'
    column represents the model study year, while exact indicator years are
    preserved in columns ending with '_year'.
    """

    master = master.copy()
    master["year"] = END_YEAR

    column_order = ["country", "country_code", "year"]
    remaining_columns = [
        column for column in master.columns if column not in column_order
    ]

    master = master[column_order + remaining_columns]

    return master


def add_worldbank_coverage_summary(master: pd.DataFrame) -> pd.DataFrame:
    """
    Add World Bank data coverage fields by row.
    """

    master = master.copy()

    indicator_value_columns = [
        column
        for column in master.columns
        if column not in ["country", "country_code", "year"]
        and not column.endswith("_year")
        and not column.endswith("_indicator_code")
        and not column.endswith("_data_available")
    ]

    data_available_columns = [
        column for column in master.columns if column.endswith("_data_available")
    ]

    if data_available_columns:
        for column in data_available_columns:
            master[column] = master[column].fillna(False).astype(bool)

        master["worldbank_indicators_available"] = master[
            data_available_columns
        ].sum(axis=1)

        master["worldbank_indicator_count"] = len(data_available_columns)
    else:
        master["worldbank_indicators_available"] = master[
            indicator_value_columns
        ].notna().sum(axis=1)

        master["worldbank_indicator_count"] = len(indicator_value_columns)

    master["worldbank_coverage_share"] = (
        master["worldbank_indicators_available"]
        / master["worldbank_indicator_count"].replace(0, pd.NA)
    ).fillna(0)

    master["worldbank_coverage_flag"] = pd.cut(
        master["worldbank_coverage_share"],
        bins=[-0.01, 0.25, 0.50, 0.75, 1.00],
        labels=[
            "Low World Bank coverage",
            "Partial World Bank coverage",
            "Moderate World Bank coverage",
            "Strong World Bank coverage",
        ],
    ).astype(str)

    return master


def print_quality_summary(master: pd.DataFrame) -> None:
    """
    Print basic data quality information for the World Bank dataset.
    """

    print("\nWorld Bank data quality summary")
    print("-" * 40)
    print(f"Countries / economies: {master['country_code'].nunique()}")
    print(f"Rows: {len(master)}")

    duplicate_count = master["country_code"].duplicated().sum()
    print(f"Duplicate country codes after consolidation: {duplicate_count}")

    indicator_columns = [
        column
        for column in master.columns
        if column not in ["country", "country_code", "year"]
        and not column.endswith("_year")
        and not column.endswith("_indicator_code")
        and not column.endswith("_data_available")
        and not column.startswith("worldbank_")
    ]

    if indicator_columns:
        print("\nMissing value counts:")
        missing = master[indicator_columns].isna().sum().sort_values(ascending=False)
        print(missing)

    year_columns = [column for column in master.columns if column.endswith("_year")]

    if year_columns:
        print("\nLatest data year ranges:")
        for column in year_columns:
            min_year = master[column].min()
            max_year = master[column].max()
            print(f"  {column}: {min_year} to {max_year}")

    if "worldbank_coverage_share" in master.columns:
        print("\nWorld Bank coverage flag distribution:")
        print(master["worldbank_coverage_flag"].value_counts())

    print("-" * 40)


def build_worldbank_dataset() -> pd.DataFrame:
    """
    Build the World Bank dataset used in the executive protection model.

    This version keeps the latest available observation for each country up to
    END_YEAR and adds a homicide-rate proxy from the World Bank API.
    """

    print("Downloading World Bank WGI indicators...")

    frames = []

    for code, name in WGI_INDICATORS.items():
        print(f"  Fetching {code}: {name}")
        df = fetch_latest_indicator(
            indicator_code=code,
            indicator_name=name,
            source=WGI_SOURCE,
        )
        frames.append(df)
        time.sleep(0.25)

    print("\nDownloading World Bank economic and energy indicators...")

    for code, name in ECONOMIC_INDICATORS.items():
        print(f"  Fetching {code}: {name}")
        df = fetch_latest_indicator(
            indicator_code=code,
            indicator_name=name,
            source=None,
        )
        frames.append(df)
        time.sleep(0.25)

    print("\nDownloading World Bank crime proxy indicators...")

    for code, name in CRIME_INDICATORS.items():
        print(f"  Fetching {code}: {name}")
        df = fetch_latest_indicator(
            indicator_code=code,
            indicator_name=name,
            source=None,
        )
        frames.append(df)
        time.sleep(0.25)

    master = merge_indicator_frames(frames)
    master = add_model_year(master)
    master = add_worldbank_coverage_summary(master)

    WORLD_BANK_FILE.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(WORLD_BANK_FILE, index=False)

    print(f"\nWorld Bank dataset saved to: {WORLD_BANK_FILE}")
    print(f"Shape: {master.shape}")

    print_quality_summary(master)

    return master


if __name__ == "__main__":
    build_worldbank_dataset()