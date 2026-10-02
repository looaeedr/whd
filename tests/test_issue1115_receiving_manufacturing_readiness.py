# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine.manufacturing_api as manufacturing_api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, resize_receiving_sets,
)
from ae_engine.receiving_manufacturing_readiness import (
    BAY_INTRINSIC, BLOCKED, JOINT_INTRINSIC, NOT_EXPORTABLE, READY,
    ReceivingExportBlocked, ReceivingIntrinsicFailure, ReceivingManufacturingInstance,
    assert_receiving_exportable, classify_receiving_intrinsic_code,
    project_receiving_readiness, receiving_export_blockers,
    resolve_receiving_readiness, save_receiving_manufacturing_instances_dxf,
)
from ae_engine.sheetmetal_drawing import DrawingScene
import phase6_project_file


def _layout():
    layout = new_receiving_layout(width=800.0, height=1600.0, depth=350.0, back_panel_mode="FULL")
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    layout = resize_receiving_sets(layout, set_count=2)
    layout = resize_receiving_bays(layout, set_index=1, bay_count=2)
    return layout


def _ids(layout):
    s1, s2 = layout["sets"]
    return {
        "s1": s1["stable_id"], "s2": s2["stable_id"],
        "b1": s1["bays"][0]["stable_id"], "b2": s1["bays"][1]["stable_id"], "b3": s1["bays"][2]["stable_id"],
        "j1": s1["joints"][0]["stable_id"], "j2": s1["joints"][1]["stable_id"],
        "s2b1": s2["bays"][0]["stable_id"], "s2b2": s2["bays"][1]["stable_id"],
        "s2j1": s2["joints"][0]["stable_id"],
    }


def _failure(*, kind, set_id, entity_id, code, reason, piece="", features=()):
    return ReceivingIntrinsicFailure(
        kind=kind, set_id=set_id, entity_id=entity_id, code=code, reason=reason,
        physical_piece=piece, feature_ids=tuple(features),
    )


