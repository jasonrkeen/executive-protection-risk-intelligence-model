import re
from pathlib import Path

import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    SCENARIO_FILE,
    FORWARD_2026_RISK_FILE,
    COUNTRY_PROFILES_DIR,
    COUNTRY_PROFILE_SUMMARY_FILE,
)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    """
    Read a CSV if it exists. Return an empty DataFrame otherwise.
    """

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, low_memory=False)


def clean_filename(value: str) -> str:
    """
    Convert a country name into a safe markdown filename.
    """

    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")

    return value or "country_profile"


def format_number(value, decimals: int = 2):
    """
    Format numeric values for profile text.
    """

    if pd.isna(value):
        return "N/A"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if value.is_integer():
        return f"{int(value):,}"

    return f"{value:,.{decimals}f}"


def get_top_risk_drivers(row: pd.Series, top_n: int = 3) -> list[tuple[str, float]]:
    """
    Identify the highest component risk drivers for a country.
    """

    driver_map = {
        "Civil Unrest / Political Violence": "civil_unrest_political_violence_score",
        "Governance / Rule-of-Law Risk": "governance_risk_score",
        "Violent-Crime Proxy Risk": "violent_crime_score",
        "Energy-Sector Exposure": "energy_exposure_score",
        "Recent Risk Momentum": "recent_risk_momentum_score",
    }

    drivers = []

    for label, column in driver_map.items():
        if column in row.index:
            value = pd.to_numeric(row[column], errors="coerce")

            if pd.notna(value):
                drivers.append((label, float(value)))

    drivers = sorted(drivers, key=lambda item: item[1], reverse=True)

    return drivers[:top_n]


def build_driver_text(drivers: list[tuple[str, float]]) -> str:
    """
    Build markdown bullet text for top risk drivers.
    """

    if not drivers:
        return "- No component driver data available."

    lines = []

    for label, value in drivers:
        lines.append(f"- **{label}:** {value:.2f}")

    return "\n".join(lines)


def get_country_scenarios(
    scenarios: pd.DataFrame,
    country: str,
) -> pd.DataFrame:
    """
    Get scenario rows for one country.
    """

    if scenarios.empty or "country" not in scenarios.columns:
        return pd.DataFrame()

    output = scenarios[scenarios["country"] == country].copy()

    if output.empty:
        return output

    if "scenario_ep_risk_score" in output.columns:
        output["scenario_ep_risk_score"] = pd.to_numeric(
            output["scenario_ep_risk_score"],
            errors="coerce",
        )

        output = output.sort_values(
            "scenario_ep_risk_score",
            ascending=False,
        )

    return output


def get_country_forward_row(
    forward_scores: pd.DataFrame,
    country: str,
) -> pd.Series | None:
    """
    Get forward-risk row for one country if available.
    """

    if forward_scores.empty or "country" not in forward_scores.columns:
        return None

    match = forward_scores[forward_scores["country"] == country].copy()

    if match.empty:
        return None

    return match.iloc[0]


def build_scenario_table(country_scenarios: pd.DataFrame, max_rows: int = 7) -> str:
    """
    Build markdown scenario table for one country.
    """

    if country_scenarios.empty:
        return "No scenario output available for this country."

    columns = [
        "scenario",
        "baseline_ep_risk_score",
        "scenario_ep_risk_score",
        "scenario_score_lift",
        "scenario_risk_bucket",
    ]

    available_columns = [
        column for column in columns if column in country_scenarios.columns
    ]

    if not available_columns:
        return "No scenario output available for this country."

    display = country_scenarios[available_columns].head(max_rows).copy()

    header = "| Scenario | Baseline | Scenario Score | Lift | Scenario Bucket |"
    separator = "|---|---:|---:|---:|---|"

    lines = [header, separator]

    for _, row in display.iterrows():
        scenario = str(row.get("scenario", "N/A")).replace("_", " ").title()
        baseline = format_number(row.get("baseline_ep_risk_score"), 2)
        score = format_number(row.get("scenario_ep_risk_score"), 2)
        lift = format_number(row.get("scenario_score_lift"), 2)
        bucket = row.get("scenario_risk_bucket", "N/A")

        lines.append(
            f"| {scenario} | {baseline} | {score} | {lift} | {bucket} |"
        )

    return "\n".join(lines)


