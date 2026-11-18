# Fictional country-component fixture

All 25 rows are invented jurisdictions with synthetic identifiers. There are no real people, trips, locations, or source observations. No observation date applies.

For row index `i` from 0 through 24, the five component scores are `10 + ((i * k) % 81)`, with `k` equal to 7, 11, 17, 19, and 23 in the original model's component order. Event-count, fatality, spread, and raw momentum fields are explicitly zero. These are demonstration assumptions, not verified absence of events.

The existing composite and severity-uplift functions are used unchanged. Uplifts may still arise from component thresholds. Original scenario multipliers and Monte Carlo weight draws are retained, with seed 42 and 1,000 simulations by default. A top-20 indicator selects 20 of the 25 fictional entries per draw; its mean describes ranking sensitivity within this fixture, not an event probability.

This sample does not run trip-level or residual-protection assessments and provides no evidence that could satisfy their preflight requirements.
