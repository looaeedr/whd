from __future__ import annotations

import os
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement


def _snapshot():
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "door_gap_w": 3.5,
        "door_gap_h": 3.5,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    }


def test_r06_outer_door_has_authoritative_placement_contract():
    placement = resolve_assembly_placement(_snapshot(), "door_c1_r1")
    assert placement.stable_id == "door_c1_r1"
    assert placement.parent_assembly_node == "box_body"
    assert placement.relationship == "OUTER_DOOR"
    assert placement.mate_target == "box_body:front_opening"
    assert placement.placement_kind == "receiving_outer_door"
    assert placement.anchor == "door_layout_cell:0:0"
    assert placement.world_offset == pytest.approx((0.0, 250.0, 175.0))


def test_r06_panel_and_top_left_right_frames_share_outer_door_datum():
    panel = resolve_assembly_placement(_snapshot(), "inner_door:upper:panel")
    assert panel.relationship == "INNER_DOOR_PANEL"
    assert panel.mate_target == "door_c1_r1"
    assert panel.placement_kind == "inner_door_panel"
    assert panel.world_offset == pytest.approx((0.0, 225.0, 95.0))

    expected = {
        "inner_door:upper:top_frame": ("inner_door_frame_top", (0.0, 730.0, 95.0)),
        "inner_door:upper:left_frame": ("inner_door_frame_left", (-313.5, 225.0, 95.0)),
        "inner_door:upper:right_frame": ("inner_door_frame_right", (313.5, 225.0, 95.0)),
    }
    for stable_id, (kind, offset) in expected.items():
        placement = resolve_assembly_placement(_snapshot(), stable_id)
        assert placement.stable_id == stable_id
        assert placement.parent_assembly_node == "box_body:door_layout:inner_door"
        assert placement.relationship == "INNER_DOOR_FRAME"
        assert placement.placement_kind == kind
        assert placement.world_offset == pytest.approx(offset)


def test_r06_divider_guard_stays_authoritative_and_repeatable():
    stable_id = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    first = resolve_assembly_placement(_snapshot(), stable_id)
    second = resolve_assembly_placement(_snapshot(), stable_id)
    assert first == second
    assert first.relationship == "SHARED_STRUCTURAL_DIVIDER"
    assert first.placement_kind == "divider_horizontal"
    assert first.world_offset == pytest.approx((0.0, -300.0, 0.0))


def test_unknown_receiving_derived_part_must_fail_closed_not_origin_fallback():
    with pytest.raises(ValueError, match="no authoritative placement contract"):
        resolve_assembly_placement(_snapshot(), "inner_door:upper:unknown")


def test_workspace_stores_all_supported_receiving_placements():
    from phase6_designer_workspace import Phase6DesignerWorkspace

    parts = (
        "box_body", "door_c1_r1",
        "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
        "inner_door:upper:top_frame", "inner_door:upper:left_frame",
        "inner_door:upper:right_frame", "inner_door:upper:panel",
    )
    ws = Phase6DesignerWorkspace.from_snapshot({"existing_parts": list(parts)})
    stored = ws.resolve_and_store_assembly_placements(_snapshot(), resolver=resolve_assembly_placement)
    for key in parts[1:]:
        assert key in stored
        assert stored[key]["world_offset"] != [0.0, 0.0, 0.0] or key.startswith("box_body:divider:")


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_3d_and_collision_scene_consume_resolver_offsets_and_frame_orientation():
    import tkinter as tk
    import gui
    import fold_designer_bridge as bridge

    root = tk.Tk(); root.withdraw(); app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
        by_key = {part.part_key: part for part in resolved.parts}
        snapshot = designer._phase6_input_snapshot
        for key in (
            "door_c1_r1",
            "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
            "inner_door:upper:panel",
        ):
            expected = resolve_assembly_placement(snapshot, key)
            assert by_key[key].placement == expected.placement_kind
            assert by_key[key].offset == pytest.approx(expected.world_offset)

        dims = bridge._phase6_operator_finished_dimensions(designer)
        world = bridge._phase6_build_joint_world_geometry(resolved.parts, dims, 2.0)
        tri = world["world_triangles_by_part"]
        def bounds(key):
            pts = [p for t in tri[key] for p in t[:3]]
            return tuple((min(p[i] for p in pts), max(p[i] for p in pts)) for i in range(3))
        body = bounds("box_body")
        divider = bounds("box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1")
        assert divider[2][0] >= body[2][0] - 1e-6
        assert divider[2][1] <= body[2][1] + 1e-6
        top = bounds("inner_door:upper:top_frame")
        assert (top[0][1] - top[0][0]) > (top[1][1] - top[1][0])
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass


def test_receiving_family_coordinate_contract_exposes_front_skin_door_plane_and_inward_direction():
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    contract = cabinet_family_policy.assembly_coordinate_contract(
        _snapshot(), depth=350.0, thickness=2.0
    )
    assert contract is not None
    assert contract["front_axis"] == "Z"
    assert contract["body_front_skin"] == pytest.approx(174.0)
    assert contract["outer_door_plane"] == pytest.approx(175.0)
    assert tuple(contract["inward_vector"]) == pytest.approx((0.0, 0.0, -1.0))


def test_2d_receiving_overlay_consumes_authoritative_placement_not_local_50px_offsets():
    import inspect
    import gui

    source = inspect.getsource(gui.BoxCalculatorGUI._draw_door_layout_dividers_and_frames)
    assert "resolve_assembly_placement" in source
    assert "inset_px = 50.0 * scale" not in source
    assert "world_to_canvas" in source
