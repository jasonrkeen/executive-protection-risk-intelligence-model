# Real-source provenance verification — 26 October 2026

Status: **metadata and one WGI country-year API sample verified; operational
readiness NOT ESTABLISHED; ACLED account entitlement UNKNOWN**.

This milestone is stacked on PR #12 (`b076b86ac1df12fd9a4779ff9fbde4b677117ada`).
It adds an isolated verifier, not a replacement production feed. Existing scoring,
configuration, frozen artifacts and synthetic demonstrations remain unchanged.
No real itinerary, principal, personal record or ACLED event was requested or
introduced. Tests fabricate responses; the dated receipt records real requests.

## Evidence register and vintage boundaries

All primary sources below were inspected on 2026-10-26. Web documentation is a
dated observation, not an immutable contract. API response SHA-256 hashes,
request URLs, retrieval times and status codes are in
[`provenance/wgi_api_receipt_20261026.json`](provenance/wgi_api_receipt_20261026.json).
Only metadata and presence checks are published; full response bytes stay local
under ignored `data/raw/`. A hash identifies bytes; it does not authenticate the
provider, prove accuracy or reconstruct an unavailable snapshot.

| ID | Primary evidence | Verified observation | Limit |
|---|---|---|---|
| WB1 | [WGI home](https://www.worldbank.org/en/publication/worldwide-governance-indicators) | Explicit 2026 Update citation, six dimensions, coverage 1996–2025 | Release year is not observation year |
| WB2 | [World Bank catalog](https://datacatalog.worldbank.org/search/dataset/0038026/worldwide-governance-indicators) | 2026 aggregate files dated September 18; catalog metadata September 29; public/CC BY 4.0 designation | These dates are not proven first-publication dates; underlying third-party rights not inferred |
| WB3 | [WGI documentation](https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation) | Estimates with model-based standard errors and separate 0–100 scores with 90% intervals | Not calibrated protection-risk uncertainty |
| WB4 | [2026 methodology, section 3.3](https://www.worldbank.org/content/dam/sites/govindicators/doc/The%20Worldwide%20Governance%20Indicators%202026%20Methodology.pdf) | Fixed benchmark transformation; estimate ±1.64 SE transformed to score intervals, capped at 0/100 | Not a percentile rank, cohort min-max, or universal estimate-to-score formula |
| WB5 | [Source 3](https://api.worldbank.org/v2/source/3?format=json) and [indicator inventory](https://api.worldbank.org/v2/source/3/indicator?format=json&per_page=1000) | WGI source identity; API lastupdated 2026-09-25; 36 named series | API supplies an update date, not an explicit immutable release identifier |
| WB6 | [Source 75](https://api.worldbank.org/v2/source/75?format=json) | ESG source, lastupdated 2026-06-24 | Do not treat as synonymous with the WGI database |
| AC1 | [Getting started](https://acleddata.com/api-documentation/getting-started) | myACLED account; cookie or OAuth access; current API base `https://acleddata.com/api/` | Documentation verified, authentication/entitlements not tested |
| AC2 | [EULA](https://acleddata.com/eula), updated July 8, 2025 | Entity-specific licensing; redistribution restrictions; API/platform download routes; scraping prohibited | No determination of this user's applicable license |
| AC3 | [Content usage](https://acleddata.com/contentusage), updated July 8, 2025 | Third-party services require authorization; substitute products and some AI uses prohibited | Public portfolio or commercial protection use is not authorized by this milestone |
| AC4 | [Attribution](https://acleddata.com/attributionpolicy) | Cite ACLED, access date, filters and transformations; cite visualizations | Page displays malformed date `20 September July 2026`; exact effective date unresolved |
| AC5 | [Codebook](https://acleddata.com/methodology/acled-codebook) | Stable event IDs, date precision, source/source_scale and timestamp definitions | Source names are not guaranteed article URLs or independent corroboration |
| AC6 | [Deleted endpoint](https://acleddata.com/api-documentation/deleted-endpoint) | Deletion IDs/timestamps needed to reconcile local extracts | Page retains legacy key/email instructions conflicting with AC1; live behavior untested |

The 2026 release is independently supported by WB1/WB2, rather than inferred
from the calendar. Revised history must not be spliced into a prior vintage.
WB2 dates, WB5 update date, retrieval date and observation year remain separate.
Exact first release day and workbook/API numeric parity remain **unknown**.
No underlying proprietary WGI source dataset was downloaded.

## Verified API mapping and baseline discrepancy

Source **3**, prefix **`GOV_WGI_`**:

| Dimension suffix | Provider dimension | Existing model role |
|---|---|---|
| PV | Political Stability | `political_stability`, scored |
| RL | Rule of Law | `rule_of_law`, scored |
| CC | Control of Corruption | `control_of_corruption`, scored |
| GE | Government Effectiveness | `government_effectiveness`, scored |
| VA | Voice and Accountability | `voice_accountability`, informational |
| RQ | Regulatory Quality | Not added to model scoring |

| Field suffix | Meaning and unit |
|---|---|
| `.EST` | Governance estimate; statistical units, typically about −2.5 to +2.5 (not hard bounds) |
| `.SE` | Model-based standard error in estimate units |
| `.SR` | Source count, not accuracy or independence |
| `.SC` | Fixed-reference governance score, 0–100 |
| `.SC_LB`, `.SC_UB` | Lower/upper 90% confidence bounds in score units |

For example: `GOV_WGI_PV.EST`, `GOV_WGI_PV.SE`. The checked-in
[contract](provenance/wgi_api_contract.json) contains exact provider names.
The API sample's `unit` strings were empty; meaning comes from named indicator
metadata plus WB3/WB4, never from numeric range alone. Percentile ranks must not
be substituted for absolute scores. Cross-dimension covariance was not established.

The unchanged `src/config.py` uses source 75 and legacy codes such as `PV.EST`.
The exact USA/2025 legacy request returned an API error envelope (id 120), despite
HTTP 200. The full source-3 inventory and all six fields for each dimension were
available and non-null for USA/2025. This is a public national aggregate smoke
test, not an executive/person-level dataset or validation of every country/year.
The verifier rejects pagination, nulls, duplicates, changed names/source IDs,
wrong country/year, inconsistent update dates and invalid uncertainty bounds.
Missing data are never replaced with zero. Failure produces no success receipt.

## ACLED access and provenance decision

**Current decision: documentation only; no ACLED downloader or credentials used.**

AC1 documents authenticated programmatic access and platform access. AC5 also
describes export-tool and curated-file routes. These are candidate acquisition
options only after applicable account scope and purpose are established. A
download button or successful login would not establish publication permission.

AC2 distinguishes corporate and public-sector licenses. External data-derived
materials must be transformative and non-reconstructable; a reorganized dataset
or dashboard alone is insufficient. Raw data/analysis and access credentials
must not be redistributed. AI restrictions are conditional but substantive;
this review does not assert either blanket AI permission or a universal ban.
AC3 further restricts providing services without authorization. Unresolved scope
requires provider clarification before any real ACLED integration or release.
No provider was contacted in this milestone.

For a later authorized **private** extract, the proposed research provenance
record should include acquisition route, scope/permission evidence reference,
UTC retrieval time, sanitized filters, response restrictions and page counts,
raw-file hash, schema/version, event ID, event date/year, time/geo precision,
source/source_scale, provider timestamp and local snapshot ID. Keep restricted
records and any source text outside Git and public CI artifacts. A public
receipt must be separately reviewed: even filters/counts may reveal scope.
These are project requirements, not a claim that ACLED supplies every field.

AC5 defines time precision as 1 (highest) through 3 (lowest); timestamp is an API
upload time, not the event date or necessarily a complete revision history.
AC6 supports deletion reconciliation using `event_id_cnty`/`deleted_timestamp`.
Retain both snapshots for authorized private comparison; a revision flag is
locally derived, not assumed to be a native provider field. Neither row presence
nor absence establishes reporting completeness. Authentication discrepancies
between AC1 and AC6 remain recorded rather than silently resolved by old examples.

## Reproduction and review gates

Offline, no credentials or network required:

```bash
python -m pytest -q tests/test_provider_verification.py
python -m pytest -q
```

Opt-in public World Bank verification (choose a NEW directory for each run):

```bash
python -m src.provider_verification --live --output-dir data/raw/provider_verification_NEW
```

This performs five bounded requests. Raw WGI responses remain ignored locally;
only `receipt.json` is a candidate for publication after review. Later runs may
fail when provider names, inventories or timestamps change; do not weaken the
contract automatically. CI runs offline tests and the existing fictional demos,
not live provider access. No new dependency is needed (standard library only).

Remaining gates: workbook/API vintage parity; country/year coverage for the
actual cohort; approved baseline migration; covariance/uncertainty methodology;
ACLED account/purpose/redistribution authorization; private extraction/revision
reconciliation; independent model validation. Issues #9 and #11 remain open.
This milestone establishes neither travel advice nor operational readiness.
