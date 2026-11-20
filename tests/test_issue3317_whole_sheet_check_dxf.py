"""#3317 true whole-piece V replacement CHECK and verified diagnostic-only DXF.

This is not a manufacturing or R/BA certification test. Real Tk PartSpec /
FinalScene are preserved and every DXF is checked by independent reopen.
"""
from __future__ import annotations

from dataclasses import replace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import (
    DrawingScene, LinePrimitive, PolylinePrimitive,
)
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
def test_real_gui_whole_sheet_v_contour_matches_engine_and_dxf_reopen(
    part_key, tmp_path,
):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()
        original = app._query_fold_designer_render_data(
            part_key, app._make_original_fold_designer_snapshot(),
        )
        old_scene = tuple(original.scene.primitives)
        result = app._project_v_miter_gui_check_for_corner(part_key, "bottom")
        assert result.full_sheet_check_scene is not None
        assert result.material_check is not None
        assert result.material_check_failure is None
        scene = result.full_sheet_check_scene
        assert all(p.layer in {"CHECK", "DATUM"} for p in scene.primitives)
        remain = [
            p for p in scene.primitives
            if isinstance(p, PolylinePrimitive)
            and p.semantic_id == "v_miter_whole_sheet_unverified_remaining"
        ]
        assert len(remain) == 1 and remain[0].closed
        assert remain[0].points == result.material_check.remaining_outline
        original_datum = [
            p for p in scene.primitives if isinstance(p, PolylinePrimitive)
            and p.semantic_id == "v_miter_original_factory_corner_datum"
        ]
        assert len(original_datum) == 1
        assert original_datum[0].layer == "DATUM"
        assert any(p.layer == "DATUM" and isinstance(p, LinePrimitive)
                   for p in scene.primitives)
        assert tuple(original.scene.primitives) == old_scene
        assert app.v_miter_export_check_button.cget("state") == "normal"

        path = tmp_path / f"{part_key}_CHECK_ONLY_UNCERTIFIED.dxf"
        output = api.save_v_miter_whole_sheet_check_dxf(scene, path)
        assert str(path) == output
        reopened = tuple(ezdxf.readfile(path).modelspace())
        assert len(reopened) == len(scene.primitives)
        assert not any(e.dxf.layer in {"CUTTING", "BEND", "MARKING"}
                       for e in reopened)
        actual = [
            e for e in reopened
            if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CHECK"
        ]
        assert len(actual) == 2
        candidate = tuple(actual[0].get_points("xy"))
        assert len(candidate) == len(remain[0].points)
        for (x, y), point in zip(candidate, remain[0].points):
            assert (x, y) == pytest.approx((point.x, point.y))
        with pytest.raises(FileExistsError):
            api.save_v_miter_whole_sheet_check_dxf(scene, path)
        # No source scene/production CUTTING mutation by preview/export.
        assert tuple(original.scene.primitives) == old_scene
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()


def test_full_sheet_dxf_rejects_unauthorized_manufacturing_layers(tmp_path):
    scene = DrawingScene([PolylinePrimitive(
        (Vec2(0, 0), Vec2(1, 0), Vec2(0, 1)),
        layer="CUTTING", closed=True,
        semantic_id="v_miter_whole_sheet_unverified_remaining",
    )])
    path = tmp_path / "should_not_exist.dxf"
    with pytest.raises(GeometryError, match="MANUFACTURING_LAYER_FORBIDDEN"):
        api.save_v_miter_whole_sheet_check_dxf(scene, path)
    assert not path.exists()


def test_export_rejects_untrusted_check_only_dxf_without_full_sheet_lineage(tmp_path):
    scene = DrawingScene([LinePrimitive(
        Vec2(0, 0), Vec2(10, 10), "CHECK",
    )])
    with pytest.raises(GeometryError, match="FULL_SHEET_SOURCE_REQUIRED"):
        api.save_v_miter_whole_sheet_check_dxf(
            scene, tmp_path / "fake_check.dxf",
        )


def test_dxf_reopen_failure_leaves_existing_target_untouched(monkeypatch, tmp_path):
    from ae_engine import v_miter_full_sheet_check as owner

    scene = DrawingScene([
        PolylinePrimitive(
            (Vec2(0, 0), Vec2(10, 0), Vec2(0, 10)),
            layer="CHECK", closed=True,
            semantic_id="v_miter_whole_sheet_unverified_remaining",
        )
    ])
    dest = tmp_path / "existing_CHECK_ONLY_UNCERTIFIED.dxf"
    dest.write_bytes(b"previous good content")
    def broken_reopen(_scene, _target):
        raise GeometryError("INJECTED_DXF_REOPEN_FAILURE")
    monkeypatch.setattr(owner, "_verify_check_dxf_reopen", broken_reopen)
    with pytest.raises(GeometryError, match="INJECTED_DXF_REOPEN_FAILURE"):
        api.save_v_miter_whole_sheet_check_dxf(scene, dest, overwrite=True)
    assert dest.read_bytes() == b"previous good content"
    assert not tuple(tmp_path.glob(".v_miter_check_*.dxf"))


def test_save_reopen_uses_actual_gui_button_and_never_main_dxf(monkeypatch, tmp_path):
    import tkinter as tk
    import gui

    target = tmp_path / "gui_CHECK_ONLY_UNCERTIFIED.dxf"
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", lambda **_kw: str(target))
    messages = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args, **kwargs: messages.append(args))
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *args, **kwargs: pytest.fail(str(args)))
    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("door")
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()
        assert app.v_miter_export_check_button.cget("state") == "normal"
        app.v_miter_export_check_button.invoke()
        assert target.exists()
        assert len(messages) == 1
        assert all(e.dxf.layer in {"CHECK", "DATUM"}
                   for e in ezdxf.readfile(target).modelspace())
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
