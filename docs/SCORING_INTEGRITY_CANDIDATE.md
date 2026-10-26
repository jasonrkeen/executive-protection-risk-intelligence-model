# Scoring Integrity: Fixed Reference and Explicit Evidence Status (Research Candidate)

**Status:** Experimental synthetic shadow demonstration; **NOT ADOPTED** as the
production scoring contract or a travel/security clearance system. All inputs
in this experiment are fictional. The original historical country model and
its files remain unchanged. This builds upon the synthetic methodology audit
([METHODOLOGY_RED_TEAM.md](METHODOLOGY_RED_TEAM.md)).

## Why this candidate exists

The existing historical scorer uses relative min-max normalization and can fill
unavailable homicide observations with defaults. When *all* homicide rates are
missing, a constant imputed vector can produce the neutral-looking index **50**.
Adding a new country with an extreme value can also change scores for countries
whose raw observations have not changed.

Both are mathematical behaviors, not evidence that the risks have improved or
that a missing value represents a reported zero. The remedy under investigation
is to separate an **evidence state** from a numerical risk index and to freeze a
transparent reference population before comparing scores.

## Reproducible demonstration

From the repo root with development requirements installed:

~~~bash
python -m src.offline_synthetic_demo --output-dir outputs/synthetic_offline_demo
python -m src.scoring_integrity_demo \
  --demo-dir outputs/synthetic_offline_demo \
  --output-dir outputs/scoring_integrity_candidate_demo
~~~

Use a new destination for repeat runs; output directories are never overwritten.
The scoring runner first checks every upstream input and output fingerprint,
historical source window, and source-module hash. No network calls or provider
credentials are required or allowed by its tests. A failing source, malformed
contract, or invalid scoring calculation prevents publication of trusted output.

The demonstration creates:

