from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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


PROJECT_ROOT = Path(__file__).resolve().parent

CITY_EP_RISK_FEATURES_FILE = (
    PROJECT_ROOT / "data" / "processed" / "city_ep_risk_features.csv"
)

TOP_CITY_EP_RISK_RANKINGS_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_25_city_ep_risk_rankings.csv"
)

TOP_20_CITY_RISK_CHART = (
    PROJECT_ROOT / "outputs" / "charts" / "top_20_city_ep_risk_rankings.png"
)

CITY_COMPONENT_BREAKDOWN_CHART = (
    PROJECT_ROOT / "outputs" / "charts" / "top_15_city_risk_component_breakdown.png"
)

CITY_RISK_MAP_FILE = (
    PROJECT_ROOT / "outputs" / "maps" / "city_ep_risk_map.html"
)

CITY_ACCESS_PROXY_FILE = (
    PROJECT_ROOT / "data" / "processed" / "city_access_proxy_features.csv"
)

TOP_OPERATIONAL_RISK_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_25_city_operational_risk_rankings.csv"
)

PROTECTIVE_INTELLIGENCE_TRIP_SCORES_FILE = (
    PROJECT_ROOT / "data" / "processed" / "protective_intelligence_trip_scores.csv"
)

TOP_PROTECTIVE_INTELLIGENCE_PRIORITIES_FILE = (
    PROJECT_ROOT / "outputs" / "tables" / "top_protective_intelligence_priorities.csv"
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
        "city_features": read_csv_if_exists(CITY_EP_RISK_FEATURES_FILE),
        "top_city_rankings": read_csv_if_exists(TOP_CITY_EP_RISK_RANKINGS_FILE),
        "city_access": read_csv_if_exists(CITY_ACCESS_PROXY_FILE),
        "top_operational_city_rankings": read_csv_if_exists(TOP_OPERATIONAL_RISK_FILE),
        "pi_trip_scores": read_csv_if_exists(PROTECTIVE_INTELLIGENCE_TRIP_SCORES_FILE),
        "top_pi_priorities": read_csv_if_exists(TOP_PROTECTIVE_INTELLIGENCE_PRIORITIES_FILE),
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
        st.warning("Risk rankings file not found. Run `python main.py` first.")
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


def show_city_risk_tab(
    city_features: pd.DataFrame,
    top_city_rankings: pd.DataFrame,
    city_access: pd.DataFrame,
    top_operational_city_rankings: pd.DataFrame,
):
    st.subheader("City-Level Protective Intelligence Rankings")

    if city_features.empty:
        st.warning(
            "No city-level ACLED output available. Run "
            "`python -m src.acled_city_processing` or `python main.py` first."
        )
        return

    st.write(
        "This module ranks ACLED city/location records by recent civil unrest, "
        "political violence, severity, event momentum, and EP-relevant exposure."
    )

    display = city_features.copy()

    if "city_ep_risk_score" in display.columns:
        display = display.sort_values("city_ep_risk_score", ascending=False)

    col1, col2, col3, col4 = st.columns(4)

    top_row = display.iloc[0]

    col1.metric("City/Locations Ranked", f"{len(display):,}")
    col2.metric("Highest Risk Location", str(top_row.get("city", "N/A")))
    col3.metric("Country", str(top_row.get("country", "N/A")))
    col4.metric("Top City EP Score", format_score(top_row.get("city_ep_risk_score")))

    st.markdown("### Filters")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    if "country" in display.columns:
        country_options = ["All"] + sorted(display["country"].dropna().unique().tolist())
    else:
        country_options = ["All"]

    selected_country = filter_col1.selectbox("Filter by country", country_options)

    signal_options = ["All"]
    if "signal" in display.columns:
        signal_options += sorted(display["signal"].dropna().unique().tolist())

    selected_signal = filter_col2.selectbox("Filter by city risk signal", signal_options)

    top_n = filter_col3.slider("Number of city/location rows", 10, 100, 25)

    filtered = display.copy()

    if selected_country != "All" and "country" in filtered.columns:
        filtered = filtered[filtered["country"] == selected_country]

    if selected_signal != "All" and "signal" in filtered.columns:
        filtered = filtered[filtered["signal"] == selected_signal]

    if filtered.empty:
        st.info("No city/location rows match the selected filters.")
        return

    st.markdown("### City Risk Rankings")

    display_columns = [
        "rank",
        "city",
        "country",
        "admin1",
        "admin2",
        "events_30d",
        "events_90d",
        "fatalities_90d",
        "protests_90d",
        "riots_90d",
        "violence_against_civilians_90d",
        "civil_unrest_score",
        "political_violence_score",
        "severity_score",
        "momentum_score",
        "ep_relevance_score",
        "city_ep_risk_score",
        "signal",
        "primary_driver",
    ]

    display_columns = [column for column in display_columns if column in filtered.columns]

    st.dataframe(
        filtered[display_columns].head(top_n),
        use_container_width=True,
        hide_index=True,
    )

    csv_data = filtered[display_columns].to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Filtered City Risk Rankings",
        data=csv_data,
        file_name="filtered_city_ep_risk_rankings.csv",
        mime="text/csv",
    )

    if "city_ep_risk_score" in filtered.columns:
        st.markdown("### City EP Risk Score Chart")

        chart_df = filtered.sort_values(
            "city_ep_risk_score",
            ascending=False,
        ).head(top_n).copy()

        if "city" in chart_df.columns and "country" in chart_df.columns:
            chart_df["city_label"] = (
                chart_df["city"].astype(str) + ", " + chart_df["country"].astype(str)
            )
            st.bar_chart(chart_df.set_index("city_label")["city_ep_risk_score"])

    st.markdown("### City Risk Components")

    component_columns = [
        "civil_unrest_score",
        "political_violence_score",
        "severity_score",
        "momentum_score",
        "ep_relevance_score",
    ]

    available_components = [
        column for column in component_columns if column in filtered.columns
    ]

    if available_components:
        city_selector_df = filtered.head(500).copy()

        city_selector_df["city_selection_label"] = (
            city_selector_df["city"].astype(str)
            + ", "
            + city_selector_df["country"].astype(str)
            + " | "
            + city_selector_df["admin1"].astype(str)
            + " | Rank "
            + city_selector_df["rank"].astype(str)
        )

        selected_city_label = st.selectbox(
            "Select city/location for component view",
            city_selector_df["city_selection_label"].tolist(),
        )

        selected_row = city_selector_df[
            city_selector_df["city_selection_label"] == selected_city_label
        ].iloc[0]

        component_labels = {
            "civil_unrest_score": "Civil Unrest",
            "political_violence_score": "Political Violence",
            "severity_score": "Severity",
            "momentum_score": "Recent Momentum",
            "ep_relevance_score": "EP-Relevant Exposure",
        }

        component_df = pd.DataFrame(
            {
                "component": [component_labels[column] for column in available_components],
                "score": [selected_row.get(column) for column in available_components],
            }
        )

        st.dataframe(component_df, use_container_width=True, hide_index=True)
        st.bar_chart(component_df.set_index("component")["score"])

        st.markdown("### Selected City / Location Detail")

        detail_columns = [
            "rank",
            "city",
            "country",
            "admin1",
            "admin2",
            "total_events",
            "events_30d",
            "events_60d",
            "events_90d",
            "events_180d",
            "fatalities_30d",
            "fatalities_90d",
            "civil_unrest_90d",
            "political_violence_90d",
            "protests_90d",
            "riots_90d",
            "violence_against_civilians_90d",
            "event_momentum_ratio",
            "fatality_momentum_ratio",
            "city_ep_risk_score",
            "signal",
            "primary_driver",
        ]

        detail_columns = [
            column for column in detail_columns if column in selected_row.index
        ]

        detail_df = pd.DataFrame(
            [
                {
                    "indicator": column,
                    "value": selected_row.get(column),
                }
                for column in detail_columns
            ]
        )

        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    st.markdown("### Access & Support Proxy Layer")

    if city_access.empty:
        st.info(
            "Access proxy output not found. Run `python -m src.access_proxy_layer` "
            "or `python main.py` first."
        )
    else:
        access_display = city_access.copy()

        if selected_country != "All" and "country" in access_display.columns:
            access_display = access_display[
                access_display["country"] == selected_country
            ]

        if "city_operational_ep_risk_score" in access_display.columns:
            access_display = access_display.sort_values(
                "city_operational_ep_risk_score",
                ascending=False,
            )

        if access_display.empty:
            st.info("No access proxy rows match the selected country filter.")
        else:
            access_col1, access_col2, access_col3, access_col4 = st.columns(4)

            access_top = access_display.iloc[0]

            access_col1.metric(
                "Top Operational Risk Location",
                str(access_top.get("city", "N/A")),
            )
            access_col2.metric(
                "Operational EP Score",
                format_score(access_top.get("city_operational_ep_risk_score")),
            )
            access_col3.metric(
                "Support Gap Score",
                format_score(access_top.get("support_gap_score")),
            )
            access_col4.markdown("**Operational Signal**")
            access_col4.markdown(
                f"""
                <div style="
                    font-size: 1.45rem;
                    line-height: 1.25;
                    font-weight: 500;
                    color: #fafafa;
                    white-space: normal;
                    word-break: normal;
                    overflow-wrap: break-word;
                ">
                    {access_top.get("operational_ep_signal", "N/A")}
                </div>
                """,
                unsafe_allow_html=True,
            )

            operational_columns = [
                "operational_rank",
                "city",
                "country",
                "admin1",
                "city_ep_risk_score",
                "nearest_airport_name",
                "nearest_airport_iata",
                "nearest_airport_km",
                "airport_access_score",
                "airport_access_status",
                "hospital_beds_per_1000",
                "physicians_per_1000",
                "medical_capacity_score",
                "medical_capacity_status",
                "support_access_score",
                "support_gap_score",
                "city_operational_ep_risk_score",
                "operational_ep_signal",
            ]

            operational_columns = [
                column for column in operational_columns
                if column in access_display.columns
            ]

            st.dataframe(
                access_display[operational_columns].head(top_n),
                use_container_width=True,
                hide_index=True,
            )

            if "city_operational_ep_risk_score" in access_display.columns:
                operational_chart_df = access_display.head(top_n).copy()

                operational_chart_df["city_label"] = (
                    operational_chart_df["city"].astype(str)
                    + ", "
                    + operational_chart_df["country"].astype(str)
                )

                st.markdown("### Access-Adjusted Operational EP Risk Chart")
                st.bar_chart(
                    operational_chart_df.set_index("city_label")[
                        "city_operational_ep_risk_score"
                    ]
                )

            access_csv = (
                access_display[operational_columns]
                .to_csv(index=False)
                .encode("utf-8")
            )

            st.download_button(
                label="Download Access-Adjusted City Risk Rankings",
                data=access_csv,
                file_name="access_adjusted_city_operational_risk_rankings.csv",
                mime="text/csv",
            )

        if not top_operational_city_rankings.empty:
            st.markdown("### Top 25 Access-Adjusted Operational City Rankings")

            top_operational_columns = [
                "operational_rank",
                "city",
                "country",
                "admin1",
                "city_ep_risk_score",
                "airport_access_score",
                "medical_capacity_score",
                "support_access_score",
                "support_gap_score",
                "city_operational_ep_risk_score",
                "operational_ep_signal",
            ]

            top_operational_columns = [
                column for column in top_operational_columns
                if column in top_operational_city_rankings.columns
            ]

            st.dataframe(
                top_operational_city_rankings[top_operational_columns],
                use_container_width=True,
                hide_index=True,
            )

        st.info(
            "The access proxy layer combines airport access and country-level medical "
            "capacity indicators into a support-access score. The access-adjusted "
            "operational EP score increases when city risk is high and support access "
            "is constrained. This is a planning-support proxy, not a medical or tactical "
            "assessment."
        )

    st.markdown("### Geospatial City Risk Map")

    if CITY_RISK_MAP_FILE.exists():
        with open(CITY_RISK_MAP_FILE, "r", encoding="utf-8") as map_file:
            map_html = map_file.read()

        components.html(map_html, height=760, scrolling=False)
    else:
        st.info(
            "City risk map not found. Run `python -m src.city_map_generator` "
            "or `python main.py` first."
        )

    st.markdown("### Saved City-Level Charts")

    chart_col1, chart_col2 = st.columns(2)

    if TOP_20_CITY_RISK_CHART.exists():
        chart_col1.image(
            str(TOP_20_CITY_RISK_CHART),
            caption="Top 20 City-Level EP Risk Rankings",
            use_container_width=True,
        )
    else:
        chart_col1.info("Top 20 city risk chart not found.")

    if CITY_COMPONENT_BREAKDOWN_CHART.exists():
        chart_col2.image(
            str(CITY_COMPONENT_BREAKDOWN_CHART),
            caption="Top 15 City Risk Component Breakdown",
            use_container_width=True,
        )
    else:
        chart_col2.info("City component breakdown chart not found.")

    st.markdown("### Top 25 City Risk Table")

    if not top_city_rankings.empty:
        top_display_columns = [
            "rank",
            "city",
            "country",
            "admin1",
            "events_90d",
            "fatalities_90d",
            "city_ep_risk_score",
            "signal",
            "primary_driver",
        ]

        top_display_columns = [
            column for column in top_display_columns
            if column in top_city_rankings.columns
        ]

        st.dataframe(
            top_city_rankings[top_display_columns],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Methodology Note")

    st.info(
        "ACLED location names are treated as city/location-level records. Some entries "
        "may represent neighborhoods, towns, villages, districts, or event locations rather "
        "than formal city boundaries. This module should be interpreted as a protective "
        "intelligence screening layer, not a predictive threat model."
    )



def show_pi_posture_tab(
    pi_trip_scores: pd.DataFrame,
    top_pi_priorities: pd.DataFrame,
):
    st.subheader("Protective Intelligence Posture")

    if pi_trip_scores.empty and top_pi_priorities.empty:
        st.warning(
            "No Protective Intelligence posture output available. Run "
            "`python -m src.protective_intelligence_score` or `python main.py` first."
        )
        return

    st.write(
        "This layer combines city risk, support-access constraints, trip exposure, "
        "movement predictability, venue/hotel/airport exposure, online visibility, "
        "and reputational or business sensitivity into a decision-support score."
    )

    display = top_pi_priorities.copy() if not top_pi_priorities.empty else pi_trip_scores.copy()

    if "protective_intelligence_risk_score" in display.columns:
        display = display.sort_values(
            "protective_intelligence_risk_score",
            ascending=False,
        )

    if display.empty:
        st.info("No Protective Intelligence posture rows available.")
        return

    top_row = display.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Trips Scored", f"{len(display):,}")
    col2.metric("Top PI Location", str(top_row.get("city", "N/A")))
    col3.metric(
        "Top PI Score",
        format_score(top_row.get("protective_intelligence_risk_score")),
    )
    col4.markdown("**Recommended Posture**")
    col4.markdown(
        f"""
        <div style="
            font-size: 1.25rem;
            line-height: 1.25;
            font-weight: 500;
            color: #fafafa;
            white-space: normal;
            word-break: normal;
            overflow-wrap: break-word;
        ">
            {top_row.get("protective_posture_recommendation", "N/A")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Filters")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    scenario_options = ["All"]
    if "scenario" in display.columns:
        scenario_options += sorted(display["scenario"].dropna().unique().tolist())

    selected_scenario = filter_col1.selectbox(
        "Filter by scenario",
        scenario_options,
        key="pi_scenario_filter",
    )

    signal_options = ["All"]
    if "protective_intelligence_signal" in display.columns:
        signal_options += sorted(
            display["protective_intelligence_signal"].dropna().unique().tolist()
        )

    selected_signal = filter_col2.selectbox(
        "Filter by PI signal",
        signal_options,
        key="pi_signal_filter",
    )

    posture_options = ["All"]
    if "protective_posture_recommendation" in display.columns:
        posture_options += sorted(
            display["protective_posture_recommendation"].dropna().unique().tolist()
        )

    selected_posture = filter_col3.selectbox(
        "Filter by posture",
        posture_options,
        key="pi_posture_filter",
    )

    top_n = filter_col4.slider(
        "Number of PI rows",
        3,
        50,
        min(10, max(3, len(display))),
        key="pi_top_n_slider",
    )

    filtered = display.copy()

    if selected_scenario != "All" and "scenario" in filtered.columns:
        filtered = filtered[filtered["scenario"] == selected_scenario]

    if selected_signal != "All" and "protective_intelligence_signal" in filtered.columns:
        filtered = filtered[
            filtered["protective_intelligence_signal"] == selected_signal
        ]

    if selected_posture != "All" and "protective_posture_recommendation" in filtered.columns:
        filtered = filtered[
            filtered["protective_posture_recommendation"] == selected_posture
        ]

    if filtered.empty:
        st.info("No Protective Intelligence rows match the selected filters.")
        return

    st.markdown("### Protective Intelligence Priority Rankings")

    display_columns = [
        "pi_priority_rank",
        "trip_id",
        "principal",
        "city",
        "country",
        "scenario",
        "visibility_level",
        "travel_predictability",
        "venue_exposure",
        "hotel_airport_exposure",
        "online_visibility",
        "city_ep_risk_score",
        "support_gap_score",
        "protective_intelligence_base_score",
        "scenario_multiplier",
        "protective_intelligence_risk_score",
        "protective_intelligence_signal",
        "protective_posture_recommendation",
        "city_context_match_flag",
    ]

    display_columns = [column for column in display_columns if column in filtered.columns]

    st.dataframe(
        filtered[display_columns].head(top_n),
        use_container_width=True,
        hide_index=True,
    )

    csv_data = filtered[display_columns].to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download Protective Intelligence Priorities",
        data=csv_data,
        file_name="protective_intelligence_priorities.csv",
        mime="text/csv",
    )

    if "protective_intelligence_risk_score" in filtered.columns:
        st.markdown("### Protective Intelligence Risk Score Chart")

        chart_df = filtered.sort_values(
            "protective_intelligence_risk_score",
            ascending=False,
        ).head(top_n).copy()

        label_parts = []
        if "trip_id" in chart_df.columns:
            label_parts.append(chart_df["trip_id"].astype(str))
        if "city" in chart_df.columns:
            label_parts.append(chart_df["city"].astype(str))
        if "country" in chart_df.columns:
            label_parts.append(chart_df["country"].astype(str))

        if label_parts:
            chart_df["trip_label"] = label_parts[0]
            for part in label_parts[1:]:
                chart_df["trip_label"] = chart_df["trip_label"] + " | " + part
        else:
            chart_df["trip_label"] = chart_df.index.astype(str)

        st.bar_chart(
            chart_df.set_index("trip_label")["protective_intelligence_risk_score"]
        )

    st.markdown("### Trip Exposure Component View")

    selector_df = filtered.head(500).copy()

    if "trip_id" in selector_df.columns:
        selector_df["trip_selection_label"] = (
            selector_df["trip_id"].astype(str)
            + " | "
            + selector_df.get("principal", pd.Series("N/A", index=selector_df.index)).astype(str)
            + " | "
            + selector_df.get("city", pd.Series("N/A", index=selector_df.index)).astype(str)
            + ", "
            + selector_df.get("country", pd.Series("N/A", index=selector_df.index)).astype(str)
        )
    else:
        selector_df["trip_selection_label"] = selector_df.index.astype(str)

    selected_trip_label = st.selectbox(
        "Select trip / principal movement for component view",
        selector_df["trip_selection_label"].tolist(),
        key="pi_trip_selector",
    )

    selected_row = selector_df[
        selector_df["trip_selection_label"] == selected_trip_label
    ].iloc[0]

    component_columns = [
        "local_threat_environment_score",
        "principal_exposure_score",
        "movement_predictability_score",
        "venue_airport_hotel_exposure_score",
        "online_information_leakage_score",
        "support_gap_score",
        "reputational_business_sensitivity_score",
    ]

    component_labels = {
        "local_threat_environment_score": "Local Threat Environment",
        "principal_exposure_score": "Principal Exposure",
        "movement_predictability_score": "Movement Predictability",
        "venue_airport_hotel_exposure_score": "Venue / Airport / Hotel Exposure",
        "online_information_leakage_score": "Online / Information Leakage",
        "support_gap_score": "Medical / Evacuation Constraints",
        "reputational_business_sensitivity_score": "Reputational / Business Sensitivity",
    }

    available_components = [
        column for column in component_columns if column in selected_row.index
    ]

    if available_components:
        component_df = pd.DataFrame(
            {
                "component": [component_labels[column] for column in available_components],
                "score": [selected_row.get(column) for column in available_components],
            }
        )

        st.dataframe(component_df, use_container_width=True, hide_index=True)
        st.bar_chart(component_df.set_index("component")["score"])

    st.markdown("### Selected PI Movement Detail")

    detail_columns = [
        "pi_priority_rank",
        "trip_id",
        "principal",
        "city",
        "country",
        "scenario",
        "visibility_level",
        "travel_predictability",
        "venue_exposure",
        "hotel_airport_exposure",
        "online_visibility",
        "reputational_sensitivity",
        "business_sector_sensitivity",
        "city_ep_risk_score",
        "signal",
        "primary_driver",
        "nearest_airport_name",
        "nearest_airport_iata",
        "nearest_airport_km",
        "airport_access_status",
        "medical_capacity_status",
        "support_access_score",
        "support_gap_score",
        "protective_intelligence_base_score",
        "scenario_multiplier",
        "protective_intelligence_risk_score",
        "protective_intelligence_signal",
        "protective_posture_recommendation",
        "analyst_priority_note",
        "city_context_match_flag",
    ]

    detail_columns = [column for column in detail_columns if column in selected_row.index]

    detail_df = pd.DataFrame(
        [
            {
                "indicator": column,
                "value": selected_row.get(column),
            }
            for column in detail_columns
        ]
    )

    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    if "analyst_priority_note" in selected_row.index:
        st.markdown("### Analyst Priority Note")
        st.info(str(selected_row.get("analyst_priority_note", "N/A")))

    st.markdown("### Methodology Note")

    st.info(
        "The Protective Intelligence posture score is a decision-support screening "
        "indicator. It combines external city risk, support-access constraints, and "
        "trip/principal exposure assumptions. It should not be interpreted as a tactical "
        "protection plan, route approval, or real-world incident probability forecast."
    )

def show_intelligence_signal_tab(
    intelligence_signals: pd.DataFrame,
    intelligence_signal_top: pd.DataFrame,
):
    st.subheader("Executive Protection Intelligence Signal")

    if intelligence_signals.empty and intelligence_signal_top.empty:
        st.warning(
            "No intelligence signal output available. Run `python -m src.intelligence_signal` "
            "or `python main.py` first."
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
            "City Risk",
            "PI Posture",
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
        show_city_risk_tab(
            data["city_features"],
            data["top_city_rankings"],
            data["city_access"],
            data["top_operational_city_rankings"],
        )

    with tabs[3]:
        show_pi_posture_tab(
            data["pi_trip_scores"],
            data["top_pi_priorities"],
        )

    with tabs[4]:
        show_intelligence_signal_tab(
            data["intelligence_signals"],
            data["intelligence_signal_top"],
        )

    with tabs[5]:
        show_forward_tab(data["forward"])

    with tabs[6]:
        show_monitoring_tab(
            data["score_changes"],
            data["bucket_changes"],
            data["rank_movers"],
        )

    with tabs[7]:
        show_sensitivity_tab(data["sensitivity_overlap"])

    with tabs[8]:
        show_monte_carlo_tab(
            data["monte_carlo_summary"],
            data["monte_carlo_top20"],
        )

    with tabs[9]:
        show_spillover_tab(
            data["spillover"],
            data["spillover_top"],
        )

    with tabs[10]:
        show_governance_tab(
            data["governance"],
            data["assumptions"],
            data["coverage"],
        )


if __name__ == "__main__":
    main()