"""Application/session lifecycle seams extracted from the legacy GUI host.

Authoritative settings, workspace, project and manufacturing ownership remains
with the existing services/controllers/engine.  This module only coordinates them.
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
from whd_theme import WHD_THEME, apply_ttk_dark_theme
import ae_engine.ae as ae  # AE manufacturing engine package
from ae_engine import manufacturing_api
from ae_engine.engineering_drawing import build_engineering_drawing_projection
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
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
from gui_modules.drawing import (
    _corner_preview_canvas_point,
    _corner_preview_flip_y_for_target,
    render_drawing_scene,
)
from gui_modules.layout import _project_toolbar_presentation
from gui_modules.part_panels import (
    _phase6_logical_part_present as _phase6_logical_part_present_impl,
)
from gui_modules.render_2d import (
    _draw_layout_resolved_features as _draw_layout_resolved_features_impl,
    _draw_layout_baseline_secondary as _draw_layout_baseline_secondary_impl,
    draw_grid as _draw_grid_impl,
)
from gui_modules.project_actions import (
    save_phase6_project_as as _save_phase6_project_as_impl,
    save_phase6_project as _save_phase6_project_impl,
    open_phase6_project as _open_phase6_project_impl,
    load_phase6_project as _load_phase6_project_impl,
)
from ae_engine.hole_catalog import (
    load_hole_catalog,
    load_pipe_catalog,
    feature_from_definition,
    custom_circle_definition,
    custom_rectangle_definition,
)
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
    TextPrimitive,
    DrawingScene,
    resolved_features_to_primitives,
    mirror_point_y,
)
from gui_modules.application.command_router import (
    _Phase6UpdateScheduler,
    install_application_update_scheduler_lifecycle,
)

def phase6_application_host_init(self, root):
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
    self.COLOR_BG = WHD_THEME["background"]          # 主背景
    self.COLOR_PANEL = WHD_THEME["panel"]       # 面板背景
    self.COLOR_INPUT_BG = WHD_THEME["input"]    # 輸入框背景
    self.COLOR_TEXT = WHD_THEME["text"]        # 主要文字
    self.COLOR_TEXT_MUTED = WHD_THEME["muted_text"]  # 次要文字
    self.COLOR_ACCENT = WHD_THEME["action"]      # 藍色亮點/按鈕
    self.COLOR_ACCENT_HOVER = "#0066cc"# 按鈕懸停
    self.COLOR_CANVAS_BG = WHD_THEME["canvas"]   # 畫布背景

    self.root.configure(bg=self.COLOR_BG)

    # Committed runtime settings 的唯一所有者。config.ini 只負責啟動預設與明確持久化。
    self.settings_service = SettingsService(ae)
    self._settings_sync_guard = False
    self._phase6_update_scheduler = _Phase6UpdateScheduler(self)
    install_application_update_scheduler_lifecycle(self)
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
    # DXF export selection is an independent operator intention.
    # Physical presence constrains what export_selected_dxf() may emit, but
    # changing presence must never rewrite the export checkboxes themselves.
    self.is_indicator_box_var.set("indicator_box" in existing)
    # Small indicator door may exist independently of the box in project
    # state; the existing legacy toggle represents the standalone-door mode.
    self.is_door_indicator_var.set("indicator_door" in existing and "indicator_box" not in existing)

    # Legacy 2D tabs are retired. Physical presence is projected by the
    # authoritative workspace and Fold Designer views only.
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
    self._active_cabinet_type = _current_cabinet_type_name(self)
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
    box_profile = snapshot.get("box_body_profile", ws_source.get("box_body_profile"))
    if box_profile is None:
        # Legacy projects predate the canonical Fold Profile. Some migration
        # adapters materialize the missing key as an explicit null, so null
        # remains a migration signal. An explicit empty list is corrupt and
        # is rejected below instead of reviving scalar geometry.
        migration_source = dict(settings)
        for key in (
            "model", "w", "h", "d", "t", "fw",
            "zl1", "zl2", "zr1", "zr2", "z_comp",
        ):
            if key in snapshot:
                migration_source[key] = snapshot[key]
        migration_source["model"] = str(
            snapshot.get("model")
            or _current_cabinet_type_name(self)
        ).strip()
        box_profile = build_box_body_profile(migration_source)
        if not box_profile:
            raise ValueError("legacy Box Body Fold Profile migration failed")
    elif not list(box_profile):
        raise ValueError("canonical Box Body Fold Profile is empty")

    self._store_fold_designer_workspace({
        "box_body_profile": box_profile,
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
        workspace_active = str(
            (dict(workspace or {}).get("active_part") if workspace else "")
            or payload.get("box_body_active_piece")
            or payload.get("active_part")
            or ""
        )
        if workspace_active.startswith("box_body:") and not workspace_active.startswith("box_body:divider:"):
            self.box_body_piece_2d_selected_var.set(workspace_active)
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

def open_original_fold_designer(self, *, target_window=None):
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

    if target_window is None:
        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.grab_set()
    else:
        window = target_window
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

    designer_factory = getattr(self, "_fold_designer_factory", None)
    if designer_factory is None:
        raise RuntimeError("Fold Designer factory is not connected")
    designer = designer_factory(
        window, designer_snapshot,
        on_settings_change=None,
        on_save_defaults=self._save_fold_designer_defaults,
        on_corner_change=None,
        on_live_sync=lambda payload: self._apply_fold_designer_live_snapshot(deepcopy(payload)),
        on_baseline_data_query=self._query_fold_designer_baseline_data,
        on_scene_query=self._query_fold_designer_render_data,
        on_part_spec_query=self._fold_designer_part_spec_from_payload,
        on_ui_text_size_change=lambda value: self._apply_ui_text_size_preference(
            value, persist=True, notify_designer=False
        ),
        on_project_load=load_project_from_designer,
        on_project_path_change=project_path_changed,
        on_project_save=save_project_from_designer,
        output_draw_stock_var=self.draw_stock_var,
        output_export_vars={
            "box_body": self.export_z_var,
            "head": self.export_head_var,
            "tail": self.export_tail_var,
            "door": self.export_door_var,
            "base_plate": self.export_base_plate_var,
            "indicator_box": self.export_ib_var,
            "indicator_door": self.export_ib_door_var,
        },
        on_export_selected_dxf=lambda: self.export_selected_dxf(),
    )
    designer._corner_data_view_render_callback = self._render_fold_designer_corner_data_view
    self.fold_designer_window = window
    self.fold_designer_app = designer
    window.protocol("WM_DELETE_WINDOW", close_designer)
    return designer

