"""#2517 main-window Joint replay and physical part navigation use public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
from gui_modules.application import lifecycle as gui


def _receiving_navigation_source(active, *, revision=1, fingerprint="prior"):
    return {
        "origin": "fold_designer",
        "revision": revision,
        "fingerprint": fingerprint,
        "model": "受電箱",
        "active_mode": "set_bay",
        "active_part": active,
        "workspace": {
            "active_part": active,
            "existing_parts": (
                "box_body:back", "box_body:left_side",
                "box_body:divider:horizontal:1",
            ),
            "part_profiles": {},
        },
    }


@pytest.mark.parametrize(("selected", "expected_sheet"), [
    ("box_body:left_side", "box_body:left_side"),
    ("box_body:divider:horizontal:1", "untouched"),
])
def test_real_gui_navigation_uses_public_engine_identity_without_selecting_divider(
    monkeypatch, selected, expected_sheet,
):
    previous = _receiving_navigation_source("box_body:back")
    current = _receiving_navigation_source(
        selected, revision=2, fingerprint="new",
    )
    source_before = deepcopy((previous, current))
    assert api.operator_receiving_navigation_only_sync_change(previous, current)
    selected_sheet = ["untouched"]
    active = []
    commits = []
    checked = []
    real_identity = api.is_box_body_physical_piece_key

    def delegated_identity(part):
        checked.append(part)
        return real_identity(part)

    monkeypatch.setattr(api, "is_box_body_physical_piece_key", delegated_identity)
    host = SimpleNamespace(
        _fold_designer_live_sync_guard=False,
        _phase6_last_fold_designer_revision=1,
        _phase6_last_fold_designer_fingerprint="prior",
        _phase6_last_fold_designer_live_payload=deepcopy(previous),
        workspace_controller=SimpleNamespace(set_active_part=active.append),
        box_body_piece_2d_selected_var=SimpleNamespace(
            set=lambda key: selected_sheet.__setitem__(0, key)
        ),
        _sync_fold_designer_manual_corner_context=lambda _part: None,
        _compose_phase6_project_snapshot_from_main_gui=lambda: {"committed": True},
        project_controller=SimpleNamespace(capture_committed=commits.append),
    )
    assert gui._apply_fold_designer_live_snapshot(host, current) is True
    assert host._fold_designer_live_sync_guard is False
    assert checked == [selected]
    assert active == [selected]
    assert selected_sheet == [expected_sheet]
    assert commits == [{"committed": True}]
    assert host._phase6_last_fold_designer_revision == 2
    assert (previous, current) == source_before


@pytest.mark.parametrize("version", (0, 2))
def test_main_gui_public_joint_replay_matches_canonical_engine_and_detaches(version):
    raw = {
        "model": "金庫型",
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_joint_schema_version": version,
        "assembly_joints": [],
    }
    saved = deepcopy(raw)
    assert api.migrate_operator_assembly_joint_snapshot is migrate_legacy_snapshot_joints
    assert ae_engine.migrate_operator_assembly_joint_snapshot is migrate_legacy_snapshot_joints
    projected = api.migrate_operator_assembly_joint_snapshot(raw)
    assert projected == migrate_legacy_snapshot_joints(raw)
    assert raw == saved
    assert projected is not raw


def test_project_reload_rejects_illegal_joint_source_before_advancing_live_graph():
    raw = {
        "assembly_joint_schema_version": 999,
        "assembly_type": "INSERT",
        "assembly_joints": [],
    }
    before = deepcopy(raw)
    state = {"sentinel": "still committed"}
    host = SimpleNamespace(
        settings_service=SimpleNamespace(snapshot=lambda: {}),
        _apply_fold_designer_live_settings=lambda _settings: None,
        _apply_manual_corner_snapshot=lambda *_args: None,
        assembly_joint_state=state,
    )
    with pytest.raises(ValueError, match="unsupported assembly joint schema"):
        gui._apply_original_fold_designer_snapshot(host, raw)
    assert host.assembly_joint_state is state
    assert raw == before


def test_live_sync_rejects_illegal_joint_source_and_releases_sync_guard():
    payload = {
        "model": "金庫型",
        "assembly_joint_schema_version": 999,
        "assembly_type": "INSERT",
        "assembly_joints": [],
    }
    before = deepcopy(payload)
    state = {"sentinel": "still committed"}
    host = SimpleNamespace(
        _fold_designer_live_sync_guard=False,
        baseline_var=SimpleNamespace(get=lambda: "金庫型"),
        _apply_manual_corner_snapshot=lambda *_args: None,
        assembly_joint_state=state,
    )
    with pytest.raises(ValueError, match="unsupported assembly joint schema"):
        gui._apply_fold_designer_live_snapshot(host, payload)
    assert host._fold_designer_live_sync_guard is False
    assert host.assembly_joint_state is state
    assert payload == before


def test_canonical_project_save_reload_keeps_public_joint_graph(tmp_path):
    import phase6_project_file as project

    saved = {
        "model": "金庫型",
        "w": 800.0, "h": 1200.0, "d": 350.0, "t": 2.0, "fw": 25.0,
        "assembly_type": "INSERT_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
        "assembly_joint_schema_version": 2,
        "assembly_joints": [],
    }
    before = deepcopy(saved)
    expected = api.normalize_project_snapshot_authority(saved)
    path = project.write_project(
        tmp_path / "joints.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    restored = project.read_project(path)["snapshot"]
    assert saved == before
    assert restored["assembly_joint_schema_version"] == expected["assembly_joint_schema_version"]
    assert restored["assembly_joints"] == expected["assembly_joints"]


def test_main_gui_two_replay_ports_and_navigation_have_no_private_manufacturing_rules():
    module = inspect.getsource(gui)
    assert "from ae_engine.assembly_joint import" not in module
    for func in (
        gui._apply_original_fold_designer_snapshot,
        gui._apply_fold_designer_live_snapshot,
    ):
        source = inspect.getsource(func)
        assert "manufacturing_api.migrate_operator_assembly_joint_snapshot(" in source
        assert "migrate_legacy_snapshot_joints(" not in source

    live = inspect.getsource(gui._apply_fold_designer_live_snapshot)
    assert live.count("manufacturing_api.is_box_body_physical_piece_key(") == 2
    assert 'startswith("box_body:")' not in live
    assert 'startswith("box_body:divider:")' not in live
