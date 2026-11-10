"""#2517: 2D GUI source captions and custom-model label use public Engine."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import ae, manufacturing_api as api
from gui_modules.application import render_snapshots as gui


def _render():
    return SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 200.0, 300.0)),
        box_body_face_contexts={"left": object(), "back": object(), "right": object()},
    )


def _part_host(model="金庫型"):
    return SimpleNamespace(
        _baseline_source_model=lambda: model,
        _manufacturing_context=lambda **kwargs: "context",
        _authoritative_render_data=lambda spec, context: _render(),
        _indicator_box_part_spec=lambda values, groups, features: "indicator-box-spec",
        _end_cap_part_spec=lambda values, **kwargs: SimpleNamespace(
            is_tail=api.normalize_operator_settings_boolean(kwargs["is_tail"]),
        ),
        indicator_l_var=SimpleNamespace(get=lambda: "1"),
        indicator_layer_g_vars=[SimpleNamespace(get=lambda: "2")],
        surface_features={"indicator_box": []},
        baseline_var=SimpleNamespace(get=lambda: model),
    )


def test_original_engine_source_caption_owners_are_exact_public_callable_aliases():
    for public, owner in (
        ("operator_indicator_shared_baseline_source_label", ae.indicator_shared_baseline_source_label),
        ("operator_baseline_source_label", ae.baseline_source_label),
        ("operator_box_body_baseline_source_label", ae.box_body_baseline_source_label),
    ):
        assert getattr(api, public) is owner
        assert getattr(ae_engine, public) is owner
        assert public in ae_engine.__all__
    assert ae_engine.is_unknown_operator_model is api.is_unknown_operator_model
    assert "is_unknown_operator_model" in ae_engine.__all__


@pytest.mark.parametrize("baseline", ("", "not-a-real-baseline-folder", "自訂"))
def test_operator_source_captions_keep_original_missing_baseline_semantics(baseline):
    assert api.operator_baseline_source_label(baseline, "門.dxf") == (
        ae.baseline_source_label(baseline, "門.dxf")
    )
    assert api.operator_box_body_baseline_source_label(baseline) == (
        ae.box_body_baseline_source_label(baseline)
    )
    assert api.operator_indicator_shared_baseline_source_label("盒子.dxf") == (
        ae.indicator_shared_baseline_source_label("盒子.dxf")
    )
    if baseline == "":
        assert "未使用基準檔" in api.operator_baseline_source_label(baseline, "門.dxf")
        assert "未使用基準檔" in api.operator_box_body_baseline_source_label(baseline)


def test_actual_indicator_box_2d_snapshot_uses_public_shared_source_label(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api, "operator_indicator_shared_baseline_source_label",
        lambda filename: (calls.append(filename), "ENGINE SHARED SOURCE")[1],
    )
    result = gui.indicator_box_render_snapshot(_part_host(), {"w": 300.0})
    assert result["baseline_label"] == "ENGINE SHARED SOURCE"
    assert calls == ["盒子.dxf"]


def test_actual_door_grid_2d_snapshot_uses_public_baseline_source_label(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api, "operator_baseline_source_label",
        lambda model, filename: (calls.append((model, filename)), "ENGINE DOOR SOURCE")[1],
    )
    host = SimpleNamespace(
        w_var=SimpleNamespace(get=lambda: "800"),
        h_var=SimpleNamespace(get=lambda: "1200"),
        get_door_layout_columns=lambda: (),
        get_door_layout_cells=lambda: (),
        get_float_values=lambda: {},
        _baseline_source_model=lambda: "金庫型",
        door_layout_selected_var=SimpleNamespace(get=lambda: ""),
    )
    result = gui.door_layout_overview_snapshot(host, render_data_by_part_key={})
    assert result["baseline_status"] == "ENGINE DOOR SOURCE"
    assert calls == [("金庫型", "門.dxf")]
    assert result["error"] is None


def test_real_box_body_face_2d_snapshot_uses_public_label(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api, "operator_box_body_baseline_source_label",
        lambda model: (calls.append(model), "ENGINE BOX SOURCE")[1],
    )
    monkeypatch.setattr(api, "project_box_body_2d_piece_inventory", lambda *args: ((), None))
    host = SimpleNamespace(
        fold_designer_app=None,
        _box_body_part_spec=lambda value: "spec",
        _manufacturing_context=lambda **kwargs: "context",
        _authoritative_render_data=lambda spec, context: _render(),
        _refresh_box_body_piece_tabs_2d=lambda data: None,
        _baseline_source_model=lambda: "金庫型",
        box_body_face_selected_var=SimpleNamespace(get=lambda: "back"),
    )
    snapshot = gui.box_body_render_snapshot(
        host, {"w": 800.0, "h": 1200.0, "d": 350.0},
        face_dimensions_fn=lambda **kwargs: {"back": (800.0, 1200.0)},
    )
    assert snapshot["baseline_status"] == "ENGINE BOX SOURCE"
    assert calls == ["金庫型"]


def test_real_endcap_finalscene_snapshot_model_label_uses_public_engine(monkeypatch):
    source = []
    original = api.is_unknown_operator_model

    def observed(value):
        source.append(value)
        return original(value)

    monkeypatch.setattr(api, "is_unknown_operator_model", observed)
    host = _part_host("自訂")
    result = gui.end_cap_render_snapshot(host, {"w": 400.0}, is_tail=True)
    assert source == ["自訂"]
    assert "自訂 / Final Part Geometry" in result["baseline_hint"]
    assert result["is_tail"] is True


def test_gui_render_snapshot_contains_no_private_ae_or_corner_type_imports():
    source = Path(gui.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Import)
        and any(alias.name == "ae_engine.ae" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "ae_engine.corner_type_ui"
        for node in ast.walk(tree)
    )
    for api_name in (
        "operator_indicator_shared_baseline_source_label",
        "operator_baseline_source_label",
        "operator_box_body_baseline_source_label",
        "is_unknown_operator_model",
    ):
        assert "manufacturing_api." + api_name + "(" in source
