# -*- coding: utf-8 -*-
"""T09 — LEFT/RIGHT WRAP + multi-WRAP joint-local target relief contracts."""
from types import SimpleNamespace

import pytest
from shapely.geometry import box

from ae_engine.assembly_joint import AssemblyJoint, AssemblyJointRelation, AssemblyJointSource
from ae_engine.sheetmetal_drawing import DrawingScene
from ae_engine.manufacturing_api import PartRenderData
from phase6_final_scene_view import AssemblyScenePart


def _render(material):
    scene = DrawingScene()
    minx, miny, maxx, maxy = map(float, material.bounds)
    scene.add_polyline(
        [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)],
        layer="CUTTING",
        closed=True,
    )
    return PartRenderData(scene=scene, material=material, fold_guides=(), metadata={})


def _endcap_part(part_key="head"):
    return AssemblyScenePart(
        part_key=part_key,
        render_data=_render(box(0, 0, 120, 80)),
        x_profile=({"len": 120.0, "core": True},),
        y_profile=({"len": 80.0, "core": True},),
        placement="top" if part_key == "head" else "bottom",
    )


def _side_wrap_joint(part_key, edge):
    edge = str(edge).upper()
    return AssemblyJoint(
        joint_id=f"{part_key}:{edge}:wrap",
        subject_part=part_key,
        target_part="box_body",
        subject_region=f"{edge.lower()}_edge",
        target_region=f"{edge.lower()}_mating_zone",
        relation=AssemblyJointRelation.WRAP,
        source=AssemblyJointSource.USER_ADDED,
        edge=edge,
    )


def _piece_by_role(body_part, role):
    return next(piece for piece in body_part.render_data.pieces if piece.role == role)


def test_joint_projection_keeps_canonical_owner_but_can_use_piece_level_geometry_key(monkeypatch):
    import ae_engine.assembly_collision as collision

    joint = _side_wrap_joint("head", "LEFT")
    fake_projection = SimpleNamespace(has_interference=True, pair_count=2, segments_2d=())
    monkeypatch.setattr(
        collision,
        "backproject_world_interference_to_flat",
        lambda source, mapped, tolerance=1e-6: fake_projection,
    )
    monkeypatch.setattr(
        collision,
        "classify_joint_interference",
        lambda *args, **kwargs: SimpleNamespace(illegal_penetration=True, has_contact=True),
    )

    result = collision.project_joint_interference_to_relief_owner(
        joint,
        world_triangles_by_part={"head": ("head-world",)},
        mapped_skin_triangles_by_part={"box_body:left_side": ("left-uv",)},
        flat_material_by_part={"box_body:left_side": box(0, 0, 100, 100)},
        relief_geometry_key="box_body:left_side",
        source_geometry_key="head",
    )

    assert result.preserve_part == "head"
    assert result.relief_part == "box_body"
    assert result.relief_geometry_key == "box_body:left_side"
    assert result.source_geometry_key == "head"
    assert result.evidence["relief_geometry_key"] == "box_body:left_side"


