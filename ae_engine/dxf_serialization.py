# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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


def verify_quantity_check_dxf(scene, filepath):
    """Independently reopen staged Q contents, layer/style and exact placement."""
    import math
    import re
    expected = [p for p in scene.primitives if isinstance(p, TextPrimitive)
                and p.semantic_id == "manufacturing_quantity"]
    if len(expected) != 1:
        raise ValueError("quantity CHECK scene must contain exactly one Q")
    text = expected[0]
    doc = ezdxf.readfile(filepath)
    if "CHECK" not in doc.layers:
        raise ValueError("staged quantity CHECK DXF is missing CHECK layer")
    layer = doc.layers.get("CHECK")
    rows = []
    check_entities = []
    for entity in doc.modelspace():
        if entity.dxftype() not in {"MTEXT", "TEXT"}:
            continue
        if entity.dxf.layer == "CHECK":
            check_entities.append(entity)
        value = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
        if entity.dxf.layer == "CHECK" and re.fullmatch(r"[Qq][0-9]+", value.strip()):
            rows.append((entity, value))
    if len(check_entities) != 1 or len(rows) != 1 or rows[0][1] != text.text:
        raise ValueError("staged quantity CHECK DXF has missing, duplicate or incorrect Q")
    entity = rows[0][0]
    if (entity.dxftype() != "MTEXT" or entity.dxf.layer != "CHECK"
            or entity.dxf.color != 2 or entity.dxf.linetype not in {"BYLAYER", "CONTINUOUS"}
            or layer.dxf.color != 2 or layer.dxf.linetype != "CONTINUOUS"
            or entity.dxf.attachment_point != 5
            or not math.isclose(entity.dxf.char_height, text.char_height, abs_tol=1e-6)
            or not math.isclose(entity.dxf.insert.x, text.insert.x, abs_tol=1e-6)
            or not math.isclose(entity.dxf.insert.y, text.insert.y, abs_tol=1e-6)):
        raise ValueError("staged quantity CHECK DXF layer/style/placement differs")
