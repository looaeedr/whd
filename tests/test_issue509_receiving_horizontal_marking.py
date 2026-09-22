from __future__ import annotations

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import derive_all_inner_door_frames
from ae_engine.manufacturing_api import (
    build_box_body_divider_render_data,
    build_inner_door_frame_render_data,
    save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.sheetmetal_drawing import LinePrimitive


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


def _build_geometry(snapshot):
    frames = derive_all_inner_door_frames(
        cabinet_family_policy.derive_inner_door_frame_sets(snapshot)
    )
    dividers = derive_box_body_dividers(
        snapshot["door_layout_columns"],
        depth=float(snapshot["d"]),
        thickness=float(snapshot["t"]),
        layout_scope=snapshot["door_layout_scope"],
        model_name=snapshot["model"],
        frame_width=float(snapshot["fw"]),
    )
    parts = []
    for divider in dividers:
        placement = resolve_assembly_placement(snapshot, divider.stable_id)
        parts.append(ResolvedManufacturingPart(
            part_key=divider.stable_id,
            render_data=build_box_body_divider_render_data(divider),
            placement=placement.placement_kind,
            offset=tuple(placement.world_offset),
        ))
    for frame in frames:
        placement = resolve_assembly_placement(snapshot, frame.stable_id)
        parts.append(ResolvedManufacturingPart(
            part_key=frame.stable_id,
            render_data=build_inner_door_frame_render_data(frame),
            placement=placement.placement_kind,
            offset=tuple(placement.world_offset),
        ))
    return ResolvedManufacturingGeometry(parts=tuple(parts))


def _joint_marks(geometry, part_id):
    data = geometry.part(part_id).render_data
    return data, [
        primitive
        for primitive in tuple(data.scene.primitives)
        if isinstance(primitive, LinePrimitive)
        and str(primitive.layer) == "MARKING"
    ]


def test_receiving_top_left_right_frames_each_own_upper_horizontal_marking(tmp_path):
    from ae_engine import receiving_joint_marking as marking

    snapshot = _snapshot()
    original = _build_geometry(snapshot)
    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        original,
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    expected = (
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
    )
    for part_id in expected:
        data, marks = _joint_marks(resolution.geometry, part_id)
        assert len(marks) == 1, (part_id, marks)
        line = marks[0]
        assert float(line.p1.y) == pytest.approx(float(line.p2.y))
        assert abs(float(line.p2.x) - float(line.p1.x)) > 0.0

        rows = tuple(data.metadata.get("joint_markings") or ())
        assert len(rows) == 1
        assert rows[0]["boundary_role"] == "UPPER_HORIZONTAL"
        assert rows[0]["locator_part_id"] == part_id

    divider_id = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    _divider, divider_marks = _joint_marks(resolution.geometry, divider_id)
    assert divider_marks == []

    outputs = save_resolved_manufacturing_geometry_dxf(
        resolution.geometry, tmp_path, overwrite=True
    )
    for part_id in expected:
        doc = ezdxf.readfile(outputs[part_id])
        saved = [
            entity for entity in doc.modelspace()
            if entity.dxftype() == "LINE"
            and str(entity.dxf.layer) == "MARKING"
        ]
        assert len(saved) == 1
        start = saved[0].dxf.start
        end = saved[0].dxf.end
        assert float(start.y) == pytest.approx(float(end.y))
