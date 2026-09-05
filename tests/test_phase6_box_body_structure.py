from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine.box_body_structure import resolve_box_body_structure
from ae_engine.sheetmetal_part_adapters import build_box_body_result_from_fold_profile
from phase6_box_body_structure import (
    BoxBodyStructureType,
    default_box_body_structure_state,
    set_active_structure,
    set_join_seam_bend,
    set_two_piece_width,
)
from phase6_fold_profiles import build_box_body_profile


def _snapshot(w=1200.0, t=2.0):
    return {
        "w": w, "h": 1600.0, "d": 400.0, "t": t, "fw": 25.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0,
    }


def _two_piece_state():
    return set_active_structure(default_box_body_structure_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT)


def test_integral_resolver_is_geometry_equivalent_to_existing_box_body_adapter():
    snapshot = _snapshot()
    profile = build_box_body_profile(snapshot)
    existing = build_box_body_result_from_fold_profile(profile, h=snapshot["h"], t=snapshot["t"])
    resolved = resolve_box_body_structure(
        profile, w=snapshot["w"], h=snapshot["h"], t=snapshot["t"],
        structure_state=default_box_body_structure_state(),
    )
    assert len(resolved.pieces) == 1
    result = resolved.pieces[0].structural
    assert result.outline == existing.outline
    assert result.bends == existing.bends
    assert result.width == pytest.approx(existing.width)
    assert result.height == pytest.approx(existing.height)


def test_two_piece_first_activation_splits_w_in_half_and_preserves_outer_fold_chains():
    snapshot = _snapshot()
    profile = build_box_body_profile(snapshot)
    resolved = resolve_box_body_structure(
        profile, w=1200.0, h=1600.0, t=2.0, structure_state=_two_piece_state()
    )
    left, right = resolved.pieces
    assert left.formed_width == pytest.approx(600.0)
    assert right.formed_width == pytest.approx(600.0)
    assert left.formed_w_end == pytest.approx(right.formed_w_start)

    left_keys = [seg.phase6_key for seg in left.fold_profile]
    right_keys = [seg.phase6_key for seg in right.fold_profile]
    assert left_keys[:4] == ["zl1", "zl2", "fw_left", "d_left"]
    assert left_keys[-2:] == ["w_left", "seam_bend_left"]
    assert right_keys[:2] == ["seam_bend_right", "w_right"]
    assert right_keys[-4:] == ["d_right", "fw_right", "zr2", "zr1"]
    assert left.fold_profile[-1].length == pytest.approx(12.0)
    assert right.fold_profile[0].length == pytest.approx(12.0)


def test_two_piece_system_half_allows_point_five_and_manual_input_returns_to_integers():
    snapshot = _snapshot(w=1201.0)
    profile = build_box_body_profile(snapshot)
    state = _two_piece_state()
    resolved = resolve_box_body_structure(profile, w=1201.0, h=1600.0, t=2.0, structure_state=state)
    assert [piece.formed_width for piece in resolved.pieces] == pytest.approx([600.5, 600.5])

    with pytest.raises(ValueError, match="只接受整數"):
        set_two_piece_width(state, 1201.0, "left", 600.5)
    state = set_two_piece_width(state, 1201.0, "left", 600)
    resolved = resolve_box_body_structure(profile, w=1201.0, h=1600.0, t=2.0, structure_state=state)
    assert [piece.formed_width for piece in resolved.pieces] == pytest.approx([600.0, 601.0])


def test_two_piece_rejects_side_below_50_and_keeps_sum_equal_w():
    state = _two_piece_state()
    with pytest.raises(ValueError, match="50"):
        set_two_piece_width(state, 1200.0, "left", 49)
    state = set_two_piece_width(state, 1200.0, "right", 500)
    snapshot = _snapshot()
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    assert [p.formed_width for p in resolved.pieces] == pytest.approx([700.0, 500.0])
    assert sum(p.formed_width for p in resolved.pieces) == pytest.approx(1200.0)


