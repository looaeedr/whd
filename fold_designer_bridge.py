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
from typing import Mapping, MutableMapping
from whd_theme import WHD_THEME, apply_ttk_dark_theme, configure_tk_menu

from ae_engine.cabinet_types import policy as cabinet_family_policy
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_part_navigation import (
    NavigationIntent,
    NavigationMemory,
    NavigationRequest,
    box_body_piece_keys as _dm7_box_body_piece_keys,
    is_box_body_physical_piece_key as _dm7_is_box_body_physical_piece_key,
    operator_part_selector_keys as _dm7_operator_part_selector_keys,
    operator_part_label as _dm7_operator_part_label,
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
from phase6_navigation_view_adapter import (
    refresh_structure_tree as _navigation_view_refresh_structure_tree,
    refresh_box_body_piece_selector as _navigation_view_refresh_box_body_piece_selector,
    on_structure_tree_select as _navigation_view_on_structure_tree_select,
    set_structure_tree_visibility as _navigation_view_set_structure_tree_visibility,
    on_box_body_piece_tab_changed as _navigation_view_on_box_body_piece_tab_changed,
    refresh_sticky_structure_tree as _navigation_view_refresh_sticky_structure_tree,
    clear_navigation_residue as _navigation_view_clear_navigation_residue,
    refresh_content_switch as _navigation_view_refresh_content_switch,
    build_content_switch as _navigation_view_build_content_switch,
    build_part_navigation_widgets as _navigation_view_build_part_navigation_widgets,
    on_structure_tree_click as _navigation_view_on_structure_tree_click,
    refresh_part_selector as _navigation_view_refresh_part_selector,
    refresh_part_button_states as _navigation_view_refresh_part_button_states,
    refresh_add_part_menu as _navigation_view_refresh_add_part_menu,
    hide_corner_data_canvas as _navigation_view_hide_corner_data_canvas,
    show_corner_data_mode as _navigation_view_show_corner_data_mode,
    project_assembly_mode as _navigation_view_project_assembly_mode,
    project_active_part_selector as _navigation_view_project_active_part_selector,
    finalize_single_part_layout as _navigation_view_finalize_single_part_layout,
    refresh_persistent_structure_controls as _navigation_view_refresh_persistent_structure_controls,
    pack_right_panel_above_canvas as _navigation_view_pack_right_panel_above_canvas,
    hide_original_structure_mode_controls as _navigation_view_hide_original_structure_mode_controls,
)
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
from gui_modules.application.receiving_set_bay_adapter import (
    ReceivingSetBayAdapter,
    receiving_layout_stable_ids,
)
from gui_modules.application.receiving_set_bay_controls import (
    RECEIVING_SWITCH_BRANDS,
    build_receiving_set_bay_controls,
    open_receiving_layer_preview,
    refresh_receiving_layer_rows,
)
from gui_modules.application.receiving_switch_layout_adapter import (
    ReceivingSwitchLayoutAdapter,
)
from ae_engine.receiving_layout import (
    ensure_receiving_layout,
    project_receiving_bay_legacy_aliases,
)
from ae_engine.receiving_switch_layout import (
    RECEIVING_SWITCH_LAYOUT_KEY,
    normalize_receiving_switch_layout,
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
    """Compatibility delegate; composition owns derived-sync orchestration."""
    return _phase6_composition(self).sync_authoritative_derived_parts(globals())

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
        self._phase6_receiving_set_bay_adapter = None
        if _phase6_receiving_layout_applicable(self):
            _phase6_receiving_adapter(self, reset=True)
            _phase6_sync_receiving_current_bay(self, validate_common=False)
            snapshot = dict(self._phase6_input_snapshot)
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
    return _phase6_composition(self).apply_settings_profile_projection(
        globals(), plan, render=bool(render)
    )


def _phase6_refresh_profiles_from_settings(
    self,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
):
    return _phase6_composition(self).refresh_profiles_from_settings(
        globals(),
        reset_box_profile=bool(reset_box_profile),
        reset_all_profiles=bool(reset_all_profiles),
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
    return _phase6_composition(self).flush_pending_settings(globals())


def _phase6_stage_setting_update(self, key, value):
    return _phase6_composition(self).stage_setting_update(
        globals(), key, value
    )


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
    return _phase6_composition(self).corner_pair_var_changed(
        globals(), part_key, pair_key, var
    )


def _phase6_corner_type_selected(self, part_key, target_key):
    return _phase6_composition(self).corner_type_selected(
        globals(), part_key, target_key
    )


def _phase6_corner_mode_selected(self, part_key, target_key):
    return _phase6_composition(self).corner_mode_selected(
        globals(), part_key, target_key
    )


def _phase6_corner_target_var_changed(self, part_key, target_key):
    return _phase6_composition(self).corner_target_var_changed(
        globals(), part_key, target_key
    )


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
    return _phase6_composition(self).on_baseline_model_changed(
        globals(), *_args
    )


def _phase6_collect_workspace_state(self):
    return _phase6_composition(self).collect_workspace_state(globals())


def _phase6_relief_profile_fingerprint(profile):
    from phase6_assembly_relief_state import relief_profile_fingerprint

    return relief_profile_fingerprint(profile)

def _phase6_current_relief_source_signature(self, required):
    return _phase6_composition(self).current_relief_source_signature(
        globals(), required
    )


def _phase6_relief_source_matches_current(saved_source, current_source, required):
    from phase6_assembly_relief_state import source_matches_current

    return source_matches_current(saved_source, current_source, required)

def _phase6_serialize_assembly_relief_state(self):
    return _phase6_composition(self).serialize_assembly_relief_state(
        globals()
    )


def _phase6_corner_transaction_payload(self):
    return _phase6_composition(self).corner_transaction_payload(globals())


def _phase6_publish_live_state(self, *, force=False):
    """Compatibility port: composition owns live-sync publication effects."""
    return _phase6_composition(self).publish_live_state(globals(), force=force)


def _phase6_build_project_snapshot(self):
    """Compatibility port: composition owns project snapshot orchestration."""
    return _phase6_composition(self).build_project_snapshot(globals())


def _phase6_load_project_file(self):
    """Compatibility port: composition owns project-load application effects."""
    return _phase6_composition(self).load_project_file(globals())


def _phase6_save_project_file(self, *, save_as=False):
    """Compatibility port: composition owns project-save application effects."""
    return _phase6_composition(self).save_project_file(
        globals(), save_as=bool(save_as)
    )


def _phase6_save_project_file_as(self):
    return _phase6_save_project_file(self, save_as=True)




def _phase6_refresh_active_endcap_from_linked(self, linked):
    return _phase6_composition(self).refresh_active_endcap_from_linked(
        globals(), linked
    )

def _phase6_commit_endcap_fw_state(self):
    return _phase6_composition(self).commit_endcap_fw_state(globals())

def _phase6_set_endcap_fw_override(self, part_key, value):
    return _phase6_composition(self).set_endcap_fw_override(
        globals(), part_key, value
    )

def _phase6_on_endcap_fw_value_selected(self, part_key, value_var):
    return _phase6_composition(self).on_endcap_fw_value_selected(
        globals(), part_key, value_var
    )

def _phase6_receiving_layout_applicable(self):
    return _phase6_composition(self).receiving_layout_applicable()


def _phase6_confirm_receiving_destructive(self, stable_ids):
    return _phase6_composition(self).confirm_receiving_destructive(
        stable_ids
    )


def _phase6_receiving_adapter(self, *, reset=False):
    return _phase6_composition(self).receiving_adapter(
        globals(), reset=bool(reset)
    )


def _phase6_sync_receiving_current_bay(
    self,
    *,
    validate_common=True,
    refresh_controls=True,
):
    return _phase6_composition(self).sync_receiving_current_bay(
        globals(),
        validate_common=bool(validate_common),
        refresh_controls=bool(refresh_controls),
    )


def _phase6_commit_receiving_current_bay_controls(self):
    return _phase6_composition(
        self
    ).commit_receiving_current_bay_controls(globals())


def _phase6_receiving_switch_adapter(self, *, reset=False):
    return _phase6_composition(self).receiving_switch_adapter(
        globals(), reset=bool(reset)
    )


def _phase6_mark_receiving_switch_layout_dirty(self, adapter):
    return _phase6_composition(self).mark_receiving_switch_layout_dirty(
        globals(), adapter
    )


def _phase6_refresh_receiving_set_bay_control(self):
    return _phase6_composition(self).refresh_receiving_set_bay_control(
        globals()
    )


def _phase6_on_receiving_switch_brand_selected(self, brand):
    return _phase6_composition(self).on_receiving_switch_brand_selected(
        globals(), brand
    )


def _phase6_add_receiving_layer(self):
    return _phase6_composition(self).add_receiving_layer(globals())


def _phase6_resize_receiving_bays(self, layer_index, delta):
    return _phase6_composition(self).resize_receiving_bays(
        globals(), layer_index, delta
    )


def _phase6_confirm_receiving_opening(
    self,
    layer_index,
    connection_index,
    brand,
):
    return _phase6_composition(self).confirm_receiving_opening(
        globals(),
        layer_index,
        connection_index,
        brand,
    )


def _phase6_open_receiving_layer_preview(self, layer_index):
    return _phase6_composition(self).open_receiving_layer_preview(
        globals(), layer_index
    )


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
    return _phase6_composition(
        self
    ).back_panel_mode_control_is_applicable(globals())


def _phase6_refresh_back_panel_mode_control(self):
    return _phase6_composition(self).refresh_back_panel_mode_control(
        globals()
    )


def _phase6_select_back_panel_mode(self, var):
    return _phase6_composition(self).select_back_panel_mode(
        globals(), var
    )


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
    return _phase6_composition(self).on_assembly_type_selected(
        globals(), *_args
    )


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
    return _phase6_composition(self).on_endcap_edge_relation_selected(
        globals(), part_key, edge
    )

def _phase6_ensure_drawing_edge_hosts(self):
    return _phase6_composition(self).ensure_drawing_edge_hosts(globals())

def _phase6_clear_drawing_edge_controls(self):
    return _phase6_composition(self).clear_drawing_edge_controls()

def _phase6_place_drawing_edge_host(host, edge):
    plan = Phase6CornerDataViewAdapter.edge_host_placement(edge)
    if plan:
        host.place(**plan)

def _phase6_render_endcap_edge_controls(self, *, part_key):
    return _phase6_composition(self).render_endcap_edge_controls(
        globals(), part_key=part_key
    )

def _phase6_commit_base_plate_edge_shrink(self, edge, raw_value):
    return _phase6_composition(self).commit_base_plate_edge_shrink(
        globals(), edge, raw_value
    )

def _phase6_render_base_plate_edge_controls(self):
    return _phase6_composition(self).render_base_plate_edge_controls(globals())

def _phase6_render_active_drawing_edge_controls(self):
    return _phase6_composition(self).render_active_drawing_edge_controls(globals())

def _phase6_on_box_symmetry_changed(self):
    return _phase6_composition(self).on_box_symmetry_changed(globals())

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



def _phase6_ensure_settings_panel(self):
    return _phase6_composition(self).settings_panel(globals())

def _phase6_sync_settings_panel_compat(self):
    return _phase6_composition(self).sync_settings_panel_compat()


def _phase6_settings_panel_toggle_baseline(self):
    return _phase6_composition(self).settings_panel_toggle_baseline()


def _phase6_invalidate_settings_page(self, context):
    return _phase6_composition(self).invalidate_settings_page(context)


def _phase6_render_settings_context(self, context):
    return _phase6_composition(self).render_settings_context(
        globals(), context
    )


def _phase6_save_current_settings_as_defaults(self):
    return _phase6_composition(self).save_current_settings_as_defaults()


def _phase6_apply_external_settings(self, updates):
    return _phase6_composition(self).apply_external_settings(
        globals(), updates
    )


def _phase6_apply_external_model(self, model):
    return _phase6_composition(self).apply_external_model(
        globals(), model
    )


def _phase6_apply_external_sync(self, envelope):
    return _phase6_composition(self).apply_external_sync(
        globals(), envelope
    )


def _phase6_left_workspace_width(value) -> int:
    """Return the visual-review width floor for each supported UI text scale."""
    key = normalize_ui_text_size(value)
    return {"small": 338, "medium": 430, "large": 480}[key]


def _phase6_update_left_workspace_width(self, key=None):
    return _phase6_composition(self).update_left_workspace_width(
        globals(), key
    )


def _phase6_apply_ui_text_size(self, key):
    return _phase6_composition(self).apply_ui_text_size(globals(), key)


def _phase6_on_ui_text_size_changed(self, *_args):
    return _phase6_composition(self).on_ui_text_size_changed(
        globals(), *_args
    )


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
    """Compatibility port to the pure operator part-label projection owner."""
    return _dm7_operator_part_label(
        value, snapshot=snapshot, base_labels=PART_LABELS
    )


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
    return _phase6_composition(self).status_projection(globals())


def _phase6_refresh_status_bar(self):
    return _phase6_composition(self).refresh_status_bar(globals())


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
    return _phase6_composition(self).reset_initial_values(globals())


def _phase6_save_settings_context_as_defaults(self, context):
    return _phase6_composition(self).save_settings_context_as_defaults(
        globals(), context
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



def _phase6_final_scene_view_request(self):
    """Compatibility delegate for final-scene request construction."""
    return _phase6_final_scene_adapter(self).build_request()



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
    return _phase6_composition(self).on_assembly_diagnostic_changed()


def _phase6_create_relief_promotion_candidates(self):
    return _phase6_composition(self).create_relief_promotion_candidates(
        globals()
    )


def _phase6_update_assembly_diagnostic_status(self):
    return _phase6_composition(self).update_assembly_diagnostic_status(
        globals()
    )


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
    return _navigation_view_refresh_persistent_structure_controls(
        self,
        structure_label=_BOX_STRUCTURE_LABELS[active],
        structure_fixed=cabinet_family_policy.family_fixes_box_body_structure(getattr(self, "_phase6_input_snapshot", {}) or {}),
        assembly_label=ASSEMBLY_TYPE_LABELS[getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)],
    )


def _phase6_toggle_parameter_panel(self):
    return _phase6_composition(self).toggle_parameter_panel(globals())

def _phase6_pack_right_panel_above_canvas(self, widget):
    """Delegate right-panel packing order to the Tk view owner."""
    return _navigation_view_pack_right_panel_above_canvas(
        self, widget, tk_top=original.tk.TOP, tk_x=original.tk.X
    )

def _hide_original_structure_mode_controls(root_widget):
    """Delegate prototype-control hiding to the Tk view owner."""
    return _navigation_view_hide_original_structure_mode_controls(
        root_widget, targets={"標準十字型", "金庫型(三件)", "結構:"}
    )

def _phase6_on_assembly_part_visibility_changed(self):
    return _phase6_composition(self).on_assembly_part_visibility_changed()


def _phase6_install_assembly_panel_aliases(self, owner):
    return _phase6_composition(self).install_assembly_panel_aliases(owner)


_phase6_assembly_presentation_groups = legacy_assembly_presentation_groups


def _phase6_current_assembly_panel_part_keys(self) -> tuple[str, ...]:
    return _phase6_composition(self).current_assembly_panel_part_keys()


def _phase6_refresh_assembly_parts_panel_if_topology_changed(self) -> bool:
    return _phase6_composition(
        self
    ).refresh_assembly_parts_panel_if_topology_changed(globals())


def _phase6_refresh_assembly_parts_panel(self):
    return _phase6_composition(self).refresh_assembly_parts_panel(globals())


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
    _navigation_view_build_part_navigation_widgets(
        self,
        tk=original.tk,
        ttk=original.ttk,
        configure_menu=configure_tk_menu,
        hidden_foreground=WHD_THEME["muted_text"],
        on_structure_tree_select=lambda event: _phase6_on_structure_tree_select(self, event),
        on_structure_tree_click=lambda event: _phase6_on_structure_tree_click(self, event),
        on_box_body_piece_tab_changed=lambda event: _phase6_on_box_body_piece_tab_changed(self, event),
        remove_selected_part=self.remove_selected_part,
    )

    _phase6_build_content_switch(self)

    # #440 correction: no fixed outer wrapper around mode content.
    # The three mode surfaces are direct siblings under self.left and exactly
    # one is mapped at a time in the same layout slot.  Compatibility aliases
    # do not create any additional Frame.
    self.input_content_host = original.ttk.Frame(self.left)
    self.fold_editor_host = self.input_content_host
    self.shared_content_host = self.left

    # Operator-facing Receiving topology is projected as one row per 層.  The
    # existing ReceivingSetBayAdapter remains the topology owner; row widgets
    # never execute 3D/manufacturing work.
    receiving_controls = build_receiving_set_bay_controls(
        self.input_content_host,
        tk=original.tk,
        ttk=original.ttk,
        on_switch_brand_selected=lambda brand: _phase6_on_receiving_switch_brand_selected(
            self, brand
        ),
        on_add_layer=lambda: _phase6_add_receiving_layer(self),
    )
    self.receiving_layer_controls = receiving_controls
    self.receiving_set_bay_control = receiving_controls.frame
    self.receiving_switch_brand_var = receiving_controls.switch_brand_var
    self.receiving_switch_brand_selector = receiving_controls.switch_brand_selector

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
    return _navigation_view_refresh_sticky_structure_tree(self)

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
    return _navigation_view_clear_navigation_residue(self)

def _phase6_refresh_content_switch(self):
    return _navigation_view_refresh_content_switch(self)

def _phase6_build_content_switch(self):
    return _navigation_view_build_content_switch(self, frame_factory=original.ttk.Frame)

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
    """Compatibility wrapper for the dedicated navigation Tk view owner."""
    return _navigation_view_refresh_structure_tree(
        self,
        project_rows=_phase6_structure_tree_rows,
        label_for_key=lambda key, snapshot=None: _phase6_part_label(
            key, snapshot=snapshot
        ),
        visibility_var=lambda key: _phase6_structure_tree_visibility_var(self, key),
    )

def _phase6_on_structure_tree_select(self, _event=None):
    return _navigation_view_on_structure_tree_select(
        self,
        show_assembly=lambda: _phase6_show_assembly(self),
        show_corner_data=lambda: _phase6_show_corner_data(self),
        activate_part=lambda key: _phase6_activate_operator_part(self, key),
        refresh_tree=lambda: _phase6_refresh_structure_tree(self),
    )

def _phase6_set_structure_tree_visibility(self, key, visible):
    owner = getattr(self, "_phase6_assembly_panel_owner", None)
    return _navigation_view_set_structure_tree_visibility(
        self, key, visible,
        visibility_var=lambda part_key: _phase6_structure_tree_visibility_var(self, part_key),
        notify_visibility_changed=(owner.notify_visibility_changed if owner is not None else None),
        refresh_tree=lambda: _phase6_refresh_structure_tree(self),
    )

def _phase6_on_structure_tree_click(self, event):
    return _navigation_view_on_structure_tree_click(
        self, event,
        visibility_var=lambda key: _phase6_structure_tree_visibility_var(self, key),
        set_visibility=lambda key, visible: _phase6_set_structure_tree_visibility(self, key, visible),
    )

def _phase6_refresh_box_body_piece_selector(self):
    """Compatibility wrapper for hidden BoxBody child-tab view projection."""
    return _navigation_view_refresh_box_body_piece_selector(
        self,
        piece_keys=_phase6_box_body_piece_keys,
        label_for_key=lambda key: _phase6_part_label(key),
        frame_factory=original.ttk.Frame,
        resolve_remembered=lambda parts, remembered: _dm7_resolve_navigation(
            parts,
            NavigationRequest(None, NavigationIntent.RESTORE_CHILD_CONTEXT),
            NavigationMemory(remembered or None),
        ),
    )

def _phase6_on_box_body_piece_tab_changed(self, _event=None):
    return _navigation_view_on_box_body_piece_tab_changed(
        self,
        activate_part=lambda key: _phase6_activate_operator_part(self, key),
        resolve_operator_part=lambda key: _phase6_resolve_operator_part_key(self, key),
    )

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
    return _navigation_view_refresh_part_selector(
        self,
        tk_end=original.tk.END,
        operator_selector_keys=_phase6_operator_part_selector_keys,
        label_for_key=lambda key, snapshot=None: _phase6_part_label(key, snapshot=snapshot),
        is_box_piece=_phase6_is_box_body_physical_piece_key,
        show_assembly=lambda: _phase6_show_assembly(self),
        show_corner_data=lambda: _phase6_show_corner_data(self),
        activate_part=lambda key: _phase6_activate_operator_part(self, key),
        refresh_button_states=lambda: _fix11_refresh_part_button_states(self),
        refresh_piece_selector=lambda: _phase6_refresh_box_body_piece_selector(self),
        refresh_back_panel=lambda: _phase6_refresh_back_panel_mode_control(self),
        refresh_assembly_panel=(lambda: _phase6_refresh_assembly_parts_panel(self)) if getattr(self, "assembly_parts_panel", None) is not None else None,
        refresh_structure_tree=lambda: _phase6_refresh_structure_tree(self),
        refresh_content_switch=lambda: _phase6_refresh_content_switch(self),
        refresh_status_bar=lambda: _phase6_refresh_status_bar(self),
    )

def _fix11_refresh_part_button_states(self):
    return _navigation_view_refresh_part_button_states(
        self, is_derived_part=_phase6_is_derived_physical_part_key
    )

def _phase6_corner_data_part_keys(self) -> tuple[str, ...]:
    return _phase6_composition(self).corner_data_part_keys()


def _phase6_corner_data_navigation_rows(self) -> tuple[tuple[str, int], ...]:
    return _phase6_composition(self).corner_data_navigation_rows(globals())


def _phase6_select_corner_data_part(self, key, *, refresh_view=True):
    return _phase6_composition(self).select_corner_data_part(
        globals(), key, refresh_view=bool(refresh_view)
    )


def _phase6_corner_data_info_request_for_key(self, part_key, render_data):
    return _phase6_composition(self).corner_data_info_request_for_key(
        globals(), part_key, render_data
    )


def _phase6_corner_data_info_text_for_key(self, part_key, render_data):
    return _phase6_composition(self).corner_data_info_text_for_key(
        globals(), part_key, render_data
    )


def _phase6_corner_data_unfold_projection_for_key(self, part_key):
    return _phase6_composition(self).corner_data_unfold_projection_for_key(
        globals(), part_key
    )


def _phase6_corner_data_unfold_projections(self, part_keys):
    return _phase6_composition(self).corner_data_unfold_projections(
        globals(), part_keys
    )


def _phase6_corner_data_unfold_projection(self):
    return _phase6_composition(self).corner_data_unfold_projection(globals())


def _phase6_refresh_corner_data_unfold_view(self):
    return _phase6_composition(self).refresh_corner_data_unfold_view(globals())


def _phase6_corner_data_back_panel_mode_is_applicable(self):
    return _phase6_composition(
        self
    ).corner_data_back_panel_mode_is_applicable(globals())


def _phase6_refresh_corner_data_back_panel_mode_control(self):
    return _phase6_composition(
        self
    ).refresh_corner_data_back_panel_mode_control(globals())


def _phase6_refresh_corner_data_parts_panel(self) -> tuple[str, ...]:
    return _phase6_composition(self).refresh_corner_data_parts_panel(globals())


def _phase6_on_corner_data_mousewheel(self, event):
    return _phase6_composition(self).on_corner_data_mousewheel(
        globals(), event
    )


def _phase6_prepare_corner_data_canvas(self):
    return _phase6_composition(self).prepare_corner_data_canvas(globals())


def _phase6_hide_corner_data_canvas(self):
    """Delegate corner-data/Matplotlib visibility projection to the view owner."""
    return _navigation_view_hide_corner_data_canvas(
        self,
        visibility_plan=_phase6_corner_data_view(self).canvas_visibility_plan(False),
        tk_both=original.tk.BOTH,
    )

def _phase6_show_corner_data(self):
    """Switch to view-only Corner Data through the navigation view owner."""
    return _navigation_view_show_corner_data_mode(
        self,
        frame_factory=lambda parent: original.ttk.Frame(parent, padding=6),
        mount_shared_content=lambda mode: _phase6_mount_shared_content(self, mode),
        prepare_canvas=lambda: _phase6_prepare_corner_data_canvas(self),
        refresh_parts_panel=lambda: _phase6_refresh_corner_data_parts_panel(self),
        refresh_unfold=lambda: _phase6_refresh_corner_data_unfold_view(self),
        refresh_part_button_states=getattr(self, "_refresh_part_button_states", None),
        refresh_content_switch=lambda: _phase6_refresh_content_switch(self),
    )

def _phase6_show_assembly(self, initial=False):
    """Show assembly while Bridge retains save/update/manufacturing authority only."""
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
    _navigation_view_project_assembly_mode(
        self,
        mount_shared_content=lambda mode: _phase6_mount_shared_content(self, mode),
        pack_right_panel=lambda widget: _phase6_pack_right_panel_above_canvas(self, widget),
        clear_drawing_edge_controls=lambda: _phase6_clear_drawing_edge_controls(self),
        tk_both=original.tk.BOTH,
    )
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
    return _navigation_view_refresh_add_part_menu(
        self,
        tk_end=original.tk.END,
        known_parts=KNOWN_PARTS,
        label_for_key=lambda key: _phase6_part_label(key),
        add_part=lambda key: self.add_part(key),
    )

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
        _navigation_view_project_active_part_selector(
            self,
            key=key,
            label=_phase6_part_label("box_body") if _phase6_is_box_body_physical_piece_key(key) else _phase6_part_label(key),
            removable=key != "box_body" and not _phase6_is_derived_physical_part_key(key),
            refresh_part_button_states=getattr(self, "_refresh_part_button_states", None),
        )

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

    _navigation_view_finalize_single_part_layout(
        self,
        settings_context="box_body" if _phase6_is_box_body_physical_piece_key(key) else key,
        render_settings_context=lambda context: _phase6_render_settings_context(self, context),
        pack_right_panel=lambda widget: _phase6_pack_right_panel_above_canvas(self, widget),
        render_active_drawing_edge_controls=lambda: _phase6_render_active_drawing_edge_controls(self),
        tk_both=original.tk.BOTH,
    )

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
    _phase6_refresh_receiving_set_bay_control(self)
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
        if _phase6_receiving_layout_applicable(self):
            _phase6_commit_receiving_current_bay_controls(self)
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
        if not _phase6_receiving_layout_applicable(self):
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
    if _phase6_receiving_layout_applicable(self):
        _phase6_commit_receiving_current_bay_controls(self)
    else:
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
