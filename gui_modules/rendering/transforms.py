"""Read-only 2D preview transforms and material viewport fitting."""

from ae_engine.sheetmetal_features import CanvasTransform
from ae_engine.sheetmetal_drawing import mirror_point_y


class YMirroredPreviewTransform:
    """Reflect world Y before normal Canvas mapping; presentation only."""

    def __init__(self, base_transform, height):
        self._base = base_transform
        self.height = float(height)
        self.scale = base_transform.scale

    def world_to_canvas(self, point):
        return self._base.world_to_canvas(mirror_point_y(point, self.height))


def phase6_2d_material_viewport(
    bounds, canvas_width, canvas_height, *,
    top_gutter=175.0, right_gutter=82.0,
    bottom_gutter=48.0, left_gutter=48.0,
    transform_type=CanvasTransform,
):
    """Fit authoritative material bounds inside the presentation viewport."""
    minx, miny, maxx, maxy = (float(v) for v in bounds)
    world_w = max(1.0, maxx - minx)
    world_h = max(1.0, maxy - miny)
    cw = max(1.0, float(canvas_width))
    ch = max(1.0, float(canvas_height))
    left = max(8.0, float(left_gutter))
    top = min(max(8.0, float(top_gutter)), max(8.0, ch - 24.0))
    right = max(8.0, float(right_gutter))
    bottom_margin = max(8.0, float(bottom_gutter))
    available_w = max(1.0, cw - left - right)
    available_h = max(1.0, ch - top - bottom_margin)
    scale = min(available_w / world_w, available_h / world_h)
    material_left = left + (available_w - world_w * scale) / 2.0
    material_top = top + (available_h - world_h * scale) / 2.0
    material_bottom = material_top + world_h * scale
    transform = transform_type(
        scale=scale,
        origin_x=material_left - minx * scale,
        origin_y=material_bottom + miny * scale,
    )
    return transform, material_left, material_bottom, scale, material_top
