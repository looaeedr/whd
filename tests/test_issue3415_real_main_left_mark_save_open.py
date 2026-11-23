"""#3415 actual Main Save As -> *new root* Open -> real Designer DXF.

Do not forge a saved snapshot or overwrite missing physical source. Select
the legacy unconfigured Receiving mode through its existing GUI transaction,
then commit LEFT_FLAT_SIDE using the actual settings Apply button. Draw a
real manual MARKING line with the actual Hole Editor button and Tk canvas.
"""
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


@pytest.mark.skipif(os.name != "nt" and not os.environ.get("DISPLAY"),
                    reason="requires native Tk or Xvfb display")
def test_real_main_left_committed_mark_saveas_new_root_open_designer_export(
    tmp_path, monkeypatch,
):
    import gui
    from gui_modules.application.physical_part_hole_editor import (
        open_workspace_sheet_editor,
    )

    path = tmp_path / "real-main-left-marked.p6fold"
    first = tmp_path / "before-main-reopen.dxf"
    second = tmp_path / "after-main-reopen.dxf"
    saved_marks = None
    source_sig = None
    first_dxf_bytes = None

    for roundtrip in (0, 1):
        root = tk.Tk()
        # A real operator's Main window is visible. With withdraw(), the
        # nested editor canvas stays 1x1, so no genuine mouse hit is possible.
        root.geometry("1400x900+0+0")
        root.update_idletasks()
        root.update()
        host = None
        try:
            host = gui.BoxCalculatorGUI(root)
            if roundtrip == 0:
                # Enter by the actual Main "Open" toolbar action using the
                # repo's EXISTING legacy unconfigured Receiving project.
                # No test-built/synthetic snapshot or mode reducer injection.
                unconfigured = (
                    ROOT / "tests" / "fixtures" /
                    "issue1503_legacy_receiving_without_nfb_base.p6fold"
                )
                assert unconfigured.is_file()
                monkeypatch.setattr(
                    filedialog, "askopenfilename",
                    lambda **kw: str(unconfigured),
                )
                host.project_open_button.invoke()
                root.update()
                assert host.project_controller.project_path == str(unconfigured)
                assert host.baseline_var.get() == "受電箱"
                assert "receiving_base_plate" not in read_project(unconfigured)["snapshot"]
                designer = host.open_original_fold_designer()
                root.update()
                assert designer._phase6_input_snapshot.get("nfb_config_submitted") is not True
                panel = designer.settings_panel
                panel.invalidate_context("base_plate")
                rendered = panel.render_context("base_plate")
                fields = rendered["extension_state"]["receiving_base_plate_vars"]
                for key, value in LEFT.items():
                    fields[key].set(str(value))
                rendered["extension_state"]["receiving_base_plate_apply_button"].invoke()
                assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT
                # The legacy project legitimately contains no BasePlate at
                # all. A committed source does not silently add a physical
                # part: use the real Designer "新增板件" Tk Menu command.
                assert "base_plate" not in designer.designer_workspace.available_parts
                add_menu = designer.add_part_menu
                plate_rows = [
                    index for index in range(add_menu.index("end") + 1)
                    if add_menu.type(index) == "command"
                    and "底板" in add_menu.entrycget(index, "label")
                ]
                assert len(plate_rows) == 1, "REAL_ADD_BASE_PLATE_MENU_NOT_FOUND"
                add_menu.invoke(plate_rows[0])
                root.update()
                assert "base_plate" in designer.designer_workspace.available_parts
                spec, ctx = _real_part(host)
                assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                assert spec.corner_policy is None
                assert spec.receiving_nfb_depth_pair_mm is None
                assert not spec.seam_positions

                open_workspace_sheet_editor(host, "base_plate")
                editor = host.last_unified_hole_editor
                root.update_idletasks()
                root.update()
                assert editor.winfo_exists() and editor._manual_marking_controls
                canvas = host.last_hole_editor_canvas
                drawing_button = editor._manual_marking_controls[0]
                # Use the *actual* Tk renderer's established transform;
                # never guess pixel layout or manufacture a Feature in test.
                bound = dict(zip(
                    editor._manual_marking_place.__code__.co_freevars,
                    (cell.cell_contents
                     for cell in editor._manual_marking_place.__closure__),
                ))
                state = bound["s"]
                assert canvas.winfo_width() > 100 and canvas.winfo_height() > 100, (
                    "GUI_CANVAS_NOT_LAID_OUT"
                )
                from ae_engine.sheetmetal_features import Vec2
                cx, cy = state.canvas_view.transform.world_to_canvas(
                    Vec2(state.live_context.width / 2, state.live_context.height / 2)
                )
                drawing_button.invoke()
                assert state.manual_mark_mode[0], "GUI_MARK_DRAW_MODE_NOT_ENTERED"
                canvas.event_generate(
                    "<Button-1>", x=round(cx), y=round(cy),
                )
                root.update()
                assert len(tuple(item for item in state.live_context.feature_list
                                 if api.is_manual_mark(item))) == 1, (
                    "GUI_CANVAS_MARK_NOT_INSERTED: " +
                    editor._manual_marking_controls[2].cget("text")
                )
                assert editor._manual_marking_controls[2].cget("text") == ""
                controls = editor._manual_marking_controls
                assert len(controls) == 3
                for child in controls:
                    ancestor = child
                    while ancestor is not None and ancestor is not editor:
                        ancestor = ancestor.master
                    assert ancestor is editor, "MARKING_CHILD_HAS_NO_EDITOR_MASTER_PATH"
                _actual_editor_confirm(editor)
                root.update()
                assert not editor.winfo_exists()
                for name in (
                    "_manual_marking_controls", "_manual_marking_place",
                    "_manual_marking_select",
                ):
                    assert name not in editor.__dict__, (
                        "MARKING_EDITOR_REVERSE_REF_RETAINED: " + name
                    )
                saved_marks = tuple(
                    item for item in designer.designer_workspace.features_for("base_plate")
                    if api.is_manual_mark(item)
                )
                assert len(saved_marks) == 1
                first_spec, first_ctx = _real_part(host)
                assert any(api.is_manual_mark(item) for item in first_spec.features)
                assert first_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                source_sig = (
                    first_spec.model_name, first_spec.width, first_spec.height,
                    first_spec.receiving_bend_pattern, first_spec.bend,
                )
                host._export_authoritative_part(first_spec, first, first_ctx)
                assert first.is_file() and first.stat().st_size > 0
                first_dxf_bytes = first.read_bytes()
                expected_entities = _dxf_entities(first)
                assert api.verify_saved_part_render_data_dxf(
                    host._authoritative_render_data(first_spec, first_ctx), first
                ).ok

                monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
                host.project_save_as_button.invoke()
                assert path.is_file()
                saved = read_project(path)["snapshot"]
                assert saved["receiving_base_plate"] == LEFT
                assert tuple(item for item in saved["part_features"]["base_plate"]
                             if api.is_manual_mark(item)) == saved_marks
                assert tuple(item for item in saved["workspace"]["part_features"]["base_plate"]
                             if api.is_manual_mark(item)) == saved_marks
            else:
                monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
                host.project_open_button.invoke()
                root.update()
                assert host.project_controller.project_path == str(path)
                assert tuple(
                    item for item in host.surface_features["base_plate"]
                    if api.is_manual_mark(item)
                ) == saved_marks
                # This must come from the committed .p6fold -> live Designer
                # hydration. Passing a manually patched payload is forbidden.
                designer = host.open_original_fold_designer()
                root.update()
                assert designer._phase6_input_snapshot["receiving_base_plate"] == LEFT
                reopened_spec, reopened_ctx = _real_part(host)
                assert reopened_spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_LEFT
                assert reopened_spec.corner_policy is None
                assert not reopened_spec.seam_positions
                assert reopened_spec.receiving_nfb_depth_pair_mm is None
                assert tuple(item for item in reopened_spec.features
                             if api.is_manual_mark(item)) == saved_marks
                assert (
                    reopened_spec.model_name, reopened_spec.width,
                    reopened_spec.height, reopened_spec.receiving_bend_pattern,
                    reopened_spec.bend
                ) == source_sig
                host._export_authoritative_part(reopened_spec, second, reopened_ctx)
                assert second.is_file() and second.stat().st_size > 0
                # A separately generated DXF legitimately carries its own
                # ezdxf timestamp/metadata; comparing complete bytes across
                # two separate exports invents a false manufacturing rule.
                # Instead prove earlier output is byte-for-byte untouched,
                # and BOTH files independently reopen to the same geometry.
                assert first.read_bytes() == first_dxf_bytes, (
                    "MAIN_REOPEN_OVERWROTE_OLD_DXF_BYTES"
                )
                assert second.read_bytes() and second != first
                assert _dxf_entities(second) == expected_entities
                assert api.verify_saved_part_render_data_dxf(
                    host._authoritative_render_data(reopened_spec, reopened_ctx), second
                ).ok
        finally:
            if host is not None and host.fold_designer_window is not None:
                try:
                    host.fold_designer_window.destroy()
                except tk.TclError:
                    pass
            root.destroy()


