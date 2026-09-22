from __future__ import annotations

import json

import ezdxf
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.door_dividers import derive_box_body_dividers
from ae_engine.inner_door_frames import derive_all_inner_door_frames
from ae_engine.manufacturing_api import (
    BoxBodyStructureRenderData,
    build_box_body_divider_render_data,
    build_inner_door_frame_render_data,
    save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.sheetmetal_drawing import LinePrimitive


POLICY_ID = "RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_V2"
GATE_B_STATE = "JOINT_PLACEMENT_MARKING_PRODUCTION_ENABLED"
DISPOSITION = "ALLOW_EXPORT_WITH_DIAGNOSTIC"
FRAME_IDS = (
    "inner_door:upper:top_frame",
    "inner_door:upper:left_frame",
    "inner_door:upper:right_frame",
)
DIVIDER_ID = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"


def _snapshot(rows=(1100.0, 500.0)):
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
        "door_layout_columns": [[800.0, list(rows)]],
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


def _api():
    from ae_engine import receiving_joint_marking as marking

    assert marking.PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition == DISPOSITION
    assert marking.RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY.policy_id == POLICY_ID
    assert marking.RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY.policy_id == POLICY_ID
    assert callable(marking.resolve_joint_marking_production_status)
    assert callable(marking.resolve_receiving_joint_markings)
    return marking


def _mark_rows(geometry, part_id):
    data = geometry.part(part_id).render_data
    rows = [
        p for p in tuple(data.scene.primitives)
        if isinstance(p, LinePrimitive) and str(p.layer) == "MARKING"
    ]
    return data, rows


def _line_signature(rows):
    return tuple(sorted(
        (
            round(float(row.p1.x), 6),
            round(float(row.p1.y), 6),
            round(float(row.p2.x), 6),
            round(float(row.p2.y), 6),
        )
        for row in rows
    ))


def _frame_line_signatures(geometry):
    return {
        part_id: _line_signature(_mark_rows(geometry, part_id)[1])
        for part_id in FRAME_IDS
        if geometry.part(part_id) is not None
    }


def test_gate_b_status_and_selected_export_disposition_are_production_active():
    marking = _api()
    status = marking.resolve_joint_marking_production_status()

    assert status.gate_state == GATE_B_STATE
    assert status.activation_enabled is True
    assert status.export_disposition == DISPOSITION
    assert status.production_policy_count == 1


def test_receiving_top_left_right_frames_emit_one_upper_horizontal_mark_each(tmp_path):
    marking = _api()
    snapshot = _snapshot()
    original = _build_geometry(snapshot)
    before = {}
    for part_id in FRAME_IDS:
        data = original.part(part_id).render_data
        before[part_id] = (
            bytes(data.material.wkb),
            tuple(
                repr(p) for p in data.scene.primitives
                if str(getattr(p, "layer", "")) != "MARKING"
            ),
        )

    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        original,
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    assert resolution.status.gate_state == GATE_B_STATE
    assert len(resolution.results) == 3
    assert {r.locator_part_id for r in resolution.results} == set(FRAME_IDS)
    assert all(r.status == "EMITTED" for r in resolution.results), repr(resolution.results)
    assert all(r.export_disposition == DISPOSITION for r in resolution.results)
    assert all(len(r.mark_ids) == 1 for r in resolution.results)
    assert len({mid for r in resolution.results for mid in r.mark_ids}) == 3

    for part_id in FRAME_IDS:
        data, marks = _mark_rows(resolution.geometry, part_id)
        assert len(marks) == 1
        mark = marks[0]
        assert float(mark.p1.y) == pytest.approx(float(mark.p2.y))
        assert float(mark.p2.x) > float(mark.p1.x)
        metadata = tuple(data.metadata["joint_markings"])
        assert len(metadata) == 1
        assert metadata[0]["boundary_role"] == "UPPER_HORIZONTAL"
        assert metadata[0]["locator_part_id"] == part_id
        assert bytes(data.material.wkb) == before[part_id][0]
        assert tuple(
            repr(p) for p in data.scene.primitives
            if str(getattr(p, "layer", "")) != "MARKING"
        ) == before[part_id][1]

    _divider, divider_marks = _mark_rows(resolution.geometry, DIVIDER_ID)
    assert divider_marks == []

    outputs = save_resolved_manufacturing_geometry_dxf(
        resolution.geometry, tmp_path, overwrite=True
    )
    for part_id in FRAME_IDS:
        doc = ezdxf.readfile(outputs[part_id])
        saved_marks = [
            entity for entity in doc.modelspace()
            if entity.dxftype() == "LINE" and str(entity.dxf.layer) == "MARKING"
        ]
        assert len(saved_marks) == 1
        start = saved_marks[0].dxf.start
        end = saved_marks[0].dxf.end
        assert float(start.y) == pytest.approx(float(end.y))


def test_marking_failure_allows_dxf_but_is_machine_readable_and_non_silent(tmp_path):
    marking = _api()
    snapshot = _snapshot()
    geometry = _build_geometry(snapshot)
    without_frames = ResolvedManufacturingGeometry(
        parts=tuple(
            part for part in geometry.parts
            if not str(part.part_key).startswith("inner_door:upper:")
        )
    )

    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        without_frames,
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    assert len(resolution.results) == 3
    assert all(r.status == "SKIPPED_FAIL_CLOSED" for r in resolution.results)
    assert all(r.diagnostic_code in {"LOCATOR_MISSING", "STALE_STABLE_ID"} for r in resolution.results)
    assert all(r.export_disposition == DISPOSITION for r in resolution.results)
    assert all(not r.mark_ids for r in resolution.results)

    outputs = save_resolved_manufacturing_geometry_dxf(
        resolution.geometry, tmp_path, overwrite=True
    )
    assert outputs
    summary = marking.joint_marking_export_summary(resolution.results)
    assert len(summary) == 3
    assert all(row["status"] == "SKIPPED_FAIL_CLOSED" for row in summary)
    assert all(row["export_disposition"] == DISPOSITION for row in summary)
    assert all(row["diagnostic_code"] for row in summary)


def test_save_reload_and_ratio_change_keep_semantic_ids_without_stale_rebinding():
    marking = _api()
    snapshot = _snapshot()
    first = marking.resolve_receiving_joint_markings(
        snapshot,
        _build_geometry(snapshot),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    lines1 = _frame_line_signatures(first.geometry)
    ids1 = tuple(sorted(mid for r in first.results for mid in r.mark_ids))

    reloaded_snapshot = json.loads(json.dumps(snapshot, ensure_ascii=False))
    reloaded = marking.resolve_receiving_joint_markings(
        reloaded_snapshot,
        _build_geometry(reloaded_snapshot),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    lines2 = _frame_line_signatures(reloaded.geometry)
    ids2 = tuple(sorted(mid for r in reloaded.results for mid in r.mark_ids))
    assert ids2 == ids1
    assert lines2 == lines1

    changed = _snapshot()
    changed["door_gap_w"] = 10.0
    moved = marking.resolve_receiving_joint_markings(
        changed,
        _build_geometry(changed),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    lines3 = _frame_line_signatures(moved.geometry)
    ids3 = tuple(sorted(mid for r in moved.results for mid in r.mark_ids))
    assert ids3 == ids1
    assert lines3 != lines1

    no_boundary = _snapshot((1600.0,))
    failed = marking.resolve_receiving_joint_markings(
        no_boundary,
        first.geometry,
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    assert failed.results
    assert all(r.status == "SKIPPED_FAIL_CLOSED" for r in failed.results)
    assert all(not r.mark_ids for r in failed.results)
    for part_id in FRAME_IDS:
        if failed.geometry.part(part_id) is not None:
            _data, stale_lines = _mark_rows(failed.geometry, part_id)
            assert stale_lines == []


def test_marking_cleanup_leaves_composite_box_body_render_owner_untouched():
    marking = _api()
    snapshot = _snapshot()
    geometry = _build_geometry(snapshot)
    preview = geometry.parts[0].render_data
    composite = BoxBodyStructureRenderData(
        structure_type="TEST_COMPOSITE",
        pieces=(),
        preview_render_data=preview,
        canonical_strip_render_data=preview,
    )
    box_body = ResolvedManufacturingPart(
        part_key="box_body",
        render_data=composite,
        placement="box_body",
        offset=(0.0, 0.0, 0.0),
    )
    with_box_body = ResolvedManufacturingGeometry(
        parts=(box_body,) + tuple(geometry.parts),
    )

    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        with_box_body,
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    resolved_box_body = resolution.geometry.part("box_body")
    assert resolved_box_body is not None
    assert resolved_box_body.render_data is composite
    assert not hasattr(resolved_box_body.render_data, "metadata")
    assert len(resolution.results) == 3
    assert all(result.status == "EMITTED" for result in resolution.results)
