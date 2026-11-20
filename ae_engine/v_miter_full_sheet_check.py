# -*- coding: utf-8 -*-
"""#3317 whole-piece V-miter diagnostic scene and checked DXF.

The only sheet contour in this module is a CHECK hypothesis from the
already-qualified original-source/factory mother. Original production
CUTTING/BEND/MARKING remains unchanged and is drawn only on DATUM.
Any exported DXF here is explicitly un-certified inspection geometry.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile

import ezdxf
from shapely.geometry import Polygon

from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive,
)
from .sheetmetal_geometry_core import GeometryError
from .v_miter_ideal_mating import VMiterIdealMatingCandidate
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck, _single_source_material,
)

_CHECK_LAYERS = frozenset(("CHECK", "DATUM"))


def build_v_miter_whole_sheet_check_scene(
    render_data: PartRenderData,
    check: VMiterSourceBoundSharpCheck,
    ideal: VMiterIdealMatingCandidate,
) -> DrawingScene:
    """One 2D whole-sheet CHECK, with source original and unchanged BEND datums.

    The candidate outline is already the remainder of the single source
    stock after substituting one V: it retains all other original corner
    reliefs. Never replace the official FinalScene or convert to CUTTING.
    """
    if (not isinstance(render_data, PartRenderData)
            or not isinstance(check, VMiterSourceBoundSharpCheck)
            or not isinstance(ideal, VMiterIdealMatingCandidate)):
        raise GeometryError("V_MITER_FULL_SHEET_SOURCE_INVALID")
    original = _single_source_material(render_data.scene)
    proposal = Polygon(((p.x, p.y) for p in check.remaining_outline))
    removed = Polygon(((p.x, p.y) for p in check.removed_corner_outline))
    if any((x.is_empty or not x.is_valid or x.geom_type != "Polygon" or
            x.area <= 0 or x.interiors) for x in (proposal, removed)):
        raise GeometryError("V_MITER_FULL_SHEET_CANDIDATE_TOPOLOGY_INVALID")
    if (not math.isclose(proposal.area, check.remaining_material_area_mm2, abs_tol=1e-6)
            or not math.isclose(removed.area, check.removed_material_area_mm2, abs_tol=1e-6)
            or not math.isclose(
                check.source_material_area_mm2,
                proposal.area + removed.area, abs_tol=1e-6,
            )
            or proposal.intersection(removed).area > 1e-6
            or original.difference(proposal.union(removed)).area > 1e-6):
        raise GeometryError("V_MITER_FULL_SHEET_SOURCE_RECONCILIATION_FAILED")

    # Display actual pre-existing physical CUTTING as DATUM; the *only*
    # proposed contour is CHECK. BENDs remain reference, not press actions.
    scene = DrawingScene([
        PolylinePrimitive(
            tuple(next(p for p in render_data.scene.primitives
                       if isinstance(p, PolylinePrimitive)
                       and p.layer == "CUTTING").points),
            layer="DATUM", closed=True, color=6,
            semantic_id="v_miter_original_factory_corner_datum",
        ),
        PolylinePrimitive(
            check.remaining_outline, layer="CHECK", closed=True, color=2,
            semantic_id="v_miter_whole_sheet_unverified_remaining",
        ),
        PolylinePrimitive(
            check.removed_corner_outline, layer="CHECK", closed=True, color=2,
            semantic_id="v_miter_single_corner_removed_unverified",
        ),
        LinePrimitive(*ideal.first_flat_miter_ray, layer="CHECK", color=2),
        LinePrimitive(*ideal.second_flat_miter_ray, layer="CHECK", color=2),
    ])
    for row in render_data.scene.primitives:
        if isinstance(row, LinePrimitive) and row.layer == "BEND":
            scene.add(LinePrimitive(row.p1, row.p2, layer="DATUM", color=6))
        elif isinstance(row, CirclePrimitive) and row.layer == "CUTTING":
            scene.add(CirclePrimitive(row.center, row.radius,
                                      layer="DATUM", color=6))
    if any(row.layer not in _CHECK_LAYERS for row in scene.primitives):
        raise GeometryError("V_MITER_FULL_SHEET_MANUFACTURING_LAYER_FORBIDDEN")
    return scene


def _verify_check_dxf_reopen(scene: DrawingScene, filepath: Path) -> None:
    """Compare every serialized geometry type/layer/vertex after DXF reopen."""
    if not isinstance(scene, DrawingScene) or not scene.primitives:
        raise GeometryError("V_MITER_FULL_SHEET_CHECK_EMPTY")
    expected = tuple(scene.primitives)
    if any(row.layer not in _CHECK_LAYERS for row in expected):
        raise GeometryError("V_MITER_FULL_SHEET_MANUFACTURING_LAYER_FORBIDDEN")
    reopened = tuple(ezdxf.readfile(filepath).modelspace())
    if len(reopened) != len(expected):
        raise GeometryError("V_MITER_CHECK_DXF_REOPEN_ENTITY_COUNT_MISMATCH")

    def eq(a, b):
        return math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-7)

    for source, entity in zip(expected, reopened):
        if entity.dxf.layer != source.layer or entity.dxf.layer not in _CHECK_LAYERS:
            raise GeometryError("V_MITER_CHECK_DXF_REOPEN_LAYER_MISMATCH")
        if isinstance(source, PolylinePrimitive):
            if entity.dxftype() != "LWPOLYLINE" or bool(entity.closed) != source.closed:
                raise GeometryError("V_MITER_CHECK_DXF_REOPEN_POLYLINE_TYPE_MISMATCH")
            coords = tuple(entity.get_points("xy"))
            if len(coords) != len(source.points) or any(
                not eq(x, p.x) or not eq(y, p.y)
                for (x, y), p in zip(coords, source.points)
            ):
                raise GeometryError("V_MITER_CHECK_DXF_REOPEN_OUTLINE_MISMATCH")
        elif isinstance(source, LinePrimitive):
            if entity.dxftype() != "LINE" or any(
                not eq(a, b) for a, b in (
                    (entity.dxf.start.x, source.p1.x),
                    (entity.dxf.start.y, source.p1.y),
                    (entity.dxf.end.x, source.p2.x),
                    (entity.dxf.end.y, source.p2.y),
                )
            ):
                raise GeometryError("V_MITER_CHECK_DXF_REOPEN_LINE_MISMATCH")
        elif isinstance(source, CirclePrimitive):
            if entity.dxftype() != "CIRCLE" or any(
                not eq(a, b) for a, b in (
                    (entity.dxf.center.x, source.center.x),
                    (entity.dxf.center.y, source.center.y),
                    (entity.dxf.radius, source.radius),
                )
            ):
                raise GeometryError("V_MITER_CHECK_DXF_REOPEN_CIRCLE_MISMATCH")
        else:
            raise GeometryError("V_MITER_CHECK_DXF_SOURCE_ENTITY_UNSUPPORTED")


def save_v_miter_whole_sheet_check_dxf(
    scene: DrawingScene, output_path: str | os.PathLike[str],
    *, overwrite: bool = False,
) -> str:
    """Atomic diagnostic-only DXF: staged → reopened → exact compare → commit.

    Strictly separate from production export: no manufacturing CUTTING,
    BEND or MARKING can pass; a failed reopen never replaces target.
    """
    if type(overwrite) is not bool:
        raise GeometryError("V_MITER_CHECK_DXF_OVERWRITE_FLAG_INVALID")
    if not isinstance(scene, DrawingScene) or not scene.primitives or any(
        row.layer not in _CHECK_LAYERS for row in scene.primitives
    ):
        raise GeometryError("V_MITER_FULL_SHEET_MANUFACTURING_LAYER_FORBIDDEN")
    # Require the Engine-generated full-sheet contour, not an arbitrary
    # CHECK-only Scene masquerading as a V whole-sheet source.
    if sum(
        isinstance(row, PolylinePrimitive)
        and row.layer == "CHECK"
        and row.semantic_id == "v_miter_whole_sheet_unverified_remaining"
        and row.closed
        for row in scene.primitives
    ) != 1:
        raise GeometryError("V_MITER_CHECK_DXF_FULL_SHEET_SOURCE_REQUIRED")
    try:
        output = Path(output_path)
    except (TypeError, ValueError, OSError) as exc:
        raise GeometryError("V_MITER_CHECK_DXF_PATH_INVALID") from exc
    if output.suffix.lower() != ".dxf":
        raise GeometryError("V_MITER_CHECK_DXF_PATH_MUST_END_DXF")
    if not output.parent.is_dir():
        raise GeometryError("V_MITER_CHECK_DXF_DIRECTORY_MISSING")
    if output.exists() and not overwrite:
        raise FileExistsError(str(output))
    from .dxf_serialization import save_scene_dxf
    fd, temporary = tempfile.mkstemp(
        prefix=".v_miter_check_", suffix=".dxf", dir=output.parent
    )
    os.close(fd)
    try:
        save_scene_dxf(temporary, scene)
        _verify_check_dxf_reopen(scene, Path(temporary))
        if output.exists() and not overwrite:
            raise FileExistsError(str(output))
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(output)
