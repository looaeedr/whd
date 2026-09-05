# -*- coding: utf-8 -*-
"""自訂截角編輯器的純狀態工具。

Tkinter 畫面仍由 gui.py 負責；本模組只保存可在沒有顯示環境時測試的
截角狀態與模型判斷。
"""
from __future__ import annotations

from dataclasses import dataclass

from .sheetmetal_geometry import (
    Vec2,
    CornerTypeId,
    CornerTypeSelection,
    FourCornerTypePolicy,
    ReliefConfig,
    EDITABLE_CORNER_TYPE_IDS,
    CrossCornerMode,
    CornerDirection,
    normalize_corner_selection,
    resolve_endcap_assembly_semantics,
)
from .sheetmetal_part_adapters import (
    build_base_plate_result,
    build_door_result,
    build_endcap_result,
    build_unknown_endcap_result,
)

CUSTOM_MODEL_NAME = "自訂"
LEGACY_CUSTOM_MODEL_NAMES = ("未知類型",)
# 舊 API 名稱保留給既有呼叫端；使用者介面一律顯示「自訂」。
UNKNOWN_MODEL_NAME = CUSTOM_MODEL_NAME
CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
CORNER_LABELS = {
    "top_left": "左上",
    "top_right": "右上",
    "bottom_left": "左下",
    "bottom_right": "右下",
}
CORNER_PAIR_KEYS = ("top", "bottom")
CORNER_PAIR_CORNERS = {
    "top": ("top_left", "top_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


@dataclass(frozen=True)
class CornerTypePreviewGeometry:
    """Canonical thumbnail cropped directly from existing CUTTING/BEND paths.

    ``cut_paths`` and ``bend_paths`` are literal clipped linework from an
    already-verified Vault part.  No preview-only corner shape is reconstructed.
    """
    cut_paths: tuple[tuple[Vec2, ...], ...]
    bend_paths: tuple[tuple[Vec2, ...], ...]
    span: float
    source_part: str
    source_corner: str


@dataclass(frozen=True)
class _CanonicalCornerSource:
    result: object
    source_part: str
    source_corner: str


def _existing_corner_source(selection: CornerTypeSelection) -> _CanonicalCornerSource:
    """直接使用正式製造幾何路徑建立截角預覽，避免另外畫一套假幾何。"""
    selection = normalize_corner_selection(selection)
    policy = FourCornerTypePolicy(
        bottom_left=selection,
        bottom_right=selection,
        top_left=selection,
        top_right=selection,
        fw=25.0,
    )
    try:
        x_topology = resolve_endcap_assembly_semantics(selection).x_topology
    except ValueError:
        # CROSS/C01~C04 are corner-shape previews, not EndCap assembly types.
        x_topology = "folded"
    result = build_unknown_endcap_result(
        w=200.0, d=200.0, t=2.0, fw=25.0,
        yl1=15.0, yr1=15.0, ytop1=16.0, ybottom1=15.0,
        corner_policy=policy, x_topology=x_topology,
    )
    return _CanonicalCornerSource(
        result,
        f"semantic:{selection.type_id.value}",
        "top_left",
    )

def _extract_existing_corner_removed_extent(source: _CanonicalCornerSource) -> float:
    """Measure the real removed-corner extent only to choose one shared crop window."""
    from shapely.geometry import Polygon, box

    result = source.result
    material = Polygon([(p.x, p.y) for p in result.outline])
    blank = box(0.0, 0.0, float(result.width), float(result.height))
    removed = blank.difference(material)
    parts = list(removed.geoms) if hasattr(removed, "geoms") else [removed]
    tol = 1e-7
    if source.source_corner == "bottom_left":
        candidates = [p for p in parts if abs(p.bounds[0]) <= tol and abs(p.bounds[1]) <= tol]
        if len(candidates) != 1:
            raise ValueError(f"{source.source_part} 左下預期只有一個截角，實際找到 {len(candidates)} 個")
        b = candidates[0].bounds
        return max(float(b[2]), float(b[3]))
    if source.source_corner == "top_left":
        h = float(result.height)
        candidates = [p for p in parts if abs(p.bounds[0]) <= tol and abs(p.bounds[3] - h) <= tol]
        if len(candidates) != 1:
            raise ValueError(f"{source.source_part} 左上預期只有一個截角，實際找到 {len(candidates)} 個")
        b = candidates[0].bounds
        return max(float(b[2]), h - float(b[1]))
    raise ValueError(f"不支援的截角預覽來源角落：{source.source_corner}")


def _canonical_catalog_span(padding: float = 7.0) -> float:
    """One shared physical crop size derived from the existing source corners."""
    max_extent = max(
        _extract_existing_corner_removed_extent(
            _existing_corner_source(CornerTypeSelection(type_id))
        )
        for type_id in EDITABLE_CORNER_TYPE_IDS
    )
    return max_extent + max(2.0, float(padding))


def _canonical_transform(source: _CanonicalCornerSource, x: float, y: float) -> Vec2:
    if source.source_corner == "bottom_left":
        return Vec2(float(x), float(y))
    if source.source_corner == "top_left":
        return Vec2(float(x), float(source.result.height) - float(y))
    raise ValueError(f"不支援的截角預覽來源角落：{source.source_corner}")


def _line_paths(geometry, source: _CanonicalCornerSource) -> tuple[tuple[Vec2, ...], ...]:
    """Normalize LineString/MultiLineString crop output into local Vec2 paths."""
    if geometry.is_empty:
        return ()
    if geometry.geom_type == "LineString":
        geoms = [geometry]
    elif hasattr(geometry, "geoms"):
        geoms = [g for g in geometry.geoms if g.geom_type == "LineString"]
    else:
        geoms = []
    paths = []
    for geom in geoms:
        coords = tuple(_canonical_transform(source, x, y) for x, y in geom.coords)
        if len(coords) >= 2:
            paths.append(coords)
    return tuple(paths)


def _crop_existing_corner_linework(
    source: _CanonicalCornerSource, span: float
) -> tuple[tuple[tuple[Vec2, ...], ...], tuple[tuple[Vec2, ...], ...]]:
    """Clip the source part's literal final CUTTING outline and BEND segments."""
    from shapely.geometry import LineString, box
    from shapely.ops import linemerge

    result = source.result
    if source.source_corner == "bottom_left":
        crop = box(0.0, 0.0, span, span)
    elif source.source_corner == "top_left":
        h = float(result.height)
        crop = box(0.0, h - span, span, h)
    else:
        raise ValueError(f"不支援的截角預覽來源角落：{source.source_corner}")

    outline = LineString([(p.x, p.y) for p in result.outline])
    cut_paths = _line_paths(linemerge(outline.intersection(crop)), source)

    bends = []
    for bend in result.bends:
        segment = LineString([(bend.p1.x, bend.p1.y), (bend.p2.x, bend.p2.y)])
        bends.extend(_line_paths(segment.intersection(crop), source))
    return cut_paths, tuple(bends)


def _swap_path_axes(paths: tuple[tuple[Vec2, ...], ...]) -> tuple[tuple[Vec2, ...], ...]:
    return tuple(tuple(Vec2(p.y, p.x) for p in path) for path in paths)


def build_corner_type_preview_geometry(
    selection: CornerTypeSelection,
    *,
    padding: float = 7.0,
) -> CornerTypePreviewGeometry:
    """Crop literal existing CUTTING/BEND linework into one canonical corner view."""
    selection = normalize_corner_selection(selection)
    source = _existing_corner_source(selection)
    span = _canonical_catalog_span(padding)
    cut_paths, bend_paths = _crop_existing_corner_linework(source, span)

    return CornerTypePreviewGeometry(
        cut_paths=cut_paths,
        bend_paths=bend_paths,
        span=span,
        source_part=source.source_part,
        source_corner=source.source_corner,
    )

def normalize_custom_model_name(name) -> str:
    text = str(name or "").strip()
    if text == CUSTOM_MODEL_NAME or text in LEGACY_CUSTOM_MODEL_NAMES:
        return CUSTOM_MODEL_NAME
    return text


def with_custom_model(models) -> list[str]:
    """模型清單只暴露一個使用者可見的「自訂」。"""
    result = []
    seen = set()
    for value in models or ():
        text = normalize_custom_model_name(value)
        if not text or text in seen or text == CUSTOM_MODEL_NAME:
            continue
        result.append(text)
        seen.add(text)
    result.append(CUSTOM_MODEL_NAME)
    return result


def is_custom_model(name) -> bool:
    """新「自訂」與舊「未知類型」都視為自訂模式。"""
    return normalize_custom_model_name(name) == CUSTOM_MODEL_NAME


# 舊函式名保留給既有呼叫端；新程式可改用 custom 命名。
with_unknown_model = with_custom_model
is_unknown_model = is_custom_model


def known_model_corner_state(part_keys, cabinet_family="金庫型") -> dict[str, dict[str, CornerTypeSelection]]:
    """回傳已知盤體固定板件的已認證截角規則。

    Source of Truth 已移至 ``certified_relief_registry``；此函式只保留
    舊 GUI/Bridge 呼叫介面。未知 family 不得靜默借用金庫型公式。
    """
    from .certified_relief_registry import lookup_certified_corner_state

    return lookup_certified_corner_state(
        cabinet_family=cabinet_family,
        part_keys=tuple(part_keys or ()),
    )


def new_manual_corner_state(part_keys) -> dict[str, dict[str, CornerTypeSelection]]:
    return {
        str(part): {key: CornerTypeSelection(CornerTypeId.CROSS) for key in CORNER_KEYS}
        for part in part_keys
    }



def new_manual_corner_pair_same_state(part_keys) -> dict[str, dict[str, bool]]:
    """手動編輯預設讓上方左右共用一組選擇、下方左右共用另一組。"""
    return {str(part): {"top": True, "bottom": True} for part in part_keys}


def set_manual_corner_pair_same(
    state: dict[str, CornerTypeSelection],
    pair_same: dict[str, bool],
    pair_key: str,
    enabled: bool,
) -> None:
    """Toggle pair grouping; rejoining copies the left selection to the right."""
    if pair_key not in CORNER_PAIR_CORNERS:
        raise ValueError(f"未知的截角成對位置：{pair_key}")
    enabled = bool(enabled)
    pair_same[pair_key] = enabled
    if enabled:
        left_key, right_key = CORNER_PAIR_CORNERS[pair_key]
        state[right_key] = state[left_key]


def apply_manual_corner_selection(
    state: dict[str, CornerTypeSelection],
    pair_same: dict[str, bool],
    target_key: str,
    selection: CornerTypeSelection,
) -> None:
    """Apply one edit to a grouped pair or one explicitly split physical corner."""
    selection = normalize_corner_selection(selection)
    if target_key in CORNER_PAIR_CORNERS:
        if not pair_same.get(target_key, True):
            raise ValueError(f"截角成對位置 {target_key} 已拆分，請指定左側或右側")
        for corner_key in CORNER_PAIR_CORNERS[target_key]:
            state[corner_key] = selection
        return
    if target_key not in CORNER_KEYS:
        raise ValueError(f"未知的截角目標：{target_key}")
    state[target_key] = selection



BOX_ASSEMBLY_TYPE_IDS = (
    CornerTypeId.INSERT,
    CornerTypeId.OVERLAY,
    CornerTypeId.INSERT_OVERLAY,
)


def default_selection_for_box_assembly(type_id: CornerTypeId) -> CornerTypeSelection:
    """Return the default top-corner parameters for one cabinet assembly type."""
    type_id = CornerTypeId(type_id)
    if type_id is CornerTypeId.INSERT:
        return CornerTypeSelection(CornerTypeId.INSERT, amount_t=1.0)
    if type_id is CornerTypeId.OVERLAY:
        return CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=1.0)
    if type_id is CornerTypeId.INSERT_OVERLAY:
        return CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY, amount_t=1.0,
            secondary_retain_t=0.5, secondary_depth_t=2.0,
        )
    raise ValueError(f"不支援的箱體組合方式：{type_id}")


