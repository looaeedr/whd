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


def test_receiving_panel_and_frames_use_physical_box_body_mates():
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from ae_engine.inner_door_frames import derive_all_inner_door_frames

    snapshot = _snapshot()
    panel = resolve_assembly_placement(snapshot, "inner_door:upper:panel")
    manufactured = cabinet_family_policy.derive_inner_door_panels(snapshot)[0]
    # From the two physical side-sheet inner skins, not Box Body outer W.
    from ae_engine.cabinet_types.receiving import inner_door_body_clear_width
    assert inner_door_body_clear_width(cell_width=800.0, thickness=2.0) == pytest.approx(796.0)
    assert manufactured.width == pytest.approx(689.0)
    assert manufactured.unfolded_width == pytest.approx(723.0)
    assert panel.relationship == "INNER_DOOR_PANEL"
    assert panel.mate_target == "inner_door:upper:frame_opening"
    assert panel.world_offset[0] == pytest.approx(0.0)
    # The rendered 3D envelope must consume the same formed dimensions.
    import ae_engine.assembly_placement as placement
    envelope = placement._inner_door_geometry(snapshot, "upper")
    assert envelope["panel_width"] == pytest.approx(689.0)
    assert panel.world_offset[2] == pytest.approx(95.0)

    top = resolve_assembly_placement(snapshot, "inner_door:upper:top_frame")
    # Final 22-mm flange faces the EndCap's underside at H/2 - T = 798.
    assert top.mate_target == "head"
    assert top.world_offset == pytest.approx((0.0, 774.0, 95.0))

    vertical = cabinet_family_policy.inner_door_vertical_frame_contract(
        snapshot, "upper"
    )
    assert vertical["top_terminal_y"] == pytest.approx(750.0)
    assert panel.world_offset[1] == pytest.approx(
        (vertical["top_terminal_y"] + vertical["lower_terminal_y"]) / 2.0
    )
    frames = {
        row.stable_id: row
        for row in derive_all_inner_door_frames(
            cabinet_family_policy.derive_inner_door_frame_sets(snapshot)
        )
    }
    expected = {
        "inner_door:upper:left_frame": (-362.0, "box_body:left_side"),
        "inner_door:upper:right_frame": (373.0, "box_body:right_side"),
    }
    for stable_id, (x, mother_plate) in expected.items():
        placement = resolve_assembly_placement(snapshot, stable_id)
        frame = frames[stable_id]
        assert placement.mate_target == mother_plate
        assert placement.world_offset == pytest.approx(
            (x, vertical["center_y"], 95.0)
        )
        assert frame.span == pytest.approx(vertical["span"])
        assert placement.world_offset[1] + frame.span / 2.0 == pytest.approx(
            vertical["top_terminal_y"]
        )
        assert placement.world_offset[1] - frame.span / 2.0 == pytest.approx(
            vertical["lower_terminal_y"]
        )


@pytest.mark.parametrize("outer_fw,door_gap", [(29.0, 2.0), (35.0, 5.0)])
def test_physical_frame_mates_do_not_follow_outer_door_finished_edge(outer_fw, door_gap):
    from ae_engine.cabinet_types import policy as cabinet_family_policy

    baseline = _snapshot()
    modified = _snapshot()
    modified["fw"] = outer_fw
    modified["door_gap_w"] = door_gap

    # Changing an outer Door's frame width/gap may affect finished Door
    # sizing but must NEVER move the inner frame's last-22-mm attachment
    # from the actual Box Body side/head mother-plate skins.
    for side in ("left", "right", "top"):
        key = f"inner_door:upper:{side}_frame"
        before = resolve_assembly_placement(baseline, key)
        after = resolve_assembly_placement(modified, key)
        assert after.mate_target == before.mate_target
        assert after.world_offset[0] == pytest.approx(before.world_offset[0])
        assert after.world_offset[2] == pytest.approx(before.world_offset[2])
        if side == "top":
            assert after.world_offset[1] == pytest.approx(before.world_offset[1])

    panels = cabinet_family_policy.derive_inner_door_panels(modified)
    assert len(panels) == 1
    assert panels[0].width == pytest.approx(800 - 2 * 2 - 100 - 2 * door_gap)
    frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(modified)
    assert frame_sets[0].spans["top"] == pytest.approx(696.0)


def test_r06_divider_guard_stays_authoritative_and_repeatable():
    stable_id = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    first = resolve_assembly_placement(_snapshot(), stable_id)
    second = resolve_assembly_placement(_snapshot(), stable_id)
    assert first == second
    assert first.relationship == "SHARED_STRUCTURAL_DIVIDER"
    assert first.placement_kind == "divider_horizontal_inward"
    assert first.world_offset[:2] == pytest.approx((0.0, -300.0))
    # Depth is geometry-derived from the shared FW formed-face relation.
    # Do not lock a world-Z probe value here; Issue48 verifies the real skins.
    assert first.world_offset[2] != pytest.approx(0.0)


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
        assert stored[key]["world_offset"] != [0.0, 0.0, 0.0]


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
    from gui_modules.application import render_snapshots
    from gui_modules.rendering import door_view

    snapshot_source = inspect.getsource(render_snapshots.door_layout_divider_frame_snapshot)
    divider_view = inspect.getsource(door_view._draw_door_layout_divider_payload)
    frame_view = inspect.getsource(door_view._draw_door_layout_frame_payload)
    render_source = divider_view + frame_view
    assert "resolve_assembly_placement" in snapshot_source
    assert "world_offset" in snapshot_source
    assert "inset_px = 50.0 * scale" not in snapshot_source + render_source
    assert "_door_layout_world_to_canvas" in render_source
