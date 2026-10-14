# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Receiving-only physical side/rear-panel DXF fixed features.

The dedicated DXFs supply manufacturing fixed holes, blind holes and the
rear-panel slot/opening contours. Canonical Fold Profiles remain the owner of
CUTTING stock boundaries, BEND positions, dimensions and assembly. Never
paste the source's entire drawing (CHECK, sample BEND, alternate rear-panel
process modes) into the final manufactured part.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from ezdxf import bbox
from ezdxf.path import make_path

from .baseline_source import load_baseline_dxf_source_with_status, BASELINE_SOURCE_VERIFIED
from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from .sheetmetal_geometry import Vec2

ROLE_FILES = {
    "left_side": "左側板.dxf",
    "right_side": "右側板.dxf",
    "back": "後面板.dxf",
}
EPS = 0.04


def _reference_outline(msp):
    """Only the largest closed CUTTING outline is the material rectangle."""
    candidates = []
    for entity in msp.query("LWPOLYLINE"):
        if str(entity.dxf.layer).upper() != "CUTTING" or not entity.closed:
            continue
        points = [(float(p[0]), float(p[1])) for p in entity.get_points()]
        if len(points) != 4:
            continue
        xs, ys = zip(*points)
        width, height = max(xs)-min(xs), max(ys)-min(ys)
        if width > 0 and height > 0:
            candidates.append((width*height, entity, (min(xs), min(ys), width, height)))
    if not candidates:
        raise ValueError("RECEIVING_BASELINE_MATERIAL_OUTLINE_MISSING")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def _edge_anchor(value, source_span, target_span):
    """Preserve closest physical source edge; keep centerline at the center."""
    value, source_span, target_span = map(float, (value, source_span, target_span))
    if abs(value - source_span / 2) < 0.05:
        return target_span / 2
    if value <= source_span / 2:
        return value
    return target_span - (source_span - value)


def _source_color(entity, layer):
    # Preserve original ACI only when explicit and not BYLAYER.
    raw = entity.dxf.get("color", 256)
    if raw is None or int(raw) in (0, 256, 257):
        return {"MARKING": 211, "BLIND_HOLE": 1}.get(layer)
    return int(raw)


def _flatten_closed(entity):
    # DXF bulges must remain arcs (not a 4-corner approximation).
    points = tuple(make_path(entity).flattening(distance=0.015, segments=24))
    return tuple(Vec2(float(v.x), float(v.y)) for v in points[:-1] if points) if (
        points and (points[0]-points[-1]).magnitude < 1e-7
    ) else tuple(Vec2(float(v.x), float(v.y)) for v in points)


def _rear_template(msp, material_entity, ox, oy):
    """Pick one real R8/4.5 source keyslot, not the sample open reference line."""
    slots = []
    opening = None
    for item in msp.query("LWPOLYLINE"):
        if item is material_entity or str(item.dxf.layer).upper() != "CUTTING" or not item.closed:
            continue
        size = bbox.extents([item]).size
        w, h = float(size.x), float(size.y)
        if abs(w-650.0) < EPS and abs(h-200.0) < EPS:
            opening = item
        elif abs(w-16.0) < EPS and abs(h-23.5) < EPS:
            slots.append(item)
    if len(slots) != 6 or opening is None:
        raise ValueError("RECEIVING_REAR_SOURCE_SLOT_OR_OPENING_UNVERIFIED")
    # Slot whose upper neck centre is the (120,120) source datum.
    slot = min(slots, key=lambda s: (
        abs((bbox.extents([s]).extmin.x + bbox.extents([s]).extmax.x)/2-ox-120.0)
        + abs(bbox.extents([s]).extmax.y-oy-120.0)
    ))
    pts = _flatten_closed(slot)
    source_cx = (bbox.extents([slot]).extmin.x + bbox.extents([slot]).extmax.x)/2
    source_neck_y = bbox.extents([slot]).extmax.y
    return (tuple(Vec2(p.x-source_cx, p.y-source_neck_y) for p in pts),
            tuple(Vec2(p.x-ox, p.y-oy) for p in _flatten_closed(opening)))


