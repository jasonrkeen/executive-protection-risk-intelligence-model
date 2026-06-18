from src.worldbank_api import build_worldbank_dataset
from src.acled_api import fetch_acled_events
from src.acled_processing import build_acled_country_features
from src.energy_exposure import build_energy_exposure_features
from src.crime_data import build_crime_features
from src.data_processing import build_master_dataset
from src.risk_scoring import calculate_risk_scores
from src.change_detection import run_change_detection
from src.scenario_analysis import run_scenario_analysis
from src.sensitivity_analysis import run_sensitivity_analysis
from src.monte_carlo_risk_simulation import run_monte_carlo_risk_simulation
from src.regional_spillover import run_regional_spillover_analysis
from src.acled_forecast_update import build_acled_forward_trends
from src.forward_risk_model import run_forward_2026_risk_model
from src.intelligence_signal import build_intelligence_signals
from src.country_profile_generator import generate_country_profiles
from src.visualization import save_all_charts
from src.model_diagnostics import run_model_diagnostics
from src.model_governance import run_model_governance
from src.report_generator import generate_report

# Phase 2: City-Level Protective Intelligence Module
from src.acled_city_processing import build_city_ep_risk_features
from src.city_visualization import run_city_visualizations
from src.city_map_generator import create_city_risk_map

# Phase 3: Access and Support Proxy Layer
from src.access_proxy_layer import build_access_proxy_layer

# Phase 4: Protective Intelligence Exposure and Posture Scoring Layer
from src.protective_intelligence_score import build_protective_intelligence_scores

# Phase 5: Protective Intelligence COA Decision-Support Layer
from src.protective_intelligence_decision_layer import (
    build_decision_support_from_existing_outputs,
)


def main():
    """
    Run the full Executive Protection Risk Intelligence pipeline.

    Pipeline order:
        1. Pull / refresh World Bank data
        2. Load or pull ACLED event data
        3. Process ACLED country-year features
        4. Build energy exposure features
        5. Build crime proxy features
        6. Merge master dataset
        7. Calculate EP risk scores
        8. Run change detection
        9. Run scenario analysis
        10. Run sensitivity analysis
        11. Run Monte Carlo risk simulation
        12. Run regional spillover analysis
        13. Build ACLED forward-risk trend features
        14. Calculate 2026 forward-risk scores
        15. Build executive protection intelligence signals
        16. Generate country intelligence profiles
        17. Generate country-level charts
        18. Run city-level ACLED protective intelligence processing
        19. Generate city-level protective intelligence charts
        20. Generate city-level geospatial risk map
        21. Build airport and medical access proxy layer
        22. Build protective intelligence exposure and posture scores
        23. Build protective intelligence COA decision-support layer
        24. Run diagnostics
        25. Build model governance documentation
        26. Generate PDF report
    """

    total_steps = 26

    print("=" * 70)
    print("Starting Executive Protection Risk Intelligence pipeline...")
    print("=" * 70)

    print(f"\n[1/{total_steps}] Building World Bank dataset...")
    build_worldbank_dataset()

    print(f"\n[2/{total_steps}] Loading or downloading ACLED event data...")
    fetch_acled_events(use_existing=True, force_refresh=False)

    print(f"\n[3/{total_steps}] Processing ACLED country-year features...")
    build_acled_country_features()

    print(f"\n[4/{total_steps}] Building energy exposure features...")
    build_energy_exposure_features()

    print(f"\n[5/{total_steps}] Building violent-crime proxy features...")
    build_crime_features()

    print(f"\n[6/{total_steps}] Building master model dataset...")
    build_master_dataset()

    print(f"\n[7/{total_steps}] Calculating executive protection risk scores...")
    calculate_risk_scores()

    print(f"\n[8/{total_steps}] Running run-to-run change detection...")
    run_change_detection(update_snapshot=True)

    print(f"\n[9/{total_steps}] Running scenario analysis...")
    run_scenario_analysis()

    print(f"\n[10/{total_steps}] Running sensitivity analysis...")
    run_sensitivity_analysis()

    print(f"\n[11/{total_steps}] Running Monte Carlo risk simulation...")
    run_monte_carlo_risk_simulation()

    print(f"\n[12/{total_steps}] Running regional spillover analysis...")
    run_regional_spillover_analysis()

    print(f"\n[13/{total_steps}] Building ACLED forward-risk trend features...")
    build_acled_forward_trends(
        use_existing=True,
        force_refresh=False,
    )

    print(f"\n[14/{total_steps}] Calculating 2026 forward-risk scores...")
    run_forward_2026_risk_model()

    print(f"\n[15/{total_steps}] Building executive protection intelligence signals...")
    build_intelligence_signals()

    print(f"\n[16/{total_steps}] Generating country intelligence profiles...")
    generate_country_profiles()

    print(f"\n[17/{total_steps}] Saving country-level charts...")
    save_all_charts()

    print(
        f"\n[18/{total_steps}] Running Phase 2 city-level ACLED protective intelligence processing..."
    )
    build_city_ep_risk_features()

    print(f"\n[19/{total_steps}] Saving city-level protective intelligence charts...")
    run_city_visualizations()

    print(f"\n[20/{total_steps}] Creating city-level EP risk map...")
    create_city_risk_map()

    print(f"\n[21/{total_steps}] Building airport and medical access proxy layer...")
    build_access_proxy_layer()

    print(
        f"\n[22/{total_steps}] Building protective intelligence exposure and posture scores..."
    )
    build_protective_intelligence_scores()

    print(
        f"\n[23/{total_steps}] Building protective intelligence COA decision-support layer..."
    )
    build_decision_support_from_existing_outputs()

    print(f"\n[24/{total_steps}] Running model diagnostics...")
    run_model_diagnostics()

    print(f"\n[25/{total_steps}] Building model governance documentation...")
    run_model_governance()

    print(f"\n[26/{total_steps}] Generating PDF report...")
    generate_report()

    print("\n" + "=" * 70)
    print("Pipeline complete.")
    print("=" * 70)
    print("New decision-support outputs should be available in:")
    print("- outputs/tables/protective_intelligence_decision_support.csv")
    print("- outputs/tables/top_decision_escalations.csv")
    print("- outputs/tables/decision_rule_audit.csv")


if __name__ == "__main__":
    main()