def test_t012_bay_intrinsic_blocks_only_that_bay_and_does_not_chain_propagate():
    layout = _layout(); ids = _ids(layout)
    failure = _failure(
        kind=BAY_INTRINSIC, set_id=ids["s1"], entity_id=ids["b2"],
        code="RECEIVING_PAIRING_MARK_CONFLICT", reason="zero-clearance mark conflict",
        piece="box_body:left_side", features=("pairing:X", "existing:hole:7"),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))

    assert readiness.bay(ids["b2"]).status == BLOCKED
    assert readiness.bay(ids["b1"]).status == READY
    assert readiness.bay(ids["b3"]).status == READY
    assert readiness.joint(ids["j1"]).status == READY
    assert readiness.joint(ids["j2"]).status == READY
    assert readiness.set(ids["s1"]).status == BLOCKED
    assert readiness.set(ids["s2"]).status == READY

    assert_receiving_exportable(readiness, scope="BAY", bay_id=ids["b3"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_exportable(readiness, scope="BAY", bay_id=ids["b2"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_exportable(readiness, scope="SET", set_id=ids["s1"])
    assert_receiving_exportable(readiness, scope="SET", set_id=ids["s2"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_exportable(readiness, scope="PROJECT")


def test_t012_joint_intrinsic_blocks_joint_and_exactly_two_participant_bays_only():
    layout = _layout(); ids = _ids(layout)
    failure = _failure(
        kind=JOINT_INTRINSIC, set_id=ids["s1"], entity_id=ids["j1"],
        code="RECEIVING_JOINT_FEATURE_CONFLICT", reason="lock feature conflict",
        piece="box_body:right_side|box_body:left_side", features=("lock:0", "existing:slot:3"),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))

    assert readiness.joint(ids["j1"]).status == BLOCKED
    assert readiness.bay(ids["b1"]).status == BLOCKED
    assert readiness.bay(ids["b2"]).status == BLOCKED
    assert readiness.joint(ids["j2"]).status == READY
    assert readiness.bay(ids["b3"]).status == READY
    assert readiness.set(ids["s2"]).status == READY


def test_t012_not_exportable_cannot_be_reclassified_as_intrinsic_failure():
    assert classify_receiving_intrinsic_code("RECEIVING_BAY_COMMON_STATE_INVALID") == BAY_INTRINSIC
    assert classify_receiving_intrinsic_code("RECEIVING_LOCK_PATTERN_BOUNDS_VIOLATION") == JOINT_INTRINSIC
    with pytest.raises(ValueError, match="NOT_EXPORTABLE"):
        classify_receiving_intrinsic_code(NOT_EXPORTABLE)
    with pytest.raises(ValueError, match="NOT_EXPORTABLE"):
        _failure(
            kind=BAY_INTRINSIC, set_id="s", entity_id="b", code=NOT_EXPORTABLE,
            reason="derived state must not propagate",
        )


def test_t012a_ui_projection_is_read_only_with_piece_feature_and_reason_details():
    layout = _layout(); ids = _ids(layout)
    failure = _failure(
        kind=BAY_INTRINSIC, set_id=ids["s1"], entity_id=ids["b2"],
        code="RECEIVING_PAIRING_MARK_CONFLICT", reason="zero-clearance intersection",
        piece="box_body:left_side", features=("mark:circle", "cut:slot"),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))
    before = repr(readiness)
    projection = project_receiving_readiness(layout, readiness)
    assert repr(readiness) == before

    by_set = {row["stable_id"]: row for row in projection["sets"]}
    s1 = by_set[ids["s1"]]
    bays = {row["stable_id"]: row for row in s1["bays"]}
    joints = {row["stable_id"]: row for row in s1["joints"]}
    assert bays[ids["b2"]]["status"] == BLOCKED
    assert bays[ids["b3"]]["status"] == READY
    assert joints[ids["j2"]]["status"] == READY
    diagnostic = bays[ids["b2"]]["diagnostics"][0]
    assert diagnostic["physical_piece"] == "box_body:left_side"
    assert diagnostic["feature_ids"] == ("mark:circle", "cut:slot")
    assert diagnostic["reason"] == "zero-clearance intersection"


def test_t012_project_batch_blockers_are_known_before_any_export_mutation(tmp_path):
    layout = _layout(); ids = _ids(layout)
    failure = _failure(
        kind=BAY_INTRINSIC, set_id=ids["s1"], entity_id=ids["b2"],
        code="RECEIVING_BAY_COMMON_STATE_INVALID", reason="common state invalid",
    )
    readiness = resolve_receiving_readiness(layout, (failure,))
    blockers = receiving_export_blockers(readiness, scope="PROJECT")
    assert blockers == (failure,)
    assert not (tmp_path / "receiving").exists()


def test_t015_save_reload_preserves_stable_instance_identity_without_legacy_aliases(tmp_path):
    layout = _layout(); ids = _ids(layout)
    payload = {
        "schema": phase6_project_file.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱", "t": 2.0, "fw": 29.0, "receiving_layout": layout,
            "w": 999.0, "h": 999.0, "d": 999.0, "back_panel_mode": "HALF",
            "_receiving_runtime_selection": {"set_index": 0, "bay_index": 2},
        },
        "final_geometry": {},
    }
    path = phase6_project_file.write_project(tmp_path / "multi-bay.p6fold", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == phase6_project_file.PROJECT_SCHEMA_V2
    for key in ("w", "h", "d", "back_panel_mode", "_receiving_runtime_selection"):
        assert key not in raw["snapshot"]

    loaded = phase6_project_file.read_project(path)
    restored = loaded["snapshot"]["receiving_layout"]
    assert _ids(restored) == ids
    assert [row["stable_id"] for row in restored["sets"][0]["bays"]] == [
        row["stable_id"] for row in layout["sets"][0]["bays"]
    ]
    assert [row["stable_id"] for row in restored["sets"][0]["joints"]] == [
        row["stable_id"] for row in layout["sets"][0]["joints"]
    ]


def _physical_geometry_with_all_export_layers():
    pieces = []
    for role in ("left_side", "back", "right_side"):
        scene = DrawingScene()
        scene.add_polyline(((0, 0), (120, 0), (120, 200), (0, 200)), layer="CUTTING", closed=True)
        scene.add_circle((30, 40), 5, layer="BLIND_HOLE", source_type="t016", source_id=f"{role}:blind")
        scene.add_line((20, 100), (100, 100), layer="MARKING")
        render = manufacturing_api.PartRenderData(
            scene=scene,
            material=manufacturing_api.material_polygon_from_final_scene(scene),
            fold_guides=manufacturing_api.fold_guides_from_final_scene(scene),
            metadata={"t016_role": role},
        )
        pieces.append(SimpleNamespace(key=role, role=role, render_data=render))
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", SimpleNamespace(pieces=tuple(pieces))),
    ))


def test_t016_real_generic_dxf_save_reopen_keeps_multi_instance_inventory_unambiguous(tmp_path):
    layout = _layout(); ids = _ids(layout)
    readiness = resolve_receiving_readiness(layout)
    geometry_a = _physical_geometry_with_all_export_layers()
    geometry_b = _physical_geometry_with_all_export_layers()
    instances = (
        ReceivingManufacturingInstance(ids["s1"], ids["b1"], geometry_a),
        ReceivingManufacturingInstance(ids["s1"], ids["b3"], geometry_b),
    )
    inventory = save_receiving_manufacturing_instances_dxf(
        instances, tmp_path / "receiving", readiness=readiness, overwrite=True
    )
    assert len(inventory) == 6
    by_instance = {}
    for row in inventory:
        by_instance.setdefault((row.set_id, row.bay_id), set()).add(row.part_id)
        assert row.part_id in {"box_body:left_side", "box_body:back", "box_body:right_side"}
        assert Path(tmp_path / "receiving" / row.relative_path).exists()
    assert by_instance == {
        (ids["s1"], ids["b1"]): {"box_body:left_side", "box_body:back", "box_body:right_side"},
        (ids["s1"], ids["b3"]): {"box_body:left_side", "box_body:back", "box_body:right_side"},
    }

    # Reopen each stable instance separately with the existing generic verifier.
    results = {}
    from ae_engine.receiving_manufacturing_readiness import verify_receiving_manufacturing_instances_dxf
    results = verify_receiving_manufacturing_instances_dxf(instances, tmp_path / "receiving")
    assert set(results) == {(ids["s1"], ids["b1"]), (ids["s1"], ids["b3"])}
    for result in results.values():
        assert result.ok is True
        assert result.issues == ()
        assert set(result.part_results) == {"box_body:left_side", "box_body:back", "box_body:right_side"}