def test_receiving_head_left_wrap_discovers_both_target_piece_end_corners_from_one_raw_material(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from tests.test_piece_level_joint_geometry import _receiving_body_part

    body = _receiving_body_part()
    head = _endcap_part("head")
    joint = _side_wrap_joint("head", "LEFT")
    raw_left = _piece_by_role(body, "left_side").render_data.material
    calls = []

    def fake_world(parts, finished_dimensions, sheet_thickness):
        body_now = next(part for part in parts if part.part_key == "box_body")
        left_now = _piece_by_role(body_now, "left_side").render_data.material
        return {
            "flat_material_by_part": {
                "box_body:left_side": left_now,
                "head": head.render_data.material,
            },
            "mapped_skin_triangles_by_part": {
                "box_body:left_side": ("left-uv",),
                "head": ("head-uv",),
            },
            "world_triangles_by_part": {
                "box_body:left_side": ("left-world",),
                "box_body": ("body-world",),
                "head": ("head-world",),
            },
        }

    def fake_discover(_joint, **kwargs):
        corner = kwargs["corner_name_override"]
        material = kwargs["flat_material_by_part"]["box_body:left_side"]
        calls.append((corner, kwargs["relief_geometry_key"], float(material.area)))
        minx, miny, maxx, maxy = map(float, material.bounds)
        if corner == "top_left":
            cut = box(minx, maxy - 10.0, minx + 10.0, maxy)
        elif corner == "top_right":
            cut = box(maxx - 10.0, maxy - 10.0, maxx, maxy)
        else:  # pragma: no cover - contract failure will show the wrong corner
            raise AssertionError(corner)
        projected = SimpleNamespace(
            joint_id=_joint.joint_id,
            preserve_part="head",
            relief_part="box_body",
            relief_geometry_key="box_body:left_side",
            source_geometry_key="head",
            projection=SimpleNamespace(pair_count=2, segments_2d=(), segments_world=()),
            illegal_penetration=True,
            has_contact=True,
            evidence={},
        )
        return SimpleNamespace(
            joint_id=_joint.joint_id,
            preserve_part="head",
            relief_part="box_body",
            relief_geometry_key="box_body:left_side",
            source_geometry_key="head",
            status="CANDIDATE",
            projection=projected,
            cut_polygon_2d=cut,
            corner_relief=SimpleNamespace(
                measurement=SimpleNamespace(
                    corner_name=corner,
                    primary_u=10.0,
                    primary_v=10.0,
                    secondary_u=None,
                    secondary_depth=None,
                )
            ),
            evidence={"corner_name": corner},
        )

    monkeypatch.setattr(bridge, "_phase6_build_joint_world_geometry", fake_world)
    monkeypatch.setattr(collision, "discover_joint_relief_candidate", fake_discover)
    monkeypatch.setattr(
        collision,
        "project_joint_interference_to_relief_owner",
        lambda *_args, **_kwargs: SimpleNamespace(
            illegal_penetration=False,
            has_contact=True,
            projection=SimpleNamespace(pair_count=0, segments_2d=(), segments_world=()),
            evidence={"post": "clear"},
        ),
    )

    solved, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head),
        (joint,),
        finished_dimensions=(800.0, 600.0, 350.0),
        sheet_thickness=2.0,
    )

    solved_body = next(part for part in solved if part.part_key == "box_body")
    left_after = _piece_by_role(solved_body, "left_side").render_data.material
    assert float(left_after.area) == pytest.approx(float(raw_left.area) - 200.0)
    assert next(part for part in solved if part.part_key == "head").render_data.material.area == pytest.approx(
        head.render_data.material.area
    )
    assert {(corner, key) for corner, key, _area in calls} == {
        ("top_left", "box_body:left_side"),
        ("top_right", "box_body:left_side"),
    }
    # Both corner discoveries must see the exact same pre-cut target material.
    assert {area for _corner, _key, area in calls} == {float(raw_left.area)}
    assert len(state["items"]) == 1
    item = state["items"][joint.joint_id]
    assert item["relief_part"] == "box_body"
    assert item["relief_geometry_key"] == "box_body:left_side"
    assert set(item["corner_names"]) == {"top_left", "top_right"}
    assert len(item["cut_polygons"]) == 2
    assert diagnostics[0].candidate_status == "PROVISIONAL_3D"
    assert diagnostics[0].illegal_penetration is False


