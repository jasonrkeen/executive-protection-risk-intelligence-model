import numpy as np
import pandas as pd

from src.config import (
    ACLED_FORWARD_TRENDS_FILE,
    FORWARD_2026_RISK_FILE,
    FORWARD_2026_TOP_CHANGES_FILE,
    RISK_BUCKETS,
)


def assign_risk_bucket(score: float) -> str:
    """
    Assign score to a risk bucket using the project bucket settings.
    """

    for lower, upper, label in RISK_BUCKETS:
        if lower <= score < upper:
            return label

    return "Unclassified"


def bounded_adjustment(value: float, lower: float, upper: float) -> float:
    """
    Bound an adjustment value.
    """

    return max(lower, min(value, upper))


def get_baseline_anchor_floor(row: pd.Series) -> float:
    """
    Set the maximum negative adjustment based on baseline risk severity.

    High and Elevated countries should not ease too aggressively from one YTD
    momentum comparison. The model can show easing, but the forward estimate
    remains anchored to the structural 2024 baseline.
    """

    baseline_score = row.get("baseline_ep_risk_score_2024", 0)
    baseline_bucket = str(row.get("baseline_risk_bucket_2024", ""))

    if baseline_bucket in ["High", "Severe"] or baseline_score >= 70:
        return -6

    if baseline_bucket == "Elevated" or baseline_score >= 50:
        return -7

    return -10


def current_activity_is_low(row: pd.Series) -> bool:
    """
    Identify countries where current 2026 YTD ACLED activity is genuinely low.

    This is used as a diagnostic flag only. It does not override the baseline
    anchor for High or Elevated baseline countries.
    """

    events = row.get("2026_ytd_events", 0)
    fatalities = row.get("2026_ytd_fatalities", 0)
    violent_events = row.get("2026_ytd_violent_events", 0)

    return events <= 25 and fatalities <= 25 and violent_events <= 10


def apply_baseline_anchored_floor(row: pd.Series) -> float:
    """
    Apply a baseline-aware floor to the ACLED forward adjustment.

    The raw ACLED trend model can produce a -10 easing adjustment. This function
    keeps that possible for Moderate/Low baseline countries, but limits downside
    adjustment for High/Elevated baseline countries so that one partial-year
    comparison does not overstate improvement.
    """

    raw_adjustment = row.get("acled_forward_adjustment_raw", 0)
    raw_adjustment = bounded_adjustment(raw_adjustment, -10, 20)

    floor = get_baseline_anchor_floor(row)

    return round(max(raw_adjustment, floor), 2)


def detect_missing_2026_forward_data(df: pd.DataFrame) -> bool:
    """
    Detect whether the forward ACLED pull returned no 2026 YTD data.

    If every country has zero 2026 YTD events, or if the upstream forward
    trend file explicitly says target-year data is unavailable, the model
    should retain the baseline rather than treating missing data as easing.
    """

    if df.empty:
        return True

    if "target_year_data_status" in df.columns:
        status = df["target_year_data_status"].fillna("").astype(str)

        if status.str.contains(
            "Target-year ACLED data unavailable",
            case=False,
            regex=False,
        ).all():
            return True

    if "target_year_data_available" in df.columns:
        available = df["target_year_data_available"].fillna(False)

        if available.dtype == object:
            available = available.astype(str).str.lower().isin(["true", "1", "yes"])

        if available.sum() == 0:
            return True

    if "2026_ytd_events" not in df.columns:
        return True

    events = pd.to_numeric(df["2026_ytd_events"], errors="coerce").fillna(0)

    return events.sum() == 0