| Output | Purpose |
| --- | --- |
| \`candidate_homicide_baseline.csv\` | In-range observed-only fictional homicide indices and evidence states |
| \`candidate_shadow_comparison.csv\` | Side-by-side original historical component/composite and research-only shadow composite; never a new risk band |
| \`candidate_all_missing_shadow.csv\` | Missing evidence produces **WITHHELD** instead of a numeric shadow score |
| \`candidate_evidence_stress.csv\` | All missing, one missing, stale, conflicting, imputed, and negative-value cases |
| \`frozen_reference_cohort_probe.csv\` | Original country remains stable under frozen reference while legacy cohort min-max shifts |
| \`SCORING_DECISION_RECORD.md\` | Generated options, assumptions, rejected silent clipping, and release requirements |
| \`SYNTHETIC_CANDIDATE_SCORING_REVIEW.pdf\` | Explicit source status and WITHHELD states in a research-only report |
| \`scoring_integrity_receipt.json\` | Fingerprints for reference/inputs/code/outputs, upstream receipt, quality flags, limitations |

The module also has a standalone, research-only Streamlit presentation helper.
**It is not installed in the live dashboard.** No production data, risk band,
COA logic, composite weight, severity rule, or threshold was modified.

## Evidence contract

The candidate accepts one record per fictional country with these fields:

| Field | Contract |
| --- | --- |
| \`country\` | Nonblank unique country key |
| \`homicide_rate_per_100k\` | A nonnegative finite observation; missing is not interpreted as zero |
| \`source_status\` | One of \`observed\`, \`observed_zero\`, \`unavailable\`, \`imputed\`, \`conflicting\` |
| \`source_year\` | Source observation year, required for any observed value |
| \`source_ref\` | Nonblank reference for observed or observed-zero records |
| \`unit\` | Exactly \`per_100k_population\` |

Candidate numerical scores are **withheld** whenever the source is missing,
stale, imputed, conflicting, future-dated, invalid, or outside the declared
reference domain. Zero is accepted only with the explicit \`observed_zero\`
declaration and supporting source/year, not as a default for missing data.
Unknown statuses, incompatible units, duplicate country rows, and malformed
reference definitions are rejected as invalid contracts.

All candidate rows require analyst review. Even successful synthetic
\`RESEARCH_OBSERVED_IN_RANGE\` results do not prove source authenticity.

## Frozen reference policy — explicitly provisional

The immutable **toy** reference \`examples/offline_synthetic/scoring_reference.json\`
contains an example homicide-rate anchor of **3–12 per 100,000**, taken
exclusively from two fictional countries with a 2024 structural baseline.
The synthetic evidence declarations have a 2024 vintage, and the policy compares
them to a **2026** assessment year with a provisional **three-calendar-year**
maximum age. That age rule is **not** a scientifically or operationally
validated period for real homicide data; local availability varies.

Unlike rolling min-max scaling, this reference is **not refitted** when new
countries are introduced. Adding a fictional comparator with homicide rate 120
changes the original Testland legacy component from 100.00 to 7.69, while
its fixed-reference research component remains 100.00. The new comparator is
**BLOCKED_OUTSIDE_REFERENCE**, not silently clipped to 100.

**A fixed two-country reference is not a proposed real-world benchmark.**
Selecting any valid operational reference domain would require source-specific,
country-year population review, units, coverage, outlier treatment, reference
revision governance, and independent review. Unchanged synthetic indices do not
establish validated absolute risk.

## Shadow composite limitations

The experimental shadow uses the **original** weighted historical country score,
replaces only its 15% homicide component with the candidate observed-only index,
and **holds the existing severity uplift fixed**. It does not recompute
upstream conflict/energy/governance features, model cohort statistics, severity
thresholds, time-varying overlays, or analyst decision support.

If the candidate homicide component is blocked, the shadow composite is also
**WITHHELD**, with an explicit \`WITHHELD_REQUIRED_SOURCE_EVIDENCE\` disposition.
Even when numerically available, the composite remains a fictional
\`SHADOW_RESEARCH_ONLY_NOT_VALIDATED\` illustration; other components lack
independent source verification. **Risk band and protective posture are always
NOT_ISSUED**, regardless of the observed toy component score.

## Decision options

| Option | Benefit | Major limitation | Research disposition |
| --- | --- | --- | --- |
| Keep legacy rolling min-max and implicit fills | Preserves historical numerical results | Missing evidence can yield 50; new comparison countries remap scores | **Freeze for comparison**, not source-certified |
| Fixed, versioned reference and source-status gate | Separates unavailable evidence from observed measures; avoids comparator-induced score drift | Choice of reference and age allowance unvalidated | **Candidate for validation** |
| Fixed reference with automatic clipping/median fill | Easy numerical continuity | Creates plausible-looking numbers from unsupported evidence | **Rejected for candidate** |

This is a methodological decision proposal, not an automatic release upgrade.

## Source-quality and release gates still outstanding

1. Independently retrieve/licence an appropriate ACLED historical data snapshot,
   record its extract date, event IDs, revisions, territorial coverage and reported
   uncertainty; validate representativeness by country and year.
2. Obtain World Bank WGI source year, estimated uncertainty and country-specific
   coverage; propagate plausible uncertainty into national scores.
3. Develop a frozen, **realistic and defensible** normalization population and
   reference policy, explicitly testing outliers, zeros, sparse observations,
   source revisions, new countries and country/year withdrawal.
4. Recalculate all components and severity adjustments from source data, test
   data-quality propagation into reporting/dashboard/decision layers, and
   compare against a versioned original baseline.
5. Conduct independent practitioner assessments and a preregistered test of
   analyst interpretation/decision quality. No probability claims until proper
   outcome data justify calibration.

**Disposition:** Useful mathematical and engineering safety improvement in a
fictional research slice; **not validated for operational, commercial or
individual threat assessments**. Do not merge without review of stacked
draft PRs #5, #7, and #8 and the currently defined candidate acceptance gates.

Work item: [GitHub Issue #9](https://github.com/jasonrkeen/executive-protection-risk-intelligence-model/issues/9).
