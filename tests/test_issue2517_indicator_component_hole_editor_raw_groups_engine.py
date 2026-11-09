"""#2517 standalone Box/SmallDoor Hole Editors share raw Engine indicator groups."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import indicator_editor_geometry as engine
from gui_modules.editors import hole_editor as gui


class Var:
    def __init__(self, raw):
        self.raw = raw
    def get(self):
        return self.raw


def host(layers, groups):
    return SimpleNamespace(
        indicator_l_var=Var(layers),
        indicator_layer_g_vars=[Var(v) for v in groups],
    )


def values():
    return {"t": 2.0, "fw": 25.0, "door_gap_w": 3.5, "door_gap_h": 3.5}


@pytest.mark.parametrize("layers,groups", [
    (True, ["3"]), (False, ["3"]), (1.5, ["3"]),
    ("0", ["3"]), ("2.5", ["3", "2"]), ("bad", ["3"]),
    ("2", ["3"]), ("1", [True]), ("1", [False]),
    ("1", [3.5]), ("1", ["3.5"]), ("1", ["0"]),
    ("1", [float("nan")]), ("1", ["inf"]), ("1", ["bad"]),
    (7, ["2"] * 6), (None, ["2"]),
])
@pytest.mark.parametrize("component", ["box", "door"])
def test_bad_operator_groups_never_reach_any_component_geometry(
    monkeypatch, layers, groups, component,
):
    observed = []
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *args: observed.append(args))
    def forbidden(*args, **kwargs):
        pytest.fail("invalid raw group must not reach manufacturing geometry")
    monkeypatch.setattr(api, "resolve_indicator_box_editor_geometry", forbidden)
    monkeypatch.setattr(api, "indicator_small_door_operator_spec", forbidden)
    monkeypatch.setattr(api, "resolve_indicator_door_editor_geometry", forbidden)
    ui = host(layers, groups)
    before = repr((layers, groups))
    result = (gui._indicator_box_context(ui, values())
              if component == "box" else gui._indicator_door_context(ui, values()))
    assert result is None
    assert observed and observed[-1][0] == "輸入錯誤"
    assert repr((layers, groups)) == before


@pytest.mark.parametrize("raw", [
    (True,), (2.5,), ("2.5",), (0,), (-1,), (float("nan"),),
    ("inf",), (), ("bad",),
])
@pytest.mark.parametrize("component", ["box", "door"])
def test_headless_component_api_also_rejects_lossy_groups(raw, component):
    with pytest.raises(ValueError):
        if component == "box":
            api.resolve_indicator_box_editor_geometry(raw, thickness=2.0)
        else:
            # The raw group gate executes before consulting DoorPartSpec.
            api.resolve_indicator_door_editor_geometry(
                raw, thickness=2.0, door_spec=None,
            )


@pytest.mark.parametrize("layers,groups,expected", [
    ("1", ["03"], (3,)),
    ("2", ["03", "2", "bad hidden"], (3, 2)),
    (2.0, [3.0, "2"], (3, 2)),
])
def test_gui_sources_match_existing_headless_normalizer(
    layers, groups, expected,
):
    ui = host(layers, groups)
    before = repr((layers, groups))
    accepted = gui._indicator_groups(ui)
    assert tuple(accepted) == expected
    assert tuple(accepted) == api.normalize_fold_designer_indicator_groups(expected)
    assert repr((layers, groups)) == before


@pytest.mark.parametrize("component", ["box", "door"])
def test_real_component_geometry_is_equal_from_gui_and_headless_engine(component):
    source = json.loads(json.dumps({"layers": "2", "groups": ["3", "2", "hidden"]}))
    before = deepcopy(source)
    ui = host(source["layers"], source["groups"])
    if component == "box":
        projected = gui._indicator_box_context(ui, values())
        direct = api.resolve_indicator_box_editor_geometry((3, 2), thickness=2.0)
    else:
        projected = gui._indicator_door_context(ui, values())
        spec, _context = api.indicator_small_door_operator_spec(
            (3, 2), thickness=2.0, frame_width=25.0,
            door_gap_w=3.5, door_gap_h=3.5,
        )
        direct = api.resolve_indicator_door_editor_geometry(
            (3, 2), thickness=2.0, door_spec=spec,
        )
    assert projected is not None
    assert projected["width"] == pytest.approx(direct.width)
    assert projected["height"] == pytest.approx(direct.height)
    assert projected["baseline_status_text"] == direct.baseline_status
    assert source == before


def test_gui_and_engine_component_source_no_local_int_conversion():
    gui_src = inspect.getsource(gui._indicator_groups)
    engine_src = inspect.getsource(engine._normalize_editor_groups)
    assert "normalize_fold_designer_indicator_groups(" in gui_src
    assert "normalize_fold_designer_indicator_groups(" in engine_src
    assert "int(host.indicator_l_var.get())" not in gui_src
    assert "int(host.indicator_layer_g_vars" not in gui_src
    assert "tuple(int(value) for value in groups)" not in engine_src
