"""Synthetic-only regression fixtures; no live sources or personal data."""
from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.preflight import PreflightError, TRIP_FIELDS, require_preflight, require_unique_trip_context
from src.residual_protective_risk import FIELDS

AS_OF = "2026-10-17"


def seal(root: Path, evidence: dict) -> None:
    raw = root / "data/raw"
    evidence['input_sha256'] = {
        key: hashlib.sha256((raw/name).read_bytes()).hexdigest()
        for key, name in [('trips','protective_intelligence_trip_inputs.csv'),
                          ('capacity','protective_capacity_inputs.csv'), ('events','acled_events.csv')]
    }
    (raw/'rpr1_evidence.json').write_text(json.dumps(evidence), encoding='utf-8')


@pytest.fixture
def package(tmp_path: Path) -> tuple[Path, dict]:
    raw = tmp_path/'data/raw'
    raw.mkdir(parents=True)
    trip = dict(trip_id='001', principal='SYNTHETIC', city='Test City', country='Test Country',
                scenario='site visit', visibility_level='low', travel_predictability='low',
                venue_exposure='low', hotel_airport_exposure='low', online_visibility='low',
                reputational_sensitivity='low', business_sector_sensitivity='other')
    pd.DataFrame([trip]).to_csv(raw/'protective_intelligence_trip_inputs.csv', index=False)
    pd.DataFrame([dict(trip_id='001', **dict.fromkeys(FIELDS,50))]).to_csv(raw/'protective_capacity_inputs.csv', index=False)
    pd.DataFrame([dict(country='Test Country',location='Test City',admin1='A',admin2='B',event_date='2026-10-16',year=2026,event_type='Protests',fatalities=0)]).to_csv(raw/'acled_events.csv', index=False)
    evidence = dict(schema_version=1,data_class='synthetic',contains_personal_data=False,
        event_source=dict(source_ref='synthetic://fixture',reviewer_ref='TEST-REVIEW',review_status='approved',
                          coverage_from='2026-10-01',coverage_through='2026-10-16',retrieved_on=AS_OF),
        assessments=[dict(trip_id='001',kind=kind,source_ref='synthetic://fixture',assessor_ref='TEST-ASSESSOR',
                          covered_fields=list(FIELDS if kind == 'capacity' else TRIP_FIELDS),
                          reviewer_ref='TEST-REVIEW',scope='Synthetic movement only',review_status='approved',
                          assessed_on='2026-10-16',movement_on='2026-10-18',expires_on='2026-10-19')
                     for kind in ('trip','capacity')])
    seal(tmp_path,evidence)
    return tmp_path,evidence


def test_valid_package_read_only(package):
    root, evidence = package
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    result = require_preflight(AS_OF,'synthetic',root)
    assert result.trip_count == 1
    assert result.status == 'PASS_EXPERIMENTAL_RESEARCH_ONLY'
    assert before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def test_synthetic_cannot_pass_current(package):
    root, _ = package
    with pytest.raises(PreflightError,match='data_class'):
        require_preflight(AS_OF,'current',root)


@pytest.mark.parametrize('assessment',[None,'','20261017','bad'])
def test_explicit_date_required(package,assessment):
    with pytest.raises(PreflightError,match='explicit'):
        require_preflight(assessment,'synthetic',package[0])


def test_old_events_with_recent_retrieval_blocked(package):
    root,e = package
    p=root/'data/raw/acled_events.csv'
    d=pd.read_csv(p); d['event_date']='2024-12-31'; d['year']=2024; d.to_csv(p,index=False)
    e['event_source'].update(coverage_from='2024-01-01',coverage_through='2024-12-31')
    seal(root,e)
    with pytest.raises(PreflightError,match='Stale event coverage'):
        require_preflight(AS_OF,'synthetic',root)


def test_recent_coverage_label_cannot_hide_old_observations(package):
    root,e=package
    p=root/'data/raw/acled_events.csv'
    d=pd.read_csv(p); d['event_date']='2024-12-31'; d['year']=2024; d.to_csv(p,index=False)
    e['event_source']['coverage_from']='2024-01-01'; seal(root,e)
    with pytest.raises(PreflightError,match='Stale event observations'):
        require_preflight(AS_OF,'synthetic',root)


@pytest.mark.parametrize('fault',['missing_file','blank','missing_column','orphan','duplicate','infinite','missing_id'])
def test_capacity_failures(package,fault):
    root,e=package; p=root/'data/raw/protective_capacity_inputs.csv'
    d=pd.read_csv(p,dtype=str)
    if fault=='missing_file': p.unlink()
    else:
        if fault=='blank': d[FIELDS[0]]=''
        if fault=='missing_id': d=d.drop(columns=['trip_id'])
        if fault=='missing_column': d=d.drop(columns=[FIELDS[0]])
        if fault=='orphan': d['trip_id']='002'
        if fault=='duplicate': d=pd.concat([d,d])
        if fault=='infinite': d[FIELDS[0]]='inf'
        d.to_csv(p,index=False); seal(root,e)
    with pytest.raises(PreflightError): require_preflight(AS_OF,'synthetic',root)


