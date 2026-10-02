# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.receiving_layout import (
    append_receiving_set,
    new_receiving_layout,
    resize_receiving_bays,
    strip_legacy_receiving_aliases,
)
from ae_engine.receiving_manufacturing_readiness import (
    BAY_INTRINSIC,
    BLOCKED,
    JOINT_INTRINSIC,
    NOT_EXPORTABLE,
    READY,
    ReceivingExportBlocked,
    ReceivingIntrinsicFailure,
    ReceivingManufacturingInstance,
    classify_receiving_intrinsic_code,
    intrinsic_failure,
    project_receiving_readiness,
    receiving_export_blockers,
    receiving_instance_directory,
    resolve_receiving_readiness,
    save_receiving_manufacturing_instances_dxf,
    verify_receiving_manufacturing_instances_dxf,
)
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
import phase6_project_file as project


def _layout():
    layout = new_receiving_layout(
        width=800, height=1600, depth=350, back_panel_mode="FULL"
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    layout = append_receiving_set(layout)
    return layout


def _failure(*, code, set_id, entity_id, piece, features=("feature:a",)):
    return intrinsic_failure(
        set_id=set_id,
        entity_id=entity_id,
        code=code,
        reason=f"blocked by {code}",
        physical_piece=piece,
        feature_ids=features,
    )


def test_t012_joint_intrinsic_blocks_exactly_joint_and_two_participant_bays():
    layout = _layout()
    set1, set2 = layout["sets"]
    joint1, joint2 = set1["joints"]
    bay1, bay2, bay3 = set1["bays"]
    set2_bay1 = set2["bays"][0]

    failure = _failure(
        code="RECEIVING_LOCK_PATTERN_WIDTH_INVARIANT_VIOLATION",
        set_id=set1["stable_id"],
        entity_id=joint1["stable_id"],
        piece="box_body:left_side",
        features=("lock:0", "existing:hole:4"),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))

    assert failure.kind == JOINT_INTRINSIC
    assert readiness.joint(joint1["stable_id"]).status == BLOCKED
    assert readiness.joint(joint2["stable_id"]).status == READY
    assert readiness.bay(bay1["stable_id"]).status == BLOCKED
    assert readiness.bay(bay2["stable_id"]).status == BLOCKED
    assert readiness.bay(bay3["stable_id"]).status == READY
    assert readiness.bay(set2_bay1["stable_id"]).status == READY
    assert readiness.set(set1["stable_id"]).status == BLOCKED
    assert readiness.set(set2["stable_id"]).status == READY

    assert receiving_export_blockers(
        readiness, scope="BAY", bay_id=bay3["stable_id"]
    ) == ()
    assert receiving_export_blockers(
        readiness, scope="SET", set_id=set2["stable_id"]
    ) == ()
    assert receiving_export_blockers(
        readiness, scope="SET", set_id=set1["stable_id"]
    ) == (failure,)
    assert receiving_export_blockers(readiness, scope="PROJECT") == (failure,)


def test_t012_bay_intrinsic_does_not_invalidate_neighbor_joint_or_neighbor_bay():
    layout = _layout()
    set1 = layout["sets"][0]
    bay1, bay2, bay3 = set1["bays"]
    joint1, joint2 = set1["joints"]

    failure = _failure(
        code="RECEIVING_BAY_COMMON_STATE_INVALID",
        set_id=set1["stable_id"],
        entity_id=bay2["stable_id"],
        piece="door_c1_r1",
        features=("common-state:door-layout",),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))

    assert failure.kind == BAY_INTRINSIC
    assert readiness.bay(bay2["stable_id"]).status == BLOCKED
    assert readiness.bay(bay1["stable_id"]).status == READY
    assert readiness.bay(bay3["stable_id"]).status == READY
    assert readiness.joint(joint1["stable_id"]).status == READY
    assert readiness.joint(joint2["stable_id"]).status == READY

    # NOT_EXPORTABLE is derived state only; it cannot become a new intrinsic
    # cause and therefore cannot create chain propagation.
    with pytest.raises(ValueError, match="NOT_EXPORTABLE"):
        classify_receiving_intrinsic_code(NOT_EXPORTABLE)
    with pytest.raises(ValueError, match="NOT_EXPORTABLE"):
        ReceivingIntrinsicFailure(
            kind=BAY_INTRINSIC,
            set_id=set1["stable_id"],
            entity_id=bay3["stable_id"],
            code=NOT_EXPORTABLE,
            reason="must not re-propagate",
        )

    assert receiving_export_blockers(
        readiness, scope="BAY", bay_id=bay1["stable_id"]
    ) == ()
    assert receiving_export_blockers(
        readiness,
        scope="PROJECT",
        requested_bay_ids=(bay1["stable_id"], bay3["stable_id"]),
    ) == ()
    assert receiving_export_blockers(readiness, scope="PROJECT") == (failure,)


