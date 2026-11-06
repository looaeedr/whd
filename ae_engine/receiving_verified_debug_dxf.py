# -*- coding: utf-8 -*-
"""CHECK-only Receiving DXF review sheet using *verified* source FinalScenes.

This diagnostic is not NC or a replacement manufacturing flat. It may only be
called from the existing source-guarded grouped commit after every real sheet
passed independent Save→Reload. Positions are translations of canonical flat
primitives, not recalculated stock, folds, contours or holes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re

import ezdxf

from .composed_panel_dxf import (
    _scene_bounds, _translated, _source_signature, _actual_signature,
)
from .dxf_serialization import save_scene_dxf
from .sheetmetal_drawing import (
    DrawingScene, CirclePrimitive, PolylinePrimitive, LinePrimitive,
    TextPrimitive,
)
from .sheetmetal_geometry import Vec2


# Row 0: head above back; row 1: left / back / right; row 2: tail
# below back; doors follow; real inner door surrounded by actual frames.
# Divider below inner door; verified base plate last.
_SLOTS = {
    "左側板": (1, 0), "後面板": (1, 1), "右側板": (1, 2),
    "封頭": (0, 1), "封尾": (2, 1),
    "上門": (3, 1), "下門": (4, 1),
    "上框": (5, 1), "左框": (6, 0),
    "內門": (6, 1), "右框": (6, 2),
    "下框／中隔": (7, 1), "底板": (8, 1),
}
_GAP = 70.0


@dataclass(frozen=True)
class ReceivingDebugQuantity:
    role: str
    representative_part: str
    count: int
    canonical_signature: tuple[str, ...]


def _role(identity):
    key = str(identity).casefold()
    if key == "box_body" or key.startswith("box_body:"):
        if "left_side" in key:
            return "左側板"
        if "right_side" in key:
            return "右側板"
        return "後面板"
    if key == "head" or key.startswith("head:"):
        return "封頭"
    if key == "tail" or key.startswith("tail:"):
        return "封尾"
    if key == "door" or key.startswith(("door_", "door:")):
        numbered_row = re.search(r"(?:^|_)r([0-9]+)(?:_|$)", key)
        return "下門" if numbered_row and int(numbered_row.group(1)) >= 2 else "上門"
    if key.startswith("inner_door:"):
        for suffix, role in (
            (":top_frame", "上框"), (":left_frame", "左框"),
            (":right_frame", "右框"), (":bottom_frame", "下框／中隔"),
            (":divider_frame", "下框／中隔"),
        ):
            if key.endswith(suffix):
                return role
        return "內門"
    if key.startswith(("divider", "middle_plate")):
        return "下框／中隔"
    if key == "base_plate" or key.startswith("base_plate:"):
        return "底板"
    return "其他板件"


def _source_signature_for_quantity(render):
    scene = getattr(render, "scene", None)
    if not isinstance(scene, DrawingScene):
        raise ValueError("RECEIVING_DEBUG_FINAL_SCENE_REQUIRED")
    # CHECK notes (e.g. panel names, Q) are not machining features.
    physical = DrawingScene([
        p for p in scene.primitives if str(p.layer).upper() != "CHECK"
    ])
    if not physical.primitives:
        raise ValueError("RECEIVING_DEBUG_PHYSICAL_PRIMITIVES_REQUIRED")
    min_x, min_y, _, _ = _scene_bounds(physical)
    # Every CUTTING/BEND/BLIND_HOLE/MARKING contour is compared in local UV.
    # A one-hole difference changes this signature even for equal W/H.
    return tuple(sorted(
        repr(_source_signature(_translated(p, -min_x, -min_y)))
        for p in physical.primitives
    ))


def _check_only(primitive):
    colors = {"CUTTING": 3, "BEND": 5, "MARKING": 211,
              "BLIND_HOLE": 1, "DATUM": 6}
    color = colors.get(str(primitive.layer).upper(), 2)
    if isinstance(primitive, PolylinePrimitive):
        return PolylinePrimitive(primitive.points, "CHECK",
                                 primitive.closed, color, primitive.semantic_id)
    if isinstance(primitive, LinePrimitive):
        return LinePrimitive(primitive.p1, primitive.p2, "CHECK", color)
    if isinstance(primitive, CirclePrimitive):
        return CirclePrimitive(primitive.center, primitive.radius, "CHECK",
                               color, primitive.source_type, primitive.source_id)
    if isinstance(primitive, TextPrimitive):
        return TextPrimitive(primitive.text, primitive.insert, "CHECK",
                             primitive.char_height, primitive.attachment_point,
                             color, primitive.semantic_id)
    raise ValueError("RECEIVING_DEBUG_PRIMITIVE_NOT_SUPPORTED")


def _label(scene, label, x, y, size=7):
    scene.add(TextPrimitive(str(label), Vec2(float(x), float(y)),
                            "CHECK", float(size), 1, 2, "debug_source_label"))


def compose_verified_receiving_debug_layout(panel_rows):
    """Return diagnostic scene + strict quantity inventory in saved Set/Bay order."""
    bays = tuple((str(name), tuple(parts)) for name, parts in panel_rows)
    if not bays or any(not parts for _, parts in bays):
        raise ValueError("RECEIVING_DEBUG_INCOMPLETE_VERIFIED_BAYS")
    counts = Counter()
    representative = {}
    part_records = {}
    for name, parts in bays:
        if len({str(key) for key, _ in parts}) != len(parts):
            raise ValueError("RECEIVING_DEBUG_DUPLICATE_PHYSICAL_PART")
        for key, render in parts:
            role = _role(key)
            signature = _source_signature_for_quantity(render)
            count_key = (role, signature)
            counts[count_key] += 1
            representative.setdefault(count_key, str(key))
            part_records[(name, str(key))] = count_key
    ordered = sorted(counts, key=lambda key: (
        _SLOTS.get(key[0], (9, 1)), key[0], key[1],
    ))
    quantities = tuple(
        ReceivingDebugQuantity(key[0], representative[key],
                               counts[key], key[1]) for key in ordered
    )
    scene = DrawingScene()
    _label(scene, "DEBUG ONLY - NOT FOR NC / 只供檢查", 0, 60, 14)
    _label(scene, "相同板件、相同孔型／孔位／加工層才合計", 0, 35, 10)
    cursor = 0.0
    for item in quantities:
        _label(scene, f"{item.role} / {item.representative_part}  Q{item.count}",
               0, cursor)
        cursor -= 20
    cursor -= 90

    for panel_name, parts in bays:
        _label(scene, f"盤名 {panel_name}", 0, cursor, 12)
        cursor -= 55
        slots = defaultdict(list)
        for key, render in parts:
            slots[_SLOTS.get(_role(key), (9, 1))].append((str(key), render))
        column_width = [0.0, 0.0, 0.0]
        row_height = defaultdict(float)
        for (row, col), items in slots.items():
            for _key, render in items:
                x0, y0, x1, y1 = _scene_bounds(render.scene)
                column_width[col] = max(column_width[col], x1 - x0 + _GAP)
                row_height[row] += y1 - y0 + _GAP + 28
        column_x = [0.0, column_width[0], column_width[0] + column_width[1]]
        for row in sorted(row_height):
            column_y = defaultdict(float)
            for (cell_row, col), items in sorted(slots.items()):
                if cell_row != row:
                    continue
                for key, render in items:
                    x0, _y0, _x1, y1 = _scene_bounds(render.scene)
                    top = cursor - column_y[col] - 30
                    _label(scene, f"{_role(key)} / {key}  "
                           f"Q{counts[part_records[(panel_name, key)]]}",
                           column_x[col], top + 15)
                    for source in render.scene.primitives:
                        moved = _translated(source, column_x[col] - x0, top - y1)
                        scene.add(_check_only(moved))
                    min_y = _scene_bounds(render.scene)[1]
                    column_y[col] += y1 - min_y + _GAP + 28
            cursor -= row_height[row]
        cursor -= 90
    return scene, quantities


def save_verified_receiving_debug_dxf(destination, panel_rows, *, pre_commit_guard):
    """Stage, reopen, exact-CHECK verify; caller performs grouped atomic publish."""
    if not callable(pre_commit_guard):
        raise ValueError("RECEIVING_DEBUG_SOURCE_GUARD_REQUIRED")
    scene, quantities = compose_verified_receiving_debug_layout(panel_rows)
    pre_commit_guard()
    save_scene_dxf(destination, scene)
    doc = ezdxf.readfile(destination)
    if doc.audit().errors:
        raise ValueError("RECEIVING_DEBUG_DXF_AUDIT_FAILED")
    actual = Counter(_actual_signature(ent) for ent in doc.modelspace())
    expected = Counter(_source_signature(p) for p in scene.primitives)
    if actual != expected:
        raise ValueError("RECEIVING_DEBUG_DXF_SAVE_RELOAD_MISMATCH")
    if any(ent.dxf.layer != "CHECK" for ent in doc.modelspace()):
        raise ValueError("RECEIVING_DEBUG_NOT_CHECK_ONLY")
    pre_commit_guard()
    return quantities
