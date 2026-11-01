"""#2517: editing Fold rows goes through the Engine, not GUI topology math."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import operator_fold_editor_save_segments as package_fold_save
import phase6_bending_ui as gui


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_headless_fold_editor_save_uses_new_bend_topology_and_preserves_source(family):
    old = [
        {"len": 22, "angle": 90, "phase6_key": "zl1", "ui_len_add": 999},
        {"len": 100, "angle": -90, "phase6_key": "custom", "phase6_ui_sign": -1},
        {"len": 15, "phase6_key": "rear"},
    ]
    before = deepcopy(old)
    edited = (
        {"len": 30, "angle": 0},   # removed bend: no 1T for first row
        {"len": 105, "angle": 90}, # live BEND: 1T for second and third
        {"len": 17},
    )
    rows = manufacturing_api.operator_fold_editor_save_segments(old, edited, 2)
    assert rows == package_fold_save(old, edited, 2)
    assert old == before
    assert [x["len"] for x in rows] == [30, 103, 15]
    assert [x.get("angle") for x in rows] == [0, -90, None]
    assert [x.get("phase6_key") for x in rows] == ["zl1", "custom", "rear"]
    assert rows[1]["phase6_ui_sign"] == 1.0
    assert "ui_len_add" not in rows[0]
    assert rows[1]["ui_len_add"] == 2
    assert rows[2]["ui_len_add"] == 2


def test_negative_operator_length_keeps_positive_material_and_direction():
    rows = manufacturing_api.operator_fold_editor_save_segments(
        ({"len": 20, "phase6_key": "operator"},),
        ({"len": -24},),
        2,
    )
    assert rows == [{"len": 24, "phase6_ui_sign": -1.0, "phase6_key": "operator"}]


def test_gui_fold_editor_save_collects_controls_then_delegates_to_public_api(monkeypatch):
    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    active = {"X": [{"len": 14, "phase6_key": "fw_left"}]}
    sentinel = [{"len": 90, "phase6_key": "fw_left"}]
    calls = []

    def fake_api(old_segments, rows, thickness):
        calls.append((old_segments, rows, thickness))
        return sentinel

    monkeypatch.setattr(manufacturing_api, "operator_fold_editor_save_segments", fake_api)
    state = SimpleNamespace(
        phase6_thickness=2.0, phase6_fold_ui_vault_key="箱身", profiles_vault={},
    )
    host = SimpleNamespace(
        state=state,
        controls=[{"len": Var("27"), "angle": Var("90")}],
        get_active_dict=lambda: active,
        _active_profile_key=lambda _active: "X",
    )
    gui.Phase6BendingUI.save(host)
    assert calls == [([{"len": 14, "phase6_key": "fw_left"}],
                      ({"len": 27, "angle": 90},), 2.0)]
    assert active["X"] is sentinel
    assert state.profiles_vault["箱身"] is sentinel


def test_fold_editor_save_no_longer_builds_material_topology_in_gui():
    source = Path(gui.__file__).read_text(encoding="utf-8")
    saved = source.split("    def save(self):", 1)[1].split("    def add(self, pos):", 1)[0]
    assert "manufacturing_api.operator_fold_editor_save_segments(" in saved
    assert "ui_segment_length_to_engine" not in saved
    assert "apply_outside_dimension_compensation" not in saved
    engine = Path(manufacturing_api.operator_fold_editor_save_segments.__code__.co_filename)
    assert "ae_engine" in engine.parts
    engine_source = engine.read_text(encoding="utf-8")
    assert "phase6_" not in engine_source.splitlines()[0] # no GUI reverse import
    assert "from phase6_" not in engine_source
    assert "import tkinter" not in engine_source
