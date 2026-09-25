from __future__ import annotations

from types import SimpleNamespace

import gui
from ae_engine.sheetmetal_geometry import Vec2


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_task5_door_layout_hit_test_uses_visible_cell_bounds():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.door_layout_cell_bounds = {
        "0:0": (10.0, 20.0, 110.0, 120.0),
        "1:2": (120.0, 20.0, 220.0, 120.0),
    }

    assert host._door_layout_cell_at_canvas_point(10.0, 20.0) == (0, 0)
    assert host._door_layout_cell_at_canvas_point(200.0, 100.0) == (1, 2)
    assert host._door_layout_cell_at_canvas_point(500.0, 500.0) is None


def test_task5_multidoor_press_selects_then_manual_double_click_opens_editor():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.multi_door_enabled_var = Var(True)
    host.door_layout_cell_bounds = {"1:2": (10.0, 20.0, 110.0, 120.0)}
    host._door_layout_last_click = None
    events = []
    host.select_door_layout_cell = lambda c, r: events.append(("select", c, r))
    host.open_door_layout_cell_editor = lambda c, r: events.append(("open", c, r))

    first = SimpleNamespace(x=50.0, y=60.0, time=1000)
    second = SimpleNamespace(x=50.0, y=60.0, time=1500)

    assert host.on_door_canvas_press(first) == "break"
    assert events == [("select", 1, 2)]
    assert host._door_layout_last_click == ((1, 2), 1000)

    assert host.on_door_canvas_press(second) == "break"
    assert events == [("select", 1, 2), ("open", 1, 2)]
    assert host._door_layout_last_click is None


def test_task5_multidoor_press_miss_clears_pending_click():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.multi_door_enabled_var = Var(True)
    host.door_layout_cell_bounds = {"0:0": (0.0, 0.0, 10.0, 10.0)}
    host._door_layout_last_click = ((0, 0), 100)
    host.select_door_layout_cell = lambda *_args: (_ for _ in ()).throw(
        AssertionError("miss must not select")
    )
    host.open_door_layout_cell_editor = lambda *_args: (_ for _ in ()).throw(
        AssertionError("miss must not open")
    )

    assert host.on_door_canvas_press(SimpleNamespace(x=50.0, y=50.0, time=500)) == "break"
    assert host._door_layout_last_click is None


def test_task5_single_door_press_starts_indicator_drag_only_on_hit():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.multi_door_enabled_var = Var(False)
    host.is_door_indicator_var = Var(True)
    host.door_indicator_offset_x = 7.0
    host.door_indicator_offset_y = -3.0
    host.drag_active = False

    class Transform:
        def canvas_to_world(self, x, y):
            return Vec2(float(x) / 10.0, float(y) / 10.0)

    class Layout:
        def __init__(self):
            self.seen = []

        def hit_test(self, world, padding):
            self.seen.append((world, padding))
            return True

    layout = Layout()
    host.last_door_draw_params = {
        "transform": Transform(),
        "indicator_layout": layout,
    }

    result = host.on_door_canvas_press(SimpleNamespace(x=30.0, y=40.0))

    assert result is None
    assert layout.seen == [(Vec2(3.0, 4.0), 15.0)]
    assert host.drag_active is True
    assert host.drag_start_world == Vec2(3.0, 4.0)
    assert host.drag_start_offset_x == 7.0
    assert host.drag_start_offset_y == -3.0


def test_task5_drag_clamps_offsets_and_redraws_preview():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.drag_active = True
    host.drag_start_world = Vec2(1.0, 2.0)
    host.drag_start_offset_x = 5.0
    host.drag_start_offset_y = 6.0
    host.door_indicator_offset_x = 5.0
    host.door_indicator_offset_y = 6.0
    events = []
    host.draw_preview = lambda: events.append("draw")

    class Transform:
        def canvas_to_world(self, x, y):
            return Vec2(float(x), float(y))

    class Layout:
        def clamp_offset(self, desired):
            events.append(("clamp", desired))
            return Vec2(8.0, 9.0)

    host.last_door_draw_params = {
        "transform": Transform(),
        "indicator_layout": Layout(),
    }

    host.on_door_canvas_drag(SimpleNamespace(x=4.0, y=7.0))

    assert events == [("clamp", Vec2(8.0, 11.0)), "draw"]
    assert host.door_indicator_offset_x == 8.0
    assert host.door_indicator_offset_y == 9.0


def test_task5_release_and_double_click_routing_are_stable():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    host.drag_active = True

    host.on_door_canvas_release(SimpleNamespace())
    assert host.drag_active is False

    events = []
    host.multi_door_enabled_var = Var(True)
    host.door_layout_cell_bounds = {"2:1": (0.0, 0.0, 100.0, 100.0)}
    host.open_door_layout_cell_editor = lambda c, r: events.append(("cell", c, r))
    host.open_part_hole_editor = lambda part: events.append(("part", part))

    assert host.on_door_canvas_double_click(
        SimpleNamespace(x=50.0, y=50.0)
    ) == "break"
    assert events == [("cell", 2, 1)]

    host.multi_door_enabled_var = Var(False)
    assert host.on_door_canvas_double_click(
        SimpleNamespace(x=50.0, y=50.0)
    ) == "break"
    assert events == [("cell", 2, 1), ("part", "door")]
