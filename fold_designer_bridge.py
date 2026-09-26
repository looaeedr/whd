# -*- coding: utf-8 -*-
"""Phase6 與原始 Fold Designer 之間的 UI／交易 adapter。

此模組不擁有 CornerType／EndCap FW／Fold Profile 機械語意；那些規則分別由
``phase6_endcap_semantics`` 與 ``phase6_fold_profiles`` 擁有。這裡只保留
Fold Designer/Tk 接線、交易協調、scene/view adapter 與舊 caller 相容 re-export。
"""
from __future__ import annotations

from phase6_corner_dimension_display import (
    render_data_corner_dimension_text as _phase6_render_data_corner_dimension_text,
    measurement_text as _phase6_relief_measurement_text,
)

from copy import deepcopy
from dataclasses import dataclass
from phase6_sync_envelope import (
    materialize_sync_value,
    plan_live_sync_envelope,
    stable_fingerprint,
)
from pathlib import Path
import re
import logging
from typing import Mapping, MutableMapping
from whd_theme import WHD_THEME, apply_ttk_dark_theme, configure_tk_menu

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_part_adapters import (
    derive_door_layout_cells,
    door_layout_part_key,
)
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_derived_part_projection import (
    DerivedPartRequestAssemblyInput,
    build_derived_part_projection_request,
    build_derived_part_sync_plan,
)
from phase6_part_navigation import (
    NavigationIntent,
    NavigationMemory,
    NavigationRequest,
    box_body_piece_keys as _dm7_box_body_piece_keys,
    is_box_body_physical_piece_key as _dm7_is_box_body_physical_piece_key,
    operator_part_selector_keys as _dm7_operator_part_selector_keys,
    project_hierarchy as _dm7_project_hierarchy,
    resolve_navigation as _dm7_resolve_navigation,
)
from phase6_assembly_presentation import (
    build_assembly_presentation_model,
    legacy_assembly_presentation_groups,
)
from phase6_assembly_panel import AssemblyPanelActions, Phase6AssemblyPanel
from phase6_box_body_structure import (
    BoxBodyStructureType, BackPanelMode, normalize_box_body_structure_state,
    set_side_back_geometry, set_side_back_piece_profile,
    set_side_back_back_panel_mode, back_panel_mode, side_rear_bend_outside_length,
    resolve_two_piece_widths, resolve_three_piece_widths,
)

from phase6_settings_center import (
    GLOBAL_CONTEXT, settings_for_context, UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size, ui_text_size_label,
)
from phase6_settings_service import Phase6SettingsTransactionService
from phase6_settings_profile_projection import (
    SettingsProfileProjectionRequest,
    build_settings_profile_projection,
    build_standard_part_profiles,
    door_part_projections as _phase6_door_part_projections,
    materialize_settings_profile_value,
    merge_keyed_profiles as _merge_keyed_profiles,
    project_part_dimensions,
)
from phase6_project_controller import Phase6ProjectController
from phase6_registry_diagnostics_panel import build_registry_choice
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
from gui_modules.application.command_router import (
    execute_fold_designer_update_reasons,
    submit_fold_designer_update_intent,
    queue_fold_designer_update,
    cancel_fold_designer_update_intents,
    install_fold_designer_keyboard_shortcuts,
)
from phase6_workspace_shell import (
    mount_shared_content as _workspace_shell_mount_shared_content,
    toggle_fullscreen as _workspace_shell_toggle_fullscreen,
)
from gui_modules.application.fold_designer_adapter import (
    Phase6FoldDesignerComposition,
    install_fold_designer_bridge_facade,
)
import phase6_project_file as _phase6_project_file
from phase6_settings_panel import (
    setting_number_text as _setting_number_text,
    build_choice_menubutton,
)
from ui_text_scale import TextScaleController
from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource,
    migrate_legacy_snapshot_joints, edge_relation_for_part,
)
from ae_engine.assembly_intent import get_assembly_intent
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CrossCornerMode, CornerDirection,
    EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS, normalize_corner_selection,
)

from ae_engine.corner_type_ui import (
    CUSTOM_MODEL_NAME, LEGACY_CUSTOM_MODEL_NAMES, known_model_corner_state,
    normalize_custom_model_name,
)

from phase6_endcap_semantics import (
    ASSEMBLY_TYPE_LABELS, ASSEMBLY_LABEL_TO_TYPE, ENDCAP_FW_PARTS,
    normalize_endcap_fw_state, resolve_endcap_fw, set_endcap_fw_follow, set_endcap_fw_override,
    commit_box_fw, commit_endcap_fw,
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap,
    resolve_box_assembly_type, apply_box_assembly_type_to_raw_state, assembly_intent_value,
    selection_to_raw as _phase6_selection_to_raw,
    selection_from_raw as _phase6_selection_from_raw,
)
from phase6_fold_profiles import (
    _num, _ui_len, apply_outside_dimension_compensation,
    build_box_body_profile, build_endcap_profile, read_endcap_profile,
    build_endcap_xy_profiles, _phase6_fold_tabs_for_part,
    _phase6_normalize_endcap_profile_order, read_endcap_xy_profiles,
    engine_angle_to_ui, ui_angle_to_engine, engine_segment_length_to_ui,
    ui_segment_length_to_engine, read_box_body_profile, can_remove_segment, clone_profile,
    profile_to_fold_segments, formed_box_body_fw_widths,
    build_linked_endcap_xy_profiles, merge_box_body_profile,
)

from phase6_diagnostics import (
    collect_final_geometry_diagnostics,
    json_safe as _phase6_json_safe,
    serialize_scene as _phase6_serialize_scene,
    material_diagnostic as _phase6_material_diagnostic,
    serialize_fold_guides as _phase6_serialize_fold_guides,
    write_diagnostic_json as _phase6_write_diagnostic_json,
)

from phase6_final_scene_contracts import FinalSceneViewRequest
from phase6_final_scene_projection import (
    _phase6_profile_base_index,
    _phase6_profile_geometry,
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_profile_flat_map,
    _phase6_folded_mesh_from_polygon,
    _phase6_fitted_limits_from_vertices,
    _phase6_fold_ownership_exemptions,
    format_operator_info_text,
)
from phase6_final_scene_renderer import (
    Phase6FinalSceneView,
    _PHASE6_DEFAULT_VIEW,
    _PHASE6_ZOOM_MIN,
    _PHASE6_ZOOM_MAX,
)
from phase6_final_scene_view import (
    _phase6_add_mesh_boundary_lines,
    _phase6_draw_scene_markings,
    _phase6_configure_3d_only_figure,
    _phase6_adjust_zoom_scale,
)


from phase6_manufacturing_geometry import (
    _PHASE6_ASSEMBLY_PLACEMENTS,
    _phase6_door_part_assembly_placement,
    _phase6_assembly_placement_for_part,
    _phase6_relief_polygon_coords,
    _phase6_assembly_relief_clearance,
    _phase6_current_cabinet_family,
    _phase6_solution_is_committable,
    _phase6_apply_resolved_cut_to_part,
    _phase6_box_body_piece_solver_key,
    _phase6_manufacturing_state_signature,
    _phase6_joint_registry_diagnostic_info,
    _phase6_build_joint_world_geometry,
    _phase6_resolve_explicit_joint_reliefs,
    _phase6_resolve_family_divider_reliefs,
)

from phase6_manufacturing_adapter import (
    build_scene_payload_for_app,
    operator_finished_dimensions_for_app,
    read_standard_part_profiles as adapter_read_standard_part_profiles,
    resolve_for_app,
)


_phase6_resolve_manufacturing_geometry = resolve_for_app


@dataclass(frozen=True)
class Phase6DrawingEdgeHosts:
    top: object
    bottom: object
    left: object
    right: object
    center: object


@dataclass(frozen=True)
class Phase6PartDimensionProjection:
    part_key: str
    label: str
    formed_width: float
    formed_height: float
    blank_width: float
    blank_height: float


@dataclass(frozen=True)
class Phase6CornerDataUnfoldProjection:
    """Selected stable identity paired with already-authoritative unfold render data."""
    part_key: str
    render_data: object


def _phase6_box_body_piece_dimension_projections(render_data) -> tuple[Phase6PartDimensionProjection, ...]:
    """Project resolved physical Box Body pieces without recomputing any dimensions."""
    rows = []
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        key = f"box_body:{role}" if role else str(getattr(piece, "key", "") or "")
        formed_w, formed_h = tuple(float(v) for v in piece.formed_outer_dimensions)
        blank_w, blank_h = tuple(float(v) for v in piece.material_dimensions)
        rows.append(Phase6PartDimensionProjection(
            part_key=key,
            label=_phase6_part_label(key),
            formed_width=formed_w, formed_height=formed_h,
            blank_width=blank_w, blank_height=blank_h,
        ))
    return tuple(rows)


_phase6_is_box_body_physical_piece_key = _dm7_is_box_body_physical_piece_key


def _phase6_is_side_back_editable_piece_key(value) -> bool:
    """Only side/back-split physical children own editable piece Fold profiles."""
    return str(value or "") in {
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
    }


_phase6_operator_part_selector_keys = _dm7_operator_part_selector_keys


_phase6_box_body_piece_keys = _dm7_box_body_piece_keys


def _phase6_structure_tree_rows(values) -> tuple[tuple[str, str | None], ...]:
    """Compatibility adapter to the common DM7 hierarchy projection."""
    return tuple((row.part_key, row.parent_key) for row in _dm7_project_hierarchy(values))


def _phase6_reverse_fold_traversal(rows):
    """Reverse a fold chain while moving bend ownership to the same boundary."""
    source = clone_profile(tuple(rows or ()))
    result = []
    total = len(source)
    for index, source_row in enumerate(reversed(source)):
        row = {k: v for k, v in source_row.items() if k != "angle"}
        owner_index = total - 2 - index
        if owner_index >= 0 and "angle" in source[owner_index]:
            row["angle"] = float(source[owner_index]["angle"])
        result.append(row)
    if result:
        result[-1].pop("angle", None)
    return result


