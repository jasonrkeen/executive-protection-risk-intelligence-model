# Offline synthetic reproduction

Use Python 3.13.5 and the exact runtime/transitive pins in `requirements.txt`. Test tools are pinned in `requirements-dev.txt`, retaining pytest 8.4.2. These versions define the sample environment, not the original environment behind historical reports.

```bash
python -m pip install -r requirements.txt
python sample_run.py
```

The command reads [25 fictional component rows](../data/sample/README.md) and calls the original composite/severity, scenario, random-weight, single-simulation, and summary functions. Default settings come from the existing configuration: seed 42 and 1,000 simulations. Model formulas, weights, thresholds, caps, and Monte Carlo severity damping are unchanged.

Four CSVs (`synthetic_scores.csv`, `synthetic_scenarios.csv`, `synthetic_simulations.csv`, `synthetic_simulation_summary.csv`), an interpretation note, and `run_manifest.json` are written. The manifest records settings, input/source/dependency-file hashes, environment, and artifact hashes, excluding timestamps and absolute paths. Repeat runs are tested for byte equality within the recorded environment; cross-platform byte identity is not promised.

The default destination is a new `outputs/sample/` directory. Existing destinations are refused. Repeat with `python sample_run.py --output-dir outputs/sample/repeat`. Relative paths resolve from the repository root; in-repository destinations must be under `outputs/sample/`. New external directories are supported. Optional `--seed` and `--simulations` affect only the sample. Original configuration imports can create missing empty directories without rewriting saved artifacts.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q
```

The entire existing preflight, residual-risk, and intelligence-validation suite is retained. Added tests check hand-calculated weighted scores, scaling/missing-value behavior, bucket boundaries, scenario and simulation arithmetic, seeded positive weights summing to one, top-20 counts, repeat runs, output protection, and preservation hashes. External network connections are blocked during tests; local loopback is permitted for Windows Streamlit test infrastructure. Independent sample subprocesses block all socket connections.

[GitHub Actions](../.github/workflows/tests.yml) runs the complete suite and default sample on Windows and Ubuntu, checks dependencies and unchanged tracked files, and uploads artifacts. Consult [actual run results](https://github.com/jasonrkeen/executive-protection-risk-intelligence-model/actions/workflows/tests.yml) for execution evidence.

[Preservation hashes](../tests/preserved_files.json) cover the original model, dashboard, tracked inputs, published outputs, documentation/examples, and existing tests. Text hashes normalize checkout line endings; binary hashes preserve exact bytes. Do not update references merely to make tests pass. PDF/PNG Git attributes prevent Windows checkout line-ending conversion.

## Boundaries

This is a country-level software demonstration. It neither invokes nor satisfies trip-level preflight gates and does not produce residual-protection assessments, movement plans, or operational recommendations. Existing evidence requirements remain enforced by the unchanged code and regression tests. Scenario labels are inherited categories applied to fictional inputs.

No live ACLED or World Bank requests, personal data, real trips, or credentials are used. Full source-data reproduction, published-report regeneration, predictive validity, and independent empirical validation remain unestablished. Existing dashboard tests cover specific views, not every user interaction. Simulation shares describe weight/ranking sensitivity. Model logic, published results, historical artifacts, and releases remain unchanged.
