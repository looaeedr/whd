from __future__ import annotations

import os

import pytest


def _receiving_snapshot():
    from ae_engine.cabinet_types.receiving import apply_family_defaults

    return apply_family_defaults({
        "model": "金庫型",
        "w": 400.0,
        "h": 600.0,
        "d": 250.0,
        "t": 2.0,
        "fw": 25.0,
    })


def test_enabled_inner_doors_derive_real_panel_parts_with_stable_ids():
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    snap = _receiving_snapshot()
    panels = cabinet_family_policy.derive_inner_door_panels(snap)
    assert [panel.stable_id for panel in panels] == ["inner_door:upper:panel"]
    first = panels[0]
    assert first.inner_door_id == "upper"
    assert first.cell_key == "0:0"
    assert first.width > 0
    assert first.height > 0

    repeat = cabinet_family_policy.derive_inner_door_panels(snap)
    assert [panel.stable_id for panel in repeat] == ["inner_door:upper:panel"]

    snap["inner_doors"] = [
        *snap["inner_doors"],
        {"stable_id": "lower", "cell_key": "0:1", "included_frame_sides": ["top", "left", "right"]},
    ]
    panels = cabinet_family_policy.derive_inner_door_panels(snap)
    assert {panel.stable_id for panel in panels} == {
        "inner_door:upper:panel",
        "inner_door:lower:panel",
    }

    snap["inner_doors"] = [item for item in snap["inner_doors"] if item["cell_key"] != "0:0"]
    panels = cabinet_family_policy.derive_inner_door_panels(snap)
    assert [panel.stable_id for panel in panels] == ["inner_door:lower:panel"]


