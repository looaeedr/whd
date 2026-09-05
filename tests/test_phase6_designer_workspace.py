from copy import deepcopy

import pytest


def _snapshot():
    return {
        "existing_parts": ["box_body", "head", "door"],
        "active_part": "head",
        "part_profiles": {
            "head": {"X": [{"phase6_key": "hx", "len": 11}], "Y": []},
            "door": {"X": [{"phase6_key": "dx", "len": 22}], "Y": []},
        },
        "part_features": {"head": [{"id": "h1"}], "door": [{"id": "d1"}]},
        "part_face_features": {"box_body": {"left": [{"id": "l1"}]}},
    }


def test_from_snapshot_normalizes_box_body_and_defensive_copies():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    source = _snapshot()
    source["existing_parts"] = ["head", "door"]
    ws = Phase6DesignerWorkspace.from_snapshot(source)

    assert ws.available_parts == ("box_body", "head", "door")
    assert ws.active_part == "head"
    profiles = ws.profiles_for("head")
    profiles["X"][0]["len"] = 999
    assert ws.profiles_for("head")["X"][0]["len"] == 11


def test_remove_add_round_trip_preserves_stash_and_marks_dirty():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot(_snapshot())
    assert ws.remove_part("door") is True
    assert "door" not in ws.available_parts
    assert ws.dirty is True

    restored = ws.add_part("door", default_profiles={"X": [{"len": 999}], "Y": []})
    assert restored is True
    assert ws.profiles_for("door")["X"][0]["len"] == 22
    assert ws.features_for("door") == [{"id": "d1"}]


def test_box_body_cannot_be_removed():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot(_snapshot())
    with pytest.raises(ValueError, match="箱身"):
        ws.remove_part("box_body")


def test_home_clears_activity_but_keeps_stash_and_presence():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot(_snapshot())
    ws.select_part("door")
    ws.begin_switch("door")
    ws.finish_switch()
    ws.show_home()

    assert ws.active_part is None
    assert ws.selected_part is None
    assert ws.available_parts == ("box_body", "head", "door")
    assert ws.profiles_for("door")["X"][0]["len"] == 22


def test_begin_switch_validates_presence_and_owns_switching_flag():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot(_snapshot())
    with pytest.raises(ValueError, match="不存在"):
        ws.begin_switch("tail")
    assert ws.switching is False

    ws.begin_switch("door")
    assert ws.switching is True
    assert ws.active_part == "door"
    assert ws.selected_part == "door"
    ws.finish_switch()
    assert ws.switching is False


def test_stash_and_snapshot_are_defensive_and_mark_clean_is_explicit():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot(_snapshot())
    ws.mark_clean()
    source = {"X": [{"phase6_key": "x", "len": 33}], "Y": []}
    ws.stash_profiles("head", source)
    source["X"][0]["len"] = 999
    assert ws.profiles_for("head")["X"][0]["len"] == 33
    assert ws.dirty is True

    snap = ws.snapshot()
    snap["part_profiles"]["head"]["X"][0]["len"] = 777
    assert ws.profiles_for("head")["X"][0]["len"] == 33
    ws.mark_clean()
    assert ws.dirty is False


def test_owner_module_has_no_ui_or_manufacturing_dependencies():
    from pathlib import Path
    source = Path(__import__("phase6_designer_workspace").__file__).read_text(encoding="utf-8")
    forbidden = ("tkinter", "fold_designer_bridge", "ae_engine", "Phase6ProjectSession", "SettingsService", "renderer")
    assert not [name for name in forbidden if name in source]


def test_real_designer_legacy_workspace_names_are_properties_over_one_owner():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        assert designer.designer_workspace is not None
        for name in (
            "available_parts", "active_part_key", "selected_part_key",
            "_phase6_part_profiles", "_phase6_part_features",
            "_phase6_part_face_features", "_phase6_workspace_dirty",
            "_phase6_switching_part",
        ):
            assert name not in designer.__dict__
        assert tuple(designer.available_parts) == designer.designer_workspace.available_parts
        assert designer.active_part_key == designer.designer_workspace.active_part
        assert designer.selected_part_key == designer.designer_workspace.selected_part
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_bridge_lifecycle_methods_do_not_mutate_legacy_workspace_backing_names_directly():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(__import__("fold_designer_bridge").__file__).read_text(encoding="utf-8"))
    targets = {
        "_fix11_select_part", "_fix11_remove_selected_part", "_phase6_show_home",
        "_fix11_save_current_part", "_fix11_activate_part", "_fix11_add_part", "_fix11_remove_part",
    }
    forbidden_attrs = {
        "available_parts", "active_part_key", "selected_part_key",
        "_phase6_part_profiles", "_phase6_part_features", "_phase6_workspace_dirty",
        "_phase6_switching_part",
    }
    violations = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in targets:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Store) and child.attr in forbidden_attrs:
                violations.append((node.name, child.attr, child.lineno))
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                owner = child.func.value
                if isinstance(owner, ast.Attribute) and owner.attr in forbidden_attrs and child.func.attr in {"append", "remove", "clear", "extend", "setdefault", "update"}:
                    violations.append((node.name, f"{owner.attr}.{child.func.attr}", child.lineno))
    assert violations == []


def test_workspace_collection_uses_designer_workspace_snapshot_not_legacy_mirrors():
    from types import SimpleNamespace
    import fold_designer_bridge as bridge
    from phase6_designer_workspace import Phase6DesignerWorkspace

    ws = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "head"],
        "active_part": "head",
        "part_profiles": {"head": {"X": [{"len": 11}], "Y": []}},
        "part_features": {"head": [{"id": "real"}]},
    })
    holder = SimpleNamespace(
        designer_workspace=ws,
        available_parts=["box_body", "door"],
        active_part_key="door",
        _phase6_part_profiles={"door": {"X": [{"len": 999}], "Y": []}},
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_endcap_fw_state={},
        _phase6_input_snapshot={"fw": 25},
        state=SimpleNamespace(profiles_vault={"箱身": [{"len": 400, "core": "W"}]}),
    )

    collected = bridge._phase6_collect_workspace_state(holder)
    assert collected["existing_parts"] == ["box_body", "head"]
    assert collected["active_part"] == "head"
    assert collected["part_profiles"]["head"]["X"][0]["len"] == 11
    assert "door" not in collected["part_profiles"]


def test_real_designer_switch_saves_outgoing_before_workspace_changes_active_part():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("door")
        root.update_idletasks(); root.update()

        calls = []
        workspace = designer.designer_workspace
        original_begin = workspace.begin_switch
        designer._save_current_part = lambda notify=True: calls.append(("save", workspace.active_part))

        def begin(key):
            calls.append(("begin", workspace.active_part, key))
            return original_begin(key)

        workspace.begin_switch = begin
        designer.activate_part("head")
        root.update_idletasks(); root.update()

        assert calls[:2] == [("save", "door"), ("begin", "door", "head")]
        assert workspace.active_part == "head"
        assert workspace.switching is False
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_destroying_designer_cancels_owned_tk_after_callbacks():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        # Simulate the two delayed jobs owned by the designer.  Destroying the
        # designer Toplevel must cancel and clear them before its Tcl commands
        # disappear, otherwise later tests/new designers inherit stale work.
        designer._job = designer.root.after(60_000, lambda: None)
        designer._phase6_settings_debounce_job = designer.root.after(60_000, lambda: None)

        app.fold_designer_window.destroy()
        root.update_idletasks(); root.update()

        assert designer._job is None
        assert designer._phase6_settings_debounce_job is None
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
