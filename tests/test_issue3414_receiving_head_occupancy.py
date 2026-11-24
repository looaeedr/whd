"""Lifecycle only: keep role holes, retire physical Head occupant."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from phase6_designer_workspace import Phase6DesignerWorkspace

KEY = api.HEAD_OCCUPANCY_KEY
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "issue1503_legacy_receiving_without_nfb_base.p6fold"


def _snapshot():
    source = read_project(FIXTURE)["snapshot"]
    assert source["model"] == "受電箱" and "head" in source["existing_parts"]
    assert api.receiving_head_scope(source) is not None
    hole = CircleFeature(6.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(100.0, 100.0))
    source.setdefault("part_features", {})["head"] = [hole]
    if isinstance(source.get("workspace"), dict):
        source["workspace"].setdefault("part_features", {})["head"] = [hole]
    return source, hole


def _write(path, source):
    return write_project(path, {"schema": PROJECT_SCHEMA, "snapshot": source})


def _live(source, workspace):
    return {**source, **workspace.snapshot()}


def test_head_owner_roundtrip_replacement_and_ordinary_role_holes(tmp_path):
    source, hole = _snapshot()
    assert KEY not in source
    workspace = Phase6DesignerWorkspace.from_snapshot(source)
    first = workspace.snapshot()[KEY]["active"]
    assert first and api.receiving_head_occupant_status(_live(source, workspace), first) == "present"
    saved = read_project(_write(tmp_path / "first.p6fold", _live(source, workspace)))["snapshot"]
    reloaded = Phase6DesignerWorkspace.from_snapshot(saved)
    assert reloaded.snapshot()[KEY]["active"] == first
    assert reloaded.remove_part("head")
    removed = _live(saved, reloaded)
    assert api.receiving_head_occupant_status(removed, first) == "orphaned"
    absent = read_project(_write(tmp_path / "removed.p6fold", removed))["snapshot"]
    reloaded = Phase6DesignerWorkspace.from_snapshot(absent)
    assert reloaded.add_part("head")
    next_state = _live(absent, reloaded)
    second = next_state[KEY]["active"]
    assert second and second != first
    assert api.receiving_head_occupant_status(next_state, first) == "orphaned"
    assert api.receiving_head_occupant_status(next_state, second) == "present"
    assert reloaded.features_for("head") == [hole]
    final = read_project(_write(tmp_path / "second.p6fold", next_state))["snapshot"]
    assert final[KEY] == next_state[KEY]
    assert api.receiving_head_occupant_status(final, first) == "orphaned"
    # No new mark or export permission is carried by this identity record.
    assert not any(api.is_manual_mark(f) for f in reloaded.features_for("head"))


def test_scope_change_and_invalid_saved_owner_do_not_rebind():
    source, _ = _snapshot()
    ws = Phase6DesignerWorkspace.from_snapshot(source)
    original = _live(source, ws)
    owner = original[KEY]["active"]
    multi = deepcopy(original)
    multi["receiving_layout"], _ = api.resize_receiving_operator_topology_with_removed_ids(
        multi["receiving_layout"], set_index=0, bay_count=2,
    )
    assert api.receiving_head_occupant_status(multi, owner) == "orphaned"
    assert ws.sync_head_occupancy(multi)["active"] is None
    assert ws.sync_head_occupancy(original)["active"] != owner
    corrupt = deepcopy(original)
    corrupt[KEY]["retired"] = [owner]
    with pytest.raises(ValueError, match="HEAD_OCCUPANCY_OWNER_INVALID"):
        api.reconcile_receiving_head_occupancy(corrupt)


def test_primary_head_occupant_file_menu_remove_readd(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog
    import gui

    source, hole = _snapshot()
    initial = _write(tmp_path / "initial.p6fold", source)
    first_path = tmp_path / "first.p6fold"
    removed_path = tmp_path / "removed.p6fold"
    second_path = tmp_path / "second.p6fold"
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        menu = designer.project_file_menu

        def open_path(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(path))
            menu.invoke(0)
            root.update()
            assert host.project_controller.project_path == str(path)

        def save_path(path):
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_: str(path))
            menu.invoke(2)
            root.update()
            assert path.is_file()
            return read_project(path)["snapshot"]

        def workspace():
            return designer.designer_workspace

        open_path(initial)
        first = workspace().snapshot()[KEY]["active"]
        assert first
        assert workspace().features_for("head") == [hole]
        assert save_path(first_path)[KEY]["active"] == first
        open_path(first_path)
        assert workspace().snapshot()[KEY]["active"] == first

        # These are the shipped Primary Add/Remove command handlers.
        designer.activate_part("head")
        root.update()
        assert designer.remove_part("head")
        root.update()
        assert "head" not in workspace().available_parts
        removed = save_path(removed_path)
        assert api.receiving_head_occupant_status(removed, first) == "orphaned"
        open_path(removed_path)
        assert "head" not in workspace().available_parts
        designer.add_part("head")
        root.update()
        second = workspace().snapshot()[KEY]["active"]
        assert second and second != first
        # Legacy role holes deliberately retain their historical behavior.
        assert workspace().features_for("head") == [hole]
        saved = save_path(second_path)
        assert api.receiving_head_occupant_status(saved, first) == "orphaned"
        assert api.receiving_head_occupant_status(saved, second) == "present"
        open_path(second_path)
        assert workspace().snapshot()[KEY] == saved[KEY]
        assert workspace().features_for("head") == [hole]
    finally:
        root.destroy()


def test_primary_family_selector_retires_head_and_allocates_on_return(tmp_path, monkeypatch):
    """The real Family selector has a workspace port; standalone Settings does not."""
    import tkinter as tk
    from tkinter import filedialog
    import gui

    source, _ = _snapshot()
    initial = _write(tmp_path / "family-initial.p6fold", source)
    saved_path = tmp_path / "family-return.p6fold"
    root = tk.Tk()
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        menu = designer.project_file_menu
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(initial))
        menu.invoke(0)
        root.update_idletasks()
        root.update()
        assert host.project_controller.project_path == str(initial)

        def live():
            return _live(designer._phase6_input_snapshot, designer.designer_workspace)

        first = live()[KEY]["active"]
        assert first
        assert api.receiving_head_occupant_status(live(), first) == "present"
        designer.baseline_model_var.set("金庫型")
        root.update_idletasks()
        root.update()
        assert designer.baseline_model_var.get() == "金庫型"
        assert live()["model"] == "金庫型"
        assert live()[KEY]["active"] is None
        assert first in live()[KEY]["retired"]
        assert api.receiving_head_occupant_status(live(), first) == "orphaned"

        designer.baseline_model_var.set("受電箱")
        root.update_idletasks()
        root.update()
        assert designer.baseline_model_var.get() == "受電箱"
        assert live()["model"] == "受電箱"
        assert "head" in designer.designer_workspace.available_parts
        second = live()[KEY]["active"]
        assert second and second != first
        assert api.receiving_head_occupant_status(live(), first) == "orphaned"
        assert api.receiving_head_occupant_status(live(), second) == "present"
        assert not any(api.is_manual_mark(f) for f in designer.designer_workspace.features_for("head"))

        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_: str(saved_path))
        menu.invoke(2)
        root.update()
        persisted = read_project(saved_path)["snapshot"]
        assert persisted[KEY] == live()[KEY]
        assert api.receiving_head_occupant_status(persisted, first) == "orphaned"
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **_: str(saved_path))
        menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(saved_path)
        assert live()[KEY] == persisted[KEY]
    finally:
        root.destroy()
