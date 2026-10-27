from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_main_inner_door_preview_opens_real_hole_editor(tmp_path, monkeypatch):
    """The physical preview opens the editable inner door without switching 3D parts."""
    import tkinter as tk
    import gui
    from gui_modules.editors import hole_editor
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project
    from phase6_receiving_modes import fresh_receiving_mode

    snapshot = fresh_receiving_mode('quantity', {'w': 800, 'h': 1600, 'd': 350, 't': 2})
    path = write_project(tmp_path / 'inner-door.p6fold',
                         {'schema': PROJECT_SCHEMA_V2, 'snapshot': snapshot})
    errors = []
    monkeypatch.setattr(hole_editor.messagebox, 'showerror', lambda *args, **kw: errors.append(args))
    root = tk.Tk()
    app = gui.Phase6PrimaryApplication(root)
    try:
        designer = app.load_phase6_project(path)
        key = 'inner_door:upper:panel'
        assert key in designer.designer_workspace.available_parts
        active_before = designer.designer_workspace.active_part
        # Same public callback bound to the physical preview's double-click.
        app.open_part_hole_editor(key)
        root.update_idletasks()
        root.update()
        assert errors == [], errors
        window = app.last_unified_hole_editor
        assert window.winfo_exists()
        assert '內門門板' in window.title()
        # Verify the actual unified Tk canvas dimension labels, not only the
        # adapter's reference object.
        canvases = []
        pending = [window]
        while pending:
            widget = pending.pop()
            if isinstance(widget, tk.Canvas):
                canvases.append(widget)
            pending.extend(widget.winfo_children())
        labels = [canvas.itemcget(item, "text")
                  for canvas in canvases for item in canvas.find_all()
                  if canvas.type(item) == "text"]
        assert any(label == "W = 800.00 mm" for label in labels), labels
        assert any(label == "H = 1100.00 mm" for label in labels), labels
        assert designer.designer_workspace.active_part == active_before
    finally:
        root.destroy()


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


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
@pytest.mark.parametrize('family,mode,structure', [
    ('受電箱', 'quantity', None), ('受電箱', 'set_bay', None),
    ('金庫型', 'quantity', None), ('分電箱', 'quantity', None),
    ('自由箱型', 'quantity', None),
    ('受電箱', 'quantity', 'two_piece_w_split'),
    ('受電箱', 'quantity', 'three_piece_w_split'),
])
def test_all_receiving_physical_previews_open_real_hole_editors(tmp_path, monkeypatch, family, mode, structure):
    import tkinter as tk
    import gui
    from gui_modules.editors import hole_editor
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project
    from phase6_receiving_modes import fresh_receiving_mode

    if family == '受電箱':
        snapshot = fresh_receiving_mode(mode, {'w': 800, 'h': 1600, 'd': 350, 't': 2})
    else:
        from ae_engine.cabinet_types import policy
        snapshot = policy.apply_fresh_family_defaults({'w': 800, 'h': 1600, 'd': 350, 't': 2}, family)
        snapshot['existing_parts'] = ['box_body', 'head', 'tail', 'door', 'base_plate', 'indicator_box', 'indicator_door']
        snapshot['door_indicator_box_enabled'] = True
    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot(snapshot)
    workspace.add_custom_part(display_name='自訂補強板', fold_axis='X', transverse_length=150)
    snapshot.update(workspace.snapshot())
    if structure is not None:
        from phase6_box_body_structure import normalize_box_body_structure_state
        state = normalize_box_body_structure_state(snapshot.get('box_body_structure'))
        state['active_type'] = structure
        snapshot['box_body_structure'] = state
    from phase6_project_file import PROJECT_SCHEMA_V1
    path = write_project(tmp_path / 'all-parts.p6fold',
                         {'schema': PROJECT_SCHEMA_V2 if family == '受電箱' else PROJECT_SCHEMA_V1,
                          'snapshot': snapshot})
    errors = []
    monkeypatch.setattr(hole_editor.messagebox, 'showerror', lambda *a, **kw: errors.append(a))
    root = tk.Tk()
    host = gui.Phase6PrimaryApplication(root)
    failures = []
    try:
        designer = host.load_phase6_project(path)
        active = designer.designer_workspace.active_part
        import fold_designer_bridge as bridge
        import re
        designer._phase6_3d_display_mode = 'corner_data'
        # Mount the real lazy list panel before rebuilding its real widgets.
        from tkinter import ttk
        designer.corner_data_panel = ttk.Frame(root)
        bridge._phase6_refresh_corner_data_parts_panel(designer)
        for key in designer.designer_workspace.available_parts:
            errors.clear()
            try:
                host.open_part_hole_editor(key)
                window = getattr(host, 'last_unified_hole_editor', None)
                assert not errors, errors
                assert window is not None and window.winfo_exists()
                assert designer.designer_workspace.active_part == active
                window.destroy()
                button = designer.corner_data_part_buttons[key]
                binding = button.bind('<Double-Button-1>')
                command = re.search(r'\[([^\s]+) ', binding)
                assert command is not None, f'缺少板件清單雙擊入口：{key}'
                root.tk.call(command.group(1), 'event')
                window = host.last_unified_hole_editor
                assert window.winfo_exists()
                assert not errors, errors
                assert designer.designer_workspace.active_part == active
            except Exception as exc:
                failures.append((key, str(exc)))
            finally:
                window = getattr(host, 'last_unified_hole_editor', None)
                if window is not None and window.winfo_exists():
                    window.destroy()
        assert not failures, failures
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires Tk display')
def test_derived_sheet_holes_confirm_cancel_reload_and_real_dxf(tmp_path, monkeypatch):
    import tkinter as tk
    import ezdxf
    import gui
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    from phase6_project_file import PROJECT_SCHEMA_V2, write_project, read_project
    from phase6_receiving_modes import fresh_receiving_mode
    from phase6_designer_workspace import Phase6DesignerWorkspace

    snapshot = fresh_receiving_mode('quantity', {'w': 800, 'h': 1600, 'd': 350, 't': 2})
    ws = Phase6DesignerWorkspace.from_snapshot(snapshot)
    ws.add_custom_part(display_name='補強板', fold_axis='Y', transverse_length=150)
    snapshot.update(ws.snapshot())
    path = write_project(tmp_path / 'source.p6fold', {'schema': PROJECT_SCHEMA_V2, 'snapshot': snapshot})
    root = tk.Tk()
    host = gui.Phase6PrimaryApplication(root)
    original_open = host._open_unified_hole_editor
    contexts = []
    def capture(*args, **kwargs):
        contexts.append((args, kwargs))
        return original_open(*args, **kwargs)
    monkeypatch.setattr(host, '_open_unified_hole_editor', capture)
    def button(window, text):
        for child in window.winfo_children():
            if isinstance(child, tk.Button) and child.cget('text') == text:
                return child
            found = button(child, text)
            if found is not None:
                return found
        return None
    try:
        app = host.load_phase6_project(path)
        workspace = app.designer_workspace
        keys = [k for k in workspace.available_parts if
                k == 'base_plate' or k.startswith(('custom:', 'box_body:divider:', 'base_plate:fixing_plate:'))
                or k in {'box_body:left_side', 'box_body:back', 'box_body:right_side'}
                or (k.startswith('inner_door:') and k.endswith('_frame'))]
        assert len(keys) >= 8
        def render_for(key):
            if key in {'box_body:left_side', 'box_body:back', 'box_body:right_side'}:
                body = host._query_fold_designer_render_data('box_body', build_scene_payload_for_app(app, 'box_body'))
                return next(p.render_data for p in body.pieces if f'box_body:{p.role}' == key)
            return host._query_fold_designer_render_data(key, build_scene_payload_for_app(app, key))
        for key in keys:
            baseline = render_for(key)
            point = baseline.material.representative_point()
            feature = CircleFeature(diameter=1, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                                    offset=Vec2(point.x, point.y))
            host.open_part_hole_editor(key)
            contexts[-1][1]['feature_list_override'].append(feature)
            button(host.last_unified_hole_editor, '確定全部').invoke()
            assert workspace.features_for(key) == [feature], key
            edited = render_for(key)
            count = lambda render: sum(isinstance(p, CirclePrimitive) and p.layer == 'CUTTING'
                                       for p in render.scene.primitives)
            assert count(edited) == count(baseline) + 1, key
            assert not edited.material.contains(point), key
            assert tuple(edited.fold_guides) == tuple(baseline.fold_guides)
            output = tmp_path / f'{keys.index(key)}.dxf'
            if key.startswith('base_plate:fixing_plate:'):
                # The Hole Editor may preserve a source-flat fixing-plate
                # feature, but an arbitrary edited preview is NOT the
                # separately source/skin/side-contact-certified folded EAR.
                # The generic DXF output must remain fail-closed.
                with pytest.raises(ValueError, match='BASE_FIXING_PLATE_MANUFACTURING_UNVERIFIED'):
                    save_part_render_data_dxf(edited, output)
                assert not output.exists(), key
            else:
                exported = save_part_render_data_dxf(edited, output)
                circles = [e for e in ezdxf.readfile(exported).modelspace()
                           if e.dxftype() == 'CIRCLE' and e.dxf.layer == 'CUTTING']
                assert any(e.dxf.radius == pytest.approx(.5) and e.dxf.center.x == pytest.approx(point.x)
                           and e.dxf.center.y == pytest.approx(point.y) for e in circles), key
            host.open_part_hole_editor(key)
            contexts[-1][1]['feature_list_override'].clear()
            button(host.last_unified_hole_editor, '取消全部').invoke()
            assert workspace.features_for(key) == [feature], key
        saved = write_project(tmp_path / 'edited.p6fold',
                              {'schema': PROJECT_SCHEMA_V2,
                               'snapshot': host._compose_phase6_project_snapshot_from_main_gui()})
        restored = Phase6DesignerWorkspace.from_snapshot(read_project(saved)['snapshot'])
        for key in keys:
            assert restored.features_for(key) == workspace.features_for(key), key
        assert workspace.features_for('door_c1_r1') == []
        assert workspace.features_for('inner_door:upper:panel') == []
        from phase6_manufacturing_adapter import resolve_for_app
        resolved = resolve_for_app(app)
        for key in keys:
            if key.startswith('box_body:') and not key.startswith('box_body:divider:'):
                final = next(p.render_data for p in resolved.part('box_body').render_data.pieces
                             if f'box_body:{p.role}' == key)
            else:
                final = resolved.part(key).render_data
            assert any(isinstance(p, CirclePrimitive) and p.radius == pytest.approx(.5)
                       for p in final.scene.primitives), key
    finally:
        root.destroy()


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
    # The editor canvas measures the upper 800x1100 cell while the real
    # manufactured sheet remains a 723x1075 unfolded part.
    assert width == pytest.approx(723.0) and height == pytest.approx(1075.0)
    guide = kwargs["reference_guide"]
    assert (guide.width, guide.height) == pytest.approx((800.0, 1100.0))
    assert (guide.min_point.x, guide.min_point.y) == pytest.approx((-38.5, 13.5))
    assert (guide.max_point.x, guide.max_point.y) == pytest.approx((761.5, 1113.5))
    assert kwargs["baseline_scene"] is not None
    assert kwargs["door_thickness"] == pytest.approx(2.0)
    feature = CircleFeature(diameter=8.0, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0.0, 0.0))
    kwargs["feature_list_override"].append(feature)
    kwargs["sync_callback"]()
    # Preview stays in the original editor draft; only main Confirm All
    # commits. Its Cancel All cannot leave a physical inner-door hole.
    assert workspace.features_for(key) == []
    assert ("update", "geometry", True) not in calls
    kwargs["on_confirm_features"]([feature])
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
    assert workspace.features_for(key) == []
    assert workspace.features_for("head") == []
    assert ("update", "geometry", True) not in calls
    calls[0][2]["on_confirm_features"]([feature])
    assert workspace.features_for(key) == [feature]
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


