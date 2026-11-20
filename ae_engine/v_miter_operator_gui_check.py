# -*- coding: utf-8 -*-
"""#3317 live GUI fifth-choice CHECK: real FinalScene BEND + authored Fold.

This projection NEVER creates a fifth certified CornerType, replaces the
source CUTTING, or adds any production BEND/MARKING/DXF. It exposes an
operator-selectable, source-backed *ideal* 2D/formed-3D diagnostic pending
measured R/BA/T/actual cut-face certification.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_ideal_mating import (
    VMiterIdealMatingCandidate, project_ideal_v_miter_mating_candidate,
)
from .v_miter_material_trial import _single_source_material

V_MITER_GUI_CHECK = "V_MITER_CHECK"
V_MITER_GUI_UNCERTIFIED = "V_MITER_GUI_CHECK_ONLY_UNCERTIFIED"
V_MITER_GUI_CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
V_MITER_GUI_PART_KEYS = ("head", "tail", "door", "base_plate")


@dataclass(frozen=True)
class VMiterOperatorGUICheck:
    part_key: str
    corner_key: str
    first_bend_axis: str
    second_bend_axis: str
    first_flange_height_mm: float
    second_flange_height_mm: float
    second_fold_angle_deg: float
    ideal: VMiterIdealMatingCandidate
    check_scene: DrawingScene
    first_bend_source_gap_mm: float = 0.0
    second_bend_source_gap_mm: float = 0.0
    manufacturing_status: str = V_MITER_GUI_UNCERTIFIED


def normalize_operator_v_miter_gui_choices(raw: Mapping | None) -> dict[str, dict[str, str]]:
    """Keep selection per physical corner; a CHECK choice is not CornerType."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise GeometryError("V_MITER_GUI_CHOICES_INVALID")
    result = {}
    for part, corners in raw.items():
        if type(part) is not str or part not in V_MITER_GUI_PART_KEYS or not isinstance(corners, Mapping):
            raise GeometryError("V_MITER_GUI_PART_INVALID")
        normalized = {}
        for corner, mode in corners.items():
            if type(corner) is not str or corner not in V_MITER_GUI_CORNER_KEYS or mode != V_MITER_GUI_CHECK:
                raise GeometryError("V_MITER_GUI_CORNER_OR_MODE_INVALID")
            normalized[corner] = V_MITER_GUI_CHECK
        if normalized:
            result[part] = normalized
    return result


def change_operator_v_miter_gui_choice(
    raw: Mapping | None, part_key: str, target_key: str,
    pair_same: Mapping, *, enabled: bool,
) -> dict[str, dict[str, str]]:
    """Atomic physical corner draft; never touches FourCornerTypePolicy."""
    choices = normalize_operator_v_miter_gui_choices(raw)
    if type(enabled) is not bool or type(part_key) is not str or part_key not in V_MITER_GUI_PART_KEYS:
        raise GeometryError("V_MITER_GUI_SELECTION_INVALID")
    if not isinstance(pair_same, Mapping):
        raise GeometryError("V_MITER_GUI_PAIR_SOURCE_INVALID")
    if target_key in ("top", "bottom"):
        if pair_same.get(target_key) is not True:
            raise GeometryError("V_MITER_GUI_PAIR_IS_SPLIT")
        from .corner_state_transactions import project_operator_corner_pair_members
        targets = project_operator_corner_pair_members(target_key)
    elif target_key in V_MITER_GUI_CORNER_KEYS:
        targets = (target_key,)
    else:
        raise GeometryError("V_MITER_GUI_TARGET_INVALID")
    updated = dict(choices.get(part_key, {}))
    for key in targets:
        if enabled:
            updated[key] = V_MITER_GUI_CHECK
        else:
            updated.pop(key, None)
    if updated:
        choices[part_key] = updated
    else:
        choices.pop(part_key, None)
    return choices


def require_no_operator_v_miter_gui_check_for_export(snapshot: Mapping) -> None:
    """Never silently export the old four-type contour while V is selected."""
    if not isinstance(snapshot, Mapping):
        raise GeometryError("V_MITER_GUI_EXPORT_SOURCE_INVALID")
    choices = normalize_operator_v_miter_gui_choices(
        snapshot.get("v_miter_gui_check_corners"),
    )
    if choices:
        raise GeometryError(
            "V_MITER_GUI_CHECK_ONLY_UNCERTIFIED: V 型斜接尚未認證，"
            "禁止把原四種截角輸出當作第五種加工圖"
        )


