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


def test_t3_nominal_divider_stays_pre_relief_rectangle():
    """T2 owns nominal geometry; T3 relief is intentionally assembly-dependent."""
    snapshot = _snapshot()
    divider, divider_part = _divider_part(snapshot)
    exterior = list(divider_part.render_data.material.exterior.coords)
    assert len(exterior) == 5
    assert "divider_assembly_relief" not in divider_part.render_data.metadata

def test_t3_family_solver_commits_verified_relief_and_preserves_mating_contact():
    from ae_engine.assembly_collision import verify_divider_front_fold_relief

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])

    solved_parts, diagnostics, family_joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=dims,
        sheet_thickness=snapshot["t"],
        clearance=0.0,
    )
    by_key = {part.part_key: part for part in solved_parts}
    print("family_divider_diagnostics=", diagnostics)
    solved = by_key[divider.stable_id]
    exterior = list(solved.render_data.material.exterior.coords)

    assert len(family_joints) == 1
    assert family_joints[0].subject_part == divider.stable_id
    assert family_joints[0].target_part == "box_body"
    assert len(exterior) > 5

    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    assert relief["verified"] is True
    assert relief["trust_level"] == "PROVISIONAL_3D"
    assert relief["core_start"] == pytest.approx(41.0)
    cut_depths = dict(relief["cut_depths"])
    assert cut_depths["box_body:left_side"] > 0.0
    assert cut_depths["box_body:right_side"] > 0.0
    # This fixture is left/right symmetric, so the dynamic collision result
    # must also be symmetric. Do not hard-code the case output in millimetres.
    assert cut_depths["box_body:left_side"] == pytest.approx(
        cut_depths["box_body:right_side"], abs=1e-4
    )
    placement = dict(dict(relief["evidence"]).get("placement") or {})
    assert placement.get("contract") == "DIVIDER_FW_FACE_FLUSH_V1"
    assert placement.get("fw_face_flush") is True
    assert placement.get("core_inward") is True
    assert placement.get("valid") is True
    projection_by_source = dict(dict(relief["evidence"])["projection_by_source"])
    expected_pre_pairs = sum(int(dict(row)["pair_count"]) for row in projection_by_source.values())
    assert relief["pre_pair_count"] == expected_pre_pairs
    assert relief["pre_pair_count"] > 0
    assert relief["retained_contact_segments"] > 0

    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.candidate_status == "PROVISIONAL_3D_VERIFIED"
    assert diag.preserve_part == "box_body"
    assert diag.relief_part == divider.stable_id
    assert diag.illegal_penetration is False
    assert diag.pre_pair_count == expected_pre_pairs
    assert diag.post_pair_count > 0

    solved_world = bridge._phase6_build_joint_world_geometry(
        tuple(solved_parts), dims, snapshot["t"]
    )
    verification = verify_divider_front_fold_relief(
        family_joints[0],
        world_triangles_by_part=solved_world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=solved_world["mapped_skin_triangles_by_part"],
        flat_material_by_part=solved_world["flat_material_by_part"],
        core_start=41.0,
        source_geometry_keys=("box_body:left_side", "box_body:right_side"),
    )
    assert verification["verified"] is True
    assert verification["front_illegal_segments"] == 0
    assert verification["retained_contact_segments"] > 0

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



def _projection_segments_in_front_relief_band(projection, *, core_start=41.0, tolerance=1e-6):
    rows = []
    for segment in tuple(projection.segments_2d or ()):
        xs = [float(segment[0][0]), float(segment[1][0])]
        if min(xs) < float(core_start) - float(tolerance):
            rows.append(segment)
    return tuple(rows)


def _divider_collision_depth_for_edge(projection, material, *, edge):
    minx, miny, maxx, maxy = map(float, material.bounds)
    points = [
        (float(p[0]), float(p[1]))
        for segment in _projection_segments_in_front_relief_band(projection)
        for p in segment
    ]
    if not points:
        return 0.0
    if edge == "min":
        return max(0.0, max(p[1] for p in points) - miny)
    return max(0.0, maxy - min(p[1] for p in points))


