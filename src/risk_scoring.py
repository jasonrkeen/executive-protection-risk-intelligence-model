import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from src.config import (
    MASTER_DATA_FILE,
    RISK_RANKINGS_FILE,
    RISK_WEIGHTS,
    RISK_BUCKETS,
)


def minmax_score(series: pd.Series, higher_is_risk: bool = True) -> pd.Series:
    """
    Convert a numeric series to a 0-100 score.
    """

    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)

    if values.notna().sum() == 0:
        return pd.Series(50, index=series.index)

    values = values.fillna(values.median())

    if values.nunique() <= 1:
        return pd.Series(50, index=series.index)

    scaler = MinMaxScaler(feature_range=(0, 100))
    scored = scaler.fit_transform(values.to_numpy().reshape(-1, 1)).ravel()

    if not higher_is_risk:
        scored = 100 - scored

    return pd.Series(scored, index=series.index)


def assign_risk_bucket(score: float) -> str:
    """
    Assign score to a risk bucket.
    """

    for lower, upper, label in RISK_BUCKETS:
        if lower <= score < upper:
            return label

    return "Unclassified"


def ensure_numeric_columns(
    df: pd.DataFrame,
    columns: list[str],
    default: float = 0,
) -> pd.DataFrame:
    """
    Ensure required columns exist and are numeric.
    """

    output = df.copy()

    for column in columns:
        if column not in output.columns:
            output[column] = default

        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(default)

    return output


