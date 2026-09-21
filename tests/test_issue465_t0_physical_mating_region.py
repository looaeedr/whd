from __future__ import annotations

import pytest


def _left_frame():
    from ae_engine.inner_door_frames import derive_inner_door_frames

    return derive_inner_door_frames(
        "upper",
        spans={"top": 600.0, "bottom": 600.0, "left": 900.0, "right": 900.0},
        thickness=2.0,
        included_sides=("top", "left", "right"),
    )[1]


def test_r1_inner_door_owner_publishes_lower_terminal_mating_region():
    import ae_engine.inner_door_frames as owner

    resolver = getattr(owner, "inner_door_frame_mating_region", None)
    assert callable(resolver), "R1: Inner Door Frame owner must publish a terminal mating-region API"

    region = resolver(_left_frame(), "LOWER_TERMINAL_FACE")
    assert region.region_id == "LOWER_TERMINAL_FACE"
    assert region.region_role == "LOWER_TERMINAL"
    assert region.physical_face_kind == "TERMINAL_BOUNDARY_WALL"
    assert region.flat_boundary_axis == "Y"
    assert region.flat_boundary_side == "MIN"
    assert tuple(region.flat_outward_normal) == pytest.approx((0.0, -1.0))


def test_r2_neutral_contract_and_resolver_build_true_solid_terminal_face():
    import ae_engine.assembly_geometry as geometry
    import ae_engine.contracts as contracts
    import ae_engine.inner_door_frames as owner
    from ae_engine.contracts import FoldProfileSegment
    from ae_engine.manufacturing_api import build_inner_door_frame_render_data

    contract_type = getattr(contracts, "ResolvedPhysicalMatingRegion", None)
    resolver = getattr(geometry, "resolve_physical_mating_region", None)
    owner_resolver = getattr(owner, "inner_door_frame_mating_region", None)

    assert contract_type is not None, "R2: ResolvedPhysicalMatingRegion contract is missing"
    assert callable(resolver), "R2: neutral physical mating-region resolver is missing"
    assert callable(owner_resolver), "R1 prerequisite: owner semantic API is missing"

    frame = _left_frame()
    render_data = build_inner_door_frame_render_data(frame)
    semantic = owner_resolver(frame, "LOWER_TERMINAL_FACE")

    resolved = resolver(
        part_id=frame.stable_id,
        semantic=semantic,
        render_data=render_data,
        x_profile=frame.fold_profile,
        y_profile=(FoldProfileSegment(frame.span),),
        placement="inner_door_frame_left",
        dimensions=(800.0, 1600.0, 350.0),
        offset=(-317.5, 225.0, 95.0),
        sheet_thickness=frame.thickness,
    )

    assert isinstance(resolved, contract_type)
    assert resolved.part_id == frame.stable_id
    assert resolved.region_id == "LOWER_TERMINAL_FACE"
    assert resolved.physical_face_kind == "TERMINAL_BOUNDARY_WALL"
    assert resolved.flat_mapping is None
    assert len(resolved.world_polygon) >= 4
    assert resolved.supporting_plane is not None
    assert tuple(resolved.outward_normal) == pytest.approx((0.0, -1.0, 0.0))