def test_two_piece_seam_bend_is_material_outside_w_and_large_value_is_warning_only():
    snapshot = _snapshot()
    profile = build_box_body_profile(snapshot)
    state = set_join_seam_bend(_two_piece_state(), BoxBodyStructureType.TWO_PIECE_W_SPLIT, 50)
    resolved = resolve_box_body_structure(profile, w=1200.0, h=1600.0, t=2.0, structure_state=state)
    assert len(resolved.warnings) == 1
    assert resolved.warnings[0].code == "seam_bend_large"
    assert resolved.pieces[0].fold_profile[-1].length == pytest.approx(50.0)
    assert resolved.pieces[1].fold_profile[0].length == pytest.approx(50.0)
    # W split remains package dimensions; seam material is extra flat width.
    assert sum(p.formed_width for p in resolved.pieces) == pytest.approx(1200.0)

    with pytest.raises(ValueError, match="12"):
        set_join_seam_bend(state, BoxBodyStructureType.TWO_PIECE_W_SPLIT, 11.9)


def test_two_piece_end_relief_uses_each_endcap_ybottom1_plus_shared_extra_and_single_side_meat():
    snapshot = _snapshot(t=2.0)
    profile = build_box_body_profile(snapshot)
    state = _two_piece_state()
    cfg = state["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    cfg["endcap_extra_relief"] = 5.0
    cfg["endcap_single_side_meat_t"] = 0.5

    resolved = resolve_box_body_structure(
        profile, w=1200.0, h=1600.0, t=2.0, structure_state=state,
        head_ybottom1=15.0, tail_ybottom1=22.0,
    )
    left, right = resolved.pieces
    # bottom = tail 22 + 5; top = head 15 + 5
    left_seam = next(b for b in left.structural.bends if b.name == "w_left")
    right_seam = next(b for b in right.structural.bends if b.name == "seam_bend_right")
    assert left_seam.p1.y == pytest.approx(27.0)
    assert right_seam.p1.y == pytest.approx(27.0)
    assert left.structural.height - left_seam.p2.y == pytest.approx(20.0)
    assert right.structural.height - right_seam.p2.y == pytest.approx(20.0)

    # 0.5T = 1 mm material remains beside the seam bend at both relieved ends.
    seam_x_left = left.structural.width - 12.0
    bottom_inner_x = max(p.x for p in left.structural.outline if abs(p.y) < 1e-9)
    assert bottom_inner_x - seam_x_left == pytest.approx(1.0)
    seam_x_right = 12.0
    bottom_inner_x_right = min(p.x for p in right.structural.outline if abs(p.y) < 1e-9)
    assert seam_x_right - bottom_inner_x_right == pytest.approx(1.0)


def test_two_piece_end_relief_rejects_impossible_overlap_in_short_box():
    snapshot = _snapshot()
    profile = build_box_body_profile(snapshot)
    with pytest.raises(ValueError, match="避讓深度"):
        resolve_box_body_structure(
            profile, w=1200.0, h=50.0, t=2.0, structure_state=_two_piece_state(),
            head_ybottom1=20.0, tail_ybottom1=20.0,
        )


def test_base_plate_cross_relief_is_local_centered_20mm_and_keeps_half_t_meat():
    from ae_engine.box_body_structure import apply_base_plate_structure_reliefs
    from ae_engine.sheetmetal_part_adapters import build_base_plate_result

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _two_piece_state()
    structure = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    base = build_base_plate_result(
        w=1200.0, h=1600.0, t=2.0,
        shrink_top=55.0, shrink_bottom=55.0, shrink_left=55.0, shrink_right=55.0,
        bend=15.0,
    )
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=1200.0, shrink_left=55.0, shrink_right=55.0,
        thickness=2.0, structure=structure, structure_state=state,
    )

    # Base Plate unfolded seam center: 15 + (600 - 55) = 560; default span is 550..570.
    coords = {(round(p.x, 6), round(p.y, 6)) for p in relieved.outline}
    assert (550.0, 14.0) in coords
    assert (570.0, 14.0) in coords
    assert (550.0, 0.0) in coords
    assert (570.0, 0.0) in coords

    bottom = sorted(
        (b.p1.x, b.p2.x) for b in relieved.bends if b.name == "bottom"
    )
    top = sorted((b.p1.x, b.p2.x) for b in relieved.bends if b.name == "top")
    assert bottom == pytest.approx([(15.0, 550.0), (570.0, 1105.0)])
    assert top == pytest.approx([(15.0, 550.0), (570.0, 1105.0)])