def _orthogonal_bends(scene: DrawingScene):
    vertical, horizontal = [], []
    for row in scene.primitives:
        if not isinstance(row, LinePrimitive) or row.layer != "BEND":
            continue
        x1, y1, x2, y2 = row.p1.x, row.p1.y, row.p2.x, row.p2.y
        if not all(type(v) in (int, float) and math.isfinite(v)
                   for v in (x1, y1, x2, y2)):
            raise GeometryError("V_MITER_GUI_INVALID_BEND_SOURCE")
        if abs(x1 - x2) <= 1e-7 and abs(y1 - y2) > 1e-7:
            vertical.append(row)
        elif abs(y1 - y2) <= 1e-7 and abs(x1 - x2) > 1e-7:
            horizontal.append(row)
    return vertical, horizontal


def _station_gap(position: float, a: float, b: float) -> float:
    """Actual missing length from one orthogonal station to real drawn BEND."""
    lo, hi = min(a, b), max(a, b)
    return max(0.0, lo - position, position - hi)


def _physical_corner_bends(scene, material, corner_key):
    """Resolve real BEND stations, not a fictional continuous source crease.

    Four-side manufacturing BENDs may cross in their interiors (Door) or end
    1-2 mm short of an orthogonal station (EndCap CornerType relief). These
    shortfalls are *measured*, never interpreted as manufactured BEND or
    certified clearance. A detached virtual station is used only to draw the
    ideal CHECK rays; actual scene/CUTTING/BEND are untouched.
    """
    vertical, horizontal = _orthogonal_bends(scene)
    if not vertical or not horizontal:
        raise GeometryError("V_MITER_GUI_TWO_PHYSICAL_BENDS_REQUIRED")
    minx, miny, maxx, maxy = material.bounds
    midx, midy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    cx = minx if corner_key.endswith("left") else maxx
    cy = maxy if corner_key.startswith("top") else miny
    width, height = maxx - minx, maxy - miny
    if min(width, height) <= 1e-8:
        raise GeometryError("V_MITER_GUI_INVALID_MATERIAL_BOUNDS")
    choices = []
    for vx in vertical:
        for hy in horizontal:
            meet = Vec2(vx.p1.x, hy.p1.y)
            # Only source BEND stations in the requested physical quadrant.
            if not (minx < meet.x < maxx and miny < meet.y < maxy):
                continue
            if (corner_key.endswith("left") and meet.x >= midx
                    or corner_key.endswith("right") and meet.x <= midx
                    or corner_key.startswith("bottom") and meet.y >= midy
                    or corner_key.startswith("top") and meet.y <= midy):
                continue
            gap_v = _station_gap(meet.y, vx.p1.y, vx.p2.y)
            gap_h = _station_gap(meet.x, hy.p1.x, hy.p2.x)
            distance = math.hypot(
                (meet.x - cx) / width, (meet.y - cy) / height,
            )
            choices.append((gap_v + gap_h, distance, meet, vx, hy, gap_v, gap_h))
    if not choices:
        raise GeometryError("V_MITER_GUI_NO_PHYSICAL_BEND_STATIONS_IN_CORNER")
    choices.sort(key=lambda row: (row[0], row[1]))
    if len(choices) > 1 and all(
        abs(choices[1][i] - choices[0][i]) <= 1e-9 for i in (0, 1)
    ):
        raise GeometryError("V_MITER_GUI_AMBIGUOUS_SOURCE_CORNER")
    _, _, meet, vx, hy, gap_v, gap_h = choices[0]
    # The inward rays follow genuine BEND material; only a possible short
    # station-to-first-drawn-point gap is virtual, quantified for the operator.
    up = corner_key.startswith("bottom")
    right = corner_key.endswith("left")
    far_v = max((vx.p1, vx.p2), key=lambda p: p.y) if up else min(
        (vx.p1, vx.p2), key=lambda p: p.y
    )
    far_h = max((hy.p1, hy.p2), key=lambda p: p.x) if right else min(
        (hy.p1, hy.p2), key=lambda p: p.x
    )
    if (abs(far_v.y - meet.y) <= 1e-7
            or abs(far_h.x - meet.x) <= 1e-7):
        raise GeometryError("V_MITER_GUI_BEND_CORE_RAYS_HAVE_NO_REACH")
    if up != (far_v.y > meet.y) or right != (far_h.x > meet.x):
        raise GeometryError("V_MITER_GUI_BEND_CORE_RAY_DIRECTION_INVALID")
    flange_x = meet.x - minx if right else maxx - meet.x
    flange_y = meet.y - miny if up else maxy - meet.y
    if min(flange_x, flange_y) <= 1e-8:
        raise GeometryError("V_MITER_GUI_MISSING_FLANGE_MATERIAL")
    projected_v = LinePrimitive(meet, far_v, "BEND")
    projected_h = LinePrimitive(meet, far_h, "BEND")
    return (
        projected_v, projected_h, float(flange_x), float(flange_y),
        float(gap_v), float(gap_h),
    )