def test_receiving_tail_right_wrap_uses_bottom_boundary_of_right_side_piece(monkeypatch):
    import ae_engine.assembly_collision as collision
    import fold_designer_bridge as bridge
    from tests.test_piece_level_joint_geometry import _receiving_body_part

    body = _receiving_body_part()
    tail = _endcap_part("tail")
    joint = _side_wrap_joint("tail", "RIGHT")
    seen = []

    def fake_world(parts, finished_dimensions, sheet_thickness):
        body_now = next(part for part in parts if part.part_key == "box_body")
        right_now = _piece_by_role(body_now, "right_side").render_data.material
        return {
            "flat_material_by_part": {"box_body:right_side": right_now, "tail": tail.render_data.material},
            "mapped_skin_triangles_by_part": {"box_body:right_side": ("right-uv",), "tail": ("tail-uv",)},
            "world_triangles_by_part": {"box_body:right_side": ("right-world",), "box_body": ("body-world",), "tail": ("tail-world",)},
        }

    def fake_discover(_joint, **kwargs):
        corner = kwargs["corner_name_override"]
        seen.append((corner, kwargs["relief_geometry_key"]))
        projected = SimpleNamespace(
            joint_id=_joint.joint_id, preserve_part="tail", relief_part="box_body",
            relief_geometry_key="box_body:right_side", source_geometry_key="tail",
            projection=SimpleNamespace(pair_count=0, segments_2d=(), segments_world=()),
            illegal_penetration=False, has_contact=True, evidence={},
        )
        return SimpleNamespace(
            joint_id=_joint.joint_id, preserve_part="tail", relief_part="box_body",
            relief_geometry_key="box_body:right_side", source_geometry_key="tail",
            status="NO_ILLEGAL_PENETRATION", projection=projected,
            cut_polygon_2d=None, corner_relief=None, evidence={"reason": "LEGAL_CONTACT_OR_CLEAR"},
        )

    monkeypatch.setattr(bridge, "_phase6_build_joint_world_geometry", fake_world)
    monkeypatch.setattr(collision, "discover_joint_relief_candidate", fake_discover)

    solved, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, tail), (joint,), finished_dimensions=(800.0, 600.0, 350.0), sheet_thickness=2.0,
    )

    assert {(corner, key) for corner, key in seen} == {
        ("bottom_left", "box_body:right_side"),
        ("bottom_right", "box_body:right_side"),
    }
    assert state["items"] == {}
    assert diagnostics[0].candidate_status == "NO_ILLEGAL_PENETRATION"
    assert next(part for part in solved if part.part_key == "box_body").render_data.pieces

@pytest.mark.parametrize("edge", ["LEFT", "RIGHT"])
def test_real_receiving_head_side_wrap_iterates_until_zero_illegal_penetration(edge):
    """Real receiving geometry must converge instead of stopping after one provisional cut."""
    import fold_designer_bridge as bridge
    from tests.test_piece_level_joint_geometry import _receiving_body_part
    from tests.test_receiving_bottom_wrap_registry import _receiving_lookup_fixture

    body = _receiving_body_part()
    render, profiles, _structure, _corner_type = _receiving_lookup_fixture("head")
    head = AssemblyScenePart(
        part_key="head",
        render_data=render,
        x_profile=tuple(profiles["X"]),
        y_profile=tuple(profiles["Y"]),
        placement="top",
    )
    joint = _side_wrap_joint("head", edge)

    solved, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head), (joint,),
        finished_dimensions=(800.0, 600.0, 350.0),
        sheet_thickness=2.0,
    )

    assert diagnostics[0].candidate_status == "PROVISIONAL_3D"
    assert diagnostics[0].illegal_penetration is False
    assert diagnostics[0].post_pair_count >= 0
    item = state["items"][joint.joint_id]
    assert item["verified"] is True
    assert item["evidence"]["solver_iterations"] > 1
    assert item["evidence"]["post_illegal_penetration"] is False
    body_after = next(part for part in solved if part.part_key == "box_body")
    role = "left_side" if edge == "LEFT" else "right_side"
    material = _piece_by_role(body_after, role).render_data.material
    assert material.is_valid
    assert not material.is_empty


