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

        # Confirm All is an operator action, but a physical plate SOURCE was
        # never selected. Never auto-create it from test-only defaults.
        assert designer._phase6_input_snapshot.get("receiving_base_plate") is None
        scene = bridge._phase6_final_scene_adapter(designer).query_assembly_render_data()
        keys = {p.part_key for p in scene.assembly_parts}
        assert not any(k.startswith("base_plate:nfb_layer:") for k in keys)
        assert scene.formed_fixing_plate_skins == ()

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
                "source_configured": False,
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
        app.load_phase6_project(saved_path, open_designer=True)
        _pump(root)
        reloaded_designer = app.fold_designer_app
        assert reloaded_designer._phase6_input_snapshot.get("receiving_base_plate") is None
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
        # RED on old version: a real operator must not see an unexplained blank.
        labels = [x.get_text() for x in reloaded_view.renderer.ax3d.texts]
        assert any(MISSING_MESSAGE in x for x in labels), (
            "UNCONFIGURED_RECEIVING_BASE_SILENTLY_INVISIBLE: "
            "3D must display a clear missing-source diagnostic, "
            "not fabricate geometry or report 16 theoretical marks"
        )
    finally:
        root.destroy()
