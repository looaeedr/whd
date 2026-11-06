# -*- coding: utf-8 -*-
"""#2517 Quantity allocation door sketches use the public Engine projection."""
import inspect
from types import SimpleNamespace
import pytest

from ae_engine import manufacturing_api
from gui_modules.application.receiving_quantity_allocation_ui import ReceivingQuantityAllocationUI


class _Canvas:
    def __init__(self):
        self.lines = []
    def delete(self, *_args):
        pass
    def winfo_width(self):
        return 600
    def winfo_height(self):
        return 290
    def cget(self, name):
        return {"width": "600", "height": "290"}[name]
    def configure(self, **_kwargs):
        pass
    def create_text(self, *_args, **_kwargs):
        pass
    def create_rectangle(self, *_args, **_kwargs):
        pass
    def create_line(self, *args, **_kwargs):
        self.lines.append(args)


def test_quantity_draft_uses_engine_seam_not_gui_1100_1600(monkeypatch):
    seen = []
    def project(bay):
        seen.append(bay)
        return .375
    monkeypatch.setattr(manufacturing_api, "project_receiving_operator_bay_door_split_ratio", project)
    ui = object.__new__(ReceivingQuantityAllocationUI)
    ui.canvas = _Canvas()
    ui.role = "head"
    ui.draft = SimpleNamespace(counts=(2,), assigned={"head": {}}, active_version={"head": None})
    ui.reconcile = lambda: None
    ui._draw_original_door_marks = lambda *_args: None

    ui.paint()

    assert seen == [None]
    assert len(ui.canvas.lines) == 2
    assert all(line[1] == pytest.approx(27 + 105 * .375) for line in ui.canvas.lines)
    assert len(ui._hitboxes) == 2
    assert "1100.0 / 1600.0" not in inspect.getsource(ReceivingQuantityAllocationUI.paint)


def test_draft_family_schematic_matches_canonical_engine_default():
    assert manufacturing_api.project_receiving_operator_bay_door_split_ratio(None) == pytest.approx(1100 / 1600)
