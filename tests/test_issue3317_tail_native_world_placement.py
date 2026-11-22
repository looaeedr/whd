# -*- coding: utf-8 -*-
"""#3317 source-only R2000 Ø4 V: assembled true-T Tail native orientation.

The existing independent Factory CHECK source is unmodified. This is NOT
a machining clearance, BA/R solver, or permission to export manufacture.
"""
import math

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.assembly_geometry import triangle_bounds
from ae_engine.assembly_geometry_primitives import place_endcap_against_box_body
from ae_engine.v_miter_tail_d4_delivery import build_tail_d4_check_from_original


def _signed_volume(triangles):
    total = 0.
    for a,b,c in triangles:
        total += (
            a[0]*(b[1]*c[2]-b[2]*c[1])
            + a[1]*(b[2]*c[0]-b[0]*c[2])
            + a[2]*(b[0]*c[1]-b[1]*c[0])
        )/6.
    return total


# Native W620 / H600 / D185 Box Body lower OUTSIDE skin is -298 at T2.
# Only the canonical body Y-plane is material to the EndCap mapping; no
# invented bend is introduced by the reference triangles in this unit.
_BODY_LOWER_DATUM = (
    ((-310.,-298.,-92.5),(310.,-298.,-92.5),(310.,-298.,92.5)),
    ((-310.,-298.,-92.5),(310.,-298.,92.5),(-310.,-298.,92.5)),
    ((-310.,298.,-92.5),(310.,298.,-92.5),(310.,298.,92.5)),
)


def test_native_thick_tail_local_skin_uses_box_body_lower_datum_not_midpoint():
    local = (
        ((320.,120.,0.),(321.,120.,0.),(320.,121.,0.)),
        ((320.,120.,-2.),(321.,120.,-2.),(320.,121.,-2.)),
        ((320.,120.,48.),(321.,120.,48.),(320.,121.,48.)),
    )
    placed=api.place_prethickened_endcap_world_skins(
        local,placement="bottom",box_body_world=_BODY_LOWER_DATUM,
    )
    assert [row[0][1] for row in placed] == pytest.approx(
        (-298.,-300.,-250.),abs=1e-9,
    )
    # Local Y is NOT mirrored; original offset is NOT dropped.
    assert placed[0][0][2] < placed[0][1][2]  # wound face is (a,c,b)
    shifted=api.place_prethickened_endcap_world_skins(
        local,placement="bottom",box_body_world=_BODY_LOWER_DATUM,
        offset=(3.,4.,5.),
    )
    for before,after in zip(placed,shifted):
        for p,q in zip(before,after):
            assert q==pytest.approx((p[0]+3.,p[1]+4.,p[2]+5.),abs=1e-9)


@pytest.mark.parametrize("axis",("x","y"))
def test_real_factory_d4_assembled_tail_t2_has_native_winding_and_zero_half_t(axis):
    # Uses the ACTUAL _build_end_cap_scene Factory, FOUR genuine CUTTING
    # features, finite existing BEND and source-keyed checked Ø4 full-T mesh.
    flat,checks=build_tail_d4_check_from_original(
        __import__(
            "ae_engine.v_miter_tail_d4_delivery",fromlist=["default_vault_tail_d4_spec"]
        ).default_vault_tail_d4_spec(),
    )
    check=checks[axis]
    assert len(tuple(p for p in flat.result_scene.primitives
                     if p.layer=="CUTTING"))==5  # outer + four Factory holes
    vertices=check.inner_xyz+check.outer_xyz
    local=tuple(tuple(vertices[i] for i in face) for face in check.shell_faces)
    placed=api.place_prethickened_endcap_world_skins(
        local,placement="bottom",box_body_world=_BODY_LOWER_DATUM,
    )
    assert len(placed)==len(local)
    raw_native=place_endcap_against_box_body(
        local,"bottom",_BODY_LOWER_DATUM,sheet_thickness=0.,
    )
    assert placed==tuple((a,c,b) for a,b,c in raw_native)
    assert not any(
        point[1] < -301.
        for triangle in placed for point in triangle
        if abs(point[1]+298.)<=1e-5
    )
    # Anti-handness reversal once, with NO displacement of any world vertex.
    original_volume=_signed_volume(local)
    raw_volume=_signed_volume(raw_native)
    fixed_volume=_signed_volume(placed)
    assert abs(original_volume)>1.
    assert raw_volume==pytest.approx(-original_volume,abs=1e-5)
    assert fixed_volume==pytest.approx(original_volume,abs=1e-5)
    assert all(
        tuple(sorted(placed[i]))==tuple(sorted(raw_native[i]))
        for i in range(len(local))
    )
    assert all(math.isfinite(v) for tri in placed for p in tri for v in p)


