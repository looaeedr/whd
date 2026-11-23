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
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck, _single_source_material,
    project_v_miter_sharp_source_perimeter_check,
)
from .v_miter_factory_mother_check import (
    VMiterFactoryMotherReplacementCheck,
    project_v_miter_replaced_factory_corner_check,
)
from .v_miter_full_sheet_check import build_v_miter_whole_sheet_check_scene
from .v_miter_bounded_contact import (
    VMiterSharpThicknessWitness,
    project_v_miter_sharp_thickness_witness,
)
from .v_miter_source_marking_check import (
    VMiterSourceBendMarkingCheck,
    project_v_miter_source_bend_marking_check,
)
from .v_miter_factory_fold_check import (
    VMiterFactoryPrecutFoldCheck,
    project_v_miter_factory_precut_fold_check,
)
from .v_miter_trial_defaults import (
    VMiterTrialParameterDefaults, project_v_miter_trial_parameter_defaults,
)
from .v_miter_factory_relief_check import (
    VMiterFactoryBottomReliefCheck,
    project_v_miter_factory_bottom_relief_default_check,
)
from .v_miter_factory_radius_ba_check import (
    VMiterFactoryRadiusBADefaultCheck,
    project_v_miter_factory_radius_ba_default_check,
)
from .v_miter_factory_true_t_check import (
    VMiterFactoryPostVTrueTCheck,
    project_v_miter_factory_post_v_true_t_check,
)

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
    material_check: VMiterSourceBoundSharpCheck | None
    factory_mother_check: VMiterFactoryMotherReplacementCheck | None
    material_check_failure: str | None
    full_sheet_check_scene: DrawingScene | None = None
    sharp_t_witness: VMiterSharpThicknessWitness | None = None
    sharp_t_failure: str | None = None
    source_bend_marking_check: VMiterSourceBendMarkingCheck | None = None
    factory_precut_fold_check: VMiterFactoryPrecutFoldCheck | None = None
    factory_precut_fold_failure: str | None = None
    factory_true_t_check: VMiterFactoryPostVTrueTCheck | None = None
    factory_true_t_failure: str | None = None
    first_bend_source_gap_mm: float = 0.0
    second_bend_source_gap_mm: float = 0.0
    # Original same-FinalScene finite BEND owners, not projected CHECK rays.
    first_physical_bend: LinePrimitive | None = None
    second_physical_bend: LinePrimitive | None = None
    first_signed_fold_angle_deg: float = 0.0
    second_signed_fold_angle_deg: float = 0.0
    manufacturing_status: str = V_MITER_GUI_UNCERTIFIED
    trial_defaults: VMiterTrialParameterDefaults | None = None
    factory_radius_ba_check: VMiterFactoryRadiusBADefaultCheck | None = None
    factory_radius_ba_failure: str | None = None
    factory_bottom_relief_check: VMiterFactoryBottomReliefCheck | None = None
    factory_bottom_relief_failure: str | None = None


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


