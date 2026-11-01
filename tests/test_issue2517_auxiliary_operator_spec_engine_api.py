"""#2517: BasePlate and IndicatorBox manufacturing request owners are Engine."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import (
    build_base_plate_operator_part_spec,
    build_indicator_box_operator_part_spec,
    manufacturing_api,
)
from ae_engine.contracts import BasePlatePartSpec, IndicatorBoxPartSpec
from ae_engine.box_body_fold_profile import profile_to_fold_segments
from gui_modules.application import manufacturing_adapter as gui


def data(model):
    return {
        "model": model, "w": 800, "h": 1600, "t": 2, "fw": 25,
        "base_plate_shrink_top": 3, "base_plate_shrink_bottom": 4,
        "base_plate_shrink_left": 5, "base_plate_shrink_right": 6,
        "base_plate_bend": 15, "physical_id": "base_plate:nfb_layer:1",
        "receiving_bend_pattern": "CONFIRMED_SOURCE_PATTERN",
        "receiving_nfb_depth_pair_mm": (120, 80),
    }


@pytest.mark.parametrize("model,receiving", [
    ("金庫型", False), ("受電箱", True), ("RECEIVING", True), ("自訂", False),
])
def test_headless_base_plate_preserves_operator_and_receiving_source(model, receiving):
    values = data(model)
    prior = deepcopy(values)
    structure = {"active_type": "three_piece"}
    profile = [{"phase6_key": "w", "len": 794, "core": "W"}]
    actual = manufacturing_api.build_base_plate_operator_part_spec(
        values, features=({"source": "saved"},),
        box_body_structure_state=structure, box_body_fold_profile=profile,
    )
    assert isinstance(actual, BasePlatePartSpec)
    assert actual == build_base_plate_operator_part_spec(
        values, features=({"source": "saved"},),
        box_body_structure_state=structure, box_body_fold_profile=profile,
    )
    assert (actual.width, actual.height, actual.thickness) == (800, 1600, 2)
    assert (actual.shrink_top, actual.shrink_bottom, actual.shrink_left,
            actual.shrink_right, actual.bend) == (3, 4, 5, 6, 15)
    assert actual.box_body_structure_state == structure
    assert actual.box_body_fold_profile == profile_to_fold_segments(profile)
    assert actual.physical_id == "base_plate:nfb_layer:1"
    assert actual.receiving_bend_pattern == (
        "CONFIRMED_SOURCE_PATTERN" if receiving else None
    )
    assert actual.receiving_nfb_depth_pair_mm == ((120, 80) if receiving else None)
    assert values == prior
    with pytest.raises(FrozenInstanceError):
        actual.width = 10


def test_legacy_empty_model_default_id_and_source_roundtrip():
    values = data("")
    values.pop("physical_id")
    roundtrip = json.loads(json.dumps(values, ensure_ascii=False))
    got = build_base_plate_operator_part_spec(roundtrip, features=())
    assert got.model_name is None and got.physical_id == "base_plate"
    assert got.receiving_nfb_depth_pair_mm is None
    assert got.receiving_bend_pattern is None
    values.pop("base_plate_shrink_top")
    with pytest.raises(KeyError, match="base_plate_shrink_top"):
        build_base_plate_operator_part_spec(values, features=())


def test_indicator_group_normalization_is_single_public_engine_owner():
    value = {"t": 2.5}
    got = manufacturing_api.build_indicator_box_operator_part_spec(
        value, ["2", 3, 4], features=["existing"],
    )
    assert isinstance(got, IndicatorBoxPartSpec)
    assert got is not None
    assert got == build_indicator_box_operator_part_spec(
        value, ("2", 3, 4), features=("existing",),
    )
    assert got.layer_groups == (2, 3, 4)
    assert got.thickness == pytest.approx(2.5)
    assert got.model_name is None
    assert got.corner_policy is None
    assert got.features == ("existing",)
    with pytest.raises(ValueError):
        build_indicator_box_operator_part_spec(value, ["bad"], features=[])
    with pytest.raises(KeyError):
        build_indicator_box_operator_part_spec({}, (2, 2), features=[])


def test_base_plate_gui_only_collects_current_workspace_sources(monkeypatch):
    sentinel = object()
    seen = []
    def port(values, **kwargs):
        seen.append((values, kwargs))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "build_base_plate_operator_part_spec", port)
    source = data("受電箱")
    host = SimpleNamespace(workspace_controller=SimpleNamespace(
        box_body_structure_state=lambda: {"active_type": "three_piece"},
        box_body_profile=lambda: [{"phase6_key": "w", "len": 800}],
    ))
    assert gui._base_plate_part_spec_from_values(
        host, source, features=["hole"]
    ) is sentinel
    assert seen[0][0] is source
    assert seen[0][1]["box_body_structure_state"] == {"active_type": "three_piece"}
    assert seen[0][1]["box_body_fold_profile"] == [{"phase6_key": "w", "len": 800}]
    body = inspect.getsource(gui._base_plate_part_spec_from_values)
    assert "manufacturing_api.build_base_plate_operator_part_spec(" in body
    for forbidden in ("BasePlatePartSpec(", "profile_to_fold_segments(",
                      "receiving_nfb_depth_pair_mm", "receiving_bend_pattern"):
        assert forbidden not in body


def test_both_indicator_gui_entries_use_same_public_port(monkeypatch):
    calls = []
    sentinel = object()
    def port(values, groups, *, features):
        calls.append((values, groups, features))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "build_indicator_box_operator_part_spec", port)
    host = SimpleNamespace()
    val = {"t": 2.0}
    assert gui._indicator_box_part_spec_from_values(
        host, val, ["2"], features=["cut"],
    ) is sentinel
    assert gui._indicator_box_part_spec(
        host, val, ["2"], features=["cut"],
    ) is sentinel
    assert calls == [(val, ["2"], ["cut"]), (val, ["2"], ["cut"])]
    for fn in (gui._indicator_box_part_spec_from_values, gui._indicator_box_part_spec):
        source = inspect.getsource(fn)
        assert "manufacturing_api.build_indicator_box_operator_part_spec(" in source
        assert "IndicatorBoxPartSpec(" not in source
