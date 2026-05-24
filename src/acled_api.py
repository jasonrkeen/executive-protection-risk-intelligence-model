import os
import time
from typing import Dict, Optional

import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import (
    START_YEAR,
    END_YEAR,
    ACLED_RAW_FILE,
    ACLED_CHECKPOINT_FILE,
    ACLED_API_BASE_URL,
    ACLED_OAUTH_URL,
    ACLED_API_LIMIT,
    ACLED_API_FIELDS,
    ACLED_EVENT_TYPES,
)


def get_acled_credentials() -> tuple[str, str]:
    """
    Load ACLED credentials from .env.

    Required .env variables:
        ACLED_USERNAME
        ACLED_PASSWORD
    """

    load_dotenv()

    username = os.getenv("ACLED_USERNAME")
    password = os.getenv("ACLED_PASSWORD")

    if not username or not password:
        raise ValueError(
            "Missing ACLED credentials. Create a .env file in the project root with:\n"
            "ACLED_USERNAME=your_myacled_email_here\n"
            "ACLED_PASSWORD=your_myacled_password_here"
        )

    return username, password


def request_acled_token(username: str, password: str) -> str:
    """
    Request an OAuth bearer token from ACLED.
    """

    payload = {
        "username": username,
        "password": password,
        "grant_type": "password",
        "client_id": "acled",
        "scope": "authenticated",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(
        ACLED_OAUTH_URL,
        data=payload,
        headers=headers,
        timeout=45,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "ACLED authentication failed.\n"
            f"Status code: {response.status_code}\n"
            f"Response: {response.text[:800]}"
        )

    token_payload = response.json()
    access_token = token_payload.get("access_token")

    if not access_token:
        raise RuntimeError(
            "ACLED authentication response did not include an access_token.\n"
            f"Response keys: {list(token_payload.keys())}"
        )

    return access_token


def build_acled_params(page: int) -> Dict[str, str | int]:
    """
    Build ACLED query parameters.

    This pull focuses on event types most relevant to executive protection:
    protests, riots, battles, remote violence, and violence against civilians.

    The date range is controlled by START_YEAR and END_YEAR in config.py.
    """

    return {
        "year": f"{START_YEAR}|{END_YEAR}",
        "year_where": "BETWEEN",
        "event_type": "|".join(ACLED_EVENT_TYPES),
        "fields": "|".join(ACLED_API_FIELDS),
        "limit": ACLED_API_LIMIT,
        "page": page,
        "with_total": "true",
    }


def fetch_acled_page(access_token: str, page: int) -> pd.DataFrame:
    """
    Fetch one page of ACLED data.
    """

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    params = build_acled_params(page=page)

    response = requests.get(
        ACLED_API_BASE_URL,
        headers=headers,
        params=params,
        timeout=90,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "ACLED data request failed.\n"
            f"Status code: {response.status_code}\n"
            f"Response: {response.text[:800]}"
        )

    payload = response.json()
    data = payload.get("data", [])

    if not isinstance(data, list):
        raise RuntimeError(
            "Unexpected ACLED response format. Expected payload['data'] to be a list.\n"
            f"Response keys: {list(payload.keys())}"
        )

    df = pd.DataFrame(data)

    count = payload.get("count")
    total_count = payload.get("total_count")

    print(
        f"  Page {page}: rows={len(df)}"
        + (f", count={count}" if count is not None else "")
        + (f", total_count={total_count}" if total_count is not None else "")
    )

    return df


def clean_acled_events(events: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize ACLED event fields and remove duplicates.
    """

    if events.empty:
        return events

    events = events.copy()

    if "year" in events.columns:
        events["year"] = pd.to_numeric(events["year"], errors="coerce")

    if "fatalities" in events.columns:
        events["fatalities"] = pd.to_numeric(
            events["fatalities"],
            errors="coerce",
        ).fillna(0)

    if "event_date" in events.columns:
        events["event_date"] = pd.to_datetime(
            events["event_date"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")

    if "latitude" in events.columns:
        events["latitude"] = pd.to_numeric(events["latitude"], errors="coerce")

    if "longitude" in events.columns:
        events["longitude"] = pd.to_numeric(events["longitude"], errors="coerce")

    if "event_id_cnty" in events.columns:
        events = events.drop_duplicates(subset=["event_id_cnty"], keep="first")
    else:
        events = events.drop_duplicates()

    events = events.reset_index(drop=True)

    return events


def append_checkpoint(df: pd.DataFrame) -> None:
    """
    Append one page of ACLED data to a checkpoint CSV.

    This protects against losing progress during very large downloads.
    """

    if df.empty:
        return

    ACLED_CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)

    write_header = not ACLED_CHECKPOINT_FILE.exists()

    df.to_csv(
        ACLED_CHECKPOINT_FILE,
        mode="a",
        header=write_header,
        index=False,
    )


def finalize_from_checkpoint() -> pd.DataFrame:
    """
    Read checkpoint data, clean it, deduplicate it, and save final raw ACLED CSV.
    """

    if not ACLED_CHECKPOINT_FILE.exists():
        raise FileNotFoundError(
            f"Checkpoint file not found at {ACLED_CHECKPOINT_FILE}"
        )

    print(f"Finalizing ACLED data from checkpoint: {ACLED_CHECKPOINT_FILE}")

    events = pd.read_csv(ACLED_CHECKPOINT_FILE, low_memory=False)
    events = clean_acled_events(events)

    ACLED_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(ACLED_RAW_FILE, index=False)

    print(f"\nACLED raw events saved to: {ACLED_RAW_FILE}")
    print(f"Shape: {events.shape}")

    return events


def load_existing_acled_file() -> pd.DataFrame:
    """
    Load the existing ACLED raw file if it has already been downloaded.
    """

    events = pd.read_csv(ACLED_RAW_FILE, low_memory=False)
    events = clean_acled_events(events)

    print(f"Using existing ACLED raw file: {ACLED_RAW_FILE}")
    print(f"Shape: {events.shape}")

    return events


def remove_existing_acled_files() -> None:
    """
    Remove old ACLED raw and checkpoint files before a forced refresh.
    """

    if ACLED_RAW_FILE.exists():
        ACLED_RAW_FILE.unlink()
        print(f"Deleted existing ACLED raw file: {ACLED_RAW_FILE}")

    if ACLED_CHECKPOINT_FILE.exists():
        ACLED_CHECKPOINT_FILE.unlink()
        print(f"Deleted existing ACLED checkpoint file: {ACLED_CHECKPOINT_FILE}")


def fetch_acled_events(
    max_pages: Optional[int] = None,
    force_refresh: bool = False,
    use_existing: bool = True,
) -> pd.DataFrame:
    """
    Fetch ACLED events across all available pages for the configured query.

    Parameters
    ----------
    max_pages:
        Optional page limit for testing.
    force_refresh:
        If True, delete old ACLED raw/checkpoint files and re-download.
    use_existing:
        If True, use data/raw/acled_events.csv when it already exists.
    """

    ACLED_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)

    if force_refresh:
        remove_existing_acled_files()

    if use_existing and ACLED_RAW_FILE.exists() and not force_refresh:
        return load_existing_acled_file()

    if ACLED_CHECKPOINT_FILE.exists() and not force_refresh:
        print(
            f"Checkpoint file already exists at {ACLED_CHECKPOINT_FILE}. "
            "Finalizing from checkpoint instead of re-downloading."
        )
        return finalize_from_checkpoint()

    username, password = get_acled_credentials()

    print("Authenticating with ACLED...")
    access_token = request_acled_token(username=username, password=password)

    print("Downloading ACLED event data...")
    print(f"Configured year range: {START_YEAR} to {END_YEAR}")
    print(f"Configured event types: {', '.join(ACLED_EVENT_TYPES)}")

    page = 1
    total_rows_downloaded = 0

    while True:
        df = fetch_acled_page(access_token=access_token, page=page)

        if df.empty:
            print("No rows returned. Ending ACLED download.")
            break

        append_checkpoint(df)

        total_rows_downloaded += len(df)

        print(f"  Total rows checkpointed so far: {total_rows_downloaded:,}")

        if len(df) < ACLED_API_LIMIT:
            print("Final page reached.")
            break

        page += 1

        if max_pages is not None and page > max_pages:
            print(f"Reached max_pages={max_pages}. Stopping early.")
            break

        time.sleep(0.5)

    if not ACLED_CHECKPOINT_FILE.exists():
        raise RuntimeError("No ACLED events returned for the configured query.")

    events = finalize_from_checkpoint()

    return events


if __name__ == "__main__":
    fetch_acled_events()