def normalize_operator_v_miter_gui_relief_modes(
    raw: Mapping | None,
    selected_choices: Mapping | None = None,
) -> dict[str, dict[str, str]]:
    """Validate persisted per-physical-corner R/hole CHECK inputs only.

    Old .p6fold snapshots may omit the map: ROUND_R is the default. This is
    never a certified CornerType/Registry rule or an output entitlement.
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise GeometryError("V_MITER_GUI_RELIEF_MODES_INVALID")
    selected = (
        normalize_operator_v_miter_gui_choices(selected_choices)
        if selected_choices is not None else None
    )
    normalized = {}
    for part, corners in raw.items():
        if (type(part) is not str or part not in V_MITER_GUI_PART_KEYS
                or not isinstance(corners, Mapping)):
            raise GeometryError("V_MITER_GUI_RELIEF_PART_INVALID")
        rows = {}
        for corner, mode in corners.items():
            if (type(corner) is not str
                    or corner not in V_MITER_GUI_CORNER_KEYS
                    or type(mode) is not str
                    or mode not in ("ROUND_R", "RELIEF_HOLE")):
                raise GeometryError("V_MITER_GUI_RELIEF_MODE_INVALID")
            if selected is not None and corner not in selected.get(part, {}):
                raise GeometryError("V_MITER_GUI_RELIEF_ORPHAN_CORNER")
            rows[corner] = mode
        if rows:
            normalized[part] = rows
    return normalized


def project_operator_v_miter_gui_selected_relief_modes(
    raw: Mapping | None, selected_choices: Mapping | None,
) -> dict[str, dict[str, str]]:
    """Discard explicit CHECK relief inputs after their V choice is removed."""
    normalized = normalize_operator_v_miter_gui_relief_modes(raw)
    selected = normalize_operator_v_miter_gui_choices(selected_choices)
    return {
        part: keep for part, corners in normalized.items()
        if (keep := {
            corner: mode for corner, mode in corners.items()
            if corner in selected.get(part, {})
        })
    }


def change_operator_v_miter_gui_relief_mode(
    raw: Mapping | None, selected_choices: Mapping | None,
    part_key: str, target_key: str, pair_same: Mapping,
    *, relief_mode: str,
) -> dict[str, dict[str, str]]:
    """Change one physical V corner or a deliberately paired V selection."""
    selected = normalize_operator_v_miter_gui_choices(selected_choices)
    result = normalize_operator_v_miter_gui_relief_modes(raw, selected)
    if (type(part_key) is not str or part_key not in V_MITER_GUI_PART_KEYS
            or type(relief_mode) is not str
            or relief_mode not in ("ROUND_R", "RELIEF_HOLE")
            or not isinstance(pair_same, Mapping)):
        raise GeometryError("V_MITER_GUI_RELIEF_SELECTION_INVALID")
    if target_key in ("top", "bottom"):
        if pair_same.get(target_key) is not True:
            raise GeometryError("V_MITER_GUI_RELIEF_PAIR_IS_SPLIT")
        from .corner_state_transactions import project_operator_corner_pair_members
        targets = project_operator_corner_pair_members(target_key)
    elif target_key in V_MITER_GUI_CORNER_KEYS:
        targets = (target_key,)
    else:
        raise GeometryError("V_MITER_GUI_RELIEF_TARGET_INVALID")
    if any(selected.get(part_key, {}).get(corner) != V_MITER_GUI_CHECK
           for corner in targets):
        raise GeometryError("V_MITER_GUI_RELIEF_SELECTED_V_REQUIRED")
    updated = dict(result.get(part_key, {}))
    for corner in targets:
        updated[corner] = relief_mode
    result[part_key] = updated
    return result


def normalize_operator_v_miter_gui_first_bend_axes(
    raw: Mapping | None,
    selected_choices: Mapping | None = None,
) -> dict[str, dict[str, str]]:
    """Saved operator first BEND choice; never infer X/Y from a 90/90 tie.

    Missing is deliberately UNSPECIFIED, including for legacy projects.
    The choice is a physical-corner input, not a certified V manufacturing token.
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise GeometryError("V_MITER_GUI_FIRST_BEND_MAP_INVALID")
    selected = (
        normalize_operator_v_miter_gui_choices(selected_choices)
        if selected_choices is not None else None
    )
    normalized = {}
    for part, corners in raw.items():
        if (type(part) is not str or part not in V_MITER_GUI_PART_KEYS
                or not isinstance(corners, Mapping)):
            raise GeometryError("V_MITER_GUI_FIRST_BEND_PART_INVALID")
        rows = {}
        for corner, axis in corners.items():
            if (type(corner) is not str or corner not in V_MITER_GUI_CORNER_KEYS
                    or type(axis) is not str or axis not in ("x", "y")):
                raise GeometryError("V_MITER_GUI_FIRST_BEND_AXIS_INVALID")
            if selected is not None and corner not in selected.get(part, {}):
                raise GeometryError("V_MITER_GUI_FIRST_BEND_ORPHAN_CORNER")
            rows[corner] = axis
        if rows:
            normalized[part] = rows
    return normalized


