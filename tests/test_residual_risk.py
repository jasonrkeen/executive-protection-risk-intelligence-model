import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.residual_protective_risk import CAPACITY, LOAD, FIELDS, score_residual_risk, build_residual_risk
from src.protective_intelligence_decision_layer import build_decision_support_layer, build_decision_support_from_existing_outputs


def trips(score=62):
    return pd.DataFrame([{"trip_id": "001", "protective_intelligence_risk_score": score}])


def capacity(c=100, load=0):
    return pd.DataFrame([{"trip_id": "001", **dict.fromkeys(CAPACITY, c), **dict.fromkeys(LOAD, load)}])


class ResidualTests(unittest.TestCase):
    def test_hand_calculated_endpoints(self):
        strong = score_residual_risk(trips(), capacity()).iloc[0]
        weak = score_residual_risk(trips(), capacity(0, 100)).iloc[0]
        saturated = score_residual_risk(trips(), capacity(100, 100)).iloc[0]
        self.assertEqual(strong.residual_risk_score, 46.5)
        self.assertEqual(weak.residual_risk_score, 77.5)
        self.assertAlmostEqual(saturated.residual_risk_score, 57.35)
        self.assertEqual(saturated.protective_coverage_gap, 35)

    def test_monotonicity_and_bounds_grid(self):
        for pi in (0, 20, 62, 100):
            for load in (0, 25, 50, 75, 100):
                values = [score_residual_risk(trips(pi), capacity(c, load)).iloc[0].residual_risk_score for c in range(0, 101, 10)]
                self.assertTrue(all(0 <= v <= 100 for v in values))
                self.assertTrue(all(a >= b for a, b in zip(values, values[1:])))
            values = [score_residual_risk(trips(pi), capacity(80, load)).iloc[0].residual_risk_score for load in range(101)]
            self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))

    def test_missing_and_partial_unknown(self):
        for cap in (None, capacity().drop(columns=[FIELDS[0]]), pd.DataFrame(columns=["trip_id"])):
            row = score_residual_risk(trips(), cap).iloc[0]
            self.assertEqual(row.residual_risk_score, 62)
            self.assertEqual(row.capacity_modifier, 1)
            self.assertTrue(pd.isna(row.protective_coverage_gap))
            self.assertEqual(row.residual_review_state, "Capacity assessment required")

    def test_invalid_values_rejected(self):
        for bad in (-1, 101, np.inf, "bad"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    score_residual_risk(trips(bad), capacity())
                cap = capacity().astype(object)
                cap.loc[0, FIELDS[0]] = bad
                with self.assertRaises(ValueError):
                    score_residual_risk(trips(), cap)
        with self.assertRaises(ValueError):
            score_residual_risk(trips(np.nan), capacity())

    def test_join_rejections(self):
        for cap in (pd.concat([capacity(), capacity()]), capacity().assign(trip_id="other"), capacity().assign(trip_id=None)):
            with self.assertRaises(ValueError):
                score_residual_risk(trips(), cap)
        with self.assertRaises(ValueError):
            score_residual_risk(pd.concat([trips(), trips()]), capacity())

    def test_no_support_gap_double_count_or_input_mutation(self):
        t = trips().assign(support_gap_score=0)
        original = t.copy(deep=True)
        a = score_residual_risk(t, capacity())
        b = score_residual_risk(t.assign(support_gap_score=100), capacity())
        pd.testing.assert_frame_equal(t, original)
        self.assertEqual(a.residual_risk_score[0], b.residual_risk_score[0])
        self.assertEqual(a.protective_intelligence_risk_score[0], 62)

    def test_coa_floor_and_no_downgrade(self):
        low = build_decision_support_layer(score_residual_risk(trips(20), capacity(0, 100)))
        self.assertEqual(low.coa_level[0], "Security Lead Review")
        self.assertEqual(low.primary_decision_driver[0], "Protective-planning review required")
        unknown = build_decision_support_layer(score_residual_risk(trips(20)))
        self.assertEqual(unknown.coa_level[0], "Validate")
        self.assertEqual(unknown.data_confidence[0], "Low")
        baseline = build_decision_support_layer(trips(95))
        mitigated = build_decision_support_layer(score_residual_risk(trips(95), capacity()))
        self.assertEqual(baseline.coa_level[0], mitigated.coa_level[0])

    def test_csv_pipeline_preserves_ids_and_consumes_residual(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            trips(20).to_csv(root / 'pi.csv', index=False)
            capacity(0, 100).to_csv(root / 'capacity.csv', index=False)
            output = build_residual_risk(root/'pi.csv', root/'capacity.csv', root/'residual.csv')
            self.assertEqual(pd.read_csv(output, dtype={"trip_id": str}).trip_id[0], "001")
            paths = build_decision_support_from_existing_outputs(output, output_dir=root/'coa')
            result = pd.read_csv(paths['decision_support'], dtype={"trip_id": str})
            self.assertEqual(result.trip_id[0], "001")
            self.assertEqual(result.coa_level[0], "Security Lead Review")
            self.assertIn('residual_risk_score', result)
            with self.assertRaises(FileNotFoundError):
                build_decision_support_from_existing_outputs(root/'missing.csv')

    def test_pipeline_order(self):
        import src.main as pipeline
        calls = []
        names = [name for name, value in vars(pipeline).items() if callable(value) and name != 'main']
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in names:
                stack.enter_context(patch.object(pipeline, name, side_effect=lambda *a, _name=name, **kw: calls.append((_name, kw)) or 'residual.csv'))
            pipeline.main()
        order = [name for name, kw in calls]
        self.assertLess(order.index('build_protective_intelligence_scores'), order.index('build_residual_risk'))
        self.assertLess(order.index('build_residual_risk'), order.index('build_decision_support_from_existing_outputs'))
        self.assertEqual(dict(calls)['build_decision_support_from_existing_outputs']['input_path'], 'residual.csv')

    def test_streamlit_populated_and_empty(self):
        from streamlit.testing.v1 import AppTest
        for populated in (False, True):
            script = ('import pandas as pd\nfrom src.residual_risk_views import show_residual_risk_tab\n'
                      'from tests.test_residual_risk import trips, capacity\n'
                      'from src.residual_protective_risk import score_residual_risk\n'
                      'show_residual_risk_tab(' + ('score_residual_risk(trips(), capacity())' if populated else 'pd.DataFrame()') + ')')
            app = AppTest.from_string(script).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.dataframe), int(populated))

    def test_review_threshold_boundaries(self):
        # At zero workload, capacity 40 gives gap 60 exactly.
        self.assertTrue(score_residual_risk(trips(20), capacity(40, 0)).residual_review_required[0])
        self.assertFalse(score_residual_risk(trips(20), capacity(40.01, 0)).residual_review_required[0])
        self.assertTrue(score_residual_risk(trips(20), capacity(100, 70)).residual_review_required[0])
        self.assertFalse(score_residual_risk(trips(20), capacity(100, 69.99)).residual_review_required[0])
        self.assertTrue(score_residual_risk(trips(80), capacity(100, 0)).residual_review_required[0])
        self.assertFalse(score_residual_risk(trips(79.99), capacity(100, 0)).residual_review_required[0])

    def test_full_dashboard_tab(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        labels = [tab.label for tab in app.tabs]
        self.assertEqual(labels[3:6], ['PI Posture', 'Residual Risk', 'Decision Support'])

    def test_report_section_builds_known_and_unknown(self):
        from src.residual_risk_views import add_residual_risk_section
        from src.report_generator import make_styles
        from reportlab.platypus import SimpleDocTemplate
        with tempfile.TemporaryDirectory() as td:
            for name, scores in [('known', score_residual_risk(trips(), capacity())),
                                 ('unknown', score_residual_risk(trips())),
                                 ('absent', pd.DataFrame())]:
                path = Path(td) / (name + '.pdf')
                story = []
                add_residual_risk_section(story, make_styles(), scores)
                SimpleDocTemplate(str(path)).build(story)
                self.assertGreater(path.stat().st_size, 1000)

    def test_explicit_missing_capacity_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                build_residual_risk(Path(td)/'pi.csv', Path(td)/'missing.csv')

    def test_corrupt_residual_cannot_bypass_coa(self):
        for column, value in [('residual_review_state', 'No additional capacity review trigger'),
                              ('residual_risk_score', 0), ('residual_model_version', 'old')]:
            scored = score_residual_risk(trips(20), capacity(0, 100))
            scored[column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                build_decision_support_layer(scored)
        with self.assertRaises(ValueError):
            build_decision_support_layer(score_residual_risk(trips()).drop(columns=['residual_review_state']))

    def test_residual_audit_counts(self):
        from src.protective_intelligence_decision_layer import build_decision_rule_audit
        scored = pd.concat([score_residual_risk(trips(20)),
                            score_residual_risk(trips(20), capacity(0, 100)).assign(trip_id='002')], ignore_index=True)
        audit = build_decision_rule_audit(build_decision_support_layer(scored)).set_index('rule_id')
        self.assertEqual(audit.loc['RPR1-UNKNOWN', 'triggered_record_count'], 1)
        self.assertEqual(audit.loc['RPR1-REVIEW', 'triggered_record_count'], 1)

    def test_real_pi_to_residual_to_coa_synthetic(self):
        from src import protective_intelligence_score as pi
        from src.report_generator import read_csv_if_exists
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = pd.DataFrame([dict(trip_id='001', principal='Synthetic', city='Test', country='Test',
                scenario='routine executive travel', visibility_level='low', travel_predictability='low',
                venue_exposure='low', hotel_airport_exposure='low', online_visibility='low',
                reputational_sensitivity='low', business_sector_sensitivity='other')])
            raw.to_csv(root/'raw.csv', index=False)
            with patch.object(pi, 'TRIP_INPUT_FILE', root/'raw.csv'):
                loaded = pi.load_trip_inputs()
            self.assertEqual(loaded.trip_id[0], '001')
            context = pd.DataFrame([dict(city_key='test', country_key='test', city_ep_risk_score=40,
                support_gap_score=20, city_operational_ep_risk_score=35, rank=1)])
            baseline = pi.calculate_protective_intelligence_scores(loaded, context)
            baseline.to_csv(root/'pi.csv', index=False)
            capacity(0, 100).to_csv(root/'capacity.csv', index=False)
            output = build_residual_risk(root/'pi.csv', root/'capacity.csv', root/'residual.csv')
            displayed = read_csv_if_exists(output)
            self.assertEqual(displayed.trip_id[0], '001')
            self.assertAlmostEqual(displayed.protective_intelligence_risk_score[0], baseline.protective_intelligence_risk_score[0])
            result = build_decision_support_from_existing_outputs(output, output_dir=root/'coa')
            self.assertEqual(pd.read_csv(result['decision_support']).coa_level[0], 'Security Lead Review')

    def test_order_independent_matching_and_empty_schema(self):
        ts = pd.concat([trips(20), trips(80).assign(trip_id='002')], ignore_index=True)
        cs = pd.concat([capacity(0, 100).assign(trip_id='002'), capacity()], ignore_index=True)
        result = score_residual_risk(ts, cs).set_index('trip_id')
        self.assertEqual(result.loc['001', 'residual_risk_score'], 15)
        self.assertEqual(result.loc['002', 'residual_risk_score'], 100)
        with self.assertRaises(ValueError):
            score_residual_risk(trips().drop(columns=['protective_intelligence_risk_score']))
        with self.assertRaises(ValueError):
            score_residual_risk(pd.concat([trips(), trips()['trip_id']], axis=1))

    def test_invalid_views_do_not_present_scores(self):
        from streamlit.testing.v1 import AppTest
        script = ('from tests.test_residual_risk import trips, capacity\n'
                  'from src.residual_protective_risk import score_residual_risk\n'
                  'from src.residual_risk_views import show_residual_risk_tab\n'
                  'scores=score_residual_risk(trips(), capacity())\n'
                  'scores["residual_risk_score"]=0\nshow_residual_risk_tab(scores)')
        app = AppTest.from_string(script).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.dataframe), 0)
        from src.residual_risk_views import add_residual_risk_section
        from src.report_generator import make_styles
        story = []
        add_residual_risk_section(story, make_styles(), trips())
        text = ' '.join(item.getPlainText() for item in story if hasattr(item, 'getPlainText'))
        self.assertIn('invalid or incompatible', text)

    def test_custom_rules_are_used_in_saved_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            score_residual_risk(trips()).to_csv(root/'residual.csv', index=False)
            pd.DataFrame([{'rule_id': 'CUSTOM', 'coa_level': 'Validate'}]).to_csv(root/'rules.csv', index=False)
            paths = build_decision_support_from_existing_outputs(root/'residual.csv', rules_path=root/'rules.csv', output_dir=root/'coa')
            rules = pd.read_csv(paths['decision_rule_audit']).rule_id.tolist()
            self.assertEqual(rules, ['CUSTOM', 'RPR1-UNKNOWN', 'RPR1-REVIEW'])


if __name__ == '__main__':
    unittest.main()
