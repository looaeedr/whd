# -*- coding: utf-8 -*-
"""#1503 RED: saved legacy project, native Tk GUI, no invented base or NFB flags.

Source: sanitized user's /WHD/受電箱.p6fold (2026-09-09), *not* the
2026-10-19 live Windows project. Preserve this provenance distinction.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import tkinter as tk
from tkinter import ttk

import pytest

from tests.test_issue1503_single_gui_real_tier_2d3d import (
    _pump, _walk, _buttons, _pick_400,
)

FIXTURE = Path(__file__).parent / "fixtures" / "issue1503_legacy_receiving_without_nfb_base.p6fold"
MISSING_MESSAGE = "受電箱實體底板尚未配置"


def test_auto_source_does_not_trigger_legacy_manual_base_warning(monkeypatch):
    """#1502: a genuine resolver result can exist without manual settings."""
    import ae_engine.receiving_base_plate_config as source
    from phase6_final_scene_view import receiving_base_source_display_warnings
    snapshot = {"model": "受電箱", "w": 800, "h": 1600, "d": 350,
                "t": 2, "nfb_config_submitted": True}
    assert "receiving_base_plate" not in snapshot

    monkeypatch.setattr(source, "receiving_base_plate_values",
                        lambda data: {"receiving_bend_pattern": "CENTER_DOUBLE_SIDE_FOLD"})
    assert receiving_base_source_display_warnings(snapshot, "受電箱") == ()

    monkeypatch.setattr(source, "receiving_base_plate_values", lambda data: None)
    missing = receiving_base_source_display_warnings(snapshot, "受電箱")
    assert len(missing) == 1 and "來源不足" in missing[0]
    assert receiving_base_source_display_warnings(snapshot, "金庫型") == ()


def test_fixture_preserves_missing_authorities():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = raw["snapshot"]
    assert raw["schema"] == "phase6-fold-project-v1"
    assert (snap["model"], snap["w"], snap["h"], snap["d"], snap["t"]) == (
        "受電箱", 800, 1600, 350, 2
    )
    assert snap["existing_parts"] == ["box_body", "head", "tail"]
    # Do not inject or manufacture physical source/approval into the fixture.
    for key in ("receiving_base_plate", "nfb_config_submitted", "nfb_config"):
        assert key not in snap



