"""#3317: one existing, distant genuine CUTTING circle in Custom Head V CHECK.

Uses a real Tk application and the actual public Engine PartSpec/FinalScene,
never a hand-drawn outline or production fifth-CornerType/DXF source.
"""
from dataclasses import replace
from copy import deepcopy
import json

import pytest
from shapely.geometry import Point, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.contracts import EndCapPartSpec
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from gui_modules.application.endcap_live_v_check_consumer import KEY
from gui_modules.application.endcap_live_v_check_view import (
    close_saved_live_check_window, show_saved_endcap_live_check_window,
)
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


@pytest.fixture
def custom_head_native():
    import tkinter as tk
    from gui import BoxCalculatorGUI

    root = tk.Tk()
    root.withdraw()
    app = BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("head")
        payload = app._make_original_fold_designer_snapshot()
        actual, _ = app._fold_designer_part_spec_from_payload("head", payload)
        assert isinstance(actual, EndCapPartSpec)
        spec = replace(
            actual, width=400, depth=250, thickness=2, frame_width=25,
            fold_left=15, fold_right=15, fold_top=16, fold_bottom=15,
            fold_profile_x=(), fold_profile_y=(), model_name="自訂",
            is_tail=False, holes=(),
        )
        no_hole = api.build_operator_part_render_data(spec)
        yield app, spec, no_hole
    finally:
        close_saved_live_check_window(app)
        root.destroy()


def _feature(dx=0, dy=0):
    return CircleFeature(
        diameter=6, anchor=FeatureAnchor.PANEL_CENTER,
        offset=Vec2(dx, dy), layer="CUTTING",
    )


def _capture(spec, render, mode="ROUND_R"):
    return api.capture_endcap_live_v_miter_check_snapshot(
        spec, render, "bottom_left", first_bend_axis="x",
        relief_mode=mode,
    )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_native_custom_head_distant_circle_kept_in_2d_and_3d_not_claimed(
    custom_head_native, tmp_path, mode,
):
    app, bare_spec, bare = custom_head_native
    no_hole = _capture(bare_spec, bare, mode)
    no_hole_replay = api.replay_endcap_live_v_miter_check_snapshot(
        bare_spec, bare, no_hole,
    )
    assert no_hole_replay.factory_true_t_check is not None
    spec = replace(bare_spec, holes=(_feature(),))
    rendered = api.build_operator_part_render_data(spec)
    original_primitives = tuple(rendered.scene.primitives)
    cutting = [p for p in original_primitives if p.layer == "CUTTING"]
    circles = [p for p in cutting if isinstance(p, CirclePrimitive)]
    outlines = [p for p in cutting if isinstance(p, PolylinePrimitive)]
    assert len(circles) == len(outlines) == 1
    hole = circles[0]
    assert (hole.center.x, hole.center.y, hole.radius) == pytest.approx(
        (211, 162, 3),
    )
    assert len(rendered.material.interiors) == 1
    assert rendered.material.area == pytest.approx(
        Polygon([(p.x, p.y) for p in outlines[0].points]).difference(
            Point(hole.center.x, hole.center.y).buffer(3, quad_segs=32)
        ).area,
        abs=1e-6,
    )
    record = _capture(spec, rendered, mode)
    assert record["source_fold_sha256"] != no_hole["source_fold_sha256"]
    saved = app._compose_phase6_project_snapshot_from_main_gui()
    saved[KEY] = {"head": {"bottom_left": record}}
    path = tmp_path / "original-hole-check.p6fold"
    write_project(path, {"schema": PROJECT_SCHEMA_V1, "snapshot": saved})
    raw = path.read_bytes()
    decoded = read_project(path)["snapshot"]
    assert decoded[KEY]["head"]["bottom_left"] == record
    replay = api.replay_endcap_live_v_miter_check_snapshot(
        spec, rendered, decoded[KEY]["head"]["bottom_left"],
    )
    assert replay.first_bend_axis == "x"
    assert replay.first_physical_bend.p1.x == replay.first_physical_bend.p2.x == 15
    assert replay.second_physical_bend.p1.y == replay.second_physical_bend.p2.y == 41
    assert replay.factory_bottom_relief_check is not None
    assert replay.factory_true_t_check is None
    assert replay.factory_true_t_failure == (
        "V_MITER_LIVE_EXISTING_CUTTING_HOLE_3D_UNSUPPORTED"
    )
    check = replay.full_sheet_check_scene
    assert {p.layer for p in check.primitives} <= {"CHECK", "DATUM"}
    for layer in ("CHECK", "DATUM"):
        inner = [p for p in check.primitives
                 if isinstance(p, CirclePrimitive) and p.layer == layer]
        assert len(inner) == 1
        assert inner[0].center == hole.center
        assert inner[0].radius == hole.radius
    assert tuple(rendered.scene.primitives) == original_primitives
    assert all(p.layer != "CHECK" for p in rendered.scene.primitives)
    win = show_saved_endcap_live_check_window(app, replay, record)
    try:
        win.update()
        assert win.winfo_exists() and win.grab_status() == "local"
        assert len(win._saved_endcap_check_2d_canvas.find_all()) >= 5
        assert "不提供含孔厚板 3D" in win._saved_endcap_check_3d_warning.cget("text")
        assert win._saved_endcap_check_3d_figure is None
        assert win._saved_endcap_check_3d_triangles == ((), ())
    finally:
        close_saved_live_check_window(app)
    assert path.read_bytes() == raw
    assert tuple(rendered.scene.primitives) == original_primitives
    with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
        api.require_no_operator_v_miter_gui_check_for_export({
            "v_miter_gui_check_corners": {"head": {"bottom_left": "V_MITER_CHECK"}},
        })
    moved_spec = replace(bare_spec, holes=(_feature(13, 0),))
    moved = api.build_operator_part_render_data(moved_spec)
    with pytest.raises(GeometryError, match="V_MITER_LIVE_SOURCE_CHANGED"):
        api.replay_endcap_live_v_miter_check_snapshot(moved_spec, moved, record)


