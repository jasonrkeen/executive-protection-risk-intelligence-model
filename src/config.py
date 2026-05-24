from pathlib import Path

# =========================
# Project metadata
# =========================

PROJECT_TITLE = "A Quantitative OSINT Model for Executive Protection Risk in Global Energy Operations"
PROJECT_SUBTITLE = (
    "Country-level risk intelligence for executive travel, site visits, "
    "corporate events, and energy-sector security planning"
)

AUTHOR_NAME = "Jason Keen"
AUTHOR_EMAIL = "keenjasonr@gmail.com"

STUDY_YEAR = 2024
START_YEAR = 2020
END_YEAR = 2024

# =========================
# Directories
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

OUTPUTS_DIR = BASE_DIR / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"
TABLES_DIR = OUTPUTS_DIR / "tables"
REPORTS_DIR = OUTPUTS_DIR / "reports"

# Country profile markdown outputs
COUNTRY_PROFILES_DIR = REPORTS_DIR / "country_profiles"

for directory in [
    RAW_DIR,
    PROCESSED_DIR,
    CHARTS_DIR,
    TABLES_DIR,
    REPORTS_DIR,
    COUNTRY_PROFILES_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

# =========================
# File paths
# =========================

WORLD_BANK_FILE = PROCESSED_DIR / "worldbank_ep_indicators.csv"

ACLED_RAW_FILE = RAW_DIR / "acled_events.csv"
ACLED_CHECKPOINT_FILE = RAW_DIR / "acled_events_checkpoint.csv"
ACLED_COUNTRY_FILE = PROCESSED_DIR / "acled_country_risk_features.csv"

CRIME_FILE = RAW_DIR / "homicide_rate.csv"
CRIME_PROCESSED_FILE = PROCESSED_DIR / "crime_features.csv"

ENERGY_FILE = PROCESSED_DIR / "energy_exposure_features.csv"
MASTER_DATA_FILE = PROCESSED_DIR / "executive_protection_master_dataset.csv"

RISK_RANKINGS_FILE = TABLES_DIR / "executive_protection_risk_rankings.csv"
SCENARIO_FILE = TABLES_DIR / "scenario_risk_results.csv"

REPORT_FILE = REPORTS_DIR / "executive_protection_risk_intelligence_report.pdf"

# Country profile outputs
COUNTRY_PROFILE_SUMMARY_FILE = TABLES_DIR / "country_profile_summaries.csv"

# =========================
# Diagnostics outputs
# =========================

MODEL_DIAGNOSTICS_FILE = TABLES_DIR / "model_diagnostics_summary.csv"
MODEL_COMPONENT_MATURITY_FILE = TABLES_DIR / "model_component_maturity.csv"
MODEL_MATURITY_FILE = TABLES_DIR / "model_maturity_summary.csv"
MISSING_VALUES_FILE = TABLES_DIR / "master_dataset_missing_values.csv"
MODEL_COMPONENT_COVERAGE_FILE = TABLES_DIR / "model_component_coverage_summary.csv"

# =========================
# Model governance outputs
# =========================

MODEL_GOVERNANCE_FILE = TABLES_DIR / "model_governance_summary.csv"
MODEL_ASSUMPTIONS_FILE = TABLES_DIR / "model_assumptions_summary.csv"

# =========================
# Sensitivity analysis outputs
# =========================

SENSITIVITY_RANKINGS_FILE = TABLES_DIR / "sensitivity_rankings.csv"
SENSITIVITY_TOP20_FILE = TABLES_DIR / "sensitivity_top_20_by_scenario.csv"
SENSITIVITY_OVERLAP_FILE = TABLES_DIR / "sensitivity_top_20_overlap.csv"
SENSITIVITY_SUMMARY_FILE = TABLES_DIR / "sensitivity_summary.csv"
SENSITIVITY_OVERLAP_CHART = CHARTS_DIR / "sensitivity_top20_overlap.png"

# =========================
# Monte Carlo simulation outputs
# =========================

MONTE_CARLO_SIMULATION_FILE = TABLES_DIR / "monte_carlo_risk_simulation.csv"
MONTE_CARLO_COUNTRY_SUMMARY_FILE = TABLES_DIR / "monte_carlo_country_summary.csv"
MONTE_CARLO_TOP20_PROBABILITY_FILE = TABLES_DIR / "monte_carlo_top20_probability.csv"
MONTE_CARLO_SCORE_DISTRIBUTION_CHART = CHARTS_DIR / "monte_carlo_score_distribution.png"
MONTE_CARLO_TOP20_PROBABILITY_CHART = CHARTS_DIR / "monte_carlo_top20_probability.png"

MONTE_CARLO_SIMULATIONS = 1000
MONTE_CARLO_RANDOM_SEED = 42

# =========================
# Scenario analysis outputs
# =========================

SCENARIO_TOP_COUNTRIES_FILE = TABLES_DIR / "scenario_top_countries.csv"
SCENARIO_SUMMARY_FILE = TABLES_DIR / "scenario_summary.csv"

# =========================
# Change detection outputs
# =========================

RISK_RANKINGS_SNAPSHOT_FILE = TABLES_DIR / "executive_protection_risk_rankings_previous.csv"
RISK_SCORE_CHANGES_FILE = TABLES_DIR / "risk_score_changes.csv"
RISK_BUCKET_CHANGES_FILE = TABLES_DIR / "risk_bucket_changes.csv"
TOP_RANK_MOVERS_FILE = TABLES_DIR / "top_rank_movers.csv"

# =========================
# Regional spillover outputs
# =========================

REGIONAL_SPILLOVER_FILE = TABLES_DIR / "regional_spillover_scores.csv"
REGIONAL_SPILLOVER_TOP_COUNTRIES_FILE = TABLES_DIR / "regional_spillover_top_countries.csv"
REGIONAL_SPILLOVER_CHART = CHARTS_DIR / "regional_spillover_top_countries.png"

# =========================
# Intelligence signal outputs
# =========================

INTELLIGENCE_SIGNAL_FILE = TABLES_DIR / "executive_protection_intelligence_signals.csv"
INTELLIGENCE_SIGNAL_TOP_COUNTRIES_FILE = TABLES_DIR / "top_intelligence_signal_countries.csv"
INTELLIGENCE_SIGNAL_CHART = CHARTS_DIR / "executive_protection_intelligence_signals.png"

# =========================
# 2026 Forward Risk Update files
# =========================

FORWARD_ACLED_EVENTS_FILE = RAW_DIR / "acled_2025_2026_forward_events.csv"
ACLED_FORWARD_TRENDS_FILE = PROCESSED_DIR / "acled_2025_2026_country_trends.csv"
FORWARD_2026_RISK_FILE = TABLES_DIR / "forward_2026_risk_scores.csv"
FORWARD_2026_TOP_CHANGES_FILE = TABLES_DIR / "forward_2026_top_risk_changes.csv"

# =========================
# World Bank indicators
# =========================

# WGI indicators use source=75 in the World Bank API.
WGI_SOURCE = 75

WGI_INDICATORS = {
    "PV.EST": "political_stability",
    "RL.EST": "rule_of_law",
    "CC.EST": "control_of_corruption",
    "GE.EST": "government_effectiveness",
    "VA.EST": "voice_accountability",
}

ECONOMIC_INDICATORS = {
    "NY.GDP.PCAP.CD": "gdp_per_capita",
    "SP.POP.TOTL": "population",
    "SP.URB.TOTL.IN.ZS": "urban_population_pct",
    "NY.GDP.PETR.RT.ZS": "oil_rents_pct_gdp",
    "NY.GDP.NGAS.RT.ZS": "natural_gas_rents_pct_gdp",
    "TX.VAL.FUEL.ZS.UN": "fuel_exports_pct_merchandise_exports",
}

CRIME_INDICATORS = {
    "VC.IHR.PSRC.P5": "homicide_rate_per_100k",
}

# =========================
# ACLED API settings
# =========================

ACLED_API_BASE_URL = "https://acleddata.com/api/acled/read"
ACLED_OAUTH_URL = "https://acleddata.com/oauth/token"

ACLED_API_LIMIT = 5000

ACLED_API_FIELDS = [
    "event_id_cnty",
    "event_date",
    "year",
    "disorder_type",
    "event_type",
    "sub_event_type",
    "country",
    "admin1",
    "admin2",
    "location",
    "latitude",
    "longitude",
    "fatalities",
]

ACLED_EVENT_TYPES = [
    "Protests",
    "Riots",
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
]

# =========================
# 2026 Forward ACLED settings
# =========================

FORWARD_ACLED_FIELDS = [
    "event_id_cnty",
    "event_date",
    "year",
    "event_type",
    "sub_event_type",
    "country",
    "admin1",
    "admin2",
    "location",
    "fatalities",
]

FORWARD_ACLED_EVENT_TYPES = [
    "Protests",
    "Riots",
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
]

# =========================
# Risk score weights
# =========================

RISK_WEIGHTS = {
    "civil_unrest_political_violence_score": 0.35,
    "governance_risk_score": 0.20,
    "violent_crime_score": 0.15,
    "energy_exposure_score": 0.20,
    "recent_risk_momentum_score": 0.10,
}

RISK_BUCKETS = [
    (0, 25, "Low"),
    (25, 50, "Moderate"),
    (50, 70, "Elevated"),
    (70, 85, "High"),
    (85, 101, "Severe"),
]

# =========================
# Sensitivity assumptions
# =========================

SENSITIVITY_SCENARIOS = {
    "baseline": {
        "civil_unrest_political_violence_score": 0.35,
        "governance_risk_score": 0.20,
        "violent_crime_score": 0.15,
        "energy_exposure_score": 0.20,
        "recent_risk_momentum_score": 0.10,
    },
    "equal_weight": {
        "civil_unrest_political_violence_score": 0.20,
        "governance_risk_score": 0.20,
        "violent_crime_score": 0.20,
        "energy_exposure_score": 0.20,
        "recent_risk_momentum_score": 0.20,
    },
    "civil_unrest_heavy": {
        "civil_unrest_political_violence_score": 0.50,
        "governance_risk_score": 0.15,
        "violent_crime_score": 0.10,
        "energy_exposure_score": 0.15,
        "recent_risk_momentum_score": 0.10,
    },
    "governance_heavy": {
        "civil_unrest_political_violence_score": 0.25,
        "governance_risk_score": 0.40,
        "violent_crime_score": 0.15,
        "energy_exposure_score": 0.15,
        "recent_risk_momentum_score": 0.05,
    },
    "crime_heavy": {
        "civil_unrest_political_violence_score": 0.25,
        "governance_risk_score": 0.15,
        "violent_crime_score": 0.35,
        "energy_exposure_score": 0.15,
        "recent_risk_momentum_score": 0.10,
    },
    "energy_exposure_heavy": {
        "civil_unrest_political_violence_score": 0.25,
        "governance_risk_score": 0.15,
        "violent_crime_score": 0.10,
        "energy_exposure_score": 0.40,
        "recent_risk_momentum_score": 0.10,
    },
    "recent_momentum_heavy": {
        "civil_unrest_political_violence_score": 0.25,
        "governance_risk_score": 0.15,
        "violent_crime_score": 0.10,
        "energy_exposure_score": 0.15,
        "recent_risk_momentum_score": 0.35,
    },
}

# =========================
# Scenario assumptions
# =========================

SCENARIO_MULTIPLIERS = {
    "routine_executive_travel": 1.00,
    "public_energy_event": 1.15,
    "site_visit_to_energy_asset": 1.20,
    "travel_during_civil_unrest": 1.35,
    "high_visibility_executive_visit": 1.40,
    "major_energy_project_announcement": 1.30,
    "labor_unrest_or_protest_environment": 1.25,
}

# =========================
# 2026 Forward Risk settings
# =========================

FORWARD_TOP_N_COUNTRIES = 20
FORWARD_BASELINE_YEAR = 2024
FORWARD_TARGET_YEAR = 2026
FORWARD_COMPARISON_YEAR = 2025

# Optional country-name overrides for ACLED forward update queries.
# These help align World Bank / project country names with ACLED country names.
ACLED_FORWARD_COUNTRY_NAME_OVERRIDES = {
    "Congo, Rep.": "Republic of Congo",
    "Iran, Islamic Rep.": "Iran",
}