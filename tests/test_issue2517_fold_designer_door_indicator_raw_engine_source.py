"""#2517: Fold Designer's Door/Cell manufacturing aperture belongs to public Engine."""
from copy import deepcopy
from dataclasses import asdict
import inspect
import json
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.manufacturing_door_indicator import indicator_box_opening_size
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from gui_modules.application.fold_designer_manufacturing_projection import (
    _door_part_spec_from_payload_context,
)


def _values():
    return dict(
        w=650.0, h=900.0, t=2.0, fw=25.0,
        door_gap_w=2.0, door_gap_h=2.0,
        door_fold_l=15.0, door_fold_r=15.0,
        door_fold_t=15.0, door_fold_b=15.0,
    )


def _build(*, fold_designer_indicator_source=None, indicator_source_state=None, **kwargs):
    return manufacturing_api.build_door_operator_part_spec(
        _values(), model_name=None,
        fold_designer_indicator_source=fold_designer_indicator_source,
        indicator_source_state=indicator_source_state, **kwargs,
    )


def test_root_facade_single_door_source_uses_same_canonical_engine():
    assert ae_engine.build_door_operator_part_spec is manufacturing_api.build_door_operator_part_spec
    raw = {
        "door_indicator_box_enabled": True,
        "indicator_layer_groups": [2, 3],
        "door_indicator_offset": [-1.25, 2.5],
        "use_box_distance": "false",
    }
    saved = deepcopy(raw)
    spec = _build(fold_designer_indicator_source=raw)
    expected = _build(
        indicator_hole=indicator_box_opening_size((2, 3), thickness=2.0),
        door_indicator_offset=(-1.25, 2.5),
        use_box_distance=False,
    )
    assert spec == expected
    assert spec.indicator_hole == expected.indicator_hole
    assert spec.door_indicator is None
    assert spec.door_indicator_offset == (-1.25, 2.5)
    assert spec.use_box_distance is False
    assert raw == saved


def test_direct_indicator_and_disabled_box_flag_decode_without_gui_truthiness():
    source = {
        "door_indicator_box_enabled": "false",
        "door_indicator_groups": [2, 1],
        "indicator_layer_groups": ["not an enabled input"],
        "door_indicator_offset": [3.25, -1.5],
        "use_box_distance": "0",
    }
    result = _build(fold_designer_indicator_source=source)
    assert result.indicator_hole is None
    assert result.door_indicator == (2, 1)
    assert result.door_indicator_offset == (3.25, -1.5)
    assert result.use_box_distance is False
    assert source["indicator_layer_groups"] == ["not an enabled input"]


@pytest.mark.parametrize("source", [
    {"door_indicator_box_enabled": "sometimes"},
    {"door_indicator_box_enabled": True, "indicator_layer_groups": []},
    {"door_indicator_box_enabled": True, "indicator_layer_groups": [True]},
    {"door_indicator_groups": [0]},
    {"door_indicator_groups": [2], "door_indicator_offset": ["nan", 0]},
    {"door_indicator_groups": [2], "use_box_distance": "ambiguous"},
])
def test_invalid_single_door_hole_inputs_fail_closed(source):
    original = deepcopy(source)
    with pytest.raises((ValueError, TypeError, IndexError)):
        _build(fold_designer_indicator_source=source)
    assert source == original


def test_source_mutual_exclusion_and_wrong_type_are_rejected():
    raw = {"door_indicator_box_enabled": True, "indicator_layer_groups": [2]}
    for invalid in (
        {"indicator_hole": (30, 50)},
        {"door_indicator": (2,)},
        {"door_indicator_offset": (1, 0)},
        {"use_box_distance": True},
        {"indicator_source_state": {"mode": "none"}},
    ):
        with pytest.raises(ValueError, match="DOOR_OPERATOR_INDICATOR_DUPLICATE_SOURCE"):
            _build(fold_designer_indicator_source=raw, **invalid)
    with pytest.raises(ValueError, match="DOOR_OPERATOR_INDICATOR_DUPLICATE_SOURCE"):
        _build(fold_designer_indicator_source=["not-a-mapping"])


