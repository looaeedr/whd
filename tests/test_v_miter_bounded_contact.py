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
