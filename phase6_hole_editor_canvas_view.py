# -*- coding: utf-8 -*-
"""Phase6 統一開孔編輯器的 Canvas/Tk 顯示模組。

這個模組只擁有 Canvas 顯示狀態：transform、resolved feature cache、
浮動參考框的位置與 hit-test。它不擁有開孔草稿，也不建立製造幾何。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence
import tkinter as tk

from ae_engine.sheetmetal_features import (
    CanvasTransform,
    ResolvedCircle,
    ResolvedRect,
    Vec2,
    feature_reference_anchor,
    feature_reference_point,
    hit_test_resolved_features,
    resolve_surface_features,
)


def _rects_overlap(a, b, *, gap=0.0):
    al, at, ar, ab = a
    bl, bt, br, bb = b
    return not (
        ar + gap <= bl or br + gap <= al or ab + gap <= bt or bb + gap <= at
    )


def _layout_axis_reference_overlay_rects(
    canvas_w,
    canvas_h,
    *,
    crosshair,
    feature_rect,
    sizes,
    x_side,
    y_side,
    margin=8,
    gap=12,
):
    cw, ch = float(canvas_w), float(canvas_h)
    cx, cy = map(float, crosshair)
    fl, ft, fr, fb = map(float, feature_rect)
    occupied = [(fl-gap, ft-gap, fr+gap, fb+gap)]
    result = {}
    safe = float(gap) + 8.0

    def rect_for(center, size):
        x, y = center
        w, h = size
        return (x-w/2.0, y-h/2.0, x+w/2.0, y+h/2.0)

    def fits(rect):
        l, t, r, b = rect
        if l < margin or t < margin or r > cw-margin or b > ch-margin:
            return False
        return all(not _rects_overlap(rect, other, gap=4) for other in occupied)

    def choose(name, candidates):
        size = sizes[name]
        for center in candidates:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect
                occupied.append(rect)
                return
        w, h = size
        fallbacks = [
            (min(max(cx, margin+w/2), cw-margin-w/2), margin+h/2),
            (min(max(cx, margin+w/2), cw-margin-w/2), ch-margin-h/2),
            (margin+w/2, min(max(cy, margin+h/2), ch-margin-h/2)),
            (cw-margin-w/2, min(max(cy, margin+h/2), ch-margin-h/2)),
            (margin+w/2, margin+h/2),
            (cw-margin-w/2, margin+h/2),
            (margin+w/2, ch-margin-h/2),
            (cw-margin-w/2, ch-margin-h/2),
        ]
        for center in fallbacks:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect
                occupied.append(rect)
                return
        x = min(max(cx, margin+w/2), cw-margin-w/2)
        y = min(max(cy, margin+h/2), ch-margin-h/2)
        rect = rect_for((x, y), size)
        result[name] = rect
        occupied.append(rect)

    xw, _xh = sizes["x_group"]
    _yw, yh = sizes["y_group"]
    pw, _ph = sizes["panel"]

    left_x = fl - safe - xw/2.0
    right_x = fr + safe + xw/2.0
    x_primary = left_x if x_side == "left" else right_x
    x_alt = right_x if x_side == "left" else left_x
    choose("x_group", [(x_primary, cy), (x_alt, cy)])

    top_y = ft - safe - yh/2.0
    bottom_y = fb + safe + yh/2.0
    y_primary = top_y if y_side == "top" else bottom_y
    y_alt = bottom_y if y_side == "top" else top_y
    choose("y_group", [(cx, y_primary), (cx, y_alt)])

    left_panel_x = fl - safe - pw/2.0
    right_panel_x = fr + safe + pw/2.0
    panel_primary = right_panel_x if x_side == "left" else left_panel_x
    panel_alt = left_panel_x if x_side == "left" else right_panel_x
    choose("panel", [(panel_primary, cy), (panel_alt, cy), (cx, y_alt)])
    return result


@dataclass(frozen=True)
class HoleEditorCanvasFrame:
    surface: object
    features: Sequence[object]
    width: float
    height: float
    reference_guide: object
    selected_index: int
    reference_distances: object | None = None
    measure_guide: object | None = None
    baseline_scene: object | None = None
    extra_bounds: tuple[float, float, float, float] | None = None
    insert_label: str | None = None
    error_text: str | None = None
    draw_extra: Callable[[object, CanvasTransform, int, int], None] | None = None


class Phase6HoleEditorCanvasView:
    """統一開孔編輯器 Canvas 的唯一顯示狀態 owner。"""

    def __init__(
        self,
        canvas,
        *,
        draw_grid: Callable[[object, int, int], None],
        render_secondary_scene: Callable[[object, object, CanvasTransform], None],
        render_resolved_features: Callable[..., None],
        overlay_widgets: Mapping[str, object] | None = None,
        pad: int = 105,
    ):
        self.canvas = canvas
        self._draw_grid = draw_grid
        self._render_secondary_scene = render_secondary_scene
        self._render_resolved_features = render_resolved_features
        self._overlay_widgets = dict(overlay_widgets or {})
        self._pad = int(pad)
        self.transform: CanvasTransform | None = None
        self._resolved = []

    @property
    def resolved_features(self):
        return tuple(self._resolved)

    def hide_overlays(self) -> None:
        for widget in self._overlay_widgets.values():
            widget.place_forget()

    def canvas_to_world(self, x: float, y: float):
        if self.transform is None:
            return None
        return self.transform.canvas_to_world(x, y)

    def hit_test(self, x: float, y: float):
        if self.transform is None:
            return None
        point = self.transform.canvas_to_world(x, y)
        tolerance = 8.0 / self.transform.scale if self.transform.scale else 2.0
        return hit_test_resolved_features(point, self._resolved, tolerance=tolerance)

    def _resolved_canvas_rect(self, resolved_feature):
        tr = self.transform
        if tr is None:
            return None
        if isinstance(resolved_feature, ResolvedCircle):
            points = (
                Vec2(resolved_feature.center.x-resolved_feature.radius, resolved_feature.center.y-resolved_feature.radius),
                Vec2(resolved_feature.center.x+resolved_feature.radius, resolved_feature.center.y+resolved_feature.radius),
            )
        elif isinstance(resolved_feature, ResolvedRect):
            points = resolved_feature.points
        else:
            points = resolved_feature.points
        canvas_points = [tr.world_to_canvas(point) for point in points]
        xs = [point[0] for point in canvas_points]
        ys = [point[1] for point in canvas_points]
        return (min(xs), min(ys), max(xs), max(ys))

    def _place_reference_overlays(self, frame, reference_point, feature_rect):
        distances = frame.reference_distances
        if distances is None or not self._overlay_widgets:
            self.hide_overlays()
            return
        required = {"x_group", "y_group", "panel"}
        if not required.issubset(self._overlay_widgets):
            self.hide_overlays()
            return
        canvas = self.canvas
        canvas.update_idletasks()
        x_group = self._overlay_widgets["x_group"]
        y_group = self._overlay_widgets["y_group"]
        panel = self._overlay_widgets["panel"]
        sizes = {
            "x_group": (max(178, x_group.winfo_reqwidth()), max(82, x_group.winfo_reqheight())),
            "y_group": (max(178, y_group.winfo_reqwidth()), max(82, y_group.winfo_reqheight())),
            "panel": (max(138, panel.winfo_reqwidth()), max(90, panel.winfo_reqheight())),
        }
        cx, cy = self.transform.world_to_canvas(reference_point)
        rects = _layout_axis_reference_overlay_rects(
            max(2, canvas.winfo_width()),
            max(2, canvas.winfo_height()),
            crosshair=(cx, cy),
            feature_rect=feature_rect,
            sizes=sizes,
            x_side=distances.x_side,
            y_side=distances.y_side,
        )
        for name, widget in self._overlay_widgets.items():
            if name not in rects:
                continue
            left, top, _right, _bottom = rects[name]
            widget.place(x=int(left), y=int(top), anchor=tk.NW)

    def _build_transform(self, frame, cw, ch):
        minx, miny, maxx, maxy = frame.surface.polygon.bounds
        guide = frame.reference_guide
        gminx = float(guide.min_point.x)
        gminy = float(guide.min_point.y)
        gmaxx = float(guide.max_point.x)
        gmaxy = float(guide.max_point.y)
        extra = frame.extra_bounds
        view_minx = min(minx, gminx, extra[0] if extra else gminx)
        view_miny = min(miny, gminy, extra[1] if extra else gminy)
        view_maxx = max(maxx, gmaxx, extra[2] if extra else gmaxx)
        view_maxy = max(maxy, gmaxy, extra[3] if extra else gmaxy)
        view_w = max(view_maxx-view_minx, 1e-9)
        view_h = max(view_maxy-view_miny, 1e-9)
        pad = self._pad
        scale = min((cw - 2*pad)/view_w, (ch - 2*pad)/view_h) if view_w > 0 and view_h > 0 else 1.0
        scale = max(scale, 0.01)
        left_px = pad + (cw - 2*pad - view_w*scale)/2
        bottom_px = ch - (pad + (ch - 2*pad - view_h*scale)/2)
        return CanvasTransform(scale, left_px - view_minx*scale, bottom_px + view_miny*scale)

    def render(self, frame: HoleEditorCanvasFrame) -> None:
        canvas = self.canvas
        canvas.delete("all")
        canvas.update_idletasks()
        cw = max(2, canvas.winfo_width())
        ch = max(2, canvas.winfo_height())
        self._draw_grid(canvas, cw, ch)

        tr = self._build_transform(frame, cw, ch)
        self.transform = tr

        coords = []
        for point in frame.surface.outline:
            coords.extend(tr.world_to_canvas(point))
        canvas.create_polygon(*coords, outline="#30d158", fill="", width=2)

        if frame.baseline_scene is not None:
            self._render_secondary_scene(canvas, frame.baseline_scene, tr)

        guide = frame.reference_guide
        gx0, gy0 = tr.world_to_canvas(guide.min_point)
        gx1, gy1 = tr.world_to_canvas(guide.max_point)
        canvas.create_rectangle(gx0, gy0, gx1, gy1, outline="#f2f2f7", width=2, dash=(10, 5))

        sw = guide.width
        sh = guide.height
        x_left, y_top = tr.world_to_canvas(Vec2(guide.min_point.x, guide.max_point.y))
        x_right, _ = tr.world_to_canvas(Vec2(guide.max_point.x, guide.max_point.y))
        _, y_bottom = tr.world_to_canvas(Vec2(guide.min_point.x, guide.min_point.y))
        dim_y = max(22, y_top - 32)
        dim_x = max(22, x_left - 38)
        canvas.create_line(x_left, y_top, x_left, dim_y, fill="#8e8e93", dash=(4, 3))
        canvas.create_line(x_right, y_top, x_right, dim_y, fill="#8e8e93", dash=(4, 3))
        canvas.create_line(x_left, dim_y, x_right, dim_y, fill="#8e8e93", width=2, arrow=tk.BOTH)
        canvas.create_text((x_left+x_right)/2, dim_y-15, text=f"W = {sw:.2f} mm", fill="#f2f2f7", font=("Consolas", 14, "bold"))
        canvas.create_line(x_left, y_top, dim_x, y_top, fill="#8e8e93", dash=(4, 3))
        canvas.create_line(x_left, y_bottom, dim_x, y_bottom, fill="#8e8e93", dash=(4, 3))
        canvas.create_line(dim_x, y_top, dim_x, y_bottom, fill="#8e8e93", width=2, arrow=tk.BOTH)
        canvas.create_text(dim_x-18, (y_top+y_bottom)/2, text=f"H = {sh:.2f} mm", fill="#f2f2f7", font=("Consolas", 14, "bold"), angle=90)

        try:
            self._resolved = list(resolve_surface_features(frame.surface, frame.features, frame.width, frame.height))
        except ValueError:
            self._resolved = []
        self._render_resolved_features(canvas, self._resolved, tr, color="#ff9f0a")

        if frame.draw_extra is not None:
            frame.draw_extra(canvas, tr, cw, ch)

        if frame.error_text:
            canvas.create_text(
                cw/2,
                ch-20,
                anchor=tk.S,
                text=frame.error_text,
                fill="#ff453a",
                font=("Microsoft JhengHei", 11, "bold"),
                width=max(260, cw-80),
                tags=("indicator_fit_error",),
            )

        selected = frame.selected_index
        if 0 <= selected < len(frame.features):
            feature = frame.features[selected]
            anchor = feature_reference_anchor(feature)
            reference_point = feature_reference_point(feature, anchor, frame.width, frame.height)
            measure_guide = frame.measure_guide or guide
            x0, y0 = tr.world_to_canvas(Vec2(measure_guide.min_point.x, reference_point.y))
            x1, y1 = tr.world_to_canvas(Vec2(measure_guide.max_point.x, reference_point.y))
            canvas.create_line(x0, y0, x1, y1, fill="#ffd60a", width=2, dash=(8, 4))
            x0, y0 = tr.world_to_canvas(Vec2(reference_point.x, measure_guide.min_point.y))
            x1, y1 = tr.world_to_canvas(Vec2(reference_point.x, measure_guide.max_point.y))
            canvas.create_line(x0, y0, x1, y1, fill="#ffd60a", width=2, dash=(8, 4))
            cx, cy = tr.world_to_canvas(reference_point)
            canvas.create_oval(cx-6, cy-6, cx+6, cy+6, outline="#ffd60a", width=2)
            if selected < len(self._resolved):
                selected_rect = self._resolved_canvas_rect(self._resolved[selected])
            else:
                selected_rect = (cx-10, cy-10, cx+10, cy+10)
            self._place_reference_overlays(frame, reference_point, selected_rect)
        else:
            self.hide_overlays()

        if frame.insert_label:
            canvas.create_text(
                16,
                16,
                anchor=tk.NW,
                text=f"插入模式：{frame.insert_label}",
                fill="#30d158",
                font=("Microsoft JhengHei", 12, "bold"),
            )
