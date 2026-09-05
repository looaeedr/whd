# -*- coding: utf-8 -*-
"""受電箱 cabinet-family policy.

受電箱與金庫型是同層盤體型態。與金庫型相同的幾何仍走既有共用引擎；
本模組只保存受電箱已確認的 family 差異與預設值。
"""
from __future__ import annotations

from copy import deepcopy

from .registry import CabinetTypeRegistration

REGISTRATION = CabinetTypeRegistration(
    canonical_name="受電箱",
    aliases=(),
    module_name=__name__,
    implemented=True,
)

BOX_BODY_DEFAULTS = {
    "w": 800.0,
    "h": 1600.0,
    "d": 350.0,
    "fw": 29.0,
    "zl1": 24.0,
    "zl2": 24.0,
    "zr2": 18.0,
}

DOOR_DEFAULTS = {
    "door_gap_w": 3.5,
    "door_gap_h": 3.5,
    "door_fold_l": 19.0,
    "door_fold_r": 19.0,
    "door_fold_t": 19.0,
    "door_fold_b": 19.0,
}

ENDCAP_DEFAULTS = {
    "ybottom1": 15.0,
}

BASE_PLATE_DEFAULTS = {
    "base_plate_shrink_top": 0.0,
    "base_plate_shrink_bottom": 0.0,
    "base_plate_shrink_left": 0.0,
    "base_plate_shrink_right": 0.0,
    "base_plate_bend": 15.0,
}

DOOR_NAMEPLATE_CENTER_DATUM_TOP = 140.0

FRESH_ASSEMBLY_INTENT = "WRAP_OVERLAY"
DEFAULT_DOOR_LAYOUT_SCOPE = "receiving-main"
DEFAULT_DOOR_LAYOUT_COLUMNS = ((800.0, (1100.0, 500.0)),)
DEFAULT_INNER_DOOR_ID = "upper"
INNER_DOOR_INSET_LEFT = 50.0
INNER_DOOR_INSET_RIGHT = 50.0
INNER_DOOR_INSET_TOP = 50.0


def default_door_layout_columns() -> list[list[object]]:
    """Return the canonical fresh receiving multi-door layout as JSON-safe data."""
    return [[float(width), [float(value) for value in heights]] for width, heights in DEFAULT_DOOR_LAYOUT_COLUMNS]


def default_inner_doors(*, thickness: float, depth: float = BOX_BODY_DEFAULTS["d"], layout_scope: str = DEFAULT_DOOR_LAYOUT_SCOPE) -> list[dict[str, object]]:
    """Return fresh receiving inner-door authoritative topology/config.

    Frame spans are not duplicated here: ``derive_inner_door_frame_sets``
    recomputes them from Door finished geometry and the confirmed 50 mm insets.
    """
    from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role

    dividers = derive_box_body_dividers(
        DEFAULT_DOOR_LAYOUT_COLUMNS,
        depth=float(depth),
        thickness=float(thickness),
        layout_scope=str(layout_scope),
    )
    role = resolve_inner_door_lower_frame_role(DEFAULT_INNER_DOOR_ID, dividers)
    if role is None:
        raise ValueError("receiving fresh layout must provide one horizontal divider")
    return [{
        "stable_id": DEFAULT_INNER_DOOR_ID,
        "cell_key": "0:0",
        "included_frame_sides": ["top", "left", "right"],
        "lower_frame_role": {
            "role": role.role,
            "divider_stable_id": role.divider_stable_id,
        },
    }]


