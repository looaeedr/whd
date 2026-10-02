# -*- coding: utf-8 -*-
"""Receiving per-Bay left-side pairing MARKING.

R-023..R-027 owner. Geometry is constructed on the authoritative formed main
face in cabinet world coordinates, then backprojected through mapped-skin UV.
No post-backprojection mirror/rotation and no machining-side semantics exist.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .assembly_marking_geometry import backproject_mapped_skin_world_points
from .receiving_layout import (
    RECEIVING_RUNTIME_SELECTION_KEY,
    derive_bay_lock_state,
    normalize_receiving_layout,
)
from .receiving_joint_marking import _owner_render_data, _replace_owner_render_data
from .sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
)
from .sheetmetal_geometry import Vec2


RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS = "RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS"
RECEIVING_PAIRING_MARK_CONFLICT = "RECEIVING_PAIRING_MARK_CONFLICT"
RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED = (
    "RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED"
)
RECEIVING_PAIRING_MARK_SELECTION_UNAVAILABLE = (
    "RECEIVING_PAIRING_MARK_SELECTION_UNAVAILABLE"
)

# OPEN-02: provisional until product/manufacturing signoff. Tests must assert
# only the formula/centering relation, never this absolute value.
PAIRING_SYMBOL_INSET = 5.0
PAIRING_FRAME_WIDTH = 50.0
PAIRING_FRAME_HEIGHT = 100.0
PAIRING_HALF_HEIGHT = 50.0
BACK_OPENING_GLYPH_WIDTH = 30.0
BACK_OPENING_GLYPH_HEIGHT = 20.0

_EPS = 1e-7
_ROUND = 9
_OWNER_KEY = "box_body:left_side"
_SOURCE = "RECEIVING_PAIRING_MARK"


class ReceivingPairingMarkError(ValueError):
    def __init__(self, code: str, detail: str, *, evidence=None):
        self.code = str(code)
        self.detail = str(detail)
        self.evidence = dict(evidence or {})
        super().__init__(f"{self.code}: {self.detail}")


@dataclass(frozen=True)
class ReceivingPairingMarkDiagnostic:
    set_id: str
    bay_id: str
    physical_piece: str
    status: str
    diagnostic_code: str | None
    diagnostic_detail: str
    back_panel_mode: str
    right_locked: bool
    primitive_count: int
    evidence: Mapping[str, object]


@dataclass(frozen=True)
class ReceivingPairingMarkingResolution:
    geometry: object
    result: ReceivingPairingMarkDiagnostic


def pairing_symbol_size(*, inset: float = PAIRING_SYMBOL_INSET) -> float:
    value = float(PAIRING_FRAME_WIDTH) - 2.0 * float(inset)
    if float(inset) <= 0.0 or value <= 0.0 or value >= PAIRING_FRAME_WIDTH:
        raise ReceivingPairingMarkError(
            RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS,
            "PAIRING_SYMBOL_INSET must keep the symbol strictly inside 50x50",
            evidence={"inset": float(inset), "symbol_size": float(value)},
        )
    return float(value)


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a):
    return math.sqrt(sum(float(v) * float(v) for v in a))


def _unit(a):
    mag = _norm(a)
    if mag <= _EPS:
        raise ValueError("degenerate mapped-skin triangle")
    return tuple(float(v) / mag for v in a)


def _triangle_normal(world):
    a, b, c = tuple(world)
    return _unit(_cross(_sub(b, a), _sub(c, a)))


def _canonical_normal(normal):
    n = _unit(normal)
    for value in n:
        if abs(value) > _EPS:
            return tuple(-v for v in n) if value < 0.0 else n
    return n


def _main_face(mapping):
    """Return one deterministic dominant X-normal formed main-face skin."""
    groups = {}
    for record in tuple(mapping or ()):
        world = tuple(getattr(record, "world", ()) or ())
        if len(world) != 3:
            continue
        normal = _canonical_normal(_triangle_normal(world))
        if abs(float(normal[0])) < 0.9:
            continue
        plane_x = sum(float(point[0]) for point in world) / 3.0
        key = round(float(plane_x), 7)
        groups.setdefault(key, []).append(record)
    candidates = []
    for plane_x, records in groups.items():
        polys = []
        for record in records:
            coords = [(float(p[2]), float(p[1])) for p in record.world]
            poly = Polygon(coords)
            if poly.is_valid and not poly.is_empty and float(poly.area) > _EPS:
                polys.append(poly)
        if not polys:
            continue
        region = unary_union(polys)
        area = float(getattr(region, "area", 0.0))
        if area > _EPS:
            candidates.append((-area, float(plane_x), tuple(records), region))
    if not candidates:
        raise ReceivingPairingMarkError(
            RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED,
            "left-side authoritative formed main face is unavailable",
        )
    candidates.sort(key=lambda row: (row[0], row[1]))
    _neg_area, plane_x, records, region = candidates[0]
    min_z, min_y, max_z, max_y = map(float, region.bounds)
    return {
        "mapping": records,
        "region": region,
        "plane_x": float(plane_x),
        "center_y": (min_y + max_y) / 2.0,
        "center_z": (min_z + max_z) / 2.0,
        "bounds": (min_z, min_y, max_z, max_y),
    }


def _world_point(x, y, z):
    return (float(x), float(y), float(z))


def _world_rect(*, x, center_y, center_z, width_d, height_h):
    hz = float(width_d) / 2.0
    hy = float(height_h) / 2.0
    return (
        _world_point(x, center_y - hy, center_z - hz),
        _world_point(x, center_y - hy, center_z + hz),
        _world_point(x, center_y + hy, center_z + hz),
        _world_point(x, center_y + hy, center_z - hz),
    )


def _line_world_geom(points):
    return LineString([(float(p[2]), float(p[1])) for p in points])


def _candidate_world_geometry(*, face, mode: str, right_locked: bool, inset: float):
    mode = str(mode or "").strip().upper()
    if mode not in {"FULL", "HALF", "BACK_OPENING"}:
        raise ValueError(f"unsupported Receiving back_panel_mode: {mode!r}")
    symbol_size = pairing_symbol_size(inset=float(inset))
    if BACK_OPENING_GLYPH_WIDTH > PAIRING_FRAME_WIDTH + _EPS or BACK_OPENING_GLYPH_HEIGHT > PAIRING_HALF_HEIGHT + _EPS:
        raise ReceivingPairingMarkError(
            RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS,
            "BACK_OPENING 30x20 glyph exceeds lower 50x50 region",
            evidence={
                "glyph_width": float(BACK_OPENING_GLYPH_WIDTH),
                "glyph_height": float(BACK_OPENING_GLYPH_HEIGHT),
            },
        )

    x = float(face["plane_x"])
    cy = float(face["center_y"])
    cz = float(face["center_z"])
    top_cy = cy + PAIRING_HALF_HEIGHT / 2.0
    bottom_cy = cy - PAIRING_HALF_HEIGHT / 2.0

    rows = []
    if mode == "HALF":
        rows.append({
            "kind": "polyline", "role": "frame_top",
            "points": _world_rect(
                x=x, center_y=top_cy, center_z=cz,
                width_d=PAIRING_FRAME_WIDTH, height_h=PAIRING_HALF_HEIGHT,
            ),
            "closed": True,
        })
    else:
        rows.append({
            "kind": "polyline", "role": "frame_full",
            "points": _world_rect(
                x=x, center_y=cy, center_z=cz,
                width_d=PAIRING_FRAME_WIDTH, height_h=PAIRING_FRAME_HEIGHT,
            ),
            "closed": True,
        })

    radius = symbol_size / 2.0
    if right_locked:
        rows.append({
            "kind": "circle", "role": "right_lock_circle",
            "center": _world_point(x, top_cy, cz),
            "radius": float(radius),
            "axis_d": _world_point(x, top_cy, cz + radius),
            "axis_h": _world_point(x, top_cy + radius, cz),
        })
    else:
        half = symbol_size / 2.0
        rows.extend((
            {
                "kind": "line", "role": "right_unlock_x_a",
                "points": (
                    _world_point(x, top_cy - half, cz - half),
                    _world_point(x, top_cy + half, cz + half),
                ),
            },
            {
                "kind": "line", "role": "right_unlock_x_b",
                "points": (
                    _world_point(x, top_cy - half, cz + half),
                    _world_point(x, top_cy + half, cz - half),
                ),
            },
        ))

    if mode == "BACK_OPENING":
        rows.append({
            "kind": "polyline", "role": "back_opening_glyph",
            "points": _world_rect(
                x=x, center_y=bottom_cy, center_z=cz,
                width_d=BACK_OPENING_GLYPH_WIDTH,
                height_h=BACK_OPENING_GLYPH_HEIGHT,
            ),
            "closed": True,
        })

    # R-027 formed-face containment. Pairing shapes are strokes, not filled
    # machining regions, so containment is evaluated on their geometric paths.
    for row in rows:
        if row["kind"] == "circle":
            center = row["center"]
            geom = Point(float(center[2]), float(center[1])).buffer(
                float(row["radius"]), resolution=64
            ).boundary
        else:
            points = tuple(row["points"])
            coords = [(float(p[2]), float(p[1])) for p in points]
            if row.get("closed"):
                coords = coords + [coords[0]]
            geom = LineString(coords)
        if not face["region"].covers(geom):
            raise ReceivingPairingMarkError(
                RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS,
                f"pairing primitive {row['role']} exceeds formed main face",
                evidence={"role": row["role"], "formed_face_bounds": face["bounds"]},
            )
        row["formed_geometry"] = geom
    return tuple(rows)


def _round_point(point):
    return tuple(round(float(v), _ROUND) for v in point)


def _primitive_signature(primitive):
    if isinstance(primitive, LinePrimitive):
        points = sorted((
            _round_point((primitive.p1.x, primitive.p1.y)),
            _round_point((primitive.p2.x, primitive.p2.y)),
        ))
        return ("line", tuple(points))
    if isinstance(primitive, CirclePrimitive):
        return (
            "circle",
            _round_point((primitive.center.x, primitive.center.y)),
            round(float(primitive.radius), _ROUND),
        )
    if isinstance(primitive, PolylinePrimitive):
        return (
            "polyline",
            tuple(_round_point((p.x, p.y)) for p in primitive.points),
            bool(primitive.closed),
        )
    return None


def _clean_prior_pairing_marks(render_data):
    metadata = dict(getattr(render_data, "metadata", {}) or {})
    prior = tuple(metadata.get("receiving_pairing_markings") or ())
    owned = {
        tuple(row.get("primitive_signature") or ())
        for row in prior
        if isinstance(row, Mapping) and row.get("primitive_signature")
    }
    scene = DrawingScene()
    for primitive in tuple(getattr(render_data.scene, "primitives", ()) or ()):
        signature = _primitive_signature(primitive)
        if signature is not None and tuple(signature) in owned:
            continue
        scene.add(primitive)
    metadata["receiving_pairing_markings"] = ()
    return replace(render_data, scene=scene, metadata=metadata)


def _backproject_rows(rows, mapping, *, bay_id: str):
    primitives = []
    metadata_rows = []
    for row in rows:
        kind = row["kind"]
        role = str(row["role"])
        if kind == "circle":
            world_points = (row["center"], row["axis_d"], row["axis_h"])
            projected = backproject_mapped_skin_world_points(mapping, world_points)
            if projected.status != "RESOLVED" or len(projected.flat_points) != 3:
                raise ReceivingPairingMarkError(
                    RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED,
                    f"circle backprojection failed: {projected.diagnostic_code}",
                    evidence=dict(projected.evidence or {}),
                )
            center, axis_d, axis_h = projected.flat_points
            rd = math.hypot(axis_d[0] - center[0], axis_d[1] - center[1])
            rh = math.hypot(axis_h[0] - center[0], axis_h[1] - center[1])
            if abs(rd - rh) > 1e-5 or min(rd, rh) <= _EPS:
                raise ReceivingPairingMarkError(
                    RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED,
                    "formed circle did not backproject as an isometric circle",
                    evidence={"radius_d": rd, "radius_h": rh},
                )
            primitive = CirclePrimitive(
                center=Vec2(float(center[0]), float(center[1])),
                radius=(rd + rh) / 2.0,
                layer="MARKING",
                color=211,
                source_type=_SOURCE,
                source_id=f"{bay_id}:{role}",
            )
        else:
            world_points = tuple(row["points"])
            projected = backproject_mapped_skin_world_points(mapping, world_points)
            if projected.status != "RESOLVED" or len(projected.flat_points) != len(world_points):
                raise ReceivingPairingMarkError(
                    RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED,
                    f"{role} backprojection failed: {projected.diagnostic_code}",
                    evidence=dict(projected.evidence or {}),
                )
            points = tuple(Vec2(float(x), float(y)) for x, y in projected.flat_points)
            primitive = (
                PolylinePrimitive(points=points, layer="MARKING", closed=True, color=211)
                if row.get("closed")
                else LinePrimitive(points[0], points[1], "MARKING", 211)
            )
        primitives.append(primitive)
        metadata_rows.append({
            "source": _SOURCE,
            "bay_id": str(bay_id),
            "role": role,
            "primitive_signature": _primitive_signature(primitive),
            "world_points": (
                tuple(tuple(float(v) for v in point) for point in row["points"])
                if row.get("points") is not None
                else ()
            ),
            "world_center": (
                tuple(float(v) for v in row["center"])
                if row.get("center") is not None
                else None
            ),
            "world_radius": (
                float(row["radius"]) if row.get("radius") is not None else None
            ),
        })
    return tuple(primitives), tuple(metadata_rows)


def _flat_mark_geometry(primitive):
    if isinstance(primitive, LinePrimitive):
        return LineString((
            (float(primitive.p1.x), float(primitive.p1.y)),
            (float(primitive.p2.x), float(primitive.p2.y)),
        ))
    if isinstance(primitive, CirclePrimitive):
        return Point(float(primitive.center.x), float(primitive.center.y)).buffer(
            float(primitive.radius), resolution=64
        ).boundary
    if isinstance(primitive, PolylinePrimitive):
        coords = [(float(p.x), float(p.y)) for p in primitive.points]
        if primitive.closed and coords:
            coords = coords + [coords[0]]
        return LineString(coords)
    return None


def _existing_conflict_geometry(primitive, material):
    layer = str(getattr(primitive, "layer", "") or "").strip().upper()
    if layer not in {"CUTTING", "BLIND_HOLE", "MARKING"}:
        return None
    if isinstance(primitive, LinePrimitive):
        return LineString((
            (float(primitive.p1.x), float(primitive.p1.y)),
            (float(primitive.p2.x), float(primitive.p2.y)),
        ))
    if isinstance(primitive, CirclePrimitive):
        disk = Point(float(primitive.center.x), float(primitive.center.y)).buffer(
            float(primitive.radius), resolution=64
        )
        return disk.boundary if layer == "MARKING" else disk
    if isinstance(primitive, PolylinePrimitive):
        coords = [(float(p.x), float(p.y)) for p in primitive.points]
        if not coords:
            return None
        line_coords = coords + [coords[0]] if primitive.closed else coords
        line = LineString(line_coords)
        if layer == "MARKING" or not primitive.closed:
            return line
        try:
            polygon = Polygon(coords)
        except Exception:
            return line
        if not polygon.is_valid or polygon.is_empty:
            return line
        # The outer stock/material CUTTING profile contains Final Material and
        # is a boundary, not a filled forbidden feature. Smaller closed CUTTING
        # profiles are cutouts and use their interior for conflict checks.
        if polygon.covers(material):
            return polygon.boundary
        return polygon
    return None


def _validate_flat(primitives, render_data):
    material = render_data.material
    candidate_rows = []
    for index, primitive in enumerate(primitives):
        geom = _flat_mark_geometry(primitive)
        if geom is None or geom.is_empty or not material.covers(geom):
            raise ReceivingPairingMarkError(
                RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS,
                "pairing MARKING exceeds Final Material",
                evidence={"candidate_index": index},
            )
        candidate_rows.append((index, geom))

    existing = []
    for index, primitive in enumerate(tuple(render_data.scene.primitives or ())):
        geom = _existing_conflict_geometry(primitive, material)
        if geom is None or geom.is_empty:
            continue
        feature_id = (
            str(getattr(primitive, "source_id", "") or "")
            or f"scene:{index}:{str(getattr(primitive, 'layer', ''))}:{type(primitive).__name__}"
        )
        existing.append((feature_id, geom))

    conflicts = []
    for candidate_index, candidate in candidate_rows:
        for feature_id, other in existing:
            if candidate.intersects(other):
                conflicts.append((candidate_index, feature_id))
    if conflicts:
        raise ReceivingPairingMarkError(
            RECEIVING_PAIRING_MARK_CONFLICT,
            "pairing MARKING intersects same-piece manufacturing geometry",
            evidence={
                "conflicting_feature_ids": tuple(sorted({row[1] for row in conflicts})),
                "candidate_indices": tuple(sorted({row[0] for row in conflicts})),
            },
        )


def _selection(snapshot, *, set_index, bay_index):
    layout = normalize_receiving_layout(dict(snapshot or {}).get("receiving_layout"))
    if set_index is None or bay_index is None:
        runtime = dict(dict(snapshot or {}).get(RECEIVING_RUNTIME_SELECTION_KEY) or {})
        if set_index is None:
            set_index = runtime.get("set_index")
        if bay_index is None:
            bay_index = runtime.get("bay_index")
    if set_index is None or bay_index is None:
        if len(layout["sets"]) == 1 and len(layout["sets"][0]["bays"]) == 1:
            set_index = 0
            bay_index = 0
        else:
            raise ReceivingPairingMarkError(
                RECEIVING_PAIRING_MARK_SELECTION_UNAVAILABLE,
                "multi-Bay pairing MARKING requires transient runtime selection",
            )
    si = int(set_index)
    bi = int(bay_index)
    selected = layout["sets"][si]
    bay = selected["bays"][bi]
    _left_locked, right_locked = derive_bay_lock_state(layout, set_index=si, bay_index=bi)
    return layout, si, bi, selected, bay, bool(right_locked)


def resolve_receiving_pairing_marking(
    snapshot,
    geometry,
    *,
    world_geometry,
    set_index=None,
    bay_index=None,
    symbol_inset: float = PAIRING_SYMBOL_INSET,
) -> ReceivingPairingMarkingResolution:
    """Resolve one selected Bay pairing mark into left-side FinalScene only."""
    snapshot = dict(snapshot or {})
    try:
        _layout, si, bi, set_row, bay, right_locked = _selection(
            snapshot, set_index=set_index, bay_index=bay_index
        )
        bay_id = str(bay["stable_id"])
        set_id = str(set_row["stable_id"])
        mode = str(bay["back_panel_mode"]).strip().upper()
    except Exception as exc:
        code = getattr(exc, "code", RECEIVING_PAIRING_MARK_SELECTION_UNAVAILABLE)
        diagnostic = ReceivingPairingMarkDiagnostic(
            set_id="", bay_id="", physical_piece=_OWNER_KEY, status="BLOCKED",
            diagnostic_code=str(code), diagnostic_detail=str(exc),
            back_panel_mode="", right_locked=False, primitive_count=0,
            evidence=dict(getattr(exc, "evidence", {}) or {}),
        )
        return ReceivingPairingMarkingResolution(
            geometry=replace(geometry, diagnostics=tuple(geometry.diagnostics or ()) + (diagnostic,)),
            result=diagnostic,
        )

    data = _owner_render_data(geometry, _OWNER_KEY)
    if data is None:
        diagnostic = ReceivingPairingMarkDiagnostic(
            set_id=set_id, bay_id=bay_id, physical_piece=_OWNER_KEY, status="BLOCKED",
            diagnostic_code=RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED,
            diagnostic_detail="left-side physical piece is unavailable",
            back_panel_mode=mode, right_locked=right_locked, primitive_count=0, evidence={},
        )
        return ReceivingPairingMarkingResolution(
            geometry=replace(geometry, diagnostics=tuple(geometry.diagnostics or ()) + (diagnostic,)),
            result=diagnostic,
        )

    cleaned = _clean_prior_pairing_marks(data)
    cleaned_geometry = _replace_owner_render_data(geometry, _OWNER_KEY, cleaned)
    mapping = tuple(
        dict(world_geometry or {}).get("mapped_skin_triangles_by_part", {}).get(_OWNER_KEY, ())
        or ()
    )
    try:
        face = _main_face(mapping)
        rows = _candidate_world_geometry(
            face=face, mode=mode, right_locked=right_locked, inset=float(symbol_inset)
        )
        primitives, metadata_rows = _backproject_rows(rows, face["mapping"], bay_id=bay_id)
        _validate_flat(primitives, cleaned)
        scene = DrawingScene()
        scene.extend(tuple(cleaned.scene.primitives or ()))
        scene.extend(primitives)
        metadata = dict(cleaned.metadata or {})
        metadata["receiving_pairing_markings"] = metadata_rows
        metadata["receiving_pairing_mark_provisional"] = {
            "PAIRING_SYMBOL_INSET": float(symbol_inset),
            "open_item": "OPEN-02",
        }
        updated = replace(cleaned, scene=scene, metadata=metadata)
        enriched = _replace_owner_render_data(cleaned_geometry, _OWNER_KEY, updated)
        diagnostic = ReceivingPairingMarkDiagnostic(
            set_id=set_id, bay_id=bay_id, physical_piece=_OWNER_KEY, status="EMITTED",
            diagnostic_code=None, diagnostic_detail="", back_panel_mode=mode,
            right_locked=right_locked, primitive_count=len(primitives),
            evidence={
                "symbol_size": pairing_symbol_size(inset=float(symbol_inset)),
                "symbol_inset": float(symbol_inset),
                "formed_face_bounds": tuple(face["bounds"]),
                "mapping_record_count": len(face["mapping"]),
                "transform": "FORMED_WORLD_TO_MAPPED_SKIN_FLAT",
                "machining_side": None,
            },
        )
        enriched = replace(
            enriched, diagnostics=tuple(enriched.diagnostics or ()) + (diagnostic,)
        )
        return ReceivingPairingMarkingResolution(geometry=enriched, result=diagnostic)
    except Exception as exc:
        code = getattr(exc, "code", RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED)
        diagnostic = ReceivingPairingMarkDiagnostic(
            set_id=set_id, bay_id=bay_id, physical_piece=_OWNER_KEY, status="BLOCKED",
            diagnostic_code=str(code), diagnostic_detail=str(exc), back_panel_mode=mode,
            right_locked=right_locked, primitive_count=0,
            evidence=dict(getattr(exc, "evidence", {}) or {}),
        )
        blocked = replace(
            cleaned_geometry, diagnostics=tuple(cleaned_geometry.diagnostics or ()) + (diagnostic,)
        )
        return ReceivingPairingMarkingResolution(geometry=blocked, result=diagnostic)


__all__ = [
    "BACK_OPENING_GLYPH_HEIGHT",
    "BACK_OPENING_GLYPH_WIDTH",
    "PAIRING_SYMBOL_INSET",
    "RECEIVING_PAIRING_MARK_BACKPROJECTION_FAILED",
    "RECEIVING_PAIRING_MARK_CONFLICT",
    "RECEIVING_PAIRING_MARK_OUT_OF_BOUNDS",
    "RECEIVING_PAIRING_MARK_SELECTION_UNAVAILABLE",
    "ReceivingPairingMarkDiagnostic",
    "ReceivingPairingMarkError",
    "ReceivingPairingMarkingResolution",
    "pairing_symbol_size",
    "resolve_receiving_pairing_marking",
]
