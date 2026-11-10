"""#2690: compose already-certified physical flat scenes in one DXF.

This module never calculates a blank or maps world XYZ to manufacturing UV.
Each incoming piece is an Engine-resolved independent flat DrawingScene; all
material/cutting/fold features are translated rigidly without re-solving.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
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
from .manufacturing_render_data import (
    PartRenderData, FoldGuide, BoxBodyStructureRenderData,
)
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


def _source_rows(panels, *, preserve_input_order=False, box_body_owner_by_panel=None,
                 _verified_nfb_pair_parts=None):
    """Return physically owned, canonical input rows; never forge certification."""
    groups = []
    names = set()
    # Only the Engine's freshly re-resolved and Save->Reload-verified NFB
    # pair transaction may supply these per-panel physical part IDs. This
    # authorizes their PART_ONLY flat placement, NOT whole-cabinet MFG-2.
    if _verified_nfb_pair_parts is not None and not isinstance(
        _verified_nfb_pair_parts, Mapping
    ):
        raise TypeError("COMPOSED_DXF_NFB_PAIR_PROOF_INVALID")
    verified_pairs = _verified_nfb_pair_parts or {}
    if box_body_owner_by_panel is not None and not isinstance(
        box_body_owner_by_panel, Mapping
    ):
        raise TypeError("COMPOSED_DXF_BOX_BODY_OWNER_MAPPING_REQUIRED")
    for name, geometry in tuple(panels or ()):
        panel_name = normalize_panel_name(name)
        if panel_name.casefold() in names:
            raise ValueError("COMPOSED_DXF_DUPLICATE_PANEL_NAME")
        names.add(panel_name.casefold())
        if not isinstance(geometry, ResolvedManufacturingGeometry):
            raise ValueError("COMPOSED_DXF_FINAL_SCENE_REQUIRED")
        rows = tuple(resolved_physical_render_parts(geometry))
        verified = frozenset(verified_pairs.get(panel_name, ()))
        if verified:
            physical = {key for key, _ in rows}
            doors = {key for key in verified if key.startswith("inner_door:")}
            bases = {key for key in verified
                     if key == "base_plate" or key.startswith("base_plate:nfb_layer:")}
            if (not doors or not bases or len(doors) != 1
                    or verified != doors | bases or not verified <= physical):
                raise ValueError("COMPOSED_DXF_NFB_PAIR_INVENTORY_MISMATCH")
        if not rows or len({key for key, _ in rows}) != len(rows):
            raise ValueError("COMPOSED_DXF_PHYSICAL_INVENTORY_INVALID")
        guard_rows = tuple((key, "", render)
                           for key, render in rows)
        _reject_unapproved_nfb_pad_ear_manufacturing(guard_rows)
        _validate_nfb_base_part_scope(
            tuple(row for row in guard_rows if row[0] not in verified),
            part_only=False,
        )
        for key, render in rows:
            if key not in verified:
                reject_unverified_receiving_nfb_tier_base(
                    render, output_key=key,
                )
            meta = getattr(render, "metadata", None) or {}
            if (meta.get("baseline_fit_error")
                    or meta.get("receiving_base_plate_unconfigured") is True
                    or (key not in verified and meta.get("nfb_v5_trial_status")
                        and meta.get("nfb_trial_export_approved") is not True)):
                raise ValueError("COMPOSED_DXF_SOURCE_NOT_MANUFACTURING_APPROVED")
            # A caller-changed logical output name must never retag a
            # canonical physical sheet. Box Body may legitimately carry its
            # root identity while the Engine exposes a split physical piece.
            stable = str(meta.get("stable_id") or "")
            if stable and stable != key and not (
                    stable == "box_body" and key.startswith("box_body:")):
                raise ValueError("COMPOSED_DXF_PHYSICAL_ID_SOURCE_MISMATCH")
            topology = getattr(render, "unfolded_topology", None)
            if (key.startswith("box_body:")
                    and getattr(topology, "source", "") == "BOX_BODY_PHYSICAL_PIECE"
                    and str(getattr(topology, "piece_id", "")) != key.partition(":")[2]):
                raise ValueError("COMPOSED_DXF_BOX_BODY_TOPOLOGY_ID_MISMATCH")
            if not isinstance(render, PartRenderData) or render.scene is None:
                raise ValueError("COMPOSED_DXF_PHYSICAL_FLAT_SCENE_REQUIRED")
        # The incoming flattened physical rows may be in arbitrary order.
        # When the canonical BoxBody owner supplies piece topology, it must
        # determine LEFT/BACK/RIGHT (or LEFT/MIDDLE/RIGHT) in the packer.
        # Formed W gives ORDER, not a flat UV x-position: every source blank
        # retains its genuine CUTTING/BEND geometry and an independent gap.
        owners = [
            part.render_data
            for part in tuple(getattr(geometry, "parts", ()) or ())
            if (part.part_key == "box_body"
                and isinstance(part.render_data, BoxBodyStructureRenderData))
        ]
        detached_owner = (
            box_body_owner_by_panel.get(panel_name)
            if box_body_owner_by_panel is not None else None
        )
        if detached_owner is not None:
            if not isinstance(detached_owner, BoxBodyStructureRenderData):
                raise TypeError("COMPOSED_DXF_BOX_BODY_OWNER_TYPE_INVALID")
            if owners and owners[0] is not detached_owner:
                raise ValueError("COMPOSED_DXF_BOX_BODY_OWNER_AMBIGUOUS")
            if not owners:
                owners.append(detached_owner)
        if len(owners) > 1:
            raise ValueError("COMPOSED_DXF_BOX_BODY_OWNER_AMBIGUOUS")
        body_owner = {}
        for owner_data in owners:
            for piece in owner_data.pieces:
                owner = "box_body:" + str(piece.key)
                if owner in body_owner:
                    raise ValueError("COMPOSED_DXF_DUPLICATE_BODY_TOPOLOGY_OWNER")
                # Keep the genuine vertical assembly relationship, including
                # inset/back panels. This only moves the complete flat rigidly.
                body_owner[owner] = (
                    _finite(piece.formed_w_start),
                    _finite(piece.formed_y_offset),
                    str(piece.role),
                )
        # A canonical Receiving lower C support has a box_body:divider:
        # identity, but it is an INDEPENDENT physical blank. It must not be
        # mistaken for one of the BoxBody's left/back/right shell pieces.
        body = [(key, data) for key, data in rows
                if key == "box_body" or (
                    key.startswith("box_body:")
                    and not key.startswith("box_body:divider:")
                )]
        others = [(key, data) for key, data in rows if (key, data) not in body]
        if body_owner:
            if set(body_owner) != {key for key, _ in body}:
                raise ValueError("COMPOSED_DXF_BODY_TOPOLOGY_SOURCE_MISMATCH")
            role_order = {
                "left": 0, "left_side": 0, "integral": 0,
                "middle": 1, "back": 1, "right": 2, "right_side": 2,
            }
            body.sort(key=lambda row: (
                body_owner[row[0]][0],
                role_order.get(body_owner[row[0]][2], 99),
                row[0],
            ))
            minimum_y = min(record[1] for record in body_owner.values())
            arranged_body = tuple((
                key, data, body_owner[key][1] - minimum_y,
            ) for key, data in body)
        else:
            arranged_body = tuple((key, data, 0.0) for key, data in body)
        groups.append((panel_name, arranged_body
                       + tuple((key, data, 0.0) for key, data in others)))
    if not groups:
        raise ValueError("COMPOSED_DXF_EMPTY_PANELS")
    return tuple(groups) if preserve_input_order else tuple(sorted(
        groups, key=lambda row: (row[0].casefold(), row[0])
    ))


def _compose(rows, *, gap, quantity_summary=False):
    scene = DrawingScene()
    sheet_receipts = []
    originals = []
    translated_materials = []
    translated_guides = []
    y_cursor = 0.0
    for panel_name, pieces in rows:
        x_cursor = 0.0
        row_height = 0.0
        for physical_id, render, assembly_y in pieces:
            bounds = _scene_bounds(render.scene)
            x0, y0, x1, y1 = bounds
            # BoxBody y placement is canonical formed-piece data, not a
            # second unfolded polygon or a guess from the 3D world bbox.
            dy = y_cursor + assembly_y - y0
            dx = x_cursor - x0
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
            row_height = max(row_height, assembly_y + height)
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
    if quantity_summary:
        # Count the actual already-approved flat sheets, not logical Bay labels.
        # The complete manufacturing primitive fingerprint prevents a different
        # hole, bend, marking, blank outline, or part role from being merged.
        quantities = {}
        for panel_name, pieces in rows:
            for physical_id, render, _assembly_y in pieces:
                primitives = Counter(
                    _source_signature(primitive)
                    for primitive in render.scene.primitives
                    if str(primitive.layer).upper() != "CHECK"
                )
                identity = (
                    physical_id,
                    tuple(sorted(primitives.items(), key=lambda item: repr(item[0]))),
                )
                if identity not in quantities:
                    quantities[identity] = [physical_id, 0, []]
                quantities[identity][1] += 1
                quantities[identity][2].append(panel_name)
        if sum(item[1] for item in quantities.values()) != len(sheet_receipts):
            raise ValueError("COMPOSED_DXF_QUANTITY_INVENTORY_MISMATCH")
        variants = Counter(item[0] for item in quantities.values())
        current_variant = Counter()
        summary_lines = [
            f"總計：{len(sheet_receipts)}片；同板件同孔位 {len(quantities)} 種"
        ]
        for physical_id, count, panel_names in quantities.values():
            current_variant[physical_id] += 1
            variant = (
                f"（式樣{current_variant[physical_id]}）"
                if variants[physical_id] > 1 else ""
            )
            summary_lines.append(
                f"{physical_id}{variant} × {count}：{', '.join(panel_names)}"
            )
        # CHECK-only labels live ABOVE the last manufacturing row; never
        # alter CUTTING/BEND or the independently reopened source flats.
        line_step = max(12.0, float(gap) / 5.0)
        top = y_cursor + float(gap) + line_step * (len(summary_lines) - 1)
        for index, line in enumerate(summary_lines):
            scene.add(TextPrimitive(
                line, Vec2(0.0, top - index * line_step),
                "CHECK", 7.0, 1, 2, "composed_quantity_summary",
            ))
    combined = PartRenderData(
        scene=scene, material=unary_union(translated_materials),
        fold_guides=tuple(translated_guides),
    )
    return combined, tuple(sheet_receipts), tuple(originals)


def save_composed_panel_dxf(
    panels, output_path, *, pre_commit_guard, overwrite=False, gap=60.0,
    preserve_input_order=False, box_body_owner_by_panel=None,
    _verified_nfb_pair_parts=None, quantity_summary=False,
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
    if type(preserve_input_order) is not bool:
        raise TypeError("COMPOSED_DXF_ORDER_POLICY_MUST_BE_BOOL")
    rows = _source_rows(
        panels, preserve_input_order=preserve_input_order,
        box_body_owner_by_panel=box_body_owner_by_panel,
        _verified_nfb_pair_parts=_verified_nfb_pair_parts,
    )
    pre_commit_guard()
    if type(quantity_summary) is not bool:
        raise TypeError("COMPOSED_DXF_QUANTITY_SUMMARY_FLAG_MUST_BE_BOOL")
    composite, sheets, originals = _compose(
        rows, gap=float(gap), quantity_summary=quantity_summary,
    )
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
        # Existing single-part material verification intentionally treats
        # second closed CUTTING outlines as holes. Do NOT feed an entire
        # multi-blank modelspace into that single-blank acceptance function.
        # Every original flat passed its own material/BEND/holes verification
        # above; now independently reopen the COMPOSED bytes and prove all of
        # each physical sheet's translated features appear exactly once.
        actual = Counter(_actual_signature(entity)
                         for entity in ezdxf.readfile(staged).modelspace())
        remaining = actual.copy()
        for receipt, (_, physical_id, render) in zip(sheets, originals):
            dx, dy = receipt.offset
            source = Counter(_source_signature(_translated(p, dx, dy))
                             for p in render.scene.primitives)
            for signature, quantity in source.items():
                if remaining[signature] < quantity:
                    raise ValueError(
                        "COMPOSED_DXF_SHEET_READBACK_MISMATCH:" + physical_id
                    )
                remaining[signature] -= quantity
        # The only remaining entities must be the exact non-cutting provenance
        # CHECK texts. No dropped, duplicated or foreign entity is accepted.
        expected = Counter(_source_signature(p) for p in composite.scene.primitives)
        if actual != expected:
            raise ValueError("COMPOSED_DXF_EXACT_PRIMITIVE_READBACK_MISMATCH")
        pre_commit_guard()  # Source drift after staging must not replace output.
        _atomic_commit_staged_dxfs({"composed": staged}, root, overwrite=overwrite)
        return ComposedPanelDxfResult(str(path), sheets)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