def test_native_custom_head_duplicate_or_unverifiable_cutting_rejected(custom_head_native):
    _, bare_spec, bare = custom_head_native
    spec = replace(bare_spec, holes=(_feature(),))
    rendered = api.build_operator_part_render_data(spec)
    valid_record = _capture(spec, rendered)
    circle = next(p for p in rendered.scene.primitives if isinstance(p, CirclePrimitive)
                  and p.layer == "CUTTING")
    # Duplicating a CUTTING primitive can be invisible to a unioned material
    # polygon. The source gate must still see and reject it.
    duplicated = replace(
        rendered, scene=DrawingScene([*rendered.scene.primitives, circle]),
    )
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"):
        _capture(spec, duplicated)
    outer = next(p for p in rendered.scene.primitives if isinstance(p, PolylinePrimitive)
                 and p.layer == "CUTTING")
    ambiguous = replace(
        rendered, scene=DrawingScene([*rendered.scene.primitives, outer]),
    )
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"):
        _capture(spec, ambiguous)
    wrong_material = replace(rendered, material=bare.material)
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"):
        _capture(spec, wrong_material)
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"):
        _capture(replace(spec, holes=()), rendered)
    assert _capture(spec, rendered) == valid_record


@pytest.mark.parametrize("delta", ((-196, -121), (-192, -118)))
def test_native_custom_head_circle_near_left_lower_v_or_relief_rejected(
    custom_head_native, delta,
):
    _, bare_spec, _ = custom_head_native
    spec = replace(bare_spec, holes=(_feature(*delta),))
    rendered = api.build_operator_part_render_data(spec)
    # A close/touching hole cannot be projected as unchanged CHECK material;
    # it may be outside the original trimmed stock or intersect the V/R cut.
    with pytest.raises(GeometryError, match="V_MITER_EXISTING_HOLE_"):
        _capture(spec, rendered)
