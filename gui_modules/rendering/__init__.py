"""One-way 2D rendering/presentation surface.

Rendering consumes authoritative resolved/projection data only.  It does not own
manufacturing geometry, project truth, physical-part identity, DXF truth, or 3D
placement.
"""

from .canvas_2d import (
    render_structural_result,
    render_secondary_scene,
    render_resolved_features,
    render_surface_user_features,
    feature_surface_from_drawing_scene,
)
from .overlays import (
    _rects_overlap,
    layout_reference_overlay_rects,
    draw_phase6_annotation_projection,
    draw_phase6_corner_dimension_overlay,
)
from .transforms import (
    YMirroredPreviewTransform,
    phase6_2d_material_viewport,
)
from .door_view import (
    draw_preview_error,
    draw_indicator_box_preview,
    draw_indicator_door_preview,
)

__all__ = [
    "_rects_overlap",
    "layout_reference_overlay_rects",
    "render_structural_result",
    "render_secondary_scene",
    "render_resolved_features",
    "render_surface_user_features",
    "feature_surface_from_drawing_scene",
    "draw_phase6_annotation_projection",
    "draw_phase6_corner_dimension_overlay",
    "YMirroredPreviewTransform",
    "phase6_2d_material_viewport",
    "draw_preview_error",
    "draw_indicator_box_preview",
    "draw_indicator_door_preview",
]
