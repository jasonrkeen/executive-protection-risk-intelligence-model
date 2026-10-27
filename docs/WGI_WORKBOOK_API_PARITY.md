# WGI workbook/API parity and country-year coverage

Verified 26 October 2026 against PR #13 (`8769c9438fe9829a54ea17b9d781fe985edd9387`).
This is a separate research verifier. Main, baseline configuration, scoring,
earlier receipts and synthetic fixtures are unchanged. ACLED remains
documentation-only: no ACLED requests, credentials or events were used.

## Result and scope

The 2026 provider workbook and source-3 API agree on **202,092 available numeric
cells** across 216 provider economies, six dimensions and six aggregate fields.
Of these, 154,275 are exactly equal as parsed numbers; 47,817 differ by at most
`1.4210854715202004e-14`, consistent with binary floating-point representation.
No cells with a value in only one source, or numeric mismatches, were found in
this acquisition.
This establishes numerical parity for the retained bytes and mapped fields,
not an immutable provider release-ID guarantee or substantive data accuracy.

The denominator is **233,280 cells**: 216 economies × 30 calendar years
(1996–2025) × 36 fields. **31,188 cells are unavailable in both sources** and
are NOT counted as matches. There are no observations in either source for
1997, 1999 or 2001. The workbook has 27 represented years, with additional
economy/dimension gaps within those years. No gaps are interpolated or zero-filled.

| Window | Economy-years | All 36 fields present and matching | Four scored dimensions complete | Five baseline-fetched dimensions complete |
|---|---:|---:|---:|---:|
| Baseline window, 2020–2024 | 1,080 | 1,036 | 1,061 | 1,036 |
| Latest observation year, 2025 | 216 | 206 | 213 | 206 |

Each dimension's completeness requires its six mapped fields. Scored dimensions
are PV/RL/CC/GE; baseline-fetched dimensions also include VA. RQ is audited for
provider parity but is not added to scoring. These flags indicate data coverage,
not operational readiness or validated model inputs.

The four scored dimensions are incomplete for ANT in every baseline year;
COK and NIU in 2020–2021; and NCL and PYF throughout 2020–2024. In 2025,
ANT, NCL and PYF remain incomplete. Additional VA gaps explain why the full
36-field denominator has more incomplete economy-years. The country summary
lists the actual missing dimensions rather than labeling all gaps equivalently.

The universe is the **216 WGI source-3 economies**, including territories and
historical entities. It is not a count of sovereign states or a reconstruction
of the model's final merged country cohort. `src/worldbank_api.py` requests
`country/all`; this audit therefore covers the WGI universe and explicitly
reports the configured 2020–2024 window. It does not run the production pipeline
or validate its latest-available-value fallback, joins to other sources, or
forward-2026 outputs. Provider numeric presence is not reporting completeness.

## Primary sources and mapping

Sources accessed 2026-10-26:

