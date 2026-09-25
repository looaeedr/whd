# -*- coding: utf-8 -*-
from types import SimpleNamespace

import gui
from ae_engine.drawing_annotations import AnnotationPlan, LinearDimensionAnnotation
from ae_engine.engineering_drawing import EngineeringDrawingProjection
from ae_engine.sheetmetal_drawing import TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2


class _Canvas:
    def __init__(self):
        self.text_calls = []
    def create_text(self, *args, **kwargs):
        self.text_calls.append((args, kwargs))
    def create_line(self, *args, **kwargs):
        pass


class _Transform:
    def world_to_canvas(self, p):
        return (float(p.x), float(p.y))


def test_dm6_t3_red_2d_sink_uses_semantic_identity_not_display_text(monkeypatch):
    y_dim = LinearDimensionAnnotation(
        axis="y", value=100.0,
        start=Vec2(0.0, 0.0), end=Vec2(0.0, 100.0),
        label="100",
    )
    # Presentation text is deliberately reformatted. Engineering identity stays y-dimension.
    primitive = TextPrimitive(
        "100.0 mm", Vec2(-15.0, 50.0), "DIMENSION", 5.0, 5,
        semantic_id=y_dim.semantic_id,
    )
    plan = AnnotationPlan(
        overall_dimensions=(y_dim,),
        feature_callouts=(), corner_callouts=(), radius_callouts=(),
        primitives=(primitive,), diagnostics=(),
    )
    projection = EngineeringDrawingProjection(
        part_key="probe", annotation_plan=plan, primitives=(primitive,)
    )
    monkeypatch.setattr(gui, "build_engineering_drawing_projection", lambda *a, **k: projection)

    canvas = _Canvas()
    gui._draw_phase6_annotation_projection(
        canvas, SimpleNamespace(), _Transform(), part_key="probe"
    )

    assert len(canvas.text_calls) == 1
    _args, kwargs = canvas.text_calls[0]
    assert kwargs["angle"] == 90, (
        "DM6 T3 RED: 2D sink must derive y-axis presentation from semantic identity; "
        "display text formatting must not change engineering ownership"
    )
