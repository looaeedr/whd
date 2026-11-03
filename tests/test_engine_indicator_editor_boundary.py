"""Engine-owned indicator editor projections: GUI may format but never solve."""
import inspect
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import manufacturing_adapter


def test_engine_resolves_shared_indicator_box_and_small_door_editor_geometry():
    groups = (2,)
    spec = manufacturing_api.indicator_small_door_spec(groups, thickness=2.0)
    result = manufacturing_api.resolve_indicator_editor_components(
        groups, thickness=2.0, door_spec=spec,
    )
    assert set(result) == {"indicator_box", "indicator_door"}
    for item in result.values():
        assert item.width > 0 and item.height > 0
        assert item.surface is not None
        assert item.reference_guide is not None
        assert item.baseline_scene is not None


def test_gui_only_forwards_indicator_inputs_and_formats_engine_result():
    source = inspect.getsource(manufacturing_adapter._indicator_component_editor_contexts)
    assert "resolve_indicator_editor_components(" in source
    for forbidden in (
        "get_stretched_indicator_box_data(",
        "get_stretched_door_data(",
        "build_unknown_door_result(",
        "build_indicator_box_result(",
        "build_finished_reference_guide(",
    ):
        assert forbidden not in source


def test_component_editor_contexts_preserve_exact_engine_groups(monkeypatch):
    source = {
        "mode": "indicator_box", "layers": 2,
        "groups": [3, 2, 2, 2, 2, 2],
        "offset_x": 1.25, "offset_y": -2.5, "is_box_dist": False,
    }
    original = deepcopy(source)
    calls = []
    data = SimpleNamespace(
        surface="surface", width=210.0, height=180.0,
        reference_guide="guide", baseline_scene="scene",
        baseline_status="valid",
    )
    monkeypatch.setattr(
        manufacturing_api, "resolve_indicator_editor_components",
        lambda groups, *, thickness, door_spec:
            calls.append(("engine", groups, thickness, door_spec))
            or {"indicator_box": data, "indicator_door": data},
    )
    host = SimpleNamespace(
        _normalize_door_indicator_state=lambda _:
            pytest.fail("GUI may not repair a physical source"),
        _indicator_door_part_spec=lambda val, groups, *, features:
            calls.append(("door-spec", groups, features)) or "spec",
    )
    result = manufacturing_adapter._indicator_component_editor_contexts(
        host, source, {"t": 2.0}, box_features=["box"], door_features=["door"],
    )
    assert source == original
    assert calls == [
        ("door-spec", (3, 2), ["door"]),
        ("engine", (3, 2), 2.0, "spec"),
    ]
    assert result["indicator_box"]["width"] == 210.0
    assert "排列 [3, 2]" in result["indicator_box"]["baseline_status_text"]


@pytest.mark.parametrize("invalid", (
    {"layers": True}, {"layers": 7}, {"groups": [0, 2]},
    {"groups": [False, 2]}, {"offset_x": float("inf")},
    {"offset_y": "broken"}, {"is_box_dist": "unknown"},
))
def test_component_editor_contexts_reject_invalid_source_before_spec(invalid):
    source = {
        "mode": "indicator_box", "layers": 2, "groups": [3, 2, 2, 2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    source.update(invalid)
    before = deepcopy(source)
    host = SimpleNamespace(
        _normalize_door_indicator_state=lambda _:
            pytest.fail("display repair must not run"),
        _indicator_door_part_spec=lambda *a, **kw:
            pytest.fail("invalid state must not create a physical DoorPartSpec"),
    )
    with pytest.raises(ValueError):
        manufacturing_adapter._indicator_component_editor_contexts(
            host, source, {"t": 2.0}, box_features=[], door_features=[],
        )
    assert source == before


def test_component_context_source_does_not_contain_gui_group_coercion():
    source = inspect.getsource(manufacturing_adapter._indicator_component_editor_contexts)
    assert "project_operator_door_cell_indicator_manufacturing_source(" in source
    assert "_normalize_door_indicator_state(" not in source
    assert "max(1, min(6, int(" not in source
    assert "tuple(int(v)" not in source
