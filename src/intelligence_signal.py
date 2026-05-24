import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    SCENARIO_FILE,
    FORWARD_2026_RISK_FILE,
    MONTE_CARLO_TOP20_PROBABILITY_FILE,
    REGIONAL_SPILLOVER_FILE,
    INTELLIGENCE_SIGNAL_FILE,
    INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE,
    INTELLIGENCE_SIGNAL_CHART,
)


def read_csv_if_exists(path) -> pd.DataFrame:
    """
    Read CSV if available.
    """

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path, low_memory=False)


def normalize_0_100(series: pd.Series) -> pd.Series:
    """
    Normalize a numeric series to 0-100.
    """

    values = pd.to_numeric(series, errors="coerce")

    if values.notna().sum() == 0:
        return pd.Series(0, index=series.index)

    values = values.fillna(values.median())

    min_value = values.min()
    max_value = values.max()

    if max_value == min_value:
        return pd.Series(50, index=series.index)

    return ((values - min_value) / (max_value - min_value) * 100).round(2)


def classify_signal(score: float) -> str:
    """
    Convert intelligence signal score to analyst-facing category.
    """

    if score >= 85:
        return "Severe Watch"
    if score >= 70:
        return "High Attention"
    if score >= 55:
        return "Elevated Monitoring"
    if score >= 40:
        return "Routine Monitoring"

    return "Limited Monitoring"


def classify_signal_change(flag: str) -> str:
    """
    Convert forward flag into concise monitoring language.
    """

    if pd.isna(flag):
        return "No forward signal"

    flag = str(flag)

    if "rising materially" in flag.lower():
        return "Forward risk rising materially"
    if "rising" in flag.lower():
        return "Forward risk rising"
    if "easing materially" in flag.lower():
        return "Forward risk easing materially"
    if "easing" in flag.lower():
        return "Forward risk easing"

    return "Forward risk stable / mixed"


