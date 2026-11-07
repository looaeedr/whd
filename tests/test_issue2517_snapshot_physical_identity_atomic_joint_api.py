"""#2517: saved physical-sheet identity and live Joint state are Engine-owned."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_snapshot_projection as gui


class _Workspace:
    active_part = "head"

    def box_body_profile(self):
        return []

    def part_profiles_snapshot(self):
        return {}

    def workspace_snapshot(self):
        return {"existing_parts": ["box_body", "head", "tail"]}


def _host():
    live_joint = {
        "assembly_type": "INSERT",
        "assembly_joint_schema_version": 1,
        "assembly_joints": [],
    }
    return SimpleNamespace(
        workspace_controller=_Workspace(),
        _phase6_current_existing_parts=lambda: ("box_body", "head", "tail"),
        assembly_joint_state=live_joint,
        surface_features={},
        door_layout_features={},
        box_body_face_features={},
    )


def _base_snapshot():
    return {
        "model": "金庫型", "assembly_type": "INSERT_OVERLAY",
        "w": 800.0, "h": 1200.0, "d": 350.0, "t": 2.0, "fw": 25.0,
    }


@pytest.mark.parametrize(("part_key", "expected"), (
    ("box_body:left_side", True),
    ("box_body:right_side", True),
    ("box_body:back", True),
    ("box_body:divider:horizontal:1", False),
    ("box_body", False),
    ("door_c1_r1", False),
    ("head", False),
    ("", False),
    (None, False),
))
def test_snapshot_uses_existing_public_engine_physical_identity(part_key, expected):
    assert api.is_box_body_physical_piece_key(part_key) is expected
    assert ae_engine.is_box_body_physical_piece_key is api.is_box_body_physical_piece_key
    source = inspect.getsource(gui._snapshot_base_state)
    assert "manufacturing_api.is_box_body_physical_piece_key(workspace_active)" in source
    assert "workspace_active.startswith(" not in source


def test_engine_joint_projection_is_detached_and_workspace_defer_preserves_live_state():
    host = _host()
    before = deepcopy(host.assembly_joint_state)
    live = host.assembly_joint_state
    snapshot = _base_snapshot()
    profiles, candidate = gui._snapshot_workspace_state(
        host, snapshot, defer_joint_commit=True,
    )
    expected = api.project_operator_assembly_joint_snapshot(
        before,
        existing_parts=("box_body", "head", "tail"),
        assembly_type=snapshot["assembly_type"],
    )
    assert profiles == {}
    assert candidate == expected
    assert snapshot["assembly_joints"] == candidate["assembly_joints"]
    assert snapshot["assembly_joint_schema_version"] == candidate["assembly_joint_schema_version"]
    assert host.assembly_joint_state is live
    assert host.assembly_joint_state == before


def test_full_snapshot_failure_does_not_commit_joint_state(monkeypatch):
    host = _host()
    original_joint = host.assembly_joint_state
    before = deepcopy(original_joint)
    monkeypatch.setattr(gui, "_snapshot_base_state", lambda _host: _base_snapshot())

    def fail_indicator_projection(_host, _snapshot):
        raise ValueError("invalid enabled indicator dimensions")

    monkeypatch.setattr(gui, "_snapshot_part_dimensions", fail_indicator_projection)
    with pytest.raises(ValueError, match="invalid enabled indicator dimensions"):
        gui._make_original_fold_designer_snapshot(host)
    assert host.assembly_joint_state is original_joint
    assert host.assembly_joint_state == before


def test_full_snapshot_success_commits_same_engine_joint_projection(monkeypatch):
    host = _host()
    before = deepcopy(host.assembly_joint_state)
    monkeypatch.setattr(gui, "_snapshot_base_state", lambda _host: _base_snapshot())

    def finish_dimensions(_host, snapshot):
        snapshot["part_dimensions"] = {"head": {"width": 400.0, "height": 300.0}}

    monkeypatch.setattr(gui, "_snapshot_part_dimensions", finish_dimensions)
    saved = gui._make_original_fold_designer_snapshot(host)
    expected = api.project_operator_assembly_joint_snapshot(
        before,
        existing_parts=("box_body", "head", "tail"),
        assembly_type=saved["assembly_type"],
    )
    assert saved["assembly_joints"] == expected["assembly_joints"]
    assert saved["assembly_joint_schema_version"] == expected["assembly_joint_schema_version"]
    assert host.assembly_joint_state == expected
    assert host.assembly_joint_state is not before
    assert saved["part_dimensions"]["head"]["width"] == 400.0


def test_standalone_workspace_projection_keeps_legacy_joint_commit():
    host = _host()
    before = host.assembly_joint_state
    snapshot = _base_snapshot()
    assert gui._snapshot_workspace_state(host, snapshot) == {}
    assert host.assembly_joint_state is not before
    assert host.assembly_joint_state["assembly_joints"] == snapshot["assembly_joints"]
