"""#2517: all public IndicatorBox/SmallDoor dimension callers retain original source."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_door_indicator as owner
from ae_engine.contracts import (
    DoorPartSpec, IndicatorBoxPartSpec, ManufacturingContext,
)
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import manufacturing_adapter as gui


def _base_door():
    return DoorPartSpec(
        width=800.0, height=1100.0, thickness=2.125,
        frame_width=25.0, model_name="金庫型",
    )


def _result(entry, groups, thickness):
    if entry == "unfolded":
        return api.indicator_box_unfolded_size(groups, thickness=thickness)
    if entry == "finished":
        return api.indicator_box_finished_face_size(groups, thickness=thickness)
    if entry == "opening":
        return api.indicator_box_opening_size(groups, thickness=thickness)
    if entry == "small_finished":
        return api.indicator_small_door_finished_size(groups, thickness=thickness)
    if entry == "small_spec":
        return api.indicator_small_door_spec(groups, thickness=thickness)
    if entry == "small_unfolded":
        return api.indicator_small_door_unfolded_size(groups, thickness=thickness)
    if entry == "operator_spec":
        return api.indicator_small_door_operator_spec(
            groups, thickness=thickness, frame_width=25.0,
            door_gap_w=3.5, door_gap_h=3.5,
        )
    if entry == "offset":
        return api.door_indicator_offset_for_finished_center(
            _base_door(), groups, Vec2(310.0, 400.0),
        )
    raise AssertionError(entry)


_ENTRIES = (
    "unfolded", "finished", "opening", "small_finished",
    "small_spec", "small_unfolded", "operator_spec", "offset",
)


@pytest.mark.parametrize("entry", _ENTRIES)
@pytest.mark.parametrize("bad", [
    [True], [False], [2.5], ["2.5"], [float("nan")],
    [float("inf")], [0], [-1], [], "2", {"layer": 2},
])
def test_invalid_original_indicator_groups_reject_before_ae_geometry(
    monkeypatch, entry, bad,
):
    monkeypatch.setattr(
        owner.ae, "get_indicator_box_data",
        lambda *a, **kw: pytest.fail("invalid groups entered manufacturing geometry"),
    )
    before = repr(bad)
    with pytest.raises((ValueError, TypeError)):
        _result(entry, bad, 2.125)
    assert repr(bad) == before


@pytest.mark.parametrize("entry", _ENTRIES[:-1])
@pytest.mark.parametrize("bad", [
    True, False, 0, -2, None, "", "nan", "inf",
    float("nan"), float("inf"), "bad",
])
def test_invalid_original_indicator_t_rejects_before_ae_geometry(
    monkeypatch, entry, bad,
):
    monkeypatch.setattr(
        owner.ae, "get_indicator_box_data",
        lambda *a, **kw: pytest.fail("invalid T entered manufacturing geometry"),
    )
    before = repr(bad)
    with pytest.raises((ValueError, TypeError)):
        _result(entry, (2,), bad)
    assert repr(bad) == before


@pytest.mark.parametrize("xy", [
    (True, 400.0), (310.0, float("nan")),
    (310.0, float("inf")), ("bad", 400.0),
])
def test_indicator_center_source_rejects_before_offset_becomes_a_hole(xy):
    with pytest.raises((ValueError, TypeError)):
        api.door_indicator_offset_for_finished_center(
            _base_door(), (2,), Vec2(*xy),
        )


def test_public_sizes_and_gui_operator_small_door_share_canonical_saved_source():
    source = {"groups": ["03", 2.0], "t": "2.125"}
    before = deepcopy(source)
    recovered = json.loads(json.dumps(source))
    groups = api.normalize_fold_designer_indicator_groups(recovered["groups"])
    t = api.normalize_operator_source_dimension(recovered["t"], field="t")
    assert groups == (3, 2) and t == 2.125
    for entry in _ENTRIES:
        assert _result(entry, source["groups"], source["t"]) == _result(entry, groups, t)

    raw_spec, raw_context = _result("operator_spec", source["groups"], source["t"])
    expected, ctx = _result("operator_spec", groups, t)
    assert raw_spec == expected and raw_context == ctx
    assert raw_spec.indicator_window_groups == (3, 2)
    assert raw_spec.thickness == pytest.approx(t)
    # Original GUI source forwarding is unchanged; only Engine source qualification changes.
    forwarded = inspect.getsource(gui._indicator_door_part_spec_from_values)
    assert "manufacturing_api.indicator_small_door_operator_spec(" in forwarded
    assert source == before


def test_project_save_reload_real_indicator_baseline_dxf_and_headless_size(tmp_path):
    import phase6_project_file as project

    original = {
        "model": "金庫型", "w": 800.0, "h": 1100.0, "d": 350.0,
        "t": 2.125, "fw": 25.0,
        "indicator_layer_groups": [3, 2],
    }
    path = project.write_project(
        tmp_path / "indicator-size.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    saved = project.read_project(path)["snapshot"]
    assert saved["indicator_layer_groups"] == original["indicator_layer_groups"]
    groups = api.normalize_fold_designer_indicator_groups(saved["indicator_layer_groups"])
    assert groups == (3, 2)
    assert api.indicator_box_unfolded_size(groups, thickness=saved["t"]) == (
        api.indicator_box_unfolded_size(groups, thickness=original["t"])
    )
    assert api.indicator_small_door_spec(
        groups, thickness=saved["t"]
    ) == api.indicator_small_door_spec(
        groups, thickness=original["t"]
    )

    # Verify actual committed source '基準檔/指示燈/盒子.dxf', not a screenshot.
    root = Path(__file__).resolve().parents[1]
    assert (root / "基準檔" / "指示燈" / "盒子.dxf").is_file()
    output = tmp_path / "indicator-box-real.dxf"
    spec = IndicatorBoxPartSpec(layer_groups=groups, thickness=saved["t"])
    api.generate_part(
        spec, output, ManufacturingContext(resource_root=root),
    )
    reopened = ezdxf.readfile(output)
    layers = {e.dxf.layer for e in reopened.modelspace()}
    assert "CUTTING" in layers and "BEND" in layers


def test_direct_public_gate_does_not_erase_original_gui_or_engine_validation():
    for fn in (
        owner.indicator_box_unfolded_size,
        owner.indicator_small_door_spec,
    ):
        source = inspect.getsource(fn)
        assert "_validated_indicator_box_physical_source(groups, thickness)" in source
        assert "tuple(int(v) for v in groups)" not in source
    source = inspect.getsource(owner.indicator_small_door_operator_spec)
    assert "thickness=thickness, context=context" in source
    assert "thickness=float(thickness)" not in source
    offset_source = inspect.getsource(owner.door_indicator_offset_for_finished_center)
    assert "normalize_fold_designer_indicator_groups(groups)" in offset_source
    assert "normalize_fold_designer_indicator_offsets(" in offset_source
    assert "tuple(int(v) for v in groups)" not in offset_source
