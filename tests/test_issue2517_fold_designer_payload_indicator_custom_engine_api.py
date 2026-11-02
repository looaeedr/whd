"""#2517 Fold Designer payload manufacturing: no GUI-synthesized indicator holes."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from gui_modules.application import fold_designer_manufacturing_projection as gui


def _indicator(mode="indicator_box", **changes):
    state = dict(mode=mode, layers=2, groups=[3, 4, 2, 2, 2, 2],
                 offset_x=1.25, offset_y=-2.5, is_box_dist=False)
    state.update(changes)
    return state


@pytest.mark.parametrize("mode", ("indicator_box", "indicator"))
def test_real_saved_door_cell_indicator_source_is_exact_engine_source(mode):
    raw = _indicator(mode)
    before = deepcopy(raw)
    state = api.project_operator_door_cell_indicator_manufacturing_source(raw)
    assert state == raw
    assert raw == before
    assert state["groups"][:state["layers"]] == [3, 4]


@pytest.mark.parametrize("bad", (
    {"layers": True}, {"layers": 1.5}, {"layers": 0},
    {"layers": 7}, {"layers": "invalid"}, {"layers": 3, "groups": [2]},
    {"groups": [True, 2]}, {"groups": [1.3, 2]},
    {"groups": [0, 2]}, {"groups": [9, 2]},
    {"offset_x": float("nan")}, {"offset_y": float("inf")},
    {"offset_x": "bad"}, {"is_box_dist": "bad"},
))
def test_bad_active_multi_door_source_fails_before_part_spec(bad):
    source = _indicator(**bad)
    with pytest.raises(ValueError):
        api.project_operator_door_cell_indicator_manufacturing_source(source)
    calls = []
    host = SimpleNamespace(_door_part_spec_from_values=lambda *a, **kw: calls.append("spec"))
    cell = SimpleNamespace(column_index=0, row_index=0, edges=None)
    with pytest.raises(ValueError):
        gui._door_part_spec_from_payload_context(
            host, {"door_layout_indicator_states": {"0:0": source}},
            300.0, 250.0, 2.0, 25.0, "金庫型", False, (), None, cell,
        )
    assert calls == []


def test_disabled_corrupt_control_and_legacy_mode_are_not_fabricated():
    assert api.project_operator_door_cell_indicator_manufacturing_source(None)["mode"] == "none"
    assert api.project_operator_door_cell_indicator_manufacturing_source(
        _indicator(mode="none", layers="bad", groups=None)
    )["mode"] == "none"
    old = {k: v for k, v in _indicator().items() if k != "mode"}
    old["box_enabled"] = True
    assert api.project_operator_door_cell_indicator_manufacturing_source(old)["mode"] == "indicator_box"
    old["groups"] = [True, 4]
    with pytest.raises(ValueError):
        api.project_operator_door_cell_indicator_manufacturing_source(old)
    with pytest.raises(ValueError):
        api.project_operator_door_cell_indicator_manufacturing_source(False)
    with pytest.raises(ValueError, match="模式來源無效"):
        api.project_operator_door_cell_indicator_manufacturing_source(
            _indicator(mode="unknown"),
        )


def _payload(model, cat, key, t=2.0):
    return dict(model=model, t=t, w=800, h=1600, d=350, fw=25,
                custom_parts=cat.snapshot(), fold_profiles=api.build_custom_part_profiles(
                    {"custom_parts": cat.snapshot(), "t": t}, key,
                ))


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("axis", ("X", "Y"))
def test_gui_custom_payload_matches_headless_part_spec_and_real_dxf(tmp_path, model, axis):
    cat = api.CustomPartCatalog()
    key = cat.add(display_name="加強板", fold_axis=axis,
                  transverse_length=123.456, per_box_count=2)
    source = _payload(model, cat, key)
    before = deepcopy(source)
    expected = api.custom_part_spec(source, key, profiles=source["fold_profiles"])
    actual, context = gui._fold_designer_part_spec_from_payload(SimpleNamespace(), key, source)
    assert actual == expected and isinstance(context, ManufacturingContext)
    assert source == before
    render = api.build_part_render_data(actual)
    path = tmp_path / (model + "-" + axis + ".dxf")
    api.generate_part(actual, path)
    reopened = ezdxf.readfile(path)
    assert len(reopened.modelspace().query('LINE[layer=="BEND"]')) == 1
    assert api.verify_saved_part_render_data_dxf(render, path).ok


def test_invalid_custom_payload_never_uses_bridge_material_fallback():
    cat = api.CustomPartCatalog()
    key = cat.add(display_name="板", fold_axis="X", transverse_length=100)
    valid = _payload("金庫型", cat, key)
    invalid = deepcopy(valid)
    invalid["fold_profiles"]["Y"][0]["len"] = 0
    with pytest.raises(ValueError, match="metadata"):
        gui._fold_designer_part_spec_from_payload(SimpleNamespace(), key, invalid)
    assert valid["fold_profiles"]["Y"][0]["len"] == 100


def test_gui_manufacturing_payload_uses_public_api_not_compat_or_truncation():
    src = inspect.getsource(gui._fold_designer_part_spec_from_payload)
    assert "manufacturing_api.custom_part_spec(" in src
    assert "from phase6_custom_fold_profiles import" not in src
    door = inspect.getsource(gui._door_part_spec_from_payload_context)
    assert "project_operator_door_cell_indicator_manufacturing_source(" in door
    assert "layers = max(1, min(6, int(" not in door
    assert "tuple(int(v)" not in door


def test_real_multi_door_indicator_uses_same_part_spec_and_independent_dxf(tmp_path):
    """An enabled cell must export real Engine hole geometry, not only pass mocks."""
    host = SimpleNamespace(_door_part_spec_from_values=(
        lambda values, **kw: api.build_door_operator_part_spec(
            values, **kw,
        )
    ))
    cell = SimpleNamespace(column_index=0, row_index=0, edges=None)
    source = _indicator("indicator", groups=[1, 1, 2, 2, 2, 2],
                        offset_x=0.0, offset_y=0.0)
    spec = gui._door_part_spec_from_payload_context(
        host, {"door_layout_indicator_states": {"0:0": source}},
        500.0, 600.0, 2.0, 25.0, "金庫型", False, (), None, cell,
    )
    assert spec.door_indicator == (1, 1)
    render = api.build_part_render_data(spec)
    assert render.material.area > 0
    path = tmp_path / "door_c1_r1.dxf"
    api.generate_part(spec, path)
    assert len(ezdxf.readfile(path).modelspace()) > 0
    assert api.verify_saved_part_render_data_dxf(render, path).ok
