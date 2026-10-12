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
    from gui_modules.application.fold_designer_snapshot_projection import _snapshot_base_state

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

        snapshot = _snapshot_base_state(app)
        assert snapshot["receiving_base_plate"] == physical
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
