"""#2690: compose already-certified physical flat scenes in one DXF.

This module never calculates a blank or maps world XYZ to manufacturing UV.
Each incoming piece is an Engine-resolved independent flat DrawingScene; all
material/cutting/fold features are translated rigidly without re-solving.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import os
import tempfile
import shutil

import ezdxf
from shapely.affinity import translate as move_material
from shapely.ops import unary_union

from .contracts import ResolvedManufacturingGeometry
from .dxf_serialization import save_scene_dxf
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, _reject_unapproved_nfb_pad_ear_manufacturing,
    _validate_nfb_base_part_scope, reject_unverified_receiving_nfb_tier_base,
    resolved_physical_render_parts,
)
from .manufacturing_render_data import PartRenderData, FoldGuide
from .manufacturing_verification import verify_saved_part_render_data_dxf
from .panel_naming import normalize_panel_name
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive, TextPrimitive,
)
from .sheetmetal_geometry import Vec2


@dataclass(frozen=True)
class ComposedPhysicalSheet:
    panel_name: str
    physical_id: str
    offset: tuple[float, float]
    flat_bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class ComposedPanelDxfResult:
    path: str
    sheets: tuple[ComposedPhysicalSheet, ...]


def _finite(value):
    if isinstance(value, bool):
        raise ValueError("COMPOSED_DXF_INVALID_FLAT_COORDINATE")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("COMPOSED_DXF_INVALID_FLAT_COORDINATE") from exc
    if not isfinite(result):
        raise ValueError("COMPOSED_DXF_INVALID_FLAT_COORDINATE")
    return result


def _scene_bounds(scene):
    xs, ys = [], []
    for p in scene.primitives:
        if isinstance(p, PolylinePrimitive):
            coords = [(pt.x, pt.y) for pt in p.points]
            if len(coords) < 2:
                raise ValueError("COMPOSED_DXF_DEGENERATE_FLAT_SCENE")
        elif isinstance(p, LinePrimitive):
            coords = [(p.p1.x, p.p1.y), (p.p2.x, p.p2.y)]
        elif isinstance(p, CirclePrimitive):
            r = _finite(p.radius)
            if r <= 0:
                raise ValueError("COMPOSED_DXF_INVALID_RADIUS")
            x, y = _finite(p.center.x), _finite(p.center.y)
            coords = [(x-r, y-r), (x+r, y+r)]
        elif isinstance(p, TextPrimitive):
            if _finite(p.char_height) <= 0:
                raise ValueError("COMPOSED_DXF_INVALID_TEXT_HEIGHT")
            coords = [(p.insert.x, p.insert.y)]
        else:
            raise ValueError("COMPOSED_DXF_UNSUPPORTED_PRIMITIVE")
        for x, y in coords:
            xs.append(_finite(x))
            ys.append(_finite(y))
    if not xs:
        raise ValueError("COMPOSED_DXF_EMPTY_FLAT_SCENE")
    return min(xs), min(ys), max(xs), max(ys)


def _translated(primitive, dx, dy):
    def xy(p):
        return Vec2(_finite(p.x) + dx, _finite(p.y) + dy)

    if isinstance(primitive, PolylinePrimitive):
        return PolylinePrimitive(tuple(xy(p) for p in primitive.points),
                                 primitive.layer, primitive.closed, primitive.color,
                                 primitive.semantic_id)
    if isinstance(primitive, LinePrimitive):
        return LinePrimitive(xy(primitive.p1), xy(primitive.p2),
                             primitive.layer, primitive.color)
    if isinstance(primitive, CirclePrimitive):
        return CirclePrimitive(xy(primitive.center), primitive.radius,
                               primitive.layer, primitive.color,
                               primitive.source_type, primitive.source_id)
    if isinstance(primitive, TextPrimitive):
        return TextPrimitive(primitive.text, xy(primitive.insert), primitive.layer,
                             primitive.char_height, primitive.attachment_point,
                             primitive.color, primitive.semantic_id)
    raise ValueError("COMPOSED_DXF_UNSUPPORTED_PRIMITIVE")


def _shift_guide(guide, dx, dy):
    if guide.axis == "x":
        return FoldGuide("x", guide.position + dx,
                         guide.span_start + dy, guide.span_end + dy)
    if guide.axis == "y":
        return FoldGuide("y", guide.position + dy,
                         guide.span_start + dx, guide.span_end + dx)
    raise ValueError("COMPOSED_DXF_UNKNOWN_FOLD_AXIS")


def _numbers(values):
    return tuple(round(_finite(x), 7) for x in values)


def _color(value):
    return 211 if value is None else value


def _source_signature(primitive):
    layer = str(primitive.layer).upper()
    color = primitive.color
    if isinstance(primitive, PolylinePrimitive):
        return (layer, "POLYLINE", _numbers(v for p in primitive.points
                                            for v in (p.x, p.y)),
                bool(primitive.closed), color)
    if isinstance(primitive, LinePrimitive):
        return (layer, "LINE", _numbers((primitive.p1.x, primitive.p1.y,
                                        primitive.p2.x, primitive.p2.y)), color)
    if isinstance(primitive, CirclePrimitive):
        return (layer, "CIRCLE", _numbers((primitive.center.x, primitive.center.y,
                                          primitive.radius)), color)
    if isinstance(primitive, TextPrimitive):
        return (layer, "TEXT", primitive.text,
                _numbers((primitive.insert.x, primitive.insert.y,
                          primitive.char_height)),
                int(primitive.attachment_point), _color(color) if layer=="MARKING" else color)
    raise ValueError("COMPOSED_DXF_UNSUPPORTED_PRIMITIVE")


def _actual_signature(entity):
    layer = str(entity.dxf.layer).upper()
    kind = entity.dxftype()
    color = entity.dxf.get("color", None)
    if kind == "LWPOLYLINE":
        return (layer, "POLYLINE",
                _numbers(v for pt in entity.get_points("xy") for v in pt),
                bool(entity.closed), color)
    if kind == "LINE":
        return (layer, "LINE", _numbers((entity.dxf.start.x, entity.dxf.start.y,
                                        entity.dxf.end.x, entity.dxf.end.y)), color)
    if kind == "CIRCLE":
        return (layer, "CIRCLE", _numbers((entity.dxf.center.x, entity.dxf.center.y,
                                          entity.dxf.radius)), color)
    if kind == "MTEXT":
        return (layer, "TEXT", entity.plain_text(),
                _numbers((entity.dxf.insert.x, entity.dxf.insert.y,
                          entity.dxf.char_height)),
                int(entity.dxf.attachment_point), color)
    raise ValueError("COMPOSED_DXF_UNEXPECTED_DXF_ENTITY:" + kind)


def _source_rows(panels):
    """Return physically owned, canonical input rows; never forge certification."""
    groups = []
    names = set()
    for name, geometry in tuple(panels or ()):
        panel_name = normalize_panel_name(name)
        if panel_name.casefold() in names:
            raise ValueError("COMPOSED_DXF_DUPLICATE_PANEL_NAME")
        names.add(panel_name.casefold())
        if not isinstance(geometry, ResolvedManufacturingGeometry):
            raise ValueError("COMPOSED_DXF_FINAL_SCENE_REQUIRED")
        rows = tuple(resolved_physical_render_parts(geometry))
        if not rows or len({key for key, _ in rows}) != len(rows):
            raise ValueError("COMPOSED_DXF_PHYSICAL_INVENTORY_INVALID")
        guard_rows = tuple((panel_name + ":" + key, "", render)
                           for key, render in rows)
        _reject_unapproved_nfb_pad_ear_manufacturing(guard_rows)
        _validate_nfb_base_part_scope(guard_rows, part_only=False)
        for key, render in rows:
            reject_unverified_receiving_nfb_tier_base(
                render, output_key=panel_name + ":" + key,
            )
            meta = getattr(render, "metadata", None) or {}
            if (meta.get("baseline_fit_error")
                    or meta.get("receiving_base_plate_unconfigured") is True
                    or (meta.get("nfb_v5_trial_status")
                        and meta.get("nfb_trial_export_approved") is not True)):
                raise ValueError("COMPOSED_DXF_SOURCE_NOT_MANUFACTURING_APPROVED")
            if not isinstance(render, PartRenderData) or render.scene is None:
                raise ValueError("COMPOSED_DXF_PHYSICAL_FLAT_SCENE_REQUIRED")
        # The Engine's canonical box-body pieces are ordered by the owner
        # (formed_w_start), not by a guessed world-coordinate DXF projection.
        body = [(key, data) for key, data in rows if key == "box_body"
                or key.startswith("box_body:")]
        others = [(key, data) for key, data in rows if (key, data) not in body]
        groups.append((panel_name, tuple(body + others)))
    if not groups:
        raise ValueError("COMPOSED_DXF_EMPTY_PANELS")
    return tuple(sorted(groups, key=lambda row: (row[0].casefold(), row[0])))


def _compose(rows, *, gap):
    scene = DrawingScene()
    sheet_receipts = []
    originals = []
    translated_materials = []
    translated_guides = []
    y_cursor = 0.0
    for panel_name, pieces in rows:
        x_cursor = 0.0
        row_height = 0.0
        for physical_id, render in pieces:
            bounds = _scene_bounds(render.scene)
            x0, y0, x1, y1 = bounds
            dx, dy = x_cursor-x0, y_cursor-y0
            moved = [_translated(p, dx, dy) for p in render.scene.primitives]
            scene.extend(moved)
            translated_materials.append(move_material(render.material, xoff=dx, yoff=dy))
            translated_guides.extend(_shift_guide(g, dx, dy) for g in render.fold_guides)
            sheet_receipts.append(ComposedPhysicalSheet(
                panel_name, physical_id, (dx, dy), bounds,
            ))
            originals.append((panel_name, physical_id, render))
            width, height = x1-x0, y1-y0
            x_cursor += width + gap
            row_height = max(row_height, height)
            # Deliberate CHECK-only provenance label outside the flat blank.
            scene.add(TextPrimitive(
                physical_id, Vec2(dx+x0, y_cursor-gap/3), "CHECK",
                5.0, 1, 2, "composed_physical_source",
            ))
        scene.add(TextPrimitive(
            panel_name, Vec2(0.0, y_cursor + row_height + gap/2),
            "CHECK", 9.0, 1, 2, "composed_panel_name",
        ))
        y_cursor += row_height + 2*gap
    combined = PartRenderData(
        scene=scene, material=unary_union(translated_materials),
        fold_guides=tuple(translated_guides),
    )
    return combined, tuple(sheet_receipts), tuple(originals)


def save_composed_panel_dxf(
    panels, output_path, *, pre_commit_guard, overwrite=False, gap=60.0,
):
    """Publish one staged, independently reopened multi-panel flat DXF.

    The caller must present already certified Engine results plus a source
    fingerprint guard.  This is NOT a new whole-Receiving MFG-2/NC release.
    """
    if not callable(pre_commit_guard):
        raise ValueError("COMPOSED_DXF_PRECOMMIT_SOURCE_GUARD_REQUIRED")
    if type(overwrite) is not bool or _finite(gap) < 20:
        raise ValueError("COMPOSED_DXF_INVALID_EXPORT_POLICY")
    path = Path(output_path)
    if path.suffix.lower() != ".dxf" or not path.stem or path.name in (".dxf", "..dxf"):
        raise ValueError("COMPOSED_DXF_INVALID_OUTPUT_PATH")
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))
    rows = _source_rows(panels)
    pre_commit_guard()
    composite, sheets, originals = _compose(rows, gap=float(gap))
    # The original per-piece authority is checked independently, not inferred
    # by counting the final merged file as one successful part.
    root = path.parent
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".whd-composed-stage-", dir=str(root)))
    try:
        for index, (_, physical_id, render) in enumerate(originals):
            individual = stage / f"source-{index}.dxf"
            save_scene_dxf(individual, render.scene)
            receipt = verify_saved_part_render_data_dxf(render, individual)
            if not receipt.ok:
                raise ValueError("COMPOSED_DXF_ORIGINAL_FLAT_ROUNDTRIP_FAILED:" + physical_id)
        staged = stage / path.name
        save_scene_dxf(staged, composite.scene)
        # Full independent material and BEND acceptance covers the whole sheet.
        verified = verify_saved_part_render_data_dxf(composite, staged)
        if not verified.ok:
            raise ValueError("COMPOSED_DXF_COMBINED_ROUNDTRIP_FAILED:" +
                             ",".join(issue.category for issue in verified.issues))
        # Strict second DXF reopen checks every original primitive, including
        # arbitrary-layer MARKING, BLIND_HOLE, CHECK/text, arcs-as-polylines,
        # colors, geometry and provenance labels. No serializer is used to
        # produce the *actual* side of this comparison.
        actual = Counter(_actual_signature(entity)
                         for entity in ezdxf.readfile(staged).modelspace())
        expected = Counter(_source_signature(p) for p in composite.scene.primitives)
        if actual != expected:
            raise ValueError("COMPOSED_DXF_EXACT_PRIMITIVE_READBACK_MISMATCH")
        pre_commit_guard()  # Source drift after staging must not replace output.
        _atomic_commit_staged_dxfs({"composed": staged}, root, overwrite=overwrite)
        return ComposedPanelDxfResult(str(path), sheets)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
