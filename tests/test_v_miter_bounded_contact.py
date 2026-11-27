"""Finite BEND / t-thick V-miter preliminary geometry, no manufacturing token."""
import math

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


def _geometry(*, mirror=False, first_length=100, second_length=100, second_to=None):
    sign = -1 if mirror else 1
    first = LinePrimitive(Vec2(-sign * first_length, 0), Vec2(0, 0), "BEND")
    if second_to is None:
        second_to = (0, second_length)
    second = LinePrimitive(Vec2(0, 0), Vec2(sign * second_to[0], second_to[1]), "BEND")
    return DrawingScene([first, second]), first, second


def _params(**override):
    options = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=90,
        relief_mode="ROUND_R",
    )
    options.update(override)
    return options


def test_60_degree_ideal_miter_is_outside_one_original_bend_ray():
    scene, first, second = _geometry()
    result = manufacturing_api.diagnose_v_miter_bounded_bend_reach(
        scene, first, second, **_params(second_fold_angle_deg=60)
    )
    assert result.needs_independent_material_extension_evidence
    assert result.first_axial_seam_reach_mm == pytest.approx(-20 / math.sqrt(3))
    assert result.first_outside_bend_span_mm == pytest.approx(20 / math.sqrt(3))
    assert result.second_outside_bend_span_mm == pytest.approx(0)
    assert result.manufacturing_status == "V_MITER_BOUNDED_CONTACT_UNCERTIFIED"
    with pytest.raises(GeometryError, match="material extension unverified"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, first, second, **_params(second_fold_angle_deg=60)
        )


def _source_stock_with_bends(first, second, *, right=130, left=-130, top=130):
    """A real single closed CUTTING stock, not inferred from a candidate V."""
    cutting = PolylinePrimitive((
        Vec2(left, -70), Vec2(right, -70),
        Vec2(right, top), Vec2(left, top),
    ), "CUTTING", closed=True)
    return DrawingScene([cutting, first, second])


@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_60_degree_source_stock_exists_but_missing_real_first_bend_is_still_blocked(
    mirror, mode,
):
    """Independently show real original stock is NOT a source BEND extension."""
    _, first, second = _geometry(mirror=mirror)
    scene = _source_stock_with_bends(first, second)
    original = list(scene.primitives)
    p = _params(second_fold_angle_deg=60, relief_mode=mode, relief_t_factor=1.5)
    result = manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
        scene, first, second, **p,
    )
    sign = -1 if mirror else 1
    assert result.manufacturing_status == "V_MITER_SOURCE_BEND_EXTENSION_UNCERTIFIED"
    assert result.bounded.needs_independent_material_extension_evidence
    assert result.first_original_stock_covers_extension is True
    assert result.second_original_stock_covers_extension is None
    assert result.second_missing_bend_extension is None
    assert result.bounded.first_outside_bend_span_mm == pytest.approx(20 / math.sqrt(3))
    start, end = result.first_missing_bend_extension
    assert (start.x, start.y) == pytest.approx((0, 0))
    assert (end.x, end.y) == pytest.approx((sign * 20 / math.sqrt(3), 0))
    # Explicitly NOT a permission to move the existing BEND, cut the
    # stock, fit a virtual flange, or publish any manufacturing MARKING.
    assert scene.primitives == original
    with pytest.raises(GeometryError, match="material extension unverified"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, first, second, **p,
        )


def test_60_degree_stock_missing_interior_is_detected_separately_from_bend():
    _, first, second = _geometry()
    p = _params(second_fold_angle_deg=60)
    # The first physical BEND ends at x=0; a negative-axis reach requires
    # +X stock. The original CUTTING here has none, despite valid BEND data.
    no_positive_x = _source_stock_with_bends(first, second, right=0)
    absent = manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
        no_positive_x, first, second, **p,
    )
    assert absent.bounded.first_outside_bend_span_mm > 0
    assert absent.first_original_stock_covers_extension is False
    assert absent.first_missing_bend_extension is not None

    # Even if the hypothetical crease is ON original CUTTING perimeter,
    # a zero-width boundary coincidence cannot count as interior stock.
    first_on_boundary = PolylinePrimitive((
        Vec2(-100, -70), Vec2(130, -70),
        Vec2(130, 0), Vec2(-100, 0),
    ), "CUTTING", closed=True)
    boundary = DrawingScene([first_on_boundary, first, second])
    edge_only = manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
        boundary, first, second, **p,
    )
    assert edge_only.first_original_stock_covers_extension is False


