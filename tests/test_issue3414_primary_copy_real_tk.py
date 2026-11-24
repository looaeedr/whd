"""#3414 real Primary target editor: operator chooses saved source file, copy→Undo→DXF."""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import tkinter as tk
from tkinter import filedialog

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
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
    target["part_features"] = {"base_plate": []}
    target["workspace"] = {"part_features": {"base_plate": []}}
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
        # Only the file selector is replaced, not the native Tk controls.
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **kwargs: str(origin),
        )
        state.manual_mark_copy_button.invoke()
        root.update()
        candidates = [
            f for f in state.live_context.feature_list if api.is_manual_group(f)
        ]
        assert len(candidates) == 1, state.manual_mark_status.cget("text")
        clone = candidates[0]
        clone_id = api.group_parameters(clone)["group_id"]
        assert clone_id != old_id
        assert api.group_parameters(clone)["members"] == api.group_parameters(group)["members"]
        assert dict(api.group_member_world_points(clone)) == dict(
            api.group_member_world_points(group)
        )

        state.undo_btn.invoke()
        root.update()
        assert not any(api.is_manual_group(f)
                       for f in state.live_context.feature_list)
        state.manual_mark_copy_button.invoke()
        root.update()
        assert len([f for f in state.live_context.feature_list
                    if api.is_manual_group(f)]) == 1
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
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
        assert api.group_parameters(stored[0])["group_id"] == api.group_parameters(final_mark)["group_id"]

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
    finally:
        if root.winfo_exists():
            root.destroy()
