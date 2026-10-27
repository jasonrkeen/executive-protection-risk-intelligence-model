"""Fictional consumer fixtures only; no provider requests or real observations."""
from copy import deepcopy
from dataclasses import asdict
from datetime import date
import hashlib
import json
from unittest.mock import patch

import pytest

import src.wgi_numeric_consumer as consumer
from src.wgi_numeric_adapter import FIELDS, UNITS
from src.wgi_observation_policy import Coverage, Policy, evaluate, json_hash

DIMS = ('PV', 'RL', 'CC', 'GE')


def fixture():
    decisions, numeric = [], []
    for policy in (Policy('strict', 0, DIMS), Policy('lag', 1, DIMS)):
        for country, missing in [('AAA', frozenset()), ('BBB', frozenset(DIMS))]:
            d = evaluate([Coverage(country, 2025, missing)], country, 2026, policy, date(2026, 10, 26))
            decisions.append(d)
            if not d['policy_eligible']:
                continue
            for dim in DIMS:
                numeric.append({'country_code': country, 'target_year': 2026, 'policy': policy.name,
                    'dimension': dim, 'observation_year': 2025, 'policy_decision': d['decision'],
                    'estimate': -3.1, 'estimate_standard_error': .123456789, 'source_count': 7,
                    'governance_score': 0, 'score_ci90_lower': 0, 'score_ci90_upper': 10.123456789,
                    'units': deepcopy(UNITS), 'confidence_level': .90, 'confidence_interval_scale': 'score',
                    'indicator_ids': {f: f'GOV_WGI_{dim}.{f}' for f in FIELDS},
                    'source_payload_sha256': {f: 'a' * 64 for f in FIELDS},
                    'source_id': '3', 'source_lastupdated': '2026-09-25', 'release_label': 'FICTIONAL_TEST_RELEASE',
                    'parity_receipt_canonical_sha256': 'b' * 64,
                    'assessment_date': d['assessment_date'], 'production_use_authorized': False,
                    'point_in_time_backtest_validated': False, 'data_class': 'REAL_WGI_AGGREGATES_RESEARCH_ONLY'})
    return decisions, numeric


def test_complete_cohort_preserves_every_field_and_withheld_nulls():
    decisions, numeric = fixture()
    original = deepcopy((decisions, numeric))
    cases = consumer.consume(decisions, numeric, DIMS)
    assert len(cases) == 4
    assert sum(c.dimensions is None for c in cases) == 3
    for c in cases:
        assert c.decision in decisions
        assert not c.production_use_authorized and not c.point_in_time_backtest_validated
        if c.dimensions is not None:
            assert len(c.dimensions) == 4
            for dim, row in c.dimensions.items():
                assert row == next(n for n in numeric if n['dimension'] == dim)
                assert row['observation_year'] == 2025 and row['target_year'] == 2026
                assert row['governance_score'] == 0 and row['estimate'] == -3.1
    assert original == (decisions, numeric)
    # Returned research views must not alias mutable source records.
    cases[0].decision['assessment_date'] = 'CHANGED'
    next(c for c in cases if c.dimensions is not None).dimensions['PV']['units']['EST'] = 'CHANGED'
    assert original == (decisions, numeric)


def test_order_invariance_and_no_numeric_for_all_withheld():
    d, n = fixture()
    assert consumer.consume(d, n, DIMS) == consumer.consume(d[::-1], n[::-1], DIMS)
    withheld = [r for r in d if not r['policy_eligible']]
    assert all(c.dimensions is None for c in consumer.consume(withheld, [], DIMS))


@pytest.mark.parametrize('change', ['missing_dimension', 'duplicate_dimension', 'orphan', 'withheld_value',
    'wrong_year', 'bool_year', 'wrong_status', 'wrong_units', 'wrong_interval_scale', 'wrong_confidence',
    'wrong_indicator', 'production', 'backtest', 'assessment', 'duplicate_decision', 'wrong_eligibility',
    'selected_withheld', 'future_selected', 'stale_selected', 'missing_decision', 'required_dimension'])
def test_bad_joins_and_semantics_fail(change):
    d, n = fixture()
    eligible = next(r for r in d if r['policy_eligible'])
    if change == 'missing_dimension': n.pop()
    if change == 'duplicate_dimension': n.append(deepcopy(n[0]))
    if change == 'orphan': n[0]['country_code'] = 'CCC'
    if change == 'withheld_value': n[0]['policy'] = 'strict'
    if change == 'wrong_year': n[0]['observation_year'] = 2026
    if change == 'bool_year': n[0]['observation_year'] = True
    if change == 'wrong_status': n[0]['policy_decision'] = 'RESEARCH_ELIGIBLE_EXACT_YEAR'
    if change == 'wrong_units': n[0]['units']['SE'] = 'score'
    if change == 'wrong_interval_scale': n[0]['confidence_interval_scale'] = 'estimate'
    if change == 'wrong_confidence': n[0]['confidence_level'] = .95
    if change == 'wrong_indicator': n[0]['indicator_ids']['SE'] = 'PV.SE'
    if change == 'production': n[0]['production_use_authorized'] = True
    if change == 'backtest': eligible['point_in_time_backtest_validated'] = True
    if change == 'assessment': n[0]['assessment_date'] = '2026-10-27'
    if change == 'duplicate_decision': d.append(deepcopy(d[0]))
    if change == 'wrong_eligibility': eligible['policy_eligible'] = False
    if change == 'selected_withheld': d[0]['selected_observation_year'] = 2025
    if change == 'future_selected': eligible['selected_observation_year'] = 2027
    if change == 'stale_selected': eligible['selected_observation_year'] = 2024
    if change == 'missing_decision': d.remove(eligible)
    if change == 'required_dimension': eligible['required_dimensions'] = 'PV;RL;CC'
    with pytest.raises(consumer.ConsumerError): consumer.consume(d, n, DIMS)