- [World Bank catalog](https://datacatalog.worldbank.org/search/dataset/0038026/worldwide-governance-indicators): identifies the WGI 2026 aggregate workbook for 1996–2025, resource update September 18 and public/CC BY 4.0 designation.
- [Official workbook](https://datacatalogfiles.worldbank.org/ddh-published/0038026/DR0095947/WGI%202026%20Governance%20Estimates%20and%20Scores%20%281996-2025%29.xlsx): retained locally with SHA-256 `8e4754bda8b2be0b36d172c18a4caa634cb36fddd54145d16ab7316d22b3542c` (10,958,369 bytes).
- [Source metadata](https://api.worldbank.org/v2/source/3?format=json) and [indicator inventory](https://api.worldbank.org/v2/source/3/indicator?format=json&per_page=1000): WGI identity, 36 names and API update date 2026-09-25, consistent with #13.
- [Source-specific economy registry](https://api.worldbank.org/v2/sources/3/country?format=json&per_page=1000): 216 unique codes/names. This plural `sources` endpoint is distinct from the indicator endpoint.
- [WGI methodology documentation](https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation): estimate/standard-error units remain distinct from fixed-reference score/confidence-bound units.

The six workbook sheets are `va`, `pv`, `ge`, `rq`, `rl`, `cc`. Rows are keyed
by provider economy code, year and dimension. The verifier inspects only A:P,
uses exact header names, and maps:

| API suffix | Workbook column | Unit |
|---|---|---|
| EST | I: Governance estimate (approx. -2.5 to +2.5) | Estimate |
| SE | J: Standard error (estimate) | Estimate |
| SR | H: Number of sources | Integer count, exact equality |
| SC | M: Governance score (0-100) | Fixed-reference score |
| SC_LB | O: Lower threshold (90% conf. int. score) | Score |
| SC_UB | P: Upper threshold (90% conf. int. score) | Score |

K/L (estimate confidence bounds) and N (score standard error) are **not** mapped
onto score bounds or estimate SE. They are not part of the 36-series parity
claim. No covariance or joint uncertainty model is inferred.

The API returns blank `countryiso3code` for AIA, ANT, COK, GUF, JEY, MTQ, NIU,
REU and TWN. Their exact API names map uniquely to source-3 registry codes;
that explicit recovery is recorded in the receipt. Unknown names, conflicting
nonblank codes and nonunique registry names stop verification. No fuzzy matching
or third-party ISO substitution occurs. Nine workbook/API display-name
differences are also recorded, including replacement characters already in the
workbook. Provider codes establish identity; names are not silently repaired.

## Evidence and reproduction

- [Dated receipt](provenance/wgi_parity_receipt_20261026.json): per-indicator/year results, incomplete baseline/latest economy-years, country crosswalk, exact request URLs, hashes, retrieval times and environment.
- [216-economy coverage summary](provenance/wgi_country_coverage_20261026.csv): complete-year counts and 2024/2025 missing dimensions. It contains coverage metadata, not numeric governance observations.
- [Verification contract](provenance/wgi_parity_contract.json): workbook URL, calendar/window definitions, field mapping and absolute tolerance (`1e-7`, no relative tolerance; source counts compare exactly). Actual maximum error is much smaller than the declared tolerance.

The acquisition used 40 requests: one workbook, three metadata requests and
36 single-indicator API requests. All response pages reported complete results
on page 1; pagination would be rejected rather than truncated. API source and
update dates must agree throughout. Null cells and absent rows are counted
separately in the generated full 6,480-row country-year coverage CSV.

The official aggregate workbook also bundles source-mean columns from Q onward.
The complete download stays private/ignored locally; those columns are not
inspected by the verifier, analyzed, copied into results or redistributed.
Neither the workbook nor API observation payloads are committed. No underlying
source-data workbook is requested. Publication consists only of metadata and
derived coverage counts. This does not extend rights to third-party source data.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# Explicit live access: use NEW directories on every acquisition/report run.
python -m src.wgi_parity --live --raw-dir data/raw/wgi_parity_NEW --output-dir data/raw/wgi_parity_report_NEW
# Recheck exact retained inputs offline (no provider calls):
python -m src.wgi_parity --replay --raw-dir data/raw/wgi_parity_NEW --output-dir data/raw/wgi_parity_replay_NEW
```

Replay checks every manifest URL and input hash before parsing. Acquisition and
report directories refuse overwrite. Error envelopes, schema/identity drift,
duplicate keys, nonnumeric/nonfinite cells and inconsistent source dates stop
the audit. Numeric/missingness discrepancies are retained as exceptions rather
than hidden by an inner join. Empty comparisons cannot claim parity. Synthetic
unit fixtures test these failures without accessing providers; existing CI runs
the full test suite and earlier fictional demonstrations, not live downloads.

Raw-response hashes are byte-exact. Code/config hashes describe local file bytes
and can differ across checkouts due to line endings; compare Git content before
interpreting such a difference as a logic change. Later provider downloads can
change: retain the ignored originals to replay this acquisition exactly.

Remaining gates: approval of any production API migration, model-specific
handling of unavailable dimensions/stale observations, other-source cohort
alignment, uncertainty calibration and independent operational validation.
ACLED permissions and provenance questions from #13 remain unresolved. No
stacked PR is merged and neither issue #9 nor #11 is closed by this milestone.