def test_t012a_ui_projection_exposes_ready_blocked_detail_without_mutating_authority():
    layout = _layout()
    set1 = layout["sets"][0]
    bay2 = set1["bays"][1]
    failure = _failure(
        code="RECEIVING_PAIRING_MARK_CONFLICT",
        set_id=set1["stable_id"],
        entity_id=bay2["stable_id"],
        piece="box_body:left_side",
        features=("pairing:right_lock_circle", "existing:blind:2"),
    )
    readiness = resolve_receiving_readiness(layout, (failure,))
    adapter = ReceivingSetBayAdapter(layout)
    before = adapter.layout

    projected = adapter.project_readiness(readiness)

    assert adapter.layout == before
    set_row = projected["sets"][0]
    bay_rows = {row["stable_id"]: row for row in set_row["bays"]}
    joint_rows = {row["stable_id"]: row for row in set_row["joints"]}
    assert set_row["status"] == BLOCKED
    assert bay_rows[bay2["stable_id"]]["status"] == BLOCKED
    assert all(row["status"] == READY for row in joint_rows.values())
    detail = bay_rows[bay2["stable_id"]]["diagnostics"][0]
    assert detail["physical_piece"] == "box_body:left_side"
    assert detail["feature_ids"] == (
        "pairing:right_lock_circle",
        "existing:blind:2",
    )
    assert detail["reason"] == "blocked by RECEIVING_PAIRING_MARK_CONFLICT"

    # Projection is a pure view of readiness, not an alternate authority.
    assert project_receiving_readiness(layout, readiness) == projected


def _render(*, marker_offset=0.0):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        layer="CUTTING",
        closed=True,
    ))
    scene.add(CirclePrimitive(
        center=Vec2(20 + marker_offset, 20),
        radius=3.0,
        layer="BLIND_HOLE",
        color=1,
        source_type="t016",
        source_id="blind:1",
    ))
    scene.add(LinePrimitive(
        Vec2(40 + marker_offset, 10),
        Vec2(40 + marker_offset, 50),
        "MARKING",
        211,
    ))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )


def _geometry(*, marker_offset=0.0):
    left = SimpleNamespace(
        key="left_side", role="left_side", render_data=_render(marker_offset=marker_offset)
    )
    back = SimpleNamespace(key="back", role="back", render_data=_render())
    right = SimpleNamespace(key="right_side", role="right_side", render_data=_render())
    box = SimpleNamespace(pieces=(left, back, right))
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", box),
    ))


def test_t012_project_batch_fails_closed_before_any_output_when_one_requested_bay_is_invalid(tmp_path):
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0,
        bay_count=2,
    )
    set1 = layout["sets"][0]
    bay1, bay2 = set1["bays"]
    failure = _failure(
        code="RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS",
        set_id=set1["stable_id"],
        entity_id=bay2["stable_id"],
        piece="box_body:left_side",
    )
    readiness = resolve_receiving_readiness(layout, (failure,))
    instances = (
        ReceivingManufacturingInstance(set1["stable_id"], bay1["stable_id"], _geometry()),
        ReceivingManufacturingInstance(set1["stable_id"], bay2["stable_id"], _geometry(marker_offset=1)),
    )
    root = tmp_path / "batch"

    with pytest.raises(ReceivingExportBlocked):
        save_receiving_manufacturing_instances_dxf(
            instances, root, readiness=readiness
        )
    assert not root.exists()


