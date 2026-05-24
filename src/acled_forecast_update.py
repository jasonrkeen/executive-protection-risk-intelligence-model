import argparse
from datetime import date
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from src.acled_api import get_acled_credentials, request_acled_token
from src.config import (
    ACLED_API_BASE_URL,
    ACLED_API_LIMIT,
    ACLED_FORWARD_TRENDS_FILE,
    FORWARD_ACLED_EVENTS_FILE,
    RISK_RANKINGS_FILE,
    FORWARD_TOP_N_COUNTRIES,
    FORWARD_TARGET_YEAR,
    FORWARD_COMPARISON_YEAR,
    ACLED_FORWARD_COUNTRY_NAME_OVERRIDES,
    FORWARD_ACLED_FIELDS,
    FORWARD_ACLED_EVENT_TYPES,
)


def get_forward_date_windows() -> dict:
    """
    Build date windows for the comparison year and target year.

    The target window uses FORWARD_TARGET_YEAR from config.py.
    The comparison YTD window uses the same month/day cutoff in
    FORWARD_COMPARISON_YEAR as the target window.
    """

    today = date.today()

    target_year = FORWARD_TARGET_YEAR
    comparison_year = FORWARD_COMPARISON_YEAR

    if today.year > target_year:
        target_end = date(target_year, 12, 31)
    elif today.year == target_year:
        target_end = today
    else:
        # If the system date is before the configured target year, use the
        # full target year as the configured forward window.
        target_end = date(target_year, 12, 31)

    target_start = date(target_year, 1, 1)

    comparison_start = date(comparison_year, 1, 1)
    comparison_end = date(comparison_year, target_end.month, target_end.day)

    full_comparison_start = date(comparison_year, 1, 1)
    full_comparison_end = date(comparison_year, 12, 31)

    return {
        "target_start": target_start.isoformat(),
        "target_end": target_end.isoformat(),
        "comparison_start": comparison_start.isoformat(),
        "comparison_end": comparison_end.isoformat(),
        "full_comparison_start": full_comparison_start.isoformat(),
        "full_comparison_end": full_comparison_end.isoformat(),
    }


def get_acled_country_name(country: str) -> str:
    """
    Convert project country name to ACLED country name when needed.
    """

    return ACLED_FORWARD_COUNTRY_NAME_OVERRIDES.get(country, country)


def load_existing_forward_trends() -> pd.DataFrame:
    """
    Load existing forward trends if already created.
    """

    trends = pd.read_csv(ACLED_FORWARD_TRENDS_FILE, low_memory=False)

    print(f"Using existing ACLED forward trends file: {ACLED_FORWARD_TRENDS_FILE}")
    print(f"Shape: {trends.shape}")

    return trends


