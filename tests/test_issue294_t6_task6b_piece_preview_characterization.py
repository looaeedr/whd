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


def test_task6b_physical_piece_preview_consumes_piece_render_data_without_rederiving(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    transform = FakeTransform()

    render_data = SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 100.0, 50.0)),
        scene=object(),
        warnings=(SimpleNamespace(message="WARN"),),
    )
    piece = SimpleNamespace(
        render_data=render_data,
        role="left",
        formed_outer_dimensions=(90.0, 40.0),
        material_dimensions=(100.0, 50.0),
    )
    aggregate = SimpleNamespace(
        pieces=(piece, SimpleNamespace(), SimpleNamespace()),
    )

    host.canvas_z = canvas
    host.draw_stock_var = Var(True)
    host.COLOR_TEXT_MUTED = "#777"
    host._box_body_piece_label = lambda part_key: (
        events.append(("label", part_key)) or "左片"
    )

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
        gui,
        "_draw_phase6_annotation_projection",
        lambda target, data, actual_transform, *, part_key: events.append(
            ("annotation", target, data, actual_transform, part_key)
        ),
    )

    gui.Phase6ApplicationHost._draw_box_body_piece_preview(
        host, aggregate, piece, "box_body:left"
    )

    assert ("viewport", (0.0, 0.0, 100.0, 50.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("label", "box_body:left") in events
    assert ("annotation", canvas, render_data, transform, "box_body:left") in events

    stock = next(
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "rectangle"
    )
    assert stock == (
        (10.0, 20.0, 210.0, 120.0),
        {"outline": "#00d4d4", "width": 1.5, "dash": (8, 4)},
    )

    text = next(
        kwargs["text"]
        for name, _args, kwargs in canvas.calls
        if name == "text"
    )
    assert "左片展開預覽（箱身子板件）" in text
    assert "成形：90 × 40 mm" in text
    assert "展開：100 × 50 mm" in text
    assert "雙擊畫布編輯此片開孔" in text
    assert "⚠ WARN" in text

    assert host.last_box_body_face_overview == {
        "mode": "physical_piece",
        "piece_key": "box_body:left",
        "role": "left",
        "material_bounds": (0.0, 0.0, 100.0, 50.0),
        "aggregate_piece_count": 3,
    }
