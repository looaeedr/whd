"""#1959 original WHD main toolbar Save/Open with CADCraft-approved hole Features.

The native CADCraft process and its geometry transfer are covered by the
sibling Windows GUI test. This test exercises the separate REAL main toolbar
buttons and canonical .p6fold→DoorPartSpec manufacturing, no fake save/load.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import os

import ezdxf
import pytest

from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import generate_part
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from phase6_project_file import read_project
from tools.issue1959_whd_real_manufacturing_parity import _features, _signature


def _door_export(features, output, root):
    context = ManufacturingContext(resource_root=root, draw_stock=False)
    generate_part(DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25,
        gap_w=3.5, gap_h=3.5,
        fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
        features=tuple(features),
    ), output, context)
    return Counter(_signature(entity) for entity in
                   ezdxf.readfile(output).modelspace())


def test_cadcraft_approved_features_survive_actual_whd_main_toolbar_save_open(
    tmp_path, monkeypatch,
):
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires actual Tk display")
    import tkinter as tk
    import tkinter.filedialog as filedialog
    import gui

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        app.w_var.set("500")
        app.h_var.set("600")
        app.d_var.set("350")
        app._apply_existing_parts_from_fold_workspace(["box_body", "door"])
        root.update_idletasks()
        root.update()

        old, additions = _features()  # The same native CADCraft parity cases.
        owned = app.surface_features.setdefault("door", [])
        owned[:] = [old]
        identity = id(owned)
        # Existing WHD Session, not a parallel CADCraft persistence store.
        session = Phase6HoleEditorSession("door", owned)
        session.execute(HoleEditorAction.preview_all((old, *additions)))
        assert session.has_active_edit
        session.execute(HoleEditorAction.commit_active())
        session.finish(commit=True)
        accepted = tuple(owned)
        assert id(owned) == identity and len(accepted) == 4

        authority_root = tmp_path / "authority"
        authority_root.mkdir()
        before = _door_export(
            accepted, tmp_path / "before-toolbar-reload.dxf", authority_root
        )

        # Actually INVOKE WHD's global 'Save As' toolbar button. Only dialog
        # file selection is injected, never project.save or read_project.
        project_path = tmp_path / "WHD-CADCraft-confirmed.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **kw: str(project_path))
        app.project_save_as_button.invoke()
        assert project_path.is_file(), "WHD_MAIN_TOOLBAR_SAVE_AS_DID_NOT_WRITE"
        persisted = read_project(project_path)
        saved = tuple(persisted["snapshot"]["part_features"]["door"])
        assert saved == accepted, "CADCRAFT_CONFIRMED_FEATURES_MISSING_FROM_GUI_SAVE"
        assert not persisted["final_geometry"]
        assert "door" in persisted["snapshot"]["existing_parts"]

        # Destroy the live working Feature contents before opening. An actual
        # main-toolbar Open must reconstruct them from the .p6fold on disk.
        owned[:] = [old]
        assert tuple(owned) != accepted
        monkeypatch.setattr(filedialog, "askopenfilename",
                            lambda **kw: str(project_path))
        app.project_open_button.invoke()
        root.update_idletasks()
        root.update()

        restored = tuple(app.surface_features.get("door", ()))
        assert restored == accepted, "WHD_MAIN_TOOLBAR_OPEN_LOST_APPROVED_CADCraft_HOLES"
        assert len(restored) == 4
        assert app.project_controller.project_path == str(project_path)
        assert "door" in app._phase6_existing_parts

        # Verify that the WHD true Save button subsequently preserves the
        # restored holes, without asking for a second project filename.
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **kw: (_ for _ in ()).throw(
                                AssertionError("Save should reuse project path")
                            ))
        app.project_save_button.invoke()
        re_saved = tuple(read_project(project_path)["snapshot"]["part_features"]["door"])
        assert re_saved == accepted, "WHD_MAIN_TOOLBAR_SAVE_LOST_RESTORED_CADCraft_HOLES"

        # WHD alone regenerates complete manufacturing geometry from the
        # restored main-app Features; CADCraft DXF is not an input here.
        after = _door_export(
            re_saved, tmp_path / "after-toolbar-reload.dxf", authority_root
        )
        assert before == after, "WHD_GUI_RELOAD_MANUFACTURING_GEOMETRY_DRIFT"
        assert any(layer == "CUTTING" and kind == "CIRCLE"
                   for kind, layer, _ in after)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
