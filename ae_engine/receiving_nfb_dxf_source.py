# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""NFB DXF source evidence without inventing a manufacturable main-hole pivot.

Unlike the legacy single-hole catalog reader, an NFB drawing can contain many
upper opening / lower spacer groups. Never center an entire document bbox,
flatten away bulges, or interpret a filename as manufacturing certification.

This reader preserves source SHA / entity ancestry / layer & effective ACI and
supports diagnostic 90-degree rotations around an *explicit* source pivot.
It does not write CUTTING, infer a product model, or certify any candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import cos, isfinite, radians, sin
from pathlib import Path
from typing import Iterable


KNOWN_PROCESS_COLORS = (30, 150, 212)
ALLOWED_ROTATIONS = (0, 90, 180, 270)
SOURCE_STATUS = "SOURCE_OBSERVED_UNCERTIFIED"


@dataclass(frozen=True)
class NfbSourceEntity:
    source_id: str
    source_hash: str
    source_path: str
    group_id: str
    dxf_type: str
    layer: str
    layer_color_aci: int | None
    entity_color_aci: int | None
    effective_color_aci: int | None
    color_authority: str
    handle_path: str
    vertices_xy: tuple[tuple[float, float], ...] = ()
    bulges: tuple[float, ...] = ()
    closed: bool = False
    center_xy: tuple[float, float] | None = None
    radius: float | None = None
    arc_angles: tuple[float, float] | None = None


@dataclass(frozen=True)
class NfbSourceInventory:
    source_path: str
    source_sha256: str
    source_id: str
    status: str
    entities: tuple[NfbSourceEntity, ...]
    diagnostics: tuple[str, ...]
    process_aci_entity_counts: tuple[tuple[int, int], ...]
    unresolved_color_entities: int
    grouped_entity_counts: tuple[tuple[str, int], ...]
    main_hole_source_id: None = None
    approved_manufacturing_rule_revision: None = None


def _xy(v) -> tuple[float, float]:
    xy = float(v[0]), float(v[1])
    if not all(isfinite(x) for x in xy):
        raise ValueError("NFB DXF has non-finite geometry coordinates")
    return xy


def _effective_aci(entity, document, *, inherited_layer: str | None, inherited_aci: int | None):
    original_layer = str(entity.dxf.get("layer", "0"))
    layer = inherited_layer if original_layer == "0" and inherited_layer else original_layer
    layer_color = None
    try:
        layer_entry = document.layers.get(layer)
        layer_color = abs(int(layer_entry.dxf.color))
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    try:
        entity_color = int(entity.dxf.get("color", 256))
    except (TypeError, ValueError):
        entity_color = None
    if entity_color is not None and 1 <= entity_color <= 255:
        return layer, layer_color, entity_color, entity_color, "ENTITY"
    if entity_color == 256 and layer_color is not None and 1 <= layer_color <= 255:
        return layer, layer_color, entity_color, layer_color, "LAYER"
    if entity_color == 0 and inherited_aci is not None:
        return layer, layer_color, entity_color, inherited_aci, "BLOCK_INHERITED"
    return layer, layer_color, entity_color, None, "UNRESOLVED_COLOR"


def _primitive_geometry(entity):
    kind = entity.dxftype()
    if kind == "CIRCLE":
        center = _xy(entity.dxf.center)
        r = float(entity.dxf.radius)
        if not isfinite(r) or r <= 0:
            raise ValueError("NFB DXF CIRCLE has invalid radius")
        return (), (), True, center, r, None
    if kind == "ARC":
        center = _xy(entity.dxf.center)
        r = float(entity.dxf.radius)
        angles = float(entity.dxf.start_angle), float(entity.dxf.end_angle)
        if not isfinite(r) or r <= 0 or not all(isfinite(a) for a in angles):
            raise ValueError("NFB DXF ARC has invalid geometry")
        return (), (), False, center, r, angles
    if kind == "LINE":
        return (_xy(entity.dxf.start), _xy(entity.dxf.end)), (), False, None, None, None
    if kind == "LWPOLYLINE":
        rows = tuple(entity.get_points("xyb"))
        return (
            tuple(_xy((row[0], row[1])) for row in rows),
            tuple(float(row[2]) for row in rows),
            bool(entity.closed), None, None, None,
        )
    if kind == "POLYLINE":
        # Preserve old-style vertex bulges; do not silently straighten arcs.
        rows = tuple(entity.vertices)
        return (
            tuple(_xy(row.dxf.location) for row in rows),
            tuple(float(row.dxf.get("bulge", 0.0)) for row in rows),
            bool(entity.is_closed), None, None, None,
        )
    return None


