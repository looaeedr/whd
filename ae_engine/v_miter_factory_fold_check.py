# -*- coding: utf-8 -*-
"""#3317 fold candidates from the independent PRE-CORNER Factory topology.

The old four-type CUTTING clipped physical BEND in the FinalScene. A V
replacement cannot simply draw a straight line through the missing section:
it must rebuild the SAME typed Factory *uncut* Fold, establish identity with
the existing physical BEND, and clip against the *new* one-piece V material.

This is a detached CHECK of a proposed replacement fold. It never certifies
MARKING, bend relief, R/BA, interference or physical machining eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Polygon, box

from .contracts import DoorPartSpec, EndCapPartSpec
from .manufacturing_render_data import PartRenderData
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_factory_mother_check import (
    VMiterFactoryMotherReplacementCheck, _factory_original_shape,
    _selected_original_corner_component,
)
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck, _single_source_material,
)
from .v_miter_bend_marking import project_v_miter_bend_markings

_GEOMETRY_TOL = 1e-7


@dataclass(frozen=True)
class VMiterFactoryPrecutFoldCheck:
    """Fold stock before/after ONE substituted corner, always CHECK-only."""

    first_original_bend_mm: float
    second_original_bend_mm: float
    first_surviving_factory_fold_mm: float
    second_surviving_factory_fold_mm: float
    first_additional_factory_fold_mm: float
    second_additional_factory_fold_mm: float
    first_proposed_segments: tuple[LinePrimitive, ...]
    second_proposed_segments: tuple[LinePrimitive, ...]
    first_proposed_alignment_marks: tuple[LinePrimitive, ...]
    second_proposed_alignment_marks: tuple[LinePrimitive, ...]
    geometry_model: str = "FACTORY_PRE_CORNER_FOLD_CLIPPED_TO_V_SOURCE_CHECK"
    manufacturing_status: str = "V_MITER_FACTORY_PRECORNER_FOLD_UNCERTIFIED"


def _source_line(row: LinePrimitive) -> LineString:
    if not isinstance(row, LinePrimitive) or row.layer != "BEND":
        raise GeometryError("V_MITER_FACTORY_FOLD_REAL_BEND_REQUIRED")
    coords = tuple((float(point.x), float(point.y))
                   for point in (row.p1, row.p2))
    if not all(math.isfinite(z) for point in coords for z in point):
        raise GeometryError("V_MITER_FACTORY_FOLD_NONFINITE_BEND")
    line = LineString(coords)
    if not math.isfinite(line.length) or line.length <= _GEOMETRY_TOL:
        raise GeometryError("V_MITER_FACTORY_FOLD_DEGENERATE_BEND")
    return line


def _segments(geometry):
    """Retain *all* connected physical portions, never only the longest."""
    if geometry.geom_type == "LineString":
        rows = (geometry,)
    else:
        rows = tuple(
            x for x in getattr(geometry, "geoms", ())
            if x.geom_type == "LineString"
        )
    if len(rows) > 32:
        raise GeometryError("V_MITER_FACTORY_FOLD_SEGMENTS_EXCEED_LIMIT")
    return tuple(x for x in rows if x.length > _GEOMETRY_TOL)


def project_v_miter_factory_precut_fold_check(
    part_spec: DoorPartSpec | EndCapPartSpec,
    render_data: PartRenderData,
    corner_key: str,
    source_check: VMiterSourceBoundSharpCheck,
    first_real_bend: LinePrimitive,
    second_real_bend: LinePrimitive,
    factory_mother: VMiterFactoryMotherReplacementCheck | None = None,
) -> VMiterFactoryPrecutFoldCheck:
    """Prove existing source BEND belongs to independently rebuilt Factory.

    The full pre-corner axis is *not* treated as a surviving bend until the
    V remaining CUTTING is checked and the axis clipped to its interior.
    An extension beyond an old four-type BEND can then be displayed with
    explicit Factory-Fold provenance, but is NOT a manufactured BEND.
    """
    if (not isinstance(part_spec, (DoorPartSpec, EndCapPartSpec))
            or not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or first_real_bend is second_real_bend):
        raise GeometryError("V_MITER_FACTORY_FOLD_TYPED_SOURCE_REQUIRED")
    for old in (first_real_bend, second_real_bend):
        if not any(p is old for p in render_data.scene.primitives):
            raise GeometryError("V_MITER_FACTORY_FOLD_BEND_IDENTITY_NOT_IN_FINAL_SCENE")

    original = _single_source_material(render_data.scene)
    old_factory, width, height, all_precut_axes = _factory_original_shape(part_spec)
    if old_factory.symmetric_difference(original).area > 1e-6:
        raise GeometryError("V_MITER_FACTORY_FOLD_SOURCE_DIFFERS_FROM_FACTORY")

    remaining = Polygon(((p.x, p.y) for p in source_check.remaining_outline))
    removed = Polygon(((p.x, p.y) for p in source_check.removed_corner_outline))
    if any(
        g.geom_type != "Polygon" or g.is_empty or not g.is_valid or g.interiors
        for g in (remaining, removed)
    ):
        raise GeometryError("V_MITER_FACTORY_FOLD_V_SOURCE_NOT_ONE_SHEET")
    restored = remaining.union(removed)
    if (restored.geom_type != "Polygon" or not restored.is_valid or
            restored.interiors or remaining.intersection(removed).area > 1e-6
            or abs(remaining.area - source_check.remaining_material_area_mm2) > 1e-6
            or abs(removed.area - source_check.removed_material_area_mm2) > 1e-6
            or abs(restored.area - source_check.source_material_area_mm2) > 1e-6
            or restored.difference(box(0.0, 0.0, width, height)).area > 1e-6):
        raise GeometryError("V_MITER_FACTORY_FOLD_V_SOURCE_AREA_MISMATCH")

    if factory_mother is None:
        if restored.symmetric_difference(original).area > 1e-6:
            raise GeometryError("V_MITER_FACTORY_FOLD_UNVERIFIED_RESTORED_SOURCE")
    else:
        if (not isinstance(factory_mother, VMiterFactoryMotherReplacementCheck)
                or factory_mother.source_check is not source_check
                or abs(factory_mother.actual_original_material_area_mm2 - original.area) > 1e-6
                or abs(factory_mother.restored_source_material_area_mm2 - restored.area) > 1e-6):
            raise GeometryError("V_MITER_FACTORY_FOLD_MOTHER_IDENTITY_MISMATCH")
        old_cut = _selected_original_corner_component(
            original, box(0.0, 0.0, width, height), corner_key,
        )
        added = restored.difference(original)
        if (original.difference(restored).area > 1e-6
                or added.symmetric_difference(old_cut).area > 1e-6
                or abs(added.area - factory_mother.restored_corner_material_area_mm2) > 1e-6):
            raise GeometryError("V_MITER_FACTORY_FOLD_SELECTED_CORNER_NOT_RESTORED")

    def find_proven_precut_axis(actual: LinePrimitive):
        physical = _source_line(actual)
        # A real FinalScene BEND must lie on one, and only one, original
        # uncut Factory axis at the SAME location and original station.
        matches = []
        for bend in all_precut_axes:
            factory_line = LineString((
                (bend.p1.x, bend.p1.y), (bend.p2.x, bend.p2.y)
            ))
            if (physical.difference(factory_line.buffer(_GEOMETRY_TOL)).length
                    <= _GEOMETRY_TOL
                    and factory_line.length >= physical.length - _GEOMETRY_TOL):
                matches.append(factory_line)
        if len(matches) != 1:
            raise GeometryError("V_MITER_FACTORY_FOLD_ORIGINAL_BEND_NOT_UNIQUE_IN_TOPOLOGY")
        full = matches[0]
        # A source BEND outside the original factory metal is not evidence.
        if physical.difference(original.buffer(_GEOMETRY_TOL)).length > _GEOMETRY_TOL:
            raise GeometryError("V_MITER_FACTORY_FOLD_OLD_BEND_NOT_ON_STOCK")

        true_after_v = full.intersection(remaining).difference(
            remaining.boundary.buffer(_GEOMETRY_TOL)
        )
        sections = _segments(true_after_v)
        if not sections:
            raise GeometryError("V_MITER_FACTORY_FOLD_NO_V_SURVIVING_SEGMENTS")
        if any(
            section.difference(full.buffer(_GEOMETRY_TOL)).length > _GEOMETRY_TOL
            or section.difference(remaining.buffer(_GEOMETRY_TOL)).length > _GEOMETRY_TOL
            for section in sections
        ):
            raise GeometryError("V_MITER_FACTORY_FOLD_CONTINUATION_OFF_SOURCE")
        seen = sum(part.length for part in sections)
        if seen > full.length + _GEOMETRY_TOL:
            raise GeometryError("V_MITER_FACTORY_FOLD_SURVIVAL_EXCEEDS_SOURCE_AXIS")
        extra = sum(part.difference(physical).length for part in sections)
        proposed = tuple(
            LinePrimitive(Vec2(*a.coords[0]), Vec2(*a.coords[-1]), "CHECK", color=5)
            for a in sections
        )
        return physical.length, seen, extra, proposed

    first = find_proven_precut_axis(first_real_bend)
    second = find_proven_precut_axis(second_real_bend)

    def align_proposed_fold(segments: tuple[LinePrimitive, ...]):
        """Re-use the SAME Engine 20/50 marking rule on the *new* V Fold.

        A proposed Fold is an independently source-checked Factory axis,
        NOT an existing physical BEND. Expose only diagnostic CHECK strokes:
        never manufacture a CNC MARKING or silently copy the old short marks
        that would miss newly recovered metal.
        """
        marks = []
        for segment in segments:
            proposed_bend = LinePrimitive(segment.p1, segment.p2, "BEND")
            for stroke in project_v_miter_bend_markings(
                proposed_bend, stroke_mm=20.0, clear_gap_mm=50.0,
            ):
                line = LineString((
                    (stroke.p1.x, stroke.p1.y),
                    (stroke.p2.x, stroke.p2.y),
                ))
                if (line.difference(remaining.buffer(_GEOMETRY_TOL)).length
                        > _GEOMETRY_TOL):
                    raise GeometryError("V_MITER_FACTORY_FOLD_MARKS_OUTSIDE_V_SOURCE")
                marks.append(LinePrimitive(
                    stroke.p1, stroke.p2, "CHECK", color=3,
                ))
        return tuple(marks)

    first_marks = align_proposed_fold(first[3])
    second_marks = align_proposed_fold(second[3])
    return VMiterFactoryPrecutFoldCheck(
        first_original_bend_mm=first[0],
        second_original_bend_mm=second[0],
        first_surviving_factory_fold_mm=first[1],
        second_surviving_factory_fold_mm=second[1],
        first_additional_factory_fold_mm=first[2],
        second_additional_factory_fold_mm=second[2],
        first_proposed_segments=first[3],
        second_proposed_segments=second[3],
        first_proposed_alignment_marks=first_marks,
        second_proposed_alignment_marks=second_marks,
    )
