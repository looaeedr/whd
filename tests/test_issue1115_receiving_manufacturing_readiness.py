# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

import ae_engine.manufacturing_api as manufacturing_api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.sheetmetal_drawing import DrawingScene
import phase6_project_file

from ae_engine.receiving_layout import (
    new_receiving_layout,
    resize_receiving_bays,
    resize_receiving_sets,
)
from ae_engine.receiving_manufacturing_readiness import (
    BAY_INTRINSIC,
    BLOCKED,
    JOINT_INTRINSIC,
    READY,
    ReceivingIntrinsicFailure,
    build_receiving_readiness_graph,
    evaluate_receiving_export,
    receiving_readiness_projection,
    save_receiving_instance_batch_dxf,
)


def _layout():
    layout = new_receiving_layout(
        width=800.0, height=1600.0, depth=350.0, back_panel_mode="FULL"
    )
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    layout = resize_receiving_sets(layout, set_count=2)
    layout = resize_receiving_bays(layout, set_index=1, bay_count=2)
    return layout


def _ids(layout):
    s1, s2 = layout["sets"]
    return {
        "s1": s1["stable_id"], "s2": s2["stable_id"],
        "b1": s1["bays"][0]["stable_id"], "b2": s1["bays"][1]["stable_id"],
        "b3": s1["bays"][2]["stable_id"],
        "j1": s1["joints"][0]["stable_id"], "j2": s1["joints"][1]["stable_id"],
        "s2b1": s2["bays"][0]["stable_id"], "s2b2": s2["bays"][1]["stable_id"],
        "s2j1": s2["joints"][0]["stable_id"],
    }


def test_t012_bay_intrinsic_blocks_only_that_bay_and_never_chain_propagates():
    layout = _layout()
    ids = _ids(layout)
    failure = ReceivingIntrinsicFailure(
        scope=BAY_INTRINSIC, set_id=ids["s1"], bay_id=ids["b2"],
        physical_piece="box_body:left_side",
        conflicting_feature_ids=("pairing:X", "existing:hole:7"),
        reason="pairing mark conflict",
        diagnostic_code="RECEIVING_PAIRING_MARK_CONFLICT",
    )
    graph = build_receiving_readiness_graph(layout, (failure,))

    assert graph.bays[ids["b2"]].status == BLOCKED
    assert graph.bays[ids["b1"]].status == READY
    assert graph.bays[ids["b3"]].status == READY
    assert graph.joints[ids["j1"]].status == READY
    assert graph.joints[ids["j2"]].status == READY
    assert graph.sets[ids["s1"]].status == BLOCKED
    assert graph.sets[ids["s2"]].status == READY

    # An unaffected neighbor Bay may still export because its incident Joint is READY.
    assert evaluate_receiving_export(graph, bay_ids=(ids["b3"],)).ready is True
    assert evaluate_receiving_export(graph, bay_ids=(ids["b2"],)).ready is False
    assert evaluate_receiving_export(graph, set_ids=(ids["s1"],)).ready is False
    assert evaluate_receiving_export(graph, set_ids=(ids["s2"],)).ready is True
    assert evaluate_receiving_export(graph, full_project=True).ready is False


def test_t012_joint_intrinsic_blocks_joint_and_exactly_two_participant_bay_packages():
    layout = _layout()
    ids = _ids(layout)
    failure = ReceivingIntrinsicFailure(
        scope=JOINT_INTRINSIC, set_id=ids["s1"], joint_id=ids["j1"],
        physical_piece="box_body:right_side|box_body:left_side",
        conflicting_feature_ids=("lock:0", "existing:slot:3"),
        reason="lock feature conflict",
        diagnostic_code="RECEIVING_LOCK_FEATURE_CONFLICT",
    )
    graph = build_receiving_readiness_graph(layout, (failure,))

    assert graph.joints[ids["j1"]].status == BLOCKED
    assert graph.bays[ids["b1"]].status == BLOCKED
    assert graph.bays[ids["b2"]].status == BLOCKED
    # Critical no-chain assertion: b2 NOT_EXPORTABLE must not invalidate j2/b3.
    assert graph.joints[ids["j2"]].status == READY
    assert graph.bays[ids["b3"]].status == READY
    assert graph.sets[ids["s2"]].status == READY


