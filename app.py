from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import (
    PROJECT_TITLE,
    PROJECT_SUBTITLE,
    AUTHOR_NAME,
    AUTHOR_EMAIL,
    RISK_RANKINGS_FILE,
    SCENARIO_FILE,
    SCENARIO_SUMMARY_FILE,
    SENSITIVITY_OVERLAP_FILE,
    FORWARD_2026_RISK_FILE,
    COUNTRY_PROFILE_SUMMARY_FILE,
    MODEL_GOVERNANCE_FILE,
    MODEL_ASSUMPTIONS_FILE,
    MODEL_MATURITY_FILE,
    MODEL_COMPONENT_COVERAGE_FILE,
    RISK_SCORE_CHANGES_FILE,
    RISK_BUCKET_CHANGES_FILE,
    TOP_RANK_MOVERS_FILE,
    MONTE_CARLO_COUNTRY_SUMMARY_FILE,
    MONTE_CARLO_TOP20_PROBABILITY_FILE,
    REGIONAL_SPILLOVER_FILE,
    REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE,
    INTELLIGENCE_SIGNAL_FILE,
    INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE,
    REPORT_FILE,
)


st.set_page_config(
    page_title="Executive Protection Risk Intelligence",
    page_icon="🌍",
    layout="wide",
)


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def format_score(value):
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "N/A"


@st.cache_data
def load_data():
    return {
        "rankings": read_csv_if_exists(RISK_RANKINGS_FILE),
        "scenarios": read_csv_if_exists(SCENARIO_FILE),
        "scenario_summary": read_csv_if_exists(SCENARIO_SUMMARY_FILE),
        "sensitivity_overlap": read_csv_if_exists(SENSITIVITY_OVERLAP_FILE),
        "forward": read_csv_if_exists(FORWARD_2026_RISK_FILE),
        "profiles": read_csv_if_exists(COUNTRY_PROFILE_SUMMARY_FILE),
        "governance": read_csv_if_exists(MODEL_GOVERNANCE_FILE),
        "assumptions": read_csv_if_exists(MODEL_ASSUMPTIONS_FILE),
        "maturity": read_csv_if_exists(MODEL_MATURITY_FILE),
        "coverage": read_csv_if_exists(MODEL_COMPONENT_COVERAGE_FILE),
        "score_changes": read_csv_if_exists(RISK_SCORE_CHANGES_FILE),
        "bucket_changes": read_csv_if_exists(RISK_BUCKET_CHANGES_FILE),
        "rank_movers": read_csv_if_exists(TOP_RANK_MOVERS_FILE),
        "monte_carlo_summary": read_csv_if_exists(MONTE_CARLO_COUNTRY_SUMMARY_FILE),
        "monte_carlo_top20": read_csv_if_exists(MONTE_CARLO_TOP20_PROBABILITY_FILE),
        "spillover": read_csv_if_exists(REGIONAL_SPILLOVER_FILE),
        "spillover_top": read_csv_if_exists(REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE),
        "intelligence_signals": read_csv_if_exists(INTELLIGENCE_SIGNAL_FILE),
        "intelligence_signal_top": read_csv_if_exists(INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE),
    }


def show_header():
    st.title("🌍 Executive Protection Risk Intelligence Dashboard")
    st.caption(PROJECT_TITLE)
    st.write(PROJECT_SUBTITLE)
    st.caption(f"{AUTHOR_NAME} | {AUTHOR_EMAIL}")


def show_report_download():
    if REPORT_FILE.exists():
        with open(REPORT_FILE, "rb") as file:
            st.download_button(
                label="Download PDF Report",
                data=file,
                file_name=REPORT_FILE.name,
                mime="application/pdf",
            )


def show_overview(rankings: pd.DataFrame, maturity: pd.DataFrame):
    st.subheader("Model Overview")

    if rankings.empty:
        st.warning("Risk rankings file not found. Run `python -m src.main` first.")
        return

    top_country = rankings.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Countries Ranked", f"{len(rankings):,}")
    col2.metric("Highest Risk Country", str(top_country.get("country", "N/A")))
    col3.metric(
        "Top EP Risk Score",
        format_score(top_country.get("executive_protection_risk_score")),
    )
    col4.metric("Top Risk Bucket", str(top_country.get("risk_bucket", "N/A")))

    if not maturity.empty:
        row = maturity.iloc[0]
        st.info(
            f"Baseline model maturity: **{row.get('model_maturity', 'N/A')}** | "
            f"Forward layer status: **{row.get('forward_layer_status', 'N/A')}**"
        )


