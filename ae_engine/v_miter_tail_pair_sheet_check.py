# -*- coding: utf-8 -*-
"""#3317: one Custom Tail two-bottom-V source-qualified FLAT 2D CHECK only.

Not a new V solver. Replay both old physical-corner Engine outcomes against
the SAME untouched canonical material, apply independently signed deltas, and
require one valid, hole-free connected contour and all original finite BENDs.
The Factory mother is a *theoretical uncut* source comparison; positive signed
delta is NOT permission to add stock to an already cut physical sheet.

No generated CUTTING/BEND/MARKING, manufacturing DXF, or 3D is authorized.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import dist, isfinite

from shapely.geometry import LineString, Polygon, box

from .contracts import EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import (
    DrawingScene, LinePrimitive, PolylinePrimitive, CirclePrimitive, TextPrimitive,
)
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_factory_mother_check import (
    _factory_original_shape, _selected_original_corner_component,
)
from .v_miter_material_trial import _single_source_material
from .v_miter_operator_gui_check import (
    V_MITER_GUI_UNCERTIFIED,
    VMiterOperatorGUICheck, project_operator_v_miter_live_corner_check,
)

_CORNERS = ("bottom_left", "bottom_right")
_AREA_TOL = 1e-6
_LENGTH_TOL = 1e-7


@dataclass(frozen=True)
class VMiterTailPairOneSheet2DCheck:
    """A single unmanufacturable two-V CHECK perimeter; original BEND datum."""

    scene: DrawingScene
    source_area_mm2: float
    combined_area_mm2: float
    # Signed retained-area delta relative to the old trimmed Factory, not
    # stock that can be physically added back to an already cut panel.
    corner_signed_area_deltas_mm2: tuple[tuple[str, float], ...]
    original_finite_bends: tuple[LinePrimitive, ...]
    # Original Engine mapper evidence ONLY, never a solved 3D corner/root.
    finite_tip_edge_lengths_mm: tuple[tuple[str, float, float], ...] = ()
    formed_3d_rejection: str = "V_MITER_TAIL_PAIR_3D_FINITE_TIP_OWNER_UNVERIFIED"

    def require_formed_3d_check(self):
        """Do not render/manufacture a stretched or still-unproven 3D sheet."""
        raise GeometryError(self.formed_3d_rejection)
    geometry_model: str = "FACTORY_VERIFIED_CUSTOM_TAIL_TWO_BOTTOM_V_SINGLE_SHEET_2D_CHECK"
    manufacturing_status: str = "V_MITER_TAIL_PAIR_ONE_SHEET_2D_UNCERTIFIED"


def _polygon_from_proven_outline(points, code: str) -> Polygon:
    if not points or any(
        not (isfinite(float(p.x)) and isfinite(float(p.y))) for p in points
    ):
        raise GeometryError(code)
    shape = Polygon([(p.x, p.y) for p in points])
    if (shape.geom_type != "Polygon" or shape.is_empty
            or not shape.is_valid or shape.interiors or shape.area <= _AREA_TOL):
        raise GeometryError(code)
    return shape



def _finite_tip_3d_guard_from_real_stock(spec, render, stock):
    """Reject non-isometric original finite-tip mapping, not infer new folds.

    #3379 pre-corner Factory extension is CHECK-only. #3381/#3390 each
    solve separate single-corner flange skins, not this connected two-V
    sheet. None owns the shared X/Y root or licenses folding retained stock.
    """
    from .assembly_geometry_folded_mesh import _profile_map_with_guides
    from .manufacturing_render_data import fold_guides_from_final_scene
    missing = "V_MITER_TAIL_PAIR_3D_FINITE_TIP_SOURCE_UNPROVEN"
    guides = fold_guides_from_final_scene(render.scene)
    sides = sorted((g for g in guides if g.axis == "x"),
                   key=lambda g: g.position)
    horizontals = sorted((g for g in guides if g.axis == "y"),
                         key=lambda g: g.position)
    if len(sides) != 2 or not horizontals:
        return (), missing
    left, right = sides
    bottom = horizontals[0]
    minx, miny, maxx, _ = map(float, stock.bounds)
    edges = (
        ("side_left", (minx, bottom.position), (minx, left.span_start)),
        ("side_right", (maxx, bottom.position), (maxx, right.span_start)),
        ("bottom_left", (left.position, miny), (bottom.span_start, miny)),
        ("bottom_right", (bottom.span_end, miny), (right.position, miny)),
    )

    def existing_3d(point):
        x, y = point
        ux, zx = _profile_map_with_guides(
            x, y, spec.fold_profile_x, axis="x", fold_guides=guides,
        )
        uy, zy = _profile_map_with_guides(
            y, x, spec.fold_profile_y, axis="y", fold_guides=guides,
        )
        return float(ux), float(uy), float(zx + zy)

    measured = []
    for name, start, end in edges:
        edge = LineString((start, end))
        # Every millimeter must exist on the REAL newly connected CUTTING
        # boundary. No sample-only point or invented crease extension.
        if (edge.length <= _LENGTH_TOL
                or edge.difference(stock.boundary.buffer(1e-6)).length > 1e-6):
            return (), missing
        try:
            after = dist(existing_3d(start), existing_3d(end))
        except (GeometryError, ValueError, TypeError, ArithmeticError):
            return (), "V_MITER_TAIL_PAIR_3D_FINITE_TIP_MAP_UNVERIFIED"
        if not isfinite(after):
            return (), "V_MITER_TAIL_PAIR_3D_FINITE_TIP_MAP_UNVERIFIED"
        measured.append((name, float(edge.length), float(after)))
    # Even when four edges look right, a continuous two-axis physical root
    # would still need its own no-tear/no-overlap 3D source proof.
    return tuple(measured), (
        "V_MITER_TAIL_PAIR_3D_FINITE_TIP_STRETCH_REJECTED"
        if any(abs(before - after) > 1e-5 for _, before, after in measured)
        else "V_MITER_TAIL_PAIR_3D_CONTINUOUS_ROOT_UNVERIFIED"
    )


def project_v_miter_custom_tail_bottom_pair_one_sheet_2d_check(
    part_spec: EndCapPartSpec,
    render_data: PartRenderData,
    replays: Mapping[str, VMiterOperatorGUICheck],
) -> VMiterTailPairOneSheet2DCheck:
    """Prove BOTH independent Factory R-corrected deltas on one source sheet.

    Deliberately cannot use RELIEF_HOLE here: it can cut the already
    existing finite BEND and the presently unmodified physical BEND is
    mandatory for this narrowly approved check. Do not silently shorten it.
    """
    if (not isinstance(part_spec, EndCapPartSpec) or not part_spec.is_tail
            or part_spec.model_name is not None
            or not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)
            or not isinstance(replays, Mapping)
            or set(replays) != set(_CORNERS)):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_AUTHENTIC_SOURCE_REQUIRED")

    actual = render_data.material
    # Prior to requiring one CUTTING polyline, diagnose actual original
    # CUTTING circles/inner voids as an explicit UNSUPPORTED feature.
    if (part_spec.holes or not isinstance(actual, Polygon)
            or actual.is_empty or not actual.is_valid or actual.interiors
            or any(isinstance(row, CirclePrimitive)
                   for row in render_data.scene.primitives)):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_EXISTING_HOLE_OR_MATERIAL_UNSUPPORTED")
    original = _single_source_material(render_data.scene)
    if actual.symmetric_difference(original).area > _AREA_TOL:
        raise GeometryError("V_MITER_TAIL_PAIR_2D_EXISTING_HOLE_OR_MATERIAL_UNSUPPORTED")

    # The typed Factory builder, not a chosen pixel-size box, is the
    # authority for the actual uncut blank and the two old corner cuts.
    factory, factory_width, factory_height, _axes = _factory_original_shape(part_spec)
    if factory.symmetric_difference(original).area > _AREA_TOL:
        raise GeometryError("V_MITER_TAIL_PAIR_2D_FACTORY_SOURCE_CHANGED")
    mother = box(0.0, 0.0, factory_width, factory_height)

    bends = tuple(
        row for row in render_data.scene.primitives
        if isinstance(row, LinePrimitive) and row.layer == "BEND"
    )
    if (len(bends) < 3 or any(
            row.layer == "BEND" and not isinstance(row, LinePrimitive)
            for row in render_data.scene.primitives)):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_FINITE_BENDS_REQUIRED")
    # Reject duplicate original physical creases, including a duplicated Y.
    def unoriented(row):
        return tuple(sorted(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y))))
    if len({unoriented(row) for row in bends}) != len(bends):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_DUPLICATED_ORIGINAL_BEND")

    checked = {}
    for corner in _CORNERS:
        prior = replays[corner]
        if (not isinstance(prior, VMiterOperatorGUICheck)
                or prior.part_key != "tail" or prior.corner_key != corner
                or prior.first_bend_axis != "x"
                or prior.second_bend_axis != "y"
                or prior.manufacturing_status != V_MITER_GUI_UNCERTIFIED
                or prior.factory_bottom_relief_check is None
                or prior.factory_mother_check is None
                or prior.factory_mother_check.source_check is not prior.material_check
                or prior.factory_bottom_relief_check.relief_mode.value != "ROUND_R"):
            raise GeometryError("V_MITER_TAIL_PAIR_2D_ROUND_R_SOURCE_REQUIRED")
        # A synthetic caller cannot pass two locally forged/stale checks.
        # Re-evaluate each on this exact PartSpec + PartRenderData with the
        # old Engine. No new V/contact/relief solver is introduced.
        expected = project_operator_v_miter_live_corner_check(
            part_spec, render_data, corner,
            first_bend_axis="x", relief_mode="ROUND_R",
        )
        if (prior.first_physical_bend is not expected.first_physical_bend
                or prior.second_physical_bend is not expected.second_physical_bend
                or prior.factory_bottom_relief_check
                != expected.factory_bottom_relief_check
                or prior.factory_mother_check != expected.factory_mother_check):
            raise GeometryError("V_MITER_TAIL_PAIR_2D_REPLAY_SOURCE_CHANGED")
        checked[corner] = prior

    left, right = (checked[key] for key in _CORNERS)
    if (left.first_physical_bend is right.first_physical_bend
            or left.second_physical_bend is not right.second_physical_bend
            or len({
                id(left.first_physical_bend), id(right.first_physical_bend),
                id(left.second_physical_bend),
            }) != 3
            or any(
                not any(old is bend for old in bends)
                for bend in (
                    left.first_physical_bend, right.first_physical_bend,
                    left.second_physical_bend,
                )
            )):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_SHARED_ORIGINAL_BEND_REQUIRED")

    delta_regions = {}
    signed_deltas = []
    adds, removes = [], []
    for corner in _CORNERS:
        candidate = checked[corner].factory_bottom_relief_check
        cut = _selected_original_corner_component(factory, mother, corner)
        remaining = _polygon_from_proven_outline(
            candidate.corrected_remaining_outline,
            "V_MITER_TAIL_PAIR_2D_INVALID_CORRECTED_OUTLINE",
        )
        removed = _polygon_from_proven_outline(
            candidate.corrected_removed_outline,
            "V_MITER_TAIL_PAIR_2D_INVALID_CORRECTED_REMOVAL",
        )
        restored = original.union(cut)
        # Reconstruct full original+selected-corner mother independently,
        # ensure corrected and removed partition it with no missing stock.
        if (restored.geom_type != "Polygon" or restored.interiors
                or remaining.intersection(removed).area > _AREA_TOL
                or remaining.union(removed).symmetric_difference(restored).area > _AREA_TOL
                or abs(candidate.source_original_area_mm2 - restored.area) > _AREA_TOL
                or abs(candidate.corrected_remaining_area_mm2 - remaining.area) > _AREA_TOL
                or abs(candidate.corrected_removed_area_mm2 - removed.area) > _AREA_TOL):
            raise GeometryError("V_MITER_TAIL_PAIR_2D_FACTORY_CORNER_PARTITION_CHANGED")

        added = remaining.difference(original)
        lost = original.difference(remaining)
        # All theoretical material *gain* must be INSIDE the truly removed
        # old Factory corner, not arbitrary W-dependent imagined stock.
        # Any loss must come only from the verified Factory V relief.
        if (added.is_empty and lost.is_empty
                or added.difference(cut.buffer(_LENGTH_TOL)).area > _AREA_TOL
                or lost.difference(removed.buffer(_LENGTH_TOL)).area > _AREA_TOL):
            raise GeometryError("V_MITER_TAIL_PAIR_2D_DELTA_OUTSIDE_FACTORY_CORNER")
        delta = added.union(lost)
        if delta.is_empty or delta.area <= _AREA_TOL:
            raise GeometryError("V_MITER_TAIL_PAIR_2D_CORNER_DELTA_EMPTY")
        delta_regions[corner] = delta
        adds.append(added)
        removes.append(lost)
        signed = added.area - lost.area
        if abs(signed - (remaining.area - original.area)) > _AREA_TOL:
            raise GeometryError("V_MITER_TAIL_PAIR_2D_SIGNED_DELTA_AREA_MISMATCH")
        signed_deltas.append((corner, signed))

    if (not delta_regions[_CORNERS[0]].disjoint(delta_regions[_CORNERS[1]])
            or delta_regions[_CORNERS[0]].distance(
                delta_regions[_CORNERS[1]]
            ) <= _LENGTH_TOL):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_CORNER_DELTAS_OVERLAP")
    # Apply signed changes to one original physical source, never union
    # two full-sheet independently corrected outlines.
    final = original.difference(removes[0].union(removes[1])).union(
        adds[0].union(adds[1])
    )
    expected_area = original.area + sum(value for _, value in signed_deltas)
    if (final.geom_type != "Polygon" or final.is_empty or not final.is_valid
            or final.interiors or final.area <= _AREA_TOL
            or abs(final.area - expected_area) > _AREA_TOL
            or final.difference(mother.buffer(_LENGTH_TOL)).area > _AREA_TOL):
        raise GeometryError("V_MITER_TAIL_PAIR_2D_NOT_ONE_VALID_SHEET")

    # Every *original finite* BEND, not just the three chosen ones, must
    # survive with precisely its real endpoints. Never extend/clip BEND,
    # unlike the unrelated illustrated Vault D4 V90 sample.
    for bend in bends:
        line = LineString(((bend.p1.x, bend.p1.y), (bend.p2.x, bend.p2.y)))
        if (line.length <= _LENGTH_TOL
                or line.difference(final.buffer(_LENGTH_TOL)).length
                > _LENGTH_TOL):
            raise GeometryError("V_MITER_TAIL_PAIR_2D_ORIGINAL_BEND_SHORTENED")

    # One CHECK contour. Original CUTTING/BEND are simply copied as
    # non-manufacturing DATUM for visibility; source stays untouched.
    scene = DrawingScene([
        PolylinePrimitive(
            tuple(Vec2(float(x), float(y)) for x, y in final.exterior.coords),
            "CHECK", closed=True,
            semantic_id="v_miter_custom_tail_same_sheet_two_bottom_v_check",
        ),
    ])
    for row in render_data.scene.primitives:
        if row.layer == "CUTTING":
            if not isinstance(row, PolylinePrimitive):
                raise GeometryError("V_MITER_TAIL_PAIR_2D_UNSUPPORTED_SOURCE_PRIMITIVE")
            scene.add(PolylinePrimitive(
                row.points, "DATUM", closed=row.closed, color=6,
                semantic_id="original_factory_cutting_datum",
            ))
        elif row.layer == "BEND":
            if not isinstance(row, LinePrimitive):
                raise GeometryError("V_MITER_TAIL_PAIR_2D_UNSUPPORTED_SOURCE_BEND")
            scene.add(LinePrimitive(row.p1, row.p2, "DATUM", color=6))
        else:
            # Preserve the geometry of actual existing non-CUTTING/BEND
            # source strokes/annotations as read-only DATUM; no original
            # MARKING is re-issued or new manufacturing geometry inferred.
            if not isinstance(row, (LinePrimitive, PolylinePrimitive, TextPrimitive)):
                raise GeometryError("V_MITER_TAIL_PAIR_2D_EXTRA_SOURCE_GEOMETRY_UNSUPPORTED")
            scene.add(replace(row, layer="DATUM", color=6))

    edge_lengths, rejection = _finite_tip_3d_guard_from_real_stock(
        part_spec, render_data, final,
    )
    return VMiterTailPairOneSheet2DCheck(
        scene=scene,
        source_area_mm2=original.area,
        combined_area_mm2=final.area,
        corner_signed_area_deltas_mm2=tuple(signed_deltas),
        original_finite_bends=bends,
        finite_tip_edge_lengths_mm=edge_lengths,
        formed_3d_rejection=rejection,
    )
