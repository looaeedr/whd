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
    frame_id = "receiving:inner:test:frame:left"
    monkeypatch.setattr(
        owner, "_derived_receiving_frames",
        lambda _snapshot: (SimpleNamespace(stable_id=frame_id),),
    )
    result = _resolve({
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800., [float("nan")]]],
        "d": 300., "t": 2.,
        "inner_doors": [{"stable_id": "receiving:inner:test", "included_frame_sides": ("left",)}],
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
