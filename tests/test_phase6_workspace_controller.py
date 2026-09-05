from copy import deepcopy

import pytest

from phase6_workspace_controller import Phase6WorkspaceController


def test_workspace_controller_keeps_box_body_and_defensive_copies_state():
    source = {
        "existing_parts": ["tail"],
        "active_part": "tail",
        "part_profiles": {"tail": {"Y": [{"len": 10.0}]}},
        "box_body_profile": [{"len": 20.0}],
    }
    controller = Phase6WorkspaceController(default_existing_parts={"box_body", "head"})
    saved = controller.commit_workspace(source)

    assert controller.current_existing_parts() == {"box_body", "tail"}
    assert controller.active_part == "tail"
    assert saved["existing_parts"] == ["box_body", "tail"]

    source["part_profiles"]["tail"]["Y"][0]["len"] = 999.0
    saved["part_profiles"]["tail"]["Y"][0]["len"] = 888.0
    assert controller.profile_for("tail")["Y"][0]["len"] == 10.0


def test_authoritative_workspace_ignores_legacy_indicator_fallback():
    controller = Phase6WorkspaceController(
        default_existing_parts={"box_body", "head", "tail", "door", "base_plate"}
    )
    assert "indicator_box" in controller.current_existing_parts(indicator_box_enabled=True)
    assert "indicator_door" in controller.current_existing_parts(indicator_box_enabled=True)

    controller.commit_workspace({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {},
    })

    assert controller.current_existing_parts(indicator_box_enabled=True) == {"box_body", "head"}


def test_delete_part_keeps_profile_stash_and_readd_restores_presence():
    controller = Phase6WorkspaceController()
    controller.commit_workspace({
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "tail",
        "part_profiles": {"tail": {"Y": [{"len": 33.0}]}},
    })

    existing = controller.set_part_presence("tail", False)
    assert existing == {"box_body", "head"}
    assert controller.active_part == "box_body"
    assert controller.profile_for("tail") == {"Y": [{"len": 33.0}]}

    existing = controller.set_part_presence("tail", True)
    assert existing == {"box_body", "head", "tail"}
    assert controller.profile_for("tail") == {"Y": [{"len": 33.0}]}


def test_invalid_active_part_cannot_escape_existing_parts():
    controller = Phase6WorkspaceController()
    controller.commit_workspace({
        "existing_parts": ["box_body", "head"],
        "active_part": "door",
        "part_profiles": {},
    })
    assert controller.active_part == "box_body"
    assert controller.set_active_part("tail") == "box_body"
    assert controller.set_active_part("head") == "head"
    assert controller.set_active_part(None) is None


def test_workspace_snapshot_returns_deep_copy_and_keeps_profile_stash_for_absent_parts():
    controller = Phase6WorkspaceController()
    controller.commit_workspace({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {
            "head": {"X": [{"len": 1.0}]},
            "tail": {"X": [{"len": 2.0}]},
        },
        "box_body_profile": [{"len": 15.0}],
    })

    snapshot = controller.workspace_snapshot()
    assert snapshot["existing_parts"] == ["box_body", "head"]
    assert "tail" in snapshot["part_profiles"]
    snapshot["part_profiles"]["tail"]["X"][0]["len"] = 999.0
    assert controller.profile_for("tail")["X"][0]["len"] == 2.0


def test_legacy_bundle_is_compatibility_view_not_mutable_backing_state():
    controller = Phase6WorkspaceController()
    controller.load_legacy_bundle({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {"head": {"Y": [{"len": 5.0}]}},
    })
    bundle = controller.legacy_bundle()
    bundle["existing_parts"].append("tail")
    bundle["part_profiles"]["head"]["Y"][0]["len"] = 777.0

    assert controller.current_existing_parts() == {"box_body", "head"}
    assert controller.profile_for("head")["Y"][0]["len"] == 5.0


def test_real_gui_workspace_compatibility_aliases_share_one_controller():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        assert isinstance(app.workspace_controller, Phase6WorkspaceController)
        for legacy_name in (
            "fold_designer_part_bundle",
            "_phase6_existing_parts",
            "_fold_designer_last_part_key",
            "fold_designer_box_body_profile",
        ):
            assert legacy_name not in app.__dict__

        app._phase6_existing_parts = {"box_body", "head"}
        assert app.workspace_controller.current_existing_parts() == {"box_body", "head"}

        app.fold_designer_part_bundle = {
            "existing_parts": ["box_body", "head"],
            "active_part": "head",
            "part_profiles": {"head": {"Y": [{"len": 12.0}]}},
        }
        assert app.workspace_controller.has_authoritative_workspace is True
        assert app._fold_designer_last_part_key == "head"
        assert app.workspace_controller.profile_for("head")["Y"][0]["len"] == 12.0
    finally:
        root.destroy()