def load_top_countries(top_n: int = FORWARD_TOP_N_COUNTRIES) -> pd.DataFrame:
    """
    Load top baseline-risk countries from the existing risk rankings.
    """

    if not RISK_RANKINGS_FILE.exists():
        raise FileNotFoundError(
            f"Risk rankings file not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    rankings = pd.read_csv(RISK_RANKINGS_FILE, low_memory=False)

    required_columns = {
        "country",
        "country_code",
        "executive_protection_risk_score",
        "risk_bucket",
    }

    missing = required_columns.difference(rankings.columns)

    if missing:
        raise ValueError(
            f"Risk rankings file is missing required columns: {missing}"
        )

    top = rankings.head(top_n).copy()
    top["acled_query_country"] = top["country"].apply(get_acled_country_name)

    return top


def build_acled_params(
    country: str,
    start_date: str,
    end_date: str,
    page: int,
) -> Dict[str, str | int]:
    """
    Build ACLED API parameters for a country/date window.
    """

    return {
        "country": country,
        "event_date": f"{start_date}|{end_date}",
        "event_date_where": "BETWEEN",
        "event_type": "|".join(FORWARD_ACLED_EVENT_TYPES),
        "fields": "|".join(FORWARD_ACLED_FIELDS),
        "limit": ACLED_API_LIMIT,
        "page": page,
        "with_total": "true",
    }


def fetch_acled_page(
    access_token: str,
    country: str,
    start_date: str,
    end_date: str,
    page: int,
) -> pd.DataFrame:
    """
    Fetch one ACLED page for one country/date window.
    """

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    params = build_acled_params(
        country=country,
        start_date=start_date,
        end_date=end_date,
        page=page,
    )

    response = requests.get(
        ACLED_API_BASE_URL,
        headers=headers,
        params=params,
        timeout=90,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "ACLED forward update request failed.\n"
            f"Country: {country}\n"
            f"Date window: {start_date} to {end_date}\n"
            f"Status code: {response.status_code}\n"
            f"Response: {response.text[:800]}"
        )

    payload = response.json()
    data = payload.get("data", [])

    if not isinstance(data, list):
        raise RuntimeError(
            "Unexpected ACLED response format. Expected payload['data'] to be a list."
        )

    df = pd.DataFrame(data)

    total_count = payload.get("total_count")

    print(
        f"    {country} | {start_date} to {end_date} | "
        f"page {page}: rows={len(df)}"
        + (f", total_count={total_count}" if total_count is not None else "")
    )

    return df


def fetch_country_window_events(
    access_token: str,
    project_country: str,
    acled_country: str,
    start_date: str,
    end_date: str,
    label: str,
    max_pages: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fetch all pages of ACLED events for one country/date window.
    """

    frames: List[pd.DataFrame] = []
    page = 1

    while True:
        df = fetch_acled_page(
            access_token=access_token,
            country=acled_country,
            start_date=start_date,
            end_date=end_date,
            page=page,
        )

        if df.empty:
            break

        df["project_country"] = project_country
        df["acled_query_country"] = acled_country
        df["forward_window"] = label
        frames.append(df)

        if len(df) < ACLED_API_LIMIT:
            break

        page += 1

        if max_pages is not None and page > max_pages:
            print(f"    Reached max_pages={max_pages} for {project_country}, {label}.")
            break

        time.sleep(0.3)

    if not frames:
        return pd.DataFrame(
            columns=FORWARD_ACLED_FIELDS
            + ["project_country", "acled_query_country", "forward_window"]
        )

    events = pd.concat(frames, ignore_index=True)

    return events


def clean_forward_events(events: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize forward ACLED events.
    """

    if events.empty:
        return events

    events = events.copy()

    if "event_date" in events.columns:
        events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce")

    if "year" in events.columns:
        events["year"] = pd.to_numeric(events["year"], errors="coerce")

    if "fatalities" in events.columns:
        events["fatalities"] = pd.to_numeric(
            events["fatalities"], errors="coerce"
        ).fillna(0)

    if "event_id_cnty" in events.columns:
        events = events.drop_duplicates(subset=["event_id_cnty"], keep="first")
    else:
        events = events.drop_duplicates()

    return events.reset_index(drop=True)


def aggregate_window_features(events: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate country/window ACLED events into risk update features.
    """

    if events.empty:
        return pd.DataFrame(
            columns=[
                "project_country",
                "forward_window",
                "events",
                "fatalities",
                "civil_unrest_events",
                "violent_events",
                "fatal_events",
                "high_fatality_events",
                "unique_locations",
            ]
        )

    temp = events.copy()

    temp["civil_unrest_flag"] = temp["event_type"].isin(
        ["Protests", "Riots"]
    ).astype(int)

    temp["violent_event_flag"] = temp["event_type"].isin(
        [
            "Battles",
            "Explosions/Remote violence",
            "Violence against civilians",
        ]
    ).astype(int)

    temp["fatal_event_flag"] = (temp["fatalities"] > 0).astype(int)
    temp["high_fatality_event_flag"] = (temp["fatalities"] >= 5).astype(int)

    output = (
        temp.groupby(["project_country", "forward_window"], as_index=False)
        .agg(
            events=("event_type", "size"),
            fatalities=("fatalities", "sum"),
            civil_unrest_events=("civil_unrest_flag", "sum"),
            violent_events=("violent_event_flag", "sum"),
            fatal_events=("fatal_event_flag", "sum"),
            high_fatality_events=("high_fatality_event_flag", "sum"),
            unique_locations=("location", "nunique"),
        )
    )

    return output


def build_country_trend_row(
    country_row: pd.Series,
    aggregated: pd.DataFrame,
) -> dict:
    """
    Convert aggregated window features into one row per country.
    """

    country = country_row["country"]
    country_code = country_row["country_code"]
    acled_query_country = country_row["acled_query_country"]

    row = {
        "country": country,
        "country_code": country_code,
        "acled_query_country": acled_query_country,
        "baseline_ep_risk_score_2024": country_row["executive_protection_risk_score"],
        "baseline_risk_bucket_2024": country_row["risk_bucket"],
    }

    windows = {
        "comparison_ytd": "2025_ytd_same_period",
        "comparison_full_year": "2025_full_year",
        "target_ytd": "2026_ytd",
    }

    country_data = aggregated[aggregated["project_country"] == country].copy()

    for source_window, prefix in windows.items():
        window_data = country_data[country_data["forward_window"] == source_window]

        if window_data.empty:
            row[f"{prefix}_events"] = 0
            row[f"{prefix}_fatalities"] = 0
            row[f"{prefix}_civil_unrest_events"] = 0
            row[f"{prefix}_violent_events"] = 0
            row[f"{prefix}_fatal_events"] = 0
            row[f"{prefix}_high_fatality_events"] = 0
            row[f"{prefix}_unique_locations"] = 0
        else:
            data = window_data.iloc[0]
            row[f"{prefix}_events"] = data["events"]
            row[f"{prefix}_fatalities"] = data["fatalities"]
            row[f"{prefix}_civil_unrest_events"] = data["civil_unrest_events"]
            row[f"{prefix}_violent_events"] = data["violent_events"]
            row[f"{prefix}_fatal_events"] = data["fatal_events"]
            row[f"{prefix}_high_fatality_events"] = data["high_fatality_events"]
            row[f"{prefix}_unique_locations"] = data["unique_locations"]

    row["forward_data_available"] = (
        row["2025_ytd_same_period_events"] > 0
        or row["2025_full_year_events"] > 0
        or row["2026_ytd_events"] > 0
    )

    row["target_year_data_available"] = row["2026_ytd_events"] > 0

    if row["target_year_data_available"]:
        row["forward_fetch_status"] = "Target-year ACLED forward data returned"
    elif row["forward_data_available"]:
        row["forward_fetch_status"] = (
            "Comparison data returned; target-year ACLED data unavailable"
        )
    else:
        row["forward_fetch_status"] = "No ACLED forward events returned"

    row["event_momentum_2026_vs_2025_ytd"] = (
        (row["2026_ytd_events"] + 1)
        / (row["2025_ytd_same_period_events"] + 1)
    )

    row["fatality_momentum_2026_vs_2025_ytd"] = (
        (row["2026_ytd_fatalities"] + 1)
        / (row["2025_ytd_same_period_fatalities"] + 1)
    )

    row["violent_event_momentum_2026_vs_2025_ytd"] = (
        (row["2026_ytd_violent_events"] + 1)
        / (row["2025_ytd_same_period_violent_events"] + 1)
    )

    row["civil_unrest_momentum_2026_vs_2025_ytd"] = (
        (row["2026_ytd_civil_unrest_events"] + 1)
        / (row["2025_ytd_same_period_civil_unrest_events"] + 1)
    )

    return row


def save_forward_events(events: pd.DataFrame) -> None:
    """
    Save raw forward ACLED events for auditability.
    """

    FORWARD_ACLED_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(FORWARD_ACLED_EVENTS_FILE, index=False)
    print(f"Forward ACLED raw events saved to: {FORWARD_ACLED_EVENTS_FILE}")
    print(f"Forward ACLED raw events shape: {events.shape}")


def build_acled_forward_trends(
    max_pages_per_window: Optional[int] = None,
    force_refresh: bool = False,
    use_existing: bool = True,
) -> pd.DataFrame:
    """
    Build comparison-year and target-year ACLED trend features for the current
    top-risk countries.
    """

    print("Building ACLED 2025-2026 forward risk update...")

    if use_existing and ACLED_FORWARD_TRENDS_FILE.exists() and not force_refresh:
        return load_existing_forward_trends()

    top_countries = load_top_countries()
    date_windows = get_forward_date_windows()

    print("\nForward date windows:")
    for key, value in date_windows.items():
        print(f"  {key}: {value}")

    username, password = get_acled_credentials()
    access_token = request_acled_token(username=username, password=password)

    all_events = []

    for _, country_row in top_countries.iterrows():
        project_country = country_row["country"]
        acled_country = country_row["acled_query_country"]

        print(f"\nFetching forward ACLED windows for {project_country}...")
        if project_country != acled_country:
            print(f"  Using ACLED query country override: {acled_country}")

        window_specs = [
            (
                "comparison_ytd",
                date_windows["comparison_start"],
                date_windows["comparison_end"],
            ),
            (
                "comparison_full_year",
                date_windows["full_comparison_start"],
                date_windows["full_comparison_end"],
            ),
            (
                "target_ytd",
                date_windows["target_start"],
                date_windows["target_end"],
            ),
        ]

        for label, start_date, end_date in window_specs:
            events = fetch_country_window_events(
                access_token=access_token,
                project_country=project_country,
                acled_country=acled_country,
                start_date=start_date,
                end_date=end_date,
                label=label,
                max_pages=max_pages_per_window,
            )

            if not events.empty:
                all_events.append(events)

            time.sleep(0.3)

    if all_events:
        events = pd.concat(all_events, ignore_index=True)
        events = clean_forward_events(events)
    else:
        events = pd.DataFrame(
            columns=FORWARD_ACLED_FIELDS
            + ["project_country", "acled_query_country", "forward_window"]
        )

    save_forward_events(events)

    aggregated = aggregate_window_features(events)

    rows = []

    for _, country_row in top_countries.iterrows():
        rows.append(build_country_trend_row(country_row, aggregated))

    trends = pd.DataFrame(rows)

    for column in trends.columns:
        if column not in [
            "country",
            "country_code",
            "acled_query_country",
            "baseline_risk_bucket_2024",
            "forward_fetch_status",
        ]:
            trends[column] = pd.to_numeric(trends[column], errors="coerce")

    trends["forward_update_window"] = (
        f"{date_windows['target_start']} to {date_windows['target_end']}"
    )
    trends["comparison_window"] = (
        f"{date_windows['comparison_start']} to {date_windows['comparison_end']}"
    )

    target_year_events = (
        pd.to_numeric(trends["2026_ytd_events"], errors="coerce").fillna(0).sum()
        if "2026_ytd_events" in trends.columns
        else 0
    )

    trends["target_year_data_status"] = (
        "Target-year ACLED data available"
        if target_year_events > 0
        else "Target-year ACLED data unavailable"
    )

    ACLED_FORWARD_TRENDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    trends.to_csv(ACLED_FORWARD_TRENDS_FILE, index=False)

    print(f"\nACLED forward trends saved to: {ACLED_FORWARD_TRENDS_FILE}")
    print(f"Shape: {trends.shape}")

    if "forward_fetch_status" in trends.columns:
        print("\nForward fetch status:")
        print(trends["forward_fetch_status"].value_counts().to_string())

    if "target_year_data_status" in trends.columns:
        print("\nTarget-year data status:")
        print(trends["target_year_data_status"].value_counts().to_string())

    return trends


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Build ACLED forward-risk trend features."
    )

    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force a fresh ACLED API pull instead of using the existing trends file.",
    )

    parser.add_argument(
        "--no-existing",
        action="store_true",
        help="Do not use the existing trends file.",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional max pages per country/window for testing.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    build_acled_forward_trends(
        max_pages_per_window=args.max_pages,
        force_refresh=args.force_refresh,
        use_existing=not args.no_existing,
    )