@pytest.mark.parametrize('fault',['ambiguous','missing'])
def test_location_join_failures(package,fault):
    root,e=package; p=root/'data/raw/acled_events.csv'; d=pd.read_csv(p)
    if fault=='ambiguous': d=pd.concat([d,d.assign(admin1='Other')])
    else: d['location']='Another City'
    d.to_csv(p,index=False); seal(root,e)
    with pytest.raises(PreflightError,match='location join'): require_preflight(AS_OF,'synthetic',root)


@pytest.mark.parametrize('fault',['expired','future','stale','missing','unapproved','movement_mismatch'])
def test_evidence_failures(package,fault):
    root,e=package; r=e['assessments'][0]
    if fault=='expired': r['expires_on']='2026-10-16'
    if fault=='future': r['assessed_on']='2026-10-18'
    if fault=='stale': r['assessed_on']='2026-01-01'
    if fault=='missing': e['assessments'].pop()
    if fault=='unapproved': r['review_status']='pending'
    if fault=='movement_mismatch': r['movement_on']='2026-10-19'
    seal(root,e)
    with pytest.raises(PreflightError): require_preflight(AS_OF,'synthetic',root)


def test_hash_mismatch(package):
    root,_=package
    with (root/'data/raw/acled_events.csv').open('a') as f: f.write('\n')
    with pytest.raises(PreflightError,match='hashes'): require_preflight(AS_OF,'synthetic',root)


def test_failed_gate_prevents_all_pipeline_work():
    import src.main as pipeline
    with patch.object(pipeline,'require_preflight',side_effect=PreflightError('blocked')), \
         patch.object(pipeline,'build_worldbank_dataset') as first:
        with pytest.raises(PreflightError): pipeline.main(date.today().isoformat())
        first.assert_not_called()


def test_generated_join_is_checked_again():
    from src.protective_intelligence_score import calculate_protective_intelligence_scores
    trip=pd.DataFrame([dict(trip_id='001',city_key='city',country_key='country')])
    context=pd.DataFrame([dict(city_key='city',country_key='country')]*2)
    with pytest.raises(PreflightError,match='2 matches'):
        calculate_protective_intelligence_scores(trip,context)


@pytest.mark.parametrize('age,passes',[(30,True),(31,False)])
def test_exact_freshness_boundary(package,age,passes):
    from datetime import timedelta
    root,e=package
    observed=(date.fromisoformat(AS_OF)-timedelta(days=age)).isoformat()
    p=root/'data/raw/acled_events.csv'; d=pd.read_csv(p)
    d['event_date']=observed; d.to_csv(p,index=False)
    e['event_source'].update(coverage_from=observed,coverage_through=observed)
    for rec in e['assessments']: rec['assessed_on']=observed
    seal(root,e)
    if passes: assert require_preflight(AS_OF,'synthetic',root).trip_count==1
    else:
        with pytest.raises(PreflightError,match='Stale'):
            require_preflight(AS_OF,'synthetic',root)


@pytest.mark.parametrize('fault',['future_event','bad_date','future_retrieval','wrong_hash','wrong_schema','no_source'])
def test_source_contract_failures(package,fault):
    root,e=package
    if fault in {'future_event','bad_date'}:
        p=root/'data/raw/acled_events.csv'; d=pd.read_csv(p)
        d['event_date']='2026-10-18' if fault=='future_event' else 'invalid'
        d.to_csv(p,index=False)
    if fault=='future_retrieval': e['event_source']['retrieved_on']='2026-10-18'
    if fault=='wrong_schema': e['schema_version']=2
    if fault=='no_source': e['event_source']['source_ref']=''
    seal(root,e)
    if fault=='wrong_hash':
        e['input_sha256']['events']='0'*64
        (root/'data/raw/rpr1_evidence.json').write_text(json.dumps(e))
    with pytest.raises(PreflightError): require_preflight(AS_OF,'synthetic',root)


def test_repeated_events_same_location_not_ambiguous(package):
    root,e=package; p=root/'data/raw/acled_events.csv'; d=pd.read_csv(p)
    pd.concat([d,d.assign(event_date='2026-10-15')]).to_csv(p,index=False)
    seal(root,e)
    assert require_preflight(AS_OF,'synthetic',root).trip_count==1