def project_operator_v_miter_gui_selected_first_bend_axes(
    raw: Mapping | None, selected_choices: Mapping | None,
) -> dict[str, dict[str, str]]:
    """Drop a saved first-fold choice when that physical V corner is removed."""
    normalized = normalize_operator_v_miter_gui_first_bend_axes(raw)
    selected = normalize_operator_v_miter_gui_choices(selected_choices)
    return {
        part: keep for part, corners in normalized.items()
        if (keep := {
            corner: axis for corner, axis in corners.items()
            if corner in selected.get(part, {})
        })
    }


def change_operator_v_miter_gui_first_bend_axis(
    raw: Mapping | None, selected_choices: Mapping | None,
    part_key: str, target_key: str, pair_same: Mapping,
    *, first_bend_axis: str,
) -> dict[str, dict[str, str]]:
    """Explicitly select X/Y as the 90-degree first V bend for the real corner."""
    selected = normalize_operator_v_miter_gui_choices(selected_choices)
    result = normalize_operator_v_miter_gui_first_bend_axes(raw, selected)
    if (type(part_key) is not str or part_key not in V_MITER_GUI_PART_KEYS
            or type(first_bend_axis) is not str
            or first_bend_axis not in ("x", "y")
            or not isinstance(pair_same, Mapping)):
        raise GeometryError("V_MITER_GUI_FIRST_BEND_SELECTION_INVALID")
    if target_key in ("top", "bottom"):
        if pair_same.get(target_key) is not True:
            raise GeometryError("V_MITER_GUI_FIRST_BEND_PAIR_IS_SPLIT")
        from .corner_state_transactions import project_operator_corner_pair_members
        targets = project_operator_corner_pair_members(target_key)
    elif target_key in V_MITER_GUI_CORNER_KEYS:
        targets = (target_key,)
    else:
        raise GeometryError("V_MITER_GUI_FIRST_BEND_TARGET_INVALID")
    if any(selected.get(part_key, {}).get(corner) != V_MITER_GUI_CHECK
           for corner in targets):
        raise GeometryError("V_MITER_GUI_FIRST_BEND_SELECTED_V_REQUIRED")
    updated = dict(result.get(part_key, {}))
    for corner in targets:
        updated[corner] = first_bend_axis
    result[part_key] = updated
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


def _physical_corner_bends(
    scene, material, corner_key, *, expected_stations: tuple[float, float] | None = None,
):
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
    # Head/Tail live CHECK supplies the two stations from its *current*
    # PartSpec Fold; scene-only nearest-BEND selection is never a fallback
    # when a physical source binding has been requested.
    if expected_stations is not None:
        if (not isinstance(expected_stations, tuple) or len(expected_stations) != 2
                or any(type(v) not in (float, int) or not math.isfinite(v)
                       for v in expected_stations)):
            raise GeometryError("V_MITER_GUI_BOUND_STATIONS_INVALID")
        station_x, station_y = expected_stations
        vertical = [row for row in vertical if abs(row.p1.x - station_x) <= 1e-6]
        horizontal = [row for row in horizontal if abs(row.p1.y - station_y) <= 1e-6]
        if not vertical or not horizontal:
            raise GeometryError("V_MITER_GUI_PARTSPEC_BEND_SOURCE_MISMATCH")
        if len(vertical) != 1 or len(horizontal) != 1:
            raise GeometryError("V_MITER_GUI_AMBIGUOUS_BOUND_BEND_SOURCE")
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
    if expected_stations is not None and len(choices) != 1:
        raise GeometryError("V_MITER_GUI_BOUND_BENDS_NOT_IN_CORNER")
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
        float(gap_v), float(gap_h), vx, hy,
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