def _phase6_box_body_piece_part_profiles(
    render_data, snapshot=None
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Project manufacturing pieces into operator-facing physical-child profiles.

    Material lengths remain authoritative.  The adapter only changes traversal
    and signed operator presentation: Receiving right-side editing is front→rear
    while manufacturing keeps its local rear→front chain; Receiving zl1 may carry
    a negative operator direction without ever making material length negative.
    """
    source_snapshot = dict(snapshot or {})
    result = {}
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        if not role:
            continue
        key = f"box_body:{role}"
        rows = [
            {
                "len": float(row.length),
                **({"angle": float(row.angle)} if row.angle is not None else {}),
                **({"core": row.core} if getattr(row, "core", None) else {}),
                "phase6_key": str(getattr(row, "phase6_key", "") or ""),
            }
            for row in tuple(getattr(piece, "fold_profile", ()) or ())
        ]
        if role == "right_side":
            rows = _phase6_reverse_fold_traversal(rows)
        if role == "left_side" and float(source_snapshot.get("zl1", 0.0) or 0.0) < 0.0:
            for row in rows:
                if str(row.get("phase6_key") or "") == "zl1":
                    row["phase6_ui_sign"] = -1.0
                    break
        result[key] = {
            "X": rows,
            "Y": [{
                "len": float(piece.material_dimensions[1]),
                "phase6_key": "box_body_piece_height",
            }],
        }
    return result


def _phase6_box_body_structure_render_data(self):
    """Read the one authoritative aggregate BoxBody manufacturing result."""
    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        raise RuntimeError("3D final-scene provider is not connected")
    payload = _phase6_scene_query_payload_for_part(self, "box_body")
    render_data = callback("box_body", payload)
    if render_data is None:
        raise ValueError("manufacturing BoxBody render data unavailable")
    return render_data


def _phase6_box_body_piece_render_data(self, part_key):
    """Select one physical child from the resolved aggregate manufacturing result."""
    key = str(part_key or "")
    if not _phase6_is_box_body_physical_piece_key(key):
        raise ValueError(f"not a BoxBody physical piece: {key}")
    role = key.split(":", 1)[1]

    # A physical-piece editor is a sink, not a second BoxBody solve. Read the
    # same resolved aggregate consumed by assembly so single-part 2D/3D cannot
    # drift from assembly relief/corner results.
    resolved = _phase6_resolve_manufacturing_geometry(self)
    render_data = resolved.part("box_body").render_data
    piece = next(
        (item for item in tuple(getattr(render_data, "pieces", ()) or ())
         if str(getattr(item, "role", "") or "") == role),
        None,
    )
    if piece is None:
        raise ValueError(f"BoxBody physical piece is not present in current structure: {key}")
    return piece.render_data


PART_LABELS = {
    "box_body": "箱身",
    "head": "封頭",
    "tail": "封尾",
    "door": "門",
    "base_plate": "底板",
    "indicator_box": "指示燈盒",
    "indicator_door": "指示燈小門",
}
KNOWN_PARTS = tuple(PART_LABELS)


def normalize_part_selection(part_keys, active_part=None):
    """Preserve the Phase6 part order and choose a safe initial part.

    An empty model is the only case that invents a part: one box body.
    """
    seen = set()
    parts = []
    for raw in part_keys or ():
        key = str(raw or "").strip()
        if key and key not in seen:
            parts.append(key); seen.add(key)
    if not parts:
        parts = ["box_body"]
    active = str(active_part) if active_part in parts else parts[0]
    return parts, active




def _phase6_replace_mapping(self, attr_name, values):
    """Preserve one mutable mapping identity across legacy snapshot refreshes."""
    current = getattr(self, attr_name, None)
    if isinstance(current, MutableMapping):
        current.clear()
        current.update(dict(values or {}))
        return current
    replacement = dict(values or {})
    setattr(self, attr_name, replacement)
    return replacement


def _designer_workspace(self) -> Phase6DesignerWorkspace:
    return self.designer_workspace


def _phase6_workspace_navigation(self):
    return _phase6_composition(self).workspace_navigation()

def _phase6_composition(self) -> Phase6FoldDesignerComposition:
    composition = getattr(self, "_phase6_composition_owner", None)
    if composition is None:
        composition = Phase6FoldDesignerComposition(self)
        self._phase6_composition_owner = composition
    return composition


def _phase6_settings_service(self):
    return _phase6_composition(self).settings_service()

def _phase6_settings_transactions(self):
    return _phase6_composition(self).settings_transactions()


def _phase6_settings_application_apply_profile_plan(
    self,
    committed,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
    editor_commit=False,
    editor_changed_keys=(),
):
    committed = dict(committed or {})
    if bool(editor_commit):
        _phase6_recalculate_part_dimensions(self)
        changed_keys = set(editor_changed_keys or ())
        if {"w", "h", "d", "t", "fw"}.intersection(changed_keys):
            _phase6_refresh_linked_part_profiles(self, changed_keys)
        return committed
    if "t" in committed:
        self.state.phase6_thickness = float(committed["t"])
    self._phase6_settings_guard = True
    try:
        return _phase6_refresh_profiles_from_settings(
            self,
            reset_box_profile=bool(reset_box_profile),
            reset_all_profiles=bool(reset_all_profiles),
            render=bool(render),
        )
    finally:
        self._phase6_settings_guard = False

def _phase6_settings_application_project_ui_values(
    self,
    values,
    *,
    rejected_key=None,
    error=None,
    baseline_transition=None,
    baseline_stage=None,
    new_model="",
    old_model="",
    new_editable=False,
    old_editable=False,
    factory_reset=False,
    editor_commit=False,
    editor_snapshot=None,
):
    values = dict(values or {})
    plan = baseline_transition
    if bool(editor_commit) and editor_snapshot is not None:
        self._phase6_input_snapshot.update(dict(editor_snapshot or {}))

    if rejected_key == "w":
        if error is not None:
            _phase6_box_structure_error(self, ValueError(str(error)))
        self._phase6_settings_guard = True
        try:
            previous_w = values.get("w")
            if previous_w is not None and hasattr(self, "v_w"):
                self.v_w.set(_setting_number_text(previous_w))
            var = getattr(self, "left_global_vars", {}).get("w")
            if previous_w is not None and var is not None:
                var.set(_setting_number_text(previous_w))
        finally:
            self._phase6_settings_guard = False
        return

    if baseline_stage == "commit" and plan is not None:
        remembered = getattr(plan, "remember_non_receiving_structure", None)
        if remembered is not None:
            self._phase6_non_receiving_structure_state = deepcopy(remembered)

        if "fw" in values:
            state = getattr(self, "_phase6_endcap_fw_state", None)
            if isinstance(state, MutableMapping):
                commit_box_fw(state, float(values["fw"]))
                self._phase6_input_snapshot["endcap_fw"] = deepcopy(state)

        defaults = dict(getattr(plan, "defaults", {}) or {})
        if defaults:
            for key, attr in (("w", "w"), ("h", "h"), ("d", "d")):
                if key in defaults:
                    setattr(self.state, attr, original.get_int(defaults[key]))
            self.v_w.set(str(self.state.w))
            self.v_h.set(str(self.state.h))
            self.v_d.set(str(self.state.d))
            self._phase6_last_w = self.state.w
            self._phase6_last_d = self.state.d

        assembly_var = getattr(self, "assembly_type_var", None)
        if assembly_var is not None:
            assembly_var.set(ASSEMBLY_TYPE_LABELS[plan.assembly_type])

    if "ui_text_size" in values:
        key = values["ui_text_size"]
        if hasattr(self, "_ui_text_controller"):
            self._ui_text_controller.apply(key)
        self.state.ui_text_scale = (
            getattr(self, "_ui_text_controller", None).factor
            if hasattr(self, "_ui_text_controller")
            else 1.0
        )
        var = getattr(self, "ui_text_size_var", None)
        if var is not None and var.get() != ui_text_size_label(key):
            var.set(ui_text_size_label(key))

    self._phase6_settings_guard = True
    try:
        if "w" in values:
            self.v_w.set(_setting_number_text(values["w"]))
        if "h" in values:
            self.v_h.set(_setting_number_text(values["h"]))
        if "d" in values:
            self.v_d.set(_setting_number_text(values["d"]))
        for key, var in getattr(self, "left_global_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(ui_text_size_label(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(_setting_number_text(values[key]))
        for key, var in getattr(self, "setting_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(ui_text_size_label(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(_setting_number_text(values[key]))
    finally:
        self._phase6_settings_guard = False

    if baseline_stage == "state":
        if bool(new_editable) and str(old_model or "") and not bool(old_editable):
            self._corner_transaction_unknown_state = deepcopy(
                self._phase6_corner_state
            )
            self._corner_transaction_unknown_pairs = deepcopy(
                self._phase6_corner_pair_same
            )
        self._corner_editable = bool(new_editable)
        self._phase6_baseline_last_model = str(new_model or "")
        _phase6_apply_box_symmetry_policy(self)
        bend_ui = getattr(self, "bend_ui", None)
        refresh_symmetry = getattr(bend_ui, "_phase6_refresh_symmetry_bar", None)
        if callable(refresh_symmetry):
            refresh_symmetry()

    if baseline_stage == "finalize":
        _phase6_invalidate_corner_pages(self)
        if (
            hasattr(self, "settings_center")
            and getattr(self, "active_part_key", None) is not None
        ):
            _phase6_render_settings_context(
                self,
                getattr(self, "settings_context", self.active_part_key),
            )
        corner_data_panel = getattr(self, "corner_data_panel", None)
        if (
            str(getattr(self, "_phase6_3d_display_mode", "") or "")
            == "corner_data"
            and corner_data_panel is not None
            and corner_data_panel.winfo_manager()
        ):
            _phase6_refresh_corner_data_parts_panel(self)
            if getattr(self, "corner_data_canvas", None) is not None:
                _phase6_refresh_corner_data_unfold_view(self)

def _phase6_settings_application_submit_update_intent(self, committed):
    payload = dict(committed or {}) if isinstance(committed, Mapping) else {}
    if payload.get("reason") == "baseline":
        submit = getattr(self, "submit_update_intent", None)
        if callable(submit):
            return submit("baseline", commit=True)
        return _phase6_publish_live_state(self, force=bool(payload.get("force", True)))

    legacy_job = getattr(self, "_job", None)
    if legacy_job is not None:
        try:
            self.root.after_cancel(legacy_job)
        except Exception:
            pass
        self._job = None
    try:
        return self.do_update()
    except Exception:
        return None

def _phase6_settings_application_publish_live_state(self, committed, *, partial=False):
    if (
        not getattr(self, "_phase6_transactional_mode", False)
        and self._settings_change_callback is not None
    ):
        payload = dict(committed or {}) if bool(partial) else dict(self._settings_values)
        if payload:
            self._settings_change_callback(payload)


def _phase6_settings_coordinator(self):
    composition = _phase6_composition(self)
    return composition.settings_coordinator(
        composition.settings_application_ports(globals())
    )

def _phase6_registry_diagnostics(self):
    return _phase6_composition(self).registry_diagnostics()

def _phase6_sync_registry_diagnostics_compatibility_mirrors(
    self, controller=None
):
    """Mirror controller-owned registry state for legacy readers/tests only."""
    controller = controller or _phase6_registry_diagnostics(self)
    self._phase6_registry_candidate_id = controller.candidate_id
    self._phase6_registry_candidate_record = controller.candidate_record
    self._phase6_registry_regression_evidence = controller.regression_evidence
    self._phase6_registry_rule_records = controller.rule_records
    self._phase6_last_relief_promotion_candidates = (
        controller.promotion_candidates
    )
    return controller

def _phase6_registry_load_rule_rows(self):
    """Load Registry rows through the existing controller; no Tk ownership here."""
    from ae_engine.certified_relief_registry import load_external_relief_rule_records

    controller = _phase6_registry_diagnostics(self)
    rows = controller.load_rule_records(loader=load_external_relief_rule_records)
    _phase6_sync_registry_diagnostics_compatibility_mirrors(self, controller)
    return rows


def _phase6_registry_preview_payload(self):
    """Return validated 2D preview data; drawing is owned by the panel."""
    result = _phase6_registry_validate_formula_form(self)
    geometry = _phase6_corner_data_view(self).registry_preview_geometry(result)
    return {"result": result, "geometry": geometry}


def _phase6_registry_panel(self):
    return _phase6_composition(self).registry_panel(globals())

def _phase6_corner_data_view(self):
    return _phase6_composition(self).corner_data_view()

def _phase6_sync_corner_data_view_compatibility_mirrors(
    self, adapter=None
):
    """Mirror adapter-owned selection for legacy readers/tests only."""
    adapter = adapter or _phase6_corner_data_view(self)
    self._phase6_corner_data_selected_part_key = adapter.selected_part_key
    return adapter


def _phase6_final_scene_adapter(self):
    composition = _phase6_composition(self)
    return composition.final_scene_adapter(
        composition.final_scene_ports(globals())
    )

def _phase6_sync_authoritative_derived_parts(self):
    """Plan derived physical-part topology first, then apply workspace mutations."""
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    workspace = _designer_workspace(self)
    navigation = _phase6_workspace_navigation(self)
    if not navigation.supports_derived_sync:
        return (), ()

    # ---- Pure input/projection phase: no workspace/navigation mutation below ----
    door_rows = _phase6_door_part_projections(snapshot)
    source_part_features = dict(snapshot.get("part_features") or {})
    known_feature_keys = set(workspace.part_features_snapshot())
    source_parts = tuple(snapshot.get("existing_parts") or ())
    available_parts = tuple(workspace.available_parts)

    door_profiles = {}
    for row in door_rows:
        local = dict(snapshot)
        local_dims = {
            key: dict(value)
            for key, value in dict(snapshot.get("part_dimensions") or {}).items()
        }
        local_dims[row.part_key] = {
            "width": row.formed_width,
            "height": row.formed_height,
        }
        local["part_dimensions"] = local_dims
        door_profiles[row.part_key] = build_standard_part_profiles(local, row.part_key)

    base_plate_profiles = {}
    if door_rows:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        shrink_left = _num(snapshot.get("base_plate_shrink_left", 55), 55)
        shrink_right = _num(snapshot.get("base_plate_shrink_right", 55), 55)
        shrink_top = _num(snapshot.get("base_plate_shrink_top", 55), 55)
        shrink_bottom = _num(snapshot.get("base_plate_shrink_bottom", 55), 55)
        for cell in derive_door_layout_cells(columns):
            base_key = door_layout_part_key(cell).replace("door_", "base_plate_", 1)
            local = dict(snapshot)
            local_dims = {
                key: dict(value)
                for key, value in dict(snapshot.get("part_dimensions") or {}).items()
            }
            local_dims[base_key] = {
                "width": max(
                    1.0,
                    float(cell.start_width) - shrink_left - shrink_right,
                ),
                "height": max(
                    1.0,
                    float(cell.start_height) - shrink_top - shrink_bottom,
                ),
            }
            local["part_dimensions"] = local_dims
            base_plate_profiles[base_key] = build_standard_part_profiles(
                local, base_key
            )

    try:
        box_render_data = _phase6_box_body_structure_render_data(self)
    except Exception:
        box_render_data = None
    box_piece_profiles = (
        _phase6_box_body_piece_part_profiles(box_render_data, snapshot)
        if box_render_data is not None
        else {}
    )
    desired_piece_keys = set(box_piece_profiles)
    current_piece_keys = {
        key
        for key in available_parts
        if _phase6_is_box_body_physical_piece_key(key)
    }

    divider_profiles = {}
    columns = list(snapshot.get("door_layout_columns") or ())
    if bool(snapshot.get("multi_door_enabled", False)) and columns:
        from ae_engine.door_dividers import (
            derive_box_body_dividers,
            divider_part_profiles,
        )

        normalized_columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in columns
        )
        dividers = derive_box_body_dividers(
            normalized_columns,
            depth=float(snapshot.get("d", 0.0)),
            thickness=float(snapshot.get("t", 0.0)),
            layout_scope=(
                str(snapshot.get("door_layout_scope") or "main").strip()
                or "main"
            ),
            handle_edges=dict(snapshot.get("door_handle_edges") or {}),
            model_name=str(snapshot.get("model") or "").strip() or None,
            frame_width=float(snapshot.get("fw", 0.0)),
        )
        divider_profiles = divider_part_profiles(dividers)

    from ae_engine.inner_door_frames import (
        InnerDoorFrameSet,
        derive_all_inner_door_frames,
        inner_door_frame_part_profiles,
    )
    from ae_engine.inner_door_panels import inner_door_panel_part_profiles

    frame_sets = []
    thickness = float(snapshot.get("t", 0.0))
    if cabinet_family_policy.has_inner_door_frame_derivation(snapshot):
        frame_sets.extend(
            cabinet_family_policy.derive_inner_door_frame_sets(snapshot)
        )
    else:
        for item in list(snapshot.get("inner_doors") or ()):
            if not isinstance(item, Mapping):
                continue
            spans = item.get("frame_spans")
            if not isinstance(spans, Mapping) or not spans:
                continue
            stable_id = str(item.get("stable_id") or "").strip()
            if not stable_id:
                continue
            included = tuple(
                str(side).strip().lower()
                for side in (
                    item.get("included_frame_sides")
                    or ("top", "bottom", "left", "right")
                )
            )
            frame_sets.append(
                InnerDoorFrameSet(
                    inner_door_id=stable_id,
                    spans=dict(spans),
                    thickness=thickness,
                    included_sides=included,
                )
            )
    frames = derive_all_inner_door_frames(tuple(frame_sets))
    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)
    inner_profiles = inner_door_frame_part_profiles(frames)
    inner_profiles.update(inner_door_panel_part_profiles(panels))

    single_door_profiles = (
        build_standard_part_profiles(snapshot, "door")
        if not door_rows and "door" in source_parts and "door" not in available_parts
        else None
    )
    single_base_plate_profiles = (
        build_standard_part_profiles(snapshot, "base_plate")
        if (
            not door_rows
            and "base_plate" in source_parts
            and "base_plate" not in available_parts
        )
        else None
    )
    request = build_derived_part_projection_request(
        DerivedPartRequestAssemblyInput(
            door_part_keys=tuple(row.part_key for row in door_rows),
            door_profiles=door_profiles,
            base_plate_profiles=base_plate_profiles,
            divider_profiles=divider_profiles,
            inner_profiles=inner_profiles,
            box_piece_profiles=box_piece_profiles,
            current_piece_keys=tuple(current_piece_keys),
            source_parts=source_parts,
            available_parts=available_parts,
            source_part_features=source_part_features,
            known_feature_keys=tuple(known_feature_keys),
            single_door_profiles=single_door_profiles,
            single_base_plate_profiles=single_base_plate_profiles,
            active_part=workspace.active_part,
            selected_part=workspace.selected_part,
        )
    )
    plan = build_derived_part_sync_plan(request)

    # Workspace/navigation remains the unique mutation owner.
    navigation.apply_derived_sync_plan(plan)

    return (
        tuple(divider_profiles),
        tuple(
            [
                *(frame.stable_id for frame in frames),
                *(panel.stable_id for panel in panels),
            ]
        ),
    )

def _legacy_available_parts_get(self):
    return list(_designer_workspace(self).available_parts)

def _legacy_available_parts_set(self, values):
    _designer_workspace(self).replace_available_parts(values)


def _legacy_active_part_get(self):
    return _designer_workspace(self).active_part

def _legacy_active_part_set(self, value):
    _designer_workspace(self).active_part = value


def _legacy_selected_part_get(self):
    return _designer_workspace(self).selected_part

def _legacy_selected_part_set(self, value):
    _designer_workspace(self).selected_part = value


def _legacy_part_profiles_get(self):
    return _designer_workspace(self).part_profiles_snapshot()

def _legacy_part_profiles_set(self, value):
    _designer_workspace(self).replace_part_profiles(value)


def _legacy_part_features_get(self):
    return _designer_workspace(self).part_features_snapshot()

def _legacy_part_features_set(self, value):
    _designer_workspace(self).replace_part_features(value)


def _legacy_part_face_features_get(self):
    return _designer_workspace(self).part_face_features_snapshot()

def _legacy_part_face_features_set(self, value):
    _designer_workspace(self).replace_part_face_features(value)


def _legacy_workspace_dirty_get(self):
    return _designer_workspace(self).dirty

def _legacy_workspace_dirty_set(self, value):
    _designer_workspace(self).dirty = value


def _legacy_switching_part_get(self):
    return _designer_workspace(self).switching

def _legacy_switching_part_set(self, value):
    _designer_workspace(self).switching = value


def _legacy_box_body_active_piece_get(self):
    return _phase6_workspace_navigation(self).remembered_box_body_child


def _legacy_box_body_active_piece_set(self, value):
    _phase6_workspace_navigation(self).remembered_box_body_child = value


def _legacy_settings_assembly_type_get(self):
    return _phase6_composition(self).assembly_type

def _legacy_settings_last_external_revision_get(self):
    return _phase6_composition(self).last_external_revision

def _legacy_settings_last_external_transaction_id_get(self):
    return _phase6_composition(self).last_external_transaction_id

def _legacy_settings_active_transaction_id_get(self):
    return _phase6_composition(self).active_transaction_id

def _phase6_legacy_getattr(self, name):
    readers = {
        "_phase6_assembly_type": _legacy_settings_assembly_type_get,
        "_phase6_last_external_revision": _legacy_settings_last_external_revision_get,
        "_phase6_last_external_transaction_id": _legacy_settings_last_external_transaction_id_get,
        "_phase6_active_transaction_id": _legacy_settings_active_transaction_id_get,
    }
    reader = readers.get(str(name))
    if reader is not None:
        return reader(self)
    raise AttributeError(str(name))


def project_features_to_original_holes(features, width, height):
    """Project supported Phase6 features into the original Renderer's hole DTO.

    Raw Phase6 feature objects are never edited. Profile/custom holes stay in the
    bundle but are intentionally not falsified as circles/rectangles for preview.
    """
    from ae_engine.sheetmetal_features import CircleFeature, RectFeature, feature_finished_point

    holes = []
    for index, feature in enumerate(features or (), start=1):
        if not isinstance(feature, (CircleFeature, RectFeature)):
            continue
        center = feature_finished_point(feature, float(width), float(height))
        if isinstance(feature, CircleFeature):
            hole = {
                "type": "圓孔", "name": f"孔{len(holes)+1}",
                "x": _ui_len(center.x), "y": _ui_len(center.y),
                "d1": _ui_len(feature.diameter), "d2": 0,
            }
        else:
            hole = {
                "type": "方孔", "name": f"孔{len(holes)+1}",
                "x": _ui_len(center.x), "y": _ui_len(center.y),
                "d1": _ui_len(feature.width), "d2": _ui_len(feature.height),
            }
        holes.append(hole)
    return holes



def _phase6_rebuild_linked_endcaps(self):
    """Rebuild only existing head/tail derived profiles from current box topology."""
    box_profile = self.state.profiles_vault.get("箱身", [])
    snapshot = dict(self._phase6_input_snapshot)
    snapshot.update(getattr(self, "_settings_values", {}) or {})
    snapshot["corner_state"] = deepcopy(getattr(self, "_phase6_corner_state", {}) or {})
    snapshot["corner_pair_same"] = deepcopy(getattr(self, "_phase6_corner_pair_same", {}) or {})
    snapshot["assembly_type"] = assembly_intent_value(getattr(
        self, "_phase6_assembly_type", resolve_box_assembly_type(snapshot)
    ))
    snapshot["endcap_fw"] = deepcopy(getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(snapshot)))
    linked = build_linked_endcap_xy_profiles(snapshot, box_profile)
    for key in ("head", "tail"):
        if key in self.designer_workspace.available_parts:
            self.designer_workspace.stash_profiles(key, linked[key])

    # If Head/Tail is the live editor, replace that live cache in the same
    # transaction.  Otherwise OVERLAY can correctly update Workspace while the
    # active editor/Single3D keeps stale yl1/core/yr1 X folds until a part switch.
    active = str(getattr(getattr(self, "designer_workspace", None), "active_part", "") or "")
    if active in linked:
        fresh = linked[active]
        self.state.profiles["X"] = clone_profile(fresh.get("X", ()))
        self.state.profiles["Y"] = clone_profile(fresh.get("Y", ()))
        tabs = _phase6_fold_tabs_for_part(snapshot, active)
        self.state.phase6_fold_ui_tabs = list(tabs) if tabs is not None else None
        self.state.active_bend = self.state.phase6_fold_ui_tabs[0] if self.state.phase6_fold_ui_tabs else "X"
        if hasattr(self.state, "enable_x"):
            self.state.enable_x = bool(self.state.profiles["X"])
        self.state.enable_y = bool(self.state.profiles["Y"])
        for attr, enabled in (("v_ex", bool(self.state.profiles["X"])), ("v_ey", self.state.enable_y)):
            var = getattr(self, attr, None)
            if var is not None:
                try:
                    if bool(var.get()) != bool(enabled):
                        var.set(bool(enabled))
                except Exception:
                    pass
        bend_ui = getattr(self, "bend_ui", None)
        root = getattr(self, "root", None)
        if bend_ui is not None:
            scheduled_part = active

            def refresh_live_tabs():
                # This callback may outlive an outgoing EndCap save during a
                # part switch. Never rebuild the new part's editor from stale
                # Head/Tail state; that also prevents a second queued redraw.
                current_part = str(
                    getattr(getattr(self, "designer_workspace", None), "active_part", "") or ""
                )
                if current_part != scheduled_part:
                    return
                try:
                    bend_ui.rebuild_tabs()
                except Exception:
                    pass
            if root is not None and hasattr(root, "after_idle"):
                root.after_idle(refresh_live_tabs)
            else:
                refresh_live_tabs()
    return linked


from phase6_bending_ui import (
    Phase6BendingUI,
    resolve_profile_key as _phase6_resolve_profile_key,
    _phase6_box_symmetry_allowed,
    _phase6_apply_box_symmetry_policy,
)

# ---------------------------------------------------------------------------
# Thin Tk bridge: input grid stays the user's original implementation.
# Only metadata preservation / D-W-D row locking are added here.
# ---------------------------------------------------------------------------
import fold_designer_original as original

def _phase6_snapshot_with_settings_fallback(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Materialize legacy nested global dimensions once at the snapshot ingress.

    Explicit top-level W/H/D/T/FW are authoritative. Nested settings is only
    a backward-compatible fallback when the corresponding top-level field is
    absent, so this adaptation cannot create a competing live settings owner.
    """
    normalized = dict(snapshot or {})
    settings = normalized.get("settings")
    if isinstance(settings, Mapping):
        for key in ("w", "h", "d", "t", "fw"):
            if key not in normalized and key in settings:
                normalized[key] = settings[key]
    return normalized


class Phase6FoldDesignerApp(original.MainApp):
    """Original MainApp loaded with Phase6 data; Renderer is untouched."""

    _PHASE6_STABLE_MAPPING_NAMES = frozenset({
        "_settings_values",
        "_phase6_input_snapshot",
        "_phase6_box_whd",
        "_phase6_pending_settings",
    })

    def __setattr__(self, name, value):
        if name in self._PHASE6_STABLE_MAPPING_NAMES:
            current = self.__dict__.get(name)
            if isinstance(current, MutableMapping):
                if value is current:
                    return
                current.clear()
                current.update(dict(value or {}))
                return
        super().__setattr__(name, value)

    def __init__(self, root, snapshot: Mapping[str, object]):
        _phase6_replace_mapping(self, "_phase6_input_snapshot", dict(snapshot))
        self._phase6_sync_ready = False
        self._phase6_last_w = None
        self._phase6_last_d = None
        self._phase6_destroying = False
        # BendingUI is constructed inside predecessor MainApp.__init__; install the
        # bridge-owned transaction action on this instance before that constructor runs.
        # This preserves the 3-argument BendingUI constructor without facade growth.
        self._phase6_on_box_symmetry_changed = lambda: _phase6_on_box_symmetry_changed(self)
        saved_bending_ui = original.BendingUI
        original.BendingUI = Phase6BendingUI
        try:
            super().__init__(root)
        finally:
            original.BendingUI = saved_bending_ui
        # Tk ``after`` jobs belong to the Tcl interpreter, not to the Toplevel
        # that scheduled them.  Destroying the designer therefore does not
        # automatically clear Python-side job ownership.  Bind cleanup to the
        # designer root itself so direct ``Toplevel.destroy()`` callers and the
        # normal GUI close path share the same teardown invariant.
        self.root.bind("<Destroy>", self._phase6_on_root_destroy, add="+")
        self.load_phase6_snapshot(snapshot)

    def _phase6_cancel_owned_tk_jobs(self):
        for attr in ("_job", "_phase6_settings_debounce_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
            setattr(self, attr, None)

        service = getattr(self, "_phase6_settings_transaction_service", None)
        if service is not None:
            settings_job = service.debounce_job
            if settings_job is not None:
                try:
                    self.root.after_cancel(settings_job)
                except Exception:
                    pass
            service.clear_debounce_job()
            service.clear_pending()

        cancel_fold_designer_update_intents(self)

        if hasattr(self, "_phase6_pending_settings"):
            _phase6_replace_mapping(self, "_phase6_pending_settings", {})

    def _phase6_on_root_destroy(self, event):
        if getattr(event, "widget", None) is not self.root:
            return
        self._phase6_destroying = True
        self._phase6_cancel_owned_tk_jobs()

    def load_phase6_snapshot(self, snapshot: Mapping[str, object]):
        snapshot = _phase6_snapshot_with_settings_fallback(snapshot)
        _phase6_replace_mapping(self, "_phase6_input_snapshot", dict(snapshot))
        stored = snapshot.get("box_body_profile")
        if stored:
            self.state.profiles_vault["箱身"] = merge_box_body_profile(stored, snapshot)
        else:
            self.state.profiles_vault["箱身"] = build_box_body_profile(snapshot)
        endcap = build_endcap_profile(snapshot)
        self.state.profiles_vault["封頭"] = clone_profile(endcap)
        self.state.profiles_vault["封尾"] = clone_profile(endcap)
        self.state.w = original.get_int(snapshot.get("w", self.state.w))
        self.state.h = original.get_int(snapshot.get("h", self.state.h))
        self.state.d = original.get_int(snapshot.get("d", self.state.d))
        self.v_w.set(str(self.state.w))
        self.v_h.set(str(self.state.h))
        self.v_d.set(str(self.state.d))
        self.state.struct_mode = "vault"
        self.v_mode.set("vault")
        _phase6_apply_box_symmetry_policy(self)
        self.bend_ui.rebuild_tabs()
        self._phase6_last_w = self.state.w
        self._phase6_last_d = self.state.d
        self._phase6_sync_ready = True
        self.do_update()

    def _sync_dwd_with_top_whd(self):
        profile = self.state.profiles_vault.get("箱身", [])
        w_segments = [seg for seg in profile if seg.get("core") == "W"]
        d_segments = [seg for seg in profile if seg.get("core") == "D"]
        if len(w_segments) != 1 or len(d_segments) != 2:
            return

        top_w = original.get_int(self.v_w.get())
        top_d = original.get_int(self.v_d.get())
        core_w = original.get_int(engine_segment_length_to_ui(w_segments[0]))
        d_values = [original.get_int(engine_segment_length_to_ui(seg)) for seg in d_segments]

        last_w = self._phase6_last_w
        last_d = self._phase6_last_d
        if top_w != last_w:
            w_segments[0]["len"] = ui_segment_length_to_engine(w_segments[0], top_w)
            core_w = top_w
        elif core_w != last_w:
            self.v_w.set(str(core_w))
            top_w = core_w

        if top_d != last_d:
            for seg in d_segments:
                seg["len"] = ui_segment_length_to_engine(seg, top_d)
            d_value = top_d
        else:
            changed = [value for value in d_values if value != last_d]
            d_value = changed[0] if changed else d_values[0]
            for seg in d_segments:
                seg["len"] = ui_segment_length_to_engine(seg, d_value)
            if d_value != top_d:
                self.v_d.set(str(d_value))

        self._phase6_last_w = top_w
        self._phase6_last_d = d_value

    def do_update(self):
        _phase6_apply_box_symmetry_policy(self)
        if getattr(self, "_phase6_sync_ready", False):
            self._sync_dwd_with_top_whd()
        return original.MainApp.do_update(self)

    def export_phase6_snapshot(self) -> dict:
        self.bend_ui.save()
        result = dict(self._phase6_input_snapshot)
        result.update(read_box_body_profile(self.state.profiles_vault["箱身"], self._phase6_input_snapshot))
        head = read_endcap_profile(self.state.profiles_vault["封頭"])
        tail = read_endcap_profile(self.state.profiles_vault["封尾"])
        if head != tail:
            raise ValueError("Phase6 目前封頭/封尾共用同一組折彎值，兩個分頁必須一致")
        result.update(head)
        result["h"] = original.get_int(self.v_h.get())
        result["box_body_profile"] = clone_profile(self.state.profiles_vault["箱身"])
        result["head_profile"] = clone_profile(self.state.profiles_vault["封頭"])
        result["tail_profile"] = clone_profile(self.state.profiles_vault["封尾"])
        if hasattr(self, "designer_workspace"):
            result["box_body_structure"] = self.designer_workspace.box_body_structure_state()
        return result

# ---------------------------------------------------------------------------
# FIX11 multi-part bundle helpers. These adapt data only; original Renderer is
# deliberately untouched.
# ---------------------------------------------------------------------------

def read_standard_part_profiles(part_key, profiles, original_snapshot):
    """Compatibility wrapper for adapter-owned standard profile reverse mapping."""
    return adapter_read_standard_part_profiles(part_key, profiles, original_snapshot)
def _part_preview_size(snapshot, key):
    dims = dict((snapshot.get("part_dimensions") or {}).get(key, {}) or {})
    return (
        _num(dims.get("width", snapshot.get("w", 500)), 500),
        _num(dims.get("height", snapshot.get("h", 600)), 600),
    )


def _copy_features(snapshot, key):
    return list((snapshot.get("part_features") or {}).get(key, ()) or ())





def _hide_original_global_dimension_controls(root_widget):
    """Hide the prototype W/H/D structure block; Phase6 settings center owns it."""
    for child in root_widget.winfo_children():
        try:
            text = str(child.cget("text"))
        except Exception:
            text = ""
        if "結構模式與空間約束" in text:
            manager = child.winfo_manager()
            if manager == "pack":
                child.pack_forget()
            elif manager == "grid":
                child.grid_remove()
            return True
    return False


def _phase6_recalculate_part_dimensions(self):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    dims = project_part_dimensions(snapshot)
    self._phase6_input_snapshot.update(
        dict(getattr(self, "_settings_values", {}) or {})
    )
    self._phase6_input_snapshot.update({"part_dimensions": deepcopy(dims)})
    return deepcopy(dims)


def _phase6_apply_settings_profile_projection(self, plan, *, render=True):
    snapshot = materialize_settings_profile_value(plan.snapshot)
    self._phase6_input_snapshot.update(snapshot)

    box_profile = materialize_settings_profile_value(plan.box_body_profile)
    self.state.profiles_vault["箱身"] = box_profile

    if plan.derived_sync_required:
        _phase6_sync_authoritative_derived_parts(self)
    _phase6_refresh_assembly_parts_panel_if_topology_changed(self)

    navigation = _phase6_workspace_navigation(self)
    planned_profiles = materialize_settings_profile_value(plan.part_profiles)
    for key, profiles in planned_profiles.items():
        navigation.stash_profiles(key, profiles)

    active = str(plan.active_part or self.designer_workspace.active_part or "box_body")
    if active == "box_body":
        self.state.phase6_fold_ui_profiles = {
            "X": self.state.profiles_vault["箱身"]
        }
    elif active in self.designer_workspace.available_parts:
        active_profiles = materialize_settings_profile_value(plan.active_profiles)
        profiles = active_profiles or (
            self.designer_workspace.profiles_for(active, {}) or {}
        )
        self.state.profiles["X"] = clone_profile(profiles.get("X", []))
        self.state.profiles["Y"] = clone_profile(profiles.get("Y", []))

    if render:
        try:
            self.bend_ui.render()
        except Exception:
            pass
    return plan

def _phase6_refresh_profiles_from_settings(
    self,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
):
    """Build a pure Settings-to-Profile plan, then apply it through existing owners."""
    workspace = self.designer_workspace
    request = SettingsProfileProjectionRequest(
        settings_values=getattr(self, "_settings_values", {}),
        input_snapshot=getattr(self, "_phase6_input_snapshot", {}),
        available_parts=tuple(workspace.available_parts),
        existing_profiles=workspace.part_profiles_snapshot(),
        box_body_profile=self.state.profiles_vault.get("箱身", []),
        active_part=workspace.active_part or "box_body",
        reset_box_profile=bool(reset_box_profile),
        reset_all_profiles=bool(reset_all_profiles),
    )
    plan = build_settings_profile_projection(request)
    return _phase6_apply_settings_profile_projection(
        self,
        plan,
        render=bool(render),
    )

def _phase6_apply_setting_updates(self, updates, *, notify=True):
    return _phase6_settings_coordinator(self).apply_updates(
        updates,
        notify=bool(notify),
        external_apply_guard=bool(
            getattr(self, "_phase6_external_apply_guard", False)
        ),
    )

def _phase6_flush_pending_settings(self):
    service = _phase6_settings_service(self)
    plan = service.drain_pending()
    if plan.cancel_job is not None:
        try:
            self.root.after_cancel(plan.cancel_job)
        except Exception:
            pass
    if not plan.pending:
        return {}
    return _phase6_apply_setting_updates(self, plan.pending, notify=True)

def _phase6_stage_setting_update(self, key, value):
    service = _phase6_settings_service(self)
    plan = service.stage_setting_update(
        key,
        value,
        destroying=bool(getattr(self, "_phase6_destroying", False)),
    )
    if not plan.changed:
        return
    if plan.cancel_job is not None:
        try:
            self.root.after_cancel(plan.cancel_job)
        except Exception:
            pass
    job = self.root.after(plan.schedule_after_ms, self.flush_pending_settings)
    service.install_debounce_job(job)




_CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
_CORNER_PAIR_KEYS = {"top": ("top_left", "top_right"), "bottom": ("bottom_left", "bottom_right")}
_CORNER_TYPE_IDS = tuple(item.value for item in EDITABLE_CORNER_TYPE_IDS)
_CORNER_TYPE_LABEL_BY_ID = {item.value: CORNER_TYPE_LABELS[item] for item in EDITABLE_CORNER_TYPE_IDS}
_CORNER_TYPE_BY_LABEL = {label: type_id for type_id, label in _CORNER_TYPE_LABEL_BY_ID.items()}
_CORNER_MODE_LABEL = {
    CrossCornerMode.STANDARD: "標準",
    CrossCornerMode.RETAIN: "單邊留肉",
    CrossCornerMode.EXTRA_CUT: "多切",
}
_CORNER_MODE_BY_LABEL = {value: key for key, value in _CORNER_MODE_LABEL.items()}
_CORNER_DIRECTION_LABEL = {
    CornerDirection.WIDTH: "寬",
    CornerDirection.HEIGHT: "高",
    CornerDirection.BOTH: "寬＋高",
}
_CORNER_DIRECTION_BY_LABEL = {value: key for key, value in _CORNER_DIRECTION_LABEL.items()}

# 只供畫面顯示的固定製造 policy 摘要；真正幾何仍以引擎 policy 為準。
_FIXED_CORNER_SUMMARIES = {
    "door": "十字截角｜單邊留肉 1T",
    "base_plate": "十字截角｜標準",
    "indicator_box": "十字截角｜單邊留肉 1T（固定）",
    "indicator_door": "十字截角｜單邊留肉 1T（固定）",
    "head": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）｜下方：十字截角 多切 0.5T（寬＋高）",
    "tail": "上方：嵌入貼外型（貼外留肉 1T／嵌入留肉 0.5T／深度 2T）｜下方：十字截角 多切 0.5T（寬＋高）",
}





def _phase6_ensure_corner_part(self, part_key):
    return _phase6_settings_transactions(self).ensure_corner_part(part_key)

def _phase6_notify_corner_change(self):
    """Corner edits are production edits: publish them to canonical state now."""
    if _phase6_is_unknown_baseline(self, getattr(self, "baseline_model_var", None).get() if getattr(self, "baseline_model_var", None) is not None else ""):
        self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
        self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)
    _phase6_publish_live_state(self)


def _phase6_corner_type_editable(self, part_key):
    return bool(getattr(self, "_corner_editable", False)) and part_key not in {"indicator_box", "indicator_door"}


def _phase6_corner_parameters_unlockable(self, part_key):
    return part_key not in {GLOBAL_CONTEXT, "box_body", "indicator_box", "indicator_door"}


def _phase6_corner_parameters_unlocked(self, part_key):
    # 3D 右上只有一個參數鎖。解鎖後目前板件的結構／進階／截角細部
    # 一次展開；不再維護每個板件各自一顆細部參數鎖。
    return bool(getattr(self, "_phase6_parameters_unlocked", False))


def _phase6_corner_parameters_editable(self, part_key):
    return _phase6_corner_parameters_unlockable(self, part_key) and _phase6_corner_parameters_unlocked(self, part_key)


def _phase6_corner_parameter_summary(selection):
    selection = normalize_corner_selection(selection)
    if selection.type_id is CornerTypeId.CROSS:
        mode = _CORNER_MODE_LABEL[selection.cross_mode]
        if selection.cross_mode is CrossCornerMode.STANDARD:
            return mode
        direction = _CORNER_DIRECTION_LABEL[selection.direction]
        return f"{mode}｜{direction}｜{_setting_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.OVERLAY:
        return f"留肉（高）｜{_setting_number_text(selection.amount_t)}T"
    if selection.type_id is CornerTypeId.INSERT:
        return f"多切（高）｜{_setting_number_text(selection.amount_t)}T"
    return (
        f"貼外留肉 {_setting_number_text(selection.amount_t)}T｜"
        f"嵌入留肉 {_setting_number_text(selection.secondary_retain_t)}T｜"
        f"深度 {_setting_number_text(selection.secondary_depth_t)}T"
    )


def _phase6_corner_pair_var_changed(self, part_key, pair_key, var):
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_parameters_editable(self, part_key):
        return
    _phase6_settings_transactions(self).commit_corner_pair(
        part_key, pair_key, bool(var.get())
    )
    _phase6_notify_corner_change(self)
    _phase6_invalidate_settings_page(self, part_key)
    _phase6_render_settings_context(self, part_key)



def _phase6_corner_type_selected(self, part_key, target_key):
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_type_editable(self, part_key):
        return
    var = self.corner_type_vars.get(target_key)
    if var is None:
        return
    type_id = _CORNER_TYPE_BY_LABEL.get(str(var.get()).strip())
    if type_id is None:
        return
    _phase6_settings_transactions(self).commit_corner_type(
        part_key, target_key, type_id
    )
    _phase6_notify_corner_change(self)
    _phase6_invalidate_settings_page(self, part_key)
    _phase6_render_settings_context(self, part_key)

def _phase6_corner_mode_selected(self, part_key, target_key):
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_parameters_editable(self, part_key):
        return
    transactions = _phase6_settings_transactions(self)
    current = transactions.corner_selection(part_key, target_key)
    if current.type_id is not CornerTypeId.CROSS:
        return
    var = self.corner_mode_vars.get(target_key)
    mode = _CORNER_MODE_BY_LABEL.get(str(var.get()).strip()) if var is not None else None
    if mode is None:
        return
    transactions.commit_corner_mode(part_key, target_key, mode)
    _phase6_notify_corner_change(self)
    _phase6_invalidate_settings_page(self, part_key)
    _phase6_render_settings_context(self, part_key)

def _phase6_corner_target_var_changed(self, part_key, target_key):
    """Commit semantic parameter widgets through the T2 transaction owner."""
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_parameters_editable(self, part_key):
        return
    transactions = _phase6_settings_transactions(self)
    current = transactions.corner_selection(part_key, target_key)
    try:
        amount_var = self.corner_amount_vars.get(target_key)
        amount = float(amount_var.get()) if amount_var is not None else current.amount_t
        mode_var = self.corner_mode_vars.get(target_key)
        mode = (
            _CORNER_MODE_BY_LABEL.get(str(mode_var.get()).strip(), current.cross_mode)
            if mode_var is not None else current.cross_mode
        )
        direction_var = self.corner_direction_vars.get(target_key)
        direction = (
            _CORNER_DIRECTION_BY_LABEL.get(
                str(direction_var.get()).strip(), current.direction
            )
            if direction_var is not None else current.direction
        )
        retain_var = self.corner_secondary_retain_vars.get(target_key)
        depth_var = self.corner_secondary_depth_vars.get(target_key)
        retain = (
            float(retain_var.get())
            if retain_var is not None
            else current.secondary_retain_t
        )
        depth = (
            float(depth_var.get())
            if depth_var is not None
            else current.secondary_depth_t
        )
        transactions.commit_corner_parameters(
            part_key,
            target_key,
            amount_t=amount,
            cross_mode=mode,
            direction=direction,
            secondary_retain_t=retain,
            secondary_depth_t=depth,
        )
    except (TypeError, ValueError, original.tk.TclError):
        return
    _phase6_notify_corner_change(self)

def _phase6_is_unknown_baseline(self, value):
    text = str(value or "").strip()
    explicit = str(getattr(self, "_baseline_unknown_value", "") or "").strip()
    return (
        text == CUSTOM_MODEL_NAME
        or text in LEGACY_CUSTOM_MODEL_NAMES
        or (explicit and text == explicit)
    )


def _phase6_should_show_baseline_data(self, context, baseline_specs):
    """Return whether the current settings page has meaningful baseline-only data."""
    context = str(context or GLOBAL_CONTEXT)
    if context == GLOBAL_CONTEXT:
        return False
    model_var = getattr(self, "baseline_model_var", None)
    model = model_var.get() if model_var is not None else ""
    if _phase6_is_unknown_baseline(self, model):
        return False
    return bool(
        baseline_specs
        or context in {"box_body", "head", "tail", "door", "indicator_door"}
    )


def _phase6_invalidate_corner_pages(self):
    cache = getattr(self, "_settings_page_cache", None) or {}
    for context in list(cache):
        if context == GLOBAL_CONTEXT:
            continue
        _phase6_invalidate_settings_page(self, context)


def _phase6_known_model_corner_state(self):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    model_var = getattr(self, "baseline_model_var", None)
    model = str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()
    try:
        live_model = str(model_var.get() or "").strip() if model_var is not None else ""
    except Exception:
        live_model = ""
    if live_model:
        model = live_model
    try:
        from ae_engine.cabinet_types.registry import resolve_cabinet_type
        family = resolve_cabinet_type(model).canonical_name
    except Exception:
        family = "金庫型"
    return known_model_corner_state(
        getattr(self, "available_parts", KNOWN_PARTS),
        cabinet_family=family,
    )


def _phase6_on_baseline_model_changed(self, *_args):
    if getattr(self, "_phase6_baseline_guard", False):
        return
    self._phase6_corner_param_unlocked = {}
    new_model = str(self.baseline_model_var.get() or "").strip()
    old_model = str(
        getattr(self, "_phase6_baseline_last_model", "") or ""
    ).strip()
    old_editable = _phase6_is_unknown_baseline(self, old_model)
    if old_editable:
        self._corner_transaction_unknown_state = deepcopy(
            self._phase6_corner_state
        )
        self._corner_transaction_unknown_pairs = deepcopy(
            self._phase6_corner_pair_same
        )

    editable = _phase6_is_unknown_baseline(self, new_model)
    needs_fixed_corner_preset = bool(
        (not editable and new_model and new_model != old_model)
        or (editable and old_model and not old_editable)
    )
    fixed_corner_state = (
        _phase6_known_model_corner_state(self)
        if needs_fixed_corner_preset
        else {}
    )
    previous_non_receiving_structure = getattr(
        self,
        "_phase6_non_receiving_structure_state",
        None,
    )
    return _phase6_settings_coordinator(self).apply_baseline_transition(
        new_model=new_model,
        old_model=old_model,
        new_editable=editable,
        old_editable=old_editable,
        fixed_corner_state=fixed_corner_state,
        available_parts=tuple(
            getattr(self.designer_workspace, "available_parts", ()) or ()
        ),
        previous_non_receiving_structure=previous_non_receiving_structure,
    )

def _phase6_collect_workspace_state(self):
    active = self.designer_workspace.active_part
    live_active_profiles = None
    # The visible fold editor is live canonical state.  The adapter only supplies
    # that editor payload; DesignerWorkspace owns how it projects the shared schema.
    if active and active != "box_body":
        profiles = getattr(self.state, "profiles", {}) or {}
        live_x = profiles.get("X", ()) or ()
        live_y = profiles.get("Y", ()) or ()
        if live_x or live_y:
            live_active_profiles = {
                "X": clone_profile(live_x),
                "Y": clone_profile(live_y),
            }
    owner = self.designer_workspace.export_shared_snapshot(
        live_active_profiles=live_active_profiles
    )
    part_features_snapshot = getattr(self.designer_workspace, "part_features_snapshot", None)
    if callable(part_features_snapshot):
        owner["part_features"] = part_features_snapshot()
    part_face_features_snapshot = getattr(self.designer_workspace, "part_face_features_snapshot", None)
    if callable(part_face_features_snapshot):
        owner["part_face_features"] = part_face_features_snapshot()
    assembly_placements_snapshot = getattr(self.designer_workspace, "assembly_placements_snapshot", None)
    if callable(assembly_placements_snapshot):
        owner["assembly_placements"] = assembly_placements_snapshot()
    resolve_and_store = getattr(self.designer_workspace, "resolve_and_store_assembly_placements", None)
    if callable(resolve_and_store):
        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            owner["assembly_placements"] = resolve_and_store(
                dict(getattr(self, "_phase6_input_snapshot", {}) or {}),
                resolver=resolve_assembly_placement,
            )
        except Exception:
            pass
    graph_state = migrate_legacy_snapshot_joints(
        dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    )
    return {
        "assembly_type": assembly_intent_value(getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)),
        "assembly_joint_schema_version": graph_state["assembly_joint_schema_version"],
        "assembly_joints": deepcopy(graph_state["assembly_joints"]),
        "endcap_fw": deepcopy(
            getattr(self, "_phase6_endcap_fw_state", None)
            or normalize_endcap_fw_state(getattr(self, "_phase6_input_snapshot", {}) or {})
        ),
        "box_body_profile": clone_profile(self.state.profiles_vault.get("箱身", [])),
        **owner,
    }


