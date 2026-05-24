import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    REGIONAL_SPILLOVER_FILE,
    REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE,
    REGIONAL_SPILLOVER_CHART,
)


REGION_MAP = {
    "Africa": [
        "Nigeria",
        "Sudan",
        "South Sudan",
        "Congo, Dem. Rep.",
        "Congo, Rep.",
        "Cameroon",
        "Mali",
        "Niger",
        "Chad",
        "Somalia",
        "Ethiopia",
        "Kenya",
        "Libya",
        "Algeria",
        "Angola",
        "Mozambique",
    ],
    "Middle East": [
        "Iran, Islamic Rep.",
        "Iraq",
        "Syria",
        "Lebanon",
        "Yemen, Rep.",
        "Israel",
        "Jordan",
        "Saudi Arabia",
        "Oman",
        "United Arab Emirates",
        "Qatar",
        "Kuwait",
        "Bahrain",
    ],
    "Europe / Eurasia": [
        "Ukraine",
        "Russian Federation",
        "Belarus",
        "Moldova",
        "Georgia",
        "Armenia",
        "Azerbaijan",
        "Turkey",
    ],
    "South Asia": [
        "Pakistan",
        "India",
        "Bangladesh",
        "Sri Lanka",
        "Nepal",
        "Afghanistan",
    ],
    "Southeast Asia": [
        "Myanmar",
        "Thailand",
        "Vietnam",
        "Cambodia",
        "Lao PDR",
        "Malaysia",
        "Indonesia",
        "Philippines",
    ],
    "Latin America": [
        "Mexico",
        "Brazil",
        "Colombia",
        "Venezuela, RB",
        "Ecuador",
        "Peru",
        "Chile",
        "Argentina",
        "Bolivia",
        "Paraguay",
        "Haiti",
    ],
}


def load_rankings() -> pd.DataFrame:
    """
    Load baseline EP risk rankings.
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
        "executive_protection_risk_score",
        "risk_bucket",
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(f"Risk rankings file is missing required columns: {missing}")

    df["executive_protection_risk_score"] = pd.to_numeric(
        df["executive_protection_risk_score"],
        errors="coerce",
    ).fillna(0)

    return df


def assign_region(country: str) -> str:
    """
    Assign a country to an analytical region.
    """

    for region, countries in REGION_MAP.items():
        if country in countries:
            return region

    return "Other / Unmapped"


def classify_spillover_score(score: float) -> str:
    """
    Classify regional spillover score.
    """

    if score >= 75:
        return "Severe Regional Spillover Exposure"
    if score >= 60:
        return "High Regional Spillover Exposure"
    if score >= 45:
        return "Elevated Regional Spillover Exposure"
    if score >= 30:
        return "Moderate Regional Spillover Exposure"

    return "Limited Regional Spillover Exposure"


def build_regional_context(rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Build region-level context statistics.
    """

    df = rankings.copy()
    df["analytical_region"] = df["country"].apply(assign_region)

    region_summary = (
        df.groupby("analytical_region", as_index=False)
        .agg(
            regional_country_count=("country", "count"),
            regional_average_ep_risk_score=(
                "executive_protection_risk_score",
                "mean",
            ),
            regional_max_ep_risk_score=("executive_protection_risk_score", "max"),
            elevated_or_higher_countries=(
                "risk_bucket",
                lambda x: x.isin(["Elevated", "High", "Severe"]).sum(),
            ),
            high_or_severe_countries=(
                "risk_bucket",
                lambda x: x.isin(["High", "Severe"]).sum(),
            ),
        )
        .reset_index(drop=True)
    )

    region_summary["regional_average_ep_risk_score"] = region_summary[
        "regional_average_ep_risk_score"
    ].round(2)

    region_summary["regional_elevated_share"] = (
        region_summary["elevated_or_higher_countries"]
        / region_summary["regional_country_count"].replace(0, pd.NA)
    ).fillna(0)

    region_summary["regional_high_severe_share"] = (
        region_summary["high_or_severe_countries"]
        / region_summary["regional_country_count"].replace(0, pd.NA)
    ).fillna(0)

    return region_summary


