# Synthetic WGI Country Uncertainty and ACLED Event Provenance

**Disposition: RESEARCH ONLY, NOT VALIDATED.** This is an offline, reproducible,
two-fictional-country diagnostic. It does not fetch World Bank or ACLED data,
redistribute restricted provider content, recalibrate incident probabilities, or
approve protective operations. The existing 2024 country results and 27-stage
production pipeline remain unchanged.

**Prerequisites:** draft PR #5 (historical-year integrity), #7 (fictional
scoring→report reproducibility), #8 (red-team), #10 (source-status candidate).
This work is stacked and must not be merged independently.

## Why this matters

The World Bank's **2026 WGI update** (last updated September 18, 2026) includes
estimates and absolute fixed-reference 0–100 scores for **1996–2025**.
Historical values were revised. The two presentations represent **different
scales**, so the existing model's 2024 historical estimate inputs must not be
replaced with 0–100 WGI scores and then independently min-max normalized
without an explicit methodology revision. The existing WGI source codes/API
path and 2024 WGI release vintage require separate live-source verification.

The WGI reports standard errors, reflecting uncertainty in the governance
estimates. Such uncertainties require country-specific support and cannot be
treated as independently observed exact values. **WGI estimates are not
definitive judgements**, and the World Bank cautions against using them alone
for high-stakes investment, credit or governance decisions.

