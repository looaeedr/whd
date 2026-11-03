"""#2517: standalone IndicatorBox/SmallDoor reject lossy physical group sources.

GUI and headless callers must use the same Engine manufacturing request gate.
"""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_manufacturing_projection as gui


def _payload(family="金庫型", *, groups=(2, 3), include_groups=True):
    data = {
        "model": family, "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "features": (),
    }
    if include_groups:
        data["indicator_layer_groups"] = groups
    return data


def _host(calls):
    def box(values, groups, *, features):
        calls.append("indicator_box")
        return api.build_indicator_box_operator_part_spec(
            values, groups, features=features,
        )

    def door(values, groups, *, features):
        calls.append("indicator_door")
        return api.indicator_small_door_operator_spec(
            groups, thickness=values["t"], frame_width=values["fw"],
            door_gap_w=values["door_gap_w"], door_gap_h=values["door_gap_h"],
            indicator_door_fold=values.get("indicator_door_fold"),
            features=features,
        )

    return SimpleNamespace(
        _indicator_box_part_spec_from_values=box,
        _indicator_door_part_spec_from_values=door,
    )


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("part", ("indicator_box", "indicator_door"))
def test_standalone_indicator_gui_and_headless_share_physical_groups(
    monkeypatch, family, part, tmp_path,
):
    # The corner policy is unrelated to this independent part's source gate.
    monkeypatch.setattr(gui, "_payload_policy", lambda *args: None)
    source = _payload(family, groups=[2, "3"])
    before = deepcopy(source)
    calls = []
    spec, context = gui._fold_designer_part_spec_from_payload(
        _host(calls), part, source,
    )
    assert calls == [part]
    assert source == before
    if part == "indicator_box":
        direct = api.build_indicator_box_operator_part_spec(
            {"t": 2.0}, [2, "3"], features=(),
        )
    else:
        defaults = api.resolve_fold_designer_legacy_numeric_settings(
            source, part_name=part,
        )
        direct, direct_context = api.indicator_small_door_operator_spec(
            [2, "3"], thickness=2.0, frame_width=29.0,
            door_gap_w=defaults["door_gap_w"],
            door_gap_h=defaults["door_gap_h"],
            indicator_door_fold=defaults["indicator_door_fold"],
            features=(),
        )
        assert context == direct_context
    assert spec == direct
    assert spec.layer_groups == (2, 3) if part == "indicator_box" else spec.indicator_window_groups == (2, 3)

    # Genuine Engine FinalScene -> DXF -> independent disk reopen, not a GUI drawing.
    render = api.build_part_render_data(spec, context)
    path = tmp_path / f"{family}-{part}.dxf"
    api.save_part_render_data_dxf(render, path, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(render, path).ok


@pytest.mark.parametrize("part", ("indicator_box", "indicator_door"))
@pytest.mark.parametrize("groups", (
    [True, 2], [False], [2.5], [0], [-1], ["2.5"],
    [float("nan")], [float("inf")], ["bad"], [],
))
def test_invalid_standalone_indicator_source_rejected_before_any_part_spec(
    monkeypatch, part, groups,
):
    monkeypatch.setattr(gui, "_payload_policy", lambda *args: None)
    calls = []
    raw = _payload("受電箱", groups=groups)
    before = deepcopy(raw)
    with pytest.raises(ValueError, match="指示燈"):
        gui._fold_designer_part_spec_from_payload(_host(calls), part, raw)
    assert calls == []
    # NaN is not self-equal; compare source representation without sanitizing it.
    assert repr(raw) == repr(before)
    if part == "indicator_box":
        with pytest.raises(ValueError, match="指示燈"):
            api.build_indicator_box_operator_part_spec(
                {"t": 2}, groups, features=(),
            )
    else:
        with pytest.raises(ValueError, match="指示燈"):
            api.indicator_small_door_operator_spec(
                groups, thickness=2, frame_width=29,
                door_gap_w=3.5, door_gap_h=3.5,
            )


@pytest.mark.parametrize("part", ("indicator_box", "indicator_door"))
def test_missing_legacy_indicator_groups_keep_one_layer_but_explicit_empty_fails(
    monkeypatch, part,
):
    monkeypatch.setattr(gui, "_payload_policy", lambda *args: None)
    calls = []
    spec, _ = gui._fold_designer_part_spec_from_payload(
        _host(calls), part, _payload(include_groups=False),
    )
    assert calls == [part]
    groups = spec.layer_groups if part == "indicator_box" else spec.indicator_window_groups
    assert groups == (1,)
    with pytest.raises(ValueError, match="指示燈"):
        gui._fold_designer_part_spec_from_payload(
            _host([]), part, _payload(groups=[]),
        )


def test_gui_manufacturing_does_not_silently_int_cast_indicator_groups():
    source = inspect.getsource(gui._fold_designer_part_spec_from_payload)
    assert "normalize_fold_designer_indicator_groups(" in source
    assert "tuple(int(v) for v in (data.get(\"indicator_layer_groups\")" not in source