def _partspec_corner_fold_station(
    profile, origin, *, near_min: bool, phase6_role: str | None = None,
    scene_bend_count: int | None = None,
):
    """Resolve the *named* physical fold role at this EndCap corner.

    Head Y is a three-crease chain: its return at the first Y boundary is
    not the lower corner crease. Tail is natively ordered in the opposite
    direction. The immutable PartSpec phase6_key, not the nearest/first
    bend, identifies the physical role. Keyless legacy folds can be
    disambiguated only with at most two source creases on this axis.
    """
    if not profile:
        raise GeometryError("V_MITER_GUI_AUTHORED_FOLD_ANGLE_REQUIRED")
    at = float(origin)
    boundaries = []
    keyed = []
    for row in profile:
        length = getattr(row, "length", None)
        angle = getattr(row, "angle", None)
        key = getattr(row, "phase6_key", None)
        if type(length) not in (int, float) or not math.isfinite(length) or length < 0:
            raise GeometryError("V_MITER_GUI_FOLD_MATERIAL_INVALID")
        if key is not None and (type(key) is not str or not key):
            raise GeometryError("V_MITER_GUI_FOLD_ROLE_INVALID")
        at += length
        keyed.append(key)
        if angle is None:
            continue
        if type(angle) not in (int, float) or not math.isfinite(angle):
            raise GeometryError("V_MITER_GUI_FOLD_ANGLE_MISSING")
        if abs(angle) <= 1e-9:
            continue
        if not 0 < abs(angle) < 180:
            raise GeometryError("V_MITER_GUI_FOLD_ANGLE_OUT_OF_RANGE")
        if boundaries and at - boundaries[-1][0] <= 1e-7:
            raise GeometryError("V_MITER_GUI_AMBIGUOUS_AUTHORED_FOLD_STATION")
        boundaries.append((at, float(angle), key))
    if not boundaries:
        raise GeometryError("V_MITER_GUI_BEND_NOT_LINKED_TO_FOLD")
    named_roles = [key for key in keyed if key is not None]
    if len(named_roles) != len(set(named_roles)):
        raise GeometryError("V_MITER_GUI_DUPLICATE_AUTHORED_FOLD_ROLE")
    if phase6_role is not None and any(keyed):
        matches = [(at, angle) for at, angle, key in boundaries if key == phase6_role]
        if len(matches) != 1:
            raise GeometryError("V_MITER_GUI_NAMED_CORNER_FOLD_REQUIRED")
        return matches[0]
    if phase6_role is not None and not any(keyed):
        if (len(boundaries) >= 3 or
                (scene_bend_count is not None and scene_bend_count >= 3)):
            raise GeometryError("V_MITER_GUI_KEYLESS_MULTIFOLD_AMBIGUOUS")
    chosen = boundaries[0] if near_min else boundaries[-1]
    return chosen[0], chosen[1]