def inspect_nfb_dxf_source(path: str | Path, *, max_insert_depth: int = 8) -> NfbSourceInventory:
    """Read one actual DXF and return only provenance, not certified holes.

    Virtual INSERT entities are read with their true transformed coordinates.
    Block color/layer provenance is retained; recursive/unsupported geometry is
    diagnosed rather than quietly certified as a rectangular cutting profile.
    """
    import ezdxf

    src = Path(path)
    data = src.read_bytes()
    digest = sha256(data).hexdigest()
    document = ezdxf.readfile(src)
    entities: list[NfbSourceEntity] = []
    diagnostics: list[str] = []

    def visit(entity, *, lineage: str, group_id: str, layer: str | None,
              color: int | None, depth: int) -> None:
        kind = entity.dxftype()
        if kind == "INSERT":
            if depth >= max_insert_depth:
                diagnostics.append(f"{lineage}:INSERT_MAX_DEPTH")
                return
            insertion_layer, _lc, _ec, insertion_aci, _authority = _effective_aci(
                entity, document, inherited_layer=layer, inherited_aci=color,
            )
            name = str(entity.dxf.get("name", ""))
            subgroup = f"{group_id}/INSERT:{lineage}:{name}"
            try:
                children = tuple(entity.virtual_entities())
            except (TypeError, ValueError, AttributeError, RuntimeError) as exc:
                diagnostics.append(f"{lineage}:INSERT_UNRESOLVED:{type(exc).__name__}")
                return
            for index, child in enumerate(children):
                visit(child, lineage=f"{lineage}/{index}",
                      group_id=subgroup, layer=insertion_layer,
                      color=insertion_aci, depth=depth + 1)
            return
        geometry = _primitive_geometry(entity)
        if geometry is None:
            # Graphic annotations are not manufacturing holes.
            if kind not in {"TEXT", "MTEXT", "DIMENSION", "POINT", "HATCH"}:
                diagnostics.append(f"{lineage}:UNSUPPORTED:{kind}")
            return
        layer_name, layer_aci, explicit_aci, effective_aci, authority = _effective_aci(
            entity, document, inherited_layer=layer, inherited_aci=color,
        )
        vertices, bulges, closed, center, radius, angles = geometry
        if kind in {"LWPOLYLINE", "POLYLINE"} and (
            len(vertices) < 2 or not all(isfinite(b) for b in bulges)
        ):
            diagnostics.append(f"{lineage}:INVALID_POLYLINE")
            return
        if effective_aci is None:
            diagnostics.append(f"{lineage}:COLOR_UNRESOLVED")
        entities.append(NfbSourceEntity(
            source_id=f"{digest}:{lineage}", source_hash=digest,
            source_path=src.name, group_id=group_id, dxf_type=kind,
            layer=layer_name, layer_color_aci=layer_aci,
            entity_color_aci=explicit_aci,
            effective_color_aci=effective_aci, color_authority=authority,
            handle_path=lineage, vertices_xy=vertices, bulges=bulges,
            closed=closed, center_xy=center, radius=radius, arc_angles=angles,
        ))

    for index, entity in enumerate(document.modelspace()):
        handle = str(entity.dxf.get("handle", "")).strip()
        # Stable even for malformed/handleless entities, without bbox ownership.
        lineage = handle if handle else f"item_{index}"
        visit(entity, lineage=lineage, group_id="modelspace",
              layer=None, color=None, depth=0)

    counts = tuple((color, sum(e.effective_color_aci == color for e in entities))
                   for color in KNOWN_PROCESS_COLORS)
    groups = sorted({e.group_id for e in entities})
    return NfbSourceInventory(
        source_path=src.name, source_sha256=digest,
        source_id=f"NFB-DXF:{digest}", status=SOURCE_STATUS,
        entities=tuple(entities), diagnostics=tuple(diagnostics),
        process_aci_entity_counts=counts,
        unresolved_color_entities=sum(e.effective_color_aci is None for e in entities),
        grouped_entity_counts=tuple(
            (group, sum(e.group_id == group for e in entities)) for group in groups
        ),
    )


def circle_candidate_pivot(
    inventory: NfbSourceInventory, *, source_entity_id: str
) -> tuple[float, float]:
    """Return a specifically selected source CIRCLE center, never a file bbox.

    A circle center is a candidate location only. It does not prove this is the
    main NFB opening or grant a manufacturing rule/revision.
    """
    matches = [row for row in inventory.entities if row.source_id == source_entity_id]
    if len(matches) != 1 or matches[0].dxf_type != "CIRCLE" or matches[0].center_xy is None:
        raise ValueError("NFB main-hole pivot has no uniquely selected source CIRCLE")
    return matches[0].center_xy


@dataclass(frozen=True)
class NfbUpperColor150Reference:
    """User-confirmed common origin for UPPER middle-board and inner-door holes.

    It does not certify NFB model identity or release a CUTTING operation.
    """
    source_id: str
    source_sha256: str
    source_entity_id: str
    center_xy: tuple[float, float]
    size_mm: tuple[float, float]
    source_outline_vertices_xy: tuple[tuple[float, float], ...]
    source_color_aci: int = 150
    consumers: tuple[str, str] = ("MIDDLE_PLATE", "INNER_DOOR")
    status: str = "USER_CONFIRMED_UPPER_REFERENCE_ONLY"