def test_inner_door_panel_has_real_manufacturing_render_data(tmp_path):
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data, measure_unfolded_blanks

    panel = cabinet_family_policy.derive_inner_door_panels(_receiving_snapshot())[0]
    render = build_inner_door_panel_render_data(panel)
    assert render.metadata["stable_id"] == "inner_door:upper:panel"
    # A real inner Door is bent, not the old unbent finished-size rectangle.
    # CUTTING has certified door-corner reliefs and BEND guides.
    assert render.material.area < panel.unfolded_width * panel.unfolded_height
    assert render.fold_guides
    blank = measure_unfolded_blanks(render, part_key=panel.stable_id)[0]
    assert blank.width == pytest.approx(panel.unfolded_width)
    assert blank.height == pytest.approx(panel.unfolded_height)
    # Independent known receiving 800-mm manufacturing acceptance:
    # 800 outer W - 2 * 2 side sheets = 796 inner clear width;
    # 796 - 2 * 50 formed frames - 2 * 3.5 gaps = 689 finished;
    # 689 - 2 * 2 + 2 * 19 folded Door lips = 723 CUTTING blank.
    # This must not be copied from the production width resolver.
    assert panel.thickness == pytest.approx(2.0)
    assert panel.fold_left == pytest.approx(19.0)
    assert panel.fold_right == pytest.approx(19.0)
    assert panel.width == pytest.approx(689.0)
    assert panel.unfolded_width == pytest.approx(723.0)
    assert render.metadata["finished_width"] == pytest.approx(689.0)
    assert render.metadata["unfolded_width"] == pytest.approx(723.0)
    # Same finished-to-blank formula as the outer Door, but inner-door
    # assembly deductions: 1100 - (50 top frame + T2) - two 3.5 gaps.
    assert panel.height == pytest.approx(1041.0)
    assert panel.unfolded_height == pytest.approx(1075.0)
    assert render.metadata["finished_height"] == pytest.approx(1041.0)
    assert render.metadata["unfolded_height"] == pytest.approx(1075.0)

    # Measure the actual generated CUTTING polygon; do not validate a
    # manufacturing number only against metadata produced by the same code.
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    cutting_outlines = [
        item for item in tuple(render.scene.primitives)
        if isinstance(item, PolylinePrimitive)
        and str(item.layer).upper() == "CUTTING"
    ]
    # Vault baseline can contain inner CUTTING apertures as additional
    # contours. Exactly ONE contour has the finished blank's full extent.
    outer = [
        shape for shape in cutting_outlines
        if max(p.x for p in shape.points) - min(p.x for p in shape.points)
           == pytest.approx(panel.unfolded_width)
        and max(p.y for p in shape.points) - min(p.y for p in shape.points)
           == pytest.approx(panel.unfolded_height)
    ]
    assert len(outer) == 1
    cutting_x = [float(point.x) for point in outer[0].points]
    cutting_y = [float(point.y) for point in outer[0].points]
    assert max(cutting_x) - min(cutting_x) == pytest.approx(723.0)
    assert max(cutting_y) - min(cutting_y) == pytest.approx(1075.0)

    # Single-cabinet real panel uses the same FinalScene in the standalone
    # physical DXF (not a thumbnail or a Bay/NFB-only preview).
    import ezdxf
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    path = save_part_render_data_dxf(render, tmp_path / "inner-door-upper.dxf")
    drawing = ezdxf.readfile(path)
    entities = tuple(drawing.modelspace())
    assert any(e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CUTTING" for e in entities)
    assert any(e.dxf.layer == "BEND" for e in entities)


@pytest.mark.parametrize(
    "cell_height,thickness,gap_h",
    [(1100.0, 2.0, 3.5), (500.0, 2.0, 3.5),
     (1100.0, 3.0, 5.0)],
)
def test_inner_door_vertical_deductions_keep_bottom_frame_absent(
    cell_height, thickness, gap_h,
):
    from ae_engine.cabinet_types.receiving import inner_door_panel_vertical_contract
    from ae_engine.inner_door_frames import inner_door_frame_formed_occupation

    contract = inner_door_panel_vertical_contract(
        cell_height=cell_height, thickness=thickness, gap_h=gap_h,
    )
    top = inner_door_frame_formed_occupation(thickness) + thickness
    expected_height = cell_height - top - 2.0 * gap_h
    assert contract["top_occupation"] == pytest.approx(top)
    assert contract["bottom_occupation"] == 0.0
    assert contract["finished_height"] == pytest.approx(expected_height)
    assert contract["center_offset_y"] == pytest.approx(-top / 2.0)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_each_outer_door_data_row_has_independent_inner_door_checkbox_state():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        app.rebuild_door_layout_ui()
        root.update_idletasks(); root.update()

        assert set(app.door_layout_inner_door_vars) >= {"0:0", "0:1"}
        assert bool(app.door_layout_inner_door_vars["0:0"].get()) is True
        assert bool(app.door_layout_inner_door_vars["0:1"].get()) is False

        app.door_layout_inner_door_vars["0:1"].set(True)
        app._commit_receiving_inner_door_checkbox("0:1")
        assert app._receiving_inner_door_enabled("0:0") is True
        assert app._receiving_inner_door_enabled("0:1") is True
        assert {item["cell_key"] for item in app.receiving_inner_doors} == {"0:0", "0:1"}

        upper_id = next(item["stable_id"] for item in app.receiving_inner_doors if item["cell_key"] == "0:0")
        app.door_layout_inner_door_vars["0:0"].set(False)
        app._commit_receiving_inner_door_checkbox("0:0")
        assert app._receiving_inner_door_enabled("0:0") is False
        assert app._receiving_inner_door_enabled("0:1") is True

        app.door_layout_inner_door_vars["0:0"].set(True)
        app._commit_receiving_inner_door_checkbox("0:0")
        assert next(item["stable_id"] for item in app.receiving_inner_doors if item["cell_key"] == "0:0") == upper_id
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_3d_workspace_generates_panels_only_for_checked_outer_doors_and_keeps_guards_green():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        panel_keys = {k for k in designer.designer_workspace.available_parts if k.startswith("inner_door:") and k.endswith(":panel")}
        assert panel_keys == {"inner_door:upper:panel"}
        # A SINGLE receiving cabinet must show its existing real inner-door
        # sheet in the ordinary part menu without opening multi-settings.
        keys = designer.designer_workspace.available_parts
        assert keys.index("inner_door:upper:panel") < keys.index("inner_door:upper:top_frame")
        menu = designer.part_choice_menu
        menu_labels = tuple(
            str(menu.entrycget(i, "label"))
            for i in range(int(menu.index("end")) + 1)
        )
        assert "上層內門門板" in menu_labels
        designer.activate_part("inner_door:upper:panel")
        root.update_idletasks(); root.update()
        hole_button = getattr(designer, "_phase6_inner_door_hole_button", None)
        assert hole_button is not None
        assert hole_button.winfo_exists()
        assert hole_button.cget("text") == "內門開孔編輯"
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()
        assert getattr(designer, "_phase6_inner_door_hole_button", None) is None
        assert "inner_door:upper:panel" not in menu_labels
        assert "inner_door:upper:top_frame" in designer.designer_workspace.available_parts
        divider_keys = {k for k in designer.designer_workspace.available_parts if k.startswith("box_body:divider:")}
        assert len(divider_keys) == 1

        app.receiving_inner_doors.append({
            "stable_id": "lower", "cell_key": "0:1", "included_frame_sides": ["top", "left", "right"]
        })
        payload = app._make_original_fold_designer_snapshot()
        designer._phase6_input_snapshot.update(payload)
        from fold_designer_bridge import _phase6_sync_authoritative_derived_parts
        _phase6_sync_authoritative_derived_parts(designer)
        panel_keys = {k for k in designer.designer_workspace.available_parts if k.startswith("inner_door:") and k.endswith(":panel")}
        assert panel_keys == {"inner_door:upper:panel", "inner_door:lower:panel"}

        app.receiving_inner_doors = [item for item in app.receiving_inner_doors if item["cell_key"] != "0:0"]
        payload = app._make_original_fold_designer_snapshot()
        designer._phase6_input_snapshot.update(payload)
        _phase6_sync_authoritative_derived_parts(designer)
        panel_keys = {k for k in designer.designer_workspace.available_parts if k.startswith("inner_door:") and k.endswith(":panel")}
        assert panel_keys == {"inner_door:lower:panel"}
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass



def test_inner_door_reuses_vault_certified_sheet_rules_and_fixed_19_folds():
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data
    from ae_engine.sheetmetal_part_adapters import (
        build_door_result, DoorFrameEdges,
    )
    from ae_engine.sheetmetal_drawing import structural_result_to_primitives

    snapshot = _receiving_snapshot()
    snapshot.update({
        "door_fold_l": 40.0, "door_fold_r": 30.0,
        "door_fold_t": 21.0, "door_fold_b": 25.0,
    })
    panel = cabinet_family_policy.derive_inner_door_panels(snapshot)[0]
    assert (panel.fold_left, panel.fold_right, panel.fold_top, panel.fold_bottom) == (19.0,) * 4
    expected = build_door_result(
        w=panel.width, h=panel.height, t=panel.thickness,
        fw=25.0, gap_w=0.0, gap_h=0.0,
        fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0,
        frame_edges=DoorFrameEdges(left=False, right=False, top=False, bottom=False),
    )
    inner = build_inner_door_panel_render_data(panel)
    assert tuple(inner.scene.primitives) == tuple(structural_result_to_primitives(expected))
    assert inner.metadata["source_cabinet_family"] == "金庫型"
    assert inner.metadata["door_corner_rule"] == "VAULT_CERTIFIED_FOUR_SIDE"
    assert inner.metadata["inner_door_hole_feature_count"] == 0

def test_inner_door_hole_features_reach_real_vault_cutting_and_dxf(tmp_path):
    from pathlib import Path
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.contracts import ManufacturingContext
    from ae_engine.manufacturing_api import (
        build_inner_door_panel_render_data, save_part_render_data_dxf,
    )
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    import ezdxf

    panel = cabinet_family_policy.derive_inner_door_panels(_receiving_snapshot())[0]
    ctx = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    baseline = build_inner_door_panel_render_data(panel, context=ctx)
    feature = CircleFeature(
        diameter=9.0, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0.0, 0.0),
    )
    edited = build_inner_door_panel_render_data(
        panel, features=(feature,), context=ctx,
    )
    original = [p for p in baseline.scene.primitives if isinstance(p, CirclePrimitive)]
    circles = [p for p in edited.scene.primitives if isinstance(p, CirclePrimitive)]
    assert len(circles) == len(original) + 1
    assert edited.metadata["inner_door_hole_feature_count"] == 1
    assert tuple(edited.fold_guides) == tuple(baseline.fold_guides)
    path = save_part_render_data_dxf(edited, tmp_path / "inner-door-with-user-hole.dxf")
    doc = ezdxf.readfile(path)
    cutting_circles = [
        obj for obj in doc.modelspace()
        if obj.dxftype() == "CIRCLE" and obj.dxf.layer == "CUTTING"
    ]
    original_cutting = [row for row in original if row.layer == "CUTTING"]
    assert len(cutting_circles) == len(original_cutting) + 1


