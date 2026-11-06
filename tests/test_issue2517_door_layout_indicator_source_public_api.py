"""#2517: original Door-cell indicator source is resolved only inside public Engine."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import manufacturing_adapter as adapter
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges


def _values(model):
    return dict(
        model=model, w=600.0, h=800.0, t=2.0, fw=25.0,
        door_gap_w=2.0, door_gap_h=2.0,
        door_fold_l=10.0, door_fold_r=10.0,
        door_fold_t=10.0, door_fold_b=10.0,
    )


def _source(mode):
    return dict(
        mode=mode, layers=2, groups=[2, 3, 999],
        offset_x=4.5, offset_y=-7.25, is_box_dist=True,
    )


def _build(values, **kwargs):
    return manufacturing_api.build_door_operator_part_spec(
        values, model_name=values["model"], features=(), **kwargs
    )


@pytest.mark.parametrize("family", ("受電箱", "金庫型"))
@pytest.mark.parametrize("mode", ("indicator_box", "indicator"))
def test_engine_owns_indicator_mode_groups_opening_and_offset(family, mode):
    values = _values(family)
    source = _source(mode)
    original = deepcopy(source)
    canonical = manufacturing_api.project_operator_door_cell_indicator_manufacturing_source(source)
    groups = tuple(canonical["groups"][:canonical["layers"]])
    old_equivalent = _build(
        values,
        indicator_hole=(
            manufacturing_api.indicator_box_opening_size(groups, thickness=values["t"])
            if mode == "indicator_box" else None
        ),
        door_indicator=groups if mode == "indicator" else None,
        door_indicator_offset=(canonical["offset_x"], canonical["offset_y"]),
        use_box_distance=canonical["is_box_dist"],
    )
    actual = _build(values, indicator_source_state=source)
    assert actual == old_equivalent
    assert actual.door_indicator_offset == (4.5, -7.25)
    assert source == original
    assert (actual.indicator_hole is not None) == (mode == "indicator_box")
    assert (actual.door_indicator is not None) == (mode == "indicator")


def test_legacy_flags_are_engine_validated_not_gui_repaired():
    source = _source("indicator")
    source.pop("mode")
    source["enabled"] = True
    source["box_enabled"] = False
    spec = _build(_values("受電箱"), indicator_source_state=source)
    assert spec.door_indicator == (2, 3)
    assert spec.indicator_hole is None


def test_disabled_source_never_fabricates_a_physical_lamp():
    state = dict(mode="none", layers="broken", groups="bad",
                 offset_x=float("nan"), offset_y=True)
    spec = _build(_values("金庫型"), indicator_source_state=state)
    assert spec.indicator_hole is None
    assert spec.door_indicator is None
    assert spec.door_indicator_offset == (0.0, 0.0)


@pytest.mark.parametrize("bad_source", [
    {"mode": "indicator", "layers": 2, "groups": [2],
     "offset_x": 0, "offset_y": 0, "is_box_dist": False},
    {"mode": "indicator_box", "layers": 1, "groups": [True],
     "offset_x": 0, "offset_y": 0, "is_box_dist": False},
    {"mode": "indicator", "layers": 1, "groups": [2],
     "offset_x": float("nan"), "offset_y": 0, "is_box_dist": False},
    {"mode": "indicator_box", "layers": 1, "groups": [2],
     "offset_x": 0, "offset_y": float("inf"), "is_box_dist": False},
])
def test_invalid_active_original_hole_source_never_builds_a_partspec(bad_source):
    with pytest.raises(ValueError):
        _build(_values("受電箱"), indicator_source_state=bad_source)


def test_engine_rejects_competing_raw_and_precomputed_hole_sources():
    with pytest.raises(ValueError, match="DOOR_OPERATOR_INDICATOR_DUPLICATE_SOURCE"):
        _build(
            _values("受電箱"), indicator_source_state=_source("indicator_box"),
            indicator_hole=(20.0, 20.0),
        )


def test_legacy_direct_door_indicator_source_remains_backward_compatible():
    spec = _build(
        _values("金庫型"), door_indicator=(2, 3),
        door_indicator_offset=(3.0, -5.0), use_box_distance=False,
    )
    assert spec.door_indicator == (2, 3)
    assert spec.door_indicator_offset == (3.0, -5.0)


def test_gui_forwards_raw_original_cell_source_without_constructing_holes(monkeypatch):
    raw = _source("indicator_box")
    seen = []

    def engine(values, **kwargs):
        seen.append((dict(values), kwargs))
        return "engine-spec"

    monkeypatch.setattr(manufacturing_api, "build_door_operator_part_spec", engine)
    host = SimpleNamespace(
        _door_layout_cell_key=lambda cell: "cell_1",
        door_layout_indicator_states={"cell_1": raw},
        door_layout_features={"cell_1": []},
        _baseline_source_model=lambda: "受電箱",
        _manual_corner_policy=lambda *args: None,
        _door_material_frame_width=lambda fw, t: fw,
        door_nameplate_center_datum_top=None,
    )
    host._door_part_spec_from_values = (
        lambda values, **kwargs: adapter._door_part_spec_from_values(
            host, values, **kwargs
        )
    )
    cell = SimpleNamespace(start_width=540.0, start_height=720.0, edges=DoorFrameEdges())
    assert adapter._door_layout_part_spec(host, cell, _values("受電箱")) == "engine-spec"
    values, kwargs = seen[0]
    assert values["w"] == 540.0 and values["h"] == 720.0
    assert kwargs["indicator_source_state"] is raw
    assert kwargs["indicator_hole"] is None
    assert kwargs["door_indicator"] is None
    assert kwargs["door_indicator_offset"] == (0.0, 0.0)
    source = inspect.getsource(adapter._door_layout_part_spec)
    assert "indicator_box_opening_size(" not in source
    assert "project_operator_door_cell_indicator_manufacturing_source(" not in source
