# -*- coding: utf-8 -*-
import pytest


def test_layout_topology_derives_vertical_and_horizontal_box_body_dividers_without_n_minus_one_shortcut():
    from ae_engine.door_dividers import derive_box_body_dividers

    parts = derive_box_body_dividers(
        [(600, [600, 500, 700]), (500, [800, 1000])],
        depth=350, thickness=2, layout_scope="cabinet-A",
        handle_edges={},
    )
    assert [(p.axis, p.boundary_key, p.owner) for p in parts] == [
        ("VERTICAL", "C0|C1", "box_body"),
        ("HORIZONTAL", "C0:R0|R1", "box_body"),
        ("HORIZONTAL", "C0:R1|R2", "box_body"),
        ("HORIZONTAL", "C1:R0|R1", "box_body"),
    ]
    assert [p.span for p in parts] == pytest.approx([1800.0, 598.0, 598.0, 496.0])


def test_divider_fold_chain_uses_per_door_handle_edge_and_converts_formed_depth_through_topology():
    from ae_engine.door_dividers import derive_box_body_dividers

    parts = derive_box_body_dividers(
        [(400, [600, 600]), (400, [1200])],
        depth=350, thickness=2, layout_scope="cabinet-A",
        handle_edges={
            "0:0": "RIGHT",   # handle touches the vertical divider
            "0:1": "LEFT",    # does not touch the horizontal boundary above it
            "1:0": "LEFT",    # also touches the vertical divider
        },
    )
    vertical = next(p for p in parts if p.axis == "VERTICAL")
    horizontal = next(p for p in parts if p.axis == "HORIZONTAL")
    assert vertical.handle_side is True
    assert vertical.signed_fold_chain[:3] == (-15.0, 20.0, 25.0)
    assert horizontal.handle_side is False
    assert horizontal.signed_fold_chain[:3] == (18.0, 20.0, 25.0)

    # User contract says the D-2T core is a *formed outside* segment.  With a
    # real bend on each side, the material segment loses another 2T.
    assert vertical.formed_core_depth == pytest.approx(346.0)
    assert vertical.material_lengths == pytest.approx((15, 20, 25, 342, 15))
    assert all(value > 0 for value in vertical.material_lengths)


def test_divider_stable_ids_do_not_change_when_only_partition_ratios_change():
    from ae_engine.door_dividers import derive_box_body_dividers

    a = derive_box_body_dividers(
        [(600, [700, 500]), (400, [1200])],
        depth=350, thickness=2, layout_scope="cabinet-A",
    )
    b = derive_box_body_dividers(
        [(550, [650, 550]), (450, [1200])],
        depth=350, thickness=2, layout_scope="cabinet-A",
    )
    assert {p.stable_id for p in a} == {p.stable_id for p in b}
    assert all(p.stable_id.startswith("box_body:divider:cabinet-A:") for p in a)


def test_receiving_upper_inner_door_uses_horizontal_divider_as_lower_frame_role_without_bottom_frame_part():
    from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role
    from ae_engine.inner_door_frames import derive_inner_door_frames

    dividers = derive_box_body_dividers(
        [(800, [1100, 500])], depth=350, thickness=2, layout_scope="receiving-main"
    )
    role = resolve_inner_door_lower_frame_role("upper", dividers)
    assert role is not None
    assert role.role == "lower_frame"
    assert role.divider_stable_id == dividers[0].stable_id
    assert dividers[0].owner == "box_body"

    frames = derive_inner_door_frames(
        "upper", spans={"top": 700, "left": 1000, "right": 1000}, thickness=2,
        included_sides=("top", "left", "right"),
    )
    assert {f.side for f in frames} == {"top", "left", "right"}
    assert not any(f.side == "bottom" for f in frames)


def test_shared_lower_frame_reference_keeps_id_across_ratio_change_and_drops_when_boundary_disappears():
    from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role

    first = derive_box_body_dividers([(800, [1100, 500])], depth=350, thickness=2, layout_scope="R")
    role1 = resolve_inner_door_lower_frame_role("upper", first)
    changed_ratio = derive_box_body_dividers([(800, [1000, 600])], depth=350, thickness=2, layout_scope="R")
    role2 = resolve_inner_door_lower_frame_role("upper", changed_ratio, previous_divider_stable_id=role1.divider_stable_id)
    assert role2.divider_stable_id == role1.divider_stable_id

    no_boundary = derive_box_body_dividers([(800, [1600])], depth=350, thickness=2, layout_scope="R")
    assert resolve_inner_door_lower_frame_role(
        "upper", no_boundary, previous_divider_stable_id=role1.divider_stable_id
    ) is None


def test_divider_is_selectable_physical_part_and_manufacturing_uses_same_material_chain():
    from ae_engine.door_dividers import derive_box_body_dividers, divider_part_profiles
    from ae_engine.manufacturing_api import build_box_body_divider_render_data, measure_unfolded_blanks
    from phase6_designer_workspace import Phase6DesignerWorkspace

    divider = derive_box_body_dividers(
        [(800, [1100, 500])], depth=350, thickness=2, layout_scope="R"
    )[0]
    data = build_box_body_divider_render_data(divider)
    blank = measure_unfolded_blanks(data, part_key=divider.stable_id)[0]
    assert blank.width == pytest.approx(sum(divider.material_lengths))
    assert blank.height == pytest.approx(divider.span)
    assert data.metadata["owner"] == "box_body"
    assert data.metadata["stable_id"] == divider.stable_id

    workspace = Phase6DesignerWorkspace.from_snapshot({"existing_parts": ["box_body", "door"]})
    workspace.sync_derived_parts(namespace="box_body:divider:", part_profiles=divider_part_profiles((divider,)))
    assert divider.stable_id in workspace.available_parts
    assert workspace.select_part(divider.stable_id)
    workspace.sync_derived_parts(namespace="box_body:divider:", part_profiles={})
    assert divider.stable_id not in workspace.available_parts
