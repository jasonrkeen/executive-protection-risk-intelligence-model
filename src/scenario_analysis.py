import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    SCENARIO_FILE,
    SCENARIO_MULTIPLIERS,
    RISK_BUCKETS,
    SCENARIO_TOP_COUNTRIES_FILE,
    SCENARIO_SUMMARY_FILE,
)


SCENARIO_DESCRIPTIONS = {
    "routine_executive_travel": {
        "description": "Baseline executive travel under normal operating conditions.",
        "operational_relevance": (
            "Useful for standard itinerary screening and country-level "
            "travel-risk comparison."
        ),
    },
    "public_energy_event": {
        "description": "Executive attendance at a visible public energy-sector event.",
        "operational_relevance": (
            "Relevant for conferences, shareholder-facing events, media appearances, "
            "and public venues."
        ),
    },
    "site_visit_to_energy_asset": {
        "description": (
            "Executive visit to an energy production, infrastructure, or project site."
        ),
        "operational_relevance": (
            "Relevant for facility visits, field operations, remote assets, and "
            "project inspections."
        ),
    },
    "travel_during_civil_unrest": {
        "description": (
            "Executive movement during an elevated civil unrest or protest environment."
        ),
        "operational_relevance": (
            "Relevant for route planning, movement timing, protest monitoring, "
            "and contingency planning."
        ),
    },
    "high_visibility_executive_visit": {
        "description": (
            "High-profile executive travel where visibility, symbolic value, or "
            "media attention is elevated."
        ),
        "operational_relevance": (
            "Relevant for senior leadership visits, major announcements, government "
            "meetings, and public-facing travel."
        ),
    },
    "major_energy_project_announcement": {
        "description": (
            "Executive presence connected to a major energy investment, project launch, "
            "or policy-sensitive announcement."
        ),
        "operational_relevance": (
            "Relevant where energy projects intersect with local politics, environmental "
            "opposition, or community tensions."
        ),
    },
    "labor_unrest_or_protest_environment": {
        "description": (
            "Executive travel or site activity in a labor unrest, activist, or "
            "protest-sensitive environment."
        ),
        "operational_relevance": (
            "Relevant for workforce disruption, organized demonstrations, and "
            "event-security planning."
        ),
    },
}


def assign_risk_bucket(score: float) -> str:
    """
    Assign a scenario-adjusted score to a risk bucket.
    """

    for lower, upper, label in RISK_BUCKETS:
        if lower <= score < upper:
            return label

    return "Unclassified"