def _bound_endcap_corner_bends(part_spec, scene, material, corner_key):
    """One EndCap role-to-FinalScene BEND binding for live CHECK and replay.

    Product owner: EndCap X roles yl1/endcap_w_core; Head lower Y fw,
    Tail lower Y ybottom1; either upper Y endcap_d_core. Each must be
    exactly one *finite original BEND owner* at that authored station.
    """
    part_key = "tail" if part_spec.is_tail else "head"
    px, py = _endcap_existing_fold_angle_sources(part_spec, part_key)
    minx, miny, _, _ = material.bounds
    vertical, horizontal = _orthogonal_bends(scene)
    left = corner_key.endswith("left")
    bottom = corner_key.startswith("bottom")
    role_x = "yl1" if left else "endcap_w_core"
    role_y = (
        ("ybottom1" if part_spec.is_tail else "fw") if bottom
        else "endcap_d_core"
    )
    x_station, x_angle = _partspec_corner_fold_station(
        px, minx, near_min=left,
        phase6_role=role_x, scene_bend_count=len(vertical),
    )
    y_station, y_angle = _partspec_corner_fold_station(
        py, miny, near_min=bottom,
        phase6_role=role_y, scene_bend_count=len(horizontal),
    )
    sources = _physical_corner_bends(
        scene, material, corner_key, expected_stations=(x_station, y_station),
    )
    *_, x_real, y_real = sources
    if (x_angle != _profile_angle_at_bend(px, x_real.p1.x, minx)
            or y_angle != _profile_angle_at_bend(py, y_real.p1.y, miny)):
        raise GeometryError("V_MITER_GUI_PARTSPEC_FOLD_SOURCE_CHANGED")
    return (*sources, x_angle, y_angle)


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
    *, relief_mode: str = "ROUND_R", run_radius_ba_trial: bool = False,
    first_bend_axis: str | None = None,
) -> VMiterOperatorGUICheck:
    """Project an actual per-corner 2D/3D ideal V, strictly CHECK-only.

    Do not infer a second angle from a BEND drawing (it contains no angles).
    Door has the existing physical fixed-90 four-side flange contract; EndCap
    angles come from its *authored current* X/Y FoldProfileSegment and must
    match the same FinalScene's true BEND station.
    """
    if type(run_radius_ba_trial) is not bool:
        raise GeometryError("V_MITER_GUI_R_BA_TRIAL_FLAG_INVALID")
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
    if isinstance(part_spec, EndCapPartSpec):
        # Real GUI requires an explicit first bend before invoking this
        # read-only Engine API. Preserve old internal CHECK-only calls without
        # selecting a manufacturing order when one uniquely has 90 degrees.
        x_bend, y_bend, x_height, y_height, x_gap, y_gap, x_real, y_real, angle_x, angle_y = (
            _bound_endcap_corner_bends(
                part_spec, render_data.scene, material, corner_key,
            )
        )
        if angle_x * angle_y <= 0:
            raise GeometryError("V_MITER_GUI_OPPOSITE_FOLD_SENSE")
    else:
        # Preserve the pre-existing uncertified Door diagnostic only. Door
        # has NOT received fifth-corner product approval or a new source
        # contract in this Head/Tail first slice.
        x_bend, y_bend, x_height, y_height, x_gap, y_gap, x_real, y_real = _physical_corner_bends(
            render_data.scene, material, corner_key,
        )
        angle_x = angle_y = 90.0
    if not (0 < abs(angle_x) < 180 and 0 < abs(angle_y) < 180):
        raise GeometryError("V_MITER_GUI_FOLD_ANGLE_OUT_OF_RANGE")
    # Once the operator supplies a fold order, no X-first tie break is allowed.
    # This is an Engine source-choice seam, not GUI geometry or a DXF release.
    if first_bend_axis is not None:
        if type(first_bend_axis) is not str or first_bend_axis not in ("x", "y"):
            raise GeometryError("V_MITER_GUI_FIRST_BEND_AXIS_INVALID")
        selected_angle = angle_x if first_bend_axis == "x" else angle_y
        if abs(abs(selected_angle) - 90) > 1e-8:
            raise GeometryError("V_MITER_GUI_SELECTED_FIRST_BEND_NOT_90_DEG")
        if first_bend_axis == "x":
            first, second = (x_bend, "x", x_height), (y_bend, "y", y_height)
            second_angle = abs(angle_y)
        else:
            first, second = (y_bend, "y", y_height), (x_bend, "x", x_height)
            second_angle = abs(angle_x)
    elif abs(abs(angle_x) - 90) <= 1e-8:
        # Legacy internal readonly CHECK only. GUI still rejects a missing
        # operator choice; this can never authorize a fifth CornerType.
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
    # Unverified Engine-owned starting R/BA and R/hole parameters, derived
    # from the REAL thickness and authored second Fold angle. They never
    # modify actual source CUTTING, BEND or certified Registry.
    trial_defaults = project_v_miter_trial_parameter_defaults(
        thickness_mm=t, second_fold_angle_deg=second_angle,
        relief_mode=mode,
    )
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
    # A true original CUTTING perimeter is mandatory for any closed cut
    # proposal; unlike the ideal seam, this result conserves physical stock.
    # Only draw CHECK: no manufacturing CUTTING/BEND/MARKING is generated.
    # A previously manufactured four-type CUTTING may have already cut
    # away the original V apex. That finished polygon is not permission to
    # reconstruct missing stock or claim a real V outline. Preserve the
    # qualified ideal rays and explicitly report the blocked material source.
    factory_mother = None
    try:
        stock_check = project_v_miter_sharp_source_perimeter_check(
            render_data.scene, ideal,
        )
    except GeometryError as original_failure:
        # The four-type factory cut may already have removed the source V
        # apex. Replace only that one old Factory corner using a strictly
        # rebuilt and compared PartSpec mother, never an inferred rectangle.
        try:
            factory_mother = project_v_miter_replaced_factory_corner_check(
                part_spec, render_data, corner_key, ideal,
            )
        except GeometryError as factory_failure:
            stock_check = None
            stock_failure = (
                f"{original_failure}; Factory source: {factory_failure}"
            )
        else:
            stock_check = factory_mother.source_check
            stock_failure = None
    else:
        stock_failure = None
    from .sheetmetal_drawing import PolylinePrimitive
    check = DrawingScene(
        ([
            PolylinePrimitive(stock_check.removed_corner_outline, "CHECK",
                              closed=True, semantic_id="v_miter_removed_stock_check"),
        ] if stock_check is not None else []) + [
            LinePrimitive(ideal.first_flat_miter_ray[0], ideal.first_flat_miter_ray[1], "CHECK", 211),
            LinePrimitive(ideal.second_flat_miter_ray[0], ideal.second_flat_miter_ray[1], "CHECK", 211),
        ]
    )
    whole_sheet = (
        build_v_miter_whole_sheet_check_scene(render_data, stock_check, ideal)
        if stock_check is not None else None
    )
    marking = None
    factory_precut_fold = None
    factory_precut_failure = None
    factory_true_t = None
    factory_true_t_failure = None
    factory_radius_ba = None
    factory_radius_ba_failure = None
    factory_bottom_relief = None
    factory_bottom_relief_failure = None
    if stock_check is not None:
        # These exact objects are the original physical BEND primitives,
        # not the temporary corner-station extensions used for ideal rays.
        real_first = x_real if first[1] == "x" else y_real
        real_second = y_real if second[1] == "y" else x_real
        marking = project_v_miter_source_bend_marking_check(
            render_data.scene, real_first, real_second, stock_check,
        )
        whole_sheet.extend(marking.check_strokes)
        # The original factory topology is independent of the old trimmed
        # BEND line. Where it can be re-proven, draw post-V proposed crease
        # segments as CHECK only, not a fabricated BEND or factory sign-off.
        try:
            factory_precut_fold = project_v_miter_factory_precut_fold_check(
                part_spec, render_data, corner_key, stock_check,
                real_first, real_second, factory_mother,
            )
        except GeometryError as exc:
            factory_precut_failure = str(exc)
        else:
            whole_sheet.extend(factory_precut_fold.first_proposed_segments)
            whole_sheet.extend(factory_precut_fold.second_proposed_segments)
            whole_sheet.extend(factory_precut_fold.first_proposed_alignment_marks)
            whole_sheet.extend(factory_precut_fold.second_proposed_alignment_marks)
            # Apply the Engine's unverified R or circular hole to actual
            # Factory source-clipped V sides, NOT the shorter ideal V tips.
            # This 2D CHECK is not a certified physical 3D R/BA/Fold result.
            try:
                factory_bottom_relief = project_v_miter_factory_bottom_relief_default_check(
                    part_spec, render_data, corner_key, ideal, stock_check,
                    factory_precut_fold, real_first, real_second,
                    trial_defaults, factory_mother,
                )
            except GeometryError as exc:
                factory_bottom_relief_failure = str(exc)
            else:
                whole_sheet.add(PolylinePrimitive(
                    factory_bottom_relief.corrected_remaining_outline,
                    "CHECK", closed=True, color=1,
                    semantic_id="v_miter_engine_factory_r_or_hole_uncertified",
                ))
            # Reuse exactly this factory-proven V remaining stock + Fold as
            # input for the physical-T shadow. No new CNC authority and no
            # separate GUI-owned 3D sheet geometry.
            try:
                factory_true_t = project_v_miter_factory_post_v_true_t_check(
                    part_spec, render_data, corner_key, ideal, stock_check,
                    factory_precut_fold, real_first, real_second,
                    first[0], second[0], factory_mother,
                )
            except GeometryError as exc:
                factory_true_t_failure = str(exc)
            if run_radius_ba_trial:
                if factory_bottom_relief is None:
                    factory_radius_ba_failure = (
                        factory_bottom_relief_failure
                        or "V_MITER_FACTORY_R_BA_SOURCE_RELIEF_REQUIRED"
                    )
                elif factory_true_t is None:
                    factory_radius_ba_failure = (
                        factory_true_t_failure
                        or "V_MITER_FACTORY_R_BA_REQUIRES_SOURCE_TRUE_T"
                    )
                else:
                    try:
                        factory_radius_ba = project_v_miter_factory_radius_ba_default_check(
                            part_spec, render_data, corner_key, ideal, stock_check,
                            factory_precut_fold, real_first, real_second,
                            first[0], second[0], trial_defaults, factory_mother,
                            relief_check=factory_bottom_relief,
                        )
                    except GeometryError as exc:
                        factory_radius_ba_failure = str(exc)
                    # The Factory V cut is a full source-clipped ray;
                    # this curvature trial does NOT invent a corrected
                    # 2D contour or retarget the old ideal-tip trim solver.
    if factory_bottom_relief is None and factory_bottom_relief_failure is None:
        factory_bottom_relief_failure = (
            factory_precut_failure or stock_failure
            or "V_MITER_FACTORY_RELIEF_VERIFIED_MOTHER_REQUIRED"
        )
    if run_radius_ba_trial and factory_radius_ba is None and factory_radius_ba_failure is None:
        factory_radius_ba_failure = (
            factory_precut_failure or stock_failure
            or "V_MITER_FACTORY_R_BA_VERIFIED_MOTHER_REQUIRED"
        )
    # A finite T local sharp-fold cross-section is meaningful only where
    # the original BEND actually contains the physical intersection and
    # one closed source sheet survives. It remains strictly CHECK: the
    # existing analytic bisector does NOT solve real R/BA, 3D cut sidewalls
    # or a certified interference-free weld.
    sharp_t = None
    sharp_t_failure = None
    if stock_check is None:
        sharp_t_failure = "V_MITER_SHARP_T_REQUIRES_VERIFIED_SOURCE_STOCK"
    elif max(x_gap, y_gap) > 1e-7:
        sharp_t_failure = "V_MITER_SHARP_T_ORIGINAL_BEND_HAS_PHYSICAL_GAP"
    else:
        try:
            sharp_t = project_v_miter_sharp_thickness_witness(
                DrawingScene([first[0], second[0]]), first[0], second[0],
                thickness_mm=t,
                first_flange_height_mm=first[2],
                second_flange_height_mm=second[2],
                second_fold_angle_deg=second_angle,
                relief_mode=mode,
            )
        except GeometryError as exc:
            sharp_t_failure = str(exc)
    return VMiterOperatorGUICheck(
        part_key=part_key, corner_key=corner_key,
        first_bend_axis=first[1], second_bend_axis=second[1],
        first_physical_bend=x_real if first[1] == "x" else y_real,
        second_physical_bend=y_real if second[1] == "y" else x_real,
        first_signed_fold_angle_deg=angle_x if first[1] == "x" else angle_y,
        second_signed_fold_angle_deg=angle_y if second[1] == "y" else angle_x,
        first_flange_height_mm=first[2], second_flange_height_mm=second[2],
        second_fold_angle_deg=second_angle, ideal=ideal, check_scene=check,
        material_check=stock_check,
        factory_mother_check=factory_mother,
        material_check_failure=stock_failure,
        full_sheet_check_scene=whole_sheet,
        sharp_t_witness=sharp_t,
        sharp_t_failure=sharp_t_failure,
        source_bend_marking_check=marking,
        factory_precut_fold_check=factory_precut_fold,
        factory_precut_fold_failure=factory_precut_failure,
        factory_true_t_check=factory_true_t,
        factory_true_t_failure=factory_true_t_failure,
        first_bend_source_gap_mm=x_gap if first[1] == "x" else y_gap,
        second_bend_source_gap_mm=y_gap if second[1] == "y" else x_gap,
        trial_defaults=trial_defaults,
        factory_radius_ba_check=factory_radius_ba,
        factory_radius_ba_failure=factory_radius_ba_failure,
        factory_bottom_relief_check=factory_bottom_relief,
        factory_bottom_relief_failure=factory_bottom_relief_failure,
    )
