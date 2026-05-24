import numpy as np
import pandas as pd

from src.config import (
    RISK_RANKINGS_FILE,
    RISK_WEIGHTS,
    RISK_BUCKETS,
    MONTE_CARLO_SIMULATION_FILE,
    MONTE_CARLO_COUNTRY_SUMMARY_FILE,
    MONTE_CARLO_TOP20_PROBABILITY_FILE,
    MONTE_CARLO_SCORE_DISTRIBUTION_CHART,
    MONTE_CARLO_TOP20_PROBABILITY_CHART,
    MONTE_CARLO_SIMULATIONS,
    MONTE_CARLO_RANDOM_SEED,
)


COMPONENT_COLUMNS = [
    "civil_unrest_political_violence_score",
    "governance_risk_score",
    "violent_crime_score",
    "energy_exposure_score",
    "recent_risk_momentum_score",
]


def assign_risk_bucket(score: float) -> str:
    """
    Assign score to project risk bucket.
    """

    for lower, upper, label in RISK_BUCKETS:
        if lower <= score < upper:
            return label

    return "Unclassified"


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
        "executive_protection_risk_score",
        "risk_bucket",
        *COMPONENT_COLUMNS,
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(
            f"Risk rankings file is missing required Monte Carlo columns: {missing}"
        )

    for column in COMPONENT_COLUMNS + ["executive_protection_risk_score"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    if "severity_uplift_total" not in df.columns:
        df["severity_uplift_total"] = 0

    df["severity_uplift_total"] = pd.to_numeric(
        df["severity_uplift_total"],
        errors="coerce",
    ).fillna(0)

    df = df.sort_values(
        "executive_protection_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    df["baseline_rank"] = df.index + 1

    return df


def draw_random_weights(
    rng: np.random.Generator,
    concentration: float = 75,
) -> dict:
    """
    Draw random component weights around the baseline model weights.

    A Dirichlet distribution keeps all weights positive and summing to 1.
    The concentration parameter controls how tightly simulated weights cluster
    around the baseline weights.
    """

    baseline_weights = np.array([RISK_WEIGHTS[column] for column in COMPONENT_COLUMNS])
    alpha = baseline_weights * concentration

    sampled = rng.dirichlet(alpha)

    return dict(zip(COMPONENT_COLUMNS, sampled))


def run_single_simulation(
    rankings: pd.DataFrame,
    weights: dict,
    simulation_id: int,
) -> pd.DataFrame:
    """
    Run one simulated scoring scenario.
    """

    output = rankings[
        [
            "country",
            "country_code",
            "baseline_rank",
            "executive_protection_risk_score",
            "risk_bucket",
            "severity_uplift_total",
            *COMPONENT_COLUMNS,
        ]
    ].copy()

    output["simulation_id"] = simulation_id

    output["simulated_weighted_score"] = 0.0

    for component, weight in weights.items():
        output["simulated_weighted_score"] += output[component] * weight
        output[f"weight_{component}"] = round(weight, 6)

    # Keep the same bounded severity calibration concept, but dampen it slightly
    # so the simulation tests component-weight uncertainty rather than completely
    # reusing the original final score.
    output["simulated_ep_risk_score"] = (
        output["simulated_weighted_score"] + output["severity_uplift_total"] * 0.85
    ).clip(lower=0, upper=100)

    output["simulated_ep_risk_score"] = output[
        "simulated_ep_risk_score"
    ].round(2)

    output = output.sort_values(
        "simulated_ep_risk_score",
        ascending=False,
    ).reset_index(drop=True)

    output["simulated_rank"] = output.index + 1
    output["simulated_risk_bucket"] = output["simulated_ep_risk_score"].apply(
        assign_risk_bucket
    )

    output["in_simulated_top20"] = output["simulated_rank"] <= 20

    output["score_change_vs_baseline"] = (
        output["simulated_ep_risk_score"]
        - output["executive_protection_risk_score"]
    ).round(2)

    output["rank_change_vs_baseline"] = (
        output["baseline_rank"] - output["simulated_rank"]
    )

    return output


def build_country_summary(simulation_results: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize Monte Carlo results by country.
    """

    summary = (
        simulation_results.groupby(["country", "country_code"], as_index=False)
        .agg(
            baseline_score=("executive_protection_risk_score", "first"),
            baseline_bucket=("risk_bucket", "first"),
            baseline_rank=("baseline_rank", "first"),
            mean_simulated_score=("simulated_ep_risk_score", "mean"),
            median_simulated_score=("simulated_ep_risk_score", "median"),
            min_simulated_score=("simulated_ep_risk_score", "min"),
            max_simulated_score=("simulated_ep_risk_score", "max"),
            score_volatility=("simulated_ep_risk_score", "std"),
            mean_simulated_rank=("simulated_rank", "mean"),
            best_simulated_rank=("simulated_rank", "min"),
            worst_simulated_rank=("simulated_rank", "max"),
            top20_probability=("in_simulated_top20", "mean"),
        )
        .reset_index(drop=True)
    )

    summary["mean_simulated_score"] = summary["mean_simulated_score"].round(2)
    summary["median_simulated_score"] = summary["median_simulated_score"].round(2)
    summary["score_volatility"] = summary["score_volatility"].round(2)
    summary["mean_simulated_rank"] = summary["mean_simulated_rank"].round(2)
    summary["top20_probability"] = summary["top20_probability"].round(4)

    summary["score_range"] = (
        summary["max_simulated_score"] - summary["min_simulated_score"]
    ).round(2)

    summary["rank_range"] = (
        summary["worst_simulated_rank"] - summary["best_simulated_rank"]
    )

    summary["monte_carlo_stability_flag"] = summary["top20_probability"].apply(
        classify_top20_stability
    )

    summary = summary.sort_values(
        ["top20_probability", "mean_simulated_score"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return summary


def classify_top20_stability(probability: float) -> str:
    """
    Classify Monte Carlo top-20 stability.
    """

    if probability >= 0.90:
        return "Highly Stable Top-20 Risk"
    if probability >= 0.70:
        return "Stable Top-20 Risk"
    if probability >= 0.40:
        return "Moderately Sensitive"
    if probability > 0:
        return "Occasional Top-20 Risk"
    return "Not Top-20 Stable"


def build_top20_probability_table(country_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Build top-20 probability output table.
    """

    columns = [
        "country",
        "country_code",
        "baseline_rank",
        "baseline_score",
        "baseline_bucket",
        "mean_simulated_score",
        "score_volatility",
        "mean_simulated_rank",
        "best_simulated_rank",
        "worst_simulated_rank",
        "top20_probability",
        "monte_carlo_stability_flag",
    ]

    columns = [column for column in columns if column in country_summary.columns]

    return country_summary[columns].copy()


def save_monte_carlo_charts(country_summary: pd.DataFrame) -> None:
    """
    Save Monte Carlo charts.
    """

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed. Skipping Monte Carlo charts.")
        return

    if country_summary.empty:
        return

    MONTE_CARLO_SCORE_DISTRIBUTION_CHART.parent.mkdir(parents=True, exist_ok=True)

    top_score = country_summary.sort_values(
        "mean_simulated_score",
        ascending=False,
    ).head(20)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top_score["country"], top_score["mean_simulated_score"])
    ax.invert_yaxis()
    ax.set_title("Monte Carlo Mean Simulated EP Risk Score")
    ax.set_xlabel("Mean Simulated EP Risk Score")
    ax.set_ylabel("Country")
    plt.tight_layout()
    plt.savefig(MONTE_CARLO_SCORE_DISTRIBUTION_CHART, dpi=300)
    plt.close()

    print(f"Saved Monte Carlo chart: {MONTE_CARLO_SCORE_DISTRIBUTION_CHART}")

    top_probability = country_summary.sort_values(
        "top20_probability",
        ascending=False,
    ).head(25)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top_probability["country"], top_probability["top20_probability"])
    ax.invert_yaxis()
    ax.set_title("Monte Carlo Top-20 Risk Probability")
    ax.set_xlabel("Probability of Ranking in Simulated Top 20")
    ax.set_ylabel("Country")
    plt.tight_layout()
    plt.savefig(MONTE_CARLO_TOP20_PROBABILITY_CHART, dpi=300)
    plt.close()

    print(f"Saved Monte Carlo chart: {MONTE_CARLO_TOP20_PROBABILITY_CHART}")


def run_monte_carlo_risk_simulation(
    n_simulations: int = MONTE_CARLO_SIMULATIONS,
    random_seed: int = MONTE_CARLO_RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Run Monte Carlo model-weight simulation.
    """

    print("Running Monte Carlo risk simulation...")

    rankings = load_rankings()
    rng = np.random.default_rng(random_seed)

    simulation_outputs = []

    for simulation_id in range(1, n_simulations + 1):
        weights = draw_random_weights(rng)
        simulated = run_single_simulation(
            rankings=rankings,
            weights=weights,
            simulation_id=simulation_id,
        )
        simulation_outputs.append(simulated)

    simulation_results = pd.concat(simulation_outputs, ignore_index=True)
    country_summary = build_country_summary(simulation_results)
    top20_probability = build_top20_probability_table(country_summary)

    MONTE_CARLO_SIMULATION_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save all simulations. This can be a larger file, but useful for auditability.
    simulation_results.to_csv(MONTE_CARLO_SIMULATION_FILE, index=False)
    country_summary.to_csv(MONTE_CARLO_COUNTRY_SUMMARY_FILE, index=False)
    top20_probability.to_csv(MONTE_CARLO_TOP20_PROBABILITY_FILE, index=False)

    save_monte_carlo_charts(country_summary)

    print(f"Monte Carlo simulation rows saved to: {MONTE_CARLO_SIMULATION_FILE}")
    print(f"Monte Carlo country summary saved to: {MONTE_CARLO_COUNTRY_SUMMARY_FILE}")
    print(f"Monte Carlo top-20 probability saved to: {MONTE_CARLO_TOP20_PROBABILITY_FILE}")
    print(f"Simulations completed: {n_simulations:,}")
    print(f"Countries simulated: {rankings['country_code'].nunique():,}")

    if not top20_probability.empty:
        print("\nTop Monte Carlo-stable countries:")
        print(
            top20_probability[
                [
                    "country",
                    "baseline_rank",
                    "mean_simulated_rank",
                    "top20_probability",
                    "monte_carlo_stability_flag",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

    return simulation_results, country_summary, top20_probability


if __name__ == "__main__":
    run_monte_carlo_risk_simulation()