def test_receiving_inner_door_work_area_follows_actual_cell_not_panel_blank():
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, build_door_result
    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, Vec2, feature_is_within_surface,
        feature_surface_from_structural_result, feature_reference_anchor,
        reference_distances,
    )
    from gui_modules.application.receiving_inner_door_hole_editor import inner_door_work_area_guide

    snapshot = _receiving_snapshot()
    snapshot["inner_doors"] = [
        *snapshot["inner_doors"],
        {"stable_id": "lower", "cell_key": "0:1", "included_frame_sides": ["top", "left", "right"]},
    ]
    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)
    for panel in panels:
        structural = build_door_result(
            w=panel.width, h=panel.height, t=panel.thickness,
            fw=25, gap_w=0, gap_h=0,
            fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
            frame_edges=DoorFrameEdges(left=False, right=False, top=False, bottom=False),
        )
        guide = inner_door_work_area_guide(snapshot, panel, structural)
        assert guide.width == pytest.approx(800)
        assert guide.height == pytest.approx(1100 if panel.cell_key == "0:0" else 500)
        # The outer work-area rectangle is ONLY a dimension datum, never an
        # expanded CUTTING surface.
        surface = feature_surface_from_structural_result("door", structural)
        forbidden = CircleFeature(
            diameter=8, anchor=FeatureAnchor.PANEL_CENTER,
            offset=Vec2(guide.min_point.x - structural.width/2 + 2, 0),
        )
        assert not feature_is_within_surface(surface, forbidden, structural.width, structural.height)
        centered = CircleFeature(
            diameter=8, anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(0, 0),
        )
        assert feature_is_within_surface(surface, centered, structural.width, structural.height)
        # Edge-distance input/readout uses the work-cell datum, while the hole
        # keeps its original local manufacturing position and center anchor.
        distances = reference_distances(
            surface, [centered], 0, feature_reference_anchor(centered),
            structural.width, structural.height, reference_guide=guide,
        )
        assert distances.x_edge_distance == pytest.approx(400.0)
        assert distances.y_edge_distance == pytest.approx(524.0 if panel.cell_key == "0:0" else 224.0)


