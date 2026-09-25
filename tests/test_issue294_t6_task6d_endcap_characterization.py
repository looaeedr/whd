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
    def create_rectangle(self, *args, **kwargs):
        return self._record("rectangle", *args, **kwargs)
    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)


class FakeTransform:
    scale = 2.0
    def world_to_canvas(self, point):
        return float(point.x) * 2.0 + 10.0, float(point.y) * 2.0 + 20.0


def test_task6d_endcap_preview_consumes_authoritative_render_data(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    spec = object()
    context = object()
    render_data = SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 80.0, 40.0)),
        scene=object(),
    )

    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host._baseline_source_model = lambda: "MODEL"
    host.baseline_var = Var("MODEL")
    host._end_cap_part_spec = lambda val, *, is_tail: (
        events.append(("spec", dict(val), is_tail)) or spec
    )
    host._manufacturing_context = lambda *, draw_stock: (
        events.append(("context", draw_stock)) or context
    )
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render-data", actual_spec, actual_context)) or render_data
    )
    host.draw_stock_var = Var(False)
    host.COLOR_TEXT_MUTED = "#777"
    host._draw_phase6_finished_dimension_summary = (
        lambda target, *, part_key: events.append(("finished", target, part_key))
    )

    transform = FakeTransform()
    monkeypatch.setattr(gui, "is_unknown_model", lambda _model: False)
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

    gui.Phase6ApplicationHost.draw_end_cap(
        host, {"w": 100.0}, canvas, part_label="封頭", is_tail=False
    )

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    assert ("spec", {"w": 100.0}, False) in events
    assert ("context", False) in events
    assert ("render-data", spec, context) in events
    assert ("viewport", (0.0, 0.0, 80.0, 40.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "head") in events
    assert ("finished", canvas, "head") in events
    assert ("hint", canvas, 640, True) in events

    text = next(
        kwargs["text"]
        for name, _args, kwargs in canvas.calls
        if name == "text"
    )
    assert "封頭展開預覽 (MODEL Final Part Geometry)" in text
    assert "[封頭]" in text


def test_task6d_endcap_error_path_keeps_hint_visible():
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    host.draw_grid = lambda *_args: None
    host._baseline_source_model = lambda: "MODEL"
    host.baseline_var = Var("MODEL")
    host._end_cap_part_spec = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError("boom")
    )
    host._manufacturing_context = lambda **_kwargs: object()
    host._authoritative_render_data = lambda *_args: None

    original_hint = gui.draw_hole_editor_hint
    gui.draw_hole_editor_hint = lambda target, cw, *, endcap: events.append(
        ("hint", target, cw, endcap)
    )
    try:
        gui.Phase6ApplicationHost.draw_end_cap(
            host, {}, canvas, part_label="封頭/尾", is_tail=True
        )
    finally:
        gui.draw_hole_editor_hint = original_hint

    text = next(
        kwargs["text"]
        for name, _args, kwargs in canvas.calls
        if name == "text"
    )
    assert "封頭尾載入失敗: boom" in text
    assert ("hint", canvas, 640, True) in events
