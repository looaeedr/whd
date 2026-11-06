# -*- coding: utf-8 -*-
"""#2517 main GUI AssemblyJoint state source commits through public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import gui
from ae_engine import manufacturing_api as api
from ae_engine import assembly_intent_transactions as owner
from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource,
    edge_relation_for_part, migrate_legacy_snapshot_joints,
    sync_snapshot_intent_joints,
)


def _legacy_commit_reference(before, stable, parts):
    """Prior GUI semantics, used solely as an independent regression oracle."""
    state = dict(before or {})
    state.setdefault("existing_parts", list(parts))
    state["existing_parts"] = list(parts)
    if not state.get("assembly_joint_schema_version"):
        state["assembly_type"] = stable
        state = migrate_legacy_snapshot_joints(state)
    return sync_snapshot_intent_joints(state, stable)


def _host(source):
    selected = []
    host = SimpleNamespace(
        assembly_joint_state=deepcopy(source),
        box_assembly_type_var=SimpleNamespace(
            get=lambda: "",
            set=lambda label: selected.append(label),
        ),
        _phase6_current_existing_parts=lambda: ("box_body", "head", "tail"),
        refresh_corner_type_panel=lambda: None,
    )
    return host, selected


def test_gui_uses_one_existing_engine_owner_no_private_joint_sync_in_event():
    assert api.commit_operator_box_assembly_joint_state is owner.commit_box_assembly_joint_state
    method = inspect.getsource(gui.Phase6ApplicationHost._set_box_assembly_type)
    assert "manufacturing_api.commit_operator_box_assembly_joint_state(" in method
    assert "migrate_legacy_snapshot_joints(" not in method
    assert "sync_snapshot_intent_joints(" not in method


@pytest.mark.parametrize("stable", ("INSERT", "OVERLAY", "INSERT_OVERLAY", "WRAP_OVERLAY"))
@pytest.mark.parametrize("schema", (None, 2))
def test_public_commit_exact_previous_gui_joint_state_and_save_reload(stable, schema):
    state = {"assembly_type": "INSERT", "existing_parts": ["head", "box_body", "tail"]}
    if schema is not None:
        state = migrate_legacy_snapshot_joints(state)
    original = deepcopy(state)
    parts = ("box_body", "head", "tail")
    result = api.commit_operator_box_assembly_joint_state(state, stable, available_parts=parts)
    assert result == _legacy_commit_reference(state, stable, parts)
    assert state == original
    assert result["assembly_joint_schema_version"] == 2
    for cap in ("head", "tail"):
        bottom = edge_relation_for_part(result, cap, "BOTTOM")
        assert bottom.value == ("WRAP" if stable == "WRAP_OVERLAY" else "INSERT")
    encoded = json.loads(json.dumps(result))
    assert migrate_legacy_snapshot_joints(encoded) == encoded


def test_main_gui_event_commits_only_engine_result(monkeypatch):
    source = {"assembly_type": "INSERT_OVERLAY"}
    host, selected = _host(source)
    calls = []
    real = api.commit_operator_box_assembly_joint_state
    def capture(*args, **kwargs):
        result = real(*args, **kwargs)
        calls.append((deepcopy(args), deepcopy(kwargs), deepcopy(result)))
        return result
    monkeypatch.setattr(api, "commit_operator_box_assembly_joint_state", capture)
    selected_type = gui.Phase6ApplicationHost._set_box_assembly_type(
        host, "OVERLAY", recalculate=False, notify_designer=False,
    )
    args, kwargs, result = calls.pop()
    assert args[0] == source and args[1] == "OVERLAY"
    assert kwargs["available_parts"] == ("box_body", "head", "tail")
    assert host.assembly_joint_state == result
    assert selected_type.value == "OVERLAY"
    assert selected == ["貼外"]


def test_user_joint_survives_main_gui_preset_and_invalid_intent_writes_nothing():
    user = AssemblyJoint(
        joint_id="user:preserved", subject_part="head", target_part="box_body",
        subject_region="rear_edge", target_region="rear_mating",
        relation=AssemblyJointRelation.WRAP, source=AssemblyJointSource.USER_ADDED,
    ).to_dict()
    source = migrate_legacy_snapshot_joints({
        "assembly_type": "INSERT", "existing_parts": ["box_body", "head", "tail"],
        "assembly_joints": [user],
    })
    before = deepcopy(source)
    result = api.commit_operator_box_assembly_joint_state(
        source, "OVERLAY", available_parts=("box_body", "head", "tail"),
    )
    assert any(j["joint_id"] == user["joint_id"] and j == user for j in result["assembly_joints"])
    assert source == before
    host, selected = _host(source)
    with pytest.raises(ValueError):
        gui.Phase6ApplicationHost._set_box_assembly_type(
            host, "INVALID", recalculate=False, notify_designer=False,
        )
    assert host.assembly_joint_state == source and selected == []
    for value in ("INVALID", "WRAP", ""):
        with pytest.raises(ValueError):
            api.commit_operator_box_assembly_joint_state(
                source, value, available_parts=("box_body", "head", "tail"),
            )
        assert source == before
