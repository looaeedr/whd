from __future__ import annotations

from types import SimpleNamespace

import gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


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

    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)

    def create_rectangle(self, *args, **kwargs):
        return self._record("rectangle", *args, **kwargs)

    def create_line(self, *args, **kwargs):
        return self._record("line", *args, **kwargs)


class FakeTransform:
    scale = 2.0

    def world_to_canvas(self, point):
        return float(point.x) * 2.0 + 10.0, float(point.y) * 2.0 + 20.0


def test_task4b_multi_door_route_stays_outside_single_door_preview():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    events = []
    host.multi_door_enabled_var = Var(True)
    host.draw_door_layout_overview = lambda: events.append("overview")

    gui.Phase6ApplicationHost.draw_door(host, {})

    assert events == ["overview"]


def test_task4b_single_door_consumes_authoritative_render_data_and_preserves_preview(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    context_calls = []
    spec = SimpleNamespace(
        model_name="門.dxf",
        frame_edges="FRAME-EDGES",
        use_box_distance=False,
    )
    render_data = SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 120.0, 80.0)),
        scene=object(),
    )

    host.multi_door_enabled_var = Var(False)
    host.canvas_door = canvas
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host.w_var = Var(100)
    host.h_var = Var(60)
    host.t_var = Var(2)
    host.fw_z_var = Var(62)
    host.door_gap_w_var = Var(3)
    host.door_gap_h_var = Var(4)
    host.door_fold_l_var = Var(29)
    host.door_fold_r_var = Var(29)
    host.door_fold_t_var = Var(29)
    host.door_fold_b_var = Var(29)
    host.is_indicator_box_var = Var(False)
    host.is_door_indicator_var = Var(False)
    host.draw_stock_var = Var(False)
    host.COLOR_TEXT_MUTED = "#777"
    host.door_indicator_offset_x = 0.0
    host.door_indicator_offset_y = 0.0

    def single_spec(door_val, *, indicator_hole=None, door_indicator=None):
        events.append(("spec", dict(door_val), indicator_hole, door_indicator))
        return spec

    def context(*, draw_stock):
        token = object()
        context_calls.append((draw_stock, token))
        return token

    host._single_door_part_spec = single_spec
    host._manufacturing_context = context
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render_data", actual_spec, actual_context)) or render_data
    )
    host._draw_phase6_finished_dimension_summary = (
        lambda target, *, part_key: events.append(("finished", target, part_key))
    )

    transform = FakeTransform()
    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda bounds, cw, ch: (
            events.append(("viewport", bounds, cw, ch))
            or (transform, 10.0, 180.0, 2.0, 20.0)
        ),
    )
    monkeypatch.setattr(
        gui,
        "render_drawing_scene",
        lambda target, scene, actual_transform, *, skip_layers: events.append(
            ("scene", target, scene, actual_transform, skip_layers)
        ),
    )
    monkeypatch.setattr(
        gui.manufacturing_api,
        "door_finished_face_size",
        lambda actual_spec, actual_context: (
            events.append(("finished_size", actual_spec, actual_context))
            or (90.0, 40.0)
        ),
    )
    monkeypatch.setattr(
        gui,
        "_draw_phase6_annotation_projection",
        lambda target, data, actual_transform, *, part_key: events.append(
            ("annotation", target, data, actual_transform, part_key)
        ),
    )
    monkeypatch.setattr(
        gui,
        "draw_hole_editor_hint",
        lambda target, cw, *, endcap: events.append(("hint", target, cw, endcap)),
    )

    gui.Phase6ApplicationHost.draw_door(host, {})

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    spec_event = next(item for item in events if item[0] == "spec")
    assert spec_event[1] == {
        "w": 100.0,
        "h": 60.0,
        "t": 2.0,
        "fw": 62.0,
        "door_gap_w": 3.0,
        "door_gap_h": 4.0,
        "door_fold_l": 29.0,
        "door_fold_r": 29.0,
        "door_fold_t": 29.0,
        "door_fold_b": 29.0,
    }
    assert spec_event[2:] == (None, None)
    assert len(context_calls) == 2
    assert ("viewport", (0.0, 0.0, 120.0, 80.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "door") in events
    assert ("finished", canvas, "door") in events
    assert ("hint", canvas, 640, False) in events

    texts = [
        kwargs.get("text", "")
        for name, _args, kwargs in canvas.calls
        if name == "text"
    ]
    assert any("門板展開預覽 (門.dxf 最終製造幾何)" in text for text in texts)
    assert any("成品寬 = 90.00 mm / 成品高 = 40.00 mm" in text for text in texts)

    params = host.last_door_draw_params
    assert params["transform"] is transform
    assert params["blank_w"] == 120.0
    assert params["blank_h"] == 80.0
    assert params["indicator_context"] is None
    assert params["indicator_groups"] == ()
    assert params["indicator_layout"] is None
    assert params["frame_edges"] == "FRAME-EDGES"
    assert params["layout_cell"] is None
    assert params["render_data"] is render_data


def test_task4b_base_plate_consumes_authoritative_render_data_and_keeps_box_overlay(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    context = object()
    spec = object()
    render_data = SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 80.0, 40.0)),
        scene=object(),
    )

    host.canvas_base_plate = canvas
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host.base_plate_shrink_top_var = Var(10)
    host.base_plate_shrink_bottom_var = Var(10)
    host.base_plate_shrink_left_var = Var(10)
    host.base_plate_shrink_right_var = Var(10)
    host.base_plate_bend_var = Var(5)
    host.draw_stock_var = Var(False)
    host.COLOR_TEXT = "#eee"

    def base_spec(values):
        events.append(("spec", dict(values)))
        return spec

    host._base_plate_part_spec = base_spec
    host._manufacturing_context = lambda *, draw_stock: (
        events.append(("context", draw_stock)) or context
    )
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render_data", actual_spec, actual_context)) or render_data
    )
    host._draw_phase6_finished_dimension_summary = (
        lambda target, *, part_key: events.append(("finished", target, part_key))
    )

    transform = FakeTransform()
    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda bounds, cw, ch: (
            events.append(("viewport", bounds, cw, ch))
            or (transform, 10.0, 140.0, 2.0, 20.0)
        ),
    )
    monkeypatch.setattr(
        gui,
        "render_drawing_scene",
        lambda target, scene, actual_transform, *, skip_layers: events.append(
            ("scene", target, scene, actual_transform, skip_layers)
        ),
    )
    monkeypatch.setattr(
        gui,
        "_draw_phase6_annotation_projection",
        lambda target, data, actual_transform, *, part_key: events.append(
            ("annotation", target, data, actual_transform, part_key)
        ),
    )
    monkeypatch.setattr(
        gui,
        "draw_hole_editor_hint",
        lambda target, cw, *, endcap: events.append(("hint", target, cw, endcap)),
    )

    gui.Phase6ApplicationHost.draw_base_plate(host, {"w": 100.0, "h": 60.0})

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    spec_values = next(item[1] for item in events if item[0] == "spec")
    assert spec_values["base_plate_shrink_top"] == 10.0
    assert spec_values["base_plate_shrink_bottom"] == 10.0
    assert spec_values["base_plate_shrink_left"] == 10.0
    assert spec_values["base_plate_shrink_right"] == 10.0
    assert spec_values["base_plate_bend"] == 5.0
    assert ("context", False) in events
    assert ("render_data", spec, context) in events
    assert ("viewport", (-5.0, -5.0, 95.0, 55.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "base_plate") in events
    assert ("finished", canvas, "base_plate") in events
    assert ("hint", canvas, 640, False) in events

    overlay_rects = [
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "rectangle" and kwargs.get("outline") == "#ff453a"
    ]
    assert len(overlay_rects) == 1
    assert overlay_rects[0][1] == {"outline": "#ff453a", "width": 1.2, "dash": (4, 4)}

    texts = [
        kwargs.get("text", "")
        for name, _args, kwargs in canvas.calls
        if name == "text"
    ]
    assert any("底板展開預覽｜Final Part Geometry" in text for text in texts)
    assert any("展開圖孔距 W:40.0 H:0.0" in text for text in texts)