def apply_missing_forward_data_guard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep forward scores equal to baseline when 2026 ACLED data is unavailable.

    This prevents missing 2026 data from being misread as a broad improvement
    in the operating environment.
    """

    output = df.copy()

    output["acled_forward_adjustment"] = 0.0
    output["acled_forward_adjustment_raw"] = 0.0
    output["baseline_anchor_floor"] = 0.0
    output["current_activity_low_flag"] = True
    output["forward_adjustment_note"] = (
        "2026 ACLED data unavailable; baseline retained"
    )

    adjustment_columns = [
        "event_momentum_adjustment",
        "fatality_momentum_adjustment",
        "violent_event_momentum_adjustment",
        "civil_unrest_momentum_adjustment",
        "current_severity_adjustment",
    ]

    for column in adjustment_columns:
        output[column] = 0.0

    momentum_columns = [
        "event_momentum_2026_vs_2025_ytd",
        "fatality_momentum_2026_vs_2025_ytd",
        "violent_event_momentum_2026_vs_2025_ytd",
        "civil_unrest_momentum_2026_vs_2025_ytd",
    ]

    for column in momentum_columns:
        if column not in output.columns:
            output[column] = np.nan

    if "target_year_data_status" not in output.columns:
        output["target_year_data_status"] = "Target-year ACLED data unavailable"

    if "forward_fetch_status" not in output.columns:
        output["forward_fetch_status"] = "Target-year ACLED data unavailable"

    return output


def calculate_acled_trend_adjustment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate a 2026 forward adjustment from ACLED YTD trend signals.

    Adjustment ranges:
        event momentum:      -6 to +8
        fatality momentum:   -8 to +10
        violent momentum:    -5 to +7
        civil unrest trend:  -4 to +5
        current severity:     0 to +8

    Total raw ACLED adjustment is capped from -10 to +20. Then a baseline-aware
    floor prevents structurally High/Elevated countries from easing too sharply.
    """

    output = df.copy()

    numeric_columns = [
        "event_momentum_2026_vs_2025_ytd",
        "fatality_momentum_2026_vs_2025_ytd",
        "violent_event_momentum_2026_vs_2025_ytd",
        "civil_unrest_momentum_2026_vs_2025_ytd",
        "2026_ytd_events",
        "2026_ytd_fatalities",
        "2026_ytd_violent_events",
        "2026_ytd_high_fatality_events",
        "2026_ytd_unique_locations",
        "baseline_ep_risk_score_2024",
    ]

    for column in numeric_columns:
        if column not in output.columns:
            output[column] = 0

        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)

    output["event_momentum_adjustment"] = output[
        "event_momentum_2026_vs_2025_ytd"
    ].apply(lambda x: bounded_adjustment((x - 1) * 6, -6, 8))

    output["fatality_momentum_adjustment"] = output[
        "fatality_momentum_2026_vs_2025_ytd"
    ].apply(lambda x: bounded_adjustment((x - 1) * 6, -8, 10))

    output["violent_event_momentum_adjustment"] = output[
        "violent_event_momentum_2026_vs_2025_ytd"
    ].apply(lambda x: bounded_adjustment((x - 1) * 5, -5, 7))

    output["civil_unrest_momentum_adjustment"] = output[
        "civil_unrest_momentum_2026_vs_2025_ytd"
    ].apply(lambda x: bounded_adjustment((x - 1) * 4, -4, 5))

    output["current_event_percentile"] = output["2026_ytd_events"].rank(pct=True)
    output["current_fatality_percentile"] = output["2026_ytd_fatalities"].rank(
        pct=True
    )
    output["current_violent_event_percentile"] = output[
        "2026_ytd_violent_events"
    ].rank(pct=True)
    output["current_location_percentile"] = output[
        "2026_ytd_unique_locations"
    ].rank(pct=True)

    output["current_severity_adjustment"] = (
        output["current_event_percentile"] * 2
        + output["current_fatality_percentile"] * 3
        + output["current_violent_event_percentile"] * 2
        + output["current_location_percentile"] * 1
    ).round(2)

    output["current_severity_adjustment"] = output[
        "current_severity_adjustment"
    ].clip(lower=0, upper=8)

    output["acled_forward_adjustment_raw"] = (
        output["event_momentum_adjustment"]
        + output["fatality_momentum_adjustment"]
        + output["violent_event_momentum_adjustment"]
        + output["civil_unrest_momentum_adjustment"]
        + output["current_severity_adjustment"]
    )

    output["acled_forward_adjustment_raw"] = output[
        "acled_forward_adjustment_raw"
    ].clip(lower=-10, upper=20)

    output["baseline_anchor_floor"] = output.apply(
        get_baseline_anchor_floor,
        axis=1,
    )

    output["current_activity_low_flag"] = output.apply(
        current_activity_is_low,
        axis=1,
    )

    output["acled_forward_adjustment"] = output.apply(
        apply_baseline_anchored_floor,
        axis=1,
    )

    output["forward_adjustment_note"] = np.where(
        output["acled_forward_adjustment_raw"] < output["acled_forward_adjustment"],
        "Baseline anchor limited downside adjustment",
        "Raw ACLED trend adjustment applied",
    )

    if "target_year_data_status" not in output.columns:
        output["target_year_data_status"] = "Target-year ACLED data available"

    if "forward_fetch_status" not in output.columns:
        output["forward_fetch_status"] = "Target-year ACLED forward data returned"

    return output


def classify_forward_change(change: float) -> str:
    """
    Classify the 2026 forward score change.
    """

    if change >= 10:
        return "Rising materially"
    if change >= 5:
        return "Rising"
    if change <= -10:
        return "Easing materially"
    if change <= -5:
        return "Easing"
    return "Stable / mixed"


