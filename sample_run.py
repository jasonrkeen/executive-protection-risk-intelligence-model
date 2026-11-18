"""Synthetic country-level demonstration, separate from trip-level assessment gates."""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd
from src import risk_scoring as scoring
from src import scenario_analysis as scenarios
from src import monte_carlo_risk_simulation as mc
from src.config import MONTE_CARLO_RANDOM_SEED, MONTE_CARLO_SIMULATIONS

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "data/sample/fictional_components.csv"


@dataclass(frozen=True)
class SampleSettings:
    seed: int = MONTE_CARLO_RANDOM_SEED
    simulations: int = MONTE_CARLO_SIMULATIONS

    def __post_init__(self) -> None:
        if self.seed < 0 or self.simulations < 2:
            raise ValueError("Seed must be nonnegative and simulations at least two")


def text_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n",b"\n")).hexdigest()


def destination_path(path: Path) -> Path:
    destination = (ROOT/path).resolve()
    if destination == ROOT or destination in ROOT.parents:
        raise ValueError("Output cannot be the repository or its parent")
    if ROOT in destination.parents and not destination.is_relative_to((ROOT/"outputs/sample").resolve()):
        raise ValueError("Repository output must be under outputs/sample")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {destination}")
    return destination


def calculate_sample(settings: SampleSettings) -> dict[str,pd.DataFrame]:
    inputs = pd.read_csv(INPUT)
    ranked = scoring.calculate_composite_score(inputs).sort_values(
        "executive_protection_risk_score",ascending=False).reset_index(drop=True)
    ranked["baseline_rank"] = ranked.index + 1
    rng = np.random.default_rng(settings.seed)
    draws = pd.concat([mc.run_single_simulation(ranked,mc.draw_random_weights(rng),i)
                       for i in range(1,settings.simulations+1)],ignore_index=True)
    return {"synthetic_scores.csv":ranked, "synthetic_scenarios.csv":scenarios.calculate_scenario_results(ranked),
            "synthetic_simulations.csv":draws, "synthetic_simulation_summary.csv":mc.build_country_summary(draws)}


def run_sample(output: Path = Path("outputs/sample"), settings: SampleSettings = SampleSettings()) -> dict[str,Any]:
    destination = destination_path(output)
    tables = calculate_sample(settings)
    destination.mkdir(parents=True,exist_ok=False)
    for name, frame in tables.items():
        frame.to_csv(destination/name,index=False,lineterminator="\n")
    (destination/"README.md").write_text(
        "# SYNTHETIC country-level software demonstration\n\n"
        "Fictional component inputs; no observed countries, people, trips, or locations.\n"
        "Scores and scenario labels are illustrative model outputs, not operational recommendations.\n"
        "Top-20 shares measure ranking sensitivity within this 25-row fixture, not event probabilities.\n"
        "Trip-level preflight and evidence requirements are unchanged and are not satisfied by this sample.\n",
        encoding="utf-8",newline="\n")
    sources = [ROOT/"sample_run.py",*sorted((ROOT/"src").glob("*.py"))]
    manifest = {
        "status":"SYNTHETIC_COUNTRY_DEMO_NOT_OPERATIONAL_OR_EMPIRICALLY_VALIDATED",
        "settings":asdict(settings), "input_sha256_lf":text_hash(INPUT),
        "source_sha256_lf":{p.relative_to(ROOT).as_posix():text_hash(p) for p in sources},
        "requirements_sha256_lf":text_hash(ROOT/"requirements.txt"),
        "environment":{"python":platform.python_version(),"system":platform.system(),
                       "packages":{name:version(name) for name in ("numpy","pandas","scikit-learn")}},
        "artifact_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.iterdir())},
        "limits":"Same-environment repeatability only; no live sources, trip assessment, predictive validation, or historical result reproduction.",
    }
    (destination/"run_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",
                                               encoding="utf-8",newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("outputs/sample"))
    parser.add_argument("--seed",type=int,default=MONTE_CARLO_RANDOM_SEED)
    parser.add_argument("--simulations",type=int,default=MONTE_CARLO_SIMULATIONS)
    args = parser.parse_args()
    try:
        run_sample(args.output_dir,SampleSettings(args.seed,args.simulations))
    except (ValueError,FileExistsError) as exc:
        parser.error(str(exc))
    print("SYNTHETIC sample complete; no live or trip-level assessment performed.")


if __name__ == "__main__":
    main()
