"""#2517 raw BoxBody/EndCap manufacturing material reuse is Engine authority."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_cache_source_plan as source_plan
from ae_engine.contracts import BoxBodyPartSpec, EndCapPartSpec, ManufacturingContext
from gui_modules.application import fold_designer_manufacturing_projection as gui
from gui_modules.application.state_sync import Phase6DerivedCacheOwner


SNAPSHOT = {"model": "受電箱", "active_mode": "set_bay"}


def _box(structure=None):
    return BoxBodyPartSpec(
        width=800, height=1600, depth=350, thickness=2, frame_width=25,
        model_name="受電箱", structure_state=structure or {},
    )


def _endcap(structure=None):
    return EndCapPartSpec(
        width=800, depth=350, thickness=2, frame_width=25,
        model_name="受電箱", box_body_structure_state=structure or {},
    )


def test_engine_only_real_receiving_raw_part_types_request_witness(monkeypatch):
    called = []
    stamp = (("箱身.dxf", (1,)), ("封頭尾.dxf", (2,)), ("門.dxf", (3,)))
    def witness(model, *, context, include_physical_panels):
        called.append((model, context, include_physical_panels))
        return stamp
    monkeypatch.setattr(source_plan, "receiving_baseline_source_stamp", witness)
    ctx = ManufacturingContext(draw_stock=False)
    for part in (_box(), _endcap()):
        plan = api.plan_operator_raw_material_reuse(part, SNAPSHOT, context=ctx)
        assert plan == api.OperatorRawMaterialReusePlan(True, stamp)
    assert called == [("受電箱", ctx, False)] * 2
    for invalid in (
        {"model": "金庫型", "active_mode": "set_bay"},
        {"model": "受電箱", "active_mode": "quantity"},
        {"model": "RECEIVING", "active_mode": "set_bay"},
        None,
    ):
        assert api.plan_operator_raw_material_reuse(
            _box(), invalid, context=ctx,
        ) == api.OperatorRawMaterialReusePlan(False, None)
    wrong = replace(_box(), model_name="金庫型")
    assert not api.plan_operator_raw_material_reuse(wrong, SNAPSHOT).eligible
    assert len(called) == 2


def test_three_physical_sheets_and_endcap_source_are_engine_checked(monkeypatch):
    called = []
    stamp = [("箱身.dxf", ("source",)), ("封頭尾.dxf", None), ("門.dxf", ("source",))]
    def witness(model, *, context, include_physical_panels):
        called.append(include_physical_panels)
        return tuple(stamp)
    monkeypatch.setattr(source_plan, "receiving_baseline_source_stamp", witness)
    dedicated = {"active_type": "three_piece_side_back_split"}
    plan = api.plan_operator_raw_material_reuse(_box(dedicated), SNAPSHOT)
    assert plan.eligible and plan.source_stamp == tuple(stamp)
    endcap = api.plan_operator_raw_material_reuse(_endcap(dedicated), SNAPSHOT)
    assert endcap.eligible and endcap.source_stamp is None
    assert called == [True, True]
    stamp[1] = ("封頭尾.dxf", ("verified",))
    assert api.plan_operator_raw_material_reuse(_endcap(), SNAPSHOT).source_stamp == tuple(stamp)


def test_relief_solved_endcap_never_borrows_raw_cache(monkeypatch):
    monkeypatch.setattr(source_plan, "receiving_baseline_source_stamp",
                        lambda *_a, **_kw: pytest.fail("solved EndCap cannot be raw"))
    solved = replace(_endcap(), resolved_assembly_relief_cuts=(((1., 2.), (3., 4.), (5., 6.)),))
    assert not api.plan_operator_raw_material_reuse(solved, SNAPSHOT).eligible
    with_relief = replace(_endcap(), assembly_relief=object())
    assert not api.plan_operator_raw_material_reuse(with_relief, SNAPSHOT).eligible


def test_gui_only_manages_lru_reuse_and_retirement(monkeypatch):
    owner = Phase6DerivedCacheOwner()
    host = SimpleNamespace(_derived_cache_owner=owner, _phase6_input_snapshot=dict(SNAPSHOT))
    ctx = ManufacturingContext(draw_stock=False)
    part = _endcap()
    stamps = [("source", "A")]
    calls = []
    monkeypatch.setattr(
        api, "plan_operator_raw_material_reuse",
        lambda spec, snapshot, *, context:
            api.OperatorRawMaterialReusePlan(True, tuple(stamps)),
    )
    def factory(spec, context):
        material = object()
        calls.append(material)
        return material
    monkeypatch.setattr(api, "build_part_render_data", factory)
    first = gui._authoritative_render_data(host, part, ctx)
    owner.invalidate("geometry", ("w",))
    assert gui._authoritative_render_data(host, part, ctx) is first
    assert len(calls) == 1
    stamps[:] = [("source", "B")]
    owner.invalidate("geometry", ("w",))
    assert gui._authoritative_render_data(host, part, ctx) is not first
    assert len(calls) == 2

    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/fold_designer_manufacturing_projection.py"
              ).read_text(encoding="utf-8")
    section = source.split("def _authoritative_render_data(")[1].split(
        "def _require_verified_baseline_sources_for_manufacturing("
    )[0]
    assert "manufacturing_api.plan_operator_raw_material_reuse(" in section
    source_eligibility = section.split("    if isinstance(spec, BoxBodyPartSpec):")[0]
    assert "from phase6_box_body_structure" not in source_eligibility
    assert "_receiving_baseline_source_stamp(" not in section
    assert 'snapshot.get("model")' not in section
    engine = (Path(__file__).resolve().parents[1] /
              "ae_engine/manufacturing_cache_source_plan.py"
              ).read_text(encoding="utf-8")
    assert "from gui_modules" not in engine and "from phase6_" not in engine
