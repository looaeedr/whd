"""Phase6 Fold Designer composition settings implementation.

Extracted mechanically from fold_designer_adapter; public composition methods remain thin routes.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
import tkinter as tk
import ae_engine.ae as ae
from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.receiving_layout import (
    ensure_receiving_layout as ensure_receiving_preview_layout,
    resize_receiving_bays as resize_receiving_preview_bays,
)
from ae_engine.receiving_joint_locks import resolve_receiving_joint_lock_pattern
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.corner_type_ui import (
    is_unknown_model,
    normalize_custom_model_name,
    known_model_corner_state,
    policy_from_corner_state,
)
from ae_engine.sheetmetal_geometry import (
    CornerTypeId,
    CornerTypeSelection,
    EDITABLE_CORNER_TYPE_IDS,
    CORNER_TYPE_LABELS,
    normalize_corner_selection,
)
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    derive_door_layout_cells,
    door_layout_part_key,
    door_layout_export_filename,
    door_layout_feature_map_to_part_features,
)
from phase6_fold_profiles import formed_box_body_fw_widths
from ae_engine.assembly_joint import AssemblyJointSource, migrate_legacy_snapshot_joints
from phase6_endcap_semantics import (
    normalize_endcap_fw_state,
    ASSEMBLY_TYPE_LABELS,
    assembly_intent_value,
    normalize_endcap_bottom_wrap_state,
)
from phase6_settings_center import UI_TEXT_SIZE_LABELS, load_factory_defaults_from_ae
from phase6_settings_service import Phase6SettingsTransactionService
from phase6_sync_envelope import (
    materialize_sync_value,
    plan_live_sync_envelope,
)
from phase6_settings_contracts import SettingsStateSnapshot
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_project_controller import Phase6ProjectController
from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
from phase6_registry_diagnostics_panel import (
    Phase6RegistryDiagnosticsPanel,
    registry_present_token,
    registry_formula_display,
    registry_formula_raw,
    registry_preconditions_display,
    registry_preconditions_raw,
    registry_source_display,
    registry_source_raw,
)
from phase6_settings_panel import Phase6SettingsPanel
from phase6_workspace_shell import (
    WorkspaceShellActions,
    WorkspaceShellOwner,
    WorkspaceShellState,
    toggle_fullscreen as workspace_shell_toggle_fullscreen,
)
from phase6_box_body_structure import BoxBodyStructureType
from whd_theme import WHD_THEME
from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneDependencies,
    FinalSceneViewRequest,
)
from phase6_final_scene_renderer import Phase6FinalSceneRenderer
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
from phase6_assembly_panel import Phase6AssemblyPanel
from phase6_manufacturing_adapter import operator_finished_dimensions_for_app
from phase6_final_scene_view import Phase6FinalSceneViewAdapter
from gui_modules.application.state_sync import Phase6DerivedCacheOwner
from phase6_derived_part_projection import (
    DerivedPartRequestAssemblyInput,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
)
from gui_modules.runtime_error_log import write_runtime_exception
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)
from gui_modules.parts.panels.divider import collect_divider_input
from gui_modules.parts.panels.door import collect_door_input
from gui_modules.parts.panels.indicator_box import collect_indicator_box_input
from gui_modules.parts.panels.multipart import collect_multipart_input
from gui_modules.application.fold_designer_manufacturing_projection import (
    _fold_designer_secondary_scene_rows,
    _query_fold_designer_baseline_data,
    _apply_cabinet_family_endcap_policy,
    _fold_designer_corner_policy_from_payload,
    _authoritative_render_data,
    _require_verified_baseline_sources_for_manufacturing,
    _export_authoritative_part,
    _query_fold_designer_render_data,
    _payload_topology_context,
    _payload_policy,
    _fold_designer_part_spec_from_payload,
)
from gui_modules.application.fold_designer_snapshot_projection import (
    _snapshot_base_state,
    _snapshot_workspace_state,
    _snapshot_part_dimensions,
    _make_original_fold_designer_snapshot,
)

def settings_context_extension_projection(self, namespace, context):
    """Project Settings context extensions at the existing composition boundary."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    endcap_fw_parts = required("ENDCAP_FW_PARTS")
    global_context = required("GLOBAL_CONTEXT")
    cross_corner_mode = required("CrossCornerMode")

    def endcap_fw_projection(part_key):
        part_key = str(part_key)
        snapshot = dict(getattr(app, "_phase6_input_snapshot", {}) or {})
        snapshot.update(dict(getattr(app, "_settings_values", {}) or {}))
        state = app._phase6_endcap_fw_state.setdefault(
            part_key,
            {
                "follow_box": True,
                "value": required("_num")(snapshot.get("fw", 25), 25),
            },
        )
        return {
            "follow": bool(state.get("follow_box", True)),
            "effective": required("resolve_endcap_fw")(
                snapshot,
                part_key,
                state=app._phase6_endcap_fw_state,
            ),
        }

    def box_structure_projection():
        state = required("_phase6_box_structure_state")(app)
        active = BoxBodyStructureType(state["active_type"])
        cfg = state["configs"][active.value]
        total_w = required("_phase6_box_structure_w")(app)
        piece_values = {}
        mode = "integral"
        if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
            mode = "two_w"
            left, right = required("resolve_two_piece_widths")(
                state, total_w
            )
            piece_values = {
                "box_body:left": (
                    "width", "W 包外", left, "mm", "left"
                ),
                "box_body:right": (
                    "width", "W 包外", right, "mm", "right"
                ),
            }
        elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
            mode = "three_w"
            left, middle, right = required("resolve_three_piece_widths")(
                state, total_w
            )
            piece_values = {
                "box_body:left": (
                    "width", "W 包外", left, "mm", "left"
                ),
                "box_body:middle": (
                    "width", "W 包外", middle, "mm", "middle"
                ),
                "box_body:right": (
                    "width", "W 包外", right, "mm", "right"
                ),
            }
        elif active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
            mode = "side_back"
            snapshot = getattr(app, "_phase6_input_snapshot", {}) or {}
            outside_family = (
                cabinet_family_policy.box_body_profile_uses_outside_dimensions(
                    snapshot
                )
            )
            rear_bend = (
                required("side_rear_bend_outside_length")(
                    state, float(snapshot.get("t", 2.0))
                )
                if outside_family
                else float(cfg.get("side_rear_bend", 15))
            )
            width_comp_t = float(cfg.get("back_width_comp_t", 0.5))
            piece_values = {
                "box_body:left_side": (
                    "rear_bend",
                    "後折",
                    rear_bend,
                    "mm",
                    "side_rear_bend",
                ),
                "box_body:back": (
                    "width_comp_t",
                    "寬補償",
                    width_comp_t,
                    "T",
                    "back_width_comp_t",
                ),
                "box_body:right_side": (
                    "rear_bend",
                    "後折",
                    rear_bend,
                    "mm",
                    "side_rear_bend",
                ),
            }

        projections = ()
        projection_error = None
        if active is not BoxBodyStructureType.INTEGRAL:
            try:
                render_data = required(
                    "_phase6_box_body_structure_render_data"
                )(app)
                projections = required(
                    "_phase6_box_body_piece_dimension_projections"
                )(render_data)
                active_piece_key = str(
                    getattr(app.designer_workspace, "active_part", "")
                    or ""
                )
                if required(
                    "_phase6_is_box_body_physical_piece_key"
                )(active_piece_key):
                    projections = tuple(
                        row
                        for row in projections
                        if row.part_key == active_piece_key
                    )
            except Exception as exc:
                projection_error = str(exc)

        pieces = []
        for projection in projections:
            part_key = str(projection.part_key)
            spec = piece_values.get(part_key)
            input_spec = None
            if spec is not None:
                field_key, label, value, suffix, state_field = spec
                input_spec = {
                    "field_key": field_key,
                    "label": label,
                    "value": value,
                    "suffix": suffix,
                    "state_field": state_field,
                }
            detail = None
            if active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
                if part_key in {
                    "box_body:left_side",
                    "box_body:right_side",
                }:
                    detail = (
                        "成型深度 D："
                        f"{required('_setting_number_text')(required('_phase6_box_structure_d')(app))} mm"
                    )
                elif part_key == "box_body:back":
                    detail = (
                        "成型寬："
                        f"{required('_setting_number_text')(projection.formed_width)} mm"
                    )
            pieces.append(
                {
                    "part_key": part_key,
                    "label": projection.label,
                    "formed_width": projection.formed_width,
                    "formed_height": projection.formed_height,
                    "blank_width": projection.blank_width,
                    "blank_height": projection.blank_height,
                    "input": input_spec,
                    "back_panel_selector": None,
                    "detail": detail,
                }
            )

        advanced_fields = ()
        if mode in {"two_w", "three_w"}:
            advanced_fields = (
                {
                    "label": "封頭尾額外避讓",
                    "field": "endcap_extra_relief",
                    "value": cfg.get("endcap_extra_relief", 5),
                    "suffix": "mm",
                },
                {
                    "label": "封頭尾單邊留肉",
                    "field": "endcap_single_side_meat_t",
                    "value": cfg.get("endcap_single_side_meat_t", 0.5),
                    "suffix": "T",
                },
                {
                    "label": "底板避讓總長",
                    "field": "baseplate_relief_length",
                    "value": cfg.get("baseplate_relief_length", 20),
                    "suffix": "mm",
                },
                {
                    "label": "底板單邊留肉",
                    "field": "baseplate_single_side_meat_t",
                    "value": cfg.get("baseplate_single_side_meat_t", 0.5),
                    "suffix": "T",
                },
            )
        advanced_flags = dict(
            getattr(app, "_phase6_box_structure_advanced_open", {}) or {}
        )
        return {
            "active_type": active,
            "mode": mode,
            "pieces": tuple(pieces),
            "projection_error": projection_error,
            "seam_bend": cfg.get("seam_bend", 12),
            "advanced_open": bool(
                advanced_flags.get(active.value, False)
            ),
            "advanced_fields": advanced_fields,
        }

    def bottom_wrap_projection(part_key):
        snapshot = dict(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        )
        if (
            str(part_key) not in endcap_fw_parts
            or not cabinet_family_policy.supports_bottom_wrap_controls(
                snapshot
            )
        ):
            return None
        item = required("resolve_endcap_bottom_wrap")(
            snapshot,
            str(part_key),
            state=getattr(
                app,
                "_phase6_endcap_bottom_wrap_state",
                required("normalize_endcap_bottom_wrap_state")(snapshot),
            ),
        )
        if not bool(item.get("enabled", False)):
            return None
        return {
            "reserve_u": item["reserve_u"],
            "reserve_v": item["reserve_v"],
        }

    def corner_projection(part_key):
        part_key = str(part_key)
        if part_key == global_context or part_key == "box_body":
            return {"mode": "none"}

        fixed_summaries = required("_FIXED_CORNER_SUMMARIES")
        if part_key in {"indicator_box", "indicator_door"}:
            summary = fixed_summaries.get(part_key, "")
            if summary:
                return {"mode": "fixed", "summary": summary}

        type_editable = required("_phase6_corner_type_editable")(
            app, part_key
        )
        params_unlocked = required(
            "_phase6_corner_parameters_unlocked"
        )(app, part_key)
        params_editable = required(
            "_phase6_corner_parameters_editable"
        )(app, part_key)
        if not type_editable and not params_unlocked:
            summary = fixed_summaries.get(part_key, "")
            if summary:
                return {"mode": "fixed", "summary": summary}

        state, pairs = required("_phase6_ensure_corner_part")(
            app, part_key
        )
        pair_keys = required("_CORNER_PAIR_KEYS")
        type_labels = required("_CORNER_TYPE_LABEL_BY_ID")
        direction_labels = required("_CORNER_DIRECTION_LABEL")
        mode_labels = required("_CORNER_MODE_LABEL")
        pair_rows = []
        for pair_key in ("top", "bottom"):
            targets = (
                (pair_key,)
                if pairs[pair_key]
                else pair_keys[pair_key]
            )
            target_rows = []
            for target_key in targets:
                physical = (
                    pair_keys[target_key][0]
                    if target_key in pair_keys
                    else target_key
                )
                selection = required("_phase6_selection_from_raw")(
                    state[physical]
                )
                if (
                    selection.type_id is CornerTypeId.CROSS
                    and selection.cross_mode is cross_corner_mode.RETAIN
                ):
                    direction_options = ("寬", "高")
                elif (
                    selection.type_id is CornerTypeId.CROSS
                    and selection.cross_mode
                    is not cross_corner_mode.STANDARD
                ):
                    direction_options = ("寬＋高", "寬", "高")
                else:
                    direction_options = ()
                direction_label = (
                    direction_labels[selection.direction]
                    if selection.type_id is CornerTypeId.CROSS
                    and selection.cross_mode
                    is not cross_corner_mode.STANDARD
                    else ""
                )
                target_rows.append(
                    {
                        "target_key": target_key,
                        "side_label": (
                            ""
                            if len(targets) <= 1
                            else (
                                "左"
                                if target_key.endswith("left")
                                else "右"
                            )
                        ),
                        "type_label": type_labels[
                            selection.type_id.value
                        ],
                        "type_options": tuple(type_labels.values()),
                        "type_kind": selection.type_id.name,
                        "top_assembly_owned": (
                            part_key in {"head", "tail"}
                            and pair_key == "top"
                        ),
                        "parameter_summary": required(
                            "_phase6_corner_parameter_summary"
                        )(selection),
                        "amount_t": (
                            selection.amount_t
                            if selection.amount_t is not None
                            else 1.0
                        ),
                        "mode_label": (
                            mode_labels[selection.cross_mode]
                            if selection.type_id is CornerTypeId.CROSS
                            and selection.cross_mode is not None
                            else ""
                        ),
                        "mode_kind": (
                            selection.cross_mode.name
                            if selection.type_id is CornerTypeId.CROSS
                            and selection.cross_mode is not None
                            else ""
                        ),
                        "direction_label": direction_label,
                        "direction_options": direction_options,
                        "secondary_retain_t": (
                            selection.secondary_retain_t
                        ),
                        "secondary_depth_t": (
                            selection.secondary_depth_t
                        ),
                    }
                )
            pair_rows.append(
                {
                    "pair_key": pair_key,
                    "label": "上方" if pair_key == "top" else "下方",
                    "same": bool(pairs[pair_key]),
                    "targets": tuple(target_rows),
                }
            )
        return {
            "mode": "editable",
            "type_editable": bool(type_editable),
            "params_unlocked": bool(params_unlocked),
            "params_editable": bool(params_editable),
            "pairs": tuple(pair_rows),
        }

    context = str(context)
    return {
        "box_structure": (
            box_structure_projection()
            if context == "box_body"
            else None
        ),
        "endcap_fw": (
            endcap_fw_projection(context)
            if context in endcap_fw_parts
            else None
        ),
        "bottom_wrap": (
            bottom_wrap_projection(context)
            if context in endcap_fw_parts
            else None
        ),
        "corner": corner_projection(context),
    }