@pytest.mark.parametrize("angle,first_span", ((90, 100), (120, 100), (120, 5)))
def test_original_stock_extension_witness_tracks_actual_finite_bend_end(
    angle, first_span,
):
    _, first, second = _geometry(first_length=first_span)
    scene = _source_stock_with_bends(first, second)
    result = manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
        scene, first, second, **_params(second_fold_angle_deg=angle),
    )
    assert result.manufacturing_status.endswith("UNCERTIFIED")
    if first_span == 5:
        assert result.bounded.first_outside_bend_span_mm == pytest.approx(
            20 / math.sqrt(3) - 5
        )
        start, end = result.first_missing_bend_extension
        assert (start.x, start.y) == pytest.approx((-5, 0))
        assert (end.x, end.y) == pytest.approx((-20 / math.sqrt(3), 0))
        assert result.first_original_stock_covers_extension is True
        with pytest.raises(GeometryError, match="material extension"):
            manufacturing_api.project_v_miter_sharp_thickness_witness(
                scene, first, second,
                **_params(second_fold_angle_deg=angle),
            )
    else:
        assert not result.bounded.needs_independent_material_extension_evidence
        assert result.first_missing_bend_extension is None
        assert result.second_missing_bend_extension is None
        assert result.first_original_stock_covers_extension is None
        assert result.second_original_stock_covers_extension is None


def test_original_stock_crease_witness_never_infers_cutting_or_fake_bend_ownership():
    scene, first, second = _geometry()
    p = _params(second_fold_angle_deg=60)
    with pytest.raises(GeometryError, match="one canonical closed CUTTING"):
        manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
            scene, first, second, **p,
        )
    stock = _source_stock_with_bends(first, second)
    forged = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.diagnose_v_miter_original_stock_crease_extension(
            stock, forged, second, **p,
        )


