# WGI research-only numeric consumer

This milestone consumes the frozen [#16 numeric adapter](WGI_NUMERIC_ADAPTER.md)
package into one complete research record per country, target year and policy.
It is stacked on #16 at `00d3e8357839efa5a512f74bc472999415a2348a`.
Implementation date: 27 October 2026. The original policy assessment date stays
26 October 2026; no provider refresh or ACLED access occurs.

## Scope and output contract

`src/wgi_numeric_consumer.py` is an offline, explicitly invoked consumer. It
joins the decision ledger to the four-dimension numeric bundles. It does not
call baseline scoring, calculate a composite, rank countries, normalize values,
create risk categories, or feed operational reports. The resulting research
case is a usable evidence record, not a protective decision or score.

Each `research_cases.jsonl` record contains:

- `decision`: the complete, unchanged adapter decision, including withholding
  reason, target and selected observation years, candidate ages, missingness,
  assessment date and research flags.
- `dimensions`: a dictionary keyed by PV, RL, CC and GE for eligible cases;
  JSON **null** for every withheld case. Null never becomes zero, an empty
  eligible bundle, a neutral score, or an omitted country.
- Explicit research-only classification, `production_use_authorized=false`
  and `point_in_time_backtest_validated=false`.

Each eligible dimension record is copied in full. Estimates and estimate SE
remain in governance-estimate units; source counts retain their numeric value;
fixed-reference governance scores and their provider 90% bounds remain in
score units. There is no rounding, clipping, inversion, unit conversion,
imputation, reweighting, confidence interval derivation or joint uncertainty
calculation. Original textual number formatting is not promised.

Indicator IDs, payload hashes, release label, source update date, assessment
date, parity-receipt reference and all six numeric fields survive the join.
Target 2026 under the lag sensitivity keeps observation year 2025. Strict
2026 cases remain withheld. Historical targets still use the retained 2026
vintage and are not point-in-time backtests.

## Evidence and failure boundary

The reviewed consumer configuration pins the canonical committed adapter
receipt. The supplied package receipt must match that receipt, and both JSONL
input files must match its byte hashes. This transitively binds consumption to
#16's already verified policy, coverage and provider-response evidence. It does
not repeat workbook/API acquisition or prove the provider's factual accuracy.
The private `consume` workflow's pure join helper is not a substitute for the
hash-verifying CLI when consuming real evidence.

The join rejects duplicate decisions or dimensions, orphan numeric records,
numeric records for withheld cases, incomplete eligible bundles, mixed years,
wrong policy decisions or assessment dates, altered units/indicator mappings,
changed uncertainty interpretation, invalid numeric fields and changed research
flags. Eligible observations must satisfy the ledger's age gate. Counts must
reconcile with the pinned adapter receipt. The complete cohort is validated
before the output directory is created; evidence failures yield no partial view.

Output directories must be new and under ignored `data/raw/`. Existing outputs
cannot be overwritten. Real input/output records remain local. Only code,
synthetic tests, documentation, configuration and a metadata receipt are
committed. No real personal or itinerary records are used. ACLED remains
documentation-only, without any acquisition, transformation or redistribution.

## Retained-source replay

The [consumer receipt](provenance/wgi_consumer_receipt_20261027.json) records:

| Result | Count |
|---|---:|
| All country/target/policy cases | 1,296 |
| Eligible cases with complete numeric bundles | 1,065 |
| Withheld cases with null numeric payloads | 231 |
| Preserved dimension records | 4,260 |
| Preserved numeric fields | 25,560 |

These are repeated cases across two policies and three targets, not distinct
countries or independent observations. Both runs produced byte-identical case
and receipt files. A separate direct-JSON reconciliation compared every input
decision and every full numeric record to the output, verifying complete
coverage and exact preservation of all 25,560 numeric fields and provenance.
No raw or numeric observations appear in the public receipt.

## Reproduce

Use the existing development dependencies; this milestone adds none.

```bash
python -m pytest -q
python -m src.wgi_numeric_consumer --adapter-dir data/raw/wgi_numeric_20261027 --output-dir data/raw/wgi_consumer_NEW
```

If the adapter package is unavailable, regenerate it from the exact frozen
inputs using #16's instructions. A newly downloaded provider vintage cannot
silently replace it. The two consumer outputs are `research_cases.jsonl` and
`consumer_receipt.json`; neither is an operational scoring feed.

Synthetic tests exercise lossless joins, explicit withheld nulls, genuine zero
values, estimates outside the typical range, exact/lagged year preservation,
missing fields and dimensions, stale/future observations, unit/uncertainty
mismatches, duplicates/orphans, tampering, fail-before-write behavior, offline
execution, deterministic replay and private output restrictions. These fixtures
are fictional even though they exercise the real adapter schema.

Production adoption, any new numeric transformation, actual cross-source cohort
selection, uncertainty calibration and protective-use validation remain open.
Baselines and previous research modules/receipts are unchanged. Nothing in this
milestone authorizes travel decisions, merges prior drafts, or closes #9/#11.

Validation on 27 October 2026: **370 tests and 7 subtests passed**, including
67 new consumer tests. Real-source replay is separate from synthetic CI tests;
its evidence is the metadata receipt and the local retained-input comparison.
