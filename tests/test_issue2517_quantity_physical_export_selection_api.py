"""#2517: Quantity physical selection is an Engine request→decision, not GUI logic."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.manufacturing_quantity import (
    PhysicalPartDemand, ResolvedQuantityVersion,
)
from ae_engine.quantity_manufacturing_groups import QuantityManufacturingBatch
from ae_engine.receiving_nfb_quantity_partial import QuantityNfbPartialSelection
from gui_modules.project import export_actions


def _d(version, part, physical_id, count=1):
    return PhysicalPartDemand(version, part, physical_id, count, 1, object())


def _batch(*demands):
    versions = tuple(ResolvedQuantityVersion(
        vid, 1, object(),
    ) for vid in dict.fromkeys(d.version_id for d in demands))
    requests = tuple((v.version_id, 1, object()) for v in versions)
    return QuantityManufacturingBatch(
        versions=versions, demands=tuple(demands), requests=requests,
    )


def _report(demand, *, allowed, status):
    return {
        "version_id": demand.version_id, "part_id": demand.physical_id,
        "source_part_id": demand.source_part_id, "may_export": allowed,
        "status": status, "actual_count": demand.quantity,
        "source_dependencies": [], "reason": "SOURCE_NOT_READY" if not allowed else "",
    }


def test_legacy_quantity_uses_real_physical_ids_and_customs_without_full_nfb_probe():
    head = _d("quantity-v1", "head", "head")
    inner = _d("quantity-v1", "inner_door:0", "inner_door:0")
    custom = _d("quantity-v1", "custom:userpart", "custom:userpart")
    batch = _batch(head, inner, custom)
    def deny(*args):
        pytest.fail("non-submitted legacy quantity may not call NFB verifier")
    plan = manufacturing_api.plan_quantity_operator_export_selection(
        batch, {"quantity": {"versions": [
            {"version_id": "quantity-v1", "nfb_config_submitted": False},
        ]}}, {"head": True, "door": False}, partial_selector=deny,
    )
    assert plan.selected_demands == (head, custom)
    assert plan.full_selection is None
    assert plan.partial_selection is None
    assert plan.checked_batch is None
    assert plan.selected_reports == ()
    with pytest.raises((AttributeError, FrozenInstanceError)):
        plan.selected_demands = ()


def test_submitted_nfb_held_inner_door_never_becomes_accepted_demand():
    held = _d("quantity-v1", "inner_door:0", "inner_door:v1")
    side = _d("quantity-v1", "box_body:left_side", "box_body:left_side")
    permitted = _d("quantity-v2", "inner_door:0", "inner_door:v2")
    batch = _batch(held, side, permitted)
    reports = (
        _report(held, allowed=False, status="BLOCKED"),
        _report(side, allowed=True, status="UNAFFECTED"),
        _report(permitted, allowed=True, status="READY"),
    )
    full = QuantityNfbPartialSelection((side, permitted), reports)
    calls = []
    def select(actual_batch, snapshot):
        calls.append((actual_batch, snapshot))
        return full

    workspace = {"quantity": {"versions": [
        {"version_id": "quantity-v1", "nfb_config_submitted": True},
        {"version_id": "quantity-v2", "nfb_config_submitted": True},
    ]}}
    plan = manufacturing_api.plan_quantity_operator_export_selection(
        batch, workspace, {"door": True}, partial_selector=select,
    )
    assert len(calls) == 1 and calls[0][0] is batch
    assert plan.full_selection is full
    assert plan.selected_reports == (reports[0], reports[2])
    assert plan.selected_demands == (permitted,)
    assert plan.partial_selection.demands == (permitted,)
    assert plan.partial_selection.rows == (reports[0], reports[2])
    assert plan.partial_selection.held_piece_count == held.quantity
    assert plan.checked_batch.demands == (held, permitted)
    assert tuple(v.version_id for v in plan.checked_batch.versions) == (
        "quantity-v1", "quantity-v2",
    )
    assert tuple(req[0] for req in plan.checked_batch.requests) == (
        "quantity-v1", "quantity-v2",
    )
    # The existing CHECK gate sees the held original and cannot silently
    # treat its presence in the checked request as an approved export.
    assert held not in plan.selected_demands


def test_selecting_non_nfb_independent_only_omits_other_versions():
    held = _d("quantity-v1", "inner_door:0", "inner_door:v1")
    side = _d("quantity-v2", "box_body:left_side", "box_body:left_side")
    batch = _batch(held, side)
    reports = (
        _report(held, allowed=False, status="BLOCKED"),
        _report(side, allowed=True, status="UNAFFECTED"),
    )
    plan = manufacturing_api.plan_quantity_operator_export_selection(
        batch, {"quantity": {"versions": [
            {"nfb_config_submitted": True},
        ]}}, {"box_body": True}, partial_selector=lambda *_:
            QuantityNfbPartialSelection((side,), reports),
    )
    assert plan.selected_demands == (side,)
    assert plan.selected_reports == (reports[1],)
    assert tuple(v.version_id for v in plan.checked_batch.versions) == ("quantity-v2",)
    assert plan.checked_batch.demands == (side,)


def test_invalid_source_claims_are_rejected_not_turned_into_permitted_inventory():
    one = _d("quantity-v1", "door", "door")
    batch = _batch(one)
    with pytest.raises(TypeError, match="CANONICAL_BATCH"):
        manufacturing_api.plan_quantity_operator_export_selection(
            object(), {"quantity": {}}, {},
        )
    with pytest.raises(TypeError, match="INVALID_SOURCE_PROOF"):
        manufacturing_api.plan_quantity_operator_export_selection(
            batch,
            {"quantity": {"versions": [{"nfb_config_submitted": True}]}},
            {"door": True},
            partial_selector=lambda *_: object(),
        )


def test_gui_consumes_only_engine_quantity_physical_selection_plan():
    source = inspect.getsource(export_actions._export_selected_resolved_parts)
    assert "manufacturing_api.plan_quantity_operator_export_selection(" in source
    assert "selection.selected_demands" in source
    assert "selection.checked_batch" in source
    assert "selection.selected_reports" in source
    assert "selected_keys =" not in source
    assert "selected_reports = tuple(" not in source
    assert "selected_versions =" not in source
    assert "QuantityNfbPartialSelection(" not in source