def test_receiving_inner_door_work_area_scales_with_multicolumn_layout():
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.sheetmetal_part_adapters import DoorFrameEdges, build_door_result
    from gui_modules.application.receiving_inner_door_hole_editor import inner_door_work_area_guide

    snap = _receiving_snapshot()
    snap["door_layout_columns"] = [[300.0, [1000.0, 600.0]], [500.0, [1100.0, 500.0]]]
    snap["inner_doors"] = [
        {"stable_id": "right_upper", "cell_key": "1:0"},
        {"stable_id": "left_lower", "cell_key": "0:1"},
    ]
    for panel in cabinet_family_policy.derive_inner_door_panels(snap):
        structural = build_door_result(
            w=panel.width, h=panel.height, t=panel.thickness,
            fw=25, gap_w=0, gap_h=0,
            fold_left=19, fold_right=19, fold_top=19, fold_bottom=19,
            frame_edges=DoorFrameEdges(left=False, right=False, top=False, bottom=False),
        )
        guide = inner_door_work_area_guide(snap, panel, structural)
        assert (guide.width, guide.height) == pytest.approx(
            (500, 1100) if panel.cell_key == "1:0" else (300, 600)
        )


@pytest.mark.parametrize("invalid_id", [True, False])
def test_r4_62_boolean_inner_door_identity_never_becomes_a_panel_part(invalid_id):
    from ae_engine.inner_door_panels import derive_inner_door_panel, inner_door_panel_stable_id
    with pytest.raises(ValueError, match="inner_door_id"):
        derive_inner_door_panel(
            invalid_id, cell_key="0:0", width=723., height=900., thickness=2.,
        )
    with pytest.raises(ValueError, match="inner_door_id"):
        inner_door_panel_stable_id(invalid_id)
    valid = derive_inner_door_panel(
        "upper", cell_key="0:0", width=723., height=900., thickness=2.,
    )
    assert valid.stable_id == "inner_door:upper:panel"
    assert valid.unfolded_width == pytest.approx(757.)


