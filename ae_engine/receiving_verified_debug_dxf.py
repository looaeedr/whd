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
    if key.startswith("box_body:divider:"):
        return "下框／中隔"
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



def _debug_layout_for_panel(parts):
    """Arrange already-verified flats for inspection, using rigid moves only.

    Every role is placed relative to its actual neighboring physical piece:
    head/tail relative to back, lower door below upper, and each inner door
    inside its own top/left/right/bottom frame group. These are CHECK layout
    positions, never canonical manufactured assembly or reconstructed geometry.
    """
    def size(render):
        x0, y0, x1, y1 = _scene_bounds(render.scene)
        return x1 - x0, y1 - y0

    def stack(entries):
        placed = []
        height = 0.0
        width = 0.0
        for key, render in entries:
            w, h = size(render)
            placed.append((key, render, 0.0, height))
            width = max(width, w)
            height += h + _GAP
        return placed, width, max(0.0, height - _GAP)

    def moved(placed, dx, dy):
        return [(key, render, x + dx, y + dy)
                for key, render, x, y in placed]

    def block(placed):
        if not placed:
            return None
        x0 = min(x for _, _, x, _ in placed)
        y0 = min(y for _, _, _, y in placed)
        x1 = max(x + size(render)[0] for _, render, x, _ in placed)
        y1 = max(y + size(render)[1] for _, render, _, y in placed)
        return (moved(placed, -x0, -y0), x1 - x0, y1 - y0)

    by_role = defaultdict(list)
    inner_by_owner = defaultdict(list)
    doors = []
    for key, render in parts:
        key = str(key)
        role = _role(key)
        if key.casefold().startswith("inner_door:"):
            tokens = key.split(":")
            owner = tokens[1] if len(tokens) > 2 else ""
            inner_by_owner[owner].append((key, render))
        elif role in ("上門", "下門"):
            doors.append((key, render))
        else:
            by_role[role].append((key, render))

    def body_layout():
        data = {role: stack(by_role.pop(role, ()))
                for role in ("左側板", "後面板", "右側板", "封頭", "封尾")}
        (left, lw, lh) = data["左側板"]
        (back, bw, bh) = data["後面板"]
        (right, rw, rh) = data["右側板"]
        (head, hw, hh) = data["封頭"]
        (tail, tw, th) = data["封尾"]
        if not any((left, back, right, head, tail)):
            return None
        center_left = lw + (_GAP if left else 0.0)
        center_width = max(bw, hw, tw)
        back_y = th + (_GAP if tail else 0.0)
        # Align each side with the back, not the tallest unrelated row.
        return block(
            moved(back, center_left + (center_width - bw) / 2, back_y)
            + moved(left, 0.0, back_y + (bh - lh) / 2)
            + moved(right, center_left + center_width + _GAP,
                    back_y + (bh - rh) / 2)
            + moved(head, center_left + (center_width - hw) / 2,
                    back_y + bh + _GAP)
            + moved(tail, center_left + (center_width - tw) / 2,
                    back_y - _GAP - th)
        )

    def doors_layout():
        if not doors:
            return None
        by_column = defaultdict(list)
        for key, render in doors:
            cell = re.fullmatch(r"door_c([0-9]+)_r([0-9]+)", key.casefold())
            column, row = (int(cell.group(1)), int(cell.group(2))) if cell else (
                0, 1 if _role(key) == "上門" else 2
            )
            by_column[column].append((row, key, render))
        placed = []
        next_x = 0.0
        for column in sorted(by_column):
            # Place physical lower rows at smaller Y, directly under upper rows.
            members = sorted(by_column[column], key=lambda item: (
                item[0], item[1]
            ))
            width = max(size(render)[0] for _, _, render in members)
            y = 0.0
            for _row, key, render in reversed(members):
                w, h = size(render)
                placed.append((key, render, next_x + (width - w) / 2, y))
                y += h + _GAP
            next_x += width + _GAP
        return block(placed)

    def inner_layout(entries):
        data = {role: stack(tuple((key, render) for key, render in entries
                                  if _role(key) == role))
                for role in ("上框", "左框", "內門", "右框", "下框／中隔")}
        top, tw, th = data["上框"]
        left, lw, lh = data["左框"]
        panel, pw, ph = data["內門"]
        right, rw, rh = data["右框"]
        bottom, bw, bh = data["下框／中隔"]
        core_width = max(pw, tw, bw)
        core_height = ph if panel else max(lh, rh)
        core_x = lw + (_GAP if left else 0.0)
        core_y = bh + (_GAP if bottom else 0.0)
        # Top/bottom and left/right are anchored to the SAME inner-door
        # center. No frame gets rotated, mirrored, resized, or re-manufactured.
        return block(
            moved(panel, core_x + (core_width - pw) / 2, core_y)
            + moved(top, core_x + (core_width - tw) / 2,
                    core_y + core_height + _GAP)
            + moved(bottom, core_x + (core_width - bw) / 2,
                    core_y - _GAP - bh)
            + moved(left, 0.0, core_y + (core_height - lh) / 2)
            + moved(right, core_x + core_width + _GAP,
                    core_y + (core_height - rh) / 2)
        )

    blocks = [body_layout(), doors_layout()]
    for owner in sorted(inner_by_owner, key=lambda name: (
        {"upper": 0, "lower": 1}.get(name.casefold(), 2), name.casefold()
    )):
        blocks.append(inner_layout(inner_by_owner[owner]))
    # A standalone Divider is not an inner-door bottom frame. Keep it
    # independent below the door assembly; the base plate remains last.
    for role in ("下框／中隔", "底板", "其他板件"):
        blocks.append(block(stack(by_role.pop(role, ()))[0]))
    for role in sorted(by_role):
        blocks.append(block(stack(by_role[role])[0]))

    placed = []
    top = 0.0
    for entry in blocks:
        if entry is None:
            continue
        members, _width, height = entry
        placed.extend(moved(members, 0.0, top - height))
        top -= height + 2 * _GAP
    if len(placed) != len(parts):
        raise ValueError("RECEIVING_DEBUG_LAYOUT_PHYSICAL_INVENTORY_MISMATCH")
    return tuple(placed), -top

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
        placements, used_height = _debug_layout_for_panel(parts)
        for key, render, left, local_bottom in placements:
            x0, y0, x1, y1 = _scene_bounds(render.scene)
            bottom = cursor + local_bottom
            _label(scene, f"{_role(key)} / {key}  "
                   f"Q{counts[part_records[(panel_name, key)]]}",
                   left, bottom + (y1 - y0) + 15)
            for source in render.scene.primitives:
                # Only rigid translation into CHECK: all certified source
                # holes, corners, BEND and blank outlines remain untouched.
                moved_source = _translated(source, left - x0, bottom - y0)
                scene.add(_check_only(moved_source))
        cursor -= used_height + 90
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
