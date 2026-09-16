import json
from pathlib import Path

import pytest

from tools.test_shard_execution import (
    ExecutionError,
    build_pytest_command,
    load_xdist_policy,
    resolve_xdist_workers,
)
from tools.xdist_state_isolation import (
    XDIST_CANDIDATE,
    XDIST_SAFE,
    SERIAL_ONLY,
    audit_source_text,
    classify_scope,
    worker_count_for,
    worker_local_root,
)


PROOF_HEAD = "45811716bb03b95927a33451bf7f1c8d0769c407"
PROOF_RUN = 35124104891
PROOF_ARTIFACT = 10458605621
PROOF_DIGEST = "21340f1f0d39a97ab3c40cf756c624a7f5f3b00c22430f90a35d4f9a514d3ada"


def _proof(**overrides):
    proof = {
        "repeat_runs": 2,
        "stable_nodes": True,
        "stable_results": True,
        "protected_invariants": True,
        "cross_worker_leakage": False,
    }
    proof.update(overrides)
    return proof


def _execution_config(*, with_safe_dxf=True):
    payload = {
        "schema": "WHD_TEST_EXECUTION_CONFIG_V1",
        "ci_concurrency_budget": 4,
    }
    if with_safe_dxf:
        payload["xdist"] = {
            "default_workers": 1,
            "distribution": "load",
            "safe_shards": {
                "dxf:s00": {
                    "workers": 2,
                    "proof_run_id": PROOF_RUN,
                    "proof_head_sha": PROOF_HEAD,
                    "proof_artifact_id": PROOF_ARTIFACT,
                    "proof_artifact_sha256": PROOF_DIGEST,
                }
            },
        }
    return payload


def test_static_audit_flags_direct_config_ini_write():
    risks = audit_source_text('open("config.ini", "w").write("x")')
    assert "CONFIG_INI_WRITE" in risks


def test_static_audit_flags_dxf_baseline_write():
    risks = audit_source_text('Path("基準檔/封頭.dxf").write_bytes(payload)')
    assert "DXF_WRITE" in risks


def test_static_audit_flags_shared_fixed_path():
    risks = audit_source_text('shared = Path("/tmp/whd-shared")\nshared.mkdir(exist_ok=True)')
    assert "FIXED_PATH" in risks


def test_static_audit_flags_process_environment_mutation_without_fixture_cleanup():
    risks = audit_source_text('import os\nos.environ["WHD_MODE"] = "test"')
    assert "ENV_MUTATION" in risks


def test_static_audit_does_not_treat_monkeypatch_setenv_as_unscoped_env_mutation():
    risks = audit_source_text('def test_x(monkeypatch):\n    monkeypatch.setenv("WHD_MODE", "test")')
    assert "ENV_MUTATION" not in risks


def test_static_audit_flags_tk_root_and_global_mutation():
    risks = audit_source_text('import tkinter as tk\nCACHE = {}\ndef test_x():\n    global CACHE\n    CACHE["x"] = tk.Tk()')
    assert "TK_ROOT" in risks
    assert "GLOBAL_MUTATION" in risks


def test_no_static_risk_is_only_candidate_without_repeat_proof():
    classification = classify_scope(
        lane="unit",
        risk_flags=set(),
        proof=_proof(repeat_runs=0),
    )
    assert classification == XDIST_CANDIDATE
    assert worker_count_for(classification, requested=2) == 1


def test_repeat_proof_promotes_only_clean_non_gui_scope_to_xdist_safe():
    classification = classify_scope(
        lane="unit",
        risk_flags=set(),
        proof=_proof(),
    )
    assert classification == XDIST_SAFE
    assert worker_count_for(classification, requested=2) == 2


@pytest.mark.parametrize(
    "risk",
    [
        "CONFIG_INI_WRITE",
        "DXF_WRITE",
        "FIXED_PATH",
        "GLOBAL_MUTATION",
        "ENV_MUTATION",
        "TK_ROOT",
    ],
)
def test_any_shared_mutable_risk_forces_serial_only(risk):
    classification = classify_scope(
        lane="integration",
        risk_flags={risk},
        proof=_proof(),
    )
    assert classification == SERIAL_ONLY
    assert worker_count_for(classification, requested=2) == 1


def test_gui_or_xvfb_scope_stays_serial_even_with_clean_repeat_proof():
    classification = classify_scope(
        lane="xvfb_ui",
        risk_flags=set(),
        proof=_proof(),
        gui=True,
    )
    assert classification == SERIAL_ONLY


def test_unstable_repeat_or_leakage_never_becomes_safe():
    unstable = classify_scope(
        lane="geometry",
        risk_flags=set(),
        proof=_proof(stable_results=False),
    )
    leaking = classify_scope(
        lane="geometry",
        risk_flags=set(),
        proof=_proof(cross_worker_leakage=True),
    )
    assert unstable == XDIST_CANDIDATE
    assert leaking == SERIAL_ONLY