def test_t015_save_reload_preserves_stable_instance_inputs_without_legacy_aliases(tmp_path):
    layout = _layout()
    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "t": 2.0,
            "receiving_layout": deepcopy(layout),
        },
        "final_geometry": {},
    }
    path = project.write_project(tmp_path / "receiving-v16.p6fold", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw["schema"] == project.PROJECT_SCHEMA_V2
    assert raw["snapshot"]["receiving_layout"] == layout
    assert all(key not in raw["snapshot"] for key in ("w", "h", "d", "back_panel_mode"))

    loaded = project.read_project(path)
    assert loaded["snapshot"]["receiving_layout"] == layout
    persisted = strip_legacy_receiving_aliases(loaded["snapshot"])
    assert persisted["receiving_layout"] == layout
    assert all(key not in persisted for key in ("w", "h", "d", "back_panel_mode"))

    expected_ids = [
        row["stable_id"]
        for set_row in layout["sets"]
        for row in (
            [set_row]
            + list(set_row["bays"])
            + list(set_row["joints"])
        )
    ]
    loaded_ids = [
        row["stable_id"]
        for set_row in loaded["snapshot"]["receiving_layout"]["sets"]
        for row in (
            [set_row]
            + list(set_row["bays"])
            + list(set_row["joints"])
        )
    ]
    assert loaded_ids == expected_ids


def test_t016_multi_instance_dxf_reopens_with_unambiguous_inventory_and_layers(tmp_path):
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0,
        bay_count=2,
    )
    set1 = layout["sets"][0]
    bay1, bay2 = set1["bays"]
    readiness = resolve_receiving_readiness(layout)
    instances = (
        ReceivingManufacturingInstance(
            set1["stable_id"], bay1["stable_id"], _geometry(marker_offset=0)
        ),
        ReceivingManufacturingInstance(
            set1["stable_id"], bay2["stable_id"], _geometry(marker_offset=5)
        ),
    )
    root = tmp_path / "receiving-dxf"

    inventory = save_receiving_manufacturing_instances_dxf(
        instances, root, readiness=readiness
    )

    assert len(inventory) == 6
    assert {
        (row.set_id, row.bay_id, row.part_id)
        for row in inventory
    } == {
        (set1["stable_id"], bay1["stable_id"], "box_body:left_side"),
        (set1["stable_id"], bay1["stable_id"], "box_body:back"),
        (set1["stable_id"], bay1["stable_id"], "box_body:right_side"),
        (set1["stable_id"], bay2["stable_id"], "box_body:left_side"),
        (set1["stable_id"], bay2["stable_id"], "box_body:back"),
        (set1["stable_id"], bay2["stable_id"], "box_body:right_side"),
    }

    for bay in (bay1, bay2):
        directory = receiving_instance_directory(
            root,
            set_id=set1["stable_id"],
            bay_id=bay["stable_id"],
        )
        assert {path.name for path in directory.glob("*.dxf")} == {
            "box_body__left_side.dxf",
            "box_body__back.dxf",
            "box_body__right_side.dxf",
        }

    verified = verify_receiving_manufacturing_instances_dxf(instances, root)
    assert set(verified) == {
        (set1["stable_id"], bay1["stable_id"]),
        (set1["stable_id"], bay2["stable_id"]),
    }
    for result in verified.values():
        assert result.ok is True
        assert set(result.part_results) == {
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        }

    # Reopen evidence is per physical instance and keeps CUTTING/BLIND_HOLE/
    # MARKING in the original physical-piece DXF. Stable IDs are directory
    # identity only; they are not written into panel geometry or filenames.
    for row in inventory:
        assert "receiving:set" not in Path(row.relative_path).name
