"""Offline consumer of the frozen adapter package; never an operational score."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from src.wgi_numeric_adapter import FIELDS, UNITS
from src.wgi_observation_policy import ROOT, json_hash

CONFIG = ROOT / 'docs/provenance/wgi_numeric_consumer.json'
ADAPTER_RECEIPT = ROOT / 'docs/provenance/wgi_numeric_receipt_20261027.json'
PRIVATE_ROOT = ROOT / 'data/raw'
NUMERIC_FIELDS = ('estimate', 'estimate_standard_error', 'source_count',
                  'governance_score', 'score_ci90_lower', 'score_ci90_upper')
ELIGIBLE = {'RESEARCH_ELIGIBLE_EXACT_YEAR', 'RESEARCH_ELIGIBLE_LAGGED'}
WITHHELD = {'WITHHELD_STALE_COMMON_BUNDLE', 'WITHHELD_NO_COMMON_BUNDLE'}


class ConsumerError(ValueError):
    """Inconsistent evidence must not produce a partial research output."""


@dataclass(frozen=True)
class ResearchCase:
    decision: dict
    dimensions: dict[str, dict] | None
    data_class: str = 'WGI_RESEARCH_CASE_NOT_A_RISK_SCORE'
    production_use_authorized: bool = False
    point_in_time_backtest_validated: bool = False


def case_key(row: dict) -> tuple[str, int, str]:
    country, year, policy = row['country_code'], row['target_year'], row['policy']
    if (not isinstance(country, str) or len(country) != 3 or type(year) is not int
            or not isinstance(policy, str) or not policy):
        raise ConsumerError('Invalid case identity')
    return country, year, policy


def research_flags(row: dict) -> None:
    if row.get('production_use_authorized') is not False or row.get('point_in_time_backtest_validated') is not False:
        raise ConsumerError('Research-only flags missing or changed')


def consume(decisions: list[dict], numeric: list[dict], required: tuple[str, ...]) -> list[ResearchCase]:
    """Join without aggregation, dropping cases, filling nulls or changing numbers."""
    if not decisions or not required or len(set(required)) != len(required):
        raise ConsumerError('Empty cases or invalid required dimensions')
    ledger, grouped = {}, {}
    for decision in decisions:
        key = case_key(decision)
        research_flags(decision)
        status = decision['decision']
        if (key in ledger or status not in ELIGIBLE | WITHHELD
                or decision.get('policy_eligible') is not (status in ELIGIBLE)
                or decision['required_dimensions'].split(';') != list(required)):
            raise ConsumerError('Duplicate or inconsistent policy decision')
        year = decision['selected_observation_year']
        if status in WITHHELD:
            if year is not None:
                raise ConsumerError('Withheld case has a selected observation year')
        else:
            age = key[1] - year if type(year) is int else -1
            if (age < 0 or type(decision['max_age_years']) is not int
                    or not age <= decision['max_age_years']
                    or (status == 'RESEARCH_ELIGIBLE_EXACT_YEAR') != (age == 0)):
                raise ConsumerError('Inconsistent observation year or age policy')
        ledger[key] = decision
        grouped[key] = {}
    for row in numeric:
        key = case_key(row)
        research_flags(row)
        decision = ledger.get(key)
        dim = row['dimension']
        if (decision is None or not decision['policy_eligible'] or dim not in required
                or dim in grouped[key]):
            raise ConsumerError('Orphan, withheld, unexpected or duplicate numeric dimension')
        if (type(row['observation_year']) is not int
                or row['observation_year'] != decision['selected_observation_year']
                or row['policy_decision'] != decision['decision']
                or row['assessment_date'] != decision['assessment_date']):
            raise ConsumerError('Numeric case year or decision differs from ledger')
        if (row['units'] != UNITS or type(row['confidence_level']) not in (int, float)
                or row['confidence_level'] != .90 or row['confidence_interval_scale'] != 'score'
                or row['indicator_ids'] != {f: f'GOV_WGI_{dim}.{f}' for f in FIELDS}
                or row['data_class'] != 'REAL_WGI_AGGREGATES_RESEARCH_ONLY'):
            raise ConsumerError('Numeric units, uncertainty or indicator mapping differs')
        vals = [row[f] for f in NUMERIC_FIELDS]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in vals):
            raise ConsumerError('Missing or invalid numeric field')
        _, se, count, score, lower, upper = vals
        if se <= 0 or count < 1 or count != int(count) or not 0 <= lower <= score <= upper <= 100:
            raise ConsumerError('Invalid uncertainty, source count or score bounds')
        grouped[key][dim] = deepcopy(row)
    result = []
    for key in sorted(ledger):
        decision = ledger[key]
        if decision['policy_eligible'] and set(grouped[key]) != set(required):
            raise ConsumerError('Eligible case lacks a complete numeric bundle')
        result.append(ResearchCase(deepcopy(decision), grouped[key] if decision['policy_eligible'] else None))
    return result


def run(package: Path, output: Path) -> dict:
    if not output.resolve().is_relative_to(PRIVATE_ROOT.resolve()):
        raise ConsumerError('Outputs must remain under ignored data/raw')
    if output.exists():
        raise FileExistsError(output)
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    pinned = json.loads(ADAPTER_RECEIPT.read_text(encoding='utf-8'))
    receipt = json.loads((package / 'adapter_receipt.json').read_text(encoding='utf-8'))
    if (json_hash(pinned) != config['adapter_receipt_canonical_sha256'] or receipt != pinned):
        raise ConsumerError('Adapter receipt differs from reviewed frozen input')
    loaded = {}
    for filename in ('policy_decisions.jsonl', 'numeric_bundles.jsonl'):
        payload = (package / filename).read_bytes()
        if hashlib.sha256(payload).hexdigest() != receipt[filename + '_sha256']:
            raise ConsumerError('Adapter file hash mismatch')
        loaded[filename] = [json.loads(line) for line in payload.decode('utf-8').splitlines()]
    cases = consume(loaded['policy_decisions.jsonl'], loaded['numeric_bundles.jsonl'], tuple(config['required_dimensions']))
    if (len(cases) != receipt['country_policy_decisions']
            or sum(len(c.dimensions or {}) for c in cases) != receipt['numeric_dimension_bundles']):
        raise ConsumerError('Adapter counts differ from consumed cohort')
    rows = [asdict(c) for c in cases]
    payload = ''.join(json.dumps(r, sort_keys=True, allow_nan=False) + '\n' for r in rows).encode('utf-8')
    result = {'data_class': 'RESEARCH_CONSUMER_VALIDATION_METADATA_ONLY',
        'adapter_receipt_canonical_sha256': json_hash(receipt),
        'consumer_config_canonical_sha256': json_hash(config),
        'consumer_module_sha256_lf': hashlib.sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest(),
        'research_cases_sha256': hashlib.sha256(payload).hexdigest(),
        'case_count': len(cases), 'eligible_cases': sum(c.dimensions is not None for c in cases),
        'withheld_cases': sum(c.dimensions is None for c in cases),
        'numeric_dimension_bundles': sum(len(c.dimensions or {}) for c in cases),
        'decisions': dict(sorted(Counter(c.decision['decision'] for c in cases).items())),
        'numeric_values_published_in_receipt': False, 'production_use_authorized': False,
        'point_in_time_backtest_validated': False, 'acled': 'DOCUMENTATION_ONLY_NO_REQUESTS'}
    # Validate the full cohort before creating any output; never export a partial join.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'research_cases.jsonl').write_bytes(payload)
    (output / 'consumer_receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.adapter_dir, args.output_dir), indent=2))


if __name__ == '__main__':
    main()