def _phase6_relief_profile_fingerprint(profile):
    rows = []
    for raw in list(profile or ()):
        row = dict(raw or {})
        try:
            length = round(float(row.get("len", row.get("length", 0.0)) or 0.0), 6)
        except (TypeError, ValueError):
            length = 0.0
        angle = row.get("angle")
        try:
            angle = None if angle is None else round(float(angle), 6)
        except (TypeError, ValueError):
            angle = None
        rows.append((
            str(row.get("phase6_key") or ""), length, angle,
            str(row.get("core") or ""),
        ))
    return tuple(rows)


def _phase6_current_relief_source_signature(self, required):
    from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION

    source = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    source.update(dict(getattr(self, "_settings_values", {}) or {}))
    source.update(dict(getattr(self, "_phase6_box_whd", {}) or {}))
    source["assembly_type"] = assembly_intent_value(getattr(
        self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY
    ))
    scalar_keys = (
        "w", "h", "d", "t", "fw", "zl1", "zl2", "zr1", "zr2",
        "yl1", "yr1", "ytop1", "ybottom1", "assembly_type",
    )
    result = {key: deepcopy(source.get(key)) for key in scalar_keys if key in source}
    box_profile = clone_profile(
        (getattr(self.state, "profiles_vault", {}) or {}).get("箱身", ()) or ()
    )
    formed_left, formed_right = formed_box_body_fw_widths(
        box_profile, float(source.get("t", 0.0) or 0.0)
    )
    from ae_engine.assembly_joint import resolved_joint_graph_fingerprint
    graph_snapshot = migrate_legacy_snapshot_joints(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    structure_state = deepcopy(self.designer_workspace.box_body_structure_state() or {})
    import hashlib as _hashlib, json as _json
    structure_payload = _json.dumps(structure_state, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    family_name = str(source.get("model") or source.get("cabinet_type") or "")
    result.update({
        "relief_contract_version": RELIEF_CONTRACT_VERSION,
        "joint_graph_fingerprint": resolved_joint_graph_fingerprint(graph_snapshot),
        "family_structure_fingerprint": _hashlib.sha256(structure_payload.encode("utf-8")).hexdigest(),
        "cabinet_family": family_name,
        "box_body_formed_fw": {
            "left": None if formed_left is None else float(formed_left),
            "right": None if formed_right is None else float(formed_right),
        },
        "box_body_profile": box_profile,
        "part_profiles": {
            key: deepcopy(self.designer_workspace.profiles_for(key, {}) or {})
            for key in required
        },
    })
    return result


def _phase6_relief_source_matches_current(saved_source, current_source, required):
    from ae_engine.certified_relief_registry import RELIEF_CONTRACT_VERSION

    saved = dict(saved_source or {})
    current = dict(current_source or {})
    if not saved:
        return False
    try:
        if int(saved.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
            return False
        if int(current.get("relief_contract_version", 0) or 0) != RELIEF_CONTRACT_VERSION:
            return False
    except (TypeError, ValueError):
        return False
    saved_formed = dict(saved.get("box_body_formed_fw") or {})
    current_formed = dict(current.get("box_body_formed_fw") or {})
    for side in ("left", "right"):
        try:
            if abs(float(saved_formed[side]) - float(current_formed[side])) > 1e-6:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    for key in (
        "w", "h", "d", "t", "fw", "zl1", "zl2", "zr1", "zr2",
        "yl1", "yr1", "ytop1", "ybottom1",
    ):
        if key not in saved or key not in current:
            continue
        try:
            if abs(float(saved[key]) - float(current[key])) > 1e-6:
                return False
        except (TypeError, ValueError):
            return False
    saved_graph = str(saved.get("joint_graph_fingerprint") or "")
    current_graph = str(current.get("joint_graph_fingerprint") or "")
    if not saved_graph or not current_graph or saved_graph != current_graph:
        return False
    saved_structure = str(saved.get("family_structure_fingerprint") or "")
    current_structure = str(current.get("family_structure_fingerprint") or "")
    if not saved_structure or not current_structure or saved_structure != current_structure:
        return False
    if str(saved.get("cabinet_family") or "") != str(current.get("cabinet_family") or ""):
        return False
    # A matching geometry signature is insufficient when the Certified Rule
    # itself was revised or withdrawn.  Replay only active rule revisions.
    from ae_engine.certified_relief_registry import certified_rule_revision_exists
    saved_rules = dict(saved.get("registry_rules") or {})
    for part_key in required:
        rule = dict(saved_rules.get(str(part_key)) or {})
        rule_id = str(rule.get("rule_id") or "")
        if not rule_id:
            continue
        try:
            revision = int(rule.get("revision", 0) or 0)
        except (TypeError, ValueError):
            return False
        if revision <= 0 or not certified_rule_revision_exists(rule_id, revision):
            return False
    if "box_body_profile" in saved:
        if _phase6_relief_profile_fingerprint(saved.get("box_body_profile")) != _phase6_relief_profile_fingerprint(current.get("box_body_profile")):
            return False
    saved_parts = dict(saved.get("part_profiles") or {})
    current_parts = dict(current.get("part_profiles") or {})
    for key in required:
        saved_axes = dict(saved_parts.get(key) or {})
        current_axes = dict(current_parts.get(key) or {})
        for axis in ("X", "Y"):
            if axis not in saved_axes:
                continue
            if _phase6_relief_profile_fingerprint(saved_axes.get(axis)) != _phase6_relief_profile_fingerprint(current_axes.get(axis)):
                return False
    return True


def _phase6_serialize_assembly_relief_state(self):
    """Serialize only an atomic verified EndCap relief transaction.

    If a solve is partial/failed, preserve the previously committed relief
    state (if any).  Never manufacture a Head-new/Tail-old state.
    """
    enabled_var = getattr(self, "assembly_ignore_fixed_corner_var", None)
    fallback_enabled = bool(enabled_var.get()) if enabled_var is not None else True
    solutions = dict(getattr(self, "_phase6_last_relief_solutions", {}) or {})
    available = set(getattr(getattr(self, "designer_workspace", None), "available_parts", ()) or ())
    required = [key for key in ("head", "tail") if key in available]
    atomic_committable = bool(required) and all(
        key in solutions and _phase6_solution_is_committable(solutions[key])
        for key in required
    )
    source_signature = dict(_phase6_current_relief_source_signature(self, required) or {})
    if not atomic_committable:
        prior = deepcopy((getattr(self, "_phase6_input_snapshot", {}) or {}).get("assembly_relief") or {})
        if prior and _phase6_relief_source_matches_current(prior.get("source"), source_signature, required):
            return prior
        return {
            "enabled": False,
            "fallback_enabled": fallback_enabled,
            "clearance": _phase6_assembly_relief_clearance(self),
            "source": {},
            "parts": {},
        }
    source_signature["registry_rules"] = {
        key: {
            "rule_id": str(getattr(solutions[key], "rule_id", "") or ""),
            "revision": int(getattr(solutions[key], "rule_revision", 0) or 0),
        }
        for key in required
    }
    parts = {}
    for key in required:
        solution = solutions[key]
        measurements = []
        for item in tuple(getattr(solution, "corner_reliefs", ()) or ()):
            m = getattr(item, "measurement", None)
            if m is None:
                continue
            measurements.append({
                "corner_name": str(getattr(m, "corner_name", getattr(item, "corner_name", ""))),
                "primary_u": float(m.primary_u),
                "primary_v": float(m.primary_v),
                "secondary_u": None if m.secondary_u is None else float(m.secondary_u),
                "secondary_depth": None if m.secondary_depth is None else float(m.secondary_depth),
                "clearance_a": float(getattr(m, "clearance_a", 0.0)),
            })
        parts[key] = {
            "verified": bool(getattr(solution, "verified", False)),
            "canonical_accepted": True,
            "trust_level": str(getattr(solution, "trust_level", "PROVISIONAL_3D") or "PROVISIONAL_3D"),
            "rule_id": getattr(solution, "rule_id", None),
            "rule_revision": getattr(solution, "rule_revision", None),
            "joint_signature": [dict(item) for item in tuple(getattr(solution, "joint_signature", ()) or ())],
            "shadow_validation": deepcopy(getattr(solution, "shadow_validation", None)),
            "cuts": _phase6_relief_polygon_coords(getattr(solution, "cut_polygon_2d", None)),
            "measurements": measurements,
        }
    return {
        "enabled": True,
        "fallback_enabled": fallback_enabled,
        "clearance": _phase6_assembly_relief_clearance(self),
        "source": source_signature,
        "parts": parts,
    }


def _phase6_corner_transaction_payload(self):
    source = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    graph_state = migrate_legacy_snapshot_joints(source)
    workspace = _phase6_collect_workspace_state(self)
    return {
        "model": str(self.baseline_model_var.get() or "").strip(),
        "settings": dict(getattr(self, "_settings_values", {})),
        "multi_door_enabled": bool(source.get("multi_door_enabled", False)),
        "door_layout_columns": deepcopy(source.get("door_layout_columns") or []),
        "door_layout_scope": str(source.get("door_layout_scope") or "main"),
        "door_handle_edges": deepcopy(source.get("door_handle_edges") or {}),
        "assembly_type": assembly_intent_value(getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)),
        "assembly_joint_schema_version": graph_state["assembly_joint_schema_version"],
        "assembly_joints": deepcopy(graph_state["assembly_joints"]),
        "endcap_fw": deepcopy(
            getattr(self, "_phase6_endcap_fw_state", None)
            or normalize_endcap_fw_state(getattr(self, "_phase6_input_snapshot", {}) or {})
        ),
        "corner_state": deepcopy(getattr(self, "_phase6_corner_state", {})),
        "corner_pair_same": deepcopy(getattr(self, "_phase6_corner_pair_same", {})),
        "active_part": getattr(self, "active_part_key", None),
        "assembly_relief": _phase6_serialize_assembly_relief_state(self),
        "workspace": workspace,
        "existing_parts": list(workspace.get("existing_parts", [])),
        "part_profiles": deepcopy(workspace.get("part_profiles", {})),
        "box_body_structure": deepcopy(workspace.get("box_body_structure", {})),
        "box_body_profile": clone_profile(workspace.get("box_body_profile", [])),
        "part_features": deepcopy(workspace.get("part_features", {})),
        "part_face_features": deepcopy(workspace.get("part_face_features", {})),
        "assembly_placements": deepcopy(workspace.get("assembly_placements", {})),
    }


def _phase6_publish_live_state(self, *, force=False):
    """Publish only when the pure live-sync plan requires one envelope."""
    callback = getattr(self, "_live_sync_callback", None)
    if (
        not callable(callback)
        or getattr(self, "_phase6_live_sync_guard", False)
        or getattr(self, "_phase6_initializing", False)
        or not getattr(self, "_phase6_sync_ready", False)
        or not hasattr(self, "baseline_model_var")
        or not hasattr(self, "designer_workspace")
    ):
        return False

    state = _phase6_corner_transaction_payload(self)
    input_snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    host_relief_present = (
        isinstance(input_snapshot, Mapping)
        and "assembly_relief" in input_snapshot
    )
    host_relief = (
        deepcopy(input_snapshot.get("assembly_relief") or {})
        if host_relief_present
        else {}
    )
    plan = plan_live_sync_envelope(
        current_state=state,
        previous_state=getattr(self, "_phase6_last_live_state", None) or {},
        previous_fingerprint=getattr(
            self, "_phase6_last_live_fingerprint", None
        ),
        current_revision=getattr(self, "_phase6_sync_revision", 0),
        active_transaction_id=getattr(
            self, "_phase6_active_transaction_id", ""
        ),
        host_relief_present=host_relief_present,
        host_relief=host_relief,
        force=bool(force),
    )
    if not plan.should_publish:
        return False

    payload = materialize_sync_value(plan.payload)
    self._phase6_live_sync_guard = True
    try:
        callback(deepcopy(payload))
        self._phase6_sync_revision = plan.next_revision
        self._phase6_last_live_state = deepcopy(state)
        self._phase6_last_live_fingerprint = plan.fingerprint
        self._phase6_last_live_payload = deepcopy(payload)
        self._phase6_input_snapshot["assembly_relief"] = (
            materialize_sync_value(plan.host_relief_repair)
        )
    except Exception as exc:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"即時同步失敗：{exc}")
        return False
    finally:
        self._phase6_live_sync_guard = False
    return True


def _phase6_build_project_snapshot(self):
    """Capture one complete, reloadable Phase6 workspace plus all-part diagnostics."""
    try:
        self._save_current_part(notify=False)
    except Exception:
        pass
    model_var = getattr(self, "baseline_model_var", None)
    model = str(
        model_var.get() if model_var is not None
        else getattr(self, "_phase6_baseline_initial_model", "") or ""
    ).strip()
    owner_workspace = self.designer_workspace.snapshot()
    workspace = _phase6_collect_workspace_state(self)
    base_snapshot = deepcopy(getattr(self, "_phase6_input_snapshot", {}) or {})
    callback = getattr(self, "_scene_query_callback", None)
    final_geometry = collect_final_geometry_diagnostics(
        list(owner_workspace.get("existing_parts") or ()),
        lambda key: _phase6_scene_query_payload_for_part(self, key),
        callback if callable(callback) else None,
    )
    return Phase6ProjectController.build_designer_payload(
        schema=_phase6_project_file.PROJECT_SCHEMA,
        model=model,
        base_snapshot=base_snapshot,
        settings=getattr(self, "_settings_values", {}) or {},
        box_whd=getattr(self, "_phase6_box_whd", {}) or {},
        assembly_type=assembly_intent_value(
            getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
        ),
        endcap_fw=deepcopy(
            getattr(
                self,
                "_phase6_endcap_fw_state",
                normalize_endcap_fw_state(base_snapshot),
            )
        ),
        corner_state=getattr(self, "_phase6_corner_state", {}) or {},
        corner_pair_same=getattr(self, "_phase6_corner_pair_same", {}) or {},
        owner_workspace=owner_workspace,
        workspace=workspace,
        box_body_profile=clone_profile(workspace.get("box_body_profile", [])),
        assembly_relief=_phase6_serialize_assembly_relief_state(self),
        final_geometry=final_geometry,
    )

def _phase6_load_project_file(self):
    """透過 parent GUI 載入 .p6fold，並建立新的 3D 工作區。"""
    from tkinter import filedialog, messagebox

    path = filedialog.askopenfilename(
        parent=self.root,
        title="讀檔：Phase6 折彎專案",
        filetypes=[
            ("Phase6 折彎專案", f"*{_phase6_project_file.PROJECT_EXTENSION}"),
            ("所有檔案", "*.*"),
        ],
    )
    if not path:
        return None

    callback = getattr(self, "_project_load_callback", None)
    if not callable(callback):
        messagebox.showerror(
            "讀檔失敗",
            "目前工作區沒有可用的專案讀檔入口。",
            parent=self.root,
        )
        return None

    try:
        Phase6ProjectController.validate_project_load(
            path, _phase6_project_file.read_project
        )
        callback(str(path))
        return str(path)
    except Exception as exc:
        try:
            messagebox.showerror(
                "讀檔失敗",
                f"無法讀取 Phase6 專案：\n{exc}",
                parent=self.root,
            )
        except Exception:
            pass
        return None

def _phase6_save_project_file(self, *, save_as=False):
    """儲存 Phase6 專案；連接 main GUI 時一律委派 committed ownership。"""
    callback = getattr(self, "_project_save_callback", None)
    if callable(callback):
        return callback(
            save_as=bool(save_as),
            active_part=getattr(self, "active_part_key", None),
        )

    from tkinter import filedialog, messagebox

    if getattr(self, "_phase6_pending_settings", None):
        try:
            self.flush_pending_settings()
        except Exception:
            pass

    current = str(getattr(self, "_phase6_current_project_path", "") or "").strip()
    path = current
    if save_as or not path:
        model_var = getattr(self, "baseline_model_var", None)
        model = str(model_var.get() if model_var is not None else "").strip() or "自訂"
        safe_model = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in model)
        extension = _phase6_project_file.PROJECT_EXTENSION
        initial = Path(current).name if current else f"{safe_model}{extension}"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="另存新檔：Phase6 專案" if save_as else "儲存專案：Phase6",
            defaultextension=extension,
            filetypes=[("Phase6 折彎專案", f"*{extension}"), ("所有檔案", "*.*")],
            initialfile=initial,
        )
        if not path:
            return None

    try:
        payload = _phase6_build_project_snapshot(self)
        payload.get("snapshot", {}).pop("_runtime_project_path", None)
        target = Phase6ProjectController.write_designer_project(
            path, payload, _phase6_project_file.write_project
        )
        self._phase6_current_project_path = str(target)
        path_callback = getattr(self, "_project_path_change_callback", None)
        if callable(path_callback):
            path_callback(str(target))
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(
                f"已存專案：{Path(target).name}（全部板件）"
            )
        return str(target)
    except Exception as exc:
        messagebox.showerror(
            "存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root
        )
        return None

def _phase6_save_project_file_as(self):
    return _phase6_save_project_file(self, save_as=True)




def _phase6_refresh_active_endcap_from_linked(self, linked):
    key = str(self.designer_workspace.active_part or "")
    if key not in ENDCAP_FW_PARTS or key not in linked:
        return
    profiles = linked[key]
    self.state.profiles = {
        "X": clone_profile(profiles.get("X", ())),
        "Y": clone_profile(profiles.get("Y", ())),
    }
    try:
        self.bend_ui.rebuild_tabs()
    except Exception:
        pass


def _phase6_commit_endcap_fw_state(self):
    """View/effect refresh after transaction owner committed EndCap FW state."""
    linked = _phase6_rebuild_linked_endcaps(self)
    _phase6_refresh_active_endcap_from_linked(self, linked)
    try:
        self.do_update()
    except Exception:
        pass
    return linked


def _phase6_set_endcap_fw_override(self, part_key, value):
    _phase6_settings_transactions(self).commit_endcap_fw_override(
        str(part_key), value
    )
    return _phase6_commit_endcap_fw_state(self)




def _phase6_on_endcap_fw_value_selected(self, part_key, value_var):
    try:
        value = float(value_var.get())
    except (TypeError, ValueError):
        return
    _phase6_set_endcap_fw_override(self, part_key, value)


_BOX_STRUCTURE_LABELS = {
    BoxBodyStructureType.INTEGRAL: "一體成型",
    BoxBodyStructureType.TWO_PIECE_W_SPLIT: "二件式（W 二分）",
    BoxBodyStructureType.THREE_PIECE_W_SPLIT: "三件式（W 三分）",
    BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT: "三件式（側背分離）",
}
_BOX_STRUCTURE_LABEL_TO_TYPE = {label: key for key, label in _BOX_STRUCTURE_LABELS.items()}


_BACK_PANEL_MODE_LABELS = {
    BackPanelMode.FULL: "全板",
    BackPanelMode.HALF: "半截",
    BackPanelMode.BACK_OPENING: "背開孔",
}
_BACK_PANEL_MODE_LABEL_TO_MODE = {
    label: mode for mode, label in _BACK_PANEL_MODE_LABELS.items()
}


def _phase6_box_structure_state(self):
    return normalize_box_body_structure_state(self.designer_workspace.box_body_structure_state())


def _phase6_after_box_structure_commit(self, state, *, rebuild=False):
    """Bridge-only cache/view effects after canonical structure commit."""
    # 結構型態/尺寸是 manufacturing geometry signature 的一部分。切換後不可
    # 繼續重用上一型態的 resolved geometry，否則 3D 會停在舊結構。
    self._phase6_last_resolved_manufacturing_geometry = None
    self._phase6_last_resolved_manufacturing_signature = None
    if rebuild:
        def refresh():
            try:
                _phase6_invalidate_settings_page(self, "box_body")
                _phase6_render_settings_context(self, "box_body")
            except Exception:
                pass
        root = getattr(self, "root", None)
        if root is not None and hasattr(root, "after_idle"):
            root.after_idle(refresh)
        else:
            refresh()
    try:
        self.do_update()
    except Exception:
        pass
    return state


def _phase6_commit_box_structure_state(self, state, *, rebuild=False):
    committed = _phase6_settings_transactions(self).commit_box_structure_state(state)
    return _phase6_after_box_structure_commit(self, committed, rebuild=rebuild)


def _phase6_box_structure_error(self, exc):
    var = getattr(self, "settings_status_var", None)
    if var is not None:
        var.set(f"箱身結構設定無效：{exc}")


def _phase6_select_box_structure_type(self, var):
    type_id = _BOX_STRUCTURE_LABEL_TO_TYPE.get(str(var.get()).strip())
    if type_id is None:
        return
    state = _phase6_box_structure_state(self)
    # 受電箱的側背分離是 Family 固定拓撲；選單仍常駐顯示，但不可切換。
    if cabinet_family_policy.family_fixes_box_body_structure(
        getattr(self, "_phase6_input_snapshot", {}) or {}
    ):
        try:
            var.set(_BOX_STRUCTURE_LABELS[BoxBodyStructureType(state["active_type"])])
        except Exception:
            pass
        return
    try:
        next_state = _phase6_settings_transactions(self).activate_box_structure(
            state, type_id, _phase6_box_structure_w(self)
        )
    except Exception as exc:
        _phase6_box_structure_error(self, exc)
        return
    _phase6_after_box_structure_commit(self, next_state, rebuild=True)
    _phase6_refresh_persistent_structure_controls(self)


def _phase6_box_structure_w(self):
    values = dict(getattr(self, "_phase6_box_whd", {}) or {})
    values.update(dict(getattr(self, "_settings_values", {}) or {}))
    return float(values.get("w", getattr(getattr(self, "state", None), "w", 500.0)))


def _phase6_box_structure_d(self):
    values = dict(getattr(self, "_phase6_box_whd", {}) or {})
    values.update(dict(getattr(self, "_settings_values", {}) or {}))
    return float(values.get("d", getattr(getattr(self, "state", None), "d", 200.0)))


def _phase6_toggle_structure_advanced(self, type_id):
    flags = dict(getattr(self, "_phase6_box_structure_advanced_open", {}) or {})
    key = BoxBodyStructureType(type_id).value
    flags[key] = not bool(flags.get(key, False))
    self._phase6_box_structure_advanced_open = flags
    _phase6_invalidate_settings_page(self, "box_body")
    _phase6_render_settings_context(self, "box_body")


def _phase6_back_panel_mode_control_is_applicable(self):
    """Normal-input visibility contract for the Receiving rear-panel product choice."""
    workspace = getattr(self, "designer_workspace", None)
    active_part = str(getattr(workspace, "active_part", "") or "")
    if active_part != "box_body:back":
        return False
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    if cabinet_family_policy.canonical_family_name(snapshot) != "受電箱":
        return False
    state = _phase6_box_structure_state(self)
    return (
        str(state.get("active_type") or "")
        == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    )


def _phase6_refresh_back_panel_mode_control(self):
    """Project canonical rear-panel mode into the existing normal input region."""
    frame = getattr(self, "back_panel_mode_control", None)
    var = getattr(self, "back_panel_mode_var", None)
    selector = getattr(self, "back_panel_mode_selector", None)
    if frame is None or var is None or selector is None:
        return False

    if not _phase6_back_panel_mode_control_is_applicable(self):
        if frame.winfo_manager():
            frame.pack_forget()
        return False

    current = back_panel_mode(_phase6_box_structure_state(self))
    label = _BACK_PANEL_MODE_LABELS[current]
    if str(var.get() or "") != label:
        var.set(label)

    if not frame.winfo_manager():
        before = getattr(getattr(self, "bend_ui", None), "nb", None)
        options = {
            "fill": original.tk.X,
            "pady": (0, 4),
        }
        if before is not None and before.winfo_manager():
            options["before"] = before
        frame.pack(**options)
    return True


def _phase6_select_back_panel_mode(self, var):
    """Commit the Receiving rear-panel mode through canonical structure state."""
    mode = _BACK_PANEL_MODE_LABEL_TO_MODE.get(str(var.get()).strip())
    if mode is None:
        return
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    if cabinet_family_policy.canonical_family_name(snapshot) != "受電箱":
        return
    state = _phase6_box_structure_state(self)
    try:
        committed = set_side_back_back_panel_mode(state, mode)
        _phase6_commit_box_structure_state(self, committed, rebuild=True)
    except Exception as exc:
        _phase6_box_structure_error(self, exc)
        _phase6_after_box_structure_commit(self, state, rebuild=True)
    finally:
        _phase6_refresh_back_panel_mode_control(self)


def _phase6_apply_box_structure_numeric(self, type_id, field, var):
    state = _phase6_box_structure_state(self)
    try:
        raw = str(var.get()).strip()
        value = float(raw)
        committed = _phase6_settings_transactions(self).apply_box_structure_numeric(
            state,
            type_id,
            field,
            value,
            total_w=_phase6_box_structure_w(self),
            outside_family=cabinet_family_policy.box_body_profile_uses_outside_dimensions(
                getattr(self, "_phase6_input_snapshot", {}) or {}
            ),
        )
        _phase6_after_box_structure_commit(self, committed, rebuild=True)
    except Exception as exc:
        _phase6_box_structure_error(self, exc)
        # Recreate the UI from canonical state; invalid text never becomes truth.
        _phase6_after_box_structure_commit(self, state, rebuild=True)


