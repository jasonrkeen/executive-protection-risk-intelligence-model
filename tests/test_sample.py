import hashlib
import json
import os
import subprocess
import sys
import numpy as np
import pandas as pd
import pytest
import sample_run as sample
from src.config import RISK_WEIGHTS


def test_hand_calculated_weighted_score_and_preserved_input():
    data = pd.DataFrame([dict(zip(RISK_WEIGHTS,[10,20,30,40,50]))])
    before = data.copy(deep=True)
    result = sample.scoring.calculate_weighted_baseline_score(data)
    assert result.weighted_ep_risk_score.iloc[0] == 25
    pd.testing.assert_frame_equal(data,before)


def test_scaling_direction_missing_values_and_constants():
    values = pd.Series([10,20,30,np.nan])
    np.testing.assert_allclose(sample.scoring.minmax_score(values),[0,50,100,50])
    np.testing.assert_allclose(sample.scoring.minmax_score(values,False),[100,50,0,50])
    assert (sample.scoring.minmax_score(pd.Series([np.nan,np.inf])) == 50).all()
    assert (sample.scoring.minmax_score(pd.Series([3,3])) == 50).all()


@pytest.mark.parametrize("score,label",[(0,"Low"),(25,"Moderate"),(50,"Elevated"),(70,"High"),(85,"Severe"),(100,"Severe"),(101,"Unclassified")])
def test_bucket_boundaries(score,label):
    assert sample.scoring.assign_risk_bucket(score) == label


def test_scenarios_and_simulation_arithmetic():
    tables = sample.calculate_sample(sample.SampleSettings(simulations=3))
    ranked = tables["synthetic_scores.csv"]
    scenarios = tables["synthetic_scenarios.csv"]
    np.testing.assert_allclose(scenarios.scenario_ep_risk_score,
        [round(min(float(score)*float(multiplier),100),2) for score,multiplier in
         zip(scenarios.baseline_ep_risk_score,scenarios.scenario_multiplier)])
    single = sample.mc.run_single_simulation(ranked,RISK_WEIGHTS,1)
    expected = (single[sample.mc.COMPONENT_COLUMNS].mul(pd.Series(RISK_WEIGHTS)).sum(axis=1)
                +single.severity_uplift_total*.85).clip(0,100).round(2)
    np.testing.assert_allclose(single.simulated_ep_risk_score,expected)
    assert ranked.severity_uplift_total.between(0,25).all()
    assert ranked.executive_protection_risk_score.between(0,100).all()
    draws = tables["synthetic_simulations.csv"]
    assert draws.groupby("simulation_id").in_simulated_top20.sum().tolist() == [20,20,20]
    assert tables["synthetic_simulation_summary.csv"].top20_probability.between(0,1).all()


def test_random_weights_seed_and_normalization():
    a=sample.mc.draw_random_weights(np.random.default_rng(42))
    b=sample.mc.draw_random_weights(np.random.default_rng(42))
    c=sample.mc.draw_random_weights(np.random.default_rng(43))
    assert a == b and a != c
    assert sum(a.values()) == pytest.approx(1)
    assert all(x>0 for x in a.values())


def test_repeatability_and_manifest(tmp_path):
    a=sample.run_sample(tmp_path/"a",sample.SampleSettings(simulations=5))
    b=sample.run_sample(tmp_path/"b",sample.SampleSettings(simulations=5))
    assert a == b
    for name,expected in a["artifact_sha256"].items():
        assert hashlib.sha256((tmp_path/"a"/name).read_bytes()).hexdigest() == expected
        assert (tmp_path/"a"/name).read_bytes() == (tmp_path/"b"/name).read_bytes()


def test_independent_offline_processes(tmp_path):
    (tmp_path/"sitecustomize.py").write_text(
        "import socket\ndef blocked(*a, **k):\n raise RuntimeError('Network forbidden')\n"
        "socket.socket.connect=blocked\nsocket.socket.connect_ex=blocked\nsocket.create_connection=blocked\n")
    for name in ["a","b"]:
        result=subprocess.run([sys.executable,str(sample.ROOT/"sample_run.py"),"--simulations","5",
            "--output-dir",str(tmp_path/name)],cwd=tmp_path,env=dict(os.environ,PYTHONPATH=str(tmp_path)),
            text=True,capture_output=True,check=True)
        assert "SYNTHETIC sample complete" in result.stdout
    assert (tmp_path/"a/run_manifest.json").read_bytes() == (tmp_path/"b/run_manifest.json").read_bytes()


@pytest.mark.parametrize("path",[sample.ROOT,sample.ROOT.parent,sample.ROOT/"outputs/reports/new",sample.ROOT/"data/processed/new"])
def test_protected_paths(path):
    with pytest.raises(ValueError): sample.destination_path(path)


def test_existing_output_preserved(tmp_path):
    (tmp_path/"sentinel").write_text("keep")
    with pytest.raises(FileExistsError): sample.run_sample(tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path/"sentinel"]
    assert (tmp_path/"sentinel").read_text() == "keep"


@pytest.mark.parametrize("kwargs",[{"seed":-1},{"simulations":0},{"simulations":1}])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError): sample.SampleSettings(**kwargs)


def test_preserved_model_tests_and_published_artifacts():
    record=json.loads((sample.ROOT/"tests/preserved_files.json").read_text())
    for name,expected in record["files"].items():
        content=(sample.ROOT/name).read_bytes()
        if expected["text_lf"]: content=content.replace(b"\r\n",b"\n")
        assert hashlib.sha256(content).hexdigest() == expected["sha256"], name