def load_rankings() -> pd.DataFrame:
    """
    Load baseline EP risk rankings.
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

    rankings["executive_protection_risk_score"] = pd.to_numeric(
        rankings["executive_protection_risk_score"],
        errors="coerce",
    ).fillna(0)

    return rankings


def get_scenario_metadata(scenario: str) -> dict:
    """
    Return scenario description and operational relevance.
    """

    return SCENARIO_DESCRIPTIONS.get(
        scenario,
        {
            "description": "Scenario description not available.",
            "operational_relevance": "Operational relevance not specified.",
        },
    )


def calculate_scenario_results(rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Apply scenario multipliers to the baseline EP risk score.
    """

    rows = []

    for _, row in rankings.iterrows():
        baseline_score = row["executive_protection_risk_score"]

        for scenario, multiplier in SCENARIO_MULTIPLIERS.items():
            scenario_score = min(baseline_score * multiplier, 100)
            score_lift = scenario_score - baseline_score
            scenario_info = get_scenario_metadata(scenario)

            rows.append(
                {
                    "country": row["country"],
                    "country_code": row["country_code"],
                    "scenario": scenario,
                    "scenario_description": scenario_info["description"],
                    "operational_relevance": scenario_info["operational_relevance"],
                    "baseline_ep_risk_score": round(baseline_score, 2),
                    "baseline_risk_bucket": row["risk_bucket"],
                    "scenario_multiplier": multiplier,
                    "scenario_ep_risk_score": round(scenario_score, 2),
                    "scenario_score_lift": round(score_lift, 2),
                    "scenario_risk_bucket": assign_risk_bucket(scenario_score),
                }
            )

    output = pd.DataFrame(rows)

    if output.empty:
        return output

    output = output.sort_values(
        ["scenario", "scenario_ep_risk_score"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return output


def build_scenario_top_countries(
    scenario_results: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Build a top-country table for each scenario.
    """

    if scenario_results.empty:
        return pd.DataFrame()

    top_rows = []

    for scenario, scenario_df in scenario_results.groupby("scenario"):
        temp = scenario_df.sort_values(
            "scenario_ep_risk_score",
            ascending=False,
        ).head(top_n).copy()

        temp["scenario_rank"] = range(1, len(temp) + 1)
        top_rows.append(temp)

    if not top_rows:
        return pd.DataFrame()

    output = pd.concat(top_rows, ignore_index=True)

    keep_columns = [
        "scenario",
        "scenario_rank",
        "country",
        "country_code",
        "baseline_ep_risk_score",
        "scenario_ep_risk_score",
        "scenario_score_lift",
        "baseline_risk_bucket",
        "scenario_risk_bucket",
        "operational_relevance",
    ]

    keep_columns = [column for column in keep_columns if column in output.columns]

    return output[keep_columns]


def build_scenario_summary(scenario_results: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize risk distribution by scenario.
    """

    if scenario_results.empty:
        return pd.DataFrame()

    rows = []

    for scenario, scenario_df in scenario_results.groupby("scenario"):
        severe_count = (scenario_df["scenario_risk_bucket"] == "Severe").sum()
        high_count = (scenario_df["scenario_risk_bucket"] == "High").sum()
        elevated_count = (scenario_df["scenario_risk_bucket"] == "Elevated").sum()
        moderate_count = (scenario_df["scenario_risk_bucket"] == "Moderate").sum()
        low_count = (scenario_df["scenario_risk_bucket"] == "Low").sum()

        elevated_or_higher = scenario_df[
            scenario_df["scenario_risk_bucket"].isin(["Elevated", "High", "Severe"])
        ].shape[0]

        rows.append(
            {
                "scenario": scenario,
                "country_count": len(scenario_df),
                "average_scenario_ep_risk_score": round(
                    scenario_df["scenario_ep_risk_score"].mean(),
                    2,
                ),
                "median_scenario_ep_risk_score": round(
                    scenario_df["scenario_ep_risk_score"].median(),
                    2,
                ),
                "max_scenario_ep_risk_score": round(
                    scenario_df["scenario_ep_risk_score"].max(),
                    2,
                ),
                "low_risk_country_count": int(low_count),
                "moderate_risk_country_count": int(moderate_count),
                "elevated_risk_country_count": int(elevated_count),
                "high_risk_country_count": int(high_count),
                "severe_risk_country_count": int(severe_count),
                "elevated_or_higher_country_count": int(elevated_or_higher),
            }
        )

    output = pd.DataFrame(rows).sort_values(
        "average_scenario_ep_risk_score",
        ascending=False,
    )

    return output


def run_scenario_analysis() -> pd.DataFrame:
    """
    Run executive protection scenario analysis.
    """

    print("Running executive protection scenario analysis...")

    rankings = load_rankings()

    scenario_results = calculate_scenario_results(rankings)
    scenario_top_countries = build_scenario_top_countries(scenario_results)
    scenario_summary = build_scenario_summary(scenario_results)

    SCENARIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    scenario_results.to_csv(SCENARIO_FILE, index=False)
    scenario_top_countries.to_csv(SCENARIO_TOP_COUNTRIES_FILE, index=False)
    scenario_summary.to_csv(SCENARIO_SUMMARY_FILE, index=False)

    print(f"Scenario results saved to: {SCENARIO_FILE}")
    print(f"Scenario top countries saved to: {SCENARIO_TOP_COUNTRIES_FILE}")
    print(f"Scenario summary saved to: {SCENARIO_SUMMARY_FILE}")
    print(f"Shape: {scenario_results.shape}")

    if not scenario_summary.empty:
        print("\nScenario summary:")
        print(
            scenario_summary[
                [
                    "scenario",
                    "average_scenario_ep_risk_score",
                    "elevated_or_higher_country_count",
                    "high_risk_country_count",
                    "severe_risk_country_count",
                ]
            ].to_string(index=False)
        )

    return scenario_results


if __name__ == "__main__":
    run_scenario_analysis()