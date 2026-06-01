"""
City-Level EP Risk Visualization Module

Creates charts from the city-level ACLED protective intelligence dataset.

Input:
    data/processed/city_ep_risk_features.csv

Outputs:
    outputs/charts/top_20_city_ep_risk_rankings.png
    outputs/charts/top_15_city_risk_component_breakdown.png

Run from project root:
    python -m src.city_visualization
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
CHARTS_DIR = PROJECT_ROOT / "outputs" / "charts"

CITY_FEATURES_FILE = PROCESSED_DATA_DIR / "city_ep_risk_features.csv"

TOP_20_CITY_RISK_CHART = CHARTS_DIR / "top_20_city_ep_risk_rankings.png"
CITY_COMPONENT_BREAKDOWN_CHART = CHARTS_DIR / "top_15_city_risk_component_breakdown.png"


def load_city_features() -> pd.DataFrame:
    """
    Load processed city EP risk features.
    """
    if not CITY_FEATURES_FILE.exists():
        raise FileNotFoundError(
            f"Could not find city features file at: {CITY_FEATURES_FILE}\n"
            "Run this first:\n"
            "python -m src.acled_city_processing"
        )

    return pd.read_csv(CITY_FEATURES_FILE)


def save_top_city_risk_chart(df: pd.DataFrame, top_n: int = 20) -> Path:
    """
    Save a horizontal bar chart of the top city EP risk rankings.
    """
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    chart_df = df.head(top_n).copy()
    chart_df["city_label"] = chart_df["city"] + ", " + chart_df["country"]

    chart_df = chart_df.sort_values("city_ep_risk_score", ascending=True)

    plt.figure(figsize=(11, 8))
    plt.barh(chart_df["city_label"], chart_df["city_ep_risk_score"])
    plt.xlabel("City EP Risk Score")
    plt.ylabel("City / Location")
    plt.title("Top 20 City-Level Executive Protection Risk Rankings")
    plt.xlim(0, 100)
    plt.tight_layout()
    plt.savefig(TOP_20_CITY_RISK_CHART, dpi=300)
    plt.close()

    return TOP_20_CITY_RISK_CHART


def save_component_breakdown_chart(df: pd.DataFrame, top_n: int = 15) -> Path:
    """
    Save a stacked component breakdown chart for top-ranked cities.
    """
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    component_cols = [
        "civil_unrest_score",
        "political_violence_score",
        "severity_score",
        "momentum_score",
        "ep_relevance_score",
    ]

    missing_cols = [col for col in component_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing component columns: {missing_cols}")

    chart_df = df.head(top_n).copy()
    chart_df["city_label"] = chart_df["city"] + ", " + chart_df["country"]

    # Use weighted contribution values so the chart explains the final score.
    chart_df["Civil Unrest"] = 0.25 * chart_df["civil_unrest_score"]
    chart_df["Political Violence"] = 0.25 * chart_df["political_violence_score"]
    chart_df["Severity"] = 0.20 * chart_df["severity_score"]
    chart_df["Momentum"] = 0.20 * chart_df["momentum_score"]
    chart_df["EP-Relevant Exposure"] = 0.10 * chart_df["ep_relevance_score"]

    plot_cols = [
        "Civil Unrest",
        "Political Violence",
        "Severity",
        "Momentum",
        "EP-Relevant Exposure",
    ]

    chart_df = chart_df.sort_values("city_ep_risk_score", ascending=True)

    ax = chart_df.plot(
        x="city_label",
        y=plot_cols,
        kind="barh",
        stacked=True,
        figsize=(12, 8),
    )

    ax.set_xlabel("Weighted Contribution to Final EP Risk Score")
    ax.set_ylabel("City / Location")
    ax.set_title("Top 15 City EP Risk Score Component Breakdown")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(CITY_COMPONENT_BREAKDOWN_CHART, dpi=300)
    plt.close()

    return CITY_COMPONENT_BREAKDOWN_CHART


def run_city_visualizations() -> None:
    """
    Run all city-level visualizations.
    """
    print("Loading city EP risk features...")
    df = load_city_features()

    print(f"Loaded city rows: {len(df):,}")

    print("Creating top city EP risk ranking chart...")
    top_chart = save_top_city_risk_chart(df)

    print("Creating city risk component breakdown chart...")
    component_chart = save_component_breakdown_chart(df)

    print(f"Saved chart: {top_chart}")
    print(f"Saved chart: {component_chart}")


if __name__ == "__main__":
    run_city_visualizations()