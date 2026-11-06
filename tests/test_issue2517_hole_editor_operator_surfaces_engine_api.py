"""#2517: headless Hole Editor surfaces and GUI delegations for four parts."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import ae, manufacturing_api
from ae_engine.sheetmetal_part_adapters import build_door_result, build_base_plate_result
from gui_modules.editors import hole_editor


def values():
    return dict(
        w=800.0, h=1600.0, t=2.0, fw=25.0,
        door_gap_w=3.5, door_gap_h=3.5, door_fold_l=15.0,
        door_fold_r=17.0, door_fold_t=12.0, door_fold_b=14.0,
        base_plate_shrink_top=55.0, base_plate_shrink_bottom=55.0,
        base_plate_shrink_left=60.0, base_plate_shrink_right=60.0,
        base_plate_bend=15.0,
    )


def test_engine_single_door_dimensions_and_context_match_previous_adapter():
    v = values()
    got = manufacturing_api.project_operator_hole_editor_door(
        v, material_frame_width=25.0, baseline_model="",
    )
    old = build_door_result(
        w=v["w"], h=v["h"], t=v["t"], fw=25.0,
        gap_w=v["door_gap_w"], gap_h=v["door_gap_h"],
        fold_left=v["door_fold_l"], fold_right=v["door_fold_r"],
        fold_top=v["door_fold_t"], fold_bottom=v["door_fold_b"],
    )
    assert (got.width, got.height) == pytest.approx((old.width, old.height))
    assert got.surface is not None and got.reference_guide is not None
    assert got.door_indicator_context.left_fold == v["door_fold_l"]
    assert got.door_indicator_context.bottom_fold == v["door_fold_b"]
    assert got.baseline_scene is None


def test_door_bad_baseline_still_falls_back_for_preview_only(monkeypatch):
    monkeypatch.setattr(ae, "has_baseline_part", lambda *a: True)
    def broken(*args, **kwargs): raise ValueError("invalid baseline")
    monkeypatch.setattr(ae, "get_stretched_door_data", broken)
    got = manufacturing_api.project_operator_hole_editor_door(
        values(), material_frame_width=25.0, baseline_model="金庫型",
    )
    assert got.baseline_scene is None
    assert got.baseline_status == "未使用基準檔（程式計算生成）"


def test_engine_base_plate_dimensions_match_previous_adapter():
    v = values()
    got = manufacturing_api.project_operator_hole_editor_base_plate(v)
    old = build_base_plate_result(
        w=v["w"], h=v["h"], t=v["t"],
        shrink_top=v["base_plate_shrink_top"],
        shrink_bottom=v["base_plate_shrink_bottom"],
        shrink_left=v["base_plate_shrink_left"],
        shrink_right=v["base_plate_shrink_right"],
        bend=v["base_plate_bend"],
    )
    assert (got.width, got.height) == pytest.approx((old.width, old.height))
    assert got.reference_guide is not None
    assert got.baseline_status == "未使用基準檔（程式計算生成）"


def test_box_editor_is_independent_from_small_door_source(monkeypatch):
    def blocked(*a, **k): raise AssertionError("must not load Small Door")
    monkeypatch.setattr(ae, "get_stretched_door_data", blocked)
    box = manufacturing_api.resolve_indicator_box_editor_geometry(
        (2,), thickness=2.0,
    )
    assert box.width > 0 and box.height > 0
    assert box.reference_guide is not None and box.baseline_scene is not None


def test_small_door_editor_is_independent_from_box_source(monkeypatch):
    spec, _ = manufacturing_api.indicator_small_door_operator_spec(
        (2,), thickness=2, frame_width=25, door_gap_w=3.5, door_gap_h=3.5,
    )
    def blocked(*a, **k): raise AssertionError("must not load Box")
    monkeypatch.setattr(ae, "get_stretched_indicator_box_data", blocked)
    door = manufacturing_api.resolve_indicator_door_editor_geometry(
        (2,), thickness=2.0, door_spec=spec,
    )
    assert door.width > 0 and door.height > 0
    assert door.reference_guide is not None and door.baseline_scene is not None


def test_legacy_paired_api_still_resolves_both_parts():
    spec, _ = manufacturing_api.indicator_small_door_operator_spec(
        (2,), thickness=2, frame_width=25, door_gap_w=3.5, door_gap_h=3.5,
    )
    parts = manufacturing_api.resolve_indicator_editor_components(
        (2,), thickness=2.0, door_spec=spec,
    )
    assert set(parts) == {"indicator_box", "indicator_door"}
    for part in parts.values():
        assert part.width > 0 and part.height > 0
        assert part.baseline_scene is not None


def test_gui_dispatches_four_surfaces_without_manufacturing_owner(monkeypatch):
    calls = []
    item = SimpleNamespace(
        surface="surface", width=500, height=300, reference_guide="guide",
        baseline_scene="scene", baseline_status="source",
        door_indicator_context="context", door_frame_edges="edges",
    )
    for name,label in (
        ("project_operator_hole_editor_door", "door"),
        ("project_operator_hole_editor_base_plate", "base"),
        ("resolve_indicator_box_editor_geometry", "box"),
        ("resolve_indicator_door_editor_geometry", "small"),
    ):
        monkeypatch.setattr(manufacturing_api, name, lambda *a, _label=label, **k:
                            calls.append(_label) or item)
    monkeypatch.setattr(manufacturing_api, "indicator_small_door_operator_spec",
                        lambda *a, **k: ("spec", "ctx"))
    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value
    host = SimpleNamespace(
        _door_material_frame_width=lambda fw, t: 25.0,
        baseline_var=Var("金庫型"), _baseline_source_model=lambda: "金庫型",
        _single_door_indicator_state_snapshot=lambda: {},
        _apply_single_door_indicator_state=lambda *a: None,
        _indicator_component_editor_contexts=lambda *a, **k: None,
        surface_features={"indicator_box": [], "indicator_door": []},
        indicator_l_var=Var(1), indicator_layer_g_vars=[Var("2")],
    )
    v = values()
    assert hole_editor._door_context(host, v)["door_indicator_context"] == "context"
    assert hole_editor._base_plate_context(host, v)["surface"] == "surface"
    assert hole_editor._indicator_box_context(host, v)["surface"] == "surface"
    assert hole_editor._indicator_door_context(host, v)["surface"] == "surface"
    assert calls == ["door", "base", "box", "small"]
    source = Path(hole_editor.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import ae_engine.ae as ae", "ae.get_stretched_door_data(",
        "ae.get_stretched_indicator_box_data(", "ae.calculate_door_finished_size(",
        "build_door_result(", "build_base_plate_result(",
        "build_indicator_box_result(", "build_finished_reference_guide(",
        "ManufacturingContext(", "manufacturing_api.resolve_policy(",
    ):
        assert forbidden not in source
