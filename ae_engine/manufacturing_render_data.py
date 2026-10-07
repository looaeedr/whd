"""Authoritative manufacturing render-data values and final-scene measurements.

Extracted from manufacturing_api; this module owns no export/request policy.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Literal, Mapping

from . import ae
from .dxf_serialization import save_scene_dxf
from . import manufacturing_verification as _manufacturing_verification
from . import manufacturing_export as _manufacturing_export
from . import manufacturing_requests as _manufacturing_requests
from . import manufacturing_render as _manufacturing_render
from .contracts import (
    FinalMaterialCollisionPart,
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    FeatureLike,
    FoldProfileSegment,
    IndicatorBoxPartSpec,
    ManufacturingContext,
    ManufacturingPolicy,
    PartExportResult,
    PartSpec,
)
from .sheetmetal_features import (
    BoxBodyFaceContext,
    CircleFeature,
    DoorIndicatorContext,
    FeatureAnchor,
    ProfileFeature,
    RectFeature,
    box_body_face_contexts_from_strip,
    feature_finished_point,
    feature_to_legacy_hole,
    legacy_hole_to_feature,
    resolve_door_indicator_layout,
)
from .sheetmetal_geometry import (
    EndCapAssemblySemantics,
    FourCornerTypePolicy,
    Vec2,
    resolve_endcap_policy_assembly_semantics,
)
from .sheetmetal_part_adapters import (
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_unknown_door_result,
    build_finished_reference_guide,
)
from .cabinet_types import policy as cabinet_family_policy


@dataclass(frozen=True)
class FoldGuide:
    """One authoritative final BEND segment.

    ``axis`` is the unfolded coordinate changed by the fold: ``x`` for a
    vertical BEND line and ``y`` for a horizontal BEND line. ``span_start`` /
    ``span_end`` are the orthogonal coordinates over which that physical bend
    actually exists.  Retained corner material outside this span must not
    receive that particular fold.
    """
    axis: str
    position: float
    span_start: float
    span_end: float


def fold_guides_from_final_scene(scene):
    """Extract normalized physical fold coverage from final BEND primitives."""
    from .sheetmetal_drawing import LinePrimitive

    guides = []
    for primitive in getattr(scene, "primitives", ()):
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(getattr(primitive, "layer", "")).upper() != "BEND":
            continue
        x1, y1 = float(primitive.p1.x), float(primitive.p1.y)
        x2, y2 = float(primitive.p2.x), float(primitive.p2.y)
        if abs(x1 - x2) <= 1e-7 and abs(y1 - y2) > 1e-9:
            guides.append(FoldGuide("x", (x1 + x2) / 2.0, min(y1, y2), max(y1, y2)))
        elif abs(y1 - y2) <= 1e-7 and abs(x1 - x2) > 1e-9:
            guides.append(FoldGuide("y", (y1 + y2) / 2.0, min(x1, x2), max(x1, x2)))
    return tuple(guides)


@dataclass(frozen=True)
class MaterialSegment:
    """One traceable unfolded-material segment used to derive blank envelope."""
    axis: str
    name: str
    length: float
    source: str

    def __post_init__(self):
        object.__setattr__(self, "axis", str(self.axis).upper())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "length", max(0.0, float(self.length)))
        object.__setattr__(self, "source", str(self.source))


@dataclass(frozen=True)
class UnfoldedBlankTopology:
    """Canonical physical-piece blank envelope derived from material chains."""
    piece_id: str
    x_segments: tuple[MaterialSegment, ...]
    y_segments: tuple[MaterialSegment, ...]
    source: str
    revision: int = 1

    @property
    def width(self) -> float:
        return sum(float(item.length) for item in self.x_segments)

    @property
    def height(self) -> float:
        return sum(float(item.length) for item in self.y_segments)

    @property
    def fingerprint(self) -> str:
        payload = {
            "piece_id": self.piece_id, "source": self.source, "revision": int(self.revision),
            "x": [(s.name, round(float(s.length), 9), s.source) for s in self.x_segments],
            "y": [(s.name, round(float(s.length), 9), s.source) for s in self.y_segments],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _profile_material_segments(axis: str, rows, *, source: str) -> tuple[MaterialSegment, ...]:
    result = []
    for index, row in enumerate(tuple(rows or ())):
        name = str(getattr(row, "phase6_key", None) or getattr(row, "core", None) or f"segment_{index}")
        result.append(MaterialSegment(axis, name, float(getattr(row, "length", 0.0)), source))
    return tuple(result)


@dataclass(frozen=True)
class PartRenderData:
    """Manufacturing-owned geometry ready for non-DXF renderers.

    ``material`` is the already-resolved sheet material polygon.  A renderer may
    triangulate/fold it, but must not rediscover holes, baseline entities or
    CornerType semantics from ``scene``. ``fold_guides`` carries the exact
    finite BEND coverage from the same final scene so retained material is not
    folded across a gap where no bend physically exists.
    """
    scene: object
    material: object
    fold_guides: tuple[FoldGuide, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    unfolded_topology: UnfoldedBlankTopology | None = None
    box_body_face_contexts: Mapping[str, BoxBodyFaceContext] | None = None


def collision_part_from_render_data(
    part_id: str, render_data: PartRenderData, *, true_thickness: float = 0.0,
    resolved_joints=(), legal_contact_semantics=(), solver_constraints=(), piece_transform=None,
) -> FinalMaterialCollisionPart:
    """Project committed render data into the neutral collision contract."""
    return FinalMaterialCollisionPart(
        part_id=str(part_id),
        material=render_data.material,
        scene=render_data.scene,
        fold_guides=tuple(render_data.fold_guides or ()),
        unfolded_topology=render_data.unfolded_topology,
        true_thickness=float(true_thickness),
        piece_transform=piece_transform,
        resolved_joints=tuple(resolved_joints or ()),
        legal_contact_semantics=tuple(legal_contact_semantics or ()),
        solver_constraints=tuple(solver_constraints or ()),
        diagnostic_metadata=dict(render_data.metadata or {}),
    )


@dataclass(frozen=True)
class UnfoldedBlankInfo:
    """Canonical unfolded material envelope measured from final material."""
    part_key: str
    width: float
    height: float
    area: float
    bounds: tuple[float, float, float, float]
    material_bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    topology_fingerprint: str = ""
    topology_source: str = ""


def _measure_one_unfolded_blank(render_data, *, part_key: str) -> UnfoldedBlankInfo:
    material = getattr(render_data, "material", None)
    if material is None or bool(getattr(material, "is_empty", True)):
        raise ValueError(f"unfolded material unavailable: {part_key}")
    minx, miny, maxx, maxy = map(float, material.bounds)
    topology = getattr(render_data, "unfolded_topology", None)
    if topology is None:
        # Compatibility for externally-created legacy PartRenderData. Production
        # builders below attach a traceable topology and never rely on this path.
        width = max(0.0, maxx - minx)
        height = max(0.0, maxy - miny)
        fingerprint = ""
        source = "LEGACY_FINAL_BOUNDS"
    else:
        width = float(topology.width)
        height = float(topology.height)
        fingerprint = str(topology.fingerprint)
        source = str(topology.source)
    return UnfoldedBlankInfo(
        part_key=str(part_key),
        width=width,
        height=height,
        area=float(material.area),
        bounds=(minx, miny, maxx, maxy),
        material_bounds=(minx, miny, maxx, maxy),
        topology_fingerprint=fingerprint,
        topology_source=source,
    )


def measure_unfolded_blanks(render_data, *, part_key: str = "") -> tuple[UnfoldedBlankInfo, ...]:
    """Measure every physical sheet from canonical final material.

    Multi-piece Box Body data is intentionally measured piece-by-piece; the
    exploded preview envelope is display-only and is never a manufacturable blank.
    """
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if pieces:
        root = str(part_key or "box_body")
        return tuple(
            _measure_one_unfolded_blank(
                piece.render_data,
                part_key=f"{root}:{piece.key}",
            )
            for piece in pieces
        )
    return (_measure_one_unfolded_blank(render_data, part_key=str(part_key or "part")),)


@dataclass(frozen=True)
class BoxBodyPieceRenderData:
    """One independently manufacturable physical Box Body piece."""
    key: str
    role: str
    formed_w_start: float
    formed_w_end: float
    fold_profile: tuple[FoldProfileSegment, ...]
    render_data: PartRenderData
    formed_outer_width: float | None = None
    formed_outer_height: float | None = None
    formed_y_offset: float = 0.0

    @property
    def formed_outer_dimensions(self) -> tuple[float, float]:
        width = (float(self.formed_w_end) - float(self.formed_w_start)) if self.formed_outer_width is None else float(self.formed_outer_width)
        if self.formed_outer_height is not None:
            height = float(self.formed_outer_height)
        else:
            topology = getattr(self.render_data, "unfolded_topology", None)
            height = float(topology.height) if topology is not None else float(self.render_data.material.bounds[3] - self.render_data.material.bounds[1])
        return width, height

    @property
    def material_dimensions(self) -> tuple[float, float]:
        topology = getattr(self.render_data, "unfolded_topology", None)
        if topology is not None:
            return float(topology.width), float(topology.height)
        minx, miny, maxx, maxy = map(float, self.render_data.material.bounds)
        return maxx - minx, maxy - miny


@dataclass(frozen=True)
class BoxBodyStructureRenderData:
    """Resolved multi-piece Box Body manufacturing data from one structure state.

    ``preview_render_data`` is an exploded 2D layout only and must never be
    mistaken for the canonical Z-strip span. ``canonical_strip_render_data``
    is built from the same BoxBodyPartSpec/Fold Profile and owns whole-strip
    dimensions used by summary/projection consumers.
    """
    structure_type: object
    pieces: tuple[BoxBodyPieceRenderData, ...]
    preview_render_data: PartRenderData
    canonical_strip_render_data: PartRenderData
    warnings: tuple[object, ...] = ()

    @property
    def scene(self):
        return self.preview_render_data.scene

    @property
    def material(self):
        return self.preview_render_data.material

    @property
    def fold_guides(self):
        return self.preview_render_data.fold_guides

    @property
    def box_body_face_contexts(self):
        return self.canonical_strip_render_data.box_body_face_contexts


def material_polygon_from_final_scene(scene):
    """Resolve final material once at the manufacturing boundary.

    AE scene builders emit the authoritative structural CUTTING outline first.
    Later CUTTING contours are manufacturing cut-outs/features. Some legacy
    stretched baselines can also carry a mapped copy of the old structural
    outline; a same-sheet-bounds contour is therefore ignored rather than
    interpreted as one giant hole.
    """
    from shapely.geometry import LineString, Point, Polygon
    from .cutting_material import material_from_cutting_components
    from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive

    primary = None
    secondary = []
    linework = []

    for primitive in getattr(scene, "primitives", ()):
        if str(getattr(primitive, "layer", "")).upper() != "CUTTING":
            continue
        if isinstance(primitive, PolylinePrimitive):
            pts = [(float(p.x), float(p.y)) for p in primitive.points]
            if primitive.closed and len(pts) >= 3:
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or float(poly.area) <= 1e-9:
                    continue
                if primary is None:
                    primary = poly
                else:
                    secondary.append(poly)
            elif len(pts) >= 2:
                linework.extend(
                    LineString((a, b)) for a, b in zip(pts, pts[1:]) if a != b
                )
        elif isinstance(primitive, LinePrimitive):
            a = (float(primitive.p1.x), float(primitive.p1.y))
            b = (float(primitive.p2.x), float(primitive.p2.y))
            if a != b:
                linework.append(LineString((a, b)))
        elif isinstance(primitive, CirclePrimitive) and float(primitive.radius) > 0:
            secondary.append(
                Point(float(primitive.center.x), float(primitive.center.y)).buffer(
                    float(primitive.radius), quad_segs=32
                )
            )

    return material_from_cutting_components(
        primary=primary,
        secondary=secondary,
        linework=linework,
    )

def _translated_scene(scene, dx: float, dy: float = 0.0):
    from .sheetmetal_drawing import (
        DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive, TextPrimitive,
    )
    from .sheetmetal_geometry import Vec2
    def point(p):
        return Vec2(float(p.x) + float(dx), float(p.y) + float(dy))
    out = DrawingScene()
    for primitive in scene.primitives:
        if isinstance(primitive, PolylinePrimitive):
            out.add(PolylinePrimitive(tuple(point(p) for p in primitive.points), primitive.layer, primitive.closed, primitive.color))
        elif isinstance(primitive, LinePrimitive):
            out.add(LinePrimitive(point(primitive.p1), point(primitive.p2), primitive.layer, primitive.color))
        elif isinstance(primitive, CirclePrimitive):
            out.add(CirclePrimitive(point(primitive.center), primitive.radius, primitive.layer, primitive.color,
                                    primitive.source_type, primitive.source_id))
        elif isinstance(primitive, TextPrimitive):
            out.add(TextPrimitive(primitive.text, point(primitive.insert), primitive.layer, primitive.char_height, primitive.attachment_point, primitive.color))
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive)!r}")
    return out


def _exploded_box_body_preview(pieces, *, gap=30.0):
    from .sheetmetal_drawing import DrawingScene
    from shapely.affinity import translate as shp_translate
    from shapely.ops import unary_union
    scene = DrawingScene()
    materials = []
    cursor = 0.0
    for piece in pieces:
        minx, _miny, maxx, _maxy = map(float, piece.render_data.material.bounds)
        dx = cursor - minx
        moved = _translated_scene(piece.render_data.scene, dx)
        scene.extend(moved.primitives)
        materials.append(shp_translate(piece.render_data.material, xoff=dx))
        cursor += (maxx - minx) + float(gap)
    material = unary_union(materials)
    return PartRenderData(scene=scene, material=material, fold_guides=())