def test_fresh_single_editor_shows_csv_400_and_can_confirm_without_manual_base(tmp_path):
    """Real native Tk: no helper NFB insertion, no manual BasePlate commit."""
    import gui
    import fold_designer_bridge as bridge
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    from ae_engine.receiving_nfb_model_identity import numeric_model_ref
    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        source = tmp_path / "fresh_receiving.p6fold"
        source.write_bytes(FIXTURE.read_bytes())
        designer = app.load_phase6_project(source, open_designer=True)
        _pump(root)
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None
        settings = bridge._phase6_open_receiving_single_settings(designer)
        _pump(root)
        chosen = settings._receiving_multi_setting_list
        chosen.selection_clear(0, tk.END)
        chosen.selection_set(1)
        chosen.event_generate("<<ListboxSelect>>")
        _pump(root)
        _buttons(settings._receiving_multi_settings_host, "編輯")[0].invoke()
        _pump(root)
        editor = app.last_unified_hole_editor
        editor._receiving_config_tabs.select(1)
        _pump(root)
        frame = next(w for w in _walk(editor)
                     if hasattr(w, "_receiving_inner_switch_state") and w.winfo_exists())
        rows = frame._receiving_inner_switch_state["rows"]
        assert rows[0]["assigned"].size() == 1
        assert str(rows[0]["assigned"].get(0)) == "2P400"
        assert rows[1]["assigned"].size() == 0
        # First-time Quantity mode is now source-initialized by the user-
        # requested Receiving Family rule. Re-entering the editor must not
        # create a second copy or pretend the single CSV NFB is only a draft.
        initial = designer.designer_workspace.quantity_model.nfb_config_for_version(
            designer.designer_workspace.quantity_model.selected_version_id
        )
        assert initial and initial["nfb_config_submitted"] is True
        assert len(initial["nfb_config"]["holes"]) == 1
        _buttons(frame, "確定")[0].invoke()
        _pump(root)
        _buttons(editor, "確定全部")[0].invoke()
        _pump(root)
        cfg = designer._phase6_input_snapshot
        assert cfg.get("nfb_config_submitted") is True
        assert cfg.get("receiving_base_plate") is None
        assert cfg["nfb_config"]["layer_count"] == 1
        assert len(cfg["nfb_config"]["holes"]) == 1
        assert cfg["nfb_config"]["holes"][0]["model_filename"] == numeric_model_ref(
            "士林", "2P400"
        )
        actual = receiving_base_plate_values(cfg)
        assert actual is not None
        assert actual["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
        assert actual["h"] == 340
        scene = bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        physical = {p.part_key: p for p in scene.assembly_parts}
        assert "base_plate" in physical
        assert not scene.warnings, scene.warnings
        assert len(scene.formed_fixing_plate_skins) == 2, (
            "SHIHLIN_400_REAL_LEFT_BASE_MUST_HAVE_TWO_SOURCE_EARS"
        )
        # Verify BOTH true source UV contacts in the native SIDE preview,
        # not just the existence of an unrelated root 2D/3D Base Plate.
        from gui_modules.application.receiving_ear_side_2d import (
            present_receiving_ear_side_piece_2d,
        )
        raw_body = physical["box_body"].render_data
        for role in ("left_side", "right_side"):
            piece = next(p for p in raw_body.pieces if p.role == role)
            shown, blocker = present_receiving_ear_side_piece_2d(
                app, raw_body, piece, "box_body:" + role,
            )
            assert blocker is None, blocker
            assert shown.render_data.metadata["ear_side_mark_preview_count"] == 3
        designer._phase6_3d_display_mode = "assembly"
        native_view = designer.final_scene_view
        native_request = bridge._phase6_final_scene_adapter(designer).build_request()
        assert native_request is not None
        native_view.render(native_request)
        assert len(native_view.last_formed_ear_display_ids) == 2
        assert len(native_view.last_receiving_ear_marking_segments) == 6
        # Actual Save As and GUI reopen, not a constructed Python snapshot.
        from unittest.mock import patch
        target = tmp_path / "fresh_single_400_saved.p6fold"
        with patch("tkinter.filedialog.asksaveasfilename", return_value=str(target)):
            saved = designer.save_project_file_as()
        assert saved and target.exists()
        reloaded = app.load_phase6_project(target, open_designer=True)
        _pump(root)
        snap = reloaded._phase6_input_snapshot
        assert snap.get("receiving_base_plate") is None
        assert snap["nfb_config_submitted"] is True
        assert len(snap["nfb_config"]["holes"]) == 1
        assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    finally:
        root.destroy()


def test_saved_project_real_single_confirm_discloses_missing_source(tmp_path):
    """Old code is RED when it silently draws no real base/EAR after Confirm All."""
    import gui
    import fold_designer_bridge as bridge
    import numpy as np
    from PIL import Image

    # Use a writable copy of the real, sanitized old project. Never edit source.
    project = tmp_path / "legacy_receiving.p6fold"
    project.write_bytes(FIXTURE.read_bytes())
    root = tk.Tk()
    root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.load_phase6_project(project, open_designer=True)
        _pump(root)
        snap = designer._phase6_input_snapshot
        assert snap.get("receiving_base_plate") is None
        assert snap.get("nfb_config_submitted") is not True

        # Real native Tk route, not injecting a helper's chosen Base Plate.
        settings = bridge._phase6_open_receiving_single_settings(designer)
        _pump(root)
        selected = settings._receiving_multi_setting_list
        selected.selection_clear(0, tk.END)
        selected.selection_set(1)
        selected.event_generate("<<ListboxSelect>>")
        _pump(root)
        edit = _buttons(settings._receiving_multi_settings_host, "編輯")
        assert len(edit) == 1, "single settings must expose real inner-door editor"
        edit[0].invoke()
        _pump(root)
        editor = app.last_unified_hole_editor
        editor._receiving_config_tabs.select(1)
        _pump(root)
        frame = next(w for w in _walk(editor)
                     if hasattr(w, "_receiving_inner_switch_state") and w.winfo_exists())
        state = frame._receiving_inner_switch_state
        _pick_400(root, state, 0)
        layer_2 = next(w for w in _walk(frame)
                       if isinstance(w, ttk.Radiobutton)
                       and str(w.cget("text")) == "2"
                       and str(w.cget("value")) == "2")
        layer_2.invoke()
        _pump(root)
        _pick_400(root, state, 1)
        _buttons(frame, "確定")[0].invoke()
        _pump(root)
        assert editor._receiving_config_tabs.index(
            editor._receiving_config_tabs.select()
        ) == 0
        _buttons(editor, "確定全部")[0].invoke()
        _pump(root)

        # Source is the two actual 2P400 model selections plus the original
        # numeric CSV, NOT any manually selected base. The certified LEFT
        # blank is now uniquely recognized; it must appear on the real GUI
        # despite the pre-existing legacy project having no base settings.
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None
        # Confirm All must save original operator CSV NFB identities even
        # when physical Base Plate variant is unresolved. NOT MFG approval.
        quantity = designer.designer_workspace.quantity_model
        submitted = quantity.nfb_config_for_version(quantity.selected_version_id)
        assert submitted.get("nfb_config_submitted") is True, (
            "NORMAL_SINGLE_CSV_CONFIRM_LOST_WITHOUT_PHYSICAL_BASE"
        )
        typed = submitted["nfb_config"]
        assert typed["layer_count"] == 2 and len(typed["holes"]) == 2
        assert all(h["manual_x_state"] == "UNVERIFIED_BASIS"
                   for h in typed["holes"])
        assert designer._phase6_input_snapshot.get("nfb_config_submitted") is True
        scene = bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        keys = {p.part_key for p in scene.assembly_parts}
        assert {"base_plate:nfb_layer:0", "base_plate:nfb_layer:1"} <= keys
        for part in scene.assembly_parts:
            if part.part_key.startswith("base_plate:nfb_layer:"):
                assert part.render_data.material.area > 0
                assert part.render_data.metadata["manufacturing_ready"] is False
                assert part.part_key in designer.designer_workspace.available_parts
        assert len(scene.formed_fixing_plate_skins) == 4

        designer._phase6_3d_display_mode = "assembly"
        view = designer.final_scene_view
        request = bridge._phase6_final_scene_adapter(designer).build_request()
        assert request is not None and request.part_key == "assembly"
        view.render(request)
        view.renderer.canvas.draw()
        pixels = np.asarray(view.renderer.canvas.buffer_rgba()).copy()
        assert pixels.ndim == 3 and pixels.shape[2] == 4

        output = os.environ.get("WHD_1503_PROJECT_REPRO_ARTIFACTS")
        if output:
            folder = Path(output)
            folder.mkdir(parents=True, exist_ok=True)
            Image.fromarray(pixels).save(folder / "unconfigured_after_confirm_3d.png")
            (folder / "repro_state.json").write_text(json.dumps({
                "source_configured": True,
                "part_keys": sorted(keys),
                "formed_fixing_plate_count": len(scene.formed_fixing_plate_skins),
                "ear_line_count": len(view.last_receiving_ear_marking_segments),
                "canvas_shape": list(pixels.shape),
            }, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save through the actual application callback, then reopen the
        # resulting .p6fold. Never populate missing physical authority.
        from unittest.mock import patch
        saved_path = tmp_path / "receiving_confirmed_saved.p6fold"
        with patch("tkinter.filedialog.asksaveasfilename", return_value=str(saved_path)):
            saved = designer.save_project_file_as()
        assert saved_path.exists() and saved
        import phase6_project_file
        disk = phase6_project_file.read_project(saved_path)["snapshot"]
        assert disk.get("receiving_base_plate") is None
        assert disk.get("nfb_config_submitted") is True
        assert disk.get("nfb_config") == typed
        app.load_phase6_project(saved_path, open_designer=True)
        _pump(root)
        reloaded_designer = app.fold_designer_app
        assert reloaded_designer._phase6_input_snapshot.get("receiving_base_plate") is None
        assert reloaded_designer._phase6_input_snapshot.get("nfb_config_submitted") is True
        assert reloaded_designer._phase6_input_snapshot.get("nfb_config") == typed
        reloaded_designer._phase6_3d_display_mode = "assembly"
        reloaded_view = reloaded_designer.final_scene_view
        reloaded_request = bridge._phase6_final_scene_adapter(reloaded_designer).build_request()
        assert reloaded_request is not None and reloaded_request.part_key == "assembly"
        reloaded_view.render(reloaded_request)
        reloaded_view.renderer.canvas.draw()
        if output:
            Image.fromarray(
                np.asarray(reloaded_view.renderer.canvas.buffer_rgba()).copy()
            ).save(Path(output) / "unconfigured_after_save_reload_3d.png")
        # Same submitted CSV after Save/Reload must still yield both actual
        # tier sheets, without a fake manually persisted base pattern or a
        # misleading "missing base" warning. Source-invalid jobs retain the
        # separate read-only missing-source diagnostics test.
        restored = bridge._phase6_final_scene_adapter(
            reloaded_designer
        ).query_assembly_render_data()
        restored_keys = {p.part_key for p in restored.assembly_parts}
        assert {"base_plate:nfb_layer:0", "base_plate:nfb_layer:1"} <= restored_keys
        assert len(restored.formed_fixing_plate_skins) == 4
        assert len(reloaded_view.last_receiving_ear_marking_segments) == 12
        labels = [x.get_text() for x in reloaded_view.renderer.ax3d.texts]
        assert not any(MISSING_MESSAGE in x for x in labels), (
            "SOURCE_DERIVED_RECEIVING_BASE_STILL_MISLABELED_UNCONFIGURED"
        )
    finally:
        root.destroy()
