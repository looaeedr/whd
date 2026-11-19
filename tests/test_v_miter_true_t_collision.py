"""#3317 source-clipped V-miter finite-T formed solid collision shadows."""
import math

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _part(*, angle=90, t=2):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    p = dict(
        thickness_mm=t, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=angle,
        relief_mode="RELIEF_HOLE", relief_t_factor=1.5,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **p,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    # Both flanges MUST have physical material at the operator's full
    # heights. The V meets the perimeter at x=b.x, but the taller
    # second flange continues from there to its full 30-mm outer edge.
    outline = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y),
        Vec2(b.x, 0), Vec2(30, 10),
        Vec2(30, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    return DrawingScene([outline, first, second]), first, second, p


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_90_degree_true_t_mesh_reuses_real_source_and_detects_unbevelled_overlap(mode):
    scene, first, second, params = _part()
    params["relief_mode"] = mode
    before = list(scene.primitives)
    result = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, first, second, **params,
    )
    assert result.manufacturing_status == "V_MITER_TRUE_T_COLLISION_UNCERTIFIED"
    assert result.geometry_model == "V_MITER_SOURCE_FINITE_T_SHARP_FOLD_MESH_SHADOW"
    assert result.mating.relief.relief_mode.value == mode
    assert result.first_flange_flat_area_mm2 > 0
    assert result.second_flange_flat_area_mm2 > 0
    assert len(result.first_thick_solid_triangles) > len(result.first_formed_skin_triangles)
    assert len(result.second_thick_solid_triangles) > len(result.second_formed_skin_triangles)
    # Orthogonal, unbevelled 2-mm sheets have true overlapping wall
    # volume beyond the local R/hole root. The shared physical solver must
    # find at least one noncoplanar surface crossing, not a silent "safe".
    assert result.surface_interference_pair_count > 0
    assert result.has_detected_surface_interference
    assert all(math.isfinite(value) for tri in (
        result.first_thick_solid_triangles + result.second_thick_solid_triangles
    ) for xyz in tri for value in xyz)
    assert scene.primitives == before
    assert [x.layer for x in scene.primitives] == ["CUTTING", "BEND", "BEND"]


def test_120_degree_asymmetric_V_has_real_source_matched_thick_fold_panels():
    scene, first, second, params = _part(angle=120)
    solid = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, first, second, **params,
    )
    assert solid.mating.relief.source_trial.ideal.source.second_fold_angle_deg == 120
    assert solid.mating.relief.source_trial.ideal.first_flat_miter_ray[1].x < 0
    assert len(solid.first_formed_skin_triangles) > 0
    assert len(solid.second_formed_skin_triangles) > 0
    # The two finite-T diagnostic solids cannot be treated as certified
    # cutting even when the surface intersection solver returns no hits.
    assert solid.manufacturing_status.endswith("UNCERTIFIED")


def test_60_degree_unbounded_source_bend_needs_material_extension_proof():
    scene, first, second, params = _part(angle=60)
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, first, second, **params,
        )


