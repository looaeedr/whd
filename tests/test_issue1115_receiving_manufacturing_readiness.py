from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine.receiving_layout import (
    append_receiving_set,
    new_receiving_layout,
    resize_receiving_bays,
)
from ae_engine.receiving_manufacturing_readiness import (
    BAY_INTRINSIC,
    BLOCKED,
    JOINT_INTRINSIC,
    NOT_EXPORTABLE,
    READY,
    ReceivingExportBlocked,
    ReceivingManufacturingFailure,
    assert_receiving_export_scope_ready,
    evaluate_receiving_manufacturing_readiness,
)
from ae_engine import manufacturing_export
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter


ROLES = frozenset({"left", "middle", "right", "left_side", "back", "right_side", "integral"})


def _layout():
    layout = new_receiving_layout(width=800, height=1600, depth=350, back_panel_mode="FULL")
    layout = resize_receiving_bays(layout, set_index=0, bay_count=3)
    return append_receiving_set(layout)


def _failure(classification, entity_id, code="E", reason="blocked", pieces=(), features=()):
    return ReceivingManufacturingFailure(
        classification=classification,
        entity_id=entity_id,
        code=code,
        reason=reason,
        physical_piece_ids=pieces,
        feature_ids=features,
    )


def test_t012_joint_intrinsic_blocks_joint_exact_two_participant_bays_and_set_only():
    layout = _layout()
    joint = layout["sets"][0]["joints"][0]
    failure = _failure(
        JOINT_INTRINSIC,
        joint["stable_id"],
        code="JOINT_COLLISION",
        pieces=("box_body:left_side", "box_body:right_side"),
        features=("lock:1",),
    )
    report = evaluate_receiving_manufacturing_readiness(layout, [failure])

    set1 = layout["sets"][0]
    set2 = layout["sets"][1]
    assert report.joints[joint["stable_id"]].state == BLOCKED
    assert report.joints[set1["joints"][1]["stable_id"]].state == READY
    assert report.bays[set1["bays"][0]["stable_id"]].state == BLOCKED
    assert report.bays[set1["bays"][1]["stable_id"]].state == BLOCKED
    assert report.bays[set1["bays"][2]["stable_id"]].state == READY
    assert report.sets[set1["stable_id"]].state == BLOCKED
    assert report.sets[set2["stable_id"]].state == READY


def test_t012_bay_intrinsic_does_not_invalidate_neighbor_joint_or_bay():
    layout = _layout()
    set1 = layout["sets"][0]
    bay2 = set1["bays"][1]
    report = evaluate_receiving_manufacturing_readiness(
        layout,
        [_failure(BAY_INTRINSIC, bay2["stable_id"], code="BAY_BOUNDS")],
    )
    assert report.bays[set1["bays"][0]["stable_id"]].state == READY
    assert report.bays[bay2["stable_id"]].state == BLOCKED
    assert report.bays[set1["bays"][2]["stable_id"]].state == READY
    assert all(report.joints[row["stable_id"]].state == READY for row in set1["joints"])
    assert report.sets[set1["stable_id"]].state == BLOCKED


def test_t012_not_exportable_is_derived_only_and_never_repropagates():
    layout = _layout()
    bay2 = layout["sets"][0]["bays"][1]
    report = evaluate_receiving_manufacturing_readiness(
        layout,
        [_failure(NOT_EXPORTABLE, bay2["stable_id"], code="DERIVED_NOT_EXPORTABLE")],
    )
    assert all(node.state == READY for node in report.bays.values())
    assert all(node.state == READY for node in report.joints.values())
    assert all(node.state == READY for node in report.sets.values())


