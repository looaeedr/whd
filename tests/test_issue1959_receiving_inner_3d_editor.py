"""#1959 Receiving inner-door 3D→original editor routing, no candidate writes.

Runs in a real WHD Tk primary GUI with a true persisted Quantity Receiving
project. Native FinalScene renderer picks actual mesh, never synthetic hits.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path

import pytest

from ae_engine.receiving_quantity_box import project_common_box
from phase6_project_file import PROJECT_SCHEMA_V2, read_project, write_project
from tests.test_receiving_quantity_inner_door_presence import legacy_quantity_snapshot


def _buttons(widget):
    import tkinter as tk
    for child in widget.winfo_children():
        if isinstance(child, tk.Button):
            yield child
        yield from _buttons(child)


def test_receiving_inner_door_real_3d_pick_opens_original_editor_and_cancels_without_candidate(
    tmp_path,
):
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk display")
    import tkinter as tk
    from matplotlib.backend_bases import MouseButton, MouseEvent
    import numpy as np
    import gui
    import fold_designer_bridge as bridge

    key = "inner_door:upper:panel"
    source = project_common_box(legacy_quantity_snapshot())
    saved = write_project(
        tmp_path / "receiving-quantity-3d-inner-door.p6fold",
        {"schema": PROJECT_SCHEMA_V2, "snapshot": source},
    )
    original_bytes = saved.read_bytes()
    root = tk.Tk()
    root.withdraw()
    app = None
    editor = None
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.load_phase6_project(saved)
        for _ in range(5):
            root.update_idletasks()
            root.update()
        workspace = designer.designer_workspace
        assert key in workspace.available_parts
        original_features = tuple(workspace.features_for(key))
        before_receiving = {
            k: deepcopy(v)
            for k, v in designer._phase6_input_snapshot.items()
            if "candidate" in k or k in ("receiving_quantity_box",)
        }
        # No multi-settings entry was used: the actual physical sheet owns
        # the editor transaction, not any candidate inner-door version.
        designer.activate_part(key)
        designer._phase6_3d_display_mode = "single"
        view = designer.final_scene_view
        assert callable(view._hole_double_click_handler)
        request = bridge._phase6_final_scene_adapter(designer).build_request()
        assert request is not None and request.part_key == key
        assert request.render_data.material.area > 0

        ax = view.renderer.ax3d
        canvas = view.renderer.canvas
        ax.clear()
        triangles = view.render(request)
        assert triangles
        ax.view_init(elev=80, azim=-90)
        canvas.draw()
        picks = [(artist, part)
                 for artist, part in view._hole_pick_artists
                 if artist.get_visible() and artist.axes is ax]
        assert len(picks) == 1 and picks[0][1] == key, (
            "INNER_DOOR_REAL_3D_PANEL_NOT_PICKABLE"
        )
        artist = picks[0][0]
        bbox = ax.bbox
        event = None
        for yy in np.linspace(bbox.y0 + 8, bbox.y1 - 8, 19):
            for xx in np.linspace(bbox.x0 + 8, bbox.x1 - 8, 19):
                candidate = MouseEvent(
                    "button_press_event", canvas, float(xx), float(yy),
                    button=MouseButton.LEFT, dblclick=True,
                )
                if candidate.inaxes is ax and artist.contains(candidate)[0]:
                    event = candidate
                    break
            if event is not None:
                break
        assert event is not None, "INNER_DOOR_TRUE_3D_CANVAS_NO_VISIBLE_PICK"
        assert view.on_hole_mesh_double_click(event) == key
        root.update_idletasks()
        root.update()

        editor = app.last_unified_hole_editor
        assert editor is not None and editor.winfo_exists(), (
            "INNER_DOOR_3D_DBLCLICK_DID_NOT_OPEN_ORIGINAL_EDITOR"
        )
        assert editor._hole_header_cadcraft_draw.cget("text") == "CADCraft 開孔編輯"
        assert editor._receiving_config_frame.winfo_exists()
        assert getattr(editor, "_receiving_settings_mode", None) is None, (
            "INNER_DOOR_3D_EDIT_WRONGLY_OWNS_MULTI_CANDIDATE"
        )
        assert original_features == tuple(workspace.features_for(key))
        cancel = [b for b in _buttons(editor) if b.cget("text") == "取消全部"]
        assert len(cancel) == 1
        cancel[0].invoke()
        root.update_idletasks()
        root.update()
        assert not editor.winfo_exists()
        assert tuple(workspace.features_for(key)) == original_features
        after_receiving = {
            k: deepcopy(v)
            for k, v in designer._phase6_input_snapshot.items()
            if "candidate" in k or k in ("receiving_quantity_box",)
        }
        assert after_receiving == before_receiving, (
            "INNER_DOOR_3D_CANCEL_MODIFIED_CANDIDATE_OR_QUANTITY"
        )
        assert saved.read_bytes() == original_bytes
        assert read_project(saved)["snapshot"]["part_features"].get(key, ()) in ((), [])
        print("REAL_3D_RECEIVING_INNER_DOOR_PHYSICAL_EDITOR_CANCEL_GREEN", flush=True)
    finally:
        if editor is not None:
            try:
                if editor.winfo_exists():
                    editor.destroy()
            except Exception:
                pass
        if app is not None:
            try:
                if app.fold_designer_window is not None:
                    app.fold_designer_window.destroy()
            except Exception:
                pass
        try:
            root.destroy()
        except tk.TclError as exc:
            if "application has been destroyed" not in str(exc):
                raise



def test_receiving_3d_inner_door_original_insert_confirm_saves_physical_not_candidate(
    tmp_path,
):
    """The real editor Confirm All must persist its hole in the physical panel."""
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk display")
    import tkinter as tk
    import gui
    from ae_engine.sheetmetal_features import CircleFeature

    key = "inner_door:upper:panel"
    original = project_common_box(legacy_quantity_snapshot())
    path = write_project(
        tmp_path / "receiving-3d-inner-confirm.p6fold",
        {"schema": PROJECT_SCHEMA_V2, "snapshot": original},
    )
    root = tk.Tk()
    root.withdraw()
    app, editor = None, None
    try:
        app = gui.Phase6PrimaryApplication(root)
        designer = app.load_phase6_project(path)
        for _ in range(5):
            root.update_idletasks()
            root.update()
        workspace = designer.designer_workspace
        assert key in workspace.available_parts
        assert not workspace.features_for(key)
        before_authority = {
            k: deepcopy(v)
            for k, v in designer._phase6_input_snapshot.items()
            if "candidate" in k or k == "receiving_quantity_box"
        }
        designer.activate_part(key)
        view = designer.final_scene_view
        assert callable(view._hole_double_click_handler)
        # #2017 established native 3D inner-door hit-testing on this exact
        # real Quantity project. Here exercise the SAME installed real
        # handler followed by operator insertion and real Confirm All.
        view._hole_double_click_handler(key)
        root.update_idletasks()
        root.update()
        editor = app.last_unified_hole_editor
        assert editor and editor.winfo_exists()
        assert getattr(editor, "_receiving_settings_mode", None) is None

        lists = [
            w for w in editor.winfo_children()
        ]
        def walk(w):
            yield w
            for child in w.winfo_children():
                yield from walk(child)

        catalogs = [
            item for item in walk(editor)
            if isinstance(item, tk.Listbox)
            and "＋ 自訂圓孔" in item.get(0, tk.END)
        ]
        assert len(catalogs) == 1
        catalog = catalogs[0]
        custom = catalog.get(0, tk.END).index("＋ 自訂圓孔")
        catalog.selection_clear(0, tk.END)
        catalog.selection_set(custom)
        catalog.event_generate("<<ListboxSelect>>")
        root.update()
        insert_button = app.last_hole_editor_insert_button
        assert insert_button.cget("text") == "插入"
        insert_button.invoke()
        canvas = app.last_hole_editor_canvas
        root.update()
        width, height = canvas.winfo_width(), canvas.winfo_height()
        assert width > 200 and height > 200
        canvas.event_generate(
            "<Button-1>", x=width // 2, y=height // 2
        )
        canvas.event_generate(
            "<ButtonRelease-1>", x=width // 2, y=height // 2
        )
        root.update()
        pending = editor._receiving_pending_features()
        assert len(pending) == 1 and isinstance(pending[0], CircleFeature), (
            "INNER_DOOR_NATIVE_EDITOR_DID_NOT_INSERT_A_VALID_CIRCLE"
        )
        assert not workspace.features_for(key), (
            "INNER_DOOR_3D_INSERT_PREMATURE_PHYSICAL_COMMIT"
        )
        confirm = [b for b in _buttons(editor) if b.cget("text") == "確定全部"]
        assert len(confirm) == 1
        confirm[0].invoke()
        root.update_idletasks()
        root.update()
        assert not editor.winfo_exists()
        committed = tuple(workspace.features_for(key))
        assert committed == pending and len(committed) == 1
        assert all(isinstance(f, CircleFeature) for f in committed)
        after_authority = {
            k: deepcopy(v)
            for k, v in designer._phase6_input_snapshot.items()
            if "candidate" in k or k == "receiving_quantity_box"
        }
        assert after_authority == before_authority, (
            "INNER_DOOR_3D_CONFIRM_CHANGED_MULTI_CANDIDATE_OR_QUANTITY"
        )
        # Use WHD's original primary-toolbar Save (not a hand-built JSON
        # snapshot) and a real project reload into the Fold Designer.
        app.project_save_button.invoke()
        saved = read_project(path)
        persisted = tuple(saved["snapshot"]["part_features"][key])
        assert persisted == committed, "INNER_DOOR_3D_FEATURE_LOST_ON_PROJECT_SAVE"
        loaded = app.load_phase6_project(path)
        root.update_idletasks()
        root.update()
        assert tuple(loaded.designer_workspace.features_for(key)) == committed, (
            "INNER_DOOR_3D_FEATURE_LOST_ON_PROJECT_REOPEN"
        )
        print("REAL_RECEIVING_3D_INNER_DOOR_CONFIRM_SAVE_RELOAD_GREEN", flush=True)
    finally:
        if editor is not None:
            try:
                if editor.winfo_exists():
                    editor.destroy()
            except Exception:
                pass
        if app is not None:
            try:
                if app.fold_designer_window is not None:
                    app.fold_designer_window.destroy()
            except Exception:
                pass
        try:
            root.destroy()
        except tk.TclError as exc:
            if "application has been destroyed" not in str(exc):
                raise
