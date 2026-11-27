"""#3317 true source CUTTING material boundary for uncertified V-miter trial."""
import math

import ezdxf
import pytest
from shapely.geometry import Polygon, Point

from ae_engine import manufacturing_api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _folds():
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    return first, second


def _params(angle, relief_mode="ROUND_R"):
    return dict(thickness_mm=2, first_flange_height_mm=20,
                second_flange_height_mm=30, second_fold_angle_deg=angle,
                relief_mode=relief_mode)


def _scene_with_real_material(angle, *, rotate=False):
    first, second = _folds()
    temp = DrawingScene([first, second])
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        temp, first, second, **_params(angle)
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    # The actual source outline, not a fabricated rectangle supplied by the
    # projector, extends to both candidate V cut boundary intersections.
    points = (
        Vec2(-100, a.y), Vec2(b.x, a.y),
        Vec2(b.x, 100), Vec2(-100, 100),
    )
    if rotate:
        points = tuple(reversed(points))
    outline = PolylinePrimitive(points, layer="CUTTING", closed=True)
    return DrawingScene([outline, first, second]), outline, first, second


@pytest.mark.parametrize("angle", (60, 90, 120))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_source_outline_clips_v_notch_only_at_actual_perimeter(angle, mode):
    scene, outline, first, second = _scene_with_real_material(angle)
    original = list(scene.primitives)
    trial = manufacturing_api.project_v_miter_source_material_trial(
        scene, first, second, **_params(angle, mode),
    )
    assert trial.manufacturing_status == "V_MITER_TRIAL_CUTTING_UNCERTIFIED"
    assert trial.ideal.source.second_fold_angle_deg == angle
    assert trial.source_material_area_mm2 > trial.remaining_material_area_mm2 > 0
    assert trial.source_material_area_mm2 == pytest.approx(
        trial.remaining_material_area_mm2 + trial.removed_material_area_mm2
    )
    removed = Polygon([(p.x, p.y) for p in trial.removed_corner_outline])
    remainder = Polygon([(p.x, p.y) for p in trial.trial_remaining_outline])
    assert removed.is_valid and remainder.is_valid
    assert removed.intersection(remainder).area == pytest.approx(0, abs=1e-7)
    assert remainder.contains(Point(-50, 50))
    assert scene.primitives == original
    assert [p for p in scene.primitives if p.layer == "CUTTING"] == [outline]


def test_correct_arc_selected_even_when_original_cutting_ring_reversed():
    normal, _, first, second = _scene_with_real_material(90)
    reversed_scene, _, f2, s2 = _scene_with_real_material(90, rotate=True)
    a = manufacturing_api.project_v_miter_source_material_trial(
        normal, first, second, **_params(90)
    )
    b = manufacturing_api.project_v_miter_source_material_trial(
        reversed_scene, f2, s2, **_params(90)
    )
    assert a.removed_material_area_mm2 == pytest.approx(b.removed_material_area_mm2)
    assert a.remaining_material_area_mm2 == pytest.approx(b.remaining_material_area_mm2)


def test_real_cutting_perimeter_mismatch_rejects_invented_sheet_material():
    scene, outline, first, second = _scene_with_real_material(90)
    # Expand the right edge beyond V tip: the alleged V leg ends INSIDE
    # material and can no longer be connected to a real outer edge.
    altered = PolylinePrimitive(tuple(
        Vec2(p.x + 10, p.y) if p.x > 0 else p for p in outline.points
    ), "CUTTING", closed=True)
    scene = DrawingScene([altered, first, second])
    with pytest.raises(GeometryError, match="perimeter"):
        manufacturing_api.project_v_miter_source_material_trial(
            scene, first, second, **_params(90)
        )


def test_trial_must_not_guess_a_holed_multiple_or_open_cutting_shape():
    scene, outline, first, second = _scene_with_real_material(90)
    with pytest.raises(GeometryError, match="exactly one"):
        manufacturing_api.project_v_miter_source_material_trial(
            DrawingScene([outline, outline, first, second]),
            first, second, **_params(90)
        )
    open_outline = PolylinePrimitive(outline.points, layer="CUTTING", closed=False)
    with pytest.raises(GeometryError, match="closed"):
        manufacturing_api.project_v_miter_source_material_trial(
            DrawingScene([open_outline, first, second]),
            first, second, **_params(90)
        )


def test_trial_requires_original_bends_not_equal_looking_copies():
    scene, _, first, second = _scene_with_real_material(90)
    fake = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.project_v_miter_source_material_trial(
            scene, fake, second, **_params(90)
        )


def test_v_trial_outline_can_be_reopened_as_check_preview_but_not_cutting(tmp_path):
    scene, _, first, second = _scene_with_real_material(120)
    trial = manufacturing_api.project_v_miter_source_material_trial(
        scene, first, second, **_params(120)
    )
    # Only diagnostics: the canonical Engine does not generate a CUTTING
    # primitive for this unverified V-miter.  Deliberately use CHECK layer.
    preview = DrawingScene([
        PolylinePrimitive(trial.trial_remaining_outline, layer="CHECK", closed=True)
    ])
    target = tmp_path / "v_miter_unverified_check.dxf"
    save_scene_dxf(target, preview)
    doc = ezdxf.readfile(target)
    geometry = [p for p in doc.modelspace() if p.dxftype() == "LWPOLYLINE"]
    assert len(geometry) == 1 and geometry[0].dxf.layer == "CHECK"
    assert not any(p.dxf.layer == "CUTTING" for p in doc.modelspace())



