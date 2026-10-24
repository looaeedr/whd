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


def with_physical_sheet_features(key, render, features):
    if not features:
        return render
    surface, width, height, _ = physical_sheet_feature_context(key, render)
    normalized = tuple(legacy_hole_to_feature(dict(f)) if isinstance(f, Mapping) else f
                       for f in features)
    resolved = ae.resolve_surface_features(surface, normalized, width, height)
    scene = DrawingScene()
    scene.extend(render.scene.primitives)
    scene.extend(resolved_features_to_primitives(resolved))
    return replace(render, scene=scene, material=material_polygon_from_final_scene(scene))
