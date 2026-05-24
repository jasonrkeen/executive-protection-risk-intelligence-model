import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    SENSITIVITY_RANKINGS_FILE,
    SENSITIVITY_TOP20_FILE,
    SENSITIVITY_OVERLAP_FILE,
    SENSITIVITY_SUMMARY_FILE,
    SENSITIVITY_OVERLAP_CHART,
    SENSITIVITY_SCENARIOS,
)


def validate_weights() -> None:
    """
    Confirm each sensitivity scenario sums to 1.0.
    """

    for scenario, weights in SENSITIVITY_SCENARIOS.items():
        total_weight = round(sum(weights.values()), 6)

        if total_weight != 1.0:
            raise ValueError(
                f"Weight scenario '{scenario}' sums to {total_weight}, not 1.0."
            )


def load_rankings() -> pd.DataFrame:
    """
    Load baseline risk rankings.
    """

    if not RISK_RANKINGS_FILE.exists():
        raise FileNotFoundError(
            f"Risk rankings file not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    df = pd.read_csv(RISK_RANKINGS_FILE, low_memory=False)

    required_columns = {
        "country",
        "country_code",
        "risk_bucket",
        "executive_protection_risk_score",
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(
            f"Risk rankings file is missing required sensitivity columns: {missing}"
        )

    score_columns = [
        "executive_protection_risk_score",
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
    ]

    for column in score_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df = df.sort_values(
        "executive_protection_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    df["baseline_rank"] = df.index + 1

    return df


def calculate_sensitivity_rankings(rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Recalculate country rankings under alternative weighting scenarios.
    """

    rows = []

    baseline_lookup = rankings[
        [
            "country_code",
            "baseline_rank",
            "executive_protection_risk_score",
            "weighted_ep_risk_score",
            "severity_uplift_total",
            "risk_bucket",
        ]
    ].copy()

    baseline_lookup = baseline_lookup.rename(
        columns={
            "executive_protection_risk_score": "baseline_ep_risk_score",
            "weighted_ep_risk_score": "baseline_weighted_ep_risk_score",
            "severity_uplift_total": "baseline_severity_uplift_total",
            "risk_bucket": "baseline_risk_bucket",
        }
    )

    for scenario, weights in SENSITIVITY_SCENARIOS.items():
        scenario_df = rankings.copy()

        scenario_df["sensitivity_score"] = 0.0

        for score_column, weight in weights.items():
            if score_column not in scenario_df.columns:
                raise ValueError(
                    f"Scenario '{scenario}' references missing score column: "
                    f"{score_column}"
                )

            scenario_df[score_column] = pd.to_numeric(
                scenario_df[score_column],
                errors="coerce",
            ).fillna(0)

            scenario_df["sensitivity_score"] += scenario_df[score_column] * weight

        scenario_df["sensitivity_score"] = scenario_df["sensitivity_score"].round(2)

        scenario_df = scenario_df.sort_values(
            "sensitivity_score",
            ascending=False,
        ).reset_index(drop=True)

        scenario_df["sensitivity_rank"] = scenario_df.index + 1
        scenario_df["sensitivity_scenario"] = scenario

        scenario_df = scenario_df.merge(
            baseline_lookup,
            on="country_code",
            how="left",
            suffixes=("", "_baseline"),
        )

        scenario_df["rank_change_vs_baseline"] = (
            scenario_df["baseline_rank"] - scenario_df["sensitivity_rank"]
        )

        scenario_df["score_change_vs_baseline"] = (
            scenario_df["sensitivity_score"] - scenario_df["baseline_ep_risk_score"]
        ).round(2)

        keep_columns = [
            "sensitivity_scenario",
            "sensitivity_rank",
            "baseline_rank",
            "rank_change_vs_baseline",
            "country",
            "country_code",
            "sensitivity_score",
            "baseline_ep_risk_score",
            "baseline_weighted_ep_risk_score",
            "baseline_severity_uplift_total",
            "score_change_vs_baseline",
            "baseline_risk_bucket",
            "civil_unrest_political_violence_score",
            "governance_risk_score",
            "violent_crime_score",
            "energy_exposure_score",
            "recent_risk_momentum_score",
        ]

        optional_columns = [
            "weighted_ep_risk_score",
            "severity_uplift_total",
            "severity_uplift_total_raw",
            "calibration_note",
            "total_acled_events",
            "total_fatalities",
            "violent_political_events",
            "civil_unrest_events",
            "fatal_events",
            "high_fatality_events",
            "unique_event_locations",
            "unique_coordinate_pairs",
            "homicide_rate_per_100k",
            "homicide_rate_per_100k_year",
            "energy_exposure_raw",
            "energy_rents_pct_gdp",
            "data_coverage_flag",
            "crime_data_quality_flag",
            "energy_data_quality_flag",
        ]

        for column in optional_columns:
            if column in scenario_df.columns and column not in keep_columns:
                keep_columns.append(column)

        rows.append(scenario_df[keep_columns])

    output = pd.concat(rows, ignore_index=True)

    return output


def build_top20_by_scenario(sensitivity_rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Create a table containing the top 20 countries under each scenario.
    """

    top20 = sensitivity_rankings[
        sensitivity_rankings["sensitivity_rank"] <= 20
    ].copy()

    top20 = top20.sort_values(
        ["sensitivity_scenario", "sensitivity_rank"]
    ).reset_index(drop=True)

    return top20


def classify_ranking_stability(
    top20_scenario_share: float,
    rank_range: float,
) -> str:
    """
    Classify how stable a country's top-20 ranking is across scenarios.
    """

    if top20_scenario_share == 1 and rank_range <= 5:
        return "Highly Stable"
    if top20_scenario_share >= 0.75:
        return "Stable"
    if top20_scenario_share >= 0.50:
        return "Moderately Sensitive"
    return "Highly Sensitive"


def build_top20_overlap(sensitivity_rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Count how often each country appears in the top 20 across sensitivity scenarios.
    """

    top20 = sensitivity_rankings[
        sensitivity_rankings["sensitivity_rank"] <= 20
    ].copy()

    scenario_count = len(SENSITIVITY_SCENARIOS)

    overlap = (
        top20.groupby(["country", "country_code"], as_index=False)
        .agg(
            top20_scenario_count=("sensitivity_scenario", "nunique"),
            best_sensitivity_rank=("sensitivity_rank", "min"),
            worst_sensitivity_rank=("sensitivity_rank", "max"),
            average_sensitivity_rank=("sensitivity_rank", "mean"),
            average_sensitivity_score=("sensitivity_score", "mean"),
            max_score_change_vs_baseline=("score_change_vs_baseline", "max"),
            min_score_change_vs_baseline=("score_change_vs_baseline", "min"),
        )
        .reset_index(drop=True)
    )

    overlap["top20_scenario_share"] = (
        overlap["top20_scenario_count"] / scenario_count
    ).round(4)

    overlap["rank_range"] = (
        overlap["worst_sensitivity_rank"] - overlap["best_sensitivity_rank"]
    )

    overlap["average_sensitivity_rank"] = overlap[
        "average_sensitivity_rank"
    ].round(2)

    overlap["average_sensitivity_score"] = overlap[
        "average_sensitivity_score"
    ].round(2)

    overlap["max_score_change_vs_baseline"] = overlap[
        "max_score_change_vs_baseline"
    ].round(2)

    overlap["min_score_change_vs_baseline"] = overlap[
        "min_score_change_vs_baseline"
    ].round(2)

    overlap["ranking_stability_flag"] = overlap.apply(
        lambda row: classify_ranking_stability(
            row["top20_scenario_share"],
            row["rank_range"],
        ),
        axis=1,
    )

    overlap = overlap.sort_values(
        [
            "top20_scenario_count",
            "best_sensitivity_rank",
            "rank_range",
        ],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    return overlap


def build_scenario_level_summary(sensitivity_rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize score and rank effects by sensitivity scenario.
    """

    rows = []

    for scenario, scenario_df in sensitivity_rankings.groupby("sensitivity_scenario"):
        top20 = scenario_df[scenario_df["sensitivity_rank"] <= 20].copy()

        rows.append(
            {
                "sensitivity_scenario": scenario,
                "country_count": len(scenario_df),
                "top20_country_count": len(top20),
                "average_sensitivity_score": round(
                    scenario_df["sensitivity_score"].mean(), 2
                ),
                "median_sensitivity_score": round(
                    scenario_df["sensitivity_score"].median(), 2
                ),
                "max_sensitivity_score": round(
                    scenario_df["sensitivity_score"].max(), 2
                ),
                "average_absolute_rank_change": round(
                    scenario_df["rank_change_vs_baseline"].abs().mean(), 2
                ),
                "max_rank_gain_vs_baseline": int(
                    scenario_df["rank_change_vs_baseline"].max()
                ),
                "max_rank_loss_vs_baseline": int(
                    scenario_df["rank_change_vs_baseline"].min()
                ),
                "average_score_change_vs_baseline": round(
                    scenario_df["score_change_vs_baseline"].mean(), 2
                ),
                "top20_average_score": round(top20["sensitivity_score"].mean(), 2),
            }
        )

    output = pd.DataFrame(rows).sort_values(
        "average_absolute_rank_change",
        ascending=False,
    )

    return output


def build_sensitivity_summary(
    sensitivity_rankings: pd.DataFrame,
    overlap: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize the stability of sensitivity results.
    """

    scenario_count = len(SENSITIVITY_SCENARIOS)

    always_top20 = overlap[
        overlap["top20_scenario_count"] == scenario_count
    ].shape[0]

    majority_threshold = max(1, round(scenario_count * 0.5))

    majority_top20 = overlap[
        overlap["top20_scenario_count"] >= majority_threshold
    ].shape[0]

    highly_stable = overlap[
        overlap["ranking_stability_flag"] == "Highly Stable"
    ].shape[0]

    stable_or_better = overlap[
        overlap["ranking_stability_flag"].isin(["Highly Stable", "Stable"])
    ].shape[0]

    unique_top20_countries = overlap.shape[0]

    baseline_top20 = sensitivity_rankings[
        (sensitivity_rankings["sensitivity_scenario"] == "baseline")
        & (sensitivity_rankings["sensitivity_rank"] <= 20)
    ]["country_code"].nunique()

    average_unique_turnover = unique_top20_countries - baseline_top20

    scenario_level_summary = build_scenario_level_summary(sensitivity_rankings)

    most_sensitive_scenario = ""
    highest_avg_rank_change = 0

    if not scenario_level_summary.empty:
        most_sensitive = scenario_level_summary.iloc[0]
        most_sensitive_scenario = most_sensitive["sensitivity_scenario"]
        highest_avg_rank_change = most_sensitive["average_absolute_rank_change"]

    if always_top20 >= 15:
        stability_interpretation = (
            "The top-risk group is highly robust across weighting assumptions."
        )
    elif always_top20 >= 10:
        stability_interpretation = (
            "The top-risk group is broadly stable, with some countries sensitive "
            "to weighting assumptions."
        )
    else:
        stability_interpretation = (
            "The top-risk group is meaningfully sensitive to weighting assumptions; "
            "interpret exact ranks with caution."
        )

    summary = pd.DataFrame(
        [
            {
                "scenario_count": scenario_count,
                "baseline_top20_country_count": baseline_top20,
                "unique_countries_appearing_in_any_top20": unique_top20_countries,
                "average_unique_turnover_vs_baseline_top20": average_unique_turnover,
                "countries_top20_in_all_scenarios": always_top20,
                "countries_top20_in_majority_of_scenarios": majority_top20,
                "highly_stable_top20_countries": highly_stable,
                "stable_or_highly_stable_top20_countries": stable_or_better,
                "most_sensitive_weighting_scenario": most_sensitive_scenario,
                "highest_average_absolute_rank_change": highest_avg_rank_change,
                "stability_interpretation": stability_interpretation,
                "method_note": (
                    "Sensitivity analysis recalculates country rankings under "
                    "alternative weighting assumptions. Higher overlap indicates "
                    "that top-risk countries are stable across model assumptions."
                ),
            }
        ]
    )

    return summary


def save_sensitivity_overlap_chart(overlap: pd.DataFrame, top_n: int = 25):
    """
    Save a bar chart showing top-20 scenario overlap.
    """

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed. Skipping sensitivity overlap chart.")
        return None

    if overlap.empty:
        print("Sensitivity overlap table is empty. Skipping chart.")
        return None

    chart_df = overlap.head(top_n).copy()

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["top20_scenario_count"])
    ax.invert_yaxis()
    ax.set_title("Sensitivity Analysis: Top-20 Ranking Stability")
    ax.set_xlabel("Number of Scenarios Where Country Appears in Top 20")
    ax.set_ylabel("Country")

    SENSITIVITY_OVERLAP_CHART.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(SENSITIVITY_OVERLAP_CHART, dpi=300)
    plt.close()

    print(f"Saved sensitivity chart: {SENSITIVITY_OVERLAP_CHART}")

    return SENSITIVITY_OVERLAP_CHART


def run_sensitivity_analysis():
    """
    Run sensitivity analysis on executive protection risk rankings.
    """

    print("Running sensitivity analysis...")

    validate_weights()

    rankings = load_rankings()

    sensitivity_rankings = calculate_sensitivity_rankings(rankings)
    top20 = build_top20_by_scenario(sensitivity_rankings)
    overlap = build_top20_overlap(sensitivity_rankings)
    scenario_level_summary = build_scenario_level_summary(sensitivity_rankings)
    summary = build_sensitivity_summary(sensitivity_rankings, overlap)

    SENSITIVITY_RANKINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    sensitivity_rankings.to_csv(SENSITIVITY_RANKINGS_FILE, index=False)
    top20.to_csv(SENSITIVITY_TOP20_FILE, index=False)
    overlap.to_csv(SENSITIVITY_OVERLAP_FILE, index=False)
    summary.to_csv(SENSITIVITY_SUMMARY_FILE, index=False)

    scenario_level_file = SENSITIVITY_SUMMARY_FILE.parent / (
        "sensitivity_scenario_level_summary.csv"
    )
    scenario_level_summary.to_csv(scenario_level_file, index=False)

    save_sensitivity_overlap_chart(overlap)

    print(f"Sensitivity rankings saved to: {SENSITIVITY_RANKINGS_FILE}")
    print(f"Sensitivity top 20 saved to: {SENSITIVITY_TOP20_FILE}")
    print(f"Sensitivity overlap saved to: {SENSITIVITY_OVERLAP_FILE}")
    print(f"Sensitivity summary saved to: {SENSITIVITY_SUMMARY_FILE}")
    print(f"Sensitivity scenario-level summary saved to: {scenario_level_file}")

    if not summary.empty:
        row = summary.iloc[0]
        print(
            "Sensitivity summary: "
            f"{row['countries_top20_in_all_scenarios']} countries appear in the "
            f"top 20 across all {row['scenario_count']} scenarios."
        )
        print(row["stability_interpretation"])

    return sensitivity_rankings, top20, overlap, summary


if __name__ == "__main__":
    run_sensitivity_analysis()