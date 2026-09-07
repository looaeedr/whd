# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ae_engine.assembly_collision import project_joint_interference_to_relief_owner
from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
from ae_engine.assembly_placement import resolve_divider_placement
from ae_engine.cabinet_types import receiving
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.manufacturing_api import (
    build_box_body_divider_render_data,
    build_box_body_structure_render_data,
)
from phase6_box_body_structure import default_box_body_structure_state
from phase6_final_scene_view import AssemblyScenePart
from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments
import fold_designer_bridge as bridge


def _snapshot():
    data = receiving.apply_family_defaults({})
    data.update({
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 29.0,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "multi_door_enabled": True,
    })
    return data


def _body_part(snapshot):
    state = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    render = build_box_body_structure_render_data(BoxBodyPartSpec(
        width=snapshot["w"], height=snapshot["h"], depth=snapshot["d"],
        thickness=snapshot["t"], frame_width=snapshot["fw"], model_name="受電箱",
        zl1=snapshot["zl1"], zl2=snapshot["zl2"], zr1=snapshot.get("zr1", 0.0), zr2=snapshot["zr2"],
        fold_profile=profile_to_fold_segments(build_box_body_profile(snapshot)),
        structure_state=state,
        head_ybottom1=snapshot["ybottom1"], tail_ybottom1=snapshot["ybottom1"],
    ))
    return AssemblyScenePart(
        part_key="box_body", render_data=render, x_profile=(), y_profile=(),
        placement="box_body", offset=(0.0, 0.0, 0.0),
    )


def _divider_part(snapshot):
    divider = derive_box_body_dividers(
        tuple((float(w), tuple(float(h) for h in hs)) for w, hs in snapshot["door_layout_columns"]),
        depth=snapshot["d"], thickness=snapshot["t"],
        layout_scope=snapshot["door_layout_scope"], handle_edges={}, model_name="受電箱",
    )[0]
    render = build_box_body_divider_render_data(
        divider, context=ManufacturingContext()
    )
    placement = resolve_divider_placement(snapshot, divider.stable_id)
    profiles = {
        "X": [
            {"len": float(row.length), **({"angle": float(row.angle)} if row.angle is not None else {})}
            for row in divider.fold_profile
        ],
        "Y": [{"len": float(divider.span)}],
    }
    return divider, AssemblyScenePart(
        part_key=divider.stable_id, render_data=render,
        x_profile=tuple(profiles["X"]), y_profile=tuple(profiles["Y"]),
        placement=placement.placement_kind, offset=placement.world_offset,
    )


def _divider_insert_joint(stable_id):
    return AssemblyJoint(
        joint_id=f"{stable_id}:box_body:family",
        subject_part=stable_id,
        target_part="box_body",
        subject_region="assembly_relief",
        target_region="divider_mating_zone",
        relation=AssemblyJointRelation.INSERT,
        source=AssemblyJointSource.FAMILY_GEOMETRY,
        solver_constraints={"relief_mode": "BOUNDARY_MULTI_CORNER"},
    )


def test_t3_red_real_receiving_divider_has_pre_solve_illegal_penetration():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part),
        (snapshot["w"], snapshot["h"], snapshot["d"]),
        snapshot["t"],
    )
    joint = _divider_insert_joint(divider.stable_id)
    projected = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
    )
    print("divider_pre_pairs=", projected.projection.pair_count)
    print("divider_pre_segments_2d=", projected.projection.segments_2d)
    assert projected.preserve_part == "box_body"
    assert projected.relief_part == divider.stable_id
    assert projected.illegal_penetration is True
    assert projected.projection.pair_count > 0


def test_t3_red_current_canonical_divider_has_no_post_collision_relief():
    snapshot = _snapshot()
    divider, divider_part = _divider_part(snapshot)
    exterior = list(divider_part.render_data.material.exterior.coords)
    assert len(exterior) > 5, (
        "current canonical Divider remains nominal rectangle; "
        f"exterior={exterior}"
    )
