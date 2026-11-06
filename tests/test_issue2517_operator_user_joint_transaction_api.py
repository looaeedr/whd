# -*- coding: utf-8 -*-
"""#2517 atomic USER_ADDED AssemblyJoint transactions through the public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import fold_designer_bridge as gui
from ae_engine import manufacturing_api as api
from ae_engine import assembly_joint as owner


def _source():
    return {"existing_parts": ["box_body", "head", "tail"],
            "assembly_type": "INSERT_OVERLAY"}


def _add_kwargs():
    return {"subject_part": "head", "target_part": "box_body",
            "relation": "WRAP", "subject_region": "rear_edge",
            "target_region": "rear_mating",
            "solver_constraints": {"topology_levels": 1}}


def test_gui_routes_add_delete_to_identical_public_engine_owner():
    assert api.commit_operator_user_assembly_joint is owner.add_user_assembly_joint
    assert api.remove_operator_user_assembly_joint is owner.delete_user_assembly_joint
    add = inspect.getsource(gui._phase6_add_user_joint)
    delete = inspect.getsource(gui._phase6_delete_user_joint)
    assert "manufacturing_api.commit_operator_user_assembly_joint(" in add
    assert "manufacturing_api.remove_operator_user_assembly_joint(" in delete
    assert "AssemblyJoint(" not in add and "AssemblyJoint.from_dict" not in delete
    assert "uuid" not in add


def test_headless_gui_add_matches_exact_engine_result_and_source_is_detached(monkeypatch):
    app = SimpleNamespace(_phase6_input_snapshot=_source())
    before = deepcopy(app._phase6_input_snapshot)
    real = api.commit_operator_user_assembly_joint
    results = []
    def spy(*args, **kwargs):
        result = real(*args, **kwargs)
        results.append(result)
        return result
    monkeypatch.setattr(api, "commit_operator_user_assembly_joint", spy)
    row = gui._phase6_add_user_joint(app, **_add_kwargs())
    staged, engine_row = results.pop()
    assert row == engine_row
    assert app._phase6_input_snapshot["assembly_joints"] == staged["assembly_joints"]
    assert row["source"] == "USER_ADDED" and row["relation"] == "WRAP"
    assert row["solver_constraints"] == {"topology_levels": 1}
    assert before == _source()
    detached_source = deepcopy(_source())
    next_snapshot, _ = real(detached_source, **_add_kwargs())
    assert detached_source == before
    assert next_snapshot["assembly_joints"][-1]["source"] == "USER_ADDED"


@pytest.mark.parametrize("change", [
    {"relation": "UNKNOWN"},
    {"subject_part": ""},
    {"subject_part": "head", "target_part": "head"},
    {"solver_constraints": 42},
])
def test_rejected_gui_add_never_writes_even_a_legacy_migration(change):
    app = SimpleNamespace(_phase6_input_snapshot=_source())
    before = deepcopy(app._phase6_input_snapshot)
    proposed = {**_add_kwargs(), **change}
    with pytest.raises((ValueError, TypeError)):
        gui._phase6_add_user_joint(app, **proposed)
    assert app._phase6_input_snapshot == before
    with pytest.raises((ValueError, TypeError)):
        api.commit_operator_user_assembly_joint(before, **proposed)
    assert before == _source()


def test_duplicate_and_protected_joint_delete_leave_original_unchanged():
    app = SimpleNamespace(_phase6_input_snapshot=_source())
    row = gui._phase6_add_user_joint(app, **_add_kwargs())
    prior = deepcopy(app._phase6_input_snapshot)
    with pytest.raises(ValueError, match="相同 AssemblyJoint"):
        gui._phase6_add_user_joint(app, **_add_kwargs())
    assert app._phase6_input_snapshot == prior
    default = next(j for j in prior["assembly_joints"] if j["source"] != "USER_ADDED")
    with pytest.raises(ValueError, match="USER_ADDED"):
        gui._phase6_delete_user_joint(app, default["joint_id"])
    assert app._phase6_input_snapshot == prior
    assert gui._phase6_delete_user_joint(app, "not-present") is False
    assert app._phase6_input_snapshot == prior
    assert gui._phase6_delete_user_joint(app, row["joint_id"]) is True
    assert all(j["joint_id"] != row["joint_id"] for j in app._phase6_input_snapshot["assembly_joints"])


def test_gui_delete_matches_engine_and_serialized_joint_survives_migration(monkeypatch):
    app = SimpleNamespace(_phase6_input_snapshot=_source())
    row = gui._phase6_add_user_joint(app, **_add_kwargs())
    roundtrip = json.loads(json.dumps(app._phase6_input_snapshot))
    assert owner.migrate_legacy_snapshot_joints(roundtrip)["assembly_joints"] == roundtrip["assembly_joints"]
    real = api.remove_operator_user_assembly_joint
    received = []
    def spy(*args, **kwargs):
        result = real(*args, **kwargs)
        received.append(result)
        return result
    monkeypatch.setattr(api, "remove_operator_user_assembly_joint", spy)
    assert gui._phase6_delete_user_joint(app, row["joint_id"])
    expected_snapshot, changed = received.pop()
    assert changed and app._phase6_input_snapshot["assembly_joints"] == expected_snapshot["assembly_joints"]
    assert len(roundtrip["assembly_joints"]) == len(app._phase6_input_snapshot["assembly_joints"]) + 1
