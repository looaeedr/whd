"""#2517: independent 3D physical mesh is projected inside Engine."""
from __future__ import annotations

import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_base_fixing_plate_geometry import (
    build_fixing_plate_source_render_data,
)
import phase6_final_scene_renderer


@pytest.mark.parametrize("part_key,role", [
    ("door", "outer"),
    ("door_c1_r1", "outer"),
    ("door_c2_r14", "outer"),
    ("inner_door:some-bay:panel", "inner"),
    ("box_body", "other"),
    ("door_cat_rubbish", "other"),
    ("door_c1_rX", "other"),
    ("inner_door:some-bay:frame", "other"),
])
def test_public_engine_classifies_canonical_door_display_identity(part_key, role):
    assert manufacturing_api.door_display_part_role(part_key) == role


def test_verified_ear_fixing_plate_solid_mesh_stays_source_exact():
    source = build_fixing_plate_source_render_data(
        "base_plate:fixing_plate:left",
    )
    source_meta = dict(source.metadata)
    old_guides = source.fold_guides
    old_scene = tuple(source.scene.primitives)
    actual = manufacturing_api.project_independent_part_view_mesh(
        "base_plate:fixing_plate:left", source,
        x_profile=({"len": 256.},), y_profile=({"len": 105.},),
        thickness=2.,
    )
    assert actual.fixed_plate_hinge_y == pytest.approx(22.)
    assert actual.fold_guides[0].position == pytest.approx(22.)
    assert actual.y_profile[0].angle == pytest.approx(90.)
    pts = [v for tri in actual.triangles for v in tri]
    assert max(v[2] for v in pts) - min(v[2] for v in pts) >= 22.
    assert source.fold_guides == old_guides
    assert dict(source.metadata) == source_meta
    assert tuple(source.scene.primitives) == old_scene
    assert source.fold_guides[0].position == pytest.approx(23.)


def test_source_proof_is_required_even_if_fixing_plate_name_looks_valid():
    from dataclasses import replace
    source = build_fixing_plate_source_render_data(
        "base_plate:fixing_plate:left",
    )
    forged = replace(
        source,
        metadata={**source.metadata, "source_bend_verified": False},
    )
    with pytest.raises(ValueError, match="EAR_LOCAL_FORM_NOT_CURRENT_VERIFIED_BEND23"):
        manufacturing_api.project_independent_part_view_mesh(
            "base_plate:fixing_plate:left", forged,
            x_profile=({"len": 256.},), y_profile=({"len": 105.},),
            thickness=2.,
        )


def test_renderer_consumes_engine_mesh_and_physical_identity_not_private_formulas():
    source = inspect.getsource(
        phase6_final_scene_renderer.Phase6FinalSceneRenderer.render,
    )
    assert "manufacturing_api.project_independent_part_view_mesh(" in source
    assert source.count("manufacturing_api.door_display_part_role(") >= 2
    part_section = source.split("scene = render_data.scene", 1)[1]
    part_section = part_section.split('if not triangles:', 1)[0]
    for forbidden in (
        "verified_receiving_fixing_plate_local_fold(",
        "fit_receiving_left_zl1_formed_outside(",
        "folded_mesh_with_flat_uv_from_polygon(",
        "thicken_triangle_surface(",
        "part_key.startswith(",
    ):
        assert forbidden not in part_section
