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
    draw_single_door_preview,
    draw_base_plate_preview,
    draw_door_layout_error,
    draw_door_layout_overview_preview,
    draw_door_layout_dividers_and_frames_preview,
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
    "draw_single_door_preview",
    "draw_base_plate_preview",
    "draw_door_layout_error",
    "draw_door_layout_overview_preview",
    "draw_door_layout_dividers_and_frames_preview",
    "door_layout_cell_at_canvas_point",
    "on_door_canvas_press",
    "on_door_canvas_drag",
    "on_door_canvas_release",
    "on_door_canvas_double_click",
    "box_body_face_at_canvas_point",
    "select_box_body_face",
    "on_box_body_canvas_press",
    "draw_preview",
    "open_box_body_face_editor",
    "draw_box_body_piece_preview",
    "draw_box_body_aggregate_preview",
    "draw_end_cap_preview",
    "draw_end_cap_error",
    "box_body_baseline_faces",
]

from .interaction import (
    door_layout_cell_at_canvas_point,
    on_door_canvas_press,
    on_door_canvas_drag,
    on_door_canvas_release,
    on_door_canvas_double_click,
    box_body_face_at_canvas_point,
    select_box_body_face,
    on_box_body_canvas_press,
    draw_preview,
    open_box_body_face_editor,
)

from .box_body_view import (
    draw_box_body_piece_preview,
    draw_box_body_aggregate_preview,
    draw_end_cap_preview,
    draw_end_cap_error,
    box_body_baseline_faces,
)