def test_inner_door_editor_reuses_original_vault_hole_editor_and_stashes_per_panel():
    from types import SimpleNamespace
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from gui_modules.application.receiving_inner_door_hole_editor import (
        open_inner_door_hole_editor,
    )

    snapshot = _receiving_snapshot()
    key = cabinet_family_policy.derive_inner_door_panels(snapshot)[0].stable_id
    workspace = Phase6DesignerWorkspace.from_snapshot({
        **snapshot, "existing_parts": ["box_body", key],
        "active_part": key,
    })
    calls = []
    class EditorHost:
        def scene_query(self, *args):  # A bound source for the host bridge.
            return None
        def _open_unified_hole_editor(self, part_key, title, surface, width, height, **kwargs):
            calls.append((part_key, title, surface, width, height, kwargs))
            return "opened-vault-editor"

    host = EditorHost()
    app = SimpleNamespace(
        designer_workspace=workspace, _phase6_input_snapshot=snapshot,
        _scene_query_callback=host.scene_query,
        _load_part_holes=lambda key: calls.append(("reload", key)),
        submit_update_intent=lambda reason, commit: calls.append(("update", reason, commit)),
    )
    assert open_inner_door_hole_editor(app, key) == "opened-vault-editor"
    part_key, title, surface, width, height, kwargs = calls[0]
    assert part_key == key and title.startswith("內門門板")
    assert width == pytest.approx(723.0) and height == pytest.approx(1075.0)
    assert kwargs["baseline_scene"] is not None
    assert kwargs["door_thickness"] == pytest.approx(2.0)
    feature = CircleFeature(diameter=8.0, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0.0, 0.0))
    kwargs["feature_list_override"].append(feature)
    kwargs["sync_callback"]()
    assert workspace.features_for(key) == [feature]
    assert workspace.features_for("box_body") == []
    assert ("update", "geometry", True) in calls
    with pytest.raises(ValueError, match="請先選取"):
        workspace.active_part = "box_body"
        open_inner_door_hole_editor(app, key)

