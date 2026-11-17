"""Finite BEND / t-thick V-miter preliminary geometry, no manufacturing token."""
import math

import pytest

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
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
