"""Read-only 2D preview transforms and material viewport fitting."""

import math

from ae_engine.sheetmetal_features import CanvasTransform
from ae_engine.sheetmetal_drawing import mirror_point_y


def _finite_float(value, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} cannot be bool")
    num = float(value)
    if not math.isfinite(num):
        raise ValueError(f"{name} must be finite")
    return num


class YMirroredPreviewTransform:
    """Reflect world Y before normal Canvas mapping; presentation only."""

    def __init__(self, base_transform, height):
        self._base = base_transform
        self.height = _finite_float(height, "height")
        self.scale = base_transform.scale

    def world_to_canvas(self, point):
        return self._base.world_to_canvas(mirror_point_y(point, self.height))

    def canvas_to_world(self, cx, cy):
        return mirror_point_y(self._base.canvas_to_world(cx, cy), self.height)


def phase6_2d_material_viewport(
    bounds, canvas_width, canvas_height, *,
    top_gutter=175.0, right_gutter=82.0,
    bottom_gutter=48.0, left_gutter=48.0,
    transform_type=CanvasTransform,
):
    """Fit authoritative material bounds inside the presentation viewport."""
    raw_bounds = tuple(bounds)
    if len(raw_bounds) != 4:
        raise ValueError("bounds must contain 4 numbers")
    minx, miny, maxx, maxy = (_finite_float(v, "bounds") for v in raw_bounds)
    if minx > maxx:
        minx, maxx = maxx, minx
    if miny > maxy:
        miny, maxy = maxy, miny
    world_w = max(1.0, maxx - minx)
    world_h = max(1.0, maxy - miny)
    cw = max(1.0, _finite_float(canvas_width, "canvas_width"))
    ch = max(1.0, _finite_float(canvas_height, "canvas_height"))
    left = max(8.0, _finite_float(left_gutter, "left_gutter"))
    top = min(max(8.0, _finite_float(top_gutter, "top_gutter")), max(8.0, ch - 24.0))
    right = max(8.0, _finite_float(right_gutter, "right_gutter"))
    bottom_margin = max(8.0, _finite_float(bottom_gutter, "bottom_gutter"))
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
