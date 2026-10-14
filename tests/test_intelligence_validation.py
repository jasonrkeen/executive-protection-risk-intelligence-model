"""Contract tests for the RPR-1 evidence coverage/validation extension."""
from datetime import date
import tempfile
from pathlib import Path
import unittest

import pandas as pd

from src.intelligence_validation_layer import (
    build_validation_tables, run_intelligence_validation_layer,
)
from src.residual_protective_risk import score_residual_risk, CAPACITY, LOAD


def movement(complete_capacity=True):
    baseline = pd.DataFrame([{
        "trip_id": "TRIP-001", "principal": "Synthetic executive",
        "country": "Test Country", "city": "Test City",
        "protective_intelligence_risk_score": 62,
        "scenario": "Site visit", "visibility_level": "Moderate",
        "travel_predictability": "Moderate", "venue_exposure": "Moderate",
        "hotel_airport_exposure": "Moderate", "online_visibility": "Low",
        "reputational_sensitivity": "Low", "business_sector_sensitivity": "Energy",
        "city_context_match_flag": "Matched city/location context",
        "nearest_airport_km": 15, "medical_capacity_score": 55,
        "support_gap_score": 25,
    }])
    capacity = (
        pd.DataFrame([{"trip_id": "TRIP-001", **dict.fromkeys(CAPACITY, 80),
                       **dict.fromkeys(LOAD, 15)}])
        if complete_capacity else None
    )
    return score_residual_risk(baseline, capacity)


def audit(trips=None, decision=None, latest=None, wgi="Available (global file only)"):
    return build_validation_tables(
        movement() if trips is None else trips,
        pd.DataFrame([{"trip_id": "TRIP-001", "coa_level": "Security Lead Review"}])
        if decision is None else decision,
        latest_acled_date=latest or date(2026, 10, 12),
        review_date=date(2026, 10, 14),
        wgi_status=wgi,
        forward_status="Baseline retained - target-year ACLED unavailable",
    )


class IntelligenceValidationTests(unittest.TestCase):
    def test_complete_inputs_have_coverage_not_probabilistic_confidence(self):
        tables = audit()
        out = tables["intelligence_confidence_scores"].iloc[0]
        self.assertEqual(out["trip_id"], "TRIP-001")
        self.assertEqual(out["intelligence_confidence_score"], 100.0)
        self.assertIn("unverified", out["intelligence_confidence_label"])
        self.assertEqual(len(tables["source_coverage_gaps"]), 0)
        self.assertEqual(len(tables["analyst_collection_plan"]), 0)
        self.assertEqual(list(tables["analyst_collection_plan"].columns)[0], "trip_id")

    def test_stale_extract_is_flagged_even_when_city_event_counters_exist(self):
        tables = audit(latest=date(2024, 12, 31))
        output = tables["intelligence_confidence_scores"].iloc[0]
        self.assertTrue(output["acled_stale_flag"])
        self.assertEqual(output["acled_age_days"], 652)
        self.assertLess(output["intelligence_confidence_score"], 100)
        self.assertIn("acled_stale", set(tables["source_coverage_gaps"]["gap_code"]))

    def test_unknown_capacity_and_no_coa_never_earn_credit(self):
        tables = audit(trips=movement(False), decision=pd.DataFrame())
        output = tables["intelligence_confidence_scores"].iloc[0]
        self.assertTrue(output["capacity_assessment_missing_flag"])
        self.assertTrue(output["coa_missing_flag"])
        self.assertEqual(len(tables["intelligence_confidence_scores"]), 1)
        self.assertEqual(set(tables["analyst_collection_plan"]["trip_id"]), {"TRIP-001"})

    def test_city_default_and_missing_support_are_not_treated_as_valid_data(self):
        trips = movement()
        trips["city_context_match_flag"] = "No exact city/location match; neutral defaults used"
        trips["nearest_airport_km"] = float("nan")
        tables = audit(trips=trips)
        out = tables["intelligence_confidence_scores"].iloc[0]
        self.assertTrue(out["city_context_missing_flag"])
        self.assertTrue(out["support_proxy_missing_flag"])

    def test_wgi_failure_is_not_ignored(self):
        output = audit(wgi="Unavailable")["intelligence_confidence_scores"].iloc[0]
        self.assertTrue(output["wgi_unavailable_flag"])

    def test_duplicate_decision_ids_fail_closed(self):
        decision = pd.DataFrame([
            {"trip_id": "TRIP-001", "coa_level": "Routine"},
            {"trip_id": "TRIP-001", "coa_level": "Routine"},
        ])
        with self.assertRaises(ValueError):
            audit(decision=decision)

    def test_altered_rpr1_residual_result_is_rejected(self):
        trips = movement()
        trips.loc[0, "residual_risk_score"] = 1
        with self.assertRaises(ValueError):
            audit(trips=trips)

    def test_file_outputs_and_source_statuses_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            processed, outputs = root / "data", root / "tables"
            processed.mkdir()
            outputs.mkdir()
            movement().to_csv(processed / "residual_protective_risk_scores.csv", index=False)
            pd.DataFrame([{"trip_id": "TRIP-001", "coa_level": "Routine"}]).to_csv(
                outputs / "protective_intelligence_decision_support.csv", index=False
            )
            pd.DataFrame([{"latest_event_date": "2024-12-31"}]).to_csv(
                processed / "city_ep_risk_features.csv", index=False
            )
            pd.DataFrame([{"political_stability": float("nan")}]).to_csv(
                processed / "worldbank_ep_indicators.csv", index=False
            )
            paths = run_intelligence_validation_layer(processed, outputs, review_date=date(2026, 10, 14))
            self.assertEqual(len(paths), 4)
            self.assertTrue(all(p.exists() for p in paths.values()))
            scores = pd.read_csv(paths["intelligence_confidence_scores"])
            self.assertEqual(len(scores), 1)
            self.assertTrue(scores.iloc[0]["acled_stale_flag"])
            self.assertTrue(scores.iloc[0]["wgi_unavailable_flag"])


if __name__ == "__main__":
    unittest.main()
