import pandas as pd

from src.config import (
    WORLD_BANK_FILE,
    ACLED_RAW_FILE,
    ACLED_COUNTRY_FILE,
    CRIME_PROCESSED_FILE,
    ENERGY_FILE,
    MASTER_DATA_FILE,
    RISK_RANKINGS_FILE,
    MODEL_DIAGNOSTICS_FILE,
    MODEL_COMPONENT_MATURITY_FILE,
    MODEL_MATURITY_FILE,
    MISSING_VALUES_FILE,
    MODEL_COMPONENT_COVERAGE_FILE,
    ACLED_FORWARD_TRENDS_FILE,
    FORWARD_2026_RISK_FILE,
    FORWARD_2026_TOP_CHANGES_FILE,
    FORWARD_ACLED_EVENTS_FILE,
)


def file_status(path) -> dict:
    """
    Return file existence, row count, column count, and status for a CSV file.
    """

    if not path.exists():
        return {
            "file_path": str(path),
            "exists": False,
            "rows": 0,
            "columns": 0,
            "status": "Missing",
        }

    try:
        df = pd.read_csv(path, low_memory=False)
        return {
            "file_path": str(path),
            "exists": True,
            "rows": len(df),
            "columns": len(df.columns),
            "status": "Available",
        }
    except Exception as exc:
        return {
            "file_path": str(path),
            "exists": True,
            "rows": 0,
            "columns": 0,
            "status": f"Read error: {exc}",
        }


def safe_read_csv(path) -> pd.DataFrame:
    """
    Read a CSV if it exists. Return empty DataFrame if it does not.
    """

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def forward_target_year_data_available() -> bool:
    """
    Return True if the forward layer has nonzero target-year ACLED activity.

    This prevents the diagnostics layer from calling the forward model fully
    populated when the forward files exist but 2026 ACLED target-year data is
    unavailable and forward scores are baseline-retained.
    """

    forward_trends = safe_read_csv(ACLED_FORWARD_TRENDS_FILE)
    forward_scores = safe_read_csv(FORWARD_2026_RISK_FILE)

    if not forward_trends.empty and "2026_ytd_events" in forward_trends.columns:
        target_events = pd.to_numeric(
            forward_trends["2026_ytd_events"],
            errors="coerce",
        ).fillna(0)

        if target_events.sum() > 0:
            return True

    if not forward_scores.empty and "2026_ytd_events" in forward_scores.columns:
        target_events = pd.to_numeric(
            forward_scores["2026_ytd_events"],
            errors="coerce",
        ).fillna(0)

        if target_events.sum() > 0:
            return True

    return False


def forward_baseline_retained() -> bool:
    """
    Return True if the forward layer appears to be initialized but baseline-retained.
    """

    forward_scores = safe_read_csv(FORWARD_2026_RISK_FILE)

    if forward_scores.empty:
        return False

    if "target_year_data_status" in forward_scores.columns:
        statuses = forward_scores["target_year_data_status"].fillna("").astype(str)

        if statuses.str.contains(
            "Target-year ACLED data unavailable",
            case=False,
            regex=False,
        ).any():
            return True

    if "forward_adjustment_note" in forward_scores.columns:
        notes = forward_scores["forward_adjustment_note"].fillna("").astype(str)

        if notes.str.contains(
            "baseline retained",
            case=False,
            regex=False,
        ).any():
            return True

        if notes.str.contains(
            "2026 ACLED data unavailable",
            case=False,
            regex=False,
        ).any():
            return True

    if (
        "forward_score_change" in forward_scores.columns
        and "forward_risk_change_flag" in forward_scores.columns
    ):
        changes = pd.to_numeric(
            forward_scores["forward_score_change"],
            errors="coerce",
        ).fillna(0)

        flags = forward_scores["forward_risk_change_flag"].fillna("").astype(str)

        if changes.abs().sum() == 0 and flags.str.contains(
            "Stable / mixed",
            case=False,
            regex=False,
        ).all():
            return True

    return False


def get_forward_layer_status(
    forward_live_components: int,
    forward_total_components: int,
) -> str:
    """
    Build analyst-friendly forward-layer status.
    """

    if forward_total_components == 0:
        return "Forward layer not configured"

    if forward_live_components < forward_total_components:
        return "Forward layer incomplete or unavailable"

    if forward_target_year_data_available():
        return "Forward layer populated with target-year ACLED trend data"

    if forward_baseline_retained():
        return (
            "Forward layer initialized / baseline retained; "
            "target-year ACLED data unavailable"
        )

    return "Forward layer initialized; target-year ACLED data unavailable"


