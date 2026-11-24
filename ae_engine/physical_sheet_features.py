"""User holes on derived sheets use their canonical material coordinates."""
from collections.abc import Mapping
from dataclasses import replace

from . import ae
from .manufacturing_render_data import material_polygon_from_final_scene
from .sheetmetal_drawing import DrawingScene, resolved_features_to_primitives
from .sheetmetal_features import RectGuide, Vec2, legacy_hole_to_feature


def physical_sheet_feature_context(key, render):
    surface = ae.feature_surface_from_drawing_scene(key, render.scene)
    minx, miny, maxx, maxy = surface.polygon.bounds
    # The origin belongs to the source sheet, including translated profiles.
    guide = RectGuide(Vec2(minx, miny), Vec2(maxx, maxy), 'material_boundary')
    return surface, maxx, maxy, guide


def resolved_physical_feature_ink(surface, width, height, features):
    from .operator_manual_marking import is_manual_round_mark, _round_mark_primitive
    resolved = ae.resolve_surface_features(
        surface, tuple(f for f in features if not is_manual_round_mark(f)), width, height,
    )
    return (*resolved_features_to_primitives(resolved),
            *(_round_mark_primitive(f) for f in features if is_manual_round_mark(f)))


def with_physical_sheet_features(key, render, features):
    if not features:
        return render
    surface, width, height, _ = physical_sheet_feature_context(key, render)
    normalized = tuple(legacy_hole_to_feature(dict(f)) if isinstance(f, Mapping) else f
                       for f in features)
    from .operator_manual_marking import is_manual_mark, validate_physical_manual_markings
    validate_physical_manual_markings(
        key, render, normalized, surface=surface, width=width, height=height,
    )
    scene = DrawingScene()
    scene.extend(render.scene.primitives)
    scene.extend(resolved_physical_feature_ink(surface, width, height, normalized))
    marked = tuple(feature for feature in normalized if is_manual_mark(feature))
    material = material_polygon_from_final_scene(scene)
    if not marked:
        # Existing readonly/legacy render types need no metadata field.
        # No manual intent => preserve their original replace contract.
        return replace(render, scene=scene, material=material)
    metadata = dict(getattr(render, "metadata", None) or {})
    metadata["manual_marking_v1_features"] = marked
    return replace(render, scene=scene, material=material, metadata=metadata)