def _part_with_material(part, material):
    from dataclasses import replace
    from ae_engine.assembly_collision import _scene_with_replaced_primary_cutting

    render = replace(
        part.render_data,
        material=material,
        scene=_scene_with_replaced_primary_cutting(part.render_data.scene, material),
    )
    return replace(part, render_data=render)


def test_t3_probe_front_fold_domain_cut_from_collision_clears_only_illegal_zone():
    from shapely.geometry import box as shapely_box

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    dims = (snapshot["w"], snapshot["h"], snapshot["d"])
    joint = _divider_insert_joint(divider.stable_id)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part), dims, snapshot["t"]
    )
    raw_material = divider_part.render_data.material
    minx, miny, maxx, maxy = map(float, raw_material.bounds)

    left_projection = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        source_geometry_key="box_body:left_side",
    ).projection
    right_projection = project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part=world["world_triangles_by_part"],
        mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
        flat_material_by_part=world["flat_material_by_part"],
        source_geometry_key="box_body:right_side",
    ).projection

    core_index = next(
        i for i, row in enumerate(divider.fold_profile)
        if str(getattr(row, "core", "") or "") == "D_DIVIDER"
    )
    core_start = sum(float(row.length) for row in divider.fold_profile[:core_index])
    assert core_start == pytest.approx(41.0)

    left_depth = _divider_collision_depth_for_edge(left_projection, raw_material, edge="min")
    right_depth = _divider_collision_depth_for_edge(right_projection, raw_material, edge="max")
    print("divider_front_relief_core_start=", core_start)
    print("divider_collision_cut_depths=", (left_depth, right_depth))
    assert left_depth > 0.0
    assert right_depth > 0.0

    eps = 1e-4
    cuts = [
        shapely_box(minx - eps, miny - eps, core_start + eps, miny + left_depth + eps),
        shapely_box(minx - eps, maxy - right_depth - eps, core_start + eps, maxy + eps),
    ]
    solved_material = raw_material.difference(cuts[0].union(cuts[1]))
    solved = _part_with_material(divider_part, solved_material)
    solved_world = bridge._phase6_build_joint_world_geometry(
        (body, solved), dims, snapshot["t"]
    )

    residual_front = 0
    residual_contact = 0
    for source_key in ("box_body:left_side", "box_body:right_side"):
        projected = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=solved_world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=solved_world["mapped_skin_triangles_by_part"],
            flat_material_by_part=solved_world["flat_material_by_part"],
            source_geometry_key=source_key,
        )
        front = _projection_segments_in_front_relief_band(
            projected.projection, core_start=core_start
        )
        residual_front += len(front)
        residual_contact += max(0, len(projected.projection.segments_2d) - len(front))
        print(
            "divider_residual", source_key,
            "pairs=", projected.projection.pair_count,
            "front_illegal_segments=", len(front),
            "retained_contact_segments=", max(0, len(projected.projection.segments_2d)-len(front)),
        )

    assert residual_front == 0
    assert residual_contact > 0



def test_t3_solved_divider_bends_and_scene_material_share_one_final_geometry():
    from shapely.geometry import LineString
    from ae_engine.manufacturing_api import material_polygon_from_final_scene
    from ae_engine.sheetmetal_drawing import LinePrimitive

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    render = solved.render_data

    rebuilt = material_polygon_from_final_scene(render.scene)
    assert rebuilt.symmetric_difference(render.material).area == pytest.approx(0.0, abs=1e-8)

    bend_lines = [
        primitive for primitive in render.scene.primitives
        if isinstance(primitive, LinePrimitive)
        and str(primitive.layer).upper() == "BEND"
    ]
    assert bend_lines
    covered = render.material.buffer(1e-7)
    for bend in bend_lines:
        line = LineString([
            (float(bend.p1.x), float(bend.p1.y)),
            (float(bend.p2.x), float(bend.p2.y)),
        ])
        assert line.difference(covered).length == pytest.approx(0.0, abs=1e-8)

    assert diagnostics[0].illegal_penetration is False
