from pathlib import Path

import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    RISK_RANKINGS_SNAPSHOT_FILE,
    RISK_SCORE_CHANGES_FILE,
    RISK_BUCKET_CHANGES_FILE,
    TOP_RANK_MOVERS_FILE,
)


def load_rankings(path: Path) -> pd.DataFrame:
    """
    Load a risk rankings file.
    """

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, low_memory=False)


def prepare_rankings(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """
    Prepare rankings for comparison.
    """

    if df.empty:
        return df

    output = df.copy()

    required_columns = {
        "country",
        "country_code",
        "executive_protection_risk_score",
        "risk_bucket",
    }

    missing = required_columns.difference(output.columns)

    if missing:
        raise ValueError(f"Risk rankings file is missing required columns: {missing}")

    output["executive_protection_risk_score"] = pd.to_numeric(
        output["executive_protection_risk_score"],
        errors="coerce",
    )

    output = output.sort_values(
        "executive_protection_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    output[f"rank_{suffix}"] = output.index + 1

    keep_columns = [
        "country",
        "country_code",
        "executive_protection_risk_score",
        "risk_bucket",
        f"rank_{suffix}",
    ]

    optional_columns = [
        "weighted_ep_risk_score",
        "severity_uplift_total",
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
        "total_acled_events",
        "total_fatalities",
        "data_coverage_flag",
    ]

    keep_columns += [column for column in optional_columns if column in output.columns]

    output = output[keep_columns].copy()

    rename_map = {
        column: f"{column}_{suffix}"
        for column in output.columns
        if column not in ["country", "country_code", f"rank_{suffix}"]
    }

    output = output.rename(columns=rename_map)

    return output


def classify_score_change(change: float) -> str:
    """
    Classify score movement.
    """

    if pd.isna(change):
        return "New / missing comparison"
    if change >= 10:
        return "Risk rising materially"
    if change >= 5:
        return "Risk rising"
    if change <= -10:
        return "Risk easing materially"
    if change <= -5:
        return "Risk easing"
    return "Stable / mixed"


def classify_rank_change(change: float) -> str:
    """
    Classify rank movement.

    Positive rank change means the country moved higher in the rankings.
    """

    if pd.isna(change):
        return "New / missing comparison"
    if change >= 10:
        return "Moved up materially"
    if change >= 5:
        return "Moved up"
    if change <= -10:
        return "Moved down materially"
    if change <= -5:
        return "Moved down"
    return "Stable / mixed"


def build_change_tables(current: pd.DataFrame, previous: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build score changes, bucket changes, and top rank movers.
    """

    current_prepared = prepare_rankings(current, "current")
    previous_prepared = prepare_rankings(previous, "previous")

    comparison = current_prepared.merge(
        previous_prepared,
        on="country_code",
        how="outer",
        suffixes=("", "_previous_join"),
    )

    if "country" not in comparison.columns and "country_current" in comparison.columns:
        comparison["country"] = comparison["country_current"]

    if "country_current" in comparison.columns:
        comparison["country"] = comparison["country_current"].combine_first(
            comparison.get("country_previous")
        )

    comparison["score_change"] = (
        comparison["executive_protection_risk_score_current"]
        - comparison["executive_protection_risk_score_previous"]
    ).round(2)

    comparison["rank_change"] = (
        comparison["rank_previous"] - comparison["rank_current"]
    )

    comparison["score_change_flag"] = comparison["score_change"].apply(
        classify_score_change
    )

    comparison["rank_change_flag"] = comparison["rank_change"].apply(
        classify_rank_change
    )

    comparison["bucket_changed"] = (
        comparison["risk_bucket_current"] != comparison["risk_bucket_previous"]
    )

    comparison["bucket_change"] = (
        comparison["risk_bucket_previous"].fillna("N/A")
        + " -> "
        + comparison["risk_bucket_current"].fillna("N/A")
    )

    base_columns = [
        "country",
        "country_code",
        "rank_previous",
        "rank_current",
        "rank_change",
        "rank_change_flag",
        "executive_protection_risk_score_previous",
        "executive_protection_risk_score_current",
        "score_change",
        "score_change_flag",
        "risk_bucket_previous",
        "risk_bucket_current",
        "bucket_change",
        "bucket_changed",
    ]

    optional_columns = [
        "weighted_ep_risk_score_previous",
        "weighted_ep_risk_score_current",
        "severity_uplift_total_previous",
        "severity_uplift_total_current",
        "civil_unrest_political_violence_score_previous",
        "civil_unrest_political_violence_score_current",
        "governance_risk_score_previous",
        "governance_risk_score_current",
        "violent_crime_score_previous",
        "violent_crime_score_current",
        "energy_exposure_score_previous",
        "energy_exposure_score_current",
        "recent_risk_momentum_score_previous",
        "recent_risk_momentum_score_current",
        "total_acled_events_previous",
        "total_acled_events_current",
        "total_fatalities_previous",
        "total_fatalities_current",
        "data_coverage_flag_previous",
        "data_coverage_flag_current",
    ]

    output_columns = base_columns + [
        column for column in optional_columns if column in comparison.columns
    ]

    score_changes = comparison[output_columns].copy()

    score_changes = score_changes.sort_values(
        ["score_change", "rank_change"],
        ascending=[False, False],
    ).reset_index(drop=True)

    bucket_changes = score_changes[score_changes["bucket_changed"] == True].copy()

    top_rank_movers = score_changes.copy()
    top_rank_movers["absolute_rank_change"] = top_rank_movers["rank_change"].abs()
    top_rank_movers = top_rank_movers.sort_values(
        ["absolute_rank_change", "score_change"],
        ascending=[False, False],
    ).head(25)

    return score_changes, bucket_changes, top_rank_movers


def save_current_snapshot(current: pd.DataFrame) -> None:
    """
    Save the current rankings as the next run's previous snapshot.
    """

    RISK_RANKINGS_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    current.to_csv(RISK_RANKINGS_SNAPSHOT_FILE, index=False)


def run_change_detection(update_snapshot: bool = True) -> pd.DataFrame:
    """
    Compare current risk rankings against the previous saved snapshot.

    If no previous snapshot exists, the function creates one and exits cleanly.
    """

    print("Running run-to-run change detection...")

    current = load_rankings(RISK_RANKINGS_FILE)

    if current.empty:
        raise FileNotFoundError(
            f"Current risk rankings not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    previous = load_rankings(RISK_RANKINGS_SNAPSHOT_FILE)

    if previous.empty:
        print(
            "No previous risk ranking snapshot found. "
            "Creating initial snapshot for future comparisons."
        )
        save_current_snapshot(current)

        empty = pd.DataFrame()
        empty.to_csv(RISK_SCORE_CHANGES_FILE, index=False)
        empty.to_csv(RISK_BUCKET_CHANGES_FILE, index=False)
        empty.to_csv(TOP_RANK_MOVERS_FILE, index=False)

        return empty

    score_changes, bucket_changes, top_rank_movers = build_change_tables(
        current=current,
        previous=previous,
    )

    RISK_SCORE_CHANGES_FILE.parent.mkdir(parents=True, exist_ok=True)

    score_changes.to_csv(RISK_SCORE_CHANGES_FILE, index=False)
    bucket_changes.to_csv(RISK_BUCKET_CHANGES_FILE, index=False)
    top_rank_movers.to_csv(TOP_RANK_MOVERS_FILE, index=False)

    print(f"Risk score changes saved to: {RISK_SCORE_CHANGES_FILE}")
    print(f"Risk bucket changes saved to: {RISK_BUCKET_CHANGES_FILE}")
    print(f"Top rank movers saved to: {TOP_RANK_MOVERS_FILE}")

    print(f"Countries compared: {len(score_changes)}")
    print(f"Bucket changes: {len(bucket_changes)}")

    if not top_rank_movers.empty:
        print("\nTop rank movers:")
        print(
            top_rank_movers[
                [
                    "country",
                    "rank_previous",
                    "rank_current",
                    "rank_change",
                    "score_change",
                    "rank_change_flag",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

    if update_snapshot:
        save_current_snapshot(current)
        print(f"Updated ranking snapshot: {RISK_RANKINGS_SNAPSHOT_FILE}")

    return score_changes


if __name__ == "__main__":
    run_change_detection()