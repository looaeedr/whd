"""Non-publishing geometry proof for one selected canonical physical sheet.

The key identifies a row in this canonical resolved assembly only. It is
neither a persistent occupant ID nor permission to store or export marks.
"""
from dataclasses import dataclass, field

from .contracts import ResolvedManufacturingGeometry
from .manufacturing_export import resolved_physical_render_parts
from .manufacturing_render_data import (
    fold_guides_from_final_scene, material_polygon_from_final_scene,
)
from .operator_manual_marking import (
    MANUAL_MARK_SOURCE, _build_manual_straight_feature, _validate_manual_strokes,
)
from .sheetmetal_drawing import LinePrimitive


@dataclass(frozen=True)
class SelectedMarkingPreviewSource:
    selected_key: str
    material_class: str
    fold_guides: tuple
    _render: object = field(repr=False, compare=False)
    _seal: tuple = field(repr=False)


def _selected_geometry(render):
    meta = render.metadata or {}
    if (meta.get("formed_geometry_verified") is False
            or meta.get("receiving_base_plate_unconfigured") is True
            or meta.get("baseline_fit_error")):
        raise ValueError("MARKING_PREVIEW_INCOMPLETE_SOURCE")
    scene = render.scene
    material = render.material
    if (material is None or material.is_empty or not material.is_valid
            or not material_polygon_from_final_scene(scene).equals(material)):
        raise ValueError("MARKING_PREVIEW_CANONICAL_MATERIAL_MISMATCH")
    bends = tuple(row for row in scene.primitives
                  if str(row.layer).upper() == "BEND")
    guides = fold_guides_from_final_scene(scene)
    if (not all(isinstance(row, LinePrimitive) for row in bends)
            or len(guides) != len(bends)
            or guides != tuple(render.fold_guides)):
        raise ValueError("MARKING_PREVIEW_BEND_SOURCE_MISMATCH")
    seal = (render.unfolded_topology, tuple(scene.primitives), material.wkb, guides)
    return ("folded" if guides else "flat"), guides, seal


def open_selected_physical_marking_preview(geometry, part_key):
    """Select exact stock from the existing physical inventory, not a role alias."""
    if not isinstance(geometry, ResolvedManufacturingGeometry):
        raise ValueError("MARKING_PREVIEW_RESOLVED_SOURCE_REQUIRED")
    if not isinstance(part_key, str) or not part_key:
        raise ValueError("MARKING_PREVIEW_SELECTION_REQUIRED")
    candidates = tuple(render for key, render in resolved_physical_render_parts(
        geometry, include_unreleased_source_flats=True,
    ) if key == part_key)
    if len(candidates) != 1:
        raise ValueError("MARKING_PREVIEW_SELECTION_UNRESOLVED")
    render, = candidates
    kind, guides, seal = _selected_geometry(render)
    return SelectedMarkingPreviewSource(part_key, kind, guides, render, seal)


def _validate_selected_marks(source, features, *, allow_shapes=False):
    """Recheck selected stock before calling the one physical stroke validator."""
    from .operator_manual_marking import _source_pattern, is_manual_mark
    from .sheetmetal_feature_core import CircleFeature, ProfileFeature
    if not isinstance(source, SelectedMarkingPreviewSource):
        raise ValueError("MARKING_PREVIEW_RESOLVED_SOURCE_REQUIRED")
    render = source._render
    if _selected_geometry(render)[2] != source._seal:
        raise ValueError("MARKING_PREVIEW_SOURCE_STALE")
    rows = tuple(features)
    if allow_shapes:
        if any(not isinstance(row, (CircleFeature, ProfileFeature))
               or not is_manual_mark(row) for row in rows):
            raise ValueError("ROOT_MARKING_STORE_MARKS_ONLY")
    elif any(not isinstance(f, ProfileFeature) or f.source_type != MANUAL_MARK_SOURCE
             or _source_pattern(f)[0] != "solid" for f in rows):
        raise ValueError("MARKING_PREVIEW_SOLID_STRAIGHT_ONLY")
    # The canonical render already contains actual CUTTING and BLIND_HOLE.
    return _validate_manual_strokes(render, rows, rows, part_key=source.selected_key,
                                    surface=None)


def validate_selected_physical_marks(source, features):
    return _validate_selected_marks(source, features)


def create_selected_physical_mark(source, features, *, midpoint, length, angle_deg):
    """Return one candidate without writing anything, valid for CHECK sources."""
    mark = _build_manual_straight_feature(midpoint, length, angle_deg, "solid", 10.0, 5.0)
    validate_selected_physical_marks(source, tuple(features) + (mark,))
    return mark


def project_selected_physical_marking_preview(source, *, midpoint, length, angle_deg):
    """Return only actual solid ink, never publishable PartRenderData."""
    mark = create_selected_physical_mark(source, (), midpoint=midpoint,
                                         length=length, angle_deg=angle_deg)
    return project_selected_physical_marking_features(source, (mark,))


def project_selected_physical_marking_features(source, features, *, _allow_shapes=False):
    """Project verified authored intent through the existing physical Feature path."""
    from .physical_sheet_features import physical_sheet_feature_context, resolved_physical_feature_ink

    marks = _validate_selected_marks(source, features, allow_shapes=_allow_shapes)
    surface, width, height, _ = physical_sheet_feature_context(source.selected_key, source._render)
    return resolved_physical_feature_ink(surface, width, height, marks)
