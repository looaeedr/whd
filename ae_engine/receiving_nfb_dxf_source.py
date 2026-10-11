# -*- coding: utf-8 -*-
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
