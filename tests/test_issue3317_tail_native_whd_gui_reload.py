# -*- coding: utf-8 -*-
"""#3317 native WHD main GUI: existing non-V CUTTING survives V -> save/open -> original.

No mocked Engine, resolver, viewport, project reader/writer or selector:
only Tk file-chooser destinations are supplied for unattended GitHub Xvfb.
This is a GUI preview/persistence regression, not CNC authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import pytest
from shapely.geometry import Polygon

import gui
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_core import RectFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_hole_editor_session import Phase6HoleEditorSession, HoleEditorAction
from phase6_project_file import read_project


def _material_holes(render):
    assert render.material.geom_type == "Polygon"
    return tuple(Polygon(ring) for ring in render.material.interiors)


def _real_tail_selector(designer):
    designer.activate_part("tail")
    page = designer._phase6_render_settings_context("tail")
    extension = page["extension_state"]
    chooser = extension["tail_lower_v_choice_widget"]
    var = extension["tail_lower_v_choice_var"]
    assert chooser is not None and var is not None
    assert chooser.winfo_exists()
    return chooser, var


def _real_resolved_tail(designer):
    geometry = designer._phase6_resolve_manufacturing_geometry()
    tail = geometry.part("tail")
    assert tail is not None and tail.render_data is not None
    return tail.render_data


def _assert_same_holes(before, after):
    originals = _material_holes(before)
    updates = _material_holes(after)
    assert len(originals) >= 1
    assert len(updates) == len(originals)
    assert all(any(a.symmetric_difference(b).area < 1e-5 for b in updates)
               for a in originals)
    return originals


def test_actual_whd_main_gui_lower_v_preserves_existing_rect_clearance_roundtrip(
    tmp_path, monkeypatch,
):
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("native WHD GUI requires a real Tk/Xvfb display")
    root = tk.Tk()
    root.withdraw()
    destination = tmp_path / "vault-tail-620x185-existing-clearance.p6fold"
    try:
        def fail_dialog(title, description, **_kwargs):
            raise AssertionError(f"unexpected native GUI error {title}: {description}")

        monkeypatch.setattr(messagebox, "showerror", fail_dialog)
        monkeypatch.setattr(filedialog, "asksaveasfilename",
                            lambda **_kw: str(destination))
        monkeypatch.setattr(filedialog, "askopenfilename",
                            lambda **_kw: str(destination))
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("金庫型")
        main.w_var.set("620")
        main.h_var.set("600")
        main.d_var.set("185")
        if hasattr(main, "t_var"):
            main.t_var.set("2")
        main._apply_existing_parts_from_fold_workspace(
            ["box_body", "head", "tail"],
        )

        # Commit a genuine operator CUTTING cutout through the existing
        # WHD HoleEditor transaction, before choosing the V. This is an
        # independent rectangular clearance, not a fixture seam or V leg.
        feature = RectFeature(
            8.0, 10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(200.0, 115.0),
        )
        owned = main.surface_features.setdefault("tail", [])
        baseline_features = tuple(owned)
        session = Phase6HoleEditorSession("tail", owned)
        session.execute(HoleEditorAction.preview_all((*baseline_features, feature)))
        session.execute(HoleEditorAction.commit_active())
        session.finish(commit=True)
        assert feature in owned

        designer = main.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        chooser, selected = _real_tail_selector(designer)
        assert selected.get() == "原樣"
        original = _real_resolved_tail(designer)
        original_holes = _material_holes(original)
        assert len(original_holes) >= 1

        # Actual Tk dropdown command -> Engine preflight -> live 2D & T3D.
        chooser._phase6_menu.invoke(1)
        root.update_idletasks()
        root.update()
        assert selected.get() == "V 型"
        assert designer._phase6_input_snapshot[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        with_v = _real_resolved_tail(designer)
        _assert_same_holes(original, with_v)
        assert with_v.metadata["tail_lower_v_preview_only"] is True
        mesh = api.project_independent_part_view_mesh(
            "tail", with_v, x_profile=(), y_profile=(), thickness=2.,
        )
        assert mesh.triangles == api.tail_lower_v_preview_mesh(with_v)
        assert len(mesh.triangles) > 500

        # Invoke WHD's actual main toolbar Save As and Open buttons.
        main.project_save_as_button.invoke()
        assert destination.is_file()
        saved = read_project(destination)["snapshot"]
        assert saved[api.TAIL_LOWER_V_SNAPSHOT_KEY] == "v90"
        assert feature in saved["part_features"]["tail"]

        main.project_open_button.invoke()
        root.update_idletasks()
        root.update()
        reopened = main.fold_designer_app or main.open_original_fold_designer()
        chooser2, selected2 = _real_tail_selector(reopened)
        assert selected2.get() == "V 型"
        reloaded_v = _real_resolved_tail(reopened)
        _assert_same_holes(with_v, reloaded_v)
        assert reloaded_v.material.symmetric_difference(with_v.material).area < 1e-5
        assert api.project_independent_part_view_mesh(
            "tail", reloaded_v, x_profile=(), y_profile=(), thickness=2.,
        ).triangles == api.tail_lower_v_preview_mesh(reloaded_v)

        chooser2._phase6_menu.invoke(0)
        root.update_idletasks()
        root.update()
        assert selected2.get() == "原樣"
        assert api.TAIL_LOWER_V_SNAPSHOT_KEY not in reopened._phase6_input_snapshot
        restored = _real_resolved_tail(reopened)
        _assert_same_holes(original, restored)
        assert restored.material.symmetric_difference(original.material).area < 1e-5
        assert api.tail_lower_v_preview_mesh(restored) is None
    finally:
        root.destroy()