**Official reference materials:**
- [World Bank: 2026 Worldwide Governance Indicators](https://www.worldbank.org/en/publication/worldwide-governance-indicators)
- [World Bank WGI data catalog](https://datacatalog.worldbank.org/search/dataset/0038026/worldwide-governance-indicators)
- [World Bank: WGI standard errors and uncertainty](https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation)
- [World Bank WGI Usage Advisory](https://www.worldbank.org/en/publication/worldwide-governance-indicators/usage-advisory)

ACLED is a **living dataset**; event details and reported fatalities may change.
ACLED event date precision is recorded separately from the displayed event
date. Present event IDs, recent observations and hashes alone do not establish
geographic collection completeness or independently verify fatalities.

- [ACLED Codebook](https://acleddata.com/methodology/acled-codebook)

## Reproduce without source credentials

From repository root with development requirements installed:

~~~bash
python -m src.offline_synthetic_demo \
  --output-dir outputs/synthetic_offline_demo

python -m src.source_uncertainty_demo \
  --demo-dir outputs/synthetic_offline_demo \
  --output-dir outputs/synthetic_source_uncertainty
~~~

Existing output directories are never overwritten. Each run first verifies the
upstream synthetic demo's hashed input, generated outputs, model-code snapshot,
report and assessment-period receipt. Output is staged temporarily and only
published after every source check, actual country-score rerun and receipt
calculation completes.

### Data contract

Two extra **completely invented** fixtures are under
\`examples/offline_synthetic/\`:

**\`wgi_uncertainty_panel.csv\`** has ten fictional
\`(country, indicator)\` cells: political stability, rule of law, control of
corruption and government effectiveness, plus voice/accountability as a
supplementary dimension. Every row declares an estimate in
\`standard_normal_estimate\` units, an entirely **synthetic** positive standard
error, source count, source year (2024), release ID, release date (September
18, 2026), retrieval date, and \`synthetic://\` reference. All synthetic
estimates must exactly match the independent frozen baseline fixture before
any simulation; mismatches are blocked.

The test rejects duplicate country/dimension IDs, mixed WGI releases, mixed
standard-normal and 0–100 scales, mismatched source years, future retrievals,
invalid standard errors, and unauthorized/nonfictional records.

An absent **scored** country/dimension is flagged
\`BLOCKED_MISSING_COUNTRY_DIMENSION\`, with its country's risk output withheld
from this experimental uncertainty workflow. The informational voice dimension
remains visible even though the production governance scorer presently excludes
it from the four-indicator mean. A complete toy row is **not** proof of an
authentic source estimate.

**\`acled_provenance_sidecar.csv\`** has exactly one fictional record for
each of the earlier 20 invented event IDs. It declares the event date and year,
time precision (1–3), a synthetic source reference, extract/snapshot ID,
observation timestamp and synthetic revision flag. Missing/orphan IDs,
duplicate IDs, mismatched event years/dates, mixed snapshot IDs, unrecognized
precision, or future capture timestamps fail closed. Country/year presence
is not completeness, and zero recorded events cannot establish safe conditions.

### Uncertainty propagation

For the same two-country **2024 structural model**, the runner draws fictional
country × dimension governance estimates with a fixed random seed. It uses:

- 24 independent normal-error perturbations at **1× toy standard error**;
- 24 more at **3× toy standard error** to deliberately stress thresholds;
- the production **country-scoring functions**, recalculating civil
  unrest/political violence, governance, homicide, energy, momentum, **and
  the capped additive severity adjustment** on each modified input table.

The other indicators, 2020–2024 event features, source population and
methodology remain frozen. This is a *country-scoring-function chain rerun*,
not the entire 27-stage data-collection/forecast/dashboard/report pipeline.

**Important statistical limits:** the independent-normal draw assumption is
a transparent toy simplification, not the World Bank's uncertainty/covariance
model. WGI dimensions and different years may correlate. The reported 24-draw
min/median/max and changes in **legacy model labels** are **not confidence
intervals, empirical event probabilities, calibrated safety assessments or
real-country risk estimates**. N=2 fiction is too small for inference.

### Output artifact contract

| Artifact | What it verifies |
| --- | --- |
| \`wgi_country_dimension_coverage.csv\` | Country-specific dimension, year, unit, release/standard error and source-presence rows |
| \`wgi_country_scoring_readiness.csv\` | Blocked vs research-ready fictional country status (four scored dimensions required) |
| \`wgi_missing_dimension_stress.csv\` | Intentionally missing country/dimension row flagged, not converted to zero |
| \`wgi_missing_country_readiness.csv\` | Demonstrates withholding source-incomplete country |
| \`event_provenance_integrity.csv\` | Source event ID and timestamp/precision reconciliation |
| \`event_country_year_presence.csv\` | Synthetic country-year counts; no real completeness certification |
| \`governance_uncertainty_country_reruns.csv\` | Actual recomputed component/severity/risk-index results per toy draw |
| \`governance_uncertainty_summary.csv\` | Toy range, counts, modeled band changes per fictional country and scenario |
| \`SOURCE_UNCERTAINTY_FINDINGS.md\` | Dynamic negative-findings and methodological caveat report |
| \`source_uncertainty_receipt.json\` | SHA-256s, code/input versions, source windows, seed, sample size, source-validation flags |

The 2026 WGI and ACLED official URLs are **methodology references**, not
credentials or evidence that actual source records were collected in this
experiment. No real provider row is included or verified.

## Next gates before applying any result to real data

1. Independently check the 2026 WGI provider source availability, indicator
   codes/API aliases, estimates-versus-absolute-score units, dated exports,
   revised 2024 history, access restrictions, and standard errors. Explicitly
   distinguish 2024 observation years from the 2026 release.
2. Obtain an authorized, frozen ACLED export with source identifiers, extract
   timestamp, event time precision, country/location coverage, and revision
   comparisons. Never equate global freshness with local completeness.
3. Specify a principled covariance/uncertainty propagation method and missing
   source handling; validate with a substantially larger eligible reference
   population and practitioner review.
4. Independently rerun all country features and the complete 27-stage pipeline
   from preserved source receipts; monitor cross-release changes and historical
   score stability.
5. Predefine externally observable protective-intelligence decision outcomes
   before any attempt to establish model effectiveness or predictive validity.

**Release boundary:** This synthetic diagnostic cannot justify changing
operational score bands, country-based travel decisions or model validation
claims. The original \`main\` branch remains unchanged by this work.
