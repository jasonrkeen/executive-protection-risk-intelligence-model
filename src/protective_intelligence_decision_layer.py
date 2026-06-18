"""
Protective Intelligence Decision-Support Layer.

Purpose:
- Convert existing trip/city/country risk outputs into explainable
  protective-intelligence courses of action.
- Keep the model strategic and non-operational.
- Support analyst review, security lead triage, and portfolio presentation.

This module does NOT:
- Replace professional judgment.
- Provide route plans, tactical instructions, or client-specific SOPs.
- Assess named individuals or private threat actors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


DEFAULT_RULES_PATH = Path("data/raw/protective_intelligence_decision_rules.csv")


def _safe_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    """Convert a pandas Series to numeric with missing values filled."""
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _find_score_column(df: pd.DataFrame) -> str:
    """
    Identify the best available protective intelligence score column.

    The repo has evolved over time, so this function accepts several
    likely score names rather than hard-coding one brittle dependency.
    """
    candidates = [
        "protective_intelligence_risk_score",
        "Protective Intelligence Risk Score",
        "protective_intelligence_score",
        "trip_protective_intelligence_score",
        "operational_ep_risk_score",
        "city_ep_risk_score",
        "executive_protection_risk_score",
        "overall_risk_score",
        "risk_score",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        raise ValueError(
            "No numeric score column found. Expected a protective intelligence, "
            "operational EP, city EP, executive protection, or risk score column."
        )

    raise ValueError(
        "Could not identify the protective intelligence score column. "
        f"Available numeric columns: {numeric_cols}"
    )


def _column_exists(df: pd.DataFrame, candidates: List[str]) -> str | None:
    """Return the first matching column name from a list of candidates."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _classify_score(score: float) -> Tuple[str, str]:
    """Return broad COA level and baseline recommendation from score."""
    if score >= 80:
        return "Senior Review", "Senior security review"
    if score >= 70:
        return "Security Lead Review", "Notify security lead"
    if score >= 60:
        return "Enhanced Advance", "Require enhanced advance work"
    if score >= 45:
        return "Validate", "Request analyst validation"
    if score >= 30:
        return "Monitor", "Increase monitoring"
    return "Routine", "Continue routine monitoring"


def _risk_band(score: float) -> str:
    """Convert numeric score to a readable risk band."""
    if score >= 80:
        return "Severe"
    if score >= 70:
        return "High"
    if score >= 60:
        return "Elevated"
    if score >= 45:
        return "Moderate-Elevated"
    if score >= 30:
        return "Moderate"
    return "Low"


def _data_confidence(row: pd.Series) -> str:
    """
    Estimate confidence from available data-quality flags.

    This uses simple transparent rules. If your existing diagnostics module
    already creates stronger flags, you can wire them in here later.
    """
    warning_cols = [
        "data_quality_warning",
        "homicide_data_quality_flag",
        "medical_data_quality_flag",
        "airport_access_data_quality_flag",
        "acled_data_quality_flag",
        "data_quality_flag",
        "source_quality_flag",
    ]

    warnings = []

    for col in warning_cols:
        if col in row.index and pd.notna(row[col]):
            value = str(row[col]).strip().lower()
            if value and value not in {
                "none",
                "ok",
                "good",
                "direct",
                "current",
                "high",
                "no warning",
            }:
                warnings.append(value)

    if len(warnings) >= 3:
        return "Low"
    if len(warnings) >= 1:
        return "Medium"
    return "High"