def _profile_angle_at_bend(profile, position, origin):
    """Use authored Fold segment's RIGHT-boundary angle at the actual BEND."""
    if not profile:
        raise GeometryError("V_MITER_GUI_AUTHORED_FOLD_ANGLE_REQUIRED")
    station = float(origin)
    found = []
    for row in profile:
        length = getattr(row, "length", None)
        if type(length) not in (int, float) or not math.isfinite(length) or length < 0:
            raise GeometryError("V_MITER_GUI_FOLD_MATERIAL_INVALID")
        station += length
        if abs(station - position) <= 1e-6:
            angle = getattr(row, "angle", None)
            if type(angle) not in (int, float) or not math.isfinite(angle):
                raise GeometryError("V_MITER_GUI_FOLD_ANGLE_MISSING")
            found.append(float(angle))
    if len(found) != 1 or abs(found[0]) <= 1e-9:
        raise GeometryError("V_MITER_GUI_BEND_NOT_LINKED_TO_FOLD")
    return found[0]


def _endcap_existing_fold_angle_sources(part_spec: EndCapPartSpec, part_key: str):
    """Reuse canonical authored Fold; if missing, Engine's *existing* Factory Fold.

    A fresh Head/Tail already has physical BENDs created by the standard
    Factory but no optional authored X/Y Fold rows. Build the same Factory
    default from the immutable PartSpec source, never invent 90 degrees in
    Tk or fill an invalid *present* authored profile from defaults.
    """
    x_profile = tuple(part_spec.fold_profile_x or ())
    y_profile = tuple(part_spec.fold_profile_y or ())
    if x_profile and y_profile:
        return x_profile, y_profile
    from .endcap_factory_fold import build_endcap_xy_fold_profiles
    from .box_body_fold_profile import profile_to_fold_segments
    physical = {
        "model": part_spec.model_name or "自訂",
        "w": part_spec.width, "d": part_spec.depth,
        "t": part_spec.thickness, "fw": part_spec.frame_width,
        "yl1": part_spec.fold_left, "yr1": part_spec.fold_right,
        "ytop1": part_spec.fold_top, "ybottom1": part_spec.fold_bottom,
    }
    for field in ("w", "d", "t", "fw", "yl1", "yr1", "ytop1", "ybottom1"):
        value = physical[field]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise GeometryError("V_MITER_GUI_DEFAULT_FOLD_PHYSICAL_SOURCE_REQUIRED")
    factory_profiles = build_endcap_xy_fold_profiles(
        physical, part_key=part_key,
    )
    if not x_profile:
        x_profile = profile_to_fold_segments(factory_profiles["X"])
    if not y_profile:
        y_profile = profile_to_fold_segments(factory_profiles["Y"])
    return x_profile, y_profile


