# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

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


@dataclass(frozen=True)
class _Verification:
    ok: bool = True


def test_t016_multi_instance_inventory_keeps_stable_set_bay_identity_and_physical_names(tmp_path):
    layout = _layout()
    ids = _ids(layout)
    graph = build_receiving_readiness_graph(layout)
    geometry_by_bay = {ids["b1"]: object(), ids["b3"]: object()}

    def save_geometry(geometry, output_dir, overwrite=False):
        assert overwrite is True
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        names = {
            "box_body:left_side": "box_body__left_side.dxf",
            "box_body:back": "box_body__back.dxf",
            "box_body:right_side": "box_body__right_side.dxf",
        }
        result = {}
        for part_id, name in names.items():
            path = root / name
            path.write_text(part_id, encoding="utf-8")
            result[part_id] = str(path)
        return result

    seen_verify = []
    def verify_geometry(geometry, output_dir):
        seen_verify.append((geometry, Path(output_dir)))
        return _Verification(True)

    inventory = save_receiving_instance_batch_dxf(
        graph=graph, layout=layout, instance_geometries=geometry_by_bay,
        output_dir=tmp_path / "receiving", save_geometry=save_geometry,
        verify_geometry=verify_geometry, bay_ids=(ids["b1"], ids["b3"]), overwrite=True,
    )

    expected_suffixes = {
        "box_body:left_side": "box_body__left_side.dxf",
        "box_body:back": "box_body__back.dxf",
        "box_body:right_side": "box_body__right_side.dxf",
    }
    assert len(inventory) == 6
    for bay_id in (ids["b1"], ids["b3"]):
        prefix = f"{ids['s1']}::{bay_id}::"
        keys = [key for key in inventory if key.startswith(prefix)]
        assert len(keys) == 3
        for part_id, filename in expected_suffixes.items():
            key = prefix + part_id
            path = Path(inventory[key])
            assert path.name == filename
            assert path.exists()
            # Set/Bay identity lives in inventory/path scope, not engraved content.
            assert ids["s1"] not in path.read_text(encoding="utf-8")
            assert bay_id not in path.read_text(encoding="utf-8")
    assert len(seen_verify) == 2
