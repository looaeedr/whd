# -*- coding: utf-8 -*-
"""
箱體展開圖計算器 - GUI 介面
"""

import tkinter as tk
import time
import sys
from pathlib import Path
from copy import deepcopy
from phase6_sync_envelope import stable_fingerprint
from dataclasses import replace
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import ae_engine.ae as ae  # AE manufacturing engine package
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import (
    policy as cabinet_family_policy,
    registered_cabinet_types,
    resolve_cabinet_type,
)

PHASE6_BUILD_ID = "RECEIVING_MODEL_SINGLE_SOURCE_20260824_0701"
from ae_engine.contracts import (
    BasePlatePartSpec,
    BoxBodyPartSpec,
    DoorPartSpec,
    EndCapPartSpec,
    IndicatorBoxPartSpec,
    ManufacturingContext,
)
from ae_engine.sheetmetal_geometry import (
    Vec2,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    CornerDirection,
    EDITABLE_CORNER_TYPE_IDS,
    CORNER_TYPE_LABELS,
    normalize_corner_selection,
    box_body_vertical_offsets,
)
from ae_engine.sheetmetal_features import (
    box_body_face_dimensions,
    box_body_face_contexts_from_strip,
    resolve_box_body_face_features,
    CanvasTransform,
    CircleFeature,
    DoorIndicatorContext,
    RectFeature,
    ProfileFeature,
    legacy_hole_to_feature,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
    measure_door_indicator_position,
    door_indicator_offset_for_position,
    door_enclosure_reference_offsets,
    door_enclosure_reference_guide,
    resolve_features_in_finished_face,
    resolve_base_plate_mounting_holes,
    resolved_circles_from_baseline,
    resolve_vault_endcap_fixed_features,
    resolve_endcap_finished_face_guide,
    resolve_door_indicator_dimension_guides,
    FeatureAnchor,
    placement_from_finished_point,
    feature_finished_point,
    move_feature_to_finished_point,
    reanchor_feature,
    build_feature_placement_guides,
    feature_to_legacy_hole,
    feature_with_offset,
    expand_linear_pattern,
    expand_grid_pattern,
    ResolvedCircle,
    ResolvedRect,
    ResolvedProfile,
    resolve_endcap_features,
    endcap_feature_context_from_geometry,
    feature_surface_from_rect,
    feature_is_within_surface,
    move_feature_within_surface,
    feature_surface_from_structural_result,
    feature_surface_from_outline,
    resolve_surface_features,
    ReferenceAnchor,
    REFERENCE_ANCHOR_LABELS,
    REFERENCE_ANCHOR_BY_LABEL,
    feature_reference_anchor,
    feature_with_reference_anchor,
    feature_reference_point,
    reference_distances,
    move_feature_by_reference_distance,
    feature_with_process,
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
    align_circle_to_neighbor,
    generate_round_fill,
    generate_round_refill,
    RectGuide,
)


from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
    validate_door_layout_dimensions,
    complete_partition,
    door_layout_export_filename,
    door_layout_feature_map_to_part_features,
    door_part_features_to_layout_feature_map,
    build_box_body_result,
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_base_plate_result,
    build_indicator_box_result,
    build_endcap_result,
    build_unknown_door_result,
    build_unknown_base_plate_result,
    build_unknown_indicator_box_result,
    build_unknown_endcap_result,
    build_finished_reference_guide,
)


from ae_engine.corner_type_ui import (
    UNKNOWN_MODEL_NAME,
    CUSTOM_MODEL_NAME,
    CORNER_KEYS,
    CORNER_LABELS,
    CORNER_PAIR_CORNERS,
    apply_manual_corner_selection,
    with_unknown_model,
    is_unknown_model,
    normalize_custom_model_name,
    new_manual_corner_pair_same_state,
    new_manual_corner_state,
    known_model_corner_state,
    policy_from_corner_state,
    set_manual_corner_pair_same,
    build_corner_type_preview_geometry,
    apply_box_assembly_type, assembly_type_from_corner_state,
)


def _corner_preview_canvas_point(point, *, ox, oy, scale, span, flip_y=True):
    """Map semantic preview coordinates to the operator-facing canvas."""
    canvas_y = oy - (span - point.y) * scale if flip_y else oy - point.y * scale
    return (
        ox + point.x * scale,
        canvas_y,
    )


def _corner_preview_flip_y_for_target(target_key):
    """Top thumbnails stay flipped; bottom thumbnails use their original orientation."""
    return str(target_key or "").strip() not in {"bottom", "bottom_left", "bottom_right"}


def _endcap_profiles_for_assembly(values, stored_profiles, assembly_type, part_key):
    """Return render profiles consistent with the current box assembly type.

    OVERLAY has no left/right X bends, even when the operator has never opened
    the 3D workspace (and therefore has no stored Phase6 profile yet).  Existing
    Y topology is preserved.  Switching back from OVERLAY restores the normal X
    topology from the shared scalar parameters without changing CornerType or
    the deferred bottom-corner rule.
    """
    intent_id = assembly_intent_value(assembly_type)
    source = dict(values or {})
    source["assembly_type"] = intent_id
    defaults = build_endcap_xy_profiles(source, part_key=part_key)
    profiles = deepcopy(dict(stored_profiles or {}))

    if not profiles:
        return defaults if intent_id == CornerTypeId.OVERLAY.value else None

    current_x = list(profiles.get("X", ()) or ())
    is_flat_x = len(current_x) == 1 and current_x[0].get("phase6_key") == "endcap_w_flat"
    if intent_id == CornerTypeId.OVERLAY.value or is_flat_x:
        profiles["X"] = deepcopy(defaults["X"])
    if not profiles.get("Y"):
        profiles["Y"] = deepcopy(defaults["Y"])
    return profiles

from ae_engine.hole_catalog import (
    load_hole_catalog,
    load_pipe_catalog,
    feature_from_definition,
    custom_circle_definition,
    custom_rectangle_definition,
)


from fold_designer_bridge import Phase6FoldDesignerApp
from phase6_corner_dimension_display import render_data_corner_dimension_text
from phase6_fold_profiles import (
    profile_to_fold_segments, build_box_body_profile, build_endcap_xy_profiles, build_linked_endcap_xy_profiles,
    engine_segment_length_to_ui, formed_box_body_fw_widths,
)
from phase6_endcap_semantics import (
    resolve_box_assembly_type, ASSEMBLY_TYPE_LABELS, ASSEMBLY_LABEL_TO_TYPE,
    assembly_intent_value, assembly_intent_label, legacy_corner_projection_for_intent,
    normalize_endcap_fw_state, resolve_endcap_fw, set_endcap_fw_follow, set_endcap_fw_override,
    commit_box_fw, commit_endcap_fw,
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap,
)
from ae_engine.assembly_joint import (
    migrate_legacy_snapshot_joints, sync_snapshot_intent_joints, ASSEMBLY_JOINT_SCHEMA_VERSION,
)

from phase6_settings_center import (
    GLOBAL_CONTEXT,
    UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size,
    ui_text_size_label,
    ui_text_size_factor,
    SettingsService,
    load_factory_defaults_from_ae,
    load_corner_defaults_from_ini,
    save_corner_defaults_to_ini,
)
from ui_text_scale import TextScaleController
from phase6_project_file import (
    PROJECT_SCHEMA as PHASE6_PROJECT_SCHEMA,
    PROJECT_EXTENSION as PHASE6_PROJECT_EXTENSION,
    read_project as read_phase6_project,
    write_project as write_phase6_project,
    project_path_from_argv,
    register_windows_file_association,
)
from phase6_project_controller import Phase6ProjectController
from phase6_workspace_controller import Phase6WorkspaceController
from phase6_hole_editor_session import HoleEditorAction, Phase6HoleEditorSession
from phase6_hole_editor_canvas_view import HoleEditorCanvasFrame, Phase6HoleEditorCanvasView

from ae_engine.sheetmetal_drawing import (
    PolylinePrimitive,
    LinePrimitive,
    CirclePrimitive,
    DrawingScene,
    resolved_features_to_primitives,
    mirror_point_y,
)



def _rects_overlap(a, b, gap=0.0):
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0]
        or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def layout_reference_overlay_rects(canvas_w, canvas_h, *, crosshair, feature_rect, sizes, x_side, y_side, margin=8, gap=12):
    """Lay out CAD reference controls on the crosshair without covering the hole.

    X controls stay on the horizontal reference line; Y controls stay on the
    vertical reference line.  Preferred placement follows the selected finished
    boundary side, then falls back to the opposite side or a free perimeter slot.
    Returned values are pixel rectangles (left, top, right, bottom).
    """
    cw, ch = float(canvas_w), float(canvas_h)
    cx, cy = map(float, crosshair)
    fl, ft, fr, fb = map(float, feature_rect)
    occupied = [(fl-gap, ft-gap, fr+gap, fb+gap)]
    result = {}

    def rect_for(center, size):
        x, y = center; w, h = size
        return (x-w/2.0, y-h/2.0, x+w/2.0, y+h/2.0)

    def fits(rect):
        l,t,r,b = rect
        if l < margin or t < margin or r > cw-margin or b > ch-margin:
            return False
        return all(not _rects_overlap(rect, other, gap=4) for other in occupied)

    def choose(name, candidates):
        size = sizes[name]
        for center in candidates:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect; occupied.append(rect); return
        # Deterministic perimeter fallback: scan rows/columns outside the feature.
        w,h = size
        fallback = [
            (margin+w/2, margin+h/2), (cw-margin-w/2, margin+h/2),
            (margin+w/2, ch-margin-h/2), (cw-margin-w/2, ch-margin-h/2),
            (cw/2, margin+h/2), (cw/2, ch-margin-h/2),
            (margin+w/2, ch/2), (cw-margin-w/2, ch/2),
        ]
        for center in fallback:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect; occupied.append(rect); return
        # Very small screens: clamp to canvas; this remains deterministic.
        x = min(max(cx, margin+w/2), cw-margin-w/2)
        y = min(max(cy, margin+h/2), ch-margin-h/2)
        rect = rect_for((x,y), size)
        result[name] = rect; occupied.append(rect)

    # Horizontal controls: centers stay on the horizontal reference line.
    x_pref_left = x_side == 'left'
    left_near = fl - gap - sizes['x_edge'][0]/2
    right_near = fr + gap + sizes['x_edge'][0]/2
    left_far = left_near - gap - sizes['x_neighbor'][0]
    right_far = right_near + gap + sizes['x_neighbor'][0]
    if x_pref_left:
        choose('x_edge', [(left_near, cy), (right_near, cy)])
        choose('x_neighbor', [(left_far, cy), (right_far, cy), (right_near, cy)])
    else:
        choose('x_edge', [(right_near, cy), (left_near, cy)])
        choose('x_neighbor', [(right_far, cy), (left_far, cy), (left_near, cy)])

    # Vertical controls: centers stay on the vertical reference line.
    y_pref_top = y_side == 'top'
    top_near = ft - gap - sizes['y_edge'][1]/2
    bottom_near = fb + gap + sizes['y_edge'][1]/2
    top_far = top_near - gap - sizes['y_neighbor'][1]
    bottom_far = bottom_near + gap + sizes['y_neighbor'][1]
    if y_pref_top:
        choose('y_edge', [(cx, top_near), (cx, bottom_near)])
        choose('y_neighbor', [(cx, top_far), (cx, bottom_far), (cx, bottom_near)])
    else:
        choose('y_edge', [(cx, bottom_near), (cx, top_near)])
        choose('y_neighbor', [(cx, bottom_far), (cx, top_far), (cx, top_near)])

    # Reference panel sits diagonally outside the hole and all four fields.
    pw, ph = sizes['panel']
    panel_candidates = [
        (fr + gap + pw/2, fb + gap + ph/2),
        (fl - gap - pw/2, fb + gap + ph/2),
        (fr + gap + pw/2, ft - gap - ph/2),
        (fl - gap - pw/2, ft - gap - ph/2),
    ]
    choose('panel', panel_candidates)
    return result





class _YMirroredPreviewTransform:
    """Read-only preview transform that reflects world Y before normal Canvas mapping."""

    def __init__(self, base_transform, height):
        self._base = base_transform
        self.height = float(height)
        self.scale = base_transform.scale

    def world_to_canvas(self, point):
        return self._base.world_to_canvas(mirror_point_y(point, self.height))


def render_structural_result(canvas, result, transform, tags=None):
    polygon_coords = []
    for point in result.outline:
        cx, cy = transform.world_to_canvas(point)
        polygon_coords.extend([cx, cy])
    polygon_kwargs = {
        "outline": "#30d158",
        "fill": "",
        "width": 2,
    }
    if tags is not None:
        polygon_kwargs["tags"] = tags
    if len(polygon_coords) >= 6:
        canvas.create_polygon(*polygon_coords, **polygon_kwargs)

    for bend in result.bends:
        p1 = transform.world_to_canvas(bend.p1)
        p2 = transform.world_to_canvas(bend.p2)
        line_kwargs = {
            "fill": "#0a84ff",
            "width": 1.5,
            "dash": (6, 4),
        }
        if tags is not None:
            line_kwargs["tags"] = tags
        canvas.create_line(*p1, *p2, **line_kwargs)


def render_drawing_scene(canvas, scene, transform, *, skip_layers=()):
    skip = set(skip_layers)
    for primitive in scene.primitives:
        if primitive.layer in skip:
            continue
        if isinstance(primitive, PolylinePrimitive):
            coords = []
            for point in primitive.points:
                coords.extend(transform.world_to_canvas(point))
            if len(coords) < 4:
                continue
            color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(primitive.layer, "#30d158")
            if primitive.layer == "BEND":
                color = "#0a84ff"
            if primitive.closed and len(coords) >= 6:
                canvas.create_polygon(*coords, outline=color, fill="", width=2 if primitive.layer == "CUTTING" else 1.5)
            else:
                kwargs = {"fill": color, "width": 1.5}
                if primitive.layer == "BEND":
                    kwargs["dash"] = (6, 4)
                canvas.create_line(*coords, **kwargs)
        elif isinstance(primitive, LinePrimitive):
            p1 = transform.world_to_canvas(primitive.p1)
            p2 = transform.world_to_canvas(primitive.p2)
            color = "#0a84ff" if primitive.layer == "BEND" else {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(primitive.layer, "#30d158")
            kwargs = {"fill": color, "width": 1.5}
            if primitive.layer == "BEND":
                kwargs["dash"] = (6, 4)
            canvas.create_line(*p1, *p2, **kwargs)
        elif isinstance(primitive, CirclePrimitive):
            cx, cy = transform.world_to_canvas(primitive.center)
            r_px = primitive.radius * transform.scale
            color = {"CUTTING":"#30d158", "BLIND_HOLE":"#ff453a", "MARKING":"#8e8e93", "DATUM":"#bf5af2"}.get(primitive.layer, "#8e8e93")
            canvas.create_oval(cx-r_px, cy-r_px, cx+r_px, cy+r_px, outline=color, width=1.5)


def render_secondary_scene(canvas, scene, transform):
    """Render baseline secondary geometry without redrawing the structural outline/BEND lines."""
    secondary = DrawingScene()
    skipped_primary_outline = False
    for primitive in scene.primitives:
        if primitive.layer == "BEND":
            continue
        if (
            not skipped_primary_outline
            and isinstance(primitive, PolylinePrimitive)
            and primitive.layer == "CUTTING"
        ):
            skipped_primary_outline = True
            continue
        secondary.add(primitive)
    render_drawing_scene(canvas, secondary, transform)


def render_resolved_features(canvas, features, transform, *, color="#ff9f0a"):
    """Render already-resolved world-space features; never derives manufacturing coordinates."""
    for feature in features:
        layer = getattr(feature, "layer", "CUTTING")
        draw_color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(layer, color)
        if isinstance(feature, ResolvedCircle):
            cx, cy = transform.world_to_canvas(feature.center)
            r_px = feature.radius * transform.scale
            canvas.create_oval(cx-r_px, cy-r_px, cx+r_px, cy+r_px, outline=draw_color, width=2)
            if feature.add_centerline:
                canvas.create_line(cx-r_px, cy, cx+r_px, cy, fill="#bf5af2", width=1)
        elif isinstance(feature, ResolvedProfile) and getattr(feature, "layered_profiles", ()):
            for sub_layer, points, closed in feature.layered_profiles:
                sub_color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(sub_layer, color)
                coords = []
                for point in points:
                    coords.extend(transform.world_to_canvas(point))
                if len(coords) >= 4:
                    if closed and len(coords) >= 6:
                        canvas.create_polygon(*coords, outline=sub_color, fill="", width=2)
                    else:
                        canvas.create_line(*coords, fill=sub_color, width=2)
        elif isinstance(feature, (ResolvedRect, ResolvedProfile)):
            coords = []
            for point in feature.points:
                coords.extend(transform.world_to_canvas(point))
            if len(coords) >= 6:
                canvas.create_polygon(*coords, outline=draw_color, fill="", width=2)


def render_surface_user_features(canvas, surface, features, width, height, transform):
    if not features:
        return
    resolved = resolve_surface_features(surface, features, width, height)
    render_resolved_features(canvas, resolved, transform, color="#ff9f0a")


def feature_surface_from_drawing_scene(surface_id, scene):
    # Keep one authoritative CUTTING-outline resolver in AE so the GUI and
    # manufacturing export accept the same closed-polyline / exploded-LINE data.
    return ae.feature_surface_from_drawing_scene(surface_id, scene)


def _draw_phase6_corner_dimension_overlay(canvas, render_data, canvas_width):
    """Draw per-corner sizes measured from the same PartRenderData used by 3D."""
    text = render_data_corner_dimension_text(render_data)
    canvas.create_text(
        max(25, float(canvas_width) - 25), 42, anchor=tk.NE,
        text=text, fill="#ffd60a", justify=tk.RIGHT,
        font=('Microsoft JhengHei', 9, 'bold'),
        width=max(180, int(float(canvas_width) * 0.46)),
        tags=("phase6_corner_dimensions",),
    )
    return text


def draw_hole_editor_hint(canvas, canvas_width, *, endcap=False):
    text = "雙擊：開孔"
    canvas.create_text(
        canvas_width - 18, 18, text=text, anchor=tk.NE,
        fill="#ff9f0a", font=('Microsoft JhengHei',9,'bold'),
        tags=("phase6_hole_hint",),
    )


def _phase6_2d_material_viewport(bounds, canvas_width, canvas_height, *, top_gutter=175.0, right_gutter=82.0, bottom_gutter=48.0, left_gutter=48.0):
    """Fit material inside a dedicated viewport below operator annotations.

    The top annotation band and right dimension channel are layout contracts,
    not geometry. All six main 2D sheet-metal previews use this one helper so
    labels cannot steal space from or overlap the manufacturing material.
    """
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
    transform = CanvasTransform(
        scale=scale,
        origin_x=material_left - minx * scale,
        origin_y=material_bottom + miny * scale,
    )
    return transform, material_left, material_bottom, scale, material_top


class _Phase6UpdateScheduler:
    """Coalesce GUI work behind the single calculation-executor seam."""

    DEFAULT_DEBOUNCE_MS = 75
    MIN_DEBOUNCE_MS = 50
    MAX_DEBOUNCE_MS = 100
    _DISPLAY_ONLY_REASONS = frozenset({"display", "annotation", "camera"})
    _FULL_REASONS = frozenset({"geometry", "assembly", "baseline"})

    def __init__(self, owner):
        self.owner = owner
        self.depth = 0
        self.dirty = set()
        self._flushing = False
        self._after_job = None
        self._metrics = {
            "flushes": 0,
            "calculation_flushes": 0,
            "display_flushes": 0,
        }

    def begin(self):
        self.depth += 1

    def end(self):
        if self.depth <= 0:
            self.depth = 0
            return
        self.depth -= 1
        if self.depth == 0:
            self.request_flush()

    def mark_dirty(self, reason="geometry"):
        self.dirty.add(str(reason or "geometry"))
        if self.depth == 0:
            self.request_flush()

    @classmethod
    def _normalize_debounce_ms(cls, debounce_ms):
        if debounce_ms is None:
            return cls.DEFAULT_DEBOUNCE_MS
        value = int(debounce_ms)
        if value <= 0:
            return 0
        return max(cls.MIN_DEBOUNCE_MS, min(cls.MAX_DEBOUNCE_MS, value))

    @classmethod
    def _requires_calculation(cls, reasons):
        for reason in reasons:
            text = str(reason or "geometry")
            if text in cls._DISPLAY_ONLY_REASONS:
                continue
            if text in cls._FULL_REASONS:
                return True
            # setting:*, legacy "settings", designer snapshots, and unknown
            # mutation reasons fail closed to a full authoritative calculation.
            return True
        return False

    def request_flush(self, *, debounce_ms=None):
        if self.depth > 0 or self._flushing or not self.dirty:
            return
        delay = self._normalize_debounce_ms(debounce_ms)
        root = getattr(self.owner, "root", None)
        if delay and root is not None and hasattr(root, "after"):
            if self._after_job is not None:
                try:
                    root.after_cancel(self._after_job)
                except Exception:
                    pass
            self._after_job = root.after(delay, self.flush_now)
            return
        self.flush_now()

    def flush_now(self):
        if self.depth > 0 or self._flushing or not self.dirty:
            return False
        if self._after_job is not None:
            root = getattr(self.owner, "root", None)
            try:
                if root is not None:
                    root.after_cancel(self._after_job)
            except Exception:
                pass
            self._after_job = None
        reasons = set(self.dirty)
        self.dirty.clear()
        self._flushing = True
        try:
            self._metrics["flushes"] += 1
            if self._requires_calculation(reasons):
                self._metrics["calculation_flushes"] += 1
                self.owner.update_calculations()
            else:
                self._metrics["display_flushes"] += 1
                render = getattr(self.owner, "draw_preview", None)
                if callable(render):
                    render()
        finally:
            self._flushing = False
        return bool(reasons)

    def metrics_snapshot(self):
        return dict(self._metrics)


class _Phase6DerivedCacheOwner:
    """Own invalidation for GUI-derived geometry without touching immutable DXF source cache."""

    PRODUCTS = ("door_layout", "box_body_faces", "authoritative_render")
    _REASON_PRODUCTS = {
        "geometry": frozenset(PRODUCTS),
        "assembly": frozenset({"box_body_faces", "authoritative_render"}),
        "family-structure": frozenset(PRODUCTS),
        "baseline": frozenset(PRODUCTS),
        "display": frozenset(),
        "annotation": frozenset(),
        "camera": frozenset(),
    }

    def __init__(self):
        self._caches = {name: {} for name in self.PRODUCTS}
        self._invalidations = {name: 0 for name in self.PRODUCTS}

    def cache(self, product):
        return self._caches[str(product)]

    def invalidate(self, reason, changed_keys=()):
        reason = str(reason or "geometry")
        products = self._REASON_PRODUCTS.get(reason)
        if products is None:
            # Unknown state mutation fails closed at the derived layer only.
            products = frozenset(self.PRODUCTS)
        for product in products:
            cache = self._caches[product]
            if cache:
                cache.clear()
            self._invalidations[product] += 1
        return tuple(sorted(products))

    def metrics_snapshot(self):
        return dict(self._invalidations)


class BoxCalculatorGUI:
    def __init__(self, root):
        self.root = root
        self.project_controller = Phase6ProjectController(
            read_project=read_phase6_project,
            write_project=write_phase6_project,
            schema=PHASE6_PROJECT_SCHEMA,
        )
        self.workspace_controller = Phase6WorkspaceController()
        self.root.title(f"箱體展開圖計算器 (Box Unfolding Calculator) [{PHASE6_BUILD_ID}]")
        self.root.geometry("1100x750")
        self.root.minsize(950, 650)
        
        # 設定現代暗黑風格配色
        self.COLOR_BG = "#121214"          # 主背景
        self.COLOR_PANEL = "#1e1e24"       # 面板背景
        self.COLOR_INPUT_BG = "#151518"    # 輸入框背景
        self.COLOR_TEXT = "#e0e0e6"        # 主要文字
        self.COLOR_TEXT_MUTED = "#8e8e93"  # 次要文字
        self.COLOR_ACCENT = "#0a84ff"      # 藍色亮點/按鈕
        self.COLOR_ACCENT_HOVER = "#0066cc"# 按鈕懸停
        self.COLOR_CANVAS_BG = "#0d0d0f"   # 畫布背景
        
        self.root.configure(bg=self.COLOR_BG)

        # Committed runtime settings 的唯一所有者。config.ini 只負責啟動預設與明確持久化。
        self.settings_service = SettingsService(ae)
        self._settings_sync_guard = False
        self._phase6_update_scheduler = _Phase6UpdateScheduler(self)
        self._phase6_main_sync_revision = 0
        self._phase6_main_sync_fingerprint = None
        self._phase6_last_fold_designer_revision = 0
        self._phase6_last_fold_designer_fingerprint = None
        self._ui_text_controller = TextScaleController.for_widget(self.root)
        self._ui_text_controller.apply(self.settings_service.snapshot().get("ui_text_size", "small"))

        # 套用 ttk 樣式
        self.setup_styles()
        
        # 初始化變數
        self.init_variables()
        
        # 建立 UI 佈局
        self.create_widgets()
        
        # 綁定變數追蹤以進行即時計算與預覽更新
        self.bind_live_updates()
        
        # 首次計算與繪圖：Scheduler 是唯一 calculation executor。
        self._request_phase6_update("geometry", immediate=True)

    @property
    def fold_designer_box_body_profile(self):
        """舊介面相容：箱身 Fold Chain 直接由 Workspace Controller 提供。"""
        return self.workspace_controller.box_body_profile()

    @fold_designer_box_body_profile.setter
    def fold_designer_box_body_profile(self, profile):
        self.workspace_controller.set_box_body_profile(profile)

    @property
    def fold_designer_part_bundle(self):
        """舊介面相容：回傳 defensive-copy bundle，不保存 shadow dict。"""
        return self.workspace_controller.legacy_bundle()

    @fold_designer_part_bundle.setter
    def fold_designer_part_bundle(self, bundle):
        self.workspace_controller.load_legacy_bundle(bundle)

    @property
    def _phase6_existing_parts(self):
        """舊介面相容：實際 presence 由 Workspace Controller 擁有。"""
        return self.workspace_controller.raw_existing_parts()

    @_phase6_existing_parts.setter
    def _phase6_existing_parts(self, existing_parts):
        self.workspace_controller.replace_legacy_existing_parts(existing_parts)

    @property
    def _fold_designer_last_part_key(self):
        """舊介面相容：active part 不再有獨立 backing 欄位。"""
        return self.workspace_controller.active_part

    @_fold_designer_last_part_key.setter
    def _fold_designer_last_part_key(self, part_key):
        self.workspace_controller.set_active_part(part_key)

    @property
    def _phase6_loaded_project_path(self):
        """舊介面相容別名；直接委派 Project Controller，不保存第二份路徑。"""
        return self.project_controller.project_path

    @_phase6_loaded_project_path.setter
    def _phase6_loaded_project_path(self, path):
        self.project_controller.set_project_path(path)
        
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        # Notebook 樣式
        self.style.configure('TNotebook', background=self.COLOR_BG, borderwidth=0)
        self.style.configure('TNotebook.Tab', 
                             background=self.COLOR_PANEL, 
                             foreground=self.COLOR_TEXT, 
                             padding=[15, 6], 
                             font=self._ui_text_controller.scaled_font('Microsoft JhengHei', 10, 'bold'),
                             borderwidth=0)
        self.style.map('TNotebook.Tab', 
                       background=[('selected', self.COLOR_ACCENT)], 
                       foreground=[('selected', '#ffffff')])
        
        # ComboBox 樣式
        self.style.configure('TCombobox', 
                             fieldbackground=self.COLOR_INPUT_BG, 
                             background=self.COLOR_PANEL, 
                             foreground=self.COLOR_TEXT,
                             arrowcolor=self.COLOR_TEXT)
        
        # Label 樣式
        self.style.configure('TLabel', background=self.COLOR_PANEL, foreground=self.COLOR_TEXT, font=self._ui_text_controller.scaled_font('Microsoft JhengHei', 10))
        self.style.configure('Title.TLabel', background=self.COLOR_PANEL, foreground=self.COLOR_ACCENT, font=self._ui_text_controller.scaled_font('Microsoft JhengHei', 12, 'bold'))
        self.style.configure('Header.TLabel', background=self.COLOR_BG, foreground=self.COLOR_TEXT, font=self._ui_text_controller.scaled_font('Microsoft JhengHei', 14, 'bold'))
        
    def init_variables(self):
        # Tk variables 是 UI adapter；committed runtime 由 SettingsService 持有。
        settings = self.settings_service.snapshot()
        self.ui_text_size_var = tk.StringVar(value=ui_text_size_label(settings.get("ui_text_size", "small")))

        # 基礎設定（仍保留在主 GUI，並與 3D 設定中心雙向連動）
        self.w_var = tk.StringVar(value=self._fold_designer_number_text(settings["w"]))
        self.h_var = tk.StringVar(value=self._fold_designer_number_text(settings["h"]))
        self.d_var = tk.StringVar(value=self._fold_designer_number_text(settings["d"]))
        
        # 連動的 FW (邊框寬度)
        fw_value = float(settings["fw"])
        fw_init_val = str(int(fw_value) if fw_value.is_integer() else fw_value)
        self.fw_z_var = tk.StringVar(value=fw_init_val)
        self.fw_head_var = tk.StringVar(value=fw_init_val)
        self.fw_tail_var = tk.StringVar(value=fw_init_val)
        self.endcap_fw_state = normalize_endcap_fw_state({"fw": fw_value})
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
            "model": self.baseline_var.get() if hasattr(self, "baseline_var") else "",
        })
        self.fw_head_follow_var = tk.BooleanVar(value=True)
        self.fw_tail_follow_var = tk.BooleanVar(value=True)
        self.cb_fw_head = None
        self.cb_fw_tail = None
        
        # 進階設定
        self.t_var = tk.StringVar(value=self._fold_designer_number_text(settings["t"]))
        
        # 箱身 z 參數
        self.zl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl1"]))
        self.zl2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zl2"]))
        self.zr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr1"]))
        self.zr2_var = tk.StringVar(value=self._fold_designer_number_text(settings["zr2"]))
        self.z_comp_var = tk.StringVar(value=self._fold_designer_number_text(settings["z_comp"]))
        
        # 封頭尾 y 參數
        self.yl1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yl1"]))
        self.yr1_var = tk.StringVar(value=self._fold_designer_number_text(settings["yr1"]))
        self.ytop1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ytop1"]))
        self.ybottom1_var = tk.StringVar(value=self._fold_designer_number_text(settings["ybottom1"]))
        
        # 門參數
        self.door_gap_w_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_w"]))
        self.door_gap_h_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_gap_h"]))
        self.door_fold_l_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_l"]))
        self.door_fold_r_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_r"]))
        self.door_fold_t_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_t"]))
        self.door_fold_b_var = tk.StringVar(value=self._fold_designer_number_text(settings["door_fold_b"]))

        # 多門配置：W/H 仍是整盤尺寸；這裡只描述各欄起始寬與由上到下的起始高度。
        self.multi_door_enabled_var = tk.BooleanVar(value=False)
        self.door_layout_selected_var = tk.StringVar(value="0:0")
        self.door_layout_columns = []
        # UI adapter only. Authoritative inner-door enable state remains
        # self.receiving_inner_doors; these vars are rebuilt from that state.
        self.door_layout_inner_door_vars = {}
        self.door_layout_inner_door_offset_vars = {}
        self.door_layout_inner_door_offset_entries = {}
        # Family-authoritative inner-door presence/config. Geometry spans are
        # deliberately not invented here; T04 frame parts consume explicit
        # spans once a family/caller owns them.
        self.receiving_inner_doors = []
        self.door_layout_scope = "main"
        self.door_layout_handle_edges = {}
        self.door_nameplate_center_datum_top = None
        # 多門每一格各自保存孔位與門指示燈設定；單門仍沿用 surface_features["door"]。
        self.door_layout_features = {}
        self.door_layout_indicator_states = {}
        # Indicator-Box assembly holes belong to the Door cell that owns the box.
        self.door_layout_indicator_box_features = {}
        self.door_layout_indicator_door_features = {}
        self._derived_cache_owner = getattr(self, "_derived_cache_owner", None) or _Phase6DerivedCacheOwner()
        self._door_layout_baseline_cache = self._derived_cache_owner.cache("door_layout")
        self.door_layout_width_entries = {}
        self.door_layout_height_entries = {}
        self.door_layout_entry_windows = []
        self.door_layout_cell_bounds = {}
        self._door_layout_last_click = None  # ((column_index, row_index), event_time_ms)

        # 箱身三面編輯：使用者座標直接使用 WHD，不暴露展開/板厚補償座標。
        self.box_body_face_selected_var = tk.StringVar(value="back")
        self.box_body_face_features = {"left": [], "back": [], "right": []}
        self.box_body_face_bounds = {}
        self._box_body_face_last_click = None  # (face_key, event_time_ms)
        self.last_box_body_face_overview = {}
        self._box_body_baseline_face_cache = self._derived_cache_owner.cache("box_body_faces")
        
        # 底板參數
        self.base_plate_entries = []
        base_shrinks = [float(settings[k]) for k in (
            "base_plate_shrink_top", "base_plate_shrink_bottom",
            "base_plate_shrink_left", "base_plate_shrink_right",
        )]
        base_same = max(base_shrinks) - min(base_shrinks) < 1e-9
        self.base_plate_all_same_var = tk.BooleanVar(value=base_same)
        self.base_plate_shrink_same_var = tk.StringVar(value=self._fold_designer_number_text(base_shrinks[0]))
        self.base_plate_shrink_top_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_top"]))
        self.base_plate_shrink_bottom_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_bottom"]))
        self.base_plate_shrink_left_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_left"]))
        self.base_plate_shrink_right_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_shrink_right"]))
        self.base_plate_bend_var = tk.StringVar(value=self._fold_designer_number_text(settings["base_plate_bend"]))
        
        # 計算結果顯示用變數
        self.result_z_var = tk.StringVar(value="-")
        self.result_z_h_var = tk.StringVar(value="-")
        self.result_y_w_var = tk.StringVar(value="-")
        self.result_y_d_var = tk.StringVar(value="-")
        self.result_door_w_var = tk.StringVar(value="-")
        self.result_door_h_var = tk.StringVar(value="-")
        self.result_base_plate_w_var = tk.StringVar(value="-")
        self.result_base_plate_h_var = tk.StringVar(value="-")
        
        # 輸出選項：STOCK 開關
        self.draw_stock_var = tk.BooleanVar(value=bool(settings["draw_stock"]))
        # 輸出零件選擇
        self.export_z_var    = tk.BooleanVar(value=True)
        self.export_head_var = tk.BooleanVar(value=True)
        self.export_tail_var = tk.BooleanVar(value=True)
        self.export_door_var = tk.BooleanVar(value=True)
        self.export_base_plate_var = tk.BooleanVar(value=True)
        self.export_ib_var   = tk.BooleanVar(value=False)
        self.export_ib_door_var = tk.BooleanVar(value=False)
        self.baseline_var    = tk.StringVar(master=self.root, value="")
        self._active_cabinet_type = "金庫型"
        # Known-model switches always re-apply the target preset.  This map
        # stores immutable startup presets only; it must never become a
        # per-family "remember my last edits" session cache.
        self._cabinet_family_defaults = {}

        # 箱身組合方式是封頭/封尾上方截角的唯一類型來源。
        self.box_assembly_type_var = tk.StringVar(value=ASSEMBLY_TYPE_LABELS[CornerTypeId.INSERT_OVERLAY])
        self.cb_box_assembly = None
        self.assembly_joint_state = migrate_legacy_snapshot_joints({
            "assembly_type": "INSERT_OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        })

        # 自訂：截角型式只在此模式可手動選；金庫型永遠使用固定 Factory mapping。
        manual_corner_parts = ["head", "tail", "door", "base_plate", "indicator_box", "indicator_door"]
        self.manual_corner_state = new_manual_corner_state(manual_corner_parts)
        # Normal shop-floor case: top pair is the same, bottom pair is the same.
        # Four physical-corner values are still retained underneath for exceptions.
        self.manual_corner_pair_same = new_manual_corner_pair_same_state(manual_corner_parts)
        self.manual_active_corner_var = tk.StringVar(value="top")
        self.manual_top_same_var = tk.BooleanVar(master=self.root, value=True)
        self.manual_bottom_same_var = tk.BooleanVar(master=self.root, value=True)
        self.manual_corner_type_var = tk.StringVar(value=CornerTypeId.CROSS.value)
        self.manual_corner_cross_mode_var = tk.StringVar(value="標準")
        self.manual_corner_direction_var = tk.StringVar(value="寬")
        self.manual_corner_amount_var = tk.StringVar(value="1")
        self.manual_corner_secondary_retain_var = tk.StringVar(value="0.5")
        self.manual_corner_secondary_depth_var = tk.StringVar(value="2")
        self._manual_corner_param_guard = False
        # UI-only safety state: fine corner parameters are collapsed/locked by default.
        # This state is intentionally NOT serialized into .p6fold.
        self._manual_corner_param_unlocked = {}
        self.corner_type_panel = None
        self.corner_type_preview_canvas = None
        self.corner_type_small_canvases = {}
        saved_corner_state, saved_corner_pairs = load_corner_defaults_from_ini(ae)
        self._apply_manual_corner_snapshot(saved_corner_state, saved_corner_pairs)
        # The box-level assembly semantic is authoritative.  Old/default INI
        # snapshots may contain only CROSS end-cap corners; normalize them once
        # here so the state shown in 2D and consumed by manufacturing is the
        # same state.  Valid legacy INSERT/OVERLAY/INSERT_OVERLAY values are
        # preserved by assembly_type_from_corner_state().
        initial_assembly = assembly_type_from_corner_state(self.manual_corner_state)
        apply_box_assembly_type(
            self.manual_corner_state, self.manual_corner_pair_same, initial_assembly,
            reset_bottom_defaults=True,
        )
        self.box_assembly_type_var.set(ASSEMBLY_TYPE_LABELS[initial_assembly])

        # 指示燈盒子相關變數
        self.is_indicator_box_var = tk.BooleanVar(value=False)
        self.is_indicator_door_var = tk.BooleanVar(value=False)
        self.indicator_g_var = tk.StringVar(value="2")
        self.indicator_l_var = tk.StringVar(value="1")
        self.indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
        self.ib_hole_start_x_var = tk.StringVar(value="172.5")
        self.ib_hole_pitch_var = tk.StringVar(value="150")
        self.ib_hole_count_var = tk.StringVar(value="2")
        self.ib_hole_y_var = tk.StringVar(value="178.5")
        
        # 外門指示燈相關變數
        self.is_door_indicator_var = tk.BooleanVar(value=False)
        self.door_indicator_l_var = tk.StringVar(value="1")
        self.door_indicator_layer_g_vars = [tk.StringVar(value="2") for _ in range(6)]
        self.door_indicator_offset_x = 0.0
        self.door_indicator_offset_y = 0.0
        self.drag_active = False
        self.is_box_dist_var = tk.BooleanVar(value=False)
        
        # 左側指示燈盒子結果變數
        self.result_ib_w_var = tk.StringVar(value="-")
        self.result_ib_h_var = tk.StringVar(value="-")
        self.result_ib_door_w_var = tk.StringVar(value="-")
        self.result_ib_door_h_var = tk.StringVar(value="-")
        
        # 封頭/封尾開孔清單
        self.head_holes = []
        self.tail_holes = []
        # Generic unfolded-surface features for every other panel/frame.
        self.surface_features = {
            "box_body": [],
            "door": [],
            "base_plate": [],
            "indicator_box": [],
            "indicator_door": [],
            "head": [],
            "tail": [],
        }

        # 使用者提供的原始折彎/3D 設計器：只做資料橋接，不取代 Phase6 renderer/geometry。
        self.fold_designer_window = None
        self.fold_designer_app = None
        # Workspace presence / active part / profile stash are owned by
        # Phase6WorkspaceController.  Legacy attribute names below are
        # compatibility properties only; no second backing state is created.
        # Hidden auxiliary parts (indicator box / small door) have no top-level
        # preview Notebook tab.  When one is returned from the 3D designer,
        # keep it as the manual CornerType context until the user selects a
        # visible preview tab.
        self._manual_corner_part_override = None
        
    def _setting_var_map(self):
        """Tk variables backed by the single Phase6 runtime settings state."""
        return {
            "w": self.w_var, "h": self.h_var, "d": self.d_var,
            "t": self.t_var, "fw": self.fw_z_var, "draw_stock": self.draw_stock_var,
            "zl1": self.zl1_var, "zl2": self.zl2_var, "zr1": self.zr1_var, "zr2": self.zr2_var,
            "z_comp": self.z_comp_var,
            "yl1": self.yl1_var, "yr1": self.yr1_var,
            "ytop1": self.ytop1_var, "ybottom1": self.ybottom1_var,
            "door_gap_w": self.door_gap_w_var, "door_gap_h": self.door_gap_h_var,
            "door_fold_l": self.door_fold_l_var, "door_fold_r": self.door_fold_r_var,
            "door_fold_t": self.door_fold_t_var, "door_fold_b": self.door_fold_b_var,
            "base_plate_shrink_top": self.base_plate_shrink_top_var,
            "base_plate_shrink_bottom": self.base_plate_shrink_bottom_var,
            "base_plate_shrink_left": self.base_plate_shrink_left_var,
            "base_plate_shrink_right": self.base_plate_shrink_right_var,
            "base_plate_bend": self.base_plate_bend_var,
        }

    def _collect_main_setting_values(self):
        values = self.settings_service.snapshot().as_dict()
        for key, var in self._setting_var_map().items():
            try:
                if isinstance(var, tk.BooleanVar):
                    values[key] = bool(var.get())
                else:
                    values[key] = float(var.get())
            except (TypeError, ValueError, tk.TclError):
                pass
        return self.settings_service.update(values).as_dict()

    @staticmethod
    def _serialize_corner_selection(raw_selection):
        selection = normalize_corner_selection(raw_selection)
        raw = {
            "type_id": selection.type_id.value,
            "rotation_quadrants": 0,
        }
        if selection.cross_mode is not None:
            raw["cross_mode"] = selection.cross_mode.value
        if selection.direction is not None:
            raw["direction"] = selection.direction.value
        if selection.amount_t is not None:
            raw["amount_t"] = float(selection.amount_t)
        if selection.secondary_retain_t is not None:
            raw["secondary_retain_t"] = float(selection.secondary_retain_t)
        if selection.secondary_depth_t is not None:
            raw["secondary_depth_t"] = float(selection.secondary_depth_t)
        return raw

    def _serialize_manual_corner_state(self):
        result = {}
        for part_key, corners in self.manual_corner_state.items():
            result[part_key] = {
                corner_key: self._serialize_corner_selection(raw_selection)
                for corner_key, raw_selection in corners.items()
            }
        return result

    def _current_cabinet_type_name(self):
        var = getattr(self, "baseline_var", None)
        try:
            value = var.get() if var is not None else "金庫型"
        except Exception:
            value = "金庫型"
        value = normalize_custom_model_name(value)
        try:
            return resolve_cabinet_type(value).canonical_name
        except (KeyError, ValueError):
            # Existing baseline folders and 自訂 still use the legacy vault
            # manufacturing family unless a registered family name is selected.
            return "金庫型"

    @staticmethod
    def _baseline_model_choices():
        """One visible selector owns both cabinet type and baseline model.

        Registered implemented families are valid model choices even when they
        intentionally have no baseline DXF folder (受電箱 phase 1).  Physical
        baseline folders remain valid choices, and 自訂 stays last.
        """
        choices = []
        seen = set()
        physical_models = [normalize_custom_model_name(name) for name in ae.get_baseline_list()]
        for name in physical_models:
            name = normalize_custom_model_name(name)
            if name and name not in seen and not is_unknown_model(name):
                choices.append(name)
                seen.add(name)
        # Formula-only implemented families (currently 受電箱) must be visible
        # in the same selector even without a baseline DXF directory.  金庫型
        # remains resource-backed: do not invent it when its baseline is absent.
        for item in registered_cabinet_types():
            if not item.implemented:
                continue
            name = str(item.canonical_name or "").strip()
            if name == "金庫型" and name not in seen:
                continue
            if name and name not in seen:
                choices.append(name)
                seen.add(name)
        return with_unknown_model(choices)

    def _endcap_depth_comp_t_for_family(self, model_name=None):
        source = (
            BoxCalculatorGUI._current_cabinet_type_name(self)
            if model_name is None else model_name
        )
        return cabinet_family_policy.endcap_depth_comp_t(source)

    def _known_corner_state_for_current_family(self, parts):
        return known_model_corner_state(
            parts, cabinet_family=BoxCalculatorGUI._current_cabinet_type_name(self)
        )

    def _enforce_known_model_corner_types(self, *, reset_all=False):
        """Keep known-model CornerType fixed while allowing same-type parameter overrides."""
        model = str(self.baseline_var.get() if hasattr(self, "baseline_var") else "").strip()
        if not model or is_unknown_model(model):
            return
        fixed = self._known_corner_state_for_current_family(self.manual_corner_state.keys())
        for part_key, corners in fixed.items():
            if part_key not in self.manual_corner_state:
                continue
            for corner_key, fixed_selection in corners.items():
                current = normalize_corner_selection(self.manual_corner_state[part_key][corner_key])
                if reset_all or current.type_id is not fixed_selection.type_id:
                    self.manual_corner_state[part_key][corner_key] = fixed_selection
            if reset_all and part_key in self.manual_corner_pair_same:
                self.manual_corner_pair_same[part_key]["top"] = True
                self.manual_corner_pair_same[part_key]["bottom"] = True

    def _apply_manual_corner_snapshot(self, corner_state=None, pair_same=None):
        for part_key, corners in (corner_state or {}).items():
            if part_key not in self.manual_corner_state:
                continue
            for corner_key, raw in (corners or {}).items():
                if corner_key not in self.manual_corner_state[part_key]:
                    continue
                if isinstance(raw, dict):
                    type_id = raw.get("type_id", CornerTypeId.CROSS.value)
                    rotation = int(raw.get("rotation_quadrants", 0) or 0)
                    kwargs = {
                        "cross_mode": raw.get("cross_mode"),
                        "direction": raw.get("direction"),
                        "amount_t": raw.get("amount_t"),
                        "secondary_retain_t": raw.get("secondary_retain_t"),
                        "secondary_depth_t": raw.get("secondary_depth_t"),
                    }
                else:
                    type_id = raw
                    rotation = 0
                    kwargs = {}
                try:
                    selection = CornerTypeSelection(CornerTypeId(type_id), rotation, **kwargs)
                    self.manual_corner_state[part_key][corner_key] = normalize_corner_selection(selection)
                except (TypeError, ValueError):
                    continue
        for part_key, pairs in (pair_same or {}).items():
            if part_key not in self.manual_corner_pair_same:
                continue
            for pair_key, enabled in (pairs or {}).items():
                if pair_key in self.manual_corner_pair_same[part_key]:
                    self.manual_corner_pair_same[part_key][pair_key] = bool(enabled)
        self._enforce_known_model_corner_types(reset_all=False)
        self.refresh_corner_type_panel()

    def _apply_fold_designer_live_settings(self, values, *, recalculate=True):
        """Commit FoldDesigner values without replaying unchanged Tk writes."""
        before = self.settings_service.snapshot()
        clean = {key: value for key, value in dict(values or {}).items() if key in before}
        if not clean:
            return
        current = self.settings_service.update(clean)
        changed = {key for key in clean if before.get(key) != current.get(key)}
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is not None:
            scheduler.begin()
        self._settings_sync_guard = True
        try:
            for key, var in self._setting_var_map().items():
                if key not in changed:
                    continue
                if isinstance(var, tk.BooleanVar):
                    target = bool(current[key])
                else:
                    target = self._fold_designer_number_text(current[key])
                try:
                    existing = var.get()
                except Exception:
                    existing = object()
                if existing != target:
                    var.set(target)
            if "fw" in changed:
                box_fw = float(current["fw"])
                for part in ("head", "tail"):
                    state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
                    if bool(state.get("follow_box", True)):
                        state["value"] = box_fw
                self._sync_endcap_fw_controls()
            shrink_keys = (
                "base_plate_shrink_top", "base_plate_shrink_bottom",
                "base_plate_shrink_left", "base_plate_shrink_right",
            )
            if all(k in current for k in shrink_keys):
                shrinks = [float(current[k]) for k in shrink_keys]
                same = max(shrinks) - min(shrinks) < 1e-9
                if self.base_plate_all_same_var.get() != same:
                    self.base_plate_all_same_var.set(same)
                if same:
                    target = self._fold_designer_number_text(shrinks[0])
                    if self.base_plate_shrink_same_var.get() != target:
                        self.base_plate_shrink_same_var.set(target)
            if recalculate and changed and scheduler is not None:
                scheduler.mark_dirty("settings")
        finally:
            self._settings_sync_guard = False
            if scheduler is not None:
                scheduler.end()
        if recalculate and changed and scheduler is None:
            self._request_phase6_update("geometry")

    def _save_fold_designer_defaults(self, context, values, corner_state=None, corner_pair_same=None):
        # Explicitly saving defaults writes the 3D draft to config.ini, but it
        # must not commit that draft into the open main GUI before 確定.
        context = context or GLOBAL_CONTEXT
        draft = self.settings_service.snapshot().as_dict()
        draft.update({k: v for k, v in dict(values or {}).items() if k in draft})
        self.settings_service.persist_defaults(context=context, values=draft)
        save_corner_defaults_to_ini(
            ae,
            corner_state if corner_state is not None else self._serialize_manual_corner_state(),
            corner_pair_same if corner_pair_same is not None else self.manual_corner_pair_same,
            context=context,
        )
        return True

    def _apply_fold_designer_live_corner_state(self, corner_state, corner_pair_same):
        self._apply_manual_corner_snapshot(corner_state, corner_pair_same)
        self._request_phase6_update("assembly")

    def _notify_fold_designer_corner_state(self):
        if getattr(self, "_fold_designer_live_sync_guard", False):
            return
        designer = getattr(self, "fold_designer_app", None)
        if designer is None or not hasattr(designer, "apply_external_corner_state"):
            return
        if getattr(designer, "_transaction_confirm_callback", None) is not None:
            # Keep the 3D baseline/CornerType draft isolated until 確定.
            return
        try:
            designer.apply_external_corner_state(
                self._serialize_manual_corner_state(), deepcopy(self.manual_corner_pair_same)
            )
        except tk.TclError:
            pass

    def _phase6_external_sync_envelope(self, delta):
        state = {"settings": self.settings_service.snapshot().as_dict()}
        fingerprint = stable_fingerprint(state)
        if fingerprint == getattr(self, "_phase6_main_sync_fingerprint", None):
            return None
        revision = int(getattr(self, "_phase6_main_sync_revision", 0) or 0) + 1
        self._phase6_main_sync_revision = revision
        self._phase6_main_sync_fingerprint = fingerprint
        return {
            "origin": "main_gui",
            "revision": revision,
            "transaction_id": f"main_gui:{revision}",
            "delta": deepcopy(dict(delta or {})),
            "fingerprint": fingerprint,
        }

    def _on_main_setting_var_changed(self, key, var):
        if getattr(self, "_settings_sync_guard", False):
            return
        try:
            value = bool(var.get()) if isinstance(var, tk.BooleanVar) else float(var.get())
        except (TypeError, ValueError, tk.TclError):
            return
        scheduler = self._phase6_update_scheduler
        scheduler.begin()
        try:
            self.settings_service.update({key: value})
            if key == "fw":
                self._settings_sync_guard = True
                try:
                    for part in ("head", "tail"):
                        state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": value})
                        if bool(state.get("follow_box", True)):
                            state["value"] = float(value)
                    self._sync_endcap_fw_controls()
                finally:
                    self._settings_sync_guard = False
            scheduler.mark_dirty(f"setting:{key}")
            designer = getattr(self, "fold_designer_app", None)
            if not getattr(self, "_fold_designer_live_sync_guard", False) and designer is not None:
                try:
                    if hasattr(designer, "apply_external_sync"):
                        envelope = self._phase6_external_sync_envelope({"settings": {key: value}})
                        if envelope is not None:
                            designer.apply_external_sync(envelope)
                    elif hasattr(designer, "apply_external_settings"):
                        designer.apply_external_settings({key: value})
                except tk.TclError:
                    pass
        finally:
            scheduler.end()

    @staticmethod
    def _fold_designer_secondary_scene_rows(scene):
        """Return numeric baseline hole rows, excluding the structural outline/BEND."""
        rows = []
        skipped_outline = False
        for primitive in getattr(scene, "primitives", ()): 
            layer = str(getattr(primitive, "layer", "") or "")
            if layer not in {"CUTTING", "BLIND_HOLE"}:
                continue
            if isinstance(primitive, PolylinePrimitive):
                if layer == "CUTTING" and not skipped_outline:
                    skipped_outline = True
                    continue
                points = tuple(getattr(primitive, "points", ()) or ())
                if not getattr(primitive, "closed", False) or len(points) < 3:
                    continue
                xs = [float(p.x) for p in points]; ys = [float(p.y) for p in points]
                rows.append({
                    "kind": "方孔", "layer": layer,
                    "x": (min(xs) + max(xs)) / 2.0,
                    "y": (min(ys) + max(ys)) / 2.0,
                    "d1": max(xs) - min(xs), "d2": max(ys) - min(ys),
                })
            elif isinstance(primitive, CirclePrimitive):
                center = primitive.center
                rows.append({
                    "kind": "圓孔", "layer": layer,
                    "x": float(center.x), "y": float(center.y),
                    "d1": float(primitive.radius) * 2.0, "d2": 0.0,
                })
        return rows

    def _query_fold_designer_baseline_data(self, part_key, model, values):
        """Read-only lazy baseline numeric data for the 3D settings panel."""
        model = str(model or "").strip()
        if not model or is_unknown_model(model):
            return []
        v = dict(values or {})
        try:
            w = float(v.get("w", self.w_var.get())); h = float(v.get("h", self.h_var.get()))
            d = float(v.get("d", self.d_var.get())); t = float(v.get("t", self.t_var.get()))
            fw = float(v.get("fw", self.fw_z_var.get()))
            if part_key == "door":
                if hasattr(ae, "has_baseline_part") and not ae.has_baseline_part(model, "門.dxf"):
                    return []
                door_fw = self._door_material_frame_width(fw, t, model_name=model)
                data = ae.get_stretched_door_data(
                    model, w, h, t, door_fw,
                    float(v.get("door_gap_w", ae.door_gap_w_def)),
                    float(v.get("door_gap_h", ae.door_gap_h_def)),
                    float(v.get("door_fold_l", ae.door_fold_left_def)),
                    float(v.get("door_fold_r", ae.door_fold_right_def)),
                    float(v.get("door_fold_t", ae.door_fold_top_def)),
                    float(v.get("door_fold_b", ae.door_fold_bottom_def)),
                    frame_edges=DoorFrameEdges(),
                )
                return self._fold_designer_secondary_scene_rows(data.scene)
            if part_key in {"head", "tail"}:
                data = ae.get_stretched_end_cap_data(
                    model, w, h, d, t, FW_val=fw, is_tail=(part_key == "tail")
                )
                return self._fold_designer_secondary_scene_rows(data.scene)
        except Exception:
            return []
        return []

    def _apply_cabinet_family_endcap_policy(
        self, policy, part_key, *, snapshot=None, thickness=None, structure_state=None
    ):
        """Apply cabinet-family geometry inputs without changing operator Corner selections.

        The Corner selections remain the operator/registry Source of Truth. Cabinet families
        may supply only family geometry such as the receiving-cabinet effective bottom FW.
        Both the main GUI and Fold Designer payload adapter call this helper so 2D/3D cannot
        drift by rebuilding the same family rule differently.
        """
        if policy is None or str(part_key) not in {"head", "tail"}:
            return policy

        family_source = (
            BoxCalculatorGUI._current_cabinet_type_name(self)
            if snapshot is None else snapshot
        )
        if not cabinet_family_policy.supports_bottom_wrap_controls(family_source):
            return policy

        if structure_state is None:
            try:
                structure_state = self.workspace_controller.box_body_structure_state()
            except Exception:
                structure_state = None
        if thickness is None:
            try:
                thickness = float(self.t_var.get())
            except Exception:
                thickness = float(ae.T)
        return replace(
            policy,
            bottom_fw=cabinet_family_policy.effective_endcap_bottom_fw(
                family_source,
                structure_state,
                thickness=float(thickness),
                default_fw=float(policy.bottom_fw if policy.bottom_fw is not None else policy.fw),
            ),
        )

    @staticmethod
    def _fold_designer_corner_policy_from_payload(corner_state, part_key, fw):
        corners = dict((corner_state or {}).get(part_key, {}) or {})
        required = ("top_left", "top_right", "bottom_left", "bottom_right")
        if not all(key in corners for key in required):
            return None
        selections = {}
        for key in required:
            raw = corners[key]
            if isinstance(raw, CornerTypeSelection):
                selections[key] = normalize_corner_selection(raw)
                continue
            raw = dict(raw or {})
            selections[key] = CornerTypeSelection(
                CornerTypeId(str(raw.get("type_id", "CROSS")).upper()),
                rotation_quadrants=int(raw.get("rotation_quadrants", 0) or 0),
                cross_mode=raw.get("cross_mode"),
                direction=raw.get("direction"),
                amount_t=raw.get("amount_t"),
                secondary_retain_t=raw.get("secondary_retain_t"),
                secondary_depth_t=raw.get("secondary_depth_t"),
            )
        return policy_from_corner_state(selections, fw=float(fw))

    def _authoritative_render_data(self, spec, context=None):
        """Return one immutable manufacturing render object for an exact PartSpec.

        2D and 3D callers share this cache.  Geometry is built only by
        manufacturing_api; GUI/renderer code may consume scene/material but may
        not reconstruct CUTTING, baseline or CornerType geometry.
        """
        ctx = context or ManufacturingContext(draw_stock=False)
        cache = getattr(self, "_authoritative_part_render_cache", None)
        if cache is None:
            owner = getattr(self, "_derived_cache_owner", None)
            if owner is None:
                owner = self._derived_cache_owner = _Phase6DerivedCacheOwner()
            cache = self._authoritative_part_render_cache = owner.cache("authoritative_render")
        cache_key = (repr(spec), repr(ctx))
        if cache_key in cache:
            return cache[cache_key]
        if isinstance(spec, BoxBodyPartSpec):
            from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
            structure = normalize_box_body_structure_state(spec.structure_state)
            if structure.get("active_type") != BoxBodyStructureType.INTEGRAL.value:
                render_data = manufacturing_api.build_box_body_structure_render_data(spec, ctx)
            else:
                render_data = manufacturing_api.build_part_render_data(spec, ctx)
        else:
            render_data = manufacturing_api.build_part_render_data(spec, ctx)
        cache[cache_key] = render_data
        if len(cache) > 32:
            cache.pop(next(iter(cache)))
        return render_data

    def _require_verified_baseline_sources_for_manufacturing(self):
        """Fail closed when a baseline-backed manufacturing source is not freshly verified."""
        model = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else ""
        if not model:
            return True
        for filename in ("箱身.dxf", "封頭尾.dxf", "門.dxf"):
            path = ae.baseline_part_path(model, filename)
            if not path:
                continue
            _doc, status = ae.load_baseline_dxf_source_with_status(
                path, allow_unverified_source=False
            )
            if status != ae.BASELINE_SOURCE_VERIFIED:
                raise RuntimeError(
                    f"基準來源尚未驗證：{model}/{filename}；正式製造輸出已停止。"
                )
        return True

    def _export_authoritative_part(self, spec, output_path, context=None):
        """Save the exact cached FinalScene used by 2D/3D without rebuilding it."""
        self._flush_phase6_authoritative_state()
        self._require_verified_baseline_sources_for_manufacturing()
        ctx = context or self._manufacturing_context(draw_stock=False)
        render_data = self._authoritative_render_data(spec, ctx)
        if getattr(render_data, "pieces", None):
            output = Path(output_path)
            return manufacturing_api.generate_box_body_structure_parts(spec, output.parent, ctx)
        return manufacturing_api.save_part_render_data_dxf(
            render_data, output_path, overwrite=bool(getattr(ctx, "overwrite", False))
        )


    def _fold_designer_part_spec_from_payload(self, part_key, payload):
        """Convert Fold Designer draft state to the canonical manufacturing request.

        This is the only draft-state adapter.  It returns ``(PartSpec, context)``;
        the bridge never builds manufacturing geometry itself.
        """
        data = dict(payload or {})
        key = str(part_key or "")
        w = float(data.get("w", ae.W)); h = float(data.get("h", ae.H))
        d = float(data.get("d", ae.D)); t = float(data.get("t", ae.T))
        fw = float(data.get("fw", ae.FW))
        model = normalize_custom_model_name(data.get("model"))
        unknown = is_unknown_model(model)
        corner_state = data.get("corner_state") or {}
        features = tuple(data.get("features") or ())
        face_features = data.get("face_features") or {}
        door_cell = None
        base_plate_cell = None
        if key.startswith("door_c"):
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"門格缺少 authoritative multi-door topology: {key}")
            door_cell = next(
                (cell for cell in derive_door_layout_cells(columns)
                 if door_layout_export_filename(cell).removesuffix(".dxf") == key),
                None,
            )
            if door_cell is None:
                raise ValueError(f"門格 stable_id 不存在於 authoritative topology: {key}")
            w = float(door_cell.start_width)
            h = float(door_cell.start_height)
        elif key.startswith("base_plate_c"):
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"底板缺少 authoritative multi-door topology: {key}")
            owner_door_key = key.replace("base_plate_", "door_", 1)
            base_plate_cell = next(
                (cell for cell in derive_door_layout_cells(columns)
                 if door_layout_export_filename(cell).removesuffix(".dxf") == owner_door_key),
                None,
            )
            if base_plate_cell is None:
                raise ValueError(f"底板 stable_id 不存在於 authoritative topology: {key}")
            w = float(base_plate_cell.start_width)
            h = float(base_plate_cell.start_height)

        def payload_policy(part):
            resolved = self._fold_designer_corner_policy_from_payload(corner_state, part, fw)
            if resolved is None and not unknown:
                fallback = known_model_corner_state(
                    (part,), cabinet_family=BoxCalculatorGUI._current_cabinet_type_name(self)
                ).get(part)
                resolved = policy_from_corner_state(fallback, fw=fw) if fallback is not None else None
            return self._apply_cabinet_family_endcap_policy(
                resolved, part, snapshot=data, thickness=t,
                structure_state=data.get("box_body_structure"),
            )

        policy_part = "door" if door_cell is not None else ("base_plate" if base_plate_cell is not None else key)
        policy = payload_policy(policy_part)

        context = ManufacturingContext(draw_stock=False)
        if key == "box_body":
            spec = self._box_body_part_spec_from_values(
                {
                    "w": w, "h": h, "d": d, "t": t, "fw": fw,
                    "zl1": float(data.get("zl1", ae.zl1_def)),
                    "zl2": float(data.get("zl2", ae.zl2_def)),
                    "zr1": float(data.get("zr1", ae.zr1_def)),
                    "zr2": float(data.get("zr2", ae.zr2_def)),
                    "z_comp": float(data.get("z_comp", getattr(ae, "z_comp_def", 0.0))),
                },
                model_name=(None if unknown else model),
                features=features, face_features=face_features,
                head_corner_policy=payload_policy("head"),
                tail_corner_policy=payload_policy("tail"),
                fold_profile=data.get("fold_profile"),
                structure_state=data.get("box_body_structure"),
                head_ybottom1=float(data.get("head_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
                tail_ybottom1=float(data.get("tail_ybottom1", data.get("ybottom1", ae.ybottom1_def))),
            )
        elif key in {"head", "tail"}:
            endcap_values = {
                "w": w, "h": h, "d": d, "t": t, "fw": fw,
                "yl1": float(data.get("yl1", ae.yl1_def)),
                "yr1": float(data.get("yr1", ae.yr1_def)),
                "ytop1": float(data.get("ytop1", ae.ytop1_def)),
                "ybottom1": float(data.get("ybottom1", ae.ybottom1_def)),
                "zl1": float(data.get("zl1", ae.zl1_def)),
                "zr1": float(data.get("zr1", ae.zr1_def)),
            }
            resolved_cuts = data.get("resolved_assembly_relief_cuts", None)
            if resolved_cuts is None and bool(data.get("_use_committed_relief")):
                resolved_cuts = self._resolved_committed_assembly_relief_cuts(
                    key, endcap_values, data.get("fold_profiles") or {}
                )
            formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
                data.get("box_body_profile") or self.workspace_controller.box_body_profile() or (), t
            )
            spec = self._end_cap_part_spec_from_values(
                endcap_values,
                model_name=(None if unknown else model), is_tail=(key == "tail"),
                holes=features, corner_policy=policy, fold_profiles=data.get("fold_profiles"),
                resolved_assembly_relief_cuts=resolved_cuts or (),
                box_body_formed_fw_left=formed_fw_left, box_body_formed_fw_right=formed_fw_right,
                box_body_structure_state=(data.get("box_body_structure") or self.workspace_controller.box_body_structure_state()),
                endcap_bottom_wrap_state=data.get("endcap_bottom_wrap"),
                assembly_joints=data.get("assembly_joints"),
            )
        elif key == "door" or door_cell is not None:
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or ()))
            direct = tuple(int(v) for v in (data.get("door_indicator_groups") or ()))
            indicator_hole = None
            if bool(data.get("door_indicator_box_enabled")) and groups:
                indicator_hole = manufacturing_api.indicator_box_opening_size(groups, thickness=t)
            spec = self._door_part_spec_from_values(
                {
                    "w": w, "h": h, "t": t, "fw": fw,
                    "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                    "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                    "door_fold_l": float(data.get("door_fold_l", ae.door_fold_left_def)),
                    "door_fold_r": float(data.get("door_fold_r", ae.door_fold_right_def)),
                    "door_fold_t": float(data.get("door_fold_t", ae.door_fold_top_def)),
                    "door_fold_b": float(data.get("door_fold_b", ae.door_fold_bottom_def)),
                },
                model_name=(None if unknown else model),
                features=features,
                indicator_hole=indicator_hole,
                door_indicator=(direct or None),
                door_indicator_offset=tuple(data.get("door_indicator_offset") or (0.0, 0.0)),
                use_box_distance=bool(data.get("use_box_distance", False)),
                corner_policy=policy,
                frame_edges=(door_cell.edges if door_cell is not None else None),
            )
        elif key == "base_plate" or key.startswith("base_plate_c"):
            spec = self._base_plate_part_spec_from_values(
                {
                    "w": w, "h": h, "t": t, "fw": fw,
                    "base_plate_shrink_top": float(data.get("base_plate_shrink_top", 0)),
                    "base_plate_shrink_bottom": float(data.get("base_plate_shrink_bottom", 0)),
                    "base_plate_shrink_left": float(data.get("base_plate_shrink_left", 0)),
                    "base_plate_shrink_right": float(data.get("base_plate_shrink_right", 0)),
                    "base_plate_bend": float(data.get("base_plate_bend", 20)),
                    "model": model,
                },
                features=features, corner_policy=policy,
            )
        elif key == "indicator_box":
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
            spec = self._indicator_box_part_spec_from_values(
                {"t": t}, groups, features=features
            )
        elif key == "indicator_door":
            groups = tuple(int(v) for v in (data.get("indicator_layer_groups") or (1,)))
            spec, context = self._indicator_door_part_spec_from_values(
                {
                    "t": t, "fw": fw,
                    "door_gap_w": float(data.get("door_gap_w", ae.door_gap_w_def)),
                    "door_gap_h": float(data.get("door_gap_h", ae.door_gap_h_def)),
                    "indicator_door_fold": float(data.get("indicator_door_fold", getattr(ae, "indicator_small_door_fold_def", 19.0))),
                },
                groups, features=features,
            )
        else:
            raise ValueError(f"未知 3D 板件: {key}")
        return spec, context

    def _query_fold_designer_render_data(self, part_key, payload):
        """Return the same authoritative final geometry used by 2D consumers."""
        key = str(part_key or "")
        if key.startswith("box_body:divider:"):
            from ae_engine.door_dividers import derive_box_body_dividers

            data = dict(payload or {})
            columns = tuple(
                (float(row[0]), tuple(float(value) for value in row[1]))
                for row in tuple(data.get("door_layout_columns") or ())
            )
            if not columns:
                raise ValueError(f"中隔缺少 authoritative multi-door topology: {key}")
            dividers = derive_box_body_dividers(
                columns,
                depth=float(data.get("d", ae.D)),
                thickness=float(data.get("t", ae.T)),
                layout_scope=str(data.get("door_layout_scope") or "main").strip() or "main",
                handle_edges=dict(data.get("door_handle_edges") or {}),
            )
            divider = next((item for item in dividers if item.stable_id == key), None)
            if divider is None:
                raise ValueError(f"中隔 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_box_body_divider_render_data(divider)

        if key.startswith("inner_door:") and key.endswith(":panel"):
            data = dict(payload or {})
            panels = cabinet_family_policy.derive_inner_door_panels(data)
            panel = next((item for item in panels if item.stable_id == key), None)
            if panel is None:
                raise ValueError(f"內門板 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_inner_door_panel_render_data(panel)

        if key.startswith("inner_door:") and key.endswith("_frame"):
            from ae_engine.inner_door_frames import (
                InnerDoorFrameSet,
                derive_all_inner_door_frames,
            )
            data = dict(payload or {})
            if cabinet_family_policy.has_inner_door_frame_derivation(data):
                frame_sets = list(cabinet_family_policy.derive_inner_door_frame_sets(data))
            else:
                frame_sets = []
                thickness = float(data.get("t", ae.T))
                for item in tuple(data.get("inner_doors") or ()):
                    if not isinstance(item, dict):
                        continue
                    stable_id = str(item.get("stable_id") or "").strip()
                    spans = item.get("frame_spans")
                    if not stable_id or not isinstance(spans, dict) or not spans:
                        continue
                    included = tuple(
                        str(side).strip().lower()
                        for side in tuple(item.get("included_frame_sides") or ("top", "bottom", "left", "right"))
                    )
                    frame_sets.append(InnerDoorFrameSet(
                        inner_door_id=stable_id,
                        spans=dict(spans),
                        thickness=thickness,
                        included_sides=included,
                    ))
            frames = derive_all_inner_door_frames(tuple(frame_sets))
            frame = next((item for item in frames if item.stable_id == key), None)
            if frame is None:
                raise ValueError(f"內門框 stable_id 不存在於 authoritative topology: {key}")
            return manufacturing_api.build_inner_door_frame_render_data(frame)

        spec, context = self._fold_designer_part_spec_from_payload(part_key, payload)
        if isinstance(spec, BoxBodyPartSpec):
            from phase6_box_body_structure import BoxBodyStructureType, normalize_box_body_structure_state
            state = normalize_box_body_structure_state(spec.structure_state)
            if state.get("active_type") != BoxBodyStructureType.INTEGRAL.value:
                return manufacturing_api.build_box_body_structure_render_data(spec, context)
        return self._authoritative_render_data(spec, context)

    def _make_original_fold_designer_snapshot(self):
        def number(var, fallback=0.0):
            try:
                return float(var.get())
            except (TypeError, ValueError, tk.TclError):
                return float(fallback)

        snapshot = {
            "model": self.baseline_var.get().strip(),
            "_runtime_project_path": self.project_controller.project_path,
            "w": number(self.w_var, ae.W),
            "h": number(self.h_var, ae.H),
            "d": number(self.d_var, ae.D),
            "t": number(self.t_var, ae.T),
            "fw": number(self.fw_z_var, ae.FW),
            "zl1": number(self.zl1_var, ae.zl1_def),
            "zl2": number(self.zl2_var, ae.zl2_def),
            "zr2": number(self.zr2_var, ae.zr2_def),
            "zr1": number(self.zr1_var, ae.zr1_def),
            "yl1": number(self.yl1_var, ae.yl1_def),
            "yr1": number(self.yr1_var, ae.yr1_def),
            "ytop1": number(self.ytop1_var, ae.ytop1_def),
            "ybottom1": number(self.ybottom1_var, ae.ybottom1_def),
            "door_gap_w": number(self.door_gap_w_var, ae.door_gap_w_def),
            "door_gap_h": number(self.door_gap_h_var, ae.door_gap_h_def),
            "door_fold_l": number(self.door_fold_l_var, ae.door_fold_left_def),
            "door_fold_r": number(self.door_fold_r_var, ae.door_fold_right_def),
            "door_fold_t": number(self.door_fold_t_var, ae.door_fold_top_def),
            "door_fold_b": number(self.door_fold_b_var, ae.door_fold_bottom_def),
            "base_plate_shrink_top": number(self.base_plate_shrink_top_var, 0),
            "base_plate_shrink_bottom": number(self.base_plate_shrink_bottom_var, 0),
            "base_plate_shrink_left": number(self.base_plate_shrink_left_var, 0),
            "base_plate_shrink_right": number(self.base_plate_shrink_right_var, 0),
            "base_plate_bend": number(self.base_plate_bend_var, 20),
            "indicator_box_fold": float(getattr(ae, "indicator_box_fold_def", 49.0)),
            "indicator_door_fold": float(getattr(ae, "indicator_small_door_fold_def", 19.0)),
            "use_box_distance": bool(self.is_box_dist_var.get()),
            "assembly_type": assembly_intent_value(self._current_box_assembly_type()),
            "endcap_fw": deepcopy(self.endcap_fw_state),
            "endcap_bottom_wrap": deepcopy(getattr(
                self, "endcap_bottom_wrap_state", normalize_endcap_bottom_wrap_state({"model": self.baseline_var.get()})
            )),
            "assembly_relief": deepcopy(getattr(self, "assembly_relief_state", {}) or {}),
            "multi_door_enabled": bool(self.multi_door_enabled_var.get()) if hasattr(self, "multi_door_enabled_var") else False,
            "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
            "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
            "inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
            "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
        }
        if getattr(self, "door_layout_columns", None):
            snapshot["door_layout_columns"] = [
                [float(width), [float(v) for v in heights]]
                for width, heights in self.get_door_layout_columns()
            ]
        else:
            snapshot["door_layout_columns"] = []
        settings = self._collect_main_setting_values()
        snapshot.update({key: value for key, value in settings.items() if key in snapshot})
        snapshot["settings"] = dict(settings)
        # Project files always persist the actual current fine parameters.
        # Known models keep CornerType itself readonly in the UI, but an explicit
        # parameter unlock is a real project edit and must survive save/load.
        snapshot["corner_state"] = self._serialize_manual_corner_state()
        snapshot["corner_pair_same"] = deepcopy(self.manual_corner_pair_same)
        snapshot["corner_editable"] = is_unknown_model(self.baseline_var.get())
        snapshot["corner_type_labels"] = {type_id.value: CORNER_TYPE_LABELS[type_id] for type_id in EDITABLE_CORNER_TYPE_IDS}
        baseline_models = self._baseline_model_choices()
        snapshot["baseline_models"] = baseline_models
        snapshot["baseline_unknown_value"] = next(
            (model for model in baseline_models if is_unknown_model(model)), "自訂"
        )
        # Immutable reset source: ae.default_config, never config.ini/runtime.
        snapshot["factory_defaults"] = load_factory_defaults_from_ae(ae)

        box_body_profile = self.workspace_controller.box_body_profile()
        if box_body_profile:
            snapshot["box_body_profile"] = [dict(seg) for seg in box_body_profile]

        # Physical presence is one source of truth.  Output checkboxes only
        # decide which EXISTING parts to export; unchecking export must never
        # delete a part when the 3D designer is opened.
        committed_profiles = self.workspace_controller.part_profiles_snapshot()
        ordered = [
            key for key in ("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")
            if key in self._phase6_current_existing_parts()
        ]
        snapshot["existing_parts"] = ordered
        joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
        joint_state["existing_parts"] = list(ordered)
        joint_state["assembly_type"] = snapshot["assembly_type"]
        joint_state = migrate_legacy_snapshot_joints(joint_state)
        self.assembly_joint_state = joint_state
        snapshot["assembly_joint_schema_version"] = joint_state["assembly_joint_schema_version"]
        snapshot["assembly_joints"] = deepcopy(joint_state["assembly_joints"])

        current_tab_key = None
        if hasattr(self, "notebook"):
            try:
                selected = self.root.nametowidget(self.notebook.select())
                current_tab_key = {
                    getattr(self, "tab_z", None): "box_body",
                    getattr(self, "tab_head", None): "head",
                    getattr(self, "tab_tail", None): "tail",
                    getattr(self, "tab_door", None): "door",
                    getattr(self, "tab_base_plate", None): "base_plate",
                }.get(selected)
            except Exception:
                current_tab_key = None
        active = self.workspace_controller.active_part or current_tab_key
        snapshot["active_part"] = active if active in ordered else (ordered[0] if ordered else None)

        snapshot["part_features"] = {
            str(key): list(features or ())
            for key, features in dict(self.surface_features or {}).items()
        }
        if snapshot.get("multi_door_enabled") and snapshot.get("door_layout_columns"):
            formal_door_features = door_layout_feature_map_to_part_features(
                tuple((float(row[0]), tuple(float(v) for v in row[1])) for row in snapshot["door_layout_columns"]),
                getattr(self, "door_layout_features", {}) or {},
            )
            for key, features in formal_door_features.items():
                # Live Fold Designer formal features take precedence when present;
                # otherwise project the canonical main 2D layout store.
                snapshot["part_features"].setdefault(key, list(features))
        snapshot["part_face_features"] = {
            "box_body": {face: list(features) for face, features in self.box_body_face_features.items()}
        }

        w, h, d, t, fw = snapshot["w"], snapshot["h"], snapshot["d"], snapshot["t"], snapshot["fw"]
        door_w = max(1.0, w - (fw + 2.0 * t) * 2.0 - snapshot["door_gap_w"] * 2.0)
        door_h = max(1.0, h - (fw + 2.0 * t) * 2.0 - snapshot["door_gap_h"] * 2.0)
        base_w = max(1.0, w - snapshot["base_plate_shrink_left"] - snapshot["base_plate_shrink_right"])
        base_h = max(1.0, h - snapshot["base_plate_shrink_top"] - snapshot["base_plate_shrink_bottom"])
        try:
            layers = max(1, int(self.indicator_l_var.get()))
            groups = [int(self.indicator_layer_g_vars[i].get()) for i in range(layers)]
            policy = replace(
                manufacturing_api.resolve_policy(),
                frame_width=float(fw),
                door_gap_w=float(snapshot["door_gap_w"]), door_gap_h=float(snapshot["door_gap_h"]),
                indicator_box_fold=float(snapshot["indicator_box_fold"]),
                indicator_small_door_fold=float(snapshot["indicator_door_fold"]),
            )
            indicator_ctx = ManufacturingContext(policy=policy)
            ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
            id_w, id_h = manufacturing_api.indicator_small_door_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
        except Exception:
            groups = [1]
            indicator_ctx = ManufacturingContext()
            ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
            id_w, id_h = manufacturing_api.indicator_small_door_unfolded_size(
                groups, thickness=t, context=indicator_ctx
            )
        snapshot["indicator_layer_groups"] = list(groups)
        try:
            if self.is_door_indicator_var.get():
                _n = max(1, int(self.door_indicator_l_var.get()))
                snapshot["door_indicator_groups"] = [int(self.door_indicator_layer_g_vars[i].get()) for i in range(_n)]
            else:
                snapshot["door_indicator_groups"] = []
        except Exception:
            snapshot["door_indicator_groups"] = []
        snapshot["door_indicator_offset"] = (float(self.door_indicator_offset_x), float(self.door_indicator_offset_y))
        snapshot["door_indicator_box_enabled"] = bool(self.is_indicator_box_var.get())
        snapshot["part_dimensions"] = {
            "box_body": {"width": w, "height": h},
            "head": {"width": w, "height": d},
            "tail": {"width": w, "height": d},
            "door": {"width": door_w, "height": door_h},
            "base_plate": {"width": base_w, "height": base_h},
            "indicator_box": {"width": ib_w, "height": ib_h},
            "indicator_door": {"width": id_w, "height": id_h},
        }
        if committed_profiles:
            snapshot["part_profiles"] = committed_profiles
        return snapshot

    @staticmethod
    def _fold_designer_number_text(value):
        value = float(value)
        nearest_int = round(value)
        if abs(value - nearest_int) <= 1e-9:
            return str(int(nearest_int))
        return str(value)

    def _apply_existing_parts_from_fold_workspace(self, existing_parts):
        """Apply one exact physical-presence set across the whole main-GUI chain."""
        existing = set(str(key) for key in (existing_parts or ()))
        # Box body is the mandatory Fold Chain owner.
        existing.add("box_body")
        existing = self.workspace_controller.apply_authoritative_existing_parts(existing)
        for key, var in (
            ("box_body", self.export_z_var), ("head", self.export_head_var),
            ("tail", self.export_tail_var), ("door", self.export_door_var),
            ("base_plate", self.export_base_plate_var),
        ):
            var.set(key in existing)
        self.is_indicator_box_var.set("indicator_box" in existing)
        # Small indicator door may exist independently of the box in project
        # state; the existing legacy toggle represents the standalone-door mode.
        self.is_door_indicator_var.set("indicator_door" in existing and "indicator_box" not in existing)

        # Main 2D must reflect physical part presence, not only export checkboxes.
        # Indicator box/small-door remain Door auxiliaries and never occupy top
        # level notebook tabs; the four optional top-level parts are hidden and
        # restored transactionally with existing_parts.
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            tab_specs = (
                ("box_body", getattr(self, "tab_z", None), "  箱身 (z)  "),
                ("head", getattr(self, "tab_head", None), "  封頭 (y)  "),
                ("tail", getattr(self, "tab_tail", None), "  封尾 (y)  "),
                ("door", getattr(self, "tab_door", None), "  門 (Door)  "),
                ("base_plate", getattr(self, "tab_base_plate", None), "  底板  "),
            )
            managed_tabs = set(notebook.tabs())
            for key, tab, text in tab_specs:
                if tab is None:
                    continue
                tab_id = str(tab)
                if tab_id not in managed_tabs:
                    if key in existing:
                        notebook.add(tab, text=text)
                        managed_tabs.add(tab_id)
                    continue
                try:
                    state = str(notebook.tab(tab, "state"))
                except Exception:
                    state = "normal"
                if key in existing:
                    if state == "hidden":
                        notebook.add(tab, text=text)
                elif key != "box_body" and state != "hidden":
                    notebook.hide(tab)

        # Left result rows and output selectors must disappear completely for
        # absent parts; clearing a value while leaving an empty row still wastes
        # shop-floor screen space and invites stale export state.
        refresh_presence = getattr(self, "_phase6_refresh_presence_ui", None)
        if callable(refresh_presence):
            refresh_presence(existing)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        if getattr(self, "_manual_corner_part_override", None) not in existing:
            self._manual_corner_part_override = None
        return existing

    def _apply_phase6_project_snapshot(self, snapshot):
        """Restore one all-part .p6fold snapshot into the main GUI state."""
        self._reset_manual_corner_parameter_locks()
        snapshot = deepcopy(dict(snapshot or {}))
        model = normalize_custom_model_name(snapshot.get("model"))
        # Migration for the short-lived split-state build: cabinet_type and
        # model represented the same operator choice. Prefer 受電箱 when that
        # legacy field says receiving, then discard the duplicate state.
        legacy_cabinet_type = str(snapshot.pop("cabinet_type", "") or "").strip()
        if legacy_cabinet_type == "受電箱":
            model = "受電箱"
        snapshot["model"] = model
        if model and self.baseline_var.get().strip() != model:
            self._fold_designer_baseline_commit_guard = True
            try:
                self.baseline_var.set(model)
            finally:
                self._fold_designer_baseline_commit_guard = False

        workspace = dict(snapshot.get("workspace") or {})
        if workspace:
            snapshot.setdefault("box_body_profile", workspace.get("box_body_profile"))
            snapshot.setdefault("existing_parts", workspace.get("existing_parts", ()))
            snapshot.setdefault("active_part", workspace.get("active_part"))
            snapshot.setdefault("part_profiles", workspace.get("part_profiles", {}))

        # Existing Phase6 snapshot restoration owns global dimensions/settings,
        # CornerType and fold profiles. Project-specific state below adds every
        # part's features and indicator workspace that the old snapshot omitted.
        self._apply_original_fold_designer_snapshot(snapshot)

        part_features = dict(snapshot.get("part_features") or {})
        for key in tuple(self.surface_features):
            if str(key).startswith("door_c") and key not in part_features:
                self.surface_features.pop(key, None)
        for key, features in part_features.items():
            self.surface_features[str(key)] = list(features or ())
        if bool(snapshot.get("multi_door_enabled")) and snapshot.get("door_layout_columns"):
            columns = tuple(
                (float(row[0]), tuple(float(v) for v in row[1]))
                for row in tuple(snapshot.get("door_layout_columns") or ())
            )
            self.door_layout_features = door_part_features_to_layout_feature_map(columns, part_features)
        face_features = dict(snapshot.get("part_face_features") or {})
        if "box_body" in face_features:
            self.box_body_face_features = {
                face: list(items or ()) for face, items in dict(face_features["box_body"] or {}).items()
            }

        # Head/tail legacy lists are still used by the main 2D end-cap adapter.
        # Rebuild them from the same restored Feature objects so 2D and 3D agree.
        try:
            width = float(snapshot.get("w", self.w_var.get()))
            depth = float(snapshot.get("d", self.d_var.get()))
            self.head_holes = [
                feature_to_legacy_hole(feature, width, depth)
                for feature in self.surface_features.get("head", ())
            ]
            self.tail_holes = [
                feature_to_legacy_hole(feature, width, depth)
                for feature in self.surface_features.get("tail", ())
            ]
        except Exception:
            pass

        existing = self._apply_existing_parts_from_fold_workspace(
            snapshot.get("existing_parts") or workspace.get("existing_parts") or ()
        )

        groups = list(snapshot.get("indicator_layer_groups") or ())
        if groups:
            count = max(1, min(len(groups), len(self.indicator_layer_g_vars)))
            self.indicator_l_var.set(str(count))
            for i, value in enumerate(groups[:count]):
                self.indicator_layer_g_vars[i].set(str(int(value)))
        box_enabled = "indicator_box" in existing
        self.is_indicator_box_var.set(box_enabled)

        door_groups = list(snapshot.get("door_indicator_groups") or ())
        self.is_door_indicator_var.set("indicator_door" in existing and not box_enabled)
        if door_groups:
            count = max(1, min(len(door_groups), len(self.door_indicator_layer_g_vars)))
            self.door_indicator_l_var.set(str(count))
            for i, value in enumerate(door_groups[:count]):
                self.door_indicator_layer_g_vars[i].set(str(int(value)))
        try:
            ox, oy = snapshot.get("door_indicator_offset", (0.0, 0.0))
            self.door_indicator_offset_x = float(ox)
            self.door_indicator_offset_y = float(oy)
        except Exception:
            self.door_indicator_offset_x = 0.0
            self.door_indicator_offset_y = 0.0

        self.workspace_controller.set_active_part(snapshot.get("active_part") or workspace.get("active_part"))
        self._active_cabinet_type = BoxCalculatorGUI._current_cabinet_type_name(self)
        self._reload_current_baseline_features()
        self.refresh_corner_type_panel()
        self._request_phase6_update("geometry")
        return snapshot

    def _compose_phase6_project_snapshot_from_main_gui(self):
        """從目前主 GUI 狀態建立唯一 canonical committed snapshot。"""
        snapshot = self._make_original_fold_designer_snapshot()
        snapshot.pop("_runtime_project_path", None)
        workspace_state = self.workspace_controller.workspace_snapshot()
        workspace = {
            "box_body_profile": deepcopy(snapshot.get("box_body_profile") or workspace_state.get("box_body_profile") or []),
            "existing_parts": list(workspace_state["existing_parts"]),
            "active_part": workspace_state.get("active_part"),
            "part_profiles": deepcopy(workspace_state["part_profiles"]),
            "endcap_fw": deepcopy(snapshot.get("endcap_fw") or self.endcap_fw_state),
            "endcap_bottom_wrap": deepcopy(snapshot.get("endcap_bottom_wrap") or getattr(self, "endcap_bottom_wrap_state", {})),
            "box_body_structure": deepcopy(workspace_state["box_body_structure"]),
        }
        if "part_features" in workspace_state:
            workspace["part_features"] = deepcopy(workspace_state["part_features"])
        elif "part_features" in snapshot:
            workspace["part_features"] = deepcopy(snapshot["part_features"])
        if "part_face_features" in workspace_state:
            workspace["part_face_features"] = deepcopy(workspace_state["part_face_features"])
        elif "part_face_features" in snapshot:
            workspace["part_face_features"] = deepcopy(snapshot["part_face_features"])
        if "assembly_placements" in workspace_state:
            workspace["assembly_placements"] = deepcopy(workspace_state["assembly_placements"])
        elif "assembly_placements" in snapshot:
            workspace["assembly_placements"] = deepcopy(snapshot["assembly_placements"])
        snapshot["workspace"] = workspace
        if "assembly_placements" in workspace:
            snapshot["assembly_placements"] = deepcopy(workspace["assembly_placements"])
        if "part_features" in workspace:
            snapshot["part_features"] = deepcopy(workspace["part_features"])
        if "part_face_features" in workspace:
            snapshot["part_face_features"] = deepcopy(workspace["part_face_features"])
        return snapshot

    def _capture_phase6_committed_snapshot(self):
        """Compatibility helper；專案交易 ordering 只由 Project Controller 擁有。"""
        return self.project_controller.capture_committed(
            self._compose_phase6_project_snapshot_from_main_gui()
        )

    def save_phase6_project_as(self, *, _active_part_hint=None):
        """把 committed 全專案另存到使用者選擇的 .p6fold 路徑。"""
        model = self.baseline_var.get().strip() or "自訂"
        safe_model = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in model)
        current = self.project_controller.project_path
        initial = Path(current).name if current else f"{safe_model}{PHASE6_PROJECT_EXTENSION}"
        path = filedialog.asksaveasfilename(
            parent=self.root, title="另存新檔：Phase6 專案",
            defaultextension=PHASE6_PROJECT_EXTENSION,
            filetypes=[("Phase6 折彎專案", f"*{PHASE6_PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
            initialfile=initial,
        )
        if not path:
            return None
        self._flush_phase6_authoritative_state()
        try:
            return self.project_controller.save(
                path,
                self._compose_phase6_project_snapshot_from_main_gui,
                active_part_hint=_active_part_hint,
            )
        except Exception as exc:
            messagebox.showerror("存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root)
            return None

    def save_phase6_project(self, *, _active_part_hint=None):
        """儲存到目前專案路徑；尚無路徑時改走另存新檔。"""
        current = self.project_controller.project_path
        if not current:
            return self.save_phase6_project_as(_active_part_hint=_active_part_hint)
        self._flush_phase6_authoritative_state()
        try:
            return self.project_controller.save(
                current,
                self._compose_phase6_project_snapshot_from_main_gui,
                active_part_hint=_active_part_hint,
            )
        except Exception as exc:
            messagebox.showerror("存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root)
            return None

    def open_phase6_project(self):
        """把完整專案載入 committed 主 GUI，不強制開啟 3D。"""
        path = filedialog.askopenfilename(
            parent=self.root, title="開啟專案：Phase6",
            filetypes=[("Phase6 折彎專案", f"*{PHASE6_PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
        )
        if not path:
            return None
        try:
            self.load_phase6_project(path, open_designer=False)
            return str(Path(path))
        except Exception as exc:
            messagebox.showerror("讀檔失敗", f"無法讀取 Phase6 專案：\n{exc}", parent=self.root)
            return None

    def load_phase6_project(self, path, *, open_designer=True):
        """載入 .p6fold 專案，並可選擇進入其保存的 3D 板件。"""
        payload, committed = self.project_controller.load(path)
        snapshot = self._apply_phase6_project_snapshot(committed)
        if not open_designer:
            return payload
        designer = self.open_original_fold_designer()
        active = snapshot.get("active_part") or (snapshot.get("workspace") or {}).get("active_part")
        if active in getattr(designer, "available_parts", ()):
            designer.activate_part(active)
        return designer

    def _apply_original_fold_designer_snapshot(self, snapshot):
        settings = dict(snapshot.get("settings") or {})
        for key in self.settings_service.snapshot():
            if key in snapshot and key not in settings:
                settings[key] = snapshot[key]
        self._apply_fold_designer_live_settings(settings)
        self._apply_manual_corner_snapshot(
            snapshot.get("corner_state"), snapshot.get("corner_pair_same")
        )
        graph_state = migrate_legacy_snapshot_joints(snapshot)
        # Set the preset UI/cache first, then restore the saved Joint Graph.
        # Reversing this order normalizes every saved user edge override back
        # to the preset defaults during load.
        self._set_box_assembly_type(
            resolve_box_assembly_type(snapshot), recalculate=False, notify_designer=False
        )
        self.assembly_joint_state = {
            "assembly_joint_schema_version": graph_state["assembly_joint_schema_version"],
            "assembly_joints": deepcopy(graph_state["assembly_joints"]),
            "existing_parts": list(graph_state.get("existing_parts") or snapshot.get("existing_parts") or []),
            "assembly_type": assembly_intent_value(resolve_box_assembly_type(snapshot)),
        }
        self._apply_endcap_fw_snapshot(snapshot)
        self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state(snapshot)
        self.assembly_relief_state = deepcopy(snapshot.get("assembly_relief") or {})
        self.multi_door_enabled_var.set(bool(snapshot.get("multi_door_enabled", False)))
        layout = list(snapshot.get("door_layout_columns") or ())
        if layout:
            self.set_door_layout_columns([
                (float(row[0]), [float(v) for v in row[1]])
                for row in layout
            ])
        else:
            self.door_layout_columns = []
        self.door_layout_scope = str(snapshot.get("door_layout_scope") or "main")
        self.door_layout_handle_edges = deepcopy(dict(snapshot.get("door_handle_edges") or {}))
        self.receiving_inner_doors = deepcopy(list(snapshot.get("inner_doors") or ()))
        datum = snapshot.get("door_nameplate_center_datum_top")
        self.door_nameplate_center_datum_top = None if datum is None else float(datum)
        ws_source = dict(snapshot.get("workspace") or {})
        self._store_fold_designer_workspace({
            "box_body_profile": snapshot.get("box_body_profile", ws_source.get("box_body_profile")),
            "existing_parts": list(snapshot.get("existing_parts") or ws_source.get("existing_parts") or ()),
            "active_part": snapshot.get("active_part") or ws_source.get("active_part"),
            "part_profiles": snapshot.get("part_profiles") or ws_source.get("part_profiles", {}),
            "endcap_fw": snapshot.get("endcap_fw") or ws_source.get("endcap_fw", {}),
            "box_body_structure": ws_source.get("box_body_structure", snapshot.get("box_body_structure")),
            "assembly_placements": snapshot.get("assembly_placements") or ws_source.get("assembly_placements", {}),
            "part_features": snapshot.get("part_features") or ws_source.get("part_features", {}),
            "part_face_features": snapshot.get("part_face_features") or ws_source.get("part_face_features", {}),
        })
        self._sync_fold_designer_manual_corner_context(snapshot.get("active_part"))
        self._reload_current_baseline_features()
        self._request_phase6_update("geometry")

    def _store_fold_designer_workspace(self, workspace):
        if not workspace:
            return
        profile = workspace.get("box_body_profile")
        existing = list(workspace.get("existing_parts", ()))
        if workspace.get("endcap_fw") is not None:
            self._apply_endcap_fw_snapshot({"fw": float(self.fw_z_var.get()), "endcap_fw": workspace.get("endcap_fw")})
        part_profiles = deepcopy(dict(workspace.get("part_profiles", {}) or {}))
        # Head/tail mating topology is derived data. Project files may contain
        # diagnostic copies from an older box Fold Chain; never let those stale
        # copies become authoritative in the main 2D renderer after load/commit.
        if profile:
            linked_snapshot = self._collect_main_setting_values()
            model_var = getattr(self, "baseline_var", None)
            linked_snapshot["model"] = str(
                model_var.get() if model_var is not None else linked_snapshot.get("model", "")
            ).strip()
            current_assembly = getattr(self, "_current_box_assembly_type", None)
            assembly_type = current_assembly() if callable(current_assembly) else CornerTypeId.INSERT_OVERLAY
            linked_snapshot["assembly_type"] = assembly_intent_value(assembly_type)
            serialize_corners = getattr(self, "_serialize_manual_corner_state", None)
            if callable(serialize_corners):
                linked_snapshot["corner_state"] = serialize_corners()
            pair_same = getattr(self, "manual_corner_pair_same", None)
            if pair_same is not None:
                linked_snapshot["corner_pair_same"] = deepcopy(pair_same)
            fw_state = getattr(self, "endcap_fw_state", None)
            if fw_state is None:
                fw_state = normalize_endcap_fw_state({
                    "fw": linked_snapshot.get("fw", 25),
                    "endcap_fw": workspace.get("endcap_fw", {}),
                })
                self.endcap_fw_state = fw_state
            linked_snapshot["endcap_fw"] = deepcopy(fw_state)
            linked = build_linked_endcap_xy_profiles(linked_snapshot, profile)
            for key in ("head", "tail"):
                if key in existing:
                    part_profiles[key] = linked[key]
        committed_workspace = {
            "existing_parts": existing,
            "active_part": workspace.get("active_part"),
            "part_profiles": part_profiles,
            "box_body_structure": workspace.get("box_body_structure", self.workspace_controller.box_body_structure_state()),
        }
        if "box_body_profile" in workspace:
            committed_workspace["box_body_profile"] = (
                None if profile is None else [dict(seg) for seg in profile]
            )
        if "part_features" in workspace:
            committed_workspace["part_features"] = deepcopy(workspace["part_features"])
        if "part_face_features" in workspace:
            committed_workspace["part_face_features"] = deepcopy(workspace["part_face_features"])
        if "assembly_placements" in workspace:
            committed_workspace["assembly_placements"] = deepcopy(workspace["assembly_placements"])
        self.workspace_controller.commit_workspace(committed_workspace)

    def _apply_fold_designer_live_snapshot(self, payload):
        """Immediately merge Fold Designer state into the one canonical project state."""
        if getattr(self, "_fold_designer_live_sync_guard", False):
            return False
        payload = dict(payload or {})
        origin = str(payload.get("origin") or "")
        if origin == "main_gui":
            return False
        revision = 0
        if origin == "fold_designer":
            try:
                revision = int(payload.get("revision", 0) or 0)
            except (TypeError, ValueError):
                return False
            if revision <= int(getattr(self, "_phase6_last_fold_designer_revision", 0) or 0):
                return False
            fingerprint = str(payload.get("fingerprint") or "")
            if fingerprint and fingerprint == getattr(self, "_phase6_last_fold_designer_fingerprint", None):
                self._phase6_last_fold_designer_revision = revision
                return False
        self._fold_designer_live_sync_guard = True
        try:
            model = normalize_custom_model_name(payload.get("model"))
            baseline_changed = self.baseline_var.get().strip() != model
            if baseline_changed:
                self._fold_designer_baseline_commit_guard = True
                try:
                    self.baseline_var.set(model)
                finally:
                    self._fold_designer_baseline_commit_guard = False

            settings = dict(payload.get("settings") or {})
            if settings:
                self._apply_fold_designer_live_settings(settings, recalculate=False)

            self._apply_manual_corner_snapshot(
                payload.get("corner_state"), payload.get("corner_pair_same")
            )
            graph_state = migrate_legacy_snapshot_joints(payload)
            # Update the preset selector/cache first. _set_box_assembly_type()
            # intentionally synchronizes preset defaults, so applying it after a
            # live user-edited Joint Graph would erase Head/Tail edge overrides.
            self._set_box_assembly_type(
                resolve_box_assembly_type(payload), recalculate=False, notify_designer=False,
            )
            self.assembly_joint_state = {
                "assembly_joint_schema_version": graph_state["assembly_joint_schema_version"],
                "assembly_joints": deepcopy(graph_state["assembly_joints"]),
                "existing_parts": list(
                    graph_state.get("existing_parts")
                    or payload.get("existing_parts")
                    or self._phase6_current_existing_parts()
                ),
                "assembly_type": assembly_intent_value(resolve_box_assembly_type(payload)),
            }
            self._apply_endcap_fw_snapshot(payload)
            self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state(payload)
            self.assembly_relief_state = deepcopy(payload.get("assembly_relief") or {})
            workspace = payload.get("workspace")
            if workspace:
                self._store_fold_designer_workspace(workspace)
                self._apply_existing_parts_from_fold_workspace(workspace.get("existing_parts", ()))
                part_features = dict(workspace.get("part_features") or payload.get("part_features") or {})
                for key, features in part_features.items():
                    self.surface_features[str(key)] = list(features or ())
                try:
                    width = float(payload.get("w", self.w_var.get()))
                    depth = float(payload.get("d", self.d_var.get()))
                    if "head" in self.surface_features:
                        self.head_holes = [
                            feature_to_legacy_hole(feature, width, depth)
                            for feature in self.surface_features.get("head", ())
                        ]
                    if "tail" in self.surface_features:
                        self.tail_holes = [
                            feature_to_legacy_hole(feature, width, depth)
                            for feature in self.surface_features.get("tail", ())
                        ]
                except Exception:
                    pass
                face_features = dict(workspace.get("part_face_features") or payload.get("part_face_features") or {})
                if "box_body" in face_features:
                    self.box_body_face_features = {
                        face: list(items or ()) for face, items in dict(face_features["box_body"] or {}).items()
                    }
                raw_columns = (
                    payload.get("door_layout_columns")
                    or dict(payload.get("settings") or {}).get("door_layout_columns")
                )
                if raw_columns:
                    setter = getattr(self, "set_door_layout_columns", None)
                    if callable(setter):
                        setter([
                            (float(row[0]), [float(v) for v in row[1]])
                            for row in raw_columns
                        ])
                    else:
                        self.door_layout_columns = [
                            (float(row[0]), [float(v) for v in row[1]])
                            for row in raw_columns
                        ]
                else:
                    getter = getattr(self, "get_door_layout_columns", None)
                    raw_columns = getter() if callable(getter) else ()
                columns = tuple(
                    (float(row[0]), tuple(float(v) for v in row[1]))
                    for row in tuple(raw_columns or ())
                )
                if columns and part_features:
                    self.door_layout_features = door_part_features_to_layout_feature_map(columns, part_features)
                if "multi_door_enabled" in payload:
                    var = getattr(self, "multi_door_enabled_var", None)
                    if var is not None:
                        var.set(bool(payload.get("multi_door_enabled", False)))
                if "door_layout_scope" in payload:
                    self.door_layout_scope = str(payload.get("door_layout_scope") or "main")
                if "door_handle_edges" in payload:
                    self.door_layout_handle_edges = deepcopy(dict(payload.get("door_handle_edges") or {}))
                if "inner_doors" in payload:
                    self.receiving_inner_doors = deepcopy(list(payload.get("inner_doors") or ()))
            self._sync_fold_designer_manual_corner_context(payload.get("active_part"))
            if baseline_changed:
                self._reload_current_baseline_features()
            self.refresh_corner_type_panel()
            scheduler = self._phase6_update_scheduler
            scheduler.mark_dirty("designer_live_snapshot")
            self.project_controller.capture_committed(
                self._compose_phase6_project_snapshot_from_main_gui()
            )
            if origin == "fold_designer":
                self._phase6_last_fold_designer_revision = revision
                self._phase6_last_fold_designer_fingerprint = str(payload.get("fingerprint") or "")
            return True
        finally:
            self._fold_designer_live_sync_guard = False

    def _apply_fold_designer_corner_transaction(self, payload):
        """Legacy compatibility for older callers; no rollback semantics remain."""
        applied = self._apply_fold_designer_live_snapshot(payload)
        if applied:
            self.project_controller.confirm_designer(
                self._compose_phase6_project_snapshot_from_main_gui()
            )
        return applied

    def _reload_current_baseline_features(self):
        """Invalidate derived baseline scenes without restoring baseline defaults.

        Fold-designer edits are authoritative.  Clearing these caches forces the
        currently selected baseline DXF features to be re-read/re-stretched on
        the next redraw while preserving the edited Phase6 dimensions/folds.
        """
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("baseline")
        else:
            # Compatibility for lightweight/headless consumers constructed via
            # __new__: clear any legacy cache dictionaries in place without
            # creating a second cache owner.
            for name in (
                "_door_layout_baseline_cache",
                "_box_body_baseline_face_cache",
                "_authoritative_part_render_cache",
            ):
                cache = getattr(self, name, None)
                if isinstance(cache, dict):
                    cache.clear()

    def open_original_fold_designer(self):
        if self.fold_designer_window is not None:
            try:
                if self.fold_designer_window.winfo_exists():
                    self.fold_designer_window.deiconify()
                    self.fold_designer_window.lift()
                    return self.fold_designer_app
            except tk.TclError:
                pass

        # Live-canonical mode: opening 3D does not start a rollback-capable draft.
        designer_snapshot = self._compose_phase6_project_snapshot_from_main_gui()
        self.project_controller.capture_committed(designer_snapshot)
        designer_snapshot["_runtime_project_path"] = self.project_controller.project_path
        # Runtime-only known-family presets.  These are deliberately injected
        # after composing/capturing the project snapshot so they can guide an
        # explicit model switch inside 3D without becoming project-file state.
        # At present Vault is the baseline-backed known family; Receiving is
        # derived from that immutable preset by cabinet_family_policy.
        designer_snapshot["_runtime_family_presets"] = {
            "金庫型": deepcopy(
                dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
                or {}
            )
        }

        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.grab_set()
        designer = None

        def destroy_designer_window():
            try:
                try:
                    window.destroy()
                except tk.TclError:
                    # FigureCanvasTkAgg can leave a Python-side Tcl command
                    # already deleted after a loaded-project rebuild.  The
                    # widget tree is still safe to destroy at Tcl level; do
                    # not let that bookkeeping error block returning to 2D.
                    try:
                        window.tk.call("destroy", window._w)
                    except tk.TclError:
                        pass
                    try:
                        if window.master is not None:
                            window.master.children.pop(window._name, None)
                    except Exception:
                        pass
            finally:
                self.fold_designer_window = None
                self.fold_designer_app = None

        def close_designer():
            # No cancel semantics. Flush the visible editor once, publish, close.
            if designer is not None:
                try:
                    designer.flush_pending_settings()
                except Exception:
                    pass
                try:
                    if getattr(designer, "active_part_key", None) is not None:
                        designer._save_current_part(notify=False)
                except Exception:
                    pass
                try:
                    designer._phase6_publish_live_state(force=True)
                except Exception:
                    pass
            destroy_designer_window()

        def load_project_from_designer(path):
            destroy_designer_window()
            return self.load_phase6_project(path, open_designer=True)

        def save_project_from_designer(*, save_as=False, active_part=None):
            if save_as:
                return self.save_phase6_project_as(_active_part_hint=active_part)
            return self.save_phase6_project(_active_part_hint=active_part)

        def project_path_changed(path):
            if path:
                self.project_controller.set_project_path(path)

        def return_to_2d_corner(part_key):
            self._flush_phase6_authoritative_state()
            key = str(part_key or "box_body")
            destroy_designer_window()
            tab_map = {
                "box_body": getattr(self, "tab_z", None),
                "head": getattr(self, "tab_head", None),
                "tail": getattr(self, "tab_tail", None),
                "door": getattr(self, "tab_door", None),
                "base_plate": getattr(self, "tab_base_plate", None),
                # Indicator sheets are edited from the Door workflow.
                "indicator_box": getattr(self, "tab_door", None),
                "indicator_door": getattr(self, "tab_door", None),
            }
            target = tab_map.get(key) or getattr(self, "tab_z", None)
            try:
                if target is not None:
                    self.notebook.select(target)
                self.refresh_corner_type_panel()
                self.draw_preview()
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except tk.TclError:
                pass
            return True

        designer = Phase6FoldDesignerApp(
            window, designer_snapshot,
            on_settings_change=None,
            on_save_defaults=self._save_fold_designer_defaults,
            on_corner_change=None,
            on_live_sync=lambda payload: self._apply_fold_designer_live_snapshot(deepcopy(payload)),
            on_baseline_data_query=self._query_fold_designer_baseline_data,
            on_scene_query=self._query_fold_designer_render_data,
            on_ui_text_size_change=lambda value: self._apply_ui_text_size_preference(
                value, persist=True, notify_designer=False
            ),
            on_project_load=load_project_from_designer,
            on_project_path_change=project_path_changed,
            on_project_save=save_project_from_designer,
            on_return_2d=return_to_2d_corner,
        )
        self.fold_designer_window = window
        self.fold_designer_app = designer
        window.protocol("WM_DELETE_WINDOW", close_designer)
        return designer

    def _apply_ui_text_size_preference(self, value, *, persist=True, notify_designer=True):
        key = normalize_ui_text_size(value)
        self.settings_service.update({"ui_text_size": key})
        self._ui_text_controller.apply(key)
        self.setup_styles()
        if hasattr(self, "ui_text_size_var"):
            label = ui_text_size_label(key)
            if self.ui_text_size_var.get() != label:
                self.ui_text_size_var.set(label)
        paned = getattr(self, "main_paned", None)
        left = getattr(self, "left_container", None)
        if paned is not None and left is not None:
            base_width = 320
            factor = ui_text_size_factor(key)
            scaled_width = int(round(base_width * factor))
            try:
                paned.paneconfig(left, width=scaled_width)
            except Exception:
                pass
        if persist:
            self.settings_service.persist_defaults(keys=("ui_text_size",))
        if notify_designer:
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None and hasattr(designer, "apply_external_settings"):
                try:
                    designer.apply_external_settings({"ui_text_size": key})
                except tk.TclError:
                    pass
        try:
            self.draw_preview()
        except Exception:
            pass
        return key

    def on_ui_text_size_changed(self, event=None):
        return self._apply_ui_text_size_preference(self.ui_text_size_var.get())

    def _current_box_assembly_type(self):
        # Persisted UI mirror / Joint Graph owns the assembly intent.  Top
        # CornerType is only a legacy fallback for data that predates the graph.
        var = getattr(self, "box_assembly_type_var", None)
        if var is not None:
            try:
                label = str(var.get() or "").strip()
                if label in ASSEMBLY_LABEL_TO_TYPE:
                    return ASSEMBLY_LABEL_TO_TYPE[label]
            except Exception:
                pass
        state = getattr(self, "assembly_joint_state", None)
        if isinstance(state, dict):
            raw = state.get("assembly_type")
            if raw:
                try:
                    stable = assembly_intent_value(raw)
                    return CornerTypeId(stable) if stable != "WRAP_OVERLAY" else stable
                except Exception:
                    pass
        corner_state = getattr(self, "manual_corner_state", None)
        if corner_state:
            try:
                return assembly_type_from_corner_state(corner_state)
            except Exception:
                pass
        return CornerTypeId.INSERT_OVERLAY

    def _set_box_assembly_type(
        self, type_id, *, recalculate=True, notify_designer=True,
        reset_bottom_defaults=False,
    ):
        stable = assembly_intent_value(type_id)
        try:
            parts = tuple(self._phase6_current_existing_parts())
        except Exception:
            parts = ("box_body", "head", "tail")
        state = dict(getattr(self, "assembly_joint_state", {}) or {})
        state.setdefault("existing_parts", list(parts))
        state["existing_parts"] = list(parts)
        if not state.get("assembly_joint_schema_version"):
            state["assembly_type"] = stable
            state = migrate_legacy_snapshot_joints(state)
        state = sync_snapshot_intent_joints(state, stable)
        self.assembly_joint_state = state
        label = assembly_intent_label(stable)
        if self.box_assembly_type_var.get() != label:
            self.box_assembly_type_var.set(label)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self.refresh_corner_type_panel()
        if notify_designer:
            designer = getattr(self, "fold_designer_app", None)
            if designer is not None and getattr(designer, "_transaction_confirm_callback", None) is None:
                try:
                    designer.apply_external_assembly_type(stable)
                except Exception:
                    pass
        if recalculate:
            self._request_phase6_update("geometry")
        return CornerTypeId(stable) if stable != "WRAP_OVERLAY" else stable

    def on_box_assembly_changed(self, event=None):
        if not is_unknown_model(self.baseline_var.get()):
            return
        type_id = self._current_box_assembly_type()
        self._set_box_assembly_type(type_id, reset_bottom_defaults=False)

    def _effective_endcap_fw(self, part_key, box_fw=None):
        if box_fw is None:
            fw_var = getattr(self, "fw_z_var", None)
            if fw_var is not None:
                box_fw = float(fw_var.get())
            else:
                box_fw = float(self.settings_service.snapshot().get("fw", 25.0))
        state = getattr(self, "endcap_fw_state", None)
        if state is None:
            return float(box_fw)
        snapshot = {"fw": float(box_fw), "endcap_fw": state}
        return float(resolve_endcap_fw(snapshot, part_key, state=state))

    def _sync_endcap_fw_controls(self):
        box_fw = float(self.fw_z_var.get())
        for part, var, follow_var, combo in (
            ("head", self.fw_head_var, self.fw_head_follow_var, getattr(self, "cb_fw_head", None)),
            ("tail", self.fw_tail_var, self.fw_tail_follow_var, getattr(self, "cb_fw_tail", None)),
        ):
            state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
            follow = bool(state.get("follow_box", True))
            follow_var.set(follow)
            value = box_fw if follow else float(state.get("value", box_fw))
            text = self._fold_designer_number_text(value)
            if var.get() != text:
                var.set(text)
            if combo is not None:
                combo.configure(state="normal")

    def _apply_endcap_fw_snapshot(self, snapshot):
        state = normalize_endcap_fw_state(snapshot)
        self.endcap_fw_state = state
        self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return state

    def on_endcap_fw_follow_changed(self, part_key):
        box_fw = float(self.fw_z_var.get())
        follow_var = self.fw_head_follow_var if part_key == "head" else self.fw_tail_follow_var
        set_endcap_fw_follow(self.endcap_fw_state, part_key, bool(follow_var.get()), box_fw=box_fw)
        self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self._request_phase6_update("geometry")

    def on_fw_selected(self, source):
        if source == "z":
            # Explicit operator input on the box always retakes Head + Tail,
            # even when the numeric value is the same as before.
            commit_box_fw(self.endcap_fw_state, float(self.fw_z_var.get()))
            self._sync_endcap_fw_controls()
        elif source in {"head", "tail"}:
            var = self.fw_head_var if source == "head" else self.fw_tail_var
            try:
                value = float(var.get())
            except (TypeError, ValueError, tk.TclError):
                # The EndCap FW controls are intentionally free numeric inputs.
                # Invalid transient text must not corrupt control ownership.
                self._sync_endcap_fw_controls()
                return
            commit_endcap_fw(
                self.endcap_fw_state, source, value,
                box_fw=float(self.fw_z_var.get()),
            )
            self._sync_endcap_fw_controls()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        self._request_phase6_update("geometry")

    def _baseline_source_model(self):
        baseline_var = getattr(self, "baseline_var", None)
        if baseline_var is None or not hasattr(baseline_var, "get"):
            return None
        value = str(baseline_var.get() or "").strip()
        if not value or is_unknown_model(value):
            return None
        return value

    def _door_material_frame_width(self, frame_width, thickness, *, model_name=None):
        """Resolve operator Door FW into the material-space value consumed by AE."""
        source = self._baseline_source_model() if model_name is None else model_name
        return cabinet_family_policy.door_material_frame_width(
            source, frame_width=float(frame_width), thickness=float(thickness),
        )

    def _sync_fold_designer_manual_corner_context(self, active_part):
        key = str(active_part or "")
        if key in {"indicator_box", "indicator_door"} and key in self.manual_corner_state:
            self._manual_corner_part_override = key
        else:
            self._manual_corner_part_override = None
        self.refresh_corner_type_panel()

    def _current_manual_corner_part_key(self):
        override = getattr(self, '_manual_corner_part_override', None)
        if override in getattr(self, 'manual_corner_state', {}):
            return override
        if not hasattr(self, 'notebook'):
            return None
        try:
            selected = self.root.nametowidget(self.notebook.select())
        except Exception:
            return None
        mapping = {
            getattr(self, 'tab_head', None): 'head',
            getattr(self, 'tab_tail', None): 'tail',
            getattr(self, 'tab_door', None): 'door',
            getattr(self, 'tab_base_plate', None): 'base_plate',
            getattr(self, 'tab_indicator_box', None): 'indicator_box',
            getattr(self, 'tab_indicator_door', None): 'indicator_door',
        }
        return mapping.get(selected)

    def _manual_corner_policy(self, part_key, fw):
        state_map = getattr(self, "manual_corner_state", None)
        if isinstance(state_map, dict) and part_key in state_map:
            policy = policy_from_corner_state(state_map[part_key], fw=fw)
            family_adapter = getattr(self, "_apply_cabinet_family_endcap_policy", None)
            if callable(family_adapter):
                return family_adapter(policy, part_key)
            return policy

        # Geometry/spec helpers are also used by lightweight tests and legacy
        # callers that do not construct the full Tk state.  Preserve the same
        # model semantics instead of crashing or silently dropping CornerType.
        model_name = self._baseline_source_model() if hasattr(self, "_baseline_source_model") else None
        if model_name:
            fallback = known_model_corner_state((part_key,), cabinet_family=BoxCalculatorGUI._current_cabinet_type_name(self)).get(part_key)
        else:
            fallback = new_manual_corner_state((part_key,)).get(part_key)
        if fallback is None:
            return None
        return policy_from_corner_state(fallback, fw=fw)

    def _box_body_corner_policies(self, fw):
        """One shared CornerType state for custom and known models alike."""
        if hasattr(self, "fw_z_var") and hasattr(self, "endcap_fw_state"):
            head_fw = self._effective_endcap_fw("head", fw)
            tail_fw = self._effective_endcap_fw("tail", fw)
        else:
            # Keep this geometry helper independently usable by tests/legacy
            # callers that do not construct the full Tk FW-link state.
            head_fw = tail_fw = float(fw)
        return (
            self._manual_corner_policy("head", head_fw),
            self._manual_corner_policy("tail", tail_fw),
        )

    def _box_body_finished_height(self, val):
        """Return the single folded box-body outside height from shared assembly semantics."""
        h = float(val['h'])
        t = float(val['t'])
        head_policy, tail_policy = self._box_body_corner_policies(float(val['fw']))
        if head_policy is None or tail_policy is None:
            return h - 2.0 * t
        bottom_outer, top_outer = box_body_vertical_offsets(
            t, head_corner_policy=head_policy, tail_corner_policy=tail_policy
        )
        result = h - bottom_outer - top_outer
        if result <= 0:
            raise ValueError("箱身折後包外高度必須大於 0")
        return float(result)

    _CORNER_MODE_LABELS = {
        CrossCornerMode.STANDARD: "標準",
        CrossCornerMode.RETAIN: "單邊留肉",
        CrossCornerMode.EXTRA_CUT: "多切",
    }
    _CORNER_MODE_BY_LABEL = {value: key for key, value in _CORNER_MODE_LABELS.items()}
    _CORNER_DIRECTION_LABELS = {
        CornerDirection.WIDTH: "寬",
        CornerDirection.HEIGHT: "高",
        CornerDirection.BOTH: "寬＋高",
    }
    _CORNER_DIRECTION_BY_LABEL = {value: key for key, value in _CORNER_DIRECTION_LABELS.items()}
    _FIXED_CORNER_SUMMARIES = {
        "door": "十字截角｜單邊留肉 1T",
        "base_plate": "十字截角｜標準",
        "indicator_box": "十字截角｜單邊留肉 1T（固定）",
        "indicator_door": "十字截角｜單邊留肉 1T（固定）",
        "head": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n下方：十字截角｜多切 0.5T（寬＋高）",
        "tail": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n下方：十字截角｜多切 0.5T（寬＋高）",
    }

    def _fixed_corner_summary(self, part_key):
        if BoxCalculatorGUI._current_cabinet_type_name(self) == "受電箱" and part_key in {"head", "tail"}:
            from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part

            joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
            bottom_relation = edge_relation_for_part(joint_state, part_key, "BOTTOM")
            if bottom_relation is AssemblyJointRelation.WRAP:
                bottom_summary = "下方：包覆貼外（BOTTOM＝WRAP；FW 基準＝側板後折＋1T）"
            elif bottom_relation is AssemblyJointRelation.INSERT:
                bottom_summary = "下方：標準截角（BOTTOM＝嵌入；WRAP 關閉）"
            elif bottom_relation is None:
                bottom_summary = "下方：標準截角（BOTTOM Joint 未定義）"
            else:
                bottom_summary = f"下方：標準截角（BOTTOM＝{bottom_relation.value}）"
            return (
                "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）\n"
                + bottom_summary
            )
        return self._FIXED_CORNER_SUMMARIES.get(part_key, "目前板件使用固定截角規則")

    def _corner_part_type_editable(self, part_key):
        # CornerType 本身只在自訂盤型開放切換；已知盤型保留基準類型。
        return (
            is_unknown_model(self.baseline_var.get())
            and part_key in self.manual_corner_state
            and part_key not in {"indicator_box", "indicator_door"}
        )

    def _corner_part_editable(self, part_key):
        # Backwards-compatible meaning: type selection editable.
        return self._corner_part_type_editable(part_key)

    def _corner_part_parameters_unlockable(self, part_key):
        # 已知盤型也允許在明確解鎖後微調既有類型的細部參數；固定共享板件除外。
        return (
            part_key in self.manual_corner_state
            and part_key not in {"indicator_box", "indicator_door"}
        )

    def _manual_corner_parameters_unlocked(self, part_key):
        return bool(getattr(self, "_manual_corner_param_unlocked", {}).get(str(part_key), False))

    def _manual_corner_parameters_editable(self, part_key):
        return self._corner_part_parameters_unlockable(part_key) and self._manual_corner_parameters_unlocked(part_key)

    def _reset_manual_corner_parameter_locks(self):
        self._manual_corner_param_unlocked = {}

    def toggle_manual_corner_parameter_lock(self):
        part_key = self._current_manual_corner_part_key()
        if not self._corner_part_parameters_unlockable(part_key):
            return
        state = getattr(self, "_manual_corner_param_unlocked", None)
        if not isinstance(state, dict):
            state = {}
            self._manual_corner_param_unlocked = state
        state[part_key] = not bool(state.get(part_key, False))
        self.refresh_corner_type_panel()

    @classmethod
    def _corner_parameter_summary(cls, selection):
        selection = normalize_corner_selection(selection)
        if selection.type_id is CornerTypeId.CROSS:
            mode = cls._CORNER_MODE_LABELS[selection.cross_mode]
            if selection.cross_mode is CrossCornerMode.STANDARD:
                return mode
            direction = cls._CORNER_DIRECTION_LABELS[selection.direction]
            return f"{mode}｜{direction}｜{cls._corner_number_text(selection.amount_t)}T"
        if selection.type_id is CornerTypeId.OVERLAY:
            return f"留肉（高）｜{cls._corner_number_text(selection.amount_t)}T"
        if selection.type_id is CornerTypeId.INSERT:
            return f"多切（高）｜{cls._corner_number_text(selection.amount_t)}T"
        return (
            f"貼外留肉 {cls._corner_number_text(selection.amount_t)}T｜"
            f"嵌入留肉 {cls._corner_number_text(selection.secondary_retain_t)}T｜"
            f"深度 {cls._corner_number_text(selection.secondary_depth_t)}T"
        )

    def create_corner_type_panel(self, parent):
        panel = tk.Frame(parent, bg=self.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
        self.corner_type_panel = panel

        title_row = tk.Frame(panel, bg=self.COLOR_INPUT_BG)
        title_row.pack(fill=tk.X, padx=8, pady=(8, 4))
        self.manual_corner_title_label = tk.Label(
            title_row, text="截角類型", bg=self.COLOR_INPUT_BG,
            fg=self.COLOR_ACCENT, font=('Microsoft JhengHei', 10, 'bold')
        )
        self.manual_corner_title_label.pack(side=tk.LEFT)
        self.manual_corner_param_lock_button = tk.Button(
            title_row, text="🔒 參數鎖定", command=self.toggle_manual_corner_parameter_lock,
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, bd=0, cursor="hand2",
            activebackground=self.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
            font=('Microsoft JhengHei', 9, 'bold'), padx=6, pady=1,
        )
        self.manual_corner_part_label = tk.Label(
            title_row, text="", bg=self.COLOR_INPUT_BG,
            fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9)
        )
        self.manual_corner_part_label.pack(side=tk.RIGHT)

        self.manual_corner_fixed_summary = tk.Label(
            panel, text="", justify=tk.LEFT, anchor=tk.W,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
            font=('Microsoft JhengHei', 9), wraplength=520,
        )

        self.manual_corner_editor_frame = tk.Frame(panel, bg=self.COLOR_INPUT_BG)
        editor = self.manual_corner_editor_frame

        # 預設以上方／下方成對編輯；只有取消「左右相同」才拆成左右兩個角。
        self.manual_corner_pair_buttons = {}
        self.manual_corner_pair_same_checkbuttons = {}
        for pair_key, pair_label, same_var in (
            ('top', '上方截角', self.manual_top_same_var),
            ('bottom', '下方截角', self.manual_bottom_same_var),
        ):
            pair_row = tk.Frame(editor, bg=self.COLOR_INPUT_BG)
            pair_row.pack(fill=tk.X, padx=8, pady=3)
            tk.Label(
                pair_row, text=pair_label, width=8, anchor=tk.W,
                bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                font=('Microsoft JhengHei', 9, 'bold'),
            ).pack(side=tk.LEFT)
            same_cb = tk.Checkbutton(
                pair_row, text='左右相同', variable=same_var,
                bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                activebackground=self.COLOR_INPUT_BG, activeforeground=self.COLOR_TEXT,
                selectcolor=self.COLOR_PANEL,
                command=lambda p=pair_key: self.on_manual_corner_pair_same_changed(p),
            )
            same_cb.pack(side=tk.LEFT, padx=(2, 8))
            self.manual_corner_pair_same_checkbuttons[pair_key] = same_cb
            button_frame = tk.Frame(pair_row, bg=self.COLOR_INPUT_BG)
            button_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            left_key, right_key = CORNER_PAIR_CORNERS[pair_key]
            pair_button = tk.Button(
                button_frame, text=('上方' if pair_key == 'top' else '下方'),
                bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, bd=0,
                activebackground=self.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
                command=lambda p=pair_key: self.select_manual_corner(p),
            )
            left_button = tk.Button(
                button_frame, text=CORNER_LABELS[left_key],
                bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, bd=0,
                activebackground=self.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
                command=lambda k=left_key: self.select_manual_corner(k),
            )
            right_button = tk.Button(
                button_frame, text=CORNER_LABELS[right_key],
                bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, bd=0,
                activebackground=self.COLOR_ACCENT_HOVER, activeforeground='#ffffff',
                command=lambda k=right_key: self.select_manual_corner(k),
            )
            self.manual_corner_pair_buttons[pair_key] = {
                'frame': button_frame, 'pair': pair_button,
                'left': left_button, 'right': right_button,
            }

        type_frame = tk.Frame(editor, bg=self.COLOR_INPUT_BG)
        type_frame.pack(fill=tk.X, padx=8, pady=(5, 2))
        self.manual_corner_type_frame = type_frame
        self.corner_type_small_canvases = {}
        self.manual_corner_type_buttons = {}
        for type_id in EDITABLE_CORNER_TYPE_IDS:
            row = tk.Frame(type_frame, bg=self.COLOR_INPUT_BG)
            row.pack(fill=tk.X, pady=2)
            icon = tk.Canvas(
                row, width=54, height=40, bg=self.COLOR_CANVAS_BG,
                highlightthickness=1, highlightbackground='#34343a'
            )
            icon.pack(side=tk.LEFT, padx=(0, 6))
            icon.bind('<Button-1>', lambda e, tid=type_id: self.set_manual_corner_type(tid))
            self.corner_type_small_canvases[type_id] = icon
            rb = tk.Radiobutton(
                row,
                text=CORNER_TYPE_LABELS[type_id],
                variable=self.manual_corner_type_var,
                value=type_id.value,
                command=lambda tid=type_id: self.set_manual_corner_type(tid),
                bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                activebackground=self.COLOR_INPUT_BG, activeforeground=self.COLOR_TEXT,
                selectcolor=self.COLOR_PANEL, anchor=tk.W,
            )
            rb.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.manual_corner_type_buttons[type_id] = rb

        self.manual_corner_param_summary = tk.Label(
            editor, text="", justify=tk.LEFT, anchor=tk.W,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 9), wraplength=520,
        )

        self.manual_corner_param_frame = tk.Frame(editor, bg=self.COLOR_INPUT_BG)

        self.manual_corner_mode_row = tk.Frame(self.manual_corner_param_frame, bg=self.COLOR_INPUT_BG)
        tk.Label(self.manual_corner_mode_row, text="方式 :", width=12, anchor=tk.W,
                 bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT).pack(side=tk.LEFT)
        self.manual_corner_mode_cb = ttk.Combobox(
            self.manual_corner_mode_row, textvariable=self.manual_corner_cross_mode_var,
            values=['標準', '單邊留肉', '多切'], width=12, state='readonly', style='TCombobox'
        )
        self.manual_corner_mode_cb.pack(side=tk.LEFT, padx=4)
        self.manual_corner_mode_cb.bind('<<ComboboxSelected>>', self.on_manual_corner_mode_changed)

        self.manual_corner_direction_row = tk.Frame(self.manual_corner_param_frame, bg=self.COLOR_INPUT_BG)
        self.manual_corner_direction_label = tk.Label(
            self.manual_corner_direction_row, text="方向 :", width=12, anchor=tk.W,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT
        )
        self.manual_corner_direction_label.pack(side=tk.LEFT)
        self.manual_corner_direction_cb = ttk.Combobox(
            self.manual_corner_direction_row, textvariable=self.manual_corner_direction_var,
            width=12, state='readonly', style='TCombobox'
        )
        self.manual_corner_direction_cb.pack(side=tk.LEFT, padx=4)
        self.manual_corner_direction_cb.bind('<<ComboboxSelected>>', self.on_manual_corner_parameter_changed)

        self.manual_corner_amount_row = tk.Frame(self.manual_corner_param_frame, bg=self.COLOR_INPUT_BG)
        self.manual_corner_amount_label = tk.Label(
            self.manual_corner_amount_row, text="數值 :", width=12, anchor=tk.W,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT
        )
        self.manual_corner_amount_label.pack(side=tk.LEFT)
        self.manual_corner_amount_entry = ttk.Entry(
            self.manual_corner_amount_row, textvariable=self.manual_corner_amount_var,
            width=8, justify=tk.CENTER
        )
        self.manual_corner_amount_entry.pack(side=tk.LEFT, padx=4)
        tk.Label(self.manual_corner_amount_row, text="T", bg=self.COLOR_INPUT_BG,
                 fg=self.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        self.manual_corner_amount_entry.bind('<Return>', self.on_manual_corner_parameter_changed)
        self.manual_corner_amount_entry.bind('<FocusOut>', self.on_manual_corner_parameter_changed)

        self.manual_corner_secondary_row = tk.Frame(self.manual_corner_param_frame, bg=self.COLOR_INPUT_BG)
        tk.Label(self.manual_corner_secondary_row, text="嵌入留肉 :", width=12, anchor=tk.W,
                 bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT).pack(side=tk.LEFT)
        self.manual_corner_secondary_retain_entry = ttk.Entry(
            self.manual_corner_secondary_row, textvariable=self.manual_corner_secondary_retain_var,
            width=7, justify=tk.CENTER
        )
        self.manual_corner_secondary_retain_entry.pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(self.manual_corner_secondary_row, text="T   深度 :", bg=self.COLOR_INPUT_BG,
                 fg=self.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        self.manual_corner_secondary_depth_entry = ttk.Entry(
            self.manual_corner_secondary_row, textvariable=self.manual_corner_secondary_depth_var,
            width=7, justify=tk.CENTER
        )
        self.manual_corner_secondary_depth_entry.pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(self.manual_corner_secondary_row, text="T", bg=self.COLOR_INPUT_BG,
                 fg=self.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
        for entry in (self.manual_corner_secondary_retain_entry, self.manual_corner_secondary_depth_entry):
            entry.bind('<Return>', self.on_manual_corner_parameter_changed)
            entry.bind('<FocusOut>', self.on_manual_corner_parameter_changed)

        self.corner_type_preview_canvas = tk.Canvas(
            editor, width=150, height=105, bg=self.COLOR_CANVAS_BG,
            highlightthickness=1, highlightbackground='#34343a'
        )
        self.corner_type_preview_canvas.pack(padx=8, pady=(4, 8))

        panel.pack_forget()
        self.corner_type_panel_anchor = tk.Frame(parent, bg=self.COLOR_PANEL, height=1)
        self.corner_type_panel_anchor.pack(fill=tk.X)

    def _draw_corner_type_icon(self, canvas, selection_or_type, *, large=False, flip_y=True):
        """Render a preview from the same semantic selection used by production geometry."""
        canvas.delete('all')
        w = max(10, int(float(canvas.cget('width'))))
        h = max(10, int(float(canvas.cget('height'))))
        margin = 5 if not large else 12
        if isinstance(selection_or_type, CornerTypeSelection):
            selection = normalize_corner_selection(selection_or_type)
        else:
            selection = CornerTypeSelection(CornerTypeId(selection_or_type))
        preview = build_corner_type_preview_geometry(selection)
        usable_w = max(1.0, w - 2 * margin)
        usable_h = max(1.0, h - 2 * margin)
        scale = min(usable_w / preview.span, usable_h / preview.span)
        ox = margin + (usable_w - preview.span * scale) / 2.0
        oy = h - margin - (usable_h - preview.span * scale) / 2.0

        def pt(point):
            return _corner_preview_canvas_point(
                point, ox=ox, oy=oy, scale=scale, span=preview.span, flip_y=flip_y
            )

        for path in preview.cut_paths:
            coords = []
            for point in path:
                coords.extend(pt(point))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill='#30d158', width=3 if large else 2,
                                   capstyle=tk.PROJECTING, joinstyle=tk.MITER)
        for path in preview.bend_paths:
            coords = []
            for point in path:
                coords.extend(pt(point))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill='#0a84ff', dash=(3, 2), width=1,
                                   capstyle=tk.PROJECTING, joinstyle=tk.MITER)
        if large:
            canvas.create_text(
                w / 2, 10, text=CORNER_TYPE_LABELS[selection.type_id],
                fill=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')
            )

    def _pair_for_corner_target(self, target_key):
        if target_key in ('top', 'top_left', 'top_right'):
            return 'top'
        if target_key in ('bottom', 'bottom_left', 'bottom_right'):
            return 'bottom'
        return None

    def _normalize_manual_corner_target(self, part_key):
        target = self.manual_active_corner_var.get()
        same = self.manual_corner_pair_same[part_key]
        pair = self._pair_for_corner_target(target)
        if pair is None:
            target = 'top'; pair = 'top'
        if same[pair]:
            target = pair
        elif target == pair:
            target = CORNER_PAIR_CORNERS[pair][0]
        self.manual_active_corner_var.set(target)
        return target

    def _manual_selection_for_target(self, part_key, target_key):
        if target_key in CORNER_PAIR_CORNERS:
            target_key = CORNER_PAIR_CORNERS[target_key][0]
        return normalize_corner_selection(self.manual_corner_state[part_key][target_key])

    def select_manual_corner(self, corner_key):
        part_key = self._current_manual_corner_part_key()
        if part_key is None or part_key not in self.manual_corner_state:
            return
        valid = set(CORNER_KEYS) | {'top', 'bottom'}
        if corner_key not in valid:
            return
        pair = self._pair_for_corner_target(corner_key)
        if corner_key in ('top', 'bottom') and not self.manual_corner_pair_same[part_key][pair]:
            corner_key = CORNER_PAIR_CORNERS[pair][0]
        elif corner_key in CORNER_KEYS and self.manual_corner_pair_same[part_key][pair]:
            corner_key = pair
        self.manual_active_corner_var.set(corner_key)
        self.refresh_corner_type_panel()

    def on_manual_corner_pair_same_changed(self, pair_key):
        part_key = self._current_manual_corner_part_key()
        if part_key is None or part_key not in self.manual_corner_state:
            return
        if not self._manual_corner_parameters_editable(part_key):
            self.refresh_corner_type_panel()
            return
        enabled = self.manual_top_same_var.get() if pair_key == 'top' else self.manual_bottom_same_var.get()
        set_manual_corner_pair_same(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key], pair_key, enabled
        )
        if enabled:
            self.manual_active_corner_var.set(pair_key)
        elif self._pair_for_corner_target(self.manual_active_corner_var.get()) == pair_key:
            self.manual_active_corner_var.set(CORNER_PAIR_CORNERS[pair_key][0])
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def set_manual_corner_type(self, type_id):
        part_key = self._current_manual_corner_part_key()
        if not self._corner_part_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        if part_key in {"head", "tail"} and target_key in {"top", "top_left", "top_right"}:
            # 上方類型由箱身組合方式擁有；此頁只調左右參數。
            self.refresh_corner_type_panel()
            return
        type_id = CornerTypeId(type_id)
        current = self._manual_selection_for_target(part_key, target_key)
        selection = current if current.type_id is type_id else CornerTypeSelection(type_id)
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    @staticmethod
    def _corner_number_text(value):
        value = float(value)
        return str(int(value)) if value.is_integer() else f"{value:g}"

    def _selection_from_manual_corner_controls(self):
        try:
            type_id = CornerTypeId(self.manual_corner_type_var.get())
        except ValueError:
            return None
        try:
            amount = float(self.manual_corner_amount_var.get())
            secondary_retain = float(self.manual_corner_secondary_retain_var.get())
            secondary_depth = float(self.manual_corner_secondary_depth_var.get())
        except (TypeError, ValueError, tk.TclError):
            return None
        try:
            if type_id is CornerTypeId.CROSS:
                mode = self._CORNER_MODE_BY_LABEL.get(
                    self.manual_corner_cross_mode_var.get(), CrossCornerMode.STANDARD
                )
                if mode is CrossCornerMode.STANDARD:
                    return CornerTypeSelection(type_id, cross_mode=mode)
                direction = self._CORNER_DIRECTION_BY_LABEL.get(self.manual_corner_direction_var.get())
                if direction is None:
                    direction = CornerDirection.WIDTH if mode is CrossCornerMode.RETAIN else CornerDirection.BOTH
                return CornerTypeSelection(
                    type_id, cross_mode=mode, direction=direction, amount_t=amount
                )
            if type_id is CornerTypeId.OVERLAY:
                return CornerTypeSelection(type_id, amount_t=amount)
            if type_id is CornerTypeId.INSERT:
                return CornerTypeSelection(type_id, amount_t=amount)
            if type_id is CornerTypeId.INSERT_OVERLAY:
                return CornerTypeSelection(
                    type_id, amount_t=amount,
                    secondary_retain_t=secondary_retain,
                    secondary_depth_t=secondary_depth,
                )
        except (TypeError, ValueError):
            return None
        return None

    def on_manual_corner_mode_changed(self, event=None):
        if self._manual_corner_param_guard:
            return
        part_key = self._current_manual_corner_part_key()
        if not self._manual_corner_parameters_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        mode = self._CORNER_MODE_BY_LABEL.get(self.manual_corner_cross_mode_var.get())
        if mode is None:
            return
        selection = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=mode)
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def on_manual_corner_parameter_changed(self, event=None):
        if self._manual_corner_param_guard:
            return
        part_key = self._current_manual_corner_part_key()
        if not self._manual_corner_parameters_editable(part_key):
            return
        target_key = self._normalize_manual_corner_target(part_key)
        selection = self._selection_from_manual_corner_controls()
        if selection is None:
            return
        apply_manual_corner_selection(
            self.manual_corner_state[part_key], self.manual_corner_pair_same[part_key],
            target_key, selection,
        )
        self.refresh_corner_type_panel()
        self._notify_fold_designer_corner_state()
        self._request_phase6_update("geometry")

    def _refresh_manual_corner_parameter_rows(self, selection):
        for row in (
            self.manual_corner_mode_row, self.manual_corner_direction_row,
            self.manual_corner_amount_row, self.manual_corner_secondary_row,
        ):
            row.pack_forget()

        if selection.type_id is CornerTypeId.CROSS:
            self.manual_corner_mode_row.pack(fill=tk.X, pady=2)
            if selection.cross_mode is CrossCornerMode.STANDARD:
                return
            self.manual_corner_direction_row.pack(fill=tk.X, pady=2)
            self.manual_corner_amount_row.pack(fill=tk.X, pady=2)
            if selection.cross_mode is CrossCornerMode.RETAIN:
                self.manual_corner_direction_label.configure(text="留肉方向 :")
                self.manual_corner_direction_cb.configure(values=['寬', '高'], state='readonly')
                self.manual_corner_amount_label.configure(text="留肉 :")
            else:
                self.manual_corner_direction_label.configure(text="多切方向 :")
                self.manual_corner_direction_cb.configure(values=['寬＋高', '寬', '高'], state='readonly')
                self.manual_corner_amount_label.configure(text="多切 :")
            return

        self.manual_corner_amount_row.pack(fill=tk.X, pady=2)
        if selection.type_id is CornerTypeId.OVERLAY:
            self.manual_corner_amount_label.configure(text="留肉（高） :")
        elif selection.type_id is CornerTypeId.INSERT:
            self.manual_corner_amount_label.configure(text="多切（高） :")
        else:
            self.manual_corner_amount_label.configure(text="貼外留肉（高） :")
            self.manual_corner_secondary_row.pack(fill=tk.X, pady=2)

    def refresh_corner_type_panel(self):
        if self.corner_type_panel is None:
            return
        part_key = self._current_manual_corner_part_key()
        if part_key not in self.manual_corner_state:
            self.corner_type_panel.pack_forget()
            return
        if not self.corner_type_panel.winfo_ismapped():
            self.corner_type_panel.pack(fill=tk.X, pady=(6, 8), before=self.corner_type_panel_anchor)

        part_labels = {
            'head': '封頭', 'tail': '封尾', 'door': '門', 'base_plate': '底板',
            'indicator_box': '指示燈盒', 'indicator_door': '指示燈小門',
        }
        self.manual_corner_part_label.configure(text=f"板件：{part_labels.get(part_key, part_key)}")
        type_editable = self._corner_part_type_editable(part_key)
        unlockable = self._corner_part_parameters_unlockable(part_key)
        params_unlocked = self._manual_corner_parameters_unlocked(part_key)
        if not unlockable:
            self.manual_corner_title_label.configure(text="截角類型（固定 / 唯讀）")
            self.manual_corner_param_lock_button.pack_forget()
            self.manual_corner_editor_frame.pack_forget()
            summary = self._fixed_corner_summary(part_key)
            self.manual_corner_fixed_summary.configure(text=summary)
            self.manual_corner_fixed_summary.pack(fill=tk.X, padx=8, pady=(2, 8))
            return

        self.manual_corner_title_label.configure(text="截角類型" if type_editable else "截角類型（基準預設）")
        self.manual_corner_fixed_summary.pack_forget()
        if not self.manual_corner_param_lock_button.winfo_ismapped():
            self.manual_corner_param_lock_button.pack(side=tk.RIGHT, padx=(6, 0))
        self.manual_corner_param_lock_button.configure(text="🔓 參數解鎖" if params_unlocked else "🔒 參數鎖定")
        if not self.manual_corner_editor_frame.winfo_ismapped():
            self.manual_corner_editor_frame.pack(fill=tk.X)

        same = self.manual_corner_pair_same[part_key]
        self.manual_top_same_var.set(same['top'])
        self.manual_bottom_same_var.set(same['bottom'])
        target_key = self._normalize_manual_corner_target(part_key)
        selection = self._manual_selection_for_target(part_key, target_key)

        self._manual_corner_param_guard = True
        try:
            self.manual_corner_type_var.set(selection.type_id.value)
            if selection.cross_mode is not None:
                self.manual_corner_cross_mode_var.set(self._CORNER_MODE_LABELS[selection.cross_mode])
            if selection.direction is not None:
                self.manual_corner_direction_var.set(self._CORNER_DIRECTION_LABELS[selection.direction])
            self.manual_corner_amount_var.set(self._corner_number_text(selection.amount_t or 1.0))
            self.manual_corner_secondary_retain_var.set(
                self._corner_number_text(selection.secondary_retain_t if selection.secondary_retain_t is not None else 0.5)
            )
            self.manual_corner_secondary_depth_var.set(
                self._corner_number_text(selection.secondary_depth_t if selection.secondary_depth_t is not None else 2.0)
            )
        finally:
            self._manual_corner_param_guard = False

        for pair_key, controls in self.manual_corner_pair_buttons.items():
            for widget in (controls['pair'], controls['left'], controls['right']):
                widget.pack_forget()
            if same[pair_key]:
                controls['pair'].pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                controls['left'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
                controls['right'].pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
            pair_targets = {pair_key} if same[pair_key] else set(CORNER_PAIR_CORNERS[pair_key])
            for name in ('pair', 'left', 'right'):
                widget = controls[name]
                widget_target = pair_key if name == 'pair' else CORNER_PAIR_CORNERS[pair_key][0 if name == 'left' else 1]
                active = widget_target == target_key and widget_target in pair_targets
                widget.configure(bg=self.COLOR_ACCENT if active else self.COLOR_PANEL,
                                 fg='#ffffff' if active else self.COLOR_TEXT)

        params_editable = self._manual_corner_parameters_editable(part_key)
        for cb in self.manual_corner_pair_same_checkbuttons.values():
            if params_unlocked:
                if not cb.winfo_ismapped():
                    cb.pack(side=tk.LEFT, padx=(2, 8), before=cb.master.winfo_children()[-1])
                cb.configure(state=(tk.NORMAL if params_editable else tk.DISABLED))
            else:
                cb.pack_forget()
        target_type_editable = type_editable and not (
            part_key in {"head", "tail"} and target_key in {"top", "top_left", "top_right"}
        )
        for rb in self.manual_corner_type_buttons.values():
            rb.configure(state=(tk.NORMAL if target_type_editable else tk.DISABLED))

        flip_y = _corner_preview_flip_y_for_target(target_key)
        for type_id, canvas in self.corner_type_small_canvases.items():
            self._draw_corner_type_icon(
                canvas, CornerTypeSelection(type_id), large=False, flip_y=flip_y
            )
            canvas.configure(highlightbackground=self.COLOR_ACCENT if type_id is selection.type_id else '#34343a')
        if params_unlocked:
            self.manual_corner_param_summary.pack_forget()
            if not self.manual_corner_param_frame.winfo_ismapped():
                self.manual_corner_param_frame.pack(fill=tk.X, padx=8, pady=(5, 2))
            self._refresh_manual_corner_parameter_rows(selection)
        else:
            self.manual_corner_param_frame.pack_forget()
            self.manual_corner_param_summary.configure(text=f"目前參數：{self._corner_parameter_summary(selection)}")
            if not self.manual_corner_param_summary.winfo_ismapped():
                self.manual_corner_param_summary.pack(fill=tk.X, padx=8, pady=(3, 5))
        if self.corner_type_preview_canvas is not None:
            self._draw_corner_type_icon(
                self.corner_type_preview_canvas, selection, large=True, flip_y=flip_y
            )

    def on_preview_tab_changed(self, event=None):
        # 真正切換主分頁後，由該板件接管目前截角編輯內容
        # back from a hidden auxiliary part returned by the 3D designer.
        self._manual_corner_part_override = None
        self.refresh_corner_type_panel()
        self.draw_preview()

    def create_widgets(self):
        # 全域專案列：和一般桌面軟體一樣固定在主視窗左上角，
        # 不屬於任何板件/2D/3D 頁面。
        self.project_toolbar = tk.Frame(self.root, bg=self.COLOR_BG)
        self.project_toolbar.pack(fill=tk.X, padx=20, pady=(8, 0))
        project_button_opts = dict(
            font=('Microsoft JhengHei', 9), bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
            activebackground=self.COLOR_ACCENT, activeforeground="#ffffff",
            bd=0, cursor="hand2", padx=10, pady=4,
        )
        self.project_open_button = tk.Button(
            self.project_toolbar, text="開啟專案", command=self.open_phase6_project, **project_button_opts
        )
        self.project_open_button.pack(side=tk.LEFT, padx=(0, 4))
        self.project_save_button = tk.Button(
            self.project_toolbar, text="儲存專案", command=self.save_phase6_project, **project_button_opts
        )
        self.project_save_button.pack(side=tk.LEFT, padx=(0, 4))
        self.project_save_as_button = tk.Button(
            self.project_toolbar, text="另存新檔", command=self.save_phase6_project_as, **project_button_opts
        )
        self.project_save_as_button.pack(side=tk.LEFT)

        # 頂部標題列
        title_frame = tk.Frame(self.root, bg=self.COLOR_BG, height=60)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        
        title_lbl = ttk.Label(title_frame, text="箱體板金展開計算與預覽工具", style='Header.TLabel')
        title_lbl.pack(side=tk.LEFT, pady=5)
        
        subtitle_lbl = tk.Label(title_frame, text="支援實時預覽、參數連動與 DXF 加工層輸出", 
                                bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9))
        subtitle_lbl.pack(side=tk.LEFT, padx=15, pady=10)

        text_size_frame = tk.Frame(title_frame, bg=self.COLOR_BG)
        text_size_frame.pack(side=tk.RIGHT, pady=5)
        tk.Label(
            text_size_frame, text="文字大小：", bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 9)
        ).pack(side=tk.LEFT, padx=(0, 4))
        self.ui_text_size_combo = ttk.Combobox(
            text_size_frame, textvariable=self.ui_text_size_var,
            values=tuple(UI_TEXT_SIZE_LABELS.values()), state="readonly", width=4,
        )
        self.ui_text_size_combo.pack(side=tk.LEFT)
        self.ui_text_size_combo.bind("<<ComboboxSelected>>", self.on_ui_text_size_changed)
        
        # 主內容區域 (左右分欄)
        main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.COLOR_BG, bd=0, sashwidth=4)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.main_paned = main_paned
        
        # ==========================================
        # 左側：控制面板
        # ==========================================
        left_container = tk.Frame(main_paned, bg=self.COLOR_BG)
        main_paned.add(left_container, width=320)
        self.left_container = left_container
        
        # 控制面板卡片
        ctrl_card = tk.Frame(left_container, bg=self.COLOR_PANEL, bd=0)
        ctrl_card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 內距包裝框（使用 Canvas + Scrollbar 支援捲動）
        scroll_canvas = tk.Canvas(ctrl_card, bg=self.COLOR_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(ctrl_card, orient=tk.VERTICAL, command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ctrl_pad_frame = tk.Frame(scroll_canvas, bg=self.COLOR_PANEL)
        scroll_win = scroll_canvas.create_window((0, 0), window=ctrl_pad_frame, anchor=tk.NW)
        
        def on_frame_configure(event):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))
        def on_canvas_resize(event):
            scroll_canvas.itemconfig(scroll_win, width=event.width)
        def on_mousewheel(event):
            scroll_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
        ctrl_pad_frame.bind('<Configure>', on_frame_configure)
        scroll_canvas.bind('<Configure>', on_canvas_resize)
        scroll_canvas.bind('<MouseWheel>', on_mousewheel)
        ctrl_pad_frame.bind('<MouseWheel>', on_mousewheel)
        
        # 區段 0：基準型號就是盤體類型；只有一個 Source of Truth。
        lbl_sec0 = ttk.Label(ctrl_pad_frame, text="0. 基準型號", style='Title.TLabel')
        lbl_sec0.pack(anchor=tk.W, pady=(0, 6))

        row_base = tk.Frame(ctrl_pad_frame, bg=self.COLOR_PANEL)
        row_base.pack(fill=tk.X, pady=2)
        
        lbl_base = ttk.Label(row_base, text="基準型號 :", width=12, anchor=tk.W)
        lbl_base.pack(side=tk.LEFT)
        
        base_models = self._baseline_model_choices()
        self.baseline_cb = ttk.Combobox(row_base, textvariable=self.baseline_var, 
                                        values=base_models, state="readonly", style='TCombobox')
        self.baseline_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if base_models:
            if "金庫型" in base_models:
                idx = base_models.index("金庫型")
                self.baseline_cb.current(idx)
            elif CUSTOM_MODEL_NAME in base_models:
                self.baseline_cb.current(base_models.index(CUSTOM_MODEL_NAME))
            else:
                self.baseline_cb.current(0)
            
        self._baseline_last_value = self.baseline_var.get().strip()
        self._enforce_known_model_corner_types(reset_all=True)
        # Capture the canonical Vault startup state before the user can edit it.
        # Returning to a known model must restore this preset, not the last
        # runtime values used before switching away.
        self._cabinet_family_defaults["金庫型"] = self._capture_cabinet_family_runtime()
        self.baseline_var.trace_add("write", lambda *args: self.on_baseline_changed())

        self.fold_designer_button = tk.Button(
            ctrl_pad_frame, text="開啟折彎 / 3D 設計", command=self.open_original_fold_designer,
            font=('Microsoft JhengHei', 10, 'bold'), bg=self.COLOR_ACCENT, fg="#ffffff",
            activebackground=self.COLOR_ACCENT, activeforeground="#ffffff", bd=0, cursor="hand2"
        )
        self.fold_designer_button.pack(fill=tk.X, pady=(8, 4), ipady=4)

        # 截角類型面板：自訂可編輯；固定板件／已知基準只顯示實際唯讀語意。
        self.create_corner_type_panel(ctrl_pad_frame)

        # 分隔線
        self.create_separator(ctrl_pad_frame)
        
        # 區段 1：基礎尺寸
        lbl_sec1 = ttk.Label(ctrl_pad_frame, text="1. 基礎尺寸設定 (mm)", style='Title.TLabel')
        lbl_sec1.pack(anchor=tk.W, pady=(0, 10))
        
        # 寬、高、深輸入框
        self.create_input_row(ctrl_pad_frame, "寬度 (W) :", self.w_var)
        self.create_input_row(ctrl_pad_frame, "高度 (H) :", self.h_var)
        self.create_input_row(ctrl_pad_frame, "深度 (D) :", self.d_var)
        
        # 折彎/板件專屬設定已集中到 3D 設定中心；主 GUI 僅保留全域尺寸。
        self.create_separator(ctrl_pad_frame)
        
        # 區段 3：計算結果與輸出
        lbl_sec3 = ttk.Label(ctrl_pad_frame, text="2. 展開尺寸計算結果", style='Title.TLabel')
        lbl_sec3.pack(anchor=tk.W, pady=(0, 10))
        
        # 結果顯示區域
        result_box = tk.Frame(ctrl_pad_frame, bg=self.COLOR_INPUT_BG, bd=1, relief=tk.SOLID, highlightthickness=0)
        result_box.pack(fill=tk.X, pady=5)
        
        self._phase6_result_part_rows = {
            "box_body": [
                self.create_result_row(result_box, "箱身 (z) 總長度:", self.result_z_var),
                self.create_result_row(result_box, "箱身 (z) 展開高:", self.result_z_h_var),
            ],
            # Head/Tail share the same unfolded-size result. Keep it while either
            # physical end cap exists; hide it only when both are deleted.
            "endcap": [
                self.create_result_row(result_box, "封頭/尾 展開寬:", self.result_y_w_var),
                self.create_result_row(result_box, "封頭/尾 展開深:", self.result_y_d_var),
            ],
            "door": [
                self.create_result_row(result_box, "門 (Door) 展開寬:", self.result_door_w_var),
                self.create_result_row(result_box, "門 (Door) 展開高:", self.result_door_h_var),
            ],
            "base_plate": [
                self.create_result_row(result_box, "底板 展開寬:", self.result_base_plate_w_var),
                self.create_result_row(result_box, "底板 展開高:", self.result_base_plate_h_var),
            ],
            "indicator_box": [
                self.create_result_row(result_box, "指示燈盒子 展開寬:", self.result_ib_w_var),
                self.create_result_row(result_box, "指示燈盒子 展開高:", self.result_ib_h_var),
            ],
            "indicator_door": [
                self.create_result_row(result_box, "指示燈小門 展開寬:", self.result_ib_door_w_var),
                self.create_result_row(result_box, "指示燈小門 展開高:", self.result_ib_door_h_var),
            ],
        }
        
        # 輸出選項區塊（固定顯示）
        self.create_separator(ctrl_pad_frame)
        
        lbl_output_opts = ttk.Label(ctrl_pad_frame, text="3. DXF 輸出選項", style='Title.TLabel')
        lbl_output_opts.pack(anchor=tk.W, pady=(0, 6))
        
        output_opts_box = tk.Frame(ctrl_pad_frame, bg=self.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
        output_opts_box.pack(fill=tk.X, pady=(0, 4))
        
        def make_chk(parent, text, var, cmd=None):
            return tk.Checkbutton(
                parent, text=text, variable=var,
                bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                selectcolor=self.COLOR_PANEL,
                activebackground=self.COLOR_INPUT_BG, activeforeground=self.COLOR_ACCENT,
                font=('Microsoft JhengHei', 9), cursor="hand2",
                command=cmd
            )
        
        # DXF 選項（只剩 STOCK）
        make_chk(output_opts_box, "輸出 STOCK 母材外框 (青色虛線)",
                 self.draw_stock_var, self.draw_preview).pack(anchor=tk.W, padx=10, pady=(6,6))
        
        # 輸出零件選擇
        self.create_separator(ctrl_pad_frame)
        lbl_parts = ttk.Label(ctrl_pad_frame, text="4. 選擇輸出零件", style='Title.TLabel')
        lbl_parts.pack(anchor=tk.W, pady=(0, 6))
        
        parts_box = tk.Frame(ctrl_pad_frame, bg=self.COLOR_INPUT_BG, bd=1, relief=tk.SOLID)
        parts_box.pack(fill=tk.X, pady=(0, 8))
        
        self._phase6_output_part_widgets = {
            "box_body": make_chk(parts_box, "箱身 (Z)  →  box_body_z.dxf", self.export_z_var),
            "head": make_chk(parts_box, "封頭 (Y)  →  end_cap_head.dxf", self.export_head_var),
            "tail": make_chk(parts_box, "封尾 (Y)  →  end_cap_tail.dxf", self.export_tail_var),
            "door": make_chk(parts_box, "門 (Door)  →  door_unfold.dxf / 多門 door_cN_rM.dxf", self.export_door_var),
            "base_plate": make_chk(parts_box, "底板  →  base_plate.dxf", self.export_base_plate_var),
            "indicator_box": make_chk(parts_box, "指示燈盒子  →  indicator_box.dxf", self.export_ib_var),
            "indicator_door": make_chk(parts_box, "指示燈小門  →  indicator_door.dxf", self.export_ib_door_var),
        }
        for index, key in enumerate(("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")):
            pady = (6, 1) if index == 0 else ((1, 6) if index == 6 else (1, 1))
            self._phase6_output_part_widgets[key].pack(anchor=tk.W, padx=10, pady=pady)
        
        # 輸出按鈕
        self.btn_export = tk.Button(
            ctrl_pad_frame,
            text="輸出選取的 DXF 檔案",
            font=('Microsoft JhengHei', 11, 'bold'),
            bg=self.COLOR_ACCENT, fg="#ffffff",
            activebackground=self.COLOR_ACCENT_HOVER, activeforeground="#ffffff",
            bd=0, height=2, cursor="hand2",
            command=self.export_selected_dxf
        )
        self.btn_export.pack(fill=tk.X, pady=(8, 0))
        
        # ==========================================
        # 右側：預覽與分頁面
        # ==========================================
        right_container = tk.Frame(main_paned, bg=self.COLOR_BG)
        main_paned.add(right_container, stretch="always")
        
        # 分頁面 (Notebook)
        self.notebook = ttk.Notebook(right_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 箱身 (z) 分頁
        self.tab_z = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.notebook.add(self.tab_z, text="  箱身 (z)  ")
        self.setup_tab_z_ui()
        
        # 封頭 (y) 分頁
        self.tab_head = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.notebook.add(self.tab_head, text="  封頭 (y)  ")
        self.setup_tab_endcap_ui(self.tab_head, 'head')
        
        # 封尾 (y) 分頁
        self.tab_tail = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.notebook.add(self.tab_tail, text="  封尾 (y)  ")
        self.setup_tab_endcap_ui(self.tab_tail, 'tail')
        
        # 門 (Door) 分頁
        self.tab_door = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.notebook.add(self.tab_door, text="  門 (Door)  ")
        self.setup_tab_door_ui()
        
        # 底板分頁
        self.tab_base_plate = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.notebook.add(self.tab_base_plate, text="  底板  ")
        self.setup_tab_base_plate_ui()
        
        # 指示燈盒子 / 小門是 Door 的附屬零件，不佔主 Notebook 第一層。
        # 保留內部 frame/UI 供既有共用邏輯使用；實際入口在 Door 開孔編輯器。
        self.tab_indicator_box = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.setup_tab_indicator_box_ui()

        self.tab_indicator_door = tk.Frame(self.notebook, bg=self.COLOR_BG)
        self.setup_tab_indicator_door_ui()
        
        # 當切換分頁時重新繪圖
        self.notebook.bind("<<NotebookTabChanged>>", self.on_preview_tab_changed)
        
        # 初始化底板四面同綁定與 trace
        self.base_plate_shrink_same_var.trace_add("write", lambda *args: self.sync_base_plate_shrink())
        self.on_base_plate_same_toggle()
        self._phase6_refresh_presence_ui()
        
    def on_base_plate_same_toggle(self, *args):
        # UI 已搬到 3D；此 helper 只保留舊資料同步語意。
        if self.base_plate_all_same_var.get():
            self.sync_base_plate_shrink()
        self._request_phase6_update("geometry")

    def sync_base_plate_shrink(self, *args):
        if self.base_plate_all_same_var.get():
            val = self.base_plate_shrink_same_var.get()
            self.base_plate_shrink_top_var.set(val)
            self.base_plate_shrink_bottom_var.set(val)
            self.base_plate_shrink_left_var.set(val)
            self.base_plate_shrink_right_var.set(val)

    def create_input_row(self, parent, label_text, var):
        row = tk.Frame(parent, bg=self.COLOR_PANEL)
        row.pack(fill=tk.X, pady=4)
        
        lbl = ttk.Label(row, text=label_text, width=12, anchor=tk.W)
        lbl.pack(side=tk.LEFT)
        
        entry = tk.Entry(row, textvariable=var, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                         insertbackground=self.COLOR_TEXT, bd=1, relief=tk.SOLID, 
                         font=('Microsoft JhengHei', 10), justify=tk.CENTER)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        
    def create_result_row(self, parent, label_text, var):
        row = tk.Frame(parent, bg=self.COLOR_INPUT_BG)
        row.pack(fill=tk.X, pady=6, padx=10)
        
        lbl = tk.Label(row, text=label_text, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT_MUTED, 
                       font=('Microsoft JhengHei', 9), anchor=tk.W)
        lbl.pack(side=tk.LEFT)
        
        val = tk.Label(row, textvariable=var, bg=self.COLOR_INPUT_BG, fg="#30d158", 
                       font=('Consolas', 11, 'bold'), anchor=tk.E)
        val.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        return row

    def _phase6_current_existing_parts(self):
        """Return physical presence from the single Workspace Controller."""
        indicator_var = getattr(self, "is_indicator_box_var", None)
        indicator_enabled = bool(indicator_var.get()) if indicator_var is not None else False
        return self.workspace_controller.current_existing_parts(
            indicator_box_enabled=indicator_enabled
        )

    def _phase6_set_part_presence(self, key, present):
        """Mutate physical presence through the single Workspace Controller."""
        existing = self.workspace_controller.set_part_presence(str(key), bool(present))
        self._phase6_refresh_presence_ui(existing)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return existing

    def _phase6_refresh_presence_ui(self, existing_parts=None):
        """Hide absent-part controls completely so they occupy zero layout space."""
        existing = set(existing_parts) if existing_parts is not None else self._phase6_current_existing_parts()
        existing.add("box_body")

        result_groups = getattr(self, "_phase6_result_part_rows", {}) or {}
        visibility = {
            "box_body": "box_body" in existing,
            "endcap": bool({"head", "tail"} & existing),
            "door": "door" in existing,
            "base_plate": "base_plate" in existing,
            "indicator_box": "indicator_box" in existing,
            "indicator_door": "indicator_door" in existing,
        }
        for group in ("box_body", "endcap", "door", "base_plate", "indicator_box", "indicator_door"):
            for row in result_groups.get(group, ()): 
                row.pack_forget()
                if visibility[group]:
                    row.pack(fill=tk.X, pady=6, padx=10)

        output_widgets = getattr(self, "_phase6_output_part_widgets", {}) or {}
        output_order = ("box_body", "head", "tail", "door", "base_plate", "indicator_box", "indicator_door")
        for widget in output_widgets.values():
            widget.pack_forget()
        visible_keys = [key for key in output_order if key in existing and key in output_widgets]
        for index, key in enumerate(visible_keys):
            pady = (6, 1) if index == 0 else ((1, 6) if index == len(visible_keys) - 1 else (1, 1))
            output_widgets[key].pack(anchor=tk.W, padx=10, pady=pady)

        # No stale numbers for absent physical panels.
        if not visibility["endcap"]:
            self.result_y_w_var.set("-"); self.result_y_d_var.set("-")
        if not visibility["door"]:
            self.result_door_w_var.set("-"); self.result_door_h_var.set("-")
        if not visibility["base_plate"]:
            self.result_base_plate_w_var.set("-"); self.result_base_plate_h_var.set("-")
        if not visibility["indicator_box"]:
            self.result_ib_w_var.set("-"); self.result_ib_h_var.set("-")
        if not visibility["indicator_door"]:
            self.result_ib_door_w_var.set("-"); self.result_ib_door_h_var.set("-")
        return existing
        
    def create_separator(self, parent):
        sep = tk.Frame(parent, height=1, bg="#2a2a30")
        sep.pack(fill=tk.X, pady=15)
        
    def create_advanced_inputs(self, parent):
        # 箱身參數
        lbl_z = tk.Label(parent, text="箱身折彎與補償:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_z.pack(anchor=tk.W, pady=(8, 2))
        
        row_z1 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_z1.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_z1, "zl1", self.zl1_var)
        self.create_sub_input(row_z1, "zl2", self.zl2_var)
        # 佔位用以維持排版對齊
        tk.Frame(row_z1, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        row_z2 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_z2.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_z2, "zr1", self.zr1_var)
        self.create_sub_input(row_z2, "zr2", self.zr2_var)
        # 佔位用以維持排版對齊
        tk.Frame(row_z2, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        # 封頭尾參數
        lbl_y = tk.Label(parent, text="封頭尾折彎:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_y.pack(anchor=tk.W, pady=(8, 2))
        
        row_y1 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_y1.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_y1, "yl1", self.yl1_var)
        self.create_sub_input(row_y1, "yr1", self.yr1_var)
        # 佔位用
        tk.Frame(row_y1, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        row_y2 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_y2.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_y2, "y上1", self.ytop1_var)
        self.create_sub_input(row_y2, "y下1", self.ybottom1_var)
        # 佔位用
        tk.Frame(row_y2, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        # 門參數
        lbl_door = tk.Label(parent, text="門間隙與折邊:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_door.pack(anchor=tk.W, pady=(8, 2))
        
        row_door1 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_door1.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_door1, "間隙W", self.door_gap_w_var)
        self.create_sub_input(row_door1, "間隙H", self.door_gap_h_var)
        # 佔位用
        tk.Frame(row_door1, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        row_door2 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_door2.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_door2, "左折", self.door_fold_l_var)
        self.create_sub_input(row_door2, "右折", self.door_fold_r_var)
        # 佔位用
        tk.Frame(row_door2, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        row_door3 = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_door3.pack(fill=tk.X, pady=2)
        self.create_sub_input(row_door3, "上折", self.door_fold_t_var)
        self.create_sub_input(row_door3, "下折", self.door_fold_b_var)
        # 佔位用
        tk.Frame(row_door3, bg=self.COLOR_PANEL, width=65).pack(side=tk.LEFT, padx=2)
        
        # 底板參數
        lbl_base = tk.Label(parent, text="底板收縮與折邊:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_base.pack(anchor=tk.W, pady=(8, 2))
        
        # 1. 四面同與折邊
        row_same = tk.Frame(parent, bg=self.COLOR_PANEL)
        row_same.pack(fill=tk.X, pady=2)
        
        # 四面同核取方塊
        self.chk_same = tk.Checkbutton(
            row_same, text="四面同", variable=self.base_plate_all_same_var,
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
            activebackground=self.COLOR_PANEL, activeforeground=self.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9), cursor="hand2",
            command=self.on_base_plate_same_toggle
        )
        self.chk_same.pack(side=tk.LEFT, padx=2)
        
        # 四面同的值輸入框
        self.entry_shrink_same = tk.Entry(
            row_same, textvariable=self.base_plate_shrink_same_var, width=5,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, insertbackground=self.COLOR_TEXT,
            bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
        )
        self.entry_shrink_same.pack(side=tk.LEFT, padx=2)
        
        # 折邊輸入框
        lbl_bend = tk.Label(row_same, text="  折邊:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9))
        lbl_bend.pack(side=tk.LEFT, padx=2)
        self.entry_bend = tk.Entry(
            row_same, textvariable=self.base_plate_bend_var, width=5,
            bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, insertbackground=self.COLOR_TEXT,
            bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
        )
        self.entry_bend.pack(side=tk.LEFT, padx=2)
        
        # 2. 上下左右十字形收縮輸入框
        grid_frame = tk.Frame(parent, bg=self.COLOR_PANEL)
        grid_frame.pack(pady=4)
        
        def make_grid_input(parent, row, col, label_text, var):
            f = tk.Frame(parent, bg=self.COLOR_PANEL)
            f.grid(row=row, column=col, padx=4, pady=2)
            lbl = tk.Label(f, text=label_text, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 8))
            lbl.pack(side=tk.TOP)
            entry = tk.Entry(
                f, textvariable=var, width=5,
                bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, insertbackground=self.COLOR_TEXT,
                bd=1, relief=tk.SOLID, font=('Microsoft JhengHei', 9), justify=tk.CENTER
            )
            entry.pack(side=tk.TOP)
            return entry
            
        # Row 0: 上
        e_top = make_grid_input(grid_frame, 0, 1, "上縮", self.base_plate_shrink_top_var)
        # Row 1: 左, 右
        e_left = make_grid_input(grid_frame, 1, 0, "左縮", self.base_plate_shrink_left_var)
        
        lbl_center = tk.Label(grid_frame, text="底板", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold'))
        lbl_center.grid(row=1, column=1, padx=6)
        
        e_right = make_grid_input(grid_frame, 1, 2, "右縮", self.base_plate_shrink_right_var)
        # Row 2: 下
        e_bottom = make_grid_input(grid_frame, 2, 1, "下縮", self.base_plate_shrink_bottom_var)
        
        self.base_plate_entries.extend([e_top, e_bottom, e_left, e_right])
        
        # 輸出選項區塊
        sep = tk.Frame(parent, height=1, bg="#2a2a30")
        sep.pack(fill=tk.X, pady=(12, 6))
        
        lbl_out = tk.Label(parent, text="輸出選項:", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED,
                           font=('Microsoft JhengHei', 9, 'bold'))
        lbl_out.pack(anchor=tk.W, pady=(0, 4))
        
        stock_row = tk.Frame(parent, bg=self.COLOR_PANEL)
        stock_row.pack(fill=tk.X, pady=2)
        
        # STOCK 勾選框
        self.chk_stock = tk.Checkbutton(
            stock_row,
            text="輸出 STOCK 母材外框 (青色)",
            variable=self.draw_stock_var,
            bg=self.COLOR_PANEL,
            fg=self.COLOR_TEXT,
            selectcolor=self.COLOR_INPUT_BG,
            activebackground=self.COLOR_PANEL,
            activeforeground=self.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9),
            cursor="hand2",
            command=self.draw_preview
        )
        self.chk_stock.pack(side=tk.LEFT, padx=2)

    def create_sub_input(self, parent, label_text, var):
        frame = tk.Frame(parent, bg=self.COLOR_PANEL)
        frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        lbl = tk.Label(frame, text=label_text, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 8))
        lbl.pack(side=tk.TOP, anchor=tk.W)
        
        entry = tk.Entry(frame, textvariable=var, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT,
                         insertbackground=self.COLOR_TEXT, bd=1, relief=tk.SOLID, 
                         font=('Consolas', 9), justify=tk.CENTER, width=6)
        entry.pack(side=tk.BOTTOM, fill=tk.X, ipady=1)
        
    def toggle_advanced_panel(self):
        if self.adv_frame.winfo_manager():
            # 已展開，進行收合
            self.adv_frame.pack_forget()
            self.adv_btn.configure(text="▶ 進階參數設定 (板厚/折彎)")
        else:
            # 已收合，進行展開
            self.adv_frame.pack(fill=tk.X, before=self.adv_btn.master.children[list(self.adv_btn.master.children.keys())[-3]]) # 插在計算結果前
            self.adv_frame.pack(fill=tk.X, pady=(5, 10))
            self.adv_btn.configure(text="▼ 收起進階參數設定")

    def setup_tab_z_ui(self):
        # 頂部控制列
        top_ctrl = tk.Frame(self.tab_z, bg=self.COLOR_BG)
        top_ctrl.pack(fill=tk.X, padx=10, pady=5)
        
        lbl_fw = ttk.Label(top_ctrl, text="邊框寬度 (FW) :", style='TLabel')
        lbl_fw.pack(side=tk.LEFT, padx=5)
        
        # 箱身 FW 選擇框
        self.cb_fw_z = ttk.Combobox(top_ctrl, textvariable=self.fw_z_var, values=["20", "25", "30", "35"], 
                                    width=8, state="readonly", style='TCombobox')
        self.cb_fw_z.pack(side=tk.LEFT, padx=5)
        self.cb_fw_z.bind("<<ComboboxSelected>>", lambda e: self.on_fw_selected("z"))

        ttk.Label(top_ctrl, text="組合方式 :", style='TLabel').pack(side=tk.LEFT, padx=(15, 5))
        self.cb_box_assembly = ttk.Combobox(
            top_ctrl, textvariable=self.box_assembly_type_var,
            values=tuple(ASSEMBLY_TYPE_LABELS.values()), width=10, state="readonly", style='TCombobox'
        )
        self.cb_box_assembly.pack(side=tk.LEFT, padx=5)
        self.cb_box_assembly.bind("<<ComboboxSelected>>", self.on_box_assembly_changed)
        
        # 板厚
        lbl_t = ttk.Label(top_ctrl, text="板厚 (T) :", style='TLabel')
        lbl_t.pack(side=tk.LEFT, padx=(15, 5))
        
        entry_t_z = ttk.Entry(top_ctrl, textvariable=self.t_var, width=6, justify=tk.CENTER)
        entry_t_z.pack(side=tk.LEFT, padx=5)
        
        info_lbl = tk.Label(top_ctrl, text="(與封頭尾連動)", bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9))
        info_lbl.pack(side=tk.LEFT, padx=5)
        
        # 畫布 Frame
        canvas_frame = tk.Frame(self.tab_z, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # 箱身畫布
        self.canvas_z = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        self.canvas_z.pack(fill=tk.BOTH, expand=True)
        self.canvas_z.bind("<Configure>", lambda e: self.draw_preview())
        self.canvas_z.bind("<Button-1>", self.on_box_body_canvas_press)

    def _attach_part_hole_entrypoint(self, canvas, part_key, *, allow_double=True):
        """All supported panels use one memorable entry point: double-click opens holes."""
        canvas.unbind("<Button-3>")
        if allow_double:
            canvas.bind("<Double-Button-1>", lambda e, k=part_key: self.open_part_hole_editor(k))

    def setup_tab_endcap_ui(self, tab_frame, key):
        """建立封頭或封尾分頁 UI，key='head' 或 'tail'"""
        label_map = {'head': '封頭', 'tail': '封尾'}
        # 頂部控制列
        top_ctrl = tk.Frame(tab_frame, bg=self.COLOR_BG)
        top_ctrl.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(top_ctrl, text=f"{label_map[key]} — 邊框寬度 (FW) :",
                 bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
                 font=('Microsoft JhengHei', 9)).pack(side=tk.LEFT, padx=5)
        
        follow_var = self.fw_head_follow_var if key == 'head' else self.fw_tail_follow_var
        ttk.Checkbutton(
            top_ctrl, text="跟隨箱身 FW", variable=follow_var, state="disabled",
        ).pack(side=tk.LEFT, padx=(0, 5))
        cb_var = self.fw_head_var if key == 'head' else self.fw_tail_var
        cb = ttk.Combobox(top_ctrl, textvariable=cb_var,
                          values=["20", "25", "30", "35"],
                          width=8, state="normal", style='TCombobox')
        cb.pack(side=tk.LEFT, padx=5)
        cb.bind("<<ComboboxSelected>>", lambda e, k=key: self.on_fw_selected(k))
        cb.bind("<Return>", lambda e, k=key: self.on_fw_selected(k))
        cb.bind("<FocusOut>", lambda e, k=key: self.on_fw_selected(k))
        if key == 'head':
            self.cb_fw_head = cb
        else:
            self.cb_fw_tail = cb
        self._sync_endcap_fw_controls()
        
        # 板厚
        tk.Label(top_ctrl, text="板厚 (T) :",
                 bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
                 font=('Microsoft JhengHei', 9)).pack(side=tk.LEFT, padx=(15, 5))
        
        entry_t = ttk.Entry(top_ctrl, textvariable=self.t_var, width=6, justify=tk.CENTER)
        entry_t.pack(side=tk.LEFT, padx=5)
        
        # 畫布
        canvas_frame = tk.Frame(tab_frame, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        canvas = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.bind("<Configure>", lambda e: self.draw_preview())
        
        # 儲存畫布參照
        if key == 'head':
            self.canvas_head = canvas
        else:
            self.canvas_tail = canvas
        
        # 雙擊畫布開啟開孔編輯器
        canvas.bind("<Double-Button-1>", lambda e, k=key: self.open_hole_editor(k))
        
        # 雙擊提示標籤
        hint_lbl = tk.Label(canvas_frame,
            text="雙擊畫布開啟統一開孔編輯器",
            bg=self.COLOR_CANVAS_BG, fg="#3a3a48",
            font=('Microsoft JhengHei', 8))
        hint_lbl.place(relx=1.0, rely=1.0, anchor=tk.SE, x=-5, y=-5)

    def setup_tab_base_plate_ui(self):
        # 底板收縮/折邊已集中到 3D 設定中心；此頁只保留預覽/開孔入口。
        canvas_frame = tk.Frame(self.tab_base_plate, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.canvas_base_plate = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        self.canvas_base_plate.pack(fill=tk.BOTH, expand=True)
        self.canvas_base_plate.bind("<Configure>", lambda e: self.draw_preview())
        self._attach_part_hole_entrypoint(self.canvas_base_plate, "base_plate", allow_double=True)

        # 舊版 draw_base_plate 會查這兩個容器；保留空容器避免相容路徑失效。
        self.canvas_frames = {}
        self.canvas_window_ids = {}

    @staticmethod
    def _door_layout_number_text(value):
        value = float(value)
        return str(int(value)) if value.is_integer() else str(value)

    def _new_door_layout_column(self, width, heights, *, width_auto=False, height_auto=None):
        height_values = list(heights)
        if height_auto is None:
            height_auto = [False] * len(height_values)
        return {
            "width_var": tk.StringVar(value=self._door_layout_number_text(width)),
            "width_auto": bool(width_auto),
            "width_committed": float(width),
            "height_vars": [tk.StringVar(value=self._door_layout_number_text(v)) for v in height_values],
            "height_auto": [bool(v) for v in height_auto],
            "height_committed": [float(v) for v in height_values],
            "height_completion": None,
        }

    def set_door_layout_columns(self, columns):
        """Replace Door layout with explicit user values, then append any W/H remainders."""
        model = []
        for width, heights in columns:
            height_values = list(heights)
            if not height_values:
                raise ValueError("每一欄至少需要一層高度")
            model.append(self._new_door_layout_column(width, height_values))
        if not model:
            raise ValueError("門配置至少需要一欄")
        self.door_layout_columns = model
        self.door_layout_selected_var.set("0:0")
        self._recompute_door_layout_remainders(rebuild=False)
        if hasattr(self, "door_layout_columns_frame"):
            self.rebuild_door_layout_ui()

    def _ensure_door_layout_default(self):
        if self.door_layout_columns:
            return
        try:
            width = float(self.w_var.get())
            height = float(self.h_var.get())
        except ValueError:
            width, height = ae.W, ae.H
        self.door_layout_columns = [self._new_door_layout_column(width, [height])]
        self._recompute_door_layout_remainders(rebuild=False)

    @staticmethod
    def _parse_layout_value(var, label):
        try:
            value = float(var.get())
        except ValueError as exc:
            raise ValueError(f"{label}不是有效數字") from exc
        if value <= 0:
            raise ValueError(f"{label}必須大於 0")
        return value

    def _recompute_column_height_remainder(self, column, column_index, total_height):
        fixed = []
        for row_index, (var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"]), start=1):
            if not is_auto:
                fixed.append(self._parse_layout_value(var, f"欄 {column_index+1} 第 {row_index} 層高度"))
        completion = complete_partition(fixed, total_height, tolerance=0.01)
        column["height_vars"] = [tk.StringVar(value=self._door_layout_number_text(v)) for v in completion.values]
        column["height_committed"] = [float(v) for v in completion.values]
        column["height_auto"] = [False] * len(completion.values)
        if completion.auto_index is not None:
            column["height_auto"][completion.auto_index] = True
        column["height_completion"] = completion

    def _recompute_door_layout_remainders(self, *, rebuild=True):
        """Regenerate the one automatic width/height remainder from user-owned cells."""
        if not self.door_layout_columns:
            return
        try:
            total_width = float(self.w_var.get())
            total_height = float(self.h_var.get())
        except ValueError as exc:
            raise ValueError("W / H 必須先填入有效數字") from exc
        if total_width <= 0 or total_height <= 0:
            raise ValueError("W / H 必須大於 0")

        fixed_columns = [column for column in self.door_layout_columns if not column.get("width_auto", False)]
        fixed_widths = [
            self._parse_layout_value(column["width_var"], f"欄 {index+1} 寬度")
            for index, column in enumerate(fixed_columns)
        ]
        width_completion = complete_partition(fixed_widths, total_width, tolerance=0.01)

        for index, column in enumerate(fixed_columns):
            self._recompute_column_height_remainder(column, index, total_height)

        model = fixed_columns
        if width_completion.auto_index is not None:
            auto_width = width_completion.values[width_completion.auto_index]
            auto_column = self._new_door_layout_column(
                auto_width, [total_height], width_auto=True, height_auto=[True]
            )
            auto_column["height_completion"] = complete_partition([], total_height, tolerance=0.01)
            model.append(auto_column)

        self.door_layout_columns = model
        for column in self.door_layout_columns:
            try:
                column["width_committed"] = self._parse_layout_value(column["width_var"], "欄寬")
            except ValueError:
                pass
        self._door_layout_width_completion = width_completion

        # Keep selection on a real cell after automatic cells are inserted/removed.
        if self.door_layout_columns:
            try:
                c_text, r_text = self.door_layout_selected_var.get().split(":", 1)
                c_idx, r_idx = int(c_text), int(r_text)
            except Exception:
                c_idx = r_idx = 0
            c_idx = min(max(c_idx, 0), len(self.door_layout_columns) - 1)
            r_idx = min(max(r_idx, 0), len(self.door_layout_columns[c_idx]["height_vars"]) - 1)
            self.door_layout_selected_var.set(f"{c_idx}:{r_idx}")

        if rebuild and hasattr(self, "door_layout_columns_frame"):
            self.rebuild_door_layout_ui()

    def get_door_layout_columns(self):
        """Read current fixed + generated remainder cells as numeric layout values."""
        if not self.door_layout_columns:
            self._ensure_door_layout_default()
        columns = []
        for column_index, column in enumerate(self.door_layout_columns, start=1):
            if isinstance(column, (list, tuple)):
                columns.append((float(column[0]), [float(h) for h in list(column[1])]))
                continue
            width = self._parse_layout_value(column["width_var"], f"欄 {column_index} 寬度")
            heights = [
                self._parse_layout_value(var, f"欄 {column_index} 第 {row_index} 層高度")
                for row_index, var in enumerate(column["height_vars"], start=1)
            ]
            columns.append((width, heights))
        return columns

    def get_door_layout_cells(self):
        columns = self.get_door_layout_columns()
        try:
            total_width = float(self.w_var.get())
            total_height = float(self.h_var.get())
        except ValueError as exc:
            raise ValueError("W / H 必須先填入有效數字") from exc
        return validate_door_layout_dimensions(
            columns, total_width=total_width, total_height=total_height, tolerance=0.01
        )

    @staticmethod
    def _door_layout_cell_key(cell):
        return f"{cell.column_index}:{cell.row_index}"

    def get_selected_door_layout_cell(self):
        cells = self.get_door_layout_cells()
        selected_key = self.door_layout_selected_var.get()
        for cell in cells:
            if self._door_layout_cell_key(cell) == selected_key:
                return cell
        first = cells[0]
        self.door_layout_selected_var.set(self._door_layout_cell_key(first))
        return first

    def select_door_layout_cell(self, column_index, row_index):
        """Select one multi-door cell without rebuilding geometry or Canvas widgets."""
        selected_key = f"{int(column_index)}:{int(row_index)}"
        self.door_layout_selected_var.set(selected_key)

        canvas = getattr(self, "canvas_door", None)
        if canvas is not None:
            for key, item_id in getattr(self, "door_layout_cell_items", {}).items():
                try:
                    canvas.itemconfigure(
                        item_id,
                        outline=self.COLOR_ACCENT if key == selected_key else "#30d158",
                        width=3 if key == selected_key else 2,
                    )
                except tk.TclError:
                    pass

        if hasattr(self, "last_door_layout_overview"):
            self.last_door_layout_overview["selected"] = selected_key

    def _sync_door_canvas_double_click_binding(self):
        """Multi-door counts two Button-1 presses itself; single Door keeps Tk double-click."""
        if not hasattr(self, "canvas_door"):
            return
        self.canvas_door.unbind("<Double-Button-1>")
        if not self.multi_door_enabled_var.get():
            self.canvas_door.bind("<Double-Button-1>", self.on_door_canvas_double_click)

    def toggle_multi_door_layout(self):
        self._door_layout_last_click = None
        if self.multi_door_enabled_var.get():
            self._ensure_door_layout_default()
            self._recompute_door_layout_remainders(rebuild=False)
        self._sync_door_canvas_double_click_binding()
        # 舊的欄/層表單永久不佔 Door 分頁空間；尺寸直接在 Canvas 上編輯。
        if hasattr(self, "door_layout_body"):
            self.door_layout_body.pack_forget()
        self._on_door_layout_value_changed()

    def _reject_door_layout_dimension(self, var, previous_value, message):
        var.set(self._door_layout_number_text(previous_value))
        messagebox.showwarning("多門尺寸錯誤", message)
        self.refresh_door_layout_status()
        try:
            self.draw_preview()
        except Exception:
            pass
        return False

    def commit_door_layout_width(self, column_index):
        column = self.door_layout_columns[column_index]
        if "width_committed" in column:
            previous = float(column["width_committed"])
        else:
            previous = self._parse_layout_value(column["width_var"], "欄寬")
        try:
            current = self._parse_layout_value(column["width_var"], f"欄 {column_index+1} 寬度")
            total_width = self._parse_layout_value(self.w_var, "W")
            other_fixed = sum(
                self._parse_layout_value(c["width_var"], "欄寬")
                for i, c in enumerate(self.door_layout_columns)
                if i != column_index and not c.get("width_auto", False)
            )
            maximum = total_width - other_fixed
            if current > maximum + 0.01:
                return self._reject_door_layout_dimension(
                    column["width_var"], previous,
                    f"欄 {column_index+1} 寬度不可超過盤體 W。\n"
                    f"W = {total_width:g} mm，其餘固定欄合計 {other_fixed:g} mm，"
                    f"此欄最大只能輸入 {max(0.0, maximum):g} mm。"
                )
        except ValueError as exc:
            return self._reject_door_layout_dimension(column["width_var"], previous, str(exc))

        if column.get("width_auto", False):
            expected = total_width - other_fixed
            if abs(current - expected) > 0.01:
                column["width_auto"] = False
        column["width_committed"] = current
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)
        return True

    def commit_door_layout_height(self, column_index, row_index):
        column = self.door_layout_columns[column_index]
        committed = column.get("height_committed") or []
        previous = float(committed[row_index]) if row_index < len(committed) else self._parse_layout_value(
            column["height_vars"][row_index], "高度"
        )
        try:
            current = self._parse_layout_value(
                column["height_vars"][row_index], f"欄 {column_index+1} 第 {row_index+1} 層高度"
            )
            total_height = self._parse_layout_value(self.h_var, "H")
            other_fixed = sum(
                self._parse_layout_value(var, "高度")
                for i, (var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"]))
                if i != row_index and not is_auto
            )
            maximum = total_height - other_fixed
            if current > maximum + 0.01:
                return self._reject_door_layout_dimension(
                    column["height_vars"][row_index], previous,
                    f"欄 {column_index+1} 第 {row_index+1} 層高度不可超過盤體 H。\n"
                    f"H = {total_height:g} mm，同欄其他固定高度合計 {other_fixed:g} mm，"
                    f"此層最大只能輸入 {max(0.0, maximum):g} mm。"
                )
        except ValueError as exc:
            return self._reject_door_layout_dimension(column["height_vars"][row_index], previous, str(exc))

        if column["height_auto"][row_index]:
            expected = total_height - other_fixed
            if abs(current - expected) > 0.01:
                column["height_auto"][row_index] = False
        if row_index >= len(committed):
            column["height_committed"] = [
                self._parse_layout_value(var, "高度") for var in column["height_vars"]
            ]
        else:
            column["height_committed"][row_index] = current
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)
        return True

    def add_door_layout_column(self):
        """Compatibility action: promote current auto width; remainder creates the next column."""
        self._ensure_door_layout_default()
        auto_index = next((i for i, c in enumerate(self.door_layout_columns) if c.get("width_auto")), None)
        if auto_index is not None:
            self.commit_door_layout_width(auto_index)

    def _remap_door_layout_owned_data(self, mapper):
        for attr in (
            "door_layout_features", "door_layout_indicator_states",
            "door_layout_indicator_box_features", "door_layout_indicator_door_features",
        ):
            source = getattr(self, attr, {})
            remapped = {}
            for key, value in source.items():
                try:
                    c_text, r_text = key.split(":", 1)
                    mapped = mapper(int(c_text), int(r_text))
                except Exception:
                    mapped = None
                if mapped is None:
                    continue
                c_new, r_new = mapped
                remapped[f"{c_new}:{r_new}"] = value
            setattr(self, attr, remapped)

    def remove_door_layout_column(self, column_index):
        if not self.door_layout_columns:
            return
        if self.door_layout_columns[column_index].get("width_auto"):
            return
        self._remap_door_layout_owned_data(
            lambda c, r: None if c == column_index else ((c - 1, r) if c > column_index else (c, r))
        )
        del self.door_layout_columns[column_index]
        self.door_layout_selected_var.set("0:0")
        if not self.door_layout_columns:
            try:
                total_h = float(self.h_var.get())
            except ValueError:
                total_h = ae.H
            self.door_layout_columns = [self._new_door_layout_column(0.0, [total_h], width_auto=True, height_auto=[True])]
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)

    def add_door_layout_height(self, column_index):
        """Compatibility action: promote current auto height; remainder creates the next segment."""
        column = self.door_layout_columns[column_index]
        auto_index = next((i for i, value in enumerate(column["height_auto"]) if value), None)
        if auto_index is not None:
            self.commit_door_layout_height(column_index, auto_index)

    def remove_door_layout_height(self, column_index, row_index):
        column = self.door_layout_columns[column_index]
        if column["height_auto"][row_index]:
            return
        self._remap_door_layout_owned_data(
            lambda c, r: (
                None if c == column_index and r == row_index
                else ((c, r - 1) if c == column_index and r > row_index else (c, r))
            )
        )
        del column["height_vars"][row_index]
        del column["height_auto"][row_index]
        self.door_layout_selected_var.set(f"{column_index}:0")
        self._recompute_door_layout_remainders(rebuild=True)
        self._on_door_layout_value_changed(recompute=False)

    def _on_door_layout_value_changed(self, *, recompute=True):
        if recompute and self.multi_door_enabled_var.get():
            try:
                self._recompute_door_layout_remainders(rebuild=False)
            except Exception:
                pass
        self.refresh_door_layout_status()
        self._request_phase6_update("geometry")

    def _on_total_door_dimension_changed(self):
        if self.multi_door_enabled_var.get() and self.door_layout_columns:
            try:
                self._recompute_door_layout_remainders(rebuild=True)
            except Exception:
                self.refresh_door_layout_status()

    def _request_phase6_update(self, reason="geometry", *, immediate=False, debounce_ms=None):
        """Route a GUI mutation through the one authoritative update scheduler."""
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate(reason)
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is None:
            scheduler = self._phase6_update_scheduler = _Phase6UpdateScheduler(self)
        scheduler.mark_dirty(reason)
        if immediate:
            return scheduler.flush_now()
        if debounce_ms is not None:
            scheduler.request_flush(debounce_ms=debounce_ms)
        return True

    def _flush_phase6_authoritative_state(self):
        """Commit pending GUI mutations before persistence/manufacturing boundaries."""
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is None:
            return False
        return scheduler.flush_now()

    def _on_main_geometry_var_changed(self, reason="geometry"):
        self._phase6_update_scheduler.mark_dirty(reason)

    @staticmethod
    def _receiving_inner_door_stable_id_for_cell(cell_key):
        key = str(cell_key or "").strip()
        if key == "0:0":
            return "upper"
        if key == "0:1":
            return "lower"
        try:
            column, row = (int(v) for v in key.split(":", 1))
        except (TypeError, ValueError):
            raise ValueError(f"invalid door cell key: {cell_key!r}")
        return f"c{column + 1}r{row + 1}"

    def _receiving_inner_door_enabled(self, cell_key):
        key = str(cell_key or "").strip()
        return any(
            isinstance(item, dict) and str(item.get("cell_key") or "").strip() == key
            for item in list(getattr(self, "receiving_inner_doors", []) or [])
        )

    def _receiving_inner_door_inward_offset(self, cell_key):
        key = str(cell_key or "").strip()
        item = next((
            item for item in list(getattr(self, "receiving_inner_doors", []) or [])
            if isinstance(item, dict) and str(item.get("cell_key") or "").strip() == key
        ), None)
        default = cabinet_family_policy.default_inner_door_inward_offset_mm(
            {"model": str(self.baseline_var.get() or "").strip()}, default=0.0
        )
        try:
            return float((item or {}).get("inward_offset_mm", default))
        except (TypeError, ValueError):
            return float(default)

    def _set_receiving_inner_door_inward_offset(self, cell_key, value):
        key = str(cell_key or "").strip()
        offset = float(value)
        if offset < 0:
            raise ValueError("內門內退尺寸不可小於 0")
        found = False
        items = []
        for raw in list(getattr(self, "receiving_inner_doors", []) or []):
            if not isinstance(raw, dict):
                continue
            item = deepcopy(raw)
            if str(item.get("cell_key") or "").strip() == key:
                item["inward_offset_mm"] = offset
                found = True
            items.append(item)
        if not found:
            raise ValueError(f"door cell has no enabled inner door: {key!r}")
        self.receiving_inner_doors = items
        return offset

    def _commit_receiving_inner_door_inward_offset(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_offset_vars", {}) or {}).get(key)
        if var is None:
            return False
        try:
            value = self._set_receiving_inner_door_inward_offset(key, var.get())
        except (TypeError, ValueError):
            var.set(self._fold_designer_number_text(self._receiving_inner_door_inward_offset(key)))
            return False
        var.set(self._fold_designer_number_text(value))
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is not None:
            scheduler.mark_dirty("inner_door_inward_offset")
        if hasattr(self, "canvas_door"):
            try:
                self.draw_door_layout_overview()
            except Exception:
                pass
        return True

    def _set_receiving_inner_door_enabled(self, cell_key, enabled):
        key = str(cell_key or "").strip()
        items = [deepcopy(item) for item in list(getattr(self, "receiving_inner_doors", []) or []) if isinstance(item, dict)]
        existing = next((item for item in items if str(item.get("cell_key") or "").strip() == key), None)
        items = [item for item in items if str(item.get("cell_key") or "").strip() != key]
        if bool(enabled):
            stable_id = str((existing or {}).get("stable_id") or self._receiving_inner_door_stable_id_for_cell(key)).strip()
            item = deepcopy(existing or {})
            default_offset = cabinet_family_policy.default_inner_door_inward_offset_mm(
                {"model": str(self.baseline_var.get() or "").strip()}, default=0.0
            )
            item.update({
                "stable_id": stable_id,
                "cell_key": key,
                "included_frame_sides": list(item.get("included_frame_sides") or ("top", "left", "right")),
                "inward_offset_mm": float(item.get("inward_offset_mm", default_offset)),
            })
            items.append(item)
        def sort_key(item):
            raw = str(item.get("cell_key") or "")
            try:
                return tuple(int(v) for v in raw.split(":", 1))
            except Exception:
                return (10**9, 10**9)
        items.sort(key=sort_key)
        self.receiving_inner_doors = items
        return bool(enabled)

    def _commit_receiving_inner_door_checkbox(self, cell_key):
        key = str(cell_key or "").strip()
        var = dict(getattr(self, "door_layout_inner_door_vars", {}) or {}).get(key)
        enabled = bool(var.get()) if var is not None else False
        self._set_receiving_inner_door_enabled(key, enabled)
        entry = dict(getattr(self, "door_layout_inner_door_offset_entries", {}) or {}).get(key)
        if entry is not None:
            try:
                entry.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except Exception:
                pass
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        scheduler = getattr(self, "_phase6_update_scheduler", None)
        if scheduler is not None:
            scheduler.mark_dirty("inner_door")
        if hasattr(self, "canvas_door"):
            try:
                self.draw_door_layout_overview()
            except Exception:
                pass
        return enabled

    def refresh_door_layout_status(self):
        if not hasattr(self, "door_layout_status_label"):
            return
        if not self.multi_door_enabled_var.get():
            self.door_layout_status_label.config(text="單門模式：沿用左側 W / H", fg=self.COLOR_TEXT_MUTED)
            return
        try:
            width_completion = getattr(self, "_door_layout_width_completion", None)
            if width_completion is not None and not width_completion.valid:
                self.door_layout_status_label.config(
                    text=f"配置待修正：寬度超出 {width_completion.excess:g} mm", fg="#ff9f0a"
                )
                return
            for index, column in enumerate(self.door_layout_columns, start=1):
                completion = column.get("height_completion")
                if completion is not None and not completion.valid:
                    self.door_layout_status_label.config(
                        text=f"配置待修正：欄 {index} 高度超出 {completion.excess:g} mm", fg="#ff9f0a"
                    )
                    return
            cells = self.get_door_layout_cells()
            self.door_layout_status_label.config(
                text=f"配置有效：{len(cells)} 片門｜點選格子可選擇門片", fg="#30d158"
            )
        except Exception as exc:
            self.door_layout_status_label.config(text=f"配置待修正：{exc}", fg="#ff9f0a")

    def rebuild_door_layout_ui(self):
        if not hasattr(self, "door_layout_columns_frame"):
            return
        for widget in self.door_layout_columns_frame.winfo_children():
            widget.destroy()
        self.door_layout_inner_door_vars = {}
        self.door_layout_inner_door_offset_vars = {}
        self.door_layout_inner_door_offset_entries = {}
        self._ensure_door_layout_default()

        for column_index, column in enumerate(self.door_layout_columns):
            col_frame = tk.Frame(self.door_layout_columns_frame, bg=self.COLOR_PANEL, bd=1, relief=tk.SOLID)
            col_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=3, pady=3)

            width_row = tk.Frame(col_frame, bg=self.COLOR_PANEL)
            width_row.pack(fill=tk.X, padx=4, pady=(4, 2))
            width_caption = f"欄 {column_index+1} 寬" + (" (自動)" if column.get("width_auto") else "")
            tk.Label(
                width_row, text=width_caption, bg=self.COLOR_PANEL,
                fg="#30d158" if column.get("width_auto") else self.COLOR_TEXT,
                font=('Microsoft JhengHei', 8, 'bold')
            ).pack(anchor=tk.CENTER)
            width_entry = tk.Entry(
                width_row, textvariable=column["width_var"], width=8,
                bg=self.COLOR_INPUT_BG, fg="#30d158" if column.get("width_auto") else self.COLOR_TEXT,
                insertbackground=self.COLOR_TEXT, font=('Consolas', 10, 'bold'), justify=tk.CENTER
            )
            width_entry.pack(anchor=tk.CENTER, pady=2)
            width_entry.bind("<FocusOut>", lambda e, c=column_index: self.commit_door_layout_width(c))
            width_entry.bind("<Return>", lambda e, c=column_index: self.commit_door_layout_width(c))

            tk.Label(
                col_frame, text="高度 ↓", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED,
                font=('Microsoft JhengHei', 8)
            ).pack(anchor=tk.CENTER, pady=(2, 0))

            for row_index, (height_var, is_auto) in enumerate(zip(column["height_vars"], column["height_auto"])):
                height_row = tk.Frame(col_frame, bg=self.COLOR_PANEL)
                height_row.pack(fill=tk.X, padx=4, pady=1)
                tk.Label(
                    height_row, text=f"{row_index+1}", width=2, bg=self.COLOR_PANEL,
                    fg="#30d158" if is_auto else self.COLOR_TEXT_MUTED, font=('Consolas', 8, 'bold')
                ).pack(side=tk.LEFT)
                height_entry = tk.Entry(
                    height_row, textvariable=height_var, width=7,
                    bg=self.COLOR_INPUT_BG, fg="#30d158" if is_auto else self.COLOR_TEXT,
                    insertbackground=self.COLOR_TEXT, font=('Consolas', 10), justify=tk.CENTER
                )
                height_entry.pack(side=tk.LEFT, padx=2)
                height_entry.bind(
                    "<FocusOut>", lambda e, c=column_index, r=row_index: self.commit_door_layout_height(c, r)
                )
                height_entry.bind(
                    "<Return>", lambda e, c=column_index, r=row_index: self.commit_door_layout_height(c, r)
                )
                if is_auto:
                    tk.Label(
                        height_row, text="自動", bg=self.COLOR_PANEL, fg="#30d158",
                        font=('Microsoft JhengHei', 7, 'bold')
                    ).pack(side=tk.LEFT, padx=(1, 0))
                else:
                    tk.Button(
                        height_row, text="−", width=2,
                        command=lambda c=column_index, r=row_index: self.remove_door_layout_height(c, r),
                        bg=self.COLOR_BG, fg="#ff6b6b", bd=1, relief=tk.SOLID,
                        activebackground=self.COLOR_PANEL, activeforeground="#ff6b6b"
                    ).pack(side=tk.LEFT, padx=(1, 0))

                if str(self.baseline_var.get() or "").strip() == "受電箱":
                    cell_key = f"{column_index}:{row_index}"
                    inner_var = tk.BooleanVar(
                        master=self.root,
                        value=self._receiving_inner_door_enabled(cell_key),
                    )
                    self.door_layout_inner_door_vars[cell_key] = inner_var
                    tk.Checkbutton(
                        height_row, text="內門", variable=inner_var,
                        bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                        activebackground=self.COLOR_PANEL, activeforeground=self.COLOR_ACCENT,
                        font=('Microsoft JhengHei', 8, 'bold'), cursor="hand2",
                        command=lambda key=cell_key: self._commit_receiving_inner_door_checkbox(key),
                    ).pack(side=tk.LEFT, padx=(5, 0))
                    offset_var = tk.StringVar(
                        master=self.root,
                        value=self._fold_designer_number_text(self._receiving_inner_door_inward_offset(cell_key)),
                    )
                    self.door_layout_inner_door_offset_vars[cell_key] = offset_var
                    tk.Label(
                        height_row, text="內退", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED,
                        font=('Microsoft JhengHei', 7, 'bold')
                    ).pack(side=tk.LEFT, padx=(3, 1))
                    offset_entry = tk.Entry(
                        height_row, textvariable=offset_var, width=5,
                        state=tk.NORMAL if inner_var.get() else tk.DISABLED,
                        bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, disabledforeground=self.COLOR_TEXT_MUTED,
                        insertbackground=self.COLOR_TEXT, font=('Consolas', 9), justify=tk.CENTER
                    )
                    offset_entry.pack(side=tk.LEFT, padx=(0, 1))
                    offset_entry.bind(
                        "<FocusOut>", lambda e, key=cell_key: self._commit_receiving_inner_door_inward_offset(key)
                    )
                    offset_entry.bind(
                        "<Return>", lambda e, key=cell_key: self._commit_receiving_inner_door_inward_offset(key)
                    )
                    self.door_layout_inner_door_offset_entries[cell_key] = offset_entry
                    tk.Label(
                        height_row, text="mm", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED,
                        font=('Consolas', 7)
                    ).pack(side=tk.LEFT)

            if not column.get("width_auto"):
                tk.Button(
                    col_frame, text="刪除此欄", command=lambda c=column_index: self.remove_door_layout_column(c),
                    bg=self.COLOR_BG, fg="#ff6b6b", bd=1, relief=tk.SOLID,
                    activebackground=self.COLOR_PANEL, activeforeground="#ff6b6b",
                    font=('Microsoft JhengHei', 8, 'bold')
                ).pack(anchor=tk.CENTER, pady=(3, 4))

        self.refresh_door_layout_status()

    def setup_tab_door_ui(self):
        # Door 第一頁只保留「啟用多門配置」；其餘編輯都直接在 Canvas / 開孔 editor。
        top_ctrl = tk.Frame(self.tab_door, bg=self.COLOR_BG)
        top_ctrl.pack(fill=tk.X, padx=10, pady=5)
        tk.Checkbutton(
            top_ctrl, text="啟用多門配置", variable=self.multi_door_enabled_var,
            bg=self.COLOR_BG, fg=self.COLOR_TEXT, selectcolor=self.COLOR_PANEL,
            activebackground=self.COLOR_BG, activeforeground=self.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9, 'bold'), cursor="hand2",
            command=self.toggle_multi_door_layout,
        ).pack(side=tk.LEFT, padx=5)
        self.door_layout_status_label = tk.Label(
            top_ctrl, text="", bg=self.COLOR_BG, fg=self.COLOR_TEXT_MUTED,
            font=('Microsoft JhengHei', 8, 'bold')
        )
        # 狀態 label 只留作既有邏輯相容，不 pack、不佔畫面。

        self.door_layout_body = tk.Frame(self.tab_door, bg=self.COLOR_PANEL, bd=1, relief=tk.SOLID)
        self.door_layout_columns_frame = tk.Frame(self.door_layout_body, bg=self.COLOR_PANEL)
        self.door_layout_columns_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
        layout_actions = tk.Frame(self.door_layout_body, bg=self.COLOR_PANEL)
        layout_actions.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(
            layout_actions,
            text="寬度由左→右；高度由上→下。綠色『自動』格是剩餘尺寸，直接修改它就會固定並自動補下一格。",
            bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 8)
        ).pack(side=tk.LEFT, padx=8)
        self._ensure_door_layout_default()
        self.rebuild_door_layout_ui()
        # 預設單門模式，不顯示多門明細。
        self.door_layout_body.pack_forget()
        
        # 門指示燈選項面板 (預設隱藏)
        self.door_indicator_opts_frame = tk.Frame(self.tab_door, bg=self.COLOR_BG)
        
        door_ind_ctrl = tk.Frame(self.door_indicator_opts_frame, bg=self.COLOR_BG)
        door_ind_ctrl.pack(fill=tk.X, pady=2)
        
        lbl_door_grid = tk.Label(door_ind_ctrl, text="指示燈層數 (3個為一層) :", bg=self.COLOR_BG, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 10, 'bold'))
        lbl_door_grid.pack(side=tk.LEFT, padx=5)
        
        self.cb_door_ind_l = ttk.Combobox(door_ind_ctrl, textvariable=self.door_indicator_l_var, values=["1", "2", "3", "4", "5", "6"], width=6, state="readonly", style='TCombobox')
        self.cb_door_ind_l.pack(side=tk.LEFT, padx=2)
        self.cb_door_ind_l.bind("<<ComboboxSelected>>", lambda e: self.on_door_layers_count_changed())
        
        btn_reset_pos_x = tk.Button(
            door_ind_ctrl,
            text="左右置中",
            font=('Microsoft JhengHei', 9, 'bold'),
            bg=self.COLOR_PANEL, fg=self.COLOR_ACCENT, bd=1, relief=tk.SOLID,
            activebackground=self.COLOR_BG, activeforeground=self.COLOR_ACCENT,
            cursor="hand2", padx=10,
            command=self.reset_door_indicator_offset_x
        )
        btn_reset_pos_x.pack(side=tk.LEFT, padx=10)
        
        btn_reset_pos_y = tk.Button(
            door_ind_ctrl,
            text="上下置中",
            font=('Microsoft JhengHei', 9, 'bold'),
            bg=self.COLOR_PANEL, fg=self.COLOR_ACCENT, bd=1, relief=tk.SOLID,
            activebackground=self.COLOR_BG, activeforeground=self.COLOR_ACCENT,
            cursor="hand2", padx=10,
            command=self.reset_door_indicator_offset_y
        )
        btn_reset_pos_y.pack(side=tk.LEFT, padx=10)
        
        self.chk_box_dist = tk.Checkbutton(
            door_ind_ctrl,
            text="箱體定位距離",
            variable=self.is_box_dist_var,
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT,
            selectcolor=self.COLOR_PANEL,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9, 'bold'),
            cursor="hand2",
            command=self.update_calculations
        )
        self.chk_box_dist.pack(side=tk.LEFT, padx=15)
        
        # 每層組數配置
        self.door_layers_config_frame = tk.Frame(self.door_indicator_opts_frame, bg=self.COLOR_PANEL)
        self.door_layers_config_frame.pack(fill=tk.X, padx=10, pady=2)
        
        self.rebuild_door_layers_config_ui()
        
        # 畫布 Frame
        canvas_frame = tk.Frame(self.tab_door, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        self.door_canvas_frame = canvas_frame
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # 門畫布
        self.canvas_door = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        self.canvas_door.pack(fill=tk.BOTH, expand=True)
        self.canvas_door.bind("<Configure>", lambda e: self.draw_preview())
        self.canvas_door.bind("<Button-1>", self.on_door_canvas_press)
        self.canvas_door.bind("<B1-Motion>", self.on_door_canvas_drag)
        self.canvas_door.bind("<ButtonRelease-1>", self.on_door_canvas_release)
        self._attach_part_hole_entrypoint(self.canvas_door, "door", allow_double=True)
        # 覆寫通用雙擊：單門開 Door editor；多門由格子 tag 精準處理並阻止重複開窗。
        self.canvas_door.bind("<Double-Button-1>", self.on_door_canvas_double_click)

    def setup_tab_indicator_box_ui(self):
        # 頂部控制列
        top_ctrl = tk.Frame(self.tab_indicator_box, bg=self.COLOR_BG)
        top_ctrl.pack(fill=tk.X, padx=10, pady=5)
        
        self.chk_indicator_box_enabled = tk.Checkbutton(
            top_ctrl, text="門板預留指示燈盒開孔", variable=self.is_indicator_box_var,
            bg=self.COLOR_BG, fg=self.COLOR_TEXT, selectcolor=self.COLOR_PANEL,
            activebackground=self.COLOR_BG, activeforeground=self.COLOR_ACCENT,
            font=('Microsoft JhengHei', 9, 'bold'), cursor="hand2",
            command=self.on_indicator_box_toggle,
        )
        self.chk_indicator_box_enabled.pack(side=tk.LEFT, padx=(5, 14))

        # 層數選擇
        lbl_grid = tk.Label(top_ctrl, text="指示燈層數 (3個為一層) :", bg=self.COLOR_BG, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 10, 'bold'))
        lbl_grid.pack(side=tk.LEFT, padx=5)
        
        self.cb_ib_l = ttk.Combobox(top_ctrl, textvariable=self.indicator_l_var, values=["1", "2", "3", "4", "5", "6"], width=6, state="readonly", style='TCombobox')
        self.cb_ib_l.pack(side=tk.LEFT, padx=2)
        self.cb_ib_l.bind("<<ComboboxSelected>>", lambda e: self.on_layers_count_changed())
        
        # 說明標籤
        lbl_formula = ttk.Label(top_ctrl, text="公式：W=171+90*(g_max-1)+135 (單組W=326) / H=280*(L-1)+445 | 線槽跨距 100", style='TLabel')
        lbl_formula.pack(side=tk.RIGHT, padx=5)
        
        # 每層組數的配置區域 (動態 Frame)
        self.layers_config_frame = tk.Frame(self.tab_indicator_box, bg=self.COLOR_PANEL)
        self.layers_config_frame.pack(fill=tk.X, padx=10, pady=2)
        
        # 畫布 Frame
        canvas_frame = tk.Frame(self.tab_indicator_box, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # 畫布
        self.canvas_indicator_box = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        self.canvas_indicator_box.pack(fill=tk.BOTH, expand=True)
        self.canvas_indicator_box.bind("<Configure>", lambda e: self.draw_preview())
        self._attach_part_hole_entrypoint(self.canvas_indicator_box, "indicator_box", allow_double=True)
        
        # 初始化動態組數選單
        self.rebuild_layers_config_ui()

    def on_layers_count_changed(self):
        self.rebuild_layers_config_ui()
        self._request_phase6_update("geometry")

    def rebuild_layers_config_ui(self):
        # 清空先前的元件
        for widget in self.layers_config_frame.winfo_children():
            widget.destroy()
            
        try:
            layers = int(self.indicator_l_var.get())
        except ValueError:
            layers = 3
            
        # 逐層建立橫向的組數選擇選單
        for ly in range(layers):
            ly_frame = tk.Frame(self.layers_config_frame, bg=self.COLOR_PANEL)
            ly_frame.pack(side=tk.LEFT, padx=15, pady=4)
            
            label_text = f"第 {ly+1} 層組數:"
            if ly == 0:
                label_text = "第 1 層 (底) 組數:"
            elif ly == layers - 1 and layers > 1:
                label_text = f"第 {ly+1} 層 (頂) 組數:"
                
            tk.Label(ly_frame, text=label_text, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')).pack(side=tk.LEFT, padx=2)
            
            cb = ttk.Combobox(ly_frame, textvariable=self.indicator_layer_g_vars[ly], values=["1", "2", "3", "4", "5", "6", "7", "8"], width=4, state="readonly", style='TCombobox')
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self._request_phase6_update("geometry"))



    def draw_indicator_box(self, val):
        canvas = self.canvas_indicator_box
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        try:
            count = max(1, int(self.indicator_l_var.get()))
            layer_groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(count))
            spec = self._indicator_box_part_spec(
                val, layer_groups, features=self.surface_features["indicator_box"]
            )
            render_data = self._authoritative_render_data(
                spec, self._manufacturing_context(draw_stock=False)
            )
            minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
            blank_w = maxx - minx
            blank_h = maxy - miny
            box_baseline_label = ae.indicator_shared_baseline_source_label("盒子.dxf")
        except Exception as exc:
            canvas.create_text(
                cw/2, ch/2, text=f"指示燈盒 Final Part Geometry 載入失敗:\n{exc}",
                fill="#ff3333", font=('Microsoft JhengHei', 11, 'bold')
            )
            return

        canvas_transform, left, bottom, scale, _material_top = _phase6_2d_material_viewport(
            (minx, miny, maxx, maxy), cw, ch
        )

        if self.draw_stock_var.get():
            sx0, sy0 = canvas_transform.world_to_canvas(Vec2(minx, miny))
            sx1, sy1 = canvas_transform.world_to_canvas(Vec2(maxx, maxy))
            canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4)
            )

        render_drawing_scene(
            canvas, render_data.scene, canvas_transform,
            skip_layers=("CHECK", "STOCK"),
        )

        canvas.create_text(
            cw / 2, bottom - blank_h * scale - 20,
            text=f"W = {blank_w:.2f} mm", fill="#30d158", font=('Consolas', 10, 'bold')
        )
        canvas.create_text(
            left + blank_w * scale + 45, bottom - (blank_h * scale) / 2,
            text=f"H = {blank_h:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold'), angle=90
        )
        stock_hint = "  STOCK 母材外框: 青色虛線" if self.draw_stock_var.get() else ""
        canvas.create_text(
            25, 25, anchor=tk.NW,
            text=(
                f"指示燈盒子展開預覽｜{box_baseline_label}｜Final Part Geometry\n"
                f"CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
                f"折彎線 (BEND): 藍色虛線{stock_hint}\n"
                f"排列 {list(layer_groups)}，共 {sum(layer_groups)} 顆指示燈"
            ),
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )
        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=False)

    def _normalize_door_indicator_state(self, state):
        raw = dict(state or {})
        mode = raw.get("mode")
        if mode not in {"none", "indicator", "indicator_box"}:
            if raw.get("box_enabled"):
                mode = "indicator_box"
            elif raw.get("enabled"):
                mode = "indicator"
            else:
                mode = "none"
        try:
            layers = max(1, min(6, int(raw.get("layers", 1))))
        except (TypeError, ValueError):
            layers = 1
        groups = list(raw.get("groups", [2] * 6))
        while len(groups) < 6:
            groups.append(2)
        normalized_groups = []
        for value in groups[:6]:
            try:
                normalized_groups.append(max(1, int(value)))
            except (TypeError, ValueError):
                normalized_groups.append(2)
        return {
            "mode": mode,
            "enabled": mode == "indicator",
            "box_enabled": mode == "indicator_box",
            "layers": layers,
            "groups": normalized_groups,
            "offset_x": float(raw.get("offset_x", 0.0) or 0.0),
            "offset_y": float(raw.get("offset_y", 0.0) or 0.0),
            "is_box_dist": bool(raw.get("is_box_dist", False)),
        }

    def _door_layout_indicator_state_for_key(self, key):
        state = self.door_layout_indicator_states.get(key)
        normalized = self._normalize_door_indicator_state(state)
        if state is None:
            state = normalized
            self.door_layout_indicator_states[key] = state
        else:
            state.clear()
            state.update(normalized)
        return state

    def _destroy_door_layout_entry_widgets(self):
        for widget in list(self.door_layout_width_entries.values()) + list(self.door_layout_height_entries.values()):
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self.door_layout_width_entries = {}
        self.door_layout_height_entries = {}
        self.door_layout_entry_windows = []

    def _door_layout_entry_menu(self, entry, *, column_index, row_index=None):
        menu = tk.Menu(entry, tearoff=False)
        if row_index is None:
            column = self.door_layout_columns[column_index]
            if not column.get("width_auto", False):
                menu.add_command(label="刪除此欄", command=lambda: self.remove_door_layout_column(column_index))
        else:
            column = self.door_layout_columns[column_index]
            if not column["height_auto"][row_index]:
                menu.add_command(label="刪除此層", command=lambda: self.remove_door_layout_height(column_index, row_index))
        if menu.index("end") is not None:
            entry.bind("<Button-3>", lambda e, m=menu: (m.tk_popup(e.x_root, e.y_root), "break")[1])

    @staticmethod
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
            layer = getattr(feature, "layer", "CUTTING")
            color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(layer, "#ff9f0a")
            tags = ("door_layout_feature", tag)
            if isinstance(feature, ResolvedCircle):
                cx, cy = pt(feature.center)
                r = max(2.0, feature.radius * scale)
                canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=2, tags=tags)
                if feature.add_centerline:
                    canvas.create_line(cx-r, cy, cx+r, cy, fill="#bf5af2", width=1, tags=tags)
            elif isinstance(feature, ResolvedRect):
                coords = []
                for p in feature.points:
                    coords.extend(pt(p))
                canvas.create_polygon(*coords, outline=color, fill="", width=2, tags=tags)
            elif isinstance(feature, ResolvedProfile):
                coords = []
                for p in feature.points:
                    coords.extend(pt(p))
                if len(coords) >= 6:
                    canvas.create_polygon(*coords, outline=color, fill="", width=2, tags=tags)
                for sub_layer, points, closed in getattr(feature, "layered_profiles", ()):
                    sub_color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(sub_layer, color)
                    sub = []
                    for p in points:
                        sub.extend(pt(p))
                    if len(sub) >= 4:
                        if closed and len(sub) >= 6:
                            canvas.create_polygon(*sub, outline=sub_color, fill="", width=1, tags=tags)
                        else:
                            canvas.create_line(*sub, fill=sub_color, width=1, tags=tags)

    @staticmethod
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
            if primitive.layer in {"BEND", "CHECK", "STOCK"}:
                continue
            if isinstance(primitive, PolylinePrimitive) and primitive.layer == "CUTTING" and primitive.closed and not skipped_outline:
                skipped_outline = True
                continue
            color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(primitive.layer, "#64d2ff")
            tags = ("door_layout_baseline", tag)
            if isinstance(primitive, CirclePrimitive):
                cx, cy = pt(primitive.center)
                r = max(1.5, primitive.radius * scale)
                canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=1.5, tags=tags)
            elif isinstance(primitive, LinePrimitive):
                a = pt(primitive.p1); b = pt(primitive.p2)
                canvas.create_line(*a, *b, fill=color, width=1.2, tags=tags)
            elif isinstance(primitive, PolylinePrimitive):
                coords = []
                for p in primitive.points:
                    coords.extend(pt(p))
                if len(coords) >= 4:
                    if primitive.closed and len(coords) >= 6:
                        canvas.create_polygon(*coords, outline=color, fill="", width=1.2, tags=tags)
                    else:
                        canvas.create_line(*coords, fill=color, width=1.2, tags=tags)

    def _door_layout_cell_result(self, cell, val=None):
        val = val or self.get_float_values()
        return build_door_result(
            w=cell.start_width, h=cell.start_height, t=val['t'],
            fw=self._door_material_frame_width(val['fw'], val['t']),
            gap_w=val['door_gap_w'], gap_h=val['door_gap_h'],
            fold_left=val['door_fold_l'], fold_right=val['door_fold_r'],
            fold_top=val['door_fold_t'], fold_bottom=val['door_fold_b'],
            frame_edges=cell.edges,
        )

    def _door_layout_cell_resolved_features(self, cell, result, key):
        resolved = []
        features = self.door_layout_features.setdefault(key, [])
        if features:
            surface = feature_surface_from_structural_result("door", result)
            try:
                resolved.extend(resolve_surface_features(surface, features, result.width, result.height))
            except ValueError:
                pass
        state = self._door_layout_indicator_state_for_key(key)
        mode = state.get("mode", "indicator" if state.get("enabled") else "none")
        if mode in {"indicator", "indicator_box"}:
            try:
                material_fw = self._door_material_frame_width(
                    self.fw_z_var.get(), self.t_var.get()
                )
                finished_w, finished_h = ae.calculate_door_finished_size(
                    cell.start_width, cell.start_height, material_fw,
                    self.door_gap_w_var.get(), self.door_gap_h_var.get(), self.t_var.get(),
                    frame_edges=cell.edges,
                )
                context = DoorIndicatorContext(
                    finished_width=float(finished_w), finished_height=float(finished_h),
                    left_fold=float(self.door_fold_l_var.get()), bottom_fold=float(self.door_fold_b_var.get()),
                )
                groups = tuple(int(v) for v in state.get("groups", [2])[:int(state.get("layers", 1))])
                if mode == "indicator":
                    layout = resolve_door_indicator_layout(
                        context, groups,
                        Vec2(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
                    )
                    resolved.extend(layout.features)
                else:
                    hole_w, hole_h = manufacturing_api.indicator_box_opening_size(groups, thickness=float(self.t_var.get()))
                    resolved.append(ResolvedRect(
                        center=Vec2(
                            context.left_fold + context.finished_width / 2.0 + float(state.get("offset_x", 0.0)),
                            context.bottom_fold + context.finished_height / 2.0 + float(state.get("offset_y", 0.0)),
                        ),
                        width=hole_w, height=hole_h, layer="CUTTING", source_type="indicator_box_opening",
                    ))
            except Exception:
                pass
        return resolved

    def _door_layout_baseline_scene(self, cell, val):
        model = self._baseline_source_model()
        if not model or not ae.has_baseline_part(model, "門.dxf"):
            return None, ae.baseline_source_label("", "門.dxf")
        source_fp = ae.baseline_source_fingerprint(ae.baseline_expected_path(model, "門.dxf"))
        cache_key = (
            source_fp, model, float(cell.start_width), float(cell.start_height), float(val['t']), float(val['fw']),
            float(val['door_gap_w']), float(val['door_gap_h']),
            float(val['door_fold_l']), float(val['door_fold_r']), float(val['door_fold_t']), float(val['door_fold_b']),
            bool(cell.edges.left), bool(cell.edges.right), bool(cell.edges.top), bool(cell.edges.bottom),
        )
        if cache_key in self._door_layout_baseline_cache:
            return self._door_layout_baseline_cache[cache_key], ae.baseline_source_label(model, "門.dxf")
        try:
            material_fw = self._door_material_frame_width(
                val['fw'], val['t'], model_name=model
            )
            data = ae.get_stretched_door_data(
                model, cell.start_width, cell.start_height, val['t'], material_fw,
                val['door_gap_w'], val['door_gap_h'],
                val['door_fold_l'], val['door_fold_r'], val['door_fold_t'], val['door_fold_b'],
                frame_edges=cell.edges,
            )
            self._door_layout_baseline_cache[cache_key] = data.scene
            return data.scene, ae.baseline_source_label(model, "門.dxf")
        except Exception:
            return None, "未使用基準檔（程式計算生成）"

    def open_door_indicator_component_editor(self, key, component):
        state = self._door_layout_indicator_state_for_key(key)
        if state.get("mode") != "indicator_box":
            return
        try:
            val = self.get_float_values()
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = [int(v) for v in list(state.get("groups", [2] * 6))[:layers]]
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return

        if component == "indicator_box":
            box_corner_policy = None
            data = ae.get_stretched_indicator_box_data(
                "指示燈", groups, val['t'], corner_policy=None
            )
            baseline_scene = data.scene
            status = ae.indicator_shared_baseline_source_label("盒子.dxf")
            surface = feature_surface_from_drawing_scene("indicator_box", data.scene)
            width, height = data.params['w'], data.params['h']
            fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
            result = (
                build_unknown_indicator_box_result(
                    total_width=width, total_height=height, t=val['t'], fold=fold,
                    corner_policy=box_corner_policy,
                ) if box_corner_policy is not None else
                build_indicator_box_result(total_width=width, total_height=height, t=val['t'], fold=fold)
            )
            guide = build_finished_reference_guide(
                "indicator_box", result, finished_width=width - 2.0 * fold + val['t'],
                finished_height=height - 2.0 * fold + val['t'],
            )
            feature_store = self.door_layout_indicator_box_features.setdefault(key, [])
            title = "指示燈盒子"
        elif component == "indicator_door":
            t = val['t']; fw = val['fw']; gw = val['door_gap_w']; gh = val['door_gap_h']
            policy = replace(
                manufacturing_api.resolve_policy(),
                frame_width=float(fw), door_gap_w=float(gw), door_gap_h=float(gh),
                indicator_small_door_fold=float(getattr(ae, 'indicator_small_door_fold_def', 19.0)),
            )
            indicator_ctx = ManufacturingContext(policy=policy)
            door_spec = manufacturing_api.indicator_small_door_spec(
                groups, thickness=t, context=indicator_ctx
            )
            finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec, indicator_ctx)
            source_w, source_h = door_spec.width, door_spec.height
            data = ae.get_stretched_door_data(
                None, source_w, source_h, t, fw, gw, gh,
                door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
                indicator_window_groups=groups,
            )
            surface = feature_surface_from_drawing_scene("indicator_door", data.scene)
            width, height = data.params['total_width'], data.params['total_depth']
            result = build_door_result(
                w=source_w, h=source_h, t=t, fw=fw, gap_w=gw, gap_h=gh,
                fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0,
            )
            guide = build_finished_reference_guide(
                "indicator_door", result, finished_width=finished_w, finished_height=finished_h,
            )
            feature_store = self.door_layout_indicator_door_features.setdefault(key, [])
            baseline_scene = data.scene
            status = ae.indicator_shared_baseline_source_label("小門.dxf")
            title = "指示燈小門"
        else:
            return

        self._open_unified_hole_editor(
            component, f"{title} [{key}]", surface, width, height,
            reference_guide=guide, feature_list_override=feature_store,
            baseline_scene=baseline_scene, baseline_status_text=status,
            on_close=self.draw_door_layout_overview,
        )

    def open_door_layout_cell_editor(self, column_index, row_index):
        """Open the unified Door hole editor for exactly one multi-door layout cell."""
        existing = getattr(self, "last_unified_hole_editor", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        self.door_layout_selected_var.set(f"{int(column_index)}:{int(row_index)}")
        cell = self.get_selected_door_layout_cell()
        key = self._door_layout_cell_key(cell)
        try:
            val = self.get_float_values()
            result = self._door_layout_cell_result(cell, val)
            surface = feature_surface_from_structural_result("door", result)
            material_fw = self._door_material_frame_width(val['fw'], val['t'])
            finished_w, finished_h = ae.calculate_door_finished_size(
                cell.start_width, cell.start_height, material_fw, val['door_gap_w'], val['door_gap_h'], val['t'],
                frame_edges=cell.edges,
            )
            reference_guide = build_finished_reference_guide(
                "door", result, finished_width=finished_w, finished_height=finished_h,
            )
        except Exception as exc:
            messagebox.showerror("開孔失敗", str(exc))
            return
        features = self.door_layout_features.setdefault(key, [])
        indicator_state = self._door_layout_indicator_state_for_key(key)
        indicator_context = DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=val['door_fold_l'], bottom_fold=val['door_fold_b'],
        )
        baseline_scene, baseline_status = self._door_layout_baseline_scene(cell, val)
        self._open_unified_hole_editor(
            "door", f"門板 C{cell.column_index+1}-R{cell.row_index+1}",
            surface, result.width, result.height,
            reference_guide=reference_guide,
            feature_list_override=features,
            door_indicator_state=indicator_state,
            door_indicator_context=indicator_context,
            door_indicator_commit=lambda state, key=key: self._apply_multi_door_indicator_state(key, state),
            door_frame_edges=cell.edges, door_gap_w=val['door_gap_w'], door_gap_h=val['door_gap_h'],
            door_frame_width=val['fw'], door_thickness=val['t'],
            on_close=self.draw_door_layout_overview,
            baseline_scene=baseline_scene, baseline_status_text=baseline_status,
            indicator_component_context_provider=lambda state, key=key, val=val: self._indicator_component_editor_contexts(
                state, val,
                box_features=self.door_layout_indicator_box_features.setdefault(key, []),
                door_features=self.door_layout_indicator_door_features.setdefault(key, []),
            ),
        )

    def draw_door_layout_overview(self):
        """Draw the whole Door partition; dimensions are editable around the cells, cells only show holes."""
        self._sync_door_canvas_double_click_binding()
        canvas = self.canvas_door
        self._destroy_door_layout_entry_widgets()
        canvas.delete("all")
        self.door_layout_cell_items = {}
        self.door_layout_cell_bounds = {}

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        try:
            total_w = float(self.w_var.get())
            total_h = float(self.h_var.get())
            columns = self.get_door_layout_columns()
            cells = self.get_door_layout_cells()
            val = self.get_float_values()
        except Exception as exc:
            canvas.create_text(
                cw / 2, ch / 2, text=f"多門配置無效:\n{exc}", fill="#ff9f0a",
                font=('Microsoft JhengHei', 11, 'bold'), width=max(240, cw - 80),
            )
            return

        # Extra top/left space is only for direct dimension Entry widgets, not a separate panel.
        left_margin, right_margin = 58.0, 24.0
        top_margin, bottom_margin = 48.0, 24.0
        avail_w = max(1.0, cw - left_margin - right_margin)
        avail_h = max(1.0, ch - top_margin - bottom_margin)
        scale = min(avail_w / total_w, avail_h / total_h)
        draw_w = total_w * scale
        draw_h = total_h * scale
        x0 = left_margin + (avail_w - draw_w) / 2.0
        y0 = top_margin + (avail_h - draw_h) / 2.0
        selected_key = self.door_layout_selected_var.get()

        cell_map = {(cell.column_index, cell.row_index): cell for cell in cells}
        x_cursor = x0
        for column_index, (column_w, heights) in enumerate(columns):
            col_px = column_w * scale
            column = self.door_layout_columns[column_index]
            width_entry = tk.Entry(
                canvas, textvariable=column["width_var"], width=9,
                bg=self.COLOR_INPUT_BG,
                fg="#30d158" if column.get("width_auto") else self.COLOR_TEXT,
                insertbackground=self.COLOR_TEXT, font=('Consolas', 13, 'bold'), justify=tk.CENTER,
                bd=1, relief=tk.SOLID,
            )
            width_entry.bind("<FocusOut>", lambda e, c=column_index: self.commit_door_layout_width(c))
            width_entry.bind("<Return>", lambda e, c=column_index: self.commit_door_layout_width(c))
            self._door_layout_entry_menu(width_entry, column_index=column_index)
            win = canvas.create_window(x_cursor + col_px / 2.0, y0 - 24, window=width_entry, anchor=tk.CENTER,
                                       tags=("door_layout_dimension", "door_layout_width_entry"))
            self.door_layout_width_entries[column_index] = width_entry
            self.door_layout_entry_windows.append(win)

            y_cursor = y0
            for row_index, segment_h in enumerate(heights):
                row_px = segment_h * scale
                x1, y1 = x_cursor, y_cursor
                x2, y2 = x_cursor + col_px, y_cursor + row_px
                key = f"{column_index}:{row_index}"
                selected = key == selected_key
                outline = self.COLOR_ACCENT if selected else "#30d158"
                width = 3 if selected else 2
                tag = f"door_layout_cell_{column_index}_{row_index}"
                rect = canvas.create_rectangle(
                    x1, y1, x2, y2, outline=outline, width=width,
                    tags=("door_layout_cell", tag),
                )
                self.door_layout_cell_items[key] = rect
                self.door_layout_cell_bounds[key] = (x1, y1, x2, y2)

                height_entry = tk.Entry(
                    canvas, textvariable=column["height_vars"][row_index], width=9,
                    bg=self.COLOR_INPUT_BG,
                    fg="#30d158" if column["height_auto"][row_index] else self.COLOR_TEXT,
                    insertbackground=self.COLOR_TEXT, font=('Consolas', 13, 'bold'), justify=tk.CENTER,
                    bd=1, relief=tk.SOLID,
                )
                height_entry.bind("<FocusOut>", lambda e, c=column_index, r=row_index: self.commit_door_layout_height(c, r))
                height_entry.bind("<Return>", lambda e, c=column_index, r=row_index: self.commit_door_layout_height(c, r))
                self._door_layout_entry_menu(height_entry, column_index=column_index, row_index=row_index)
                # Keep the dimension control on the edge so the cell interior remains available for holes.
                hwin = canvas.create_window(x1 + 4, (y1 + y2) / 2.0, window=height_entry, anchor=tk.W,
                                            tags=("door_layout_dimension", "door_layout_height_entry"))
                self.door_layout_height_entries[(column_index, row_index)] = height_entry
                self.door_layout_entry_windows.append(hwin)

                cell = cell_map[(column_index, row_index)]
                result = self._door_layout_cell_result(cell, val)
                baseline_scene, _baseline_status = self._door_layout_baseline_scene(cell, val)
                self._draw_layout_baseline_secondary(
                    canvas, baseline_scene, result.width, result.height, (x1, y1, x2, y2),
                    f"door_layout_baseline_{column_index}_{row_index}",
                )
                resolved = self._door_layout_cell_resolved_features(cell, result, key)
                self._draw_layout_resolved_features(
                    canvas, resolved, result.width, result.height, (x1, y1, x2, y2),
                    f"door_layout_feature_{column_index}_{row_index}",
                )

                # Mouse interaction is handled by canvas-level coordinate hit-testing so the
                # whole cell interior is clickable even though the rectangle has no fill.
                y_cursor = y2
            x_cursor += col_px

        baseline_model = self._baseline_source_model() or ""
        baseline_status = ae.baseline_source_label(baseline_model, "門.dxf")
        canvas.create_text(
            10, 10, anchor=tk.NW, text=baseline_status,
            fill=("#64d2ff" if baseline_status.startswith("基準檔：") else "#ff9f0a"),
            font=('Microsoft JhengHei', 9, 'bold'), tags=("door_baseline_status",),
        )
        canvas.create_text(
            10, 30, anchor=tk.NW,
            text="各欄獨立分層：修改該欄綠色『自動』高度即可新增下一層（例 2 / 3 / 2）",
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9, 'bold'),
            tags=("door_layout_asymmetric_hint",),
        )

        self._draw_door_layout_dividers_and_frames(canvas, scale, x0, y0, columns, cells, val)

        self.last_door_layout_overview = {
            "columns": columns, "cell_count": len(cells), "selected": selected_key,
            "scale": scale, "origin": (x0, y0),
        }

    def _draw_door_layout_dividers_and_frames(self, canvas, scale, x0, y0, columns, cells, val):
        """Render derived parts from the authoritative assembly placement owner."""
        t_val = float(val.get('t', 2.0))
        snapshot = self._compose_phase6_project_snapshot_from_main_gui()
        total_w = float(snapshot.get("w", val.get("w", 0.0)))
        total_h = float(snapshot.get("h", val.get("h", 0.0)))

        def world_to_canvas(world_x, world_y):
            return (
                x0 + (float(world_x) + total_w / 2.0) * scale,
                y0 + (total_h / 2.0 - float(world_y)) * scale,
            )

        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            from ae_engine.door_dividers import derive_box_body_dividers
            normalized = tuple((float(c[0]), tuple(float(h) for h in c[1])) for c in columns)
            dividers = derive_box_body_dividers(
                normalized,
                depth=float(val.get('d', 350.0)),
                thickness=t_val,
                layout_scope=getattr(self, "door_layout_scope", "main"),
                handle_edges=getattr(self, "door_layout_handle_edges", {}),
            )
            for div in dividers:
                placement = resolve_assembly_placement(snapshot, div.stable_id)
                cx, cy, _cz = placement.world_offset
                if div.axis == "HORIZONTAL":
                    x1, y = world_to_canvas(cx - float(div.span) / 2.0, cy)
                    x2, _ = world_to_canvas(cx + float(div.span) / 2.0, cy)
                    canvas.create_rectangle(
                        x1, y - 3, x2, y + 3,
                        fill="#00d4d4", outline="#00a3a3", width=1,
                        tags=("door_layout_divider",)
                    )
                    canvas.create_text(
                        (x1 + x2) / 2.0, y + 14,
                        text=f"中隔 W-2T={div.span:.1f} mm (成型深={div.formed_core_depth:.1f})",
                        fill="#00d4d4", font=('Consolas', 9, 'bold'),
                        tags=("door_layout_divider",)
                    )
                elif div.axis == "VERTICAL":
                    x, y1 = world_to_canvas(cx, cy + float(div.span) / 2.0)
                    _, y2 = world_to_canvas(cx, cy - float(div.span) / 2.0)
                    canvas.create_rectangle(
                        x - 3, y1, x + 3, y2,
                        fill="#00d4d4", outline="#00a3a3", width=1,
                        tags=("door_layout_divider",)
                    )
        except Exception:
            pass

        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            from ae_engine.inner_door_frames import inner_door_frame_stable_id
            if cabinet_family_policy.has_inner_door_frame_derivation(snapshot):
                frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(snapshot)
                for fset in frame_sets:
                    for side in tuple(fset.included_sides):
                        if side not in {"top", "left", "right"}:
                            continue
                        stable_id = inner_door_frame_stable_id(fset.inner_door_id, side)
                        placement = resolve_assembly_placement(snapshot, stable_id)
                        cx, cy, _cz = placement.world_offset
                        span = float(fset.spans[side])
                        if side == "top":
                            x1, y = world_to_canvas(cx - span / 2.0, cy)
                            x2, _ = world_to_canvas(cx + span / 2.0, cy)
                            canvas.create_line(
                                x1, y, x2, y, fill="#ff9f0a", width=2, dash=(6, 3),
                                tags=("door_layout_frame",)
                            )
                            canvas.create_text(
                                (x1 + x2) / 2.0, y + 14,
                                text=f"內門框 (頂/左/右內縮50mm, 寬={span:.1f})",
                                fill="#ff9f0a", font=('Microsoft JhengHei', 8, 'bold'),
                                tags=("door_layout_frame",)
                            )
                        else:
                            x, y1 = world_to_canvas(cx, cy + span / 2.0)
                            _, y2 = world_to_canvas(cx, cy - span / 2.0)
                            canvas.create_line(
                                x, y1, x, y2, fill="#ff9f0a", width=2, dash=(6, 3),
                                tags=("door_layout_frame",)
                            )
        except Exception:
            pass

    def draw_door(self, val):
        """Draw Door from the same final PartRenderData consumed by Phase6 3D."""
        if self.multi_door_enabled_var.get():
            self.draw_door_layout_overview()
            return

        canvas = self.canvas_door
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        try:
            door_val = {
                'w': float(self.w_var.get()),
                'h': float(self.h_var.get()),
                't': float(self.t_var.get()),
                'fw': float(self.fw_z_var.get()),
                'door_gap_w': float(self.door_gap_w_var.get()),
                'door_gap_h': float(self.door_gap_h_var.get()),
                'door_fold_l': float(self.door_fold_l_var.get()),
                'door_fold_r': float(self.door_fold_r_var.get()),
                'door_fold_t': float(self.door_fold_t_var.get()),
                'door_fold_b': float(self.door_fold_b_var.get()),
            }
        except ValueError:
            canvas.create_text(
                cw/2, ch/2,
                text="請先填寫門板所需的尺寸 (W / H / T / FW / 折邊)",
                fill="#ff9f0a", font=('Microsoft JhengHei', 11, 'bold')
            )
            return

        indicator_hole = None
        indicator_box_groups = ()
        if self.is_indicator_box_var.get():
            try:
                count = max(1, int(self.indicator_l_var.get()))
                indicator_box_groups = tuple(
                    int(self.indicator_layer_g_vars[i].get()) for i in range(count)
                )
                indicator_hole = manufacturing_api.indicator_box_opening_size(
                    indicator_box_groups, thickness=door_val['t']
                )
            except Exception:
                indicator_hole = None
                indicator_box_groups = ()

        door_indicator = None
        if self.is_door_indicator_var.get():
            try:
                count = max(1, int(self.door_indicator_l_var.get()))
                door_indicator = tuple(
                    int(self.door_indicator_layer_g_vars[i].get()) for i in range(count)
                )
            except Exception:
                door_indicator = None

        try:
            spec = self._single_door_part_spec(
                door_val, indicator_hole=indicator_hole, door_indicator=door_indicator
            )
            render_data = self._authoritative_render_data(
                spec, self._manufacturing_context(draw_stock=False)
            )
            minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
            blank_w = maxx - minx
            blank_h = maxy - miny
            if blank_w <= 0 or blank_h <= 0:
                raise ValueError("門板 Final Part Geometry 尺寸無效")
            finished_w, finished_h = manufacturing_api.door_finished_face_size(
                spec, self._manufacturing_context(draw_stock=False)
            )
        except Exception as exc:
            canvas.create_text(
                cw/2, ch/2, text=f"門板 Final Part Geometry 載入失敗:\n{exc}",
                fill="#ff3333", font=('Microsoft JhengHei', 10, 'bold'),
                width=max(200, cw-40),
            )
            return

        canvas_transform, left, bottom, scale, _material_top = _phase6_2d_material_viewport(
            (minx, miny, maxx, maxy), cw, ch
        )

        if self.draw_stock_var.get():
            sx0, sy0 = canvas_transform.world_to_canvas(Vec2(minx, miny))
            sx1, sy1 = canvas_transform.world_to_canvas(Vec2(maxx, maxy))
            canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4)
            )

        # Manufacturing geometry is rendered exactly once from the final scene.
        # Baseline handle holes, fixed holes, user holes and CornerType CUTTING
        # therefore cannot diverge from the material consumed by 3D.
        render_drawing_scene(
            canvas, render_data.scene, canvas_transform,
            skip_layers=("CHECK", "STOCK"),
        )

        canvas.create_text(
            cw / 2, bottom - blank_h * scale - 20,
            text=f"W = {blank_w:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold')
        )
        canvas.create_text(
            left + blank_w * scale + 45, bottom - (blank_h * scale) / 2,
            text=f"H = {blank_h:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold'), angle=90
        )
        stock_hint = "  STOCK: 青色虛線" if self.draw_stock_var.get() else ""
        baseline_hint = f" ({spec.model_name} 最終製造幾何)" if spec.model_name else " (自訂最終製造幾何)"
        canvas.create_text(
            25, 25, anchor=tk.NW,
            text=(
                f"門板展開預覽{baseline_hint}\n"
                f"CUTTING/截角/固定孔/使用者開孔：同一份 Final Part Geometry\n"
                f"折彎線 (BEND): 藍色虛線{stock_hint}\n"
                f"成品寬 = {finished_w:.2f} mm / 成品高 = {finished_h:.2f} mm\n"
                f"折邊: 左{door_val['door_fold_l']} 右{door_val['door_fold_r']} "
                f"上{door_val['door_fold_t']} 下{door_val['door_fold_b']}"
            ),
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )

        indicator_context = None
        indicator_layout = None
        indicator_groups = tuple(door_indicator or ())
        if indicator_groups:
            try:
                indicator_context = DoorIndicatorContext(
                    finished_width=finished_w,
                    finished_height=finished_h,
                    left_fold=door_val['door_fold_l'],
                    bottom_fold=door_val['door_fold_b'],
                )
                indicator_layout = resolve_door_indicator_layout(
                    indicator_context,
                    indicator_groups,
                    Vec2(self.door_indicator_offset_x, self.door_indicator_offset_y),
                )
            except Exception:
                indicator_context = None
                indicator_layout = None

        self.last_door_draw_params = {
            'transform': canvas_transform,
            'blank_w': blank_w,
            'blank_h': blank_h,
            'indicator_context': indicator_context,
            'indicator_groups': indicator_groups,
            'indicator_layout': indicator_layout,
            'frame_edges': spec.frame_edges,
            'layout_cell': None,
            'render_data': render_data,
        }

        if indicator_layout is not None and indicator_context is not None:
            try:
                position = measure_door_indicator_position(
                    indicator_layout,
                    indicator_context,
                    frame_width=door_val['fw'],
                    thickness=door_val['t'],
                    use_box_distance=spec.use_box_distance,
                    frame_edges=spec.frame_edges,
                    gap_w=door_val['door_gap_w'], gap_h=door_val['door_gap_h'],
                )
                x_guide, y_guide = resolve_door_indicator_dimension_guides(position)

                p1_cx, p1_cy = canvas_transform.world_to_canvas(x_guide.start)
                p2_cx, p2_cy = canvas_transform.world_to_canvas(x_guide.end)
                p1_cy -= 20; p2_cy -= 20
                canvas.create_line(
                    p1_cx, p1_cy, p2_cx, p2_cy, fill="#ff9f0a",
                    arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1.2
                )
                canvas.create_text(
                    (p1_cx + p2_cx)/2, p1_cy - 10,
                    text=f"X={x_guide.value:.1f}", fill="#ff9f0a",
                    font=('Consolas', 9, 'bold'), tags="dim_x"
                )

                p1_cx, p1_cy = canvas_transform.world_to_canvas(y_guide.start)
                p2_cx, p2_cy = canvas_transform.world_to_canvas(y_guide.end)
                p1_cx -= 20; p2_cx -= 20
                canvas.create_line(
                    p1_cx, p1_cy, p2_cx, p2_cy, fill="#ff9f0a",
                    arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1.2
                )
                canvas.create_text(
                    p1_cx - 30, (p1_cy + p2_cy)/2,
                    text=f"Y={y_guide.value:.1f}", fill="#ff9f0a",
                    font=('Consolas', 9, 'bold'), tags="dim_y"
                )
            except Exception:
                pass

        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=False)

    def draw_base_plate(self, val):
        canvas = self.canvas_base_plate
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        try:
            shrink_top = float(self.base_plate_shrink_top_var.get())
            shrink_bottom = float(self.base_plate_shrink_bottom_var.get())
            shrink_left = float(self.base_plate_shrink_left_var.get())
            shrink_right = float(self.base_plate_shrink_right_var.get())
            bend = float(self.base_plate_bend_var.get())
            spec_val = dict(val)
            spec_val.update({
                'base_plate_shrink_top': shrink_top,
                'base_plate_shrink_bottom': shrink_bottom,
                'base_plate_shrink_left': shrink_left,
                'base_plate_shrink_right': shrink_right,
                'base_plate_bend': bend,
            })
            spec = self._base_plate_part_spec(spec_val)
            render_data = self._authoritative_render_data(
                spec, self._manufacturing_context(draw_stock=False)
            )
            minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
            total_width = maxx - minx
            total_height = maxy - miny
        except Exception as exc:
            canvas.create_text(
                cw/2, ch/2, text=f"底板 Final Part Geometry 載入失敗:\n{exc}",
                fill="#ff3333", font=('Microsoft JhengHei', 10, 'bold')
            )
            return

        box_l = -(shrink_left - bend)
        box_b = -(shrink_bottom - bend)
        world_min_x = min(minx, box_l)
        world_max_x = max(maxx, box_l + val['w'])
        world_min_y = min(miny, box_b)
        world_max_y = max(maxy, box_b + val['h'])
        canvas_transform, left, bottom, scale, _material_top = _phase6_2d_material_viewport(
            (world_min_x, world_min_y, world_max_x, world_max_y), cw, ch
        )

        def to_canvas(rx, ry):
            return canvas_transform.world_to_canvas(Vec2(rx, ry))

        if self.draw_stock_var.get():
            sx0, sy0 = to_canvas(minx, miny)
            sx1, sy1 = to_canvas(maxx, maxy)
            canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4)
            )

        render_drawing_scene(
            canvas, render_data.scene, canvas_transform,
            skip_layers=("CHECK", "STOCK"),
        )

        bx0, by0 = to_canvas(box_l, box_b)
        bx1, by1 = to_canvas(box_l + val['w'], box_b + val['h'])
        canvas.create_rectangle(
            bx0, by0, bx1, by1, outline="#ff453a", width=1.2, dash=(4, 4)
        )

        stock_hint = " + [母材]" if self.draw_stock_var.get() else ""
        hole_w = total_width - 2.0 * bend - 30.0
        hole_h = total_height - 2.0 * bend - 30.0
        canvas.create_text(
            20, 20,
            text=(
                "底板展開預覽｜Final Part Geometry\n"
                "CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
                "箱身外框對照線: 紅色虛線\n"
                f"展開圖孔距 W:{hole_w:.1f} H:{hole_h:.1f}{stock_hint}"
            ),
            fill=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold'), anchor=tk.NW,
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )
        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=False)

    def _disable_all_door_indicators(self):
        """Disable only the legacy single-Door direct-indicator mode.

        Multi-Door cells own their own mutually-exclusive mode and must not be
        changed by the single-Door Indicator-Box checkbox.
        """
        self.is_door_indicator_var.set(False)

    def _disable_indicator_box_for_door_indicator(self):
        """Direct Door indicators remove the separate Indicator-Box assembly from physical presence."""
        self.is_indicator_box_var.set(False)
        existing = self.workspace_controller.set_part_presence("indicator_box", False)
        existing = self.workspace_controller.set_part_presence("indicator_door", False)
        self._phase6_refresh_presence_ui(existing)
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")

    def on_indicator_box_toggle(self):
        """Indicator Box toggle also owns physical box/small-door presence."""
        enabled = bool(self.is_indicator_box_var.get())
        if enabled:
            self._disable_all_door_indicators()
        self._phase6_set_part_presence("indicator_box", enabled)
        self._phase6_set_part_presence("indicator_door", enabled)
        self._request_phase6_update("geometry")

    def on_door_indicator_toggle(self):
        """Direct Door indicators exclude the Indicator-Box opening mode without hiding its tabs."""
        if self.is_door_indicator_var.get():
            self._disable_indicator_box_for_door_indicator()
        self._request_phase6_update("geometry")

    def on_door_layers_count_changed(self):
        self.rebuild_door_layers_config_ui()
        self._request_phase6_update("geometry")

    def rebuild_door_layers_config_ui(self):
        # 清空先前的元件
        for widget in self.door_layers_config_frame.winfo_children():
            widget.destroy()
            
        try:
            layers = int(self.door_indicator_l_var.get())
        except ValueError:
            layers = 1
            
        # 逐層建立橫向的組數選擇選單
        for ly in range(layers):
            ly_frame = tk.Frame(self.door_layers_config_frame, bg=self.COLOR_PANEL)
            ly_frame.pack(side=tk.LEFT, padx=15, pady=4)
            
            label_text = f"第 {ly+1} 層組數:"
            if ly == 0:
                label_text = "第 1 層 (底) 組數:"
            elif ly == layers - 1 and layers > 1:
                label_text = f"第 {ly+1} 層 (頂) 組數:"
                
            tk.Label(ly_frame, text=label_text, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9, 'bold')).pack(side=tk.LEFT, padx=2)
            
            cb = ttk.Combobox(ly_frame, textvariable=self.door_indicator_layer_g_vars[ly], values=["1", "2", "3", "4", "5", "6", "7", "8"], width=4, state="readonly", style='TCombobox')
            cb.pack(side=tk.LEFT, padx=2)
            cb.bind("<<ComboboxSelected>>", lambda e: self._request_phase6_update("geometry"))

    def reset_door_indicator_offset_x(self):
        self.door_indicator_offset_x = 0.0
        self.draw_preview()

    def reset_door_indicator_offset_y(self):
        self.door_indicator_offset_y = 0.0
        self.draw_preview()

        draw_hole_editor_hint(canvas, cw, endcap=False)

    def _door_layout_cell_at_canvas_point(self, x, y):
        """Return (column_index, row_index) for any point inside a visible multi-door cell."""
        for key, bounds in self.door_layout_cell_bounds.items():
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                column_index, row_index = (int(part) for part in key.split(":", 1))
                return column_index, row_index
        return None

    def on_door_canvas_press(self, event):
        if self.multi_door_enabled_var.get():
            hit = self._door_layout_cell_at_canvas_point(event.x, event.y)
            if hit is None:
                self._door_layout_last_click = None
                return "break"

            event_time = int(getattr(event, "time", 0) or 0)
            if not event_time:
                event_time = int(time.monotonic() * 1000)
            last = self._door_layout_last_click
            is_manual_double = False
            if last is not None:
                last_hit, last_time = last
                delta = event_time - last_time if event_time and last_time else 999999
                is_manual_double = (last_hit == hit and 0 <= delta <= 650)

            if is_manual_double:
                self._door_layout_last_click = None
                self.open_door_layout_cell_editor(*hit)
            else:
                self._door_layout_last_click = (hit, event_time)
                self.select_door_layout_cell(*hit)
            return "break"
        if not self.is_door_indicator_var.get() or not hasattr(self, 'last_door_draw_params'):
            return
        params = self.last_door_draw_params
        transform = params.get('transform')
        layout = params.get('indicator_layout')
        if transform is None or layout is None:
            return
        world = transform.canvas_to_world(event.x, event.y)
        if layout.hit_test(world, padding=15.0):
            self.drag_active = True
            self.drag_start_world = world
            self.drag_start_offset_x = self.door_indicator_offset_x
            self.drag_start_offset_y = self.door_indicator_offset_y

    def on_door_canvas_drag(self, event):
        if not self.drag_active:
            return
        params = self.last_door_draw_params
        transform = params.get('transform')
        layout = params.get('indicator_layout')
        if transform is None or layout is None:
            return
        world = transform.canvas_to_world(event.x, event.y)
        delta = world - self.drag_start_world
        desired = Vec2(
            self.drag_start_offset_x + delta.x,
            self.drag_start_offset_y + delta.y,
        )
        clamped = layout.clamp_offset(desired)
        self.door_indicator_offset_x = clamped.x
        self.door_indicator_offset_y = clamped.y
        self.draw_preview()

    def on_door_canvas_release(self, event):
        self.drag_active = False

    def on_door_canvas_double_click(self, event):
        if self.multi_door_enabled_var.get():
            hit = self._door_layout_cell_at_canvas_point(event.x, event.y) if event is not None else None
            if hit is not None:
                self.open_door_layout_cell_editor(*hit)
            return "break"
        self.open_part_hole_editor("door")
        return "break"

    def ask_xy_dialog(self, current_x, current_y):
        dialog = tk.Toplevel(self.root)
        dialog.title("輸入指示燈定位距離")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 200, self.root.winfo_rooty() + 150))
        dialog.configure(bg=self.COLOR_BG)
        
        tk.Label(dialog, text="請輸入新的定位距離 (mm)", bg=self.COLOR_BG, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 10, 'bold')).pack(pady=10)
        
        input_frame = tk.Frame(dialog, bg=self.COLOR_BG)
        input_frame.pack(padx=20, pady=5)
        
        tk.Label(input_frame, text="水平距離 X (mm):", bg=self.COLOR_BG, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9)).grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        entry_x = ttk.Entry(input_frame, width=12)
        entry_x.insert(0, f"{current_x:.1f}")
        entry_x.grid(row=0, column=1, padx=5, pady=5)
        entry_x.focus_set()
        
        tk.Label(input_frame, text="垂直距離 Y (mm):", bg=self.COLOR_BG, fg=self.COLOR_TEXT, font=('Microsoft JhengHei', 9)).grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        entry_y = ttk.Entry(input_frame, width=12)
        entry_y.insert(0, f"{current_y:.1f}")
        entry_y.grid(row=1, column=1, padx=5, pady=5)
        
        result = [None, None]
        
        def on_ok(event=None):
            try:
                result[0] = float(entry_x.get())
                result[1] = float(entry_y.get())
                dialog.destroy()
            except ValueError:
                from tkinter import messagebox
                messagebox.showerror("錯誤", "請輸入正確的數字格式", parent=dialog)
                
        def on_cancel():
            dialog.destroy()
            
        btn_frame = tk.Frame(dialog, bg=self.COLOR_BG)
        btn_frame.pack(pady=15)
        
        btn_ok = tk.Button(btn_frame, text="確認", font=('Microsoft JhengHei', 9, 'bold'), bg=self.COLOR_PANEL, fg=self.COLOR_ACCENT, bd=1, relief=tk.SOLID, padx=15, command=on_ok)
        btn_ok.pack(side=tk.LEFT, padx=10)
        
        btn_cancel = tk.Button(btn_frame, text="取消", font=('Microsoft JhengHei', 9), bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, bd=1, relief=tk.SOLID, padx=15, command=on_cancel)
        btn_cancel.pack(side=tk.LEFT, padx=10)
        
        dialog.bind("<Return>", on_ok)
        dialog.bind("<Escape>", lambda e: on_cancel())
        
        self.root.wait_window(dialog)
        return result[0], result[1]

    def on_double_click_indicator(self):
        params = self.last_door_draw_params
        context = params.get('indicator_context')
        groups = params.get('indicator_groups')
        layout = params.get('indicator_layout')
        if context is None or not groups or layout is None:
            return
        try:
            t_val = float(self.t_var.get())
        except Exception:
            t_val = 2.0
        try:
            fw_val = float(self.fw_z_var.get())
        except Exception:
            fw_val = 62.0

        position = measure_door_indicator_position(
            layout,
            context,
            frame_width=fw_val,
            thickness=t_val,
            use_box_distance=self.is_box_dist_var.get(),
            frame_edges=params.get('frame_edges') or DoorFrameEdges(),
            gap_w=float(self.door_gap_w_var.get()), gap_h=float(self.door_gap_h_var.get()),
        )
        new_x, new_y = self.ask_xy_dialog(position.distance_x, position.distance_y)
        if new_x is not None and new_y is not None:
            target = door_indicator_offset_for_position(
                context,
                groups,
                x_distance=new_x,
                y_distance=new_y,
                frame_width=fw_val,
                thickness=t_val,
                use_box_distance=self.is_box_dist_var.get(),
                frame_edges=params.get('frame_edges') or DoorFrameEdges(),
                gap_w=float(self.door_gap_w_var.get()), gap_h=float(self.door_gap_h_var.get()),
            )
            self.door_indicator_offset_x = target.x
            self.door_indicator_offset_y = target.y
            self.draw_preview()

    def _indicator_small_door_size_chain_label(self):
        gap = float(manufacturing_api.resolve_policy().indicator_small_door_gap)
        gap_text = f"{gap:g}"
        return (
            "指示燈小門展開圖預覽 | 尺寸連動：盒子內部淨開口 "
            f"→ 四邊各留 {gap_text} mm → 小門成品 → 小門展開"
        )

    def setup_tab_indicator_door_ui(self):
        # 頂部控制列
        top_ctrl = tk.Frame(self.tab_indicator_door, bg=self.COLOR_BG)
        top_ctrl.pack(fill=tk.X, padx=10, pady=5)
        
        # 說明標籤
        lbl_formula = ttk.Label(
            top_ctrl, 
            text=self._indicator_small_door_size_chain_label(), 
            style='TLabel'
        )
        lbl_formula.pack(side=tk.LEFT, padx=5)
        
        # 畫布 Frame
        canvas_frame = tk.Frame(self.tab_indicator_door, bg=self.COLOR_CANVAS_BG, bd=1, relief=tk.SOLID)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # 畫布
        self.canvas_indicator_door = tk.Canvas(canvas_frame, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        self.canvas_indicator_door.pack(fill=tk.BOTH, expand=True)
        self.canvas_indicator_door.bind("<Configure>", lambda e: self.draw_preview())
        self._attach_part_hole_entrypoint(self.canvas_indicator_door, "indicator_door", allow_double=True)

    def draw_indicator_door(self, val):
        canvas = self.canvas_indicator_door
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        try:
            count = max(1, int(self.indicator_l_var.get()))
            layer_groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(count))
            spec, context = self._indicator_door_part_spec_from_values(
                val, layer_groups, features=self.surface_features["indicator_door"]
            )
            render_data = self._authoritative_render_data(spec, context)
            minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
            blank_w = maxx - minx
            blank_h = maxy - miny
            finished_w, finished_h = manufacturing_api.door_finished_face_size(spec, context)
        except Exception as exc:
            canvas.create_text(
                cw/2, ch/2, text=f"指示燈小門 Final Part Geometry 載入失敗:\n{exc}",
                fill="#ff3333", font=('Microsoft JhengHei', 11, 'bold')
            )
            return

        canvas_transform, left, bottom, scale, _material_top = _phase6_2d_material_viewport(
            (minx, miny, maxx, maxy), cw, ch
        )

        if self.draw_stock_var.get():
            sx0, sy0 = canvas_transform.world_to_canvas(Vec2(minx, miny))
            sx1, sy1 = canvas_transform.world_to_canvas(Vec2(maxx, maxy))
            canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4)
            )

        render_drawing_scene(
            canvas, render_data.scene, canvas_transform,
            skip_layers=("CHECK", "STOCK"),
        )

        canvas.create_text(
            cw / 2, bottom - blank_h * scale - 20,
            text=f"W = {blank_w:.2f} mm", fill="#30d158", font=('Consolas', 10, 'bold')
        )
        canvas.create_text(
            left + blank_w * scale + 45, bottom - (blank_h * scale) / 2,
            text=f"H = {blank_h:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold'), angle=90
        )
        stock_hint = "  STOCK 母材外框: 青色虛線" if self.draw_stock_var.get() else ""
        canvas.create_text(
            25, 25, anchor=tk.NW,
            text=(
                "指示燈小門展開預覽｜Final Part Geometry\n"
                "CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
                f"成品 {finished_w:.2f} × {finished_h:.2f} mm{stock_hint}"
            ),
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )
        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=False)

    def _inherit_known_corner_state_into_custom(self):
        """把目前已知固定板件的實際截角狀態複製成自訂起點。"""
        copied = self._known_corner_state_for_current_family(self.manual_corner_state.keys())
        for part_key, corners in copied.items():
            if part_key not in self.manual_corner_state:
                continue
            self.manual_corner_state[part_key].update(corners)
            if part_key in self.manual_corner_pair_same:
                self.manual_corner_pair_same[part_key]["top"] = True
                self.manual_corner_pair_same[part_key]["bottom"] = True

    def _capture_cabinet_family_runtime(self):
        layout = []
        if getattr(self, "door_layout_columns", None):
            try:
                layout = [[float(width), [float(v) for v in heights]] for width, heights in self.get_door_layout_columns()]
            except Exception:
                layout = []
        return {
            "settings": {key: var.get() for key, var in self._setting_var_map().items()},
            "corner_state": self._serialize_manual_corner_state(),
            "corner_pair_same": deepcopy(self.manual_corner_pair_same),
            "endcap_bottom_wrap": deepcopy(getattr(self, "endcap_bottom_wrap_state", {})),
            "box_body_structure": self.workspace_controller.box_body_structure_state(),
            "box_body_profile": self.workspace_controller.box_body_profile(),
            "assembly_joint_state": deepcopy(getattr(self, "assembly_joint_state", {}) or {}),
            "multi_door_enabled": bool(self.multi_door_enabled_var.get()),
            "door_layout_columns": layout,
            "door_layout_scope": str(getattr(self, "door_layout_scope", "main") or "main"),
            "door_handle_edges": deepcopy(getattr(self, "door_layout_handle_edges", {}) or {}),
            "receiving_inner_doors": deepcopy(getattr(self, "receiving_inner_doors", []) or []),
            "door_nameplate_center_datum_top": getattr(self, "door_nameplate_center_datum_top", None),
        }

    def _restore_cabinet_family_runtime(self, state):
        state = dict(state or {})
        values = {}
        for key, raw in dict(state.get("settings") or {}).items():
            try:
                values[key] = bool(raw) if key == "draw_stock" else float(raw)
            except (TypeError, ValueError):
                continue
        self._apply_fold_designer_live_settings(values, recalculate=False)
        self._apply_manual_corner_snapshot(state.get("corner_state"), state.get("corner_pair_same"))
        if state.get("endcap_bottom_wrap") is not None:
            self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({
                "model": BoxCalculatorGUI._current_cabinet_type_name(self),
                "endcap_bottom_wrap": state.get("endcap_bottom_wrap"),
            })
        joint_state = state.get("assembly_joint_state")
        if isinstance(joint_state, dict) and joint_state:
            self.assembly_joint_state = migrate_legacy_snapshot_joints(deepcopy(joint_state))
            stable = assembly_intent_value(self.assembly_joint_state.get("assembly_type", "INSERT_OVERLAY"))
            self.box_assembly_type_var.set(assembly_intent_label(stable))
        self.multi_door_enabled_var.set(bool(state.get("multi_door_enabled", False)))
        layout = list(state.get("door_layout_columns") or [])
        if layout:
            self.set_door_layout_columns([(float(row[0]), [float(v) for v in row[1]]) for row in layout])
        else:
            self.door_layout_columns = []
        self.door_layout_scope = str(state.get("door_layout_scope") or "main")
        self.door_layout_handle_edges = deepcopy(dict(state.get("door_handle_edges") or {}))
        self.receiving_inner_doors = deepcopy(state.get("receiving_inner_doors") or [])
        datum = state.get("door_nameplate_center_datum_top")
        self.door_nameplate_center_datum_top = None if datum is None else float(datum)
        self.workspace_controller.set_box_body_structure_state(state.get("box_body_structure"))
        self.workspace_controller.set_box_body_profile(state.get("box_body_profile"))

    def _apply_cabinet_family_for_current_model(self):
        """Apply an explicit model switch without remembering known-family edits.

        Known models always load their own preset.  ``自訂`` is the sole
        exception: entering custom leaves the current operator values in place
        as the starting point.  Project/3D snapshot restoration uses the
        baseline commit guard and therefore does not run this fresh-preset path.
        """
        raw_model = normalize_custom_model_name(
            self.baseline_var.get() if getattr(self, "baseline_var", None) is not None else ""
        )
        new_type = BoxCalculatorGUI._current_cabinet_type_name(self)
        previous = str(getattr(self, "_active_cabinet_type", "金庫型") or "金庫型")

        # Project load / 3D live-state application owns the complete snapshot.
        # Do not wash saved values through a fresh family preset in that path.
        if getattr(self, "_fold_designer_baseline_commit_guard", False):
            self._active_cabinet_type = new_type
            return previous != new_type

        # Custom is intentionally not another family preset.  It inherits the
        # current values exactly; later edits become the custom starting state.
        if is_unknown_model(raw_model):
            self._active_cabinet_type = new_type
            owner = getattr(self, "_derived_cache_owner", None)
            if owner is not None:
                owner.invalidate("geometry")
            return previous != new_type

        if new_type == "金庫型":
            defaults = deepcopy(
                dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
                or {}
            )
            if defaults:
                self._restore_cabinet_family_runtime(defaults)
        elif new_type == "受電箱":
            # Start from immutable/startup settings, never from the last edited
            # Receiving runtime.  The family policy then overlays its canonical
            # receiving defaults (800/1600/350, FW 29, structure, etc.).
            vault_defaults = deepcopy(
                dict(getattr(self, "_cabinet_family_defaults", {}) or {}).get("金庫型")
                or {}
            )
            base_settings = dict(vault_defaults.get("settings") or self.settings_service.snapshot().as_dict())
            values = cabinet_family_policy.apply_fresh_family_defaults(base_settings, new_type)
            self._apply_fold_designer_live_settings(values, recalculate=False)
            self._set_box_assembly_type(values["assembly_type"], recalculate=False, notify_designer=False)
            self.multi_door_enabled_var.set(bool(values.get("multi_door_enabled", True)))
            self.set_door_layout_columns([
                (float(row[0]), [float(v) for v in row[1]])
                for row in values.get("door_layout_columns", ())
            ])
            self.door_layout_scope = str(values.get("door_layout_scope") or "receiving-main")
            self.door_layout_handle_edges = deepcopy(dict(values.get("door_handle_edges") or {}))
            self.receiving_inner_doors = deepcopy(values.get("inner_doors") or [])
            self.door_nameplate_center_datum_top = float(values["door_nameplate_center_datum_top"])
            structure = cabinet_family_policy.resolve_box_body_structure_state(
                new_type, self.workspace_controller.box_body_structure_state()
            )
            self.workspace_controller.set_box_body_structure_state(structure)
            self.endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state({"model": new_type})
            bottom = cabinet_family_policy.endcap_bottom_selection(new_type)
            for part in ("head", "tail"):
                self.manual_corner_state[part]["bottom_left"] = bottom
                self.manual_corner_state[part]["bottom_right"] = bottom
                self.manual_corner_pair_same[part]["bottom"] = True
            snap = self._make_original_fold_designer_snapshot()
            box_profile = build_box_body_profile(snap)
            workspace = self.workspace_controller.workspace_snapshot()
            workspace["box_body_profile"] = box_profile
            workspace["box_body_structure"] = structure
            self._store_fold_designer_workspace(workspace)

        self._active_cabinet_type = new_type
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("geometry")
        return previous != new_type


    def on_baseline_changed(self):
        self._reset_manual_corner_parameter_locks()
        owner = getattr(self, "_derived_cache_owner", None)
        if owner is not None:
            owner.invalidate("baseline")
        val = self.baseline_var.get()
        previous = str(getattr(self, "_baseline_last_value", "") or "").strip()
        self._apply_cabinet_family_for_current_model()
        if is_unknown_model(val) and previous and not is_unknown_model(previous):
            self._inherit_known_corner_state_into_custom()
        elif val and not is_unknown_model(val) and val != previous:
            self._enforce_known_model_corner_types(reset_all=True)
        current_intent = self._current_box_assembly_type()
        assembly_var = getattr(self, "box_assembly_type_var", None)
        if assembly_var is not None:
            label = assembly_intent_label(current_intent)
            if assembly_var.get() != label:
                assembly_var.set(label)
        cb_assembly = getattr(self, "cb_box_assembly", None)
        if cb_assembly is not None:
            cb_assembly.configure(state=("readonly" if is_unknown_model(val) else "disabled"))
        self._baseline_last_value = str(val or "").strip()
        self.refresh_corner_type_panel()
        if getattr(self, "_fold_designer_baseline_commit_guard", False):
            # 3D 確定 only changes the baseline/corner transaction. Do not let
            # the legacy baseline handler overwrite already-edited fold values.
            return
        if not val:
            return
        if is_unknown_model(val):
            # 自訂沒有 baseline DXF；保留使用者輸入的折彎尺寸。
            self._request_phase6_update("baseline")
            return
        if BoxCalculatorGUI._current_cabinet_type_name(self) == "受電箱":
            # 受電箱第一階段使用公式/Family policy，沒有自己的 baseline DXF。
            self._request_phase6_update("baseline")
            return
        try:
            t_val = float(self.t_var.get()) if self.t_var.get() else 2.0
            
            # 1. 載入封頭尾基準檔分析折彎參數
            geom = ae.get_stretched_end_cap_data(val, 500, 500, 150, t_val, FW_val=None, is_tail=False)
            p = geom.params
            
            self.yl1_var.set(f"{p['yl1']:.1f}".replace(".0", ""))
            self.yr1_var.set(f"{p['yr1']:.1f}".replace(".0", ""))
            self.ytop1_var.set(f"{p['ytop1']:.1f}".replace(".0", ""))
            self.ybottom1_var.set(f"{p['ybottom1']:.1f}".replace(".0", ""))
            # 基準檔更新箱身 FW；封頭尾只有仍在「跟隨箱身」時同步。
            fw_val = f"{p['fw']:.1f}".replace(".0", "")
            self.fw_z_var.set(fw_val)
            box_fw = float(p['fw'])
            for part in ("head", "tail"):
                state = self.endcap_fw_state.setdefault(part, {"follow_box": True, "value": box_fw})
                if bool(state.get("follow_box", True)):
                    state["value"] = box_fw
            self._sync_endcap_fw_controls()
            
            # 2. 箱身主結構固定由 StripFoldChain 公式控制。
            # 箱身.dxf 只映射固定加工特徵，不反推/覆寫 zl1/zl2/zr1/zr2/z_comp。

            # 3. 檢查並加載目前型號的門基準；GUI 不自行組 baseline 路徑。
            if ae.has_baseline_part(val, "門.dxf"):
                try:
                    door_fw = self._door_material_frame_width(
                        self.fw_z_var.get(), t_val, model_name=val
                    )
                    geom_door = ae.get_stretched_door_data(
                        val, 500, 500, t_val, door_fw
                    )
                    pd = geom_door.params
                    self.door_fold_l_var.set(f"{pd['door_fold_l']:.1f}".replace(".0", ""))
                    self.door_fold_r_var.set(f"{pd['door_fold_r']:.1f}".replace(".0", ""))
                    self.door_fold_t_var.set(f"{pd['door_fold_t']:.1f}".replace(".0", ""))
                    self.door_fold_b_var.set(f"{pd['door_fold_b']:.1f}".replace(".0", ""))
                except Exception as door_err:
                    self.door_fold_l_var.set("19")
                    self.door_fold_r_var.set("15")
                    self.door_fold_t_var.set("15")
                    self.door_fold_b_var.set("15")
        except Exception as e:
            messagebox.showerror("基準檔載入出錯", f"無法讀取基準檔參數: {e}")

    def bind_live_updates(self):
        # W/H 同時是 Door layout 的總尺寸；變更時要重算自動餘數。
        self.w_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())
        self.h_var.trace_add("write", lambda *args: self._on_total_door_dimension_changed())

        # 主 GUI 中仍存在的設定欄位與 3D 設定中心雙向連動。
        for key, var in self._setting_var_map().items():
            var.trace_add("write", lambda *_args, k=key, v=var: self._on_main_setting_var_changed(k, v))

        # 非 SettingsService 擁有的輸入也只送 dirty event；完整重算只能由 Scheduler 執行。
        for var in [self.base_plate_all_same_var, self.base_plate_shrink_same_var,
                    self.indicator_g_var, self.indicator_l_var] + self.indicator_layer_g_vars:
            var.trace_add(
                "write",
                lambda *_args: self._on_main_geometry_var_changed("legacy_input"),
            )
        # STOCK 開關變動時也觸發重繪 (Checkbutton 已用 command 綁定，此處不需重複)

    def get_float_values(self):
        """
        取得所有浮點數輸入值，若輸入有誤則拋出 Exception
        """
        try:
            return {
                'w': float(self.w_var.get()),
                'h': float(self.h_var.get()),
                'd': float(self.d_var.get()),
                'fw': float(self.fw_z_var.get()),
                't': float(self.t_var.get()),
                'zl1': float(self.zl1_var.get()),
                'zl2': float(self.zl2_var.get()),
                'zr1': float(self.zr1_var.get()),
                'zr2': float(self.zr2_var.get()),
                'z_comp': float(self.z_comp_var.get()),
                'yl1': float(self.yl1_var.get()),
                'yr1': float(self.yr1_var.get()),
                'ytop1': float(self.ytop1_var.get()),
                'ybottom1': float(self.ybottom1_var.get()),
                'door_gap_w': float(self.door_gap_w_var.get()),
                'door_gap_h': float(self.door_gap_h_var.get()),
                'door_fold_l': float(self.door_fold_l_var.get()),
                'door_fold_r': float(self.door_fold_r_var.get()),
                'door_fold_t': float(self.door_fold_t_var.get()),
                'door_fold_b': float(self.door_fold_b_var.get()),
                'base_plate_shrink_top': float(self.base_plate_shrink_top_var.get()),
                'base_plate_shrink_bottom': float(self.base_plate_shrink_bottom_var.get()),
                'base_plate_shrink_left': float(self.base_plate_shrink_left_var.get()),
                'base_plate_shrink_right': float(self.base_plate_shrink_right_var.get()),
                'base_plate_bend': float(self.base_plate_bend_var.get()),
            }
        except ValueError:
            raise ValueError("請輸入有效的數字格式")

    def _active_indicator_box_groups_for_results(self):
        """Return groups only when the currently relevant Door really uses an Indicator Box.

        Single-Door follows the explicit Indicator-Box toggle. Multi-Door follows
        only the currently selected cell, so an unrelated cell cannot leak box
        dimensions into the result panel.
        """
        if self.multi_door_enabled_var.get():
            key = str(self.door_layout_selected_var.get() or "")
            state = self.door_layout_indicator_states.get(key)
            if not state:
                return None
            state = self._normalize_door_indicator_state(state)
            if state.get("mode") != "indicator_box":
                return None
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = tuple(int(v) for v in list(state.get("groups", ()))[:layers])
        else:
            if not self.is_indicator_box_var.get():
                return None
            layers = max(1, min(6, int(self.indicator_l_var.get())))
            groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
        if not groups or any(value <= 0 for value in groups):
            return None
        return groups

    def _has_any_indicator_box(self):
        """True only when at least one real Door/cell is configured as Indicator Box."""
        if not self.multi_door_enabled_var.get():
            return bool(self.is_indicator_box_var.get())
        try:
            keys = [self._door_layout_cell_key(cell) for cell in self.get_door_layout_cells()]
        except Exception:
            keys = list(getattr(self, "door_layout_indicator_states", {}).keys())
        for key in keys:
            state = self._normalize_door_indicator_state(
                getattr(self, "door_layout_indicator_states", {}).get(key)
            )
            if state.get("mode") == "indicator_box":
                return True
        return False

    def _clear_indicator_box_result_values(self):
        self.result_ib_w_var.set("-")
        self.result_ib_h_var.set("-")
        self.result_ib_door_w_var.set("-")
        self.result_ib_door_h_var.set("-")

    def _refresh_indicator_box_result_values(self, val):
        """Refresh box/small-door dimensions from actual Indicator-Box state only."""
        self._clear_indicator_box_result_values()
        layer_groups = self._active_indicator_box_groups_for_results()
        if layer_groups is None:
            return

        g_max = max(layer_groups)
        indicator_ctx = ManufacturingContext()
        ib_w, ib_h = manufacturing_api.indicator_box_unfolded_size(
            layer_groups, thickness=val['t'], context=indicator_ctx
        )
        ib_door_w, ib_door_h = manufacturing_api.indicator_small_door_unfolded_size(
            layer_groups, thickness=val['t'], context=indicator_ctx
        )
        self.result_ib_w_var.set(f"{ib_w:.2f} mm")
        self.result_ib_h_var.set(f"{ib_h:.2f} mm")
        self.result_ib_door_w_var.set(f"{ib_door_w:.2f} mm")
        self.result_ib_door_h_var.set(f"{ib_door_h:.2f} mm")
        self.indicator_g_var.set(str(g_max))

        x_left_light = 171.0
        x_right_light = 171.0 + 90.0 * max(0, g_max - 1)
        if g_max <= 1:
            hc = 1
        elif g_max <= 3:
            hc = 2
        elif g_max <= 5:
            hc = 3
        else:
            hc = 4
        if hc > 1:
            max_pitch = (x_right_light - x_left_light) / (hc - 1)
            hp = max(50.0, float(int(max_pitch // 50) * 50))
            x_mid = (x_left_light + x_right_light) / 2.0
            hx = x_mid - (hc - 1) * hp / 2.0
        else:
            hp = 150.0
            hx = 191.0 if g_max == 1 else 172.5
        self.ib_hole_start_x_var.set(f"{hx:.1f}".replace(".0", ""))
        self.ib_hole_pitch_var.set(f"{int(hp)}")
        self.ib_hole_count_var.set(str(hc))
        self.ib_hole_y_var.set("178.5")

    def update_calculations(self):
        try:
            val = self.get_float_values()
            # 1. 箱身結果尺寸必須來自與 2D/3D 相同的 authoritative Fold Chain。
            # 使用舊 calculate_z_length() 會在 3D 刪增折段後仍顯示固定 9 段寬度。
            if self.workspace_controller.box_body_profile():
                z_spec = self._box_body_part_spec(val)
                z_render = self._authoritative_render_data(
                    z_spec, self._manufacturing_context(draw_stock=False)
                )
                z_minx, z_miny, z_maxx, z_maxy = (float(v) for v in z_render.material.bounds)
                z_len = z_maxx - z_minx
                z_h = z_maxy - z_miny
            else:
                # Before Phase6 has ever committed a Fold Chain, retain the
                # original main-GUI calculation path and its legacy corner state.
                z_len = ae.calculate_z_length(
                    val['zl1'], val['zl2'], val['zr1'], val['zr2'], val['z_comp'],
                    val['w'], val['d'], val['t'], val['fw']
                )
                z_h = self._box_body_finished_height(val)
            
            # 2. 封頭／封尾結果尺寸。Phase6 一旦提交 linked Fold Profile，
            # 主 2D 必須直接量同一份 authoritative FinalScene；不得再回到
            # ytop1 + FW + D 的 legacy 公式，否則 3D 自動刪折後主畫面仍會
            # 顯示舊 300 mm。
            baseline = self._baseline_source_model()
            existing_parts = self._phase6_current_existing_parts()
            committed_profiles = self.workspace_controller.part_profiles_snapshot()
            summary_part = next((
                k for k in ("head", "tail")
                if k in existing_parts and committed_profiles.get(k)
            ), None)
            has_endcap = bool({"head", "tail"} & existing_parts)
            if not has_endcap:
                y_w = y_d = None
            elif summary_part is not None:
                y_spec = self._end_cap_part_spec(val, is_tail=(summary_part == "tail"))
                y_render = self._authoritative_render_data(
                    y_spec, self._manufacturing_context(draw_stock=False)
                )
                y_minx, y_miny, y_maxx, y_maxy = (float(v) for v in y_render.material.bounds)
                y_w = y_maxx - y_minx
                y_d = y_maxy - y_miny
            else:
                if baseline:
                    geom = ae.get_stretched_end_cap_data(
                        baseline, val['w'], val['h'], val['d'], val['t'],
                        FW_val=val['fw'], is_tail=False
                    )
                    y_w = geom.params['total_width']
                    y_d = geom.params['total_depth']
                else:
                    y_w = ae.calculate_y_width(val['yl1'], val['yr1'], val['w'], val['t'])
                    y_d = ae.calculate_y_depth(
                        val['ytop1'], val['ybottom1'], val['d'], val['t'], val['fw']
                    )
            
            # 3. 計算門 Door。不存在的板件不建立/計算預覽資料。
            door_material_fw = self._door_material_frame_width(val['fw'], val['t'])
            if "door" not in existing_parts:
                door_w = door_h = None
            elif self.multi_door_enabled_var.get():
                cell = self.get_selected_door_layout_cell()
                door_w, door_h = ae.calculate_door_blank_size(
                    cell.start_width, cell.start_height, val['t'], door_material_fw,
                    val['door_gap_w'], val['door_gap_h'],
                    val['door_fold_l'], val['door_fold_r'],
                    val['door_fold_t'], val['door_fold_b'],
                    frame_edges=cell.edges,
                )
            elif baseline:
                try:
                    geom_door = ae.get_stretched_door_data(baseline, val['w'], val['h'], val['t'], door_material_fw,
                                                          val['door_gap_w'], val['door_gap_h'],
                                                          val['door_fold_l'], val['door_fold_r'],
                                                          val['door_fold_t'], val['door_fold_b'])
                    door_w = geom_door.params['total_width']
                    door_h = geom_door.params['total_depth']
                except Exception:
                    door_w, door_h = ae.calculate_door_blank_size(
                        val['w'], val['h'], val['t'], door_material_fw,
                        val['door_gap_w'], val['door_gap_h'],
                        val['door_fold_l'], val['door_fold_r'],
                        val['door_fold_t'], val['door_fold_b']
                    )
            else:
                door_w, door_h = ae.calculate_door_blank_size(
                    val['w'], val['h'], val['t'], door_material_fw,
                    val['door_gap_w'], val['door_gap_h'],
                    val['door_fold_l'], val['door_fold_r'],
                    val['door_fold_t'], val['door_fold_b']
                )
            
            # 3.5 計算底板
            if "base_plate" in existing_parts:
                base_plate_w = val['w'] - val['base_plate_shrink_left'] - val['base_plate_shrink_right'] + 2.0 * val['base_plate_bend']
                base_plate_h = val['h'] - val['base_plate_shrink_top'] - val['base_plate_shrink_bottom'] + 2.0 * val['base_plate_bend']
            else:
                base_plate_w = base_plate_h = None
            
            self.result_z_var.set(f"{z_len:.2f} mm")
            self.result_z_h_var.set(f"{z_h:.2f} mm")
            self.result_y_w_var.set("-" if y_w is None else f"{y_w:.2f} mm")
            self.result_y_d_var.set("-" if y_d is None else f"{y_d:.2f} mm")
            self.result_door_w_var.set("-" if door_w is None else f"{door_w:.2f} mm")
            self.result_door_h_var.set("-" if door_h is None else f"{door_h:.2f} mm")
            self.result_base_plate_w_var.set("-" if base_plate_w is None else f"{base_plate_w:.2f} mm")
            self.result_base_plate_h_var.set("-" if base_plate_h is None else f"{base_plate_h:.2f} mm")
            
            # 只有存在的指示燈板件才計算；不存在就保持完全空白。
            if {"indicator_box", "indicator_door"} & existing_parts:
                try:
                    self._refresh_indicator_box_result_values(val)
                except Exception:
                    self._clear_indicator_box_result_values()
            else:
                self._clear_indicator_box_result_values()
            self._phase6_refresh_presence_ui(existing_parts)
            
            # 重新繪製預覽
            self.draw_preview()
            
        except Exception:
            # 數值尚未輸入完整時，不顯示錯誤，只把計算結果顯示為 "-"
            self.result_z_var.set("-")
            self.result_z_h_var.set("-")
            self.result_y_w_var.set("-")
            self.result_y_d_var.set("-")
            self.result_door_w_var.set("-")
            self.result_door_h_var.set("-")
            self.result_base_plate_w_var.set("-")
            self.result_base_plate_h_var.set("-")
            self.result_ib_w_var.set("-")
            self.result_ib_h_var.set("-")
            self.result_ib_door_w_var.set("-")
            self.result_ib_door_h_var.set("-")


    def draw_preview(self):
        selected_tab = self.notebook.select()
        if not selected_tab:
            return
        tab_widget = self.root.nametowidget(selected_tab)
        
        try:
            val = self.get_float_values()
        except ValueError:
            return  # 輸入有誤時不繪圖
            
        existing = self._phase6_current_existing_parts()
        if tab_widget == self.tab_z and "box_body" in existing:
            self.draw_box_body(val)
        elif tab_widget == self.tab_head and "head" in existing:
            self.draw_end_cap(val, self.canvas_head, '封頭', is_tail=False)
        elif tab_widget == self.tab_tail and "tail" in existing:
            self.draw_end_cap(val, self.canvas_tail, '封尾', is_tail=True)
        elif tab_widget == self.tab_door and "door" in existing:
            self.draw_door(val)
        elif hasattr(self, 'tab_base_plate') and tab_widget == self.tab_base_plate and "base_plate" in existing:
            self.draw_base_plate(val)
        elif hasattr(self, 'tab_indicator_box') and tab_widget == self.tab_indicator_box and "indicator_box" in existing:
            self.draw_indicator_box(val)
        elif hasattr(self, 'tab_indicator_door') and tab_widget == self.tab_indicator_door and "indicator_door" in existing:
            self.draw_indicator_door(val)

    def draw_grid(self, canvas, w, h, tags=None):
        """
        在畫布背景上繪製科技感的微弱網格
        """
        grid_size = 40
        kwargs = {"fill": "#1c1c22", "width": 1}
        if tags:
            kwargs["tags"] = tags
        for x in range(0, w, grid_size):
            canvas.create_line(x, 0, x, h, **kwargs)
        for y in range(0, h, grid_size):
            canvas.create_line(0, y, w, y, **kwargs)

    def _box_body_face_at_canvas_point(self, x, y):
        for face_key, bounds in self.box_body_face_bounds.items():
            x1, y1, x2, y2 = bounds
            if x1 <= x <= x2 and y1 <= y <= y2:
                return face_key
        return None

    def select_box_body_face(self, face_key):
        if face_key not in {"left", "back", "right"}:
            return
        self.box_body_face_selected_var.set(face_key)
        # Selection must stay lightweight so a rapid second click is not delayed
        # by rebuilding the whole preview (same rule as Multi-Door).
        for key in ("left", "back", "right"):
            try:
                self.canvas_z.itemconfigure(
                    f"box_body_face_{key}",
                    outline=(self.COLOR_ACCENT if key == face_key else "#30d158"),
                    width=(3 if key == face_key else 2),
                )
            except tk.TclError:
                pass

    def on_box_body_canvas_press(self, event):
        hit = self._box_body_face_at_canvas_point(event.x, event.y)
        if hit is None:
            self._box_body_face_last_click = None
            return "break"
        event_time = int(getattr(event, "time", 0) or 0)
        if not event_time:
            event_time = int(time.monotonic() * 1000)
        last = self._box_body_face_last_click
        is_manual_double = False
        if last is not None:
            last_face, last_time = last
            delta = event_time - last_time if event_time and last_time else 999999
            is_manual_double = last_face == hit and 0 <= delta <= 650
        if is_manual_double:
            self._box_body_face_last_click = None
            self.open_box_body_face_editor(hit)
        else:
            self._box_body_face_last_click = (hit, event_time)
            self.select_box_body_face(hit)
        return "break"

    def _box_body_baseline_faces(self, val):
        model = self._baseline_source_model()
        if not model or not ae.has_baseline_part(model, "箱身.dxf"):
            return {"left": [], "back": [], "right": []}
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        source_fp = ae.baseline_source_fingerprint(ae.baseline_expected_path(model, "箱身.dxf"))
        cache_key = (
            source_fp, model, val['w'], val['h'], val['d'], val['t'], val['fw'],
            val['zl1'], val['zl2'], val['zr1'], val['zr2'], val['z_comp'],
            head_policy, tail_policy,
        )
        if cache_key not in self._box_body_baseline_face_cache:
            self._box_body_baseline_face_cache[cache_key] = ae.get_box_body_baseline_face_features(
                model,
                w=val['w'], h=val['h'], d=val['d'], t=val['t'], fw=val['fw'],
                zl1=val['zl1'], zl2=val['zl2'], zr1=val['zr1'], zr2=val['zr2'],
                z_comp=val['z_comp'],
                head_corner_policy=head_policy, tail_corner_policy=tail_policy,
            )
        return self._box_body_baseline_face_cache[cache_key]

    def _box_body_face_baseline_scene(self, face_key, val):
        resolved = self._box_body_baseline_faces(val).get(face_key, [])
        if not resolved:
            return None
        scene = DrawingScene()
        scene.extend(resolved_features_to_primitives(resolved))
        return scene

    def open_box_body_face_editor(self, face_key):
        if face_key not in {"left", "back", "right"}:
            messagebox.showerror("開孔失敗", f"未知箱身面: {face_key}")
            return
        try:
            val = self.get_float_values()
        except ValueError as exc:
            messagebox.showerror("輸入錯誤", str(exc))
            return
        dims = box_body_face_dimensions(w=val['w'], h=val['h'], d=val['d'])
        width, height = dims[face_key]
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        bottom_outer, top_outer = box_body_vertical_offsets(
            val['t'], head_corner_policy=head_policy, tail_corner_policy=tail_policy
        )
        surface = feature_surface_from_rect(
            f"box_body_{face_key}",
            Vec2(val['t'], bottom_outer),
            Vec2(width - val['t'], height - top_outer),
        )
        reference_guide = RectGuide(
            Vec2(0.0, 0.0), Vec2(width, height), "enclosure_boundary"
        )
        title = {"left": "箱身左側", "back": "箱身背面", "right": "箱身右側"}[face_key]
        self.box_body_face_selected_var.set(face_key)
        self._open_unified_hole_editor(
            f"box_body_{face_key}", title, surface, width, height,
            reference_guide=reference_guide,
            feature_list_override=self.box_body_face_features[face_key],
            baseline_scene=self._box_body_face_baseline_scene(face_key, val),
            baseline_status_text=ae.box_body_baseline_source_label(self.baseline_var.get()),
            on_close=lambda: self.draw_box_body(self.get_float_values()),
        )

    def draw_box_body(self, val):
        """Render the authoritative unfolded Box Body; face editing is only an overlay/hit-zone."""
        canvas = self.canvas_z
        canvas.delete("all")
        self.box_body_face_bounds = {}

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        # Main page remains the authoritative StripFoldChain manufacturing view.
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        spec = self._box_body_part_spec(val)
        if spec.fold_profile:
            result = build_box_body_result_from_fold_profile(
                spec.fold_profile, h=val['h'], t=val['t'],
                head_corner_policy=head_policy, tail_corner_policy=tail_policy,
            )
        else:
            result = build_box_body_result(
                w=val['w'], h=val['h'], d=val['d'], t=val['t'], fw=val['fw'],
                zl1=val['zl1'], zl2=val['zl2'], zr1=val['zr1'], zr2=val['zr2'],
                z_comp=val['z_comp'],
                head_corner_policy=head_policy, tail_corner_policy=tail_policy,
            )
        render_data = self._authoritative_render_data(
            spec, self._manufacturing_context(draw_stock=False)
        )
        minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
        z_len = maxx - minx
        z_height = maxy - miny

        transform, offset_x, offset_y, scale, _material_top = _phase6_2d_material_viewport(
            (minx, miny, maxx, maxy), cw, ch
        )

        if self.draw_stock_var.get():
            sx0, sy0 = transform.world_to_canvas(Vec2(minx, miny))
            sx1, sy1 = transform.world_to_canvas(Vec2(maxx, maxy))
            canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4))

        # CUTTING/BEND/baseline fixed processing/user features all come from the
        # same final DrawingScene that Phase6 3D consumes.
        render_drawing_scene(
            canvas, render_data.scene, transform, skip_layers=("CHECK", "STOCK")
        )
        warnings = tuple(getattr(render_data, "warnings", ()) or ())
        warning_text = (
            "\n⚠ " + "；".join(str(getattr(item, "message", item)) for item in warnings)
            if warnings else ""
        )

        baseline = self._baseline_source_model()

        # Face hit-zones still use structural topology only for editor navigation;
        # they never redraw manufacturing geometry.
        contexts = box_body_face_contexts_from_strip(
            result.topology, w=val['w'], h=val['h'], d=val['d'], t=val['t'],
            head_corner_policy=head_policy, tail_corner_policy=tail_policy,
        )
        # Faces are only hit-zones projected onto the authoritative unfolded strip.
        # They do not replace, resize, or remove any manufacturing geometry/BEND line.
        selected = self.box_body_face_selected_var.get()
        for face_key in ("left", "back", "right"):
            ctx = contexts[face_key]
            x1, y_bottom = transform.world_to_canvas(Vec2(ctx.unfolded_min_x, 0.0))
            x2, y_top = transform.world_to_canvas(Vec2(ctx.unfolded_max_x, z_height))
            bounds = (min(x1, x2), min(y_top, y_bottom), max(x1, x2), max(y_top, y_bottom))
            self.box_body_face_bounds[face_key] = bounds
            canvas.create_rectangle(
                *bounds,
                outline=(self.COLOR_ACCENT if face_key == selected else ""),
                width=(2 if face_key == selected else 1),
                dash=(4, 3),
                tags=("box_body_face_hit_zone", f"box_body_face_{face_key}"),
            )

        baseline_status = ae.box_body_baseline_source_label(baseline)
        hint_text = "箱身展開預覽 (Z-Body)"
        canvas.create_text(cw / 2, offset_y - z_height * scale - 20,
                           text=f"W = {z_len:.2f} mm", fill="#30d158", font=('Consolas', 10, 'bold'))
        canvas.create_text(offset_x + z_len * scale + 45, offset_y - (z_height * scale) / 2,
                           text=f"H = {z_height:.2f} mm", fill="#30d158", font=('Consolas', 10, 'bold'), angle=90)
        stock_hint = "  STOCK 母材外框: 青色虛線" if self.draw_stock_var.get() else ""
        canvas.create_text(
            25, 25, anchor=tk.NW,
            text=f"{hint_text}\n{baseline_status}\n外輪廓 (CUTTING): 綠色實線  折彎線 (BEND): 藍色虛線{stock_hint}\n雙擊左側/背面/右側完成面進入箱體定位編輯{warning_text}",
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )
        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=False)

        self.last_box_body_face_overview = {
            "mode": "unfolded_with_face_hit_zones",
            "dimensions": box_body_face_dimensions(w=val['w'], h=val['h'], d=val['d']),
            "unfolded_size": (z_len, z_height),
            "transform": transform,
            "contexts": contexts,
            "baseline_status": baseline_status,
        }

    def draw_end_cap(self, val, canvas, part_label='封頭/尾', is_tail=False):
        """Render the exact normalized End Cap scene used by DXF output (WYSIWYG)."""
        canvas.delete("all")
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return
        self.draw_grid(canvas, cw, ch)

        baseline = self._baseline_source_model()
        try:
            spec = self._end_cap_part_spec(val, is_tail=is_tail)
            render_data = self._authoritative_render_data(
                spec, self._manufacturing_context(draw_stock=False)
            )
            scene = render_data.scene
            minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
            y_w = maxx - minx
            y_d = maxy - miny
            if is_unknown_model(self.baseline_var.get()):
                baseline_hint = " (自訂 / Final Part Geometry)"
            elif baseline:
                baseline_hint = f" ({baseline} Final Part Geometry)"
            else:
                baseline_hint = " (Y-Cap Final Part Geometry)"
        except Exception as exc:
            canvas.create_text(
                cw / 2, ch / 2, text=f"封頭尾載入失敗: {exc}",
                fill="#ff3333", font=('Microsoft JhengHei', 10, 'bold')
            )
            draw_hole_editor_hint(canvas, cw, endcap=True)
            return

        transform, offset_x, offset_y, scale, _material_top = _phase6_2d_material_viewport(
            (minx, miny, maxx, maxy), cw, ch
        )

        render_drawing_scene(canvas, scene, transform, skip_layers=("CHECK", "STOCK"))

        if self.draw_stock_var.get():
            sx0, sy0 = transform.world_to_canvas(Vec2(minx, miny))
            sx1, sy1 = transform.world_to_canvas(Vec2(maxx, maxy))
            canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline="#00d4d4", width=1.5, dash=(8, 4)
            )

        canvas.create_text(
            cw / 2, offset_y - y_d * scale - 20,
            text=f"W = {y_w:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold')
        )
        canvas.create_text(
            offset_x + y_w * scale + 45, offset_y - (y_d * scale) / 2,
            text=f"H = {y_d:.2f} mm", fill="#30d158",
            font=('Consolas', 10, 'bold'), angle=90
        )
        stock_hint = "  STOCK: 青色虛線" if self.draw_stock_var.get() else ""

        tail_hint = "  [封尾]" if is_tail else "  [封頭]"
        canvas.create_text(
            25, 25, anchor=tk.NW,
            text=f"{part_label}展開預覽{baseline_hint}\n外輪廓: 綠色  折彎: 藍色  孔洞: 綠色{stock_hint}{tail_hint}",
            fill=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 9),
            width=max(180, int(cw * 0.48)), tags=("phase6_preview_hint",),
        )
        _draw_phase6_corner_dimension_overlay(canvas, render_data, cw)
        draw_hole_editor_hint(canvas, cw, endcap=True)

    def _manufacturing_context(self, *, draw_stock=False):
        """GUI-owned execution context for the headless manufacturing boundary."""
        return ManufacturingContext(draw_stock=bool(draw_stock), overwrite=True)

    def _box_body_part_spec_from_values(
        self, val, *, model_name, features, face_features,
        head_corner_policy=None, tail_corner_policy=None, fold_profile=None,
        structure_state=None, head_ybottom1=None, tail_ybottom1=None,
    ):
        def resolved_ybottom(part_key):
            profiles = self.workspace_controller.profile_for(part_key) or {}
            rows = list(dict(profiles).get("Y", ()) or ())
            for row in rows:
                if str(row.get("phase6_key") or "") == "ybottom1":
                    return float(engine_segment_length_to_ui(row))
            return float(val.get("ybottom1", ae.ybottom1_def))

        source_structure = (
            self.workspace_controller.box_body_structure_state()
            if structure_state is None else deepcopy(dict(structure_state or {}))
        )
        structure_state = cabinet_family_policy.resolve_box_body_structure_state(
            model_name, source_structure
        )

        return BoxBodyPartSpec(
            width=float(val['w']), height=float(val['h']), depth=float(val['d']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name,
            zl1=float(val['zl1']), zl2=float(val['zl2']),
            zr1=float(val['zr1']), zr2=float(val['zr2']),
            z_comp=float(val['z_comp']),
            fold_profile=profile_to_fold_segments(
                fold_profile if fold_profile is not None else (self.workspace_controller.box_body_profile() or ())
            ),
            features=tuple(features or ()),
            face_features={k: tuple(v) for k, v in dict(face_features or {}).items()},
            head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
            structure_state=(
                self.workspace_controller.box_body_structure_state()
                if structure_state is None else deepcopy(dict(structure_state or {}))
            ),
            head_ybottom1=(resolved_ybottom("head") if head_ybottom1 is None else float(head_ybottom1)),
            tail_ybottom1=(resolved_ybottom("tail") if tail_ybottom1 is None else float(tail_ybottom1)),
        )

    def _box_body_part_spec(self, val):
        head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
        return self._box_body_part_spec_from_values(
            val, model_name=self._baseline_source_model(),
            features=self.surface_features["box_body"],
            face_features=self.box_body_face_features,
            head_corner_policy=head_policy, tail_corner_policy=tail_policy,
        )

    def _end_cap_part_spec_from_values(
        self, val, *, model_name, is_tail, holes, corner_policy=None, fold_profiles=None,
        depth_comp_t=None, resolved_assembly_relief_cuts=(),
        box_body_formed_fw_left=None, box_body_formed_fw_right=None,
        box_body_structure_state=None, endcap_bottom_wrap_state=None, assembly_joints=None,
    ):
        profiles = dict(fold_profiles or {})
        x_rows = [dict(row) for row in profiles.get("X", ())]
        y_rows = [dict(row) for row in profiles.get("Y", ())]

        if depth_comp_t is None:
            depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(model_name)

        # Scalar folds remain the canonical/legacy request values.  Fold Profile
        # precedence is resolved exactly once inside AE manufacturing_api.
        fold_left = float(val['yl1'])
        fold_right = float(val['yr1'])
        fold_top = float(val['ytop1'])
        fold_bottom = float(val['ybottom1'])

        if box_body_structure_state is None:
            controller = getattr(self, "workspace_controller", None)
            getter = getattr(controller, "box_body_structure_state", None)
            resolved_structure_state = deepcopy(dict(getter() if callable(getter) else {}))
        else:
            resolved_structure_state = deepcopy(dict(box_body_structure_state or {}))
        if assembly_joints is None:
            joint_state = dict(getattr(self, "assembly_joint_state", {}) or {})
            resolved_assembly_joints = tuple(deepcopy(joint_state.get("assembly_joints", ())) or ())
        else:
            resolved_assembly_joints = tuple(deepcopy(tuple(assembly_joints or ())))
            joint_state = {"assembly_joints": resolved_assembly_joints}
        if cabinet_family_policy.supports_bottom_wrap_controls(model_name):
            try:
                part_key = "tail" if is_tail else "head"
                wrap_state = endcap_bottom_wrap_state
                if wrap_state is None:
                    wrap_state = getattr(self, "endcap_bottom_wrap_state", None)
                if wrap_state is None:
                    wrap_state = normalize_endcap_bottom_wrap_state({"model": model_name})
                projection_snapshot = {"model": model_name, **joint_state}
                item = resolve_endcap_bottom_wrap(projection_snapshot, part_key, state=wrap_state)
                # enabled is graph-owned; Receiving state retains only geometric
                # reserve inputs for the certified BOTTOM WRAP formula.
                resolved_structure_state = cabinet_family_policy.set_bottom_relief_reserves(
                    model_name,
                    resolved_structure_state,
                    reserve_u=item["reserve_u"],
                    reserve_v=item["reserve_v"],
                )
            except Exception:
                pass

        return EndCapPartSpec(
            width=float(val['w']), height=float(val['h']), depth=float(val['d']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name, is_tail=bool(is_tail),
            fold_left=fold_left, fold_right=fold_right,
            fold_top=fold_top, fold_bottom=fold_bottom,
            box_fold_left=float(val['zl1']), box_fold_right=float(val['zr1']),
            box_body_formed_fw_left=(None if box_body_formed_fw_left is None else float(box_body_formed_fw_left)),
            box_body_formed_fw_right=(None if box_body_formed_fw_right is None else float(box_body_formed_fw_right)),
            box_body_structure_state=resolved_structure_state,
            assembly_joints=resolved_assembly_joints,
            fold_profile_x=profile_to_fold_segments(x_rows),
            fold_profile_y=profile_to_fold_segments(y_rows),
            holes=tuple(holes or ()), corner_policy=corner_policy,
            depth_comp_t=float(depth_comp_t),
            resolved_assembly_relief_cuts=tuple(
                tuple((float(x), float(y)) for x, y in polygon)
                for polygon in tuple(resolved_assembly_relief_cuts or ())
                if len(polygon) >= 3
            ),
        )

    @staticmethod
    def _phase6_relief_profile_signature(profile):
        rows = []
        for row in list(profile or ()):
            row = dict(row or {})
            rows.append((
                str(row.get("phase6_key") or ""),
                round(float(row.get("len", row.get("length", 0.0)) or 0.0), 6),
                None if row.get("angle") is None else round(float(row.get("angle") or 0.0), 6),
                str(row.get("core") or ""),
            ))
        return tuple(rows)

    def _resolved_committed_assembly_relief_cuts(self, key, val, stored_profiles):
        state = deepcopy(getattr(self, "assembly_relief_state", {}) or {})
        if not bool(state.get("enabled")):
            return ()
        part = dict((state.get("parts") or {}).get(str(key), {}) or {})
        if not bool(part.get("verified")) and not bool(part.get("canonical_accepted")):
            return ()
        trust_level = str(part.get("trust_level") or "")
        rule_id = part.get("rule_id")
        rule_revision = part.get("rule_revision")
        if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
            from ae_engine.certified_relief_registry import certified_rule_revision_exists
            try:
                active_revision = certified_rule_revision_exists(str(rule_id), int(rule_revision))
            except (TypeError, ValueError):
                active_revision = False
            if not active_revision:
                return ()
        source = dict(state.get("source") or {})
        from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION
        try:
            if int(source.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
                return ()
        except (TypeError, ValueError):
            return ()

        # Replay identity is mechanical, not the high-level assembly mirror.
        # Graph/family/structure must all match the state that was shadow-verified.
        from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
        import hashlib as _hashlib, json as _json
        try:
            current_graph_fp = resolved_joint_graph_fingerprint(dict(getattr(self, "assembly_joint_state", {}) or {}))
        except Exception:
            return ()
        if not str(source.get("joint_graph_fingerprint") or "") or str(source.get("joint_graph_fingerprint")) != current_graph_fp:
            return ()
        controller = getattr(self, "workspace_controller", None)
        structure_getter = getattr(controller, "box_body_structure_state", None)
        current_structure = structure_getter() if callable(structure_getter) else {}
        structure_payload = _json.dumps(current_structure or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        current_structure_fp = _hashlib.sha256(structure_payload.encode("utf-8")).hexdigest()
        if not str(source.get("family_structure_fingerprint") or "") or str(source.get("family_structure_fingerprint")) != current_structure_fp:
            return ()
        family_getter = getattr(self, "_baseline_source_model", None)
        current_family = str(family_getter() if callable(family_getter) else "")
        if str(source.get("cabinet_family") or "") != current_family:
            return ()

        saved_formed = dict(source.get("box_body_formed_fw") or {})
        if saved_formed:
            body_profile_getter = getattr(controller, "box_body_profile", None)
            current_formed_left, current_formed_right = formed_box_body_fw_widths(
                body_profile_getter() if callable(body_profile_getter) else (),
                float(val.get("t", 0.0) or 0.0),
            )
            for side, current in (("left", current_formed_left), ("right", current_formed_right)):
                try:
                    if current is None or abs(float(saved_formed[side]) - float(current)) > 1e-6:
                        return ()
                except (KeyError, TypeError, ValueError):
                    return ()

        source_rules = dict(source.get("registry_rules") or {})
        if trust_level in {"CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"} and rule_id:
            saved_rule = dict(source_rules.get(str(key)) or {})
            try:
                if str(saved_rule.get("rule_id") or "") != str(rule_id):
                    return ()
                if int(saved_rule.get("revision", 0) or 0) != int(rule_revision):
                    return ()
            except (TypeError, ValueError):
                return ()

        source_profiles = dict(source.get("part_profiles") or {})
        expected = dict(source_profiles.get(str(key), {}) or {})
        current_scalars = {
            "w": float(val.get("w", 0.0)),
            "h": float(val.get("h", 0.0)),
            "d": float(val.get("d", 0.0)),
            "t": float(val.get("t", 0.0)),
            "fw": float(val.get("fw", 0.0)),
            "zl1": float(val.get("zl1", ae.zl1_def)),
            "zr1": float(val.get("zr1", ae.zr1_def)),
            "yl1": float(val.get("yl1", ae.yl1_def)),
            "yr1": float(val.get("yr1", ae.yr1_def)),
            "ytop1": float(val.get("ytop1", ae.ytop1_def)),
            "ybottom1": float(val.get("ybottom1", ae.ybottom1_def)),
        }
        for name, current in current_scalars.items():
            if name not in source:
                continue
            # ytop1 is an optional legacy aggregate. Once a saved Y Fold
            # Profile exists, that profile is the authoritative topology/length
            # fingerprint; comparing the legacy scalar as well can reject a
            # valid committed 3D relief when the top fold was structurally
            # removed (the editor adapter correctly reports ytop1=0).
            if name == "ytop1" and "Y" in expected:
                continue
            try:
                if abs(float(source[name]) - current) > 1e-6:
                    return ()
            except (TypeError, ValueError):
                return ()
        for axis in ("X", "Y"):
            expected_rows = expected.get(axis)
            if expected_rows is None:
                continue
            current_rows = dict(stored_profiles or {}).get(axis, ())
            if self._phase6_relief_profile_signature(expected_rows) != self._phase6_relief_profile_signature(current_rows):
                return ()
        cuts = []
        for polygon in list(part.get("cuts") or ()):
            coords = tuple((float(point[0]), float(point[1])) for point in polygon if len(point) >= 2)
            if len(coords) >= 3:
                cuts.append(coords)
        return tuple(cuts)

    def _end_cap_part_spec(self, val, *, is_tail):
        key = "tail" if is_tail else "head"
        stored_profiles = self.workspace_controller.profile_for(key)
        local_val = dict(val)
        local_val["fw"] = self._effective_endcap_fw(key, val.get("fw", 25.0))
        stored_profiles = _endcap_profiles_for_assembly(
            local_val, stored_profiles, self._current_box_assembly_type(), key
        )
        resolved_cuts = self._resolved_committed_assembly_relief_cuts(key, local_val, stored_profiles)
        formed_fw_left, formed_fw_right = formed_box_body_fw_widths(
            self.workspace_controller.box_body_profile() or (), local_val.get("t", 0.0)
        )
        return self._end_cap_part_spec_from_values(
            local_val, model_name=self._baseline_source_model(), is_tail=is_tail,
            holes=(self.tail_holes if is_tail else self.head_holes),
            corner_policy=(
                self._manual_corner_policy(key, local_val['fw'])
            ),
            fold_profiles=stored_profiles,
            depth_comp_t=self._endcap_depth_comp_t_for_family(self._baseline_source_model()),
            resolved_assembly_relief_cuts=resolved_cuts,
            box_body_formed_fw_left=formed_fw_left,
            box_body_formed_fw_right=formed_fw_right,
            box_body_structure_state=self.workspace_controller.box_body_structure_state(),
        )

    def _door_part_spec_from_values(
        self, val, *, model_name, features, indicator_hole=None, door_indicator=None,
        door_indicator_offset=(0.0, 0.0), use_box_distance=False, corner_policy=None,
        frame_edges=None, indicator_window_groups=None,
    ):
        """Canonical Door state -> DoorPartSpec mapping used by 2D and 3D."""
        return DoorPartSpec(
            width=float(val['w']), height=float(val['h']),
            thickness=float(val['t']), frame_width=float(val['fw']),
            model_name=model_name,
            gap_w=float(val['door_gap_w']), gap_h=float(val['door_gap_h']),
            fold_left=float(val['door_fold_l']), fold_right=float(val['door_fold_r']),
            fold_top=float(val['door_fold_t']), fold_bottom=float(val['door_fold_b']),
            frame_edges=frame_edges or DoorFrameEdges(),
            features=tuple(features or ()), feature_space="legacy_unfolded",
            indicator_hole=indicator_hole,
            door_indicator=tuple(door_indicator) if door_indicator else None,
            door_indicator_offset=(float(door_indicator_offset[0]), float(door_indicator_offset[1])),
            use_box_distance=bool(use_box_distance),
            corner_policy=corner_policy,
            indicator_window_groups=(tuple(indicator_window_groups) if indicator_window_groups else None),
            nameplate_center_datum_top=(
                None if getattr(self, "door_nameplate_center_datum_top", None) is None
                else float(self.door_nameplate_center_datum_top)
            ),
        )

    def _single_door_part_spec(self, val, *, indicator_hole=None, door_indicator=None):
        return self._door_part_spec_from_values(
            val,
            model_name=self._baseline_source_model(),
            features=self.surface_features["door"],
            indicator_hole=indicator_hole,
            door_indicator=door_indicator,
            door_indicator_offset=(self.door_indicator_offset_x, self.door_indicator_offset_y),
            use_box_distance=bool(self.is_box_dist_var.get()),
            corner_policy=(
                self._manual_corner_policy(
                    'door', self._door_material_frame_width(val['fw'], val['t'])
                )
            ),
        )

    def _door_layout_part_spec(self, cell, val):
        key = self._door_layout_cell_key(cell)
        state = self._door_layout_indicator_state_for_key(key)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        mode = state.get("mode", "indicator" if state.get("enabled") else "none")
        door_val = dict(val)
        door_val["w"] = cell.start_width
        door_val["h"] = cell.start_height
        return self._door_part_spec_from_values(
            door_val,
            model_name=self._baseline_source_model(),
            frame_edges=cell.edges,
            features=self.door_layout_features.get(key, []),
            indicator_hole=(manufacturing_api.indicator_box_opening_size(groups, thickness=val['t'])
                            if mode == "indicator_box" else None),
            door_indicator=(groups if mode == "indicator" else None),
            door_indicator_offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
            use_box_distance=bool(state.get("is_box_dist", False)),
            corner_policy=(
                self._manual_corner_policy(
                    'door', self._door_material_frame_width(val['fw'], val['t'])
                )
            ),
        )

    def _validate_indicator_state_fit(self, state, *, finished_width, finished_height, thickness):
        state = self._normalize_door_indicator_state(state)
        mode = state.get("mode", "none")
        if mode == "none":
            return (0.0, 0.0)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        return manufacturing_api.validate_door_indicator_fit(
            mode=mode, groups=groups,
            finished_width=float(finished_width), finished_height=float(finished_height),
            thickness=float(thickness),
            offset=(float(state.get("offset_x", 0.0)), float(state.get("offset_y", 0.0))),
        )

    def _validate_single_door_indicator_fit(self, val, state=None):
        state = self._single_door_indicator_state_snapshot() if state is None else state
        spec = self._single_door_part_spec(val)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
        return self._validate_indicator_state_fit(
            state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
        )

    def _validate_door_layout_indicator_fit(self, cell, state, val):
        spec = self._door_layout_part_spec(cell, val)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(spec)
        return self._validate_indicator_state_fit(
            state, finished_width=finished_w, finished_height=finished_h, thickness=val['t']
        )

    def _base_plate_part_spec_from_values(self, val, *, features, corner_policy=None):
        return BasePlatePartSpec(
            width=float(val['w']), height=float(val['h']), thickness=float(val['t']),
            shrink_top=float(val['base_plate_shrink_top']),
            shrink_bottom=float(val['base_plate_shrink_bottom']),
            shrink_left=float(val['base_plate_shrink_left']),
            shrink_right=float(val['base_plate_shrink_right']),
            bend=float(val['base_plate_bend']),
            features=tuple(features or ()), corner_policy=corner_policy,
            box_body_structure_state=self.workspace_controller.box_body_structure_state(),
            box_body_fold_profile=profile_to_fold_segments(self.workspace_controller.box_body_profile() or ()),
            model_name=str(val.get('model', '')).strip() or None,
        )

    def _base_plate_part_spec(self, val):
        return self._base_plate_part_spec_from_values(
            val, features=self.surface_features["base_plate"],
            corner_policy=(
                self._manual_corner_policy('base_plate', val['fw'])
            ),
        )

    def _indicator_box_part_spec_from_values(self, val, layer_groups, *, features):
        return IndicatorBoxPartSpec(
            layer_groups=tuple(int(v) for v in layer_groups),
            thickness=float(val['t']), model_name=None,
            features=tuple(features or ()), corner_policy=None,
        )

    def _indicator_box_part_spec(self, val, layer_groups, *, features):
        return IndicatorBoxPartSpec(
            layer_groups=tuple(int(v) for v in layer_groups),
            thickness=float(val['t']), model_name=None,
            features=tuple(features or ()), corner_policy=None,
        )

    def _indicator_door_part_spec_from_values(self, val, layer_groups, *, features):
        groups = tuple(int(v) for v in layer_groups)
        policy = replace(
            manufacturing_api.resolve_policy(),
            frame_width=float(val['fw']),
            door_gap_w=float(val['door_gap_w']),
            door_gap_h=float(val['door_gap_h']),
            indicator_small_door_fold=float(
                val.get('indicator_door_fold', getattr(ae, 'indicator_small_door_fold_def', 19.0))
            ),
        )
        context = ManufacturingContext(policy=policy, draw_stock=False)
        base = manufacturing_api.indicator_small_door_spec(
            groups, thickness=float(val['t']), context=context
        )
        spec = replace(
            base, features=tuple(features or ()), feature_space="legacy_unfolded",
            corner_policy=None, model_name=None,
        )
        return spec, context

    def _indicator_door_part_spec(self, val, layer_groups, *, features):
        spec, _context = self._indicator_door_part_spec_from_values(
            val, layer_groups, features=features
        )
        return spec

    def _indicator_component_editor_contexts(self, state, val, *, box_features, door_features):
        """Build the two editable members of one Door-owned indicator-box assembly."""
        state = self._normalize_door_indicator_state(state)
        layers = max(1, min(6, int(state.get("layers", 1))))
        groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
        if not groups:
            groups = (2,)

        # Box and small door are global shared parts, independent of the cabinet model.
        # GUI identifies the part role only; AE owns the physical shared-baseline namespace.
        box_corner_policy = None
        box_data = ae.get_stretched_indicator_box_data(
            None, groups, val['t'], corner_policy=None
        )
        box_baseline_scene = box_data.scene
        box_status = ae.indicator_shared_baseline_source_label("盒子.dxf")
        box_surface = feature_surface_from_drawing_scene("indicator_box", box_data.scene)
        box_w = float(box_data.params['w'])
        box_h = float(box_data.params['h'])
        box_fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
        box_result = (
            build_unknown_indicator_box_result(
                total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold,
                corner_policy=box_corner_policy,
            ) if box_corner_policy is not None else
            build_indicator_box_result(total_width=box_w, total_height=box_h, t=val['t'], fold=box_fold)
        )
        box_guide = build_finished_reference_guide(
            "indicator_box", box_result,
            finished_width=box_w - 2.0 * box_fold + val['t'],
            finished_height=box_h - 2.0 * box_fold + val['t'],
        )

        door_spec = self._indicator_door_part_spec(val, groups, features=door_features)
        finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec)
        if door_spec.corner_policy is not None:
            door_result = build_unknown_door_result(
                w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
                gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
                fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
                fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
                corner_policy=door_spec.corner_policy,
            )
            door_surface = feature_surface_from_structural_result("indicator_door", door_result)
            door_width, door_height = door_result.width, door_result.height
            door_baseline_scene = None
            door_status = "自訂 / 手動截角"
        else:
            door_data = ae.get_stretched_door_data(
                None, door_spec.width, door_spec.height, door_spec.thickness, door_spec.frame_width,
                door_spec.gap_w, door_spec.gap_h,
                door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
                indicator_window_groups=groups,
            )
            door_surface = feature_surface_from_drawing_scene("indicator_door", door_data.scene)
            door_width = float(door_data.params['total_width'])
            door_height = float(door_data.params['total_depth'])
            door_result = build_door_result(
                w=door_spec.width, h=door_spec.height, t=door_spec.thickness, fw=door_spec.frame_width,
                gap_w=door_spec.gap_w, gap_h=door_spec.gap_h,
                fold_left=door_spec.fold_left, fold_right=door_spec.fold_right,
                fold_top=door_spec.fold_top, fold_bottom=door_spec.fold_bottom,
            )
            door_baseline_scene = door_data.scene
            door_status = ae.indicator_shared_baseline_source_label("小門.dxf")
        door_guide = build_finished_reference_guide(
            "indicator_door", door_result,
            finished_width=float(finished_w), finished_height=float(finished_h),
        )

        return {
            "indicator_box": {
                "part_key": "indicator_box", "title": "指示燈盒 — 盒體（基準檔＋指示燈）",
                "surface": box_surface, "width": box_w, "height": box_h,
                "reference_guide": box_guide, "feature_list": box_features,
                "baseline_scene": box_baseline_scene,
                "baseline_status_text": (
                    f"{box_status}｜排列 {list(groups)}｜{box_w:g} × {box_h:g} mm"
                ),
            },
            "indicator_door": {
                "part_key": "indicator_door", "title": "指示燈盒 — 小門（基準檔）",
                "surface": door_surface, "width": door_width, "height": door_height,
                "reference_guide": door_guide, "feature_list": door_features,
                "baseline_scene": door_baseline_scene, "baseline_status_text": door_status,
            },
        }

    def export_multi_door_layout_dxfs(self, folder, val, *, draw_stock=False):
        """Export one Door DXF per validated layout cell through the headless API."""
        import os

        exported = []
        context = self._manufacturing_context(draw_stock=draw_stock)
        for cell in self.get_door_layout_cells():
            filename = door_layout_export_filename(cell)
            filepath = os.path.join(folder, filename)
            self._export_authoritative_part(self._door_layout_part_spec(cell, val), filepath, context)
            exported.append(filename)
        return exported

    def export_multi_door_indicator_box_parts(self, folder, val, *, draw_stock=False, export_box=True, export_door=True):
        """Export each per-cell Indicator-Box assembly through the headless API."""
        import os

        exported = []
        context = self._manufacturing_context(draw_stock=draw_stock)
        for cell in self.get_door_layout_cells():
            key = self._door_layout_cell_key(cell)
            state = self._door_layout_indicator_state_for_key(key)
            if state.get("mode") != "indicator_box":
                continue
            self._validate_door_layout_indicator_fit(cell, state, val)
            layers = max(1, min(6, int(state.get("layers", 1))))
            groups = tuple(int(v) for v in list(state.get("groups", [2] * 6))[:layers])
            stem = f"c{cell.column_index + 1}_r{cell.row_index + 1}"

            if export_box:
                filename = f"indicator_box_{stem}.dxf"
                spec = self._indicator_box_part_spec(
                    val, groups, features=self.door_layout_indicator_box_features.get(key, [])
                )
                self._export_authoritative_part(spec, os.path.join(folder, filename), context)
                exported.append(filename)

            if export_door:
                filename = f"indicator_door_{stem}.dxf"
                spec = self._indicator_door_part_spec(
                    val, groups, features=self.door_layout_indicator_door_features.get(key, [])
                )
                self._export_authoritative_part(spec, os.path.join(folder, filename), context)
                exported.append(filename)
        return exported

    def export_selected_dxf(self):
        """批次輸出勾選零件；GUI 只組 PartSpec，實際 DXF 一律交給 manufacturing_api。"""
        self._flush_phase6_authoritative_state()
        existing_parts = self._phase6_current_existing_parts()
        has_indicator_box = self._has_any_indicator_box()
        export_z = bool(self.export_z_var.get() and "box_body" in existing_parts)
        export_head = bool(self.export_head_var.get() and "head" in existing_parts)
        export_tail = bool(self.export_tail_var.get() and "tail" in existing_parts)
        export_door = bool(self.export_door_var.get() and "door" in existing_parts)
        export_base_plate = bool(self.export_base_plate_var.get() and "base_plate" in existing_parts)
        export_ib = bool(self.export_ib_var.get() and "indicator_box" in existing_parts and has_indicator_box)
        export_ib_door = bool(self.export_ib_door_var.get() and "indicator_door" in existing_parts and has_indicator_box)
        if not any([export_z, export_head, export_tail, export_door, export_base_plate, export_ib, export_ib_door]):
            messagebox.showwarning("未選擇零件", "請至少勾選一個要輸出的零件。")
            return

        try:
            val = self.get_float_values()
        except ValueError as ex:
            messagebox.showerror("輸入錯誤", str(ex))
            return

        try:
            indicator_related = bool(
                export_door or export_ib or export_ib_door
            )
            if indicator_related:
                if self.multi_door_enabled_var.get():
                    for cell in self.get_door_layout_cells():
                        key = self._door_layout_cell_key(cell)
                        state = self._door_layout_indicator_state_for_key(key)
                        if state.get("mode") != "none":
                            self._validate_door_layout_indicator_fit(cell, state, val)
                else:
                    self._validate_single_door_indicator_fit(val)
        except ValueError as ex:
            messagebox.showerror("指示燈配置無法套用", str(ex))
            return

        folder = filedialog.askdirectory(title="選擇 DXF 檔案儲存資料夾")
        if not folder:
            return

        import os
        draw_stock = self.draw_stock_var.get()
        context = self._manufacturing_context(draw_stock=draw_stock)
        exported = []
        errors = []

        def run_part(filename, spec):
            fp = os.path.join(folder, filename)
            result = self._export_authoritative_part(spec, fp, context)
            if isinstance(result, tuple):
                exported.extend(os.path.basename(item.output_path) for item in result)
            else:
                exported.append(filename)

        if export_z:
            try:
                run_part("box_body_z.dxf", self._box_body_part_spec(val))
            except Exception as ex:
                errors.append(f"box_body_z.dxf: {ex}")

        if export_head:
            try:
                run_part("end_cap_head.dxf", self._end_cap_part_spec(val, is_tail=False))
            except Exception as ex:
                errors.append(f"end_cap_head.dxf: {ex}")

        if export_tail:
            try:
                run_part("end_cap_tail.dxf", self._end_cap_part_spec(val, is_tail=True))
            except Exception as ex:
                errors.append(f"end_cap_tail.dxf: {ex}")

        indicator_hole = None
        if self.is_indicator_box_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                indicator_hole = manufacturing_api.indicator_box_opening_size(groups, thickness=val['t'])
            except Exception:
                pass

        if export_door:
            try:
                if self.multi_door_enabled_var.get():
                    exported.extend(self.export_multi_door_layout_dxfs(folder, val, draw_stock=draw_stock))
                else:
                    door_indicator = None
                    if self.is_door_indicator_var.get():
                        try:
                            layers = int(self.door_indicator_l_var.get())
                            door_indicator = tuple(int(self.door_indicator_layer_g_vars[i].get()) for i in range(layers))
                        except Exception:
                            pass
                    run_part(
                        "door_unfold.dxf",
                        self._single_door_part_spec(
                            val, indicator_hole=indicator_hole, door_indicator=door_indicator,
                        ),
                    )
            except Exception as ex:
                target = "multi-door layout" if self.multi_door_enabled_var.get() else "door_unfold.dxf"
                errors.append(f"{target}: {ex}")

        if export_base_plate:
            try:
                run_part("base_plate.dxf", self._base_plate_part_spec(val))
            except Exception as ex:
                errors.append(f"base_plate.dxf: {ex}")

        if self.multi_door_enabled_var.get() and (export_ib or export_ib_door):
            try:
                exported.extend(self.export_multi_door_indicator_box_parts(
                    folder, val, draw_stock=draw_stock,
                    export_box=export_ib, export_door=export_ib_door,
                ))
            except Exception as ex:
                errors.append(f"multi-door indicator box parts: {ex}")

        if export_ib and not self.multi_door_enabled_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                run_part(
                    "indicator_box.dxf",
                    self._indicator_box_part_spec(val, groups, features=self.surface_features["indicator_box"]),
                )
            except Exception as ex:
                errors.append(f"indicator_box.dxf: {ex}")

        if export_ib_door and not self.multi_door_enabled_var.get():
            try:
                layers = int(self.indicator_l_var.get())
                groups = tuple(int(self.indicator_layer_g_vars[i].get()) for i in range(layers))
                run_part(
                    "indicator_door.dxf",
                    self._indicator_door_part_spec(val, groups, features=self.surface_features["indicator_door"]),
                )
            except Exception as ex:
                errors.append(f"indicator_door.dxf: {ex}")

        if exported and not errors:
            messagebox.showinfo(
                "輸出成功",
                f"已成功輸出 {len(exported)} 個檔案至：\n{folder}\n\n" +
                "\n".join(f"  • {f}" for f in exported)
            )
        elif exported and errors:
            messagebox.showwarning(
                "部分成功",
                f"成功輸出：{', '.join(exported)}\n失敗：{', '.join(errors)}"
            )
        else:
            messagebox.showerror("輸出失敗", "\n".join(errors))


    def _single_door_indicator_state_snapshot(self):
        if self.is_indicator_box_var.get():
            mode = "indicator_box"
            layer_var = self.indicator_l_var
            group_vars = self.indicator_layer_g_vars
        else:
            mode = "indicator" if self.is_door_indicator_var.get() else "none"
            layer_var = self.door_indicator_l_var
            group_vars = self.door_indicator_layer_g_vars
        try:
            layers = max(1, min(6, int(layer_var.get())))
        except ValueError:
            layers = 1
        groups = []
        for i in range(6):
            try:
                groups.append(int(group_vars[i].get()))
            except ValueError:
                groups.append(2)
        return self._normalize_door_indicator_state({
            "mode": mode,
            "layers": layers,
            "groups": groups,
            "offset_x": float(self.door_indicator_offset_x),
            "offset_y": float(self.door_indicator_offset_y),
            "is_box_dist": bool(self.is_box_dist_var.get()),
        })

    def _apply_single_door_indicator_state(self, state):
        state = self._normalize_door_indicator_state(state)
        mode = state["mode"]
        self.is_door_indicator_var.set(mode == "indicator")
        self.is_indicator_box_var.set(mode == "indicator_box")
        layers = state["layers"]
        groups = state["groups"]
        # Keep both legacy parameter banks synchronized with the editor's one source of truth.
        self.door_indicator_l_var.set(str(layers))
        self.indicator_l_var.set(str(layers))
        for i in range(6):
            self.door_indicator_layer_g_vars[i].set(str(int(groups[i])))
            self.indicator_layer_g_vars[i].set(str(int(groups[i])))
        self.door_indicator_offset_x = float(state.get("offset_x", 0.0))
        self.door_indicator_offset_y = float(state.get("offset_y", 0.0))
        self.is_box_dist_var.set(bool(state.get("is_box_dist", False)))
        self._request_phase6_update("geometry")

    def _apply_multi_door_indicator_state(self, key, state):
        normalized = self._normalize_door_indicator_state(state)
        target = self.door_layout_indicator_states.get(key)
        if target is None:
            self.door_layout_indicator_states[key] = normalized
        else:
            target.clear()
            target.update(normalized)

    def open_part_hole_editor(self, part_key):
        """Open the generic polygon-constrained hole editor for any unfolded panel."""
        self.workspace_controller.set_active_part(part_key)
        if part_key == "door" and self.multi_door_enabled_var.get():
            cell = self.get_selected_door_layout_cell()
            self.open_door_layout_cell_editor(cell.column_index, cell.row_index)
            return
        if part_key == "box_body":
            self.open_box_body_face_editor(self.box_body_face_selected_var.get() or "back")
            return
        try:
            val = self.get_float_values()
        except ValueError as exc:
            messagebox.showerror("輸入錯誤", str(exc))
            return

        title_map = {
            "box_body": "箱身",
            "door": "門板",
            "base_plate": "底板",
            "indicator_box": "指示燈盒",
            "indicator_door": "指示燈小門",
        }
        title = title_map.get(part_key, part_key)
        door_indicator_state = None
        door_indicator_context = None
        door_indicator_commit = None
        baseline_scene = None
        baseline_status_text = None
        indicator_component_context_provider = None

        if part_key == "box_body":
            baseline_status_text = "未使用基準檔（程式計算生成）"
            head_policy, tail_policy = self._box_body_corner_policies(val['fw'])
            result = build_box_body_result(
                w=val['w'], h=val['h'], d=val['d'], t=val['t'], fw=val['fw'],
                zl1=val['zl1'], zl2=val['zl2'], zr1=val['zr1'], zr2=val['zr2'],
                z_comp=val['z_comp'],
                head_corner_policy=head_policy, tail_corner_policy=tail_policy,
            )
            surface = feature_surface_from_structural_result(part_key, result)
            width, height = result.width, result.height
            reference_guide = build_finished_reference_guide(
                part_key, result, finished_width=val['w'], finished_height=val['h']
            )
        elif part_key == "door":
            door_material_fw = self._door_material_frame_width(val['fw'], val['t'])
            if is_unknown_model(self.baseline_var.get()):
                result = build_unknown_door_result(
                    w=val['w'], h=val['h'], t=val['t'], fw=door_material_fw,
                    gap_w=val['door_gap_w'], gap_h=val['door_gap_h'],
                    fold_left=val['door_fold_l'], fold_right=val['door_fold_r'],
                    fold_top=val['door_fold_t'], fold_bottom=val['door_fold_b'],
                    corner_policy=self._manual_corner_policy('door', door_material_fw),
                )
            else:
                result = build_door_result(
                    w=val['w'], h=val['h'], t=val['t'], fw=door_material_fw,
                    gap_w=val['door_gap_w'], gap_h=val['door_gap_h'],
                    fold_left=val['door_fold_l'], fold_right=val['door_fold_r'],
                    fold_top=val['door_fold_t'], fold_bottom=val['door_fold_b'],
                )
            surface = feature_surface_from_structural_result(part_key, result)
            width, height = result.width, result.height
            finished_w, finished_h = ae.calculate_door_finished_size(
                val['w'], val['h'], door_material_fw,
                val['door_gap_w'], val['door_gap_h'], val['t'],
            )
            reference_guide = build_finished_reference_guide(
                part_key, result, finished_width=finished_w, finished_height=finished_h
            )
            door_indicator_state = self._single_door_indicator_state_snapshot()
            door_indicator_context = DoorIndicatorContext(
                finished_width=finished_w, finished_height=finished_h,
                left_fold=val['door_fold_l'], bottom_fold=val['door_fold_b'],
            )
            door_indicator_commit = self._apply_single_door_indicator_state
            model = self._baseline_source_model()
            if model and ae.has_baseline_part(model, "門.dxf"):
                try:
                    baseline_data = ae.get_stretched_door_data(
                        model, val['w'], val['h'], val['t'], door_material_fw,
                        val['door_gap_w'], val['door_gap_h'],
                        val['door_fold_l'], val['door_fold_r'], val['door_fold_t'], val['door_fold_b'],
                        frame_edges=DoorFrameEdges(),
                    )
                    baseline_scene = baseline_data.scene
                    baseline_status_text = ae.baseline_source_label(model, "門.dxf")
                except Exception:
                    baseline_status_text = "未使用基準檔（程式計算生成）"
            else:
                baseline_status_text = "未使用基準檔（程式計算生成）"
            indicator_component_context_provider = lambda state, val=val: self._indicator_component_editor_contexts(
                state, val,
                box_features=self.surface_features["indicator_box"],
                door_features=self.surface_features["indicator_door"],
            )
        elif part_key == "base_plate":
            baseline_status_text = "未使用基準檔（程式計算生成）"
            if is_unknown_model(self.baseline_var.get()):
                baseline_status_text = "自訂 / 手動截角"
                result = build_unknown_base_plate_result(
                    w=val['w'], h=val['h'], t=val['t'],
                    shrink_top=val['base_plate_shrink_top'], shrink_bottom=val['base_plate_shrink_bottom'],
                    shrink_left=val['base_plate_shrink_left'], shrink_right=val['base_plate_shrink_right'],
                    bend=val['base_plate_bend'],
                    corner_policy=self._manual_corner_policy('base_plate', val['fw']),
                )
            else:
                result = build_base_plate_result(
                    w=val['w'], h=val['h'], t=val['t'],
                    shrink_top=val['base_plate_shrink_top'], shrink_bottom=val['base_plate_shrink_bottom'],
                    shrink_left=val['base_plate_shrink_left'], shrink_right=val['base_plate_shrink_right'],
                    bend=val['base_plate_bend'],
                )
            surface = feature_surface_from_structural_result(part_key, result)
            width, height = result.width, result.height
            finished_w = val['w'] - val['base_plate_shrink_left'] - val['base_plate_shrink_right']
            finished_h = val['h'] - val['base_plate_shrink_top'] - val['base_plate_shrink_bottom']
            reference_guide = build_finished_reference_guide(
                part_key, result, finished_width=finished_w, finished_height=finished_h
            )
        elif part_key == "indicator_box":
            baseline_status_text = ae.indicator_shared_baseline_source_label("盒子.dxf")
            try:
                layers = int(self.indicator_l_var.get())
                groups = [int(self.indicator_layer_g_vars[i].get()) for i in range(layers)]
            except ValueError:
                messagebox.showerror("輸入錯誤", "指示燈排列參數無效")
                return
            indicator_corner_policy = None
            try:
                data = ae.get_stretched_indicator_box_data(
                    "指示燈", groups, val['t'], corner_policy=None
                )
                baseline_scene = data.scene
            except Exception as exc:
                messagebox.showerror("開孔失敗", f"指示燈盒基準載入失敗: {exc}")
                return
            surface = feature_surface_from_drawing_scene(part_key, data.scene)
            width, height = data.params['w'], data.params['h']
            fold = float(getattr(ae, 'indicator_box_fold_def', 49.0))
            result = (
                build_unknown_indicator_box_result(
                    total_width=width, total_height=height, t=val['t'], fold=fold,
                    corner_policy=indicator_corner_policy,
                ) if indicator_corner_policy is not None else
                build_indicator_box_result(total_width=width, total_height=height, t=val['t'], fold=fold)
            )
            reference_guide = build_finished_reference_guide(
                part_key, result,
                finished_width=width - 2.0 * fold + val['t'],
                finished_height=height - 2.0 * fold + val['t'],
            )
        elif part_key == "indicator_door":
            try:
                layers = int(self.indicator_l_var.get())
                groups = [int(self.indicator_layer_g_vars[i].get()) for i in range(layers)]
            except ValueError:
                messagebox.showerror("輸入錯誤", "指示燈排列參數無效")
                return
            t = val['t']; fw = val['fw']; gw = val['door_gap_w']; gh = val['door_gap_h']
            policy = replace(
                manufacturing_api.resolve_policy(),
                frame_width=float(fw), door_gap_w=float(gw), door_gap_h=float(gh),
                indicator_small_door_fold=float(getattr(ae, 'indicator_small_door_fold_def', 19.0)),
            )
            indicator_ctx = ManufacturingContext(policy=policy)
            door_spec = manufacturing_api.indicator_small_door_spec(
                groups, thickness=t, context=indicator_ctx
            )
            finished_w, finished_h = manufacturing_api.door_finished_face_size(door_spec, indicator_ctx)
            w_source, h_source = door_spec.width, door_spec.height
            try:
                data = ae.get_stretched_door_data(
                    None, w_source, h_source, t, fw, gw, gh,
                    door_spec.fold_left, door_spec.fold_right, door_spec.fold_top, door_spec.fold_bottom,
                    indicator_window_groups=groups,
                )
            except Exception as exc:
                messagebox.showerror("開孔失敗", f"指示燈小門基準載入失敗: {exc}")
                return
            baseline_scene = data.scene
            baseline_status_text = ae.indicator_shared_baseline_source_label("小門.dxf")
            try:
                surface = feature_surface_from_drawing_scene(part_key, data.scene)
            except ValueError as exc:
                messagebox.showerror("開孔失敗", str(exc))
                return
            width, height = data.params['total_width'], data.params['total_depth']
            result = build_door_result(
                w=w_source, h=h_source, t=t, fw=fw, gap_w=gw, gap_h=gh,
                fold_left=19.0, fold_right=19.0, fold_top=19.0, fold_bottom=19.0,
            )
            reference_guide = build_finished_reference_guide(
                part_key, result, finished_width=finished_w, finished_height=finished_h
            )
        else:
            messagebox.showerror("開孔失敗", f"未知板面: {part_key}")
            return

        self._open_unified_hole_editor(
            part_key, title, surface, width, height, reference_guide=reference_guide,
            door_indicator_state=door_indicator_state,
            door_indicator_context=door_indicator_context,
            door_indicator_commit=door_indicator_commit,
            door_frame_edges=(DoorFrameEdges() if part_key == "door" else None),
            door_gap_w=(val['door_gap_w'] if part_key == "door" else None),
            door_gap_h=(val['door_gap_h'] if part_key == "door" else None),
            door_frame_width=(val['fw'] if part_key == "door" else None),
            door_thickness=(val['t'] if part_key == "door" else None),
            baseline_scene=baseline_scene, baseline_status_text=baseline_status_text,
            indicator_component_context_provider=indicator_component_context_provider,
        )

    def _open_unified_hole_editor(
        self, part_key, title, surface, width, height, sync_callback=None, reference_guide=None,
        feature_list_override=None, door_indicator_state=None, door_indicator_context=None,
        door_indicator_commit=None, door_frame_edges=None, door_gap_w=None, door_gap_h=None,
        door_frame_width=None, door_thickness=None, on_close=None, baseline_scene=None,
        baseline_status_text=None, indicator_component_context_provider=None,
    ):
        """Unified CAD-like hole editor for every FeatureSurface."""
        feature_list = self.surface_features[part_key] if feature_list_override is None else feature_list_override
        hole_session = Phase6HoleEditorSession("door", feature_list, max_undo_steps=50)
        if reference_guide is None:
            rminx, rminy, rmaxx, rmaxy = surface.polygon.bounds
            reference_guide = RectGuide(Vec2(rminx, rminy), Vec2(rmaxx, rmaxy), "finished_boundary")
        hole_base_dir = ae.baseline_hole_catalog_root_path()
        general_catalog_defs = load_hole_catalog(hole_base_dir)
        pipe_catalog_defs = load_pipe_catalog(hole_base_dir)
        catalog_defs = general_catalog_defs + pipe_catalog_defs
        catalog_by_label = {}
        catalog_label_by_definition = {}
        for definition in catalog_defs:
            if definition.shape == "circle":
                size_text = f"Ø{definition.diameter:g}"
            elif definition.shape == "rectangle":
                size_text = f"{definition.width:g}×{definition.height:g}"
            else:
                size_text = "DXF"
            process_text = "盲孔" if definition.process == "BLIND_HOLE" else ("圖檔" if definition.process == "FROM_DXF" else "切穿")
            label = f"{definition.name}  {size_text}  [{process_text}]"
            catalog_by_label[label] = definition
            catalog_label_by_definition[id(definition)] = label

        editor = tk.Toplevel(self.root)
        self.last_unified_hole_editor = editor
        editor.title(f"{title} — 統一開孔編輯器")
        editor.configure(bg=self.COLOR_BG)
        editor.transient(self.root)
        editor.grab_set()
        screen_w = editor.winfo_screenwidth()
        screen_h = editor.winfo_screenheight()
        win_w = max(720, min(1280, screen_w - 80))
        win_h = max(560, min(820, screen_h - 120))
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        normal_geometry = [f"{win_w}x{win_h}+{pos_x}+{pos_y}"]
        fullscreen_state = [False]
        fullscreen_restore_geometry = [None]
        editor.geometry(normal_geometry[0])
        editor.minsize(min(760, win_w), min(560, win_h))

        body = tk.Frame(editor, bg=self.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left = tk.Frame(body, bg=self.COLOR_PANEL, width=min(320, max(270, win_w // 4)))
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)
        # Reserve a fixed bottom action strip before packing any scroll/content widgets.
        # This keeps Insert reachable even on the editor's minimum-height window.
        left_insert_bar = tk.Frame(left, bg=self.COLOR_PANEL)
        left_insert_bar.pack(side=tk.BOTTOM, fill=tk.X)
        center = tk.Frame(body, bg=self.COLOR_BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Door-owned Indicator-Box assembly lives as a page in this same editor.
        # The page selectors switch the shared CAD workspace context; no extra
        # editor windows/buttons are created.
        editor_tabs = None
        main_page = None
        indicator_page = None
        component_tabs = None
        indicator_box_page = None
        indicator_door_page = None
        indicator_page_visible = [False]
        if part_key == "door" and door_indicator_state is not None and indicator_component_context_provider is not None:
            editor_tabs = ttk.Notebook(center, height=32)
            main_page = tk.Frame(editor_tabs, bg=self.COLOR_BG)
            indicator_page = tk.Frame(editor_tabs, bg=self.COLOR_BG)
            editor_tabs.add(main_page, text="  門板  ")
            editor_tabs.pack(fill=tk.X, pady=(0, 4))

            component_tabs = ttk.Notebook(center, height=30)
            indicator_box_page = tk.Frame(component_tabs, bg=self.COLOR_BG)
            indicator_door_page = tk.Frame(component_tabs, bg=self.COLOR_BG)
            component_tabs.add(indicator_box_page, text="  盒體（基準檔＋指示燈）  ")
            component_tabs.add(indicator_door_page, text="  小門（基準檔）  ")

        big_font = ('Microsoft JhengHei', 15, 'bold')
        entry_font = ('Consolas', 12, 'bold')
        normal_font = ('Microsoft JhengHei', 11)

        baseline_status_var = tk.StringVar(value=str(baseline_status_text or ""))
        baseline_status_label = None
        if baseline_status_text or indicator_component_context_provider is not None:
            baseline_status_label = tk.Label(
                left, textvariable=baseline_status_var, bg=self.COLOR_PANEL,
                fg=("#64d2ff" if str(baseline_status_text or "").startswith("基準檔：") else "#ff9f0a"),
                font=('Microsoft JhengHei', 9, 'bold'), anchor=tk.W, justify=tk.LEFT, wraplength=285,
            )
            baseline_status_label.pack(fill=tk.X, padx=10, pady=(7, 2))

        indicator_redraw = [None]
        indicator_context_refresh = [None]
        indicator_mode_var = None
        indicator_layers_var = None
        indicator_group_vars = []
        indicator_offset_x_var = None
        indicator_offset_y_var = None
        indicator_box_dist_var = None

        def set_indicator_page_visible(visible):
            if editor_tabs is None or indicator_page is None or main_page is None:
                return
            visible = bool(visible)
            tabs = set(editor_tabs.tabs())
            page_name = str(indicator_page)
            if visible and page_name not in tabs:
                editor_tabs.add(indicator_page, text="  指示燈盒  ")
                indicator_page_visible[0] = True
            elif not visible and page_name in tabs:
                if editor_tabs.select() == page_name:
                    editor_tabs.select(main_page)
                editor_tabs.forget(indicator_page)
                indicator_page_visible[0] = False

        def request_indicator_redraw(*_args):
            mode = indicator_mode_var.get() if indicator_mode_var is not None else "none"
            set_indicator_page_visible(mode == "indicator_box")
            if indicator_context_refresh[0] is not None:
                editor.after_idle(indicator_context_refresh[0])
            elif indicator_redraw[0] is not None:
                editor.after_idle(indicator_redraw[0])

        def on_box_distance_toggle():
            request_indicator_redraw()
            editor.after_idle(lambda: refresh_reference_fields())

        def collect_indicator_state():
            if indicator_mode_var is None:
                return None
            try:
                layers = max(1, min(6, int(indicator_layers_var.get())))
            except (TypeError, ValueError):
                layers = 1
            groups = []
            for var in indicator_group_vars:
                try:
                    groups.append(max(1, int(var.get())))
                except ValueError:
                    groups.append(2)
            while len(groups) < 6:
                groups.append(2)
            try:
                offset_x = float(indicator_offset_x_var.get())
            except ValueError:
                offset_x = 0.0
            try:
                offset_y = float(indicator_offset_y_var.get())
            except ValueError:
                offset_y = 0.0
            return self._normalize_door_indicator_state({
                "mode": indicator_mode_var.get(),
                "layers": layers,
                "groups": groups[:6],
                "offset_x": offset_x,
                "offset_y": offset_y,
                "is_box_dist": bool(indicator_box_dist_var.get()),
            })

        if part_key == "door" and door_indicator_state is not None:
            seed_state = self._normalize_door_indicator_state(door_indicator_state)
            indicator_mode_var = tk.StringVar(value=seed_state["mode"])
            indicator_layers_var = tk.StringVar(value=str(seed_state["layers"]))
            indicator_group_vars = [tk.StringVar(value=str(int(seed_state["groups"][i]))) for i in range(6)]
            indicator_offset_x_var = tk.StringVar(value=self._door_layout_number_text(seed_state["offset_x"]))
            indicator_offset_y_var = tk.StringVar(value=self._door_layout_number_text(seed_state["offset_y"]))
            indicator_box_dist_var = tk.BooleanVar(value=seed_state["is_box_dist"])

            indicator_frame = tk.LabelFrame(
                left, text=" 門指示燈 / 指示燈盒子 ", bg=self.COLOR_PANEL, fg="#ffd60a",
                font=('Microsoft JhengHei', 11, 'bold')
            )
            indicator_frame.pack(fill=tk.X, padx=10, pady=(8, 4))
            mode_row = tk.Frame(indicator_frame, bg=self.COLOR_PANEL)
            mode_row.pack(fill=tk.X, padx=5, pady=(3, 2))
            for text, value in (("不使用", "none"), ("直接指示燈", "indicator"), ("指示燈盒子", "indicator_box")):
                tk.Radiobutton(
                    mode_row, text=text, value=value, variable=indicator_mode_var,
                    bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                    activebackground=self.COLOR_PANEL, activeforeground=self.COLOR_TEXT,
                    font=('Microsoft JhengHei', 9, 'bold'), command=request_indicator_redraw,
                ).pack(side=tk.LEFT, padx=(0, 5))

            layer_row = tk.Frame(indicator_frame, bg=self.COLOR_PANEL)
            layer_row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(layer_row, text="層數", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, width=5, anchor=tk.W).pack(side=tk.LEFT)
            layer_combo = ttk.Combobox(
                layer_row, textvariable=indicator_layers_var,
                values=["1", "2", "3", "4", "5", "6"], width=4, state="readonly"
            )
            layer_combo.pack(side=tk.LEFT)

            groups_frame = tk.Frame(indicator_frame, bg=self.COLOR_PANEL)
            groups_frame.pack(fill=tk.X, padx=6, pady=2)

            def rebuild_indicator_group_controls(*_args):
                for child in groups_frame.winfo_children():
                    child.destroy()
                try:
                    layers = max(1, min(6, int(indicator_layers_var.get())))
                except ValueError:
                    layers = 1
                for i in range(layers):
                    tk.Label(groups_frame, text=f"{i+1}層", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED,
                             font=('Microsoft JhengHei', 8)).grid(row=i, column=0, sticky="w", padx=(0, 3), pady=1)
                    cb = ttk.Combobox(groups_frame, textvariable=indicator_group_vars[i],
                                      values=[str(v) for v in range(1, 9)], width=3, state="readonly")
                    cb.grid(row=i, column=1, sticky="w", pady=1)
                    cb.bind("<<ComboboxSelected>>", request_indicator_redraw)
                request_indicator_redraw()

            layer_combo.bind("<<ComboboxSelected>>", rebuild_indicator_group_controls)
            rebuild_indicator_group_controls()

            pos_row = tk.Frame(indicator_frame, bg=self.COLOR_PANEL)
            pos_row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(pos_row, text="X", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
            x_entry = tk.Entry(pos_row, textvariable=indicator_offset_x_var, width=6, justify=tk.CENTER)
            x_entry.pack(side=tk.LEFT, padx=(2, 6))
            tk.Label(pos_row, text="Y", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED).pack(side=tk.LEFT)
            y_entry = tk.Entry(pos_row, textvariable=indicator_offset_y_var, width=6, justify=tk.CENTER)
            y_entry.pack(side=tk.LEFT, padx=(2, 6))
            tk.Button(pos_row, text="置中", command=lambda: (
                indicator_offset_x_var.set("0"), indicator_offset_y_var.set("0"), request_indicator_redraw()
            ), bg="#3a3a44", fg="white", bd=0).pack(side=tk.LEFT)
            x_entry.bind("<KeyRelease>", request_indicator_redraw)
            y_entry.bind("<KeyRelease>", request_indicator_redraw)
            tk.Checkbutton(
                indicator_frame, text="箱體定位距離", variable=indicator_box_dist_var,
                bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                activebackground=self.COLOR_PANEL, command=on_box_distance_toggle,
                font=('Microsoft JhengHei', 9),
            ).pack(anchor=tk.W, padx=6, pady=(1, 4))

        # ---- left: catalog ----
        tk.Label(left, text="一般開孔", bg=self.COLOR_PANEL, fg="#30d158", font=('Microsoft JhengHei', 13, 'bold')).pack(fill=tk.X, padx=10, pady=(10, 3))
        catalog_list = tk.Listbox(left, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, selectbackground="#0a84ff",
                                  font=('Microsoft JhengHei', 11), height=6, exportselection=False)
        catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        general_labels = [catalog_label_by_definition[id(d)] for d in general_catalog_defs] + ["＋ 自訂圓孔", "＋ 自訂方孔"]
        for label in general_labels:
            catalog_list.insert(tk.END, label)

        tk.Label(left, text="管孔清單", bg=self.COLOR_PANEL, fg="#ffd60a", font=('Microsoft JhengHei', 13, 'bold')).pack(fill=tk.X, padx=10, pady=(5, 3))
        pipe_catalog_list = tk.Listbox(left, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, selectbackground="#bf5af2",
                                       font=('Microsoft JhengHei', 11), height=5, exportselection=False)
        pipe_catalog_list.pack(fill=tk.X, padx=10, pady=(0, 4))
        pipe_labels = [catalog_label_by_definition[id(d)] for d in pipe_catalog_defs]
        for label in pipe_labels:
            pipe_catalog_list.insert(tk.END, label)

        first_label = general_labels[0] if general_labels else (pipe_labels[0] if pipe_labels else "")
        if general_labels:
            catalog_list.selection_set(0)
        elif pipe_labels:
            pipe_catalog_list.selection_set(0)
        selected_catalog_text = tk.StringVar(value=first_label)
        tk.Label(left, textvariable=selected_catalog_text, bg="#2c2c34", fg="#ffd60a", anchor=tk.W,
                 font=('Microsoft JhengHei', 10, 'bold'), wraplength=285, padx=8, pady=5).pack(fill=tk.X, padx=10, pady=(2, 5))

        custom_frame = tk.LabelFrame(left, text=" 自訂尺寸 ", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=normal_font)
        custom_frame.pack(fill=tk.X, padx=10, pady=4)
        var_d = tk.StringVar(value="22.0")
        var_w = tk.StringVar(value="40.0")
        var_h = tk.StringVar(value="40.0")
        var_blind = tk.BooleanVar(value=False)
        var_rotation = tk.StringVar(value="360°")

        def small_row(label, variable):
            row = tk.Frame(custom_frame, bg=self.COLOR_PANEL)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=label, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, width=7, anchor=tk.W, font=normal_font).pack(side=tk.LEFT)
            tk.Entry(row, textvariable=variable, font=('Consolas', 13), width=9).pack(side=tk.LEFT, fill=tk.X, expand=True)

        small_row("直徑", var_d)
        small_row("寬 W", var_w)
        small_row("高 H", var_h)
        tk.Checkbutton(custom_frame, text="盲孔", variable=var_blind, bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
                       selectcolor=self.COLOR_INPUT_BG, activebackground=self.COLOR_PANEL,
                       font=('Microsoft JhengHei', 12, 'bold')).pack(anchor=tk.W, padx=6, pady=3)

        insert_mode = [False]
        insert_btn = tk.Button(left_insert_bar, text="插入", bg="#30d158", fg="white", font=big_font, bd=0, pady=8)
        insert_btn.pack(fill=tk.X, padx=10, pady=(7, 8))
        self.last_hole_editor_insert_button = insert_btn

        tk.Label(left, text="已開孔（雙擊：切穿 ⇄ 盲孔）", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
                 font=('Microsoft JhengHei', 12, 'bold')).pack(fill=tk.X, padx=10, pady=(5, 3))
        created_list = tk.Listbox(left, bg=self.COLOR_INPUT_BG, fg=self.COLOR_TEXT, selectbackground="#5e5ce6",
                                  font=('Microsoft JhengHei', 12), height=9, exportselection=False)
        created_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        delete_btn = tk.Button(left, text="刪除選中", bg="#ff453a", fg="white",
                               font=('Microsoft JhengHei', 12, 'bold'), bd=0, pady=6)
        delete_btn.pack(fill=tk.X, padx=10, pady=(3, 10))

        # ---- center: always-visible rotation + canvas + whole-editor actions ----
        toolbar = tk.Frame(center, bg=self.COLOR_PANEL)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        tk.Label(toolbar, text="旋轉", bg=self.COLOR_PANEL, fg="#ffd60a",
                 font=('Microsoft JhengHei', 12, 'bold')).pack(side=tk.LEFT, padx=(10, 6), pady=6)
        rotation_buttons = []
        # Rotation choices: 90° 180° 270° 360°
        for angle in (90, 180, 270, 360):
            btn = tk.Button(toolbar, text=f"{angle}°", bg="#3a3a44", fg="white", bd=0,
                            font=('Microsoft JhengHei', 11, 'bold'), padx=10, pady=4)
            btn.pack(side=tk.LEFT, padx=3, pady=4)
            rotation_buttons.append((angle, btn))
        fullscreen_btn = tk.Button(toolbar, text="全螢幕", bg="#0a84ff", fg="white", bd=0,
                                   font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4)
        fullscreen_btn.pack(side=tk.LEFT, padx=(12, 3), pady=4)
        undo_btn = tk.Button(toolbar, text="↶ 回上一步", bg="#636366", fg="white", bd=0,
                             font=('Microsoft JhengHei', 11, 'bold'), padx=12, pady=4)
        undo_btn.pack(side=tk.LEFT, padx=(8, 3), pady=4)

        def toggle_fullscreen(event=None):
            entering = not fullscreen_state[0]
            if entering:
                fullscreen_restore_geometry[0] = editor.geometry()
                fullscreen_state[0] = True
                try:
                    editor.attributes("-fullscreen", True)
                    editor.update_idletasks()
                except tk.TclError:
                    pass
                try:
                    native_fullscreen = bool(editor.attributes("-fullscreen"))
                except tk.TclError:
                    native_fullscreen = False
                if not native_fullscreen:
                    editor.geometry(f"{editor.winfo_screenwidth()}x{editor.winfo_screenheight()}+0+0")
            else:
                fullscreen_state[0] = False
                try:
                    editor.attributes("-fullscreen", False)
                except tk.TclError:
                    pass
                if fullscreen_restore_geometry[0]:
                    editor.geometry(fullscreen_restore_geometry[0])
            fullscreen_btn.configure(text=("還原視窗" if fullscreen_state[0] else "全螢幕"))
            editor.after_idle(redraw)
            return "break"

        fullscreen_btn.configure(command=toggle_fullscreen)
        tk.Label(toolbar, text="雙擊已開孔：切穿 ⇄ 盲孔　右鍵孔：選十字基準",
                 bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 10)).pack(side=tk.RIGHT, padx=10)

        canvas = tk.Canvas(center, bg=self.COLOR_CANVAS_BG, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.last_hole_editor_canvas = canvas

        footer = tk.Frame(center, bg=self.COLOR_PANEL)
        footer.pack(fill=tk.X, pady=(6, 0))
        confirm_all_btn = tk.Button(footer, text="確定全部", bg="#30d158", fg="white", bd=0,
                                    font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7)
        confirm_all_btn.pack(side=tk.RIGHT, padx=(6, 10), pady=6)
        cancel_all_btn = tk.Button(footer, text="取消全部", bg="#ff453a", fg="white", bd=0,
                                   font=('Microsoft JhengHei', 13, 'bold'), padx=22, pady=7)
        cancel_all_btn.pack(side=tk.RIGHT, padx=6, pady=6)
        tk.Label(footer, text="Esc：取消目前插入／定位；沒有進行中的操作時則取消全部",
                 bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED, font=('Microsoft JhengHei', 10)).pack(side=tk.LEFT, padx=10)

        indicator_fit_error = [None]

        def validate_current_indicator_fit(show_error=False):
            if door_indicator_state is None or door_indicator_context is None:
                indicator_fit_error[0] = None
                confirm_all_btn.configure(state=tk.NORMAL)
                return True
            state_now = collect_indicator_state()
            if state_now is None or state_now.get("mode") == "none":
                indicator_fit_error[0] = None
                confirm_all_btn.configure(state=tk.NORMAL)
                return True
            try:
                manufacturing_api.validate_door_indicator_fit(
                    mode=state_now["mode"],
                    groups=tuple(int(v) for v in state_now["groups"][:state_now["layers"]]),
                    finished_width=float(door_indicator_context.finished_width),
                    finished_height=float(door_indicator_context.finished_height),
                    thickness=float(door_thickness or 0.0),
                    offset=(float(state_now["offset_x"]), float(state_now["offset_y"])),
                )
            except (ValueError, TypeError) as exc:
                indicator_fit_error[0] = str(exc)
                confirm_all_btn.configure(state=tk.DISABLED)
                if show_error:
                    messagebox.showerror("指示燈配置無法套用", str(exc))
                return False
            indicator_fit_error[0] = None
            confirm_all_btn.configure(state=tk.NORMAL)
            return True

        dragging = [False]
        editor_closed = [False]
        suppress_entry_events = [False]
        pending_after = {}
        position_authority = [None]  # "reference" or "round"; last Confirm wins on conflict
        round_window = [None]

        # The Door editor may temporarily switch the shared CAD workspace to two
        # Door-owned indicator-box members.  Session owns context snapshots / Undo;
        # this adapter only tracks which physical PartRenderData context is shown.
        active_part_key = [part_key]
        door_editor_context = {
            "part_key": part_key, "surface": surface, "width": width, "height": height,
            "reference_guide": reference_guide, "feature_list": feature_list,
            "baseline_scene": baseline_scene, "baseline_status_text": str(baseline_status_text or ""),
        }
        indicator_component_contexts = {}

        var_x_edge = tk.StringVar()
        var_x_neighbor = tk.StringVar()
        var_y_edge = tk.StringVar()
        var_y_neighbor = tk.StringVar()
        lbl_x_edge = tk.StringVar(value="X 到邊框")
        lbl_x_neighbor = tk.StringVar(value="X 到鄰近孔")
        lbl_y_edge = tk.StringVar(value="Y 到邊框")
        lbl_y_neighbor = tk.StringVar(value="Y 到鄰近孔")

        # Floating controls follow the selected reference crosshair on the canvas.
        overlay_widgets = []
        ref_entries = {}

        def add_group_entry(group, label_var, value_var, axis, mode):
            row = tk.Frame(group, bg="#24242c")
            row.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(row, textvariable=label_var, bg="#24242c", fg="#ffd60a",
                     font=('Microsoft JhengHei', 10, 'bold'), width=13, anchor=tk.W).pack(side=tk.LEFT)
            ent = tk.Entry(row, textvariable=value_var, font=entry_font, justify=tk.RIGHT, width=8)
            ent.pack(side=tk.LEFT, padx=(4, 0), ipady=2)
            ref_entries[(axis, mode)] = ent
            return ent

        # Pair each axis together: X edge + X neighbor, Y edge + Y neighbor.
        x_group = tk.Frame(canvas, bg="#24242c", bd=1, relief=tk.SOLID)
        tk.Label(x_group, text="X 定位", bg="#24242c", fg="#30d158",
                 font=('Microsoft JhengHei', 10, 'bold')).pack(fill=tk.X, padx=5, pady=(3, 1))
        ent_x_edge = add_group_entry(x_group, lbl_x_edge, var_x_edge, "x", "edge")
        ent_x_neighbor = add_group_entry(x_group, lbl_x_neighbor, var_x_neighbor, "x", "neighbor")

        y_group = tk.Frame(canvas, bg="#24242c", bd=1, relief=tk.SOLID)
        tk.Label(y_group, text="Y 定位", bg="#24242c", fg="#64d2ff",
                 font=('Microsoft JhengHei', 10, 'bold')).pack(fill=tk.X, padx=5, pady=(3, 1))
        ent_y_edge = add_group_entry(y_group, lbl_y_edge, var_y_edge, "y", "edge")
        ent_y_neighbor = add_group_entry(y_group, lbl_y_neighbor, var_y_neighbor, "y", "neighbor")
        overlay_widgets.extend([x_group, y_group])

        ref_panel = tk.Frame(canvas, bg="#1f1f27", bd=2, relief=tk.RIDGE)
        tk.Label(ref_panel, text="右鍵切換基準", bg="#1f1f27", fg="#ffd60a",
                 font=('Microsoft JhengHei', 9, 'bold')).grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(3, 2))
        confirm_ref_btn = tk.Button(ref_panel, text="確定", bg="#30d158", fg="white", bd=0,
                                    font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3)
        confirm_ref_btn.grid(row=1, column=1, padx=(2, 4), pady=(2, 4))
        cancel_ref_btn = tk.Button(ref_panel, text="取消", bg="#ff9f0a", fg="white", bd=0,
                                   font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3)
        cancel_ref_btn.grid(row=1, column=0, padx=(4, 2), pady=(2, 4))
        round_settings_btn = tk.Button(ref_panel, text="圓孔排列", bg="#5e5ce6", fg="white", bd=0,
                                       font=('Microsoft JhengHei', 9, 'bold'), padx=7, pady=3, state=tk.DISABLED)
        round_settings_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        overlay_widgets.append(ref_panel)

        canvas_view = Phase6HoleEditorCanvasView(
            canvas,
            draw_grid=self.draw_grid,
            render_secondary_scene=render_secondary_scene,
            render_resolved_features=render_resolved_features,
            overlay_widgets={"x_group": x_group, "y_group": y_group, "panel": ref_panel},
        )

        def sync_all():
            if sync_callback is not None:
                sync_callback()
            self.draw_preview()

        def feature_display(feature, i):
            process = "盲孔" if getattr(feature, "layer", "CUTTING") == "BLIND_HOLE" else ""
            if isinstance(feature, CircleFeature):
                desc = f"Ø{feature.diameter:g}"
            elif isinstance(feature, RectFeature):
                desc = f"{feature.width:g}×{feature.height:g}"
            else:
                desc = feature.source_type or "DXF孔型"
            return f"{i+1:02d}  {desc:<14}  {process}"

        def refresh_created():
            created_list.delete(0, tk.END)
            for i, feature in enumerate(feature_list):
                created_list.insert(tk.END, feature_display(feature, i))
            if 0 <= hole_session.selected_index < len(feature_list):
                created_list.selection_set(hole_session.selected_index)
                created_list.see(hole_session.selected_index)

        side_zh = {"left": "左", "right": "右", "top": "上", "bottom": "下"}
        last_distances = [None]

        def active_reference_guide():
            if (
                active_part_key[0] == "door" and indicator_box_dist_var is not None and indicator_box_dist_var.get()
                and door_frame_width is not None and door_thickness is not None
                and door_gap_w is not None and door_gap_h is not None
            ):
                return door_enclosure_reference_guide(
                    reference_guide, door_frame_edges or DoorFrameEdges(),
                    frame_width=door_frame_width, thickness=door_thickness,
                    gap_w=door_gap_w, gap_h=door_gap_h,
                )
            return reference_guide

        def refresh_reference_fields():
            idx = hole_session.selected_index
            suppress_entry_events[0] = True
            try:
                if not (0 <= idx < len(feature_list)):
                    for v in (var_x_edge, var_x_neighbor, var_y_edge, var_y_neighbor):
                        v.set("")
                    last_distances[0] = None
                    round_settings_btn.configure(state=tk.DISABLED)
                    return
                anchor = feature_reference_anchor(feature_list[idx])
                round_settings_btn.configure(state=(tk.NORMAL if isinstance(feature_list[idx], CircleFeature) else tk.DISABLED))
                d = reference_distances(
                    surface, feature_list, idx, anchor, width, height, reference_guide=active_reference_guide()
                )
                last_distances[0] = d
                xs = side_zh[d.x_side]
                ys = side_zh[d.y_side]
                lbl_x_edge.set(f"X 到{xs}邊框")
                lbl_x_neighbor.set(f"X 到{xs}側鄰近孔")
                lbl_y_edge.set(f"Y 到{ys}邊框")
                lbl_y_neighbor.set(f"Y 到{ys}側鄰近孔")
                var_x_edge.set(f"{d.x_edge_distance:.2f}")
                var_y_edge.set(f"{d.y_edge_distance:.2f}")
                var_x_neighbor.set("" if d.x_neighbor_distance is None else f"{d.x_neighbor_distance:.2f}")
                var_y_neighbor.set("" if d.y_neighbor_distance is None else f"{d.y_neighbor_distance:.2f}")
                ref_entries[("x", "neighbor")].configure(state=(tk.NORMAL if d.x_neighbor_index is not None else tk.DISABLED))
                ref_entries[("y", "neighbor")].configure(state=(tk.NORMAL if d.y_neighbor_index is not None else tk.DISABLED))
            finally:
                suppress_entry_events[0] = False

        def redraw():
            guide = reference_guide
            gminx = float(guide.min_point.x)
            gminy = float(guide.min_point.y)
            gmaxx = float(guide.max_point.x)
            gmaxy = float(guide.max_point.y)
            enclosure_bounds = None
            if (
                active_part_key[0] == "door"
                and indicator_box_dist_var is not None
                and indicator_box_dist_var.get()
                and door_frame_width is not None
                and door_thickness is not None
                and door_gap_w is not None
                and door_gap_h is not None
            ):
                enclosure_offsets = door_enclosure_reference_offsets(
                    door_frame_edges or DoorFrameEdges(),
                    frame_width=door_frame_width,
                    thickness=door_thickness,
                    gap_w=door_gap_w,
                    gap_h=door_gap_h,
                )
                enclosure_bounds = (
                    gminx - enclosure_offsets["left"],
                    gminy - enclosure_offsets["bottom"],
                    gmaxx + enclosure_offsets["right"],
                    gmaxy + enclosure_offsets["top"],
                )

            def draw_extra(canvas_obj, tr, _cw, _ch):
                if enclosure_bounds is not None:
                    ex0, ey0, ex1, ey1 = enclosure_bounds
                    edges = door_frame_edges or DoorFrameEdges()
                    sides = (
                        (Vec2(ex0, ey0), Vec2(ex0, ey1), edges.left),
                        (Vec2(ex1, ey0), Vec2(ex1, ey1), edges.right),
                        (Vec2(ex0, ey1), Vec2(ex1, ey1), edges.top),
                        (Vec2(ex0, ey0), Vec2(ex1, ey0), edges.bottom),
                    )
                    for p1, p2, present in sides:
                        c1 = tr.world_to_canvas(p1)
                        c2 = tr.world_to_canvas(p2)
                        canvas_obj.create_line(
                            *c1, *c2,
                            fill=("#64d2ff" if present else "#8e8e93"),
                            width=2,
                            dash=(None if present else (4, 4)),
                            tags=("door_enclosure_reference",),
                        )

                if active_part_key[0] != "door" or indicator_mode_var is None or door_indicator_context is None:
                    return
                try:
                    state_now = collect_indicator_state()
                    groups = tuple(int(v) for v in state_now["groups"][:state_now["layers"]])
                    if state_now["mode"] == "indicator":
                        indicator_layout = resolve_door_indicator_layout(
                            door_indicator_context,
                            groups,
                            Vec2(state_now["offset_x"], state_now["offset_y"]),
                        )
                        render_resolved_features(canvas_obj, indicator_layout.features, tr, color="#64d2ff")
                        if state_now["is_box_dist"] and door_frame_width is not None and door_thickness is not None:
                            position = measure_door_indicator_position(
                                indicator_layout,
                                door_indicator_context,
                                frame_width=door_frame_width,
                                thickness=door_thickness,
                                use_box_distance=True,
                                frame_edges=door_frame_edges or DoorFrameEdges(),
                                gap_w=door_gap_w,
                                gap_h=door_gap_h,
                            )
                            x_guide, y_guide = resolve_door_indicator_dimension_guides(position)
                            x1 = tr.world_to_canvas(x_guide.start)
                            x2 = tr.world_to_canvas(x_guide.end)
                            y1 = tr.world_to_canvas(y_guide.start)
                            y2 = tr.world_to_canvas(y_guide.end)
                            canvas_obj.create_line(*x1, *x2, fill="#ff9f0a", width=2, arrow=tk.BOTH,
                                                   tags=("door_enclosure_reference", "indicator_dimension"))
                            canvas_obj.create_text((x1[0]+x2[0])/2, (x1[1]+x2[1])/2-12,
                                                   text=f"X={x_guide.value:.1f}", fill="#ff9f0a",
                                                   font=("Consolas", 10, "bold"), tags=("indicator_dimension",))
                            canvas_obj.create_line(*y1, *y2, fill="#ff9f0a", width=2, arrow=tk.BOTH,
                                                   tags=("door_enclosure_reference", "indicator_dimension"))
                            canvas_obj.create_text((y1[0]+y2[0])/2-28, (y1[1]+y2[1])/2,
                                                   text=f"Y={y_guide.value:.1f}", fill="#ff9f0a",
                                                   font=("Consolas", 10, "bold"), angle=90, tags=("indicator_dimension",))
                    elif state_now["mode"] == "indicator_box":
                        hole_w, hole_h = manufacturing_api.indicator_box_opening_size(
                            groups, thickness=float(door_thickness or 0.0)
                        )
                        center = Vec2(
                            door_indicator_context.left_fold + door_indicator_context.finished_width / 2.0 + state_now["offset_x"],
                            door_indicator_context.bottom_fold + door_indicator_context.finished_height / 2.0 + state_now["offset_y"],
                        )
                        box_feature = ResolvedRect(
                            center=center, width=hole_w, height=hole_h,
                            layer="CUTTING", source_type="indicator_box_opening",
                        )
                        render_resolved_features(canvas_obj, [box_feature], tr, color="#64d2ff")
                except Exception:
                    pass

            validate_current_indicator_fit(False)
            canvas_view.render(HoleEditorCanvasFrame(
                surface=surface,
                features=feature_list,
                width=width,
                height=height,
                reference_guide=reference_guide,
                selected_index=hole_session.selected_index,
                reference_distances=last_distances[0],
                measure_guide=active_reference_guide(),
                baseline_scene=baseline_scene,
                extra_bounds=enclosure_bounds,
                insert_label=(selected_catalog_text.get() if insert_mode[0] else None),
                error_text=indicator_fit_error[0],
                draw_extra=draw_extra,
            ))

        indicator_redraw[0] = redraw

        def on_catalog_select(event=None, source_list=None):
            source = source_list
            if source is None and event is not None:
                source = event.widget
            if source is None:
                source = catalog_list
            sel = source.curselection()
            if not sel:
                return
            selected_catalog_text.set(source.get(sel[0]))
            other = pipe_catalog_list if source is catalog_list else catalog_list
            other.selection_clear(0, tk.END)

        def make_feature(point):
            label = selected_catalog_text.get()
            rotation = int(var_rotation.get().replace("°", ""))
            try:
                if label == "＋ 自訂圓孔":
                    definition = custom_circle_definition(float(var_d.get()), blind=var_blind.get())
                elif label == "＋ 自訂方孔":
                    definition = custom_rectangle_definition(float(var_w.get()), float(var_h.get()), blind=var_blind.get())
                else:
                    definition = catalog_by_label.get(label)
                    if definition is None:
                        raise ValueError("請先從左側選擇孔型")
                feature = feature_from_definition(definition, point, width, height, rotation_deg=rotation)
                return feature_with_reference_anchor(feature, ReferenceAnchor.CENTER)
            except (ValueError, FileNotFoundError) as exc:
                messagebox.showerror("開孔錯誤", str(exc))
                return None

        def set_insert_mode(force=None):
            if force is None:
                insert_mode[0] = not insert_mode[0]
            else:
                insert_mode[0] = bool(force)
            insert_btn.configure(text=("停止插入" if insert_mode[0] else "插入"),
                                 bg=("#ff9f0a" if insert_mode[0] else "#30d158"))
            redraw()

        insert_btn.configure(command=set_insert_mode)

        def on_catalog_double_click(event=None, source_list=None):
            source = source_list or (event.widget if event is not None else catalog_list)
            if event is not None:
                idx = source.nearest(event.y)
                if 0 <= idx < source.size():
                    source.selection_clear(0, tk.END)
                    source.selection_set(idx)
                    source.activate(idx)
            on_catalog_select(source_list=source)
            label = selected_catalog_text.get()
            if label.startswith("＋ 自訂"):
                return "break"
            set_insert_mode(True)
            canvas.focus_set()
            return "break"

        def commit_active_edit(keep_selected=True):
            hole_session.execute(HoleEditorAction.commit_active(keep_selected=keep_selected))
            refresh_created()
            refresh_reference_fields()
            redraw()

        def undo_last_action(event=None):
            hole_session.execute(HoleEditorAction.undo())
            refresh_created()
            refresh_reference_fields()
            redraw()
            sync_all()
            return "break"

        def cancel_active_edit():
            had_active = hole_session.has_active_edit
            hole_session.execute(HoleEditorAction.cancel_active())
            if not had_active:
                return False
            refresh_created()
            refresh_reference_fields()
            sync_all()
            redraw()
            return True

        def begin_edit(idx, old_feature_marker="existing"):
            if old_feature_marker == "new":
                # New features enter through HoleEditorAction.insert(); selecting the
                # already-inserted index must not create a second transaction.
                if hole_session.selected_index != idx:
                    hole_session.execute(HoleEditorAction.select(idx))
            else:
                hole_session.execute(HoleEditorAction.select(idx))
            if 0 <= idx < len(feature_list):
                rotation = int(getattr(feature_list[idx], "rotation_deg", 0) or 0) % 360
                var_rotation.set(f"{360 if rotation == 0 else rotation}°")
            refresh_created()
            refresh_reference_fields()
            redraw()

        def select_feature(idx):
            begin_edit(idx, "existing")

        def on_canvas_down(event):
            point = canvas_view.canvas_to_world(event.x, event.y)
            if point is None:
                return
            hit = canvas_view.hit_test(event.x, event.y)
            if hit is not None:
                dragging[0] = True
                select_feature(hit)
                return
            if not insert_mode[0]:
                return
            feature = make_feature(point)
            if feature is None:
                return
            if not feature_is_within_surface(surface, feature, width, height):
                messagebox.showwarning("超出開孔範圍", "孔的完整外形必須全部位於板面框內。")
                return
            hole_session.execute(HoleEditorAction.insert(feature))
            begin_edit(hole_session.selected_index, "new")
            sync_all()

        def on_canvas_drag(event):
            if not dragging[0] or not (0 <= hole_session.selected_index < len(feature_list)):
                return
            point = canvas_view.canvas_to_world(event.x, event.y)
            if point is None:
                return
            idx = hole_session.selected_index
            moved = move_feature_within_surface(feature_list[idx], point, width, height, surface)
            hole_session.execute(HoleEditorAction.replace_selected(moved))
            refresh_reference_fields()
            redraw()

        def on_canvas_up(event):
            if dragging[0]:
                dragging[0] = False
                sync_all()

        def set_reference_anchor(anchor):
            if not (0 <= hole_session.selected_index < len(feature_list)):
                return
            idx = hole_session.selected_index
            candidate = feature_with_reference_anchor(feature_list[idx], anchor)
            hole_session.execute(HoleEditorAction.replace_selected(candidate))
            refresh_reference_fields()
            redraw()
            sync_all()

        def on_canvas_right(event):
            hit = canvas_view.hit_test(event.x, event.y)
            if hit is None:
                return
            select_feature(hit)
            menu = tk.Menu(editor, tearoff=0)
            menu.add_command(label="十字基準線",state=tk.DISABLED)
            menu.add_separator()
            for anchor, label in REFERENCE_ANCHOR_LABELS.items():
                mark = "✓ " if anchor == feature_reference_anchor(feature_list[hit]) else "   "
                menu.add_command(label=mark + label, command=lambda a=anchor: set_reference_anchor(a))
            menu.tk_popup(event.x_root, event.y_root)

        def on_created_select(event=None):
            sel = created_list.curselection()
            if sel:
                select_feature(sel[0])

        def toggle_created_process(event=None):
            sel = created_list.curselection()
            if not sel:
                return
            idx = sel[0]
            hole_session.execute(HoleEditorAction.select(idx))
            old = feature_list[idx]
            process = "CUTTING" if getattr(old, "layer", "CUTTING") == "BLIND_HOLE" else "BLIND_HOLE"
            replacement = feature_with_process(old, process)
            hole_session.execute(HoleEditorAction.replace_selected_committed(replacement))
            refresh_created()
            refresh_reference_fields()
            redraw()
            sync_all()

        def delete_selected():
            idx = hole_session.selected_index
            if 0 <= idx < len(feature_list):
                hole_session.execute(HoleEditorAction.delete_selected())
                refresh_created()
                refresh_reference_fields()
                redraw()
                sync_all()

        delete_btn.configure(command=delete_selected)

        def apply_reference_value(axis, mode, show_errors=False):
            if suppress_entry_events[0]:
                return
            idx = hole_session.selected_index
            if not (0 <= idx < len(feature_list)):
                return
            variable = {('x', 'edge'): var_x_edge, ('x', 'neighbor'): var_x_neighbor,
                        ('y', 'edge'): var_y_edge, ('y', 'neighbor'): var_y_neighbor}[(axis, mode)]
            raw = variable.get().strip()
            if not raw:
                return
            try:
                value = float(raw)
            except ValueError:
                if show_errors:
                    messagebox.showerror("格式錯誤", "距離必須是數字")
                    refresh_reference_fields()
                return
            if value < 0:
                return
            old = feature_list[idx]
            moved = move_feature_by_reference_distance(
                surface, feature_list, idx, feature_reference_anchor(old), width, height,
                axis=axis, mode=mode, value=value, reference_guide=active_reference_guide()
            )
            if moved == old:
                if show_errors:
                    refresh_reference_fields()
                return
            hole_session.execute(HoleEditorAction.replace_selected(moved))
            refresh_reference_fields()
            redraw()
            sync_all()

        def schedule_reference_value(axis, mode):
            key = (axis, mode)
            if key in pending_after:
                try:
                    editor.after_cancel(pending_after[key])
                except Exception:
                    pass
            pending_after[key] = editor.after(350, lambda a=axis, m=mode: apply_reference_value(a, m, False))

        for (axis, mode), ent in ref_entries.items():
            ent.bind("<KeyRelease>", lambda e, a=axis, m=mode: schedule_reference_value(a, m))
            ent.bind("<Return>", lambda e, a=axis, m=mode: apply_reference_value(a, m, True))
            ent.bind("<FocusOut>", lambda e, a=axis, m=mode: apply_reference_value(a, m, False))

        def rotate_selected(angle):
            var_rotation.set(f"{angle}°")
            idx = hole_session.selected_index
            if not (0 <= idx < len(feature_list)):
                return
            normalized = 0 if angle == 360 else angle
            candidate = replace(feature_list[idx], rotation_deg=normalized)
            if not feature_is_within_surface(surface, candidate, width, height):
                messagebox.showwarning("旋轉失敗", "旋轉後孔的完整外形會超出板面框。")
                return
            hole_session.execute(HoleEditorAction.replace_selected(candidate))
            refresh_reference_fields()
            redraw()
            sync_all()

        for angle, btn in rotation_buttons:
            btn.configure(command=lambda a=angle: rotate_selected(a))

        def open_round_hole_settings():
            idx = hole_session.selected_index
            if not (0 <= idx < len(feature_list)) or not isinstance(feature_list[idx], CircleFeature):
                return
            if round_window[0] is not None and round_window[0].winfo_exists():
                round_window[0].lift()
                return

            # Round preview is its own Session transaction. Commit any earlier
            # drag/rotate/reference edit first so there is only one active before
            # snapshot and Undo remains deterministic.
            hole_session.execute(HoleEditorAction.commit_active(keep_selected=True))
            seed_snapshot = list(feature_list)
            selected_feature = seed_snapshot[idx]
            dialog = tk.Toplevel(editor)
            round_window[0] = dialog
            dialog.title("圓孔排列設定")
            dialog.configure(bg=self.COLOR_BG)
            dialog.transient(editor)
            dialog.grab_set()
            dialog.resizable(False, False)

            direction_map = {
                "向左": "left", "向右": "right", "向上": "up", "向下": "down",
                "左右兩側": "both_horizontal", "上下兩側": "both_vertical",
            }
            round_direction = tk.StringVar(value="向右")
            round_driver = tk.StringVar(value="center")
            round_center = tk.StringVar(value=f"{max(float(selected_feature.diameter) * 2.0, 50.0):.2f}")
            round_gap = tk.StringVar()
            round_alignment = tk.StringVar(value="center")
            sync_guard = [False]

            def same_diameter_gap_from_center(center_value):
                return circle_gap_from_center_distance(center_value, selected_feature.diameter, selected_feature.diameter)

            def same_diameter_center_from_gap(gap_value):
                return circle_center_distance_from_gap(gap_value, selected_feature.diameter, selected_feature.diameter)

            def sync_from_center(event=None):
                if sync_guard[0]:
                    return
                try:
                    value = float(round_center.get())
                except ValueError:
                    return
                round_driver.set("center")
                sync_guard[0] = True
                try:
                    round_gap.set(f"{same_diameter_gap_from_center(value):.2f}")
                finally:
                    sync_guard[0] = False

            def sync_from_gap(event=None):
                if sync_guard[0]:
                    return
                try:
                    value = float(round_gap.get())
                except ValueError:
                    return
                round_driver.set("gap")
                sync_guard[0] = True
                try:
                    round_center.set(f"{same_diameter_center_from_gap(value):.2f}")
                finally:
                    sync_guard[0] = False

            sync_from_center()

            # Find the nearest existing circular neighbor only for optional pipe alignment.
            seed_point = feature_finished_point(selected_feature, width, height)
            neighbor_index = None
            neighbor_distance = None
            for other_i, other in enumerate(seed_snapshot):
                if other_i == idx or not isinstance(other, CircleFeature):
                    continue
                op = feature_finished_point(other, width, height)
                distance = (op.x-seed_point.x) ** 2 + (op.y-seed_point.y) ** 2
                if neighbor_distance is None or distance < neighbor_distance:
                    neighbor_index = other_i
                    neighbor_distance = distance

            outer = tk.Frame(dialog, bg=self.COLOR_BG)
            outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
            tk.Label(outer, text=f"目前圓孔：Ø{selected_feature.diameter:g}", bg=self.COLOR_BG, fg="#ffd60a",
                     font=('Microsoft JhengHei', 13, 'bold')).pack(anchor=tk.W, pady=(0, 8))

            dir_frame = tk.LabelFrame(outer, text=" 填滿方向 ", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
                                      font=('Microsoft JhengHei', 11, 'bold'))
            dir_frame.pack(fill=tk.X, pady=4)
            for col, label in enumerate(("向左", "向右", "向上", "向下", "左右兩側", "上下兩側")):
                tk.Radiobutton(dir_frame, text=label, variable=round_direction, value=label,
                               bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                               activebackground=self.COLOR_PANEL, font=('Microsoft JhengHei', 10, 'bold')).grid(
                                   row=col//3, column=col%3, sticky="w", padx=8, pady=4)

            spacing = tk.LabelFrame(outer, text=" 排列距離（兩欄同步） ", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
                                    font=('Microsoft JhengHei', 11, 'bold'))
            spacing.pack(fill=tk.X, pady=6)
            tk.Radiobutton(spacing, text="孔心距為主", variable=round_driver, value="center",
                           bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                           activebackground=self.COLOR_PANEL, font=('Microsoft JhengHei', 10, 'bold'),
                           command=sync_from_center).grid(row=0, column=0, sticky="w", padx=8, pady=4)
            center_entry = tk.Entry(spacing, textvariable=round_center, font=('Consolas', 13, 'bold'), width=10, justify=tk.RIGHT)
            center_entry.grid(row=0, column=1, padx=6, pady=4)
            tk.Label(spacing, text="mm", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED).grid(row=0, column=2, sticky="w")
            tk.Radiobutton(spacing, text="間距為主", variable=round_driver, value="gap",
                           bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                           activebackground=self.COLOR_PANEL, font=('Microsoft JhengHei', 10, 'bold'),
                           command=sync_from_gap).grid(row=1, column=0, sticky="w", padx=8, pady=4)
            gap_entry = tk.Entry(spacing, textvariable=round_gap, font=('Consolas', 13, 'bold'), width=10, justify=tk.RIGHT)
            gap_entry.grid(row=1, column=1, padx=6, pady=4)
            tk.Label(spacing, text="mm", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT_MUTED).grid(row=1, column=2, sticky="w")
            center_entry.bind("<KeyRelease>", sync_from_center)
            center_entry.bind("<FocusIn>", lambda e: round_driver.set("center"))
            gap_entry.bind("<KeyRelease>", sync_from_gap)
            gap_entry.bind("<FocusIn>", lambda e: round_driver.set("gap"))

            align_frame = tk.LabelFrame(outer, text=" 鄰近圓孔對齊 ", bg=self.COLOR_PANEL, fg=self.COLOR_TEXT,
                                        font=('Microsoft JhengHei', 11, 'bold'))
            if neighbor_index is not None:
                align_frame.pack(fill=tk.X, pady=6)
                for label, value in (("孔心齊", "center"), ("管頂齊", "top"), ("管底齊", "bottom")):
                    tk.Radiobutton(align_frame, text=label, variable=round_alignment, value=value,
                                   bg=self.COLOR_PANEL, fg=self.COLOR_TEXT, selectcolor=self.COLOR_INPUT_BG,
                                   activebackground=self.COLOR_PANEL, font=('Microsoft JhengHei', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=6)

            status_var = tk.StringVar(value="設定後可先預覽，再按確定。")
            tk.Label(outer, textvariable=status_var, bg=self.COLOR_BG, fg="#64d2ff",
                     font=('Microsoft JhengHei', 10)).pack(fill=tk.X, pady=(4, 2))

            def driver_value():
                try:
                    value = float(round_center.get() if round_driver.get() == "center" else round_gap.get())
                except ValueError as exc:
                    raise ValueError("孔心距 / 間距必須是數字") from exc
                if round_driver.get() == "center" and value <= 0:
                    raise ValueError("孔心距必須大於 0")
                if round_driver.get() == "gap" and value < 0:
                    raise ValueError("間距不可小於 0")
                return value

            def aligned_seed():
                seed = selected_feature
                if neighbor_index is None:
                    return seed
                direction = direction_map[round_direction.get()]
                axis = "x" if direction in {"left", "right", "both_horizontal"} else "y"
                neighbor = seed_snapshot[neighbor_index]
                candidate = align_circle_to_neighbor(seed, neighbor, round_alignment.get(), axis, width, height)
                return candidate if feature_is_within_surface(surface, candidate, width, height) else seed

            def apply_pattern(refill=False):
                try:
                    value = driver_value()
                    direction = direction_map[round_direction.get()]
                    seed = aligned_seed()
                    generator = generate_round_refill if refill else generate_round_fill
                    result = generator(seed, surface, width=width, height=height, direction=direction,
                                       driver=round_driver.get(), value=value)
                    if not result:
                        raise ValueError("目前設定無法在合法板面內產生圓孔排列")
                except ValueError as exc:
                    messagebox.showerror("圓孔排列", str(exc), parent=dialog)
                    return
                original_point = feature_finished_point(selected_feature, width, height)
                seed_result = min(result, key=lambda f: (feature_finished_point(f, width, height).x-original_point.x)**2 +
                                                       (feature_finished_point(f, width, height).y-original_point.y)**2)
                preview_features = list(seed_snapshot)
                preview_features[idx] = seed_result
                for generated in result:
                    if generated is seed_result:
                        continue
                    preview_features.append(generated)
                hole_session.execute(HoleEditorAction.preview_all(preview_features, selected_index=idx))
                refresh_created()
                refresh_reference_fields()
                redraw()
                sync_all()
                status_var.set(f"預覽：{len(result)} 孔；{'重新填滿' if refill else '填滿'}。")

            action_row = tk.Frame(outer, bg=self.COLOR_BG)
            action_row.pack(fill=tk.X, pady=(7, 4))
            tk.Button(action_row, text="填滿", command=lambda: apply_pattern(False), bg="#0a84ff", fg="white", bd=0,
                      font=('Microsoft JhengHei', 11, 'bold'), padx=18, pady=6).pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(action_row, text="重新填滿", command=lambda: apply_pattern(True), bg="#bf5af2", fg="white", bd=0,
                      font=('Microsoft JhengHei', 11, 'bold'), padx=18, pady=6).pack(side=tk.LEFT, padx=6)

            def close_round_window():
                if round_window[0] is dialog:
                    round_window[0] = None
                try:
                    dialog.grab_release()
                except tk.TclError:
                    pass
                dialog.destroy()

            def cancel_round():
                hole_session.execute(HoleEditorAction.cancel_active())
                refresh_created(); refresh_reference_fields(); redraw(); sync_all()
                close_round_window()

            def confirm_round():
                hole_session.execute(HoleEditorAction.commit_active(keep_selected=True))
                position_authority[0] = "round"
                refresh_created(); refresh_reference_fields(); redraw(); sync_all()
                close_round_window()

            footer_round = tk.Frame(outer, bg=self.COLOR_BG)
            footer_round.pack(fill=tk.X, pady=(8, 0))
            tk.Button(footer_round, text="確定", command=confirm_round, bg="#30d158", fg="white", bd=0,
                      font=('Microsoft JhengHei', 12, 'bold'), padx=28, pady=7).pack(side=tk.RIGHT, padx=(6, 0))
            tk.Button(footer_round, text="取消", command=cancel_round, bg="#ff453a", fg="white", bd=0,
                      font=('Microsoft JhengHei', 12, 'bold'), padx=28, pady=7).pack(side=tk.RIGHT, padx=6)
            dialog.protocol("WM_DELETE_WINDOW", cancel_round)
            dialog.bind("<Escape>", lambda e: (cancel_round(), "break")[1])
            dialog.update_idletasks()
            dw = min(560, max(480, dialog.winfo_reqwidth()))
            dh = min(650, max(430, dialog.winfo_reqheight()))
            dialog.geometry(f"{dw}x{dh}+{max(0, editor.winfo_rootx()+60)}+{max(0, editor.winfo_rooty()+60)}")

        round_settings_btn.configure(command=open_round_hole_settings)

        def _baseline_status_color(text):
            return "#64d2ff" if str(text or "").startswith("基準檔：") else "#ff9f0a"

        def _switch_editor_context(context_key):
            nonlocal feature_list, surface, width, height, reference_guide, baseline_scene
            # Finish/cancel transient placement state before changing which physical
            # part the shared CAD canvas represents.
            if hole_session.has_active_edit:
                cancel_active_edit()
            if insert_mode[0]:
                insert_mode[0] = False
                insert_btn.configure(text="插入", bg="#30d158")

            context = door_editor_context if context_key == "door" else indicator_component_contexts.get(context_key)
            if not context:
                return
            feature_list = context["feature_list"]
            surface = context["surface"]
            width = float(context["width"])
            height = float(context["height"])
            reference_guide = context["reference_guide"]
            baseline_scene = context.get("baseline_scene")
            active_part_key[0] = context.get("part_key", context_key)
            hole_session.activate_context(context_key, feature_list)
            feature_list = hole_session.active_features
            position_authority[0] = None
            status_text = str(context.get("baseline_status_text") or "")
            baseline_status_var.set(status_text)
            if baseline_status_label is not None:
                baseline_status_label.configure(fg=_baseline_status_color(status_text))
            refresh_created()
            refresh_reference_fields()
            redraw()

        def _selected_indicator_component_key():
            if component_tabs is None:
                return "indicator_box"
            selected_tab = component_tabs.select()
            if indicator_door_page is not None and selected_tab == str(indicator_door_page):
                return "indicator_door"
            return "indicator_box"

        def _refresh_indicator_component_contexts():
            if indicator_component_context_provider is None or indicator_mode_var is None:
                return
            state_now = collect_indicator_state()
            if state_now is None or state_now.get("mode") != "indicator_box":
                if component_tabs is not None:
                    component_tabs.pack_forget()
                if hole_session.active_context_key != "door":
                    _switch_editor_context("door")
                set_indicator_page_visible(False)
                if hole_session.active_context_key == "door":
                    redraw()
                return

            try:
                contexts = indicator_component_context_provider(state_now) or {}
            except Exception as exc:
                baseline_status_var.set(f"指示燈盒資料錯誤：{exc}")
                if baseline_status_label is not None:
                    baseline_status_label.configure(fg="#ff453a")
                set_indicator_page_visible(True)
                if hole_session.active_context_key == "door":
                    redraw()
                return

            for context_key in ("indicator_box", "indicator_door"):
                context = contexts.get(context_key)
                if not context:
                    continue
                indicator_component_contexts[context_key] = context

            set_indicator_page_visible(True)
            if editor_tabs is not None and indicator_page is not None and editor_tabs.select() == str(indicator_page):
                if component_tabs is not None and not component_tabs.winfo_manager():
                    component_tabs.pack(fill=tk.X, pady=(0, 4), before=toolbar)
                _switch_editor_context(_selected_indicator_component_key())
            elif hole_session.active_context_key != "door":
                _switch_editor_context("door")
            else:
                redraw()

        def _on_editor_page_changed(event=None):
            if editor_tabs is None or main_page is None:
                return
            selected_page = editor_tabs.select()
            if indicator_page is not None and selected_page == str(indicator_page):
                if component_tabs is not None and not component_tabs.winfo_manager():
                    component_tabs.pack(fill=tk.X, pady=(0, 4), before=toolbar)
                _refresh_indicator_component_contexts()
            else:
                if component_tabs is not None:
                    component_tabs.pack_forget()
                _switch_editor_context("door")

        def _on_indicator_component_page_changed(event=None):
            if editor_tabs is None or indicator_page is None or editor_tabs.select() != str(indicator_page):
                return
            _switch_editor_context(_selected_indicator_component_key())

        if editor_tabs is not None:
            editor_tabs.bind("<<NotebookTabChanged>>", _on_editor_page_changed)
            if component_tabs is not None:
                component_tabs.bind("<<NotebookTabChanged>>", _on_indicator_component_page_changed)
            indicator_context_refresh[0] = _refresh_indicator_component_contexts
            set_indicator_page_visible(
                indicator_mode_var is not None and indicator_mode_var.get() == "indicator_box"
            )
            _refresh_indicator_component_contexts()

        def confirm_reference_edit():
            if not (0 <= hole_session.selected_index < len(feature_list)):
                return
            position_authority[0] = "reference"
            commit_active_edit(keep_selected=False)
            sync_all()

        confirm_ref_btn.configure(command=confirm_reference_edit)
        cancel_ref_btn.configure(command=cancel_active_edit)
        undo_btn.configure(command=undo_last_action)

        def confirm_all():
            if not validate_current_indicator_fit(show_error=True):
                return
            hole_session.finish(commit=True)
            if door_indicator_state is not None:
                committed = collect_indicator_state()
                if committed is not None:
                    door_indicator_state.clear()
                    door_indicator_state.update(committed)
                    if door_indicator_commit is not None:
                        door_indicator_commit(committed)
            editor_closed[0] = True
            sync_all()
            editor.destroy()
            if on_close is not None:
                on_close()

        def cancel_all():
            if editor_closed[0]:
                return
            hole_session.finish(commit=False)
            editor_closed[0] = True
            sync_all()
            editor.destroy()
            if on_close is not None:
                on_close()

        confirm_all_btn.configure(command=confirm_all)
        cancel_all_btn.configure(command=cancel_all)

        def on_escape(event=None):
            if insert_mode[0]:
                set_insert_mode(False)
                return "break"
            if hole_session.has_active_edit:
                cancel_active_edit()
                return "break"
            cancel_all()
            return "break"

        editor.bind("<F11>", toggle_fullscreen)
        editor.bind("<Control-z>", undo_last_action)
        editor.bind("<Control-Z>", undo_last_action)
        editor.bind("<Escape>", on_escape)
        editor.protocol("WM_DELETE_WINDOW", cancel_all)

        catalog_list.bind("<<ListboxSelect>>", lambda e: on_catalog_select(e, catalog_list))
        catalog_list.bind("<Double-Button-1>", lambda e: on_catalog_double_click(e, catalog_list))
        pipe_catalog_list.bind("<<ListboxSelect>>", lambda e: on_catalog_select(e, pipe_catalog_list))
        pipe_catalog_list.bind("<Double-Button-1>", lambda e: on_catalog_double_click(e, pipe_catalog_list))
        created_list.bind("<<ListboxSelect>>", on_created_select)
        created_list.bind("<Double-Button-1>",toggle_created_process)
        canvas.bind("<Button-1>", on_canvas_down)
        canvas.bind("<B1-Motion>", on_canvas_drag)
        canvas.bind("<ButtonRelease-1>", on_canvas_up)
        canvas.bind("<Button-3>", on_canvas_right)
        canvas.bind("<Configure>", lambda e: redraw())
        refresh_created()
        editor.after(50, redraw)

    def open_hole_editor(self, key):
        """Head/Tail compatibility adapter into the same unified editor."""
        label_map={"head":"封頭","tail":"封尾"}
        if key not in label_map:
            messagebox.showerror("開孔失敗",f"未知板面: {key}"); return
        try: val=self.get_float_values()
        except ValueError:
            messagebox.showerror("輸入錯誤","請先確保主畫面所有數值輸入正確"); return
        width=float(val['w']); height=float(val['d']); thickness=float(val['t'])
        face_guide=resolve_endcap_finished_face_guide(width,height,thickness)
        surface=feature_surface_from_rect(f"{key}_finished_face",face_guide.min_point,face_guide.max_point)
        legacy=self.tail_holes if key=="tail" else self.head_holes
        self.surface_features[key]=[legacy_hole_to_feature(hole) for hole in legacy]
        def sync_legacy():
            legacy[:]=[feature_to_legacy_hole(feature,width,height) for feature in self.surface_features[key]]
        reference_guide = RectGuide(Vec2(0.0, 0.0), Vec2(width, height), "finished_boundary")
        self._open_unified_hole_editor(
            key, label_map[key], surface, width, height,
            sync_callback=sync_legacy, reference_guide=reference_guide,
        )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        register_windows_file_association(
            executable=sys.executable, script_path=str(Path(__file__).resolve()),
            frozen=bool(getattr(sys, "frozen", False)),
        )
    except Exception:
        # File association is convenience only; it must never block CAD startup.
        pass

    root = tk.Tk()
    app = BoxCalculatorGUI(root)
    project_path = project_path_from_argv(argv)
    if project_path is not None:
        def open_project_after_startup():
            try:
                app.load_phase6_project(project_path, open_designer=True)
            except Exception as exc:
                messagebox.showerror("專案開啟失敗", f"無法開啟 Phase6 專案：\n{exc}", parent=root)
        root.after_idle(open_project_after_startup)
    root.mainloop()
    return app


if __name__ == "__main__":
    main()
