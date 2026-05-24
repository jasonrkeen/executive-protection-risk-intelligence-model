import pandas as pd

from src.config import (
    MODEL_GOVERNANCE_FILE,
    MODEL_ASSUMPTIONS_FILE,
    RISK_WEIGHTS,
    RISK_BUCKETS,
    SCENARIO_MULTIPLIERS,
    SENSITIVITY_SCENARIOS,
    FORWARD_BASELINE_YEAR,
    FORWARD_TARGET_YEAR,
    FORWARD_COMPARISON_YEAR,
)


def build_governance_summary() -> pd.DataFrame:
    """
    Build a model governance summary table.
    """

    rows = [
        {
            "governance_area": "Project purpose",
            "description": (
                "Independent OSINT research model for country-level executive "
                "protection risk screening in global energy operations."
            ),
            "model_implication": (
                "Designed for strategic screening, portfolio demonstration, and "
                "risk-intelligence research."
            ),
        },
        {
            "governance_area": "Intended use",
            "description": (
                "Country-level prioritization for executive travel, site visits, "
                "public events, and energy-sector operating-environment review."
            ),
            "model_implication": (
                "Useful for early-stage triage and comparative country risk analysis."
            ),
        },
        {
            "governance_area": "Not intended use",
            "description": (
                "Not a tactical travel approval tool, protective advance plan, "
                "route-security assessment, or replacement for local intelligence."
            ),
            "model_implication": (
                "Scores should not be used as standalone operational decisions."
            ),
        },
        {
            "governance_area": "Data sources",
            "description": (
                "Uses public ACLED event data, World Bank governance and macro "
                "indicators, World Bank homicide proxy data, and World Bank "
                "energy exposure indicators."
            ),
            "model_implication": (
                "Results depend on public-data availability, reporting coverage, "
                "indicator lag, and country-name matching."
            ),
        },
        {
            "governance_area": "Scoring structure",
            "description": (
                "Composite score uses civil unrest / political violence, governance "
                "risk, violent crime proxy risk, energy exposure, and recent risk "
                "momentum."
            ),
            "model_implication": (
                "Countries can rank highly because of conflict severity, weak "
                "governance, crime exposure, energy relevance, or momentum."
            ),
        },
        {
            "governance_area": "Severity calibration",
            "description": (
                "A bounded uplift is applied for extreme conflict exposure, fatality "
                "severity, geographic spread, compound governance/violence risk, "
                "energy instability, and momentum."
            ),
            "model_implication": (
                "Prevents severe environments from being compressed into moderate "
                "scores by pure weighted averaging."
            ),
        },
        {
            "governance_area": "Scenario analysis",
            "description": (
                "Scenario multipliers estimate how baseline risk may change under "
                "operational contexts such as public events, site visits, civil unrest, "
                "or high-visibility executive travel."
            ),
            "model_implication": (
                "Scenario outputs are planning overlays, not deterministic forecasts."
            ),
        },
        {
            "governance_area": "Sensitivity analysis",
            "description": (
                "Alternative weighting scenarios test how stable country rankings are "
                "under different model assumptions."
            ),
            "model_implication": (
                "Countries stable across scenarios are more robust top-risk candidates."
            ),
        },
        {
            "governance_area": "Forward-risk layer",
            "description": (
                f"Forward update compares {FORWARD_TARGET_YEAR} ACLED activity "
                f"against {FORWARD_COMPARISON_YEAR} and anchors results to the "
                f"{FORWARD_BASELINE_YEAR} baseline."
            ),
            "model_implication": (
                "If target-year ACLED data is unavailable, the model retains the "
                "baseline rather than treating missing data as improvement."
            ),
        },
        {
            "governance_area": "Affiliation disclaimer",
            "description": (
                "Independent portfolio research project. Not affiliated with, endorsed "
                "by, or representative of any company, government agency, security "
                "organization, ACLED, the World Bank, or other referenced organization."
            ),
            "model_implication": (
                "The model should be interpreted as an open-source analytical framework."
            ),
        },
    ]

    return pd.DataFrame(rows)


def build_assumptions_summary() -> pd.DataFrame:
    """
    Build a long-form assumptions table for weights, buckets, scenarios,
    and sensitivity assumptions.
    """

    rows = []

    for component, weight in RISK_WEIGHTS.items():
        rows.append(
            {
                "assumption_type": "Baseline risk weight",
                "assumption_name": component,
                "assumption_value": weight,
                "notes": "Component weight used in the baseline EP risk score.",
            }
        )

    for lower, upper, label in RISK_BUCKETS:
        rows.append(
            {
                "assumption_type": "Risk bucket",
                "assumption_name": label,
                "assumption_value": f"{lower} to {upper}",
                "notes": "Risk bucket threshold used for score interpretation.",
            }
        )

    for scenario, multiplier in SCENARIO_MULTIPLIERS.items():
        rows.append(
            {
                "assumption_type": "Scenario multiplier",
                "assumption_name": scenario,
                "assumption_value": multiplier,
                "notes": "Multiplier applied to baseline EP risk score.",
            }
        )

    for scenario_name, weights in SENSITIVITY_SCENARIOS.items():
        for component, weight in weights.items():
            rows.append(
                {
                    "assumption_type": "Sensitivity scenario weight",
                    "assumption_name": f"{scenario_name}: {component}",
                    "assumption_value": weight,
                    "notes": (
                        "Alternative model weighting used to test ranking stability."
                    ),
                }
            )

    rows.extend(
        [
            {
                "assumption_type": "Forward-risk assumption",
                "assumption_name": "Baseline year",
                "assumption_value": FORWARD_BASELINE_YEAR,
                "notes": "Year used as the calibrated baseline anchor.",
            },
            {
                "assumption_type": "Forward-risk assumption",
                "assumption_name": "Target year",
                "assumption_value": FORWARD_TARGET_YEAR,
                "notes": "Forward-risk target year.",
            },
            {
                "assumption_type": "Forward-risk assumption",
                "assumption_name": "Comparison year",
                "assumption_value": FORWARD_COMPARISON_YEAR,
                "notes": "Comparison year for ACLED same-period trend analysis.",
            },
        ]
    )

    return pd.DataFrame(rows)


def run_model_governance():
    """
    Save model governance and assumption summary tables.
    """

    print("Building model governance documentation...")

    governance = build_governance_summary()
    assumptions = build_assumptions_summary()

    MODEL_GOVERNANCE_FILE.parent.mkdir(parents=True, exist_ok=True)

    governance.to_csv(MODEL_GOVERNANCE_FILE, index=False)
    assumptions.to_csv(MODEL_ASSUMPTIONS_FILE, index=False)

    print(f"Model governance summary saved to: {MODEL_GOVERNANCE_FILE}")
    print(f"Model assumptions summary saved to: {MODEL_ASSUMPTIONS_FILE}")

    return governance, assumptions


if __name__ == "__main__":
    run_model_governance()