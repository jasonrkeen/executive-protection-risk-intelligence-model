"""Source-vintage and WGI uncertainty research contracts (entirely synthetic).

Do not interpret WGI standard errors as independent empirical draws. The
perturbations below are sensitivity scenarios, not calibrated risk uncertainty,
not source verification and not operational protection advice.
"""
from __future__ import annotations

from datetime import date
import hashlib
import math

import numpy as np
import pandas as pd

from src.config import END_YEAR, START_YEAR
from src.offline_synthetic_demo import country_scores

DIMENSIONS = (
    "political_stability",
    "rule_of_law",
    "control_of_corruption",
    "government_effectiveness",
    "voice_accountability",  # fetched in baseline, not weighted in governance calculation
)
SCORED = DIMENSIONS[:4]
UNIT = "standard_normal_estimate"
RELEASE = "SYN-WGI-RELEASE-2026-TOY"
EVENT_SNAPSHOT = "SYN-ACLED-STYLE-2026-10-17"
AS_OF = date(2026, 10, 17)
SOURCE_STATUS = "SYNTHETIC_DECLARED_ONLY_NO_AUTHENTICATION"
WGI_COLS = {
    "country", "indicator", "source_year", "estimate", "standard_error",
    "source_count", "estimate_unit", "release_id", "release_date",
    "retrieved_on", "source_ref", "data_class",
}
EVENT_COLS = {
    "event_id_cnty", "event_date", "event_year", "time_precision",
    "source_ref", "snapshot_id", "observed_at", "revision_state", "data_class",
}


class SourceEvidenceError(ValueError):
    """Source quality or comparability is not sufficient for the toy experiment."""


def _iso_dates(s: pd.Series, field: str) -> pd.Series:
    values = s.astype(str)
    dates = pd.to_datetime(values, format="%Y-%m-%d", errors="coerce")
    if dates.isna().any() or not dates.dt.strftime("%Y-%m-%d").eq(values).all():
        raise SourceEvidenceError(f"Invalid source dates: {field}")
    return dates


def _positive_int(s: pd.Series, field: str, *, minimum: int = 1) -> pd.Series:
    numeric = pd.to_numeric(s, errors="coerce")
    if (
        numeric.isna().any() or (~np.isfinite(numeric)).any()
        or (numeric < minimum).any() or (numeric % 1 != 0).any()
    ):
        raise SourceEvidenceError(f"Invalid integer source field: {field}")
    return numeric.astype(int)