def test_unrelated_ambiguous_city_does_not_block_selected_trip(package):
    root,e=package; p=root/'data/raw/acled_events.csv'; d=pd.read_csv(p)
    pd.concat([d,d.assign(location='Elsewhere'),d.assign(location='Elsewhere',admin1='Other')]).to_csv(p,index=False)
    seal(root,e)
    assert require_preflight(AS_OF,'synthetic',root).trip_count==1


@pytest.mark.parametrize("field", ["scenario", "visibility_level", "business_sector_sensitivity"])
def test_unknown_trip_labels_blocked(package, field):
    root, evidence = package
    path = root / "data/raw/protective_intelligence_trip_inputs.csv"
    frame = pd.read_csv(path, dtype=str)
    frame[field] = "typo"
    frame.to_csv(path, index=False)
    seal(root, evidence)
    with pytest.raises(PreflightError, match="Unrecognized"):
        require_preflight(AS_OF, "synthetic", root)


@pytest.mark.parametrize("fault", ["missing_type", "bad_fatalities", "bad_year", "blank_admin", "loose_date"])
def test_event_consumer_contract(package, fault):
    root, evidence = package
    path = root / "data/raw/acled_events.csv"
    frame = pd.read_csv(path)
    if fault == "missing_type": frame = frame.drop(columns="event_type")
    if fault == "bad_fatalities": frame["fatalities"] = "unknown"
    if fault == "bad_year": frame["year"] = 2024
    if fault == "blank_admin": frame["admin1"] = ""
    if fault == "loose_date": frame["event_date"] = "2026-10-6"
    frame.to_csv(path, index=False)
    seal(root, evidence)
    with pytest.raises(PreflightError):
        require_preflight(AS_OF, "synthetic", root)


@pytest.mark.parametrize("name", ["acled_events.csv", "protective_capacity_inputs.csv", "rpr1_evidence.json"])
def test_mutated_package_cannot_be_reused(package, name):
    from src.preflight import verify_package_unchanged
    root, _ = package
    receipt = require_preflight(AS_OF, "synthetic", root)
    path = root / "data/raw" / name
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(PreflightError, match="changed"):
        verify_package_unchanged(receipt, root)


def test_live_pipeline_rejects_historical_reference_before_network():
    import src.main as pipeline
    with patch.object(pipeline, "build_worldbank_dataset") as fetch:
        with pytest.raises(PreflightError, match="today"):
            pipeline.main("2000-01-01")
        fetch.assert_not_called()


@pytest.mark.parametrize("fault", ["boolean_schema", "duplicate_json", "duplicate_csv"])
def test_ambiguous_serialization_blocked(package, fault):
    root, evidence = package
    path = root / "data/raw/rpr1_evidence.json"
    if fault == "boolean_schema":
        evidence["schema_version"] = True
        seal(root, evidence)
    elif fault == "duplicate_json":
        path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": 2, "schema_version": 1'))
    else:
        csv = root / "data/raw/protective_capacity_inputs.csv"
        lines = csv.read_text().splitlines()
        lines[0] += ",trip_id"
        lines[1] += ",002"
        csv.write_text("\n".join(lines))
        seal(root, evidence)
    with pytest.raises(PreflightError):
        require_preflight(AS_OF, "synthetic", root)


def test_incomplete_field_evidence_blocked(package):
    root, evidence = package
    evidence["assessments"][1]["covered_fields"].pop()
    seal(root, evidence)
    with pytest.raises(PreflightError, match="every assessed field"):
        require_preflight(AS_OF, "synthetic", root)


def test_failed_recheck_stops_downstream_processing():
    import src.main as pipeline
    with patch.object(pipeline, "require_preflight"), \
         patch.object(pipeline, "build_worldbank_dataset"), \
         patch.object(pipeline, "fetch_acled_events"), \
         patch.object(pipeline, "verify_package_unchanged", side_effect=PreflightError("changed")), \
         patch.object(pipeline, "build_acled_country_features") as consumer:
        with pytest.raises(PreflightError, match="changed"):
            pipeline.main(date.today().isoformat())
        consumer.assert_not_called()


def test_reserved_id_cannot_disappear_in_downstream_parser(package):
    root, evidence = package
    for name in ("protective_intelligence_trip_inputs.csv", "protective_capacity_inputs.csv"):
        path = root / "data/raw" / name
        frame = pd.read_csv(path, dtype=str)
        frame["trip_id"] = "NA"
        frame.to_csv(path, index=False)
    for record in evidence["assessments"]: record["trip_id"] = "NA"
    seal(root, evidence)
    with pytest.raises(PreflightError, match="reserved"):
        require_preflight(AS_OF, "synthetic", root)
