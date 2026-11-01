# -*- coding: utf-8 -*-
"""#2517 cache-source selection is Engine owned; exact legacy undo safety."""
from types import SimpleNamespace

from ae_engine import manufacturing_api as api
from phase6_manufacturing_adapter import _cache_service_for_app
from phase6_manufacturing_cache import ManufacturingCacheKey
from tests.test_issue359_manufacturing_cache_service import _app, _result


def test_engine_plan_only_receiving_set_bay_can_retain_previous_result():
    for snapshot in (
        None, {"model": "金庫型", "active_mode": "set_bay"},
        {"model": "受電箱", "active_mode": "quantity"},
        {"model": "受電箱"},
    ):
        plan = api.plan_manufacturing_cache_source(snapshot, {"active_type": "integral"})
        assert plan == api.ManufacturingCacheSourcePlan(1, False, False)
    receiving = {"model": "受電箱", "active_mode": "set_bay"}
    assert api.plan_manufacturing_cache_source(receiving, {"active_type": "integral"}) == (
        api.ManufacturingCacheSourcePlan(2, True, False)
    )
    assert api.plan_manufacturing_cache_source(
        receiving, {"active_type": "three_piece_side_back_split"},
    ) == api.ManufacturingCacheSourcePlan(2, True, True)


def test_unknown_or_missing_source_structure_forbids_old_receipt_reuse():
    snapshot = {"model": "RECEIVING", "active_mode": "set_bay"}
    for structure in (None, {}, {"active_type": "unverified-new-topology"}):
        result = api.plan_manufacturing_cache_source(snapshot, structure)
        assert result.history_capacity == 2
        assert not result.witness_required
    snapshot["box_body_structure"] = {"active_type": "three_piece_side_back_split"}
    assert api.plan_manufacturing_cache_source(snapshot, {}).include_physical_panels
    assert snapshot["box_body_structure"]["active_type"] == "three_piece_side_back_split"


def test_gui_invokes_engine_plan_and_retires_changed_physical_dxf(monkeypatch):
    app = _app()
    app._phase6_input_snapshot.update({
        "model": "受電箱", "active_mode": "set_bay",
        "box_body_structure": {"active_type": "three_piece_side_back_split"},
    })
    witness = [("raw", "A")]
    calls = []
    monkeypatch.setattr(
        api, "receiving_baseline_source_stamp",
        lambda model, *, context, include_physical_panels:
            calls.append((model, include_physical_panels)) or tuple(witness),
    )
    first = _cache_service_for_app(app)
    assert first.max_entries == 2
    assert calls[-1] == ("受電箱", True)
    key = ManufacturingCacheKey("1" * 64)
    first.store(key, _result(("real-material",)))
    assert _cache_service_for_app(app).lookup(key).result is not None
    witness[:] = [("raw", "B")]
    after = _cache_service_for_app(app)
    assert after is first
    assert after.lookup(key).result is None
    assert after._receiving_baseline_stamp == tuple(witness)


def test_unknown_structure_never_stamps_or_reuses_production(monkeypatch):
    app = _app()
    app._phase6_input_snapshot.update({
        "model": "受電箱", "active_mode": "set_bay",
        "box_body_structure": {"active_type": "unverified"},
    })
    monkeypatch.setattr(
        api, "receiving_baseline_source_stamp",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("not source certified")),
    )
    service = _cache_service_for_app(app)
    service.store(ManufacturingCacheKey("2" * 64), _result("old"))
    assert service.max_entries == 2
    assert _cache_service_for_app(app).result is None
    assert service._receiving_baseline_stamp is None


def test_gui_no_longer_classifies_boxbody_structure_or_history_capability():
    from pathlib import Path
    content = Path("phase6_manufacturing_adapter.py").read_text(encoding="utf-8")
    assert "from phase6_box_body_structure import BoxBodyStructureType" not in content
    assert "recognized = {kind.value for kind in BoxBodyStructureType}" not in content
    assert "manufacturing_api.plan_manufacturing_cache_source(" in content
