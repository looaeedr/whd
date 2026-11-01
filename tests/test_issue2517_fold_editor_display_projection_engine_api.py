"""#2517 Fold Editor display projection must not temporarily mutate real material."""
from copy import deepcopy
import inspect
from types import MappingProxyType, SimpleNamespace

import pytest

import fold_designer_original as original
import phase6_bending_ui as gui
from ae_engine import manufacturing_api
from ae_engine import project_operator_fold_editor_display_rows as root_project


def _material_rows():
    return [
        {"len": 15, "angle": 90, "ui_len_add": 999, "phase6_key": "zl1"},
        {"len": 100, "angle": -90, "core": "D", "phase6_key": "d_left"},
        {"len": 15, "phase6_ui_sign": -1.0, "phase6_key": "custom"},
    ]


def test_headless_display_uses_actual_bends_and_detached_readonly_rows():
    material = _material_rows()
    prior = deepcopy(material)
    view = manufacturing_api.project_operator_fold_editor_display_rows(material, 2)
    assert root_project is manufacturing_api.project_operator_fold_editor_display_rows
    assert isinstance(view, tuple) and all(isinstance(row, MappingProxyType) for row in view)
    assert [row["len"] for row in view] == [17, 104, -17]
    assert [row.get("angle") for row in view] == [-90, 90, None]
    assert [row.get("phase6_key") for row in view] == ["zl1", "d_left", "custom"]
    assert material == prior
    with pytest.raises(TypeError):
        view[0]["len"] = 99


def test_display_preserves_negative_operator_sign_even_when_bends_are_removed():
    rows = [{"len": 24, "phase6_ui_sign": -1.0}]
    assert project_len(rows) == -24
    assert rows == [{"len": 24, "phase6_ui_sign": -1.0}]


def project_len(rows):
    return manufacturing_api.project_operator_fold_editor_display_rows(rows, 2)[0]["len"]


class _Panel:
    def grid_slaves(self, **_kw):
        return []


def _host(material):
    host = object.__new__(gui.Phase6BendingUI)
    host.state = SimpleNamespace(
        phase6_fold_ui_profiles={"X": material},
        active_bend="X",
        phase6_thickness=2.0,
    )
    host.container = _Panel()
    return host


def test_renderer_only_observes_view_not_canonical_material(monkeypatch):
    material = _material_rows()
    prior = deepcopy(material)
    host = _host(material)
    seen = []
    def fake_renderer(self):
        view = self.get_active_dict()["X"]
        seen.append(tuple(row["len"] for row in view))
        assert view is not material
        assert material == prior  # immutable even *during* Tk render
        self.controls = []
    monkeypatch.setattr(original.BendingUI, "render", fake_renderer)
    monkeypatch.setattr(original.ttk, "Label", lambda *_a, **_k: SimpleNamespace(grid=lambda **_kw: None))
    host.render()
    assert seen == [(17, 104, -17)]
    assert material == prior
    assert host.get_active_dict()["X"] is material


def test_render_exception_does_not_leak_operator_view(monkeypatch):
    material = _material_rows()
    prior = deepcopy(material)
    host = _host(material)
    def exploded(_self):
        raise RuntimeError("injected Tk failure")
    monkeypatch.setattr(original.BendingUI, "render", exploded)
    with pytest.raises(RuntimeError, match="injected Tk failure"):
        host.render()
    assert material == prior
    assert host.get_active_dict()["X"] is material


def test_refresh_uses_same_engine_display_rows_and_never_mutates_material():
    class Var:
        def __init__(self, text):
            self.text = text
        def get(self):
            return self.text
        def set(self, value):
            self.text = value
    material = _material_rows()
    prior = deepcopy(material)
    host = _host(material)
    host.controls = [
        {"angle": Var("90"), "len": Var("0")},
        {"angle": Var("-90"), "len": Var("0")},
        {"len": Var("0")},
    ]
    assert host.refresh_active_profile() is True
    assert tuple(ctrl["len"].get() for ctrl in host.controls) == ("17", "104", "-17")
    assert tuple(host.controls[i]["angle"].get() for i in (0,1)) == ("-90", "90")
    assert material == prior


def test_gui_render_refresh_no_longer_recompute_or_mutate_material_rows():
    for method in (gui.Phase6BendingUI.render, gui.Phase6BendingUI.refresh_active_profile):
        src = inspect.getsource(method)
        assert "manufacturing_api.project_operator_fold_editor_display_rows(" in src
        assert "apply_outside_dimension_compensation(" not in src
        assert 'seg["len"] =' not in src
        assert 'seg["angle"] =' not in src
