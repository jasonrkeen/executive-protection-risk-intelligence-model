# RPR-1: replacement residual protective risk integration

This is a new implementation replacing the unavailable
`executive-protection-risk-intelligence-model-residual-integration-v1.zip`.
It is not the recovered package, a byte-equivalent reconstruction, or a validated
reproduction of historical numerical results. Baseline: Git commit
`d403301936c9c5eacf69e7dbd445aa8a5d55eb13`.

## Scoring contract

All inputs are analyst assessments on a 0–100 scale. Capacity measures effective
capability available to this movement, not headcount. Assess driver, close
protection, advance, intelligence, medical, communications, and local support
capacity. Use 0 for absent capability, 50 for partly adequate capability, and 100
for fully adequate capability for the assessed task. Intermediate values require
analyst judgment. These anchors are provisional, not validated measurement scales.

Workload inputs measure combined roles, concurrent duties, transitions, public
exposure, and schedule compression: 0 means no assessed burden, 50 moderate
burden, 100 extreme burden. Do not mechanically copy PI exposure values: evaluate
their incremental effect on the team's workload. Correlation with existing PI
exposure remains a construct-validity limitation.

* Capacity C = equal-weight mean of seven capability inputs.
* Saturation S = equal-weight mean of five workload inputs.
* Effective capacity E = C × (1 − 0.35 × S / 100).
* Coverage gap = 100 − E.
* Modifier = 1.25 − 0.005 × E (bounded by construction to 0.75–1.25).
* Residual score = clip(PI × modifier, 0, 100).

The coverage gap describes this capacity construct; it is not a measured
percentage of unprotected time. Scores are indices, not incident probabilities.
There is no second support/access adjustment: PI already includes that factor.
The 35% penalty, equal weights, modifier bounds, and review thresholds are
uncalibrated analyst assumptions and require empirical and practitioner review.
An effective capacity of 50 is the neutral pivot; this is an assumption.

All twelve fields must be observed to apply a modifier. Missing files, unmatched
PI movements, blanks, or partial assessments produce unknown capacity/gap,
modifier 1, and a mandatory assessment state. Numeric neutrality is not evidence
of adequate protection. Non-numeric, infinite, or out-of-range values fail;
duplicate/blank trip IDs and capacity records absent from PI input fail.

Review is triggered by gap >=60, saturation >=70, or residual >=60. In COA output,
these impose a Security Lead Review floor. Unknown assessments impose a Validate
floor and Low confidence. Baseline PI COA escalation is never downgraded.
Baseline risk bands still describe PI; residual values remain separate columns.

## Operation

Copy `examples/protective_capacity_inputs_template.csv` to
`data/raw/protective_capacity_inputs.csv` and add one row per unique movement
`trip_id`, matching the PI input. Do not commit sensitive movement data.
Run the existing pipeline with `python -m src.main`, or run
`python -m src.residual_protective_risk` after PI output exists.

The pipeline explicitly passes the new processed residual CSV to COA generation.
Standalone COA invocation retains its baseline behavior unless supplied that file.
The dashboard adds Residual Risk between PI Posture and Decision Support. The
PDF includes movement-level PI, capacity, saturation, gap, residual and review
states. Both visibly identify the replacement and its experimental status.

## Validation and release boundary

Consumption by COA, the residual tab, and the residual PDF section recomputes
derived fields and rejects inconsistent or incompatible output. This checks
internal consistency, not whether input assessments are fresh or factually valid.
An explicitly supplied missing capacity path is an error; only an absent default
capacity file is treated as an unknown assessment. Trip IDs are read as text
through PI ingestion, residual output, COA, dashboard, and reports.
The decision audit includes the RPR-1 assessment and review floors and their
triggered-record counts. A supplied decision-rules path is retained in the audit.

Run `python -m unittest discover -s tests -v`. Tests cover hand calculations,
monotonicity and bounds, missingness, invalid values, join integrity, unchanged
PI, support-gap non-duplication, COA floors, file integration, pipeline order,
and Streamlit rendering. Pipeline-order testing mocks upstream data acquisition;
it is not a full real-data run. Local and CI outcomes are recorded in the PR.

A synthetic integration test additionally executes PI input loading and scoring,
residual scoring, CSV serialization, and COA generation with actual functions.
It verifies the leading-zero movement ID and baseline PI score survive the flow.

Before operational adoption, validate source freshness and assessment evidence,
run with authorized real trip data, perform independent construct review and
sensitivity analysis, and calibrate thresholds. No automatic travel clearance.
