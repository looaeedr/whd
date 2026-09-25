"""Pure Settings-to-Profile projection planning for Fold Designer Phase 5.

This module owns immutable projection/planning only. It does not own Tk,
workspace mutation, rendering, live-sync, manufacturing, or persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)
from phase6_part_navigation import is_box_body_physical_piece_key
from phase6_settings_contracts import FrozenSettingsMapping, freeze_settings_value
from phase6_fold_profiles import (
    _num,
    _ui_len,
    apply_outside_dimension_compensation,
    build_box_body_profile,
    build_endcap_xy_profiles,
    clone_profile,
    merge_box_body_profile,
    _phase6_normalize_endcap_profile_order,
)


def materialize_settings_profile_value(value: Any) -> Any:
    """Return a detached mutable/plain representation of frozen plan data."""
    if isinstance(value, FrozenSettingsMapping):
        return {
            key: materialize_settings_profile_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [materialize_settings_profile_value(item) for item in value]
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    raise TypeError(f"unsupported frozen projection value: {value!r}")


@dataclass(frozen=True)
class DoorPartProjection:
    part_key: str
    column_index: int
    row_index: int
    start_width: float
    start_height: float
    frame_edges: DoorFrameEdges
    formed_width: float
    formed_height: float


@dataclass(frozen=True)
class SettingsProfileProjectionRequest:
    settings_values: Any
    input_snapshot: Any
    available_parts: tuple[str, ...] = ()
    existing_profiles: Any = None
    box_body_profile: Any = ()
    active_part: str = "box_body"
    reset_box_profile: bool = False
    reset_all_profiles: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "settings_values",
            freeze_settings_value(dict(self.settings_values or {})),
        )
        object.__setattr__(
            self,
            "input_snapshot",
            freeze_settings_value(dict(self.input_snapshot or {})),
        )
        object.__setattr__(
            self,
            "existing_profiles",
            freeze_settings_value(dict(self.existing_profiles or {})),
        )
        object.__setattr__(
            self,
            "box_body_profile",
            freeze_settings_value(tuple(self.box_body_profile or ())),
        )
        object.__setattr__(
            self,
            "available_parts",
            tuple(str(key) for key in tuple(self.available_parts or ())),
        )
        object.__setattr__(self, "active_part", str(self.active_part or "box_body"))
        object.__setattr__(self, "reset_box_profile", bool(self.reset_box_profile))
        object.__setattr__(self, "reset_all_profiles", bool(self.reset_all_profiles))


@dataclass(frozen=True)
class SettingsProfileProjectionPlan:
    snapshot: Any
    part_dimensions: Any
    box_body_profile: Any
    part_profiles: Any
    active_part: str
    active_profiles: Any
    derived_sync_required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot", freeze_settings_value(dict(self.snapshot or {}))
        )
        object.__setattr__(
            self,
            "part_dimensions",
            freeze_settings_value(dict(self.part_dimensions or {})),
        )
        object.__setattr__(
            self,
            "box_body_profile",
            freeze_settings_value(tuple(self.box_body_profile or ())),
        )
        object.__setattr__(
            self,
            "part_profiles",
            freeze_settings_value(dict(self.part_profiles or {})),
        )
        object.__setattr__(self, "active_part", str(self.active_part or "box_body"))
        object.__setattr__(
            self,
            "active_profiles",
            freeze_settings_value(dict(self.active_profiles or {})),
        )
        object.__setattr__(
            self, "derived_sync_required", bool(self.derived_sync_required)
        )


def _is_door_part_key(value: object) -> bool:
    key = str(value or "")
    return key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None


def _is_base_plate_part_key(value: object) -> bool:
    key = str(value or "")
    return (
        key == "base_plate"
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
    )


def is_derived_physical_part_key(value: object) -> bool:
    key = str(value or "")
    return (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or is_box_body_physical_piece_key(key)
        or key.startswith("box_body:divider:")
        or (key.startswith("inner_door:") and key.endswith("_frame"))
        or (key.startswith("inner_door:") and key.endswith(":panel"))
    )


def door_part_projections(
    snapshot: Mapping[str, object],
) -> tuple[DoorPartProjection, ...]:
    """Project authoritative multi-door cells without duplicating layout formulas."""
    if not bool(snapshot.get("multi_door_enabled", False)):
        return ()
    columns = tuple(snapshot.get("door_layout_columns") or ())
    if not columns:
        return ()
    normalized = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in columns
    )
    t = _num(snapshot.get("t", 2.0), 2.0)
    fw = _num(snapshot.get("fw", 25.0), 25.0)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot,
        frame_width=fw,
        thickness=t,
    )
    gap_w = _num(snapshot.get("door_gap_w", 3.5), 3.5)
    gap_h = _num(snapshot.get("door_gap_h", 3.5), 3.5)
    rows = []
    for cell in derive_door_layout_cells(normalized):
        formed_w, formed_h = calculate_door_finished_size(
            w=cell.start_width,
            h=cell.start_height,
            t=t,
            fw=door_material_fw,
            gap_w=gap_w,
            gap_h=gap_h,
            frame_edges=cell.edges,
        )
        rows.append(
            DoorPartProjection(
                part_key=door_layout_part_key(cell),
                column_index=cell.column_index,
                row_index=cell.row_index,
                start_width=float(cell.start_width),
                start_height=float(cell.start_height),
                frame_edges=cell.edges,
                formed_width=float(formed_w),
                formed_height=float(formed_h),
            )
        )
    return tuple(rows)


def project_part_dimensions(snapshot: Mapping[str, object]) -> dict[str, dict[str, float]]:
    """Pure projection of Settings/input state into per-part finished dimensions."""
    snapshot = dict(snapshot or {})
    w = _num(snapshot.get("w", 500), 500)
    h = _num(snapshot.get("h", 600), 600)
    d = _num(snapshot.get("d", 200), 200)
    t = _num(snapshot.get("t", 2), 2)
    fw = _num(snapshot.get("fw", 25), 25)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot,
        frame_width=fw,
        thickness=t,
    )
    dims = {
        key: dict(value)
        for key, value in (snapshot.get("part_dimensions") or {}).items()
    }
    dims["box_body"] = {"width": w, "height": h}
    dims["head"] = {"width": w, "height": d}
    dims["tail"] = {"width": w, "height": d}

    for key in tuple(dims):
        if re.fullmatch(r"door_c\d+_r\d+", str(key)) or re.fullmatch(
            r"base_plate_c\d+_r\d+", str(key)
        ):
            dims.pop(key, None)

    door_rows = door_part_projections(snapshot)
    if door_rows:
        dims.pop("door", None)
        for row in door_rows:
            dims[row.part_key] = {
                "width": row.formed_width,
                "height": row.formed_height,
            }
    else:
        door_w, door_h = calculate_door_finished_size(
            w=w,
            h=h,
            t=t,
            fw=door_material_fw,
            gap_w=_num(snapshot.get("door_gap_w", 3.5), 3.5),
            gap_h=_num(snapshot.get("door_gap_h", 3.5), 3.5),
            frame_edges=DoorFrameEdges(),
        )
        dims["door"] = {
            "width": max(1.0, float(door_w)),
            "height": max(1.0, float(door_h)),
        }

    shrink_left = _num(snapshot.get("base_plate_shrink_left", 55), 55)
    shrink_right = _num(snapshot.get("base_plate_shrink_right", 55), 55)
    shrink_top = _num(snapshot.get("base_plate_shrink_top", 55), 55)
    shrink_bottom = _num(snapshot.get("base_plate_shrink_bottom", 55), 55)
    base_w = max(1.0, w - shrink_left - shrink_right)
    base_h = max(1.0, h - shrink_top - shrink_bottom)
    dims["base_plate"] = {"width": base_w, "height": base_h}

    if door_rows:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        for cell in derive_door_layout_cells(columns):
            base_key = door_layout_part_key(cell).replace(
                "door_", "base_plate_", 1
            )
            dims[base_key] = {
                "width": max(
                    1.0,
                    float(cell.start_width) - shrink_left - shrink_right,
                ),
                "height": max(
                    1.0,
                    float(cell.start_height) - shrink_top - shrink_bottom,
                ),
            }
    return dims


def _three_segment_profile(
    left,
    center,
    right,
    *,
    left_key=None,
    center_key=None,
    right_key=None,
):
    items = [
        {"len": _ui_len(left), "angle": -90},
        {"len": _ui_len(center), "angle": -90},
        {"len": _ui_len(right)},
    ]
    for item, key in zip(items, (left_key, center_key, right_key)):
        if key:
            item["phase6_key"] = key
    return items


def build_standard_part_profiles(
    snapshot: Mapping[str, object],
    part_key: str,
) -> dict[str, list[dict]]:
    """Build the existing X/Y profiles for one non-vault panel."""
    dims = dict((snapshot.get("part_dimensions") or {}).get(part_key, {}) or {})
    w = _num(dims.get("width", snapshot.get("w", 500)), 500)
    h = _num(dims.get("height", snapshot.get("h", 600)), 600)

    if _is_door_part_key(part_key):
        t = _num(snapshot.get("t", 2), 2)
        outside_add = max(0.0, 2.0 * t)
        profiles = {
            "X": _three_segment_profile(
                snapshot.get("door_fold_l", 20),
                max(0.0, w - outside_add),
                snapshot.get("door_fold_r", 20),
                left_key="door_fold_l",
                center_key="door_face_w",
                right_key="door_fold_r",
            ),
            "Y": _three_segment_profile(
                snapshot.get("door_fold_b", 20),
                max(0.0, h - outside_add),
                snapshot.get("door_fold_t", 20),
                left_key="door_fold_b",
                center_key="door_face_h",
                right_key="door_fold_t",
            ),
        }
        profiles["X"][1]["core"] = "門包外 W"
        profiles["Y"][1]["core"] = "門包外 H"
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if _is_base_plate_part_key(part_key):
        bend = snapshot.get("base_plate_bend", 20)
        profiles = {
            "X": _three_segment_profile(
                bend,
                w,
                bend,
                left_key="base_bend_l",
                center_key="base_face_w",
                right_key="base_bend_r",
            ),
            "Y": _three_segment_profile(
                bend,
                h,
                bend,
                left_key="base_bend_b",
                center_key="base_face_h",
                right_key="base_bend_t",
            ),
        }
        t = _num(snapshot.get("t", 2), 2)
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if part_key == "indicator_box":
        fold = _num(snapshot.get("indicator_box_fold", 49), 49)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(
                fold,
                x_core,
                fold,
                left_key="ib_fold_l",
                center_key="ib_face_w",
                right_key="ib_fold_r",
            ),
            "Y": _three_segment_profile(
                fold,
                y_core,
                fold,
                left_key="ib_fold_b",
                center_key="ib_face_h",
                right_key="ib_fold_t",
            ),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if part_key == "indicator_door":
        fold = _num(snapshot.get("indicator_door_fold", 19), 19)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(
                fold,
                x_core,
                fold,
                left_key="id_fold_l",
                center_key="id_face_w",
                right_key="id_fold_r",
            ),
            "Y": _three_segment_profile(
                fold,
                y_core,
                fold,
                left_key="id_fold_b",
                center_key="id_face_h",
                right_key="id_fold_t",
            ),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    t = _num(snapshot.get("t", 2), 2)
    profiles = {
        "X": _three_segment_profile(25, w, 25),
        "Y": _three_segment_profile(25, h, 25),
    }
    profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
    profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
    return profiles


def merge_keyed_profiles(existing_profiles, default_profiles):
    """Refresh keyed segments while preserving arbitrary operator-added folds."""
    result = {}
    for axis in ("X", "Y"):
        existing = clone_profile((existing_profiles or {}).get(axis, ()))
        defaults = clone_profile((default_profiles or {}).get(axis, ()))
        if not existing:
            result[axis] = defaults
            continue
        default_by_key = {
            seg.get("phase6_key"): seg
            for seg in defaults
            if seg.get("phase6_key")
        }
        existing_keys = {
            seg.get("phase6_key")
            for seg in existing
            if seg.get("phase6_key")
        }
        if not set(default_by_key).issubset(existing_keys):
            result[axis] = defaults
            continue
        for seg in existing:
            key = seg.get("phase6_key")
            source = default_by_key.get(key)
            if source is None:
                continue
            for name in ("len", "ui_len_add", "core"):
                if name in source:
                    seg[name] = source[name]
                else:
                    seg.pop(name, None)
        result[axis] = existing
    return result


def build_settings_profile_projection(
    request: SettingsProfileProjectionRequest,
) -> SettingsProfileProjectionPlan:
    """Build one deterministic Settings-to-profile plan with no runtime effects."""
    settings_values = materialize_settings_profile_value(request.settings_values)
    snapshot = materialize_settings_profile_value(request.input_snapshot)
    snapshot.update(settings_values)

    part_dimensions = project_part_dimensions(snapshot)
    snapshot["part_dimensions"] = part_dimensions

    current_box = materialize_settings_profile_value(request.box_body_profile)
    box_profile = (
        build_box_body_profile(snapshot)
        if request.reset_box_profile
        else merge_box_body_profile(current_box, snapshot)
    )

    existing_profiles = materialize_settings_profile_value(
        request.existing_profiles
    )
    planned_profiles = {}
    for key in request.available_parts:
        if key == "box_body" or is_derived_physical_part_key(key):
            continue
        defaults = (
            build_endcap_xy_profiles(snapshot, part_key=key)
            if key in {"head", "tail"}
            else build_standard_part_profiles(snapshot, key)
        )
        existing = dict(existing_profiles.get(key, {}) or {})
        merged = (
            defaults
            if request.reset_all_profiles
            else merge_keyed_profiles(existing, defaults)
        )
        if key in {"head", "tail"}:
            merged = _phase6_normalize_endcap_profile_order(
                merged,
                snapshot,
                key,
            )
        planned_profiles[key] = merged

    active_profiles = {}
    if request.active_part == "box_body":
        active_profiles = {"X": box_profile}
    elif (
        request.active_part in planned_profiles
        and not is_derived_physical_part_key(request.active_part)
    ):
        active_profiles = planned_profiles[request.active_part]

    return SettingsProfileProjectionPlan(
        snapshot=snapshot,
        part_dimensions=part_dimensions,
        box_body_profile=box_profile,
        part_profiles=planned_profiles,
        active_part=request.active_part,
        active_profiles=active_profiles,
        derived_sync_required=True,
    )


__all__ = [
    "DoorPartProjection",
    "SettingsProfileProjectionRequest",
    "SettingsProfileProjectionPlan",
    "build_settings_profile_projection",
    "build_standard_part_profiles",
    "door_part_projections",
    "is_derived_physical_part_key",
    "materialize_settings_profile_value",
    "merge_keyed_profiles",
    "project_part_dimensions",
]
