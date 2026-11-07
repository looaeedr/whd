"""#2517: physical Fold Designer saved presence/selection is Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.workspace_state import (
    OperatorWorkspaceSnapshotPresence,
    project_operator_fold_designer_workspace_presence as owner,
)
from gui_modules.application import fold_designer_snapshot_projection as gui


def _source():
    return {
        "present": {
            "custom:7", "box_body", "tail", "indicator_door",
            "head", "door", "box_body:left_side",
        },
        "workspace": [
            "custom:7", "tail", "box_body", "box_body:left_side",
            "head", "door", "custom:orphan",
        ],
    }


def test_exact_public_owner_and_root_identity():
    assert api.project_operator_fold_designer_workspace_presence is owner
    assert ae_engine.project_operator_fold_designer_workspace_presence is owner
    assert ae_engine.OperatorWorkspaceSnapshotPresence is OperatorWorkspaceSnapshotPresence


def test_engine_orders_standard_then_committed_dynamic_only_without_mutation():
    src = _source()
    before = deepcopy(src)
    result = api.project_operator_fold_designer_workspace_presence(
        src["present"], src["workspace"], "custom:7",
    )
    assert result == OperatorWorkspaceSnapshotPresence(
        existing_parts=(
            "box_body", "head", "tail", "door", "indicator_door",
            "custom:7", "box_body:left_side",
        ),
        active_part="custom:7",
    )
    assert src == before
    with pytest.raises(Exception):
        result.active_part = "head"


@pytest.mark.parametrize(("selected", "expected"), (
    ("tail", "tail"),
    ("not-in-saved-physical-parts", "box_body"),
    (None, "box_body"),
    ("", "box_body"),
))
def test_engine_repairs_absent_or_invalid_saved_active_part(selected, expected):
    result = api.project_operator_fold_designer_workspace_presence(
        ["tail", "head", "box_body"],
        ["box_body", "head", "tail"],
        selected,
    )
    assert result.existing_parts == ("box_body", "head", "tail")
    assert result.active_part == expected


@pytest.mark.parametrize(("present", "workspace"), (
    ("head", ["box_body", "head"]),
    (["box_body"], "head"),
    (None, ["box_body"]),
    (["box_body"], None),
    ([True, "box_body"], ["box_body"]),
    (["box_body", ""], ["box_body"]),
    (["box_body"], ["box_body", 12]),
))
def test_malformed_saved_physical_source_rejected_without_write(present, workspace):
    before = deepcopy((present, workspace))
    with pytest.raises(ValueError):
        api.project_operator_fold_designer_workspace_presence(
            present, workspace, "head",
        )
    assert (present, workspace) == before


def test_actual_fold_designer_snapshot_uses_one_public_engine_presence_candidate(monkeypatch):
    source = _source()
    source_before = deepcopy(source)
    observed = []
    def spy(present, workspace, selected):
        observed.append((set(present), tuple(workspace), selected))
        return owner(present, workspace, selected)

    monkeypatch.setattr(api, "project_operator_fold_designer_workspace_presence", spy)
    monkeypatch.setattr(
        api, "project_operator_assembly_joint_snapshot",
        lambda *_args, **_kwargs: {
            "assembly_joint_schema_version": 2,
            "assembly_joints": [],
        },
    )
    monkeypatch.setattr(
        gui, "_snapshot_part_features",
        lambda _host, snapshot: snapshot.update(part_features={}),
    )
    workspace = SimpleNamespace(
        box_body_profile=lambda: None,
        part_profiles_snapshot=lambda: {},
        workspace_snapshot=lambda: {"existing_parts": list(source["workspace"])},
        active_part="disappeared",
    )
    host = SimpleNamespace(
        workspace_controller=workspace,
        _phase6_current_existing_parts=lambda: set(source["present"]),
        assembly_joint_state=None,
        box_body_face_features={},
    )
    snapshot = {"assembly_type": "OVERLAY"}
    committed_profiles, joint_state = gui._snapshot_workspace_state(
        host, snapshot, defer_joint_commit=True,
    )
    assert committed_profiles == {}
    assert joint_state["assembly_joints"] == []
    assert observed == [(source["present"], tuple(source["workspace"]), "disappeared")]
    assert snapshot["existing_parts"] == [
        "box_body", "head", "tail", "door", "indicator_door",
        "custom:7", "box_body:left_side",
    ]
    assert snapshot["active_part"] == "box_body"
    assert source == source_before


def test_real_p6fold_save_reload_keeps_engine_selected_physical_identity(tmp_path):
    import phase6_project_file as project

    physical = api.project_operator_fold_designer_workspace_presence(
        {"door", "tail", "box_body", "head"},
        ["tail", "door", "box_body", "head"],
        "tail",
    )
    snapshot = {
        "model": "金庫型", "w": 800.0, "h": 1000.0,
        "d": 350.0, "t": 2.0, "fw": 25.0,
        "existing_parts": list(physical.existing_parts),
        "active_part": physical.active_part,
        "part_features": {},
    }
    before = deepcopy(snapshot)
    target = project.write_project(
        tmp_path / "workspace-presence.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": snapshot},
    )
    restored = project.read_project(target)["snapshot"]
    assert restored["existing_parts"] == list(physical.existing_parts)
    assert restored["active_part"] == "tail"
    assert snapshot == before


def test_gui_has_no_private_physical_part_presence_ordering_or_active_repair():
    source = inspect.getsource(gui._snapshot_workspace_state)
    assert "manufacturing_api.project_operator_fold_designer_workspace_presence(" in source
    assert '("box_body", "head", "tail", "door"' not in source
    assert "active if active in ordered" not in source
