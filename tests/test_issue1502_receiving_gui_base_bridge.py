# -*- coding: utf-8 -*-
"""#1502: the real GUI adapter consumes a chosen Receiving plate, not box H."""
from pathlib import Path

import pytest

from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
from ae_engine.receiving_base_plate_config import receiving_base_plate_blank_dimensions


def test_real_receiving_gui_base_bridge_and_project_roundtrip(tmp_path):
    import tkinter as tk
    import gui
    import phase6_project_file as project
    from phase6_manufacturing_adapter import build_scene_payload_for_app

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        host = gui.BoxCalculatorGUI(root)
        host.baseline_var.set("受電箱")
        root.update()
        app = host.open_original_fold_designer()
        root.update()
        physical = {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 280.0, "shrink_top": 20.0, "shrink_bottom": 20.0,
            "shrink_left": 85.0, "shrink_right": 85.0, "bend": 20.0,
        }
        app._phase6_input_snapshot["receiving_base_plate"] = physical

        # The actual callback (same adapter used by real 2D/3D/preview) must
        # build a 280-mm nominal physical plate, not a 1600-mm enclosure blank.
        payload = build_scene_payload_for_app(app, "base_plate")
        assert payload["receiving_base_plate"] == physical
        spec, _ = app._part_spec_query_callback("base_plate", payload)
        assert spec.model_name in ("受電箱", "RECEIVING")
        assert spec.receiving_bend_pattern == RECEIVING_BASE_PATTERN_CENTER
        assert spec.height == pytest.approx(280.0)
        assert spec.physical_id == "base_plate"
        data = app._scene_query_callback("base_plate", payload)
        assert data.metadata["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_CENTER
        assert (data.unfolded_topology.width, data.unfolded_topology.height) == pytest.approx((772.0, 240.0))
        assert "receiving_base_plate_unconfigured" not in data.metadata

        snapshot = host._make_original_fold_designer_snapshot()
        assert snapshot["receiving_base_plate"] == physical
        assert snapshot["part_dimensions"]["base_plate"] == {"width": 772.0, "height": 240.0}
        assert receiving_base_plate_blank_dimensions(snapshot) == pytest.approx((772.0, 240.0))
        filename = project.write_project(
            tmp_path / "receiving-physical-base.p6fold",
            {"schema": project.PROJECT_SCHEMA_V2, "snapshot": snapshot},
        )
        restored = project.read_project(filename)["snapshot"]
        assert restored["receiving_base_plate"] == physical
        assert receiving_base_plate_blank_dimensions(restored) == pytest.approx((772.0, 240.0))
    finally:
        if app is not None:
            try:
                app.root.destroy()
            except tk.TclError:
                pass
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_receiving_operator_base_settings_submit_reset_and_real_scene(tmp_path):
    """#1502: choose the existing physical plate in the ACTUAL Tk settings page."""
    import tkinter as tk
    import gui
    import phase6_project_file as project
    from phase6_manufacturing_adapter import build_scene_payload_for_app
    from ae_engine.sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_LEFT,
        RECEIVING_BASE_PATTERN_CENTER,
        RECEIVING_BASE_PATTERN_RIGHT,
    )

    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        host = gui.BoxCalculatorGUI(root)
        host.baseline_var.set("受電箱")
        root.update()
        app = host.open_original_fold_designer()
        root.update()
        assert app._phase6_input_snapshot["model"] in ("受電箱", "RECEIVING")
        app._phase6_input_snapshot.pop("receiving_base_plate", None)
        panel = app.settings_panel
        panel.invalidate_context("base_plate")
        page = panel.render_context("base_plate")
        state = page["extension_state"]
        fields = state["receiving_base_plate_vars"]
        assert fields["pattern"].get() == ""  # No silent family-wide selection.
        assert "未配置" in state["receiving_base_plate_status_var"].get()

        physical = {
            "pattern": RECEIVING_BASE_PATTERN_CENTER,
            "height": 280.0,
            "shrink_top": 20.0, "shrink_bottom": 20.0,
            "shrink_left": 85.0, "shrink_right": 85.0, "bend": 20.0,
        }
        for key, value in physical.items():
            fields[key].set(str(value))
        state["receiving_base_plate_apply_button"].invoke()
        assert app._phase6_input_snapshot["receiving_base_plate"] == physical
        payload = build_scene_payload_for_app(app, "base_plate")
        assert payload["receiving_base_plate"] == physical
        data = app._scene_query_callback("base_plate", payload)
        assert data.metadata["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_CENTER
        assert (data.unfolded_topology.width, data.unfolded_topology.height) == pytest.approx((772, 240))

        # Invalid work cannot partially replace the committed source.
        fields["shrink_left"].set("-1")
        state["receiving_base_plate_apply_button"].invoke()
        assert app._phase6_input_snapshot["receiving_base_plate"] == physical
        assert "失敗" in state["receiving_base_plate_status_var"].get()
        fields["shrink_left"].set("85")
        fields["pattern"].set(RECEIVING_BASE_PATTERN_LEFT)
        state["receiving_base_plate_apply_button"].invoke()
        # CENTER's 772-mm blank cannot be submitted as a flat plate with
        # 670-mm weld-ear holes.  This must fail BEFORE mutating the source.
        assert app._phase6_input_snapshot["receiving_base_plate"] == physical
        assert "失敗" in state["receiving_base_plate_status_var"].get()

        # The flat left/right pattern uses a 710-mm blank at W800:
        # two existing EAR mounts span 670 with the native 20-mm edge inset.
        fields["shrink_left"].set("45")
        fields["shrink_right"].set("45")
        for new_pattern in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT):
            fields["pattern"].set(new_pattern)
            state["receiving_base_plate_apply_button"].invoke()
            assert app._phase6_input_snapshot["receiving_base_plate"]["pattern"] == new_pattern
            assert app._scene_query_callback(
                "base_plate", build_scene_payload_for_app(app, "base_plate")
            ).metadata["receiving_bend_pattern"] == new_pattern

        snapshot = host._make_original_fold_designer_snapshot()
        assert snapshot["receiving_base_plate"]["pattern"] == RECEIVING_BASE_PATTERN_RIGHT
        path = project.write_project(
            tmp_path / "operator-base.p6fold",
            {"schema": project.PROJECT_SCHEMA_V2, "snapshot": snapshot},
        )
        assert project.read_project(path)["snapshot"]["receiving_base_plate"] == snapshot["receiving_base_plate"]

        state["receiving_base_plate_reset_button"].invoke()
        assert "receiving_base_plate" not in app._phase6_input_snapshot
        assert "未配置" in state["receiving_base_plate_status_var"].get()
        assert "receiving_base_plate" not in host._make_original_fold_designer_snapshot()
    finally:
        if app is not None:
            try:
                app.root.destroy()
            except tk.TclError:
                pass
        try:
            root.destroy()
        except tk.TclError:
            pass
