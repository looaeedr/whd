from __future__ import annotations

import ezdxf

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import (
    FoldProfileSegment,
    ResolvedManufacturingGeometry,
    ResolvedManufacturingPart,
)
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
            x_profile=tuple(divider.fold_profile),
            y_profile=(FoldProfileSegment(
                length=float(divider.span), angle=None, phase6_key="divider_span"
            ),),
            placement=placement.placement_kind,
            offset=tuple(placement.world_offset),
        ))
    for frame in frames:
        placement = resolve_assembly_placement(snapshot, frame.stable_id)
        parts.append(ResolvedManufacturingPart(
            part_key=frame.stable_id,
            render_data=build_inner_door_frame_render_data(frame),
            x_profile=tuple(frame.fold_profile),
            y_profile=(FoldProfileSegment(
                length=float(frame.span), angle=None, phase6_key="frame_span"
            ),),
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


def test_issue509_frame_owned_upper_horizontal_rule_is_superseded_by_receiver_contact(tmp_path):
    from ae_engine import receiving_joint_marking as marking

    snapshot = _snapshot()
    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        _build_geometry(snapshot),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    frame_ids = (
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
    )
    for part_id in frame_ids:
        _data, marks = _joint_marks(resolution.geometry, part_id)
        assert marks == [], "#509 frame-owned marking must not regrow"

    divider_id = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    data, divider_marks = _joint_marks(resolution.geometry, divider_id)
    assert len(divider_marks) == 2
    rows = tuple(data.metadata.get("joint_markings") or ())
    assert len(rows) == 2
    assert {row["locator_part_id"] for row in rows} == {divider_id}
    assert {row["attached_part_id"] for row in rows} == {
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
    }
    assert all(row["geometry_source"] == "RECEIVER_MATING_CONTACT_BACKPROJECTION" for row in rows)

    emitted = [row for row in resolution.results if row.status == "EMITTED"]
    assert len(emitted) == 2
    assert {row.locator_part_id for row in emitted} == {divider_id}
    # This deliberately sparse fixture has no shell mother plates. Their absence
    # must fail closed rather than pushing marks back onto the frames.
    missing = [row for row in resolution.results if row.status != "EMITTED"]
    assert {row.locator_part_id for row in missing} == {
        "box_body:left_side", "box_body:right_side", "head"
    }
    assert all(row.diagnostic_code == "LOCATOR_MISSING" for row in missing)

    outputs = save_resolved_manufacturing_geometry_dxf(
        resolution.geometry, tmp_path, overwrite=True
    )
    doc = ezdxf.readfile(outputs[divider_id])
    saved = [
        entity for entity in doc.modelspace()
        if entity.dxftype() == "LINE" and str(entity.dxf.layer) == "MARKING"
    ]
    assert len(saved) == 2