def test_primary_designer_file_menu_opens_marked_a_then_unconfigured_b(
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
        editor._manual_marking_controls[0].invoke()
        canvas.event_generate("<Button-1>", x=round(x), y=round(y))
        root.update()
        assert len(tuple(
            feature for feature in state.live_context.feature_list
            if api.is_manual_mark(feature)
        )) == 1, "PRIMARY_CANVAS_MARK_NOT_INSERTED"
        _actual_editor_confirm(editor)
        root.update()
        assert not editor.winfo_exists()
        marks = tuple(
            f for f in designer.designer_workspace.features_for("base_plate")
            if api.is_manual_mark(f)
        )
        assert len(marks) == 1

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


def test_primary_confirm_scoped_reference_edges_without_gc(tmp_path, monkeypatch):
    """One true Primary A→B probe, no GC/referrer scan or synthetic session.

    Reuse the existing exact GUI workflow. Only intercept *around* its real
    open and Confirm calls to record ownership, then diagnose the state
    graph after that original test has destroyed its Tk root and returned.
    This is a closed, never-merge diagnostic, not an exit132 root-cause proof.
    """
    import sys
    from weakref import ref
    from gui_modules.application import physical_part_hole_editor as physical

    observed = {}
    original_open = physical.open_workspace_sheet_editor
    original_confirm = _actual_editor_confirm

    def named_cells(callback):
        return dict(zip(
            callback.__code__.co_freevars,
            (cell.cell_contents for cell in (callback.__closure__ or ())),
        ))

    def observe_open(host, key):
        result = original_open(host, key)
        assert key == "base_plate" and result is host.last_unified_hole_editor
        editor = result
        canvas = host.last_hole_editor_canvas
        insert = host.last_hole_editor_insert_button
        assert editor.winfo_exists() == 1 and canvas.winfo_exists() == 1

        mark_place = editor._manual_marking_place
        state = named_cells(mark_place)["s"]
        wrapped = state.redraw
        assert named_cells(wrapped)["s"] is state
        original = named_cells(wrapped)["real_redraw"]
        renderer = original.__self__
        assert type(renderer).__name__ == "HoleEditorCanvasRenderer"
        assert named_cells(renderer.context_provider)["s"] is state
        assert state.indicator_redraw[0] is wrapped

        guarded_sync = state.sync_all
        assert named_cells(guarded_sync)["s"] is state
        authoritative_sync = named_cells(guarded_sync)["authoritative_sync"]
        assert authoritative_sync.__self__.sync_callback is None, (
            "PHYSICAL_SHEET_SYNC_IS_DEFERRED_UNTIL_CONFIRM"
        )
        assert state.sync_callback is not None
        assert state.on_confirm_features is not None

        observed["refs"] = {
            "host": ref(host), "editor": ref(editor), "canvas": ref(canvas),
            "insert": ref(insert), "checked_redraw": ref(wrapped),
            "original_renderer": ref(renderer), "guarded_sync": ref(guarded_sync),
            "original_sync": ref(authoritative_sync.__self__),
            "committed_sync": ref(state.sync_callback),
        }
        observed["edges"] = {
            "host_editor": host.last_unified_hole_editor is editor,
            "host_canvas": host.last_hole_editor_canvas is canvas,
            "host_insert": host.last_hole_editor_insert_button is insert,
            "redraw_to_state": named_cells(wrapped)["s"] is state,
            "original_redraw_to_state": (
                named_cells(renderer.context_provider)["s"] is state
            ),
            "sync_to_state": named_cells(guarded_sync)["s"] is state,
            "sync_original_is_deferred": (
                authoritative_sync.__self__.sync_callback is None
            ),
        }
        return result

    def observe_confirm(editor):
        original_confirm(editor)  # actual Tk Button.invoke + Engine commit
        assert not editor.winfo_exists()
        assert all(name not in editor.__dict__ for name in (
            "_manual_marking_controls", "_manual_marking_place",
            "_manual_marking_select",
        ))
        observed["confirmed"] = True

    monkeypatch.setattr(physical, "open_workspace_sheet_editor", observe_open)
    monkeypatch.setattr(sys.modules[__name__], "_actual_editor_confirm", observe_confirm)
    # Exercise full Primary physical LEFT drawing, Save As, File > Open A,
    # authentic manufacturing DXF verification, then File > Open B.
    test_primary_designer_file_menu_opens_marked_a_then_unconfigured_b(
        tmp_path, monkeypatch,
    )
    assert observed["confirmed"] and all(observed["edges"].values())
    refs = observed["refs"]

    def remaining():
        return tuple(sorted(key for key, weak in refs.items() if weak() is not None))

    after_real_destroy = remaining()
    print("WHD_3415_OWNED_AFTER_ROOT_DESTROY", after_real_destroy, flush=True)
    assert {"editor", "canvas", "checked_redraw"}.issubset(after_real_destroy)

    # Phase 1: only exact host aliases, with identity guards. The old
    # editor must never clear a newly-installed editor or its Canvas/button.
    wrapped = refs["checked_redraw"]()
    state = named_cells(wrapped)["s"]
    host = refs["host"]()
    editor = refs["editor"]()
    canvas = refs["canvas"]()
    insert = refs["insert"]()
    for name, target in (
        ("last_unified_hole_editor", editor),
        ("last_hole_editor_canvas", canvas),
        ("last_hole_editor_insert_button", insert),
    ):
        assert getattr(host, name) is target
        if getattr(host, name) is target:
            setattr(host, name, None)
    del host, editor, canvas, insert, wrapped, state
    after_alias = remaining()
    print("WHD_3415_AFTER_IDENTITY_ALIAS_DETACH", after_alias, flush=True)
    assert "checked_redraw" in after_alias, (
        "UNEXPECTED_ALIAS_ONLY_RELEASE_OF_SELF_CLOSING_REDRAW"
    )

    # Phase 2: detach the *named* self-closing redraw and guarded sync
    # edges from this one destroyed editor's composition state.
    wrapped = refs["checked_redraw"]()
    state = named_cells(wrapped)["s"]
    assert state.indicator_redraw[0] is wrapped
    assert state.redraw is wrapped
    assert named_cells(state.sync_all)["s"] is state
    state.indicator_redraw[0] = None
    state.redraw = None
    state.sync_all = None
    state.sync_callback = None
    del state, wrapped
    after_named = remaining()
    print("WHD_3415_AFTER_NAMED_REDRAW_SYNC_DETACH", after_named, flush=True)

    # Phase 3: *diagnostic only*, release this single destroyed editor's
    # transient SimpleNamespace on the same Tk thread. This is NOT a
    # production proposal, does not traverse objects, and calls no GC.
    # It distinguishes additional state-owned closures from host aliases.
    living = refs["guarded_sync"]() or refs["original_renderer"]()
    if living is not None:
        if hasattr(living, "__closure__"):
            state = named_cells(living).get("s")
        else:
            state = named_cells(living.context_provider).get("s")
        if state is not None:
            state.__dict__.clear()
            del state
    del living
    after_scope = remaining()
    print("WHD_3415_AFTER_SINGLE_EDITOR_STATE_RELEASE", after_scope, flush=True)
    # Do not invent a GREEN memory-release verdict or force collection.
    # Printed exact weakref survivors are this probe's observable result.
