"""#3413: real Primary group placement/edit/Undo/File menu A→B/mm DXF."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
from phase6_project_file import read_project

ROOT = Path(__file__).resolve().parents[1]
LEFT = {
    "pattern": RECEIVING_BASE_PATTERN_LEFT,
    "height": 340.0,
    "shrink_top": 20.0,
    "shrink_bottom": 20.0,
    "shrink_left": 45.0,
    "shrink_right": 45.0,
    "bend": 20.0,
}


def _actual_editor_confirm(editor):
    def descendants(w):
        for child in w.winfo_children():
            yield child
            yield from descendants(child)
    buttons = [
        item for item in descendants(editor)
        if isinstance(item, tk.Button) and item.cget("text") == "確定全部"
    ]
    assert len(buttons) == 1
    buttons[0].invoke()


def _real_part(host):
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    designer = host.fold_designer_app
    designer.activate_part("base_plate")
    designer.root.update_idletasks()
    designer.root.update()
    payload = build_scene_payload_for_app(designer, "base_plate")
    spec, ctx = host._fold_designer_part_spec_from_payload("base_plate", payload)
    return spec, ctx


def _dxf_entities(path):
    drawing = ezdxf.readfile(path)
    assert drawing.header["$INSUNITS"] == 4
    entities = tuple(sorted(
        (e.dxftype(), e.dxf.layer, tuple(round(float(v), 6) for v in (
            (e.dxf.center.x, e.dxf.center.y, e.dxf.radius)
            if e.dxftype() == "CIRCLE"
            else tuple(coordinate for x, y in e.get_points("xy")
                       for coordinate in (x, y))
            if e.dxftype() == "LWPOLYLINE"
            else ()
        )))
        for e in drawing.modelspace()
        if e.dxftype() in ("CIRCLE", "LWPOLYLINE")
    ))
    assert any(layer == "MARKING" for _, layer, _ in entities)
    # Finite BEND is a DXF LINE, not necessarily a LWPOLYLINE.
    assert any(item.dxf.layer == "BEND" for item in drawing.modelspace())
    assert any(item.dxf.layer == "CUTTING" for item in drawing.modelspace())
    return entities



def test_primary_group_four_l_member_edit_rotate_mirror_undo_save_reopen_dxf_b(
    tmp_path, monkeypatch,
):
    """PyInstaller's real Primary root: File > Open must not destroy Tk.

    Only filename dialogs are replaced. Both project files are created/read
    by the existing .p6fold API; A's LEFT sheet and mark are committed through
    real Designer Settings, Add Part, and Hole Editor Tk controls.
    """
    import gui
    from gui_modules.application.physical_part_hole_editor import (
        open_workspace_sheet_editor,
    )
    from ae_engine.sheetmetal_features import Vec2

    unconfigured = (
        ROOT / "tests" / "fixtures" /
        "issue1503_legacy_receiving_without_nfb_base.p6fold"
    )
    assert unconfigured.is_file()
    assert "receiving_base_plate" not in read_project(unconfigured)["snapshot"]
    marked_path = tmp_path / "primary-A-left-marked.p6fold"
    dxf_path = tmp_path / "primary-A-reopened.dxf"

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    root.update()
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        assert host.fold_designer_window is root
        assert root.winfo_exists() == 1
        assert host._phase6_primary_workspace is True
        assert not hasattr(host, "project_open_button"), (
            "PRIMARY_MUST_NOT_USE_LEGACY_TOOLBAR"
        )
        menu = designer.project_file_menu
        assert menu.type(0) == "command"
        assert menu.entrycget(0, "label") == "開啟"
        assert menu.entrycget(2, "label") == "另存新檔"

        # Prepare A from an EXISTING unconfigured project, never from a
        # test-forged source or a synthesized Designer snapshot.
        host.load_phase6_project(unconfigured, open_designer=True)
        assert root.winfo_exists() == 1
        assert host.fold_designer_app is designer
        panel = designer.settings_panel
        panel.invalidate_context("base_plate")
        rendered = panel.render_context("base_plate")
        fields = rendered["extension_state"]["receiving_base_plate_vars"]
        for key, value in LEFT.items():
            fields[key].set(str(value))
        rendered["extension_state"]["receiving_base_plate_apply_button"].invoke()
        assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT

        assert "base_plate" not in designer.designer_workspace.available_parts
        # Hot-loading the existing unconfigured project into the Primary
        # keeps its original Tk menu. Re-project the *real* missing-part menu
        # before invoking it; no domain state/physical source is fabricated.
        designer._refresh_add_part_menu()
        add_menu = designer.add_part_menu
        plate_rows = [
            i for i in range(add_menu.index("end") + 1)
            if add_menu.type(i) == "command"
            and "底板" in add_menu.entrycget(i, "label")
        ]
        assert len(plate_rows) == 1
        add_menu.invoke(plate_rows[0])
        root.update()
        assert "base_plate" in designer.designer_workspace.available_parts

        open_workspace_sheet_editor(host, "base_plate")
        editor = host.last_unified_hole_editor
        root.update_idletasks()
        root.update()
        assert editor.winfo_exists()
        canvas = host.last_hole_editor_canvas
        bound = dict(zip(
            editor._manual_marking_place.__code__.co_freevars,
            (cell.cell_contents
             for cell in editor._manual_marking_place.__closure__),
        ))
        state = bound["s"]
        assert canvas.winfo_width() > 100 and canvas.winfo_height() > 100
        x, y = state.canvas_view.transform.world_to_canvas(
            Vec2(state.live_context.width / 2, state.live_context.height / 2)
        )
        # Four actual L corners are ONE Tk Session feature, no center ink.
        state.manual_group_spacing_x.set("40")
        state.manual_group_spacing_y.set("30")
        state.manual_group_arm_x.set("12")
        state.manual_group_arm_y.set("12")
        # Native placement semantics for the other three tools before
        # the committed four-corner group: cross at intersection, single L at
        # corner, pair L at group center. Delete each whole group with the
        # original button so final project contains only the four-corner case.
        # Tk Button events use integer pixels. Compare against the EXACT
        # physical world position the Engine receives from that real click,
        # not the pre-rounded nominal display center.
        placement = state.canvas_view.canvas_to_world(round(x), round(y))
        assert placement is not None
        for kind in ("cross", "l", "pair_l"):
            state.manual_group_tools[kind].invoke()
            canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
            root.update()
            interim = tuple(f for f in state.live_context.feature_list if api.is_manual_group(f))
            assert len(interim) == 1, (
                "PRIMARY_GROUP_TOOL_PLACEMENT_FAILED", kind,
                state.manual_group_tool[0], state.manual_mark_mode[0],
                state.manual_mark_status.cget("text"),
            )
            assert api.group_parameters(interim[0])["kind"] == kind
            corners = dict(api.group_member_world_points(interim[0]))
            if kind == "cross":
                assert corners["cross"] == placement
            if kind == "l":
                assert corners["corner"] == placement
            if kind == "pair_l":
                assert (corners["left"].x + corners["right"].x) / 2 == pytest.approx(placement.x)
                assert corners["left"].y == corners["right"].y == pytest.approx(placement.y)
            state.manual_mark_select_button.invoke()
            canvas.event_generate("<Button-1>", x=round(x), y=round(y))
            canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
            root.update()
            assert state.hole_session.selected_index >= 0
            state.delete_btn.invoke()
            root.update()
            assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
        state.manual_group_tools["quad_l"].invoke()
        canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        canvas.event_generate("<ButtonRelease-1>", x=round(x), y=round(y))
        root.update()
        rows = state.live_context.feature_list
        groups = tuple(f for f in rows if api.is_manual_group(f))
        assert len(groups) == 1
        group = groups[0]
        assert group.points == ()
        old_id = api.group_parameters(group)["group_id"]
        original_center = group.offset

        # Single click selects the WHOLE group, double click the stable
        # top-right member: no path allows a single corner to be deleted.
        state.manual_mark_select_button.invoke()
        corner = dict(api.group_member_world_points(group))["top_right"]
        px, py = state.canvas_view.transform.world_to_canvas(corner)
        canvas.event_generate("<Button-1>", x=round(px), y=round(py))
        canvas.event_generate("<ButtonRelease-1>", x=round(px), y=round(py))
        root.update()
        assert state.hole_session.selected_index == rows.index(group)
        # Tk rejects explicitly synthesizing a <Double-Button-1> modifier.
        # Generate two genuine press/release events on the live Canvas so
        # its installed double-click binding is exercised by Tk itself.
        for _ in range(2):
            canvas.event_generate("<ButtonPress-1>", x=round(px), y=round(py))
            canvas.event_generate("<ButtonRelease-1>", x=round(px), y=round(py))
        root.update()
        assert state.manual_group_member.get() == "top_right"
        state.manual_group_offset_x.set("3")
        state.manual_group_offset_y.set("1")
        state.manual_group_apply_offset.invoke()
        root.update()
        group = next(f for f in rows if api.is_manual_group(f))
        assert dict(api.group_member_world_points(group))["top_right"].x == pytest.approx(
            original_center.x + 23)
        assert dict(api.group_member_world_points(group))["top_right"].y == pytest.approx(
            original_center.y + 16)

        state.manual_group_spacing_x.set("60")
        state.manual_group_spacing_y.set("50")
        state.manual_group_apply_size.invoke()
        root.update()
        group = next(f for f in rows if api.is_manual_group(f))
        assert dict(api.group_member_world_points(group))["top_right"].x == pytest.approx(
            original_center.x + 33)
        assert dict(api.group_member_world_points(group))["top_right"].y == pytest.approx(
            original_center.y + 26)
        state.manual_group_angle.set("90")
        state.manual_group_rotate.invoke()
        state.manual_group_mirror.invoke()
        root.update()
        group = next(f for f in rows if api.is_manual_group(f))
        assert dict(api.group_member_world_points(group))["top_right"].x == pytest.approx(
            original_center.x + 26)
        assert dict(api.group_member_world_points(group))["top_right"].y == pytest.approx(
            original_center.y + 33)
        assert api.group_parameters(group)["group_id"] == old_id
        assert api.group_parameters(group)["members"][-1] == ("top_right", 3.0, 1.0)

        # Original Tk delete and Undo controls operate on the whole group.
        assert state.hole_session.selected_index >= 0
        state.delete_btn.invoke()
        root.update()
        assert not any(api.is_manual_group(f) for f in rows)
        state.undo_btn.invoke()
        root.update()
        group = next(f for f in rows if api.is_manual_group(f))
        assert api.group_parameters(group)["group_id"] == old_id
        assert dict(api.group_member_world_points(group))["top_right"].x == pytest.approx(
            original_center.x + 26)

        # Whole-group canvas drag moves the center and survives native Undo.
        cx, cy = state.canvas_view.transform.world_to_canvas(group.offset)
        tx, ty = state.canvas_view.transform.world_to_canvas(
            Vec2(group.offset.x + 5, group.offset.y + 5))
        canvas.event_generate("<Button-1>", x=round(cx), y=round(cy))
        canvas.event_generate("<B1-Motion>", x=round(tx), y=round(ty))
        canvas.event_generate("<ButtonRelease-1>", x=round(tx), y=round(ty))
        root.update()
        moved = next(f for f in rows if api.is_manual_group(f))
        assert moved.offset != original_center
        state.undo_btn.invoke()
        root.update()
        group = next(f for f in rows if api.is_manual_group(f))
        assert group.offset == original_center
        assert api.group_parameters(group)["group_id"] == old_id
        assert len(tuple(f for f in rows if api.is_manual_mark(f))) == 1
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        marks = tuple(
            f for f in designer.designer_workspace.features_for("base_plate")
            if api.is_manual_mark(f)
        )
        assert len(marks) == 1
        assert api.is_manual_group(marks[0])
        assert api.group_parameters(marks[0])["group_id"] == old_id

        # Save with the real Primary File > Save As menu, not old toolbar.
        monkeypatch.setattr(
            filedialog, "asksaveasfilename", lambda **kw: str(marked_path),
        )
        menu.invoke(2)
        assert marked_path.is_file()
        saved = read_project(marked_path)["snapshot"]
        assert saved["receiving_base_plate"] == LEFT
        assert tuple(
            f for f in saved["part_features"]["base_plate"]
            if api.is_manual_mark(f)
        ) == marks

        # True Primary File > Open A. Without the lifecycle root guard this
        # destroys the sole Tk root and causes Tcl/default-root failure.
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **kw: str(marked_path),
        )
        menu.invoke(0)
        root.update()
        assert root.winfo_exists() == 1, "PRIMARY_OPEN_DESTROYED_TK_ROOT"
        assert host.fold_designer_window is root
        assert host.fold_designer_app is designer
        assert host.project_controller.project_path == str(marked_path)
        assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT
        spec, ctx = _real_part(host)
        assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
        assert spec.corner_policy is None
        assert spec.receiving_nfb_depth_pair_mm is None
        assert not spec.seam_positions
        assert tuple(f for f in spec.features if api.is_manual_mark(f)) == marks
        assert api.group_parameters(marks[0])["members"][-1] == ("top_right", 3.0, 1.0)
        host._export_authoritative_part(spec, dxf_path, ctx)
        assert dxf_path.is_file()
        _dxf_entities(dxf_path)  # INSUNITS mm + CUTTING/BEND/MARKING
        document = ezdxf.readfile(dxf_path)
        ink = [
            e for e in document.modelspace()
            if e.dxf.layer == "MARKING"
        ]
        assert ink and all(
            e.dxf.get("linetype", "CONTINUOUS").upper() == "CONTINUOUS"
            for e in ink
        ), "PRIMARY_MARKING_NOT_CONTINUOUS"
        assert api.verify_saved_part_render_data_dxf(
            host._authoritative_render_data(spec, ctx), dxf_path
        ).ok

        # Reopen the ACTUAL editor on A, pick the same stable member and edit
        # its local offset. Native Cancel must restore committed A unchanged.
        open_workspace_sheet_editor(host, "base_plate")
        again = host.last_unified_hole_editor
        root.update()
        stage = dict(zip(
            again._manual_marking_place.__code__.co_freevars,
            (cell.cell_contents
             for cell in again._manual_marking_place.__closure__),
        ))["s"]
        persisted_group = next(
            f for f in stage.live_context.feature_list if api.is_manual_group(f)
        )
        assert api.group_parameters(persisted_group)["group_id"] == old_id
        assert api.group_parameters(persisted_group)["members"][-1] == ("top_right", 3.0, 1.0)
        member_corner = dict(api.group_member_world_points(persisted_group))["top_right"]
        ux, uy = stage.canvas_view.transform.world_to_canvas(member_corner)
        stage.manual_mark_select_button.invoke()
        stage.canvas.event_generate("<Button-1>", x=round(ux), y=round(uy))
        stage.canvas.event_generate("<ButtonRelease-1>", x=round(ux), y=round(uy))
        for _ in range(2):
            stage.canvas.event_generate("<ButtonPress-1>", x=round(ux), y=round(uy))
            stage.canvas.event_generate("<ButtonRelease-1>", x=round(ux), y=round(uy))
        root.update()
        assert stage.manual_group_member.get() == "top_right"
        stage.manual_group_offset_x.set("4")
        stage.manual_group_apply_offset.invoke()
        root.update()
        assert api.group_parameters(next(
            f for f in stage.live_context.feature_list if api.is_manual_group(f)
        ))["members"][-1] == ("top_right", 4.0, 1.0)

        cancel_buttons = []
        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)
        cancel_buttons = [w for w in walk(again)
                          if isinstance(w, tk.Button) and w.cget("text") == "取消全部"]
        assert len(cancel_buttons) == 1
        cancel_buttons[0].invoke()
        root.update()
        assert not again.winfo_exists()
        assert tuple(
            f for f in designer.designer_workspace.features_for("base_plate")
            if api.is_manual_group(f)
        ) == marks
        assert tuple(
            f for f in read_project(marked_path)["snapshot"]["part_features"]["base_plate"]
            if api.is_manual_group(f)
        ) == marks

        # Same Primary instance: File > Open B with no physical BasePlate
        # source. No A pattern, material or manual mark may survive.
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **kw: str(unconfigured),
        )
        menu.invoke(0)
        root.update()
        assert root.winfo_exists() == 1, "PRIMARY_SECOND_OPEN_DESTROYED_ROOT"
        assert host.fold_designer_window is root
        assert host.fold_designer_app is designer
        assert host.project_controller.project_path == str(unconfigured)
        assert "receiving_base_plate" not in host._phase6_input_snapshot
        assert "receiving_base_plate" not in designer._phase6_input_snapshot
        assert "base_plate" not in designer.designer_workspace.available_parts
        assert not any(
            api.is_manual_mark(f)
            for f in host.surface_features.get("base_plate", ())
        ), "PRIMARY_B_RETAINED_A_MARKING"
    finally:
        if root.winfo_exists():
            root.destroy()
