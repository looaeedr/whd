"""R5 #87: Receiving joint MARKING stays fail-closed for invalid Door/Divider source."""
from types import SimpleNamespace

import pytest

import ae_engine.receiving_joint_marking as owner
from ae_engine.contracts import ResolvedManufacturingGeometry


def _resolve(snapshot):
    return owner.resolve_receiving_joint_markings(
        snapshot,
        ResolvedManufacturingGeometry(parts=()),
        dimensions=(800., 1800., 300.),
        sheet_thickness=2.,
        world_geometry={},
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, -1.])
def test_r5_87_invalid_layout_without_physical_owner_is_noop_not_crash(monkeypatch, bad):
    monkeypatch.setattr(owner, "_derived_receiving_frames", lambda _snapshot: ())
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [bad]]],
        "d": 300., "t": 2.,
    })
    assert result.results == ()
    assert result.geometry.diagnostics == ()


def test_r5_87_invalid_layout_with_inner_frame_has_fail_closed_diagnostics(monkeypatch):
    frame_id = "inner_door:manual-r5-87:left_frame"
    monkeypatch.setattr(
        owner, "_derived_receiving_frames",
        lambda _snapshot: (SimpleNamespace(stable_id=frame_id),),
    )
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [float("nan")]]],
        "d": 300., "t": 2.,
        "inner_doors": [{"stable_id": "manual-r5-87", "included_frame_sides": ("left",)}],
    })
    assert result.results
    assert all(row.status == "SKIPPED_FAIL_CLOSED" for row in result.results)
    assert all(row.diagnostic_code == "PLACEMENT_UNRESOLVED" for row in result.results)
    assert tuple(result.geometry.diagnostics) == result.results


def test_r5_87_valid_single_column_without_inner_doors_stays_noop(monkeypatch):
    monkeypatch.setattr(owner, "_derived_receiving_frames", lambda _snapshot: ())
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [1800.]]],
        "d": 300., "t": 2.,
    })
    assert result.results == ()


def test_r5_87_bad_saved_door_id_does_not_crash_layout_error_diagnostics(monkeypatch):
    monkeypatch.setattr(
        owner, "_derived_receiving_frames",
        lambda _snapshot: (SimpleNamespace(stable_id="physical-diagnostic-owner"),),
    )
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [float("nan")]]],
        "d": 300., "t": 2.,
        "inner_doors": [{"stable_id": "illegal:source:id", "included_frame_sides": ("left",)}],
    })
    assert any(str(row.attached_part_id).startswith("invalid-inner-door:") for row in result.results)
    assert all(row.status == "SKIPPED_FAIL_CLOSED" for row in result.results)
    assert all(row.diagnostic_code == "PLACEMENT_UNRESOLVED" for row in result.results)
    assert tuple(result.geometry.diagnostics) == result.results


def test_r5_87_bad_saved_door_id_does_not_crash_frame_derivation_diagnostics(monkeypatch):
    def broken_frames(_snapshot):
        raise ValueError("inner_door_id must not contain ':'")
    monkeypatch.setattr(owner, "_derived_receiving_frames", broken_frames)
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [1800.]]],
        "d": 300., "t": 2.,
        "inner_doors": [{"stable_id": "illegal:source:id", "included_frame_sides": ("left",)}],
    })
    assert len(result.results) == 1
    assert result.results[0].status == "SKIPPED_FAIL_CLOSED"
    assert result.results[0].diagnostic_code == "STALE_STABLE_ID"
    assert result.results[0].attached_part_id.startswith("invalid-inner-door:")
    assert tuple(result.geometry.diagnostics) == result.results


def test_r5_87_atomic_rollback_keeps_original_divider_and_inner_door_policy_ids():
    from ae_engine.contracts import ResolvedJointMarkingResult
    divider = owner.RECEIVING_DIVIDER_SIDE_PLATE_POLICY
    inner = owner.RECEIVING_INNER_DOOR_MOTHER_PLATE_POLICY
    emitted = tuple(
        ResolvedJointMarkingResult(
            policy_id=policy.policy_id,
            policy_revision=policy.revision,
            locator_part_id="box_body:left_side",
            attached_part_id=f"inner-door-{index}",
            status="EMITTED", mark_ids=(f"mark-{index}",),
            evidence={"stale_contact": "must-clear"},
        ) for index, policy in enumerate((divider, inner))
    )
    skipped = ResolvedJointMarkingResult(
        policy_id=divider.policy_id, policy_revision=divider.revision,
        locator_part_id="box_body:right_side", attached_part_id="other",
        status="SKIPPED_FAIL_CLOSED", diagnostic_code="CONTACT_NOT_FOUND",
    )
    failed = owner._rollback_staged_joint_marking_results(
        emitted + (skipped,), ValueError("missing actual marking owner"),
    )
    assert [row.policy_id for row in failed] == [divider.policy_id, inner.policy_id, divider.policy_id]
    assert [row.policy_revision for row in failed] == [divider.revision, inner.revision, divider.revision]
    for row in failed[:2]:
        assert row.status == "SKIPPED_FAIL_CLOSED"
        assert row.mark_ids == ()
        assert row.evidence == {}
        assert row.diagnostic_code == "MARK_OUTSIDE_FINAL_MATERIAL"
    assert failed[2] is skipped


def test_r5_87_write_rows_rejects_missing_physical_marking_owner():
    geometry = ResolvedManufacturingGeometry(parts=())
    with pytest.raises(ValueError, match="MISSING_MARKING_OWNER"):
        owner._write_rows(
            geometry, {"box_body:left_side": ({
                "attached_part_id": "inner-door-a",
                "boundary_role": "SIDE_POSITIVE",
                "mark_id": "mark-r5-87",
            },)},
        )