def calculate_civil_unrest_political_violence_score(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a stronger civil unrest and political violence score.

    This score uses:
        - event volume
        - violent political events
        - fatalities
        - fatal event counts
        - high-fatality events
        - violence against civilians
        - riots
        - event shares
        - geographic spread
        - coordinate spread
        - high-relevance sub-event types
    """

    output = df.copy()

    required_columns = [
        "civil_unrest_events",
        "violent_political_events",
        "total_fatalities",
        "violence_against_civilians_events",
        "fatal_events",
        "high_fatality_events",
        "fatalities_per_event",
        "violent_event_share",
        "riot_share",
        "violence_against_civilians_share",
        "unique_admin1_locations",
        "unique_admin2_locations",
        "unique_event_locations",
        "unique_coordinate_pairs",
        "armed_clash_events",
        "attack_events",
        "remote_explosive_ied_events",
        "shelling_missile_attack_events",
        "excessive_force_against_protesters_events",
        "mob_violence_events",
    ]

    output = ensure_numeric_columns(output, required_columns, default=0)

    output["event_volume_raw"] = (
        output["civil_unrest_events"] * 0.35
        + output["violent_political_events"] * 0.40
        + output["violence_against_civilians_events"] * 0.25
    )

    output["fatality_intensity_raw"] = (
        output["total_fatalities"] * 0.40
        + output["fatal_events"] * 0.25
        + output["high_fatality_events"] * 0.25
        + output["fatalities_per_event"] * 0.10
    )

    output["event_composition_raw"] = (
        output["violent_event_share"] * 0.40
        + output["riot_share"] * 0.25
        + output["violence_against_civilians_share"] * 0.35
    )

    output["geographic_spread_raw"] = (
        output["unique_admin1_locations"] * 0.25
        + output["unique_admin2_locations"] * 0.25
        + output["unique_event_locations"] * 0.30
        + output["unique_coordinate_pairs"] * 0.20
    )

    output["high_relevance_sub_event_raw"] = (
        output["armed_clash_events"] * 0.20
        + output["attack_events"] * 0.20
        + output["remote_explosive_ied_events"] * 0.20
        + output["shelling_missile_attack_events"] * 0.15
        + output["excessive_force_against_protesters_events"] * 0.15
        + output["mob_violence_events"] * 0.10
    )

    output["event_volume_score"] = minmax_score(output["event_volume_raw"])
    output["fatality_intensity_score"] = minmax_score(output["fatality_intensity_raw"])
    output["event_composition_score"] = minmax_score(output["event_composition_raw"])
    output["geographic_spread_score"] = minmax_score(output["geographic_spread_raw"])
    output["high_relevance_sub_event_score"] = minmax_score(
        output["high_relevance_sub_event_raw"]
    )

    output["civil_unrest_political_violence_score"] = (
        output["event_volume_score"] * 0.35
        + output["fatality_intensity_score"] * 0.25
        + output["event_composition_score"] * 0.15
        + output["geographic_spread_score"] * 0.15
        + output["high_relevance_sub_event_score"] * 0.10
    ).round(2)

    return output


def calculate_governance_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate governance risk from World Bank WGI indicators.

    WGI indicators are generally better when higher, so the final risk score
    is inverted after calculating governance strength.
    """

    output = df.copy()

    governance_columns = [
        "political_stability",
        "rule_of_law",
        "control_of_corruption",
        "government_effectiveness",
    ]

    for column in governance_columns:
        if column not in output.columns:
            output[column] = np.nan

        output[column] = pd.to_numeric(output[column], errors="coerce")

    output["governance_strength_raw"] = output[governance_columns].mean(axis=1)

    output["governance_risk_score"] = minmax_score(
        output["governance_strength_raw"],
        higher_is_risk=False,
    ).round(2)

    return output


def calculate_crime_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate violent-crime proxy score from homicide rate.

    Median-filled values are still scored, but the associated quality flags are
    retained in the output so the report can distinguish direct/older homicide
    values from model-filled values.
    """

    output = df.copy()

    if "homicide_rate_per_100k" not in output.columns:
        output["homicide_rate_per_100k"] = np.nan

    output["homicide_rate_per_100k"] = pd.to_numeric(
        output["homicide_rate_per_100k"], errors="coerce"
    )

    if output["homicide_rate_per_100k"].notna().sum() > 0:
        output["homicide_rate_per_100k"] = output["homicide_rate_per_100k"].fillna(
            output["homicide_rate_per_100k"].median()
        )
    else:
        output["homicide_rate_per_100k"] = 0

    output["violent_crime_score"] = minmax_score(
        output["homicide_rate_per_100k"],
        higher_is_risk=True,
    ).round(2)

    return output


def calculate_energy_exposure_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate energy-sector exposure score.

    Uses the raw World Bank-derived energy exposure measure plus optional
    hydrocarbon and fuel export contribution fields.
    """

    output = df.copy()

    required_columns = [
        "energy_exposure_raw",
        "energy_rents_pct_gdp",
        "fuel_exports_pct_merchandise_exports",
        "hydrocarbon_rent_share_of_energy_exposure",
        "fuel_export_share_of_energy_exposure",
    ]

    output = ensure_numeric_columns(output, required_columns, default=0)

    output["energy_exposure_enhanced_raw"] = (
        output["energy_exposure_raw"] * 0.70
        + output["energy_rents_pct_gdp"] * 0.15
        + output["fuel_exports_pct_merchandise_exports"] * 0.15
    )

    output["energy_exposure_score"] = minmax_score(
        output["energy_exposure_enhanced_raw"],
        higher_is_risk=True,
    ).round(2)

    return output


def calculate_recent_momentum_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate recent risk momentum using event and fatality momentum.
    """

    output = df.copy()

    required_columns = [
        "recent_event_momentum",
        "recent_fatality_momentum",
        "three_year_avg_events",
        "three_year_avg_fatalities",
    ]

    output = ensure_numeric_columns(output, required_columns, default=1)

    output["recent_risk_momentum_raw"] = (
        output["recent_event_momentum"] * 0.60
        + output["recent_fatality_momentum"] * 0.40
    )

    output["recent_risk_momentum_score"] = minmax_score(
        output["recent_risk_momentum_raw"],
        higher_is_risk=True,
    ).round(2)

    return output


def calculate_weighted_baseline_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the initial weighted composite score before severity calibration.
    """

    output = df.copy()

    output["weighted_ep_risk_score"] = 0.0

    for score_column, weight in RISK_WEIGHTS.items():
        if score_column not in output.columns:
            output[score_column] = 0

        output[score_column] = pd.to_numeric(
            output[score_column], errors="coerce"
        ).fillna(0)

        output["weighted_ep_risk_score"] += output[score_column] * weight

    output["weighted_ep_risk_score"] = output["weighted_ep_risk_score"].round(2)

    return output


def calculate_severity_uplift(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a calibrated severity uplift to avoid compressing extreme-risk countries.

    The baseline weighted score is useful for relative ranking, but min-max
    component scoring can compress operationally severe environments into a
    Moderate bucket.
    """

    output = df.copy()

    required_columns = [
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
        "total_acled_events",
        "total_fatalities",
        "violent_political_events",
        "fatal_events",
        "high_fatality_events",
        "unique_event_locations",
        "unique_coordinate_pairs",
        "recent_event_momentum",
        "recent_fatality_momentum",
    ]

    output = ensure_numeric_columns(output, required_columns, default=0)

    output["acled_event_percentile"] = output["total_acled_events"].rank(pct=True)
    output["fatality_percentile"] = output["total_fatalities"].rank(pct=True)
    output["violent_event_percentile"] = output["violent_political_events"].rank(pct=True)
    output["fatal_event_percentile"] = output["fatal_events"].rank(pct=True)
    output["high_fatality_event_percentile"] = output["high_fatality_events"].rank(
        pct=True
    )
    output["location_spread_percentile"] = output["unique_event_locations"].rank(
        pct=True
    )
    output["coordinate_spread_percentile"] = output["unique_coordinate_pairs"].rank(
        pct=True
    )

    output["extreme_conflict_uplift"] = 0.0

    extreme_conflict_mask = (
        (output["civil_unrest_political_violence_score"] >= 70)
        | (
            (output["acled_event_percentile"] >= 0.98)
            & (output["fatality_percentile"] >= 0.95)
        )
        | (
            (output["violent_event_percentile"] >= 0.98)
            & (output["fatal_event_percentile"] >= 0.95)
        )
    )

    high_conflict_mask = (
        ~extreme_conflict_mask
        & (
            (output["civil_unrest_political_violence_score"] >= 50)
            | (
                (output["acled_event_percentile"] >= 0.95)
                & (output["fatality_percentile"] >= 0.90)
            )
        )
    )

    output.loc[extreme_conflict_mask, "extreme_conflict_uplift"] = 18
    output.loc[high_conflict_mask, "extreme_conflict_uplift"] = 10

    output["fatality_severity_uplift"] = 0.0

    output.loc[
        output["high_fatality_event_percentile"] >= 0.98,
        "fatality_severity_uplift",
    ] = 8

    output.loc[
        (output["high_fatality_event_percentile"] >= 0.95)
        & (output["high_fatality_event_percentile"] < 0.98),
        "fatality_severity_uplift",
    ] = 5

    output["geographic_spread_uplift"] = 0.0

    broad_spread_mask = (
        (output["location_spread_percentile"] >= 0.98)
        | (output["coordinate_spread_percentile"] >= 0.98)
    )

    moderate_spread_mask = (
        ~broad_spread_mask
        & (
            (output["location_spread_percentile"] >= 0.95)
            | (output["coordinate_spread_percentile"] >= 0.95)
        )
    )

    output.loc[broad_spread_mask, "geographic_spread_uplift"] = 6
    output.loc[moderate_spread_mask, "geographic_spread_uplift"] = 3

    output["compound_governance_violence_uplift"] = 0.0

    output.loc[
        (output["governance_risk_score"] >= 75)
        & (output["civil_unrest_political_violence_score"] >= 30),
        "compound_governance_violence_uplift",
    ] = 8

    output.loc[
        (output["governance_risk_score"] >= 65)
        & (output["civil_unrest_political_violence_score"] >= 20)
        & (output["compound_governance_violence_uplift"] == 0),
        "compound_governance_violence_uplift",
    ] = 5

    output["strategic_energy_instability_uplift"] = 0.0

    output.loc[
        (output["energy_exposure_score"] >= 80)
        & (
            (output["governance_risk_score"] >= 60)
            | (output["civil_unrest_political_violence_score"] >= 10)
        ),
        "strategic_energy_instability_uplift",
    ] = 8

    output.loc[
        (output["energy_exposure_score"] >= 60)
        & (output["governance_risk_score"] >= 60)
        & (output["strategic_energy_instability_uplift"] == 0),
        "strategic_energy_instability_uplift",
    ] = 5

    output["momentum_uplift"] = 0.0

    output.loc[
        (output["recent_risk_momentum_score"] >= 80)
        | (output["recent_fatality_momentum"] >= 1.50),
        "momentum_uplift",
    ] = 5

    output.loc[
        (
            (output["recent_risk_momentum_score"] >= 60)
            | (output["recent_event_momentum"] >= 1.25)
        )
        & (output["momentum_uplift"] == 0),
        "momentum_uplift",
    ] = 3

    output["severity_uplift_total_raw"] = (
        output["extreme_conflict_uplift"]
        + output["fatality_severity_uplift"]
        + output["geographic_spread_uplift"]
        + output["compound_governance_violence_uplift"]
        + output["strategic_energy_instability_uplift"]
        + output["momentum_uplift"]
    )

    output["severity_uplift_total"] = output["severity_uplift_total_raw"].clip(
        lower=0,
        upper=25,
    )

    output["calibration_note"] = np.where(
        output["severity_uplift_total"] > 0,
        "Severity calibration applied",
        "No severity calibration uplift",
    )

    return output


def calculate_composite_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate final Executive Protection Risk Score.

    Final score =
        weighted component score + bounded severity calibration uplift
    """

    output = df.copy()

    output = calculate_weighted_baseline_score(output)
    output = calculate_severity_uplift(output)

    output["executive_protection_risk_score"] = (
        output["weighted_ep_risk_score"] + output["severity_uplift_total"]
    ).clip(lower=0, upper=100)

    output["executive_protection_risk_score"] = output[
        "executive_protection_risk_score"
    ].round(2)

    output["risk_bucket"] = output["executive_protection_risk_score"].apply(
        assign_risk_bucket
    )

    return output


def build_output_columns(df: pd.DataFrame) -> list[str]:
    """
    Build output column list while keeping only columns present in the dataframe.
    """

    desired_columns = [
        "country",
        "country_code",
        "year",
        "executive_protection_risk_score",
        "weighted_ep_risk_score",
        "severity_uplift_total",
        "severity_uplift_total_raw",
        "risk_bucket",
        "calibration_note",

        # Component scores
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",

        # Severity uplift components
        "extreme_conflict_uplift",
        "fatality_severity_uplift",
        "geographic_spread_uplift",
        "compound_governance_violence_uplift",
        "strategic_energy_instability_uplift",
        "momentum_uplift",

        # Percentile diagnostics
        "acled_event_percentile",
        "fatality_percentile",
        "violent_event_percentile",
        "fatal_event_percentile",
        "high_fatality_event_percentile",
        "location_spread_percentile",
        "coordinate_spread_percentile",

        # Component raw scores
        "event_volume_score",
        "fatality_intensity_score",
        "event_composition_score",
        "geographic_spread_score",
        "high_relevance_sub_event_score",
        "governance_strength_raw",
        "energy_exposure_enhanced_raw",
        "recent_risk_momentum_raw",

        # Core ACLED indicators
        "total_acled_events",
        "civil_unrest_events",
        "violent_political_events",
        "total_fatalities",
        "fatal_events",
        "high_fatality_events",
        "fatalities_per_event",
        "riot_events",
        "violence_against_civilians_events",
        "violent_event_share",
        "riot_share",
        "violence_against_civilians_share",
        "unique_admin1_locations",
        "unique_admin2_locations",
        "unique_event_locations",
        "unique_coordinate_pairs",
        "recent_event_momentum",
        "recent_fatality_momentum",

        # Crime / energy
        "homicide_rate_per_100k",
        "homicide_rate_per_100k_year",
        "energy_exposure_raw",
        "energy_rents_pct_gdp",
        "oil_rents_pct_gdp",
        "natural_gas_rents_pct_gdp",
        "fuel_exports_pct_merchandise_exports",
        "hydrocarbon_rent_share_of_energy_exposure",
        "fuel_export_share_of_energy_exposure",

        # Governance
        "political_stability",
        "rule_of_law",
        "control_of_corruption",
        "government_effectiveness",

        # Data quality
        "has_acled_data",
        "has_homicide_data",
        "has_energy_exposure_data",
        "data_coverage_score",
        "data_coverage_flag",
        "acled_data_source",
        "crime_data_source",
        "crime_data_quality_flag",
        "crime_data_available",
        "energy_data_coverage_flag",
        "energy_data_quality_flag",
        "worldbank_coverage_share",
        "worldbank_coverage_flag",
    ]

    return [column for column in desired_columns if column in df.columns]


def calculate_risk_scores() -> pd.DataFrame:
    """
    Calculate the Executive Protection Risk Score.
    """

    print("Calculating executive protection risk scores...")

    if not MASTER_DATA_FILE.exists():
        raise FileNotFoundError(
            f"Master dataset not found at {MASTER_DATA_FILE}. "
            "Run python -m src.data_processing first."
        )

    df = pd.read_csv(MASTER_DATA_FILE, low_memory=False)

    df = calculate_civil_unrest_political_violence_score(df)
    df = calculate_governance_risk_score(df)
    df = calculate_crime_risk_score(df)
    df = calculate_energy_exposure_score(df)
    df = calculate_recent_momentum_score(df)
    df = calculate_composite_score(df)

    output_columns = build_output_columns(df)

    rankings = df[output_columns].sort_values(
        "executive_protection_risk_score",
        ascending=False,
    )

    RISK_RANKINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    rankings.to_csv(RISK_RANKINGS_FILE, index=False)

    print(f"Risk rankings saved to: {RISK_RANKINGS_FILE}")
    print(f"Shape: {rankings.shape}")

    if not rankings.empty:
        print("\nTop 10 countries by Executive Protection Risk Score:")
        print(
            rankings[
                [
                    "country",
                    "executive_protection_risk_score",
                    "weighted_ep_risk_score",
                    "severity_uplift_total",
                    "risk_bucket",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

        print("\nRisk bucket distribution:")
        print(rankings["risk_bucket"].value_counts().to_string())

    return rankings


if __name__ == "__main__":
    calculate_risk_scores()