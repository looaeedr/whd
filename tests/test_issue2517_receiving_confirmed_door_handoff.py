"""Confirmed Receiving Door handoff: canonical physical owners, no export bypass."""
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api, plan_receiving_factory_confirmed_door_handoff
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from tests.test_issue2517_receiving_confirmed_door_source import SOURCE, UPPER_LOWER, _saved

ROOT = Path(__file__).resolve().parents[1]


def _plan(columns=UPPER_LOWER, **overrides):
    inputs = {
        "confirmation": "fresh_family_confirmed",
        "confirmed_door_layout_columns": columns,
    }
    return plan_receiving_factory_confirmed_door_handoff(SOURCE, **(inputs | overrides))


def test_confirmed_handoff_preserves_exact_physical_specs_and_dxf(tmp_path):
    assert plan_receiving_factory_confirmed_door_handoff is api.plan_receiving_factory_confirmed_door_handoff
    plan = _plan()
    reference = api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=UPPER_LOWER,
    )
    assert [key for key, _ in plan.ordered_parts] == [
        "box_body", "door_c1_r1", "door_c1_r2", "head", "tail",
    ]
    assert dict(plan.ordered_parts) == dict(reference)
    assert plan.door_parts == reference[3:]
    assert plan.requires_inner_door_frame_resolution is True
    frames = api.build_receiving_factory_confirmed_inner_door_frames(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=UPPER_LOWER,
    )
    assert {frame.side: frame.span for frame in frames} == {
        "top": 696.0, "left": 1098.0, "right": 1098.0,
    }

    request = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "test-source", "set-1", "bay-1"),
        confirmed_parts=plan.ordered_parts,
        door_layout_columns=UPPER_LOWER,
    )
    result = export_verified_resolved_integration_bays(
        (request,), tmp_path, context=ManufacturingContext(resource_root=ROOT),
        pre_commit_guard=lambda: None,
    )
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert not result.external_cli_enabled
    assert len(result.output_files) == 7
    for path in result.output_files.values():
        doc = ezdxf.readfile(path)
        assert not doc.audit().errors
        assert any(entity.dxf.layer == "CUTTING" for entity in doc.modelspace())


def test_two_door_cells_do_not_certify_unsupported_frames():
    side_by_side = ((400.0, (1600.0,)), (400.0, (1600.0,)))
    plan = _plan(side_by_side)
    assert tuple(key for key, _ in plan.door_parts) == ("door_c1_r1", "door_c2_r1")
    assert plan.requires_inner_door_frame_resolution is True
    with pytest.raises(ValueError, match="RECEIVING_INNER_DOOR_FRAME_TOPOLOGY_UNRESOLVED"):
        api.build_receiving_factory_confirmed_inner_door_frames(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=side_by_side,
        )


def test_singleton_and_saved_handoff_do_not_invent_fresh_frames():
    assert _plan(((800.0, (1600.0,)),)).requires_inner_door_frame_resolution is False
    plan = _plan(confirmation="saved_operator_confirmed", operator_snapshot=_saved())
    assert len(plan.door_parts) == 2
    assert plan.requires_inner_door_frame_resolution is False


@pytest.mark.parametrize(("columns", "confirmation", "error"), [
    ((), "fresh_family_confirmed", "RECEIVING_DOOR_LAYOUT_REQUIRED"),
    (((799.0, (1100.0, 500.0)),), "fresh_family_confirmed",
     "RECEIVING_CONFIRMED_DOOR_SOURCE_INVALID"),
    (UPPER_LOWER, None, "RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"),
])
def test_invalid_source_is_not_replaced_by_legacy_or_preview(columns, confirmation, error):
    with pytest.raises(ValueError, match=error):
        _plan(columns, confirmation=confirmation)