@pytest.mark.parametrize("mode", ["indicator", "indicator_box", "none"])
def test_saved_cell_engine_source_equals_real_canonical_door_spec_after_json_reopen(mode):
    state = {
        "mode": mode, "layers": 2, "groups": [2, 3],
        "offset_x": -1.25, "offset_y": 2.75, "is_box_dist": False,
    }
    original = deepcopy(state)
    first = _build(indicator_source_state=state)
    reopened_state = json.loads(json.dumps(state))
    second = _build(indicator_source_state=reopened_state)
    assert first == second
    assert state == original
    if mode == "indicator":
        assert first.door_indicator == (2, 3)
        assert first.indicator_hole is None
    elif mode == "indicator_box":
        assert first.door_indicator is None
        assert first.indicator_hole == indicator_box_opening_size((2, 3), thickness=2)
    else:
        assert first.door_indicator is None
        assert first.indicator_hole is None


def _gui_host(captured, saved_cells=None):
    def forward(values, **kwargs):
        captured.append((deepcopy(values), dict(kwargs)))
        return manufacturing_api.build_door_operator_part_spec(values, **kwargs)
    return SimpleNamespace(
        door_layout_indicator_states=saved_cells or {},
        _door_part_spec_from_values=forward,
    )


def test_fold_designer_gui_forwards_unmodified_cell_source_to_real_engine():
    raw = {
        "mode": "indicator_box", "layers": 1, "groups": [2],
        "offset_x": 0.5, "offset_y": -1.25, "is_box_dist": False,
    }
    data = {"door_layout_indicator_states": {"0:1": raw}}
    saved = deepcopy(data)
    seen = []
    host = _gui_host(seen)
    cell = SimpleNamespace(column_index=0, row_index=1, edges=DoorFrameEdges())
    spec = _door_part_spec_from_payload_context(
        host, data, 650, 900, 2, 25, "自訂", True, (), None, cell,
    )
    assert len(seen) == 1
    values, kwargs = seen[0]
    assert kwargs["indicator_source_state"] is raw
    assert kwargs["fold_designer_indicator_source"] is None
    assert kwargs["indicator_source_state"] == saved["door_layout_indicator_states"]["0:1"]
    assert "indicator_hole" not in kwargs and "door_indicator" not in kwargs
    assert spec.indicator_hole == indicator_box_opening_size((2,), thickness=2)
    assert spec.door_indicator_offset == (0.5, -1.25)
    assert data == saved
    # Existing and reopened project sources request the same Engine result.
    second = _door_part_spec_from_payload_context(
        _gui_host([]), json.loads(json.dumps(data)),
        650, 900, 2, 25, "自訂", True, (), None, cell,
    )
    assert spec == second


def test_fold_designer_gui_single_door_source_uses_existing_public_part_spec():
    data = {
        "door_indicator_box_enabled": "false",
        "door_indicator_groups": [2],
        "door_indicator_offset": [0.75, -0.25],
        "use_box_distance": "false",
    }
    recorded = []
    spec = _door_part_spec_from_payload_context(
        _gui_host(recorded), data, 650, 900, 2, 25, "自訂", True,
        (), None, None,
    )
    assert recorded[0][1]["fold_designer_indicator_source"] is data
    assert recorded[0][1]["indicator_source_state"] is None
    assert spec.door_indicator == (2,)
    assert spec.use_box_distance is False


def test_invalid_cell_source_reaches_engine_without_display_repair():
    invalid = {
        "mode": "indicator_box", "layers": 2, "groups": [2],
        "offset_x": 0.0, "offset_y": 0.0, "is_box_dist": False,
    }
    prior = deepcopy(invalid)
    data = {"door_layout_indicator_states": {"0:1": invalid}}
    cell = SimpleNamespace(column_index=0, row_index=1, edges=DoorFrameEdges())
    with pytest.raises(ValueError):
        _door_part_spec_from_payload_context(
            _gui_host([]), data, 650, 900, 2, 25,
            "自訂", True, (), None, cell,
        )
    assert invalid == prior


def test_gui_no_longer_calculates_indicator_manufacturing_mode_or_aperture():
    code = inspect.getsource(_door_part_spec_from_payload_context)
    assert "manufacturing_api.indicator_box_opening_size" not in code
    assert "manufacturing_api.normalize_fold_designer_indicator_groups" not in code
    assert 'mode == "indicator_box"' not in code
    assert '"door_indicator_box_enabled"' not in code
    assert "fold_designer_indicator_source=(data if door_cell is None else None)" in code