def component_checks() -> pd.DataFrame:
    """
    Check whether each major model file exists and is populated.
    """

    files = {
        "World Bank governance / macro indicators": WORLD_BANK_FILE,
        "ACLED raw event data": ACLED_RAW_FILE,
        "ACLED country-year risk features": ACLED_COUNTRY_FILE,
        "Crime proxy features": CRIME_PROCESSED_FILE,
        "Energy exposure features": ENERGY_FILE,
        "Master model dataset": MASTER_DATA_FILE,
        "Risk rankings output": RISK_RANKINGS_FILE,
        "Forward ACLED raw events": FORWARD_ACLED_EVENTS_FILE,
        "Forward ACLED country trends": ACLED_FORWARD_TRENDS_FILE,
        "Forward 2026 risk scores": FORWARD_2026_RISK_FILE,
        "Forward 2026 top changes": FORWARD_2026_TOP_CHANGES_FILE,
    }

    rows = []

    for component, path in files.items():
        status = file_status(path)

        rows.append(
            {
                "component": component,
                "source_file": status["file_path"],
                "file_exists": status["exists"],
                "rows": status["rows"],
                "columns": status["columns"],
                "status": status["status"],
            }
        )

    return pd.DataFrame(rows)


def evaluate_component_maturity(
    diagnostics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert file diagnostics into a model maturity summary.

    Baseline model components are evaluated separately from the forward-risk
    nowcast layer because the baseline model can be fully data-driven even when
    the forward 2026 target-year ACLED data is unavailable.
    """

    maturity_rows = []

    component_mapping = {
        "World Bank governance / macro indicators": {
            "model_component": "Governance / macro risk",
            "component_group": "Baseline model",
        },
        "ACLED country-year risk features": {
            "model_component": "Civil unrest / political violence risk",
            "component_group": "Baseline model",
        },
        "Crime proxy features": {
            "model_component": "Violent crime proxy risk",
            "component_group": "Baseline model",
        },
        "Energy exposure features": {
            "model_component": "Energy-sector exposure risk",
            "component_group": "Baseline model",
        },
        "Risk rankings output": {
            "model_component": "Final model output",
            "component_group": "Baseline model",
        },
        "Forward ACLED country trends": {
            "model_component": "2026 forward ACLED trend layer",
            "component_group": "Forward nowcast layer",
        },
        "Forward 2026 risk scores": {
            "model_component": "2026 forward risk output",
            "component_group": "Forward nowcast layer",
        },
    }

    target_year_available = forward_target_year_data_available()
    baseline_retained = forward_baseline_retained()

    for source_component, metadata in component_mapping.items():
        row = diagnostics[diagnostics["component"] == source_component]

        if row.empty:
            maturity_rows.append(
                {
                    "model_component": metadata["model_component"],
                    "component_group": metadata["component_group"],
                    "status": "Missing",
                    "rows_available": 0,
                    "placeholder_used": True,
                    "data_quality_flag": "Component not found in diagnostics.",
                }
            )
            continue

        row = row.iloc[0]
        rows_available = int(row["rows"])

        if not row["file_exists"]:
            status = "Missing"
            placeholder_used = True
            flag = "Source file missing."
        elif rows_available == 0:
            status = "Placeholder / Empty"
            placeholder_used = True
            flag = "File exists but contains zero rows."
        else:
            status = "Live Data"
            placeholder_used = False
            flag = "Component populated."

            if metadata["component_group"] == "Forward nowcast layer":
                if target_year_available:
                    flag = "Forward target-year ACLED data populated."
                elif baseline_retained:
                    flag = (
                        "Forward layer initialized; target-year ACLED unavailable "
                        "and forward scores are baseline-retained."
                    )
                else:
                    flag = (
                        "Forward layer initialized; target-year ACLED data not detected."
                    )

        maturity_rows.append(
            {
                "model_component": metadata["model_component"],
                "component_group": metadata["component_group"],
                "status": status,
                "rows_available": rows_available,
                "placeholder_used": placeholder_used,
                "data_quality_flag": flag,
            }
        )

    maturity = pd.DataFrame(maturity_rows)

    baseline = maturity[maturity["component_group"] == "Baseline model"].copy()
    forward = maturity[maturity["component_group"] == "Forward nowcast layer"].copy()

    live_components = int((baseline["status"] == "Live Data").sum())
    total_components = int(len(baseline))
    placeholder_components = int(baseline["placeholder_used"].sum())
    placeholder_share = placeholder_components / total_components if total_components else 0

    if placeholder_share == 0:
        model_maturity = "Fully Data-Driven"
    elif placeholder_share <= 0.25:
        model_maturity = "Mostly Data-Driven"
    elif placeholder_share <= 0.50:
        model_maturity = "Partially Data-Driven"
    else:
        model_maturity = "Baseline / Placeholder-Heavy"

    forward_live_components = int((forward["status"] == "Live Data").sum())
    forward_total_components = int(len(forward))
    forward_placeholder_components = int(forward["placeholder_used"].sum())

    forward_layer_status = get_forward_layer_status(
        forward_live_components=forward_live_components,
        forward_total_components=forward_total_components,
    )

    summary = pd.DataFrame(
        [
            {
                "model_maturity": model_maturity,
                "live_components": live_components,
                "total_components": total_components,
                "placeholder_components": placeholder_components,
                "placeholder_share": round(placeholder_share, 4),
                "forward_layer_status": forward_layer_status,
                "forward_live_components": forward_live_components,
                "forward_total_components": forward_total_components,
                "forward_placeholder_components": forward_placeholder_components,
                "forward_target_year_data_available": target_year_available,
                "forward_baseline_retained": baseline_retained,
            }
        ]
    )

    return maturity, summary


def add_worldbank_coverage(rows: list, wb: pd.DataFrame) -> None:
    """
    Add World Bank coverage diagnostics.
    """

    if wb.empty:
        return

    country_count = wb["country_code"].nunique() if "country_code" in wb.columns else pd.NA

    rows.append(
        {
            "coverage_area": "World Bank indicators",
            "rows": len(wb),
            "countries": country_count,
            "coverage_metric": "country_code count",
            "coverage_value": country_count,
            "quality_flag": "World Bank indicator file populated",
        }
    )


def add_acled_coverage(rows: list, acled_raw: pd.DataFrame, acled: pd.DataFrame) -> None:
    """
    Add ACLED baseline coverage diagnostics.
    """

    if not acled_raw.empty:
        rows.append(
            {
                "coverage_area": "ACLED raw events",
                "rows": len(acled_raw),
                "countries": acled_raw["country"].nunique()
                if "country" in acled_raw.columns
                else pd.NA,
                "coverage_metric": "raw event rows",
                "coverage_value": len(acled_raw),
                "quality_flag": "ACLED raw event file populated",
            }
        )

    if acled.empty:
        return

    country_count = acled["country"].nunique() if "country" in acled.columns else pd.NA

    rows.append(
        {
            "coverage_area": "ACLED country-year features",
            "rows": len(acled),
            "countries": country_count,
            "coverage_metric": "countries with country-year ACLED features",
            "coverage_value": country_count,
            "quality_flag": "ACLED processed features populated",
        }
    )

    if "total_acled_events" in acled.columns:
        rows.append(
            {
                "coverage_area": "ACLED event coverage",
                "rows": len(acled),
                "countries": country_count,
                "coverage_metric": "total processed ACLED events",
                "coverage_value": pd.to_numeric(
                    acled["total_acled_events"], errors="coerce"
                ).sum(),
                "quality_flag": "ACLED event counts available",
            }
        )

    if "unique_coordinate_pairs" in acled.columns:
        rows.append(
            {
                "coverage_area": "ACLED geospatial coverage",
                "rows": len(acled),
                "countries": country_count,
                "coverage_metric": "country-years with coordinate spread populated",
                "coverage_value": int(
                    (
                        pd.to_numeric(
                            acled["unique_coordinate_pairs"], errors="coerce"
                        ).fillna(0)
                        > 0
                    ).sum()
                ),
                "quality_flag": "Coordinate-pair spread feature available",
            }
        )


def add_crime_coverage(rows: list, crime: pd.DataFrame) -> None:
    """
    Add crime proxy coverage diagnostics.
    """

    if crime.empty:
        return

    country_count = crime["country_code"].nunique() if "country_code" in crime.columns else pd.NA

    populated = (
        pd.to_numeric(crime.get("homicide_rate_per_100k"), errors="coerce")
        .notna()
        .sum()
        if "homicide_rate_per_100k" in crime.columns
        else 0
    )

    rows.append(
        {
            "coverage_area": "Homicide proxy",
            "rows": len(crime),
            "countries": country_count,
            "coverage_metric": "rows with populated homicide proxy",
            "coverage_value": int(populated),
            "quality_flag": "Crime proxy populated" if populated > 0 else "Crime proxy missing",
        }
    )

    if "crime_data_quality_flag" in crime.columns:
        for flag, count in crime["crime_data_quality_flag"].value_counts().items():
            rows.append(
                {
                    "coverage_area": "Homicide proxy quality flags",
                    "rows": len(crime),
                    "countries": country_count,
                    "coverage_metric": flag,
                    "coverage_value": int(count),
                    "quality_flag": "Crime data quality distribution",
                }
            )


def add_energy_coverage(rows: list, energy: pd.DataFrame) -> None:
    """
    Add energy exposure coverage diagnostics.
    """

    if energy.empty:
        return

    country_count = energy["country_code"].nunique() if "country_code" in energy.columns else pd.NA

    measurable = (
        (
            pd.to_numeric(energy.get("energy_exposure_raw"), errors="coerce").fillna(0)
            > 0
        ).sum()
        if "energy_exposure_raw" in energy.columns
        else 0
    )

    rows.append(
        {
            "coverage_area": "Energy exposure",
            "rows": len(energy),
            "countries": country_count,
            "coverage_metric": "rows with measurable energy exposure",
            "coverage_value": int(measurable),
            "quality_flag": "Energy exposure features populated",
        }
    )

    if "energy_data_quality_flag" in energy.columns:
        for flag, count in energy["energy_data_quality_flag"].value_counts().items():
            rows.append(
                {
                    "coverage_area": "Energy exposure quality flags",
                    "rows": len(energy),
                    "countries": country_count,
                    "coverage_metric": flag,
                    "coverage_value": int(count),
                    "quality_flag": "Energy data quality distribution",
                }
            )


def add_master_coverage(rows: list, master: pd.DataFrame) -> None:
    """
    Add master dataset coverage diagnostics.
    """

    if master.empty:
        return

    country_count = master["country_code"].nunique() if "country_code" in master.columns else pd.NA

    if "data_coverage_flag" in master.columns:
        for flag, count in master["data_coverage_flag"].value_counts().items():
            rows.append(
                {
                    "coverage_area": "Master dataset coverage flags",
                    "rows": len(master),
                    "countries": country_count,
                    "coverage_metric": flag,
                    "coverage_value": int(count),
                    "quality_flag": "Master data coverage flag distribution",
                }
            )


def add_rankings_coverage(rows: list, rankings: pd.DataFrame) -> None:
    """
    Add rankings coverage diagnostics.
    """

    if rankings.empty:
        return

    rows.append(
        {
            "coverage_area": "Risk rankings",
            "rows": len(rankings),
            "countries": rankings["country_code"].nunique()
            if "country_code" in rankings.columns
            else pd.NA,
            "coverage_metric": "ranked countries",
            "coverage_value": len(rankings),
            "quality_flag": "Risk ranking output populated",
        }
    )


def add_forward_coverage(
    rows: list,
    forward_events: pd.DataFrame,
    forward_trends: pd.DataFrame,
    forward_scores: pd.DataFrame,
) -> None:
    """
    Add 2026 forward-risk layer coverage diagnostics.
    """

    if not forward_events.empty:
        rows.append(
            {
                "coverage_area": "Forward ACLED raw events",
                "rows": len(forward_events),
                "countries": forward_events["project_country"].nunique()
                if "project_country" in forward_events.columns
                else pd.NA,
                "coverage_metric": "forward raw event rows",
                "coverage_value": len(forward_events),
                "quality_flag": "Forward ACLED raw events file populated",
            }
        )

    if not forward_trends.empty:
        target_events = (
            pd.to_numeric(forward_trends.get("2026_ytd_events"), errors="coerce")
            .fillna(0)
            .sum()
            if "2026_ytd_events" in forward_trends.columns
            else 0
        )

        rows.append(
            {
                "coverage_area": "Forward ACLED target-year availability",
                "rows": len(forward_trends),
                "countries": forward_trends["country_code"].nunique()
                if "country_code" in forward_trends.columns
                else pd.NA,
                "coverage_metric": "2026 YTD event rows represented",
                "coverage_value": int(target_events),
                "quality_flag": "Target-year ACLED data available"
                if target_events > 0
                else "Target-year ACLED data unavailable",
            }
        )

        if "forward_fetch_status" in forward_trends.columns:
            for flag, count in forward_trends["forward_fetch_status"].value_counts().items():
                rows.append(
                    {
                        "coverage_area": "Forward fetch status",
                        "rows": len(forward_trends),
                        "countries": forward_trends["country_code"].nunique()
                        if "country_code" in forward_trends.columns
                        else pd.NA,
                        "coverage_metric": flag,
                        "coverage_value": int(count),
                        "quality_flag": "Forward fetch status distribution",
                    }
                )

    if not forward_scores.empty:
        rows.append(
            {
                "coverage_area": "Forward 2026 risk scores",
                "rows": len(forward_scores),
                "countries": forward_scores["country_code"].nunique()
                if "country_code" in forward_scores.columns
                else pd.NA,
                "coverage_metric": "forward-scored countries",
                "coverage_value": len(forward_scores),
                "quality_flag": "Forward score output populated",
            }
        )

        if "forward_adjustment_note" in forward_scores.columns:
            for flag, count in forward_scores["forward_adjustment_note"].value_counts().items():
                rows.append(
                    {
                        "coverage_area": "Forward adjustment notes",
                        "rows": len(forward_scores),
                        "countries": forward_scores["country_code"].nunique()
                        if "country_code" in forward_scores.columns
                        else pd.NA,
                        "coverage_metric": flag,
                        "coverage_value": int(count),
                        "quality_flag": "Forward adjustment note distribution",
                    }
                )


def build_component_coverage_summary() -> pd.DataFrame:
    """
    Build deeper data coverage checks from the processed model files.
    """

    rows = []

    wb = safe_read_csv(WORLD_BANK_FILE)
    acled_raw = safe_read_csv(ACLED_RAW_FILE)
    acled = safe_read_csv(ACLED_COUNTRY_FILE)
    crime = safe_read_csv(CRIME_PROCESSED_FILE)
    energy = safe_read_csv(ENERGY_FILE)
    master = safe_read_csv(MASTER_DATA_FILE)
    rankings = safe_read_csv(RISK_RANKINGS_FILE)
    forward_events = safe_read_csv(FORWARD_ACLED_EVENTS_FILE)
    forward_trends = safe_read_csv(ACLED_FORWARD_TRENDS_FILE)
    forward_scores = safe_read_csv(FORWARD_2026_RISK_FILE)

    add_worldbank_coverage(rows, wb)
    add_acled_coverage(rows, acled_raw, acled)
    add_crime_coverage(rows, crime)
    add_energy_coverage(rows, energy)
    add_master_coverage(rows, master)
    add_rankings_coverage(rows, rankings)
    add_forward_coverage(rows, forward_events, forward_trends, forward_scores)

    return pd.DataFrame(rows)


def missing_value_summary() -> pd.DataFrame:
    """
    Create a missing-value summary for the master dataset.
    """

    if not MASTER_DATA_FILE.exists():
        return pd.DataFrame(
            columns=[
                "column",
                "missing_count",
                "missing_share",
                "non_missing_count",
            ]
        )

    df = pd.read_csv(MASTER_DATA_FILE, low_memory=False)

    rows = []

    for column in df.columns:
        missing_count = df[column].isna().sum()
        total = len(df)
        missing_share = missing_count / total if total else 0

        rows.append(
            {
                "column": column,
                "missing_count": int(missing_count),
                "missing_share": round(missing_share, 4),
                "non_missing_count": int(total - missing_count),
            }
        )

    output = pd.DataFrame(rows).sort_values(
        ["missing_share", "missing_count"],
        ascending=False,
    )

    return output


def run_model_diagnostics():
    """
    Run model diagnostics and save output tables.
    """

    print("Running model diagnostics...")

    diagnostics = component_checks()
    MODEL_DIAGNOSTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_csv(MODEL_DIAGNOSTICS_FILE, index=False)

    maturity, maturity_summary = evaluate_component_maturity(diagnostics)
    maturity.to_csv(MODEL_COMPONENT_MATURITY_FILE, index=False)
    maturity_summary.to_csv(MODEL_MATURITY_FILE, index=False)

    missing_values = missing_value_summary()
    missing_values.to_csv(MISSING_VALUES_FILE, index=False)

    coverage_summary = build_component_coverage_summary()
    coverage_summary.to_csv(MODEL_COMPONENT_COVERAGE_FILE, index=False)

    print(f"Model diagnostics saved to: {MODEL_DIAGNOSTICS_FILE}")
    print(f"Model component maturity saved to: {MODEL_COMPONENT_MATURITY_FILE}")
    print(f"Model maturity saved to: {MODEL_MATURITY_FILE}")
    print(f"Missing value summary saved to: {MISSING_VALUES_FILE}")
    print(f"Component coverage summary saved to: {MODEL_COMPONENT_COVERAGE_FILE}")

    if not maturity_summary.empty:
        row = maturity_summary.iloc[0]
        print(
            f"Baseline model maturity: {row['model_maturity']} "
            f"({row['live_components']}/{row['total_components']} live components)"
        )
        print(f"Forward layer status: {row['forward_layer_status']}")

    return diagnostics, maturity, maturity_summary, missing_values, coverage_summary


if __name__ == "__main__":
    run_model_diagnostics()