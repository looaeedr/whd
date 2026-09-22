from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="#517 exact GUI regressions require real Tk/Xvfb",
)


def _pump(root, cycles=5):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open_vault_designer():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("金庫型")
    _pump(root, 2)
    designer = app.open_original_fold_designer()
    try:
        designer.root.deiconify()
        designer.root.geometry("1400x900+0+0")
    except Exception:
        pass
    _pump(root, 5)
    return tk, root, app, designer


def _close(tk, root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except tk.TclError:
        pass


def _visible_back_panel_selector(designer):
    expected = ("全板", "半截", "背開孔")
    stack = [designer.root]
    matches = []
    while stack:
        widget = stack.pop()
        try:
            children = list(widget.winfo_children())
        except Exception:
            children = []
        stack.extend(children)
        try:
            values = tuple(widget.cget("values"))
        except Exception:
            continue
        if values == expected and bool(widget.winfo_ismapped()):
            matches.append(widget)
    return matches


def _mesh_bounds(triangles):
    points = [point for tri in tuple(triangles or ()) for point in tuple(tri or ())]
    assert points, "visible 3D mesh must exist"
    axes = tuple(zip(*points))
    return tuple(
        (round(min(float(v) for v in axis), 6), round(max(float(v) for v in axis), 6))
        for axis in axes
    )


def test_live_switch_with_visible_3d_replaces_vault_render_with_receiving_geometry():
    tk, root, _app, designer = _open_vault_designer()
    try:
        assert designer._phase6_3d_display_mode == "assembly"
        scene_renderer = designer.final_scene_view
        assert scene_renderer is not None
        before = _mesh_bounds(scene_renderer.last_cutting_mesh)

        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        assert str(designer._phase6_input_snapshot.get("model") or "") == "受電箱"
        after = _mesh_bounds(scene_renderer.last_cutting_mesh)
        assert after != before, (
            "Visible 3D mesh bounds stayed identical after live-switch to 受電箱; "
            f"before={before!r} after={after!r}"
        )
        assert tuple(
            str(key) for key in designer.designer_workspace.available_parts
            if str(key).startswith("box_body:")
        )[:3] == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
    finally:
        _close(tk, root, designer)


def test_structure_tree_selecting_back_panel_exposes_mapped_back_panel_mode_selector():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        tree = designer.structure_tree
        assert tree.exists("part:box_body:back")
        tree.selection_set("part:box_body:back")
        tree.focus("part:box_body:back")
        tree.event_generate("<<TreeviewSelect>>")
        _pump(root, 5)

        assert designer.designer_workspace.active_part == "box_body:back"
        selectors = _visible_back_panel_selector(designer)
        assert len(selectors) == 1, (
            "Selecting 後面板 through the real Structure Tree must expose exactly one "
            "mapped 後面板形式 selector in the existing visible input region"
        )
        selector = selectors[0]
        assert str(selector.get()) == "全板"

        # Mapped is not enough inside a Canvas: selecting 後面板 must bring the
        # selector into the user's current settings viewport without requiring
        # them to discover a hidden scroll position.
        canvas = designer.settings_scroll_canvas
        assert canvas is not None and bool(canvas.winfo_ismapped())
        selector_top = selector.winfo_rooty()
        selector_bottom = selector_top + max(1, selector.winfo_height())
        viewport_top = canvas.winfo_rooty()
        viewport_bottom = viewport_top + max(1, canvas.winfo_height())
        assert selector_bottom > viewport_top and selector_top < viewport_bottom, (
            "後面板形式 selector exists but is outside the visible settings viewport: "
            f"selector=({selector_top},{selector_bottom}) "
            f"viewport=({viewport_top},{viewport_bottom})"
        )
    finally:
        _close(tk, root, designer)


def test_actual_gui_batch_export_matches_canonical_resolved_physical_inventory(
    tmp_path, monkeypatch
):
    tk, root, app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        # Operator asks the actual 3D Output surface to export every selectable kind.
        for var in designer.output_export_vars.values():
            var.set(True)
        _pump(root, 2)

        import gui_modules.project.export_actions as export_actions
        monkeypatch.setattr(export_actions.filedialog, "askdirectory", lambda **_kw: str(tmp_path))
        monkeypatch.setattr(export_actions.messagebox, "showinfo", lambda *_a, **_kw: None)
        monkeypatch.setattr(export_actions.messagebox, "showwarning", lambda *_a, **_kw: None)
        monkeypatch.setattr(export_actions.messagebox, "showerror", lambda *_a, **_kw: None)

        expected_root = tmp_path / "_canonical"
        expected_root.mkdir()
        resolved = designer._phase6_resolve_manufacturing_geometry()

        from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf
        expected = save_resolved_manufacturing_geometry_dxf(
            resolved, expected_root, overwrite=True
        )

        designer.output_export_button.invoke()
        _pump(root, 5)

        actual_files = tuple(
            path for path in tmp_path.glob("*.dxf")
            if path.parent == tmp_path
        )
        assert len(actual_files) == len(expected), (
            "Actual GUI DXF export is missing canonical physical parts: "
            f"actual={sorted(p.name for p in actual_files)!r} "
            f"canonical_count={len(expected)}"
        )
    finally:
        _close(tk, root, designer)


def test_receiving_assembly_view_visibly_projects_three_frame_markings():
    tk, root, _app, designer = _open_vault_designer()
    try:
        designer.baseline_model_var.set("受電箱")
        _pump(root, 8)

        # Reach assembly through the real operator navigation, not a private helper.
        tree = designer.structure_tree
        tree.selection_set("mode:assembly")
        tree.focus("mode:assembly")
        tree.event_generate("<<TreeviewSelect>>")
        _pump(root, 5)
        assert designer._phase6_3d_display_mode == "assembly"

        from ae_engine.sheetmetal_drawing import LinePrimitive
        resolved = designer._phase6_resolve_manufacturing_geometry()
        source_marks = []
        for part_id in (
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
        ):
            source_marks.extend(
                primitive
                for primitive in tuple(resolved.part(part_id).render_data.scene.primitives)
                if isinstance(primitive, LinePrimitive)
                and str(primitive.layer).upper() == "MARKING"
            )
        assert len(source_marks) == 3, "canonical #509 frame MARKING source must exist"

        scene_renderer = designer.final_scene_view
        assert scene_renderer is not None
        ax = scene_renderer.renderer.ax3d
        marking_lines = [
            line for line in tuple(ax.lines)
            if str(line.get_color()).lower() == "#f59e0b"
        ]
        assert len(marking_lines) >= 3, (
            "Canonical MARKING exists in frame FinalScenes but is not visibly "
            "projected in Receiving assembly 3D"
        )
    finally:
        _close(tk, root, designer)