def test_t012a_ui_projection_is_read_only_and_contains_expandable_reason_piece_and_features():
    layout = _layout()
    ids = _ids(layout)
    failure = ReceivingIntrinsicFailure(
        scope=BAY_INTRINSIC, set_id=ids["s1"], bay_id=ids["b2"],
        physical_piece="box_body:left_side",
        conflicting_feature_ids=("mark:circle", "cut:slot"),
        reason="zero-clearance intersection",
        diagnostic_code="RECEIVING_PAIRING_MARK_CONFLICT",
    )
    graph = build_receiving_readiness_graph(layout, (failure,))
    before = (dict(graph.sets), dict(graph.bays), dict(graph.joints))
    projection = receiving_readiness_projection(graph)
    after = (dict(graph.sets), dict(graph.bays), dict(graph.joints))
    assert before == after

    rows = {(row["entity_type"], row["entity_id"]): row for row in projection}
    bay = rows[("BAY", ids["b2"])]
    assert bay["status"] == BLOCKED
    assert bay["diagnostics"] == ({
        "physical_piece": "box_body:left_side",
        "conflicting_feature_ids": ("mark:circle", "cut:slot"),
        "reason": "zero-clearance intersection",
        "diagnostic_code": "RECEIVING_PAIRING_MARK_CONFLICT",
    },)
    assert rows[("BAY", ids["b3"])]["status"] == READY
    assert rows[("JOINT", ids["j2"])]["status"] == READY
    assert rows[("SET", ids["s2"])]["status"] == READY


def test_t012_export_batch_is_fail_closed_before_any_file_write(tmp_path):
    layout = _layout()
    ids = _ids(layout)
    graph = build_receiving_readiness_graph(layout, (
        ReceivingIntrinsicFailure(
            scope=BAY_INTRINSIC, set_id=ids["s1"], bay_id=ids["b2"],
            reason="common state invalid",
            diagnostic_code="RECEIVING_BAY_COMMON_STATE_INVALID",
        ),
    ))
    calls = []
    with pytest.raises(ValueError, match="RECEIVING_EXPORT_BLOCKED"):
        save_receiving_instance_batch_dxf(
            graph=graph, layout=layout,
            instance_geometries={ids["b1"]: object(), ids["b2"]: object(), ids["b3"]: object()},
            output_dir=tmp_path / "batch",
            save_geometry=lambda *args, **kwargs: calls.append((args, kwargs)) or {},
            full_project=True, overwrite=True,
        )
    assert calls == []
    assert not (tmp_path / "batch").exists()


