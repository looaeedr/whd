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

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", args, kwargs))
        return len(self.calls)

    def create_rectangle(self, *args, **kwargs):
        self.calls.append(("rectangle", args, kwargs))
        return len(self.calls)


class FakeTransform:
    scale = 2.0

    def world_to_canvas(self, point):
        return float(point.x) * 2.0 + 10.0, float(point.y) * 2.0 + 20.0


def _render_data(bounds=(0.0, 0.0, 100.0, 50.0)):
    return SimpleNamespace(
        material=SimpleNamespace(bounds=bounds),
        scene=object(),
    )


def test_task4a_indicator_box_keeps_authority_in_host_and_presentation_order(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    spec = SimpleNamespace(name="indicator-box-spec")
    context = object()
    render_data = _render_data()

    host.canvas_indicator_box = canvas
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host.indicator_l_var = Var(1)
    host.indicator_layer_g_vars = [Var(2)]
    host.surface_features = {"indicator_box": ["hole"]}
    host._indicator_box_part_spec = lambda val, groups, *, features: (
        events.append(("spec", val, groups, features)) or spec
    )
    host._manufacturing_context = lambda *, draw_stock: (
        events.append(("context", draw_stock)) or context
    )
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render_data", actual_spec, actual_context)) or render_data
    )
    host.draw_stock_var = Var(False)
    host.COLOR_TEXT_MUTED = "#777"
    host._draw_phase6_finished_dimension_summary = (
        lambda target, *, part_key: events.append(("finished", target, part_key))
    )

    transform = FakeTransform()
    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda bounds, cw, ch: (
            events.append(("viewport", bounds, cw, ch))
            or (transform, 10.0, 120.0, 2.0, 20.0)
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
        gui.ae,
        "indicator_shared_baseline_source_label",
        lambda filename: f"BASELINE:{filename}",
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

    gui.Phase6ApplicationHost.draw_indicator_box(host, {"w": 100})

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    assert ("spec", {"w": 100}, (2,), ["hole"]) in events
    assert ("context", False) in events
    assert ("render_data", spec, context) in events
    assert ("viewport", (0.0, 0.0, 100.0, 50.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "indicator_box") in events
    assert ("finished", canvas, "indicator_box") in events
    assert ("hint", canvas, 640, False) in events

    preview_texts = [
        kwargs.get("text", "")
        for name, _args, kwargs in canvas.calls
        if name == "text"
    ]
    assert any("指示燈盒子展開預覽" in text for text in preview_texts)
    assert any("BASELINE:盒子.dxf" in text for text in preview_texts)
    assert any("排列 [2]，共 2 顆指示燈" in text for text in preview_texts)


def test_task4a_indicator_door_keeps_authority_in_host_and_finished_size_presentation(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    spec = SimpleNamespace(name="indicator-door-spec")
    context = object()
    render_data = _render_data((0.0, 0.0, 80.0, 40.0))

    host.canvas_indicator_door = canvas
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host.indicator_l_var = Var(2)
    host.indicator_layer_g_vars = [Var(1), Var(3)]
    host.surface_features = {"indicator_door": ["door-hole"]}
    host._indicator_door_part_spec_from_values = lambda val, groups, *, features: (
        events.append(("spec", val, groups, features)) or (spec, context)
    )
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render_data", actual_spec, actual_context)) or render_data
    )
    host.draw_stock_var = Var(False)
    host.COLOR_TEXT_MUTED = "#777"
    host._draw_phase6_finished_dimension_summary = (
        lambda target, *, part_key: events.append(("finished", target, part_key))
    )

    transform = FakeTransform()
    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda bounds, cw, ch: (
            events.append(("viewport", bounds, cw, ch))
            or (transform, 10.0, 100.0, 2.0, 20.0)
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
            or (72.5, 31.25)
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

    gui.Phase6ApplicationHost.draw_indicator_door(host, {"h": 50})

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    assert ("spec", {"h": 50}, (1, 3), ["door-hole"]) in events
    assert ("render_data", spec, context) in events
    assert ("finished_size", spec, context) in events
    assert ("viewport", (0.0, 0.0, 80.0, 40.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "indicator_door") in events
    assert ("finished", canvas, "indicator_door") in events
    assert ("hint", canvas, 640, False) in events

    preview_texts = [
        kwargs.get("text", "")
        for name, _args, kwargs in canvas.calls
        if name == "text"
    ]
    assert any("指示燈小門展開預覽" in text for text in preview_texts)
    assert any("成品 72.50 × 31.25 mm" in text for text in preview_texts)