@pytest.mark.parametrize("field", ["stable_id", "cell_key"])
@pytest.mark.parametrize("bad", [True, False])
def test_r5_91_receiving_family_does_not_bypass_boolean_inner_door_identity_gate(field, bad):
    from ae_engine.cabinet_types.receiving import (
        derive_inner_door_panels, derive_inner_door_frame_sets,
    )
    saved = _receiving_snapshot()
    saved["inner_doors"][0][field] = bad
    for derive in (derive_inner_door_panels, derive_inner_door_frame_sets):
        with pytest.raises(ValueError, match="invalid inner-door identity"):
            derive(saved)


@pytest.mark.parametrize("invalid", [True, False])
def test_r5_91_direct_vertical_frame_boolean_selector_must_not_become_text(invalid):
    from ae_engine.cabinet_types.receiving import inner_door_vertical_frame_contract
    snap = _receiving_snapshot()
    with pytest.raises(ValueError, match="invalid inner-door identity"):
        inner_door_vertical_frame_contract(snap, invalid)


@pytest.mark.parametrize("field", ["stable_id", "cell_key"])
@pytest.mark.parametrize("invalid", [True, False])
def test_r5_91_direct_vertical_frame_rejects_corrupt_saved_door_identifiers(field, invalid):
    from ae_engine.cabinet_types.receiving import inner_door_vertical_frame_contract
    snap = _receiving_snapshot()
    snap["inner_doors"][0][field] = invalid
    with pytest.raises(ValueError, match="invalid inner-door identity"):
        inner_door_vertical_frame_contract(snap, "upper")