def _v_source_with_actual_cut(angle, *, first_span=100, mirror=False):
    """Original CUTTING from the same ideal two-fold source (not a fake notch)."""
    _, first, second = _geometry(mirror=mirror, first_length=first_span)
    p = _params(second_fold_angle_deg=angle, relief_t_factor=1.5)
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **p,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    # This is an operator-authored source rectangle that actually has
    # both required V leg tips on its original real CUTTING boundary.
    if mirror:
        points = (
            Vec2(100, a.y), Vec2(b.x, a.y),
            Vec2(b.x, 100), Vec2(100, 100),
        )
    else:
        points = (
            Vec2(-100, a.y), Vec2(b.x, a.y),
            Vec2(b.x, 100), Vec2(-100, 100),
        )
    cut = PolylinePrimitive(points, "CUTTING", closed=True)
    return DrawingScene([cut, first, second]), first, second, p


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("mirror", (False, True))
def test_60_reverse_crease_alternate_real_source_cut_saves_metal_not_virtual_bend(
    tmp_path, mode, mirror,
):
    import ezdxf
    from shapely.geometry import LineString, Polygon
    from ae_engine.dxf_serialization import save_scene_dxf

    scene, first, second, p = _v_source_with_actual_cut(60, mirror=mirror)
    p["relief_mode"] = mode
    sign = -1 if mirror else 1
    scene.primitives.append(LinePrimitive(
        Vec2(0, 0), Vec2(sign * 20, 0), "BEND",
    ))
    before = tuple(scene.primitives)
    original = manufacturing_api.project_v_miter_relief_trial(
        scene, first, second, **p,
    )
    original_stock = Polygon((x.x, x.y) for x in scene.primitives[0].points)
    original_remaining = Polygon(
        (x.x, x.y) for x in original.trial_remaining_outline
    )
    candidate = manufacturing_api.project_v_miter_reverse_crease_asymmetric_cut_trial(
        scene, first, second, **p,
        second_leg_outer_perimeter_retract_mm=6.0,
    )
    revised = Polygon(
        (x.x, x.y) for x in candidate.candidate_remaining_outline
    )
    assert candidate.manufacturing_status == "V_MITER_REVERSE_CREASE_CUT_UNCERTIFIED"
    assert candidate.first_original_stock_covers_extension is True
    assert candidate.first_real_bend_continuation_covers is True
    assert revised.is_valid and revised.geom_type == "Polygon"
    assert original_stock.covers(revised)
    assert revised.area == pytest.approx(candidate.candidate_remaining_area_mm2)
    assert candidate.candidate_remaining_area_mm2 > original.remaining_material_area_mm2
    # Original 60-degree V lies on the back-pointing first BEND extension;
    # the changed, SOURCE PERIMETER-backed V removes less of that metal.
    assert candidate.first_remaining_interior_crease_length_mm > 0
    assert candidate.first_remaining_interior_crease_length_mm > (
        LineString(((0, 0), (sign * 20 / math.sqrt(3), 0)))
        .intersection(original_remaining)
        .difference(original_remaining.boundary.buffer(1e-7)).length
    )
    if mode == "RELIEF_HOLE":
        # An actual hole centred at apex still cuts through the start of
        # the crease; never promote partial physical interior to full.
        assert candidate.first_remaining_interior_covers_extension is False
    assert scene.primitives == list(before)
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.diagnose_v_miter_true_thickness_collision(
            scene, first, second, **p,
        )
    preview = manufacturing_api.build_v_miter_reverse_crease_asymmetric_check_scene(
        scene, first, second, **p,
        second_leg_outer_perimeter_retract_mm=6.0,
    )
    assert [x.layer for x in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[1].points == candidate.candidate_remaining_outline
    dxf = tmp_path / f"reverse_60_{mode}_{mirror}.dxf"
    save_scene_dxf(dxf, preview)
    reopened = tuple(ezdxf.readfile(dxf).modelspace())
    assert [x.dxf.layer for x in reopened] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert not any(x.dxf.layer in {"CUTTING", "BEND", "MARKING"} for x in reopened)


@pytest.mark.parametrize("bad", (0, -1, 9999, float("nan"), True))
def test_reverse_crease_asymmetric_leg_retract_requires_explicit_finite_source_arc(bad):
    scene, first, second, p = _v_source_with_actual_cut(60)
    with pytest.raises(GeometryError):
        manufacturing_api.project_v_miter_reverse_crease_asymmetric_cut_trial(
            scene, first, second, **p,
            second_leg_outer_perimeter_retract_mm=bad,
        )


def test_reverse_crease_asymmetric_leg_requires_real_60_source_not_90_or_forged():
    scene, first, second, p = _v_source_with_actual_cut(90)
    with pytest.raises(GeometryError, match="negative first BEND"):
        manufacturing_api.project_v_miter_reverse_crease_asymmetric_cut_trial(
            scene, first, second, **p,
            second_leg_outer_perimeter_retract_mm=6,
        )
    scene, first, second, p = _v_source_with_actual_cut(60)
    clone = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.project_v_miter_reverse_crease_asymmetric_cut_trial(
            scene, clone, second, **p,
            second_leg_outer_perimeter_retract_mm=6,
        )


@pytest.mark.parametrize("extra", ("none", "partial", "gap", "offset", "cross"))
def test_reverse_crease_cut_never_infers_missing_bend_from_saved_stock(extra):
    scene, first, second, p = _v_source_with_actual_cut(60)
    if extra == "partial":
        scene.primitives.append(LinePrimitive(Vec2(0, 0), Vec2(3, 0), "BEND"))
    elif extra == "gap":
        scene.primitives.extend([
            LinePrimitive(Vec2(0, 0), Vec2(3, 0), "BEND"),
            LinePrimitive(Vec2(4, 0), Vec2(20, 0), "BEND"),
        ])
    elif extra == "offset":
        scene.primitives.append(LinePrimitive(Vec2(0, .01), Vec2(20, .01), "BEND"))
    elif extra == "cross":
        scene.primitives.append(LinePrimitive(Vec2(6, -10), Vec2(6, 10), "BEND"))
    result = manufacturing_api.project_v_miter_reverse_crease_asymmetric_cut_trial(
        scene, first, second, **p,
        second_leg_outer_perimeter_retract_mm=6,
    )
    assert result.first_original_stock_covers_extension is True
    assert result.first_real_bend_continuation_covers is False
    assert result.manufacturing_status.endswith("UNCERTIFIED")


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("mirror", (False, True))
def test_60_degree_genuine_extension_is_not_foldable_after_v_relief(mode, mirror):
    """A REAL extra BEND + original material still cannot fold removed V metal."""
    scene, first, second, p = _v_source_with_actual_cut(60, mirror=mirror)
    p["relief_mode"] = mode
    sign = -1 if mirror else 1
    extra = LinePrimitive(Vec2(0, 0), Vec2(sign * 20, 0), "BEND")
    scene.primitives.append(extra)
    before = list(scene.primitives)
    result = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **p,
    )
    assert result.manufacturing_status == "V_MITER_POST_RELIEF_CREASE_UNCERTIFIED"
    assert result.original_stock.first_original_stock_covers_extension is True
    assert result.first_original_bend_continuation_covers is True
    assert result.first_remaining_material_interior_covers is False
    assert result.first_remaining_interior_crease_length_mm < (
        result.original_stock.bounded.first_outside_bend_span_mm
    )
    assert result.second_original_bend_continuation_covers is None
    assert result.second_remaining_material_interior_covers is None
    assert result.second_remaining_interior_crease_length_mm is None
    assert scene.primitives == before
    # Positive source-crease witness never bypasses true R/BA/T guards.
    with pytest.raises(GeometryError, match="material extension unverified"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, first, second, **p,
        )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_120_degree_short_crease_can_have_real_source_and_surviving_material(mode):
    """Distinguish genuine negative-axial BEND reach from a 60° V-boundary."""
    scene, first, second, p = _v_source_with_actual_cut(120, first_span=5)
    p["relief_mode"] = mode
    scene.primitives.append(
        LinePrimitive(Vec2(-5, 0), Vec2(-20, 0), "BEND")
    )
    result = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **p,
    )
    assert result.original_stock.bounded.first_outside_bend_span_mm == pytest.approx(
        20 / math.sqrt(3) - 5
    )
    assert result.first_original_bend_continuation_covers is True
    assert result.first_remaining_material_interior_covers is True
    assert result.first_remaining_interior_crease_length_mm == pytest.approx(
        result.original_stock.bounded.first_outside_bend_span_mm
    )
    assert result.manufacturing_status.endswith("UNCERTIFIED")


