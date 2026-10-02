"""Stateless 2D Canvas presentation helpers.

This module consumes already-resolved drawing/feature data. It does not own
manufacturing geometry, physical-part identity, visibility, persistence, or
application state.
"""

from ae_engine.sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile
from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive


def _draw_layout_resolved_features(canvas, resolved, blank_w, blank_h, bounds, tag):
    """Render a Door cell's edited features into the compact cabinet-layout rectangle."""
    if blank_w <= 0 or blank_h <= 0:
        return
    x1, y1, x2, y2 = bounds
    sx = (x2 - x1) / float(blank_w)
    sy = (y2 - y1) / float(blank_h)
    scale = max(0.01, min(abs(sx), abs(sy)))

    def pt(p):
        return (x1 + p.x * sx, y2 - p.y * sy)
    for feature in resolved:
        layer = getattr(feature, 'layer', 'CUTTING')
        color = {'MARKING': '#8e8e93', 'BLIND_HOLE': '#ff453a', 'DATUM': '#bf5af2'}.get(layer, '#ff9f0a')
        tags = ('door_layout_feature', tag)
        if isinstance(feature, ResolvedCircle):
            cx, cy = pt(feature.center)
            r = max(2.0, feature.radius * scale)
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=2, tags=tags)
            if feature.add_centerline:
                canvas.create_line(cx - r, cy, cx + r, cy, fill='#bf5af2', width=1, tags=tags)
        elif isinstance(feature, ResolvedRect):
            coords = []
            for p in feature.points:
                coords.extend(pt(p))
            canvas.create_polygon(*coords, outline=color, fill='', width=2, tags=tags)
        elif isinstance(feature, ResolvedProfile):
            coords = []
            for p in feature.points:
                coords.extend(pt(p))
            if len(coords) >= 6:
                canvas.create_polygon(*coords, outline=color, fill='', width=2, tags=tags)
            for sub_layer, points, closed in getattr(feature, 'layered_profiles', ()):
                sub_color = {'MARKING': '#8e8e93', 'BLIND_HOLE': '#ff453a', 'DATUM': '#bf5af2'}.get(sub_layer, color)
                sub = []
                for p in points:
                    sub.extend(pt(p))
                if len(sub) >= 4:
                    if closed and len(sub) >= 6:
                        canvas.create_polygon(*sub, outline=sub_color, fill='', width=1, tags=tags)
                    else:
                        canvas.create_line(*sub, fill=sub_color, width=1, tags=tags)

def _draw_layout_baseline_secondary(canvas, scene, blank_w, blank_h, bounds, tag):
    if scene is None or blank_w <= 0 or blank_h <= 0:
        return
    x1, y1, x2, y2 = bounds
    sx = (x2 - x1) / float(blank_w)
    sy = (y2 - y1) / float(blank_h)
    scale = max(0.01, min(abs(sx), abs(sy)))
    skipped_outline = False

    def pt(p):
        return (x1 + p.x * sx, y2 - p.y * sy)
    for primitive in scene.primitives:
        if primitive.layer in {'BEND', 'CHECK', 'STOCK'}:
            continue
        if isinstance(primitive, PolylinePrimitive) and primitive.layer == 'CUTTING' and primitive.closed and (not skipped_outline):
            skipped_outline = True
            continue
        color = {'MARKING': '#8e8e93', 'BLIND_HOLE': '#ff453a', 'DATUM': '#bf5af2'}.get(primitive.layer, '#64d2ff')
        tags = ('door_layout_baseline', tag)
        if isinstance(primitive, CirclePrimitive):
            cx, cy = pt(primitive.center)
            r = max(1.5, primitive.radius * scale)
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=1.5, tags=tags)
        elif isinstance(primitive, LinePrimitive):
            a = pt(primitive.p1)
            b = pt(primitive.p2)
            canvas.create_line(*a, *b, fill=color, width=1.2, tags=tags)
        elif isinstance(primitive, PolylinePrimitive):
            coords = []
            for p in primitive.points:
                coords.extend(pt(p))
            if len(coords) >= 4:
                if primitive.closed and len(coords) >= 6:
                    canvas.create_polygon(*coords, outline=color, fill='', width=1.2, tags=tags)
                else:
                    canvas.create_line(*coords, fill=color, width=1.2, tags=tags)

def draw_grid(self, canvas, w, h, tags=None):
    """
        在畫布背景上繪製科技感的微弱網格
        """
    grid_size = 40
    kwargs = {'fill': '#1c1c22', 'width': 1}
    if tags:
        kwargs['tags'] = tags
    for x in range(0, w, grid_size):
        canvas.create_line(x, 0, x, h, **kwargs)
    for y in range(0, h, grid_size):
        canvas.create_line(0, y, w, y, **kwargs)