def require_wgi_source_matrix(
    panel: pd.DataFrame,
    indicators: pd.DataFrame,
    *,
    as_of: date = AS_OF,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Country x dimension checks, with visible missingness and no inferred values.

    A full exact unit/release contract is structural. Within that contract,
    absent dimensional rows are flagged as BLOCKED_MISSING_SOURCE_DIMENSION
    instead of silently allowing a country with one global data-coverage flag.
    """
    if panel.empty or panel.columns.duplicated().any() or not WGI_COLS.issubset(panel):
        raise SourceEvidenceError("Missing or malformed synthetic WGI source schema")
    if (
        indicators.empty or "country" not in indicators
        or indicators.country.isna().any()
        or indicators.country.duplicated().any()
        or not set(DIMENSIONS).issubset(indicators)
    ):
        raise SourceEvidenceError("Synthetic country-grain baseline is incomplete")
    if set(panel.country) - set(indicators.country):
        raise SourceEvidenceError("Unexpected source countries outside frozen cohort")
    if panel[["country", "indicator"]].isna().any().any() or panel.duplicated(
        ["country", "indicator"]
    ).any():
        raise SourceEvidenceError("Duplicate/blank WGI country-dimension entries")
    if (not panel["indicator"].isin(DIMENSIONS).all()
            or not panel["estimate_unit"].eq(UNIT).all()):
        raise SourceEvidenceError("WGI dimensions/scales cannot be mixed (estimate vs 0-100)")
    if (not panel["data_class"].eq("synthetic").all()
            or not panel["release_id"].eq(RELEASE).all()):
        raise SourceEvidenceError("Mixed/unspecified WGI release or nonsynthetic records")
    release_dates = _iso_dates(panel["release_date"], "release_date")
    retrieved = _iso_dates(panel["retrieved_on"], "retrieved_on")
    years = _positive_int(panel["source_year"], "source_year", minimum=1996)
    counts = _positive_int(panel["source_count"], "source_count")
    values = pd.to_numeric(panel["estimate"], errors="coerce")
    errors = pd.to_numeric(panel["standard_error"], errors="coerce")
    if (
        values.isna().any() or (~np.isfinite(values)).any()
        or errors.isna().any() or (~np.isfinite(errors)).any()
        or (errors <= 0).any() or (errors > 5).any()
        or not panel["source_ref"].astype(str).str.startswith("synthetic://wgi/").all()
        or (years != END_YEAR).any()
        or (release_dates.dt.date < date(END_YEAR, 1, 1)).any()
        or (release_dates > retrieved).any()
        or (retrieved.dt.date > as_of).any()
    ):
        raise SourceEvidenceError(
            "WGI release, source year, standard error, provenance or retrieval invalid"
        )
    src = panel.copy()
    src["source_year"] = years
    src["source_count"] = counts
    src["estimate"] = values
    src["standard_error"] = errors
    src["source_vintage_after_baseline"] = release_dates.dt.year > END_YEAR
    # Compared with the frozen original synthetic 'World Bank-like' indicators.
    matrix = pd.MultiIndex.from_product(
        [sorted(indicators.country), DIMENSIONS], names=["country", "indicator"]
    )
    result = src.set_index(["country", "indicator"]).reindex(matrix).reset_index()
    frozen = indicators.set_index("country")
    result["model_uses_indicator"] = result.indicator.isin(SCORED)
    expected = []
    for entry in result.itertuples():
        original = frozen.loc[entry.country, entry.indicator]
        expected.append(original)
    result["frozen_baseline_input"] = pd.to_numeric(expected, errors="coerce")
    match = np.isclose(
        pd.to_numeric(result["estimate"], errors="coerce"),
        result["frozen_baseline_input"],
        rtol=0, atol=1e-12, equal_nan=False,
    )
    result["evidence_status"] = np.where(
        result["estimate"].isna(), "BLOCKED_MISSING_COUNTRY_DIMENSION",
        np.where(match, "SYNTHETIC_ESTIMATE_AND_ERROR_PRESENT",
                 "BLOCKED_CONFLICT_WITH_FROZEN_INPUT"),
    )
    result["source_authenticated"] = False
    result["standard_errors_empirically_validated"] = False
    result["source_release_2026_on_2024_model"] = True
    readiness_rows = []
    for country, group in result.groupby("country", sort=True):
        mandatory = group[group["model_uses_indicator"]]
        ready = (len(mandatory) == 4 and
                 mandatory["evidence_status"].eq("SYNTHETIC_ESTIMATE_AND_ERROR_PRESENT").all())
        supplemental = group[~group["model_uses_indicator"]]
        readiness_rows.append({
            "country": country,
            "scored_dimensions_covered": int(
                mandatory["evidence_status"].eq("SYNTHETIC_ESTIMATE_AND_ERROR_PRESENT").sum()
            ),
            "required_scored_dimensions": len(SCORED),
            "supplemental_dimensions_covered": int(
                supplemental["evidence_status"].eq("SYNTHETIC_ESTIMATE_AND_ERROR_PRESENT").sum()
            ),
            "source_ready_for_toy_sensitivity": bool(ready),
            "risk_output_policy": (
                "RESEARCH_ONLY_SOURCE_DECLARATIONS" if ready
                else "WITHHELD_MISSING_OR_INCOMPATIBLE_SOURCE"
            ),
            "actual_wgi_country_coverage_verified": False,
        })
    return result, pd.DataFrame(readiness_rows)


def require_event_source_ledger(
    events: pd.DataFrame, ledger: pd.DataFrame, *, as_of: date = AS_OF,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate event-identifiers, source, date precision and a single snapshot.

    This cannot prove a country without recorded events is safe. Neither a
    source reference nor a matching event ID authenticates a third-party export.
    """
    if events.empty or ledger.empty or not EVENT_COLS.issubset(ledger):
        raise SourceEvidenceError("Event/snapshot lineage is absent or malformed")
    if ledger.columns.duplicated().any() or events.columns.duplicated().any():
        raise SourceEvidenceError("Duplicate event/provenance headers")
    if (
        "event_id_cnty" not in events or "event_date" not in events
        or "year" not in events or "country" not in events
        or events.event_id_cnty.duplicated().any()
        or ledger.event_id_cnty.duplicated().any()
    ):
        raise SourceEvidenceError("Missing/duplicate event identity")
    if set(events.event_id_cnty) != set(ledger.event_id_cnty):
        raise SourceEvidenceError("Event lineage has missing or orphaned event IDs")
    if not ledger["data_class"].eq("synthetic").all():
        raise SourceEvidenceError("Only fictional event metadata may be used")
    if not ledger["snapshot_id"].eq(EVENT_SNAPSHOT).all():
        raise SourceEvidenceError("Mixed source extract snapshots cannot be combined")
    if not ledger["source_ref"].astype(str).str.startswith(
        "synthetic://acled-style/"
    ).all():
        raise SourceEvidenceError("Missing source references for synthetic events")
    if not ledger["revision_state"].isin(
        ("first_capture", "synthetic_revision_example")
    ).all():
        raise SourceEvidenceError("Unknown source revision flags")
    precision = _positive_int(ledger["time_precision"], "time_precision")
    if not precision.isin([1, 2, 3]).all():
        raise SourceEvidenceError("Source event-date precision must be 1, 2, or 3")
    event_dates = _iso_dates(events["event_date"], "ACLED-shaped event date")
    side_dates = _iso_dates(ledger["event_date"], "event provenance date")
    observed = _iso_dates(ledger["observed_at"], "extract timestamp")
    if observed.dt.date.gt(as_of).any():
        raise SourceEvidenceError("Future source extraction timestamp")
    event_years = _positive_int(events["year"], "event year", minimum=START_YEAR)
    source_years = _positive_int(ledger["event_year"], "source year", minimum=START_YEAR)
    if (
        (event_years != event_dates.dt.year).any()
        or (source_years != side_dates.dt.year).any()
    ):
        raise SourceEvidenceError("Event year disagrees with event date")
    source = ledger.copy()
    source["time_precision"] = precision
    source = source.rename(columns={"event_year": "source_event_year", "event_date": "source_event_date"})
    merged = events[["event_id_cnty", "event_date", "year", "country"]].merge(
        source, on="event_id_cnty", how="inner", validate="one_to_one"
    ).sort_values("event_id_cnty").reset_index(drop=True)
    if (
        not merged.event_date.eq(merged.source_event_date).all()
        or not pd.to_numeric(merged.year).eq(
            pd.to_numeric(merged.source_event_year)
        ).all()
    ):
        raise SourceEvidenceError("Event/source sidecar date or year disagreement")
    # Align year grain to integers before joining the year-presence grid.
    # Otherwise a string "2024" will silently fail to match integer 2024,
    # producing false zero-event cells despite verified raw records.
    merged["year"] = pd.to_numeric(merged["year"], errors="raise").astype(int)
    merged["source_event_year"] = pd.to_numeric(
        merged["source_event_year"], errors="raise"
    ).astype(int)
    merged["record_present_not_source_authenticated"] = True
    merged["source_completeness_verified"] = False
    counts = merged.groupby(["country", "year"]).agg(
        event_records=("event_id_cnty", "size"),
        records_with_imprecise_dates=(
            "time_precision", lambda x: int((x > 1).sum())
        ),
        records_marked_as_synthetic_revisions=(
            "revision_state", lambda x: int(x.eq("synthetic_revision_example").sum())
        ),
    ).reset_index()
    grid = pd.MultiIndex.from_product(
        [sorted(events.country.unique()), range(START_YEAR, as_of.year + 1)],
        names=["country", "year"]
    )
    year_table = counts.set_index(["country", "year"]).reindex(
        grid, fill_value=0
    ).reset_index()
    year_table["status"] = np.where(
        year_table.event_records.gt(0),
        "SYNTHETIC_OBSERVATION_PRESENT_NOT_COVERAGE",
        "NO_RECORDED_EVENTS_NOT_ZERO_RISK",
    )
    year_table["reporting_completeness_verified"] = False
    year_table["snapshot_id"] = EVENT_SNAPSHOT
    return merged, year_table


def full_country_reruns(
    yearly: pd.DataFrame,
    indicators: pd.DataFrame,
    panel: pd.DataFrame,
    readiness: pd.DataFrame,
    original: pd.DataFrame,
    *,
    seed: int = 42,
    draws: int = 48,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rerun the actual country score + severity functions on WGI perturbations.

    Scenario distributions assume independent normal standard-error draws,
    which is NOT a provider covariance model, and are illustrative only.
    No simulation can establish empirically calibrated incident probability.
    """
    if not isinstance(draws, int) or not 1 <= draws <= 250:
        raise SourceEvidenceError("Synthetic draws must be 1-250")
    if not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise SourceEvidenceError("Invalid repeatability seed")
    if not readiness["source_ready_for_toy_sensitivity"].all():
        raise SourceEvidenceError("Missing country/dimension WGI evidence; withhold model reruns")
    needed = {"country", "executive_protection_risk_score", "governance_risk_score",
              "severity_uplift_total", "risk_bucket"}
    if not needed.issubset(original) or original.country.duplicated().any():
        raise SourceEvidenceError("Historical source scores missing or not unique")
    if set(indicators.country) != set(original.country):
        raise SourceEvidenceError("Frozen country cohort mismatch")
    rebuilt = country_scores(yearly, indicators).set_index("country")
    truth = original.set_index("country")
    for field in ("executive_protection_risk_score", "governance_risk_score", "severity_uplift_total"):
        if not np.allclose(rebuilt[field], truth[field], atol=0.025, rtol=0):
            raise SourceEvidenceError(f"Original score not reproducible from baseline inputs: {field}")

    scored = panel[panel.indicator.isin(SCORED)].copy().sort_values(
        ["country", "indicator"]
    ).reset_index(drop=True)
    rng = np.random.default_rng(seed)
    rows = []
    for mode, scale in (("DECLARED_MARGINAL_SE", 1.0), ("AMPLIFIED_STRESS_3X_SE", 3.0)):
        for draw in range(draws):
            perturbed = indicators.copy()
            # Mean estimates and SDs only from explicitly synthetic, reviewed
            # country/dimension rows. Actual WGI covariance is NOT modeled.
            z = rng.standard_normal(len(scored))
            new_values = scored["estimate"].to_numpy() + scale * scored[
                "standard_error"
            ].to_numpy() * z
            for (record, value) in zip(scored.itertuples(), new_values):
                row_mask = perturbed.country.eq(record.country)
                if int(row_mask.sum()) != 1:
                    raise SourceEvidenceError("Unexpected country multiplicity")
                perturbed.loc[row_mask, record.indicator] = float(value)
            recalculated = country_scores(yearly, perturbed)
            recalculated = recalculated.sort_values(
                ["executive_protection_risk_score", "country"], ascending=[False, True]
            ).reset_index(drop=True)
            recalculated["scenario_rank"] = recalculated.index + 1
            for rec in recalculated.itertuples(index=False):
                baseline = truth.loc[rec.country]
                rows.append({
                    "scenario": mode,
                    "simulated_draw": draw + 1,
                    "country": rec.country,
                    "baseline_score": float(baseline["executive_protection_risk_score"]),
                    "rerun_score": float(rec.executive_protection_risk_score),
                    "score_delta": round(
                        float(rec.executive_protection_risk_score)
                        - float(baseline["executive_protection_risk_score"]), 4
                    ),
                    "baseline_governance_component": float(baseline["governance_risk_score"]),
                    "rerun_governance_component": float(rec.governance_risk_score),
                    "baseline_uplift": float(baseline["severity_uplift_total"]),
                    "rerun_uplift": float(rec.severity_uplift_total),
                    "severity_was_recalculated": True,
                    "baseline_risk_band": str(baseline["risk_bucket"]),
                    "rerun_risk_band": str(rec.risk_bucket),
                    "risk_band_changed_in_toy": (
                        str(baseline["risk_bucket"]) != str(rec.risk_bucket)
                    ),
                    "rerun_rank": int(rec.scenario_rank),
                    "wgi_correlation_assumed_independent": True,
                    "actual_world_bank_uncertainty_verified": False,
                    "real_outcome_probability": "NOT_ESTIMATED",
                })
    runs = pd.DataFrame(rows).sort_values(
        ["scenario", "simulated_draw", "country"]
    ).reset_index(drop=True)
    summary = runs.groupby(["scenario", "country"], sort=True).agg(
        draws=("simulated_draw", "count"),
        baseline_score=("baseline_score", "first"),
        minimum_rerun_score=("rerun_score", "min"),
        median_rerun_score=("rerun_score", "median"),
        maximum_rerun_score=("rerun_score", "max"),
        toy_risk_band_changes=("risk_band_changed_in_toy", "sum"),
        severity_ups_recomputed=("severity_was_recalculated", "sum"),
        rank_1_count=("rerun_rank", lambda x: int((x == 1).sum())),
    ).reset_index()
    summary["interpretation"] = "TOY_SENSITIVITY_NOT_STATISTICAL_RISK_CI"
    return runs, summary