def show_rankings_tab(rankings: pd.DataFrame):
    st.subheader("Country Risk Rankings")

    if rankings.empty:
        st.warning("No rankings data available.")
        return

    bucket_options = ["All"] + sorted(rankings["risk_bucket"].dropna().unique().tolist())
    selected_bucket = st.selectbox("Filter by risk bucket", bucket_options)

    display = rankings.copy()

    if selected_bucket != "All":
        display = display[display["risk_bucket"] == selected_bucket]

    top_n = st.slider("Number of countries to display", 10, 100, 25)

    display_columns = [
        "country",
        "country_code",
        "executive_protection_risk_score",
        "risk_bucket",
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
        "data_coverage_flag",
    ]

    display_columns = [column for column in display_columns if column in display.columns]

    st.dataframe(
        display[display_columns].head(top_n),
        use_container_width=True,
        hide_index=True,
    )

    if "executive_protection_risk_score" in display.columns:
        chart_df = display.head(top_n).set_index("country")[
            "executive_protection_risk_score"
        ]
        st.bar_chart(chart_df)


def show_country_profile_tab(
    rankings: pd.DataFrame,
    scenarios: pd.DataFrame,
    forward: pd.DataFrame,
    profiles: pd.DataFrame,
):
    st.subheader("Country Intelligence Profile")

    if rankings.empty:
        st.warning("No rankings data available.")
        return

    countries = rankings["country"].dropna().tolist()
    default_index = countries.index("Ukraine") if "Ukraine" in countries else 0
    selected_country = st.selectbox("Select country", countries, index=default_index)

    row = rankings[rankings["country"] == selected_country].iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("EP Risk Score", format_score(row.get("executive_protection_risk_score")))
    col2.metric("Risk Bucket", str(row.get("risk_bucket", "N/A")))
    col3.metric("Weighted Score", format_score(row.get("weighted_ep_risk_score")))
    col4.metric("Severity Uplift", format_score(row.get("severity_uplift_total")))

    st.markdown("### Component Scores")

    component_columns = [
        "civil_unrest_political_violence_score",
        "governance_risk_score",
        "violent_crime_score",
        "energy_exposure_score",
        "recent_risk_momentum_score",
    ]

    available_components = [
        column for column in component_columns if column in rankings.columns
    ]

    if available_components:
        component_labels = {
            "civil_unrest_political_violence_score": "Civil Unrest / Political Violence",
            "governance_risk_score": "Governance Risk",
            "violent_crime_score": "Violent Crime",
            "energy_exposure_score": "Energy Exposure",
            "recent_risk_momentum_score": "Recent Momentum",
        }

        component_df = pd.DataFrame(
            {
                "component": [component_labels[column] for column in available_components],
                "score": [row.get(column) for column in available_components],
            }
        )

        st.dataframe(component_df, use_container_width=True, hide_index=True)
        st.bar_chart(component_df.set_index("component")["score"])

    st.markdown("### ACLED Operating Environment")

    acled_columns = [
        "total_acled_events",
        "civil_unrest_events",
        "violent_political_events",
        "total_fatalities",
        "fatal_events",
        "high_fatality_events",
        "unique_event_locations",
        "unique_coordinate_pairs",
    ]

    acled_data = {
        column: row.get(column)
        for column in acled_columns
        if column in rankings.columns
    }

    if acled_data:
        st.dataframe(
            pd.DataFrame(
                [{"indicator": key, "value": value} for key, value in acled_data.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Scenario View")

    if not scenarios.empty and "country" in scenarios.columns:
        country_scenarios = scenarios[scenarios["country"] == selected_country].copy()

        if not country_scenarios.empty:
            scenario_cols = [
                "scenario",
                "baseline_ep_risk_score",
                "scenario_multiplier",
                "scenario_ep_risk_score",
                "scenario_score_lift",
                "scenario_risk_bucket",
            ]
            scenario_cols = [
                column for column in scenario_cols if column in country_scenarios.columns
            ]

            st.dataframe(
                country_scenarios[scenario_cols].sort_values(
                    "scenario_ep_risk_score",
                    ascending=False,
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No scenario rows available for this country.")

    st.markdown("### 2026 Forward Risk View")

    if not forward.empty and "country" in forward.columns:
        forward_row = forward[forward["country"] == selected_country].copy()

        if not forward_row.empty:
            forward_cols = [
                "baseline_ep_risk_score_2024",
                "forward_2026_ep_risk_score",
                "forward_score_change",
                "forward_risk_change_flag",
                "target_year_data_status",
                "forward_adjustment_note",
            ]
            forward_cols = [
                column for column in forward_cols if column in forward_row.columns
            ]

            st.dataframe(
                forward_row[forward_cols],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("This country is not currently included in the forward-risk set.")

    if not profiles.empty and "country" in profiles.columns:
        profile_row = profiles[profiles["country"] == selected_country].copy()

        if not profile_row.empty and "profile_file" in profile_row.columns:
            st.caption(f"Markdown profile file: {profile_row.iloc[0]['profile_file']}")


def show_intelligence_signal_tab(
    intelligence_signals: pd.DataFrame,
    intelligence_signal_top: pd.DataFrame,
):
    st.subheader("Executive Protection Intelligence Signal")

    if intelligence_signals.empty and intelligence_signal_top.empty:
        st.warning(
            "No intelligence signal output available. Run `python -m src.intelligence_signal` "
            "or `python -m src.main` first."
        )
        return

    st.write(
        "The Executive Protection Intelligence Signal combines baseline EP risk, "
        "scenario pressure, Monte Carlo top-20 stability, regional spillover exposure, "
        "and forward-risk pressure into a single analyst-facing monitoring score."
    )

    display = (
        intelligence_signal_top
        if not intelligence_signal_top.empty
        else intelligence_signals
    ).copy()

    col1, col2, col3, col4 = st.columns(4)

    top_row = display.iloc[0]
    col1.metric("Top Signal Country", str(top_row.get("country", "N/A")))
    col2.metric(
        "Top Signal Score",
        format_score(top_row.get("ep_intelligence_signal_score")),
    )
    col3.metric("Top Signal", str(top_row.get("ep_intelligence_signal", "N/A")))
    col4.metric("Region", str(top_row.get("analytical_region", "N/A")))

    signal_options = ["All"]
    if "ep_intelligence_signal" in display.columns:
        signal_options += sorted(display["ep_intelligence_signal"].dropna().unique().tolist())

    selected_signal = st.selectbox("Filter by intelligence signal", signal_options)

    filtered = display.copy()
    if selected_signal != "All" and "ep_intelligence_signal" in filtered.columns:
        filtered = filtered[filtered["ep_intelligence_signal"] == selected_signal]

    display_columns = [
        "country",
        "analytical_region",
        "executive_protection_risk_score",
        "risk_bucket",
        "ep_intelligence_signal_score",
        "ep_intelligence_signal",
        "scenario_pressure_score",
        "monte_carlo_top20_stability_score",
        "regional_spillover_score",
        "forward_2026_ep_risk_score",
        "forward_signal_note",
        "target_year_data_status",
    ]

    display_columns = [column for column in display_columns if column in filtered.columns]

    st.markdown("### Top Intelligence Signals")
    st.dataframe(
        filtered[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    if "ep_intelligence_signal_score" in filtered.columns:
        chart_df = filtered.sort_values(
            "ep_intelligence_signal_score",
            ascending=False,
        ).head(25)

        st.bar_chart(chart_df.set_index("country")["ep_intelligence_signal_score"])

    if "analyst_priority_note" in filtered.columns:
        st.markdown("### Analyst Priority Notes")

        note_columns = [
            "country",
            "ep_intelligence_signal",
            "analyst_priority_note",
        ]
        note_columns = [column for column in note_columns if column in filtered.columns]

        st.dataframe(
            filtered[note_columns].head(15),
            use_container_width=True,
            hide_index=True,
        )


def show_forward_tab(forward: pd.DataFrame):
    st.subheader("2026 Forward Risk Update")

    if forward.empty:
        st.warning("No forward-risk output available.")
        return

    display_columns = [
        "country",
        "baseline_ep_risk_score_2024",
        "baseline_risk_bucket_2024",
        "forward_2026_ep_risk_score",
        "forward_risk_bucket_2026",
        "forward_score_change",
        "forward_risk_change_flag",
        "target_year_data_status",
        "forward_adjustment_note",
    ]

    display_columns = [column for column in display_columns if column in forward.columns]

    st.dataframe(
        forward[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    if "forward_2026_ep_risk_score" in forward.columns:
        chart_df = forward.sort_values(
            "forward_2026_ep_risk_score",
            ascending=False,
        ).head(20)

        st.bar_chart(chart_df.set_index("country")["forward_2026_ep_risk_score"])


def show_monitoring_tab(
    score_changes: pd.DataFrame,
    bucket_changes: pd.DataFrame,
    rank_movers: pd.DataFrame,
):
    st.subheader("Run-to-Run Change Detection")

    if score_changes.empty and bucket_changes.empty and rank_movers.empty:
        st.info(
            "No change-detection results available yet. On the first run, the model "
            "creates a baseline snapshot. Movement tables appear after a later run."
        )
        return

    st.markdown("### Top Rank Movers")

    if not rank_movers.empty:
        st.dataframe(rank_movers, use_container_width=True, hide_index=True)
    else:
        st.info("No rank movers available.")

    st.markdown("### Risk Bucket Changes")

    if not bucket_changes.empty:
        st.dataframe(bucket_changes, use_container_width=True, hide_index=True)
    else:
        st.info("No bucket changes detected.")

    st.markdown("### Score Changes")

    if not score_changes.empty:
        st.dataframe(score_changes.head(50), use_container_width=True, hide_index=True)


def show_sensitivity_tab(sensitivity_overlap: pd.DataFrame):
    st.subheader("Sensitivity Analysis")

    if sensitivity_overlap.empty:
        st.warning("No sensitivity overlap data available.")
        return

    st.dataframe(
        sensitivity_overlap,
        use_container_width=True,
        hide_index=True,
    )

    if "top20_scenario_count" in sensitivity_overlap.columns:
        chart_df = sensitivity_overlap.head(25).set_index("country")[
            "top20_scenario_count"
        ]
        st.bar_chart(chart_df)


def show_monte_carlo_tab(
    monte_carlo_summary: pd.DataFrame,
    monte_carlo_top20: pd.DataFrame,
):
    st.subheader("Monte Carlo Risk Simulation")

    if monte_carlo_summary.empty and monte_carlo_top20.empty:
        st.warning("No Monte Carlo simulation output available.")
        return

    st.write(
        "Monte Carlo simulation tests ranking robustness by randomly perturbing "
        "model component weights around the baseline assumptions."
    )

    if not monte_carlo_top20.empty:
        st.markdown("### Top-20 Probability")

        display_columns = [
            "country",
            "baseline_rank",
            "baseline_score",
            "baseline_bucket",
            "mean_simulated_score",
            "score_volatility",
            "mean_simulated_rank",
            "top20_probability",
            "monte_carlo_stability_flag",
        ]

        display_columns = [
            column for column in display_columns if column in monte_carlo_top20.columns
        ]

        st.dataframe(
            monte_carlo_top20[display_columns],
            use_container_width=True,
            hide_index=True,
        )

        if "top20_probability" in monte_carlo_top20.columns:
            chart_df = monte_carlo_top20.head(25).set_index("country")[
                "top20_probability"
            ]
            st.bar_chart(chart_df)

    if not monte_carlo_summary.empty:
        st.markdown("### Score Volatility")

        volatile = monte_carlo_summary.sort_values(
            "score_volatility",
            ascending=False,
        ).head(25)

        volatility_columns = [
            "country",
            "baseline_rank",
            "baseline_score",
            "mean_simulated_score",
            "score_volatility",
            "score_range",
            "rank_range",
            "top20_probability",
        ]

        volatility_columns = [
            column for column in volatility_columns if column in volatile.columns
        ]

        st.dataframe(
            volatile[volatility_columns],
            use_container_width=True,
            hide_index=True,
        )

        if "score_volatility" in volatile.columns:
            st.bar_chart(volatile.set_index("country")["score_volatility"])


def show_spillover_tab(
    spillover: pd.DataFrame,
    spillover_top: pd.DataFrame,
):
    st.subheader("Regional Spillover Risk")

    if spillover.empty and spillover_top.empty:
        st.warning("No regional spillover output available.")
        return

    st.write(
        "Regional spillover analysis evaluates whether a country's risk profile is "
        "amplified by elevated risk in its broader analytical region."
    )

    display = spillover_top if not spillover_top.empty else spillover

    display_columns = [
        "country",
        "analytical_region",
        "executive_protection_risk_score",
        "risk_bucket",
        "regional_spillover_score",
        "regional_spillover_flag",
        "regional_average_ep_risk_score",
        "regional_max_ep_risk_score",
        "elevated_or_higher_countries",
        "high_or_severe_countries",
        "regional_context_note",
    ]

    display_columns = [column for column in display_columns if column in display.columns]

    st.dataframe(
        display[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    if "regional_spillover_score" in display.columns:
        chart_df = display.sort_values(
            "regional_spillover_score",
            ascending=False,
        ).head(25)

        st.bar_chart(chart_df.set_index("country")["regional_spillover_score"])

    if not spillover.empty and "analytical_region" in spillover.columns:
        st.markdown("### Regional Summary")

        regional_summary = (
            spillover.groupby("analytical_region", as_index=False)
            .agg(
                countries=("country", "count"),
                average_ep_risk=("executive_protection_risk_score", "mean"),
                average_spillover=("regional_spillover_score", "mean"),
                max_spillover=("regional_spillover_score", "max"),
                elevated_or_higher=("elevated_or_higher_countries", "max"),
                high_or_severe=("high_or_severe_countries", "max"),
            )
        )

        regional_summary["average_ep_risk"] = regional_summary[
            "average_ep_risk"
        ].round(2)
        regional_summary["average_spillover"] = regional_summary[
            "average_spillover"
        ].round(2)
        regional_summary["max_spillover"] = regional_summary["max_spillover"].round(2)

        st.dataframe(
            regional_summary.sort_values("average_spillover", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


def show_governance_tab(
    governance: pd.DataFrame,
    assumptions: pd.DataFrame,
    coverage: pd.DataFrame,
):
    st.subheader("Model Governance and Data Coverage")

    if not governance.empty:
        st.markdown("### Governance Summary")
        st.dataframe(governance, use_container_width=True, hide_index=True)

    if not assumptions.empty:
        st.markdown("### Model Assumptions")
        st.dataframe(assumptions, use_container_width=True, hide_index=True)

    if not coverage.empty:
        st.markdown("### Component Coverage")
        st.dataframe(coverage, use_container_width=True, hide_index=True)


def main():
    data = load_data()

    show_header()
    show_report_download()

    show_overview(data["rankings"], data["maturity"])

    tabs = st.tabs(
        [
            "Rankings",
            "Country Profile",
            "Intelligence Signal",
            "Forward Risk",
            "Monitoring",
            "Sensitivity",
            "Monte Carlo",
            "Spillover",
            "Governance",
        ]
    )

    with tabs[0]:
        show_rankings_tab(data["rankings"])

    with tabs[1]:
        show_country_profile_tab(
            data["rankings"],
            data["scenarios"],
            data["forward"],
            data["profiles"],
        )

    with tabs[2]:
        show_intelligence_signal_tab(
            data["intelligence_signals"],
            data["intelligence_signal_top"],
        )

    with tabs[3]:
        show_forward_tab(data["forward"])

    with tabs[4]:
        show_monitoring_tab(
            data["score_changes"],
            data["bucket_changes"],
            data["rank_movers"],
        )

    with tabs[5]:
        show_sensitivity_tab(data["sensitivity_overlap"])

    with tabs[6]:
        show_monte_carlo_tab(
            data["monte_carlo_summary"],
            data["monte_carlo_top20"],
        )

    with tabs[7]:
        show_spillover_tab(
            data["spillover"],
            data["spillover_top"],
        )

    with tabs[8]:
        show_governance_tab(
            data["governance"],
            data["assumptions"],
            data["coverage"],
        )


if __name__ == "__main__":
    main()