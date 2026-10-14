# -*- coding: utf-8 -*-
"""Actual imported Receiving DXF sources are used in 2D, 3D and export."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import (
    build_box_body_structure_render_data, generate_box_body_structure_parts,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
from phase6_box_body_structure import set_side_back_back_panel_mode


def spec_for_mode(mode="FULL", *, h=1600.0, d=350.0):
    snapshot = receiving.apply_family_defaults({"model": "受電箱"})
    snapshot["h"] = float(h)
    snapshot["d"] = float(d)
    snapshot["door_layout_columns"] = [[800.0, [1100.0, h-1100.0]]]
    state = set_side_back_back_panel_mode(receiving.resolve_box_body_structure_state(None), mode)
    contract = receiving.resolve_back_panel_contract(
        snapshot, structure_state=state,
        panel_width=795.0, full_panel_height=h-4,
    )
    return BoxBodyPartSpec(
        width=800.0, height=h, depth=d, thickness=2.0,
        frame_width=29.0, model_name="受電箱",
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state, back_panel_contract=contract,
    )


def _piece(result, role):
    return next(x for x in result.pieces if x.role == role)


def test_each_receiving_piece_loads_own_file_not_vault_and_preserves_checksum():
    render = build_box_body_structure_render_data(spec_for_mode())
    names = {"left_side":"左側板.dxf","right_side":"右側板.dxf","back":"後面板.dxf"}
    for role, name in names.items():
        item = _piece(render, role)
        m = item.render_data.metadata
        p = Path(m["baseline_source_path"])
        assert p.name == name
        assert p.parent.name == "受電箱"
        assert m["baseline_source_sha256"] == sha256(p.read_bytes()).hexdigest()
        assert m["baseline_source_status"] == "VERIFIED"
        assert m["baseline_stock_and_bends"] == "CANONICAL_FOLD_PROFILE_NOT_SAMPLE_DXF"
    assert _piece(render,"left_side").render_data.metadata["baseline_feature_count"] == 9
    assert _piece(render,"right_side").render_data.metadata["baseline_feature_count"] == 9
    assert _piece(render,"back").render_data.metadata["baseline_feature_count"] == 4


def test_source_cutting_blind_and_marking_holes_stay_on_the_correct_side():
    render = build_box_body_structure_render_data(spec_for_mode())
    left = _piece(render,"left_side").render_data.scene.primitives
    right = _piece(render,"right_side").render_data.scene.primitives
    def circles(prims, layer):
        return [p for p in prims if isinstance(p,CirclePrimitive) and p.layer==layer
                and p.source_type=="receiving_dedicated_baseline"]
    assert len(circles(left,"CUTTING")) == 8
    assert len(circles(right,"CUTTING")) == 6
    assert len(circles(left,"BLIND_HOLE")) == len(circles(right,"BLIND_HOLE")) == 1
    assert len(circles(left,"MARKING")) == 0
    assert len(circles(right,"MARKING")) == 2
    assert sorted(round(p.center.y,3) for p in circles(left,"CUTTING") if p.radius==5.25) == [
        98.0,98.0,798.0,798.0,1498.0,1498.0
    ]


def test_original_program_bends_remain_authoritative_and_source_dxf_mismatch_is_explicit():
    """Imported DXF is evidence/features, NOT a directive to mirror 3D."""
    render = build_box_body_structure_render_data(spec_for_mode())
    left = _piece(render, "left_side").render_data.metadata
    right = _piece(render, "right_side").render_data.metadata
    # This DXF was added AFTER the original program worked; its different
    # BEND positions are preserved for audit instead of silently copied.
    assert left["baseline_reference_bend_positions"] == (22.,362.,387.,413.)
    assert left["baseline_effective_bend_positions"] == (22.,42.,67.,413.)
    assert left["baseline_sample_bends_match"] is False
    assert left["baseline_stock_and_bends"] == "CANONICAL_FOLD_PROFILE_NOT_SAMPLE_DXF"
    assert right["baseline_sample_bends_match"] is True


@pytest.mark.parametrize("mode,amount", [("FULL",4),("HALF",4),("BACK_OPENING",5)])
def test_rear_uses_only_mode_approved_real_source_contours(mode,amount):
    back = _piece(build_box_body_structure_render_data(spec_for_mode(mode)),"back")
    primitives = back.render_data.scene.primitives
    holes = [p for p in primitives if isinstance(p,PolylinePrimitive)
             and p.layer=="CUTTING" and p.closed]
    assert len(holes) == amount+1  # actual outer stock + approved cuts
    assert back.render_data.metadata["baseline_feature_count"] == amount
    # Alternate sample source y=592 has never been directly pasted into FULL mode.
    ys = [round(max(point.y for point in p.points),3) for p in holes[1:]]
    if mode == "FULL":
        assert sorted(ys)==[120.0,120.0,1476.0,1476.0]
    if mode == "HALF":
        assert sorted(ys)==[120.0,120.0,1004.0,1004.0]


def test_receiving_source_absence_is_explicit_not_a_silent_vault_fallback(tmp_path):
    with pytest.raises(FileNotFoundError, match="受電箱板件專用基準檔不存在"):
        build_box_body_structure_render_data(
            spec_for_mode(), ManufacturingContext(resource_root=str(tmp_path)),
        )


def test_export_reports_actual_per_piece_baseline_and_reopens(tmp_path):
    import ezdxf
    results=generate_box_body_structure_parts(
        spec_for_mode(),tmp_path,ManufacturingContext(overwrite=True),
    )
    assert len(results)==3
    for result in results:
        assert result.used_baseline
        assert result.baseline_path and "受電箱" in str(result.baseline_path)
        assert Path(result.output_path).exists()
        doc=ezdxf.readfile(result.output_path)
        assert len(doc.modelspace())>0


def test_corrected_left_bends_fold_inward_in_authoritative_3d_and_keep_dimensions():
    from phase6_final_scene_projection import _phase6_box_body_structure_meshes
    data = build_box_body_structure_render_data(spec_for_mode())
    left = _piece(data, "left_side")
    assert left.material_dimensions == pytest.approx((429.0, 1596.0))
    assert left.render_data.metadata["baseline_sample_bends_match"] is False
    assert [round(row.position, 4) for row in left.render_data.fold_guides] == [
        22.0, 42.0, 67.0, 413.0,
    ]
    meshes = _phase6_box_body_structure_meshes(data, thickness=2.0)
    assert len(meshes) == 3
    triangles = next(t for piece, t in meshes if piece.role == "left_side")
    assert triangles, "The corrected panel must produce a real 3D mesh"
    coords = [point for triangle in triangles for point in triangle]
    # Left side must remain at the left box skin and fold inward, not out
    # beyond the nominal -W/2 finished skin.
    assert min(point[0] for point in coords) == pytest.approx(-399.0)
    assert max(point[0] for point in coords) > -399.0
    # Sample outside dimensions do not change when original bend order is restored.
    assert max(point[1] for point in coords) - min(point[1] for point in coords) == pytest.approx(1596.0)


def test_undersized_receiving_preview_is_diagnostic_but_cannot_export(tmp_path):
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    spec = spec_for_mode(d=40.0)
    render = build_box_body_structure_render_data(spec)
    left = _piece(render, "left_side").render_data
    assert left.metadata["baseline_fit_valid"] is False
    assert "RECEIVING_BASELINE_FIXED_HOLE_OUTSIDE_MATERIAL" in left.metadata["baseline_fit_error"]
    assert left.metadata["baseline_feature_count"] == 0
    assert not any(
        isinstance(p, CirclePrimitive) and p.source_type=="receiving_dedicated_baseline"
        for p in left.scene.primitives
    )
    with pytest.raises(ValueError, match="RECEIVING_BASELINE_FIXED_HOLE_OUTSIDE_MATERIAL"):
        generate_box_body_structure_parts(
            spec, tmp_path, ManufacturingContext(overwrite=True),
        )
    assert list(tmp_path.glob("*.dxf")) == []
    with pytest.raises(ValueError, match="RECEIVING_BASELINE_FIXED_HOLE_OUTSIDE_MATERIAL"):
        save_part_render_data_dxf(left, tmp_path/"invalid-left.dxf")
    assert not (tmp_path/"invalid-left.dxf").exists()


def test_split_left_divider_joint_selects_only_real_upper_contact_boundary():
    """A source relief must not suppress a genuine mating line or forge one."""
    from tests.test_issue1050_receiving_mother_plate_marking import (
        _snapshot, _full_receiving_geometry,
    )
    from ae_engine.cabinet_types import receiving
    from ae_engine.door_dividers import derive_box_body_dividers
    from ae_engine.receiving_joint_marking import (
        _divider_side_contact, _divider_boundary_contact_patches,
        _mapped_plane_groups, _outward_normal, _group_world_polygon,
        _polygon_world_exterior, _plane_basis, _unit,
    )
    from ae_engine.assembly_geometry import resolve_physical_mating_region
    from ae_engine.door_dividers import divider_terminal_mating_region
    from ae_engine.contracts import ResolvedPhysicalMatingRegion
    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry

    snap = _snapshot()
    geometry = _full_receiving_geometry(snap)
    world = _phase6_build_joint_world_geometry(
        geometry.parts, (800., 1600., 350.), 2.,
    )
    divider = derive_box_body_dividers(
        snap["door_layout_columns"], depth=350., thickness=2.,
        model_name="受電箱", frame_width=29., layout_scope=snap["door_layout_scope"],
    )[0]
    left = next(piece for piece in geometry.part("box_body").render_data.pieces
                if piece.role == "left_side")
    assert len(left.render_data.material.interiors) == 8
    assert left.render_data.metadata["baseline_sample_bends_match"] is False

    actual = _divider_side_contact(
        geometry=geometry, world=world, divider=divider,
        locator_id="box_body:left_side", dimensions=(800., 1600., 350.),
        sheet_thickness=2.,
    )
    assert actual.locator_part_id == "box_body:left_side"
    assert actual.attached_part_id == divider.stable_id
    # The real assembled contact polygon includes source relief edges
    # all the way to the lower terminal -327, while its upper physical
    # bay boundary remains Y=-300. This full contour is not a fake flat
    # rectangular contact drawn just at the Y=-300 reference plane.
    assert any(abs(point[1]+300.) < 1e-6 for point in actual.overlap_world)
    assert min(float(point[1]) for point in actual.overlap_world) == pytest.approx(-327.)
    assert max(float(point[1]) for point in actual.overlap_world) == pytest.approx(-300.)

    part = geometry.part(divider.stable_id)
    terminal = resolve_physical_mating_region(
        part_id=divider.stable_id,
        semantic=divider_terminal_mating_region(divider, "MIN"),
        render_data=part.render_data, x_profile=part.x_profile,
        y_profile=part.y_profile, placement=part.placement,
        dimensions=(800.,1600.,350.), offset=part.offset, sheet_thickness=2.,
    )
    group = next(g for g in _mapped_plane_groups(
        world["mapped_skin_triangles_by_part"]["box_body:left_side"]
    ) if abs(float(g[0].world[0][0])+398.) < 1e-6 and
             tuple(round(v,4) for v in _unit(_outward_normal(g[0]))) == (1.,0.,0.))
    origin=tuple(float(v) for v in group[0].world[0])
    n=(1.,0.,0.); u,v=_plane_basis(n)
    polygon=_group_world_polygon(group,origin=origin,u=u,v=v)
    mother=ResolvedPhysicalMatingRegion(
        part_id="box_body:left_side",
        region_id="ACTUAL_SOURCE_SKIN",region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=(origin,n),outward_normal=n,
        world_polygon=_polygon_world_exterior(polygon,origin=origin,u=u,v=v),
        flat_mapping=tuple(group),
    )
    # Adversarial interface: none of the two real patches reaches Y=-200.
    # The solver MUST fail closed, not choose a random island.
    assert _divider_boundary_contact_patches(mother,terminal,junction_y=-200.) == ()


def test_receiving_left_right_and_divider_fw_are_truly_assembled_not_only_coplanar():
    """Actual 3D oracle: both 29-mm flanges align, 22-mm LEFT bends inward.

    A reflected left panel previously sent its first 22-mm leg OUTSIDE W,
    moving the multi-piece scene centroid by 11mm. All three 29mm flanges
    could pass a Z-only coplanarity check while the cabinet was misassembled.
    """
    from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part
    from tests.test_issue74_divider_side_front_penetration import _piece_bands
    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
    from ae_engine.divider_manufacturing import resolve_divider_placement_evidence

    snapshot = _snapshot()
    body = _body_part(snapshot)
    _divider, divider = _divider_part(snapshot)
    world = _phase6_build_joint_world_geometry(
        (body, divider), (800., 1600., 350.), 2.,
    )
    placement = resolve_divider_placement_evidence(divider, body, world)
    assert placement.valid and placement.fw_face_flush
    assert placement.expected_fw_formed_occupation == pytest.approx(29.)
    assert placement.box_body_left_fw_planes == pytest.approx((172., 174.))
    assert placement.box_body_right_fw_planes == pytest.approx((172., 174.))
    assert placement.divider_fw_planes == pytest.approx((172., 174.))

    bands = _piece_bands(body)
    all_points = []
    expected_bands = (
        ("left_side", "fw_left", (-400., -371.), "zl1"),
        ("right_side", "fw_right", (371., 400.), "zr2"),
    )
    for role, fw_key, expected, _terminal in expected_bands:
        skins = world["mapped_skin_triangles_by_part"]["box_body:"+role]
        all_points.extend(point for skin in skins for point in skin.world)
        a, b = next((a,b) for name,a,b in bands["box_body:"+role] if name==fw_key)
        points = [point for skin in skins
                  if a+1e-6 < sum(p[0] for p in skin.flat)/3 < b-1e-6
                  for point in skin.world]
        assert points
        observed = (min(p[0] for p in points), max(p[0] for p in points))
        assert observed == pytest.approx(expected,abs=1e-5)
        assert observed[1] - observed[0] == pytest.approx(29.)
        assert {round(p[2],6) for p in points} == {172.,174.}

    # Entire finished cabinet is W800; reflecting the left 22mm OUTSIDE
    # would shift all assembled X by 11mm despite Z planes staying flush.
    outside = (min(p[0] for p in all_points),max(p[0] for p in all_points))
    assert outside == pytest.approx((-400.,400.),abs=1e-5)
    left_piece = next(p for p in body.render_data.pieces if p.role=="left_side")
    assert left_piece.fold_profile[0].angle == pytest.approx(90.)
    assert [round(bend.position,5) for bend in left_piece.render_data.fold_guides] == [
        22.,42.,67.,413.,
    ]