def assembly_type_from_corner_state(
    corner_state: dict[str, dict[str, CornerTypeSelection]],
    default: CornerTypeId = CornerTypeId.INSERT_OVERLAY,
) -> CornerTypeId:
    """Migrate legacy projects by reading the shared EndCap top-corner semantic."""
    found = []
    for part in ("head", "tail"):
        state = (corner_state or {}).get(part) or {}
        for key in ("top_left", "top_right"):
            raw = state.get(key)
            if raw is None:
                continue
            try:
                selection = normalize_corner_selection(raw)
            except Exception:
                continue
            if selection.type_id in BOX_ASSEMBLY_TYPE_IDS:
                found.append(selection.type_id)
    if not found:
        return CornerTypeId(default)
    # Legacy files normally agree. If they do not, any outside relationship
    # must remain outside-safe instead of silently reducing the cabinet height.
    if CornerTypeId.INSERT_OVERLAY in found:
        return CornerTypeId.INSERT_OVERLAY
    if CornerTypeId.OVERLAY in found:
        return CornerTypeId.OVERLAY
    return CornerTypeId.INSERT


def apply_box_assembly_type(
    corner_state: dict[str, dict[str, CornerTypeSelection]],
    pair_same: dict[str, dict[str, bool]],
    type_id: CornerTypeId,
    *,
    reset_bottom_defaults: bool = False,
) -> None:
    """Apply one box-level assembly type to EndCap top corners only.

    Head/tail remain free to split left/right *parameters*. Their type is owned
    by the box assembly selection. Bottom corners are independent manufacturing
    corners and default to CROSS/extra-cut without participating in box height.
    """
    type_id = CornerTypeId(type_id)
    if type_id not in BOX_ASSEMBLY_TYPE_IDS:
        raise ValueError(f"不支援的箱體組合方式：{type_id}")
    default_top = default_selection_for_box_assembly(type_id)
    if type_id is CornerTypeId.OVERLAY:
        default_bottom = CornerTypeSelection(
            CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
            direction=CornerDirection.WIDTH, amount_t=1.5,
        )
    else:
        default_bottom = CornerTypeSelection(
            CornerTypeId.CROSS, cross_mode=CrossCornerMode.EXTRA_CUT,
            direction=CornerDirection.BOTH, amount_t=0.5,
        )
    for part in ("head", "tail"):
        state = corner_state.setdefault(part, {})
        pairs = pair_same.setdefault(part, {"top": True, "bottom": True})
        pairs.setdefault("top", True); pairs.setdefault("bottom", True)
        for key in ("top_left", "top_right"):
            current = state.get(key)
            try:
                current = normalize_corner_selection(current) if current is not None else None
            except Exception:
                current = None
            if current is None or current.type_id is not type_id:
                state[key] = default_top
        for key in ("bottom_left", "bottom_right"):
            current = state.get(key)
            try:
                current = normalize_corner_selection(current) if current is not None else None
            except Exception:
                current = None
            if reset_bottom_defaults or current is None:
                state[key] = default_bottom


def policy_from_corner_state(state: dict[str, CornerTypeSelection], *, fw: float) -> FourCornerTypePolicy:
    missing = [key for key in CORNER_KEYS if key not in state]
    if missing:
        raise ValueError(f"缺少手動截角狀態：{', '.join(missing)}")
    return FourCornerTypePolicy(
        bottom_left=state["bottom_left"],
        bottom_right=state["bottom_right"],
        top_left=state["top_left"],
        top_right=state["top_right"],
        fw=float(fw),
    )
