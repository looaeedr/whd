# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Phase6 Fold Profile 與 linked EndCap mating chain 的單一所有權模組。"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping, Sequence

from ae_engine.sheetmetal_geometry import CornerTypeId
from ae_engine.contracts import FoldProfileSegment
from ae_engine.cabinet_types import policy as cabinet_family_policy
from phase6_endcap_semantics import (
    ENDCAP_FW_PARTS, normalize_endcap_fw_state, resolve_endcap_fw, resolve_box_assembly_type,
)

from ae_engine import manufacturing_api
from ae_engine.manufacturing_api import (
    BOX_BODY_TURNS as _BOX_BODY_TURNS,
    apply_outside_dimension_compensation as _engine_apply_outside_dimension_compensation,
    outside_profile_to_material as _engine_outside_profile_to_material,
    build_box_body_fold_profile as _engine_build_box_body_fold_profile,
    box_body_profile_to_fold_segments as _engine_box_body_profile_to_fold_segments,
)

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)

def _ui_len(value):
    """The user's fold editor displays operator fold lengths as integers."""
    return int(round(abs(_num(value))))

def _common_dimension_len(snapshot, value):
    """Common Receiving dimensions keep precision; manual fold rows keep their UI contract."""
    if snapshot.get("active_mode") == "quantity" and snapshot.get("receiving_quantity_box"):
        return abs(_num(value))
    return _ui_len(value)

def _has_real_bend(segment: Mapping[str, object]) -> bool:
    """A segment owns the bend on its right boundary when angle is non-zero."""
    return "angle" in segment and abs(_num(segment.get("angle"))) > 1e-9

def apply_outside_dimension_compensation(profile: Sequence[dict], thickness) -> list[dict]:
    """Compatibility entry; the real adjacent-bend rule is Engine-owned."""
    return _engine_apply_outside_dimension_compensation(profile, thickness)

def _outside_profile_to_material(profile: Sequence[dict], thickness, *, preserve_core_precision=False, preserve_precision=False) -> list[dict]:
    """Compatibility entry for canonical material conversion."""
    return _engine_outside_profile_to_material(
        profile, thickness,
        preserve_core_precision=preserve_core_precision,
        preserve_precision=preserve_precision,
    )

def build_box_body_profile(snapshot: Mapping[str, object]) -> list[dict]:
    """Read the same canonical material Fold as the headless Engine client."""
    return _engine_build_box_body_fold_profile(snapshot)

def _signed_like(original, magnitude):
    return -abs(magnitude) if _num(original) < 0 else abs(magnitude)

def build_endcap_profile(snapshot: Mapping[str, object]) -> list[dict]:
    """Legacy GUI entry; canonical three-row Fold belongs to Engine."""
    return manufacturing_api.build_endcap_editor_simple_profile(snapshot)


def read_endcap_profile(profile: Sequence[Mapping[str, object]]) -> dict:
    """Legacy GUI readback; source role policy belongs to Engine."""
    return manufacturing_api.read_endcap_editor_simple_profile(profile)


def build_endcap_xy_profiles(snapshot: Mapping[str, object], *, part_key: str = "head") -> dict[str, list[dict]]:
    """GUI compatibility: physical X/Y Fold is built only by public Engine."""
    return manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key=part_key)


def _phase6_fold_tabs_for_part(snapshot: Mapping[str, object], part_key: str):
    """GUI compatibility: Engine decides which physical Fold axes exist."""
    return manufacturing_api.endcap_editor_fold_tabs(snapshot, part_key)


def _phase6_normalize_endcap_profile_order(profiles, snapshot, part_key):
    """GUI compatibility: only Engine may reconcile legacy physical BEND order."""
    return manufacturing_api.normalize_endcap_profile_order(profiles, snapshot, part_key)


def read_endcap_xy_profiles(profiles: Mapping[str, Sequence[Mapping[str, object]]], original_snapshot: Mapping[str, object]) -> dict:
    """Legacy editor entry; Engine alone converts X/Y material into cabinet outside dimensions."""
    return manufacturing_api.resolve_endcap_xy_outside_dimensions(profiles, original_snapshot)


def engine_angle_to_ui(value):
    """Return the exact operator-facing angle for the stored engine convention."""
    angle = _num(value)
    if angle in (90.0, -90.0):
        angle = -angle
    return int(angle) if float(angle).is_integer() else angle

def ui_angle_to_engine(value):
    """Preserve the operator input through the existing engine sign convention."""
    angle = _num(value)
    if angle in (90.0, -90.0):
        angle = -angle
    return int(angle) if float(angle).is_integer() else angle

def formed_box_body_fw_widths(profile: Sequence[Mapping[str, object]], thickness) -> tuple[float | None, float | None]:
    """Read-only formed FW witness; Engine recomputes actual adjacent BEND."""
    return manufacturing_api.formed_box_body_fw_widths(profile, thickness)


def engine_segment_length_to_ui(seg: Mapping[str, object]):
    """GUI display only; Engine returns the outside Fold length."""
    return manufacturing_api.fold_material_segment_outside_length(seg)


def ui_segment_length_to_engine(seg: Mapping[str, object], ui_value):
    """GUI edit conversion uses the Engine material-length contract."""
    return manufacturing_api.box_body_ui_segment_length_to_material(seg, ui_value)


def read_box_body_profile(profile: Sequence[Mapping[str, object]], original: Mapping[str, object]) -> dict:
    """GUI reports canonical D/W/FW dimensions resolved by Engine."""
    return manufacturing_api.read_box_body_outside_dimensions(profile, original)


def can_remove_segment(segment: Mapping[str, object]) -> bool:
    """GUI only requests the Engine's structural-fold removal permission."""
    return manufacturing_api.can_remove_box_body_fold_segment(segment)


def clone_profile(profile: Sequence[Mapping[str, object]]) -> list[dict]:
    return deepcopy(list(profile))


def profile_to_fold_segments(profile: Sequence[Mapping[str, object]]):
    """Compatibility entry: do not create a second manufacturing Fold DTO."""
    return _engine_box_body_profile_to_fold_segments(profile)

def _phase6_is_untouched_canonical_box_profile(
    profile: Sequence[Mapping[str, object]],
    snapshot: Mapping[str, object] | None = None,
) -> bool:
    """Legacy selector compatibility; Engine owns physical mating topology."""
    return manufacturing_api.is_canonical_box_body_mating_profile(profile, snapshot)


def _phase6_box_mating_front_chain(
    profile: Sequence[Mapping[str, object]],
) -> list[dict]:
    """Legacy selector compatibility; Engine owns arbitrary front turns."""
    return manufacturing_api.box_body_front_mating_fold_chain(profile)


def build_linked_endcap_xy_profiles(
    snapshot: Mapping[str, object], box_profile: Sequence[Mapping[str, object]],
):
    """GUI forwards input profiles; Engine owns the real Head/Tail mating Fold."""
    return manufacturing_api.build_linked_endcap_xy_fold_profiles(snapshot, box_profile)


def merge_box_body_profile(profile: Sequence[Mapping[str, object]], snapshot: Mapping[str, object]) -> list[dict]:
    """Legacy Fold editor entry; Engine alone refreshes physical core/topology."""
    return manufacturing_api.merge_box_body_fold_profile(profile, snapshot)
