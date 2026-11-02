"""#2517 Live 2D Indicator sources must match Engine snapshot group semantics."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import render_snapshots as live


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def make_host(count="1", groups=("2",)):
    calls = []
    host = SimpleNamespace(
        indicator_l_var=Var(count),
        indicator_layer_g_vars=tuple(Var(v) for v in groups),
        is_indicator_box_var=Var(True),
        is_door_indicator_var=Var(False),
        door_indicator_l_var=Var("1"),
        door_indicator_layer_g_vars=(Var("3"),),
        surface_features={"indicator_box": [], "indicator_door": []},
    )
    def box_spec(val, source, **kwargs):
        calls.append(("box", source))
        return "box-spec"
    def small_door_spec(val, source, **kwargs):
        calls.append(("small-door", source))
        return ("small-door-spec", "context")
    host._indicator_box_part_spec = box_spec
    host._indicator_door_part_spec_from_values = small_door_spec
    host._manufacturing_context = lambda **kwargs: "context"
    host._authoritative_render_data = lambda spec, ctx: SimpleNamespace(
        material=SimpleNamespace(bounds=(0., 0., 150., 80.))
    )
    return host, calls


@pytest.mark.parametrize("count,groups", [
    ("0", ("2",)), ("-1", ("2",)), ("2.5", ("2",)),
    (True, ("2",)), ("not-a-number", ("2",)), ("2", ("3",)),
    ("1", (True,)), ("1", (0,)), ("1", ("-2",)),
    ("1", (2.5,)), ("1", ("2.5",)), ("1", ("invalid",)),
])
@pytest.mark.parametrize("preview", ("box", "small-door"))
def test_invalid_indicator_source_never_reaches_geometry_spec(count, groups, preview):
    host, called = make_host(count, groups)
    fn = live.indicator_box_render_snapshot if preview == "box" else live.indicator_door_render_snapshot
    with pytest.raises(ValueError, match="層數／組數無效"):
        fn(host, {"w": 450., "h": 550., "t": 2.})
    assert called == []


def test_valid_live_box_and_small_door_use_exact_engine_groups(monkeypatch):
    monkeypatch.setattr(api, "door_finished_face_size", lambda *a: (101., 55.))
    host, called = make_host("2", ("3", "2"))
    box = live.indicator_box_render_snapshot(host, {"t": 2.})
    door = live.indicator_door_render_snapshot(host, {"t": 2.})
    assert box["layer_groups"] == api.normalize_fold_designer_indicator_groups(("3", "2"))
    assert door["finished_size"] == (101., 55.)
    assert called == [("box", (3, 2)), ("small-door", (3, 2))]


@pytest.mark.parametrize("source", ("box", "door"))
@pytest.mark.parametrize("count,groups", [
    ("0", ("2",)), (True, ("2",)), ("1", (True,)),
    ("1", ("2.5",)), ("2", ("2",)), ("1", ("-1",)),
])
def test_invalid_main_door_indicator_fails_before_spec(source, count, groups):
    host, called = make_host()
    host.w_var = Var("500")
    host.h_var = Var("800")
    host.t_var = Var("2")
    host.fw_z_var = Var("25")
    for key in ("door_gap_w", "door_gap_h"):
        setattr(host, key + "_var", Var("3.5"))
    for key in ("door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b"):
        setattr(host, key + "_var", Var("15"))
    host._single_door_part_spec = lambda *a, **kw: called.append(("main", kw))
    host.door_indicator_offset_x = 0.
    host.door_indicator_offset_y = 0.
    if source == "box":
        host.indicator_l_var = Var(count)
        host.indicator_layer_g_vars = tuple(Var(v) for v in groups)
    else:
        host.is_indicator_box_var = Var(False)
        host.is_door_indicator_var = Var(True)
        host.door_indicator_l_var = Var(count)
        host.door_indicator_layer_g_vars = tuple(Var(v) for v in groups)
    with pytest.raises(ValueError, match="層數／組數無效"):
        live.single_door_render_snapshot(host)
    assert called == []


def test_live_previews_have_no_local_group_number_manufacturing_parser():
    source = Path("gui_modules/application/render_snapshots.py").read_text(encoding="utf-8")
    assert "manufacturing_api.normalize_fold_designer_indicator_groups(" in source
    assert "max(1, int(host.indicator_l_var.get()))" not in source
    assert "max(1, int(host.door_indicator_l_var.get()))" not in source
    assert "int(host.indicator_layer_g_vars[i].get())" not in source
    assert "int(host.door_indicator_layer_g_vars[i].get())" not in source
