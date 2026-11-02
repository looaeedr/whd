# -*- coding: utf-8 -*-
"""#2517: headless Door DXF and live preview use the same Engine indicator source."""
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.project import export_actions as export


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _host(*, box=False, door=False, box_layers="1", box_groups=("2",),
          door_layers="1", door_groups=("3",)):
    called = []
    def spec(values, **kwargs):
        called.append(("door_spec", kwargs))
        return "door-spec"
    def exported(spec, path, context):
        called.append(("export", spec))
    host = SimpleNamespace(
        is_indicator_box_var=Var(box),
        is_door_indicator_var=Var(door),
        multi_door_enabled_var=Var(False),
        indicator_l_var=Var(box_layers),
        indicator_layer_g_vars=tuple(Var(x) for x in box_groups),
        door_indicator_l_var=Var(door_layers),
        door_indicator_layer_g_vars=tuple(Var(x) for x in door_groups),
        _manufacturing_context=lambda *, draw_stock: "context",
        _single_door_part_spec=spec,
        _base_plate_part_spec=lambda values: "base-spec",
        _indicator_box_part_spec=lambda values, groups, *, features:
            called.append(("indicator_spec", groups)) or "indicator-box-spec",
        _indicator_door_part_spec=lambda values, groups, *, features:
            called.append(("small_door_spec", groups)) or "indicator-door-spec",
        _export_authoritative_part=exported,
        surface_features={"indicator_box": [], "indicator_door": []},
    )
    return host, called


def _flags(*selected):
    return {
        key: key in selected for key in (
            "box_body", "head", "tail", "door", "base_plate",
            "indicator_box", "indicator_door",
        )
    }


@pytest.mark.parametrize("which,kwargs", [
    ("box", dict(box=True, box_groups=("invalid",))),
    ("box", dict(box=True, box_layers="2", box_groups=("2",))),
    ("box", dict(box=True, box_groups=(0,))),
    ("door", dict(door=True, door_groups=("invalid",))),
    ("door", dict(door=True, door_layers="2", door_groups=("3",))),
    ("door", dict(door=True, door_groups=(True,))),
])
def test_bad_enabled_indicator_never_exports_door_without_holes(tmp_path, which, kwargs):
    host, called = _host(**kwargs)
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags("door"), False,
    )
    assert names == []
    assert len(errors) == 1
    assert "door_unfold.dxf" in errors[0] and "層數／組數無效" in errors[0]
    assert called == []


def test_failed_engine_opening_is_not_substituted_with_no_opening(monkeypatch, tmp_path):
    host, called = _host(box=True)
    monkeypatch.setattr(manufacturing_api, "indicator_box_opening_size",
                        lambda *a, **kw: (_ for _ in ()).throw(ValueError("opening rejected")))
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags("door"), False,
    )
    assert names == [] and "opening rejected" in errors[0]
    assert called == []


def test_valid_export_uses_exact_preview_normalized_groups(monkeypatch, tmp_path):
    host, called = _host(box=True, door=True, box_groups=("02",),
                         door_layers="2", door_groups=("3", "2"))
    opening_calls = []
    def opening(groups, *, thickness):
        opening_calls.append((groups, thickness))
        return (81.0, 42.0)
    monkeypatch.setattr(manufacturing_api, "indicator_box_opening_size", opening)
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags("door"), False,
    )
    assert names == ["door_unfold.dxf"] and errors == []
    assert opening_calls == [((2,), 2.0)]
    assert called == [
        ("door_spec", {"indicator_hole": (81.0, 42.0),
                       "door_indicator": (3, 2)}),
        ("export", "door-spec"),
    ]


def test_disabled_invalid_controls_do_not_affect_plain_door(tmp_path):
    host, called = _host(box_layers="bad", door_layers="bad")
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags("door"), False,
    )
    assert names == ["door_unfold.dxf"] and errors == []
    assert called[0] == ("door_spec", {
        "indicator_hole": None, "door_indicator": None,
    })


@pytest.mark.parametrize("selected", ["indicator_box", "indicator_door"])
def test_independent_indicator_dxf_refuses_invalid_groups(tmp_path, selected):
    host, called = _host(box_layers="1", box_groups=("0",))
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags(selected), False,
    )
    assert names == [] and len(errors) == 1
    assert selected + ".dxf" in errors[0]
    assert "層數／組數無效" in errors[0]
    assert called == []


def test_other_selected_part_keeps_own_error_boundary(tmp_path):
    host, called = _host(door=True, door_groups=("bad",))
    names, errors = export._export_selected_parts(
        host, str(tmp_path), {"t": 2.0}, _flags("door", "base_plate"), False,
    )
    assert names == ["base_plate.dxf"]
    assert len(errors) == 1 and "door_unfold.dxf" in errors[0]
    assert called == [("export", "base-spec")]
