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
        17. Generate charts
        18. Run diagnostics
        19. Build model governance documentation
        20. Generate PDF report
    """

    print("=" * 70)
    print("Starting Executive Protection Risk Intelligence pipeline...")
    print("=" * 70)

    print("\n[1/20] Building World Bank dataset...")
    build_worldbank_dataset()

    print("\n[2/20] Loading or downloading ACLED event data...")
    fetch_acled_events(use_existing=True, force_refresh=False)

    print("\n[3/20] Processing ACLED country-year features...")
    build_acled_country_features()

    print("\n[4/20] Building energy exposure features...")
    build_energy_exposure_features()

    print("\n[5/20] Building violent-crime proxy features...")
    build_crime_features()

    print("\n[6/20] Building master model dataset...")
    build_master_dataset()

    print("\n[7/20] Calculating executive protection risk scores...")
    calculate_risk_scores()

    print("\n[8/20] Running run-to-run change detection...")
    run_change_detection(update_snapshot=True)

    print("\n[9/20] Running scenario analysis...")
    run_scenario_analysis()

    print("\n[10/20] Running sensitivity analysis...")
    run_sensitivity_analysis()

    print("\n[11/20] Running Monte Carlo risk simulation...")
    run_monte_carlo_risk_simulation()

    print("\n[12/20] Running regional spillover analysis...")
    run_regional_spillover_analysis()

    print("\n[13/20] Building ACLED forward-risk trend features...")
    build_acled_forward_trends(
        use_existing=True,
        force_refresh=False,
    )

    print("\n[14/20] Calculating 2026 forward-risk scores...")
    run_forward_2026_risk_model()

    print("\n[15/20] Building executive protection intelligence signals...")
    build_intelligence_signals()

    print("\n[16/20] Generating country intelligence profiles...")
    generate_country_profiles()

    print("\n[17/20] Saving charts...")
    save_all_charts()

    print("\n[18/20] Running model diagnostics...")
    run_model_diagnostics()

    print("\n[19/20] Building model governance documentation...")
    run_model_governance()

    print("\n[20/20] Generating PDF report...")
    generate_report()

    print("\n" + "=" * 70)
    print("Pipeline complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()