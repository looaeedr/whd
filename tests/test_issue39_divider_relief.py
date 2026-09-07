# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ae_engine.assembly_collision import (
    project_joint_interference_to_relief_owner,
    discover_joint_relief_candidate,
)
from ae_engine import ae
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
        zl1=snapshot["zl1"], zl2=snapshot["zl2"], zr1=ae.zr1_def, zr2=snapshot["zr2"],
        z_comp=ae.z_comp_def,
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



def test_t3_probe_generic_corner_fitter_can_solve_divider_from_physical_projection():
    from shapely.ops import unary_union

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    joint = _divider_insert_joint(divider.stable_id)
    initial_parts = (body, divider_part)
    world = bridge._phase6_build_joint_world_geometry(initial_parts, dims, snapshot["t"])

    candidates = []
    for corner_name in ("bottom_left", "bottom_right", "top_left", "top_right"):
        candidate = discover_joint_relief_candidate(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            topology_levels=None,
            relief_component=divider_part.render_data.material,
            clearance=0.0,
            corner_name_override=corner_name,
        )
        measurement = getattr(getattr(candidate, "corner_relief", None), "measurement", None)
        print(
            "divider_candidate", corner_name,
            "status=", candidate.status,
            "measurement=", measurement,
            "cut_bounds=", None if candidate.cut_polygon_2d is None else candidate.cut_polygon_2d.bounds,
        )
        if candidate.status == "CANDIDATE":
            candidates.append(candidate)

    assert len(candidates) == 4
    cut = unary_union([candidate.cut_polygon_2d for candidate in candidates])
    solved_divider = bridge._phase6_apply_resolved_cut_to_part(divider_part, cut)
    solved_world = bridge._phase6_build_joint_world_geometry(
        (body, solved_divider), dims, snapshot["t"]
    )
    residual = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=solved_world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=solved_world["mapped_skin_triangles_by_part"],
        flat_material_by_part=solved_world["flat_material_by_part"],
    )
    print("divider_post_pairs=", residual.projection.pair_count)
    print("divider_post_illegal=", residual.illegal_penetration)
    assert residual.illegal_penetration is False



def test_t3_probe_collision_source_piece_bands():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    joint = _divider_insert_joint(divider.stable_id)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snapshot["t"]
    )

    for source_key in ("box_body:left_side", "box_body:back", "box_body:right_side"):
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        mids = []
        for a, b in projected.projection.segments_2d:
            mids.append(((float(a[0])+float(b[0]))/2.0, (float(a[1])+float(b[1]))/2.0))
        xs = [p[0] for p in mids]
        ys = [p[1] for p in mids]
        print(
            "divider_piece_projection", source_key,
            "pairs=", projected.projection.pair_count,
            "illegal=", projected.illegal_penetration,
            "x_range=", None if not xs else (min(xs), max(xs)),
            "y_range=", None if not ys else (min(ys), max(ys)),
        )
        low = sorted({round(x, 3) for x, y in mids if y < 2.0})
        high = sorted({round(x, 3) for x, y in mids if y > 794.0})
        print("  low_end_x=", low[:40], "...", low[-20:] if low else [])
        print("  high_end_x=", high[:40], "...", high[-20:] if high else [])

    assert True



def test_t3_probe_side_skin_and_divider_mating_datums():
    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snapshot["t"]
    )

    for key in ("box_body:left_side", "box_body:right_side", divider.stable_id):
        tris = world["world_triangles_by_part"][key]
        pts = [p for tri in tris for p in tri[:3]]
        xs = [float(p[0]) for p in pts]
        print("datum_world", key, "x_bounds=", (min(xs), max(xs)))

        skins = world["mapped_skin_triangles_by_part"][key]
        skin_pts = [record.world[i] for record in skins for i in range(3)]
        skin_x = [float(p[0]) for p in skin_pts]
        print("datum_skin", key, "x_bounds=", (min(skin_x), max(skin_x)))

    # Product semantics: W=800 outside and T=2 means side-sheet midplanes at
    # ±399; their inner skins are ±398. Divider span W-2T=796 terminates at
    # ±398 and must mate, not penetrate, those inner skins.
    left = world["world_triangles_by_part"]["box_body:left_side"]
    right = world["world_triangles_by_part"]["box_body:right_side"]
    left_x = [float(p[0]) for tri in left for p in tri[:3]]
    right_x = [float(p[0]) for tri in right for p in tri[:3]]
    print("expected_side_midplanes=", (-399.0, 399.0))
    print("actual_side_world_extremes=", (min(left_x), max(right_x)))
    assert True
