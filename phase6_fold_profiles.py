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
    """Return an explicit Fold-editor tab set only when topology requires it."""
    key = str(part_key or "")
    if key in ENDCAP_FW_PARTS and resolve_box_assembly_type(snapshot) is CornerTypeId.OVERLAY:
        # OVERLAY has no left/right X bends, so the 3D Fold editor must not offer
        # a fictitious X-axis bend page. Y remains the real editable fold chain.
        return ["Y"]
    return None

def _phase6_normalize_endcap_profile_order(profiles, snapshot, part_key):
    """Migrate legacy stored head/tail canonical profiles without touching extras."""
    copied = {
        "X": clone_profile((profiles or {}).get("X", ())),
        "Y": clone_profile((profiles or {}).get("Y", ())),
    }
    if str(part_key) != "tail":
        return copied
    canonical = ("ybottom1", "endcap_d_core", "fw", "ytop1")
    current = copied.get("Y", [])
    keyed = [seg.get("phase6_key") for seg in current if seg.get("phase6_key")]
    if len(current) != 4 or set(keyed) != set(canonical):
        return copied
    by_key = {seg.get("phase6_key"): dict(seg) for seg in current}
    defaults = build_endcap_xy_profiles(snapshot, part_key="tail")["Y"]
    reordered = []
    for default in defaults:
        key = default.get("phase6_key")
        seg = by_key[key]
        if "angle" in default:
            seg["angle"] = default["angle"]
        else:
            seg.pop("angle", None)
        for name in ("ui_len_add", "core"):
            if name in default:
                seg[name] = default[name]
            else:
                seg.pop(name, None)
        reordered.append(seg)
    copied["Y"] = reordered
    return copied

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
    """Return formed left/right Box Body FW outside widths from the actual fold topology.

    ``len`` is the flat/material FW.  Assembly insertion clearance must use the
    formed outside occupation, so adjacent real bends contribute their actual
    thickness compensation.  Recompute that compensation from the current
    profile instead of trusting stale saved ``ui_len_add`` metadata.
    """
    rows = apply_outside_dimension_compensation(clone_profile(profile), thickness)
    by_key = {str(seg.get("phase6_key") or ""): seg for seg in rows}
    def one(key):
        seg = by_key.get(key)
        if seg is None:
            return None
        return abs(_num(seg.get("len"))) + abs(_num(seg.get("ui_len_add")))
    return one("fw_left"), one("fw_right")


def engine_segment_length_to_ui(seg: Mapping[str, object]):
    """GUI display only; Engine returns the outside Fold length."""
    return manufacturing_api.fold_material_segment_outside_length(seg)


def ui_segment_length_to_engine(seg: Mapping[str, object], ui_value):
    """Convert an operator outside dimension back to the Renderer span."""
    return _ui_len(max(0.0, _num(ui_value) - _num(seg.get("ui_len_add"))))

def read_box_body_profile(profile: Sequence[Mapping[str, object]], original: Mapping[str, object]) -> dict:
    """Convert known Phase6 positions back while allowing extra outer folds."""
    by_key = {str(seg.get("phase6_key")): seg for seg in profile if seg.get("phase6_key")}
    d_segments = [seg for seg in profile if seg.get("core") == "D"]
    w_segments = [seg for seg in profile if seg.get("core") == "W"]
    if len(d_segments) != 2 or len(w_segments) != 1:
        raise ValueError("中央三段必須固定為 D-W-D")

    core_length = lambda seg: _common_dimension_len(original, _num(seg.get("len")) + _num(seg.get("ui_len_add")))
    d_left = core_length(d_segments[0])
    d_right = core_length(d_segments[1])
    if d_left != d_right:
        raise ValueError("D-W-D 的兩個 D 必須相同")
    w_value = core_length(w_segments[0])

    material_profile = cabinet_family_policy.box_body_profile_uses_outside_dimensions(original)
    fw_left_seg = by_key.get("fw_left")
    fw_right_seg = by_key.get("fw_right")
    if fw_left_seg is not None and fw_right_seg is not None:
        fw_left = engine_segment_length_to_ui(fw_left_seg) if material_profile else _ui_len(fw_left_seg.get("len"))
        fw_right = engine_segment_length_to_ui(fw_right_seg) if material_profile else _ui_len(fw_right_seg.get("len"))
        if fw_left != fw_right:
            raise ValueError("左右 FW 必須相同")
        fw_value = fw_left
    elif fw_left_seg is not None:
        fw_value = engine_segment_length_to_ui(fw_left_seg) if material_profile else _ui_len(fw_left_seg.get("len"))
    elif fw_right_seg is not None:
        fw_value = engine_segment_length_to_ui(fw_right_seg) if material_profile else _ui_len(fw_right_seg.get("len"))
    else:
        fw_value = _ui_len(original.get("fw"))

    def known_len(key, fallback):
        seg = by_key.get(key)
        if seg is None:
            return _ui_len(fallback)
        return engine_segment_length_to_ui(seg) if material_profile else _ui_len(seg.get("len"))

    return {
        "zl1": _signed_like(original.get("zl1"), known_len("zl1", original.get("zl1"))),
        "zl2": known_len("zl2", original.get("zl2")),
        "fw": fw_value,
        "d": d_left,
        "w": w_value,
        "zr2": known_len("zr2", original.get("zr2")),
        "zr1": _signed_like(original.get("zr1"), known_len("zr1", original.get("zr1"))),
    }

def can_remove_segment(segment: Mapping[str, object]) -> bool:
    """Keep D/W core and the two global FW fields structurally present."""
    if segment.get("core"):
        return False
    return str(segment.get("phase6_key") or "") not in {"fw_left", "fw_right"}

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
    """Refresh shared semantic core values without changing user Fold topology.

    Once an operator removes/adds a mapped outer segment, that structural choice
    is authoritative. Missing canonical keys are never recreated. Existing
    semantic keys (notably D-W-D/FW) still receive current material lengths.
    """
    merged = clone_profile(profile)
    if not merged:
        return build_box_body_profile(snapshot)
    canonical = {seg.get("phase6_key"): seg for seg in build_box_body_profile(snapshot)}
    for seg in merged:
        key = seg.get("phase6_key")
        source = canonical.get(key)
        if source is None:
            continue
        # D/W/FW remain tied to current global dimensions. Removed outer folds
        # are not resurrected; retained outer mapped folds keep their own edited
        # length unless they are structural shared dimensions.
        if key in {"d_left", "w", "d_right", "fw_left", "fw_right"}:
            seg["len"] = source["len"]
        for name in ("ui_len_add", "core"):
            if name in source:
                seg[name] = source[name]
            else:
                seg.pop(name, None)
    # Cabinet-family topology is authoritative over a previous family's saved
    # outer folds.  In particular, receiving removes terminal ``zr1``; keeping
    # the vault row merely because it existed before the family switch leaks the
    # vault topology back into the live receiving editor.
    merged = cabinet_family_policy.transform_box_body_profile(snapshot, merged)
    apply_outside_dimension_compensation(merged, snapshot.get("t", 2))
    # The D-W-D core is mandatory and cannot be removed through the UI. Reject
    # corrupt files rather than silently replacing their topology.
    d_segments = [seg for seg in merged if seg.get("core") == "D"]
    w_segments = [seg for seg in merged if seg.get("core") == "W"]
    if len(d_segments) != 2 or len(w_segments) != 1:
        raise ValueError("箱身折法資料缺少 D-W-D 核心")
    return merged