def test_base_plate_relief_is_not_created_when_seam_is_outside_finished_plate_span():
    from dataclasses import replace
    from ae_engine.box_body_structure import (
        ResolvedBoxBodyPiece,
        ResolvedBoxBodyStructure,
        apply_base_plate_structure_reliefs,
    )
    from ae_engine.sheetmetal_part_adapters import build_base_plate_result

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _two_piece_state()
    original = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    left, right = original.pieces
    # Synthetic seam at 50 mm models the W-three-split default relative to 55 mm Base Plate shrink.
    structure = ResolvedBoxBodyStructure(
        original.structure_type,
        (
            replace(left, formed_w_end=50.0),
            replace(right, formed_w_start=50.0),
        ),
        original.warnings,
    )
    base = build_base_plate_result(
        w=1200.0, h=1600.0, t=2.0,
        shrink_top=55.0, shrink_bottom=55.0, shrink_left=55.0, shrink_right=55.0,
        bend=15.0,
    )
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=1200.0, shrink_left=55.0, shrink_right=55.0,
        thickness=2.0, structure=structure, structure_state=state,
    )
    assert relieved.outline == base.outline
    assert relieved.bends == base.bends


def _three_piece_state():
    return set_active_structure(default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_W_SPLIT)


def test_three_piece_w_split_defaults_to_50_middle_50_and_reuses_join_relief_geometry():
    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _three_piece_state()
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0,
        structure_state=state, head_ybottom1=15.0, tail_ybottom1=15.0,
    )
    assert [p.formed_width for p in resolved.pieces] == pytest.approx([50.0, 1100.0, 50.0])
    assert [p.formed_w_end for p in resolved.pieces[:-1]] == pytest.approx([50.0, 1150.0])
    middle = resolved.pieces[1]
    assert [seg.phase6_key for seg in middle.fold_profile] == [
        "seam_bend_middle_left", "w_middle", "seam_bend_middle_right"
    ]
    assert middle.fold_profile[0].length == pytest.approx(12.0)
    assert middle.fold_profile[-1].length == pytest.approx(12.0)
    seam_bends = [b for b in middle.structural.bends if b.name in {"seam_bend_middle_left", "w_middle"}]
    assert len(seam_bends) == 2
    assert all(b.p1.y == pytest.approx(20.0) for b in seam_bends)


def test_three_piece_width_controls_keep_sides_linked_and_middle_absorbs_remainder():
    from phase6_box_body_structure import set_three_piece_width

    state = _three_piece_state()
    state = set_three_piece_width(state, 1200.0, "left", 80)
    snapshot = _snapshot(w=1200.0)
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    assert [p.formed_width for p in resolved.pieces] == pytest.approx([80.0, 1040.0, 80.0])

    state = set_three_piece_width(state, 1201.0, "middle", 1000)
    snapshot = _snapshot(w=1201.0)
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1201.0, h=1600.0, t=2.0, structure_state=state
    )
    assert [p.formed_width for p in resolved.pieces] == pytest.approx([100.5, 1000.0, 100.5])
    with pytest.raises(ValueError, match="只接受整數"):
        set_three_piece_width(state, 1201.0, "middle", 1000.5)


def test_three_piece_default_50mm_seams_naturally_avoid_55mm_base_plate_shrink():
    from ae_engine.box_body_structure import apply_base_plate_structure_reliefs
    from ae_engine.sheetmetal_part_adapters import build_base_plate_result

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _three_piece_state()
    structure = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    base = build_base_plate_result(
        w=1200.0, h=1600.0, t=2.0,
        shrink_top=55.0, shrink_bottom=55.0, shrink_left=55.0, shrink_right=55.0, bend=15.0,
    )
    relieved = apply_base_plate_structure_reliefs(
        base, box_w=1200.0, shrink_left=55.0, shrink_right=55.0, thickness=2.0,
        structure=structure, structure_state=state,
    )
    assert relieved.outline == base.outline
    assert relieved.bends == base.bends