def _physical_short_first_source(*, mode="RELIEF_HOLE", factor=1.5):
    scene, _, second, params = _part(angle=120)
    short = LinePrimitive(Vec2(-5, 0), Vec2(0, 0), "BEND")
    params = dict(params, relief_mode=mode, relief_t_factor=factor)
    # Preserve the very same original physical CUTTING, and same second
    # BEND owner, replacing only first physical source crease length.
    return DrawingScene([scene.primitives[0], short, second]), short, second, params


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_120_source_continuation_builds_real_true_t_3d_mesh_not_a_virtual_fold(mode):
    scene, short, second, params = _physical_short_first_source(mode=mode)
    extra = LinePrimitive(Vec2(-5, 0), Vec2(-30, 0), "BEND")
    scene.primitives.append(extra)
    before = tuple(scene.primitives)
    thick = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, short, second, **params,
    )
    demanded = 20 / math.sqrt(3)
    assert thick.manufacturing_status == "V_MITER_TRUE_T_COLLISION_UNCERTIFIED"
    # The actual source continues to -30mm, while the theoretical seam
    # stops at -11.547mm: the outboard stock is needed to satisfy the
    # actual 20mm first flange full-height source, not invented beyond it.
    assert thick.first_mesh_source_bend_span_mm == pytest.approx(30)
    assert thick.first_mesh_source_bend_span_mm > demanded > 5
    assert thick.second_mesh_source_bend_span_mm == pytest.approx(100)
    assert thick.first_flange_flat_area_mm2 > 0
    assert thick.first_full_height_source_span_mm > 0
    assert thick.first_formed_skin_triangles
    assert thick.first_thick_solid_triangles
    assert thick.second_thick_solid_triangles
    # Prove exact same 2D/formed-3D finite material as a SINGLE genuinely
    # contiguous source BEND of this length; not a synthetic mesh segment.
    complete = LinePrimitive(Vec2(-30, 0), Vec2(0, 0), "BEND")
    complete_scene = DrawingScene([scene.primitives[0], complete, second])
    full = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        complete_scene, complete, second, **params,
    )
    assert thick.first_mesh_source_bend_span_mm == pytest.approx(
        full.first_mesh_source_bend_span_mm
    )
    assert thick.first_flange_flat_area_mm2 == pytest.approx(
        full.first_flange_flat_area_mm2
    )
    assert thick.second_flange_flat_area_mm2 == pytest.approx(
        full.second_flange_flat_area_mm2
    )
    assert thick.first_formed_skin_triangles == full.first_formed_skin_triangles
    assert thick.second_formed_skin_triangles == full.second_formed_skin_triangles
    assert thick.first_thick_solid_triangles == full.first_thick_solid_triangles
    assert thick.second_thick_solid_triangles == full.second_thick_solid_triangles
    assert scene.primitives == list(before)
    assert [p.layer for p in scene.primitives] == [
        "CUTTING", "BEND", "BEND", "BEND",
    ]


@pytest.mark.parametrize("source_case", ("missing", "gap", "short", "offset", "cross"))
def test_120_never_builds_extended_true_t_without_continuous_real_source_bend(source_case):
    scene, short, second, params = _physical_short_first_source()
    if source_case == "gap":
        extras = [
            LinePrimitive(Vec2(-5, 0), Vec2(-7, 0), "BEND"),
            LinePrimitive(Vec2(-8, 0), Vec2(-30, 0), "BEND"),
        ]
    elif source_case == "short":
        extras = [LinePrimitive(Vec2(-5, 0), Vec2(-7, 0), "BEND")]
    elif source_case == "offset":
        extras = [LinePrimitive(Vec2(-5, 0.001), Vec2(-30, 0.001), "BEND")]
    elif source_case == "cross":
        extras = [LinePrimitive(Vec2(-9, -10), Vec2(-9, 10), "BEND")]
    else:
        extras = []
    scene.primitives.extend(extras)
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, short, second, **params,
        )


def test_120_real_bend_but_removed_post_relief_metal_never_builds_true_t():
    scene, short, second, params = _physical_short_first_source(
        factor=8, mode="RELIEF_HOLE",
    )
    scene.primitives.append(LinePrimitive(Vec2(-5, 0), Vec2(-30, 0), "BEND"))
    check = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, short, second, **params,
    )
    assert check.first_original_bend_continuation_covers is True
    assert check.first_remaining_material_interior_covers is False
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, short, second, **params,
        )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_60_genuine_reverse_direction_bend_never_enters_positive_mesh_domain(mode):
    scene, first, second, params = _part(angle=60)
    params["relief_mode"] = mode
    scene.primitives.append(LinePrimitive(Vec2(0, 0), Vec2(30, 0), "BEND"))
    check = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **params,
    )
    assert check.first_original_bend_continuation_covers is True
    assert check.first_remaining_material_interior_covers is False
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, first, second, **params,
        )


