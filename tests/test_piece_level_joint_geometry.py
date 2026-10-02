# -*- coding: utf-8 -*-

import pytest


def _receiving_body_part():
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from phase6_box_body_structure import default_box_body_structure_state
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
    from phase6_final_scene_view import AssemblyScenePart

    snapshot = {
        "model": "受電箱",
        "w": 800.0,
        "h": 600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "zl1": 24.0,
        "zl2": 24.0,
        "zr1": 0.0,
        "zr2": 18.0,
        "yl1": 15.0,
        "yr1": 15.0,
        "ytop1": 16.0,
        "ybottom1": 15.0,
    }
    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    data = build_box_body_structure_render_data(BoxBodyPartSpec(
        width=800.0,
        height=600.0,
        depth=350.0,
        thickness=2.0,
        frame_width=29.0,
        model_name="受電箱",
        zl1=24.0,
        zl2=24.0,
        zr1=0.0,
        zr2=18.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
        head_ybottom1=15.0,
        tail_ybottom1=15.0,
    ))
    return AssemblyScenePart(
        part_key="box_body",
        render_data=data,
        x_profile=(),
        y_profile=(),
        placement="box_body",
    )


def test_joint_world_geometry_exposes_side_back_split_piece_uv_and_aggregate_world_solid():
    import fold_designer_bridge as bridge

    body = _receiving_body_part()
    world = bridge._phase6_build_joint_world_geometry(
        (body,), (800.0, 600.0, 350.0), 2.0
    )

    piece_keys = {"box_body:left_side", "box_body:back", "box_body:right_side"}
    assert piece_keys.issubset(world["world_triangles_by_part"])
    assert piece_keys.issubset(world["mapped_skin_triangles_by_part"])
    assert piece_keys.issubset(world["flat_material_by_part"])

    # box_body is a world-space aggregate only; three unrelated piece UV planes
    # must never be forged into one flat material coordinate system.
    assert "box_body" in world["world_triangles_by_part"]
    assert "box_body" not in world["flat_material_by_part"]
    aggregate = tuple(world["world_triangles_by_part"]["box_body"])
    piece_total = sum(len(world["world_triangles_by_part"][key]) for key in piece_keys)
    assert len(aggregate) == piece_total
    assert all(world["mapped_skin_triangles_by_part"][key] for key in piece_keys)


def test_piece_level_endpoint_resolution_maps_rear_and_side_regions_to_physical_piece_keys():
    import fold_designer_bridge as bridge

    body = _receiving_body_part()
    assert bridge._phase6_box_body_piece_solver_key(body, "rear_mating", require_flat_uv=True) == "box_body:back"
    assert bridge._phase6_box_body_piece_solver_key(body, "REAR_PANEL", require_flat_uv=True) == "box_body:back"
    assert bridge._phase6_box_body_piece_solver_key(body, "left_mating_zone", require_flat_uv=True) == "box_body:left_side"
    assert bridge._phase6_box_body_piece_solver_key(body, "right_side", require_flat_uv=True) == "box_body:right_side"

    # A preserve-only endpoint may use the aggregate solid, but a relief owner
    # must identify one physical piece so its flat UV remains unambiguous.
    assert bridge._phase6_box_body_piece_solver_key(body, "mating_zone", require_flat_uv=False) == "box_body"
    with pytest.raises(ValueError, match="piece-level relief region"):
        bridge._phase6_box_body_piece_solver_key(body, "mating_zone", require_flat_uv=True)