@pytest.mark.parametrize('field', consumer.NUMERIC_FIELDS)
@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), True, '0'])
def test_numeric_missingness_is_never_coerced(field, bad):
    d, n = fixture(); n[0][field] = bad
    with pytest.raises(consumer.ConsumerError): consumer.consume(d, n, DIMS)


@pytest.mark.parametrize('field,bad', [('estimate_standard_error', 0), ('source_count', 1.5),
    ('source_count', 0), ('score_ci90_lower', -1), ('score_ci90_upper', 101), ('governance_score', 20)])
def test_numeric_invariants(field, bad):
    d, n = fixture(); n[0][field] = bad
    with pytest.raises(consumer.ConsumerError): consumer.consume(d, n, DIMS)


def package(tmp_path):
    d, n = fixture()
    source = tmp_path / 'adapter'; source.mkdir()
    receipt = {'country_policy_decisions': 4, 'numeric_dimension_bundles': 4}
    for filename, rows in [('policy_decisions.jsonl', d), ('numeric_bundles.jsonl', n)]:
        payload = ''.join(json.dumps(r) + '\n' for r in rows).encode()
        (source / filename).write_bytes(payload)
        receipt[filename + '_sha256'] = hashlib.sha256(payload).hexdigest()
    (source / 'adapter_receipt.json').write_text(json.dumps(receipt))
    pinned = tmp_path / 'pinned.json'; pinned.write_text(json.dumps(receipt))
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'adapter_receipt_canonical_sha256': json_hash(receipt), 'required_dimensions': DIMS}))
    return source, {'CONFIG': config, 'ADAPTER_RECEIPT': pinned, 'PRIVATE_ROOT': tmp_path}


def test_offline_round_trip_determinism_and_output_restrictions(tmp_path):
    source, settings = package(tmp_path)
    with patch.multiple(consumer, **settings), patch('socket.socket.connect', side_effect=AssertionError('offline')):
        a = consumer.run(source, tmp_path / 'a')
        assert a == consumer.run(source, tmp_path / 'b')
        assert a['case_count'] == 4 and a['withheld_cases'] == 3 and a['eligible_cases'] == 1
        output = (tmp_path / 'a/research_cases.jsonl').read_bytes()
        assert output == (tmp_path / 'b/research_cases.jsonl').read_bytes()
        assert [json.loads(line) for line in output.splitlines()] == [asdict(c) for c in consumer.consume(*fixture(), DIMS)]
        assert not a['numeric_values_published_in_receipt']
        with pytest.raises(FileExistsError): consumer.run(source, tmp_path / 'a')
        with pytest.raises(consumer.ConsumerError): consumer.run(source, tmp_path.parent / 'public')


@pytest.mark.parametrize('file', ['numeric_bundles.jsonl', 'policy_decisions.jsonl', 'adapter_receipt.json', 'pin', 'config'])
def test_tampering_aborts_before_output(tmp_path, file):
    source, settings = package(tmp_path)
    target = settings['ADAPTER_RECEIPT'] if file == 'pin' else settings['CONFIG'] if file == 'config' else source / file
    if file.endswith('jsonl'):
        target.write_bytes(target.read_bytes() + b'\n')
    else:
        obj = json.loads(target.read_text()); obj['tampered'] = True
        if file == 'config': obj['adapter_receipt_canonical_sha256'] = '0' * 64
        target.write_text(json.dumps(obj))
    with patch.multiple(consumer, **settings):
        with pytest.raises(consumer.ConsumerError): consumer.run(source, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_exact_year_eligible_case_keeps_zero_values():
    d, n = fixture()
    selected = next(r for r in d if r['policy_eligible'])
    selected.update(target_year=2025, decision='RESEARCH_ELIGIBLE_EXACT_YEAR', max_age_years=0)
    for row in n:
        row.update(target_year=2025, policy_decision=selected['decision'])
    result = consumer.consume([selected], n, DIMS)
    assert result[0].dimensions['PV']['governance_score'] == 0
    assert result[0].dimensions['PV']['observation_year'] == 2025


def test_semantic_failure_in_hash_consistent_fixture_writes_nothing(tmp_path):
    source, settings = package(tmp_path)
    file = source / 'numeric_bundles.jsonl'
    rows = [json.loads(s) for s in file.read_text().splitlines()]
    rows.pop()
    payload = ''.join(json.dumps(r) + '\n' for r in rows).encode()
    file.write_bytes(payload)
    receipt = json.loads(settings['ADAPTER_RECEIPT'].read_text())
    receipt['numeric_bundles.jsonl_sha256'] = hashlib.sha256(payload).hexdigest()
    for path in [settings['ADAPTER_RECEIPT'], source / 'adapter_receipt.json']:
        path.write_text(json.dumps(receipt))
    config = json.loads(settings['CONFIG'].read_text())
    config['adapter_receipt_canonical_sha256'] = json_hash(receipt)
    settings['CONFIG'].write_text(json.dumps(config))
    with patch.multiple(consumer, **settings):
        with pytest.raises(consumer.ConsumerError, match='complete numeric bundle'):
            consumer.run(source, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()
