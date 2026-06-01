"""
City-Level EP Risk Map Generator

Creates an interactive Plotly HTML map from city-level ACLED protective
intelligence risk features.

Input:
    data/processed/city_ep_risk_features.csv

Output:
    outputs/maps/city_ep_risk_map.html

Run from project root:
    python -m src.city_map_generator
"""

from pathlib import Path

import pandas as pd
import plotly.express as px


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MAPS_DIR = PROJECT_ROOT / "outputs" / "maps"

CITY_FEATURES_FILE = PROCESSED_DATA_DIR / "city_ep_risk_features.csv"
CITY_RISK_MAP_FILE = MAPS_DIR / "city_ep_risk_map.html"


SIGNAL_ORDER = [
    "Severe",
    "High",
    "Elevated",
    "Moderate",
    "Low",
]


SIGNAL_COLORS = {
    "Severe": "#dc2626",
    "High": "#f97316",
    "Elevated": "#facc15",
    "Moderate": "#38bdf8",
    "Low": "#22c55e",
}


def load_city_features() -> pd.DataFrame:
    if not CITY_FEATURES_FILE.exists():
        raise FileNotFoundError(
            f"Could not find city features file at: {CITY_FEATURES_FILE}\n"
            "Run this first:\n"
            "python -m src.acled_city_processing"
        )

    return pd.read_csv(CITY_FEATURES_FILE, low_memory=False)


def prepare_map_data(df: pd.DataFrame, top_n: int = 1000) -> pd.DataFrame:
    """
    Prepare city/location records for geospatial mapping.
    """
    required_cols = [
        "city",
        "country",
        "admin1",
        "avg_latitude",
        "avg_longitude",
        "city_ep_risk_score",
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required map columns: {missing_cols}")

    map_df = df.copy()

    map_df = map_df.dropna(subset=["avg_latitude", "avg_longitude"])
    map_df = map_df[
        (map_df["avg_latitude"].between(-90, 90))
        & (map_df["avg_longitude"].between(-180, 180))
    ]

    map_df = map_df.sort_values("city_ep_risk_score", ascending=False)
    map_df = map_df.head(top_n).copy()

    map_df["map_label"] = (
        map_df["city"].astype(str)
        + ", "
        + map_df["country"].astype(str)
    )

    fallback_cols = {
        "events_30d": 0,
        "events_90d": 0,
        "fatalities_90d": 0,
        "civil_unrest_score": 0,
        "political_violence_score": 0,
        "severity_score": 0,
        "momentum_score": 0,
        "ep_relevance_score": 0,
        "primary_driver": "N/A",
        "signal": "N/A",
    }

    for col, default_value in fallback_cols.items():
        if col not in map_df.columns:
            map_df[col] = default_value

    # Keep marker sizes readable and avoid a few records dominating the map.
    map_df["marker_size"] = map_df["city_ep_risk_score"].clip(lower=8, upper=70)

    return map_df


def create_city_risk_map(top_n: int = 1000) -> Path:
    """
    Create and save an interactive city-level EP risk map.
    """
    print("Loading city EP risk features...")
    df = load_city_features()

    print("Preparing map data...")
    map_df = prepare_map_data(df, top_n=top_n)

    MAPS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Creating map with top {len(map_df):,} city/location records...")

    fig = px.scatter_geo(
        map_df,
        lat="avg_latitude",
        lon="avg_longitude",
        size="marker_size",
        color="signal",
        category_orders={"signal": SIGNAL_ORDER},
        color_discrete_map=SIGNAL_COLORS,
        hover_name="map_label",
        hover_data={
            "admin1": True,
            "events_30d": True,
            "events_90d": True,
            "fatalities_90d": True,
            "city_ep_risk_score": ":.2f",
            "civil_unrest_score": ":.2f",
            "political_violence_score": ":.2f",
            "severity_score": ":.2f",
            "momentum_score": ":.2f",
            "ep_relevance_score": ":.2f",
            "primary_driver": True,
            "marker_size": False,
            "avg_latitude": False,
            "avg_longitude": False,
        },
        projection="natural earth",
        title="City-Level Executive Protection Risk Map",
        size_max=18,
        opacity=0.78,
    )

    fig.update_traces(
        marker=dict(
            line=dict(width=0.6, color="rgba(255,255,255,0.75)")
        )
    )

    fig.update_geos(
        showland=True,
        landcolor="#111827",
        showocean=True,
        oceancolor="#0f172a",
        showcountries=True,
        countrycolor="#475569",
        showcoastlines=True,
        coastlinecolor="#64748b",
        showframe=False,
        bgcolor="#020617",
        lataxis_showgrid=False,
        lonaxis_showgrid=False,
        projection_scale=1.12,
        center=dict(lat=8, lon=10),
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#020617",
        plot_bgcolor="#020617",
        height=620,
        autosize=True,
        margin=dict(l=10, r=10, t=55, b=85),
        title=dict(
            text="City-Level Executive Protection Risk Map",
            x=0.02,
            y=0.96,
            xanchor="left",
            yanchor="top",
            font=dict(size=22),
        ),
        legend=dict(
            title="City Risk Signal",
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(2,6,23,0.90)",
            bordercolor="rgba(148,163,184,0.45)",
            borderwidth=1,
            font=dict(size=12),
            title_font=dict(size=12),
        ),
        font=dict(
            family="Arial",
            size=12,
            color="#e5e7eb",
        ),
    )

    fig.write_html(
        CITY_RISK_MAP_FILE,
        include_plotlyjs="cdn",
        full_html=True,
        config={
            "displayModeBar": True,
            "responsive": True,
            "scrollZoom": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": [
                "lasso2d",
                "select2d",
            ],
        },
    )

    print(f"City EP risk map saved to: {CITY_RISK_MAP_FILE}")

    return CITY_RISK_MAP_FILE


if __name__ == "__main__":
    create_city_risk_map()
