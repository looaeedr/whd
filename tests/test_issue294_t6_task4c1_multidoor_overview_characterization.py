from __future__ import annotations

from types import SimpleNamespace

import pytest

import gui
from gui_modules.rendering import door_view


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeEntry:
    instances = []

    def __init__(self, canvas, **kwargs):
        self.canvas = canvas
        self.kwargs = kwargs
        self.bindings = []
        type(self).instances.append(self)

    def bind(self, event, callback):
        self.bindings.append((event, callback))


class FakeCanvas:
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        self.calls = []

    def delete(self, *args):
        self.calls.append(("delete", args, {}))

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return len(self.calls)

    def create_rectangle(self, *args, **kwargs):
        return self._record("rectangle", *args, **kwargs)

    def create_window(self, *args, **kwargs):
        return self._record("window", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)


def test_task4c1_multidoor_overview_presentation_and_cell_payloads_are_stable(monkeypatch):
    FakeEntry.instances = []
    monkeypatch.setattr(gui.tk, "Entry", FakeEntry)
    monkeypatch.setattr(
        gui.ae,
        "baseline_source_label",
        lambda model, filename: f"BASELINE:{model}:{filename}",
    )

    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    cell = SimpleNamespace(column_index=0, row_index=0)
    result = SimpleNamespace(width=100.0, height=50.0)
    columns = [(100.0, (50.0,))]
    cells = [cell]
    val = {"t": 2.0}

    host.canvas_door = canvas
    host._sync_door_canvas_double_click_binding = lambda: events.append(("sync",))
    host._destroy_door_layout_entry_widgets = lambda: events.append(("destroy",))
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host.w_var = Var(100)
    host.h_var = Var(50)
    host.get_door_layout_columns = lambda: columns
    host.get_door_layout_cells = lambda: cells
    host.get_float_values = lambda: val
    host.door_layout_selected_var = Var("0:0")
    host.door_layout_columns = [{
        "width_var": Var(100),
        "width_auto": True,
        "height_vars": [Var(50)],
        "height_auto": [True],
    }]
    host.door_layout_width_entries = {}
    host.door_layout_height_entries = {}
    host.door_layout_entry_windows = []
    host.COLOR_INPUT_BG = "#111"
    host.COLOR_TEXT = "#eee"
    host.COLOR_ACCENT = "#0af"
    host.COLOR_TEXT_MUTED = "#777"
    host.commit_door_layout_width = lambda index: events.append(("commit-width", index))
    host.commit_door_layout_height = lambda c, r: events.append(("commit-height", c, r))
    host._door_layout_entry_menu = lambda entry, **kwargs: events.append(("menu", entry, kwargs))
    host._door_layout_cell_result = lambda actual_cell, actual_val: (
        events.append(("cell-result", actual_cell, actual_val)) or result
    )
    host._door_layout_baseline_scene = lambda actual_cell, actual_val: (
        events.append(("baseline-scene", actual_cell, actual_val))
        or ("BASE-SCENE", "BASE-STATUS")
    )
    host._door_layout_cell_resolved_features = lambda actual_cell, actual_result, key: (
        events.append(("resolved", actual_cell, actual_result, key)) or ("FEATURE",)
    )
    monkeypatch.setattr(
        door_view,
        "_draw_layout_baseline_secondary_impl",
        lambda *args: events.append(("draw-baseline",) + args),
    )
    monkeypatch.setattr(
        door_view,
        "_draw_layout_resolved_features_impl",
        lambda *args: events.append(("draw-resolved",) + args),
    )
    host._baseline_source_model = lambda: "MODEL"
    host._draw_door_layout_dividers_and_frames = lambda *args: events.append(("dividers",) + args)

    gui.Phase6ApplicationHost.draw_door_layout_overview(host)

    assert events[0] == ("sync",)
    assert events[1] == ("destroy",)
    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events

    assert len(FakeEntry.instances) == 2
    assert 0 in host.door_layout_width_entries
    assert (0, 0) in host.door_layout_height_entries
    assert len(host.door_layout_entry_windows) == 2
    assert len(host.door_layout_cell_items) == 1
    assert host.door_layout_cell_bounds["0:0"] == pytest.approx(
        (58.0, 112.5, 616.0, 391.5)
    )

    draw_baseline = next(item for item in events if item[0] == "draw-baseline")
    assert draw_baseline[1] is canvas
    assert draw_baseline[2] == "BASE-SCENE"
    assert draw_baseline[3:5] == (100.0, 50.0)
    assert draw_baseline[5] == pytest.approx((58.0, 112.5, 616.0, 391.5))
    assert draw_baseline[6] == "door_layout_baseline_0_0"

    draw_resolved = next(item for item in events if item[0] == "draw-resolved")
    assert draw_resolved[1] is canvas
    assert draw_resolved[2] == ("FEATURE",)
    assert draw_resolved[3:5] == (100.0, 50.0)
    assert draw_resolved[5] == pytest.approx((58.0, 112.5, 616.0, 391.5))
    assert draw_resolved[6] == "door_layout_feature_0_0"

    cell_rect = next(
        item for item in canvas.calls
        if item[0] == "rectangle" and "door_layout_cell" in item[2].get("tags", ())
    )
    assert cell_rect[1] == pytest.approx((58.0, 112.5, 616.0, 391.5))
    assert cell_rect[2]["outline"] == "#0af"
    assert cell_rect[2]["width"] == 3

    texts = [
        kwargs.get("text", "")
        for name, _args, kwargs in canvas.calls
        if name == "text"
    ]
    assert "BASELINE:MODEL:門.dxf" in texts
    assert any("各欄獨立分層" in text for text in texts)

    divider_event = next(item for item in events if item[0] == "dividers")
    assert divider_event[1] is canvas
    assert divider_event[2] == pytest.approx(5.58)
    assert divider_event[3] == pytest.approx(58.0)
    assert divider_event[4] == pytest.approx(112.5)
    assert divider_event[5] == columns
    assert divider_event[6] == cells
    assert divider_event[7] == val

    assert host.last_door_layout_overview["columns"] == columns
    assert host.last_door_layout_overview["cell_count"] == 1
    assert host.last_door_layout_overview["selected"] == "0:0"
    assert host.last_door_layout_overview["scale"] == pytest.approx(5.58)
    assert host.last_door_layout_overview["origin"] == pytest.approx((58.0, 112.5))
