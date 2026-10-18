"""#1959 manually moved holes: CADCraft isolated DXF -> WHD existing Session.

Translation-only first GUI slice. No free-form DXF import: one specific WHD-created
isolated drawing, exact original feature order, unchanged shapes, dimensions and
manufacturing semantics. CADCraft is never the manufacturing source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import math
from pathlib import Path

import ezdxf

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, Vec2,
    feature_is_strictly_within_surface, resolve_surface_features,
)
from gui_modules.editors.cadcraft_command_session_bridge import (
    CadcraftSessionStage, _polygon, _MAX_EXCHANGE_BYTES,
)
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from tools.issue1959_whd_cadcraft_command_draw import (
    CadcraftCommandProofError, from_whd_resolved, verify_dxf,
    _near, _number, _ring,
)


@dataclass(frozen=True)
class ManualReturnTicket:
    """Live, editor-owned provenance. Never loaded from the untrusted DXF."""
    session: Phase6HoleEditorSession
    output: Path
    original_sha256: str
    context_key: str
    original: tuple
    surface: object
    width: float
    height: float


@dataclass
class ManualReturnPreview:
    stage: CadcraftSessionStage
    moves: tuple[tuple[int, float, float], ...]

    def confirm(self):
        return self.stage.confirm()

    def cancel(self):
        return self.stage.cancel()


def _read_limited(path: Path) -> bytes:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= _MAX_EXCHANGE_BYTES:
            raise CadcraftCommandProofError("INVALID_EXCHANGE_FILE_SIZE")
        data = path.read_bytes()
    except OSError as exc:
        raise CadcraftCommandProofError("CADCRAFT_EXCHANGE_NOT_READABLE") from exc
    if not 0 < len(data) <= _MAX_EXCHANGE_BYTES:
        raise CadcraftCommandProofError("INVALID_EXCHANGE_FILE_SIZE")
    return data


def _eligible(feature) -> bool:
    # An approved NFB CSV hole or an authored manufacturing source must not be
    # silently de-linked from its governing source by this prototype.
    return (
        isinstance(feature, (CircleFeature, RectFeature, ProfileFeature))
        and feature.layer == "CUTTING"
        and not feature.source_type
        and not feature.source_params
        and not getattr(feature, "layered_profiles", ())
        and not getattr(feature, "add_centerline", False)
    )


def create_manual_return_ticket(*, output: Path, features, session,
                                surface, width: float, height: float):
    """Issue provenance only for the exact freshly proven WHD->CADCraft DXF."""
    if not isinstance(session, Phase6HoleEditorSession):
        raise CadcraftCommandProofError("WHD_PHASE6_SESSION_REQUIRED")
    snapshot = session.snapshot()
    originals = tuple(features)
    if (session.has_active_edit or not originals or len(originals) > 100
            or snapshot.features != originals or not all(map(_eligible, originals))):
        raise CadcraftCommandProofError("UNSUPPORTED_OR_DIRTY_WHD_SOURCE")
    w, h = float(width), float(height)
    if not all(math.isfinite(v) and v > 0 for v in (w, h)):
        raise CadcraftCommandProofError("INVALID_WHD_FINISHED_FACE_DIMENSIONS")
    expected = from_whd_resolved(
        tuple(resolve_surface_features(surface, originals, w, h))
    )
    path = Path(output).resolve(strict=True)
    data = _read_limited(path)
    verify_dxf(path, expected)
    if sha256(_read_limited(path)).digest() != sha256(data).digest():
        raise CadcraftCommandProofError("CADCRAFT_FILE_CHANGED_DURING_TICKET")
    return ManualReturnTicket(
        session, path, sha256(data).hexdigest(), snapshot.context_key,
        originals, surface, w, h,
    )


def _dxf_moves(output: Path, original: tuple, surface, width, height):
    """Only pure translations, by preserved entity order; no resize/add/delete."""
    expected = from_whd_resolved(tuple(
        resolve_surface_features(surface, original, width, height)
    ))
    try:
        doc = ezdxf.readfile(output)
    except (OSError, ValueError, TypeError, ezdxf.DXFError) as exc:
        raise CadcraftCommandProofError("CADCRAFT_DXF_PARSE_FAILED") from exc
    if doc.header.get("$INSUNITS") != 4 or doc.header.get("$MEASUREMENT") != 1:
        raise CadcraftCommandProofError("MILLIMETRE_HEADER_MISMATCH")
    entities = list(doc.modelspace())
    if len(entities) != len(original):
        raise CadcraftCommandProofError("ENTITY_COUNT_MISMATCH")
    moves = []
    updated = []
    for index, (entity, instruction, feature) in enumerate(zip(entities, expected, original)):
        if entity.dxf.layer != "0":
            raise CadcraftCommandProofError("UNEXPECTED_LAYER")
        extrusion = tuple(entity.dxf.get("extrusion", (0, 0, 1)))
        if len(extrusion) != 3 or not all(
            _near(_number(a), b) for a, b in zip(extrusion, (0, 0, 1))
        ):
            raise CadcraftCommandProofError("UNEXPECTED_EXTRUSION")
        if instruction.kind == "circle":
            if entity.dxftype() != "CIRCLE":
                raise CadcraftCommandProofError("CHANGED_ENTITY_TYPE")
            center = entity.dxf.center
            x, y, z, radius = map(_number, (center.x, center.y, center.z, entity.dxf.radius))
            if not _near(z, 0) or not _near(radius, instruction.radius):
                raise CadcraftCommandProofError("CIRCLE_SIZE_OR_PLANE_CHANGED")
            dx, dy = x-instruction.points[0][0], y-instruction.points[0][1]
        else:
            if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
                raise CadcraftCommandProofError("OPEN_OR_CHANGED_PROFILE")
            if not _near(_number(entity.dxf.get("const_width", 0)), 0):
                raise CadcraftCommandProofError("POLYLINE_WIDTH_CHANGED")
            if not _near(_number(entity.dxf.get("elevation", 0)), 0):
                raise CadcraftCommandProofError("POLYLINE_ELEVATION_CHANGED")
            vertices = list(entity.get_points("xyseb"))
            if len(vertices) != len(instruction.points):
                raise CadcraftCommandProofError("VERTEX_COUNT_MISMATCH")
            points = tuple((_number(x), _number(y)) for x, y, *_ in vertices)
            _ring(points)
            dx = points[0][0]-instruction.points[0][0]
            dy = points[0][1]-instruction.points[0][1]
            for (x, y, start, end, bulge), (ex, ey) in zip(vertices, instruction.points):
                if (not all(_near(_number(v), 0) for v in (start, end, bulge))
                        or not _near(_number(x), ex+dx)
                        or not _near(_number(y), ey+dy)):
                    raise CadcraftCommandProofError("SHAPE_OR_ROTATION_CHANGED")
        if abs(dx) > 1_000_000 or abs(dy) > 1_000_000:
            raise CadcraftCommandProofError("OUT_OF_RANGE_TRANSLATION")
        candidate = replace(feature, offset=Vec2(
            _number(feature.offset.x+dx), _number(feature.offset.y+dy)
        ))
        if not feature_is_strictly_within_surface(surface, candidate, width, height):
            raise CadcraftCommandProofError("OUTSIDE_WHD_PHYSICAL_SURFACE")
        updated.append(candidate)
        if not _near(dx, 0) or not _near(dy, 0):
            moves.append((index, dx, dy))
    if not moves:
        raise CadcraftCommandProofError("NO_MANUAL_HOLE_POSITION_CHANGE")
    footprints = [_polygon(feature, width, height) for feature in updated]
    for index, footprint in enumerate(footprints):
        for preceding in footprints[:index]:
            if footprint.intersects(preceding):
                raise CadcraftCommandProofError("WHD_FEATURE_COLLISION")
    return tuple(updated), tuple(moves)


def stage_manual_cadcraft_return(ticket: ManualReturnTicket) -> ManualReturnPreview:
    """Fail closed before preview_all, then verify unchanged DXF at Confirm."""
    session = ticket.session
    snapshot = session.snapshot()
    if (session.has_active_edit or snapshot.context_key != ticket.context_key
            or snapshot.features != ticket.original):
        raise CadcraftCommandProofError("STALE_OR_MODIFIED_WHD_SESSION")
    data = _read_limited(ticket.output)
    digest = sha256(data).hexdigest()
    if digest == ticket.original_sha256:
        raise CadcraftCommandProofError("CADCRAFT_DRAWING_NOT_EDITED")
    updated, moves = _dxf_moves(
        ticket.output, ticket.original, ticket.surface, ticket.width, ticket.height
    )
    if sha256(_read_limited(ticket.output)).hexdigest() != digest:
        raise CadcraftCommandProofError("CADCRAFT_OUTPUT_CHANGED_DURING_VALIDATION")
    if session.snapshot() != snapshot:
        raise CadcraftCommandProofError("WHD_SESSION_CHANGED_DURING_VALIDATION")
    session.execute(HoleEditorAction.preview_all(updated))
    stage = CadcraftSessionStage(
        session=session, output=ticket.output, output_sha256=digest,
        context_key=ticket.context_key, preview_features=updated,
    )
    return ManualReturnPreview(stage=stage, moves=moves)