def test_terminal_region_identity_is_stable_while_world_face_follows_placement():
    import ae_engine.assembly_geometry as geometry
    import ae_engine.inner_door_frames as owner
    from ae_engine.contracts import FoldProfileSegment
    from ae_engine.manufacturing_api import build_inner_door_frame_render_data

    resolver = getattr(geometry, "resolve_physical_mating_region", None)
    owner_resolver = getattr(owner, "inner_door_frame_mating_region", None)
    assert callable(resolver) and callable(owner_resolver)

    def solve(span: float, offset_y: float):
        frame = derive_frame(span)
        return resolver(
            part_id=frame.stable_id,
            semantic=owner_resolver(frame, "LOWER_TERMINAL_FACE"),
            render_data=build_inner_door_frame_render_data(frame),
            x_profile=frame.fold_profile,
            y_profile=(FoldProfileSegment(frame.span),),
            placement="inner_door_frame_left",
            dimensions=(800.0, 1600.0, 350.0),
            offset=(-317.5, offset_y, 95.0),
            sheet_thickness=frame.thickness,
        )

    def derive_frame(span: float):
        from ae_engine.inner_door_frames import derive_inner_door_frames

        return derive_inner_door_frames(
            "upper",
            spans={"top": 600.0, "left": span, "right": span},
            thickness=2.0,
            included_sides=("top", "left", "right"),
        )[1]

    first = solve(900.0, 225.0)
    moved = solve(880.0, 240.0)

    assert first.region_id == moved.region_id == "LOWER_TERMINAL_FACE"
    assert first.part_id == moved.part_id == "inner_door:upper:left_frame"
    assert first.world_polygon != moved.world_polygon


def test_t0_does_not_emit_joint_placement_marking():
    from ae_engine.manufacturing_api import build_inner_door_frame_render_data

    data = build_inner_door_frame_render_data(_left_frame())
    primitives = tuple(getattr(data.scene, "primitives", ()) or ())
    assert not any(
        str(getattr(p, "layer", "")).upper() == "MARKING"
        and str(getattr(p, "source_type", "")).startswith("joint_placement")
        for p in primitives
    )



def test_t0_resolver_has_no_bbox_or_renderer_authority():
    import ast
    import inspect
    from ae_engine import assembly_geometry as geometry
    from ae_engine import inner_door_frames as owner

    resolver_tree = ast.parse(inspect.getsource(geometry.resolve_physical_mating_region))
    owner_tree = ast.parse(inspect.getsource(owner.inner_door_frame_mating_region))

    resolver_names = {
        node.id for node in ast.walk(resolver_tree) if isinstance(node, ast.Name)
    }
    resolver_attrs = {
        node.attr for node in ast.walk(resolver_tree) if isinstance(node, ast.Attribute)
    }
    owner_calls = {
        node.func.id
        for node in ast.walk(owner_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "triangle_bounds" not in resolver_names
    assert "bounds" not in resolver_attrs
    assert "renderer" not in resolver_names
    assert "collision" not in resolver_names
    assert "min" not in owner_calls
    assert "max" not in owner_calls


def test_inner_door_frame_dxf_roundtrip_is_unchanged_by_t0(tmp_path):
    from ae_engine import manufacturing_api as api

    data = api.build_inner_door_frame_render_data(_left_frame())
    path = tmp_path / "inner-door-left-frame.dxf"
    api.save_part_render_data_dxf(data, path, overwrite=True)

    result = api.verify_saved_part_render_data_dxf(data, path)
    assert result.ok is True
    assert result.issues == ()



def test_resolved_mating_region_preserves_locator_flat_mapping_provenance():
    from ae_engine.contracts import ResolvedPhysicalMatingRegion

    mapping = {
        "kind": "AUTHORITATIVE_MAPPED_PHYSICAL_FACE",
        "flat_basis": ((1.0, 0.0), (0.0, 1.0)),
        "source": "canonical_folded_uv",
    }
    provenance = {
        "semantic_owner": "ae_engine.box_body_dividers",
        "mapping_source": "folded_mesh_with_flat_uv_from_polygon",
    }
    region = ResolvedPhysicalMatingRegion(
        part_id="box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
        region_id="CORE_PHYSICAL_SEGMENT",
        region_role="LOCATOR_SUPPORT_FACE",
        physical_face_kind="MAPPED_SKIN",
        supporting_plane=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        outward_normal=(0.0, 1.0, 0.0),
        world_polygon=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)),
        flat_mapping=mapping,
        provenance=provenance,
    )

    assert region.flat_mapping is mapping
    assert region.provenance is provenance
    assert region.flat_mapping["source"] == "canonical_folded_uv"