def test_gui_production_methods_do_not_depend_on_legacy_workspace_aliases():
    import ast
    from pathlib import Path
    import gui

    legacy = {
        "fold_designer_part_bundle",
        "_phase6_existing_parts",
        "_fold_designer_last_part_key",
        "fold_designer_box_body_profile",
    }
    allowed_property_methods = set(legacy)
    tree = ast.parse(Path(gui.__file__).read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in allowed_property_methods:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr in legacy:
                violations.append((node.name, child.attr, getattr(child, "lineno", None)))
    assert violations == []


def test_loading_project_without_box_profile_clears_previous_workspace_fold_chain(tmp_path):
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import phase6_project_file as project

    root = tk.Tk(); root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.workspace_controller.set_box_body_profile([{"len": 999.0, "phase6_key": "stale"}])
        snapshot = app._make_original_fold_designer_snapshot()
        snapshot.pop("box_body_profile", None)
        snapshot["workspace"] = {
            "box_body_profile": None,
            "existing_parts": ["box_body", "head"],
            "active_part": "head",
            "part_profiles": {},
            "endcap_fw": snapshot.get("endcap_fw", {}),
        }
        payload = {
            "schema": project.PROJECT_SCHEMA,
            "saved_at": "2026-08-23T12:50:00+08:00",
            "snapshot": snapshot,
            "final_geometry": {},
        }
        path = project.write_project(tmp_path / "no-profile.p6fold", payload)

        app.load_phase6_project(path, open_designer=False)

        assert app.workspace_controller.box_body_profile() is None
        committed = app._compose_phase6_project_snapshot_from_main_gui()
        assert committed["workspace"]["box_body_profile"] == []
    finally:
        root.destroy()


def test_workspace_controller_owns_box_body_structure_state_and_preserves_inactive_configs():
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        set_active_structure,
        update_structure_config,
    )

    controller = Phase6WorkspaceController()
    state = controller.box_body_structure_state()
    assert state["active_type"] == BoxBodyStructureType.INTEGRAL.value
    assert state["locked"] is True

    state = update_structure_config(
        state,
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        {"left_w": 700.0, "right_w": 500.0},
    )
    state = set_active_structure(state, BoxBodyStructureType.TWO_PIECE_W_SPLIT)
    controller.set_box_body_structure_state(state)

    state = set_active_structure(
        controller.box_body_structure_state(),
        BoxBodyStructureType.THREE_PIECE_W_SPLIT,
    )
    controller.set_box_body_structure_state(state)
    state = set_active_structure(
        controller.box_body_structure_state(),
        BoxBodyStructureType.TWO_PIECE_W_SPLIT,
    )
    controller.set_box_body_structure_state(state)

    restored = controller.box_body_structure_state()
    two = restored["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    assert two["left_w"] == pytest.approx(700.0)
    assert two["right_w"] == pytest.approx(500.0)


def test_workspace_snapshot_round_trips_box_body_structure_and_legacy_workspace_gets_defaults():
    from phase6_box_body_structure import BoxBodyStructureType

    controller = Phase6WorkspaceController()
    controller.commit_workspace({
        "existing_parts": ["box_body"],
        "active_part": "box_body",
        "part_profiles": {},
        "box_body_structure": {
            "active_type": BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
            "locked": False,
            "configs": {
                BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value: {
                    "side_rear_bend": 18.0,
                    "back_width_comp_t": 1.0,
                }
            },
        },
    })
    snapshot = controller.workspace_snapshot()
    assert snapshot["box_body_structure"]["active_type"] == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    assert snapshot["box_body_structure"]["locked"] is False
    assert snapshot["box_body_structure"]["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]["side_rear_bend"] == pytest.approx(18.0)

    legacy = Phase6WorkspaceController()
    legacy.commit_workspace({
        "existing_parts": ["box_body"],
        "active_part": "box_body",
        "part_profiles": {},
    })
    assert legacy.box_body_structure_state()["active_type"] == BoxBodyStructureType.INTEGRAL.value
    assert legacy.box_body_structure_state()["locked"] is True


def test_designer_workspace_owns_draft_box_body_structure_and_round_trips_it():
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from phase6_box_body_structure import BoxBodyStructureType, default_box_body_structure_state, set_active_structure

    state = set_active_structure(default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT)
    ws = Phase6DesignerWorkspace.from_snapshot({"box_body_structure": state})
    assert ws.box_body_structure_state()["active_type"] == BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    ws.mark_clean()
    changed = ws.box_body_structure_state()
    changed["locked"] = False
    ws.set_box_body_structure_state(changed)
    assert ws.dirty is True
    assert ws.snapshot()["box_body_structure"]["locked"] is False