def build_forward_text(forward_row: pd.Series | None) -> str:
    """
    Build forward-risk interpretation text.
    """

    if forward_row is None:
        return (
            "No 2026 forward-risk row is available for this country. "
            "The country may not be in the current forward top-country set."
        )

    baseline = format_number(forward_row.get("baseline_ep_risk_score_2024"), 2)
    forward = format_number(forward_row.get("forward_2026_ep_risk_score"), 2)
    change = format_number(forward_row.get("forward_score_change"), 2)
    flag = forward_row.get("forward_risk_change_flag", "N/A")
    note = forward_row.get("forward_adjustment_note", "N/A")
    status = forward_row.get("target_year_data_status", "N/A")

    return (
        f"- **2024 baseline score:** {baseline}\n"
        f"- **2026 forward score:** {forward}\n"
        f"- **Forward score change:** {change}\n"
        f"- **Forward change flag:** {flag}\n"
        f"- **Target-year data status:** {status}\n"
        f"- **Forward adjustment note:** {note}"
    )


def build_analyst_interpretation(row: pd.Series) -> str:
    """
    Build a short analyst-style interpretation from the country risk row.
    """

    country = row.get("country", "This country")
    score = pd.to_numeric(row.get("executive_protection_risk_score"), errors="coerce")
    bucket = row.get("risk_bucket", "Unclassified")

    unrest = pd.to_numeric(
        row.get("civil_unrest_political_violence_score"),
        errors="coerce",
    )
    governance = pd.to_numeric(row.get("governance_risk_score"), errors="coerce")
    energy = pd.to_numeric(row.get("energy_exposure_score"), errors="coerce")
    momentum = pd.to_numeric(row.get("recent_risk_momentum_score"), errors="coerce")

    phrases = []

    if pd.notna(unrest) and unrest >= 50:
        phrases.append("elevated civil unrest or political violence exposure")

    if pd.notna(governance) and governance >= 70:
        phrases.append("weak governance or rule-of-law conditions")

    if pd.notna(energy) and energy >= 70:
        phrases.append("high strategic energy-sector exposure")

    if pd.notna(momentum) and momentum >= 70:
        phrases.append("elevated recent risk momentum")

    if phrases:
        driver_text = ", ".join(phrases)
    else:
        driver_text = "a mixed risk-driver profile without one dominant extreme component"

    if pd.notna(score):
        return (
            f"{country} is classified as **{bucket}** with a modeled Executive "
            f"Protection Risk Score of **{score:.2f}**. The country profile is "
            f"primarily shaped by {driver_text}. This profile should be used as a "
            f"strategic screening input rather than a tactical travel decision tool."
        )

    return (
        f"{country} is classified as **{bucket}**. This profile should be used as a "
        f"strategic screening input rather than a tactical travel decision tool."
    )


def build_country_profile_markdown(
    row: pd.Series,
    scenarios: pd.DataFrame,
    forward_scores: pd.DataFrame,
) -> str:
    """
    Build markdown text for one country profile.
    """

    country = row.get("country", "Unknown Country")
    country_code = row.get("country_code", "N/A")

    drivers = get_top_risk_drivers(row)
    country_scenarios = get_country_scenarios(scenarios, country)
    forward_row = get_country_forward_row(forward_scores, country)

    profile = f"""# Executive Protection Country Profile: {country}

## Summary

{build_analyst_interpretation(row)}

## Baseline Risk Snapshot

| Metric | Value |
|---|---:|
| Country code | {country_code} |
| Executive Protection Risk Score | {format_number(row.get("executive_protection_risk_score"), 2)} |
| Risk bucket | {row.get("risk_bucket", "N/A")} |
| Weighted baseline score | {format_number(row.get("weighted_ep_risk_score"), 2)} |
| Severity uplift | {format_number(row.get("severity_uplift_total"), 2)} |
| Data coverage flag | {row.get("data_coverage_flag", "N/A")} |

## Top Risk Drivers

{build_driver_text(drivers)}

## Component Scores

| Component | Score |
|---|---:|
| Civil Unrest / Political Violence | {format_number(row.get("civil_unrest_political_violence_score"), 2)} |
| Governance / Rule-of-Law Risk | {format_number(row.get("governance_risk_score"), 2)} |
| Violent-Crime Proxy Risk | {format_number(row.get("violent_crime_score"), 2)} |
| Energy-Sector Exposure | {format_number(row.get("energy_exposure_score"), 2)} |
| Recent Risk Momentum | {format_number(row.get("recent_risk_momentum_score"), 2)} |

## ACLED Operating Environment Indicators

| Indicator | Value |
|---|---:|
| Total ACLED events | {format_number(row.get("total_acled_events"), 0)} |
| Civil unrest events | {format_number(row.get("civil_unrest_events"), 0)} |
| Violent political events | {format_number(row.get("violent_political_events"), 0)} |
| Total fatalities | {format_number(row.get("total_fatalities"), 0)} |
| Fatal events | {format_number(row.get("fatal_events"), 0)} |
| High-fatality events | {format_number(row.get("high_fatality_events"), 0)} |
| Unique event locations | {format_number(row.get("unique_event_locations"), 0)} |
| Unique coordinate pairs | {format_number(row.get("unique_coordinate_pairs"), 0)} |

## Governance, Crime, and Energy Indicators

| Indicator | Value |
|---|---:|
| Political stability | {format_number(row.get("political_stability"), 2)} |
| Rule of law | {format_number(row.get("rule_of_law"), 2)} |
| Control of corruption | {format_number(row.get("control_of_corruption"), 2)} |
| Government effectiveness | {format_number(row.get("government_effectiveness"), 2)} |
| Homicide rate per 100k | {format_number(row.get("homicide_rate_per_100k"), 2)} |
| Homicide data year | {format_number(row.get("homicide_rate_per_100k_year"), 0)} |
| Crime data quality | {row.get("crime_data_quality_flag", "N/A")} |
| Energy exposure raw | {format_number(row.get("energy_exposure_raw"), 2)} |
| Energy data quality | {row.get("energy_data_quality_flag", "N/A")} |

## Scenario Risk View

{build_scenario_table(country_scenarios)}

## 2026 Forward Risk View

{build_forward_text(forward_row)}

## Analyst Note

This profile is generated from public OSINT and country-level indicators. It does not include itinerary-specific protective intelligence, route analysis, executive profile risk, local liaison information, venue security details, or proprietary security reporting.

"""

    return profile