def test_corner_data_inner_door_existing_editor_keeps_active_part_and_feature_owner():
    """View-only selection may open the ORIGINAL editor without swapping parts."""
    from types import SimpleNamespace
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from phase6_designer_workspace import Phase6DesignerWorkspace
    from gui_modules.application.receiving_inner_door_hole_editor import open_inner_door_hole_editor

    snapshot = _receiving_snapshot()
    key = cabinet_family_policy.derive_inner_door_panels(snapshot)[0].stable_id
    workspace = Phase6DesignerWorkspace.from_snapshot({
        **snapshot, "existing_parts": ["box_body", "head", key],
        "active_part": "head",
    })
    calls = []

    class OriginalHost:
        def scene_query(self, *args):
            return None

        def _open_unified_hole_editor(self, *args, **kwargs):
            calls.append(("existing", args, kwargs))
            return "original-vault-hole-editor"

    host = OriginalHost()
    app = SimpleNamespace(
        designer_workspace=workspace, _phase6_input_snapshot=snapshot,
        _scene_query_callback=host.scene_query,
        _phase6_3d_display_mode="corner_data",
        _phase6_corner_data_selected_part_key=key,
        _load_part_holes=lambda part: calls.append(("active-holes", part)),
        submit_update_intent=lambda reason, commit: calls.append(("update", reason, commit)),
        _phase6_refresh_corner_data_unfold_view=lambda: calls.append(("corner-refresh",)),
    )
    assert open_inner_door_hole_editor(
        app, key, from_corner_data=True
    ) == "original-vault-hole-editor"
    assert calls[0][0] == "existing"
    assert calls[0][1][0] == key
    feature = CircleFeature(
        diameter=8.0, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0.0, 0.0)
    )
    calls[0][2]["feature_list_override"].append(feature)
    calls[0][2]["sync_callback"]()
    assert workspace.features_for(key) == [feature]
    assert workspace.features_for("head") == []
    assert workspace.active_part == "head"
    assert ("active-holes", key) not in calls
    assert ("update", "geometry", True) in calls
    assert ("corner-refresh",) in calls

    app._phase6_corner_data_selected_part_key = "head"
    with pytest.raises(ValueError, match="請先選取"):
        open_inner_door_hole_editor(app, key, from_corner_data=True)
    app._phase6_corner_data_selected_part_key = key
    app._phase6_3d_display_mode = "assembly"
    with pytest.raises(ValueError, match="請先選取"):
        open_inner_door_hole_editor(app, key, from_corner_data=True)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_corner_data_inner_door_double_click_opens_original_hole_editor(monkeypatch):
    """Real ttk double-click routes to the existing main-GUI editor."""
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    calls = []
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks()
        root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        designer.activate_part("head")
        bridge._phase6_show_corner_data(designer)
        root.update_idletasks()
        root.update()
        key = "inner_door:upper:panel"
        button = designer.corner_data_part_buttons[key]
        assert button.bind("<Double-Button-1>")

        monkeypatch.setattr(
            app, "_open_unified_hole_editor",
            lambda *args, **kwargs: calls.append((args, kwargs)) or "existing-editor",
        )
        before = designer.designer_workspace.active_part
        button.invoke()  # One click only selects the Corner Data part.
        assert designer._phase6_corner_data_selected_part_key == key
        # Tk rejects synthesising a Double modifier directly; two actual
        # press/release cycles exercise Tk's double-click event recognition.
        for _ in range(2):
            button.event_generate("<ButtonPress-1>", x=5, y=5, when="now")
            button.event_generate("<ButtonRelease-1>", x=5, y=5, when="now")
            root.update()
        root.update_idletasks()
        assert len(calls) == 1
        assert calls[0][0][0] == key
        assert calls[0][1]["baseline_scene"] is not None
        assert designer.designer_workspace.active_part == before
        assert designer._phase6_3d_display_mode == "corner_data"
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
