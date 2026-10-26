# Methodology red team: synthetic source and scoring stress tests

**Research status:** Experimental; requires independent validation. This work
demonstrates weaknesses and invariants of the *implemented mathematics* using
two entirely fictional countries. It is not a validation of observed executive
protection incidents, source completeness, or operational effectiveness.

**Dependencies:** [Offline synthetic demonstration](OFFLINE_SYNTHETIC_DEMO.md)
and the [research model card](MODEL_CARD.md). This module is stacked on the
synthetic demo (draft PR #7), which itself builds on historical-vintage controls
(draft PR #5). They remain separate reviewable changes.

## One-command audit after the synthetic demonstration

From the repository root:

~~~bash
python -m src.offline_synthetic_demo --output-dir outputs/synthetic_offline_demo
python -m src.methodology_red_team \
  --demo-dir outputs/synthetic_offline_demo \
  --output-dir outputs/methodology_red_team_demo
~~~

Choose fresh output directories for repeat runs: neither runner overwrites an
earlier result. Both are offline and require no provider credentials. The
methodology runner verifies every referenced synthetic input, output, source-code
fingerprint and evidence manifest against the upstream receipt before executing
a stress test. It then publishes a new immutable directory with a separate
receipt, while retaining the original evidence package unchanged.

CI runs synthetic unit/integration tests, the offline demonstration, the audit
command, and checks the saved Markdown summary and audit JSON receipt.

## Tests, outputs and limits

| Test | Output | Interpretation / limitation |
| --- | --- | --- |
| Country-year source presence | country_year_observation_presence.csv | Counts **fictional** observations in each country and year. One event never establishes coverage completeness, reporting intensity or an absence of risk. |
| Leave-one-weight-out | component_weight_ablation.csv | Reweights 4 of the 5 country-risk components to total 100%; **retains the original severity uplift**. This is a partial sensitivity test, not full construct removal or out-of-sample validation. |
| Cohort scaling perturbation | homicide_cohort_dependence.csv | Adds an invented high-rate country to **one component's normalization**. Documents relative-score dependence on the comparison set; does **not** rescore the full model. |
| Missingness injection | homicide_missingness_stress.csv | Removes the highest or all fictional homicide rates and observes how the actual crime component's median/zero fill and relative scaling respond. Missing values and model defaults are not observations of safe conditions. |
| Severity structural overlap | severity_construct_overlap.csv | Reconstructs all six severity-uplift terms, validates the 25-point cap, and flags their conceptual overlap with already weighted inputs. **Does not** estimate causal/statistical double-counting. |
| Evidence integrity | methodology_receipt.json | Records upstream run receipt SHA-256, audit source hash, counts and output SHA-256; refuses input/output mismatches, source-code drift, and existing destinations. |
| Interpretive research brief | METHOD_REVIEW.md | Computes actual observed toy-example changes; explicitly labels findings **synthetic only** and enumerates the next validation gates. |

The two-country fixture is too small for defensible correlation inference. No
component-correlation estimates are reported. A stable rank among two synthetic
countries is not persuasive empirical evidence, even when thousands of random
weights are simulated.

### Known mathematical hazard: missing homicide evidence

Current country crime scoring imputes missing homicide inputs with a cohort
median when some observations remain. If all homicide inputs are missing,
the implementation fills raw homicide with zero, then its constant-vector
min-max scorer returns **50 out of 100**. This is a neutral-looking index even
though no measurement was present. The red-team runner demonstrates this
behavior without rewriting the production scoring model.

The appropriate downstream rule is to carry an explicit unverified/missing
measurement flag, never treat this midpoint as evidence of moderate safety,
and prevent unsupported individual/operational conclusions. Any future
change to imputation requires a versioned scoring-method decision,
regression tests, rerun of baselines and practitioner review.

### Known mathematical hazard: cohort-dependent normalization

For two fictional homicide rates of 3 and 12 per 100,000, the existing
min-max scoring gives 0 and 100. Adding a **fictional comparator at 120**
(without changing either original input) changes the 12-rate observation to:

\[
100 (12-3)/(120-3) \approx 7.69.
\]

This is a property of the cohort-relative component scale; it is not a
prediction of a 92-point improvement in a country's security. The test
deliberately does not pass that comparator through country-level scoring.

### Known design issue: severity adjustment and correlated constructs

The country composite already weights political violence/unrest, governance,
homicide proxy, energy exposure, and momentum. After that weighted sum, the
severity rule may add points for the underlying conflict/fatality observations,
geographic spread, compound governance/violence, energy instability and
momentum. These constructs are not statistically independent by definition.
The red-team report reconstructs each uplift and reports capped vs. uncapped
values. It does **not** claim a measured degree of double counting.

An eventual complete ablation should rerun input normalization, derived
country features, severity thresholds, regional/forward overlays and any
downstream risk bands, using frozen source snapshots. The weight-only results
here must be read as a narrower diagnostic.

## Source provenance and uncertainty beyond the synthetic demo

**ACLED:** Its historical event observations are periodically revised,
supplemented or corrected, even with unchanged event IDs. Source checks
therefore need extraction as-of, time/territorial coverage, row-level event IDs,
geographic granularity, deduplication rules and revision policies. Neither
dataset presence nor freshness alone certifies data completeness.

- [ACLED: Keeping Data Updated](https://acleddata.com/methodology/keeping-acled-data-updated)
- [ACLED Codebook](https://acleddata.com/methodology/acled-codebook)

**World Bank WGI:** Published country estimates have standard errors; small
differences between countries or time periods should not be interpreted as
meaningful when uncertainty intervals overlap. The model currently uses
country scores and global availability flags without propagating their
country-specific standard errors or source-vintage changes.

- [World Bank WGI methodology and documentation](https://www.worldbank.org/en/publication/worldwide-governance-indicators/documentation)
- [World Bank WGI: 2026 update and usage advisory](https://www.worldbank.org/en/publication/worldwide-governance-indicators)

**No real-source validation has been performed in this red team.** The named
external references explain why source-specific validation is necessary; they
are not evidence that a particular existing portfolio output has been
reconstructed or verified against its historical licensed inputs.

## Release gates still outstanding

1. **Frozen, authorized, source-specific data lineage.** Preserve dataset
   extraction receipts and records' eligible years/countries, address revised
   ACLED event versions, and confirm WGI country/source vintages and standard
   errors. A positive source-presence test is not completeness certification.
2. **Full-cohort construct review.** Independently test overlap of violence,
   fatalities, governance, energy and momentum; ablate upstream constructs
   with severity recalculation, report measurement uncertainty, and use a
   predeclared reference population for relative normalization.
3. **Missingness semantics and fail-closed use.** Separate "not available" from
   zero, never imply validated safety from neutral defaults, and trace missing
   source observations through dashboards and recommendations.
4. **Full offline pipeline rehearsal.** Use a versioned, frozen source package
   and independently reproduce all 27 steps, including forward-event overlays,
   change detection, country profiles and complete report generation.
5. **Independent validation.** Obtain appropriate practitioner feedback and
   independently defined outcomes before assessing whether screening improves
   decisions. Calibrate only if defensible outcome data and an evaluation
   design become available.

**Disposition:** Demonstration quality improves, but the model remains a
nonoperational, uncalibrated OSINT research prototype. The audit should be
reported as revealing methodological uncertainty rather than certifying
model readiness.