def _receiving_multi_wrap_fixture(*, width=800.0, height=600.0, depth=350.0, thickness=2.0, frame_width=29.0, part_key="head"):
    """Build real receiving body + EndCap with certified BOTTOM WRAP already applied."""
    from ae_engine import manufacturing_api
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec
    from phase6_box_body_structure import default_box_body_structure_state
    from phase6_fold_profiles import build_box_body_profile, build_endcap_xy_profiles, profile_to_fold_segments

    snap = {
        "model": "受電箱", "assembly_type": "WRAP_OVERLAY",
        "w": width, "h": height, "d": depth, "t": thickness, "fw": frame_width,
        "zl1": 24.0, "zl2": 24.0, "zr1": 0.0, "zr2": 18.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
    }
    structure = receiving.resolve_box_body_structure_state(default_box_body_structure_state())
    body_data = manufacturing_api.build_box_body_structure_render_data(BoxBodyPartSpec(
        width=width, height=height, depth=depth, thickness=thickness,
        frame_width=frame_width, model_name="受電箱",
        zl1=24.0, zl2=24.0, zr1=0.0, zr2=18.0,
        fold_profile=profile_to_fold_segments(build_box_body_profile(snap)),
        structure_state=structure, head_ybottom1=15.0, tail_ybottom1=15.0,
    ))
    body = AssemblyScenePart(
        part_key="box_body", render_data=body_data,
        x_profile=(), y_profile=(), placement="box_body",
    )

    profiles = build_endcap_xy_profiles(snap, part_key=part_key)
    policy = receiving.endcap_corner_policy(
        frame_width=frame_width, thickness=thickness, side_rear_bend=15.0,
    )
    bottom_joint = AssemblyJoint(
        f"{part_key}:BOTTOM:certified", part_key, "box_body",
        "bottom_edge", "bottom_mating_zone", AssemblyJointRelation.WRAP,
        source=AssemblyJointSource.INTENT_DERIVED, edge="BOTTOM",
    )
    endcap_data = manufacturing_api.build_part_render_data(EndCapPartSpec(
        width=width, height=height, depth=depth, thickness=thickness,
        frame_width=frame_width, model_name="受電箱", is_tail=(part_key == "tail"),
        fold_left=15.0, fold_right=15.0, fold_top=16.0, fold_bottom=15.0,
        box_fold_left=24.0, box_fold_right=0.0,
        fold_profile_x=profile_to_fold_segments(profiles["X"]),
        fold_profile_y=profile_to_fold_segments(profiles["Y"]),
        corner_policy=policy, depth_comp_t=2.0,
        box_body_structure_state=structure,
        assembly_joints=(bottom_joint.to_dict(),),
    ))
    endcap = AssemblyScenePart(
        part_key=part_key, render_data=endcap_data,
        x_profile=tuple(profiles["X"]), y_profile=tuple(profiles["Y"]),
        placement="top" if part_key == "head" else "bottom",
    )
    return body, endcap, bottom_joint


def _triangle_area(triangle):
    import math
    a, b, c = triangle
    u = tuple(float(b[i]) - float(a[i]) for i in range(3))
    v = tuple(float(c[i]) - float(a[i]) for i in range(3))
    cross = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    return 0.5 * math.sqrt(sum(value * value for value in cross))


def test_wrap_overlay_bottom_left_right_is_a_legal_canonical_joint_state():
    from ae_engine.assembly_joint import edge_relation_for_part, migrate_legacy_snapshot_joints, set_part_edge_relation

    state = migrate_legacy_snapshot_joints({
        "assembly_type": "WRAP_OVERLAY",
        "existing_parts": ["box_body", "head", "tail"],
    })
    state = set_part_edge_relation(state, "head", "LEFT", AssemblyJointRelation.WRAP)
    state = set_part_edge_relation(state, "head", "RIGHT", AssemblyJointRelation.WRAP)
    assert edge_relation_for_part(state, "head", "TOP") is AssemblyJointRelation.OVERLAY
    assert edge_relation_for_part(state, "head", "BOTTOM") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(state, "head", "LEFT") is AssemblyJointRelation.WRAP
    assert edge_relation_for_part(state, "head", "RIGHT") is AssemblyJointRelation.WRAP