def test_side_back_split_keeps_side_d_adds_full_height_15mm_rear_bends_and_flat_back_panel():
    from phase6_box_body_structure import set_side_back_geometry

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = set_active_structure(
        default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT
    )
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    left, back, right = resolved.pieces
    assert [p.role for p in resolved.pieces] == ["left_side", "back", "right_side"]
    assert left.fold_profile[-1].phase6_key == "side_rear_bend_left"
    assert left.fold_profile[-1].length == pytest.approx(15.0)
    assert right.fold_profile[0].phase6_key == "side_rear_bend_right"
    assert right.fold_profile[0].length == pytest.approx(15.0)
    assert sum(1 for seg in left.fold_profile if seg.core == "D") == 1
    assert sum(1 for seg in right.fold_profile if seg.core == "D") == 1
    # Back panel is W - 0.5T and has no bends; all three inherit one resolved box-body height.
    assert back.structural.width == pytest.approx(1199.0)
    assert back.structural.bends == ()
    assert left.structural.height == pytest.approx(back.structural.height)
    assert right.structural.height == pytest.approx(back.structural.height)

    state = set_side_back_geometry(state, side_rear_bend=18, back_width_comp_t=1.0)
    resolved = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    left, back, right = resolved.pieces
    assert left.fold_profile[-1].length == pytest.approx(18.0)
    assert right.fold_profile[0].length == pytest.approx(18.0)
    assert back.structural.width == pytest.approx(1198.0)


def test_back_circle_crossing_two_piece_seam_is_clipped_to_each_piece_without_moving_source_geometry():
    from ae_engine.box_body_structure import resolve_box_body_piece_face_features
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor, ResolvedProfile

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _two_piece_state()
    structure = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    hole = CircleFeature(
        anchor=FeatureAnchor.PANEL_CENTER,
        offset=__import__('ae_engine.sheetmetal_geometry', fromlist=['Vec2']).Vec2(0.0, 0.0),
        diameter=40.0,
        layer="CUTTING",
    )
    resolved = resolve_box_body_piece_face_features(
        structure, face_features={"back": [hole]},
        w=1200.0, h=1600.0, d=400.0, t=2.0,
    )
    assert len(resolved["box_body_left"]) == 1
    assert len(resolved["box_body_right"]) == 1
    assert isinstance(resolved["box_body_left"][0], ResolvedProfile)
    assert isinstance(resolved["box_body_right"][0], ResolvedProfile)
    assert resolved["box_body_left"][0].layer == "CUTTING"
    assert resolved["box_body_right"][0].layer == "CUTTING"


def test_back_feature_fully_on_one_side_is_not_duplicated_to_other_piece():
    from ae_engine.box_body_structure import resolve_box_body_piece_face_features
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = _two_piece_state()
    structure = resolve_box_body_structure(
        build_box_body_profile(snapshot), w=1200.0, h=1600.0, t=2.0, structure_state=state
    )
    hole = CircleFeature(
        anchor=FeatureAnchor.PANEL_CENTER, offset=Vec2(-300.0, 0.0), diameter=20.0, layer="CUTTING",
    )
    resolved = resolve_box_body_piece_face_features(
        structure, face_features={"back": [hole]}, w=1200.0, h=1600.0, d=400.0, t=2.0,
    )
    assert len(resolved["box_body_left"]) == 1
    assert resolved["box_body_right"] == []


def test_manufacturing_api_builds_independent_w_split_render_data_with_clipped_cross_seam_cutting():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2
    from phase6_fold_profiles import profile_to_fold_segments

    snapshot = _snapshot(w=1200.0, t=2.0)
    profile = build_box_body_profile(snapshot)
    crossing = CircleFeature(
        diameter=40.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(600.0, 800.0),
        source_type="test_crossing",
    )
    spec = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(profile),
        face_features={"back": (crossing,)},
        structure_state=_two_piece_state(),
        head_ybottom1=15.0, tail_ybottom1=15.0,
    )
    data = build_box_body_structure_render_data(spec)
    assert [p.key for p in data.pieces] == ["box_body_left", "box_body_right"]
    assert all(p.render_data.material.area > 0 for p in data.pieces)
    assert all(
        any(
            isinstance(item, PolylinePrimitive) and item.layer == "CUTTING" and item.closed
            for item in p.render_data.scene.primitives[1:]
        )
        for p in data.pieces
    )


