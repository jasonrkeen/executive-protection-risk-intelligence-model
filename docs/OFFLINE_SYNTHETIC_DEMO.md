# Offline synthetic integration demonstration

**Research-only scope.** This is a deterministic *vertical slice* of the
Executive Protection Risk Intelligence Model. It exercises real country/year
ACLED feature functions, 2024 country scoring, city event aggregation, airport
distance and medical proxy scoring, synthetic movement PI scoring, RPR-1 residual
risk, COA decision support, IV-2.1 evidence coverage, Monte Carlo weight
perturbations, and the project’s ReportLab/PDF presentation functions.

It is **not** the complete 27-stage, live-source `src.main` pipeline. In
particular, it does not fetch ACLED/World Bank/OurAirports sources, produce
live-country estimates, execute the 2026 forward-change model, or validate
real-world incident prediction or protective operations.

## Run locally

From the repository root, after installing the development requirements:

```bash
python -m pip install -r requirements-dev.txt
python -m src.offline_synthetic_demo --output-dir outputs/synthetic_offline_demo
```

No credentials, network access, or real movement data are required.

The command refuses to overwrite an existing output directory. To repeat the
demonstration, choose a **new** output directory, for example
`--output-dir outputs/synthetic_offline_demo_second`. Outputs are staged on
the destination filesystem and published only after all checks succeed. If a
validation, score, or PDF-render step fails, the incomplete temporary output is
discarded and the chosen destination is not created.

CI runs the integration tests with network sockets and Python HTTP requests
blocked, executes the documented one-command demonstration, and checks its
machine-readable receipt. The tests generate two independent runs and verify
that their receipts and output hashes match exactly.

## Fictional fixtures

`examples/offline_synthetic/` contains:

- `acled_events.csv`: 20 **invented**, ACLED-shaped records covering 2020–2024,
  2025, and a 2026 extract endpoint of October 16; none are actual ACLED data.
- `country_indicators.csv`: entirely hypothetical governance, homicide, energy
  and health indicator proxies for **Testland** and **Example Republic**.
- `airports.csv` and `medical_reference.csv`: fictional support references;
  the named airports and country health proxies must not be used for travel.
- `protective_intelligence_trip_inputs.csv`: two explicitly labelled
  **SYNTHETIC** movements with no real itinerary or identifiable principal.
- `protective_capacity_inputs.csv`: invented, complete capacity and workload
  ratings for each fake movement.
- `decision_rules.csv`: illustrative rule-lookup metadata; decision logic is
  computed by the real COA module, not by this illustrative CSV.

The runner stages exact copies of these files in a temporary `data/raw`
directory and creates a synthetic-only `rpr1_evidence.json` manifest with
SHA-256 hashes, fixed historical dates, and **TEST-ONLY** reviewer and assessor
declarations. These are programmatic fixtures, *not actual source review or
source authentication*. The normal preflight is called with explicit
`assessment_date=2026-10-17` and `mode=synthetic`. Neither the current-date
live runner nor live/proprietary source fetching is invoked.

## Output contract

The result directory contains:

| Path | Description |
| --- | --- |
| `data/raw/` | Copies of the fictional inputs and generated test-only manifest |
| `data/processed/acled_country_risk_features.csv` | Actual country/year event transformations, with synthetic source marker |
| `data/processed/city_ep_risk_features.csv` | Extract-relative city event features |
| `data/processed/city_access_proxy_features.csv` | Synthetic airport and medical support proxies |
| `data/processed/protective_intelligence_trip_scores.csv` | Actual trip-level PI scoring |
| `data/processed/residual_protective_risk_scores.csv` | Actual RPR-1 scoring, including capacity/workload ratings |
| `tables/executive_protection_risk_rankings.csv` | 2024 historical country baseline for fictional countries |
| `tables/protective_intelligence_decision_support.csv` | Actual COA scoring and review-floor logic |
| `tables/decision_rule_audit.csv` | COA and RPR-1 rule audit |
| `tables/intelligence_confidence_scores.csv` | Seven-field **evidence coverage** index, not accuracy confidence |
| `tables/source_coverage_gaps.csv` | Missing evidence categories |
| `tables/analyst_collection_plan.csv` | Follow-up collection questions |
| `tables/synthetic_weight_sensitivity.csv` | 25 runs using the configured fixed seed 42, **not** predictive validation |
| `reports/synthetic_research_demo.pdf` | Synthetic PI, COA, and evidence-audit report |
| `run_receipt.json` | Fixed model versions, exact Python/pandas/numpy/ReportLab/scikit-learn versions, source-code SHA-256 hashes, time windows, row counts, quality flags, and input/output SHA-256 fingerprints |

Additional generated tables and the synthetic medical reference are documented
in the receipt or the input directory.

A clean run is expected to report **20 invented event records, 10 historical
country-year records, 2 baseline country records, 2 city records, 2 synthetic
movements, 2 residual scores, 2 COA rows, and 2 evidence coverage records**.

All receipts state that sources and predictions remain unverified.
Independent byte-for-byte reproducibility is verified under the **same dependency
environment**. The repository currently specifies minimum package versions, not
a frozen cross-platform dependency lockfile; version changes can alter PDF or
CSV bytes. The exact analysis package versions and exercised source-file digests
are recorded to make those differences auditable.

## Failure checks

`tests/test_offline_synthetic_demo.py` verifies:

- Equivalent independent runs produce identical receipts and output bytes;
- Explicit blocked sockets/HTTP connections are not attempted;
- Missing 2020–2024 source vintages fail before output publication;
- An incomplete capacity record fails preflight even with a freshly generated
  input hash;
- Non-synthetic event IDs are rejected;
- A preexisting output directory is not overwritten, and incomplete temp
  directories are cleaned.

## Known limitations and follow-up

This is an engineering and interpretability milestone, not a model-validation
study. **Historical year presence does not establish country/year completeness.**
A global 2026 event tail does not imply adequate reporting for a quiet city,
and World Bank-like fictional inputs cannot validate real WGI country coverage.
Min-max normalization, empirical scale anchoring, double counting, and practitioner
interpretation remain to be assessed independently.

Issue #6 remains open until a truly offline reproduction of the larger pipeline
(or a documented equivalent) and an independent assessment of source provenance,
coverage, and construct validity are delivered.

The repository’s [model card](MODEL_CARD.md) explains the research-only limits.