@pytest.mark.parametrize("coverage", ("none", "partial", "gap", "reversed", "cross"))
def test_fold_extension_requires_contiguous_source_bend_not_intersection(coverage):
    """No generated/material/virtual BEND can bridge a missing physical segment."""
    scene, first, second, p = _v_source_with_actual_cut(60)
    if coverage == "partial":
        added = [LinePrimitive(Vec2(0, 0), Vec2(5, 0), "BEND")]
    elif coverage == "gap":
        added = [
            LinePrimitive(Vec2(0, 0), Vec2(5, 0), "BEND"),
            LinePrimitive(Vec2(6, 0), Vec2(20, 0), "BEND"),
        ]
    elif coverage == "reversed":
        added = [LinePrimitive(Vec2(20, 0), Vec2(0, 0), "BEND")]
    elif coverage == "cross":
        added = [
            LinePrimitive(Vec2(6, -5), Vec2(6, 5), "BEND"),
            LinePrimitive(Vec2(0, 0.1), Vec2(20, 0.1), "BEND"),
        ]
    else:
        added = []
    scene.primitives.extend(added)
    result = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **p,
    )
    assert result.first_original_bend_continuation_covers is (coverage == "reversed")
    # Post-CUTTING is independently false regardless of extra source lines.
    assert result.first_remaining_material_interior_covers is False
    assert result.first_original_bend_continuation_covers is not None


def test_without_overrun_returns_no_virtual_extension_evidence():
    scene, first, second, p = _v_source_with_actual_cut(90)
    result = manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
        scene, first, second, **p,
    )
    assert result.original_stock.bounded.needs_independent_material_extension_evidence is False
    assert result.first_original_bend_continuation_covers is None
    assert result.second_original_bend_continuation_covers is None
    assert result.first_remaining_material_interior_covers is None
    assert result.second_remaining_material_interior_covers is None


def test_survival_witness_refuses_unqualified_source_and_missing_explicit_r_factor():
    scene, first, second, p = _v_source_with_actual_cut(60)
    missing = dict(p, relief_t_factor=None)
    with pytest.raises(GeometryError, match="explicit trial factor"):
        manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
            scene, first, second, **missing,
        )
    fake = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
            scene, fake, second, **p,
        )
    cuts_only = DrawingScene([first, second])
    with pytest.raises(GeometryError, match="one canonical closed CUTTING"):
        manufacturing_api.diagnose_v_miter_physical_crease_after_relief(
            cuts_only, first, second, **p,
        )