def test_t012_set_project_and_explicit_bay_scope_fail_closed_from_same_authority():
    layout = _layout()
    set1 = layout["sets"][0]
    bay2 = set1["bays"][1]
    report = evaluate_receiving_manufacturing_readiness(
        layout,
        [_failure(BAY_INTRINSIC, bay2["stable_id"], code="BAY_INVALID")],
    )
    assert_receiving_export_scope_ready(report, scope_kind="BAY", stable_id=set1["bays"][0]["stable_id"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_export_scope_ready(report, scope_kind="BAY", stable_id=bay2["stable_id"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_export_scope_ready(report, scope_kind="SET", stable_id=set1["stable_id"])
    with pytest.raises(ReceivingExportBlocked):
        assert_receiving_export_scope_ready(report, scope_kind="PROJECT")


def test_t012a_adapter_projects_ready_blocked_rows_with_expandable_diagnostics_only():
    layout = _layout()
    joint = layout["sets"][0]["joints"][0]
    adapter = ReceivingSetBayAdapter(layout)
    rows = adapter.project_manufacturing_readiness([
        _failure(
            JOINT_INTRINSIC,
            joint["stable_id"],
            code="JOINT_BOUNDS",
            reason="hole outside participant side panel",
            pieces=("box_body:left_side",),
            features=("joint-hole:0",),
        )
    ])
    indexed = {(row["entity_kind"], row["stable_id"]): row for row in rows}
    row = indexed[("JOINT", joint["stable_id"])]
    assert row["state"] == BLOCKED
    assert row["diagnostics"][0]["physical_piece_ids"] == ("box_body:left_side",)
    assert row["diagnostics"][0]["feature_ids"] == ("joint-hole:0",)
    assert adapter.layout == layout


def test_t016_set_bay_namespace_makes_repeated_physical_piece_names_unambiguous():
    n1 = manufacturing_export.receiving_instance_namespace(
        set_id="receiving:set:1", bay_id="receiving:set:1:bay:1"
    )
    n2 = manufacturing_export.receiving_instance_namespace(
        set_id="receiving:set:1", bay_id="receiving:set:1:bay:2"
    )
    f1 = manufacturing_export.resolved_physical_dxf_filename(
        "box_body:left_side", box_body_physical_piece_roles=ROLES, instance_namespace=n1
    )
    f2 = manufacturing_export.resolved_physical_dxf_filename(
        "box_body:left_side", box_body_physical_piece_roles=ROLES, instance_namespace=n2
    )
    assert f1 != f2
    assert f1.endswith("__box_body__left_side.dxf")
    assert f2.endswith("__box_body__left_side.dxf")
    assert "receiving_set_1_bay_1" in f1
    assert "receiving_set_1_bay_2" in f2


def _geometry(*part_ids):
    return SimpleNamespace(parts=tuple(
        SimpleNamespace(part_key=part_id, render_data=SimpleNamespace(pieces=()))
        for part_id in part_ids
    ))


def test_t012_atomic_resolved_export_leaves_no_final_files_when_any_serializer_fails(tmp_path):
    calls = []

    def save(render_data, output_path, overwrite=False):
        path = Path(output_path)
        calls.append(path.name)
        if len(calls) == 2:
            raise RuntimeError("serializer failed")
        path.write_text("ok", encoding="utf-8")
        return str(path)

    with pytest.raises(RuntimeError, match="serializer failed"):
        manufacturing_export.save_resolved_manufacturing_geometry_dxf(
            _geometry("head", "tail"),
            tmp_path,
            save_part_render_data_dxf=save,
            box_body_physical_piece_roles=ROLES,
            overwrite=True,
        )
    assert list(tmp_path.glob("*.dxf")) == []


def test_t016_atomic_multi_instance_export_keeps_all_instance_files(tmp_path):
    def save(render_data, output_path, overwrite=False):
        path = Path(output_path)
        path.write_text("ok", encoding="utf-8")
        return str(path)

    ns1 = manufacturing_export.receiving_instance_namespace(
        set_id="receiving:set:1", bay_id="receiving:set:1:bay:1"
    )
    ns2 = manufacturing_export.receiving_instance_namespace(
        set_id="receiving:set:1", bay_id="receiving:set:1:bay:2"
    )
    outputs = manufacturing_export.save_resolved_manufacturing_geometry_batch_dxf(
        [(ns1, _geometry("box_body:left_side")), (ns2, _geometry("box_body:left_side"))],
        tmp_path,
        save_part_render_data_dxf=save,
        box_body_physical_piece_roles=ROLES,
        overwrite=False,
    )
    assert len(outputs) == 2
    names = sorted(path.name for path in tmp_path.glob("*.dxf"))
    assert len(names) == 2
    assert names[0] != names[1]


def test_export_actions_no_longer_has_partial_success_path():
    source = Path(__file__).parents[1] / "gui_modules" / "project" / "export_actions.py"
    text = source.read_text(encoding="utf-8")
    assert "部分成功" not in text
    assert ".whd-export-stage-" in text
    assert "_commit_staged_project_export(stage_folder, folder)" in text
    assert 'if errors:' in text
