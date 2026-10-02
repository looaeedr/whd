from __future__ import annotations

import json

import pytest

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
)
from ae_engine.sheetmetal_drawing import LinePrimitive


POLICY_ID = "RECEIVING_INNER_DOOR_MOTHER_PLATE_CONTACT_V3"
GATE_B_STATE = "JOINT_PLACEMENT_MARKING_PRODUCTION_ENABLED"
DISPOSITION = "ALLOW_EXPORT_WITH_DIAGNOSTIC"
DIVIDER_ID = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
FRAME_IDS = (
    "inner_door:upper:top_frame",
    "inner_door:upper:left_frame",
    "inner_door:upper:right_frame",
)


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


def _mark_lines(geometry, part_id):
    data = geometry.part(part_id).render_data
    return tuple(
        p for p in tuple(data.scene.primitives)
        if isinstance(p, LinePrimitive) and str(p.layer) == "MARKING"
    )


def _api():
    from ae_engine import receiving_joint_marking as marking

    assert marking.PRODUCTION_JOINT_MARKING_FAILURE_POLICY.disposition == DISPOSITION
    assert marking.RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY.policy_id == POLICY_ID
    # Compatibility symbols may remain importable, but cannot restore V2 semantics.
    assert marking.RECEIVING_INNER_DOOR_VERTICAL_FRAME_POLICY.policy_id == POLICY_ID
    assert marking.RECEIVING_INNER_DOOR_FRAME_UPPER_HORIZONTAL_POLICY.policy_id == POLICY_ID
    return marking


def test_gate_b_status_and_receiver_owned_policy_are_production_active():
    marking = _api()
    status = marking.resolve_joint_marking_production_status()
    assert status.gate_state == GATE_B_STATE
    assert status.activation_enabled is True
    assert status.export_disposition == DISPOSITION
    assert status.production_policy_count == 1
    policy = marking.RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
    assert policy.locator_selector == "RECEIVING_MOTHER_PLATE"
    assert policy.footprint_mode == "ACTUAL_CONTACT_BOUNDARY"


def test_sparse_fixture_emits_real_divider_contacts_and_never_falls_back_to_frames():
    marking = _api()
    snapshot = _snapshot()
    resolution = marking.resolve_receiving_joint_markings(
        snapshot,
        _build_geometry(snapshot),
        dimensions=(800.0, 1600.0, 350.0),
        sheet_thickness=2.0,
        cabinet_family="受電箱",
    )

    emitted = tuple(row for row in resolution.results if row.status == "EMITTED")
    assert len(emitted) == 2
    assert {row.locator_part_id for row in emitted} == {DIVIDER_ID}
    assert {row.attached_part_id for row in emitted} == {
        "inner_door:upper:left_frame", "inner_door:upper:right_frame"
    }
    assert len(_mark_lines(resolution.geometry, DIVIDER_ID)) == 2
    for frame_id in FRAME_IDS:
        assert _mark_lines(resolution.geometry, frame_id) == ()

    failures = tuple(row for row in resolution.results if row.status != "EMITTED")
    assert {row.locator_part_id for row in failures} == {
        "box_body:left_side", "box_body:right_side", "head"
    }
    assert all(row.diagnostic_code == "LOCATOR_MISSING" for row in failures)
    assert all(row.export_disposition == DISPOSITION for row in resolution.results)


def test_missing_attached_frames_fail_closed_without_stale_marking():
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
    assert all(row.status == "SKIPPED_FAIL_CLOSED" for row in resolution.results)
    assert all(row.diagnostic_code == "ATTACHED_MISSING" for row in resolution.results)
    assert _mark_lines(resolution.geometry, DIVIDER_ID) == ()


def _owned_signature(geometry):
    data = geometry.part(DIVIDER_ID).render_data
    rows = tuple(data.metadata.get("joint_markings") or ())
    return tuple(sorted(
        (
            row["mark_id"],
            tuple(round(float(v), 6) for v in row["p1"]),
            tuple(round(float(v), 6) for v in row["p2"]),
        )
        for row in rows
    ))


def test_save_reload_recomputes_equivalent_receiver_identities_and_geometry():
    marking = _api()
    snapshot = _snapshot()
    first = marking.resolve_receiving_joint_markings(
        snapshot, _build_geometry(snapshot),
        dimensions=(800.0, 1600.0, 350.0), sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    reloaded_snapshot = json.loads(json.dumps(snapshot, ensure_ascii=False))
    reloaded = marking.resolve_receiving_joint_markings(
        reloaded_snapshot, _build_geometry(reloaded_snapshot),
        dimensions=(800.0, 1600.0, 350.0), sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    assert _owned_signature(reloaded.geometry) == _owned_signature(first.geometry)

    changed = _snapshot()
    changed["door_gap_w"] = 10.0
    moved = marking.resolve_receiving_joint_markings(
        changed, _build_geometry(changed),
        dimensions=(800.0, 1600.0, 350.0), sheet_thickness=2.0,
        cabinet_family="受電箱",
    )
    ids_first = tuple(row[0] for row in _owned_signature(first.geometry))
    ids_moved = tuple(row[0] for row in _owned_signature(moved.geometry))
    assert ids_moved == ids_first
    assert _owned_signature(moved.geometry) != _owned_signature(first.geometry)