def test_real_vault_box_body_w620_h600_d185_t2_d4_native_bottom_world():
    """Factory Box Body -> actual world skin -> native placed Ø4 true-T Tail.

    The box-body reference here comes from WHD's OWN resolved physical
    Factory structure, NOT a supplied synthetic lower-Y sheet.
    """
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from ae_engine.box_body_structure_state import default_box_body_structure_state
    from phase6_fold_profiles import (
        build_box_body_profile, profile_to_fold_segments,
    )
    from phase6_final_scene_view import AssemblyScenePart
    from ae_engine.v_miter_tail_d4_delivery import default_vault_tail_d4_spec

    values={
        "model":"金庫型","w":620.,"h":600.,"d":185.,"t":2.,
        "fw":25.,"zl1":15.,"zl2":15.,"zr1":15.,"zr2":15.,
        "yl1":15.,"yr1":15.,"ytop1":16.,"ybottom1":48.,
    }
    structure=build_box_body_structure_render_data(BoxBodyPartSpec(
        width=620.,height=600.,depth=185.,thickness=2.,frame_width=25.,
        model_name="金庫型",zl1=15.,zl2=15.,zr1=15.,zr2=15.,
        fold_profile=profile_to_fold_segments(build_box_body_profile(values)),
        structure_state=default_box_body_structure_state(),
        head_ybottom1=48.,tail_ybottom1=48.,
    ))
    body=AssemblyScenePart(
        part_key="box_body",render_data=structure,
        x_profile=(),y_profile=(),placement="box_body",
    )
    source_world=api.build_joint_world_geometry(
        (body,),(620.,600.,185.),2.,
    )["world_triangles_by_part"]
    body_world=tuple(source_world["box_body"])
    assert body_world
    bounds=triangle_bounds(body_world)
    assert bounds[1][0]==pytest.approx(-298.,abs=1e-7)

    flat,checks=build_tail_d4_check_from_original(
        default_vault_tail_d4_spec()
    )
    for first in ("x","y"):
        check=checks[first]
        vertices=check.inner_xyz+check.outer_xyz
        local=tuple(tuple(vertices[i] for i in face) for face in check.shell_faces)
        world=api.place_prethickened_endcap_world_skins(
            local,placement="bottom",box_body_world=body_world,
        )
        assert len(world)==len(local)
        # Geometry has been translated/rotated, never re-thickened.
        assert _signed_volume(world)==pytest.approx(
            _signed_volume(local),abs=1e-4,
        )
        native=place_endcap_against_box_body(
            local,"bottom",body_world,sheet_thickness=0.,
        )
        assert world==tuple((a,c,b) for a,b,c in native)
        # Geometry source is the original 4-hole Factory and 5 real BENDs.
        original_cut=tuple(p for p in flat.result_scene.primitives
                           if p.layer=="CUTTING")
        native_bends=tuple(p for p in flat.result_scene.primitives
                           if p.layer=="BEND")
        assert len(original_cut)==5 and len(native_bends)==5


@pytest.mark.parametrize("first_axis", ("x","y"))
def test_d4_same_factory_source_is_one_2d_and_3d_preview_not_manufacturing(first_axis):
    from ae_engine.v_miter_tail_d4_delivery import (
        default_vault_tail_d4_spec,build_tail_d4_check_preview_render,
    )
    flat,checks=build_tail_d4_check_from_original(
        default_vault_tail_d4_spec()
    )
    preview=build_tail_d4_check_preview_render(flat,first_axis=first_axis)
    assert preview.scene is flat.result_scene
    assert preview.metadata["tail_lower_v_d4_check_only"] is True
    assert preview.metadata["tail_lower_v_preview_only"] is True
    assert preview.metadata["manufacturing_approved"] is False
    assert len(preview.material.interiors)==4
    assert len(tuple(p for p in preview.scene.primitives if p.layer=="BEND"))==5
    assert len(api.tail_lower_v_preview_mesh(preview))==len(
        checks[first_axis].shell_faces
    )
    with pytest.raises(ValueError,match="禁止加工 DXF"):
        api.reject_tail_lower_v_preview_for_dxf(preview)
