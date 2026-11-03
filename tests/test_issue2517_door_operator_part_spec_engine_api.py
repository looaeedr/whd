"""#2517: canonical Door operator spec owns 2D/3D/export source identity."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import build_door_operator_part_spec, manufacturing_api
from ae_engine.contracts import DoorPartSpec
from ae_engine.sheetmetal_part_adapters import DoorFrameEdges
from gui_modules.application import manufacturing_adapter as gui


def _values():
    return {
        "w": "800.0", "h": "1600.0", "t": "2.0", "fw": "29.0",
        "door_gap_w": "3.5", "door_gap_h": "4.5",
        "door_fold_l": "15", "door_fold_r": "14",
        "door_fold_t": "13", "door_fold_b": "12",
    }


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_public_engine_builds_legacy_door_request_exactly_and_detaches_sources(model):
    data = _values()
    features = [{"kind": "circle", "source": "original"}]
    edges = DoorFrameEdges(left=False, right=True, top=True, bottom=False)
    original = deepcopy((data, features))
    kwargs = {
        "model_name": model,
        "features": features,
        "indicator_hole": (80, 120),
        "door_indicator": [2, 3],
        "door_indicator_offset": ("7.5", "-8.0"),
        "use_box_distance": True,
        "frame_edges": edges,
        "indicator_window_groups": [1, 2, 2],
        "nameplate_center_datum_top": "65.5",
    }
    spec = manufacturing_api.build_door_operator_part_spec(data, **kwargs)
    assert isinstance(spec, DoorPartSpec)
    assert build_door_operator_part_spec(data, **kwargs) == spec
    assert (spec.width, spec.height, spec.thickness, spec.frame_width) == (800, 1600, 2, 29)
    assert (spec.gap_w, spec.gap_h) == (3.5, 4.5)
    assert (spec.fold_left, spec.fold_right, spec.fold_top, spec.fold_bottom) == (15, 14, 13, 12)
    assert spec.model_name == model
    assert spec.frame_edges == edges
    assert spec.feature_space == "legacy_unfolded"
    assert spec.features == tuple(features)
    assert spec.indicator_hole == (80, 120)
    assert spec.door_indicator == (2, 3)
    assert spec.indicator_window_groups == (1, 2, 2)
    assert spec.door_indicator_offset == (7.5, -8.0)
    assert spec.nameplate_center_datum_top == 65.5
    assert spec.use_box_distance is True
    assert (data, features) == original
    with pytest.raises(FrozenInstanceError):
        spec.width = 10.0


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
def test_gui_single_and_cell_send_source_inputs_to_same_engine_contract(model, monkeypatch):
    data = _values()
    host = SimpleNamespace(door_nameplate_center_datum_top=54.0)
    calls = []
    original = manufacturing_api.build_door_operator_part_spec
    def forwarded(values, **kwargs):
        calls.append((values, dict(kwargs)))
        return original(values, **kwargs)
    monkeypatch.setattr(manufacturing_api, "build_door_operator_part_spec", forwarded)
    single = gui._door_part_spec_from_values(
        host, data, model_name=model, features=["single"],
    )
    assert single.features == ("single",)
    assert single.frame_edges == DoorFrameEdges()
    assert single.indicator_window_groups is None
    assert single.nameplate_center_datum_top == 54.0
    assert calls[0][0] is data
    assert calls[0][1]["model_name"] == model
    cell = dict(data, w=450, h=700)
    edges = DoorFrameEdges(left=True, right=False, top=False, bottom=True)
    per_cell = gui._door_part_spec_from_values(
        host, cell, model_name=model, features=["cell"], frame_edges=edges,
        indicator_window_groups=[2], door_indicator=(2,),
    )
    assert (per_cell.width, per_cell.height) == (450, 700)
    assert per_cell.frame_edges == edges
    assert per_cell.features == ("cell",)
    assert per_cell.door_indicator == (2,)
    assert len(calls) == 2
    assert calls[1][0] is cell


def test_missing_or_bad_operator_dimensions_are_not_manufacturing_success():
    with pytest.raises(KeyError):
        manufacturing_api.build_door_operator_part_spec(
            {"w": 400}, model_name="金庫型",
        )
    data = _values()
    data["door_fold_l"] = "non_numeric"
    with pytest.raises(ValueError):
        manufacturing_api.build_door_operator_part_spec(data, model_name="受電箱")


def test_gui_no_longer_selects_door_feature_space_or_material_folds():
    source = inspect.getsource(gui._door_part_spec_from_values)
    assert "manufacturing_api.build_door_operator_part_spec(" in source
    assert "DoorPartSpec(" not in source
    assert "legacy_unfolded" not in source
    assert "float(val[" not in source
    assert "DoorFrameEdges()" not in source
    engine = inspect.getsource(manufacturing_api.build_door_operator_part_spec)
    assert "from .door_operator_part_spec import" in engine


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
@pytest.mark.parametrize("field,invalid", (
    ("w", True),
    ("w", 0.0),
    ("h", float("inf")),
    ("t", float("nan")),
    ("fw", False),
    ("door_gap_w", True),
    ("door_gap_h", float("inf")),
    ("door_fold_l", float("nan")),
    ("door_fold_r", False),
    ("door_fold_t", "1e309"),
    ("door_fold_b", "not-a-number"),
))
def test_engine_and_real_gui_adapter_reject_invalid_door_physical_source_before_manufacture(
    model, field, invalid, tmp_path,
):
    """Physical source rejection must match in both public and GUI entrypoints."""
    data = _values()
    data[field] = invalid
    original = repr(data)
    host = SimpleNamespace(door_nameplate_center_datum_top=None)
    with pytest.raises((TypeError, ValueError)):
        manufacturing_api.build_door_operator_part_spec(
            data, model_name=model, features=(),
        )
    with pytest.raises((TypeError, ValueError)):
        gui._door_part_spec_from_values(
            host, data, model_name=model, features=(),
        )
    assert repr(data) == original
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kw,invalid", (
    ("door_indicator_offset", (True, 0.0)),
    ("door_indicator_offset", (0.0, float("nan"))),
    ("door_indicator_offset", (float("inf"), 0.0)),
    ("use_box_distance", "ambiguous"),
    ("use_box_distance", float("nan")),
    ("door_indicator", (True,)),
    ("door_indicator", (1.5,)),
    ("indicator_window_groups", (0,)),
    ("indicator_window_groups", (False,)),
    ("nameplate_center_datum_top", float("nan")),
    ("nameplate_center_datum_top", True),
))
def test_engine_and_gui_reject_invalid_door_auxiliary_physical_source(
    kw, invalid,
):
    before = repr(invalid)
    host = SimpleNamespace(door_nameplate_center_datum_top=None)
    options = {kw: invalid}
    # Optional lamp positions / box-distance only matter when an actual
    # indicator or opening exists. Plain Doors ignore disabled controls.
    if kw in ("door_indicator_offset", "use_box_distance"):
        options["door_indicator"] = (2,)
    with pytest.raises((TypeError, ValueError)):
        manufacturing_api.build_door_operator_part_spec(
            _values(), model_name="受電箱", **options,
        )
    if kw != "nameplate_center_datum_top":
        with pytest.raises((TypeError, ValueError)):
            gui._door_part_spec_from_values(
                host, _values(), model_name="受電箱", features=(), **options,
            )
    assert repr(invalid) == before


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_numeric_text_and_signed_door_offsets_keep_legacy_source_compatibility(
    model,
):
    host = SimpleNamespace(door_nameplate_center_datum_top="65.5")
    val = _values()
    val["door_fold_b"] = "-2.5"  # Signed Fold is an Engine mechanical concern.
    before = deepcopy(val)
    engine = manufacturing_api.build_door_operator_part_spec(
        val, model_name=model, door_indicator_offset=("-7.25", "0"),
        use_box_distance="false", door_indicator=["2", "3"],
        indicator_window_groups=["1", 2.0],
        nameplate_center_datum_top="65.5",
    )
    guispec = gui._door_part_spec_from_values(
        host, val, model_name=model, features=(),
        door_indicator_offset=("-7.25", "0"),
        use_box_distance="false", door_indicator=["2", "3"],
        indicator_window_groups=["1", 2.0],
    )
    assert engine == guispec
    assert (engine.door_indicator_offset, engine.use_box_distance) == (
        (-7.25, 0.0), False,
    )
    assert engine.door_indicator == (2, 3)
    assert engine.indicator_window_groups == (1, 2)
    assert engine.fold_bottom == -2.5
    assert val == before


@pytest.mark.parametrize("model", ("金庫型", "受電箱"))
def test_disabled_invalid_indicator_controls_do_not_block_plain_door(
    model,
):
    """No lamp/box means disabled indicator fields are not manufacturing data."""
    host = SimpleNamespace(door_nameplate_center_datum_top=None)
    values = _values()
    options = dict(
        door_indicator=None,
        indicator_hole=None,
        door_indicator_offset=(float("nan"), True),
        use_box_distance="not-a-boolean",
    )
    direct = manufacturing_api.build_door_operator_part_spec(
        values, model_name=model, features=(), **options,
    )
    via_gui = gui._door_part_spec_from_values(
        host, values, model_name=model, features=(), **options,
    )
    assert via_gui == direct
    assert direct.door_indicator is None and direct.indicator_hole is None
    assert direct.door_indicator_offset == (0.0, 0.0)
    assert direct.use_box_distance is False


@pytest.mark.parametrize("opening", (
    (True, 80.0),
    (80.0, False),
    (float("nan"), 120.0),
    (80.0, float("inf")),
    (0, 120.0),
    (-2, 120.0),
    ("invalid", 120.0),
))
def test_gui_and_headless_door_refuse_unconfirmed_box_opening_dimensions(
    opening,
):
    """An enabled IndicatorBox CUTTING opening cannot coerce bool/nonfinite mm."""
    host = SimpleNamespace(door_nameplate_center_datum_top=None)
    options = dict(indicator_hole=opening, door_indicator_offset=(0, 0))
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.build_door_operator_part_spec(
            _values(), model_name="受電箱", features=(), **options,
        )
    with pytest.raises((ValueError, TypeError)):
        gui._door_part_spec_from_values(
            host, _values(), model_name="受電箱", features=(), **options,
        )


def test_disabled_door_keeps_valid_legacy_offsets_without_enabling_holes():
    source = _values()
    spec = manufacturing_api.build_door_operator_part_spec(
        source, model_name="金庫型",
        door_indicator=None, indicator_hole=None,
        door_indicator_offset=("-7.5", "12"),
        use_box_distance=True,
    )
    assert spec.door_indicator is None and spec.indicator_hole is None
    assert spec.door_indicator_offset == (-7.5, 12.0)
    assert spec.use_box_distance is True