def receiving_piece_baseline_features(role, *, expected_path: Path, width: float,
                                      height: float, back_contract=None):
    """Return exact source-backed fixed features and source metadata for a physical piece."""
    if role not in ROLE_FILES:
        raise ValueError("RECEIVING_BASELINE_PIECE_ROLE_UNKNOWN")
    path = Path(expected_path)
    if not path.is_file():
        raise FileNotFoundError(f"受電箱板件專用基準檔不存在：{path}")
    doc, source_status = load_baseline_dxf_source_with_status(
        path, allow_unverified_source=False,
    )
    if source_status != BASELINE_SOURCE_VERIFIED:
        raise ValueError(f"RECEIVING_BASELINE_SOURCE_UNVERIFIED: {path}")
    msp = doc.modelspace()
    material, (ox, oy, sample_w, sample_h) = _reference_outline(msp)
    if float(width) <= 0 or float(height) <= 0:
        raise ValueError("RECEIVING_BASELINE_TARGET_DIMENSIONS_INVALID")

    emitted = []
    blocked_reason = None
    if role in ("left_side", "right_side"):
        for item in msp.query("CIRCLE"):
            layer = str(item.dxf.layer).upper()
            if layer not in {"CUTTING", "MARKING", "BLIND_HOLE"}:
                continue
            x = _edge_anchor(float(item.dxf.center.x)-ox, sample_w, width)
            y = _edge_anchor(float(item.dxf.center.y)-oy, sample_h, height)
            radius = float(item.dxf.radius)
            if (radius <= 0 or x-radius < -EPS or x+radius > width+EPS
                    or y-radius < -EPS or y+radius > height+EPS):
                # An undersized *preview* still needs to exist for the
                # separate pairing/fit validator to report BLOCKED. Do not
                # clip, move, or silently discard any certified source hole.
                # The whole fixed-hole group becomes unavailable and BOTH
                # manufacturing export entrypoints must reject it.
                blocked_reason = f"RECEIVING_BASELINE_FIXED_HOLE_OUTSIDE_MATERIAL: {path}"
                continue
            emitted.append(CirclePrimitive(
                Vec2(x, y), radius, layer, _source_color(item, layer),
                source_type="receiving_dedicated_baseline",
                source_id=f"{role}:{item.dxf.handle}",
            ))
        if blocked_reason:
            emitted.clear()
        elif len(emitted) != 9:
            raise ValueError(f"RECEIVING_BASELINE_SIDE_FEATURES_INCOMPLETE: {path}")
    elif back_contract:
        contract = dict(back_contract)
        source_slot, source_opening = _rear_template(msp, material, ox, oy)
        for x, y in tuple(contract.get("fixed_slot_datums") or ()):
            points = tuple(Vec2(float(x)+p.x, float(y)+p.y) for p in source_slot)
            emitted.append(PolylinePrimitive(points, "CUTTING", True, color=3))
        if len(emitted) != 4:
            raise ValueError("RECEIVING_BACK_PANEL_EXPECTS_FOUR_MODE_SLOTS")
        opening = contract.get("opening")
        if opening is not None:
            xs = [p.x for p in source_opening]
            ys = [p.y for p in source_opening]
            want = tuple(map(float, opening))
            if max(abs(a-b) for a, b in zip(
                (min(xs), min(ys), max(xs), max(ys)), want
            )) > EPS:
                raise ValueError("RECEIVING_BACK_OPENING_SOURCE_CONTRACT_MISMATCH")
            emitted.append(PolylinePrimitive(source_opening, "CUTTING", True, color=3))
    source_bends = tuple(sorted(round(float(item.dxf.start.x)-ox, 6)
        for item in msp.query("LINE")
        if str(item.dxf.layer).upper() == "BEND"
        and abs(float(item.dxf.start.x)-float(item.dxf.end.x)) < 1e-6))
    data = path.read_bytes()
    metadata = {
        "baseline_reference_bend_positions": source_bends,
        "baseline_fit_error": blocked_reason,
        "baseline_fit_valid": blocked_reason is None,
        "baseline_source_path": str(path),
        "baseline_source_sha256": sha256(data).hexdigest(),
        "baseline_source_role": role,
        "baseline_feature_count": len(emitted),
        "baseline_reference_dimensions": (sample_w, sample_h),
        "baseline_source_status": source_status,
        "baseline_stock_and_bends": "CANONICAL_FOLD_PROFILE_NOT_SAMPLE_DXF",
    }
    return tuple(emitted), metadata