def sync_settings_panel_extension(
    self,
    namespace,
    state,
    context,
):
    """Mirror extension widgets without moving Settings state ownership."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    state = dict(state or {})
    for name in (
        "corner_pair_vars",
        "corner_pair_checkbuttons",
        "corner_type_vars",
        "corner_mode_vars",
        "corner_direction_vars",
        "corner_amount_vars",
        "corner_secondary_retain_vars",
        "corner_secondary_depth_vars",
        "corner_detail_frames",
    ):
        setattr(app, name, dict(state.get(name, {}) or {}))
    original = required("original")
    app.fixed_corner_summary_var = (
        state.get("fixed_corner_summary_var")
        or original.tk.StringVar(value="")
    )
    app.corner_param_lock_button = state.get(
        "corner_param_lock_button"
    )
    app.bottom_wrap_enabled_var = state.get(
        "bottom_wrap_enabled_var"
    )
    app.bottom_wrap_reserve_u_var = state.get(
        "bottom_wrap_reserve_u_var"
    )
    app.bottom_wrap_reserve_v_var = state.get(
        "bottom_wrap_reserve_v_var"
    )
    app.bottom_wrap_widget = state.get("bottom_wrap_widget")
    app.box_body_piece_input_host = state.get(
        "box_body_piece_input_host"
    )
    app.box_body_piece_input_sections = dict(
        state.get("box_body_piece_input_sections", {}) or {}
    )
    app.box_body_piece_input_vars = dict(
        state.get("box_body_piece_input_vars", {}) or {}
    )
    app.box_body_piece_input_entries = dict(
        state.get("box_body_piece_input_entries", {}) or {}
    )
    if (
        context in required("ENDCAP_FW_PARTS")
        and state.get("endcap_fw_follow_var") is not None
    ):
        snapshot = dict(
            getattr(app, "_phase6_input_snapshot", {}) or {}
        )
        snapshot.update(
            dict(getattr(app, "_settings_values", {}) or {})
        )
        fw_state = app._phase6_endcap_fw_state.setdefault(
            context,
            {
                "follow_box": True,
                "value": required("_num")(
                    snapshot.get("fw", 25), 25
                ),
            },
        )
        follow = bool(fw_state.get("follow_box", True))
        effective = required("resolve_endcap_fw")(
            snapshot,
            context,
            state=app._phase6_endcap_fw_state,
        )
        state["endcap_fw_follow_var"].set(follow)
        state["endcap_fw_value_var"].set(
            required("_setting_number_text")(effective)
        )
        try:
            state["endcap_fw_widget"].configure(state="normal")
        except Exception:
            pass

def sync_settings_panel_compat(self):
    app = self.app
    panel = app.settings_panel
    app.settings_center = panel.settings_center
    app.settings_fields = panel.settings_fields
    app.settings_title_var = panel.settings_title_var
    app.unfolded_size_var = panel.unfolded_size_var
    app.settings_status_var = panel.settings_status_var
    app.save_settings_button = panel.save_settings_button
    app.setting_vars = panel.setting_vars
    app._settings_page_cache = panel.page_cache
    app._settings_current_page = panel.current_page
    app.settings_context = panel.settings_context
    app.advanced_settings_visible = panel.advanced_settings_visible
    app.advanced_settings_frame = panel.advanced_settings_frame
    app.advanced_toggle_button = panel.advanced_toggle_button
    app.baseline_data_frame = panel.baseline_data_frame
    app.baseline_data_toggle_button = panel.baseline_data_toggle_button
    app.baseline_setting_cells = panel.baseline_setting_cells
    app.left_global_controls = panel.left_global_controls
    app.left_global_vars = panel.left_global_vars
    app.left_global_cells = panel.left_global_cells
    app.baseline_model_var = panel.baseline_model_var
    app.baseline_model_combo = panel.baseline_model_combo
    app.ui_text_size_var = panel.ui_text_size_var
    app.ui_text_size_combo = panel.ui_text_size_combo
    app.save_global_settings_button = panel.save_global_settings_button
    return panel

def settings_panel_toggle_baseline(self):
    self.app.settings_panel.toggle_baseline_data()
    self.sync_settings_panel_compat()

def invalidate_settings_page(self, context):
    self.app.settings_panel.invalidate_context(str(context))
    self.sync_settings_panel_compat()

def render_settings_context(self, namespace, context):
    app = self.app
    required = lambda name: self._required(namespace, name)
    app._phase6_settings_rendering = True
    try:
        page = app.settings_panel.render_context(
            str(context or required("GLOBAL_CONTEXT"))
        )
        self.sync_settings_panel_compat()
        return page
    finally:
        app._phase6_settings_rendering = False

def save_current_settings_as_defaults(self):
    return self.app.settings_panel.save_current_settings_as_defaults()

def on_baseline_model_changed(self, namespace, *_args):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if getattr(app, "_phase6_baseline_guard", False):
        return None
    app._phase6_corner_param_unlocked = {}
    new_model = str(app.baseline_model_var.get() or "").strip()
    old_model = str(
        getattr(app, "_phase6_baseline_last_model", "") or ""
    ).strip()
    old_editable = required("_phase6_is_unknown_baseline")(
        app, old_model
    )
    if old_editable:
        app._corner_transaction_unknown_state = deepcopy(
            app._phase6_corner_state
        )
        app._corner_transaction_unknown_pairs = deepcopy(
            app._phase6_corner_pair_same
        )

    editable = required("_phase6_is_unknown_baseline")(
        app, new_model
    )
    needs_fixed_corner_preset = bool(
        (not editable and new_model and new_model != old_model)
        or (editable and old_model and not old_editable)
    )
    fixed_corner_state = (
        required("_phase6_known_model_corner_state")(app)
        if needs_fixed_corner_preset
        else {}
    )
    previous_non_receiving_structure = getattr(
        app,
        "_phase6_non_receiving_structure_state",
        None,
    )
    coordinator = self.settings_coordinator(
        self.settings_application_ports(namespace)
    )
    return coordinator.apply_baseline_transition(
        new_model=new_model,
        old_model=old_model,
        new_editable=editable,
        old_editable=old_editable,
        fixed_corner_state=fixed_corner_state,
        available_parts=tuple(
            getattr(app.designer_workspace, "available_parts", ())
            or ()
        ),
        previous_non_receiving_structure=previous_non_receiving_structure,
    )

def apply_external_settings(self, namespace, updates):
    app = self.app
    app._phase6_external_apply_guard = True
    try:
        coordinator = self.settings_coordinator(
            self.settings_application_ports(namespace)
        )
        return coordinator.apply_updates(
            updates,
            notify=False,
            external_apply_guard=True,
        )
    finally:
        app._phase6_external_apply_guard = False

def apply_external_model(self, namespace, model):
    app = self.app
    plan = self.settings_transactions().plan_external_model_change(
        model
    )
    if not plan.changed:
        return False

    app._phase6_external_apply_guard = True
    try:
        model_var = getattr(app, "baseline_model_var", None)
        if model_var is None:
            return False
        if str(model_var.get() or "").strip() != plan.target_model:
            model_var.set(plan.target_model)
        if (
            str(
                (
                    getattr(app, "_phase6_input_snapshot", {}) or {}
                ).get("model")
                or ""
            ).strip()
            != plan.target_model
        ):
            self.on_baseline_model_changed(namespace)
    finally:
        app._phase6_external_apply_guard = False
    return (
        str(
            (
                getattr(app, "_phase6_input_snapshot", {}) or {}
            ).get("model")
            or ""
        ).strip()
        == plan.target_model
    )

def apply_external_sync(self, namespace, envelope):
    app = self.app
    plan = self.settings_service().plan_external_sync(envelope)
    if not plan.accepted or not plan.settings:
        return {}
    result = self.apply_external_settings(namespace, plan.settings)
    if (
        str(getattr(app, "_phase6_3d_display_mode", "") or "")
        == "corner_data"
        and getattr(app, "corner_data_canvas", None) is not None
    ):
        self.refresh_corner_data_unfold_view(namespace)
    return result

def update_left_workspace_width(self, namespace, key=None):
    app = self.app
    required = lambda name: self._required(namespace, name)
    canvas = getattr(app, "left_scroll_canvas", None)
    if canvas is None:
        return None
    value = (
        key
        if key is not None
        else app._settings_values.get("ui_text_size", "small")
    )
    target = required("_phase6_left_workspace_width")(value)
    canvas.configure(width=target)
    try:
        canvas.update_idletasks()
    except Exception:
        pass
    return target

def apply_ui_text_size(self, namespace, key):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if getattr(app, "_phase6_settings_guard", False):
        return None
    key = required("normalize_ui_text_size")(key)
    app._settings_values["ui_text_size"] = key
    app._phase6_input_snapshot["ui_text_size"] = key
    app._ui_text_controller.apply(key)
    app.state.ui_text_scale = app._ui_text_controller.factor
    self.update_left_workspace_width(namespace, key)
    callback = getattr(app, "_ui_text_size_change_callback", None)
    if (
        callback is not None
        and not getattr(app, "_phase6_external_apply_guard", False)
    ):
        callback(key)
    try:
        app.bend_ui.render()
    except Exception:
        pass
    try:
        app.renderer.render()
    except Exception:
        pass
    return key

def on_ui_text_size_changed(self, namespace, *_args):
    app = self.app
    panel = getattr(app, "settings_panel", None)
    var = (
        getattr(panel, "ui_text_size_var", None)
        if panel is not None
        else getattr(app, "ui_text_size_var", None)
    )
    if var is None:
        return None
    return self.apply_ui_text_size(namespace, var.get())
