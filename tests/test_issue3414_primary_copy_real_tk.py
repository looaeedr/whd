"""#3414 real Primary target editor: operator chooses saved source file, copy→Undo→DXF."""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import tkinter as tk
from tkinter import filedialog, messagebox

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from phase6_project_file import write_project, read_project, PROJECT_SCHEMA
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet
from tests.test_issue3413_manual_group_engine import _group
from tests.test_issue3413_primary_group_real_tk import (
    _actual_editor_confirm, _real_part,
)
from tests.test_issue2517_baseplate_alias_snapshot_finalscene_dxf_parity import _configured


def test_primary_true_canvas_target_selected_saved_group_copy_undo_reopen_normal_dxf(
    actual_sheet, tmp_path, monkeypatch,
):
    import gui
    from gui_modules.application.physical_part_hole_editor import (
        open_workspace_sheet_editor,
    )

    source = _configured("受電箱")
    group = _group(actual_sheet, kind="quad_l", pattern="dashed", dash=2, gap=5)
    source["part_features"] = {"base_plate": [group]}
    source["workspace"] = {"part_features": {"base_plate": [group]}}
    origin = Path(write_project(
        tmp_path / "source-A.p6fold",
        {"schema": PROJECT_SCHEMA, "snapshot": source},
    ))
    target = _configured("受電箱")
    # Bottom-left corner of the copied group at (150, 110) is (130, 95).
    # The real target already has a CUTTING hole at that point.
    existing_hole = CircleFeature(diameter=12, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
                                  offset=Vec2(130, 95), layer="CUTTING")
    target["part_features"] = {"base_plate": [existing_hole]}
    target["workspace"] = {"part_features": {"base_plate": [existing_hole]}}
    destination = Path(write_project(
        tmp_path / "target-B.p6fold",
        {"schema": PROJECT_SCHEMA, "snapshot": target},
    ))
    final_target = tmp_path / "target-B-copy.p6fold"
    dxf = tmp_path / "target-B-copy.dxf"
    old_id = api.group_parameters(group)["group_id"]

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    root.update()
    try:
        host = gui.Phase6PrimaryApplication(root)
        designer = host.fold_designer_app
        host.load_phase6_project(destination, open_designer=True)
        assert host.fold_designer_window is root
        assert host.project_controller.project_path == str(destination)
        designer._refresh_add_part_menu()
        menu = designer.add_part_menu
        plate_rows = [i for i in range(menu.index("end") + 1)
                      if menu.type(i) == "command"
                      and "底板" in menu.entrycget(i, "label")]
        assert len(plate_rows) == 1
        menu.invoke(plate_rows[0])
        root.update()
        assert "base_plate" in designer.designer_workspace.available_parts
        # The checkout intentionally need not contain the operator's private
        # hole catalogs. Supply one genuine OpenHole CSV through the existing
        # resource-root dependency, not a replacement loader or fake row.
        from ae_engine import ae_endcap
        fixture_root = tmp_path / "catalog-resource"
        catalog_dir = fixture_root / "基準檔" / "開孔"
        catalog_dir.mkdir(parents=True)
        (catalog_dir / "開孔.csv").write_text(
            "器具開孔名稱,加工孔徑尺寸,\nQA圓孔6,6,\n", encoding="utf-8-sig",
        )
        original_resource_path = ae_endcap.get_resource_path
        with monkeypatch.context() as resource_patch:
            resource_patch.setattr(
                ae_endcap, "get_resource_path",
                lambda relative: str(fixture_root / relative)
                if relative == "基準檔" else original_resource_path(relative),
            )
            assert Path(api.operator_hole_catalog_root_path()) == catalog_dir
            open_workspace_sheet_editor(host, "base_plate")
        editor = host.last_unified_hole_editor
        root.update()
        assert editor.winfo_exists() == 1
        copied = getattr(editor, "_manual_group_copy_from_saved", None)
        assert callable(copied), "COPY_MUST_BE_REAL_PRIMARY_HOLE_EDITOR_ACTION"
        state = dict(zip(
            editor._manual_marking_place.__code__.co_freevars,
            (cell.cell_contents for cell in editor._manual_marking_place.__closure__),
        ))["s"]
        # The native Tk controls and real catalog loader are unchanged.
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **kwargs: str(origin),
        )
        def click_target(point):
            px, py = state.canvas_view.transform.world_to_canvas(point)
            world = state.canvas_view.canvas_to_world(round(px), round(py))
            assert world is not None
            state.canvas.event_generate("<ButtonPress-1>", x=round(px), y=round(py))
            state.canvas.event_generate("<ButtonRelease-1>", x=round(px), y=round(py))
            root.update()
            return world

        def choose():
            state.manual_mark_copy_button.invoke()
            root.update()
            assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
            assert "目標群組中心" in state.manual_mark_status.cget("text")

        source_before, target_before = origin.read_bytes(), destination.read_bytes()

        # Keep an unrelated valid hole draft while exercising the real
        # Copy button's file-selection stage (not canvas placement).
        state.selected_catalog_text.set("＋ 自訂圓孔")
        state.var_d.set("6")
        state.var_blind.set(False)
        state.insert_btn.invoke()
        click_target(Vec2(200, 140))
        assert len(state.live_context.feature_list) == 2
        assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
        if state.insert_mode[0]:
            state.insert_btn.invoke()
        root.update()
        unrelated = state.hole_session.snapshot()
        assert str(state.confirm_all_btn.cget("state")) == "normal"

        # Canceling the chooser is not a rejected source.
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: "")
        state.manual_mark_copy_button.invoke()
        root.update()
        state.canvas.event_generate("<Configure>")
        root.update()
        assert not state.manual_mark_status.cget("text")
        assert not state.manual_mark_mode[0]
        assert state.hole_session.snapshot() == unrelated

        # Replace the selected saved source with another valid project
        # containing no manual group, before opening the file chooser.
        clean_source = _configured("受電箱")
        clean_source["part_features"] = {"base_plate": []}
        clean_source["workspace"] = {"part_features": {"base_plate": []}}
        write_project(origin, {"schema": PROJECT_SCHEMA, "snapshot": clean_source})
        clean_bytes = origin.read_bytes()
        assert not read_project(origin)["snapshot"]["part_features"]["base_plate"]
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(origin))
        state.manual_mark_copy_button.invoke()
        root.update()
        selection_warning = state.manual_mark_status.cget("text")
        assert "MANUAL_COPY_SOURCE_GROUP_MISSING" in selection_warning
        assert not state.manual_mark_mode[0]
        state.canvas.event_generate("<Configure>")
        root.update()
        assert state.manual_mark_status.cget("text") == selection_warning
        assert str(state.confirm_all_btn.cget("state")) == "normal"
        assert state.hole_session.snapshot() == unrelated
        assert origin.read_bytes() == clean_bytes
        assert destination.read_bytes() == target_before

        # A deliberate tool selection clears the warning, not the draft.
        state.manual_mark_select_button.invoke()
        root.update()
        assert not state.manual_mark_status.cget("text")
        assert state.hole_session.snapshot() == unrelated
        state.undo_btn.invoke()
        root.update()
        assert tuple(state.live_context.feature_list) == (existing_hole,)
        origin.write_bytes(source_before)

        # Source selection alone never inserts a draft or Undo action.
        depth = state.hole_session.snapshot().undo_depth
        choose()
        assert state.hole_session.snapshot().undo_depth == depth
        state.manual_mark_escape()
        root.update()
        assert state.hole_session.snapshot().undo_depth == depth
        choose()
        state.undo_btn.invoke()
        root.update()
        assert state.hole_session.snapshot().undo_depth == depth
        # A valid source cannot authorize a real hole collision. Configure
        # events and passive redraw must retain the warning and pending source.
        choose()
        click_target(Vec2(150, 110))
        assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
        assert state.hole_session.snapshot().undo_depth == depth
        warning = state.manual_mark_status.cget("text")
        assert "跨板定位被拒絕" in warning and "重新選點" in warning
        state.canvas.event_generate("<Configure>")
        root.update()
        assert state.manual_mark_status.cget("text") == warning
        assert str(state.confirm_all_btn.cget("state")) == "disabled"
        # No second file picker: a new valid click immediately places it.
        click_target(Vec2(200, 140))
        assert len([f for f in state.live_context.feature_list if api.is_manual_group(f)]) == 1
        state.undo_btn.invoke()
        root.update()
        assert tuple(state.live_context.feature_list) == (existing_hole,)
        assert state.hole_session.snapshot().undo_depth == depth

        # Native insert button and ordinary catalog double-click must both
        # abandon the copy before the very first real hole canvas click.
        for route in ("button", "catalog"):
            choose()
            if route == "button":
                state.selected_catalog_text.set("＋ 自訂圓孔")
                state.var_d.set("6")
                state.var_blind.set(False)
                state.insert_btn.invoke()
            else:
                # A real small round catalog opening, not a custom shortcut.
                rows = state.catalog_list.get(0, "end")
                matches = [i for i, label in enumerate(rows)
                           if label in state.catalog_by_label
                           and state.catalog_by_label[label].name == "QA圓孔6"]
                assert len(matches) == 1, "real CSV fixture must populate the Tk catalog"
                index, = matches
                definition = state.catalog_by_label[rows[index]]
                assert (definition.shape, definition.process, definition.diameter) == (
                    "circle", "CUTTING", 6.0,
                )
                state.catalog_list.see(index)
                root.update()
                x, y, w, h = state.catalog_list.bbox(index)
                # Tk synthesizes Double from consecutive real presses.
                for _ in range(2):
                    state.catalog_list.event_generate("<ButtonPress-1>", x=x+3, y=y+h//2)
                    state.catalog_list.event_generate("<ButtonRelease-1>", x=x+3, y=y+h//2)
                root.update()
            assert state.insert_mode[0]
            assert not state.manual_mark_mode[0]
            assert "目標群組中心" not in state.manual_mark_status.cget("text")
            click_target(Vec2(200, 140))
            assert len(state.live_context.feature_list) == 2
            assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
            assert state.live_context.feature_list[-1].layer in ("CUTTING", "BLIND_HOLE")
            if route == "catalog":
                inserted = state.live_context.feature_list[-1]
                assert (inserted.source_type, inserted.layer, inserted.diameter) == (
                    "QA圓孔6", "CUTTING", 6.0,
                )
            state.undo_btn.invoke()
            root.update()
            assert tuple(state.live_context.feature_list) == (existing_hole,)
            if state.insert_mode[0]:
                state.insert_btn.invoke()
            root.update()

        # Saved source changed while waiting for the click.
        choose()
        origin.write_bytes(source_before + b"\n")
        click_target(Vec2(150, 110))
        assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
        assert "SOURCE_SAVED_SOURCE_CHANGED" in state.manual_mark_status.cget("text")
        stale_warning = state.manual_mark_status.cget("text")
        state.canvas.event_generate("<Configure>")
        root.update()
        assert state.manual_mark_status.cget("text") == stale_warning
        origin.write_bytes(source_before)
        assert not state.manual_mark_mode[0]
        click_target(Vec2(200, 140))
        assert not any(api.is_manual_group(f) for f in state.live_context.feature_list)
        choose()
        placed_at = click_target(Vec2(200, 140))
        candidates = [
            f for f in state.live_context.feature_list if api.is_manual_group(f)
        ]
        assert len(candidates) == 1, state.manual_mark_status.cget("text")
        clone = candidates[0]
        clone_id = api.group_parameters(clone)["group_id"]
        assert clone_id != old_id
        assert api.group_parameters(clone)["members"] == api.group_parameters(group)["members"]
        assert (clone.offset.x, clone.offset.y) == pytest.approx(
            (placed_at.x, placed_at.y),
        )
        assert clone.offset != group.offset
        for member_id, point in api.group_member_world_points(clone):
            old = dict(api.group_member_world_points(group))[member_id]
            assert (point.x-old.x, point.y-old.y) == pytest.approx(
                (placed_at.x-group.offset.x, placed_at.y-group.offset.y),
            )

        state.undo_btn.invoke()
        root.update()
        assert not any(api.is_manual_group(f)
                       for f in state.live_context.feature_list)
        choose()
        placed_at = click_target(Vec2(210, 140))
        assert len([f for f in state.live_context.feature_list
                    if api.is_manual_group(f)]) == 1
        # The source and target files are checked again at final Confirm,
        # not merely when the source dialog was first closed.
        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, message, **kw: errors.append(message))
        destination.write_bytes(target_before + b"\n")
        _actual_editor_confirm(editor)
        root.update()
        assert editor.winfo_exists(), errors
        assert errors and "TARGET_SAVED_SOURCE_CHANGED" in errors[-1]
        assert designer.designer_workspace.features_for("base_plate") == [existing_hole]
        destination.write_bytes(target_before)
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists(), errors
        assert origin.read_bytes() == source_before
        assert destination.read_bytes() == target_before
        live = designer.designer_workspace.features_for("base_plate")
        final_mark = next(f for f in live if api.is_manual_group(f))
        assert api.group_parameters(final_mark)["group_id"] != old_id

        monkeypatch.setattr(
            filedialog, "asksaveasfilename", lambda **kwargs: str(final_target),
        )
        project_menu = designer.project_file_menu
        assert "另存" in project_menu.entrycget(2, "label")
        project_menu.invoke(2)
        root.update()
        assert final_target.is_file()
        stored = read_project(final_target)["snapshot"]["part_features"]["base_plate"]
        assert len([f for f in stored if api.is_manual_group(f)]) == 1
        assert existing_hole in stored
        stored_group = next(f for f in stored if api.is_manual_group(f))
        assert api.group_parameters(stored_group)["group_id"] == api.group_parameters(final_mark)["group_id"]
        assert (stored_group.offset.x, stored_group.offset.y) == pytest.approx(
            (placed_at.x, placed_at.y),
        )

        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **kwargs: str(final_target),
        )
        project_menu.invoke(0)
        root.update()
        assert host.project_controller.project_path == str(final_target)
        assert host.fold_designer_app is designer
        spec, ctx = _real_part(host)
        assert api.group_parameters(next(f for f in spec.features
                                         if api.is_manual_group(f)))["group_id"] != old_id
        assert host._export_authoritative_part(spec, str(dxf), ctx)
        assert dxf.is_file()
        data = ezdxf.readfile(dxf)
        assert data.header["$INSUNITS"] == 4
        assert {"CUTTING", "BEND", "MARKING"} <= {
            row.dxf.layer for row in data.modelspace()
        }
        render = api.build_part_render_data(spec, ctx)
        assert api.verify_saved_part_render_data_dxf(render, dxf).ok
    finally:
        if root.winfo_exists():
            root.destroy()