def run_forward_2026_risk_model() -> pd.DataFrame:
    """
    Build 2026 forward-adjusted EP risk scores.
    """

    print("Running 2026 forward risk model...")

    if not ACLED_FORWARD_TRENDS_FILE.exists():
        raise FileNotFoundError(
            f"ACLED forward trends file not found at {ACLED_FORWARD_TRENDS_FILE}. "
            "Run python -m src.acled_forecast_update first."
        )

    df = pd.read_csv(ACLED_FORWARD_TRENDS_FILE, low_memory=False)

    required_columns = {
        "country",
        "country_code",
        "baseline_ep_risk_score_2024",
        "baseline_risk_bucket_2024",
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(f"Forward trends file is missing required columns: {missing}")

    df["baseline_ep_risk_score_2024"] = pd.to_numeric(
        df["baseline_ep_risk_score_2024"], errors="coerce"
    ).fillna(0)

    no_2026_forward_data = detect_missing_2026_forward_data(df)

    if no_2026_forward_data:
        print(
            "Warning: 2026 ACLED YTD events are unavailable or zero for all "
            "forward countries. Keeping forward scores equal to the 2024 baseline."
        )
        df = apply_missing_forward_data_guard(df)
    else:
        df = calculate_acled_trend_adjustment(df)

    df["forward_2026_ep_risk_score"] = (
        df["baseline_ep_risk_score_2024"] + df["acled_forward_adjustment"]
    ).clip(lower=0, upper=100)

    df["forward_2026_ep_risk_score"] = df[
        "forward_2026_ep_risk_score"
    ].round(2)

    df["forward_score_change"] = (
        df["forward_2026_ep_risk_score"] - df["baseline_ep_risk_score_2024"]
    ).round(2)

    df["forward_risk_bucket_2026"] = df["forward_2026_ep_risk_score"].apply(
        assign_risk_bucket
    )

    df["forward_risk_change_flag"] = df["forward_score_change"].apply(
        classify_forward_change
    )

    output_columns = [
        "country",
        "country_code",
        "baseline_ep_risk_score_2024",
        "baseline_risk_bucket_2024",
        "forward_2026_ep_risk_score",
        "forward_risk_bucket_2026",
        "forward_score_change",
        "forward_risk_change_flag",
        "acled_forward_adjustment",
        "acled_forward_adjustment_raw",
        "baseline_anchor_floor",
        "current_activity_low_flag",
        "forward_adjustment_note",
        "target_year_data_status",
        "forward_fetch_status",
        "event_momentum_adjustment",
        "fatality_momentum_adjustment",
        "violent_event_momentum_adjustment",
        "civil_unrest_momentum_adjustment",
        "current_severity_adjustment",
        "event_momentum_2026_vs_2025_ytd",
        "fatality_momentum_2026_vs_2025_ytd",
        "violent_event_momentum_2026_vs_2025_ytd",
        "civil_unrest_momentum_2026_vs_2025_ytd",
        "2026_ytd_events",
        "2026_ytd_fatalities",
        "2026_ytd_violent_events",
        "2026_ytd_civil_unrest_events",
        "2025_ytd_same_period_events",
        "2025_ytd_same_period_fatalities",
        "2025_full_year_events",
        "2025_full_year_fatalities",
        "forward_update_window",
        "comparison_window",
    ]

    output_columns = [column for column in output_columns if column in df.columns]

    output = df[output_columns].sort_values(
        "forward_2026_ep_risk_score",
        ascending=False,
    )

    top_changes = output.sort_values(
        "forward_score_change",
        ascending=False,
    )

    FORWARD_2026_RISK_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(FORWARD_2026_RISK_FILE, index=False)
    top_changes.to_csv(FORWARD_2026_TOP_CHANGES_FILE, index=False)

    print(f"Forward 2026 risk scores saved to: {FORWARD_2026_RISK_FILE}")
    print(f"Forward 2026 top changes saved to: {FORWARD_2026_TOP_CHANGES_FILE}")
    print(f"Shape: {output.shape}")

    if not output.empty:
        print("\nTop 10 forward 2026 EP risk scores:")
        print(
            output[
                [
                    "country",
                    "baseline_ep_risk_score_2024",
                    "forward_2026_ep_risk_score",
                    "forward_score_change",
                    "forward_risk_bucket_2026",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

        print("\nForward risk change distribution:")
        print(output["forward_risk_change_flag"].value_counts().to_string())

        if "target_year_data_status" in output.columns:
            print("\nTarget-year data status:")
            print(output["target_year_data_status"].value_counts().to_string())

        if no_2026_forward_data:
            print(
                "\nForward data note: 2026 ACLED data was unavailable in the "
                "forward trends file, so forward scores were held equal to baseline."
            )

    return output


if __name__ == "__main__":
    run_forward_2026_risk_model()