"""#2517 Door preview must not silently turn invalid indicator sources into NONE."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application.render_snapshots import single_door_render_snapshot


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _host(*, box_enabled=False, box_count="1", box_groups=("2",),
          door_enabled=False, door_count="1", door_groups=("3",)):
    calls = []
    value = SimpleNamespace(
        w_var=Var("500"), h_var=Var("800"), t_var=Var("2"),
        fw_z_var=Var("25"), door_gap_w_var=Var("3.5"), door_gap_h_var=Var("3.5"),
        door_fold_l_var=Var("15"), door_fold_r_var=Var("15"),
        door_fold_t_var=Var("15"), door_fold_b_var=Var("15"),
        is_indicator_box_var=Var(box_enabled),
        indicator_l_var=Var(box_count),
        indicator_layer_g_vars=tuple(Var(x) for x in box_groups),
        is_door_indicator_var=Var(door_enabled),
        door_indicator_l_var=Var(door_count),
        door_indicator_layer_g_vars=tuple(Var(x) for x in door_groups),
        door_indicator_offset_x=0, door_indicator_offset_y=0,
    )
    def spec(values, *, indicator_hole, door_indicator):
        calls.append((indicator_hole, door_indicator))
        return SimpleNamespace(model_name="金庫型", frame_edges=None)
    value._single_door_part_spec = spec
    value._manufacturing_context = lambda *, draw_stock: "context"
    value._authoritative_render_data = lambda spec, ctx: SimpleNamespace(
        material=SimpleNamespace(bounds=(0., 0., 400., 700.))
    )
    return value, calls


@pytest.mark.parametrize("which", (
    "box_bad_groups", "box_missing_group", "box_zero_group", "box_negative_group",
    "door_bad_groups", "door_missing_group", "door_zero_group", "door_negative_group",
))
def test_invalid_enabled_indicator_never_builds_a_door_without_requested_holes(which):
    kwargs = {
        "box_bad_groups": dict(box_enabled=True, box_groups=("not-a-number",)),
        "box_missing_group": dict(box_enabled=True, box_count="2", box_groups=("2",)),
        "box_zero_group": dict(box_enabled=True, box_groups=("0",)),
        "box_negative_group": dict(box_enabled=True, box_groups=("-1",)),
        "door_bad_groups": dict(door_enabled=True, door_groups=("not-a-number",)),
        "door_missing_group": dict(door_enabled=True, door_count="2", door_groups=("3",)),
        "door_zero_group": dict(door_enabled=True, door_groups=("0",)),
        "door_negative_group": dict(door_enabled=True, door_groups=("-1",)),
    }
    host, calls = _host(**kwargs[which])
    with pytest.raises(ValueError, match="層數／組數(?:無效|必須大於 0)"):
        single_door_render_snapshot(host)
    assert not calls


def test_engine_rejected_box_opening_is_not_silently_dropped(monkeypatch):
    host, calls = _host(box_enabled=True)
    called = []
    def unavailable(groups, *, thickness):
        called.append((groups, thickness))
        raise ValueError("指示燈盒內部淨開口尺寸無效")
    monkeypatch.setattr(manufacturing_api, "indicator_box_opening_size", unavailable)
    with pytest.raises(ValueError, match="內部淨開口尺寸無效"):
        single_door_render_snapshot(host)
    assert called == [((2,), 2.0)]
    assert calls == []


def test_valid_enabled_box_and_direct_lamps_pass_exact_engine_result(monkeypatch):
    host, calls = _host(box_enabled=True, door_enabled=True, door_groups=("3", "2"),
                        door_count="2")
    opening_calls = []
    def opening(groups, *, thickness):
        opening_calls.append((groups, thickness))
        return (81., 42.)
    guide_calls = []
    def guides(finished, values, groups, spec, **kwargs):
        guide_calls.append((finished, groups, kwargs))
        return ("context", "layout", "x", "y")
    monkeypatch.setattr(manufacturing_api, "indicator_box_opening_size", opening)
    monkeypatch.setattr(manufacturing_api, "door_finished_face_size",
                        lambda spec, context: (350., 650.))
    monkeypatch.setattr(manufacturing_api, "project_operator_door_indicator_guides", guides)
    result = single_door_render_snapshot(host)
    assert opening_calls == [((2,), 2.0)]
    assert calls == [((81., 42.), (3, 2))]
    assert guide_calls == [((350., 650.), (3, 2), {"offset_x": 0, "offset_y": 0})]
    assert result["indicator_groups"] == (3, 2)
    assert result["indicator_layout"] == "layout"


def test_explicitly_disabled_indicator_stays_none_without_parsing_unused_controls(monkeypatch):
    host, calls = _host(box_count="invalid", door_count="invalid")
    monkeypatch.setattr(manufacturing_api, "door_finished_face_size",
                        lambda spec, context: (350., 650.))
    monkeypatch.setattr(manufacturing_api, "project_operator_door_indicator_guides",
                        lambda *args, **kwargs: (None, None, None, None))
    actual = single_door_render_snapshot(host)
    assert calls == [(None, None)]
    assert actual["indicator_groups"] == ()