def test_true_thickness_changes_3d_skin_offsets_but_not_2d_source_flange_area():
    scene2, first2, second2, p2 = _part(t=2)
    scene1, first1, second1, p1 = _part(t=1)
    thick = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene2, first2, second2, **p2,
    )
    thin = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene1, first1, second1, **p1,
    )
    assert thick.first_flange_flat_area_mm2 < thin.first_flange_flat_area_mm2
    # Hole radius is 0.75 mm vs 1.5 mm at explicit 1.5*T; actual
    # material and thickened panels must change together.
    assert thick.first_thick_solid_triangles != thin.first_thick_solid_triangles


def test_equal_value_detached_bend_is_not_same_engine_source():
    scene, first, second, params = _part()
    clone = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, clone, second, **params,
        )


def test_no_multiplier_and_no_valid_source_cutting_fail_closed():
    scene, first, second, params = _part()
    unset = dict(params, relief_t_factor=None)
    with pytest.raises(GeometryError, match="explicit trial factor"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, first, second, **unset,
        )
    no_cutting = DrawingScene([first, second])
    with pytest.raises(GeometryError, match="CUTTING"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            no_cutting, first, second, **params,
        )


def test_source_replay_2d_outline_and_3d_solid_are_same_trial():
    scene, first, second, params = _part()
    preview = manufacturing_api.build_v_miter_relief_trial_check_scene(
        scene, first, second, **params,
    )
    shadow = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, first, second, **params,
    )
    assert [p.layer for p in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[1].points == shadow.mating.relief.trial_remaining_outline
    # The generated true-T mesh is a diagnostic response only. Source
    # DrawingScene has not been polluted with a new production CUTTING.
    assert len(scene.primitives) == 3



def test_missing_30mm_source_flange_cannot_pass_true_T_shadow():
    scene, first, second, params = _part(angle=90)
    b = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **params,
    ).second_flat_miter_ray[1]
    a = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **params,
    ).first_flat_miter_ray[1]
    # Same valid V tip on CUTTING perimeter, but all of the second
    # flange physically reaches only x=20, not the requested 30.
    understock = PolylinePrimitive((
        Vec2(-100, a.y), Vec2(b.x, a.y),
        Vec2(b.x, 100), Vec2(-100, 100),
    ), "CUTTING", closed=True)
    incomplete = DrawingScene([understock, first, second])
    before = list(incomplete.primitives)
    assert params["second_flange_height_mm"] == 30
    assert b.x == pytest.approx(20)
    # 2D trial geometry alone is insufficient evidence of full flange
    # stock. The actual finite-T 3D check must refuse the short sheet.
    assert manufacturing_api.project_v_miter_relief_trial(
        incomplete, first, second, **params,
    ).manufacturing_status.endswith("UNCERTIFIED")
    with pytest.raises(GeometryError, match="missing requested full height"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            incomplete, first, second, **params,
        )
    assert incomplete.primitives == before


def test_true_T_shadow_exposes_real_full_height_source_spans():
    scene, first, second, params = _part(angle=90)
    result = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, first, second, **params,
    )
    assert result.first_full_height_source_span_mm > 0
    assert result.second_full_height_source_span_mm > 0
    assert result.first_full_height_source_span_mm <= 100
    assert result.second_full_height_source_span_mm <= 100
    assert result.manufacturing_status.endswith("UNCERTIFIED")


def test_unequal_height_source_does_not_silently_trim_taller_flange():
    scene, first, second, params = _part(angle=120)
    result = manufacturing_api.diagnose_v_miter_true_thickness_collision(
        scene, first, second, **params,
    )
    assert result.mating.relief.source_trial.ideal.source.first_flange_height_mm == 20
    assert result.mating.relief.source_trial.ideal.source.second_flange_height_mm == 30
    assert result.first_full_height_source_span_mm > 0
    assert result.second_full_height_source_span_mm > 0
