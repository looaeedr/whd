"""#2517 selected DXF mode, Indicator holes and STOCK use raw public Engine gates."""
from __future__ import annotations

from types import SimpleNamespace
import inspect
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui


class Var:
    def __init__(self, raw):
        self.raw = raw
    def get(self):
        return self.raw


def flags(**updates):
    selection = dict(box_body=False, head=False, tail=False, door=True,
                     base_plate=False, indicator_box=False, indicator_door=False)
    selection.update(updates)
    return selection


def host(*, multi="false", box="false", door="false"):
    recorded = []
    instance = SimpleNamespace(
        multi_door_enabled_var=Var(multi),
        is_indicator_box_var=Var(box), is_door_indicator_var=Var(door),
        indicator_l_var=Var("1"), indicator_layer_g_vars=[Var("2")] * 6,
        door_indicator_l_var=Var("1"), door_indicator_layer_g_vars=[Var("3")] * 6,
        _manufacturing_context=lambda **kw: kw,
        _single_door_part_spec=lambda val, **kw: (val, kw),
        _export_authoritative_part=lambda spec, filename, context:
            recorded.append((spec, filename, context)),
        export_multi_door_layout_dxfs=lambda folder, val, *, draw_stock:
            [f"multi-{draw_stock}.dxf"],
    )
    return instance, recorded


@pytest.mark.parametrize("mode,expected", [
    ("false", "door_unfold.dxf"), ("0", "door_unfold.dxf"),
    (0, "door_unfold.dxf"), ("true", "multi-False.dxf"),
    (1, "multi-False.dxf"),
])
def test_legacy_dxf_physical_mode_matches_engine(monkeypatch, mode, expected):
    monkeypatch.setattr(gui, "_export_selected_resolved_parts", lambda *_: None)
    instance, calls = host(multi=mode)
    files, errors = gui._export_selected_parts(
        instance, "/unused-stage", {"t": 2}, flags(), False,
    )
    assert not errors and files == [expected]
    assert bool(calls) == (expected == "door_unfold.dxf")
    assert api.normalize_operator_settings_boolean(mode) is (expected == "multi-False.dxf")


@pytest.mark.parametrize("box,door,expected", [
    ("false", "false", "none"),
    ("false", "true", "indicator"),
    ("true", "false", "indicator_box"),
    ("true", "invalid-hidden", "indicator_box"),
])
def test_legacy_dxf_indicator_holes_match_engine_mode(
    monkeypatch, box, door, expected,
):
    monkeypatch.setattr(gui, "_export_selected_resolved_parts", lambda *_: None)
    monkeypatch.setattr(api, "indicator_box_opening_size", lambda groups, *, thickness:
                        ("engine-opening", tuple(groups), thickness))
    instance, calls = host(box=box, door=door)
    files, errors = gui._export_selected_parts(
        instance, "/unused", {"t": 2}, flags(), False,
    )
    assert files == ["door_unfold.dxf"] and errors == []
    (_values, kwargs), _filename, _context = calls[0]
    assert kwargs["indicator_hole"] == (
        ("engine-opening", (2,), 2) if expected == "indicator_box" else None
    )
    assert kwargs["door_indicator"] == ((3,) if expected == "indicator" else None)


@pytest.mark.parametrize("source", [
    dict(multi="false-ish"), dict(box="bad"), dict(door="bad"),
])
def test_invalid_active_flag_cannot_reach_legacy_manufacturing(monkeypatch, source):
    monkeypatch.setattr(gui, "_export_selected_resolved_parts", lambda *_: None)
    instance, calls = host(**source)
    files, errors = gui._export_selected_parts(
        instance, "/unused", {"t": 2}, flags(), False,
    )
    assert files == [] and errors and calls == []


@pytest.mark.parametrize("mode,multi", [
    ("false", False), ("0", False), ("true", True), (1, True),
])
def test_preflight_uses_engine_mode_not_tk_truthiness(mode, multi):
    events = []
    instance = SimpleNamespace(
        multi_door_enabled_var=Var(mode),
        _validate_single_door_indicator_fit=lambda val: events.append("single"),
        get_door_layout_cells=lambda: events.append("multi") or (),
    )
    gui._validate_selected_indicator_exports(instance, flags(), {"t": 2})
    assert events == (["multi"] if multi else ["single"])


def batch_host(stock):
    return SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _phase6_current_existing_parts=lambda: {"box_body"},
        _has_any_indicator_box=lambda: False,
        get_float_values=lambda: {"t": 2},
        draw_stock_var=Var(stock),
    )


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("0", False), (0, False),
    ("true", True), ("1", True), (1, True),
])
def test_staging_receives_engine_stock_decision(monkeypatch, tmp_path, raw, expected):
    monkeypatch.setattr(gui, "_selected_export_flags", lambda *_: flags(door=False, box_body=True))
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_: str(tmp_path))
    seen = []
    class StagingReached(Exception):
        pass
    def probe(_ui, _folder, _values, _selected, stock):
        seen.append(stock)
        raise StagingReached
    monkeypatch.setattr(gui, "_export_selected_parts", probe)
    with pytest.raises(StagingReached):
        gui.export_selected_dxf(batch_host(raw))
    assert seen == [expected]


@pytest.mark.parametrize("raw", [None, "bad", "2", 2, 0.5, [], {}])
def test_bad_stock_rejected_before_dxf_or_directory(monkeypatch, raw):
    monkeypatch.setattr(gui, "_selected_export_flags", lambda *_: flags(door=False, box_body=True))
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, msg: errors.append((title, msg)))
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_: pytest.fail("must not select output directory"))
    monkeypatch.setattr(gui, "_export_selected_parts", lambda *_: pytest.fail("must not manufacture"))
    gui.export_selected_dxf(batch_host(raw))
    assert len(errors) == 1 and "STOCK" in errors[0][0]


def test_corrupt_indicator_presence_reports_error_instead_of_tk_exception(monkeypatch):
    instance = batch_host(False)
    def invalid():
        raise ValueError("BAD_SOURCE")
    instance._has_any_indicator_box = invalid
    notices = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, msg: notices.append((title, msg)))
    gui.export_selected_dxf(instance)
    assert notices == [("出圖來源無法套用", "BAD_SOURCE")]


def test_export_no_longer_uses_gui_boolean_coercion_for_physical_requests():
    source = inspect.getsource(gui._export_selected_parts)
    selected = inspect.getsource(gui.export_selected_dxf)
    assert "normalize_operator_settings_boolean(" in source
    assert "if self.multi_door_enabled_var.get():" not in source
    assert "if self.is_indicator_box_var.get():" not in source
    assert "bool(self.draw_stock_var.get())" not in selected
    assert "normalize_operator_settings_boolean(" in selected