def generate_country_profiles(top_n: int = 20) -> pd.DataFrame:
    """
    Generate markdown country profiles for top-risk countries.
    """

    print("Generating country intelligence profiles...")

    if not RISK_RANKINGS_FILE.exists():
        raise FileNotFoundError(
            f"Risk rankings file not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    rankings = pd.read_csv(RISK_RANKINGS_FILE, low_memory=False)
    scenarios = read_csv_if_exists(SCENARIO_FILE)
    forward_scores = read_csv_if_exists(FORWARD_2026_RISK_FILE)

    if rankings.empty:
        raise ValueError("Risk rankings file is empty.")

    COUNTRY_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    COUNTRY_PROFILE_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    top_countries = rankings.head(top_n).copy()

    summary_rows = []

    for _, row in top_countries.iterrows():
        country = row["country"]
        filename = clean_filename(country) + ".md"
        output_path = COUNTRY_PROFILES_DIR / filename

        markdown = build_country_profile_markdown(
            row=row,
            scenarios=scenarios,
            forward_scores=forward_scores,
        )

        output_path.write_text(markdown, encoding="utf-8")

        drivers = get_top_risk_drivers(row)
        primary_driver = drivers[0][0] if drivers else "N/A"
        secondary_driver = drivers[1][0] if len(drivers) > 1 else "N/A"

        forward_row = get_country_forward_row(forward_scores, country)

        summary_rows.append(
            {
                "country": country,
                "country_code": row.get("country_code"),
                "profile_file": str(output_path),
                "executive_protection_risk_score": row.get(
                    "executive_protection_risk_score"
                ),
                "risk_bucket": row.get("risk_bucket"),
                "weighted_ep_risk_score": row.get("weighted_ep_risk_score"),
                "severity_uplift_total": row.get("severity_uplift_total"),
                "primary_risk_driver": primary_driver,
                "secondary_risk_driver": secondary_driver,
                "data_coverage_flag": row.get("data_coverage_flag"),
                "forward_2026_ep_risk_score": None
                if forward_row is None
                else forward_row.get("forward_2026_ep_risk_score"),
                "forward_risk_change_flag": None
                if forward_row is None
                else forward_row.get("forward_risk_change_flag"),
                "target_year_data_status": None
                if forward_row is None
                else forward_row.get("target_year_data_status"),
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(COUNTRY_PROFILE_SUMMARY_FILE, index=False)

    print(f"Country profiles saved to: {COUNTRY_PROFILES_DIR}")
    print(f"Country profile summary saved to: {COUNTRY_PROFILE_SUMMARY_FILE}")
    print(f"Profiles generated: {len(summary)}")

    return summary


if __name__ == "__main__":
    generate_country_profiles()