def test_worker_count_rejects_auto_and_caps_conservative_workers():
    with pytest.raises(ValueError, match="auto"):
        worker_count_for(XDIST_SAFE, requested="auto")
    assert worker_count_for(XDIST_SAFE, requested=99) == 2


def test_worker_local_roots_are_unique_and_cannot_escape_base(tmp_path):
    gw0 = worker_local_root(tmp_path, "gw0")
    gw1 = worker_local_root(tmp_path, "gw1")
    assert gw0 == tmp_path / "gw0"
    assert gw1 == tmp_path / "gw1"
    assert gw0 != gw1
    with pytest.raises(ValueError):
        worker_local_root(tmp_path, "../escape")
    assert Path(gw0).is_relative_to(tmp_path)


def test_legacy_execution_config_defaults_every_shard_to_serial(tmp_path):
    path = tmp_path / "execution.json"
    path.write_text(json.dumps(_execution_config(with_safe_dxf=False)))
    policy = load_xdist_policy(path)
    assert policy["default_workers"] == 1
    assert policy["safe_shards"] == {}
    assert resolve_xdist_workers(policy, lane="dxf", shard_id="s00") == 1


def test_exact_proven_dxf_shard_resolves_two_workers_and_other_scopes_stay_serial(tmp_path):
    path = tmp_path / "execution.json"
    path.write_text(json.dumps(_execution_config()))
    policy = load_xdist_policy(path)
    assert resolve_xdist_workers(policy, lane="dxf", shard_id="s00") == 2
    assert resolve_xdist_workers(policy, lane="geometry", shard_id="s00") == 1
    assert resolve_xdist_workers(policy, lane="dxf", shard_id="s99") == 1
    assert policy["safe_shards"]["dxf:s00"]["proof_run_id"] == PROOF_RUN
    assert policy["safe_shards"]["dxf:s00"]["proof_head_sha"] == PROOF_HEAD


def test_xdist_policy_requires_proof_provenance_and_rejects_auto_or_more_than_two(tmp_path):
    for broken in (
        {"workers": 2},
        {
            "workers": "auto",
            "proof_run_id": PROOF_RUN,
            "proof_head_sha": PROOF_HEAD,
            "proof_artifact_id": PROOF_ARTIFACT,
            "proof_artifact_sha256": PROOF_DIGEST,
        },
        {
            "workers": 3,
            "proof_run_id": PROOF_RUN,
            "proof_head_sha": PROOF_HEAD,
            "proof_artifact_id": PROOF_ARTIFACT,
            "proof_artifact_sha256": PROOF_DIGEST,
        },
    ):
        payload = _execution_config()
        payload["xdist"]["safe_shards"]["dxf:s00"] = broken
        path = tmp_path / f"broken-{len(str(broken))}.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(ExecutionError):
            load_xdist_policy(path)


def test_xdist_policy_rejects_xvfb_safe_scope_even_with_proof(tmp_path):
    payload = _execution_config()
    payload["xdist"]["safe_shards"]["xvfb_ui:s00"] = payload["xdist"]["safe_shards"].pop("dxf:s00")
    path = tmp_path / "xvfb.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ExecutionError, match="XVFB"):
        load_xdist_policy(path)


def test_pytest_command_adds_explicit_xdist_args_only_for_two_workers(tmp_path):
    base = build_pytest_command(
        nodes=["tests/test_x.py::test_a"],
        junit_xml=tmp_path / "result.xml",
        basetemp=tmp_path / "tmp",
        xdist_workers=1,
        xdist_distribution="load",
    )
    parallel = build_pytest_command(
        nodes=["tests/test_x.py::test_a"],
        junit_xml=tmp_path / "parallel.xml",
        basetemp=tmp_path / "parallel-tmp",
        xdist_workers=2,
        xdist_distribution="load",
    )
    assert "-n" not in base
    assert "--dist=load" not in base
    assert parallel[parallel.index("-n") + 1] == "2"
    assert "--dist=load" in parallel


def test_repository_execution_config_enables_only_proven_dxf_s00():
    policy = load_xdist_policy(Path("config/ci_test_execution.json"))
    assert set(policy["safe_shards"]) == {"dxf:s00"}
    entry = policy["safe_shards"]["dxf:s00"]
    assert entry == {
        "workers": 2,
        "proof_run_id": PROOF_RUN,
        "proof_head_sha": PROOF_HEAD,
        "proof_artifact_id": PROOF_ARTIFACT,
        "proof_artifact_sha256": PROOF_DIGEST,
    }
