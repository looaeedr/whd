from pathlib import Path

import pytest

from tools.xdist_state_isolation import (
    XDIST_CANDIDATE,
    XDIST_SAFE,
    SERIAL_ONLY,
    audit_source_text,
    classify_scope,
    worker_count_for,
    worker_local_root,
)


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