def test_real_receiving_multi_wrap_combines_certified_bottom_with_side_solver_and_replays_identically():
    import fold_designer_bridge as bridge
    from ae_engine.assembly_collision import project_joint_interference_to_relief_owner

    body, head, _bottom_joint = _receiving_multi_wrap_fixture()
    left = _side_wrap_joint("head", "LEFT")
    right = _side_wrap_joint("head", "RIGHT")
    trace = dict(head.render_data.metadata.get("receiving_bottom_relief_rule") or {})
    assert trace["rule_id"] == "RECEIVING_ENDCAP_BOTTOM_WRAP_V1"
    assert trace["trust_level"] == "CERTIFIED_FROM_3D"

    solved, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head), (left, right),
        finished_dimensions=(800.0, 600.0, 350.0), sheet_thickness=2.0,
    )
    assert [diag.candidate_status for diag in diagnostics] == ["PROVISIONAL_3D", "PROVISIONAL_3D"]
    assert all(diag.registry_status == "MISS" for diag in diagnostics)
    assert all(diag.illegal_penetration is False for diag in diagnostics)
    assert set(state["items"]) == {left.joint_id, right.joint_id}

    world = bridge._phase6_build_joint_world_geometry(solved, (800.0, 600.0, 350.0), 2.0)
    for joint, geometry_key in ((left, "box_body:left_side"), (right, "box_body:right_side")):
        final = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            relief_geometry_key=geometry_key, source_geometry_key="head",
        )
        assert final.illegal_penetration is False

    replayed, replay_diagnostics, replay_state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head), (left, right),
        finished_dimensions=(800.0, 600.0, 350.0), sheet_thickness=2.0,
        committed_state=state,
    )
    assert [diag.candidate_status for diag in replay_diagnostics] == [
        "PROVISIONAL_3D_REPLAYED", "PROVISIONAL_3D_REPLAYED",
    ]
    fresh_body = next(part for part in solved if part.part_key == "box_body")
    reload_body = next(part for part in replayed if part.part_key == "box_body")
    for role in ("left_side", "back", "right_side"):
        a = _piece_by_role(fresh_body, role).render_data.material
        b = _piece_by_role(reload_body, role).render_data.material
        assert float(a.symmetric_difference(b).area) <= 1e-7
    assert replay_state == state


def test_multi_wrap_stress_case_has_valid_material_positive_lengths_and_no_degenerate_world_faces():
    import fold_designer_bridge as bridge
    from ae_engine.assembly_collision import project_joint_interference_to_relief_owner

    dims = (220.0, 260.0, 120.0)
    thickness = 3.0
    body, head, _bottom_joint = _receiving_multi_wrap_fixture(
        width=dims[0], height=dims[1], depth=dims[2],
        thickness=thickness, frame_width=35.0,
    )
    left = _side_wrap_joint("head", "LEFT")
    right = _side_wrap_joint("head", "RIGHT")
    solved, diagnostics, state = bridge._phase6_resolve_explicit_joint_reliefs(
        (body, head), (left, right),
        finished_dimensions=dims, sheet_thickness=thickness,
    )
    assert all(diag.candidate_status == "PROVISIONAL_3D" for diag in diagnostics)
    assert all(diag.illegal_penetration is False for diag in diagnostics)
    assert all(item["verified"] for item in state["items"].values())

    solved_body = next(part for part in solved if part.part_key == "box_body")
    for piece in solved_body.render_data.pieces:
        material = piece.render_data.material
        assert material.is_valid
        assert not material.is_empty
        assert float(material.area) > 1e-6
        assert all(float(segment.length) > 0.0 for segment in piece.fold_profile)

    world = bridge._phase6_build_joint_world_geometry(solved, dims, thickness)
    for key, triangles in world["world_triangles_by_part"].items():
        assert triangles, key
        assert min(_triangle_area(triangle) for triangle in triangles) > 1e-9
    for joint, geometry_key in ((left, "box_body:left_side"), (right, "box_body:right_side")):
        final = project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world["world_triangles_by_part"],
            mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
            flat_material_by_part=world["flat_material_by_part"],
            relief_geometry_key=geometry_key, source_geometry_key="head",
        )
        assert final.illegal_penetration is False