@pytest.mark.parametrize("field,bad", [
    ("t", True), ("t", False), ("t", float("nan")), ("t", 10 ** 400),
    ("door_gap_w", True), ("door_gap_h", False),
    ("door_gap_w", float("nan")), ("door_gap_h", float("inf")),
    ("door_gap_w", -1.0), ("door_gap_h", -1.0),
    ("door_gap_w", 10 ** 400),
])
def test_manual_r6_inner_door_panel_input_must_be_physical_numeric_before_cast(field, bad):
    """Boolean or nonfinite T / clearance never becomes a real formed panel."""
    from ae_engine.cabinet_types.receiving import derive_inner_door_panels
    snap = _receiving_snapshot()
    snap[field] = bad
    with pytest.raises(ValueError, match="inner-door physical"):
        derive_inner_door_panels(snap)
    assert snap[field] is bad


@pytest.mark.parametrize("bad", [True, False, float("nan"), 10 ** 400])
def test_manual_r6_inner_door_frame_source_thickness_never_casts_boolean(bad):
    from ae_engine.cabinet_types.receiving import derive_inner_door_frame_sets
    snap = _receiving_snapshot()
    snap["t"] = bad
    with pytest.raises(ValueError, match="inner-door physical"):
        derive_inner_door_frame_sets(snap)
    assert snap["t"] is bad


def test_manual_r6_inner_door_thickness_gap_gate_keeps_approved_w800_blank():
    from ae_engine.cabinet_types.receiving import derive_inner_door_panels, derive_inner_door_frame_sets
    snap = _receiving_snapshot()
    panel = derive_inner_door_panels(snap)[0]
    assert panel.thickness == pytest.approx(2.0)
    assert panel.unfolded_width == pytest.approx(723.0)
    assert panel.fold_left == pytest.approx(19.0)
    assert panel.fold_right == pytest.approx(19.0)
    assert derive_inner_door_frame_sets(snap)
