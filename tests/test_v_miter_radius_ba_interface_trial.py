"""#3317 measured-R/BA trial removes detected true-T crossings without CNC promotion."""
from __future__ import annotations

import math
import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _source(angle=90, mode="RELIEF_HOLE"):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    inputs = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=angle,
        relief_mode=mode, relief_t_factor=1.5,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **inputs,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    outline = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y), Vec2(b.x, 0),
        Vec2(30, 10), Vec2(30, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    return DrawingScene([outline, first, second]), first, second, inputs


def _calibrated(angle=90, *, radius=0.5, k=0.4):
    t = 2
    return dict(
        first_inner_radius_mm=radius,
        second_inner_radius_mm=radius,
        first_bend_allowance_mm=(math.pi / 2) * (radius + k * t),
        second_bend_allowance_mm=math.radians(angle) * (radius + k * t),
        max_permitted_edge_trim_mm=12,
    )


def test_90deg_hole_real_radius_ba_trial_is_source_bound_and_only_uncertified():
    scene, first, second, args = _source(mode="RELIEF_HOLE")
    original = tuple(scene.primitives)
    calibrated = _calibrated()
    trial = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **calibrated,
    )
    assert trial.first_neutral_axis_k == pytest.approx(.4)
    assert trial.second_neutral_axis_k == pytest.approx(.4)
    assert trial.geometry_model.endswith("TRIM_TRIAL")
    assert trial.manufacturing_status.endswith("UNCERTIFIED")
    assert trial.no_detected_noncoplanar_crossings
    assert trial.trimmed_surface_interference_pairs == 0
    assert 0 <= trial.first_edge_trim_mm <= 12
    assert trial.first_flat_trimmed_area_mm2 <= trial.first_flat_source_area_mm2
    assert trial.second_flat_source_area_mm2 > 0
    assert len(trial.first_thick_solid_triangles) > len(trial.first_formed_skin_triangles)
    assert len(trial.second_thick_solid_triangles) > len(trial.second_formed_skin_triangles)
    # This returned CHECK patch is NOT a canonical full-sheet CUTTING source.
    assert all(p.layer in {"BEND", "CUTTING"} for p in scene.primitives)
    assert tuple(scene.primitives) == original
    assert "V_MITER" not in [x.value for x in manufacturing_api.EDITABLE_CORNER_TYPE_IDS] if hasattr(manufacturing_api, "EDITABLE_CORNER_TYPE_IDS") else True


@pytest.mark.parametrize("angle", (90, 120))
def test_measured_radius_change_changes_actual_formed_arc_not_only_metadata(angle):
    scene, first, second, args = _source(angle)
    r1 = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(angle, radius=.5),
    )
    r2 = manufacturing_api.solve_v_miter_radius_ba_interface_trial(
        scene, first, second, **args, **_calibrated(angle, radius=1.0),
    )
    assert r1.second_formed_skin_triangles != r2.second_formed_skin_triangles
    assert r1.manufacturing_status.endswith("UNCERTIFIED")
    assert r2.manufacturing_status.endswith("UNCERTIFIED")


@pytest.mark.parametrize("change", [
    {"first_inner_radius_mm": True},
    {"second_inner_radius_mm": float("nan")},
    {"first_bend_allowance_mm": float("inf")},
    {"first_bend_allowance_mm": .05},
    {"second_bend_allowance_mm": 500},
    {"max_permitted_edge_trim_mm": 0},
])
def test_invalid_measurements_or_missing_allowance_fail_closed(change):
    scene, first, second, args = _source()
    params = _calibrated()
    params.update(change)
    with pytest.raises(GeometryError):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **params,
        )


def test_cannot_use_detached_bend_or_invent_60deg_material_extension():
    scene, first, second, args = _source(90)
    clone = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, clone, second, **args, **_calibrated(),
        )
    scene, first, second, args = _source(60)
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(60),
        )


def test_compensation_does_not_promote_new_corner_type_or_cutting():
    from ae_engine.sheetmetal_geometry_core import CornerTypeId, EDITABLE_CORNER_TYPE_IDS
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4
    with pytest.raises(ValueError):
        CornerTypeId("V_MITER")



def test_real_round_R_thick_joint_rejects_interference_in_original_tip_stock():
    # Independent Engine solver contract, not just the DXF CHECK wrapper.
    # This measured-T/R/BA geometry remains in interference if the actual
    # R-tip stock is preserved, so local mesh success must NOT be published.
    scene, first, second, args = _source(mode="ROUND_R")
    original = tuple(scene.primitives)
    with pytest.raises(GeometryError, match="ROUND_R source-preserving trim still has detected"):
        manufacturing_api.solve_v_miter_radius_ba_interface_trial(
            scene, first, second, **args, **_calibrated(),
        )
    assert tuple(scene.primitives) == original
