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


def test_task6c_box_body_aggregate_preview_consumes_authoritative_contexts(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    spec = object()
    context = object()
    contexts = {
        "left": SimpleNamespace(unfolded_min_x=0.0, unfolded_max_x=20.0),
        "back": SimpleNamespace(unfolded_min_x=20.0, unfolded_max_x=60.0),
        "right": SimpleNamespace(unfolded_min_x=60.0, unfolded_max_x=100.0),
    }
    render_data = SimpleNamespace(
        material=SimpleNamespace(bounds=(0.0, 0.0, 100.0, 50.0)),
        scene=object(),
        warnings=(SimpleNamespace(message="WARN"),),
        box_body_face_contexts=contexts,
        pieces=(
            SimpleNamespace(role="left"),
            SimpleNamespace(role="back"),
            SimpleNamespace(role="right"),
        ),
    )

    host.canvas_z = canvas
    host.box_body_face_bounds = {}
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host._box_body_part_spec = lambda val: (
        events.append(("spec", dict(val))) or spec
    )
    host._manufacturing_context = lambda *, draw_stock: (
        events.append(("context", draw_stock)) or context
    )
    host._authoritative_render_data = lambda actual_spec, actual_context: (
        events.append(("render-data", actual_spec, actual_context)) or render_data
    )
    host._refresh_box_body_piece_tabs_2d = lambda data: (
        events.append(("tabs", data)) or ""
    )
    host.draw_stock_var = Var(False)
    host.box_body_face_selected_var = Var("back")
    host._baseline_source_model = lambda: "MODEL"
    host.COLOR_ACCENT = "#0af"
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
    monkeypatch.setattr(
        gui.ae,
        "box_body_baseline_source_label",
        lambda model: f"BASE:{model}",
    )
    monkeypatch.setattr(
        gui,
        "box_body_face_dimensions",
        lambda **kwargs: {
            "left": (10.0, 50.0),
            "back": (20.0, 50.0),
            "right": (10.0, 50.0),
        },
    )

    val = {"w": 100.0, "h": 50.0, "d": 40.0}
    gui.Phase6ApplicationHost.draw_box_body(host, val)

    assert canvas.calls[0] == ("delete", ("all",), {})
    assert ("grid", canvas, 640, 480) in events
    assert ("spec", val) in events
    assert ("context", False) in events
    assert ("render-data", spec, context) in events
    assert ("tabs", render_data) in events
    assert ("viewport", (0.0, 0.0, 100.0, 50.0), 640, 480) in events
    assert ("scene", canvas, render_data.scene, transform, ("CHECK", "STOCK")) in events
    assert ("annotation", canvas, render_data, transform, "box_body") in events
    assert ("finished", canvas, "box_body") in events
    assert ("hint", canvas, 640, False) in events

    hit_rects = [
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "rectangle" and "box_body_face_hit_zone" in kwargs.get("tags", ())
    ]
    assert hit_rects == [
        (
            (10.0, 20.0, 50.0, 120.0),
            {
                "outline": "",
                "width": 1,
                "dash": (4, 3),
                "tags": ("box_body_face_hit_zone", "box_body_face_left"),
            },
        ),
        (
            (50.0, 20.0, 130.0, 120.0),
            {
                "outline": "#0af",
                "width": 2,
                "dash": (4, 3),
                "tags": ("box_body_face_hit_zone", "box_body_face_back"),
            },
        ),
        (
            (130.0, 20.0, 210.0, 120.0),
            {
                "outline": "",
                "width": 1,
                "dash": (4, 3),
                "tags": ("box_body_face_hit_zone", "box_body_face_right"),
            },
        ),
    ]
    assert host.box_body_face_bounds == {
        "left": (10.0, 20.0, 50.0, 120.0),
        "back": (50.0, 20.0, 130.0, 120.0),
        "right": (130.0, 20.0, 210.0, 120.0),
    }

    hint = next(
        kwargs["text"]
        for name, _args, kwargs in canvas.calls
        if name == "text"
    )
    assert "箱身展開預覽 (Z-Body)" in hint
    assert "BASE:MODEL" in hint
    assert "⚠ WARN" in hint

    assert host.last_box_body_face_overview == {
        "mode": "unfolded_with_face_hit_zones",
        "dimensions": {
            "left": (10.0, 50.0),
            "back": (20.0, 50.0),
            "right": (10.0, 50.0),
        },
        "unfolded_size": (100.0, 50.0),
        "transform": transform,
        "contexts": contexts,
        "piece_keys": ("box_body:left", "box_body:back", "box_body:right"),
        "baseline_status": "BASE:MODEL",
    }


def test_task6c_box_body_selected_piece_still_routes_to_piece_presenter(monkeypatch):
    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    events = []
    piece = SimpleNamespace(role="left")
    render_data = SimpleNamespace(
        pieces=(piece,),
        material=SimpleNamespace(bounds=(0.0, 0.0, 1.0, 1.0)),
    )

    host.canvas_z = canvas
    host.box_body_face_bounds = {}
    host.draw_grid = lambda target, cw, ch: events.append(("grid", target, cw, ch))
    host._box_body_part_spec = lambda val: "SPEC"
    host._manufacturing_context = lambda *, draw_stock: "CTX"
    host._authoritative_render_data = lambda spec, ctx: render_data
    host._refresh_box_body_piece_tabs_2d = lambda data: "box_body:left"
    host._draw_box_body_piece_preview = (
        lambda aggregate, actual_piece, key: events.append(
            ("piece", aggregate, actual_piece, key)
        )
    )

    monkeypatch.setattr(
        gui,
        "_phase6_2d_material_viewport",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("aggregate presenter must not run for selected piece")
        ),
    )

    gui.Phase6ApplicationHost.draw_box_body(host, {"w": 1, "h": 1, "d": 1})

    assert events[-1] == ("piece", render_data, piece, "box_body:left")