def resolve_upper_color150_reference(
    inventory: NfbSourceInventory, *, upper_source_entity_ids: Iterable[str],
) -> NfbUpperColor150Reference:
    """Use the explicitly selected upper Color-150 closed rectangle CENTER.

    Upper/lower separation must be evidenced by caller-selected source IDs.
    Never locate it by whole-DXF bbox, guessed Y cutoff or filename. Only
    geometry from the selected UPPER set participates; the lower assembly is
    ignored. Ambiguous, malformed or changed upper references fail closed.
    """
    selected = tuple(str(v) for v in upper_source_entity_ids)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("NFB upper-source identity missing or duplicated")
    known_ids = {row.source_id for row in inventory.entities}
    if not set(selected).issubset(known_ids):
        raise ValueError("NFB upper-source entity not found in this DXF")
    candidates = [row for row in inventory.entities
                  if row.source_id in selected and row.effective_color_aci == 150]
    if len(candidates) != 1:
        raise ValueError("NFB upper Color 150 must be one explicit closed profile")
    row = candidates[0]
    pts = tuple(row.vertices_xy)
    if (row.dxf_type not in ("LWPOLYLINE", "POLYLINE")
            or not row.closed or len(pts) != 4 or len(set(pts)) != 4
            or any(abs(float(b)) > 1e-9 for b in row.bulges)
            or row.source_hash != inventory.source_sha256):
        raise ValueError("NFB upper Color 150 must be a valid closed rectangle")
    xs = sorted({float(pt[0]) for pt in pts})
    ys = sorted({float(pt[1]) for pt in pts})
    if (len(xs) != 2 or len(ys) != 2 or
            len(set(pts)) != 4 or
            set(pts) != {(x,y) for x in xs for y in ys} or
            xs[1] <= xs[0] or ys[1] <= ys[0]):
        raise ValueError("NFB upper Color 150 is not a rectangular outline")
    return NfbUpperColor150Reference(
        source_id=inventory.source_id,
        source_sha256=inventory.source_sha256,
        source_entity_id=row.source_id,
        center_xy=((xs[0] + xs[1]) / 2.0, (ys[0] + ys[1]) / 2.0),
        size_mm=(xs[1] - xs[0], ys[1] - ys[0]),
        source_outline_vertices_xy=pts,
    )


def place_upper_nfb_point_from_color150(
    source_point_xy: Iterable[float], *,
    reference: NfbUpperColor150Reference,
    target_center_xy: Iterable[float],
    rotation_deg: int = 0,
) -> tuple[float, float]:
    """Both approved consumers use one upper-source center and 0/90/180/270.

    This returns source-relative placement geometry only; no DXF cutting is
    output and no lower-region shapes are imported through this helper.
    """
    rotated = rotate_point_around_source_pivot(
        source_point_xy, pivot_xy=reference.center_xy, rotation_deg=rotation_deg,
    )
    target = _xy(tuple(target_center_xy))
    return (
        target[0] + rotated[0] - reference.center_xy[0],
        target[1] + rotated[1] - reference.center_xy[1],
    )


def place_upper_color150_opening_outline(
    *, reference: NfbUpperColor150Reference,
    target_center_xy: Iterable[float],
    rotation_deg: int = 0,
    consumer: str,
) -> tuple[tuple[float, float], ...]:
    """The SAME real source Color-150 aperture fits middle plate or inner door.

    Coordinates remain on the caller-supplied target part plane. The caller
    must separately verify correct physical part ID, fit and production rights.
    Color-30 base holes / Color-212 marking / LOWER spacer are never copied.
    """
    if consumer not in reference.consumers:
        raise ValueError("NFB upper Color150 opening consumer must be middle plate or inner door")
    return tuple(place_upper_nfb_point_from_color150(
        point, reference=reference, target_center_xy=target_center_xy,
        rotation_deg=rotation_deg,
    ) for point in reference.source_outline_vertices_xy)


def rotate_point_around_source_pivot(
    point_xy: Iterable[float], *, pivot_xy: Iterable[float], rotation_deg: int
) -> tuple[float, float]:
    """Rotate diagnostic coordinates around an explicit source pivot.

    Only quarter-turns allowed; never derive a pivot from whole-file extents.
    """
    if isinstance(rotation_deg, bool) or rotation_deg not in ALLOWED_ROTATIONS:
        raise ValueError("NFB source rotation must be 0/90/180/270")
    point, pivot = _xy(tuple(point_xy)), _xy(tuple(pivot_xy))
    dx, dy = point[0] - pivot[0], point[1] - pivot[1]
    # Exact integer quarter-turn transform avoids floating-point center drift.
    turns = rotation_deg // 90
    x, y = ((dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx))[turns]
    return pivot[0] + x, pivot[1] + y


def inspect_expected_nfb_sources(model_paths: Iterable[str | Path]) -> tuple[tuple[str, str], ...]:
    """An absent source is UNKNOWN, not zero holes / zero model support."""
    status = []
    for source in model_paths:
        p = Path(source)
        if not p.is_file():
            status.append((str(p), "SOURCE_MISSING_UNKNOWN"))
        else:
            status.append((str(p), "SOURCE_PRESENT_NOT_CERTIFIED"))
    return tuple(status)