def project_operator_v_miter_live_corner_check(
    part_spec, render_data: PartRenderData, corner_key: str,
    *, relief_mode: str = "ROUND_R",
) -> VMiterOperatorGUICheck:
    """Project an actual per-corner 2D/3D ideal V, strictly CHECK-only.

    Do not infer a second angle from a BEND drawing (it contains no angles).
    Door has the existing physical fixed-90 four-side flange contract; EndCap
    angles come from its *authored current* X/Y FoldProfileSegment and must
    match the same FinalScene's true BEND station.
    """
    if type(corner_key) is not str or corner_key not in V_MITER_GUI_CORNER_KEYS:
        raise GeometryError("V_MITER_GUI_CORNER_INVALID")
    from .v_miter_corner_source import VMiterReliefMode
    try:
        mode = VMiterReliefMode(relief_mode)
    except (TypeError, ValueError) as exc:
        raise GeometryError("V_MITER_GUI_RELIEF_MODE_INVALID") from exc
    if not isinstance(render_data, PartRenderData) or not isinstance(render_data.scene, DrawingScene):
        raise GeometryError("V_MITER_GUI_CANONICAL_RENDER_SOURCE_REQUIRED")
    if isinstance(part_spec, DoorPartSpec):
        part_key = "door"
    elif isinstance(part_spec, EndCapPartSpec):
        part_key = "tail" if part_spec.is_tail else "head"
    else:
        # A single-axis BoxBody/BasePlate has no verified two-bend corner.
        # Do not synthesize an orthogonal fold from a nominal rectangle.
        raise GeometryError("V_MITER_GUI_PART_HAS_NO_VERIFIED_TWO_BEND_SOURCE")
    material = _single_source_material(render_data.scene)
    x_bend, y_bend, x_height, y_height, x_gap, y_gap = _physical_corner_bends(
        render_data.scene, material, corner_key,
    )
    if isinstance(part_spec, DoorPartSpec):
        # Canonical DoorPartSpec has four fixed 90-degree sheet bends; its
        # fold_left/right/top/bottom fields are physical return lengths.
        angle_x = angle_y = 90.0
    else:
        minx, miny, _, _ = material.bounds
        source_x, source_y = _endcap_existing_fold_angle_sources(part_spec, part_key)
        angle_x = _profile_angle_at_bend(
            source_x, x_bend.p1.x, minx,
        )
        angle_y = _profile_angle_at_bend(
            source_y, y_bend.p1.y, miny,
        )
        if angle_x * angle_y <= 0:
            raise GeometryError("V_MITER_GUI_OPPOSITE_FOLD_SENSE")
    if not (0 < abs(angle_x) < 180 and 0 < abs(angle_y) < 180):
        raise GeometryError("V_MITER_GUI_FOLD_ANGLE_OUT_OF_RANGE")
    if abs(abs(angle_x) - 90) <= 1e-8:
        first, second = (x_bend, "x", x_height), (y_bend, "y", y_height)
        second_angle = abs(angle_y)
    elif abs(abs(angle_y) - 90) <= 1e-8:
        first, second = (y_bend, "y", y_height), (x_bend, "x", x_height)
        second_angle = abs(angle_x)
    else:
        raise GeometryError("V_MITER_GUI_NO_FIXED_90_DEG_V_EDGE")
    t = part_spec.thickness
    if type(t) not in (int, float) or not math.isfinite(t) or t <= 0:
        raise GeometryError("V_MITER_GUI_THICKNESS_INVALID")
    # Temporary two-station CHECK scene: derived from original source
    # BEND coordinates and measured gaps, NEVER a production FinalScene.
    # Both source owners are originals; the stage itself cannot be exported.
    ideal = project_ideal_v_miter_mating_candidate(
        DrawingScene([first[0], second[0]]), first[0], second[0],
        thickness_mm=t,
        first_flange_height_mm=first[2],
        second_flange_height_mm=second[2],
        second_fold_angle_deg=second_angle,
        relief_mode=mode,
    )
    check = DrawingScene([
        LinePrimitive(ideal.first_flat_miter_ray[0], ideal.first_flat_miter_ray[1], "CHECK", 211),
        LinePrimitive(ideal.second_flat_miter_ray[0], ideal.second_flat_miter_ray[1], "CHECK", 211),
    ])
    return VMiterOperatorGUICheck(
        part_key=part_key, corner_key=corner_key,
        first_bend_axis=first[1], second_bend_axis=second[1],
        first_flange_height_mm=first[2], second_flange_height_mm=second[2],
        second_fold_angle_deg=second_angle, ideal=ideal, check_scene=check,
        first_bend_source_gap_mm=x_gap if first[1] == "x" else y_gap,
        second_bend_source_gap_mm=y_gap if second[1] == "y" else x_gap,
    )