def calculate_spillover_scores(rankings: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate regional spillover risk scores.
    """

    df = rankings.copy()
    df["analytical_region"] = df["country"].apply(assign_region)

    region_summary = build_regional_context(df)

    output = df.merge(
        region_summary,
        on="analytical_region",
        how="left",
    )

    output["regional_spillover_raw"] = (
        output["regional_average_ep_risk_score"] * 0.40
        + output["regional_max_ep_risk_score"] * 0.25
        + output["regional_elevated_share"] * 100 * 0.20
        + output["regional_high_severe_share"] * 100 * 0.15
    )

    # Blend country risk and regional pressure.
    output["regional_spillover_score"] = (
        output["regional_spillover_raw"] * 0.65
        + output["executive_protection_risk_score"] * 0.35
    ).clip(lower=0, upper=100)

    output["regional_spillover_score"] = output[
        "regional_spillover_score"
    ].round(2)

    output["regional_spillover_flag"] = output["regional_spillover_score"].apply(
        classify_spillover_score
    )

    output["regional_context_note"] = output.apply(
        lambda row: (
            f"{row['analytical_region']} has "
            f"{int(row['elevated_or_higher_countries'])} elevated-or-higher "
            f"countries and {int(row['high_or_severe_countries'])} high/severe "
            f"countries in the current model universe."
        ),
        axis=1,
    )

    columns = [
        "country",
        "country_code",
        "analytical_region",
        "executive_protection_risk_score",
        "risk_bucket",
        "regional_spillover_score",
        "regional_spillover_flag",
        "regional_country_count",
        "regional_average_ep_risk_score",
        "regional_max_ep_risk_score",
        "elevated_or_higher_countries",
        "high_or_severe_countries",
        "regional_elevated_share",
        "regional_high_severe_share",
        "regional_context_note",
    ]

    output = output[columns].sort_values(
        "regional_spillover_score",
        ascending=False,
    )

    return output


def save_spillover_chart(spillover: pd.DataFrame, top_n: int = 20):
    """
    Save regional spillover chart.
    """

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available. Skipping regional spillover chart.")
        return None

    if spillover.empty:
        return None

    REGIONAL_SPILLOVER_CHART.parent.mkdir(parents=True, exist_ok=True)

    chart_df = spillover.head(top_n).copy()

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["regional_spillover_score"])
    ax.invert_yaxis()
    ax.set_title("Top Countries by Regional Spillover Risk")
    ax.set_xlabel("Regional Spillover Score")
    ax.set_ylabel("Country")

    plt.tight_layout()
    plt.savefig(REGIONAL_SPILLOVER_CHART, dpi=300)
    plt.close()

    print(f"Regional spillover chart saved to: {REGIONAL_SPILLOVER_CHART}")

    return REGIONAL_SPILLOVER_CHART


def run_regional_spillover_analysis() -> pd.DataFrame:
    """
    Run regional spillover analysis.
    """

    print("Running regional spillover analysis...")

    rankings = load_rankings()
    spillover = calculate_spillover_scores(rankings)

    REGIONAL_SPILLOVER_FILE.parent.mkdir(parents=True, exist_ok=True)

    spillover.to_csv(REGIONAL_SPILLOVER_FILE, index=False)
    spillover.head(25).to_csv(REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE, index=False)

    save_spillover_chart(spillover)

    print(f"Regional spillover scores saved to: {REGIONAL_SPILLOVER_FILE}")
    print(f"Top regional spillover countries saved to: {REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE}")
    print(f"Shape: {spillover.shape}")

    if not spillover.empty:
        print("\nTop regional spillover countries:")
        print(
            spillover[
                [
                    "country",
                    "analytical_region",
                    "executive_protection_risk_score",
                    "regional_spillover_score",
                    "regional_spillover_flag",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

    return spillover


if __name__ == "__main__":
    run_regional_spillover_analysis()