def derive_inner_door_frame_sets(snapshot) -> tuple[object, ...]:
    """Derive receiving inner-door frame spans from canonical Door geometry.

    The upper inner door follows its outer-door cell.  Door gaps are consumed by
    the shared Door finished-size resolver first; the confirmed receiving rule
    then moves the inner-door boundary another 50 mm inward on left/right/top.
    The lower boundary is the shared box-body divider, so receiving produces no
    separate bottom frame.  Returned spans are derived data and are intentionally
    not required to be persisted in project state.
    """
    from ae_engine.inner_door_frames import InnerDoorFrameSet
    from ae_engine.sheetmetal_part_adapters import calculate_door_finished_size, derive_door_layout_cells

    data = dict(snapshot or {})
    columns = list(data.get("door_layout_columns") or ())
    if not columns or not bool(data.get("multi_door_enabled", False)):
        return ()
    normalized = tuple((float(row[0]), tuple(float(v) for v in row[1])) for row in columns)
    cells = {f"{cell.column_index}:{cell.row_index}": cell for cell in derive_door_layout_cells(normalized)}
    t = float(data.get("t", 2.0))
    fw = float(data.get("fw", BOX_BODY_DEFAULTS["fw"]))
    gap_w = float(data.get("door_gap_w", DOOR_DEFAULTS["door_gap_w"]))
    gap_h = float(data.get("door_gap_h", DOOR_DEFAULTS["door_gap_h"]))

    result = []
    for item in list(data.get("inner_doors") or ()):
        if not isinstance(item, dict):
            continue
        stable_id = str(item.get("stable_id") or "").strip()
        cell_key = str(item.get("cell_key") or "").strip()
        if not stable_id or cell_key not in cells:
            continue
        cell = cells[cell_key]
        outer_w, outer_h = calculate_door_finished_size(
            w=cell.start_width, h=cell.start_height, t=t, fw=fw,
            gap_w=gap_w, gap_h=gap_h, frame_edges=cell.edges,
        )
        inner_w = float(outer_w) - INNER_DOOR_INSET_LEFT - INNER_DOOR_INSET_RIGHT
        inner_h = float(outer_h) - INNER_DOOR_INSET_TOP
        if inner_w <= 0 or inner_h <= 0:
            raise ValueError("receiving inner-door 50 mm inset leaves no valid finished area")
        included = tuple(
            side for side in (str(v).strip().lower() for v in item.get("included_frame_sides", ("top", "left", "right")))
            if side != "bottom"
        )
        spans = {
            "top": inner_w,
            "left": inner_h,
            "right": inner_h,
        }
        result.append(InnerDoorFrameSet(
            inner_door_id=stable_id,
            spans={side: spans[side] for side in included},
            thickness=t,
            included_sides=included,
        ))
    return tuple(result)


def shared_baseline_feature_model_name() -> str:
    """Receiving reuses certified Vault baseline features, not Vault family state."""
    return "金庫型"


def apply_family_defaults(snapshot):
    """套用受電箱 *fresh family* 預設；未列出的全域值保持原樣。

    Saved-project state is restored by the project/runtime adapters and must not
    call this helper as a migration normalizer.
    """
    result = deepcopy(dict(snapshot or {}))
    result.pop("cabinet_type", None)
    result["model"] = "受電箱"
    result.update(BOX_BODY_DEFAULTS)
    result.update(DOOR_DEFAULTS)
    result.update(ENDCAP_DEFAULTS)
    result.update(BASE_PLATE_DEFAULTS)
    result["assembly_type"] = FRESH_ASSEMBLY_INTENT
    result["multi_door_enabled"] = True
    result["door_layout_scope"] = DEFAULT_DOOR_LAYOUT_SCOPE
    result["door_layout_columns"] = default_door_layout_columns()
    result["door_handle_edges"] = deepcopy(dict(result.get("door_handle_edges") or {}))
    result["door_nameplate_center_datum_top"] = float(DOOR_NAMEPLATE_CENTER_DATUM_TOP)
    try:
        thickness = float(result.get("t", 2.0))
    except (TypeError, ValueError):
        thickness = 2.0
    result["inner_doors"] = default_inner_doors(
        thickness=thickness, depth=float(result["d"]), layout_scope=DEFAULT_DOOR_LAYOUT_SCOPE
    )
    return result


def is_receiving_snapshot(snapshot) -> bool:
    """Recognize the one model Source of Truth plus the short-lived legacy split field."""
    data = dict(snapshot or {})
    model = str(data.get("model") or "").strip()
    if model == "受電箱":
        return True
    return str(data.get("cabinet_type") or "").strip() == "受電箱"


def resolve_box_body_structure_state(state=None):
    """受電箱固定使用既有側背分離結構，不建立第二套結構引擎。"""
    from phase6_box_body_structure import (
        BoxBodyStructureType,
        normalize_box_body_structure_state,
        set_active_structure,
        set_structure_locked,
    )

    result = normalize_box_body_structure_state(state)
    result = set_active_structure(result, BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT)
    result = set_structure_locked(result, True)
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg.setdefault("side_rear_bend", 15.0)
    # 受電箱後面板是無折彎平板；已確認成形/下料寬 = W - 2.5T。
    cfg["back_width_comp_t"] = 2.5
    return result


def family_fixes_box_body_structure() -> bool:
    """Receiving owns a fixed side/back-split topology, independent of UI lock state."""
    return True