def test_manufacturing_api_exports_each_w_split_piece_from_the_same_final_scene(tmp_path):
    from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
    from ae_engine.manufacturing_api import (
        build_box_body_structure_render_data,
        generate_box_body_structure_parts,
    )
    from phase6_fold_profiles import profile_to_fold_segments

    snapshot = _snapshot(w=1200.0, t=2.0)
    spec = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=_two_piece_state(),
    )
    before = build_box_body_structure_render_data(spec)
    results = generate_box_body_structure_parts(spec, tmp_path, ManufacturingContext(overwrite=True))
    assert [r.part_kind for r in results] == ["box_body_left", "box_body_right"]
    assert all(Path(r.output_path).is_file() for r in results)
    assert all(r.exporter_name == "final_scene_box_body_structure_export" for r in results)
    # Export consumes the resolved FinalScene path, not legacy box-body reconstruction.
    assert len(before.pieces) == len(results)


def test_base_plate_part_render_data_applies_actual_box_body_seam_relief():
    from ae_engine.contracts import BasePlatePartSpec
    from ae_engine.manufacturing_api import build_part_render_data
    from ae_engine.sheetmetal_drawing import LinePrimitive
    from phase6_fold_profiles import profile_to_fold_segments

    snapshot = _snapshot(w=1200.0, t=2.0)
    spec = BasePlatePartSpec(
        width=1200.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0, shrink_left=55.0, shrink_right=55.0,
        bend=15.0,
        box_body_structure_state=_two_piece_state(),
        box_body_fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
    )
    render = build_part_render_data(spec)
    bottom_bends = sorted(
        (round(p.p1.x, 6), round(p.p2.x, 6))
        for p in render.scene.primitives
        if isinstance(p, LinePrimitive) and p.layer == "BEND" and abs(p.p1.y - p.p2.y) < 1e-9 and p.p1.y < 20
    )
    assert bottom_bends == [(15.0, 550.0), (570.0, 1105.0)]