def _build_trigger_flags(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """
    Create interpretable trigger flags from available columns.

    The logic is intentionally conservative and explainable.
    """
    out = df.copy()

    score = _safe_numeric(out[score_col])

    support_gap_col = _column_exists(
        out,
        [
            "support_gap_score",
            "support_gap",
            "support_access_gap_score",
            "access_support_gap_score",
            "medical_airport_support_gap",
            "access_proxy_risk_score",
        ],
    )

    movement_col = _column_exists(
        out,
        [
            "movement_predictability_score",
            "movement_predictability",
            "itinerary_predictability_score",
            "public_movement_predictability",
            "public_event_visibility",
        ],
    )

    online_col = _column_exists(
        out,
        [
            "online_visibility_score",
            "online_visibility",
            "information_leakage_score",
            "itinerary_publicity_score",
            "public_visibility_score",
            "media_attention_level",
        ],
    )

    city_momentum_col = _column_exists(
        out,
        [
            "momentum_score",
            "recent_event_momentum",
            "city_event_momentum",
            "events_30d",
            "events_60d",
            "events_90d",
            "recent_events",
        ],
    )

    city_risk_col = _column_exists(
        out,
        [
            "city_ep_risk_score",
            "operational_ep_risk_score",
            "city_risk_score",
            "city_protective_intelligence_score",
        ],
    )

    out["trigger_moderate_score"] = score.between(30, 44.999)
    out["trigger_elevated_score"] = score.between(45, 59.999)
    out["trigger_high_score"] = score.between(60, 79.999)
    out["trigger_severe_score"] = score >= 80

    if support_gap_col:
        support_gap = _safe_numeric(out[support_gap_col])
        out["trigger_support_gap"] = support_gap >= 60
    else:
        out["trigger_support_gap"] = False

    if movement_col:
        movement = _safe_numeric(out[movement_col])
        out["trigger_predictable_movement"] = movement >= 60
    else:
        out["trigger_predictable_movement"] = False

    if online_col:
        online = _safe_numeric(out[online_col])
        out["trigger_online_visibility"] = online >= 60
    else:
        out["trigger_online_visibility"] = False

    if city_momentum_col:
        city_momentum = _safe_numeric(out[city_momentum_col])
        out["trigger_city_risk_momentum"] = city_momentum >= 60
    else:
        out["trigger_city_risk_momentum"] = False

    if city_risk_col:
        city_risk = _safe_numeric(out[city_risk_col])
        out["trigger_high_city_risk"] = city_risk >= 70
    else:
        out["trigger_high_city_risk"] = False

    out["trigger_high_score_plus_support_gap"] = (
        (score >= 70) & out["trigger_support_gap"]
    )

    trigger_cols = [
        "trigger_support_gap",
        "trigger_predictable_movement",
        "trigger_online_visibility",
        "trigger_city_risk_momentum",
        "trigger_high_city_risk",
        "trigger_high_score_plus_support_gap",
        "trigger_severe_score",
    ]

    out["trigger_count"] = out[trigger_cols].sum(axis=1)
    out["trigger_multiple_high_triggers"] = out["trigger_count"] >= 3

    return out


def _recommend_from_row(row: pd.Series, score_col: str) -> Dict[str, str]:
    """Generate a COA recommendation and explainability fields."""
    score = float(row[score_col])
    coa_level, recommendation = _classify_score(score)

    drivers: List[str] = []

    if bool(row.get("trigger_severe_score", False)):
        drivers.append("severe aggregate protective intelligence score")
    elif bool(row.get("trigger_high_score", False)):
        drivers.append("high aggregate protective intelligence score")
    elif bool(row.get("trigger_elevated_score", False)):
        drivers.append("elevated aggregate protective intelligence score")
    elif bool(row.get("trigger_moderate_score", False)):
        drivers.append("moderate aggregate protective intelligence score")

    if bool(row.get("trigger_high_score_plus_support_gap", False)):
        coa_level = "Security Lead Review"
        recommendation = "Notify security lead"
        drivers.append("high score combined with support-access gap")

    if bool(row.get("trigger_multiple_high_triggers", False)):
        coa_level = "Posture Reassessment"
        recommendation = "Consider postponement relocation or alternate plan"
        drivers.append("multiple high-severity decision triggers")

    if bool(row.get("trigger_predictable_movement", False)):
        drivers.append("predictable or highly visible movement pattern")

    if bool(row.get("trigger_online_visibility", False)):
        drivers.append("online visibility or information exposure concern")

    if bool(row.get("trigger_city_risk_momentum", False)):
        drivers.append("recent city-level unrest or violence momentum")

    if bool(row.get("trigger_high_city_risk", False)):
        drivers.append("high city-level operating-environment risk")

    if bool(row.get("trigger_support_gap", False)):
        drivers.append("support-access or medical/airport access constraint")

    if not drivers:
        drivers.append("no elevated decision trigger identified")

    primary_driver = drivers[0]
    secondary_driver = drivers[1] if len(drivers) > 1 else "None"

    analyst_note = _analyst_note(coa_level, drivers)

    return {
        "risk_band": _risk_band(score),
        "coa_level": coa_level,
        "protective_intelligence_recommendation": recommendation,
        "primary_decision_driver": primary_driver,
        "secondary_decision_driver": secondary_driver,
        "supporting_indicators": "; ".join(drivers),
        "data_confidence": _data_confidence(row),
        "analyst_note": analyst_note,
    }


def _analyst_note(coa_level: str, drivers: List[str]) -> str:
    """Create a plain-language analyst note."""
    driver_text = "; ".join(drivers)

    if coa_level == "Posture Reassessment":
        return (
            "Multiple elevated indicators are present. Review the planned movement "
            "through approved organizational security leadership channels. "
            f"Key drivers: {driver_text}."
        )

    if coa_level == "Senior Review":
        return (
            "Severe protective intelligence score. Senior review is recommended "
            f"before relying on routine posture. Key drivers: {driver_text}."
        )

    if coa_level == "Security Lead Review":
        return (
            "High-risk condition identified. Notify the security lead and validate "
            f"current assumptions. Key drivers: {driver_text}."
        )

    if coa_level == "Enhanced Advance":
        return (
            "Enhanced advance work is recommended before movement or event execution. "
            f"Key drivers: {driver_text}."
        )

    if coa_level == "Validate":
        return (
            "Analyst validation is recommended to confirm data recency, local context, "
            f"and planning assumptions. Key drivers: {driver_text}."
        )

    if coa_level == "Monitor":
        return (
            "Increase monitoring and watch for changes in local indicators. "
            f"Key drivers: {driver_text}."
        )

    return "No elevated decision trigger identified. Continue routine monitoring."


def build_decision_support_layer(
    trip_scores: pd.DataFrame,
    rules_path: str | Path = DEFAULT_RULES_PATH,
) -> pd.DataFrame:
    """
    Build the protective intelligence decision-support output table.

    Parameters
    ----------
    trip_scores:
        Existing trip/city/country score table from the model.

    rules_path:
        CSV decision rules file. The current function loads it for auditability
        and future extension, while using transparent internal logic for scoring.

    Returns
    -------
    pd.DataFrame
        Input rows plus COA recommendation, drivers, confidence, and notes.
    """
    if trip_scores.empty:
        raise ValueError("trip_scores is empty. Cannot build decision-support layer.")

    df = trip_scores.copy()
    score_col = _find_score_column(df)
    df[score_col] = _safe_numeric(df[score_col])

    if Path(rules_path).exists():
        try:
            rules = pd.read_csv(rules_path)
            df.attrs["decision_rules_loaded"] = True
            df.attrs["decision_rules_count"] = len(rules)
        except Exception as exc:
            print(f"[Decision Support] Warning: could not read rules file: {exc}")
            print("[Decision Support] Continuing with internal decision logic.")
            df.attrs["decision_rules_loaded"] = False
            df.attrs["decision_rules_count"] = 0
    else:
        df.attrs["decision_rules_loaded"] = False
        df.attrs["decision_rules_count"] = 0

    df = _build_trigger_flags(df, score_col)

    recommendations = df.apply(
        lambda row: _recommend_from_row(row, score_col),
        axis=1,
        result_type="expand",
    )

    output = pd.concat([df, recommendations], axis=1)

    priority_order = {
        "Posture Reassessment": 6,
        "Senior Review": 5,
        "Security Lead Review": 4,
        "Enhanced Advance": 3,
        "Validate": 2,
        "Monitor": 1,
        "Routine": 0,
    }

    output["decision_priority_rank"] = (
        output["coa_level"].map(priority_order).fillna(0).astype(int)
    )

    output = output.sort_values(
        by=["decision_priority_rank", score_col],
        ascending=[False, False],
    ).reset_index(drop=True)

    output.attrs["score_column_used"] = score_col

    return output


def build_decision_rule_audit(
    decision_support: pd.DataFrame,
    rules_path: str | Path = DEFAULT_RULES_PATH,
) -> pd.DataFrame:
    """
    Create a compact one-row-per-rule audit table for methodology transparency.

    This avoids cross-joining every rule against every COA summary row, which made
    the PDF audit table look repetitive. The audit now keeps each rule once and
    adds high-level decision-support output counts.
    """
    if Path(rules_path).exists():
        try:
            rules = pd.read_csv(rules_path)
            rules_file_loaded = True
        except Exception as exc:
            print(f"[Decision Support] Warning: could not read rules file: {exc}")
            rules = pd.DataFrame(
                [
                    {
                        "rule_id": "INTERNAL",
                        "min_score": None,
                        "max_score": None,
                        "required_condition": "score_and_trigger_logic",
                        "coa_level": "Internal Logic",
                        "recommendation": "See protective_intelligence_decision_layer.py",
                        "analyst_note": (
                            "Rules file could not be loaded; internal logic was used."
                        ),
                    }
                ]
            )
            rules_file_loaded = False
    else:
        rules = pd.DataFrame(
            [
                {
                    "rule_id": "INTERNAL",
                    "min_score": None,
                    "max_score": None,
                    "required_condition": "score_and_trigger_logic",
                    "coa_level": "Internal Logic",
                    "recommendation": "See protective_intelligence_decision_layer.py",
                    "analyst_note": "Rules file not found; internal logic was used.",
                }
            ]
        )
        rules_file_loaded = False

    audit = rules.copy()
    total_records = len(decision_support)

    if not decision_support.empty and "coa_level" in decision_support.columns:
        coa_counts = (
            decision_support["coa_level"]
            .value_counts(dropna=False)
            .rename_axis("output_coa_level")
            .reset_index(name="output_record_count")
        )

        coa_summary_text = "; ".join(
            f"{row['output_coa_level']}: {row['output_record_count']}"
            for _, row in coa_counts.iterrows()
        )
    else:
        coa_summary_text = "No COA output records available."

    if (
        not decision_support.empty
        and "protective_intelligence_recommendation" in decision_support.columns
    ):
        recommendation_counts = (
            decision_support["protective_intelligence_recommendation"]
            .value_counts(dropna=False)
            .rename_axis("output_recommendation")
            .reset_index(name="output_record_count")
        )

        recommendation_summary_text = "; ".join(
            f"{row['output_recommendation']}: {row['output_record_count']}"
            for _, row in recommendation_counts.iterrows()
        )
    else:
        recommendation_summary_text = "No recommendation output records available."

    audit["rules_file_loaded"] = rules_file_loaded
    audit["total_decision_records"] = total_records
    audit["output_coa_summary"] = coa_summary_text
    audit["output_recommendation_summary"] = recommendation_summary_text

    preferred_columns = [
        "rule_id",
        "min_score",
        "max_score",
        "required_condition",
        "coa_level",
        "recommendation",
        "analyst_note",
        "rules_file_loaded",
        "total_decision_records",
        "output_coa_summary",
        "output_recommendation_summary",
    ]

    preferred_columns = [
        column for column in preferred_columns if column in audit.columns
    ]

    remaining_columns = [
        column for column in audit.columns if column not in preferred_columns
    ]

    audit = audit[preferred_columns + remaining_columns]

    return audit


def save_decision_support_outputs(
    decision_support: pd.DataFrame,
    output_dir: str | Path = "outputs/tables",
    top_n: int = 25,
) -> Dict[str, Path]:
    """
    Save decision-support tables.

    Returns paths for downstream logging/reporting.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    decision_path = output_dir / "protective_intelligence_decision_support.csv"
    top_path = output_dir / "top_decision_escalations.csv"
    audit_path = output_dir / "decision_rule_audit.csv"

    decision_support.to_csv(decision_path, index=False)

    top_escalations = decision_support.sort_values(
        by=["decision_priority_rank"],
        ascending=False,
    ).head(top_n)

    top_escalations.to_csv(top_path, index=False)

    audit = build_decision_rule_audit(decision_support)
    audit.to_csv(audit_path, index=False)

    return {
        "decision_support": decision_path,
        "top_decision_escalations": top_path,
        "decision_rule_audit": audit_path,
    }


def build_decision_support_from_existing_outputs(
    input_path: str | Path | None = None,
    rules_path: str | Path = DEFAULT_RULES_PATH,
    output_dir: str | Path = "outputs/tables",
    top_n: int = 25,
) -> Dict[str, Path]:
    """
    Load the existing protective intelligence score output, build the COA
    decision-support layer, and save the output tables.

    This wrapper is designed for use inside main.py so the pipeline can call
    one clean function after build_protective_intelligence_scores().

    Parameters
    ----------
    input_path:
        Optional explicit path to an existing protective intelligence score file.
        If omitted, the function searches common project output locations.

    rules_path:
        Path to the decision-rules CSV.

    output_dir:
        Directory where output CSV tables should be saved.

    top_n:
        Number of highest-priority records to save in top_decision_escalations.csv.

    Returns
    -------
    Dict[str, Path]
        Dictionary containing output table names and file paths.
    """
    candidate_paths: List[Path] = []

    if input_path is not None:
        candidate_paths.append(Path(input_path))

    candidate_paths.extend(
        [
            Path("outputs/tables/protective_intelligence_trip_scores.csv"),
            Path("data/processed/protective_intelligence_trip_scores.csv"),
            Path("outputs/tables/protective_intelligence_scores.csv"),
            Path("data/processed/protective_intelligence_scores.csv"),
            Path("outputs/tables/protective_intelligence_posture_scores.csv"),
            Path("data/processed/protective_intelligence_posture_scores.csv"),
            Path("outputs/tables/trip_protective_intelligence_scores.csv"),
            Path("data/processed/trip_protective_intelligence_scores.csv"),
        ]
    )

    source_path = next((path for path in candidate_paths if path.exists()), None)

    if source_path is None:
        searched = "\n".join(str(path) for path in candidate_paths)
        raise FileNotFoundError(
            "Could not find an existing protective intelligence score output. "
            "Run build_protective_intelligence_scores() first.\n\n"
            f"Searched:\n{searched}"
        )

    print(f"[Decision Support] Loading source scores from: {source_path}")

    trip_scores = pd.read_csv(source_path)

    decision_support = build_decision_support_layer(
        trip_scores=trip_scores,
        rules_path=rules_path,
    )

    paths = save_decision_support_outputs(
        decision_support=decision_support,
        output_dir=output_dir,
        top_n=top_n,
    )

    print("[Decision Support] Saved decision-support outputs:")
    for name, path in paths.items():
        print(f"  - {name}: {path}")

    return paths


if __name__ == "__main__":
    build_decision_support_from_existing_outputs()