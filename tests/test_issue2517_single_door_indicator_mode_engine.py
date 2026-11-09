"""#2517: physical single Door indicator mode belongs to the public Engine."""
from __future__ import annotations

import inspect
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import door_operator_part_spec as owner
from gui_modules.application.render_snapshots import single_door_render_snapshot


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def _host(*, box="false", direct="false"):
    host = SimpleNamespace(
        w_var=Var("500.25"), h_var=Var("800.5"),
        t_var=Var("2.25"), fw_z_var=Var("25.75"),
        door_gap_w_var=Var("3.5"), door_gap_h_var=Var("3.5"),
        door_fold_l_var=Var("15"), door_fold_r_var=Var("15"),
        door_fold_t_var=Var("15"), door_fold_b_var=Var("15"),
        is_indicator_box_var=Var(box), is_door_indicator_var=Var(direct),
        indicator_l_var=Var("1"), indicator_layer_g_vars=[Var("2")],
        door_indicator_l_var=Var("1"), door_indicator_layer_g_vars=[Var("3")],
    )
    return host


@pytest.mark.parametrize(("box", "direct", "expected"), (
    (False, False, "none"),
    ("false", "false", "none"),
    (" TRUE ", "off", "indicator_box"),
    ("0", "yes", "indicator"),
    (1, 0, "indicator_box"),
    (0, 1, "indicator"),
))
def test_public_engine_mode_is_same_for_raw_and_json_reloaded_source(
    box, direct, expected,
):
    assert api.project_operator_single_door_indicator_mode is (
        owner.project_operator_single_door_indicator_mode
    )
    assert ae_engine.project_operator_single_door_indicator_mode is (
        api.project_operator_single_door_indicator_mode
    )
    source = {"box": box, "direct": direct}
    original = deepcopy(source)
    result = api.project_operator_single_door_indicator_mode(
        source["box"], source["direct"],
    )
    restored = json.loads(json.dumps(source))
    assert result == expected
    assert api.project_operator_single_door_indicator_mode(
        restored["box"], restored["direct"],
    ) == result
    assert source == original


@pytest.mark.parametrize(("box", "direct"), (
    ("true", "true"), (True, 1),
    ("invalid", "false"), ("false", "invalid"),
    (float("nan"), False), (False, float("inf")),
    (None, False), (False, []),
))
def test_invalid_or_contradictory_raw_flags_reject_without_manufacture(
    box, direct,
):
    with pytest.raises(ValueError):
        api.project_operator_single_door_indicator_mode(box, direct)
    host = _host(box=box, direct=direct)
    host._single_door_part_spec = lambda *a, **kw: pytest.fail(
        "must reject before PartSpec"
    )
    host._manufacturing_context = lambda **kw: pytest.fail(
        "must reject before rendering"
    )
    with pytest.raises(ValueError):
        single_door_render_snapshot(host)


@pytest.mark.parametrize(("box", "direct", "expected_box", "expected_direct"), (
    ("false", "false", None, None),
    ("false", "true", None, (3,)),
    ("true", "false", (77.25, 90.5), None),
))
def test_real_gui_selects_only_engine_mode_without_truthy_false(
    monkeypatch, box, direct, expected_box, expected_direct,
):
    seen = []
    opening_calls = []

    def opening(groups, *, thickness):
        opening_calls.append((groups, thickness))
        return (77.25, 90.5)

    monkeypatch.setattr(api, "indicator_box_opening_size", opening)
    host = _host(box=box, direct=direct)

    def witness(val, *, indicator_hole, door_indicator):
        seen.append((dict(val), indicator_hole, door_indicator))
        raise RuntimeError("PART_SPEC_WITNESS")

    host._single_door_part_spec = witness
    host._manufacturing_context = lambda **kw: pytest.fail(
        "preview must not render before part spec"
    )
    with pytest.raises(RuntimeError, match="PART_SPEC_WITNESS"):
        single_door_render_snapshot(host)
    assert len(seen) == 1
    assert seen[0][1] == expected_box
    assert seen[0][2] == expected_direct
    assert opening_calls == ([( (2,), 2.25)] if expected_box else [])
    assert seen[0][0]["door_fold_l"] == "15"


def test_gui_delegates_selection_and_engine_does_not_import_gui():
    gui_source = inspect.getsource(single_door_render_snapshot)
    assert "manufacturing_api.project_operator_single_door_indicator_mode(" in gui_source
    assert "if host.is_indicator_box_var.get()" not in gui_source
    assert "if host.is_door_indicator_var.get()" not in gui_source
    engine_source = inspect.getsource(owner.project_operator_single_door_indicator_mode)
    assert "normalize_operator_settings_boolean" in engine_source
    assert "gui_modules" not in inspect.getsource(owner)
    assert "import tkinter" not in inspect.getsource(owner)