def _phase6_joint_rows(self):
    snapshot = migrate_legacy_snapshot_joints(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    self._phase6_input_snapshot.update({
        "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
        "assembly_joints": deepcopy(snapshot["assembly_joints"]),
    })
    return list(self._phase6_input_snapshot["assembly_joints"])


def _phase6_add_user_joint(
    self, *, subject_part, target_part, relation, subject_region="", target_region="",
    clearance_policy="ZERO", contact_mode="AUTO", preserve_side="AUTO", relief_intent="AUTO",
    solver_constraints=None,
):
    rows = _phase6_joint_rows(self)
    rel = relation if isinstance(relation, AssemblyJointRelation) else AssemblyJointRelation(str(relation))
    import uuid
    joint = AssemblyJoint(
        joint_id=f"user:{uuid.uuid4().hex}",
        subject_part=str(subject_part), target_part=str(target_part),
        subject_region=str(subject_region or ""), target_region=str(target_region or ""),
        relation=rel, contact_mode=str(contact_mode or "AUTO"),
        preserve_side=str(preserve_side or "AUTO"), relief_intent=str(relief_intent or "AUTO"),
        clearance_policy=str(clearance_policy or "ZERO"),
        solver_constraints=dict(solver_constraints or {}),
        source=AssemblyJointSource.USER_ADDED,
    )
    key = (joint.subject_part, joint.target_part, joint.subject_region, joint.target_region, joint.relation.value)
    for raw in rows:
        existing = AssemblyJoint.from_dict(raw)
        other = (existing.subject_part, existing.target_part, existing.subject_region, existing.target_region, existing.relation.value)
        if other == key:
            raise ValueError("相同 AssemblyJoint 已存在")
    rows.append(joint.to_dict())
    self._phase6_input_snapshot["assembly_joints"] = rows
    return joint.to_dict()


def _phase6_delete_user_joint(self, joint_id):
    rows = _phase6_joint_rows(self)
    found = None
    kept = []
    for raw in rows:
        if str(raw.get("joint_id")) == str(joint_id):
            found = AssemblyJoint.from_dict(raw)
            continue
        kept.append(raw)
    if found is None:
        return False
    if found.source is not AssemblyJointSource.USER_ADDED:
        raise ValueError("只有 USER_ADDED Joint 可以刪除")
    self._phase6_input_snapshot["assembly_joints"] = kept
    return True


def _phase6_on_assembly_type_selected(self, *_args):
    if getattr(self, "_phase6_settings_rendering", False):
        return
    var = getattr(self, "assembly_type_var", None)
    type_id = ASSEMBLY_LABEL_TO_TYPE.get(str(var.get()).strip()) if var is not None else None
    if type_id is None:
        return
    transactions = _phase6_settings_transactions(self)
    transactions.commit_assembly_intent(
        type_id,
        available_parts=tuple(getattr(self.designer_workspace, "available_parts", ()) or ()),
        project_legacy_corner=False,
        mark_dirty=True,
    )
    # The box-body page owns the live assembly Combobox that fired this event.
    # Destroying/rebuilding that page from inside <<ComboboxSelected>> destroys
    # the widget while Tk is still dispatching its event. Only dependent EndCap
    # pages need rebuilding.
    for context in ("head", "tail"):
        _phase6_invalidate_settings_page(self, context)
    _phase6_rebuild_linked_endcaps(self)
    _phase6_render_active_drawing_edge_controls(self)
    try:
        self.do_update()
    except Exception:
        pass


_ENDCAP_EDGE_LABELS = {
    "TOP": "上", "BOTTOM": "下", "LEFT": "左", "RIGHT": "右",
}
_ENDCAP_RELATION_LABELS = {
    AssemblyJointRelation.INSERT: "嵌入",
    AssemblyJointRelation.OVERLAY: "貼外",
    AssemblyJointRelation.INSERT_OVERLAY: "嵌入貼外",
    AssemblyJointRelation.WRAP: "包覆",
}
_ENDCAP_LABEL_TO_RELATION = {
    label: relation for relation, label in _ENDCAP_RELATION_LABELS.items()
}

_BASE_PLATE_EDGE_SETTING_KEYS = {
    "TOP": "base_plate_shrink_top",
    "BOTTOM": "base_plate_shrink_bottom",
    "LEFT": "base_plate_shrink_left",
    "RIGHT": "base_plate_shrink_right",
}


def _phase6_endcap_joint_policy_rows(self, part_key):
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        return ()
    snapshot = migrate_legacy_snapshot_joints(
        dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    )
    intent_id = assembly_intent_value(
        snapshot.get("assembly_type")
        or getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
    )
    record = get_assembly_intent(intent_id)
    rows = []
    for edge in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
        policy = record.edge_policy(edge)
        relation = edge_relation_for_part(snapshot, part_key, edge) or policy.default_relation
        rows.append({
            "edge": edge,
            "relation": relation,
            "value": _ENDCAP_RELATION_LABELS[relation],
            "allowed": tuple(_ENDCAP_RELATION_LABELS[item] for item in policy.allowed_relations),
            "editable": bool(policy.editable),
        })
    return tuple(rows)


def _phase6_on_endcap_edge_relation_selected(self, part_key, edge):
    part_key = str(part_key)
    edge = str(edge).upper()
    var = dict(getattr(self, "endcap_joint_vars", {}) or {}).get(edge)
    if var is None:
        return None
    relation = _ENDCAP_LABEL_TO_RELATION.get(str(var.get()).strip())
    if relation is None:
        return None
    _phase6_settings_transactions(self).commit_endcap_edge_relation(
        part_key, edge, relation
    )
    try:
        self.do_update()
    except Exception:
        pass
    return relation


def _phase6_ensure_drawing_edge_hosts(self):
    existing = getattr(self, "drawing_edge_hosts", None)
    if existing is not None:
        try:
            if all(host.winfo_exists() for host in (existing.top, existing.bottom, existing.left, existing.right)):
                return existing
        except Exception:
            pass

    canvas = self.renderer.canvas.get_tk_widget()
    hosts = Phase6DrawingEdgeHosts(
        top=original.ttk.Frame(canvas, padding=(4, 2)),
        bottom=original.ttk.Frame(canvas, padding=(4, 2)),
        left=original.ttk.Frame(canvas, padding=(4, 2)),
        right=original.ttk.Frame(canvas, padding=(4, 2)),
        center=canvas,
    )
    self.drawing_edge_hosts = hosts
    return hosts


def _phase6_clear_drawing_edge_controls(self):
    hosts = getattr(self, "drawing_edge_hosts", None)
    if hosts is None:
        return
    for host in (hosts.top, hosts.bottom, hosts.left, hosts.right):
        try:
            for child in host.winfo_children():
                child.destroy()
            host.place_forget()
        except Exception:
            pass

def _phase6_place_drawing_edge_host(host, edge):
    plan = Phase6CornerDataViewAdapter.edge_host_placement(edge)
    if plan:
        host.place(**plan)

def _phase6_render_endcap_edge_controls(self, *, part_key):
    rows = _phase6_endcap_joint_policy_rows(self, part_key)
    _phase6_clear_drawing_edge_controls(self)
    self.endcap_joint_vars = {}
    self.endcap_joint_widgets = {}
    self.endcap_joint_allowed = {}
    if not rows:
        return None

    hosts = _phase6_ensure_drawing_edge_hosts(self)
    edge_hosts = {
        "TOP": hosts.top,
        "BOTTOM": hosts.bottom,
        "LEFT": hosts.left,
        "RIGHT": hosts.right,
    }
    for row in rows:
        edge = row["edge"]
        host = edge_hosts[edge]
        original.ttk.Label(host, text=f"{_ENDCAP_EDGE_LABELS[edge]}：").pack(side=original.tk.LEFT)
        var = original.tk.StringVar(master=host, value=row["value"])
        widget = build_choice_menubutton(
            host, variable=var, values=row["allowed"],
            state=("normal" if row["editable"] else "disabled"), width=5,
            command=lambda p=part_key, e=edge: _phase6_on_endcap_edge_relation_selected(self, p, e),
        )
        widget.pack(side=original.tk.LEFT)
        self.endcap_joint_vars[edge] = var
        self.endcap_joint_widgets[edge] = widget
        self.endcap_joint_allowed[edge] = tuple(row["allowed"])
        _phase6_place_drawing_edge_host(host, edge)
    return hosts

def _phase6_commit_base_plate_edge_shrink(self, edge, raw_value):
    edge = str(edge).upper()
    key = _BASE_PLATE_EDGE_SETTING_KEYS.get(edge)
    if key is None:
        return False
    try:
        value = float(raw_value)
    except (TypeError, ValueError, original.tk.TclError):
        return False
    if value < 0:
        return False
    _phase6_stage_setting_update(self, key, value)
    _phase6_flush_pending_settings(self)
    var = dict(getattr(self, "base_plate_edge_shrink_vars", {}) or {}).get(edge)
    if var is not None:
        text = _setting_number_text(self._settings_values.get(key, value))
        if var.get() != text:
            var.set(text)
    return True


def _phase6_render_base_plate_edge_controls(self):
    _phase6_clear_drawing_edge_controls(self)
    self.endcap_joint_vars = {}
    self.endcap_joint_widgets = {}
    self.endcap_joint_allowed = {}
    self.base_plate_edge_shrink_vars = {}
    self.base_plate_edge_shrink_widgets = {}

    hosts = _phase6_ensure_drawing_edge_hosts(self)
    edge_hosts = {
        "TOP": hosts.top,
        "BOTTOM": hosts.bottom,
        "LEFT": hosts.left,
        "RIGHT": hosts.right,
    }
    values = dict(getattr(self, "_settings_values", {}) or {})
    values.update(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    for edge, key in _BASE_PLATE_EDGE_SETTING_KEYS.items():
        host = edge_hosts[edge]
        original.ttk.Label(host, text=f"{_ENDCAP_EDGE_LABELS[edge]}縮：").pack(side=original.tk.LEFT)
        var = original.tk.StringVar(master=host, value=_setting_number_text(values.get(key, 55.0)))
        entry = original.ttk.Entry(host, textvariable=var, width=7, justify=original.tk.CENTER)
        entry.pack(side=original.tk.LEFT)
        entry.bind(
            "<Return>",
            lambda _e, ed=edge, v=var: _phase6_commit_base_plate_edge_shrink(self, ed, v.get()),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e, ed=edge, v=var: _phase6_commit_base_plate_edge_shrink(self, ed, v.get()),
        )
        self.base_plate_edge_shrink_vars[edge] = var
        self.base_plate_edge_shrink_widgets[edge] = entry
        _phase6_place_drawing_edge_host(host, edge)
    return hosts


def _phase6_render_active_drawing_edge_controls(self):
    mode = str(getattr(self, "_phase6_3d_display_mode", "single") or "single")
    part_key = str(getattr(self, "active_part_key", None) or "")
    if mode != "single":
        _phase6_clear_drawing_edge_controls(self)
        self.endcap_joint_vars = {}
        self.endcap_joint_widgets = {}
        self.endcap_joint_allowed = {}
        self.base_plate_edge_shrink_vars = {}
        self.base_plate_edge_shrink_widgets = {}
        return None
    if part_key in ENDCAP_FW_PARTS:
        self.base_plate_edge_shrink_vars = {}
        self.base_plate_edge_shrink_widgets = {}
        return _phase6_render_endcap_edge_controls(self, part_key=part_key)
    if part_key == "base_plate":
        return _phase6_render_base_plate_edge_controls(self)
    _phase6_clear_drawing_edge_controls(self)
    self.endcap_joint_vars = {}
    self.endcap_joint_widgets = {}
    self.endcap_joint_allowed = {}
    self.base_plate_edge_shrink_vars = {}
    self.base_plate_edge_shrink_widgets = {}
    return None

def _phase6_on_box_symmetry_changed(self):
    """Keep BoxBody symmetry authoritative and fail closed for asymmetric families."""
    var = getattr(self, "v_sy", None)
    if var is None:
        return
    transactions = _phase6_settings_transactions(self)
    if not _phase6_box_symmetry_allowed(self):
        _phase6_apply_box_symmetry_policy(self)
        target = bool(getattr(self.state, "symmetric", False))
        if hasattr(self, "bend_ui"):
            self.bend_ui._phase6_refresh_symmetry_bar()
    else:
        try:
            target = bool(var.get())
        except Exception:
            return
    transactions.commit_symmetry(self.state, target)

    # v_sy already owns an original trace to queue_update(). When this command
    # callback is invoked by the restored checkbox, cancel that queued duplicate
    # redraw and perform the update once with the new authoritative state.
    pending = getattr(self, "_job", None)
    root = getattr(self, "root", None)
    if pending and root is not None:
        try:
            root.after_cancel(pending)
        except Exception:
            pass
        self._job = None
    try:
        self.do_update()
    except Exception:
        pass

def _phase6_commit_receiving_bottom_wrap_controls(self, part_key, reserve_u_var, reserve_v_var):
    """Commit receiving WRAP reserve values without owning the Joint relation."""
    if str(part_key) not in ENDCAP_FW_PARTS:
        return None
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    if not cabinet_family_policy.supports_bottom_wrap_controls(snapshot):
        return None
    current = resolve_endcap_bottom_wrap(
        snapshot, str(part_key),
        state=getattr(self, "_phase6_endcap_bottom_wrap_state", None),
    )
    # A stale settings page may outlive an Assembly Intent change.  Never let
    # reserve editing recreate WRAP after the graph changed away from it.
    if not bool(current.get("enabled", False)):
        return None
    try:
        reserve_u = max(0.0, float(reserve_u_var.get()))
        reserve_v = max(0.0, float(reserve_v_var.get()))
    except (TypeError, ValueError, original.tk.TclError):
        return None
    committed = _phase6_settings_transactions(self).commit_bottom_wrap(
        str(part_key), reserve_u=reserve_u, reserve_v=reserve_v
    )
    self._phase6_last_resolved_manufacturing_geometry = None
    self._phase6_last_resolved_manufacturing_signature = None
    for key in ENDCAP_FW_PARTS:
        _phase6_invalidate_settings_page(self, key)
    self.do_update()
    return committed


def _phase6_apply_external_assembly_type(self, type_id):
    transactions = _phase6_settings_transactions(self)
    stable = assembly_intent_value(type_id)
    committed = transactions.commit_assembly_intent(
        type_id,
        available_parts=tuple(getattr(self.designer_workspace, "available_parts", ()) or ()),
        project_legacy_corner=True,
        reset_bottom_defaults=(stable == CornerTypeId.OVERLAY.value),
        mark_dirty=False,
    )
    for context in ("box_body", "head", "tail"):
        _phase6_invalidate_settings_page(self, context)
    if getattr(self, "active_part_key", None) is not None:
        _phase6_render_settings_context(
            self, getattr(self, "settings_context", self.active_part_key)
        )
    self.do_update()
    return committed

def _phase6_apply_external_corner_state(self, corner_state, corner_pair_same):
    transactions = _phase6_settings_transactions(self)
    self._phase6_corner_guard = True
    try:
        transactions.replace_corner_state(corner_state, corner_pair_same)
    finally:
        self._phase6_corner_guard = False
    context = getattr(self, "settings_context", GLOBAL_CONTEXT)
    if context != GLOBAL_CONTEXT:
        _phase6_invalidate_settings_page(self, context)
        _phase6_render_settings_context(self, context)



def _phase6_settings_endcap_fw_projection(self, part_key):
    part_key = str(part_key)
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    state = self._phase6_endcap_fw_state.setdefault(
        part_key, {"follow_box": True, "value": _num(snapshot.get("fw", 25), 25)}
    )
    return {
        "follow": bool(state.get("follow_box", True)),
        "effective": resolve_endcap_fw(
            snapshot, part_key, state=self._phase6_endcap_fw_state
        ),
    }


def _phase6_settings_box_structure_projection(self):
    state = _phase6_box_structure_state(self)
    active = BoxBodyStructureType(state["active_type"])
    cfg = state["configs"][active.value]
    total_w = _phase6_box_structure_w(self)
    piece_values = {}
    mode = "integral"
    if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
        mode = "two_w"
        left, right = resolve_two_piece_widths(state, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
        mode = "three_w"
        left, middle, right = resolve_three_piece_widths(state, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:middle": ("width", "W 包外", middle, "mm", "middle"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
        mode = "side_back"
        outside_family = cabinet_family_policy.box_body_profile_uses_outside_dimensions(
            getattr(self, "_phase6_input_snapshot", {}) or {}
        )
        rear_bend = (
            side_rear_bend_outside_length(
                state, float((getattr(self, "_phase6_input_snapshot", {}) or {}).get("t", 2.0))
            )
            if outside_family else float(cfg.get("side_rear_bend", 15))
        )
        width_comp_t = float(cfg.get("back_width_comp_t", 0.5))
        piece_values = {
            "box_body:left_side": ("rear_bend", "後折", rear_bend, "mm", "side_rear_bend"),
            "box_body:back": ("width_comp_t", "寬補償", width_comp_t, "T", "back_width_comp_t"),
            "box_body:right_side": ("rear_bend", "後折", rear_bend, "mm", "side_rear_bend"),
        }

    projections = ()
    projection_error = None
    if active is not BoxBodyStructureType.INTEGRAL:
        try:
            render_data = _phase6_box_body_structure_render_data(self)
            projections = _phase6_box_body_piece_dimension_projections(render_data)
            active_piece_key = str(getattr(self.designer_workspace, "active_part", "") or "")
            if _phase6_is_box_body_physical_piece_key(active_piece_key):
                projections = tuple(
                    row for row in projections if row.part_key == active_piece_key
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
            if part_key in {"box_body:left_side", "box_body:right_side"}:
                detail = f"成型深度 D：{_setting_number_text(_phase6_box_structure_d(self))} mm"
            elif part_key == "box_body:back":
                detail = f"成型寬：{_setting_number_text(projection.formed_width)} mm"
        # #517: 後面板形式 is a normal product choice projected by
        # back_panel_mode_control inside input_content_host.  settings_center
        # must not render a second selector for the same canonical state.
        back_panel_selector = None
        pieces.append({
            "part_key": part_key,
            "label": projection.label,
            "formed_width": projection.formed_width,
            "formed_height": projection.formed_height,
            "blank_width": projection.blank_width,
            "blank_height": projection.blank_height,
            "input": input_spec,
            "back_panel_selector": back_panel_selector,
            "detail": detail,
        })

    advanced_fields = ()
    if mode in {"two_w", "three_w"}:
        advanced_fields = (
            {"label": "封頭尾額外避讓", "field": "endcap_extra_relief", "value": cfg.get("endcap_extra_relief", 5), "suffix": "mm"},
            {"label": "封頭尾單邊留肉", "field": "endcap_single_side_meat_t", "value": cfg.get("endcap_single_side_meat_t", 0.5), "suffix": "T"},
            {"label": "底板避讓總長", "field": "baseplate_relief_length", "value": cfg.get("baseplate_relief_length", 20), "suffix": "mm"},
            {"label": "底板單邊留肉", "field": "baseplate_single_side_meat_t", "value": cfg.get("baseplate_single_side_meat_t", 0.5), "suffix": "T"},
        )
    advanced_flags = dict(getattr(self, "_phase6_box_structure_advanced_open", {}) or {})
    return {
        "active_type": active,
        "mode": mode,
        "pieces": tuple(pieces),
        "projection_error": projection_error,
        "seam_bend": cfg.get("seam_bend", 12),
        "advanced_open": bool(advanced_flags.get(active.value, False)),
        "advanced_fields": advanced_fields,
    }


def _phase6_settings_bottom_wrap_projection(self, part_key):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    if (
        str(part_key) not in ENDCAP_FW_PARTS
        or not cabinet_family_policy.supports_bottom_wrap_controls(snapshot)
    ):
        return None
    item = resolve_endcap_bottom_wrap(
        snapshot,
        str(part_key),
        state=getattr(
            self,
            "_phase6_endcap_bottom_wrap_state",
            normalize_endcap_bottom_wrap_state(snapshot),
        ),
    )
    if not bool(item.get("enabled", False)):
        return None
    return {
        "reserve_u": item["reserve_u"],
        "reserve_v": item["reserve_v"],
    }


def _phase6_settings_corner_projection(self, part_key):
    part_key = str(part_key)
    if part_key == GLOBAL_CONTEXT or part_key == "box_body":
        return {"mode": "none"}

    if part_key in {"indicator_box", "indicator_door"}:
        summary = _FIXED_CORNER_SUMMARIES.get(part_key, "")
        if summary:
            return {"mode": "fixed", "summary": summary}

    type_editable = _phase6_corner_type_editable(self, part_key)
    params_unlocked = _phase6_corner_parameters_unlocked(self, part_key)
    params_editable = _phase6_corner_parameters_editable(self, part_key)
    if not type_editable and not params_unlocked:
        summary = _FIXED_CORNER_SUMMARIES.get(part_key, "")
        if summary:
            return {"mode": "fixed", "summary": summary}

    state, pairs = _phase6_ensure_corner_part(self, part_key)
    pair_rows = []
    for pair_key in ("top", "bottom"):
        targets = (pair_key,) if pairs[pair_key] else _CORNER_PAIR_KEYS[pair_key]
        target_rows = []
        for target_key in targets:
            physical = (
                _CORNER_PAIR_KEYS[target_key][0]
                if target_key in _CORNER_PAIR_KEYS
                else target_key
            )
            selection = _phase6_selection_from_raw(state[physical])
            if selection.type_id is CornerTypeId.CROSS and selection.cross_mode is CrossCornerMode.RETAIN:
                direction_options = ("寬", "高")
            elif selection.type_id is CornerTypeId.CROSS and selection.cross_mode is not CrossCornerMode.STANDARD:
                direction_options = ("寬＋高", "寬", "高")
            else:
                direction_options = ()
            direction_label = (
                _CORNER_DIRECTION_LABEL[selection.direction]
                if selection.type_id is CornerTypeId.CROSS
                and selection.cross_mode is not CrossCornerMode.STANDARD
                else ""
            )
            target_rows.append({
                "target_key": target_key,
                "side_label": (
                    ""
                    if len(targets) <= 1
                    else ("左" if target_key.endswith("left") else "右")
                ),
                "type_label": _CORNER_TYPE_LABEL_BY_ID[selection.type_id.value],
                "type_options": tuple(_CORNER_TYPE_LABEL_BY_ID.values()),
                "type_kind": selection.type_id.name,
                "top_assembly_owned": (
                    part_key in {"head", "tail"} and pair_key == "top"
                ),
                "parameter_summary": _phase6_corner_parameter_summary(selection),
                "amount_t": (
                    selection.amount_t if selection.amount_t is not None else 1.0
                ),
                "mode_label": (
                    _CORNER_MODE_LABEL[selection.cross_mode]
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
                "secondary_retain_t": selection.secondary_retain_t,
                "secondary_depth_t": selection.secondary_depth_t,
            })
        pair_rows.append({
            "pair_key": pair_key,
            "label": "上方" if pair_key == "top" else "下方",
            "same": bool(pairs[pair_key]),
            "targets": tuple(target_rows),
        })
    return {
        "mode": "editable",
        "type_editable": bool(type_editable),
        "params_unlocked": bool(params_unlocked),
        "params_editable": bool(params_editable),
        "pairs": tuple(pair_rows),
    }


def _phase6_settings_context_extension_projection(self, context):
    context = str(context)
    return {
        "box_structure": (
            _phase6_settings_box_structure_projection(self)
            if context == "box_body" else None
        ),
        "endcap_fw": (
            _phase6_settings_endcap_fw_projection(self, context)
            if context in ENDCAP_FW_PARTS else None
        ),
        "bottom_wrap": (
            _phase6_settings_bottom_wrap_projection(self, context)
            if context in ENDCAP_FW_PARTS else None
        ),
        "corner": _phase6_settings_corner_projection(self, context),
    }


_SETTINGS_EXTENSION_MAP_ATTRS = (
    "corner_pair_vars",
    "corner_pair_checkbuttons",
    "corner_type_vars",
    "corner_mode_vars",
    "corner_direction_vars",
    "corner_amount_vars",
    "corner_secondary_retain_vars",
    "corner_secondary_depth_vars",
    "corner_detail_frames",
)


def _phase6_sync_settings_panel_extension(self, state, context):
    state = dict(state or {})
    for name in _SETTINGS_EXTENSION_MAP_ATTRS:
        setattr(self, name, dict(state.get(name, {}) or {}))
    self.fixed_corner_summary_var = state.get("fixed_corner_summary_var") or original.tk.StringVar(value="")
    self.corner_param_lock_button = state.get("corner_param_lock_button")
    self.bottom_wrap_enabled_var = state.get("bottom_wrap_enabled_var")
    self.bottom_wrap_reserve_u_var = state.get("bottom_wrap_reserve_u_var")
    self.bottom_wrap_reserve_v_var = state.get("bottom_wrap_reserve_v_var")
    self.bottom_wrap_widget = state.get("bottom_wrap_widget")
    self.box_body_piece_input_host = state.get("box_body_piece_input_host")
    self.box_body_piece_input_sections = dict(state.get("box_body_piece_input_sections", {}) or {})
    self.box_body_piece_input_vars = dict(state.get("box_body_piece_input_vars", {}) or {})
    self.box_body_piece_input_entries = dict(state.get("box_body_piece_input_entries", {}) or {})
    if context in ENDCAP_FW_PARTS and state.get("endcap_fw_follow_var") is not None:
        snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
        snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
        fw_state = self._phase6_endcap_fw_state.setdefault(
            context, {"follow_box": True, "value": _num(snapshot.get("fw", 25), 25)}
        )
        follow = bool(fw_state.get("follow_box", True))
        effective = resolve_endcap_fw(snapshot, context, state=self._phase6_endcap_fw_state)
        state["endcap_fw_follow_var"].set(follow)
        state["endcap_fw_value_var"].set(_setting_number_text(effective))
        try:
            state["endcap_fw_widget"].configure(state="normal")
        except Exception:
            pass



def _phase6_ensure_settings_panel(self):
    return _phase6_composition(self).settings_panel(globals())

def _phase6_sync_settings_panel_compat(self):
    panel = self.settings_panel
    self.settings_center = panel.settings_center
    self.settings_fields = panel.settings_fields
    self.settings_title_var = panel.settings_title_var
    self.unfolded_size_var = panel.unfolded_size_var
    self.settings_status_var = panel.settings_status_var
    self.save_settings_button = panel.save_settings_button
    self.setting_vars = panel.setting_vars
    self._settings_page_cache = panel.page_cache
    self._settings_current_page = panel.current_page
    self.settings_context = panel.settings_context
    self.advanced_settings_visible = panel.advanced_settings_visible
    self.advanced_settings_frame = panel.advanced_settings_frame
    self.advanced_toggle_button = panel.advanced_toggle_button
    self.baseline_data_frame = panel.baseline_data_frame
    self.baseline_data_toggle_button = panel.baseline_data_toggle_button
    self.baseline_setting_cells = panel.baseline_setting_cells
    self.left_global_controls = panel.left_global_controls
    self.left_global_vars = panel.left_global_vars
    self.left_global_cells = panel.left_global_cells
    self.baseline_model_var = panel.baseline_model_var
    self.baseline_model_combo = panel.baseline_model_combo
    self.ui_text_size_var = panel.ui_text_size_var
    self.ui_text_size_combo = panel.ui_text_size_combo
    self.save_global_settings_button = panel.save_global_settings_button


def _phase6_settings_panel_toggle_baseline(self):
    self.settings_panel.toggle_baseline_data()
    _phase6_sync_settings_panel_compat(self)


def _phase6_invalidate_settings_page(self, context):
    self.settings_panel.invalidate_context(str(context))
    _phase6_sync_settings_panel_compat(self)














def _phase6_render_settings_context(self, context):
    self._phase6_settings_rendering = True
    try:
        page = self.settings_panel.render_context(str(context or GLOBAL_CONTEXT))
        _phase6_sync_settings_panel_compat(self)
        return page
    finally:
        self._phase6_settings_rendering = False


def _phase6_save_current_settings_as_defaults(self):
    return self.settings_panel.save_current_settings_as_defaults()



def _phase6_apply_external_settings(self, updates):
    self._phase6_external_apply_guard = True
    try:
        return _phase6_apply_setting_updates(self, updates, notify=False)
    finally:
        self._phase6_external_apply_guard = False


def _phase6_apply_external_model(self, model):
    """Apply Main-GUI family selection through the existing Designer authority."""
    plan = _phase6_settings_transactions(self).plan_external_model_change(model)
    if not plan.changed:
        return False

    self._phase6_external_apply_guard = True
    try:
        model_var = getattr(self, "baseline_model_var", None)
        if model_var is None:
            return False
        if str(model_var.get() or "").strip() != plan.target_model:
            model_var.set(plan.target_model)
        # Some UI bindings invoke the handler from the selector event rather
        # than the StringVar write. Call the existing authority only when the
        # snapshot has not already reconciled itself.
        if str((getattr(self, "_phase6_input_snapshot", {}) or {}).get("model") or "").strip() != plan.target_model:
            _phase6_on_baseline_model_changed(self)
    finally:
        self._phase6_external_apply_guard = False
    return str((getattr(self, "_phase6_input_snapshot", {}) or {}).get("model") or "").strip() == plan.target_model

def _phase6_apply_external_sync(self, envelope):
    """Ingest one Main-GUI revision through the T3 orchestration service."""
    service = _phase6_settings_service(self)
    plan = service.plan_external_sync(envelope)
    if not plan.accepted or not plan.settings:
        return {}
    result = _phase6_apply_external_settings(self, plan.settings)
    if (
        str(getattr(self, "_phase6_3d_display_mode", "") or "") == "corner_data"
        and getattr(self, "corner_data_canvas", None) is not None
    ):
        _phase6_refresh_corner_data_unfold_view(self)
    return result

def _phase6_left_workspace_width(value) -> int:
    """Return the visual-review width floor for each supported UI text scale."""
    key = normalize_ui_text_size(value)
    return {"small": 338, "medium": 430, "large": 480}[key]


def _phase6_update_left_workspace_width(self, key=None):
    canvas = getattr(self, "left_scroll_canvas", None)
    if canvas is None:
        return None
    value = key if key is not None else self._settings_values.get("ui_text_size", "small")
    target = _phase6_left_workspace_width(value)
    canvas.configure(width=target)
    try:
        canvas.update_idletasks()
    except Exception:
        pass
    return target


def _phase6_apply_ui_text_size(self, key):
    if getattr(self, "_phase6_settings_guard", False):
        return
    key = normalize_ui_text_size(key)
    self._settings_values["ui_text_size"] = key
    self._phase6_input_snapshot["ui_text_size"] = key
    self._ui_text_controller.apply(key)
    self.state.ui_text_scale = self._ui_text_controller.factor
    _phase6_update_left_workspace_width(self, key)
    callback = getattr(self, "_ui_text_size_change_callback", None)
    if callback is not None and not getattr(self, "_phase6_external_apply_guard", False):
        callback(key)
    try:
        self.bend_ui.render()
    except Exception:
        pass
    try:
        self.renderer.render()
    except Exception:
        pass


def _phase6_on_ui_text_size_changed(self, *_args):
    panel = getattr(self, "settings_panel", None)
    var = getattr(panel, "ui_text_size_var", None) if panel is not None else getattr(self, "ui_text_size_var", None)
    if var is None:
        return
    return _phase6_apply_ui_text_size(self, normalize_ui_text_size(var.get()))




_PHASE6_OPERATOR_LABELS = {
    "ANY": "不限",
    "NONE": "無",
    "INSERT": "嵌入",
    "OVERLAY": "貼外",
    "INSERT_OVERLAY": "嵌入貼外",
    "WRAP": "外側包覆",
    "HEAD_OR_TAIL": "封頭／封尾",
    "DIVIDER": "中隔",
    "ENDS": "封頭／封尾",
    "receiving_divider_four_segment": "受電箱中隔四段式",
    "cross_slot_min_y": "十字槽最小縱向",
    "HEAD": "封頭",
    "TAIL": "封尾",
    "BOX_BODY": "箱身",
    "BOX_SIDE": "箱身側邊",
    "REAR_PANEL": "後面板",
    "TOP": "上方",
    "BOTTOM": "下方",
    "MATING_ZONE": "接合區",
    "OUTER_SURFACE": "外表面",
    "WRAP_ZONE": "包覆區",
    "rear_edge": "後側邊",
    "rear_mating": "後側接合區",
    "top_edge": "上側邊",
    "bottom_edge": "下側邊",
    "left_edge": "左側邊",
    "right_edge": "右側邊",
    "top_mating_zone": "上側接合區",
    "bottom_mating_zone": "下側接合區",
    "left_mating_zone": "左側接合區",
    "right_mating_zone": "右側接合區",
    "ZERO": "零間隙",
    "USER_ADDED": "使用者新增",
    "LEGACY_MIGRATED": "舊資料轉入",
    "CERTIFIED": "已認證",
    "CERTIFIED_FROM_3D": "立體驗證認證",
    "PROVISIONAL_3D": "立體暫定",
    "ENGINE_CONFLICT": "引擎衝突",
    "REGISTRY_AMBIGUOUS": "規則不明確",
    "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1": "封頭尾上方嵌入（結構接合）",
    "ENDCAP_TOP_INSERT_STANDARD_V1": "封頭尾上方嵌入（標準）",
    "ENDCAP_TOP_OVERLAY_STANDARD_V1": "封頭尾上方貼外（標準）",
    "ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1": "封頭尾上方嵌入貼外（連動框寬）",
    "ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1": "封頭尾上方嵌入貼外（標準）",
    "RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",
    "RECEIVING_DIVIDER_CROSS_STANDARD_V1": "受電箱中隔十字截角（標準）",
    "ytop1_present": "有上折",
    "ytop1_absent": "無獨立上折",
    "ybottom1_present": "有下折",
    "x_folded": "橫向有折",
    "x_flat": "橫向平板",
}


def _phase6_is_derived_physical_part_key(value):
    key = str(value or "")
    return (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or _phase6_is_box_body_physical_piece_key(key)
        or key.startswith("box_body:divider:")
        or (key.startswith("inner_door:") and key.endswith("_frame"))
        or (key.startswith("inner_door:") and key.endswith(":panel"))
    )


def _phase6_part_label(value: object, *, snapshot=None) -> str:
    """Return the single Traditional-Chinese operator label for a part identity."""
    key = str(value or "")
    if key in PART_LABELS:
        return PART_LABELS[key]
    piece_labels = {
        "box_body:left_side": "左側板", "box_body:back": "後面板", "box_body:right_side": "右側板",
        "box_body_left_side": "左側板", "box_body_back": "後面板", "box_body_right_side": "右側板",
        "box_body:left": "左箱身", "box_body:middle": "中箱身", "box_body:right": "右箱身",
    }
    if key in piece_labels:
        return piece_labels[key]
    door_match = re.fullmatch(r"door_c(\d+)_r(\d+)", key)
    if door_match:
        col, row = (int(door_match.group(1)), int(door_match.group(2)))
        snap = dict(snapshot or {})
        model = str(snap.get("model") or snap.get("baseline_model") or snap.get("cabinet_family") or "")
        columns = list(snap.get("door_layout_columns") or ())
        if model == "受電箱" and len(columns) == 1 and col == 1:
            if row == 1:
                return "上門"
            if row == 2:
                return "下門"
        return f"第{col}欄第{row}門"
    base_match = re.fullmatch(r"base_plate_c(\d+)_r(\d+)", key)
    if base_match:
        col, row = (int(base_match.group(1)), int(base_match.group(2)))
        snap = dict(snapshot or {})
        model = str(snap.get("model") or snap.get("baseline_model") or snap.get("cabinet_family") or "")
        columns = list(snap.get("door_layout_columns") or ())
        if model == "受電箱" and len(columns) == 1 and col == 1:
            if row == 1:
                return "上門底板"
            if row == 2:
                return "下門底板"
        return f"第{col}欄第{row}門底板"
    if key.startswith("box_body:divider:"):
        axis = "橫向" if ":HORIZONTAL:" in key else ("直向" if ":VERTICAL:" in key else "")
        return f"箱身中隔（{axis}）" if axis else "箱身中隔"
    if key.startswith("inner_door:") and key.endswith(":panel"):
        door_id = key.split(":", 2)[1]
        door_label = {"upper": "上層內門", "lower": "下層內門"}.get(door_id, "內門")
        return f"{door_label}門板"
    if key.startswith("inner_door:") and key.endswith("_frame"):
        side = key.rsplit(":", 1)[-1].removesuffix("_frame")
        side_label = {"top": "上框", "bottom": "下框", "left": "左框", "right": "右框"}.get(side, "框")
        door_id = key.split(":", 2)[1]
        door_label = {"upper": "上層內門", "lower": "下層內門"}.get(door_id, "內門")
        return f"{door_label}{side_label}"
    return key


def _phase6_operator_label(value, *, snapshot=None):
    raw = str(value or "")
    label = _phase6_part_label(raw, snapshot=snapshot)
    if label != raw:
        return label
    return _PHASE6_OPERATOR_LABELS.get(raw, raw)


def _phase6_operator_text(value):
    text = str(value or "")
    # Longer tokens first so INSERT_OVERLAY is not partially replaced by INSERT.
    replacements = sorted(_PHASE6_OPERATOR_LABELS.items(), key=lambda item: len(item[0]), reverse=True)
    for raw, label in replacements:
        text = text.replace(raw, label)
    for raw, label in PART_LABELS.items():
        text = text.replace(raw, label)
    return text


_PHASE6_PRESENTATION_FALLBACK = "未定義項目（代碼已記錄）"
_PHASE6_PRESENTATION_EMPTY = "未定義項目"
_PHASE6_PRESENTATION_LOG = logging.getLogger("whd.corner_presentation")


def _phase6_fail_closed_visible_text(
    candidate,
    *,
    raw_value,
    presentation_field,
    source_adapter,
):
    """Return Chinese/numeric presentation text or a diagnostic fail-closed fallback."""
    visible = str(candidate or "").strip()
    raw = str(raw_value or "")
    if not visible:
        return _PHASE6_PRESENTATION_EMPTY
    if re.search(r"[A-Za-z]", visible):
        _PHASE6_PRESENTATION_LOG.warning(
            "corner_presentation_fallback presentation_field=%s raw_value=%s source_adapter=%s",
            str(presentation_field or "unknown"),
            raw,
            str(source_adapter or "unknown"),
        )
        return _PHASE6_PRESENTATION_FALLBACK
    return visible


def _phase6_registry_present_token(
    value,
    *,
    presentation_field="value",
    source_adapter="registry_token",
    snapshot=None,
):
    """Strict presentation adapter; never expose an unmapped raw English enum/key."""
    raw = str(value or "")
    if not raw.strip():
        return _PHASE6_PRESENTATION_EMPTY
    candidate = _phase6_operator_label(raw, snapshot=snapshot)
    return _phase6_fail_closed_visible_text(
        candidate,
        raw_value=raw,
        presentation_field=presentation_field,
        source_adapter=source_adapter,
    )


_PHASE6_FORMULA_DISPLAY_TOKENS = {
    "effective_mating_width": "有效接合寬",
    "mating_width": "成型接合寬",
    "side_fold": "側折",
    "rear_bend": "後折",
    "reserve_u": "橫向預留",
    "reserve_v": "縱向預留",
    "ybottom1": "下折",
    "ytop1": "上折",
    "clearance": "間隙",
    "fold_u": "橫向折邊",
    "fold_v": "縱向折邊",
    "FW": "框寬",
    "T": "板厚",
}


def _phase6_formula_display(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_FORMULA_DISPLAY_TOKENS.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(raw)}(?![A-Za-z0-9_])", label, text)
    return text


def _phase6_formula_raw(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_FORMULA_DISPLAY_TOKENS.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(label, raw)
    return text


def _phase6_registry_formula_display(value, *, presentation_field="formula"):
    raw = str(value or "")
    candidate = _phase6_formula_display(raw)
    return _phase6_fail_closed_visible_text(
        candidate,
        raw_value=raw,
        presentation_field=presentation_field,
        source_adapter="registry_formula",
    )


def _phase6_preconditions_display(value):
    tokens = [token.strip() for token in str(value or "").split(",") if token.strip()]
    return "、".join(
        _phase6_registry_present_token(
            token,
            presentation_field="precondition",
            source_adapter="registry_preconditions",
        )
        for token in tokens
    )


def _phase6_preconditions_raw(value):
    reverse = {label: raw for raw, label in _PHASE6_OPERATOR_LABELS.items()}
    tokens = [token.strip() for token in re.split(r"[,，、]", str(value or "")) if token.strip()]
    return ",".join(reverse.get(token, token) for token in tokens)


_PHASE6_SOURCE_DISPLAY_TOKENS = {
    "CornerType": "截角類型",
    "linked-FW": "連動框寬",
    "STANDARD": "標準",
    "manufacturing": "製造",
    "contract": "契約",
    "projection": "投影",
    "Registry": "資料庫",
    "formed": "成形",
    "shadow": "陰影",
    "evidence": "證據",
    "CROSS": "十字",
    "C04": "型號04",
    "X/Y": "橫向／縱向",
    "1T": "1板厚",
    ".dxf": "圖檔",
    "band": "帶區",
    "base": "基底",
    "face": "面",
    "HIT": "命中",
    "mm": "毫米",
    "3D": "立體",
    "2D": "平面",
}


def _phase6_source_display(value):
    text = str(value or "")
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(raw, label)
    text = _phase6_operator_text(text)
    text = _phase6_formula_display(text)
    return text


def _phase6_source_raw(value):
    text = str(value or "")
    # Reverse source-specific phrases first so compound labels are not partially
    # consumed by the generic formula aliases.
    for raw, label in sorted(_PHASE6_SOURCE_DISPLAY_TOKENS.items(), key=lambda item: len(item[1]), reverse=True):
        text = text.replace(label, raw)
    reverse_operator = sorted(
        ((label, raw) for raw, label in _PHASE6_OPERATOR_LABELS.items()),
        key=lambda item: len(item[0]), reverse=True,
    )
    for label, raw in reverse_operator:
        text = text.replace(label, raw)
    reverse_parts = sorted(
        ((label, raw) for raw, label in PART_LABELS.items()),
        key=lambda item: len(item[0]), reverse=True,
    )
    for label, raw in reverse_parts:
        text = text.replace(label, raw)
    return _phase6_formula_raw(text)


def _phase6_registry_source_display(value, *, presentation_field="source"):
    raw = str(value or "")
    candidate = _phase6_source_display(raw)
    return _phase6_fail_closed_visible_text(
        candidate,
        raw_value=raw,
        presentation_field=presentation_field,
        source_adapter="registry_source",
    )




def _phase6_registry_collect_rule_form(self):
    intent = str(self.relief_registry_intent_var.get() or "INSERT_OVERLAY")
    topology = int(float(self.relief_registry_topology_var.get() or (2 if intent == "INSERT_OVERLAY" else 1)))
    main_target = str(self.relief_registry_target_role_var.get() or "BOX_SIDE")
    region = str(self.relief_registry_joint_face_var.get() or "TOP")
    signature = [{
        "relation": intent,
        "subject_role": str(self.relief_registry_part_role_var.get() or "HEAD_OR_TAIL"),
        "target_role": main_target,
        "subject_region": region,
        "target_region": "MATING_ZONE" if intent != "OVERLAY" else "OUTER_SURFACE",
    }]
    extra = str(self.relief_registry_extra_joint_var.get() or "NONE")
    if extra != "NONE":
        signature.append({
            "relation": extra,
            "subject_role": str(self.relief_registry_part_role_var.get() or "HEAD_OR_TAIL"),
            "target_role": str(self.relief_registry_extra_target_role_var.get() or "REAR_PANEL"),
            "subject_region": region,
            "target_region": "WRAP_ZONE" if extra == "WRAP" else "MATING_ZONE",
        })
    formula = {
        "primary_u": str(self.relief_registry_primary_u_var.get()).strip(),
        "primary_v": str(self.relief_registry_primary_v_var.get()).strip(),
    }
    if topology == 2:
        formula["secondary_u"] = str(self.relief_registry_secondary_u_var.get()).strip()
        formula["secondary_depth"] = str(self.relief_registry_secondary_depth_var.get()).strip()
    preconditions = [v.strip() for v in str(self.relief_registry_preconditions_var.get() or "").split(",") if v.strip()]
    return {
        "rule_id": str(self.relief_registry_rule_id_var.get() or "").strip(),
        "cabinet_family": str(self.relief_registry_family_var.get() or "ANY").strip(),
        "part_role": str(self.relief_registry_part_role_var.get() or "HEAD_OR_TAIL").strip(),
        "joint_face": region,
        "assembly_intent": intent,
        "joint_signature": signature,
        "topology_levels": topology,
        "preconditions": preconditions,
        "formula": formula,
        "symmetry": str(self.relief_registry_symmetry_var.get() or "MIRROR_IF_GEOMETRY_SYMMETRIC"),
        "source": str(self.relief_registry_source_var.get() or "").strip(),
    }


def _phase6_registry_sample_variables(self):
    values = {}
    mapping = {
        "T": self.relief_registry_sample_t_var,
        "FW": self.relief_registry_sample_fw_var,
        "side_fold": self.relief_registry_sample_side_var,
        "ytop1": self.relief_registry_sample_ytop_var,
        "mating_width": self.relief_registry_sample_mating_var,
    }
    for key, var in mapping.items():
        values[key] = float(var.get())
    values["effective_mating_width"] = values["mating_width"]
    values["fold_u"] = values["side_fold"]
    values["fold_v"] = values["ytop1"]
    values["clearance"] = 0.0
    return values


def _phase6_registry_validate_formula_form(self):
    from ae_engine.certified_relief_registry import (
        evaluate_relief_formula_record,
        _validate_editable_rule_record,
    )
    controller = _phase6_registry_diagnostics(self)
    try:
        result = controller.validate_formula(
            _phase6_registry_collect_rule_form(self),
            _phase6_registry_sample_variables(self),
            validator=_validate_editable_rule_record,
            evaluator=evaluate_relief_formula_record,
        )
        text = f"公式有效：{result['primary_u']:.3f}×{result['primary_v']:.3f}"
        if result.get("secondary_u") is not None:
            text += (
                f" + {result['secondary_u']:.3f}"
                f"×{result['secondary_depth']:.3f}"
            )
        self.relief_registry_status_var.set(text)
        self._phase6_last_rule_form_result = result
        return result
    except Exception as exc:
        self.relief_registry_status_var.set(f"公式錯誤：{exc}")
        self._phase6_last_rule_form_result = None
        return None

def _phase6_registry_save_candidate_form(self):
    from ae_engine.certified_relief_registry import save_relief_rule_candidate
    result = _phase6_registry_validate_formula_form(self)
    if result is None:
        return None
    try:
        record = _phase6_registry_collect_rule_form(self)
        controller = _phase6_registry_diagnostics(self)
        item = controller.save_candidate(
            record,
            saver=save_relief_rule_candidate,
        )
        _phase6_sync_registry_diagnostics_compatibility_mirrors(
            self, controller
        )
        self.relief_registry_status_var.set("候選已儲存（尚未認證）")
        return item
    except Exception as exc:
        self.relief_registry_status_var.set(f"候選儲存失敗：{exc}")
        return None

def _phase6_registry_run_formula_matrix(self):
    from ae_engine.certified_relief_registry import (
        evaluate_relief_formula_record,
        _validate_editable_rule_record,
    )
    try:
        controller = _phase6_registry_diagnostics(self)
        evidence = controller.run_formula_matrix(
            _phase6_registry_collect_rule_form(self),
            _phase6_registry_sample_variables(self),
            validator=_validate_editable_rule_record,
            evaluator=evaluate_relief_formula_record,
        )
        _phase6_sync_registry_diagnostics_compatibility_mirrors(
            self, controller
        )
        self.relief_registry_status_var.set(
            f"公式矩陣通過：{evidence['cases']} 組；立體零穿透="
            + ("是" if evidence.get("zero_penetration") else "尚未")
        )
        return evidence
    except Exception as exc:
        self.relief_registry_status_var.set(f"回歸失敗：{exc}")
        return None

def _phase6_registry_validate_candidate_3d(self, record, *, candidate_id):
    """Shadow-validate exactly one editable candidate without mutating the registry."""
    from ae_engine.certified_relief_registry import evaluate_editable_endcap_rule_record, _validate_editable_rule_record
    from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief

    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise ValueError("candidate-specific 3D validation requires candidate_id")
    raw = _validate_editable_rule_record(record)
    intent = str(raw.get("assembly_intent") or "").strip()
    current_intent = str(getattr(getattr(self, "_phase6_assembly_type", None), "value", getattr(self, "_phase6_assembly_type", "")) or "")
    if current_intent and intent and current_intent != intent:
        raise ValueError(f"candidate assembly_intent={intent} does not match current assembly={current_intent}")

    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        raise RuntimeError("3D final-scene provider is not connected")
    available = set(getattr(getattr(self, "designer_workspace", None), "available_parts", ()) or ())
    if "box_body" not in available:
        raise ValueError("candidate-specific 3D validation requires box_body")

    def _base_part(part_key):
        payload = _phase6_scene_query_payload_for_part(self, part_key)
        payload["_use_committed_relief"] = False
        render_data = callback(part_key, payload)
        if render_data is None or getattr(render_data, "material", None) is None:
            raise ValueError(f"candidate validation render data unavailable: {part_key}")
        x_profile, y_profile = _phase6_mesh_profiles_for_part(self, part_key, render_data.material)
        return render_data, tuple(dict(seg) for seg in x_profile), tuple(dict(seg) for seg in y_profile)

    body_render, body_x, _body_y = _base_part("box_body")
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    settings = dict(getattr(self, "_settings_values", {}) or {})
    thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
    dims = _phase6_operator_finished_dimensions(self)
    clearance = _phase6_assembly_relief_clearance(self)
    solutions = {}
    validated_parts = []
    for part_key in ("head", "tail"):
        if part_key not in available:
            continue
        end_render, end_x, end_y = _base_part(part_key)
        ephemeral = evaluate_editable_endcap_rule_record(
            raw,
            endcap_render_data=end_render,
            box_body_x_profile=body_x,
            endcap_x_profile=end_x,
            endcap_y_profile=end_y,
            sheet_thickness=thickness,
        )
        if ephemeral is None:
            raise ValueError(f"candidate formula does not apply to {part_key}")
        solution = solve_world_backprojected_endcap_relief(
            box_body_render_data=body_render,
            endcap_render_data=end_render,
            box_body_x_profile=body_x,
            endcap_x_profile=end_x,
            endcap_y_profile=end_y,
            finished_dimensions=dims,
            endcap_placement=_PHASE6_ASSEMBLY_PLACEMENTS.get(part_key, "top" if part_key == "head" else "bottom"),
            sheet_thickness=thickness,
            clearance=clearance,
            assembly_intent=intent,
            cabinet_family=_phase6_current_cabinet_family(self),
            allow_3d_fallback=False,
            certified_result_override=ephemeral,
        )
        validated_parts.append(part_key)
        solutions[part_key] = {
            "verified": bool(getattr(solution, "verified", False)),
            "trust_level": str(getattr(solution, "trust_level", "") or ""),
            "rule_id": getattr(solution, "rule_id", None),
            "rule_revision": getattr(solution, "rule_revision", None),
            "residual_pair_count": int(getattr(getattr(solution, "residual_projection", None), "pair_count", 0) or 0),
        }

    zero = bool(validated_parts) and all(bool(item["verified"]) for item in solutions.values())
    return {
        "candidate_specific": True,
        "candidate_id": candidate_id,
        "zero_penetration": bool(zero),
        "validated_parts": validated_parts,
        "solutions": solutions,
    }


def _phase6_registry_preview_assembly_3d(self):
    controller = _phase6_registry_diagnostics(self)
    try:
        candidate_id = controller.require_current_candidate(
            _phase6_registry_collect_rule_form(self)
        )
        record = controller.candidate_record
        evidence3d = _phase6_registry_validate_candidate_3d(
            self, record, candidate_id=candidate_id
        )
        evidence = controller.merge_3d_evidence(evidence3d)
        _phase6_sync_registry_diagnostics_compatibility_mirrors(
            self, controller
        )
        zero = bool(evidence.get("zero_penetration"))
        self.relief_registry_status_var.set(
            "候選專屬立體組合驗證："
            + ("零非法穿透" if zero else "仍有非法穿透")
        )
        return zero
    except Exception as exc:
        self.relief_registry_status_var.set(f"立體組合驗證失敗：{exc}")
        return False

def _phase6_registry_promote_form(self):
    from ae_engine.certified_relief_registry import promote_relief_rule_candidate
    controller = _phase6_registry_diagnostics(self)
    try:
        promoted = controller.promote_candidate(
            _phase6_registry_collect_rule_form(self),
            promoter=promote_relief_rule_candidate,
        )
        self.relief_registry_status_var.set(
            f"已認證新版次：{promoted['revision']}"
        )
        _phase6_registry_refresh_rule_tree(self)
        return promoted
    except Exception as exc:
        message = str(exc)
        if message in {
            "請先儲存候選",
            "表單已變更；請重新儲存候選後再驗證",
        }:
            self.relief_registry_status_var.set(message)
        else:
            self.relief_registry_status_var.set(f"不可認證：{exc}")
        return None

def _phase6_joint_form_add(self):
    controller = _phase6_registry_diagnostics(self)
    try:
        row = controller.route_joint_add(
            lambda **kwargs: _phase6_add_user_joint(self, **kwargs),
            subject_part=self.relief_joint_subject_var.get(),
            target_part=self.relief_joint_target_var.get(),
            relation=self.relief_joint_relation_var.get(),
            subject_region=self.relief_joint_subject_region_var.get(),
            target_region=self.relief_joint_target_region_var.get(),
            clearance_policy=self.relief_joint_clearance_var.get(),
            solver_constraints={
                "topology_levels": int(self.relief_joint_topology_var.get())
            },
        )
        self.relief_joint_status_var.set(
            (
                "外側包覆：主動板件包覆接合板件；"
                if row["relation"] == "WRAP"
                else ""
            )
            + "已新增接合規則"
        )
        _phase6_joint_form_refresh(self)
        return row
    except Exception as exc:
        self.relief_joint_status_var.set(f"新增失敗：{exc}")
        return None

def _phase6_joint_form_delete(self):
    tree = getattr(self, "relief_joint_tree", None)
    if tree is None or not tree.selection():
        self.relief_joint_status_var.set("請先選擇接合規則")
        return False
    joint_id = tree.selection()[0]
    try:
        result = _phase6_registry_diagnostics(self).route_joint_delete(
            lambda value: _phase6_delete_user_joint(self, value),
            joint_id,
        )
        self.relief_joint_status_var.set(
            "已刪除" if result else "找不到接合規則"
        )
        _phase6_joint_form_refresh(self)
        return result
    except Exception as exc:
        self.relief_joint_status_var.set(f"不可刪除：{exc}")
        return False


def _phase6_status_projection(self):
    """Project existing cabinet/part/view owners into one low-noise status line."""
    family = _phase6_current_cabinet_family(self) or "-"
    mode = str(getattr(self, "_phase6_3d_display_mode", "single") or "single")
    if mode == "corner_data":
        part_key = (
            getattr(self, "_phase6_corner_data_selected_part_key", None)
            or getattr(self, "active_part_key", None)
        )
    else:
        part_key = getattr(self, "active_part_key", None)
    part_text = _phase6_part_label(part_key) if part_key else "-"
    return Phase6ProjectController.project_status_projection(
        family=family,
        mode=mode,
        part_text=part_text,
    )

def _phase6_refresh_status_bar(self):
    """Refresh the projection sink only; never write selection/domain state."""
    text = _phase6_status_projection(self)
    var = getattr(self, "status_projection_var", None)
    if var is not None and hasattr(var, "set"):
        var.set(text)
    return text

# Compatibility routing only: concrete Tk construction lives in
# phase6_registry_diagnostics_panel.py.
_phase6_form_choice = lambda parent, variable, choices, width=18, presentation_field="choice": build_registry_choice(
    parent,
    variable,
    choices,
    present_token=_phase6_registry_present_token,
    width=width,
    presentation_field=presentation_field,
)
_phase6_registry_preview_2d = lambda self: _phase6_registry_panel(self).draw_registry_preview()
_phase6_registry_refresh_rule_tree = lambda self: _phase6_registry_panel(self).refresh_rule_rows()
_phase6_registry_rule_selected = lambda self, *_args: _phase6_registry_panel(self).populate_rule_form()
_phase6_joint_form_refresh = lambda self: _phase6_registry_panel(self).refresh_joint_rows()
_phase6_open_relief_registry_form = lambda self: _phase6_registry_panel(self).open_registry_editor()
_phase6_refresh_joint_diagnostic_menu = lambda self, resolved=None: _phase6_registry_panel(self).refresh_joint_diagnostic_menu(resolved)
_phase6_build_assembly_diagnostics = lambda self: _phase6_registry_panel(self).build_assembly_diagnostics(self.right)


def _phase6_keyboard_save(self, _event=None):
    """Ctrl+S delegates to the existing project-save authority."""
    self.save_project_file()
    return "break"


def _phase6_keyboard_open(self, _event=None):
    """Ctrl+O delegates to the existing project-open authority."""
    self.load_project_file()
    return "break"


def _phase6_keyboard_fullscreen(self, _event=None):
    """F11 delegates to the existing fullscreen presentation action."""
    _phase6_toggle_fullscreen(self)
    return "break"



def _phase6_hide_original_visual_controls(root_widget):
    for child in root_widget.winfo_children():
        try:
            text = str(child.cget("text"))
        except Exception:
            text = ""
        if "3D 視覺調整" in text:
            manager = child.winfo_manager()
            if manager == "pack":
                child.pack_forget()
            elif manager == "grid":
                child.grid_remove()
            return True
    return False


def _phase6_toggle_fullscreen(self):
    enabled, geometry = _workspace_shell_toggle_fullscreen(
        self.root,
        getattr(self, "fullscreen_button", None),
        enabled=bool(getattr(self, "_phase6_fullscreen", False)),
        restore_geometry=getattr(self, "_phase6_restore_geometry", None),
    )
    self._phase6_fullscreen = bool(enabled)
    self._phase6_restore_geometry = geometry
    return self._phase6_fullscreen

def _phase6_workspace_shell_owner(self):
    return _phase6_composition(self).workspace_shell_owner(globals())

def _phase6_apply_workspace_shell_bindings(self, owner):
    for name, value in owner.compatibility_bindings().items():
        setattr(self, name, value)


def _phase6_build_persistent_top_area(self):
    owner = _phase6_workspace_shell_owner(self)
    owner.build_persistent_top_area()
    _phase6_apply_workspace_shell_bindings(self, owner)

def _phase6_reset_initial_values(self):
    """Restore immutable AE factory defaults through the Settings coordinator."""
    self.flush_pending_settings()
    return _phase6_settings_coordinator(self).reset_factory_settings(
        getattr(self, "_factory_defaults", {}) or {}
    )

def _phase6_scene_query_payload_for_part(self, part_key):
    """Compatibility wrapper for the manufacturing adapter-owned payload builder."""
    return build_scene_payload_for_app(self, part_key)
def _phase6_query_final_render_data(self):
    """Compatibility delegate to the T6 final-scene view adapter."""
    return _phase6_final_scene_adapter(self).query_final_render_data()

def _phase6_mesh_profiles_for_part(self, part_key, material):
    key = str(part_key or "")
    if key == "box_body":
        x_profile = list((getattr(self.state, "profiles_vault", {}) or {}).get("箱身", ()) or ())
        minx, miny, maxx, maxy = material.bounds
        return x_profile, [{"len": float(maxy - miny)}]
    if key == self.designer_workspace.active_part:
        profiles = getattr(self.state, "profiles", {}) or {}
    else:
        profiles = self.designer_workspace.profiles_for(key, {}) or {}
    x_prof = list(profiles.get("X", ()))
    y_prof = list(profiles.get("Y", ()))
    if key.startswith("box_body:divider:") or (key.startswith("inner_door:") and key.endswith("_frame")):
        minx, miny, maxx, maxy = material.bounds
        if x_prof and not y_prof:
            y_prof = [{"len": float(maxy - miny)}]
        elif y_prof and not x_prof:
            x_prof = [{"len": float(maxx - minx)}]
    return x_prof, y_prof



def _phase6_on_3d_scroll(self, event):
    return _phase6_final_scene_adapter(self).on_scroll(event)


def _phase6_install_renderer_view(self):
    result = _phase6_final_scene_adapter(self).install_renderer()
    try:
        self.renderer.canvas.get_tk_widget().configure(takefocus=False)
    except Exception:
        pass
    return result




def _phase6_render_data_for_blank(self, part_key=None):
    """Return canonical final material for blank reporting without a second geometry path."""
    key = str(part_key or self.designer_workspace.active_part or "")
    if not key:
        return None
    active = str(getattr(getattr(self, "designer_workspace", None), "active_part", "") or "")
    if key == active:
        return _phase6_query_final_render_data(self)
    if (
        key in {"box_body", "head", "tail"}
        or key.startswith("box_body:divider:")
    ):
        # Divider CROSS relief and Joint Placement MARKING are derived during
        # resolved manufacturing.  Corner Data may select a Divider without
        # changing workspace.active_part, so never fall back to its raw scene.
        return _phase6_resolve_manufacturing_geometry(self).part(key).render_data
    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        return None
    return callback(key, _phase6_scene_query_payload_for_part(self, key))


def _phase6_format_unfolded_blank_text(render_data, *, part_key=""):
    from ae_engine.manufacturing_api import measure_unfolded_blanks

    return Phase6CornerDataViewAdapter.unfolded_blank_text(
        render_data,
        part_key=part_key,
        measurer=measure_unfolded_blanks,
        number_text=_setting_number_text,
    )


_PHASE6_DEFAULT_VIEW = (50.0, -90.0)


def _phase6_prepare_text_scale_controller(root, value, *, controller=None):
    """Reuse the main GUI text scale without rescanning its whole widget tree."""
    controller = controller or TextScaleController.for_widget(root)
    # When Phase6 is a Toplevel, for_widget() returns the already-applied main
    # controller whose root is the main window. Calling apply() here would walk
    # every main-GUI widget again just to open 3D. A standalone Phase6 root still
    # owns its controller and therefore applies the requested size once.
    if getattr(controller, "root", None) is root:
        controller.apply(value)
    return controller




def _phase6_operator_finished_dimensions(self, part_key=None, *, triangles=None):
    """Compatibility wrapper for adapter-owned finished dimensions."""
    return operator_finished_dimensions_for_app(
        self,
        part_key,
        triangles=triangles,
    )
def _phase6_on_assembly_diagnostic_changed(self):
    if str(getattr(self, "_phase6_3d_display_mode", "single") or "single") == "assembly":
        self.do_update()
    return True


def _phase6_create_relief_promotion_candidates(self):
    """Build non-mutating manifests for verified PROVISIONAL_3D solutions."""
    from ae_engine.certified_relief_registry import build_relief_promotion_candidate

    controller = _phase6_registry_diagnostics(self)
    candidates = controller.build_promotion_candidates(
        solutions=dict(getattr(self, "_phase6_last_relief_solutions", {}) or {}),
        snapshot=dict(getattr(self, "_phase6_input_snapshot", {}) or {}),
        assembly_intent=getattr(
            self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY
        ),
        cabinet_family=_phase6_current_cabinet_family(self),
        builder=build_relief_promotion_candidate,
    )
    _phase6_sync_registry_diagnostics_compatibility_mirrors(
        self, controller
    )
    status_var = getattr(self, "assembly_collision_status_var", None)
    if status_var is not None and callable(getattr(status_var, "set", None)):
        if candidates:
            status_var.set(
                "認證候選："
                + " / ".join(
                    "封頭" if key == "head" else "封尾"
                    for key in candidates
                )
                + "（僅建立候選，不修改正式資料庫）"
            )
        else:
            status_var.set("認證候選：目前沒有已驗證的立體暫定結果")
    return candidates

def _phase6_update_assembly_diagnostic_status(self):
    status_var = getattr(self, "assembly_collision_status_var", None)
    size_var = getattr(self, "assembly_relief_size_var", None)
    if status_var is None:
        return

    enabled_var = getattr(self, "assembly_ignore_fixed_corner_var", None)
    fallback_enabled = bool(enabled_var.get()) if enabled_var is not None else True
    size_text, status_text = _phase6_registry_diagnostics(self).diagnostic_status(
        fallback_enabled=fallback_enabled,
        solutions=dict(getattr(self, "_phase6_last_relief_solutions", {}) or {}),
        errors=dict(getattr(self, "_phase6_last_relief_errors", {}) or {}),
        measurement_text=_phase6_relief_measurement_text,
    )
    if size_var is not None:
        size_var.set(size_text)
    status_var.set(status_text)

def _phase6_build_settings_center(self):
    renderer_widget = self.renderer.canvas.get_tk_widget()
    renderer_widget.pack_forget()
    panel = _phase6_ensure_settings_panel(self)
    panel.build_settings_center(self.right)
    _phase6_build_assembly_diagnostics(self)
    renderer_widget.pack(fill=original.tk.BOTH, expand=True)
    _phase6_sync_settings_panel_compat(self)


def _phase6_refresh_persistent_structure_controls(self):
    state = _phase6_box_structure_state(self)
    active = BoxBodyStructureType(state["active_type"])
    var = getattr(self, "structure_type_var", None)
    if var is not None:
        value = _BOX_STRUCTURE_LABELS[active]
        if var.get() != value:
            var.set(value)
    button = getattr(self, "structure_choice_button", None)
    if button is not None:
        fixed_family = cabinet_family_policy.family_fixes_box_body_structure(
            getattr(self, "_phase6_input_snapshot", {}) or {}
        )
        button.configure(state=("disabled" if fixed_family else "normal"))

    assembly_var = getattr(self, "assembly_type_var", None)
    if assembly_var is not None:
        label = ASSEMBLY_TYPE_LABELS[getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)]
        if assembly_var.get() != label:
            assembly_var.set(label)


def _phase6_pack_right_panel_above_canvas(self, widget):
    """Pack a right-side settings/diagnostic panel before the expanding 3D canvas.

    Tk pack order matters: if the canvas is already packed with fill=BOTH and
    expand=True, packing a settings frame afterwards can leave the frame at
    1x1 pixels even though winfo_manager() reports "pack".
    """
    if widget is None:
        return False
    canvas_widget = self.renderer.canvas.get_tk_widget()
    options = dict(side=original.tk.TOP, fill=original.tk.X, pady=(0, 6))
    if canvas_widget.winfo_manager() == "pack" and canvas_widget.master is widget.master:
        widget.pack(before=canvas_widget, **options)
    else:
        widget.pack(**options)
    return True


def _hide_original_structure_mode_controls(root_widget):
    """Hide only the prototype's user-visible mode chooser; keep its internals."""
    targets = {"標準十字型", "金庫型(三件)", "結構:"}
    for child in root_widget.winfo_children():
        try:
            text = str(child.cget("text"))
        except Exception:
            text = ""
        if text in targets:
            manager = child.winfo_manager()
            if manager == "pack":
                child.pack_forget()
            elif manager == "grid":
                child.grid_remove()
            elif manager == "place":
                child.place_forget()
        _hide_original_structure_mode_controls(child)


def _phase6_on_assembly_part_visibility_changed(self):
    if str(getattr(self, "_phase6_3d_display_mode", "single") or "single") == "assembly":
        self.do_update()


def _phase6_install_assembly_panel_aliases(self, owner):
    """Expose rebuild-safe legacy handles for existing callers/tests."""
    self.assembly_parts_panel = owner.host
    self.assembly_parts_canvas = owner.canvas
    self.assembly_parts_scrollbar = owner.scrollbar
    self.assembly_parts_content = owner.content
    self._assembly_parts_window = owner.window_id

    self.assembly_part_visible_vars = owner.visible_vars
    self.assembly_part_corner_vars = owner.corner_vars
    self.assembly_part_formed_vars = owner.formed_vars
    self.assembly_part_blank_vars = owner.blank_vars
    self.assembly_part_checkbuttons = owner.checkbuttons
    self.assembly_part_sections = owner.sections
    self.assembly_part_detail_frames = owner.detail_frames
    self.assembly_part_detail_buttons = owner.detail_buttons
    self.assembly_presentation_group_sections = owner.group_sections
    self.assembly_presentation_group_detail_frames = owner.group_detail_frames
    self.assembly_presentation_group_detail_buttons = owner.group_detail_buttons
    self._phase6_assembly_part_detail_open_stash = owner.detail_open_stash
    self._phase6_assembly_presentation_group_open_stash = owner.group_open_stash

    self.assembly_box_body_piece_labels = owner.box_piece_labels
    self.assembly_box_body_piece_sections = owner.box_piece_sections
    self.assembly_box_body_piece_visible_vars = owner.box_piece_visible_vars
    self.assembly_box_body_piece_checkbuttons = owner.box_piece_checkbuttons
    self.assembly_box_body_piece_detail_frames = owner.box_piece_detail_frames
    self.assembly_box_body_piece_detail_buttons = owner.box_piece_detail_buttons
    self.assembly_box_body_piece_formed_vars = owner.box_piece_formed_vars
    self.assembly_box_body_piece_blank_vars = owner.box_piece_blank_vars
    self.assembly_box_body_piece_corner_vars = owner.box_piece_corner_vars
    self._phase6_box_body_piece_visibility_stash = owner.box_piece_visibility_stash
    self._phase6_box_body_piece_detail_open_stash = owner.box_piece_detail_open_stash


_phase6_assembly_presentation_groups = legacy_assembly_presentation_groups

def _phase6_current_assembly_panel_part_keys(self) -> tuple[str, ...]:
    """Return the part-key topology currently represented by assembly rows."""
    return tuple(dict(getattr(self, "assembly_part_visible_vars", {}) or {}))


def _phase6_refresh_assembly_parts_panel_if_topology_changed(self) -> bool:
    """Rebuild assembly rows only when authoritative workspace topology changed."""
    if getattr(self, "assembly_parts_panel", None) is None:
        return False
    current = _phase6_current_assembly_panel_part_keys(self)
    wanted = _phase6_operator_part_selector_keys(
        getattr(_designer_workspace(self), "available_parts", ()) or ()
    )
    if current == wanted:
        return False
    _phase6_refresh_assembly_parts_panel(self)
    return True


def _phase6_refresh_assembly_parts_panel(self):
    owner = getattr(self, "_phase6_assembly_panel_owner", None)
    if owner is None:
        return

    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    model = build_assembly_presentation_model(
        getattr(_designer_workspace(self), "available_parts", ()) or (),
        label_for=lambda key: _phase6_part_label(key, snapshot=snapshot),
    )
    owner.render(model)

    # The host widget is recreated with the logical BoxBody row. Registry and
    # stash aliases remain the same long-lived panel-owned dict objects.
    self.assembly_box_body_piece_host = owner.box_body_piece_host


# Patch methods onto the FIX10 class instead of touching the user's original file.
_FIX10_INIT = Phase6FoldDesignerApp.__init__
_FIX10_EXPORT = Phase6FoldDesignerApp.export_phase6_snapshot


def _phase6_bootstrap_authoritative_state(self, snapshot):
    # Phase 4 composition services may be reached by inherited Tk callbacks
    # during construction. Establish the authoritative mapping identities before
    # any such callback can ask the composition root for Settings owners. From
    # here onward these mappings are mutated in place; they are never rebound.
    _phase6_replace_mapping(self, "_settings_values", {})
    _phase6_replace_mapping(self, "_phase6_input_snapshot", {})
    _phase6_replace_mapping(self, "_phase6_box_whd", {})
    _phase6_replace_mapping(self, "_phase6_pending_settings", {})
    snapshot = _phase6_snapshot_with_settings_fallback(
        migrate_legacy_snapshot_joints(dict(snapshot or {}))
    )
    initial_parts, initial_active = normalize_part_selection(
        snapshot.get("existing_parts", ("box_body", "head", "tail")),
        snapshot.get("active_part"),
    )
    workspace_snapshot = dict(snapshot)
    workspace_snapshot["existing_parts"] = list(initial_parts)
    workspace_snapshot["active_part"] = initial_active
    workspace_snapshot["part_features"] = {
        key: _copy_features(snapshot, key) for key in initial_parts
    }
    workspace_snapshot["part_face_features"] = deepcopy(
        dict(snapshot.get("part_face_features") or (snapshot.get("workspace") or {}).get("part_face_features") or {})
    )
    workspace_snapshot["assembly_placements"] = deepcopy(
        dict(snapshot.get("assembly_placements") or (snapshot.get("workspace") or {}).get("assembly_placements") or {})
    )
    self.designer_workspace = Phase6DesignerWorkspace.from_snapshot(workspace_snapshot)
    _phase6_replace_mapping(self, "_phase6_box_whd", {
        "w": _ui_len(snapshot.get("w", 500)),
        "h": _ui_len(snapshot.get("h", 600)),
        "d": _ui_len(snapshot.get("d", 200)),
    })
    return snapshot


def _phase6_install_runtime_ports(self, *, on_settings_change=None, on_save_defaults=None, on_corner_change=None, on_transaction_confirm=None, on_transaction_cancel=None, on_live_sync=None, on_baseline_data_query=None, on_scene_query=None, on_part_spec_query=None, on_ui_text_size_change=None, on_project_load=None, on_project_path_change=None, on_project_save=None, output_draw_stock_var=None, output_export_vars=None, on_export_selected_dxf=None):
    self._settings_change_callback = on_settings_change
    self._phase6_transactional_mode = on_transaction_confirm is not None and on_live_sync is None
    self._live_sync_callback = on_live_sync
    self._phase6_live_sync_guard = False
    self._phase6_last_live_payload = None
    self._phase6_last_live_state = None
    self._phase6_last_live_fingerprint = None
    self._phase6_sync_revision = 0
    self._save_defaults_callback = on_save_defaults
    # Kept only for backwards constructor compatibility. Corner edits are now
    # 這些資料採交易式提交，因此絕不能觸發這個舊版即時 callback。
    self._corner_change_callback = on_corner_change
    self._transaction_confirm_callback = on_transaction_confirm
    self._transaction_cancel_callback = on_transaction_cancel
    self._baseline_data_query_callback = on_baseline_data_query
    self._scene_query_callback = on_scene_query
    self._part_spec_query_callback = on_part_spec_query
    self._ui_text_size_change_callback = on_ui_text_size_change
    self._project_load_callback = on_project_load
    self._project_path_change_callback = on_project_path_change
    self._project_save_callback = on_project_save
    self._phase6_external_draw_stock_var = output_draw_stock_var
    self._phase6_external_export_vars = dict(output_export_vars or {})
    self._phase6_export_selected_dxf_callback = on_export_selected_dxf


def _phase6_prepare_predecessor_init(self, root, snapshot):
    self._phase6_box_body_active_piece_key = str(snapshot.get("box_body_active_piece") or "")
    self._phase6_current_project_path = str(snapshot.get("_runtime_project_path") or "").strip() or None
    self._factory_defaults = dict(snapshot.get("factory_defaults") or {})
    self._baseline_models = list(snapshot.get("baseline_models") or ())
    self._phase6_baseline_initial_model = normalize_custom_model_name(snapshot.get("model"))
    if self._phase6_baseline_initial_model and self._phase6_baseline_initial_model not in self._baseline_models:
        self._baseline_models.append(self._phase6_baseline_initial_model)
    self._baseline_unknown_value = str(snapshot.get("baseline_unknown_value") or CUSTOM_MODEL_NAME).strip()
    if self._baseline_unknown_value and self._baseline_unknown_value not in self._baseline_models:
        self._baseline_models.append(self._baseline_unknown_value)
    self._phase6_baseline_last_model = self._phase6_baseline_initial_model
    self._phase6_baseline_guard = False
    self._phase6_settings_guard = False
    self._phase6_corner_guard = False
    # UI-only fine-parameter locks. Never serialize into .p6fold.
    self._phase6_corner_param_unlocked = {}
    self.corner_pair_checkbuttons = {}
    _phase6_replace_mapping(self, "_phase6_pending_settings", {})
    self._phase6_settings_rendering = False
    _phase6_replace_mapping(
        self, "_settings_values", dict(snapshot.get("settings") or {})
    )
    for key, value in snapshot.items():
        if key not in self._settings_values and any(spec.key == key for spec in settings_for_context(GLOBAL_CONTEXT) + sum((settings_for_context(p) for p in KNOWN_PARTS), ())):
            self._settings_values[key] = value
    # Constructor top-level dimensions are the current authoritative application
    # state. Nested settings may be persisted defaults from an older save, so a
    # stale mirror must never win over the values the operator just entered.
    for key in ("w", "h", "d", "t", "fw"):
        if key in snapshot:
            self._settings_values[key] = snapshot[key]
    self._phase6_corner_state = deepcopy(snapshot.get("corner_state") or {})
    self._phase6_corner_pair_same = deepcopy(snapshot.get("corner_pair_same") or {})
    initial_assembly_type = resolve_box_assembly_type(snapshot)
    _phase6_replace_mapping(
        self,
        "_phase6_input_snapshot",
        dict(getattr(self, "_phase6_input_snapshot", {}) or snapshot),
    )
    self._phase6_input_snapshot.pop("_runtime_project_path", None)
    self._phase6_input_snapshot["assembly_type"] = assembly_intent_value(
        initial_assembly_type
    )
    self._phase6_endcap_fw_state = normalize_endcap_fw_state(snapshot)
    self._phase6_input_snapshot["endcap_fw"] = deepcopy(self._phase6_endcap_fw_state)
    self._phase6_endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state(snapshot)
    self._phase6_input_snapshot["endcap_bottom_wrap"] = deepcopy(self._phase6_endcap_bottom_wrap_state)
    self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
    self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)
    self._corner_editable = _phase6_is_unknown_baseline(self, self._phase6_baseline_initial_model)
    self._ui_text_controller = _phase6_prepare_text_scale_controller(
        root, self._settings_values.get("ui_text_size", "small")
    )

    # During the inherited/original MainApp constructor, do_update() is invoked
    # twice before Phase6 installs its Final Part Geometry renderer.  Suppress
    # those legacy geometry draws completely; opening the 3D workspace should
    # construct UI state only and render nothing until a Phase6 part is selected.
    self.preview_3d_enabled = False
    self._whd_style = apply_ttk_dark_theme(root, text_scale=1.0)
    self.queue_update = _phase6_queue_update.__get__(self, type(self))
    self.do_update = _phase6_preview_aware_do_update.__get__(self, type(self))


def _phase6_finish_legacy_host_compatibility(self, snapshot):
    _phase6_settings_transactions(self)
    # FIX10 marks itself ready as soon as its legacy snapshot is loaded. Phase6
    # still has to build the persistent controls/workspace, so keep the public
    # lifecycle in INITIALIZING until the complete view state is settled.
    self._phase6_sync_ready = False
    self.state.phase6_thickness = _num(snapshot.get("t", (snapshot.get("settings") or {}).get("t", 2.0)), 2.0)
    self.state.ui_text_scale = self._ui_text_controller.factor
    self.preview_3d_enabled = True
    _hide_original_structure_mode_controls(self.left)
    _hide_original_global_dimension_controls(self.left)
    _phase6_hide_original_visual_controls(self.left)
    self._phase6_parameters_unlocked = False
    self._phase6_3d_display_mode = "assembly"
    self._phase6_fullscreen = False
    self.right_control_bar = None
    self.drawing_edge_hosts = None
    self.endcap_joint_vars = {}
    self.endcap_joint_widgets = {}
    self.endcap_joint_allowed = {}
    self.base_plate_edge_shrink_vars = {}
    self.base_plate_edge_shrink_widgets = {}
    _phase6_build_persistent_top_area(self)
    try:
        self.root.title("Phase6 折彎 / 3D 設計")
    except Exception:
        pass

    # 為了讓未修改的 Renderer 繼續運作，保留舊 notebook 與 HolesUI/state；
    # 但畫面上不再顯示整層舊「module」介面。
    tabs = list(self.main_nb.tabs())
    if len(tabs) > 1:
        self.main_nb.forget(tabs[1])
    self.main_nb.pack_forget()


def _phase6_bootstrap_workspace_profiles(self, snapshot):
    stored_profiles = snapshot.get("part_profiles") or {}
    for key in self.designer_workspace.available_parts:
        if key == "box_body":
            continue
        source = stored_profiles.get(key)
        if source:
            loaded = {
                "X": clone_profile(source.get("X", [])),
                "Y": clone_profile(source.get("Y", [])),
            }
            normalized = (
                _phase6_normalize_endcap_profile_order(loaded, snapshot, key)
                if key in {"head", "tail"} else loaded
            )
            self.designer_workspace.stash_profiles(key, normalized)
        elif key in {"head", "tail"}:
            self.designer_workspace.stash_profiles(key, build_endcap_xy_profiles(snapshot, part_key=key))
        else:
            self.designer_workspace.stash_profiles(key, build_standard_part_profiles(snapshot, key))

    # Head/tail mating fold topology is derived from the box chain. Stored
    # project copies are diagnostic only and may come from an older topology.
    _phase6_rebuild_linked_endcaps(self)
    _phase6_sync_authoritative_derived_parts(self)

    # 進入 3D 直接進箱身；不再建立首頁 landing state。
    self.designer_workspace.active_part = None
    self.designer_workspace.selected_part = None


def _phase6_install_part_editor_compatibility(self):
    # 板件選擇／新增／刪除固定同一列，永不因切換板件消失。
    self.part_selector = original.ttk.Frame(self.left)
    self.part_selector.pack(fill=original.tk.X, pady=(0, 4))
    self.part_var = original.tk.StringVar(master=self.part_selector, value="箱身")
    self.part_buttons = {}
    # The compact sheet-metal menu and the Structure Tree are two presentation
    # projections of the same authoritative part_var / workspace callbacks.
    # Keep the existing menu visible; do not create a second state owner.
    self.part_choice_button = original.ttk.Menubutton(self.part_selector, textvariable=self.part_var, style="Selector.TMenubutton", takefocus=True)
    self.part_choice_menu = configure_tk_menu(original.tk.Menu(self.part_choice_button, tearoff=False))
    self.part_choice_button.configure(menu=self.part_choice_menu)
    self.part_choice_button.pack(fill=original.tk.X, pady=(0, 4))

    # #382: keep the legacy Structure Tree object only as a compatibility/state
    # projection.  It no longer owns operator layout pixels.  Normal part input
    # and assembly content share the same left content region.
    self.structure_tree_spacer = original.ttk.Frame(self.left, height=1)
    self.structure_tree_spacer.pack_propagate(False)
    self.structure_tree_host = original.ttk.Frame(self.left)
    self.structure_tree = original.ttk.Treeview(
        self.structure_tree_host, columns=("visibility",),
        show="tree headings", selectmode="browse", height=9, takefocus=True,
    )
    self.structure_tree.heading("#0", text="板件 / 功能", anchor=original.tk.W)
    self.structure_tree.heading("visibility", text="狀態", anchor=original.tk.CENTER)
    self.structure_tree.column("#0", width=190, minwidth=120, stretch=True)
    self.structure_tree.column(
        "visibility", width=58, minwidth=52, stretch=False, anchor=original.tk.CENTER
    )
    self.structure_tree_scrollbar = original.ttk.Scrollbar(
        self.structure_tree_host, orient=original.tk.VERTICAL, command=self.structure_tree.yview
    )
    self.structure_tree.configure(yscrollcommand=self.structure_tree_scrollbar.set)
    self.structure_tree_scrollbar.pack(side=original.tk.RIGHT, fill=original.tk.Y)
    self.structure_tree.pack(side=original.tk.LEFT, fill=original.tk.BOTH, expand=True)
    self.structure_tree.tag_configure("hidden", foreground=WHD_THEME["muted_text"])
    self._phase6_structure_tree_guard = False
    self.structure_tree.bind(
        "<<TreeviewSelect>>", lambda event: _phase6_on_structure_tree_select(self, event)
    )
    self.structure_tree.bind(
        "<Button-1>", lambda event: _phase6_on_structure_tree_click(self, event), add="+"
    )

    # Legacy multipart tabs remain internal compatibility state only; the
    # Structure Tree is the single visible child-navigation surface.
    self.box_body_piece_selector = original.ttk.Notebook(self.left, height=1, takefocus=False)
    self._phase6_box_body_piece_tab_keys = ()
    self._phase6_box_body_piece_tab_map = {}
    self._phase6_box_body_piece_tab_guard = False
    self.box_body_piece_selector.bind(
        "<<NotebookTabChanged>>",
        lambda event: _phase6_on_box_body_piece_tab_changed(self, event),
    )

    self.part_action_row = original.ttk.Frame(self.part_selector)
    self.part_action_row.pack(fill=original.tk.X, pady=(0, 4))
    self.add_part_button = original.ttk.Menubutton(self.part_action_row, text="新增 ▼", style="Secondary.TMenubutton", takefocus=True)
    self.add_part_menu = configure_tk_menu(original.tk.Menu(self.add_part_button, tearoff=False))
    self.add_part_button.configure(menu=self.add_part_menu)
    self.add_part_button.pack(side=original.tk.LEFT, fill=original.tk.X, expand=True, padx=(0, 2))
    self.remove_part_button = original.ttk.Button(
        self.part_action_row, text="刪除", command=self.remove_selected_part, state="disabled", style="Secondary.TButton", takefocus=True
    )
    self.remove_part_button.pack(side=original.tk.LEFT, fill=original.tk.X, expand=True, padx=(2, 0))

    _phase6_build_content_switch(self)

    # #440 correction: no fixed outer wrapper around mode content.
    # The three mode surfaces are direct siblings under self.left and exactly
    # one is mapped at a time in the same layout slot.  Compatibility aliases
    # do not create any additional Frame.
    self.input_content_host = original.ttk.Frame(self.left)
    self.fold_editor_host = self.input_content_host
    self.shared_content_host = self.left

    # Receiving 後面板形式 is a normal product choice, not an advanced
    # parameter.  Keep one normal-input projection bound to the existing
    # canonical structure-state callback; no second state owner is created.
    self.back_panel_mode_control = original.ttk.Frame(self.input_content_host)
    original.ttk.Label(
        self.back_panel_mode_control,
        text="後面板形式",
    ).pack(side=original.tk.LEFT, padx=(0, 6))
    self.back_panel_mode_var = original.tk.StringVar(
        master=self.back_panel_mode_control,
        value=_BACK_PANEL_MODE_LABELS[BackPanelMode.FULL],
    )
    self.back_panel_mode_selector = original.ttk.Combobox(
        self.back_panel_mode_control,
        textvariable=self.back_panel_mode_var,
        values=tuple(_BACK_PANEL_MODE_LABELS[item] for item in BackPanelMode),
        state="readonly",
        width=10,
    )
    self.back_panel_mode_selector.pack(side=original.tk.LEFT)
    self.back_panel_mode_selector.bind(
        "<<ComboboxSelected>>",
        lambda _event: _phase6_select_back_panel_mode(self, self.back_panel_mode_var),
    )

    self.bend_ui = Phase6BendingUI(
        self.input_content_host, self.state, self.queue_update
    )

    # Phase 5 T2: retain the same Assembly owner/state; presentation now mounts
    # directly in the same left-side slot as normal input and Corner Data.
    self._phase6_assembly_panel_owner = Phase6AssemblyPanel(
        self.left,
        actions=AssemblyPanelActions(
            on_visibility_changed=lambda: _phase6_on_assembly_part_visibility_changed(self)
        ),
    )
    _phase6_install_assembly_panel_aliases(self, self._phase6_assembly_panel_owner)

    _phase6_refresh_assembly_parts_panel(self)


def _phase6_install_initial_owner_views(self):
    self._refresh_part_buttons()
    self._refresh_add_part_menu()
    try:
        self.root.bind("<Delete>", lambda _e: self.remove_selected_part())
    except Exception:
        pass

    _phase6_mount_shared_content(self, "single")
    _phase6_build_settings_center(self)
    _phase6_install_renderer_view(self)
    self.settings_center.pack_forget()


def _phase6_select_initial_mode(self):
    self.activate_part("box_body", initial=True)
    _phase6_show_assembly(self, initial=True)


def _phase6_mark_ready(self):
    self.designer_workspace.mark_clean()

    # READY starts from the exact authoritative state already displayed. Seed the
    # live fingerprint without invoking the callback so opening 3D never creates
    # a synthetic revision, and a no-edit close/force-publish remains a no-op.
    initial_live_state = _phase6_corner_transaction_payload(self)
    self._phase6_last_live_state = deepcopy(initial_live_state)
    self._phase6_last_live_fingerprint = stable_fingerprint(initial_live_state)
    self._phase6_last_live_payload = None
    self._phase6_initializing = False
    self._phase6_sync_ready = True



def _phase6_refresh_sticky_structure_tree(self):
    """Compatibility port retained for WorkspaceShell composition callbacks."""
    host = getattr(self, "structure_tree_host", None)
    spacer = getattr(self, "structure_tree_spacer", None)
    try:
        if host is not None:
            manager = str(host.winfo_manager() or "")
            if manager == "place":
                host.place_forget()
            elif manager == "pack":
                host.pack_forget()
            elif manager == "grid":
                host.grid_remove()
        if spacer is not None:
            manager = str(spacer.winfo_manager() or "")
            if manager == "pack":
                spacer.pack_forget()
            elif manager == "grid":
                spacer.grid_remove()
            elif manager == "place":
                spacer.place_forget()
    except Exception:
        return


def _phase6_install_keyboard_shortcuts(self):
    """Compatibility port; command_router remains the keyboard binding owner."""
    return install_fold_designer_keyboard_shortcuts(
        self,
        on_save=lambda event: _phase6_keyboard_save(self, event),
        on_open=lambda event: _phase6_keyboard_open(self, event),
        on_fullscreen=lambda event: _phase6_keyboard_fullscreen(self, event),
    )


def _fix11_init(self, root, snapshot: Mapping[str, object], on_settings_change=None, on_save_defaults=None, on_corner_change=None, on_transaction_confirm=None, on_transaction_cancel=None, on_live_sync=None, on_baseline_data_query=None, on_scene_query=None, on_part_spec_query=None, on_ui_text_size_change=None, on_project_load=None, on_project_path_change=None, on_project_save=None, output_draw_stock_var=None, output_export_vars=None, on_export_selected_dxf=None):
    # Atomic lifecycle root: enter INITIALIZING before predecessor construction can
    # emit traced callbacks, then install accepted owners in one deterministic order.
    self._phase6_initializing = True
    snapshot = _phase6_bootstrap_authoritative_state(self, snapshot)
    _phase6_install_runtime_ports(
        self,
        on_settings_change=on_settings_change,
        on_save_defaults=on_save_defaults,
        on_corner_change=on_corner_change,
        on_transaction_confirm=on_transaction_confirm,
        on_transaction_cancel=on_transaction_cancel,
        on_live_sync=on_live_sync,
        on_baseline_data_query=on_baseline_data_query,
        on_scene_query=on_scene_query,
        on_part_spec_query=on_part_spec_query,
        on_ui_text_size_change=on_ui_text_size_change,
        on_project_load=on_project_load,
        on_project_path_change=on_project_path_change,
        on_project_save=on_project_save,
        output_draw_stock_var=output_draw_stock_var,
        output_export_vars=output_export_vars,
        on_export_selected_dxf=on_export_selected_dxf,
    )
    _phase6_prepare_predecessor_init(self, root, snapshot)
    _FIX10_INIT(self, root, snapshot)
    _phase6_finish_legacy_host_compatibility(self, snapshot)
    _phase6_bootstrap_workspace_profiles(self, snapshot)
    _phase6_install_part_editor_compatibility(self)
    _phase6_install_initial_owner_views(self)
    _phase6_select_initial_mode(self)
    _phase6_mark_ready(self)


def _phase6_clear_navigation_residue(self):
    """Dismiss transient navigation popups before changing the visible content."""
    for name in ("part_choice_menu", "add_part_menu", "project_file_menu"):
        menu = getattr(self, name, None)
        if menu is None:
            continue
        try:
            menu.unpost()
        except Exception:
            pass


def _phase6_refresh_content_switch(self):
    """Project the existing display mode onto the three persistent buttons."""
    mode = str(getattr(self, "_phase6_3d_display_mode", "single") or "single")
    active = "assembly" if mode == "assembly" else "corner_data" if mode == "corner_data" else "input"
    mapping = {
        "input": getattr(self, "input_content_button", None),
        "assembly": getattr(self, "assembly_content_button", None),
        "corner_data": getattr(self, "corner_data_content_button", None),
    }
    for key, button in mapping.items():
        if button is None:
            continue
        try:
            button.state(["pressed"] if key == active else ["!pressed"])
        except Exception:
            pass
    return active



def _phase6_build_content_switch(self):
    """Retain compatibility handles without a second visible navigation strip.

    The main part selector now owns Input/Assembly/Corner-Data navigation.  Keep
    the legacy attributes so older internal callers can remain tolerant, but do
    not expose duplicate wrapper labels or buttons in the operator layout.
    """
    self.content_switch_frame = original.ttk.Frame(self.left)
    self.input_content_button = None
    self.assembly_content_button = None
    self.corner_data_content_button = None
    _phase6_refresh_content_switch(self)
    return self.content_switch_frame


def _phase6_mount_shared_content(self, mode):
    return _workspace_shell_mount_shared_content(
        getattr(self, "left", None),
        getattr(self, "input_content_host", None),
        getattr(self, "assembly_parts_panel", None),
        getattr(self, "corner_data_panel", None),
        mode,
    )

def _phase6_structure_tree_visibility_var(self, key):
    """Return the exact panel-owned visibility var for one physical identity."""
    owner = getattr(self, "_phase6_assembly_panel_owner", None)
    if owner is None:
        return None
    key = str(key or "")
    return owner.visibility_var(
        key,
        is_box_piece=_phase6_is_box_body_physical_piece_key(key),
    )


def _phase6_refresh_structure_tree(self):
    """Rebuild the CAD navigation projection from current authoritative identities."""
    tree = getattr(self, "structure_tree", None)
    if tree is None:
        return ()
    if bool(getattr(self, "_phase6_structure_tree_guard", False)):
        return ()

    self._phase6_structure_tree_guard = True
    try:
        roots = tuple(tree.get_children(""))
        if roots:
            tree.delete(*roots)
        tree.insert("", "end", iid="mode:assembly", text="組合體", values=("",), open=True)
        tree.insert("", "end", iid="mode:corner_data", text="截角資料", values=("",), open=True)
        workspace = _designer_workspace(self)
        snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
        rows = _phase6_structure_tree_rows(getattr(workspace, "available_parts", ()) or ())
        for key, parent_key in rows:
            iid = f"part:{key}"
            parent_iid = f"part:{parent_key}" if parent_key else ""
            visible_var = _phase6_structure_tree_visibility_var(self, key)
            visible = True if visible_var is None else bool(visible_var.get())
            tree.insert(
                parent_iid, "end", iid=iid,
                text=_phase6_part_label(key, snapshot=snapshot),
                values=("顯示" if visible else "隱藏",),
                tags=(() if visible else ("hidden",)),
                open=(key == "box_body"),
            )
        mode = str(getattr(self, "_phase6_3d_display_mode", "assembly") or "assembly")
        active = str(getattr(workspace, "active_part", "") or "")
        selected_iid = (
            "mode:assembly" if mode == "assembly"
            else "mode:corner_data" if mode == "corner_data"
            else f"part:{active}" if active else ""
        )
        if selected_iid and tree.exists(selected_iid):
            tree.selection_set(selected_iid)
            tree.focus(selected_iid)
            tree.see(selected_iid)
        return rows
    finally:
        # ttk.Treeview.selection_set() posts <<TreeviewSelect>> asynchronously.
        # Keep the guard alive through the queued event; dropping it here
        # creates select -> refresh -> selection_set -> select recursion.
        try:
            tree.after_idle(
                lambda: setattr(self, "_phase6_structure_tree_guard", False)
            )
        except Exception:
            self._phase6_structure_tree_guard = False


def _phase6_on_structure_tree_select(self, _event=None):
    if bool(getattr(self, "_phase6_structure_tree_guard", False)):
        return
    tree = getattr(self, "structure_tree", None)
    if tree is None:
        return
    selected = tuple(tree.selection())
    if not selected:
        return
    iid = str(selected[0])
    if iid == "mode:assembly":
        _phase6_show_assembly(self)
    elif iid == "mode:corner_data":
        _phase6_show_corner_data(self)
    elif iid.startswith("part:"):
        _phase6_activate_operator_part(self, iid[5:])
    _phase6_refresh_structure_tree(self)


def _phase6_set_structure_tree_visibility(self, key, visible):
    """Mutate the shared panel Tk var and emit the panel visibility action."""
    key = str(key or "")
    visible_var = _phase6_structure_tree_visibility_var(self, key)
    if visible_var is None:
        return False
    visible_var.set(bool(visible))
    owner = getattr(self, "_phase6_assembly_panel_owner", None)
    if owner is not None:
        owner.notify_visibility_changed()
    _phase6_refresh_structure_tree(self)
    return True


def _phase6_on_structure_tree_click(self, event):
    tree = getattr(self, "structure_tree", None)
    if tree is None or tree.identify_column(event.x) != "#1":
        return None
    iid = str(tree.identify_row(event.y) or "")
    if not iid.startswith("part:"):
        return "break"
    key = iid[5:]
    visible_var = _phase6_structure_tree_visibility_var(self, key)
    if visible_var is None:
        return "break"
    _phase6_set_structure_tree_visibility(self, key, not bool(visible_var.get()))
    return "break"

def _phase6_refresh_box_body_piece_selector(self):
    """Keep one logical 箱身 entry while exposing physical children as nested tabs."""
    notebook = getattr(self, "box_body_piece_selector", None)
    if notebook is None:
        return ()

    wanted = _phase6_box_body_piece_keys(
        getattr(_designer_workspace(self), "available_parts", ()) or ()
    )
    current = tuple(getattr(self, "_phase6_box_body_piece_tab_keys", ()) or ())
    if current != wanted:
        self._phase6_box_body_piece_tab_guard = True
        try:
            for tab_id in tuple(notebook.tabs()):
                try:
                    widget = self.root.nametowidget(tab_id)
                except Exception:
                    widget = None
                notebook.forget(tab_id)
                if widget is not None:
                    try:
                        widget.destroy()
                    except Exception:
                        pass
            tab_map = {}
            for key in wanted:
                frame = original.ttk.Frame(notebook)
                notebook.add(frame, text=_phase6_part_label(key))
                tab_map[str(frame)] = key
            self._phase6_box_body_piece_tab_map = tab_map
            self._phase6_box_body_piece_tab_keys = wanted
        finally:
            self._phase6_box_body_piece_tab_guard = False

    workspace = _designer_workspace(self)
    active = str(getattr(workspace, "active_part", "") or "")
    remembered = str(getattr(self, "_phase6_box_body_active_piece_key", "") or "")
    if active in wanted:
        desired = active
        self._phase6_box_body_active_piece_key = active
    else:
        projection = _dm7_resolve_navigation(
            getattr(workspace, "available_parts", ()) or (),
            NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
            NavigationMemory(remembered or None),
        )
        desired = str(projection.resolved_key or "")
        self._phase6_box_body_active_piece_key = projection.memory.remembered_box_body_child
    if desired:
        tab_map = dict(getattr(self, "_phase6_box_body_piece_tab_map", {}) or {})
        target_tab = next(
            (tab_id for tab_id in notebook.tabs() if tab_map.get(str(tab_id)) == desired),
            None,
        )
        if target_tab is not None and str(notebook.select()) != str(target_tab):
            self._phase6_box_body_piece_tab_guard = True
            try:
                notebook.select(target_tab)
            finally:
                self._phase6_box_body_piece_tab_guard = False

    # #124: tabs are retained only as compatibility state. Never expose a
    # second visible child navigator beside the Structure Tree.
    if notebook.winfo_manager():
        notebook.pack_forget()
    return wanted


def _phase6_on_box_body_piece_tab_changed(self, _event=None):
    if bool(getattr(self, "_phase6_box_body_piece_tab_guard", False)):
        return
    notebook = getattr(self, "box_body_piece_selector", None)
    if notebook is None:
        return
    key = dict(getattr(self, "_phase6_box_body_piece_tab_map", {}) or {}).get(
        str(notebook.select())
    )
    if not key:
        return
    workspace = _designer_workspace(self)
    if str(getattr(workspace, "active_part", "") or "") == key:
        # Keep ephemeral navigation memory synchronized without re-activating an
        # already-active manufacturing part.  Resolution remains the authority.
        _phase6_resolve_operator_part_key(self, key)
        return
    _phase6_activate_operator_part(self, key)


def _phase6_resolve_operator_part_key(self, key):
    """Resolve one explicit identity through the pure DM7 navigation owner."""
    navigation = _phase6_workspace_navigation(self)
    resolved = navigation.resolve_operator_part(key)
    # Keep the legacy compatibility surface coherent for lightweight owners
    # that do not install Phase6FoldDesignerApp's property descriptor.  On the
    # real app this assignment delegates straight back to the same controller.
    self._phase6_box_body_active_piece_key = navigation.remembered_box_body_child
    return resolved


def _phase6_activate_operator_part(self, key):
    """Activate only a successfully resolved explicit operator identity."""
    resolved = _phase6_resolve_operator_part_key(self, key)
    if not resolved:
        return None
    result = self.activate_part(resolved)
    _phase6_refresh_structure_tree(self)
    return result


def _fix11_refresh_part_buttons(self):
    self.part_buttons = {}
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    menu = getattr(self, "part_choice_menu", None)
    if menu is not None:
        menu.delete(0, original.tk.END)
        menu.add_radiobutton(
            label="組合體",
            variable=self.part_var,
            value="組合體",
            command=lambda: _phase6_show_assembly(self),
        )
        for key in _phase6_operator_part_selector_keys(self.available_parts):
            label = _phase6_part_label(key, snapshot=snapshot)
            menu.add_radiobutton(
                label=label,
                variable=self.part_var,
                value=label,
                command=lambda k=key: _phase6_activate_operator_part(self, k),
            )
        menu.add_radiobutton(
            label="截角資料",
            variable=self.part_var,
            value="截角資料",
            command=lambda: _phase6_show_corner_data(self),
        )
    active = getattr(self, "active_part_key", None)
    if hasattr(self, "part_var"):
        display_mode = str(
            getattr(self, "_phase6_3d_display_mode", "single") or "single"
        )
        if display_mode == "assembly":
            self.part_var.set("組合體")
        elif display_mode == "corner_data":
            self.part_var.set("截角資料")
        elif _phase6_is_box_body_physical_piece_key(active):
            self.part_var.set(_phase6_part_label("box_body", snapshot=snapshot))
        elif active in self.available_parts:
            self.part_var.set(_phase6_part_label(active, snapshot=snapshot))
    self._refresh_part_button_states()
    _phase6_refresh_box_body_piece_selector(self)
    _phase6_refresh_back_panel_mode_control(self)
    if getattr(self, "assembly_parts_panel", None) is not None:
        _phase6_refresh_assembly_parts_panel(self)
    _phase6_refresh_structure_tree(self)
    _phase6_refresh_content_switch(self)
    _phase6_refresh_status_bar(self)


def _fix11_refresh_part_button_states(self):
    selected = getattr(self, "selected_part_key", None)
    for button in self.part_buttons.values():
        button.state(["!disabled"])
    delete = getattr(self, "remove_part_button", None)
    if delete is not None:
        delete.configure(
            state=("normal" if selected in self.available_parts and selected != "box_body" and not _phase6_is_derived_physical_part_key(selected) else "disabled")
        )


def _phase6_corner_data_part_keys(self) -> tuple[str, ...]:
    """Project authoritative workspace identities into the 2D View."""
    return _phase6_corner_data_view(self).part_keys(
        _designer_workspace(self)
    )

def _phase6_corner_data_navigation_rows(self) -> tuple[tuple[str, int], ...]:
    """Project Corner Data rows from the canonical DM7 hierarchy."""
    return _phase6_corner_data_view(self).navigation_rows(
        _phase6_corner_data_part_keys(self),
        hierarchy_projector=_dm7_project_hierarchy,
    )

def _phase6_select_corner_data_part(self, key, *, refresh_view=True):
    """Resolve one stable view identity without activating manufacturing state."""
    adapter = _phase6_corner_data_view(self)
    previous = adapter.selected_part_key
    keys = _phase6_corner_data_part_keys(self)
    resolved = adapter.resolve_selection(
        keys,
        key,
        resolver=lambda requested: _phase6_resolve_operator_part_key(
            self, requested
        ),
    )
    _phase6_sync_corner_data_view_compatibility_mirrors(self, adapter)
    if previous != resolved:
        canvas = getattr(self, "corner_data_canvas", None)
        if canvas is not None:
            try:
                canvas._phase6_unfold_zoom = 1.0
            except Exception:
                pass
    if (
        refresh_view
        and str(getattr(self, "_phase6_3d_display_mode", "") or "")
        == "corner_data"
        and getattr(self, "corner_data_canvas", None) is not None
    ):
        _phase6_refresh_corner_data_unfold_view(self)
    _phase6_refresh_status_bar(self)
    return resolved

def _phase6_corner_data_info_request_for_key(self, part_key, render_data):
    """Build a display-only request from authoritative render/dimension sinks."""
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    settings = getattr(self, "_settings_values", {}) or {}
    return _phase6_corner_data_view(self).info_request(
        part_key=part_key,
        render_data=render_data,
        request_factory=FinalSceneViewRequest,
        profile_provider=lambda key, material: _phase6_mesh_profiles_for_part(
            self, key, material
        ),
        dimensions_provider=lambda key: _phase6_operator_finished_dimensions(
            self, key
        ),
        corner_text_provider=_phase6_render_data_corner_dimension_text,
        blank_text_provider=_phase6_format_unfolded_blank_text,
        alpha_bend=float(
            getattr(getattr(self, "state", None), "alpha_bend", 0.85)
        ),
        thickness=_num(
            settings.get("t", snapshot.get("t", 2.0)), 2.0
        ),
    )

def _phase6_corner_data_info_text_for_key(self, part_key, render_data):
    request = _phase6_corner_data_info_request_for_key(self, part_key, render_data)
    return format_operator_info_text(
        request, dimensions=request.finished_dimensions, number_text=_setting_number_text
    )


def _phase6_corner_data_unfold_projection_for_key(self, part_key):
    """Pair one stable identity with its authoritative render-data sink."""
    def render_provider(selected):
        if _phase6_is_box_body_physical_piece_key(selected):
            return _phase6_box_body_piece_render_data(self, selected)
        return _phase6_render_data_for_blank(self, selected)

    return _phase6_corner_data_view(self).unfold_projection(
        part_key,
        available_parts=_phase6_corner_data_part_keys(self),
        render_provider=render_provider,
        projection_factory=Phase6CornerDataUnfoldProjection,
    )

def _phase6_corner_data_unfold_projections(self, part_keys):
    """Batch view adapter over authoritative per-part projections."""
    return _phase6_corner_data_view(self).unfold_projections(
        part_keys,
        projection_provider=lambda key: _phase6_corner_data_unfold_projection_for_key(
            self, key
        ),
    )

def _phase6_corner_data_unfold_projection(self):
    """Return selected authoritative unfold projection."""
    return _phase6_corner_data_view(self).selected_projection(
        projection_provider=lambda key: _phase6_corner_data_unfold_projection_for_key(
            self, key
        )
    )

def _phase6_refresh_corner_data_unfold_view(self):
    """Render one adapter-projected authoritative 2D payload."""
    canvas = getattr(self, "corner_data_canvas", None)
    projection = _phase6_corner_data_unfold_projection(self)
    payload = _phase6_corner_data_view(self).view_payload(
        projection,
        info_provider=lambda part_key, render_data: _phase6_corner_data_info_text_for_key(
            self, part_key, render_data
        ),
    )
    if payload is None:
        if canvas is not None and hasattr(canvas, "delete"):
            canvas.delete("all")
        return None
    info_text = payload["info_text"]
    info_var = getattr(self, "corner_data_info_var", None)
    if info_var is not None and hasattr(info_var, "set"):
        info_var.set(info_text)
    self.corner_data_info_text = info_text
    callback = getattr(self, "_corner_data_view_render_callback", None)
    projection = payload["projection"]
    if callback is not None and canvas is not None:
        callback(canvas, projection.part_key, projection.render_data)
    return projection

def _phase6_refresh_corner_data_parts_panel(self) -> tuple[str, ...]:
    """Refresh the corner-data list as a pure View projection of workspace parts."""
    keys = _phase6_corner_data_part_keys(self)
    self.corner_data_part_keys = keys
    selected = getattr(self, "_phase6_corner_data_selected_part_key", None)
    if selected is not None:
        _phase6_select_corner_data_part(self, selected)
    panel = getattr(self, "corner_data_panel", None)
    if panel is None or not hasattr(panel, "winfo_children"):
        return keys

    for child in tuple(panel.winfo_children()):
        child.destroy()

    self.corner_data_part_rows = {}
    self.corner_data_part_buttons = {}
    self.corner_data_part_depths = {}
    navigation_rows = _phase6_corner_data_navigation_rows(self)
    for key, depth in navigation_rows:
        row = original.ttk.Frame(panel)
        row.pack(fill=original.tk.X, pady=(0, 4), padx=(18, 0) if depth else 0)
        button = original.ttk.Button(
            row,
            text=_phase6_part_label(key),
            command=lambda k=key: _phase6_select_corner_data_part(self, k),
        )
        button.pack(side=original.tk.LEFT, fill=original.tk.X, expand=True)
        self.corner_data_part_rows[key] = row
        self.corner_data_part_buttons[key] = button
        self.corner_data_part_depths[key] = depth
    return keys


def _phase6_on_corner_data_mousewheel(self, event):
    """Apply viewport zoom only; authoritative manufacturing geometry is untouched."""
    canvas = getattr(self, "corner_data_canvas", None)
    if canvas is None:
        return None
    updated = _phase6_corner_data_view(self).zoom_from_event(
        getattr(canvas, "_phase6_unfold_zoom", 1.0),
        delta=getattr(event, "delta", 0),
        button=getattr(event, "num", 0),
    )
    if updated is None:
        return None
    canvas._phase6_unfold_zoom = updated
    if str(getattr(self, "_phase6_3d_display_mode", "") or "") == "corner_data":
        _phase6_refresh_corner_data_unfold_view(self)
    return "break"

def _phase6_prepare_corner_data_canvas(self):
    """Install the 2D canvas as a View effect using adapter visibility policy."""
    renderer = getattr(self, "renderer", None)
    mpl_canvas = getattr(renderer, "canvas", None)
    get_widget = getattr(mpl_canvas, "get_tk_widget", None)
    if not callable(get_widget):
        return None
    mpl_widget = get_widget()
    canvas = getattr(self, "corner_data_canvas", None)
    try:
        alive = canvas is not None and bool(canvas.winfo_exists())
    except Exception:
        alive = canvas is not None
    info_var = getattr(self, "corner_data_info_var", None)
    if info_var is None:
        info_var = original.tk.StringVar(value="")
        self.corner_data_info_var = info_var
    info_label = getattr(self, "corner_data_info_label", None)
    try:
        info_alive = info_label is not None and bool(info_label.winfo_exists())
    except Exception:
        info_alive = info_label is not None
    if not info_alive:
        info_label = original.ttk.Label(
            mpl_widget.master,
            textvariable=self.corner_data_info_var,
            justify=original.tk.LEFT,
            anchor=original.tk.W,
            wraplength=1100,
            font=("Microsoft JhengHei", 11, "bold"),
        )
        self.corner_data_info_label = info_label
    if not alive:
        canvas = original.tk.Canvas(
            mpl_widget.master,
            bg=WHD_THEME["corner_data_canvas"],
            highlightthickness=0,
            takefocus=False,
        )
        self.corner_data_canvas = canvas
        canvas._phase6_unfold_zoom = 1.0
        canvas.bind(
            "<Configure>",
            lambda _event: (
                _phase6_refresh_corner_data_unfold_view(self)
                if str(getattr(self, "_phase6_3d_display_mode", "") or "")
                == "corner_data"
                else None
            ),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: _phase6_on_corner_data_mousewheel(self, event),
        )
        canvas.bind(
            "<Button-4>",
            lambda event: _phase6_on_corner_data_mousewheel(self, event),
        )
        canvas.bind(
            "<Button-5>",
            lambda event: _phase6_on_corner_data_mousewheel(self, event),
        )
    plan = _phase6_corner_data_view(self).canvas_visibility_plan(True)
    if not plan["mpl_canvas"] and mpl_widget.winfo_manager():
        mpl_widget.pack_forget()
    if plan["info_label"] and not info_label.winfo_manager():
        info_label.pack(fill=original.tk.X, padx=8, pady=(6, 2))
    if plan["corner_canvas"] and not canvas.winfo_manager():
        canvas.pack(fill=original.tk.BOTH, expand=True)
    return canvas

def _phase6_hide_corner_data_canvas(self):
    """Restore Matplotlib according to pure View visibility policy."""
    plan = _phase6_corner_data_view(self).canvas_visibility_plan(False)
    info_label = getattr(self, "corner_data_info_label", None)
    if info_label is not None and not plan["info_label"]:
        try:
            if info_label.winfo_manager():
                info_label.pack_forget()
        except Exception:
            pass
    canvas = getattr(self, "corner_data_canvas", None)
    if canvas is not None and not plan["corner_canvas"]:
        try:
            if canvas.winfo_manager():
                canvas.pack_forget()
        except Exception:
            pass
    renderer = getattr(self, "renderer", None)
    mpl_canvas = getattr(renderer, "canvas", None)
    get_widget = getattr(mpl_canvas, "get_tk_widget", None)
    if not callable(get_widget):
        return None
    mpl_widget = get_widget()
    if plan["mpl_canvas"] and not mpl_widget.winfo_manager():
        mpl_widget.pack(fill=original.tk.BOTH, expand=True)
    return mpl_widget

def _phase6_show_corner_data(self):
    """Switch Fold Designer to the view-only corner-data navigation mode.

    This mode is navigation only: it must not flush/publish settings, add a
    manufacturing part, or alter workspace selection/state. T2 will populate
    the authoritative part projection inside the mode panel.
    """
    _phase6_clear_navigation_residue(self)
    self._phase6_3d_display_mode = "corner_data"
    if hasattr(self, "part_var"):
        self.part_var.set("截角資料")

    piece_selector = getattr(self, "box_body_piece_selector", None)
    if piece_selector is not None and hasattr(piece_selector, "pack_forget"):
        try:
            piece_selector.pack_forget()
        except Exception:
            pass

    panel = getattr(self, "corner_data_panel", None)
    if panel is None:
        shared_host = getattr(self, "left", None)
        if shared_host is None:
            return None
        panel = original.ttk.Frame(shared_host, padding=6)
        self.corner_data_panel = panel
    _phase6_mount_shared_content(self, "corner_data")

    corner_canvas = _phase6_prepare_corner_data_canvas(self)
    _phase6_refresh_corner_data_parts_panel(self)
    if corner_canvas is not None:
        _phase6_refresh_corner_data_unfold_view(self)

    refresh = getattr(self, "_refresh_part_button_states", None)
    if callable(refresh):
        refresh()
    _phase6_refresh_content_switch(self)


def _phase6_show_assembly(self, initial=False):
    """Show the structural cabinet assembly while retaining a real active part as geometry backing."""
    _phase6_clear_navigation_residue(self)
    _phase6_hide_corner_data_canvas(self)
    if not initial and getattr(self, "_phase6_pending_settings", None):
        self.flush_pending_settings()
    before_signature = None
    if not initial:
        try:
            before_signature = _phase6_manufacturing_state_signature(self)
        except Exception:
            before_signature = None
    if not initial and self.designer_workspace.active_part is not None:
        try:
            self._save_current_part()
        except Exception:
            pass
    _phase6_workspace_navigation(self).clear_selection()
    self._phase6_3d_display_mode = "assembly"
    if hasattr(self, "part_var"):
        self.part_var.set("組合體")
    piece_selector = getattr(self, "box_body_piece_selector", None)
    if piece_selector is not None and piece_selector.winfo_manager():
        piece_selector.pack_forget()
    _phase6_mount_shared_content(self, "assembly")
    center = getattr(self, "settings_center", None)
    if center is not None and center.winfo_manager():
        center.pack_forget()
    diagnostics = getattr(self, "assembly_diagnostics_frame", None)
    if diagnostics is not None:
        if bool(getattr(self, "_phase6_parameters_unlocked", False)):
            if not diagnostics.winfo_manager():
                _phase6_pack_right_panel_above_canvas(self, diagnostics)
        elif diagnostics.winfo_manager():
            diagnostics.pack_forget()
    delete = getattr(self, "remove_part_button", None)
    if delete is not None:
        delete.configure(state="disabled")
    canvas_widget = self.renderer.canvas.get_tk_widget()
    if not canvas_widget.winfo_manager():
        canvas_widget.pack(fill=original.tk.BOTH, expand=True)
    _phase6_clear_drawing_edge_controls(self)
    self.endcap_joint_vars = {}
    self.endcap_joint_widgets = {}
    self.endcap_joint_allowed = {}
    self.base_plate_edge_shrink_vars = {}
    self.base_plate_edge_shrink_widgets = {}
    if not initial:
        try:
            after_signature = _phase6_manufacturing_state_signature(self)
        except Exception:
            after_signature = None
        reason = "display" if before_signature is not None and before_signature == after_signature else "geometry"
        submit = getattr(self, "submit_update_intent", None)
        if callable(submit):
            submit(reason, commit=True)
        else:
            self.do_update()
    _phase6_refresh_content_switch(self)
    return True


def _fix11_select_part(self, key):
    key = str(key or "")
    navigation = _phase6_workspace_navigation(self)
    if not navigation.select_part(key):
        return False
    if hasattr(self, "part_var"):
        self.part_var.set(
                _phase6_part_label("box_body")
                if _phase6_is_box_body_physical_piece_key(key)
                else _phase6_part_label(key)
            )
    self._refresh_part_button_states()
    _phase6_refresh_box_body_piece_selector(self)
    return True


def _fix11_remove_selected_part(self):
    key = self.designer_workspace.selected_part
    if key not in self.designer_workspace.available_parts:
        return False
    result = self.remove_part(key)
    if result:
        self._refresh_part_button_states()
    return result


def _fix11_refresh_add_part_menu(self):
    self.add_part_menu.delete(0, original.tk.END)
    missing = [key for key in KNOWN_PARTS if key not in self.available_parts]
    if not missing:
        self.add_part_menu.add_command(label="沒有可新增板件", state="disabled")
        return
    for key in missing:
        self.add_part_menu.add_command(label=_phase6_part_label(key), command=lambda k=key: self.add_part(k))


def _phase6_refresh_linked_part_profiles(self, changed_keys):
    """Refresh non-active parts from one shared cabinet state.

    Head/Tail Y is derived from the authoritative BoxBody Fold Chain.  Their FW
    is resolved independently through the per-endcap follow/override state, so
    changing the box FW never overwrites a detached end cap.
    """
    if not {"w", "h", "d", "t", "fw"}.intersection(set(changed_keys or ())):
        return
    snapshot = self._phase6_input_snapshot
    snapshot.update(self._settings_values)
    snapshot["endcap_fw"] = deepcopy(
        getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(snapshot))
    )
    _phase6_recalculate_part_dimensions(self)
    navigation = _phase6_workspace_navigation(self)
    active = self.designer_workspace.active_part

    if active != "box_body" and "box_body" in self.designer_workspace.available_parts:
        current = self.state.profiles_vault.get("箱身", [])
        self.state.profiles_vault["箱身"] = merge_box_body_profile(current, snapshot)

    box_profile = self.state.profiles_vault.get("箱身", [])
    linked = build_linked_endcap_xy_profiles(snapshot, box_profile)
    for key in self.designer_workspace.available_parts:
        if key == active or key == "box_body":
            continue
        existing = self.designer_workspace.profiles_for(key, {}) or {}
        if key in ENDCAP_FW_PARTS:
            # X remains the end-cap's local flange axis; Y is mating topology
            # derived from the current box chain and must never be replaced by a
            # stale independently stored profile.
            defaults = linked[key]
            x_merged = _merge_keyed_profiles(
                {"X": existing.get("X", ())}, {"X": defaults.get("X", ())}
            ).get("X", clone_profile(defaults.get("X", ())))
            navigation.stash_profiles(key, {
                "X": x_merged,
                "Y": clone_profile(defaults.get("Y", ())),
            })
        else:
            defaults = build_standard_part_profiles(snapshot, key)
            navigation.stash_profiles(key, _merge_keyed_profiles(existing, defaults))


def _phase6_store_editor_values(self, values, *, notify=True):
    return _phase6_settings_coordinator(self).commit_editor_values(
        values,
        notify=bool(notify),
        applying_settings=bool(getattr(self, "_phase6_applying_settings", False)),
        transactional_mode=bool(getattr(self, "_phase6_transactional_mode", False)),
    )

def _phase6_commit_box_body_physical_piece_profile(self, part_key, profiles, *, notify=True):
    """Commit one physical side/back Fold editor through canonical BoxBody state."""
    role = str(part_key).split(":", 1)[-1]
    if role not in {"left_side", "back", "right_side"}:
        raise ValueError(f"unsupported BoxBody physical piece: {part_key}")

    rows = clone_profile(tuple((profiles or {}).get("X", ()) or ()))
    if not rows:
        raise ValueError(f"{part_key} X Fold profile is empty")

    structure = _phase6_box_structure_state(self)
    cfg = structure["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    aggregate = clone_profile(self.state.profiles_vault.get("箱身", ()))
    aggregate_by_key = {
        str(row.get("phase6_key") or ""): row
        for row in aggregate
        if str(row.get("phase6_key") or "")
    }
    piece_by_key = {
        str(row.get("phase6_key") or ""): row
        for row in rows
        if str(row.get("phase6_key") or "")
    }

    def copy_material_length(source_key, target_keys):
        source = piece_by_key.get(source_key)
        if source is None:
            return
        for target_key in tuple(target_keys):
            target = aggregate_by_key.get(target_key)
            if target is not None:
                target["len"] = float(source.get("len", target.get("len", 0.0)))

    if role == "left_side":
        copy_material_length("zl1", ("zl1",))
        copy_material_length("zl2", ("zl2",))
        copy_material_length("fw_left", ("fw_left", "fw_right"))
        copy_material_length("d_left", ("d_left", "d_right"))
        # Rear fold is piece-local. Persist it only in this physical piece's
        # canonical profile; do not back-write the legacy shared default.
    elif role == "right_side":
        copy_material_length("d_right", ("d_left", "d_right"))
        copy_material_length("fw_right", ("fw_left", "fw_right"))
        copy_material_length("zr2", ("zr2",))
        # Rear fold is piece-local. Persist it only in this physical piece's
        # canonical profile; do not back-write the legacy shared default.
    else:
        back = piece_by_key.get("back_panel")
        if back is not None:
            t = max(1.0e-9, float(self._phase6_input_snapshot.get("t", 0.0)))
            total_w = float(_phase6_box_structure_w(self))
            comp_t = (total_w - float(back.get("len", 0.0))) / t
            structure = set_side_back_geometry(
                structure, back_width_comp_t=max(0.0, comp_t)
            )

    # Shared cabinet dimensions remain authoritative and are updated from the
    # edited physical piece before its piece-local topology is persisted.
    if aggregate:
        apply_outside_dimension_compensation(
            aggregate, float(self._phase6_input_snapshot.get("t", 0.0))
        )
        values = read_box_body_profile(aggregate, self._phase6_input_snapshot)
        if role == "left_side":
            signed = piece_by_key.get("zl1")
            if signed is not None and "phase6_ui_sign" in signed:
                sign = -1.0 if float(signed.get("phase6_ui_sign", 1.0)) < 0.0 else 1.0
                values["zl1"] = sign * abs(float(values["zl1"]))
        values["h"] = self._phase6_box_whd["h"]
        self.state.profiles_vault["箱身"] = clone_profile(aggregate)
        self._phase6_input_snapshot["box_body_profile"] = clone_profile(aggregate)
        _phase6_store_editor_values(self, values, notify=notify)

    stored_rows = (
        _phase6_reverse_fold_traversal(rows)
        if role == "right_side" else clone_profile(rows)
    )
    for row in stored_rows:
        row.pop("phase6_ui_sign", None)
    structure = set_side_back_piece_profile(structure, role, stored_rows)
    _phase6_commit_box_structure_state(self, structure, rebuild=False)
    _phase6_sync_authoritative_derived_parts(self)


def _fix11_save_current_part(self, notify=True):
    if self.designer_workspace.switching:
        return
    key = self.designer_workspace.active_part
    if not key:
        return
    try:
        self.bend_ui.save()
    except Exception:
        return

    _phase6_replace_mapping(self, "_phase6_box_whd", {
        "w": original.get_int(self.v_w.get()),
        "h": original.get_int(self.v_h.get()),
        "d": original.get_int(self.v_d.get()),
    })
    if _phase6_is_box_body_physical_piece_key(key):
        profiles = {
            "X": clone_profile(self.state.profiles.get("X", [])),
            "Y": clone_profile(self.state.profiles.get("Y", [])),
        }
        if _phase6_is_side_back_editable_piece_key(key):
            _phase6_commit_box_body_physical_piece_profile(
                self, key, profiles, notify=notify
            )
        else:
            # Two-/three-piece W-split children are manufacturing projections of
            # the aggregate BoxBody + width allocation.  Their editor is a sink:
            # preserve the current workspace view only; canonical dimensions stay
            # owned by box_body_structure and the aggregate BoxBody profile.
            self.designer_workspace.stash_profiles(key, profiles)
        return
    if _phase6_is_derived_physical_part_key(key):
        _phase6_sync_authoritative_derived_parts(self)
        return

    if key == "box_body":
        if getattr(self, "_phase6_sync_ready", False):
            self._sync_dwd_with_top_whd()
        values = read_box_body_profile(self.state.profiles_vault["箱身"], self._phase6_input_snapshot)
        values["h"] = self._phase6_box_whd["h"]
        _phase6_store_editor_values(self, values, notify=notify)
        # Box FW changed: followers resolve the new value; detached end caps keep
        # their overrides. Rebuild both derived mating profiles once.
        self._phase6_input_snapshot["endcap_fw"] = deepcopy(self._phase6_endcap_fw_state)
        _phase6_rebuild_linked_endcaps(self)
        return

    profiles = {
        "X": clone_profile(self.state.profiles.get("X", [])),
        "Y": clone_profile(self.state.profiles.get("Y", [])),
    }
    self.designer_workspace.stash_profiles(key, profiles)
    if key in ENDCAP_FW_PARTS:
        x = {str(seg.get("phase6_key")): seg for seg in profiles.get("X", ()) if seg.get("phase6_key")}
        y = {str(seg.get("phase6_key")): seg for seg in profiles.get("Y", ()) if seg.get("phase6_key")}
        required_x = {"yl1", "endcap_w_core", "yr1"}
        flat_x = len(profiles.get("X", ())) == 1 and profiles["X"][0].get("phase6_key") == "endcap_w_flat"
        if not required_x.issubset(x) and not flat_x:
            raise ValueError("封頭/封尾 X 折彎資料不完整")

        # FW is cabinet frame-width semantics with per-endcap link/override. It
        # must never be routed through _phase6_store_editor_values(), because
        # that function owns the shared box settings and would back-write box FW.
        fw_item = self._phase6_endcap_fw_state.setdefault(
            key, {"follow_box": True, "value": _num(self._phase6_input_snapshot.get("fw", 25), 25)}
        )
        if "fw" in y:
            # Receiving EndCap Y profiles store FW in MATERIAL space
            # (29 outside -> 25 span at T=2).  Treating that span as the
            # operator value makes every Head/Tail save detach FW to 25, then
            # the next rebuild subtracts 2T again and the blank height drifts
            # by 4 mm per switch.  Vault legacy profiles still use the stored
            # length as the editable FW value.
            edited_fw = (
                engine_segment_length_to_ui(y["fw"])
                if cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(
                    self._phase6_input_snapshot
                )
                else _ui_len(y["fw"].get("len"))
            )
            effective_before = resolve_endcap_fw(
                self._phase6_input_snapshot, key, state=self._phase6_endcap_fw_state
            )
            if abs(float(edited_fw) - float(effective_before)) > 1e-9:
                commit_endcap_fw(
                    self._phase6_endcap_fw_state, key, edited_fw,
                    box_fw=_num(self._phase6_input_snapshot.get("fw", 25), 25),
                )
        self._phase6_input_snapshot["endcap_fw"] = deepcopy(self._phase6_endcap_fw_state)

        canonical_y_keys = {"ytop1", "fw", "endcap_d_core", "ybottom1"}
        if canonical_y_keys.issubset(y):
            values = read_endcap_xy_profiles(profiles, self._phase6_input_snapshot)
            values.pop("fw", None)
        else:
            # Arbitrary linked Y is derived. Only independently editable X values
            # are persisted here; the box chain rebuild below regenerates Y.
            values = (
                {}
                if flat_x else {
                    "yl1": _ui_len(x["yl1"].get("len")),
                    "yr1": _ui_len(x["yr1"].get("len")),
                }
            )
        _phase6_store_editor_values(self, values, notify=notify)

        if "w" in values:
            self._phase6_box_whd["w"] = original.get_int(values["w"])
        if "d" in values:
            self._phase6_box_whd["d"] = original.get_int(values["d"])
        w_text = str(self._phase6_box_whd["w"])
        d_text = str(self._phase6_box_whd["d"])
        if self.v_w.get() != w_text:
            self.v_w.set(w_text)
        if self.v_d.get() != d_text:
            self.v_d.set(d_text)

        # Both head and tail are regenerated from the one authoritative box
        # topology. Tail retains its native ordering inside the derivation.
        _phase6_rebuild_linked_endcaps(self)
        legacy = build_endcap_profile(self._phase6_input_snapshot)
        self.state.profiles_vault["封頭"] = clone_profile(legacy)
        self.state.profiles_vault["封尾"] = clone_profile(legacy)
    else:
        _phase6_store_editor_values(
            self, read_standard_part_profiles(key, profiles, self._phase6_input_snapshot), notify=notify
        )


def _fix11_load_part_holes(self, key):
    self.state.holes = {face: [] for face in self.state.faces}
    if key == "box_body":
        w = _num(self._phase6_input_snapshot.get("w", 500), 500)
        h = _num(self._phase6_input_snapshot.get("h", 600), 600)
        d = _num(self._phase6_input_snapshot.get("d", 200), 200)
        face_dims = {"left": (d, h), "back": (w, h), "right": (d, h)}
        face_map = {"left": "左面", "back": "正面", "right": "右面"}
        for face_key, features in self._phase6_part_face_features.get("box_body", {}).items():
            if face_key not in face_dims or face_key not in face_map:
                continue
            fw, fh = face_dims[face_key]
            self.state.holes[face_map[face_key]].extend(
                project_features_to_original_holes(features, fw, fh)
            )
        # Legacy/unfolded surface features are still carried losslessly. For
        # preview, supported simple holes are appended to the front view only.
        self.state.holes["正面"].extend(
            project_features_to_original_holes(self._phase6_part_features.get(key, ()), w, h)
        )
    elif _phase6_is_derived_physical_part_key(key):
        self.state.holes["正面"] = []
    else:
        width, height = _part_preview_size(self._phase6_input_snapshot, key)
        self.state.holes["正面"] = project_features_to_original_holes(
            self._phase6_part_features.get(key, ()), width, height
        )
    self.state.active_face = "正面"
    # HolesUI is deliberately hidden in the Phase6 workspace.  Its render()
    # performs a separate Matplotlib canvas.draw(), so drawing it on every part
    # switch wastes time without changing any visible UI.  The shared hole state
    # above is sufficient for the visible 3D renderer.


def _phase6_show_home(self):
    """Legacy compatibility: 新版沒有首頁，任何舊首頁動作都回到箱身。"""
    return self.activate_part("box_body")


def _fix11_activate_part(self, key, initial=False):
    navigation = _phase6_workspace_navigation(self)
    if not navigation.has_part(key):
        return
    _phase6_clear_navigation_residue(self)
    _phase6_hide_corner_data_canvas(self)
    if _phase6_is_box_body_physical_piece_key(key):
        self._phase6_box_body_active_piece_key = str(key)
    before_signature = None
    if not initial:
        try:
            before_signature = _phase6_manufacturing_state_signature(self)
        except Exception:
            before_signature = None
    # Assembly keeps a real part (normally box_body) as geometry backing.  A Tk
    # Menu radiobutton updates part_var before invoking this callback, so neither
    # active_part nor part_var can tell us that the user is leaving assembly.
    # Capture the display mode first: assembly/corner-data -> same backing part
    # is still a real view transition and must rebuild/show the input editor.
    was_non_single = str(getattr(self, "_phase6_3d_display_mode", "single") or "single") != "single"
    plan = navigation.plan_activation(
        key,
        initial=initial,
        leaving_non_single_view=was_non_single,
    )
    if not initial:
        self._phase6_3d_display_mode = "single"
        diagnostics = getattr(self, "assembly_diagnostics_frame", None)
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
    if not initial and getattr(self, "_phase6_pending_settings", None):
        self.flush_pending_settings()
    if plan.noop:
        return

    # A delayed edit/preview update from the previous part must never run after
    # the new part becomes active.  Cancel it before saving/switching state.
    pending = getattr(self, "_job", None)
    if pending:
        try:
            self.root.after_cancel(pending)
        except Exception:
            pass
        self._job = None

    if plan.save_outgoing:
        self._save_current_part()
        # Saving head/tail can normalize W/D through traced Tk variables.  That
        # work belongs to the outgoing part and may enqueue a delayed update;
        # cancel it before the new part becomes active.
        pending = getattr(self, "_job", None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
            self._job = None

    _phase6_mount_shared_content(self, "single")
    canvas_widget = self.renderer.canvas.get_tk_widget()
    # Do not expose the Matplotlib canvas yet. Build/select the editor and the
    # right settings page first so Tk settles on one final viewport size before
    # the first visible model render.

    navigation.begin_activation(plan)
    try:
        if hasattr(self, "part_var"):
            self.part_var.set(
                _phase6_part_label("box_body")
                if _phase6_is_box_body_physical_piece_key(key)
                else _phase6_part_label(key)
            )
        if hasattr(self, "part_buttons"):
            self._refresh_part_button_states()
        if hasattr(self, "remove_part_button"):
            self.remove_part_button.configure(state=("disabled" if key == "box_body" or _phase6_is_derived_physical_part_key(key) else "normal"))

        if key == "box_body":
            # Prepare the custom X-only editor BEFORE changing v_mode.  v_mode
            # owns one trace that rebuilds the notebook; the old code changed the
            # mode first and then rebuilt a second time after installing these
            # profiles.
            self.state.phase6_fold_ui_profiles = {"X": self.state.profiles_vault["箱身"]}
            self.state.phase6_fold_ui_tabs = ["X"]
            self.state.phase6_fold_ui_vault_key = "箱身"
            self.state.struct_mode = "vault"
            self.state.active_bend = "X"
            target_mode = "vault"
        else:
            self.state.phase6_fold_ui_profiles = None
            self.state.phase6_fold_ui_vault_key = None
            if key in {"head", "tail"}:
                default_profiles = build_endcap_xy_profiles(self._phase6_input_snapshot, part_key=key)
            elif _phase6_is_derived_physical_part_key(key):
                default_profiles = self.designer_workspace.profiles_for(key, {}) or {}
            else:
                default_profiles = build_standard_part_profiles(self._phase6_input_snapshot, key)
            profiles = self.designer_workspace.profiles_for(key)
            if profiles is None:
                profiles = default_profiles
                navigation.stash_profiles(key, profiles)
            self.state.profiles["X"] = clone_profile(profiles.get("X", []))
            self.state.profiles["Y"] = clone_profile(profiles.get("Y", []))
            self.state.phase6_fold_ui_tabs = _phase6_fold_tabs_for_part(
                self._phase6_input_snapshot, key
            )
            self.state.struct_mode = "standard"
            self.state.active_bend = (
                self.state.phase6_fold_ui_tabs[0]
                if self.state.phase6_fold_ui_tabs else "X"
            )
            self.state.enable_y = bool(self.state.profiles["Y"])
            if bool(self.v_ey.get()) != self.state.enable_y:
                self.v_ey.set(self.state.enable_y)
            target_mode = "standard"

        # Rebuild exactly once.  When the Tk variable really changes, its
        # existing on_mode_change trace performs the rebuild; otherwise do it
        # explicitly.  queue_update() is suppressed while switching.
        if self.v_mode.get() != target_mode:
            self.v_mode.set(target_mode)
        elif (
            target_mode == "standard"
            and self.state.phase6_fold_ui_tabs is None
            and list(getattr(self.bend_ui, "tabs", ())) == ["X", "Y"]
        ):
            # Standard parts all use the same X/Y notebook shell.  Rebuilding it
            # destroys/recreates dozens of Tk widgets and is especially costly on
            # Windows.  Select X and refresh values in-place instead.
            try:
                if self.bend_ui.nb.index("current") != 0:
                    self.bend_ui.nb.select(0)
            except Exception:
                pass
            self.bend_ui.refresh_active_profile()
        else:
            self.bend_ui.rebuild_tabs()

        # W/H/D at the top always remain the cabinet-global dimensions.  Avoid
        # no-op StringVar.set calls because each one owns a trace callback.
        for var, value in (
            (self.v_w, self._phase6_box_whd["w"]),
            (self.v_h, self._phase6_box_whd["h"]),
            (self.v_d, self._phase6_box_whd["d"]),
        ):
            text = str(value)
            if var.get() != text:
                var.set(text)
        self._load_part_holes(key)
    finally:
        navigation.finish_activation()

    # Finish the variable-height settings page before making the canvas visible;
    # otherwise Tk/Matplotlib renders once at the tall pre-settings size and once
    # again after the settings panel changes the viewport height.
    if hasattr(self, "settings_center"):
        settings_context = "box_body" if _phase6_is_box_body_physical_piece_key(key) else key
        _phase6_render_settings_context(self, settings_context)
        if bool(getattr(self, "_phase6_parameters_unlocked", False)):
            if not self.settings_center.winfo_manager():
                _phase6_pack_right_panel_above_canvas(self, self.settings_center)
        elif self.settings_center.winfo_manager():
            self.settings_center.pack_forget()
    # Settings/editor changes can leave a Matplotlib draw_idle queued even while
    # the preview widget is hidden. Cancel that stale paint before asking Tk to
    # settle non-canvas layout; otherwise it becomes an unnecessary first draw.
    canvas = self.renderer.canvas
    pending_draw = getattr(canvas, "_idle_draw_id", None)
    if pending_draw is not None:
        try:
            self.root.after_cancel(pending_draw)
        except Exception:
            pass
        try:
            canvas._idle_draw_id = None
        except Exception:
            pass
    try:
        self.root.update_idletasks()
    except Exception:
        pass
    if not canvas_widget.winfo_manager():
        canvas_widget.pack(fill=original.tk.BOTH, expand=True)
    _phase6_render_active_drawing_edge_controls(self)

    # Let Tk/Matplotlib establish the final pixel viewport before rendering the
    # model, but suppress the resize handler's paint.  FigureCanvasTkAgg.resize()
    # updates the Figure size first and only then calls draw_idle(); skipping that
    # one blank/stale paint means the authoritative model is painted exactly once
    # at the final viewport size.
    resize_draw_idle = getattr(canvas, "draw_idle", None)
    if callable(resize_draw_idle):
        canvas.draw_idle = lambda *args, **kwargs: None
    try:
        self.root.update_idletasks()
    except Exception:
        pass
    finally:
        if callable(resize_draw_idle):
            canvas.draw_idle = resize_draw_idle

    try:
        after_signature = _phase6_manufacturing_state_signature(self)
    except Exception:
        after_signature = None
    reason = (
        "display"
        if (not initial and before_signature is not None and before_signature == after_signature)
        else "geometry"
    )
    submit = getattr(self, "submit_update_intent", None)
    if callable(submit):
        submit(reason, commit=True)
    else:
        self.do_update()
    _phase6_refresh_persistent_structure_controls(self)
    _phase6_refresh_box_body_piece_selector(self)
    _phase6_refresh_back_panel_mode_control(self)
    _phase6_refresh_content_switch(self)


def _fix11_add_part(self, key):
    key = str(key)
    if key not in PART_LABELS:
        raise ValueError(f"不支援的板件: {key}")
    navigation = _phase6_workspace_navigation(self)
    if not navigation.has_part(key):
        if key in {"head", "tail"}:
            linked = build_linked_endcap_xy_profiles(
                self._phase6_input_snapshot, self.state.profiles_vault.get("箱身", [])
            )
            defaults = linked[key]
        elif key != "box_body":
            defaults = build_standard_part_profiles(self._phase6_input_snapshot, key)
        else:
            defaults = None
        navigation.add_part(
            key,
            default_profiles=defaults,
            default_features=(),
        )
        self._refresh_part_buttons()
        self._refresh_add_part_menu()
    self.activate_part(key)


def _fix11_remove_part(self, key):
    key = str(key or "")
    navigation = _phase6_workspace_navigation(self)
    mutation = navigation.remove_part(key)
    if not mutation.changed:
        return False
    if mutation.fallback_key:
        try:
            self.activate_part(mutation.fallback_key)
        except Exception:
            pass
    self._refresh_part_buttons()
    self._refresh_add_part_menu()
    _phase6_publish_live_state(self, force=True)
    return True


def _fix11_export(self):
    # Closing/exporting owns one complete snapshot handoff.  Do not also fire a
    # live settings callback here or the main GUI recalculates twice before the
    # designer can close.
    self._save_current_part(notify=False)
    current = self.designer_workspace.active_part
    navigation = _phase6_workspace_navigation(self)
    if current not in {"box_body", "head", "tail"}:
        navigation.set_switching(True)
        try:
            self.state.struct_mode = "vault"
            self.v_mode.set("vault")
            self.state.phase6_fold_ui_profiles = None
            self.state.phase6_fold_ui_tabs = None
            self.state.phase6_fold_ui_vault_key = None
            self.state.active_bend = "箱身"
            self.v_w.set(str(self._phase6_box_whd["w"]))
            self.v_h.set(str(self._phase6_box_whd["h"]))
            self.v_d.set(str(self._phase6_box_whd["d"]))
            self.bend_ui.rebuild_tabs()
        finally:
            navigation.set_switching(False)

    # FIX10 仍透過舊箱身／金庫型 adapter 匯出；為了相容保留它，
    # 但不可讓其中過期的箱身 profile 覆蓋新值
    # that were edited in the X/Y EndCap editor. Global W/H/D are owned by the
    # bridge, while EndCap fold/FW values are owned by the shared Phase6 snapshot.
    result = _FIX10_EXPORT(self)
    result["w"] = _ui_len(self._phase6_box_whd["w"])
    result["h"] = _ui_len(self._phase6_box_whd["h"])
    result["d"] = _ui_len(self._phase6_box_whd["d"])
    for name in ("yl1", "yr1", "ytop1", "ybottom1"):
        if name in self._phase6_input_snapshot:
            result[name] = _ui_len(self._phase6_input_snapshot[name])

    if current in {"head", "tail"}:
        profiles = self.designer_workspace.profiles_for(current)
        if profiles:
            endcap_values = read_endcap_xy_profiles(profiles, self._phase6_input_snapshot)
            result.update(endcap_values)
            self._phase6_input_snapshot.update(endcap_values)
            self._phase6_box_whd["w"] = _ui_len(endcap_values["w"])
            self._phase6_box_whd["d"] = _ui_len(endcap_values["d"])
    elif current == "box_body":
        # The box body is authoritative for the shared FW when it is the part
        # being edited. Preserve that value for later EndCap sessions.
        self._phase6_input_snapshot["fw"] = _ui_len(result["fw"])
    elif "fw" in self._phase6_input_snapshot:
        result["fw"] = _ui_len(self._phase6_input_snapshot["fw"])

    owner_workspace = self.designer_workspace.snapshot()
    for key, profiles in owner_workspace["part_profiles"].items():
        result.update(read_standard_part_profiles(key, profiles, self._phase6_input_snapshot))
    result["assembly_type"] = assembly_intent_value(getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY))
    result["endcap_fw"] = deepcopy(getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(result)))
    result["endcap_bottom_wrap"] = deepcopy(
        getattr(self, "_phase6_endcap_bottom_wrap_state", normalize_endcap_bottom_wrap_state(result))
    )
    result["existing_parts"] = list(owner_workspace["existing_parts"])
    result["active_part"] = current
    result["part_profiles"] = deepcopy(owner_workspace["part_profiles"])
    result["part_features"] = deepcopy(owner_workspace["part_features"])
    result["part_face_features"] = deepcopy(owner_workspace["part_face_features"])
    result["settings"] = dict(self._settings_values)
    result["corner_state"] = deepcopy(getattr(self, "_phase6_corner_state", {}))
    result["corner_pair_same"] = deepcopy(getattr(self, "_phase6_corner_pair_same", {}))
    result.update(self._settings_values)
    return result



def _phase6_view_property(name, default=None):
    def getter(self):
        view = getattr(self, "final_scene_view", None)
        return getattr(view, name, default) if view is not None else default
    def setter(self, value):
        view = getattr(self, "final_scene_view", None)
        if view is not None:
            setattr(view, name, value)
    return property(getter, setter)







def _set_profile_phase6_len(profile, key, value):
    for seg in profile or ():
        if seg.get("phase6_key") == key:
            seg["len"] = _ui_len(value)
            return True
    return False


def _get_profile_phase6_len(profile, key, default=None):
    for seg in profile or ():
        if seg.get("phase6_key") == key:
            return _ui_len(seg.get("len"))
    return default


def _phase6_endcap_depth_comp_t(self):
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    return cabinet_family_policy.endcap_depth_comp_t(snapshot)


def _propagate_endcap_derived_cores(self, w, d):
    t = _num(self._phase6_input_snapshot.get("t", 2), 2)
    x_core = max(0.0, float(w) - 4.0 * t)
    y_core = max(0.0, float(d) - _phase6_endcap_depth_comp_t(self) * t)
    for key in ("head", "tail"):
        profiles = self._phase6_part_profiles.get(key)
        if profiles:
            _set_profile_phase6_len(profiles.get("X"), "endcap_w_core", x_core)
            _set_profile_phase6_len(profiles.get("Y"), "endcap_d_core", y_core)
    if getattr(self, "active_part_key", None) in {"head", "tail"}:
        _set_profile_phase6_len(self.state.profiles.get("X"), "endcap_w_core", x_core)
        _set_profile_phase6_len(self.state.profiles.get("Y"), "endcap_d_core", y_core)


def _sync_active_endcap_and_global_whd(self):
    top_w = original.get_int(self.v_w.get())
    top_d = original.get_int(self.v_d.get())
    last_w = original.get_int(self._phase6_last_w if self._phase6_last_w is not None else top_w)
    last_d = original.get_int(self._phase6_last_d if self._phase6_last_d is not None else top_d)
    t = _num(self._phase6_input_snapshot.get("t", 2), 2)
    depth_comp_t = _phase6_endcap_depth_comp_t(self)

    x_core = _get_profile_phase6_len(self.state.profiles.get("X"), "endcap_w_core")
    y_core = _get_profile_phase6_len(self.state.profiles.get("Y"), "endcap_d_core")
    expected_x = _ui_len(last_w - 4.0 * t)
    expected_y = _ui_len(last_d - depth_comp_t * t)

    if top_w != last_w:
        new_w = top_w
    elif x_core is not None and x_core != expected_x:
        new_w = _ui_len(x_core + 4.0 * t)
        self.v_w.set(str(new_w))
    else:
        new_w = last_w

    if top_d != last_d:
        new_d = top_d
    elif y_core is not None and y_core != expected_y:
        new_d = _ui_len(y_core + depth_comp_t * t)
        self.v_d.set(str(new_d))
    else:
        new_d = last_d

    self._phase6_box_whd["w"] = new_w
    self._phase6_box_whd["h"] = original.get_int(self.v_h.get())
    self._phase6_box_whd["d"] = new_d
    self._phase6_input_snapshot["w"] = new_w
    self._phase6_input_snapshot["h"] = self._phase6_box_whd["h"]
    self._phase6_input_snapshot["d"] = new_d
    self._phase6_last_w = new_w
    self._phase6_last_d = new_d
    _propagate_endcap_derived_cores(self, new_w, new_d)

_FIX10_DO_UPDATE = Phase6FoldDesignerApp.do_update

def _fix11_do_update(self):
    key = getattr(self, "active_part_key", "box_body")
    if key == "box_body":
        # 折彎編輯器的軸向是唯一基準；舊金庫型 Renderer 曾使用
        # active_bend="箱身" only as a visual highlight flag; mutating the shared
        # editor state here can race Tk notebook callbacks and makes the custom
        # X-only profile get indexed by "箱身" (KeyError).
        result = _FIX10_DO_UPDATE(self)
        _phase6_replace_mapping(self, "_phase6_box_whd", {
            "w": original.get_int(self.v_w.get()),
            "h": original.get_int(self.v_h.get()),
            "d": original.get_int(self.v_d.get()),
        })
        self._phase6_input_snapshot.update(self._phase6_box_whd)
        _propagate_endcap_derived_cores(self, self._phase6_box_whd["w"], self._phase6_box_whd["d"])
        # The inherited MainApp constructor briefly owns an unannotated legacy
        # 5-row visual profile before load_phase6_snapshot() installs D-W-D
        # semantic metadata. Do not derive end caps from that bootstrap state.
        if getattr(self, "_phase6_sync_ready", False):
            _phase6_rebuild_linked_endcaps(self)
        return result
    if key in {"head", "tail"}:
        _sync_active_endcap_and_global_whd(self)
        return original.MainApp.do_update(self)

    # All other parts keep their local fold profiles, but W/H/D at the top are
    # always the cabinet-global values.
    _phase6_replace_mapping(self, "_phase6_box_whd", {
        "w": original.get_int(self.v_w.get()),
        "h": original.get_int(self.v_h.get()),
        "d": original.get_int(self.v_d.get()),
    })
    self._phase6_input_snapshot.update(self._phase6_box_whd)
    return original.MainApp.do_update(self)


_PHASE6_RENDERING_DO_UPDATE = _fix11_do_update

_PHASE6_FULL_UPDATE_REASONS = frozenset({"geometry", "assembly", "baseline"})
_PHASE6_DISPLAY_UPDATE_REASONS = frozenset({"display", "annotation", "camera"})

def _phase6_render_committed_view(self):
    return _phase6_final_scene_adapter(self).render_committed()


def _phase6_execute_update_intents(self, reasons):
    return execute_fold_designer_update_reasons(
        self,
        reasons,
        full_update=lambda: _PHASE6_RENDERING_DO_UPDATE(self),
        render_committed=lambda: _phase6_render_committed_view(self),
        publish_if_changed=lambda: _phase6_publish_live_state(self),
    )


def _phase6_submit_update_intent(self, reason, *, commit=False):
    return submit_fold_designer_update_intent(
        self,
        reason,
        commit=commit,
        executor=lambda reasons: _phase6_execute_update_intents(self, reasons),
    )


def _phase6_preview_aware_do_update(self):
    """Legacy compatibility wrapper: submit intent, never execute update/render."""
    return self.submit_update_intent("geometry", commit=True)


def _phase6_set_3d_preview_enabled(self, enabled):
    return _phase6_final_scene_adapter(self).set_preview_enabled(enabled)


def _phase6_queue_update(self, *args):
    return queue_fold_designer_update(
        self,
        executor=lambda reasons: _phase6_execute_update_intents(self, reasons),
    )

install_fold_designer_bridge_facade(
    Phase6FoldDesignerApp,
    {
        "__getattr__": _phase6_legacy_getattr,
        "_phase6_last_cutting_mesh": _phase6_view_property("last_cutting_mesh", []),
        "_phase6_last_cutting_material": _phase6_view_property("last_cutting_material", None),
        "_phase6_zoom_scale": _phase6_view_property("zoom_scale", 1.0),
        "__init__": _fix11_init,
        "_refresh_part_buttons": _fix11_refresh_part_buttons,
        "_refresh_part_button_states": _fix11_refresh_part_button_states,
        "_refresh_add_part_menu": _fix11_refresh_add_part_menu,
        "_save_current_part": _fix11_save_current_part,
        "_load_part_holes": _fix11_load_part_holes,
        "activate_part": _fix11_activate_part,
        "show_home": _phase6_show_home,
        "on_3d_scroll": _phase6_on_3d_scroll,
        "add_part": _fix11_add_part,
        "select_part": _fix11_select_part,
        "remove_selected_part": _fix11_remove_selected_part,
        "remove_part": _fix11_remove_part,
        "available_parts": property(_legacy_available_parts_get, _legacy_available_parts_set),
        "active_part_key": property(_legacy_active_part_get, _legacy_active_part_set),
        "selected_part_key": property(_legacy_selected_part_get, _legacy_selected_part_set),
        "_phase6_part_profiles": property(_legacy_part_profiles_get, _legacy_part_profiles_set),
        "_phase6_part_features": property(_legacy_part_features_get, _legacy_part_features_set),
        "_phase6_part_face_features": property(_legacy_part_face_features_get, _legacy_part_face_features_set),
        "_phase6_workspace_dirty": property(_legacy_workspace_dirty_get, _legacy_workspace_dirty_set),
        "_phase6_switching_part": property(_legacy_switching_part_get, _legacy_switching_part_set),
        "_phase6_box_body_active_piece_key": property(_legacy_box_body_active_piece_get, _legacy_box_body_active_piece_set),
        "apply_external_assembly_type": _phase6_apply_external_assembly_type,
        "export_phase6_snapshot": _fix11_export,
        "toggle_baseline_data": _phase6_settings_panel_toggle_baseline,
        "save_current_settings_as_defaults": _phase6_save_current_settings_as_defaults,
        "flush_pending_settings": _phase6_flush_pending_settings,
        "_phase6_publish_live_state": _phase6_publish_live_state,
        "_phase6_resolve_manufacturing_geometry": _phase6_resolve_manufacturing_geometry,
        "apply_external_settings": _phase6_apply_external_settings,
        "apply_external_model": _phase6_apply_external_model,
        "apply_external_sync": _phase6_apply_external_sync,
        "_phase6_refresh_corner_data_unfold_view": _phase6_refresh_corner_data_unfold_view,
        "on_ui_text_size_changed": _phase6_on_ui_text_size_changed,
        "apply_external_corner_state": _phase6_apply_external_corner_state,
        "reset_initial_values": _phase6_reset_initial_values,
        "save_project_file": _phase6_save_project_file,
        "save_project_file_as": _phase6_save_project_file_as,
        "load_project_file": _phase6_load_project_file,
        "submit_update_intent": _phase6_submit_update_intent,
        "set_3d_preview_enabled": _phase6_set_3d_preview_enabled,
    },
)