def _side_back_config(state=None):
    from phase6_box_body_structure import BoxBodyStructureType

    result = resolve_box_body_structure_state(state)
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    cfg.setdefault("bottom_external_wrap", True)
    cfg.setdefault("bottom_relief_reserve_u", 2.0)
    cfg.setdefault("bottom_relief_reserve_v", 1.0)
    return result, cfg


def bottom_external_wrap_enabled(state=None) -> bool:
    """Return the receiving EndCap lower-face external-WRAP option."""
    _state, cfg = _side_back_config(state)
    return bool(cfg.get("bottom_external_wrap", True))


def set_bottom_external_wrap(state, enabled: bool) -> dict:
    """Return a canonical structure-state copy with lower WRAP enabled/disabled."""
    result, cfg = _side_back_config(state)
    cfg["bottom_external_wrap"] = bool(enabled)
    return result


def bottom_relief_reserves(state=None) -> tuple[float, float]:
    """Return explicit millimetre reserves ``(X, Y)`` for receiving lower WRAP."""
    _state, cfg = _side_back_config(state)
    try:
        reserve_u = max(0.0, float(cfg.get("bottom_relief_reserve_u", 2.0)))
    except (TypeError, ValueError):
        reserve_u = 2.0
    try:
        reserve_v = max(0.0, float(cfg.get("bottom_relief_reserve_v", 1.0)))
    except (TypeError, ValueError):
        reserve_v = 1.0
    return reserve_u, reserve_v


def set_bottom_relief_reserves(state, *, reserve_u=None, reserve_v=None) -> dict:
    """Return a canonical structure-state copy with explicit X/Y reserve values."""
    result, cfg = _side_back_config(state)
    if reserve_u is not None:
        cfg["bottom_relief_reserve_u"] = max(0.0, float(reserve_u))
    if reserve_v is not None:
        cfg["bottom_relief_reserve_v"] = max(0.0, float(reserve_v))
    return result


def transform_box_body_profile(profile):
    """受電箱沿用金庫型 Fold Chain，只移除終端 zr1。"""
    rows = [dict(row) for row in (profile or ()) if str(row.get("phase6_key") or "") != "zr1"]
    if rows:
        rows[-1].pop("angle", None)
    return rows


def endcap_depth_comp_t() -> float:
    """受電箱 ybottom1 外貼 W，EndCap D 材料核心固定採 D-2T。"""
    return 2.0


def bottom_effective_fw(*, side_rear_bend: float, thickness: float) -> float:
    return float(side_rear_bend) + float(thickness)


def endcap_bottom_selection():
    """受電箱封頭/尾下方永遠以 STANDARD 15×15 為母體。

    外側包覆 WRAP 是獨立 Joint/Registry 衍生，不得把下方母體改成
    INSERT_OVERLAY 或其他組合方式。
    """
    from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, CrossCornerMode
    return CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)


def endcap_corner_policy(*, frame_width: float, thickness: float, side_rear_bend: float):
    """受電箱封頭尾：上方依組合語意；下方 STANDARD，WRAP 另由 Joint Registry 衍生。"""
    from ae_engine.corner_type_ui import known_model_corner_state
    from ae_engine.sheetmetal_geometry import FourCornerTypePolicy

    top = known_model_corner_state(("head",), cabinet_family="受電箱")["head"]
    bottom = endcap_bottom_selection()
    return FourCornerTypePolicy(
        bottom_left=bottom,
        bottom_right=bottom,
        top_left=top["top_left"],
        top_right=top["top_right"],
        fw=float(frame_width),
        bottom_fw=bottom_effective_fw(
            side_rear_bend=float(side_rear_bend), thickness=float(thickness)
        ),
    )


def box_body_profile_uses_outside_dimensions() -> bool:
    """Receiving operator BoxBody Fold values enter the family as outside dimensions."""
    return True


def endcap_fw_profile_uses_material_dimensions() -> bool:
    """Receiving EndCap Y Fold Profile stores FW in material space."""
    return True


def supports_bottom_wrap_controls() -> bool:
    return True


def default_bottom_wrap_enabled() -> bool:
    return True


def bottom_relief_registry_applicable(state=None) -> bool:
    """Family-side applicability input only; Registry remains the answer owner."""
    from phase6_box_body_structure import BoxBodyStructureType
    resolved = resolve_box_body_structure_state(state)
    return resolved.get("active_type") == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
