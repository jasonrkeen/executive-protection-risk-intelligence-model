# RPR-1 experimental research preflight

The full pipeline now fails before its first network request or generated output
unless staged inputs pass an explicit-date gate **and** include actual events
from every configured historical baseline year (currently 2020–2024).
There is no bypass switch in `src.main`. This is an engineering readiness
check, not certification, empirical validation, or travel clearance. RPR-1
weights and thresholds remain uncalibrated.

## Prepare a reviewed package

Stage these files locally under `data/raw/` (never commit them):

1. `protective_intelligence_trip_inputs.csv`: use the blank template in `examples/`.
   Use pseudonymous movement/principal identifiers, never real personal data.
2. `protective_capacity_inputs.csv`: use the existing capacity template. Every
   movement requires all seven capability and five workload assessments, 0–100.
   The gate blocks missingness even though the standalone RPR-1 scoring function
   deliberately retains its unknown/neutral behavior for exploratory research.
3. `acled_events.csv`: authorized source export using canonical `country`,
   `location`, `admin1`, `admin2`, and `event_date` columns, plus the fields required
   by the existing event pipeline. Dates must be YYYY-MM-DD. Preserve the source
   terms and query receipt; do not replace a failed query with zero events.
4. `rpr1_evidence.json`: copy the evidence template and fill the reviewed values.
   It intentionally cannot pass with blanks or pending approval.

Set `data_class` to `deidentified_research` for a current research run, or
`synthetic` only for standalone fixture validation. `contains_personal_data=false`
is an explicit declaration, not automated personal-data detection. Reviewer and
assessor references must be nonpersonal internal identifiers.

Record the SHA-256 of each exact CSV under `input_sha256`. Use your operating system's SHA-256 tool
or `hashlib.sha256(Path(path).read_bytes()).hexdigest()` in Python. A reviewer must
check those exact bytes before approval. Changing data requires fresh review and
updated hashes. Hashes prove byte consistency, not factual authenticity.

Keep two evidence records per movement: `kind=trip` and `kind=capacity`. Record
the source/evidence reference, assessment date, movement date, expiry, applicability
scope, assessor, reviewer, and review status. Both records must describe the same
movement date. The capacity evidence reference must support all twelve assessments;
use a local evidence register for field-specific sources and gaps. Do not mark
approval merely to make the gate pass. Evidence documents themselves are not
fetched or authenticated by the gate.

## Run

Read-only check (prints a JSON receipt on success; exits 2 on a blocked check):

The receipt includes the assessment date, mode, applied freshness policy, input
hashes and evidence-file hash. Preserve it with the run record; a pass does not
approve later input changes.

```
python -m src.preflight --assessment-date YYYY-MM-DD
```

After a successful check, the full pipeline repeats it and then checks
historical source-year presence **before** performing any network fetch:

```
python -m src.main --assessment-date YYYY-MM-DD
```

The read-only `src.preflight` command does **not** itself check baseline
year presence. The full `src.main` command checks that each year in
`src.config.START_YEAR` through `END_YEAR` has at least one raw ACLED event.
This catches a recent-only extract that would otherwise create an empty or
incomplete historical country dataset. Year presence is **not** evidence of
geographic coverage, event completeness, source integrity, or comparability
across the historical period.

The assessment date is the analyst's explicit reference date, never inferred
from file modification time or the newest event. Standalone synthetic checking
uses `python -m src.preflight --assessment-date YYYY-MM-DD --mode synthetic`.
Synthetic mode does not run the network-enabled full pipeline. Unit tests create
temporary synthetic files; no provider data are committed or fetched.

## Checks and provisional policy

`PreflightPolicy` in `src/preflight_config.py` sets a 30-day maximum event age and a 30-day
maximum assessment age. These are provisional research controls, not validated
operational limits. The boundary is inclusive: 30 days passes, 31 days fails.
Changes require review and sensitivity consideration.

The gate checks reviewed source coverage dates and actual newest event dates;
a recent retrieval timestamp cannot rescue old observations. Events must fall
inside declared coverage, which cannot extend after retrieval or assessment.
Assessments must be current at the reference date and remain valid through the
movement date. Capacity/trip IDs must match exactly, including leading zeros.

Location matching uses the current scorer's normalized city/country key. If the
raw source has more than one administrative location under that key, the run is
blocked rather than choosing one or multiplying rows. The gate conservatively
checks the whole staged source before filtering. Resolve ambiguity through a
reviewed location-key implementation, not arbitrary source-row deletion.
The PI calculation checks actual generated context again, blocking unmatched or
multiple matches. Absence of a location is missing context, not a zero-risk city.

## What passing does not establish

Passing only confirms this package's shape, dates, declarations, hashes and join
uniqueness. It does not establish event reporting completeness, local airport or
medical readiness, assessor reliability, correctness of approvals, or predictive
accuracy. Event freshness is assessed for the dataset, not each quiet location.
The caller supplies the reference date; using an old reference date is historical
research and must never be represented as a current assessment.

Country risk remains anchored to the 2024 historical baseline even with
a fresh 2026 event tail. City rolling windows are measured relative to the
dataset's latest observation and do not certify city-specific event coverage.
Other legacy pipeline sources (country/forward/World Bank) may have different
vintages, and the full pipeline may fetch revised data. This gate is not a frozen
snapshot runner or an end-to-end provenance certificate. Preserve final receipts
and inspect all output source dates. Standalone legacy stages remain callable;
the enforced entry point is `src.main`, plus the PI join guard. Do not edit input
files during a run. Current real-data validation and independent practitioner
review remain outstanding.

Tests: `python -m pip install -r requirements-dev.txt` then `python -m pytest -q`.
The new pytest cases run alongside the existing unittest suite in CI.


## Review hardening

The live `src.main` entry point requires today's local date. Historical dates
remain available only to the read-only preflight command; its receipt is valid
only as of the recorded date. Passing a historical check cannot authorize a live run.

Trip exposure, scenario and sector labels must belong to the scorer's explicit
vocabularies; typos cannot silently receive fallback scores. Event inputs require
canonical year, event_type and fatalities as well as location/date columns.
Year must match the strict event date; fatalities must be finite nonnegative
integers. Administrative identity must be nonblank (resolve missing identifiers
with source evidence; do not invent labels to pass). Duplicate CSV headers,
duplicate JSON keys and boolean schema versions are rejected.

Each assessment lists `covered_fields` exactly as in the template. Reviewers must
verify support for all listed fields. This is a coverage declaration, not automatic
verification of linked evidence or reviewer identity.

The pipeline rechecks hashes before country, city, PI, residual scoring and report
generation. Changes abort the run; discard partial outputs. These checks detect
changes at boundaries, but are not an atomic snapshot or protection against a
concurrent writer changing and restoring inputs between checks. Run with exclusive
ownership of the staged files. Legacy standalone stages and dashboard readers do
not acquire a preflight attestation by being callable or by displaying old outputs.
