> This file mirrors `.github/copilot-instructions.md` and `CLAUDE.md`; keep all three in sync when any changes.

# AGENTS.md — executive-protection-risk-intelligence-model

## Purpose
Multi-layer OSINT executive protection risk model combining country risk, city-level ACLED analysis, geospatial mapping, airport/medical access proxies, and trip-level protective intelligence posture scoring.

## Tech stack
- Python; dependencies in `requirements.txt`
- Key libraries: `pandas`, `numpy`, `requests`, `matplotlib`, `scikit-learn`, `reportlab`, `python-dotenv`, `streamlit`, `plotly`

## Folder structure
- `.github/` (1 files)
- `data/` (1 files)
- `docs/` (1 files)
- `examples/` (1 files)
- `outputs/` (61 files)
- `src/` (32 files)
- `tests/` (2 files)
- `README.md`
- `app.py`
- `requirements.txt`

## Setup, run, test
Commands documented in README.md (referenced files exist):
```bash
python -m src.acled_api
python -m src.acled_forecast_update
python -m src.forward_risk_model
python -m src.acled_forecast_update --force-refresh
python -m streamlit run app.py
```
- Tests: 2 Python test file(s) under `tests/`; framework appears to be unittest. Add/update tests with any logic change.
- CI workflows exist in `.github/workflows/`; keep them passing.

## Conventions observed
- Functions use type hints; keep annotating new code.
- Config lives in: `src/config.py`; avoid hardcoding parameters elsewhere.
- Random seeds are set for reproducibility (Monte Carlo/simulation); keep seeded, deterministic runs.
- API keys are loaded from a local `.env` via python-dotenv; `.env` must stay uncommitted.
- Raw data (`data/raw/`) is gitignored; download/fetch it via the pipeline, do not commit it.
- Public data sources referenced: ACLED, World Bank.
- Write paths relative to the repo root (no absolute local paths).

## Output artifacts
- Generated outputs go to: `outputs/charts/`, `outputs/maps/`, `outputs/reports/`, `outputs/screenshots/`
- A PDF report is produced with `reportlab`; keep it in sync with model changes.
- Streamlit dashboard: `app.py`, `src/residual_risk_views.py` (run with `streamlit run <file>`).
- Charts are generated with matplotlib / plotly.

## Guardrails
- Never commit secrets, API keys, tokens, or `.env` files.
- Do not commit large raw datasets or binaries; keep data fetched or documented with its source.
- Keep analysis source-backed: cite data sources and assumptions; label scenario/forecast outputs as model estimates, not facts.
- Synthetic data must stay synthetic; never introduce real personal or sensitive records.
- Preserve reproducibility: no unseeded randomness, no hidden manual steps.
