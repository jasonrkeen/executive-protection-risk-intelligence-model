# WGI numeric adapter — isolated research milestone

Implemented 27 October 2026, stacked on draft #15
(`b59963a7f349fa9e29d08b866de3ef9acc7d7a38`). The frozen policy assessment
remains **26 October 2026**. This implementation date is not a new provider
release, retrieval date or observation year.

## Contract

`src/wgi_numeric_adapter.py` connects the #15 missingness/age gate to the
retained #14 aggregate API values. It recomputes decisions from verified
coverage rather than trusting an editable decision CSV. The adapter is offline,
exports research records only, and does not call or modify any scoring function.
Baseline code/configuration, previous receipts and synthetic artifacts remain
unchanged. ACLED remains documentation-only with no requests or data access.

For each eligible country/target/policy case, the adapter emits one record for
each of PV, RL, CC and GE. All four dimensions use the single observation year
selected by #15. A withheld case emits **no numeric records**. The separate
decision ledger retains every withheld case and reason, so absence from the
numeric file cannot be interpreted as zero risk or a zero governance estimate.

| Numeric output | Provider suffix | Preserved unit |
|---|---|---|
| `estimate` | EST | Governance estimate |
| `estimate_standard_error` | SE | Governance estimate |
| `source_count` | SR | Integer source count |
| `governance_score` | SC | Fixed-reference score, 0–100 |
| `score_ci90_lower` | SC_LB | Fixed-reference score, 0–100 |
| `score_ci90_upper` | SC_UB | Fixed-reference score, 0–100 |

The input contract and independently checked mappings are documented in
[the provenance milestone](REAL_SOURCE_PROVENANCE_VERIFICATION.md) and
[the workbook/API parity audit](WGI_WORKBOOK_API_PARITY.md). This adapter copies
the retained API numeric values without rounding, normalization or conversion.
JSON preserves the parsed numeric values; original textual number formatting
is not promised. Values below −2.5 or above +2.5 in estimate units are not clipped.
Zero estimates and zero score bounds remain valid numbers, distinct from nulls.

Score bounds are provider-supplied **90% intervals in score units**, not estimate
units. Estimate SE is not a score SE, percentile rank, variance or confidence
bound. No confidence bounds, covariance, error inflation, distributions or
joint uncertainty are derived. Workbook-only estimate bounds and score SE are
not silently substituted into the six mapped fields.

## Failure and provenance behavior

The adapter pins the canonical #15 policy configuration, which pins #14's
canonical receipt. It verifies the coverage hash, exact acquisition manifest,
all 40 retained response-file hashes/URLs, source identity/update date, indicator
names, and economy identities before selecting values. The workbook is only
hash-checked; no workbook or source-mean columns are parsed in this milestone.

Each numeric record retains target year and observation year separately, policy
name/decision, unit dictionary, indicator IDs, six originating API payload hashes,
source ID/update date, release label and policy assessment date. The receipt
hash binds those references to the existing request/retrieval provenance.
The release label is not claimed to be an immutable provider release identifier.

For example, the one-year sensitivity for target 2026 selects observation year
2025, retaining that year on every dimension. It never relabels the values as
observed in 2026. Target-2024 evaluations use the retained 2026 vintage and are
retrospective exercises, not point-in-time backtests. Every record explicitly
keeps `point_in_time_backtest_validated=False` and
`production_use_authorized=False`.

Selected bundles must have six finite numeric fields, positive estimate SE,
a positive integer-valued source count and ordered score bounds within 0–100
containing the score. Booleans and numeric strings are rejected. A coverage
claim contradicted by a missing/invalid selected value aborts the whole run
before output creation. No partial country bundle is exported, older values
cannot patch a selected year, and no missing value is imputed. Withheld cases
remain withheld even when unrelated or older numerical values exist.

All validation completes before creating a new output directory. Existing
directories cannot be overwritten. Numeric output is restricted to the ignored
repository `data/raw/` tree. No real numeric observations, raw workbooks, API
payloads, personal records or itineraries are committed. The public deliverable
is code/tests/documentation and a metadata-only validation receipt.

## Results on the frozen input

The six target/policy combinations retain #15's decisions:

| Case | Eligible country cases | Numeric dimension records |
|---|---:|---:|
| Strict target 2024 | 213 | 852 |
| Strict target 2025 | 213 | 852 |
| Strict target 2026 | 0 | 0 |
| One-year sensitivity, target 2024 | 213 | 852 |
| One-year sensitivity, target 2025 | 213 | 852 |
| One-year sensitivity, target 2026 | 213 | 852 |

Total: **1,296 country-policy decisions**, **1,065 eligible cases**, **231 withheld
cases**, and **4,260 dimension records**. These are repeated cases across policy
variants, not 1,065 distinct economies or independent observations. The universe
is still 216 WGI economies, not the final cross-source model cohort. All selected
uncertainty fields passed the stated structural checks; this does not establish
their empirical calibration or operational suitability.

[The dated adapter receipt](provenance/wgi_numeric_receipt_20261027.json) records
counts, hashes and limits without including numeric governance observations.
No new provider requests were made, so these are results on the retained
26 October acquisition, not a 27 October data refresh.

## Reproduction and validation

Install the existing development requirements (including #14's pinned workbook
reader dependency, imported by shared validation helpers). No dependency is added.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m src.wgi_numeric_adapter --raw-dir data/raw/wgi_parity_20261026 --coverage-csv data/raw/wgi_parity_publish_20261026/country_year_coverage.csv --output-dir data/raw/wgi_numeric_NEW
```

Use a new output directory for every run. The local outputs are
`numeric_bundles.jsonl`, `policy_decisions.jsonl` and `adapter_receipt.json`.
The first contains real national aggregate values and must remain uncommitted.
If retained input files are unavailable, stop or recover the exact frozen bytes;
fresh downloads cannot silently replace this snapshot.

Synthetic test fixtures cover all six fields, null/NaN/infinity/bool/string
failures, zero and boundary values, estimate values outside the typical range,
SE/count/bound invariants, coherent year selection, lagged year preservation,
withheld-output suppression, metadata scale substitution, raw/manifest/receipt/
policy/coverage tampering, offline determinism and output restrictions. CI runs
these fixtures and the prior fictional demonstration suite without provider access.

Production adoption still requires an approved numeric consumer, preservation
of withholding through the full scoring chain, actual cohort reconciliation,
uncertainty-method validation and independent review. This adapter neither
authorizes travel decisions nor changes the baseline. No PR is merged and main
is unchanged; issues #9/#11 are not closed by this milestone.

Validation completed on 2026-10-27: **303 tests and 7 subtests passed**, including
52 adapter tests. Two retained-source runs produced byte-identical numeric,
decision and receipt files. A separate direct-JSON comparison matched all
25,560 emitted fields (4,260 bundles times six fields) to their original API
country, indicator and observation-year keys. This verifies transfer fidelity,
not calibration or suitability for protective decisions.
