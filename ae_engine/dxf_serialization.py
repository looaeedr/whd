# -*- coding: utf-8 -*-
"""DXF serialization boundary for canonical DrawingScene output.

This module serializes already-resolved drawing primitives only. It must not
recompute CUTTING, BEND, MARKING, or any manufacturing geometry.
"""
from __future__ import annotations

import ezdxf

from .sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)


def setup_dxf_layers(doc) -> None:
    """Create the canonical WHD DXF layer table without changing geometry."""
    if "CUTTING" not in doc.layers:
        doc.layers.new(name="CUTTING", dxfattribs={"color": 3, "linetype": "CONTINUOUS"})
    if "BEND" not in doc.layers:
        doc.layers.new(name="BEND", dxfattribs={"color": 5, "linetype": "CONTINUOUS"})
    if "MARKING" not in doc.layers:
        doc.layers.new(name="MARKING", dxfattribs={"color": 211, "linetype": "CONTINUOUS"})
    if "BLIND_HOLE" not in doc.layers:
        doc.layers.new(name="BLIND_HOLE", dxfattribs={"color": 1, "linetype": "CONTINUOUS"})
    if "STOCK" not in doc.layers:
        doc.layers.new(name="STOCK", dxfattribs={"color": 4, "linetype": "CONTINUOUS"})
    if "CENTER" not in doc.linetypes:
        doc.linetypes.add(
            name="CENTER",
            description="Center ____ _ ____ _ ____ _ ____",
            pattern=[1.25, -0.25, 0.25, -0.25],
        )
    if "DATUM" not in doc.layers:
        doc.layers.new(name="DATUM", dxfattribs={"color": 6, "linetype": "CENTER"})
    if "CHECK" not in doc.layers:
        doc.layers.new(name="CHECK", dxfattribs={"color": 2, "linetype": "CONTINUOUS"})


def add_drawing_scene_to_dxf(msp, scene: DrawingScene) -> None:
    """Serialize a canonical DrawingScene without recalculating coordinates."""
    for primitive in scene.primitives:
        attrs = {"layer": primitive.layer}
        color = getattr(primitive, "color", None)
        if color is None and primitive.layer == "MARKING":
            color = 211
        if color is not None:
            attrs["color"] = color

        if isinstance(primitive, PolylinePrimitive):
            msp.add_lwpolyline(
                [(p.x, p.y) for p in primitive.points],
                close=primitive.closed,
                dxfattribs=attrs,
            )
        elif isinstance(primitive, LinePrimitive):
            msp.add_line(
                (primitive.p1.x, primitive.p1.y),
                (primitive.p2.x, primitive.p2.y),
                dxfattribs=attrs,
            )
        elif isinstance(primitive, CirclePrimitive):
            msp.add_circle(
                (primitive.center.x, primitive.center.y),
                primitive.radius,
                dxfattribs=attrs,
            )
        elif isinstance(primitive, TextPrimitive):
            attrs.update({
                "insert": (primitive.insert.x, primitive.insert.y),
                "char_height": primitive.char_height,
                "attachment_point": primitive.attachment_point,
            })
            msp.add_mtext(primitive.text, dxfattribs=attrs)
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive).__name__}")


def save_scene_dxf(filepath, scene: DrawingScene) -> None:
    """Serialize one already-resolved DrawingScene to a new DXF document."""
    doc = ezdxf.new("R2010")
    setup_dxf_layers(doc)
    add_drawing_scene_to_dxf(doc.modelspace(), scene)
    doc.saveas(filepath)