def test_t015_save_reload_preserves_stable_instance_identity_without_legacy_aliases(tmp_path):
    layout = _layout()
    ids = _ids(layout)
    payload = {
        "schema": phase6_project_file.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "t": 2.0,
            "fw": 29.0,
            "receiving_layout": layout,
            # Runtime aliases deliberately present before writer materialization.
            "w": 999.0, "h": 999.0, "d": 999.0,
            "back_panel_mode": "HALF",
            "_receiving_runtime_selection": {"set_index": 0, "bay_index": 2},
        },
        "final_geometry": {},
    }
    path = phase6_project_file.write_project(tmp_path / "multi-bay.p6fold", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema"] == phase6_project_file.PROJECT_SCHEMA_V2
    assert "w" not in raw["snapshot"]
    assert "h" not in raw["snapshot"]
    assert "d" not in raw["snapshot"]
    assert "back_panel_mode" not in raw["snapshot"]
    assert "_receiving_runtime_selection" not in raw["snapshot"]

    loaded = phase6_project_file.read_project(path)
    restored = loaded["snapshot"]["receiving_layout"]
    restored_ids = _ids(restored)
    assert restored_ids == ids
    assert [bay["stable_id"] for bay in restored["sets"][0]["bays"]] == [
        layout["sets"][0]["bays"][0]["stable_id"],
        layout["sets"][0]["bays"][1]["stable_id"],
        layout["sets"][0]["bays"][2]["stable_id"],
    ]
    assert [joint["stable_id"] for joint in restored["sets"][0]["joints"]] == [
        layout["sets"][0]["joints"][0]["stable_id"],
        layout["sets"][0]["joints"][1]["stable_id"],
    ]


def _physical_geometry_with_all_export_layers():
    pieces = []
    for role, x_offset in (("left_side", 0.0), ("back", 140.0), ("right_side", 280.0)):
        scene = DrawingScene()
        scene.add_polyline(
            ((0.0, 0.0), (120.0, 0.0), (120.0, 200.0), (0.0, 200.0)),
            layer="CUTTING", closed=True,
        )
        scene.add_circle(
            (30.0 + x_offset * 0.0, 40.0), 5.0,
            layer="BLIND_HOLE", source_type="t016", source_id=f"{role}:blind",
        )
        scene.add_line((20.0, 100.0), (100.0, 100.0), layer="MARKING")
        render = manufacturing_api.PartRenderData(
            scene=scene,
            material=manufacturing_api.material_polygon_from_final_scene(scene),
            fold_guides=manufacturing_api.fold_guides_from_final_scene(scene),
            metadata={"t016_role": role},
        )
        pieces.append(SimpleNamespace(key=role, role=role, render_data=render))
    structure = SimpleNamespace(pieces=tuple(pieces))
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", structure),
    ))


def test_t016_real_generic_dxf_save_reopen_per_multi_instance_physical_piece(tmp_path):
    layout = _layout()
    ids = _ids(layout)
    graph = build_receiving_readiness_graph(layout)
    geometry_a = _physical_geometry_with_all_export_layers()
    geometry_b = _physical_geometry_with_all_export_layers()

    inventory = save_receiving_instance_batch_dxf(
        graph=graph, layout=layout,
        instance_geometries={ids["b1"]: geometry_a, ids["b3"]: geometry_b},
        output_dir=tmp_path / "receiving",
        save_geometry=manufacturing_api.save_resolved_manufacturing_geometry_dxf,
        verify_geometry=manufacturing_api.verify_saved_resolved_manufacturing_geometry_dxf,
        bay_ids=(ids["b1"], ids["b3"]), overwrite=True,
    )

    assert len(inventory) == 6
    for bay_id in (ids["b1"], ids["b3"]):
        prefix = f"{ids['s1']}::{bay_id}::"
        for part_id, filename in {
            "box_body:left_side": "box_body__left_side.dxf",
            "box_body:back": "box_body__back.dxf",
            "box_body:right_side": "box_body__right_side.dxf",
        }.items():
            key = prefix + part_id
            assert key in inventory
            path = Path(inventory[key])
            assert path.name == filename
            assert path.exists()
            assert ids["s1"] not in path.read_text(encoding="utf-8")
            assert bay_id not in path.read_text(encoding="utf-8")

    # Independent reopen acceptance proves expected/actual inventory and all
    # physical piece FinalScenes without collapsing repeated part IDs.
    set_dir = next((tmp_path / "receiving").iterdir())
    bay_dirs = sorted(path for path in set_dir.iterdir() if path.is_dir())
    assert len(bay_dirs) == 2
    for geometry, bay_dir in zip((geometry_a, geometry_b), bay_dirs):
        verification = manufacturing_api.verify_saved_resolved_manufacturing_geometry_dxf(
            geometry, bay_dir
        )
        assert verification.ok is True
        assert verification.issues == ()
        assert set(verification.part_results) == {
            "box_body:left_side", "box_body:back", "box_body:right_side"
        }
