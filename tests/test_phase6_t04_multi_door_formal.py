from __future__ import annotations

from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def test_door_part_projections_use_cell_identity_edges_and_resolved_finished_size():
    import fold_designer_bridge as bridge

    snapshot = {
        "multi_door_enabled": True,
        "door_layout_columns": [[600.0, [600.0, 500.0, 700.0]], [500.0, [800.0, 1000.0]]],
        "t": 2.0, "fw": 25.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    }
    rows = bridge._phase6_door_part_projections(snapshot)
    assert tuple(row.part_key for row in rows) == (
        "door_c1_r1", "door_c1_r2", "door_c1_r3", "door_c2_r1", "door_c2_r2"
    )
    assert rows[0].frame_edges == DoorFrameEdges(left=True, right=False, top=True, bottom=False)
    assert (rows[0].start_width, rows[0].start_height) == (600.0, 600.0)
    assert (rows[0].formed_width, rows[0].formed_height) == (564.0, 564.0)
    assert rows[-1].frame_edges == DoorFrameEdges()
    assert (rows[-1].formed_width, rows[-1].formed_height) == (435.0, 935.0)


def test_single_door_snapshot_has_no_dynamic_door_projections():
    import fold_designer_bridge as bridge
    assert bridge._phase6_door_part_projections({
        "multi_door_enabled": False,
        "door_layout_columns": [[800.0, [1600.0]]],
        "t": 2.0, "fw": 25.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    }) == ()