@pytest.mark.parametrize("angle", (90, 120))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_bounded_finite_thickness_bisector_is_local_not_certified_cutting(angle, mode):
    scene, first, second = _geometry()
    witness = manufacturing_api.project_v_miter_sharp_thickness_witness(
        scene, first, second,
        **_params(second_fold_angle_deg=angle, relief_mode=mode)
    )
    assert not witness.bounded.needs_independent_material_extension_evidence
    assert witness.thickness_mm == pytest.approx(2)
    assert witness.geometry_model == "IDEAL_SHARP_BEND_FINITE_T_SLAB_BISECTOR"
    assert witness.manufacturing_status == "V_MITER_SHARP_THICKNESS_UNCERTIFIED"
    assert witness.cross_section_width_mm == pytest.approx(math.sqrt(2))
    mid = witness.seam_midpoint
    tip = witness.cross_section_tip
    delta = tuple(tip[i] - mid[i] for i in range(3))
    assert math.hypot(*delta) == pytest.approx(witness.cross_section_width_mm)
    # The bevel normal and the shared plane intersection define one plane.
    assert sum(delta[i] * witness.bisector_normal[i] for i in range(3)) == pytest.approx(0, abs=1e-7)
    assert scene.primitives == [first, second]
    assert not any(p.layer == "CUTTING" for p in scene.primitives)


def test_short_source_crease_reach_cannot_be_silently_extended():
    scene, first, second = _geometry(first_length=5)
    reach = manufacturing_api.diagnose_v_miter_bounded_bend_reach(
        scene, first, second, **_params(second_fold_angle_deg=120)
    )
    assert reach.first_outside_bend_span_mm == pytest.approx(20 / math.sqrt(3) - 5)
    assert reach.needs_independent_material_extension_evidence
    with pytest.raises(GeometryError, match="material extension"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, first, second, **_params(second_fold_angle_deg=120)
        )


def test_too_thick_for_flange_cannot_claim_local_bevel():
    scene, first, second = _geometry()
    with pytest.raises(GeometryError, match="T is not smaller"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, first, second, **_params(thickness_mm=20)
        )


@pytest.mark.parametrize("mirror", [False, True])
def test_90_degree_witness_mirrors_cleanly_and_stays_inside_bend_domains(mirror):
    scene, first, second = _geometry(mirror=mirror)
    w = manufacturing_api.project_v_miter_sharp_thickness_witness(
        scene, first, second, **_params()
    )
    sign = -1 if mirror else 1
    assert w.cross_section_tip[0] == pytest.approx(-sign)
    assert w.cross_section_tip[1] == pytest.approx(1)
    assert w.seam_midpoint[2] == pytest.approx(10)


def test_orthogonal_and_nonorthogonal_source_diagnostics_are_distinct():
    scene, first, second = _geometry(second_to=(100, 100))
    w = manufacturing_api.project_v_miter_sharp_thickness_witness(
        scene, first, second, **_params(second_fold_angle_deg=90)
    )
    assert w.bounded.ideal.source.flat_bend_line_angle_deg == pytest.approx(45)
    assert w.cross_section_width_mm > 0
    assert w.manufacturing_status.endswith("UNCERTIFIED")


def test_qualified_but_forged_or_parallel_bend_never_produces_thickness_contact():
    scene, first, second = _geometry()
    forged = LinePrimitive(first.p1, first.p2, "BEND")
    with pytest.raises(GeometryError, match="original scene"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            scene, forged, second, **_params()
        )
    parallel = LinePrimitive(Vec2(-100, 100), Vec2(0, 100), "BEND")
    with pytest.raises(GeometryError, match="parallel"):
        manufacturing_api.project_v_miter_sharp_thickness_witness(
            DrawingScene([first, parallel]), first, parallel, **_params()
        )


def test_source_material_must_be_independently_validated_not_inferred_from_bend():
    scene, first, second = _geometry()
    candidate = manufacturing_api.diagnose_v_miter_bounded_bend_reach(
        scene, first, second, **_params(second_fold_angle_deg=120)
    )
    assert candidate.ideal.manufacturing_status == "V_MITER_CUTTING_UNCERTIFIED"
    assert candidate.manufacturing_status == "V_MITER_BOUNDED_CONTACT_UNCERTIFIED"
    assert len(scene.primitives) == 2
