from __future__ import annotations

import os

import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types import receiving


def _snapshot():
    data = receiving.apply_family_defaults({})
    data.update({
        "t": 2.0,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "multi_door_enabled": True,
    })
    return data


def _material_size(render_data):
    minx, miny, maxx, maxy = map(float, render_data.material.bounds)
    return maxx - minx, maxy - miny


def test_receiving_per_door_base_plates_have_authoritative_distinct_placements():
    upper = resolve_assembly_placement(_snapshot(), "base_plate_c1_r1")
    lower = resolve_assembly_placement(_snapshot(), "base_plate_c1_r2")

    assert upper.stable_id == "base_plate_c1_r1"
    assert lower.stable_id == "base_plate_c1_r2"
    assert upper.placement_kind == "receiving_base_plate"
    assert lower.placement_kind == "receiving_base_plate"
    assert upper.relationship == "BASE_PLATE"
    assert lower.relationship == "BASE_PLATE"
    assert upper.world_offset == pytest.approx((0.0, 250.0, 0.0))
    assert lower.world_offset == pytest.approx((0.0, -550.0, 0.0))
    assert upper.world_offset != lower.world_offset
    assert resolve_assembly_placement(_snapshot(), "base_plate_c1_r1") == upper


@pytest.mark.skipif(not (os.name == "nt" or os.environ.get("DISPLAY")), reason="需要 Tk 顯示環境")
def test_receiving_dynamic_base_plate_dimensions_are_scoped_to_owning_door_cells():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        dims = bridge._phase6_recalculate_part_dimensions(designer)
        assert dims["base_plate_c1_r1"] == {"width": 690.0, "height": 990.0}
        assert dims["base_plate_c1_r2"] == {"width": 690.0, "height": 390.0}
        # Legacy template metadata remains for T13/project compatibility; it is
        # not an available physical part after T19 topology materialization.
        assert dims["base_plate"] == {"width": 690.0, "height": 1490.0}
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


@pytest.mark.skipif(not (os.name == "nt" or os.environ.get("DISPLAY")), reason="需要 Tk 顯示環境")
def test_receiving_dynamic_base_plate_render_blank_uses_cell_nominal_size_plus_55_shrink():
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        snapshot = app._make_original_fold_designer_snapshot()

        upper = app._query_fold_designer_render_data("base_plate_c1_r1", snapshot)
        lower = app._query_fold_designer_render_data("base_plate_c1_r2", snapshot)

        assert _material_size(upper) == pytest.approx((720.0, 1020.0))
        assert _material_size(lower) == pytest.approx((720.0, 420.0))
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def test_receiving_base_plate_placement_keeps_vertical_plate_inside_owning_cell_height():
    from ae_engine.assembly_geometry import place_assembly_triangles

    snapshot = _snapshot()
    cases = (
        ("base_plate_c1_r1", 990.0, (-300.0, 800.0)),
        ("base_plate_c1_r2", 390.0, (-800.0, -300.0)),
    )
    for stable_id, finished_h, cell_bounds in cases:
        placement = resolve_assembly_placement(snapshot, stable_id)
        half_w = 690.0 / 2.0
        half_h = finished_h / 2.0
        local = (
            ((-half_w, -half_h, 0.0), (half_w, -half_h, 0.0), (half_w, half_h, 0.0)),
            ((-half_w, -half_h, 0.0), (half_w, half_h, 0.0), (-half_w, half_h, 0.0)),
        )
        world = place_assembly_triangles(
            local,
            placement.placement_kind,
            (800.0, 1600.0, 350.0),
            placement.world_offset,
        )
        ys = [point[1] for tri in world for point in tri]
        assert min(ys) >= cell_bounds[0] - 1e-6
        assert max(ys) <= cell_bounds[1] + 1e-6
