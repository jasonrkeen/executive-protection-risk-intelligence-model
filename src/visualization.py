import matplotlib.pyplot as plt
import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    CHARTS_DIR,
    FORWARD_2026_RISK_FILE,
)


def ensure_charts_dir() -> None:
    """
    Ensure chart output directory exists.
    """

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def load_rankings() -> pd.DataFrame:
    """
    Load executive protection risk rankings.
    """

    if not RISK_RANKINGS_FILE.exists():
        raise FileNotFoundError(
            f"Risk rankings file not found at {RISK_RANKINGS_FILE}. "
            "Run python -m src.risk_scoring first."
        )

    return pd.read_csv(RISK_RANKINGS_FILE, low_memory=False)


def load_forward_scores() -> pd.DataFrame:
    """
    Load 2026 forward risk scores if available.
    """

    if not FORWARD_2026_RISK_FILE.exists():
        print(
            f"Forward 2026 risk file not found at {FORWARD_2026_RISK_FILE}. "
            "Skipping forward-risk charts."
        )
        return pd.DataFrame()

    return pd.read_csv(FORWARD_2026_RISK_FILE, low_memory=False)


def has_nonzero_forward_changes(df: pd.DataFrame) -> bool:
    """
    Return True if at least one forward score change is materially non-zero.
    """

    if df.empty or "forward_score_change" not in df.columns:
        return False

    changes = pd.to_numeric(df["forward_score_change"], errors="coerce").fillna(0)

    return bool((changes.abs() > 0.01).any())


def forward_target_year_available(df: pd.DataFrame) -> bool:
    """
    Return True if the forward score file appears to contain actual 2026 ACLED data.
    """

    if df.empty:
        return False

    if "target_year_data_status" in df.columns:
        status = df["target_year_data_status"].fillna("").astype(str)
        if status.str.contains(
            "Target-year ACLED data unavailable",
            case=False,
            regex=False,
        ).all():
            return False

    if "2026_ytd_events" in df.columns:
        events = pd.to_numeric(df["2026_ytd_events"], errors="coerce").fillna(0)
        return bool(events.sum() > 0)

    return False