def build_scenario_pressure(scenarios: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize scenario pressure by country.
    """

    if scenarios.empty or "country" not in scenarios.columns:
        return pd.DataFrame(columns=["country", "scenario_pressure_score"])

    df = scenarios.copy()

    if "scenario_ep_risk_score" not in df.columns:
        return pd.DataFrame(columns=["country", "scenario_pressure_score"])

    df["scenario_ep_risk_score"] = pd.to_numeric(
        df["scenario_ep_risk_score"],
        errors="coerce",
    )

    summary = (
        df.groupby("country", as_index=False)
        .agg(
            max_scenario_ep_risk_score=("scenario_ep_risk_score", "max"),
            average_scenario_ep_risk_score=("scenario_ep_risk_score", "mean"),
        )
        .reset_index(drop=True)
    )

    summary["scenario_pressure_score"] = (
        summary["max_scenario_ep_risk_score"] * 0.70
        + summary["average_scenario_ep_risk_score"] * 0.30
    ).round(2)

    return summary


def build_intelligence_signals() -> pd.DataFrame:
    """
    Build executive protection intelligence signals.
    """

    print("Building Executive Protection Intelligence Signals...")

    rankings = read_csv_if_exists(RISK_RANKINGS_FILE)

    if rankings.empty:
        raise FileNotFoundError(
            f"Risk rankings file not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    scenarios = read_csv_if_exists(SCENARIO_FILE)
    forward = read_csv_if_exists(FORWARD_2026_RISK_FILE)
    monte_carlo = read_csv_if_exists(MONTE_CARLO_TOP20_PROBABILITY_FILE)
    spillover = read_csv_if_exists(REGIONAL_SPILLOVER_FILE)

    df = rankings.copy()

    df["executive_protection_risk_score"] = pd.to_numeric(
        df["executive_protection_risk_score"],
        errors="coerce",
    ).fillna(0)

    scenario_pressure = build_scenario_pressure(scenarios)

    if not scenario_pressure.empty:
        df = df.merge(scenario_pressure, on="country", how="left")
    else:
        df["scenario_pressure_score"] = df["executive_protection_risk_score"]

    if not monte_carlo.empty:
        monte_cols = [
            column
            for column in [
                "country",
                "top20_probability",
                "mean_simulated_score",
                "score_volatility",
                "monte_carlo_stability_flag",
            ]
            if column in monte_carlo.columns
        ]
        df = df.merge(monte_carlo[monte_cols], on="country", how="left")
    else:
        df["top20_probability"] = 0
        df["mean_simulated_score"] = df["executive_protection_risk_score"]
        df["score_volatility"] = 0
        df["monte_carlo_stability_flag"] = "No Monte Carlo output"

    if not spillover.empty:
        spillover_cols = [
            column
            for column in [
                "country",
                "analytical_region",
                "regional_spillover_score",
                "regional_spillover_flag",
            ]
            if column in spillover.columns
        ]
        df = df.merge(spillover[spillover_cols], on="country", how="left")
    else:
        df["analytical_region"] = "N/A"
        df["regional_spillover_score"] = 0
        df["regional_spillover_flag"] = "No spillover output"

    if not forward.empty:
        forward_cols = [
            column
            for column in [
                "country",
                "forward_2026_ep_risk_score",
                "forward_score_change",
                "forward_risk_change_flag",
                "target_year_data_status",
            ]
            if column in forward.columns
        ]
        df = df.merge(forward[forward_cols], on="country", how="left")
    else:
        df["forward_2026_ep_risk_score"] = pd.NA
        df["forward_score_change"] = pd.NA
        df["forward_risk_change_flag"] = "No forward output"
        df["target_year_data_status"] = "No forward output"

    df["scenario_pressure_score"] = pd.to_numeric(
        df["scenario_pressure_score"],
        errors="coerce",
    ).fillna(df["executive_protection_risk_score"])

    df["top20_probability"] = pd.to_numeric(
        df["top20_probability"],
        errors="coerce",
    ).fillna(0)

    df["mean_simulated_score"] = pd.to_numeric(
        df["mean_simulated_score"],
        errors="coerce",
    ).fillna(df["executive_protection_risk_score"])

    df["regional_spillover_score"] = pd.to_numeric(
        df["regional_spillover_score"],
        errors="coerce",
    ).fillna(0)

    df["forward_2026_ep_risk_score"] = pd.to_numeric(
        df["forward_2026_ep_risk_score"],
        errors="coerce",
    ).fillna(df["executive_protection_risk_score"])

    df["forward_score_change"] = pd.to_numeric(
        df["forward_score_change"],
        errors="coerce",
    ).fillna(0)

    # Convert top-20 probability to 0-100.
    df["monte_carlo_top20_stability_score"] = (df["top20_probability"] * 100).round(2)

    # Forward pressure rewards rising risk but does not over-penalize easing,
    # because the forward layer may be unavailable or baseline-retained.
    df["forward_pressure_score"] = (
        df["forward_2026_ep_risk_score"]
        + df["forward_score_change"].clip(lower=0) * 1.5
    ).clip(lower=0, upper=100)

    df["forward_pressure_score"] = df["forward_pressure_score"].round(2)

    # Final executive-facing intelligence signal.
    df["ep_intelligence_signal_score"] = (
        df["executive_protection_risk_score"] * 0.35
        + df["scenario_pressure_score"] * 0.20
        + df["monte_carlo_top20_stability_score"] * 0.20
        + df["regional_spillover_score"] * 0.15
        + df["forward_pressure_score"] * 0.10
    ).clip(lower=0, upper=100)

    df["ep_intelligence_signal_score"] = df[
        "ep_intelligence_signal_score"
    ].round(2)

    df["ep_intelligence_signal"] = df["ep_intelligence_signal_score"].apply(
        classify_signal
    )

    df["forward_signal_note"] = df["forward_risk_change_flag"].apply(
        classify_signal_change
    )

    df["analyst_priority_note"] = df.apply(build_priority_note, axis=1)

    output_columns = [
        "country",
        "country_code",
        "analytical_region",
        "executive_protection_risk_score",
        "risk_bucket",
        "ep_intelligence_signal_score",
        "ep_intelligence_signal",
        "scenario_pressure_score",
        "monte_carlo_top20_stability_score",
        "top20_probability",
        "monte_carlo_stability_flag",
        "regional_spillover_score",
        "regional_spillover_flag",
        "forward_2026_ep_risk_score",
        "forward_score_change",
        "forward_signal_note",
        "target_year_data_status",
        "data_coverage_flag",
        "analyst_priority_note",
    ]

    output_columns = [column for column in output_columns if column in df.columns]

    output = df[output_columns].sort_values(
        "ep_intelligence_signal_score",
        ascending=False,
    )

    INTELLIGENCE_SIGNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(INTELLIGENCE_SIGNAL_FILE, index=False)
    output.head(25).to_csv(INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE, index=False)

    save_intelligence_signal_chart(output)

    print(f"Intelligence signals saved to: {INTELLIGENCE_SIGNAL_FILE}")
    print(f"Top intelligence signals saved to: {INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE}")
    print(f"Shape: {output.shape}")

    if not output.empty:
        print("\nTop Executive Protection Intelligence Signals:")
        print(
            output[
                [
                    "country",
                    "ep_intelligence_signal_score",
                    "ep_intelligence_signal",
                    "risk_bucket",
                    "analytical_region",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

    return output


def build_priority_note(row: pd.Series) -> str:
    """
    Build concise analyst-facing priority note.
    """

    signal = row.get("ep_intelligence_signal", "N/A")
    bucket = row.get("risk_bucket", "N/A")
    spillover = row.get("regional_spillover_flag", "N/A")
    mc_flag = row.get("monte_carlo_stability_flag", "N/A")
    forward_note = row.get("forward_signal_note", "N/A")

    return (
        f"{signal}: baseline bucket is {bucket}; regional context is "
        f"{spillover}; Monte Carlo classification is {mc_flag}; "
        f"{forward_note}."
    )


def save_intelligence_signal_chart(signals: pd.DataFrame, top_n: int = 20):
    """
    Save intelligence signal chart.
    """

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available. Skipping intelligence signal chart.")
        return None

    if signals.empty:
        return None

    INTELLIGENCE_SIGNAL_CHART.parent.mkdir(parents=True, exist_ok=True)

    chart_df = signals.head(top_n).copy()

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["ep_intelligence_signal_score"])
    ax.invert_yaxis()
    ax.set_title("Top Executive Protection Intelligence Signals")
    ax.set_xlabel("EP Intelligence Signal Score")
    ax.set_ylabel("Country")

    plt.tight_layout()
    plt.savefig(INTELLIGENCE_SIGNAL_CHART, dpi=300)
    plt.close()

    print(f"Intelligence signal chart saved to: {INTELLIGENCE_SIGNAL_CHART}")

    return INTELLIGENCE_SIGNAL_CHART


if __name__ == "__main__":
    build_intelligence_signals()