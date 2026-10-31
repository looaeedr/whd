# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Pure Settings-to-Profile projection planning for Fold Designer Phase 5.

This module owns immutable projection/planning only. It does not own Tk,
workspace mutation, rendering, live-sync, manufacturing, or persistence.
"""
# 3D 操作包外輸入是唯一權威；2D/3D/製造共享正反算契約，但輸出不能反寫使用者輸入。
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.manufacturing_api import (
    DoorPartProjection, door_part_projections, project_part_dimensions,
    build_standard_part_fold_profiles, merge_keyed_fold_profiles,
)
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
        or key.startswith("base_plate:fixing_plate:")
        or key.startswith("base_plate:nfb_layer:")
        or key.startswith("nfb_pad:")
        or is_box_body_physical_piece_key(key)
        or key.startswith("box_body:divider:")
        or (key.startswith("inner_door:") and key.endswith("_frame"))
        or (key.startswith("inner_door:") and key.endswith(":panel"))
    )






def build_standard_part_profiles(
    snapshot: Mapping[str, object], part_key: str,
) -> dict[str, list[dict]]:
    """Settings view routes custom extension or forwards standard Fold to Engine."""
    from phase6_custom_parts import is_custom_part
    if is_custom_part(part_key):
        from phase6_custom_fold_profiles import build_custom_part_profiles
        return build_custom_part_profiles(snapshot, part_key)
    return build_standard_part_fold_profiles(snapshot, part_key)


def merge_keyed_profiles(existing_profiles, default_profiles):
    """Phase6 compatibility: Engine alone reconciles keyed material Fold rows."""
    return merge_keyed_fold_profiles(existing_profiles, default_profiles)


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