def test_structure_3d_mesh_assembles_w_split_to_one_box_envelope():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_final_scene_view import _phase6_box_body_structure_meshes
    from phase6_fold_profiles import profile_to_fold_segments

    snapshot = _snapshot(w=1200.0, t=2.0)
    spec = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=_two_piece_state(),
    )
    data = build_box_body_structure_render_data(spec)
    meshes = _phase6_box_body_structure_meshes(data, thickness=2.0)
    assert len(meshes) == 2
    pts = [p for item in meshes for tri in item[1] for p in tri]
    xs = [p[0] for p in pts]; zs = [p[2] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(1196.0, abs=1e-6)
    assert max(zs) - min(zs) == pytest.approx(396.0, abs=1e-6)


def test_structure_3d_mesh_assembles_side_back_panels_in_world_orientation():
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_final_scene_view import _phase6_box_body_structure_meshes
    from phase6_fold_profiles import profile_to_fold_segments
    from phase6_box_body_structure import set_active_structure

    snapshot = _snapshot(w=1200.0, t=2.0)
    state = set_active_structure(default_box_body_structure_state(), BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT)
    spec = BoxBodyPartSpec(
        width=1200.0, height=1600.0, depth=400.0, thickness=2.0, frame_width=25.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
    )
    data = build_box_body_structure_render_data(spec)
    meshes = _phase6_box_body_structure_meshes(data, thickness=2.0)
    assert [item[0].role for item in meshes] == ["left_side", "back", "right_side"]
    # Side rear flanges remain on the rear outer layer (z=0).  The flat back
    # panel is the WRAP target and must sit one sheet thickness inward so its
    # outer skin contacts the wrapper/side-flange inner skin instead of sharing
    # the same mid-plane and creating a full-thickness penetration.
    back_pts = [p for piece, tris in meshes if piece.role == "back" for tri in tris for p in tri]
    assert {round(p[2], 6) for p in back_pts} == {2.0}
    side_pts = [p for piece, tris in meshes if "side" in piece.role for tri in tris for p in tri]
    assert min(p[2] for p in side_pts) == pytest.approx(0.0)
    assert max(p[2] for p in side_pts) == pytest.approx(396.0)


def test_real_box_body_settings_page_uses_persistent_structure_selector_and_context_parameters():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()
        assert designer.structure_choice_button.winfo_exists()
        assert designer.structure_type_var.get() == "一體成型"
        page = designer.settings_panel.page_cache["box_body"]
        widgets = _phase6_test_descendants(page["frame"])
        texts = [str(w.cget("text")) for w in widgets if "text" in w.keys()]
        assert "結構參數" in texts
        assert "W 左" not in texts  # 一體成型沒有 W 分件尺寸
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()

def test_real_box_body_structure_selector_drives_two_piece_final_geometry():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()
        designer.structure_type_var.set("二件式（W 二分）")
        bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
        root.update_idletasks(); root.update()
        state = designer.designer_workspace.box_body_structure_state()
        assert state["active_type"] == BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
        cfg = state["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
        assert cfg["left_w"] is not None and cfg["right_w"] is not None
        render_data = bridge._phase6_query_final_render_data(designer)
        assert [piece.role for piece in render_data.pieces] == ["left", "right"]
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()



def test_real_global_w_edit_reconciles_two_piece_at_commit_without_weakening_resolver():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()

        # Establish a normal committed W=1200 through the real global-settings seam.
        w_var = designer.settings_panel.left_global_vars["w"]
        w_var.set("1200")
        designer.flush_pending_settings()
        root.update_idletasks(); root.update()

        state = set_active_structure(
            designer.designer_workspace.box_body_structure_state(),
            BoxBodyStructureType.TWO_PIECE_W_SPLIT,
        )
        state["locked"] = False
        state = set_two_piece_width(state, 1200.0, "left", 600)
        designer.designer_workspace.set_box_body_structure_state(state)

        # A normal global W edit preserves the driving side and complements the other.
        w_var.set("1300")
        designer.flush_pending_settings()
        root.update_idletasks(); root.update()
        cfg = designer.designer_workspace.box_body_structure_state()["configs"][
            BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
        ]
        assert cfg["left_w"] == pytest.approx(600.0)
        assert cfg["right_w"] == pytest.approx(700.0)

        import fold_designer_bridge as bridge
        render_data = bridge._phase6_query_final_render_data(designer)
        assert [piece.formed_w_end - piece.formed_w_start for piece in render_data.pieces] == pytest.approx([600.0, 700.0])

        # If a new total W cannot satisfy the split, reject/revert the W edit.
        w_var.set("80")
        designer.flush_pending_settings()
        root.update_idletasks(); root.update()
        assert float(designer._phase6_box_whd["w"]) == pytest.approx(1300.0)
        assert float(w_var.get()) == pytest.approx(1300.0)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()

def _phase6_test_descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(_phase6_test_descendants(child))
    return out


def _phase6_test_unlock_and_choose(designer, root, label):
    # 結構選擇已移到永久置頂區，不再依附 settings-page 的解鎖按鈕。
    import fold_designer_bridge as bridge
    designer.activate_part("box_body")
    root.update_idletasks(); root.update()
    designer.structure_type_var.set(label)
    bridge._phase6_select_box_structure_type(designer, designer.structure_type_var)
    root.update_idletasks(); root.update()
    return designer.settings_panel.page_cache["box_body"]["frame"]


def test_real_w_split_advanced_relief_controls_are_collapsed_by_default_and_expand_on_demand():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        page = _phase6_test_unlock_and_choose(designer, root, "二件式（W 二分）")
        widgets = _phase6_test_descendants(page)
        toggle = next(w for w in widgets if "text" in w.keys() and "截角／避讓" in str(w.cget("text")))
        advanced = next(w for w in widgets if w.winfo_class() == "TLabelframe" and str(w.cget("text")) == "截角／避讓")
        assert str(toggle.cget("text")).startswith("▶")
        assert advanced.grid_info() == {}

        toggle.invoke(); root.update_idletasks(); root.update()
        page = designer.settings_panel.page_cache["box_body"]["frame"]
        widgets = _phase6_test_descendants(page)
        toggle = next(w for w in widgets if "text" in w.keys() and "截角／避讓" in str(w.cget("text")))
        advanced = next(w for w in widgets if w.winfo_class() == "TLabelframe" and str(w.cget("text")) == "截角／避讓")
        assert str(toggle.cget("text")).startswith("▼")
        assert advanced.grid_info() != {}
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_real_side_back_structure_shows_readonly_formed_depth_d():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui

    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        page = _phase6_test_unlock_and_choose(designer, root, "三件式（側背分離）")
        texts = [str(w.cget("text")) for w in _phase6_test_descendants(page) if "text" in w.keys()]
        assert any(text.startswith("側板成型深度 D：") and text.endswith(" mm") for text in texts)
    finally:
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
