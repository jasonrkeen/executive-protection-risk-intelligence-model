# Research Model Card — Executive Protection Risk Intelligence Model

**Status:** experimental, uncalibrated strategic OSINT screening research (October 26, 2026)  
**Owner:** independent portfolio research  
**Operational approval:** none; no real-trip authorization or end-to-end live-source validation is claimed

## Research objective and intended users

Test whether transparent combinations of open-source conflict and governance
indicators, energy operating-environment exposure, location-level event features,
public access/medical proxies, and explicitly hypothetical movement assumptions
can support **analyst prioritization and evidence-gap identification**.

Potential users include academic reviewers, OSINT researchers, corporate-security
analysts, and protective-intelligence practitioners conducting a controlled
methodology review. Intended outputs are relative screening indices, supporting
factor breakdowns, analyst collection questions, and suggested *human review*
pathways—not decisions about any identifiable individual.

## Explicit non-uses

Do not use any score, risk band, course-of-action text, dashboard, or PDF alone to
approve/deny travel; choose routes, venues, hotels, medical facilities, staffing,
transportation, or evacuation plans; predict an attack against a person; or claim
that an incident is likely to occur with a score/100 probability.

The repository intentionally does not publish real movement, principal, family,
residential, itinerary, or proprietary security data. Use only synthetic or
approved deidentified research inputs.

## Temporal provenance and comparability

| Layer | Window in source code | Required interpretation |
| --- | --- | --- |
| Country structural risk | ACLED features from 2020–2024, model year 2024; World Bank vintage up to 2024 | **Historical baseline**, not a current 2026 country risk |
| 2026 forward overlay | Selected 2025/2026 same-period ACLED features, when available | Heuristic change signal *anchored to* 2024; baseline is retained when target data unavailable |
| City event analysis | 30/60/90/180-day windows relative to newest observation in the staged dataset | Relative to **extract endpoint**; no local reporting-completeness guarantee |
| RPR-1 movement assessment | Reviewed, pseudonymous trip and capacity inputs, with expiry/freshness checks | Analyst assumptions, not an authenticated operational inventory |
| Evidence coverage | Seven source/field/output presence checks | **Coverage index**, not confidence in truth or a predictive probability |

The live entry point requires an assessment date equal to the local current date,
a passing reviewed-input preflight, and a historical-year presence guard. At least
one raw event per configured baseline year is **necessary but not sufficient**
to demonstrate any country's coverage; it does not establish that the data
collection is complete, geographically representative, or source-authenticated.

All reports should display source-specific *data-through* dates and the historical
baseline year rather than implying every layer represents one contemporaneous
measurement. Older committed charts, screenshots, reports, and country profiles
are **illustrations from earlier runs**, not evidence of current conditions.

## Model construction and assumptions

- Country composite: 35% political violence/civil unrest, 20% governance,
  15% homicide proxy, 20% energy exposure, 10% momentum, with a bounded
  additional severity uplift.
- Scores are relative/normalized indices, not empirical incident frequencies
  or actuarially calibrated probabilities. Changing the country cohort can
  change min-max scaling and rankings without new local incidents.
- Energy exposure may capture strategic relevance or operating concentration,
  rather than principal-specific threat. Political violence, fatalities, momentum,
  and severity uplift may overlap; examine correlation/double counting.
- Scenario multipliers, posture thresholds, PI exposure values, RPR-1 protective
  capacity scales, task saturation penalty, and evidence-coverage weights are
  analyst-derived assumptions and **remain unvalidated**.
- Monte Carlo runs vary model weights; stability under randomized weights does
  **not** establish external validity. Sensitivity and Monte Carlo tests are
  internal robustness checks only.
- ACLED geography is an event-record location, not necessarily a formal city
  boundary. OurAirports distance and World Bank health indicators are not
  verified local transportation, hospital, or evacuation capacity.

## Input/output controls and technical tests

- Staged ACLED, trip and capacity files are hash-bound to a reviewed evidence
  manifest. The full run rechecks hashes at selected boundaries.
- The preflight rejects stale global event observations, mismatched trip/capacity
  identifiers, missing review declarations, malformed fields, and ambiguous
  joined locations. Review approvals and sources remain **declarations**, not
  authenticated third-party attestations.
- The baseline-year guard prevents recent-only event extracts from silently
  failing to populate the configured historical country model.
- CI uses synthetic fixtures and unit/integration tests; successful
  checks do not prove a complete reproducible real-source pipeline run,
  accuracy, dashboard runtime health, or third-party provider availability.
- A separate [synthetic methodological red team](METHODOLOGY_RED_TEAM.md)
  tests cohort normalization sensitivity, homicide missingness, weight-only
  ablations, historical source-presence gaps and construct overlap. These
  are diagnostic perturbations on two fictional countries, **not**
  empirical or predictive validation.
- A further [missingness-aware fixed-reference scoring candidate](SCORING_INTEGRITY_CANDIDATE.md)
  demonstrates when scores should be **WITHHELD**, including an explicit
  observed-zero state. It is isolated to a fictional research-only shadow
  calculation and does not alter the existing published scoring methodology.

## Known threats to validity

1. **Temporal mismatch:** 2024 historical structural scores are displayed near
   2026 event overlays; distinguish vintages in every published result.
2. **Reporting bias:** event counts vary with source access, media coverage,
   geography, and retrospective revisions. Zero reports do not imply zero risk.
3. **Proxy validity:** homicide, governance, energy, airport-distance, and
   national health indicators only indirectly measure relevant security concerns.
4. **Missing data:** median/default fills can conceal absence of measurements;
   coverage flags must be read alongside every score.
5. **Construct overlap:** severity uplift and PI/RPR-1 workload may reuse
   concepts that already influence upstream scores.
6. **Output semantics:** named posture and COA recommendations must not be
   interpreted as binding travel, personnel, or threat judgments.
7. **Reproducibility:** raw source snapshots are not checked into Git, and an
   authorized complete live-data run has not yet been independently repeated.

## Required validation before external or commercial use

1. Produce a **fully offline synthetic end-to-end demonstration** with pinned
   versions and a reproducible evidence/test receipt.
2. Independently verify ACLED extraction dates, sampling frame, country and
   administrative joins, and World Bank vintage/coverage at the **country** level.
3. Stress test cohort normalization, missingness, components removed one at a
   time, source exclusions, and historical time slices. Predefine acceptance
   criteria and report negative or inconclusive findings.
4. Seek independent practitioner assessment of threat constructs, capacity
   anchors, escalation rules, and how analysts interpret each output.
5. If incident-labelled outcomes are later obtained through appropriate lawful
   access, specify the outcome and validation design *before* fitting/calibrating
   any predictive quantities. Do not retrofit probabilities to existing indices.
6. Publish a versioned model card, data dictionary, source ledger, evidence
   coverage, tests, and release notes. Never publish actual sensitive itineraries
   or individual-level profiles.

## Release statement

**Research prototype — not operationally validated.** A passing preflight,
synthetic test, workflow badge, or complete evidence-coverage index does not
establish source truth, local collection completeness, validated incident
prediction, or clearance for executive travel.
