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
    assert len(cutting_outlines) == 1
    cutting_x = [float(point.x) for point in cutting_outlines[0].points]
    cutting_y = [float(point.y) for point in cutting_outlines[0].points]
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