def save_top_risk_chart(top_n: int = 20):
    """
    Save horizontal bar chart of top countries by EP risk score.
    """

    ensure_charts_dir()
    df = load_rankings().head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(df["country"], df["executive_protection_risk_score"])
    ax.invert_yaxis()
    ax.set_title("Top Countries by Executive Protection Risk Score")
    ax.set_xlabel("EP Risk Score")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "top_ep_risk_countries.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_component_score_chart(top_n: int = 15):
    """
    Save grouped horizontal component score chart for top-risk countries.
    """

    ensure_charts_dir()
    df = load_rankings().head(top_n).copy()

    component_columns = [
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
    ]

    available_components = [column for column in component_columns if column in df.columns]

    if not available_components:
        print("No component score columns available. Skipping component chart.")
        return None

    chart_df = df.set_index("country")[available_components]

    fig, ax = plt.subplots(figsize=(11, 7))
    chart_df.plot(kind="barh", ax=ax)
    ax.invert_yaxis()
    ax.set_title("EP Risk Component Scores for Top-Risk Countries")
    ax.set_xlabel("Component Score")
    ax.set_ylabel("Country")
    ax.legend(
        [
            "Civil Unrest / Political Violence",
            "Governance Risk",
            "Violent Crime",
            "Energy Exposure",
            "Recent Momentum",
        ][: len(available_components)],
        fontsize=8,
    )

    path = CHARTS_DIR / "ep_risk_component_scores.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_weighted_vs_final_score_chart(top_n: int = 15):
    """
    Save chart comparing weighted baseline score to final calibrated score.
    """

    ensure_charts_dir()
    df = load_rankings().head(top_n).copy()

    required_columns = {
        "country",
        "weighted_ep_risk_score",
        "executive_protection_risk_score",
    }

    if not required_columns.issubset(df.columns):
        print("Weighted/final score columns not found. Skipping calibration score chart.")
        return None

    chart_df = df.set_index("country")[
        ["weighted_ep_risk_score", "executive_protection_risk_score"]
    ].copy()

    fig, ax = plt.subplots(figsize=(10, 7))
    chart_df.plot(kind="barh", ax=ax)
    ax.invert_yaxis()
    ax.set_title("Weighted Baseline vs. Final Calibrated EP Risk Score")
    ax.set_xlabel("Risk Score")
    ax.set_ylabel("Country")
    ax.legend(["Weighted Baseline", "Final Calibrated"], fontsize=8)

    path = CHARTS_DIR / "weighted_vs_final_ep_risk_score.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_severity_uplift_chart(top_n: int = 15):
    """
    Save chart showing severity uplift by country.
    """

    ensure_charts_dir()
    df = load_rankings().copy()

    required_columns = {
        "country",
        "severity_uplift_total",
    }

    if not required_columns.issubset(df.columns):
        print("Severity uplift columns not found. Skipping severity uplift chart.")
        return None

    chart_df = df[df["severity_uplift_total"].fillna(0) > 0].copy()

    if chart_df.empty:
        print("No severity uplift values found. Skipping severity uplift chart.")
        return None

    chart_df = chart_df.sort_values("severity_uplift_total", ascending=False).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["severity_uplift_total"])
    ax.invert_yaxis()
    ax.set_title("Largest Severity Calibration Uplifts")
    ax.set_xlabel("Severity Uplift")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "severity_calibration_uplifts.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_energy_vs_risk_scatter():
    """
    Save energy exposure vs. EP risk scatterplot.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "energy_exposure_score" not in df.columns:
        print("energy_exposure_score not found. Skipping energy scatter.")
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["energy_exposure_score"],
        df["executive_protection_risk_score"],
        alpha=0.7,
    )
    ax.set_title("Energy Exposure vs. Executive Protection Risk")
    ax.set_xlabel("Energy Exposure Score")
    ax.set_ylabel("Executive Protection Risk Score")

    path = CHARTS_DIR / "energy_exposure_vs_ep_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_governance_vs_risk_scatter():
    """
    Save governance risk vs. EP risk scatterplot.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "governance_risk_score" not in df.columns:
        print("governance_risk_score not found. Skipping governance scatter.")
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["governance_risk_score"],
        df["executive_protection_risk_score"],
        alpha=0.7,
    )
    ax.set_title("Governance Risk vs. Executive Protection Risk")
    ax.set_xlabel("Governance Risk Score")
    ax.set_ylabel("Executive Protection Risk Score")

    path = CHARTS_DIR / "governance_risk_vs_ep_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_civil_unrest_vs_risk_scatter():
    """
    Save civil unrest / political violence vs. EP risk scatterplot.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "civil_unrest_political_violence_score" not in df.columns:
        print(
            "civil_unrest_political_violence_score not found. "
            "Skipping civil unrest scatter."
        )
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["civil_unrest_political_violence_score"],
        df["executive_protection_risk_score"],
        alpha=0.7,
    )
    ax.set_title("Civil Unrest / Political Violence vs. EP Risk")
    ax.set_xlabel("Civil Unrest / Political Violence Score")
    ax.set_ylabel("Executive Protection Risk Score")

    path = CHARTS_DIR / "civil_unrest_vs_ep_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_crime_vs_risk_scatter():
    """
    Save violent crime score vs. EP risk scatterplot.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "violent_crime_score" not in df.columns:
        print("violent_crime_score not found. Skipping crime scatter.")
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["violent_crime_score"],
        df["executive_protection_risk_score"],
        alpha=0.7,
    )
    ax.set_title("Violent Crime Proxy vs. Executive Protection Risk")
    ax.set_xlabel("Violent Crime Score")
    ax.set_ylabel("Executive Protection Risk Score")

    path = CHARTS_DIR / "violent_crime_vs_ep_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_recent_momentum_vs_risk_scatter():
    """
    Save recent risk momentum vs. EP risk scatterplot.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "recent_risk_momentum_score" not in df.columns:
        print("recent_risk_momentum_score not found. Skipping momentum scatter.")
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df["recent_risk_momentum_score"],
        df["executive_protection_risk_score"],
        alpha=0.7,
    )
    ax.set_title("Recent Risk Momentum vs. Executive Protection Risk")
    ax.set_xlabel("Recent Risk Momentum Score")
    ax.set_ylabel("Executive Protection Risk Score")

    path = CHARTS_DIR / "recent_momentum_vs_ep_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_risk_bucket_distribution_chart():
    """
    Save risk bucket distribution chart.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "risk_bucket" not in df.columns:
        print("risk_bucket not found. Skipping bucket distribution.")
        return None

    bucket_order = ["Low", "Moderate", "Elevated", "High", "Severe"]

    counts = df["risk_bucket"].value_counts().reindex(bucket_order).fillna(0)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(counts.index, counts.values)
    ax.set_title("Executive Protection Risk Bucket Distribution")
    ax.set_xlabel("Risk Bucket")
    ax.set_ylabel("Country Count")

    path = CHARTS_DIR / "ep_risk_bucket_distribution.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_data_coverage_chart():
    """
    Save data coverage distribution chart.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "data_coverage_flag" not in df.columns:
        print("data_coverage_flag not found. Skipping data coverage chart.")
        return None

    counts = df["data_coverage_flag"].value_counts()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(counts.index, counts.values)
    ax.set_title("Model Data Coverage Distribution")
    ax.set_xlabel("Data Coverage Flag")
    ax.set_ylabel("Country Count")
    ax.tick_params(axis="x", rotation=20)

    path = CHARTS_DIR / "model_data_coverage_distribution.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_acled_event_volume_chart(top_n: int = 20):
    """
    Save top countries by ACLED event volume.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "total_acled_events" not in df.columns:
        print("total_acled_events not found. Skipping ACLED volume chart.")
        return None

    chart_df = df.sort_values("total_acled_events", ascending=False).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["total_acled_events"])
    ax.invert_yaxis()
    ax.set_title("Top Countries by ACLED Event Volume")
    ax.set_xlabel("Total ACLED Events")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "top_acled_event_volume_countries.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_fatality_intensity_chart(top_n: int = 20):
    """
    Save top countries by total fatalities.
    """

    ensure_charts_dir()
    df = load_rankings()

    if "total_fatalities" not in df.columns:
        print("total_fatalities not found. Skipping fatality chart.")
        return None

    chart_df = df.sort_values("total_fatalities", ascending=False).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["total_fatalities"])
    ax.invert_yaxis()
    ax.set_title("Top Countries by ACLED-Reported Fatalities")
    ax.set_xlabel("Total Fatalities")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "top_acled_fatality_countries.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_forward_2026_risk_chart(top_n: int = 15):
    """
    Save top 2026 forward EP risk scores.
    """

    ensure_charts_dir()
    df = load_forward_scores()

    if df.empty:
        return None

    required_columns = {
        "country",
        "forward_2026_ep_risk_score",
    }

    if not required_columns.issubset(df.columns):
        print("Forward score columns not found. Skipping forward risk chart.")
        return None

    chart_df = df.sort_values(
        "forward_2026_ep_risk_score",
        ascending=False,
    ).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["forward_2026_ep_risk_score"])
    ax.invert_yaxis()
    ax.set_title("Top Countries by 2026 Forward EP Risk Score")
    ax.set_xlabel("2026 Forward EP Risk Score")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "forward_2026_top_risk_countries.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_forward_2026_score_change_chart(top_n: int = 20):
    """
    Save 2026 forward score change chart.

    Skips chart when all score changes are zero because that usually means the
    forward layer retained baseline due to unavailable target-year ACLED data.
    """

    ensure_charts_dir()
    df = load_forward_scores()

    if df.empty:
        return None

    required_columns = {
        "country",
        "forward_score_change",
    }

    if not required_columns.issubset(df.columns):
        print("Forward score change columns not found. Skipping forward change chart.")
        return None

    if not has_nonzero_forward_changes(df):
        print("All forward score changes are zero. Skipping forward change chart.")
        return None

    chart_df = df.sort_values(
        "forward_score_change",
        ascending=True,
    ).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["forward_score_change"])
    ax.set_title("Largest 2026 Forward EP Risk Score Changes")
    ax.set_xlabel("Forward Score Change vs. 2024 Baseline")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "forward_2026_score_changes.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_forward_2026_momentum_chart(top_n: int = 15):
    """
    Save forward ACLED event momentum chart.

    Skips chart when target-year ACLED data is unavailable.
    """

    ensure_charts_dir()
    df = load_forward_scores()

    if df.empty:
        return None

    if not forward_target_year_available(df):
        print("Target-year ACLED data unavailable. Skipping forward momentum chart.")
        return None

    required_columns = {
        "country",
        "event_momentum_2026_vs_2025_ytd",
    }

    if not required_columns.issubset(df.columns):
        print("Forward momentum columns not found. Skipping forward momentum chart.")
        return None

    chart_df = df.sort_values(
        "event_momentum_2026_vs_2025_ytd",
        ascending=False,
    ).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(chart_df["country"], chart_df["event_momentum_2026_vs_2025_ytd"])
    ax.invert_yaxis()
    ax.set_title("2026 YTD ACLED Event Momentum vs. 2025 Same Period")
    ax.set_xlabel("Event Momentum Ratio")
    ax.set_ylabel("Country")

    path = CHARTS_DIR / "forward_2026_acled_event_momentum.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_forward_2026_bucket_distribution_chart():
    """
    Save 2026 forward risk bucket distribution.
    """

    ensure_charts_dir()
    df = load_forward_scores()

    if df.empty:
        return None

    if "forward_risk_bucket_2026" not in df.columns:
        print("forward_risk_bucket_2026 not found. Skipping forward bucket chart.")
        return None

    bucket_order = ["Low", "Moderate", "Elevated", "High", "Severe"]

    counts = df["forward_risk_bucket_2026"].value_counts().reindex(bucket_order).fillna(0)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(counts.index, counts.values)
    ax.set_title("2026 Forward EP Risk Bucket Distribution")
    ax.set_xlabel("Forward Risk Bucket")
    ax.set_ylabel("Country Count")

    path = CHARTS_DIR / "forward_2026_bucket_distribution.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()

    print(f"Saved chart: {path}")
    return path


def save_all_charts():
    """
    Save all model charts.
    """

    paths = [
        save_top_risk_chart(),
        save_component_score_chart(),
        save_weighted_vs_final_score_chart(),
        save_severity_uplift_chart(),
        save_energy_vs_risk_scatter(),
        save_governance_vs_risk_scatter(),
        save_civil_unrest_vs_risk_scatter(),
        save_crime_vs_risk_scatter(),
        save_recent_momentum_vs_risk_scatter(),
        save_risk_bucket_distribution_chart(),
        save_data_coverage_chart(),
        save_acled_event_volume_chart(),
        save_fatality_intensity_chart(),
        save_forward_2026_risk_chart(),
        save_forward_2026_score_change_chart(),
        save_forward_2026_momentum_chart(),
        save_forward_2026_bucket_distribution_chart(),
    ]

    return [path for path in paths if path is not None]


if __name__ == "__main__":
    save_all_charts()