@pytest.mark.parametrize("angle", (60, 90, 120))
def test_v_miter_check_preview_is_same_source_2d_and_dxf_never_real_cutting(angle, tmp_path):
    scene, outline, first, second = _scene_with_real_material(angle)
    before = list(scene.primitives)
    preview = manufacturing_api.build_v_miter_trial_check_scene(
        scene, first, second, **_params(angle)
    )
    assert preview is not scene
    assert scene.primitives == before
    assert [p.layer for p in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[0].semantic_id == "v_miter_source_reference_only"
    assert preview.primitives[1].semantic_id == "v_miter_uncertified_trial_only"
    candidate = manufacturing_api.project_v_miter_source_material_trial(
        scene, first, second, **_params(angle)
    )
    assert preview.primitives[1].points == candidate.trial_remaining_outline
    path = tmp_path / f"trial_check_{angle}.dxf"
    save_scene_dxf(path, preview)
    reopened = ezdxf.readfile(path)
    entities = list(reopened.modelspace())
    assert len(entities) == 4
    assert [e.dxf.layer for e in entities] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert all(e.dxf.layer not in {"CUTTING", "BEND", "MARKING"} for e in entities)
    target = entities[1]
    assert target.dxftype() == "LWPOLYLINE"
    actual = tuple((x, y) for x, y in target.get_points("xy"))
    expected = tuple((p.x, p.y) for p in candidate.trial_remaining_outline)
    assert len(actual) == len(expected)
    for row, wanted in zip(actual, expected):
        assert row == pytest.approx(wanted)


def test_preview_fail_closed_on_forged_source_and_missing_real_material():
    scene, outline, first, second = _scene_with_real_material(90)
    detached = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.build_v_miter_trial_check_scene(
            scene, detached, second, **_params(90)
        )
    with pytest.raises(GeometryError, match="CUTTING"):
        manufacturing_api.build_v_miter_trial_check_scene(
            DrawingScene([first, second]), first, second, **_params(90)
        )



@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_concave_source_arc_cannot_overhang_outside_wedge_despite_valid_midpoint(
    reverse, mode,
):
    """Old midpoint-only check mistakenly accepts this *valid* stock polygon.

    For 90° BEND, the wedge is x >= 0 and y <= 0. The exterior arc runs
    through (-5,-25), outside the wedge, but the arc midpoint is
    (approximately 16.46,-25), inside it. The cut and remaining material
    are individually valid polygons and their areas balance, so those
    checks cannot replace whole-arc wedge validation.
    """
    first, second = _folds()
    points = (
        Vec2(-100, -20), Vec2(0, -20), Vec2(-5, -25),
        Vec2(20, -25), Vec2(20, 100), Vec2(-100, 100),
    )
    if reverse:
        points = tuple(reversed(points))
    outline = PolylinePrimitive(points, "CUTTING", closed=True)
    assert Polygon([(p.x, p.y) for p in points]).is_valid
    scene = DrawingScene([outline, first, second])
    before = list(scene.primitives)
    with pytest.raises(GeometryError, match="exterior arc leaves.*V cut sector"):
        manufacturing_api.project_v_miter_source_material_trial(
            scene, first, second, **_params(90, mode),
        )
    assert scene.primitives == before


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_overhanging_source_cannot_enter_rounded_or_holed_relief_trial(mode):
    first, second = _folds()
    outline = PolylinePrimitive((
        Vec2(-100, -20), Vec2(0, -20), Vec2(-5, -25),
        Vec2(20, -25), Vec2(20, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    scene = DrawingScene([outline, first, second])
    with pytest.raises(GeometryError, match="exterior arc leaves.*V cut sector"):
        manufacturing_api.project_v_miter_relief_trial(
            scene, first, second,
            **_params(90, mode), relief_t_factor=1.5,
        )
    assert scene.primitives == [outline, first, second]



def test_120_degree_flange_validly_extends_outside_fixed_bend_wedge():
    """Do not regress legitimate asymmetric V which crosses old X=0 crease."""
    scene, _, first, second = _scene_with_real_material(120)
    candidate = manufacturing_api.project_v_miter_source_material_trial(
        scene, first, second, **_params(120),
    )
    apex = candidate.ideal.source.bend_intersection
    first_tip = candidate.ideal.first_flat_miter_ray[1]
    assert first_tip.x < apex.x  # outside fixed +X wedge, yet valid V sector
    assert candidate.remaining_material_area_mm2 > 0
    assert candidate.source_material_area_mm2 == pytest.approx(
        candidate.remaining_material_area_mm2 + candidate.removed_material_area_mm2
    )
