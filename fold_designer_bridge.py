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
from phase6_sync_envelope import mapping_delta, stable_fingerprint
from datetime import datetime
from pathlib import Path
import re
import logging
from typing import Mapping, MutableMapping, Sequence
from whd_theme import WHD_THEME, WHD_SEMANTIC_COLORS, apply_ttk_dark_theme, configure_tk_menu

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.display_dimensions import resolve_operator_finished_dimensions
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController
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
from phase6_box_body_structure import (
    BoxBodyStructureType, normalize_box_body_structure_state, set_active_structure,
    activate_structure_with_defaults,
    set_structure_locked, set_two_piece_width, set_three_piece_width,
    reconcile_box_body_structure_for_total_w_change,
    set_join_seam_bend, set_side_back_geometry, set_side_back_piece_profile,
    side_rear_bend_outside_length,
    update_structure_config,
    resolve_two_piece_widths, resolve_three_piece_widths,
)

from phase6_settings_center import (
    GLOBAL_CONTEXT, settings_for_context, UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size, ui_text_size_label, ui_text_size_factor,
)
from phase6_settings_transaction_controller import Phase6SettingsTransactionController
from phase6_settings_service import Phase6SettingsTransactionService
from phase6_project_controller import Phase6ProjectController
from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
from phase6_corner_data_view_adapter import Phase6CornerDataViewAdapter
from gui_modules.application.command_router import (
    execute_fold_designer_update_reasons,
    submit_fold_designer_update_intent,
    flush_fold_designer_update_intents,
    queue_fold_designer_update,
    cancel_fold_designer_update_intents,
    apply_fold_designer_settings_delta,
    install_fold_designer_keyboard_shortcuts,
)
from gui_modules.application.fold_designer_adapter import (
    FinalSceneCompositionPorts,
    Phase6FoldDesignerComposition,
    install_fold_designer_bridge_facade,
)
import phase6_project_file as _phase6_project_file
from phase6_settings_panel import (
    Phase6SettingsPanel, SettingsPanelExtensionResult,
    setting_number_text as _setting_number_text,
    build_choice_menubutton,
)
from ui_text_scale import TextScaleController
from ae_engine.assembly_joint import (
    AssemblyJoint, AssemblyJointRelation, AssemblyJointSource, ResolvedAssemblyGraph,
    sync_snapshot_intent_joints, migrate_legacy_snapshot_joints,
    edge_relation_for_part, set_part_edge_relation,
)
from ae_engine.assembly_intent import get_assembly_intent
from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection,
    FourCornerTypePolicy, EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS, normalize_corner_selection,
    box_body_height_from_corner_policies,
)

from ae_engine.corner_type_ui import (
    CUSTOM_MODEL_NAME, LEGACY_CUSTOM_MODEL_NAMES, known_model_corner_state,
    normalize_custom_model_name, policy_from_corner_state,
)

from phase6_endcap_semantics import (
    ASSEMBLY_TYPE_LABELS, ASSEMBLY_LABEL_TO_TYPE, ENDCAP_FW_PARTS,
    normalize_endcap_fw_state, resolve_endcap_fw, set_endcap_fw_follow, set_endcap_fw_override,
    commit_box_fw, commit_endcap_fw,
    normalize_endcap_bottom_wrap_state, resolve_endcap_bottom_wrap, commit_endcap_bottom_wrap,
    resolve_box_assembly_type, apply_box_assembly_type_to_raw_state, assembly_intent_value,
    legacy_corner_projection_for_intent,
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
    DiagnosticSnapshotContext, build_active_diagnostic_snapshot,
    collect_final_geometry_diagnostics,
    json_safe as _phase6_json_safe,
    serialize_scene as _phase6_serialize_scene,
    material_diagnostic as _phase6_material_diagnostic,
    serialize_fold_guides as _phase6_serialize_fold_guides,
    write_diagnostic_json as _phase6_write_diagnostic_json,
)

from phase6_final_scene_contracts import (
    AssemblyScenePart,
    AssemblySceneRenderData,
    FinalSceneDependencies,
    FinalSceneViewRequest,
)
from phase6_final_scene_projection import (
    make_assembly_scene_render_data as _project_assembly_scene_render_data,
    _phase6_profile_base_index,
    _phase6_profile_geometry,
    _phase6_fold_mask_for_cross_coordinate,
    _phase6_profile_map_with_guides,
    _phase6_profile_map,
    _phase6_profile_flat_map,
    _phase6_folded_mesh_from_polygon,
    _phase6_fitted_limits_from_vertices,
    _phase6_scene_fold_boundaries,
    _phase6_profile_to_scene_boundaries,
    _phase6_fold_ownership_exemptions,
    _phase6_folded_outside_envelope,
    _phase6_profile_operator_fold_values,
    format_operator_info_text,
)
from phase6_final_scene_renderer import (
    Phase6FinalSceneRenderer,
    Phase6FinalSceneView,
    _PHASE6_DEFAULT_VIEW,
    _PHASE6_ZOOM_MIN,
    _PHASE6_ZOOM_MAX,
    _PHASE6_ZOOM_STEP,
)
from phase6_final_scene_view import (
    Phase6FinalSceneViewAdapter,
    _phase6_remove_original_bend_surfaces,
    _phase6_add_mesh_boundary_lines,
    _phase6_draw_scene_bends,
    _phase6_draw_scene_markings,
    _phase6_configure_3d_only_figure,
    _phase6_scale_current_3d_limits,
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
    _phase6_apply_resolved_cut_to_owner,
    _phase6_side_wrap_target_corners,
    _phase6_box_body_piece_solver_key,
    _phase6_expand_box_body_fw_world_mid,
    _phase6_shift_multistage_terminal_fold_world_mid,
    _phase6_joint_relief_state_item_matches,
    _phase6_cut_geometry_from_state_item,
    _phase6_signature_canonical_value,
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


def _phase6_resolve_manufacturing_geometry(self):
    """Compatibility-only manufacturing entry."""
    return resolve_for_app(self)


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


@dataclass(frozen=True)
class DoorPartProjection:
    part_key: str
    column_index: int
    row_index: int
    start_width: float
    start_height: float
    frame_edges: DoorFrameEdges
    formed_width: float
    formed_height: float


def _phase6_door_part_projections(snapshot: Mapping[str, object]) -> tuple[DoorPartProjection, ...]:
    """Project authoritative multi-door cells without duplicating layout/size formulas."""
    if not bool(snapshot.get("multi_door_enabled", False)):
        return ()
    columns = tuple(snapshot.get("door_layout_columns") or ())
    if not columns:
        return ()
    normalized = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in columns
    )
    t = _num(snapshot.get("t", 2.0), 2.0)
    fw = _num(snapshot.get("fw", 25.0), 25.0)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot, frame_width=fw, thickness=t,
    )
    gap_w = _num(snapshot.get("door_gap_w", 3.5), 3.5)
    gap_h = _num(snapshot.get("door_gap_h", 3.5), 3.5)
    rows = []
    for cell in derive_door_layout_cells(normalized):
        formed_w, formed_h = calculate_door_finished_size(
            w=cell.start_width,
            h=cell.start_height,
            t=t,
            fw=door_material_fw,
            gap_w=gap_w,
            gap_h=gap_h,
            frame_edges=cell.edges,
        )
        rows.append(DoorPartProjection(
            part_key=door_layout_part_key(cell),
            column_index=cell.column_index,
            row_index=cell.row_index,
            start_width=float(cell.start_width),
            start_height=float(cell.start_height),
            frame_edges=cell.edges,
            formed_width=float(formed_w),
            formed_height=float(formed_h),
        ))
    return tuple(rows)


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


def _phase6_is_box_body_physical_piece_key(value) -> bool:
    """Compatibility adapter to the single DM7 navigation identity owner."""
    return _dm7_is_box_body_physical_piece_key(value)


def _phase6_is_side_back_editable_piece_key(value) -> bool:
    """Only side/back-split physical children own editable piece Fold profiles."""
    return str(value or "") in {
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
    }


def _phase6_operator_part_selector_keys(values) -> tuple[str, ...]:
    """Compatibility adapter to the common DM7 hierarchy projection."""
    return _dm7_operator_part_selector_keys(values)


def _phase6_box_body_piece_keys(values) -> tuple[str, ...]:
    """Compatibility adapter to authoritative child identity classification."""
    return _dm7_box_body_piece_keys(values)


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


def _phase6_is_door_part_key(value) -> bool:
    key = str(value or "")
    return key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None


def _phase6_is_base_plate_part_key(value) -> bool:
    key = str(value or "")
    return key == "base_plate" or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None




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


def _phase6_workspace_navigation(self) -> Phase6WorkspaceNavigationController:
    workspace = _designer_workspace(self)
    controller = getattr(self, "_phase6_workspace_navigation_controller", None)
    if controller is None or getattr(controller, "workspace", None) is not workspace:
        # Seed only from a real instance field.  Phase6FoldDesignerApp exposes
        # _phase6_box_body_active_piece_key as a property backed by this
        # controller, so getattr(self, ...) here would recurse through the
        # descriptor.  Lightweight compatibility/test owners may still carry
        # the legacy value directly in __dict__.
        legacy_memory = getattr(self, "__dict__", {}).get(
            "_phase6_box_body_active_piece_key"
        )
        controller = Phase6WorkspaceNavigationController(
            workspace,
            remembered_box_body_child=legacy_memory,
        )
        self._phase6_workspace_navigation_controller = controller
    return controller


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

def _phase6_registry_diagnostics(self):
    controller = getattr(self, "_phase6_registry_diagnostics_controller", None)
    if controller is None:
        controller = Phase6RegistryDiagnosticsController(
            candidate_id=getattr(self, "_phase6_registry_candidate_id", ""),
            candidate_record=getattr(self, "_phase6_registry_candidate_record", {}),
            regression_evidence=getattr(
                self, "_phase6_registry_regression_evidence", {}
            ),
            rule_records=getattr(self, "_phase6_registry_rule_records", {}),
            promotion_candidates=getattr(
                self, "_phase6_last_relief_promotion_candidates", {}
            ),
        )
        self._phase6_registry_diagnostics_controller = controller
    return controller


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


def _phase6_corner_data_view(self):
    adapter = getattr(self, "_phase6_corner_data_view_adapter", None)
    if adapter is None:
        adapter = Phase6CornerDataViewAdapter(
            selected_part_key=getattr(
                self, "_phase6_corner_data_selected_part_key", None
            )
        )
        self._phase6_corner_data_view_adapter = adapter
    return adapter


def _phase6_sync_corner_data_view_compatibility_mirrors(
    self, adapter=None
):
    """Mirror adapter-owned selection for legacy readers/tests only."""
    adapter = adapter or _phase6_corner_data_view(self)
    self._phase6_corner_data_selected_part_key = adapter.selected_part_key
    return adapter


def _phase6_final_scene_renderer(self):
    return _phase6_composition(self).final_scene_renderer(
        number_text=_setting_number_text
    )

def _phase6_final_scene_scene_query(self, key, payload):
    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        raise RuntimeError("3D final-scene provider is not connected")
    return callback(key, payload)


def _phase6_final_scene_corner_text_sink(self, values):
    values = {str(key): str(value) for key, value in dict(values or {}).items()}
    self._phase6_last_assembly_corner_dimension_texts = dict(values)
    vars_by_part = getattr(self, "assembly_part_corner_vars", {}) or {}
    for key, value in values.items():
        var = vars_by_part.get(key)
        if var is not None and callable(getattr(var, "set", None)):
            var.set(value)


def _phase6_final_scene_operator_dimensions(self, part_key=None):
    """Call the operator-dimension provider across legacy/new callable shapes."""
    provider = _phase6_operator_finished_dimensions
    try:
        import inspect
        parameters = tuple(inspect.signature(provider).parameters.values())
        positional = tuple(
            p for p in parameters
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )
        accepts_varargs = any(
            p.kind is inspect.Parameter.VAR_POSITIONAL
            for p in parameters
        )
    except (TypeError, ValueError):
        positional = ()
        accepts_varargs = True

    if part_key is None or (not accepts_varargs and len(positional) <= 1):
        return provider(self)
    return provider(self, part_key)


def _phase6_final_scene_part_text_sink(self, kind, part_key, value):
    mapping_name = (
        "assembly_part_formed_vars"
        if str(kind) == "formed"
        else "assembly_part_blank_vars"
    )
    var = (getattr(self, mapping_name, {}) or {}).get(str(part_key))
    if var is not None and callable(getattr(var, "set", None)):
        var.set(value)


def _phase6_final_scene_visibility(self, parts):
    parts = tuple(parts or ())
    visible_vars = getattr(self, "assembly_part_visible_vars", {}) or {}
    visible_parts = [
        part
        for part in parts
        if bool(
            getattr(
                visible_vars.get(part.part_key),
                "get",
                lambda: True,
            )()
        )
    ]
    if not visible_parts and parts:
        fallback = next(
            (part for part in parts if part.part_key == "box_body"),
            parts[0],
        )
        visible_parts = [fallback]
        var = visible_vars.get(fallback.part_key)
        if var is not None and callable(getattr(var, "set", None)):
            var.set(True)

    visible_keys = {part.part_key for part in visible_parts}
    box_part = next(
        (part for part in parts if part.part_key == "box_body"),
        None,
    )
    box_piece_keys = tuple(
        f"box_body:{str(getattr(piece, 'role', '') or '').strip()}"
        for piece in tuple(
            getattr(
                getattr(box_part, "render_data", None),
                "pieces",
                (),
            )
            or ()
        )
        if str(getattr(piece, "role", "") or "").strip()
    )
    visible_box_body_piece_keys = None
    if box_piece_keys:
        piece_vars = dict(
            getattr(self, "assembly_box_body_piece_visible_vars", {}) or {}
        )
        if "box_body" not in visible_keys:
            visible_box_body_piece_keys = ()
        else:
            visible_box_body_piece_keys = tuple(
                key
                for key in box_piece_keys
                if bool(
                    getattr(
                        piece_vars.get(key),
                        "get",
                        lambda: True,
                    )()
                )
            )
            if (
                not visible_box_body_piece_keys
                and visible_keys == {"box_body"}
            ):
                first = box_piece_keys[0]
                var = piece_vars.get(first)
                if var is not None and callable(getattr(var, "set", None)):
                    var.set(True)
                visible_box_body_piece_keys = (first,)

    return (
        tuple(part.part_key for part in visible_parts),
        visible_box_body_piece_keys,
    )


def _phase6_final_scene_render_committed(self):
    if not getattr(self, "preview_3d_enabled", True):
        return None
    canvas = self.renderer.canvas
    draw = getattr(canvas, "draw", None)
    draw_idle = getattr(canvas, "draw_idle", None)
    if (
        callable(draw)
        and callable(draw_idle)
        and not getattr(self, "_phase6_force_sync_preview", False)
    ):
        canvas.draw = draw_idle
        try:
            return self.renderer.render()
        finally:
            canvas.draw = draw
    return self.renderer.render()


def _phase6_final_scene_set_preview_enabled(self, enabled):
    enabled = bool(enabled)
    self.preview_3d_enabled = enabled
    var = getattr(self, "preview_3d_var", None)
    if var is not None and bool(var.get()) != enabled:
        var.set(enabled)
    widget = self.renderer.canvas.get_tk_widget()
    if enabled:
        if not widget.winfo_manager():
            widget.pack(fill="both", expand=True)
        self.submit_update_intent("display", commit=True)
    elif widget.winfo_manager() == "pack":
        widget.pack_forget()
    return enabled


def _phase6_final_scene_refresh_preview(self):
    if not getattr(self, "preview_3d_enabled", True):
        return _phase6_final_scene_set_preview_enabled(self, True)
    self._phase6_force_sync_preview = True
    try:
        return self.submit_update_intent("display", commit=True)
    finally:
        self._phase6_force_sync_preview = False


def _phase6_final_scene_adapter(self):
    return _phase6_composition(self).final_scene_adapter(
        FinalSceneCompositionPorts(
                number_text=_setting_number_text,
                is_physical_piece_key=_phase6_is_box_body_physical_piece_key,
                physical_piece_render_data=lambda key: _phase6_box_body_piece_render_data(
                    self, key
                ),
                user_joint_parts=lambda: {
                    str(raw.get(field) or "")
                    for raw in tuple(
                        migrate_legacy_snapshot_joints(
                            dict(getattr(self, "_phase6_input_snapshot", {}) or {})
                        ).get("assembly_joints", ()) or ()
                    )
                    if str(raw.get("source") or "")
                    == AssemblyJointSource.USER_ADDED.value
                    for field in ("subject_part", "target_part")
                },
                resolve_geometry=lambda: _phase6_resolve_manufacturing_geometry(
                    self
                ),
                scene_payload_for_part=lambda key: _phase6_scene_query_payload_for_part(
                    self, key
                ),
                publish_live_state=lambda **kwargs: _phase6_publish_live_state(
                    self, **kwargs
                ),
                corner_dimension_text=_phase6_render_data_corner_dimension_text,
                formed_size_text=lambda render_data, **kwargs: _phase6_format_formed_size_text(
                    render_data, **kwargs
                ),
                blank_text=lambda render_data, *, part_key="": _phase6_format_unfolded_blank_text(
                    render_data, part_key=part_key
                ),
                refresh_box_body_piece_info=lambda render_data: _phase6_refresh_box_body_piece_info_rows(
                    self, render_data
                ),
                operator_dimensions=lambda part_key=None: _phase6_final_scene_operator_dimensions(
                    self, part_key
                ),
                cabinet_family=lambda: _phase6_current_cabinet_family(self),
                assembly_blank_text=lambda render_data: _phase6_assembly_unfolded_blank_text(
                    render_data,
                    snapshot=getattr(self, "_phase6_input_snapshot", {}),
                ),
                active_mesh_profiles=lambda material: _phase6_active_mesh_profiles(
                    self, material
                ),
                assembly_render_data_cls=AssemblySceneRenderData,
                assembly_part_cls=AssemblyScenePart,
                final_render_provider=lambda: _phase6_query_final_render_data(
                    self
                ),
                assembly_render_provider=lambda: _phase6_query_assembly_render_data(
                    self
                ),
                request_provider=lambda: _phase6_final_scene_view_request(self),
                after_render=lambda: (
                    _phase6_update_unfolded_size_label(self),
                    _phase6_update_assembly_diagnostic_status(self),
                ),
                active_part=lambda: str(
                    getattr(
                        getattr(self, "designer_workspace", None),
                        "active_part",
                        "",
                    )
                    or ""
                ),
                scene_query=lambda key, payload: _phase6_final_scene_scene_query(
                    self, key, payload
                ),
                input_snapshot=lambda: dict(
                    getattr(self, "_phase6_input_snapshot", {}) or {}
                ),
                settings_values=lambda: dict(
                    getattr(self, "_settings_values", {}) or {}
                ),
                alpha_bend=lambda: float(
                    getattr(getattr(self, "state", None), "alpha_bend", 0.85)
                ),
                display_mode=lambda: str(
                    getattr(self, "_phase6_3d_display_mode", "single")
                    or "single"
                ),
                assembly_corner_text_sink=lambda values: _phase6_final_scene_corner_text_sink(
                    self, values
                ),
                assembly_part_text_sink=lambda kind, key, value: _phase6_final_scene_part_text_sink(
                    self, kind, key, value
                ),
                assembly_visibility=lambda parts: _phase6_final_scene_visibility(
                    self, parts
                ),
                interference_probe_parts=lambda: tuple(
                    getattr(self, "_phase6_last_interference_probe_parts", ())
                    or ()
                ),
                show_interference=lambda: bool(
                    getattr(
                        getattr(self, "assembly_show_interference_var", None),
                        "get",
                        lambda: True,
                    )()
                ),
                render_committed=lambda: _phase6_final_scene_render_committed(
                    self
                ),
                set_preview_enabled=lambda enabled: _phase6_final_scene_set_preview_enabled(
                    self, enabled
                ),
                refresh_preview=lambda: _phase6_final_scene_refresh_preview(
                    self
                ),

        )
    )

def _phase6_sync_authoritative_derived_parts(self):
    """Sync topology-derived physical parts into the persistent workspace.

    Divider geometry is fully determined by authoritative multi-door topology.
    Receiving frame spans are derived by its family policy from Door finished
    geometry plus the confirmed 50 mm left/right/top insets; other families may
    still supply explicit spans to the generic frame capability.
    """
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    workspace = _designer_workspace(self)
    navigation = _phase6_workspace_navigation(self)
    if not navigation.supports_derived_sync:
        # Baseline-change and migration adapters may supply a lightweight
        # workspace facade that predates topology-derived physical parts.
        # Derived synchronization is additive capability; it must not make
        # those transactions fail before a full DesignerWorkspace is attached.
        return (), ()

    # Multi-Door cells are topology-owned physical parts.  The legacy logical
    # ``door`` exists only in single-door mode; otherwise every downstream
    # consumer sees exactly the formal cell identities.
    door_rows = _phase6_door_part_projections(snapshot)
    # A formal multi-door part can be born after the initial workspace snapshot
    # has been constructed. Preserve any canonical per-door features already
    # present in the source snapshot when that identity is first materialized.
    # Existing workspace feature stashes always win so live edits are never
    # overwritten by an older snapshot during later topology refreshes.
    source_part_features = dict(snapshot.get("part_features") or {})
    known_feature_keys = set(workspace.part_features_snapshot())
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

    legacy_active = workspace.active_part == "door"
    legacy_selected = workspace.selected_part == "door"
    if door_rows and "door" in workspace.available_parts:
        navigation.remove_part("door")
    navigation.sync_derived_parts(namespace="door_c", part_profiles=door_profiles)
    for row in door_rows:
        if row.part_key not in known_feature_keys and row.part_key in source_part_features:
            navigation.stash_features(row.part_key, source_part_features[row.part_key])
    if door_rows:
        if legacy_active:
            navigation.set_active_part(door_rows[0].part_key)
        if legacy_selected:
            navigation.set_selected_part(door_rows[0].part_key)
    else:
        source_parts = tuple(snapshot.get("existing_parts") or ())
        if "door" in source_parts and "door" not in workspace.available_parts:
            navigation.add_part(
                "door",
                default_profiles=build_standard_part_profiles(snapshot, "door"),
            )

    # Receiving multi-door Base Plates are physical parts owned 1:1 by the
    # authoritative Door cells.  Their finished-face dimensions are the owning
    # cell nominal W/H after the existing family shrink policy.
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
                "width": max(1.0, float(cell.start_width) - shrink_left - shrink_right),
                "height": max(1.0, float(cell.start_height) - shrink_top - shrink_bottom),
            }
            local["part_dimensions"] = local_dims
            base_plate_profiles[base_key] = build_standard_part_profiles(local, base_key)

    legacy_base_active = workspace.active_part == "base_plate"
    legacy_base_selected = workspace.selected_part == "base_plate"
    if door_rows and "base_plate" in workspace.available_parts:
        navigation.remove_part("base_plate")
    navigation.sync_derived_parts(
        namespace="base_plate_c",
        part_profiles=base_plate_profiles,
    )
    if door_rows:
        first_base = str(door_rows[0].part_key).replace("door_", "base_plate_", 1)
        if legacy_base_active:
            navigation.set_active_part(first_base)
        if legacy_base_selected:
            navigation.set_selected_part(first_base)
    else:
        source_parts = tuple(snapshot.get("existing_parts") or ())
        if "base_plate" in source_parts and "base_plate" not in workspace.available_parts:
            navigation.add_part(
                "base_plate",
                default_profiles=build_standard_part_profiles(snapshot, "base_plate"),
            )

    # Manufacturing-owned multipart BoxBody identities must be real 3D workspace
    # contexts, not only nested labels inside the aggregate `box_body` page.
    # Query the canonical aggregate result and project exactly its physical pieces.
    try:
        box_render_data = _phase6_box_body_structure_render_data(self)
    except Exception:
        box_render_data = None
    if box_render_data is not None:
        box_piece_profiles = _phase6_box_body_piece_part_profiles(box_render_data, snapshot)
        desired_piece_keys = set(box_piece_profiles)
        current_piece_keys = {
            key for key in workspace.available_parts
            if _phase6_is_box_body_physical_piece_key(key)
        }
        for key in tuple(current_piece_keys - desired_piece_keys):
            navigation.remove_part(key)
        for key, profiles in box_piece_profiles.items():
            if key in workspace.available_parts:
                navigation.stash_profiles(key, profiles)
            else:
                navigation.add_part(key, default_profiles=profiles)

    divider_profiles = {}
    columns = list(snapshot.get("door_layout_columns") or ())
    if bool(snapshot.get("multi_door_enabled", False)) and columns:
        from ae_engine.door_dividers import derive_box_body_dividers, divider_part_profiles

        normalized_columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in columns
        )
        dividers = derive_box_body_dividers(
            normalized_columns,
            depth=float(snapshot.get("d", 0.0)),
            thickness=float(snapshot.get("t", 0.0)),
            layout_scope=str(snapshot.get("door_layout_scope") or "main").strip() or "main",
            handle_edges=dict(snapshot.get("door_handle_edges") or {}),
            model_name=str(snapshot.get("model") or "").strip() or None,
            frame_width=float(snapshot.get("fw", 0.0)),
        )
        divider_profiles = divider_part_profiles(dividers)
    navigation.sync_derived_parts(
        namespace="box_body:divider:",
        part_profiles=divider_profiles,
    )

    from ae_engine.inner_door_frames import (
        InnerDoorFrameSet,
        derive_all_inner_door_frames,
        inner_door_frame_part_profiles,
    )

    frame_sets = []
    thickness = float(snapshot.get("t", 0.0))
    if cabinet_family_policy.has_inner_door_frame_derivation(snapshot):
        frame_sets.extend(cabinet_family_policy.derive_inner_door_frame_sets(snapshot))
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
            included = tuple(str(side).strip().lower() for side in (item.get("included_frame_sides") or ("top", "bottom", "left", "right")))
            frame_sets.append(InnerDoorFrameSet(
                inner_door_id=stable_id,
                spans=dict(spans),
                thickness=thickness,
                included_sides=included,
            ))
    frames = derive_all_inner_door_frames(tuple(frame_sets))
    from ae_engine.inner_door_panels import inner_door_panel_part_profiles
    panels = cabinet_family_policy.derive_inner_door_panels(snapshot)
    inner_profiles = inner_door_frame_part_profiles(frames)
    inner_profiles.update(inner_door_panel_part_profiles(panels))
    navigation.sync_derived_parts(
        namespace="inner_door:",
        part_profiles=inner_profiles,
    )
    return (
        tuple(divider_profiles),
        tuple([*(frame.stable_id for frame in frames), *(panel.stable_id for panel in panels)]),
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


def _phase6_resolve_profile_key(active_dict: Mapping[str, object], requested: object) -> str:
    """Resolve stale notebook/renderer labels to a real editable profile key."""
    key = str(requested)
    if key in active_dict:
        return key
    if "X" in active_dict:
        return "X"
    try:
        return next(iter(active_dict))
    except StopIteration:
        raise KeyError(key)

# ---------------------------------------------------------------------------
# Thin Tk bridge: input grid stays the user's original implementation.
# Only metadata preservation / D-W-D row locking are added here.
# ---------------------------------------------------------------------------
import fold_designer_original as original


def _phase6_box_symmetry_allowed(owner) -> bool:
    """Resolve the current family symmetry capability from live/snapshot state."""
    snapshot = dict(getattr(owner, "_phase6_input_snapshot", {}) or {})
    model = str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()
    model_var = getattr(owner, "baseline_model_var", None)
    if model_var is not None:
        try:
            live = str(model_var.get() or "").strip()
        except Exception:
            live = ""
        if live:
            model = live
    return cabinet_family_policy.box_body_symmetry_allowed(model)


def _phase6_legacy_symmetry_widgets(owner, *, exclude=None):
    """Capture original Designer symmetry widgets so Receiving can hide them too."""
    cached = getattr(owner, "_phase6_legacy_symmetry_widgets", None)
    if cached is not None:
        return cached
    found = []

    def walk(parent):
        try:
            children = tuple(parent.winfo_children())
        except Exception:
            return
        for child in children:
            if child is exclude:
                continue
            try:
                text = str(child.cget("text") or "")
            except Exception:
                text = ""
            if text == "對稱折彎":
                try:
                    info = dict(child.pack_info()) if child.winfo_manager() == "pack" else None
                    siblings = list(child.master.pack_slaves()) if info is not None else []
                    idx = siblings.index(child) if child in siblings else -1
                    next_widget = siblings[idx + 1] if idx >= 0 and idx + 1 < len(siblings) else None
                except Exception:
                    info = None
                    next_widget = None
                found.append((child, info, next_widget))
            walk(child)

    left = getattr(owner, "left", None)
    if left is not None:
        walk(left)
    owner._phase6_legacy_symmetry_widgets = found
    return found


def _phase6_set_legacy_symmetry_visibility(owner, allowed: bool, *, exclude=None):
    for widget, info, next_widget in _phase6_legacy_symmetry_widgets(owner, exclude=exclude):
        try:
            managed = bool(widget.winfo_manager())
        except Exception:
            continue
        if allowed:
            if not managed and info is not None:
                opts = {k: v for k, v in info.items() if k != "in"}
                try:
                    if next_widget is not None and next_widget.winfo_manager():
                        widget.pack(in_=widget.master, before=next_widget, **opts)
                    else:
                        widget.pack(in_=widget.master, **opts)
                except Exception:
                    pass
        elif managed:
            try:
                widget.pack_forget()
            except Exception:
                pass


def _phase6_apply_box_symmetry_policy(owner, *, bending_ui=None) -> bool:
    """Normalize state/UI so a disallowed family can never have effective symmetry."""
    allowed = _phase6_box_symmetry_allowed(owner)
    if not allowed:
        try:
            owner.state.symmetric = False
        except Exception:
            pass
        var = getattr(owner, "v_sy", None)
        if var is not None:
            try:
                if bool(var.get()):
                    var.set(False)
            except Exception:
                pass
    ui = bending_ui if bending_ui is not None else getattr(owner, "bend_ui", None)
    if ui is not None:
        phase_var = getattr(ui, "phase6_symmetry_var", None)
        if not allowed and phase_var is not None:
            try:
                if bool(phase_var.get()):
                    phase_var.set(False)
            except Exception:
                pass
        _phase6_set_legacy_symmetry_visibility(
            owner, allowed, exclude=getattr(ui, "phase6_symmetry_check", None)
        )
    return allowed


class Phase6BendingUI(original.BendingUI):
    """Original BendingUI with Phase6 metadata and boundary-only conversion."""

    def __init__(self, parent, state, update_cb):
        super().__init__(parent, state, update_cb)
        owner = getattr(update_cb, "__self__", None)
        self.phase6_symmetry_bar = original.ttk.Frame(parent)
        self.phase6_symmetry_var = getattr(owner, "v_sy", None)
        if self.phase6_symmetry_var is None:
            self.phase6_symmetry_var = original.tk.BooleanVar(value=bool(getattr(state, "symmetric", True)))
        self.phase6_symmetry_check = original.ttk.Checkbutton(
            self.phase6_symmetry_bar,
            text="對稱折彎",
            variable=self.phase6_symmetry_var,
            command=self._phase6_on_symmetry_toggle,
        )
        self.phase6_symmetry_check.pack(side=original.tk.LEFT, padx=(0, 8))
        original.ttk.Label(
            self.phase6_symmetry_bar,
            text="開啟時，箱身兩側對應折彎同步修改／刪除",
        ).pack(side=original.tk.LEFT)
        self._phase6_refresh_symmetry_bar()

    def _phase6_on_symmetry_toggle(self):
        owner = getattr(self.update_cb, "__self__", None)
        if owner is not None and hasattr(owner, "v_sy"):
            _phase6_on_box_symmetry_changed(owner)
        else:
            self.state.symmetric = bool(self.phase6_symmetry_var.get())
            self._mark_workspace_dirty()
            self.update_cb()

    def _phase6_refresh_symmetry_bar(self):
        bar = getattr(self, "phase6_symmetry_bar", None)
        if bar is None:
            return
        owner = getattr(self.update_cb, "__self__", None)
        allowed = _phase6_apply_box_symmetry_policy(owner, bending_ui=self) if owner is not None else True
        show = (
            allowed
            and getattr(self.state, "phase6_fold_ui_vault_key", None) == "箱身"
        )
        if show:
            if not bar.winfo_manager():
                bar.pack(fill=original.tk.X, pady=(0, 4), before=self.container)
            try:
                self.phase6_symmetry_var.set(bool(getattr(self.state, "symmetric", True)))
            except Exception:
                pass
        elif bar.winfo_manager():
            bar.pack_forget()

    def rebuild_tabs(self):
        custom_tabs = getattr(self.state, "phase6_fold_ui_tabs", None)
        if not custom_tabs:
            return super().rebuild_tabs()
        for tab in self.nb.tabs():
            self.nb.forget(tab)
        self.tabs.clear()
        labels = {"X": " X 軸折彎 ", "Y": " Y 軸折彎 "}
        for key in custom_tabs:
            self.nb.add(original.ttk.Frame(self.nb), text=labels.get(key, f" {key} "))
            self.tabs.append(key)
        if self.state.active_bend not in self.tabs:
            self.state.active_bend = self.tabs[0]
        self.nb.select(self.tabs.index(self.state.active_bend))
        self.render()
        self._phase6_refresh_symmetry_bar()

    def _mark_workspace_dirty(self):
        owner = getattr(self.update_cb, "__self__", None)
        if owner is not None and hasattr(owner, "designer_workspace"):
            owner.designer_workspace.mark_dirty()

    def apply_mirror(self, idx, key):
        if getattr(self, "_phase6_refreshing_controls", False):
            return
        self._mark_workspace_dirty()
        owner = getattr(self.update_cb, "__self__", None)
        symmetry_allowed = _phase6_box_symmetry_allowed(owner) if owner is not None else True
        if symmetry_allowed and getattr(self.state, "symmetric", False):
            active = self.get_active_dict()
            profile_key = self._active_profile_key(active)
            segs = active.get(profile_key, ())
            is_box = getattr(self.state, "phase6_fold_ui_vault_key", None) == "箱身"
            pair = {
                "zl1": "zr1", "zr1": "zl1",
                "zl2": "zr2", "zr2": "zl2",
                "fw_left": "fw_right", "fw_right": "fw_left",
                "d_left": "d_right", "d_right": "d_left",
                "w": "w",
            }
            try:
                source_key = str(segs[idx].get("phase6_key") or "")
                target_idx = None
                if is_box and source_key in pair:
                    if key == "len":
                        target_key = pair[source_key]
                        target_idx = next(
                            (i for i, seg in enumerate(segs) if str(seg.get("phase6_key") or "") == target_key),
                            None,
                        )
                    elif key == "angle" and idx + 1 < len(segs):
                        next_key = str(segs[idx + 1].get("phase6_key") or "")
                        if next_key in pair:
                            target_left = pair[next_key]
                            target_right = pair[source_key]
                            target_idx = next(
                                (
                                    i for i in range(len(segs) - 1)
                                    if str(segs[i].get("phase6_key") or "") == target_left
                                    and str(segs[i + 1].get("phase6_key") or "") == target_right
                                ),
                                None,
                            )
                if target_idx is not None and target_idx != idx and key in self.controls[target_idx]:
                    value = original.get_int(self.controls[idx][key].get())
                    self.controls[target_idx][key].set(str(value))
                    self.save(); self.update_cb()
                    return None

                if is_box:
                    # Never fall back from a known structural Phase6 row to raw
                    # positional mirroring: after asymmetric add/remove history
                    # that is exactly how FW/D/Z fields became cross-wired.
                    if source_key in pair:
                        self.save(); self.update_cb()
                        return None
                    # Unkeyed operator-added folds may still mirror by position,
                    # but only when the opposite candidate is also unkeyed.
                    legacy_idx = (
                        len(self.controls) - 1 - idx
                        if key == "len" else len(self.controls) - 2 - idx
                    )
                    if 0 <= legacy_idx < len(segs):
                        candidate_key = str(segs[legacy_idx].get("phase6_key") or "")
                        if candidate_key:
                            self.save(); self.update_cb()
                            return None
            except (TypeError, ValueError, IndexError, KeyError):
                pass
            return super().apply_mirror(idx, key)
        # Original BendingUI returns immediately when symmetry is off, which
        # leaves typed edits only in Tk variables. Phase6 must persist every
        # asymmetric edit into the authoritative Fold Chain before recomputing.
        self.save()
        self.update_cb()
        return None

    def refresh_active_profile(self):
        """Refresh existing editor vars when the X/Y widget topology is unchanged."""
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        segs = active_dict[active_key]
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        if len(self.controls) != len(segs):
            self.render(); return False
        for ctrl, seg in zip(self.controls, segs):
            if (("angle" in ctrl) != ("angle" in seg)) or "len" not in ctrl:
                self.render(); return False
        self._phase6_refreshing_controls = True
        try:
            for index, (ctrl, seg) in enumerate(zip(self.controls, segs)):
                if "angle" in ctrl:
                    text = str(original.get_int(engine_angle_to_ui(seg.get("angle", 0))))
                    if ctrl["angle"].get() != text:
                        ctrl["angle"].set(text)
                operator_length = engine_segment_length_to_ui(seg)
                if float(seg.get("phase6_ui_sign", 1.0) or 1.0) < 0.0:
                    operator_length = -operator_length
                length_text = str(original.get_int(operator_length))
                if ctrl["len"].get() != length_text:
                    ctrl["len"].set(length_text)
                labels = self.container.grid_slaves(row=index + 1, column=5)
                if labels:
                    core = seg.get("core")
                    material_text = f"料 {_ui_len(seg.get('len'))}"
                    labels[0].configure(text=f"{material_text} / {core}" if core else material_text)
        finally:
            self._phase6_refreshing_controls = False
        return True

    def get_active_dict(self):
        custom = getattr(self.state, "phase6_fold_ui_profiles", None)
        if custom is not None:
            return custom
        return super().get_active_dict()

    def on_tab(self, event):
        # Programmatic tab selection during part switching already renders the
        # selected profile in rebuild_tabs().  Tk still emits TabChanged later;
        # do not redraw/schedule another full 3D update when the key did not
        # actually change.  Real operator tab clicks still follow the original
        # path below.
        try:
            idx = self.nb.index("current")
        except Exception:
            return
        if not (0 <= idx < len(self.tabs)):
            return
        key = self.tabs[idx]
        if key == self.state.active_bend:
            return
        self.state.active_bend = key
        self.render()
        self._phase6_refresh_symmetry_bar()
        self.update_cb()

    def _active_profile_key(self, active_dict=None):
        active_dict = self.get_active_dict() if active_dict is None else active_dict
        key = _phase6_resolve_profile_key(active_dict, self.state.active_bend)
        if self.state.active_bend != key:
            self.state.active_bend = key
        return key

    def render(self):
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        segs = active_dict[active_key]
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        saved = []
        for seg in segs:
            original_values = {}
            if "angle" in seg:
                original_values["angle"] = seg["angle"]
                seg["angle"] = engine_angle_to_ui(seg["angle"])
            if _num(seg.get("ui_len_add")):
                original_values["len"] = seg["len"]
                operator_length = engine_segment_length_to_ui(seg)
                if float(seg.get("phase6_ui_sign", 1.0) or 1.0) < 0.0:
                    operator_length = -operator_length
                seg["len"] = operator_length
            if original_values:
                saved.append((seg, original_values))
        try:
            super().render()
        finally:
            for seg, values in saved:
                seg.update(values)

        for index, seg in enumerate(segs):
            row = index + 1
            # The editable value is always operator outside dimension; show the
            # authoritative material segment beside it for cutting/corner work.
            length_labels = self.container.grid_slaves(row=row, column=3)
            if length_labels:
                try:
                    length_labels[0].configure(text="包外:")
                except Exception:
                    pass
            core = seg.get("core")
            material_text = f"料 {_ui_len(seg.get('len'))}"
            label = f"{material_text} / {core}" if core else material_text
            original.ttk.Label(self.container, text=label).grid(row=row, column=5, padx=4)
            if core:
                delete_widgets = self.container.grid_slaves(row=row, column=6)
                if delete_widgets:
                    delete_widgets[0].configure(state="disabled")

    def save(self):
        active_dict = self.get_active_dict()
        active_key = self._active_profile_key(active_dict)
        old_segs = list(active_dict[active_key])
        thickness = getattr(self.state, "phase6_thickness", 2.0)

        # Build the edited bend topology first, so changing an angle and a length
        # in the same row uses the NEW adjacent-bend count for outside -> material.
        topology = []
        for ctrl in self.controls:
            seg = {"len": 0}
            if "angle" in ctrl:
                seg["angle"] = ui_angle_to_engine(original.get_int(ctrl["angle"].get()))
            topology.append(seg)
        apply_outside_dimension_compensation(topology, thickness)

        new_segs = []
        for index, ctrl in enumerate(self.controls):
            old = old_segs[index] if index < len(old_segs) else {}
            ui_length = original.get_int(ctrl["len"].get())
            conversion = dict(old)
            conversion["ui_len_add"] = topology[index].get("ui_len_add", 0)
            length = ui_segment_length_to_engine(conversion, abs(ui_length))
            seg = {"len": length}
            if "phase6_ui_sign" in old or ui_length < 0:
                seg["phase6_ui_sign"] = -1.0 if ui_length < 0 else 1.0
            if "angle" in topology[index]:
                seg["angle"] = topology[index]["angle"]
            for key in ("core", "phase6_key"):
                if key in old:
                    seg[key] = old[key]
            new_segs.append(seg)
        apply_outside_dimension_compensation(new_segs, thickness)
        active_dict[active_key] = new_segs
        vault_key = getattr(self.state, "phase6_fold_ui_vault_key", None)
        if vault_key and active_key == "X":
            self.state.profiles_vault[vault_key] = new_segs

    def add(self, pos):
        self._mark_workspace_dirty()
        self.save()
        active_dict = self.get_active_dict()
        segs = active_dict[self._active_profile_key(active_dict)]
        if pos == 0:
            segs.insert(0, {"angle": 90, "len": 50, "ui_len_add": getattr(self.state, "phase6_thickness", 2.0)})
        else:
            if segs:
                segs[-1]["angle"] = -90
            segs.append({"len": 50})
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        self.render(); self.update_cb()

    def remove(self, idx):
        self._mark_workspace_dirty()
        self.save()
        active_dict = self.get_active_dict()
        segs = active_dict[self._active_profile_key(active_dict)]
        if not (0 <= idx < len(segs)):
            return
        if not can_remove_segment(segs[idx]):
            return

        remove_indexes = [idx]
        owner = getattr(self.update_cb, "__self__", None)
        symmetry_allowed = _phase6_box_symmetry_allowed(owner) if owner is not None else True
        is_symmetric_box = (
            symmetry_allowed
            and bool(getattr(self.state, "symmetric", False))
            and getattr(self.state, "phase6_fold_ui_vault_key", None) == "箱身"
        )
        if is_symmetric_box:
            mirror_idx = len(segs) - 1 - idx
            if mirror_idx != idx:
                if not (0 <= mirror_idx < len(segs)) or not can_remove_segment(segs[mirror_idx]):
                    return
                remove_indexes.append(mirror_idx)

        for remove_idx in sorted(set(remove_indexes), reverse=True):
            segs.pop(remove_idx)
        if segs and "angle" in segs[-1]:
            del segs[-1]["angle"]
        apply_outside_dimension_compensation(segs, getattr(self.state, "phase6_thickness", 2.0))
        self.render(); self.update_cb()


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

    def __init__(self, root, snapshot: Mapping[str, object]):
        _phase6_replace_mapping(self, "_phase6_input_snapshot", dict(snapshot))
        self._phase6_sync_ready = False
        self._phase6_last_w = None
        self._phase6_last_d = None
        self._phase6_destroying = False
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

def _three_segment_profile(left, center, right, *, left_key=None, center_key=None, right_key=None):
    items = [
        {"len": _ui_len(left), "angle": -90},
        {"len": _ui_len(center), "angle": -90},
        {"len": _ui_len(right)},
    ]
    for item, key in zip(items, (left_key, center_key, right_key)):
        if key:
            item["phase6_key"] = key
    return items


def build_standard_part_profiles(snapshot: Mapping[str, object], part_key: str) -> dict[str, list[dict]]:
    """Build the original designer's X/Y profiles for one non-vault panel."""
    dims = dict((snapshot.get("part_dimensions") or {}).get(part_key, {}) or {})
    w = _num(dims.get("width", snapshot.get("w", 500)), 500)
    h = _num(dims.get("height", snapshot.get("h", 600)), 600)
    if _phase6_is_door_part_key(part_key):
        t = _num(snapshot.get("t", 2), 2)
        outside_add = max(0.0, 2.0 * t)
        profiles = {
            "X": _three_segment_profile(
                snapshot.get("door_fold_l", 20), max(0.0, w - outside_add), snapshot.get("door_fold_r", 20),
                left_key="door_fold_l", center_key="door_face_w", right_key="door_fold_r",
            ),
            "Y": _three_segment_profile(
                snapshot.get("door_fold_b", 20), max(0.0, h - outside_add), snapshot.get("door_fold_t", 20),
                left_key="door_fold_b", center_key="door_face_h", right_key="door_fold_t",
            ),
        }
        profiles["X"][1]["core"] = "門包外 W"
        profiles["Y"][1]["core"] = "門包外 H"
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles
    if _phase6_is_base_plate_part_key(part_key):
        bend = snapshot.get("base_plate_bend", 20)
        profiles = {
            "X": _three_segment_profile(bend, w, bend, left_key="base_bend_l", center_key="base_face_w", right_key="base_bend_r"),
            "Y": _three_segment_profile(bend, h, bend, left_key="base_bend_b", center_key="base_face_h", right_key="base_bend_t"),
        }
        t = _num(snapshot.get("t", 2), 2)
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles
    if part_key == "indicator_box":
        # part_dimensions carries the real unfolded blank size.  The original
        # Renderer must receive the real BEND-line span (blank - both folds),
        # while FIX13 shows the operator the outside finished-face dimension.
        # For this four-side box that outside dimension is BEND span + 1T.
        fold = _num(snapshot.get("indicator_box_fold", 49), 49)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(fold, x_core, fold, left_key="ib_fold_l", center_key="ib_face_w", right_key="ib_fold_r"),
            "Y": _three_segment_profile(fold, y_core, fold, left_key="ib_fold_b", center_key="ib_face_h", right_key="ib_fold_t"),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles
    if part_key == "indicator_door":
        # The small door's part_dimensions is likewise the unfolded blank.
        # Its Door contract defines finished outside size as BEND span + 2T.
        fold = _num(snapshot.get("indicator_door_fold", 19), 19)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(fold, x_core, fold, left_key="id_fold_l", center_key="id_face_w", right_key="id_fold_r"),
            "Y": _three_segment_profile(fold, y_core, fold, left_key="id_fold_b", center_key="id_face_h", right_key="id_fold_t"),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles
    # Generic Unknown add: start from a simple editable X/Y panel without
    # inventing manufacturing policy.
    t = _num(snapshot.get("t", 2), 2)
    profiles = {
        "X": _three_segment_profile(25, w, 25),
        "Y": _three_segment_profile(25, h, 25),
    }
    profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
    profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
    return profiles


def _profile_value(profile, key, default=0):
    for seg in profile or ():
        if seg.get("phase6_key") == key:
            return _ui_len(seg.get("len"))
    return _ui_len(default)


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





def _merge_keyed_profiles(existing_profiles, default_profiles):
    """Refresh Phase6 keyed segments while preserving arbitrary extra folds."""
    result = {}
    for axis in ("X", "Y"):
        existing = clone_profile((existing_profiles or {}).get(axis, ()))
        defaults = clone_profile((default_profiles or {}).get(axis, ()))
        if not existing:
            result[axis] = defaults
            continue
        default_by_key = {
            seg.get("phase6_key"): seg for seg in defaults if seg.get("phase6_key")
        }
        existing_keys = {seg.get("phase6_key") for seg in existing if seg.get("phase6_key")}
        if not set(default_by_key).issubset(existing_keys):
            result[axis] = defaults
            continue
        for seg in existing:
            key = seg.get("phase6_key")
            source = default_by_key.get(key)
            if source is None:
                continue
            for name in ("len", "ui_len_add", "core"):
                if name in source:
                    seg[name] = source[name]
                else:
                    seg.pop(name, None)
        result[axis] = existing
    return result


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
    values = self._settings_values
    snapshot = self._phase6_input_snapshot
    snapshot.update(values)
    w = _num(values.get("w", snapshot.get("w", 500)), 500)
    h = _num(values.get("h", snapshot.get("h", 600)), 600)
    d = _num(values.get("d", snapshot.get("d", 200)), 200)
    t = _num(values.get("t", snapshot.get("t", 2)), 2)
    fw = _num(values.get("fw", snapshot.get("fw", 25)), 25)
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        snapshot, frame_width=fw, thickness=t,
    )
    dims = {key: dict(value) for key, value in (snapshot.get("part_dimensions") or {}).items()}
    dims["box_body"] = {"width": w, "height": h}
    dims["head"] = {"width": w, "height": d}
    dims["tail"] = {"width": w, "height": d}
    for key in tuple(dims):
        if re.fullmatch(r"door_c\d+_r\d+", str(key)) or re.fullmatch(r"base_plate_c\d+_r\d+", str(key)):
            dims.pop(key, None)
    door_rows = _phase6_door_part_projections(snapshot)
    if door_rows:
        dims.pop("door", None)
        for row in door_rows:
            dims[row.part_key] = {"width": row.formed_width, "height": row.formed_height}
    else:
        door_w, door_h = calculate_door_finished_size(
            w=w,
            h=h,
            t=t,
            fw=door_material_fw,
            gap_w=_num(values.get("door_gap_w", 3.5), 3.5),
            gap_h=_num(values.get("door_gap_h", 3.5), 3.5),
            frame_edges=DoorFrameEdges(),
        )
        dims["door"] = {
            "width": max(1.0, float(door_w)),
            "height": max(1.0, float(door_h)),
        }
    shrink_left = _num(values.get("base_plate_shrink_left", 55), 55)
    shrink_right = _num(values.get("base_plate_shrink_right", 55), 55)
    shrink_top = _num(values.get("base_plate_shrink_top", 55), 55)
    shrink_bottom = _num(values.get("base_plate_shrink_bottom", 55), 55)
    base_w = max(1.0, w - shrink_left - shrink_right)
    base_h = max(1.0, h - shrink_top - shrink_bottom)
    # Preserve the legacy canonical template metadata for project compatibility;
    # actual multi-door physical parts are the stable base_plate_cX_rY identities.
    dims["base_plate"] = {"width": base_w, "height": base_h}
    if door_rows:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        for cell in derive_door_layout_cells(columns):
            base_key = door_layout_part_key(cell).replace("door_", "base_plate_", 1)
            dims[base_key] = {
                "width": max(1.0, float(cell.start_width) - shrink_left - shrink_right),
                "height": max(1.0, float(cell.start_height) - shrink_top - shrink_bottom),
            }
    snapshot["part_dimensions"] = dims
    return dims


def _phase6_refresh_profiles_from_settings(self, *, reset_box_profile=False):
    """Push settings values into Fold profiles using the correct authority boundary.

    Ordinary edits preserve operator-owned Fold topology through
    ``merge_box_body_profile``.  A switch to another known cabinet family is a
    preset transaction instead: the target family's canonical BoxBody profile
    replaces the outgoing family's topology/outer-fold dimensions.  Only the
    caller that owns that explicit family switch may request the reset.
    """
    snapshot = self._phase6_input_snapshot
    snapshot.update(self._settings_values)
    _phase6_recalculate_part_dimensions(self)

    current_box = self.state.profiles_vault.get("箱身", [])
    self.state.profiles_vault["箱身"] = (
        build_box_body_profile(snapshot)
        if reset_box_profile
        else merge_box_body_profile(current_box, snapshot)
    )

    _phase6_sync_authoritative_derived_parts(self)
    _phase6_refresh_assembly_parts_panel_if_topology_changed(self)
    for key in self.designer_workspace.available_parts:
        if key == "box_body" or _phase6_is_derived_physical_part_key(key):
            continue
        defaults = (
            build_endcap_xy_profiles(snapshot, part_key=key)
            if key in {"head", "tail"}
            else build_standard_part_profiles(snapshot, key)
        )
        existing = self.designer_workspace.profiles_for(key, {}) or {}
        merged = _merge_keyed_profiles(existing, defaults)
        merged = (
            _phase6_normalize_endcap_profile_order(merged, snapshot, key)
            if key in {"head", "tail"} else merged
        )
        self.designer_workspace.stash_profiles(key, merged)

    active = self.designer_workspace.active_part or "box_body"
    if active == "box_body":
        self.state.phase6_fold_ui_profiles = {"X": self.state.profiles_vault["箱身"]}
    elif active in self.designer_workspace.available_parts:
        profiles = self.designer_workspace.profiles_for(active, {}) or {}
        self.state.profiles["X"] = clone_profile(profiles.get("X", []))
        self.state.profiles["Y"] = clone_profile(profiles.get("Y", []))
    try:
        self.bend_ui.render()
    except Exception:
        pass


def _phase6_apply_setting_updates(self, updates, *, notify=True):
    transactions = _phase6_settings_transactions(self)
    clean = transactions.normalize_updates(
        updates,
        external_apply_guard=bool(getattr(self, "_phase6_external_apply_guard", False)),
    )
    if not clean:
        return {}

    # A legitimate global W edit is a commit seam, not a geometry-resolver
    # repair path. Preserve the operator's last W-split driver and derive the
    # complementary widths here; if the new W cannot produce a legal split,
    # reject/revert W while leaving the strict resolver fail-closed.
    if "w" in clean:
        previous_w = float((getattr(self, "_phase6_box_whd", {}) or {}).get(
            "w", getattr(getattr(self, "state", None), "w", clean["w"])
        ))
        try:
            transactions.commit_reconciled_width_structure(clean["w"])
        except Exception as exc:
            clean.pop("w", None)
            transactions.restore_setting("w", previous_w)
            _phase6_box_structure_error(self, exc)
            self._phase6_settings_guard = True
            try:
                if hasattr(self, "v_w"):
                    self.v_w.set(_setting_number_text(previous_w))
                var = getattr(self, "left_global_vars", {}).get("w")
                if var is not None:
                    var.set(_setting_number_text(previous_w))
            finally:
                self._phase6_settings_guard = False
            if not clean:
                return {}
        else:
            pass

    self._phase6_applying_settings = True
    try:
        try:
            self._save_current_part()
        except Exception:
            pass
    finally:
        self._phase6_applying_settings = False
    clean = transactions.commit_settings(clean)
    if "t" in clean:
        self.state.phase6_thickness = float(clean["t"])
    if "ui_text_size" in clean:
        key = clean["ui_text_size"]
        if hasattr(self, "_ui_text_controller"):
            self._ui_text_controller.apply(key)
        self.state.ui_text_scale = getattr(self, "_ui_text_controller", None).factor if hasattr(self, "_ui_text_controller") else 1.0
        var = getattr(self, "ui_text_size_var", None)
        if var is not None and var.get() != ui_text_size_label(key):
            var.set(ui_text_size_label(key))
    self._phase6_settings_guard = True
    try:
        if "w" in clean: self.v_w.set(_setting_number_text(clean["w"]))
        if "h" in clean: self.v_h.set(_setting_number_text(clean["h"]))
        if "d" in clean: self.v_d.set(_setting_number_text(clean["d"]))
        for key, var in getattr(self, "left_global_vars", {}).items():
            if key not in clean:
                continue
            if key == "ui_text_size":
                var.set(ui_text_size_label(clean[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(clean[key]))
            else:
                var.set(_setting_number_text(clean[key]))
        _phase6_refresh_profiles_from_settings(self)
        for key, var in getattr(self, "setting_vars", {}).items():
            if key in clean:
                if key == "ui_text_size":
                    var.set(ui_text_size_label(clean[key]))
                elif isinstance(var, original.tk.BooleanVar):
                    var.set(bool(clean[key]))
                else:
                    var.set(_setting_number_text(clean[key]))
    finally:
        self._phase6_settings_guard = False
    legacy_job = getattr(self, "_job", None)
    if legacy_job is not None:
        try:
            self.root.after_cancel(legacy_job)
        except Exception:
            pass
        self._job = None
    try:
        self.do_update()
    except Exception:
        pass
    if (
        notify
        and not getattr(self, "_phase6_transactional_mode", False)
        and self._settings_change_callback is not None
    ):
        self._settings_change_callback(dict(self._settings_values))
    return clean


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

def _phase6_on_setting_var_changed(self, key, var, spec):
    if getattr(self, "_phase6_settings_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    raw = var.get()
    if spec.kind == "bool":
        value = bool(raw)
    elif spec.kind == "choice":
        value = normalize_ui_text_size(raw) if spec.key == "ui_text_size" else str(raw)
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError, original.tk.TclError):
            return
    _phase6_stage_setting_update(self, key, value)



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


def _phase6_toggle_corner_parameter_lock(self):
    return _phase6_toggle_parameter_panel(self)


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

def _phase6_corner_targets(pairs, target_key):
    return _CORNER_PAIR_KEYS[target_key] if target_key in _CORNER_PAIR_KEYS else (target_key,)


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
    old_model = str(getattr(self, "_phase6_baseline_last_model", "") or "").strip()
    old_editable = _phase6_is_unknown_baseline(self, old_model)
    if old_editable:
        self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
        self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)

    editable = _phase6_is_unknown_baseline(self, new_model)
    needs_fixed_corner_preset = bool(
        (not editable and new_model and new_model != old_model)
        or (editable and old_model and not old_editable)
    )
    fixed_corner_state = (
        _phase6_known_model_corner_state(self)
        if needs_fixed_corner_preset else {}
    )

    transactions = _phase6_settings_transactions(self)
    previous_non_receiving_structure = getattr(
        self, "_phase6_non_receiving_structure_state", None
    )
    plan = None
    try:
        plan = transactions.commit_family_model_transition(
            new_model,
            old_model,
            new_editable=editable,
            old_editable=old_editable,
            fixed_corner_state=fixed_corner_state,
            available_parts=tuple(
                getattr(self.designer_workspace, "available_parts", ()) or ()
            ),
            previous_non_receiving_structure=previous_non_receiving_structure,
        )
    except Exception:
        # Preserve the baseline fail-closed behavior: rendering/validation will
        # surface the real family/structure error; do not invent a fallback.
        plan = None

    if plan is not None:
        if plan.remember_non_receiving_structure is not None:
            self._phase6_non_receiving_structure_state = deepcopy(
                plan.remember_non_receiving_structure
            )

        if editable and old_model and not old_editable:
            self._corner_transaction_unknown_state = deepcopy(
                self._phase6_corner_state
            )
            self._corner_transaction_unknown_pairs = deepcopy(
                self._phase6_corner_pair_same
            )

        if plan.family_values:
            _phase6_store_editor_values(
                self, plan.family_values, notify=True
            )
            defaults = dict(plan.defaults or {})
            self.state.w = original.get_int(defaults["w"])
            self.state.h = original.get_int(defaults["h"])
            self.state.d = original.get_int(defaults["d"])
            self.v_w.set(str(self.state.w))
            self.v_h.set(str(self.state.h))
            self.v_d.set(str(self.state.d))
            self._phase6_last_w = self.state.w
            self._phase6_last_d = self.state.d
            _phase6_refresh_profiles_from_settings(
                self, reset_box_profile=True
            )

            assembly_var = getattr(self, "assembly_type_var", None)
            if assembly_var is not None:
                assembly_var.set(ASSEMBLY_TYPE_LABELS[plan.assembly_type])

    self._corner_editable = editable
    self._phase6_baseline_last_model = new_model
    _phase6_apply_box_symmetry_policy(self)
    if hasattr(self, "bend_ui"):
        self.bend_ui._phase6_refresh_symmetry_bar()
    _phase6_sync_authoritative_derived_parts(self)
    refresh_parts = getattr(self, "_refresh_part_buttons", None)
    if callable(refresh_parts) and getattr(self, "part_choice_menu", None) is not None:
        refresh_parts()
    else:
        _phase6_refresh_assembly_parts_panel_if_topology_changed(self)
    _phase6_refresh_persistent_structure_controls(self)

    # Cached pages depend on whether the family is editable. Baseline changes
    # are explicit user actions, so rebuilding here preserves the old UI order.
    _phase6_invalidate_corner_pages(self)
    if hasattr(self, "settings_center") and getattr(self, "active_part_key", None) is not None:
        _phase6_render_settings_context(
            self, getattr(self, "settings_context", self.active_part_key)
        )
    if hasattr(self, "settings_status_var"):
        self.settings_status_var.set(
            "自訂：沿用目前資料並即時同步主畫面"
            if editable else "已選基準型號；截角修改即時同步主畫面"
        )
    submit = getattr(self, "submit_update_intent", None)
    if callable(submit):
        submit("baseline", commit=True)
    else:
        _phase6_publish_live_state(self, force=True)

    corner_data_panel = getattr(self, "corner_data_panel", None)
    if (
        str(getattr(self, "_phase6_3d_display_mode", "") or "") == "corner_data"
        and corner_data_panel is not None
        and corner_data_panel.winfo_manager()
    ):
        _phase6_refresh_corner_data_parts_panel(self)
        if getattr(self, "corner_data_canvas", None) is not None:
            _phase6_refresh_corner_data_unfold_view(self)

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
    """Publish one revision only when authoritative live state actually changes."""
    callback = getattr(self, "_live_sync_callback", None)
    if (not callable(callback) or getattr(self, "_phase6_live_sync_guard", False)
            or getattr(self, "_phase6_initializing", False)
            or not getattr(self, "_phase6_sync_ready", False)
            or not hasattr(self, "baseline_model_var")
            or not hasattr(self, "designer_workspace")):
        return False
    state = _phase6_corner_transaction_payload(self)
    fingerprint = stable_fingerprint(state)

    # Initialization can legitimately solve/normalize a verified assembly relief
    # while live publication is suppressed.  In that case the designer's
    # last-live fingerprint already describes the canonical state, but the host
    # snapshot may still carry the older relief contract.  ``force`` never
    # bypasses anti-echo for an equivalent host; it only repairs that proven
    # host/canonical relief delta.
    input_snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    host_relief_present = isinstance(input_snapshot, Mapping) and "assembly_relief" in input_snapshot
    host_relief = deepcopy(input_snapshot.get("assembly_relief") or {}) if host_relief_present else {}
    canonical_relief = deepcopy(state.get("assembly_relief") or {})
    force_host_relief_sync = bool(
        force
        and host_relief_present
        and stable_fingerprint(host_relief) != stable_fingerprint(canonical_relief)
    )

    if (fingerprint == getattr(self, "_phase6_last_live_fingerprint", None)
            and not force_host_relief_sync):
        return False
    previous = getattr(self, "_phase6_last_live_state", None) or {}
    if force_host_relief_sync:
        previous = deepcopy(state)
        previous["assembly_relief"] = host_relief
    delta = mapping_delta(previous, state)
    if not delta and previous:
        return False
    revision = int(getattr(self, "_phase6_sync_revision", 0) or 0) + 1
    transaction_id = (
        str(getattr(self, "_phase6_active_transaction_id", "") or "").strip()
        or f"fold_designer:{revision}"
    )
    payload = deepcopy(state)
    payload.update({
        "origin": "fold_designer",
        "revision": revision,
        "transaction_id": transaction_id,
        "delta": deepcopy(delta),
        "fingerprint": fingerprint,
    })
    self._phase6_live_sync_guard = True
    try:
        callback(deepcopy(payload))
        self._phase6_sync_revision = revision
        self._phase6_last_live_state = deepcopy(state)
        self._phase6_last_live_fingerprint = fingerprint
        self._phase6_last_live_payload = deepcopy(payload)
        self._phase6_input_snapshot["assembly_relief"] = deepcopy(state.get("assembly_relief") or {})
    except Exception as exc:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"即時同步失敗：{exc}")
        return False
    finally:
        self._phase6_live_sync_guard = False
    return True


def _phase6_build_diagnostic_snapshot(self):
    """Capture the exact draft + Final Part Geometry currently used by 3D."""
    model_var = getattr(self, "baseline_model_var", None)
    model = str(
        model_var.get() if model_var is not None
        else getattr(self, "_phase6_baseline_initial_model", "") or ""
    ).strip()
    active_part = self.designer_workspace.active_part
    payload = _phase6_scene_query_payload(self) if active_part else {}
    settings = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    settings.update(dict(getattr(self, "_settings_values", {}) or {}))
    settings.update(dict(getattr(self, "_phase6_box_whd", {}) or {}))
    provider = (lambda: _phase6_query_final_render_data(self)) if active_part else None
    return Phase6ProjectController.build_diagnostic_payload(
        model=model,
        active_part=active_part,
        settings=settings,
        corner_state=getattr(self, "_phase6_corner_state", {}) or {},
        corner_pair_same=getattr(self, "_phase6_corner_pair_same", {}) or {},
        workspace=_phase6_collect_workspace_state(self),
        active_part_payload=payload,
        final_geometry_provider=provider,
        context_factory=DiagnosticSnapshotContext,
        builder=build_active_diagnostic_snapshot,
    )

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

def _phase6_save_diagnostic_file(self):
    """儲存 staged 折彎診斷工作區，但不提交 main GUI transaction。"""
    from tkinter import filedialog, messagebox

    if getattr(self, "_phase6_pending_settings", None):
        try:
            self.flush_pending_settings()
        except Exception:
            pass
    try:
        self._save_current_part(notify=False)
    except Exception:
        pass

    model_var = getattr(self, "baseline_model_var", None)
    model = str(model_var.get() if model_var is not None else "").strip() or "自訂"
    part = PART_LABELS.get(getattr(self, "active_part_key", None), "工作區")
    safe_model = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in model)
    initial = f"Phase6折彎_{safe_model}_{part}.json"
    path = filedialog.asksaveasfilename(
        parent=self.root,
        title="存檔：折彎診斷工作檔",
        defaultextension=".json",
        filetypes=[("Phase6 折彎診斷 JSON", "*.json"), ("所有檔案", "*.*")],
        initialfile=initial,
    )
    if not path:
        return None
    try:
        target = Phase6ProjectController.write_diagnostic(
            path,
            _phase6_build_diagnostic_snapshot(self),
            _phase6_write_diagnostic_json,
        )
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(
                f"已存檔：{Path(target).name}（未提交主畫面）"
            )
        return target
    except Exception as exc:
        messagebox.showerror(
            "存檔失敗", f"無法儲存折彎診斷檔：\n{exc}", parent=self.root
        )
        return None

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


def _phase6_confirm_corner_transaction(self):
    self.flush_pending_settings()
    # Capture the visible fold editor only after a part has actually been selected.
    # Confirming directly from the landing view must not fabricate a Box Body edit.
    if getattr(self, "active_part_key", None) is not None:
        self._save_current_part(notify=False)
    if _phase6_is_unknown_baseline(self, self.baseline_model_var.get()):
        self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
        self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)
    callback = getattr(self, "_transaction_confirm_callback", None)
    if callback is None:
        return False
    try:
        callback(_phase6_corner_transaction_payload(self))
    except Exception as exc:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"確定失敗：{exc}")
        return False
    return True


def _phase6_cancel_corner_transaction(self):
    callback = getattr(self, "_transaction_cancel_callback", None)
    if callback is None:
        return False
    try:
        callback()
    except Exception as exc:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"取消失敗：{exc}")
        return False
    return True


def _phase6_export_workspace_state_if_dirty(self):
    """只在折彎工作區結構真的改變時保存結構。"""
    if not bool(getattr(self, "_phase6_workspace_dirty", False)):
        return None
    pending = getattr(self, "_job", None)
    if pending:
        try:
            self.root.after_cancel(pending)
        except Exception:
            pass
        self._job = None
    self._save_current_part(notify=False)
    owner = self.designer_workspace.snapshot()
    result = Phase6ProjectController.build_workspace_export(
        owner_workspace=owner,
        box_body_profile=clone_profile(
            self.state.profiles_vault.get("箱身", [])
        ),
        structure_state=self.designer_workspace.box_body_structure_state(),
    )
    self.designer_workspace.mark_clean()
    return result

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


def _phase6_set_endcap_fw_follow(self, part_key, follow_box):
    _phase6_settings_transactions(self).commit_endcap_fw_follow(
        str(part_key), bool(follow_box)
    )
    return _phase6_commit_endcap_fw_state(self)


def _phase6_set_endcap_fw_override(self, part_key, value):
    _phase6_settings_transactions(self).commit_endcap_fw_override(
        str(part_key), value
    )
    return _phase6_commit_endcap_fw_state(self)


def _phase6_on_endcap_fw_follow_selected(self, part_key, follow_var, value_var, value_widget):
    follow = bool(follow_var.get())
    _phase6_set_endcap_fw_follow(self, part_key, follow)
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    effective = resolve_endcap_fw(snapshot, part_key, state=self._phase6_endcap_fw_state)
    value_var.set(_setting_number_text(effective))
    try:
        value_widget.configure(state=("disabled" if follow else "normal"))
    except Exception:
        pass


def _phase6_on_endcap_fw_value_selected(self, part_key, value_var):
    try:
        value = float(value_var.get())
    except (TypeError, ValueError):
        return
    _phase6_set_endcap_fw_override(self, part_key, value)


def _phase6_build_endcap_fw_settings(self, parent, part_key, start_row):
    part_key = str(part_key)
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    state = self._phase6_endcap_fw_state.setdefault(
        part_key, {"follow_box": True, "value": _num(snapshot.get("fw", 25), 25)}
    )
    follow = bool(state.get("follow_box", True))
    effective = resolve_endcap_fw(snapshot, part_key, state=self._phase6_endcap_fw_state)

    box = original.ttk.Frame(parent, padding=4)
    box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
    original.ttk.Label(
        box, text="邊框寬度 FW", font=("Microsoft JhengHei", 9, "bold")
    ).pack(anchor=original.tk.W)
    original.ttk.Separator(box, orient=original.tk.HORIZONTAL).pack(
        fill=original.tk.X, pady=(2, 4)
    )
    follow_var = original.tk.BooleanVar(value=follow)
    value_var = original.tk.StringVar(value=_setting_number_text(effective))
    check = original.ttk.Checkbutton(box, text="跟隨箱身 FW", variable=follow_var)
    check.pack(side=original.tk.LEFT, padx=(0, 8))
    entry = original.ttk.Entry(box, textvariable=value_var, width=9, justify=original.tk.CENTER)
    entry.pack(side=original.tk.LEFT, padx=(0, 6))
    entry.configure(state="normal")
    check.configure(state="disabled")
    entry.bind("<Return>", lambda _e: _phase6_on_endcap_fw_value_selected(self, part_key, value_var))
    entry.bind("<FocusOut>", lambda _e: _phase6_on_endcap_fw_value_selected(self, part_key, value_var))
    original.ttk.Label(box, text="直接修改：先改一端會帶另一端；再改另一端後各自獨立").pack(side=original.tk.LEFT)
    return start_row + 1, follow_var, value_var, entry


_BOX_STRUCTURE_LABELS = {
    BoxBodyStructureType.INTEGRAL: "一體成型",
    BoxBodyStructureType.TWO_PIECE_W_SPLIT: "二件式（W 二分）",
    BoxBodyStructureType.THREE_PIECE_W_SPLIT: "三件式（W 三分）",
    BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT: "三件式（側背分離）",
}
_BOX_STRUCTURE_LABEL_TO_TYPE = {label: key for key, label in _BOX_STRUCTURE_LABELS.items()}


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


def _phase6_toggle_box_structure_lock(self):
    state = _phase6_box_structure_state(self)
    committed = _phase6_settings_transactions(self).toggle_box_structure_lock(state)
    _phase6_after_box_structure_commit(self, committed, rebuild=True)


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


def _phase6_structure_entry(box, row, label, value, callback, *, suffix="mm"):
    original.ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
    var = original.tk.StringVar(value=_setting_number_text(value))
    entry = original.ttk.Entry(box, textvariable=var, width=10, justify=original.tk.CENTER)
    entry.grid(row=row, column=1, sticky="w", pady=2)
    original.ttk.Label(box, text=suffix).grid(row=row, column=2, sticky="w", padx=(5, 12), pady=2)
    entry.bind("<Return>", lambda _e: callback(var))
    entry.bind("<FocusOut>", lambda _e: callback(var))
    return var, entry


def _phase6_build_box_structure_settings(self, parent, start_row):
    state = _phase6_box_structure_state(self)
    active = BoxBodyStructureType(state["active_type"])
    frame = original.ttk.LabelFrame(parent, text="結構參數", padding=5)
    frame.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))

    # T14: this is a UI projection of the already-resolved physical Box Body
    # pieces.  The stable IDs and dimensions come from render_data.pieces;
    # edits still write the single canonical box_body_structure_state.
    self.box_body_piece_input_host = original.ttk.Frame(frame)
    self.box_body_piece_input_host.grid(row=0, column=0, columnspan=4, sticky="ew")
    self.box_body_piece_input_sections = {}
    self.box_body_piece_input_vars = {}
    self.box_body_piece_input_entries = {}

    cfg = state["configs"][active.value]
    total_w = _phase6_box_structure_w(self)
    piece_values = {}
    if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
        left, right = resolve_two_piece_widths(state, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
        left, middle, right = resolve_three_piece_widths(state, total_w)
        piece_values = {
            "box_body:left": ("width", "W 包外", left, "mm", "left"),
            "box_body:middle": ("width", "W 包外", middle, "mm", "middle"),
            "box_body:right": ("width", "W 包外", right, "mm", "right"),
        }
    elif active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
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
            original.ttk.Label(
                self.box_body_piece_input_host,
                text=f"逐片尺寸：無法解析（{exc}）",
                foreground=WHD_SEMANTIC_COLORS["warning"],
            ).pack(fill=original.tk.X, pady=2)

    for projection in projections:
        part_key = str(projection.part_key)
        sub = original.ttk.LabelFrame(
            self.box_body_piece_input_host, text=projection.label, padding=4
        )
        sub._phase6_part_key = part_key
        sub.pack(fill=original.tk.X, pady=(2, 4))
        self.box_body_piece_input_sections[part_key] = sub
        self.box_body_piece_input_vars[part_key] = {}
        self.box_body_piece_input_entries[part_key] = {}

        spec = piece_values.get(part_key)
        if spec is not None:
            field_key, label, value, suffix, state_field = spec
            original.ttk.Label(sub, text=label).grid(
                row=0, column=0, sticky="w", padx=(0, 6), pady=2
            )
            var = original.tk.StringVar(
                master=sub, value=_setting_number_text(value)
            )
            entry = original.ttk.Entry(
                sub, textvariable=var, width=10, justify=original.tk.CENTER
            )
            entry.grid(row=0, column=1, sticky="w", pady=2)
            original.ttk.Label(sub, text=suffix).grid(
                row=0, column=2, sticky="w", padx=(5, 12), pady=2
            )

            if active is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
                callback = lambda v=var, f=state_field: _phase6_apply_box_structure_numeric(
                    self, active, f, v
                )
            elif active is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
                callback = lambda v=var, f=state_field: _phase6_apply_box_structure_numeric(
                    self, active, f, v
                )
            else:
                callback = lambda v=var, f=state_field: _phase6_apply_box_structure_numeric(
                    self, active, f, v
                )
            entry.bind("<Return>", lambda _e, cb=callback: cb())
            entry.bind("<FocusOut>", lambda _e, cb=callback: cb())
            self.box_body_piece_input_vars[part_key][field_key] = var
            self.box_body_piece_input_entries[part_key][field_key] = entry

        original.ttk.Label(
            sub,
            text=(
                f"包外尺寸：{_setting_number_text(projection.formed_width)} × "
                f"{_setting_number_text(projection.formed_height)} mm"
            ),
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 0))
        original.ttk.Label(
            sub,
            text=(
                f"料尺寸：{_setting_number_text(projection.blank_width)} × "
                f"{_setting_number_text(projection.blank_height)} mm"
            ),
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 2))

        if active is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
            if part_key in {"box_body:left_side", "box_body:right_side"}:
                original.ttk.Label(
                    sub,
                    text=f"成型深度 D：{_setting_number_text(_phase6_box_structure_d(self))} mm",
                ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(0, 2))
            elif part_key == "box_body:back":
                original.ttk.Label(
                    sub,
                    text=f"成型寬：{_setting_number_text(projection.formed_width)} mm",
                ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(0, 2))

    # Shared seam/relief settings remain shared canonical structure settings;
    # they are intentionally not duplicated into one child piece.
    row = 1
    if active in {BoxBodyStructureType.TWO_PIECE_W_SPLIT, BoxBodyStructureType.THREE_PIECE_W_SPLIT}:
        _phase6_structure_entry(
            frame, row, "中央接合折邊", cfg.get("seam_bend", 12),
            lambda v: _phase6_apply_box_structure_numeric(self, active, "seam_bend", v)
        )
        row += 1
        seam = float(cfg.get("seam_bend", 12))
        if seam >= 50:
            original.ttk.Label(
                frame,
                text=f"⚠ 中央接合折邊 {seam:g} mm 已達 50 mm 以上，請確認尺寸是否合理。",
                foreground=WHD_SEMANTIC_COLORS["warning"],
            ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(2, 4))
            row += 1
        advanced_flags = dict(getattr(self, "_phase6_box_structure_advanced_open", {}) or {})
        advanced_open = bool(advanced_flags.get(active.value, False))
        original.ttk.Button(
            frame, text=("▼ 截角／避讓" if advanced_open else "▶ 截角／避讓"),
            command=lambda t=active: _phase6_toggle_structure_advanced(self, t),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 0))
        row += 1
        advanced = original.ttk.LabelFrame(frame, text="截角／避讓", padding=4)
        if advanced_open:
            advanced.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(3, 0))
        row += 1
        ar = 0
        for label, field, value, suffix in (
            ("封頭尾額外避讓", "endcap_extra_relief", cfg.get("endcap_extra_relief", 5), "mm"),
            ("封頭尾單邊留肉", "endcap_single_side_meat_t", cfg.get("endcap_single_side_meat_t", 0.5), "T"),
            ("底板避讓總長", "baseplate_relief_length", cfg.get("baseplate_relief_length", 20), "mm"),
            ("底板單邊留肉", "baseplate_single_side_meat_t", cfg.get("baseplate_single_side_meat_t", 0.5), "T"),
        ):
            _phase6_structure_entry(
                advanced, ar, label, value,
                lambda v, f=field: _phase6_apply_box_structure_numeric(self, active, f, v),
                suffix=suffix,
            )
            ar += 1
    return start_row + 1


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


def _phase6_sync_joint_state_for_intent(self, type_id):
    snapshot = deepcopy(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    workspace = getattr(self, "designer_workspace", None)
    parts = tuple(getattr(workspace, "available_parts", ()) or snapshot.get("existing_parts", ()) or ())
    if parts:
        snapshot["existing_parts"] = list(parts)
    snapshot = migrate_legacy_snapshot_joints(snapshot)
    snapshot = sync_snapshot_intent_joints(snapshot, type_id)
    self._phase6_input_snapshot.update({
        "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
        "assembly_joints": deepcopy(snapshot["assembly_joints"]),
        "assembly_type": snapshot["assembly_type"],
    })
    return tuple(snapshot["assembly_joints"])


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

def _phase6_build_endcap_joint_settings(self, parent, part_key, start_row):
    # Compatibility hook only. Four-edge AssemblyJoint controls are owned by
    # the drawing-edge hosts and intentionally never live inside the lockable
    # settings panel. Canonical writes still go through
    # _phase6_on_endcap_edge_relation_selected().
    return start_row


def _phase6_build_assembly_settings(self, parent, start_row):
    # 組合方式已移到右側 3D 常駐控制列。保留函式只為舊 caller 相容，
    # 不再在可鎖定的參數面板重複建立第二份 UI。
    return start_row


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

def _phase6_build_box_symmetry_settings(self, parent, start_row):
    box = original.ttk.LabelFrame(parent, text="箱身折彎", padding=4)
    box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
    if not hasattr(self, "v_sy"):
        self.v_sy = original.tk.BooleanVar(value=bool(getattr(self.state, "symmetric", True)))
    original.ttk.Checkbutton(
        box,
        text="對稱折彎",
        variable=self.v_sy,
        command=lambda: _phase6_on_box_symmetry_changed(self),
    ).pack(side=original.tk.LEFT, padx=(0, 8))
    original.ttk.Label(box, text="開啟時，箱身兩側對應折彎同步修改").pack(side=original.tk.LEFT)
    return start_row + 1


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


def _phase6_build_receiving_bottom_wrap_settings(self, parent, part_key, start_row):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    if (
        str(part_key) not in ENDCAP_FW_PARTS
        or not cabinet_family_policy.supports_bottom_wrap_controls(snapshot)
    ):
        return start_row, None, None, None, None
    item = resolve_endcap_bottom_wrap(
        snapshot, str(part_key),
        state=getattr(self, "_phase6_endcap_bottom_wrap_state", normalize_endcap_bottom_wrap_state(snapshot)),
    )
    if not bool(item.get("enabled", False)):
        return start_row, None, None, None, None
    box = original.ttk.LabelFrame(parent, text="下方包覆貼外預留", padding=4)
    box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
    reserve_u_var = original.tk.StringVar(value=_setting_number_text(item["reserve_u"]))
    reserve_v_var = original.tk.StringVar(value=_setting_number_text(item["reserve_v"]))
    original.ttk.Label(box, text="X 預留 (mm)").grid(row=0, column=0, sticky="e")
    u_entry = original.ttk.Entry(box, textvariable=reserve_u_var, width=8, justify=original.tk.CENTER)
    u_entry.grid(row=0, column=1, padx=(3, 10))
    original.ttk.Label(box, text="Y 預留 (mm)").grid(row=0, column=2, sticky="e")
    v_entry = original.ttk.Entry(box, textvariable=reserve_v_var, width=8, justify=original.tk.CENTER)
    v_entry.grid(row=0, column=3, padx=3)
    for entry in (u_entry, v_entry):
        entry.bind("<Return>", lambda _e: _phase6_commit_receiving_bottom_wrap_controls(
            self, part_key, reserve_u_var, reserve_v_var
        ))
        entry.bind("<FocusOut>", lambda _e: _phase6_commit_receiving_bottom_wrap_controls(
            self, part_key, reserve_u_var, reserve_v_var
        ))
    original.ttk.Label(
        box, text="WRAP 關係由組合方式／Joint Graph 決定；此處只調整預留。封頭/封尾先連動，修改另一端後才獨立。"
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 0))
    return start_row + 1, None, reserve_u_var, reserve_v_var, box


def _phase6_build_corner_settings(self, parent, part_key, start_row):
    self.corner_pair_vars = {}
    self.corner_pair_checkbuttons = {}
    self.corner_type_vars = {}
    self.corner_mode_vars = {}
    self.corner_direction_vars = {}
    self.corner_amount_vars = {}
    self.corner_secondary_retain_vars = {}
    self.corner_secondary_depth_vars = {}
    self.corner_detail_frames = {}
    self.fixed_corner_summary_var = original.tk.StringVar(value="")
    self.corner_param_lock_button = None
    if part_key == GLOBAL_CONTEXT or part_key == "box_body":
        return start_row

    # Shared indicator parts are factory-fixed and never unlockable.
    if part_key in {"indicator_box", "indicator_door"}:
        summary = _FIXED_CORNER_SUMMARIES.get(part_key, "")
        if summary:
            box = original.ttk.LabelFrame(parent, text="截角類型（固定 / 唯讀）", padding=4)
            box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
            self.fixed_corner_summary_var.set(summary)
            original.ttk.Label(box, textvariable=self.fixed_corner_summary_var, wraplength=900).pack(anchor=original.tk.W)
            return start_row + 1
        return start_row

    type_editable = _phase6_corner_type_editable(self, part_key)
    params_unlocked = _phase6_corner_parameters_unlocked(self, part_key)
    params_editable = _phase6_corner_parameters_editable(self, part_key)

    if not type_editable and not params_unlocked:
        # A read-only settings page is a view. Building it must not materialize
        # default Corner state into the canonical manufacturing snapshot, or a
        # pure part switch invalidates the manufacturing cache.
        summary = _FIXED_CORNER_SUMMARIES.get(part_key, "")
        if summary:
            box = original.ttk.LabelFrame(parent, text="截角類型（固定 / 唯讀）", padding=4)
            box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
            self.fixed_corner_summary_var.set(summary)
            original.ttk.Label(box, textvariable=self.fixed_corner_summary_var, wraplength=900).pack(anchor=original.tk.W)
            return start_row + 1

    state, pairs = _phase6_ensure_corner_part(self, part_key)
    box = original.ttk.LabelFrame(
        parent,
        text="截角類型" if type_editable else "截角類型（基準預設）",
        padding=4,
    )
    box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))

    for pair_key in ("top", "bottom"):
        row = original.ttk.Frame(box)
        row.pack(fill=original.tk.X, pady=3)
        original.ttk.Label(row, text="上方" if pair_key == "top" else "下方", width=6).pack(side=original.tk.LEFT)
        same_var = original.tk.BooleanVar(master=row, value=bool(pairs[pair_key]))
        self.corner_pair_vars[pair_key] = same_var
        same_cb = original.ttk.Checkbutton(
            row, text="左右相同", variable=same_var,
            command=lambda p=part_key, pair=pair_key, v=same_var: _phase6_corner_pair_var_changed(self, p, pair, v),
        )
        same_cb.configure(state=("normal" if params_editable else "disabled"))
        self.corner_pair_checkbuttons[pair_key] = same_cb
        if params_unlocked:
            same_cb.pack(side=original.tk.LEFT, padx=(0, 6))
        targets = (pair_key,) if pairs[pair_key] else _CORNER_PAIR_KEYS[pair_key]

        for target_key in targets:
            physical = _CORNER_PAIR_KEYS[target_key][0] if target_key in _CORNER_PAIR_KEYS else target_key
            selection = _phase6_selection_from_raw(state[physical])
            target = original.ttk.Frame(row)
            target.pack(side=original.tk.LEFT, padx=(3, 8))
            if len(targets) > 1:
                original.ttk.Label(target, text="左" if target_key.endswith("left") else "右").grid(row=0, column=0, sticky="w")

            type_var = original.tk.StringVar(value=_CORNER_TYPE_LABEL_BY_ID[selection.type_id.value])
            self.corner_type_vars[target_key] = type_var
            top_assembly_owned = part_key in {"head", "tail"} and pair_key == "top"
            type_cb = build_choice_menubutton(
                target,
                variable=type_var,
                values=tuple(_CORNER_TYPE_LABEL_BY_ID.values()),
                state=("normal" if type_editable and not top_assembly_owned else "disabled"),
                width=12,
                command=lambda p=part_key, t=target_key: _phase6_corner_type_selected(self, p, t),
            )
            type_cb.grid(row=0, column=1, padx=2, sticky="w")

            subrow = original.ttk.Frame(target)
            self.corner_detail_frames[target_key] = subrow
            amount_var = original.tk.StringVar(value=_setting_number_text(selection.amount_t if selection.amount_t is not None else 1.0))
            self.corner_amount_vars[target_key] = amount_var

            if params_unlocked:
                subrow.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
            else:
                original.ttk.Label(
                    target,
                    text=_phase6_corner_parameter_summary(selection),
                ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

            if selection.type_id is CornerTypeId.CROSS:
                mode_var = original.tk.StringVar(value=_CORNER_MODE_LABEL[selection.cross_mode])
                self.corner_mode_vars[target_key] = mode_var
                mode_cb = build_choice_menubutton(
                    subrow,
                    variable=mode_var,
                    values=("標準", "單邊留肉", "多切"),
                    state=("normal" if params_editable else "disabled"),
                    width=9,
                    command=lambda p=part_key, t=target_key: _phase6_corner_mode_selected(self, p, t),
                )
                mode_cb.pack(side=original.tk.LEFT, padx=(0, 3))
                if selection.cross_mode is not CrossCornerMode.STANDARD:
                    direction_values = ("寬", "高") if selection.cross_mode is CrossCornerMode.RETAIN else ("寬＋高", "寬", "高")
                    direction_var = original.tk.StringVar(value=_CORNER_DIRECTION_LABEL[selection.direction])
                    self.corner_direction_vars[target_key] = direction_var
                    direction_cb = build_choice_menubutton(
                        subrow,
                        variable=direction_var,
                        values=direction_values,
                        state=("normal" if params_editable else "disabled"),
                        width=7,
                        command=lambda p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t),
                    )
                    direction_cb.pack(side=original.tk.LEFT, padx=3)
                    entry = original.ttk.Entry(subrow, textvariable=amount_var, width=6, justify=original.tk.CENTER)
                    entry.configure(state=("normal" if params_editable else "disabled"))
                    entry.pack(side=original.tk.LEFT, padx=(3, 1))
                    original.ttk.Label(subrow, text="T").pack(side=original.tk.LEFT)
                    entry.bind("<Return>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
                    entry.bind("<FocusOut>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
            elif selection.type_id in (CornerTypeId.OVERLAY, CornerTypeId.INSERT):
                action = "留肉（高）" if selection.type_id is CornerTypeId.OVERLAY else "多切（高）"
                original.ttk.Label(subrow, text=action).pack(side=original.tk.LEFT, padx=(0, 3))
                entry = original.ttk.Entry(subrow, textvariable=amount_var, width=6, justify=original.tk.CENTER)
                entry.configure(state=("normal" if params_editable else "disabled"))
                entry.pack(side=original.tk.LEFT, padx=(3, 1))
                original.ttk.Label(subrow, text="T").pack(side=original.tk.LEFT)
                entry.bind("<Return>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
                entry.bind("<FocusOut>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
            else:
                original.ttk.Label(subrow, text="貼外留肉（高）").pack(side=original.tk.LEFT, padx=(0, 2))
                primary = original.ttk.Entry(subrow, textvariable=amount_var, width=5, justify=original.tk.CENTER)
                primary.configure(state=("normal" if params_editable else "disabled"))
                primary.pack(side=original.tk.LEFT, padx=(1, 1)); original.ttk.Label(subrow, text="T").pack(side=original.tk.LEFT)
                retain_var = original.tk.StringVar(value=_setting_number_text(selection.secondary_retain_t))
                depth_var = original.tk.StringVar(value=_setting_number_text(selection.secondary_depth_t))
                self.corner_secondary_retain_vars[target_key] = retain_var
                self.corner_secondary_depth_vars[target_key] = depth_var
                original.ttk.Label(subrow, text="  嵌入留肉").pack(side=original.tk.LEFT)
                retain = original.ttk.Entry(subrow, textvariable=retain_var, width=5, justify=original.tk.CENTER)
                retain.configure(state=("normal" if params_editable else "disabled"))
                retain.pack(side=original.tk.LEFT, padx=(1, 1)); original.ttk.Label(subrow, text="T  深度").pack(side=original.tk.LEFT)
                depth = original.ttk.Entry(subrow, textvariable=depth_var, width=5, justify=original.tk.CENTER)
                depth.configure(state=("normal" if params_editable else "disabled"))
                depth.pack(side=original.tk.LEFT, padx=(1, 1)); original.ttk.Label(subrow, text="T").pack(side=original.tk.LEFT)
                for entry in (primary, retain, depth):
                    entry.bind("<Return>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
                    entry.bind("<FocusOut>", lambda _e, p=part_key, t=target_key: _phase6_corner_target_var_changed(self, p, t))
    return start_row + 1

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


def _phase6_render_settings_panel_extensions(self, parent, context, start_row):
    old = {name: getattr(self, name, None) for name in _SETTINGS_EXTENSION_MAP_ATTRS}
    old_summary = getattr(self, "fixed_corner_summary_var", None)
    old_lock_button = getattr(self, "corner_param_lock_button", None)
    for name in _SETTINGS_EXTENSION_MAP_ATTRS:
        setattr(self, name, {})
    self.fixed_corner_summary_var = original.tk.StringVar(value="")
    self.corner_param_lock_button = None
    endcap_fw_follow_var = None
    endcap_fw_value_var = None
    endcap_fw_widget = None
    bottom_wrap_enabled_var = None
    bottom_wrap_reserve_u_var = None
    bottom_wrap_reserve_v_var = None
    bottom_wrap_widget = None
    try:
        next_row = int(start_row)
        if context == "box_body":
            next_row = _phase6_build_box_structure_settings(self, parent, next_row)
        elif context in ENDCAP_FW_PARTS:
            next_row = _phase6_build_endcap_joint_settings(self, parent, context, next_row)
            next_row, endcap_fw_follow_var, endcap_fw_value_var, endcap_fw_widget = _phase6_build_endcap_fw_settings(
                self, parent, context, next_row
            )
            next_row, bottom_wrap_enabled_var, bottom_wrap_reserve_u_var, bottom_wrap_reserve_v_var, bottom_wrap_widget = (
                _phase6_build_receiving_bottom_wrap_settings(self, parent, context, next_row)
            )
        next_row = _phase6_build_corner_settings(self, parent, context, next_row)
        state = {name: dict(getattr(self, name, {}) or {}) for name in _SETTINGS_EXTENSION_MAP_ATTRS}
        state.update({
            "fixed_corner_summary_var": self.fixed_corner_summary_var,
            "corner_param_lock_button": self.corner_param_lock_button,
            "endcap_fw_follow_var": endcap_fw_follow_var,
            "endcap_fw_value_var": endcap_fw_value_var,
            "endcap_fw_widget": endcap_fw_widget,
            "bottom_wrap_enabled_var": bottom_wrap_enabled_var,
            "bottom_wrap_reserve_u_var": bottom_wrap_reserve_u_var,
            "bottom_wrap_reserve_v_var": bottom_wrap_reserve_v_var,
            "bottom_wrap_widget": bottom_wrap_widget,
        })
        return SettingsPanelExtensionResult(next_row=next_row, state=state)
    finally:
        for name, value in old.items():
            setattr(self, name, value if value is not None else {})
        self.fixed_corner_summary_var = old_summary
        self.corner_param_lock_button = old_lock_button


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
    panel = getattr(self, "settings_panel", None)
    if panel is not None:
        return panel
    panel = Phase6SettingsPanel(
        values_snapshot=lambda: dict(self._settings_values),
        stage_setting_update=lambda key, value: _phase6_stage_setting_update(self, key, value),
        flush_settings=lambda: _phase6_flush_pending_settings(self),
        save_defaults=lambda context: _phase6_save_settings_context_as_defaults(self, context),
        query_baseline_rows=(
            (lambda context, model, values: self._baseline_data_query_callback(context, model, values))
            if self._baseline_data_query_callback is not None else None
        ),
        is_unknown_baseline=lambda model: _phase6_is_unknown_baseline(self, model),
        should_show_baseline_data=lambda context, specs: _phase6_should_show_baseline_data(self, context, specs),
        part_labels=PART_LABELS,
        render_context_extensions=lambda parent, context, row: _phase6_render_settings_panel_extensions(self, parent, context, row),
        sync_context_extension=lambda state, context: _phase6_sync_settings_panel_extension(self, state, context),
        baseline_model_changed=lambda: _phase6_on_baseline_model_changed(self),
        ui_text_size_changed=lambda key: _phase6_apply_ui_text_size(self, key),
    )
    self.settings_panel = panel
    return panel


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


def _phase6_settings_panel_toggle_advanced(self):
    self.settings_panel.toggle_advanced()
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


def _phase6_show_global_settings(self):
    # Backwards-compatible API: global controls now live permanently at left.
    if hasattr(self, "settings_status_var"):
        self.settings_status_var.set("全域設定固定在左側")
    return getattr(self, "left_global_controls", None)



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


def _phase6_bind_translated_var(raw_var, display_var, to_display, to_raw):
    busy = {"value": False}
    def raw_changed(*_args):
        if busy["value"]:
            return
        busy["value"] = True
        try:
            display_var.set(to_display(raw_var.get()))
        finally:
            busy["value"] = False
    def display_changed(*_args):
        if busy["value"]:
            return
        busy["value"] = True
        try:
            raw_var.set(to_raw(display_var.get()))
        finally:
            busy["value"] = False
    raw_var.trace_add("write", raw_changed)
    display_var.trace_add("write", display_changed)
    raw_changed()
    display_var._phase6_raw_var = raw_var
    return display_var


def _phase6_form_choice(parent, variable, choices, *, width=18, presentation_field="choice"):
    display_var = original.tk.StringVar(
        master=parent,
        value=_phase6_registry_present_token(
            variable.get(),
            presentation_field=presentation_field,
            source_adapter="registry_choice",
        ),
    )
    button = original.ttk.Menubutton(parent, textvariable=display_var, width=width, style="Selector.TMenubutton")
    menu = configure_tk_menu(original.tk.Menu(button, tearoff=False))

    def choose(raw):
        variable.set(str(raw))
        display_var.set(_phase6_registry_present_token(
            raw,
            presentation_field=presentation_field,
            source_adapter="registry_choice",
        ))

    for choice in choices:
        menu.add_command(
            label=_phase6_registry_present_token(
                choice,
                presentation_field=presentation_field,
                source_adapter="registry_choice",
            ),
            command=lambda v=str(choice): choose(v),
        )
    button.configure(menu=menu)

    def sync_display(*_args):
        value = _phase6_registry_present_token(
            variable.get(),
            presentation_field=presentation_field,
            source_adapter="registry_choice",
        )
        if display_var.get() != value:
            display_var.set(value)

    variable.trace_add("write", sync_display)
    button._phase6_display_var = display_var
    button._phase6_raw_var = variable
    button._phase6_presentation_field = presentation_field
    return button


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

def _phase6_registry_preview_2d(self):
    result = _phase6_registry_validate_formula_form(self)
    canvas = getattr(self, "relief_registry_preview_canvas", None)
    if canvas is None:
        return result
    geometry = _phase6_corner_data_view(self).registry_preview_geometry(result)
    canvas.delete("all")
    canvas.create_rectangle(*geometry["outer"], outline="#777")
    if not result:
        return None
    for rect in geometry["cuts"]:
        canvas.create_rectangle(*rect, outline="#222", width=2)
    return result

def _phase6_registry_candidate_form_is_current(self):
    try:
        current = _phase6_registry_collect_rule_form(self)
    except Exception:
        return False
    return _phase6_registry_diagnostics(self).candidate_is_current(current)

def _phase6_registry_require_current_candidate(self):
    return _phase6_registry_diagnostics(self).require_current_candidate(
        _phase6_registry_collect_rule_form(self)
    )

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

def _phase6_registry_refresh_rule_tree(self):
    from ae_engine.certified_relief_registry import load_external_relief_rule_records
    tree = getattr(self, "relief_registry_rule_tree", None)
    if tree is None:
        return ()
    for item in tree.get_children():
        tree.delete(item)
    controller = _phase6_registry_diagnostics(self)
    rows = controller.load_rule_records(
        loader=load_external_relief_rule_records
    )
    _phase6_sync_registry_diagnostics_compatibility_mirrors(
        self, controller
    )
    active_rows = [row for row in rows if bool(row.get("active", True))]
    for row in active_rows:
        tree.insert("", "end", iid=f"{row['rule_id']}@{row['revision']}", values=(
            _phase6_registry_present_token(
                row["rule_id"],
                presentation_field="rule_id",
                source_adapter="registry_rule_tree",
            ),
            row["revision"],
            _phase6_registry_present_token(
                row.get("trust_level", ""),
                presentation_field="trust_level",
                source_adapter="registry_rule_tree",
            ),
            _phase6_registry_present_token(
                row.get("assembly_intent", ""),
                presentation_field="assembly_intent",
                source_adapter="registry_rule_tree",
            ),
            row.get("topology_levels", ""),
        ))
    return rows

def _phase6_registry_rule_selected(self, *_args):
    tree = getattr(self, "relief_registry_rule_tree", None)
    if tree is None or not tree.selection():
        return
    key = tree.selection()[0]
    raw = _phase6_registry_diagnostics(self).rule_record(key)
    if not raw:
        return
    formula = dict(raw.get("formula", {}) or {})
    self.relief_registry_rule_name_var.set(_phase6_registry_present_token(
        raw.get("rule_id", ""),
        presentation_field="rule_id",
        source_adapter="registry_rule_selection",
    ))
    setters = (
        (self.relief_registry_rule_id_var, raw.get("rule_id", "")),
        (self.relief_registry_family_var, raw.get("cabinet_family", "ANY")),
        (self.relief_registry_part_role_var, raw.get("part_role", "HEAD_OR_TAIL")),
        (self.relief_registry_joint_face_var, raw.get("joint_face", "TOP")),
        (self.relief_registry_intent_var, raw.get("assembly_intent", "INSERT_OVERLAY")),
        (self.relief_registry_topology_var, raw.get("topology_levels", 2)),
        (self.relief_registry_primary_u_var, formula.get("primary_u", "")),
        (self.relief_registry_primary_v_var, formula.get("primary_v", "")),
        (self.relief_registry_secondary_u_var, formula.get("secondary_u", "")),
        (self.relief_registry_secondary_depth_var, formula.get("secondary_depth", "")),
        (
            self.relief_registry_preconditions_var,
            ",".join(str(v) for v in (raw.get("preconditions", ()) or ())),
        ),
        (self.relief_registry_source_var, str(raw.get("source", ""))),
    )
    for var, value in setters:
        var.set(str(value))
    sig = list(raw.get("joint_signature", ()) or ())
    extra = sig[1].get("relation") if len(sig) > 1 else "NONE"
    self.relief_registry_extra_joint_var.set(str(extra))
    if len(sig) > 1:
        self.relief_registry_extra_target_role_var.set(
            str(sig[1].get("target_role", "REAR_PANEL"))
        )

def _phase6_joint_form_refresh(self):
    tree = getattr(self, "relief_joint_tree", None)
    if tree is None:
        return ()
    rows = _phase6_joint_rows(self)
    for item in tree.get_children():
        tree.delete(item)
    for row in rows:
        tree.insert("", "end", iid=str(row["joint_id"]), values=(
            _phase6_registry_present_token(row.get("subject_part", ""), presentation_field="subject_part", source_adapter="joint_tree"),
            _phase6_registry_present_token(row.get("target_part", ""), presentation_field="target_part", source_adapter="joint_tree"),
            _phase6_registry_present_token(row.get("relation", ""), presentation_field="relation", source_adapter="joint_tree"),
            _phase6_registry_present_token(row.get("source", ""), presentation_field="source", source_adapter="joint_tree"),
            _phase6_registry_present_token(row.get("subject_region", ""), presentation_field="subject_region", source_adapter="joint_tree"),
            _phase6_registry_present_token(row.get("target_region", ""), presentation_field="target_region", source_adapter="joint_tree"),
        ))
    return rows


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

def _phase6_configure_floating_surface(window, owner, *, modal=False):
    """Apply shared foreground/focus behavior without owning domain state."""
    try:
        return_focus = owner.focus_get()
    except Exception:
        return_focus = None
    if return_focus is None:
        return_focus = owner
    window._phase6_return_focus = return_focus

    def close_surface(_event=None):
        try:
            window.grab_release()
        except Exception:
            pass
        try:
            window.destroy()
        finally:
            try:
                if bool(return_focus.winfo_exists()):
                    return_focus.after_idle(return_focus.focus_set)
            except Exception:
                pass
        return "break"

    window._phase6_close_surface = close_surface
    try:
        window.transient(owner)
    except Exception:
        pass
    try:
        window.configure(takefocus=True)
    except Exception:
        pass
    window._phase6_foreground_role = "floating_surface"
    try:
        window.bind("<Escape>", close_surface, add="+")
        window.protocol("WM_DELETE_WINDOW", close_surface)
        window.lift()
        window.after_idle(window.focus_set)
    except Exception:
        pass
    if modal:
        try:
            window.grab_set()
        except Exception:
            pass
    return window


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

def _phase6_open_relief_registry_form(self):
    existing = getattr(self, "relief_registry_window", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify(); existing.lift(); return existing
    except Exception:
        pass
    win = original.tk.Toplevel(self.root)
    win.title("截角資料庫／組合接合")
    win.geometry("1120x720")
    _phase6_configure_floating_surface(win, self.root, modal=False)
    self.relief_registry_window = win
    notebook = original.ttk.Notebook(win)
    notebook.pack(fill=original.tk.BOTH, expand=True, padx=8, pady=8)
    self.relief_registry_notebook = notebook

    rules_tab = original.ttk.Frame(notebook, padding=8)
    joints_tab = original.ttk.Frame(notebook, padding=8)
    notebook.add(rules_tab, text="截角公式")
    notebook.add(joints_tab, text="組合接合")

    # ----- Rules tab -----
    left = original.ttk.Frame(rules_tab); left.pack(side=original.tk.LEFT, fill=original.tk.Y, padx=(0, 8))
    cols = ("id", "rev", "trust", "intent", "topology")
    tree = original.ttk.Treeview(left, columns=cols, show="headings", height=24)
    widths = {"id":280,"rev":45,"trust":105,"intent":120,"topology":55}
    labels = {"id":"規則名稱","rev":"版次","trust":"認證狀態","intent":"組合方式","topology":"級數"}
    for col in cols:
        tree.heading(col, text=labels[col]); tree.column(col, width=widths[col], stretch=(col=="id"))
    tree.pack(fill=original.tk.BOTH, expand=True)
    tree.bind("<<TreeviewSelect>>", lambda _e: _phase6_registry_rule_selected(self))
    self.relief_registry_rule_tree = tree

    form = original.ttk.Frame(rules_tab); form.pack(side=original.tk.LEFT, fill=original.tk.BOTH, expand=True)
    vars_defaults = {
        "rule_id":"USER_RULE_001", "rule_name":"自訂截角規則", "family":"ANY", "part_role":"HEAD_OR_TAIL", "joint_face":"TOP",
        "intent":"INSERT_OVERLAY", "topology":"2", "target_role":"BOX_SIDE", "extra_joint":"NONE",
        "extra_target_role":"REAR_PANEL", "primary_u":"side_fold + FW", "primary_v":"ytop1 + FW - T",
        "secondary_u":"side_fold + 0.5*T", "secondary_depth":"2*T",
        "preconditions":"ytop1_present,x_folded", "symmetry":"MIRROR_IF_GEOMETRY_SYMMETRIC", "source":"",
        "sample_t":"2", "sample_fw":"25", "sample_side":"15", "sample_ytop":"16", "sample_mating":"50",
    }
    for name, default in vars_defaults.items():
        setattr(self, f"relief_registry_{name}_var", original.tk.StringVar(value=default))
    self.relief_registry_status_var = original.tk.StringVar(value="請先驗證公式")

    row = 0
    def entry(label, var, width=28):
        nonlocal row
        original.ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=3, pady=2)
        widget = original.ttk.Entry(form, textvariable=var, width=width)
        widget.grid(row=row, column=1, columnspan=3, sticky="ew", padx=3, pady=2); row += 1
        return widget
    original.ttk.Label(form, text="規則名稱").grid(row=row, column=0, sticky="w", padx=3, pady=2)
    original.ttk.Entry(
        form, textvariable=self.relief_registry_rule_name_var, width=28, state="readonly"
    ).grid(row=row, column=1, columnspan=3, sticky="ew", padx=3, pady=2)
    row += 1
    original.ttk.Label(form, text="盤體條件").grid(row=row,column=0,sticky="w",padx=3,pady=2)
    _phase6_form_choice(form,self.relief_registry_family_var,("ANY","金庫型","受電箱"),width=14).grid(row=row,column=1,sticky="w")
    original.ttk.Label(form, text="板件角色").grid(row=row,column=2,sticky="e")
    _phase6_form_choice(form,self.relief_registry_part_role_var,("HEAD_OR_TAIL","HEAD","TAIL"),width=18).grid(row=row,column=3,sticky="ew"); row+=1
    original.ttk.Label(form,text="截角／接合位置").grid(row=row,column=0,sticky="w")
    _phase6_form_choice(form,self.relief_registry_joint_face_var,("TOP","BOTTOM"),width=18).grid(row=row,column=1,sticky="ew")
    original.ttk.Label(form,text="組合方式").grid(row=row,column=2,sticky="e")
    _phase6_form_choice(form,self.relief_registry_intent_var,("INSERT","OVERLAY","INSERT_OVERLAY"),width=16).grid(row=row,column=3,sticky="ew"); row+=1
    original.ttk.Label(form,text="截角級數").grid(row=row,column=0,sticky="w")
    _phase6_form_choice(form,self.relief_registry_topology_var,("1","2"),width=8).grid(row=row,column=1,sticky="w")
    original.ttk.Label(form,text="主要接合對象").grid(row=row,column=2,sticky="e")
    _phase6_form_choice(form,self.relief_registry_target_role_var,("BOX_SIDE","REAR_PANEL"),width=18).grid(row=row,column=3,sticky="ew"); row+=1
    original.ttk.Label(form,text="附加接合方式").grid(row=row,column=0,sticky="w")
    _phase6_form_choice(form,self.relief_registry_extra_joint_var,("NONE","WRAP","INSERT","OVERLAY","INSERT_OVERLAY"),width=16).grid(row=row,column=1,sticky="ew")
    original.ttk.Label(form,text="附加接合對象").grid(row=row,column=2,sticky="e")
    _phase6_form_choice(form,self.relief_registry_extra_target_role_var,("REAR_PANEL","BOX_SIDE"),width=18).grid(row=row,column=3,sticky="ew"); row+=1
    # Formulas and preconditions keep stable evaluator tokens internally while
    # the operator edits Traditional-Chinese aliases.
    for raw_name in ("primary_u", "primary_v", "secondary_u", "secondary_depth"):
        raw_var = getattr(self, f"relief_registry_{raw_name}_var")
        display_var = original.tk.StringVar(master=form)
        _phase6_bind_translated_var(
            raw_var,
            display_var,
            lambda value, field=raw_name: _phase6_registry_formula_display(
                value, presentation_field=field
            ),
            _phase6_formula_raw,
        )
        setattr(self, f"relief_registry_{raw_name}_display_var", display_var)
    self.relief_registry_preconditions_display_var = original.tk.StringVar(master=form)
    _phase6_bind_translated_var(
        self.relief_registry_preconditions_var, self.relief_registry_preconditions_display_var,
        _phase6_preconditions_display, _phase6_preconditions_raw,
    )
    entry("第一級橫向公式", self.relief_registry_primary_u_display_var)
    entry("第一級縱向公式", self.relief_registry_primary_v_display_var)
    entry("第二級橫向公式", self.relief_registry_secondary_u_display_var)
    entry("第二級深度公式", self.relief_registry_secondary_depth_display_var)
    entry("適用條件", self.relief_registry_preconditions_display_var)
    self.relief_registry_source_display_var = original.tk.StringVar(master=form)
    _phase6_bind_translated_var(
        self.relief_registry_source_var, self.relief_registry_source_display_var,
        lambda value: _phase6_registry_source_display(value, presentation_field="source"),
        _phase6_source_raw,
    )
    entry("公式來源／備註", self.relief_registry_source_display_var)

    help_box = original.ttk.LabelFrame(form, text="公式變數說明", padding=6)
    help_box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(5, 3)); row += 1
    help_lines = (
        "板厚：目前板件厚度。",
        "名義框寬：封頭／封尾自身的框寬參數；不等於箱身成型後實際占位。",
        "側折：封頭／封尾橫向側邊折彎基底；貼外沒有橫向折彎時為 0。",
        "上折：封頭／封尾縱向第一折尺寸。",
        "成型接合寬：接合對象折好後真正需要避讓的寬度，例如貼外取箱身成型框寬。",
        "第一級橫向／縱向：主要截角的橫向／縱向切除量；第二級橫向／深度：二級截角的內側位置與深度。",
        "嵌入、貼外、嵌入貼外、外側包覆皆以同一接合語意資料層保存。",
    )
    for help_row, text in enumerate(help_lines):
        original.ttk.Label(help_box, text=text, wraplength=660, justify="left").grid(
            row=help_row, column=0, sticky="w", pady=1
        )

    sample = original.ttk.LabelFrame(form,text="即時公式預覽",padding=5); sample.grid(row=row,column=0,columnspan=4,sticky="ew",pady=5); row+=1
    for col,(label,var) in enumerate((("板厚",self.relief_registry_sample_t_var),("名義框寬",self.relief_registry_sample_fw_var),("側折",self.relief_registry_sample_side_var),("上折",self.relief_registry_sample_ytop_var),("成型接合寬",self.relief_registry_sample_mating_var))):
        original.ttk.Label(sample,text=label).grid(row=0,column=col*2,sticky="e")
        original.ttk.Entry(sample,textvariable=var,width=7).grid(row=0,column=col*2+1,sticky="w",padx=(2,6))
    canvas=original.tk.Canvas(form,width=245,height=160,background="white",highlightthickness=1,highlightbackground="#aaa")
    canvas.grid(row=row,column=0,columnspan=4,sticky="w",pady=4); self.relief_registry_preview_canvas=canvas; row+=1
    actions=original.ttk.Frame(form); actions.grid(row=row,column=0,columnspan=4,sticky="ew",pady=4); row+=1
    for text,cmd in (
        ("驗證公式",lambda:_phase6_registry_validate_formula_form(self)),
        ("預覽平面",lambda:_phase6_registry_preview_2d(self)),
        ("預覽立體組合",lambda:_phase6_registry_preview_assembly_3d(self)),
        ("儲存候選",lambda:_phase6_registry_save_candidate_form(self)),
        ("執行回歸",lambda:_phase6_registry_run_formula_matrix(self)),
    ):
        original.ttk.Button(actions,text=text,command=cmd).pack(side=original.tk.LEFT,padx=2)
    self.relief_registry_save_candidate_button = next((w for w in actions.winfo_children() if str(w.cget("text"))=="儲存候選"), None)
    self.relief_registry_promote_button=original.ttk.Button(actions,text="認證新版次",command=lambda:_phase6_registry_promote_form(self),style="Primary.TButton")
    self.relief_registry_promote_button.pack(side=original.tk.LEFT,padx=2)
    original.ttk.Label(form,textvariable=self.relief_registry_status_var,foreground=WHD_THEME["text"]).grid(row=row,column=0,columnspan=4,sticky="w",pady=(4,0))
    for col in (1,3): form.columnconfigure(col,weight=1)

    # ----- Joint tab -----
    jcols=("subject","target","relation","source","subject_region","target_region")
    jtree=original.ttk.Treeview(joints_tab,columns=jcols,show="headings",height=15)
    for col,label,width in (("subject","主動板件",100),("target","接合板件",100),("relation","接合關係",130),("source","資料來源",120),("subject_region","主動板件區域",160),("target_region","接合板件區域",160)):
        jtree.heading(col,text=label); jtree.column(col,width=width)
    jtree.pack(fill=original.tk.X,pady=(0,8)); self.relief_joint_tree=jtree
    self.relief_joint_relation_choices=("INSERT","OVERLAY","INSERT_OVERLAY","WRAP")
    self.relief_joint_subject_var=original.tk.StringVar(value="head")
    self.relief_joint_target_var=original.tk.StringVar(value="box_body")
    self.relief_joint_relation_var=original.tk.StringVar(value="WRAP")
    self.relief_joint_subject_region_var=original.tk.StringVar(value="rear_edge")
    self.relief_joint_target_region_var=original.tk.StringVar(value="rear_mating")
    self.relief_joint_clearance_var=original.tk.StringVar(value="ZERO")
    self.relief_joint_topology_var=original.tk.StringVar(value="1")
    self.relief_joint_status_var=original.tk.StringVar(value="外側包覆：主動板件包覆接合板件")
    jf=original.ttk.LabelFrame(joints_tab,text="新增使用者接合規則",padding=6); jf.pack(fill=original.tk.X)
    fields=(
        ("主動板件",self.relief_joint_subject_var,("head","tail","box_body")),
        ("接合板件",self.relief_joint_target_var,("box_body","head","tail")),
        ("主動板件區域",self.relief_joint_subject_region_var,("rear_edge","TOP","BOTTOM")),
        ("接合板件區域",self.relief_joint_target_region_var,("rear_mating","MATING_ZONE","OUTER_SURFACE")),
        ("間隙條件",self.relief_joint_clearance_var,("ZERO",)),
    )
    for i,(label,var,choices) in enumerate(fields):
        original.ttk.Label(jf,text=label).grid(row=i//3*2,column=(i%3)*2,sticky="w",padx=3)
        _phase6_form_choice(jf,var,choices,width=18).grid(row=i//3*2+1,column=(i%3)*2,sticky="ew",padx=3,pady=(0,4))
    original.ttk.Label(jf,text="接合關係").grid(row=0,column=5,sticky="w",padx=3)
    _phase6_form_choice(jf,self.relief_joint_relation_var,self.relief_joint_relation_choices,width=16).grid(row=1,column=5,sticky="ew",padx=3)
    original.ttk.Label(jf,text="自動辨識級數").grid(row=2,column=4,sticky="w",padx=3)
    _phase6_form_choice(jf,self.relief_joint_topology_var,("1","2"),width=8).grid(row=3,column=4,sticky="w",padx=3)
    buttons=original.ttk.Frame(joints_tab); buttons.pack(fill=original.tk.X,pady=6)
    original.ttk.Button(buttons,text="新增接合",command=lambda:_phase6_joint_form_add(self)).pack(side=original.tk.LEFT,padx=2)
    original.ttk.Button(buttons,text="刪除使用者接合",command=lambda:_phase6_joint_form_delete(self)).pack(side=original.tk.LEFT,padx=2)
    original.ttk.Label(buttons,textvariable=self.relief_joint_status_var).pack(side=original.tk.LEFT,padx=10)

    _phase6_registry_refresh_rule_tree(self)
    _phase6_joint_form_refresh(self)
    return win


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



def _phase6_install_keyboard_shortcuts(self):
    """Compatibility view-binding facade; command_router owns the binding loop."""
    return install_fold_designer_keyboard_shortcuts(
        self,
        on_save=lambda event: _phase6_keyboard_save(self, event),
        on_open=lambda event: _phase6_keyboard_open(self, event),
        on_fullscreen=lambda event: _phase6_keyboard_fullscreen(self, event),
    )

def _phase6_build_project_toolbar(self, parent=None):
    """永久置頂的「檔案」選單。"""
    parent = parent or self.left
    self.project_toolbar = original.ttk.Frame(parent)
    self.project_toolbar.pack(side=original.tk.LEFT, padx=(0, 8))
    self.project_file_button = original.ttk.Menubutton(self.project_toolbar, text="檔案 ▼", style="Secondary.TMenubutton", takefocus=True)
    self.project_file_menu = configure_tk_menu(original.tk.Menu(self.project_file_button, tearoff=False))
    self.project_file_menu.add_command(label="開啟", command=self.load_project_file)
    self.project_file_menu.add_command(label="儲存", command=self.save_project_file)
    self.project_file_menu.add_command(label="另存新檔", command=self.save_project_file_as)
    self.project_file_button.configure(menu=self.project_file_menu)
    self.project_file_button.pack(side=original.tk.LEFT)
    self.relief_registry_button = original.ttk.Button(
        self.project_toolbar, text="截角資料庫", command=lambda: _phase6_open_relief_registry_form(self), style="Secondary.TButton", takefocus=True
    )
    self.relief_registry_button.pack(side=original.tk.LEFT, padx=(6, 0))




def _phase6_build_transaction_buttons(self, parent=None):
    """Top-right project actions: live canonical mode has no confirm/cancel."""
    parent = parent or self.left
    self.transaction_buttons = original.ttk.Frame(parent)
    self.transaction_buttons.pack(side=original.tk.RIGHT)
    self.transaction_buttons.columnconfigure(0, weight=1)
    self.reset_initial_button = original.ttk.Button(
        self.transaction_buttons, text="還原初始值", command=self.reset_initial_values, style="Secondary.TButton", takefocus=True
    )
    self.reset_initial_button.grid(row=0, column=0, sticky="ew")


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


def _phase6_build_visual_controls(self, parent):
    # T2 presentation only: keep the existing display controls/variables, but
    # remove the decorative section title so the renderer gets the vertical space.
    self.visual_controls = original.ttk.Frame(parent, padding=(4, 2))
    self.visual_controls.pack(side=original.tk.LEFT, fill=original.tk.X, padx=(0, 8))

    original.ttk.Label(self.visual_controls, text="文字大小").grid(row=0, column=0, sticky="w")
    self.ui_text_size_combo = build_choice_menubutton(
        self.visual_controls,
        variable=self.ui_text_size_var,
        values=tuple(UI_TEXT_SIZE_LABELS.values()),
        width=5,
    )
    self.ui_text_size_combo.grid(row=0, column=1, sticky="w", padx=(4, 10))
    self.settings_panel.ui_text_size_combo = self.ui_text_size_combo

    original.ttk.Label(self.visual_controls, text="折彎透視").grid(row=0, column=2, sticky="w")
    original.ttk.Scale(
        self.visual_controls, from_=0.1, to=1.0, variable=self.v_a_bend, command=self.queue_update,
        length=110,
    ).grid(row=0, column=3, sticky="ew", padx=(4, 8))
    original.ttk.Label(self.visual_controls, text="面板透視").grid(row=0, column=4, sticky="w")
    original.ttk.Scale(
        self.visual_controls, from_=0.0, to=1.0, variable=self.v_a_face, command=self.queue_update,
        length=110,
    ).grid(row=0, column=5, sticky="ew", padx=(4, 0))


def _phase6_toggle_fullscreen(self):
    root = self.root
    enabled = bool(getattr(self, "_phase6_fullscreen", False))
    if not enabled:
        try:
            self._phase6_restore_geometry = root.geometry()
        except Exception:
            self._phase6_restore_geometry = None
        applied = False
        try:
            root.state("zoomed")
            applied = True
        except Exception:
            pass
        if not applied:
            try:
                root.attributes("-zoomed", True)
                applied = True
            except Exception:
                pass
        if not applied:
            try:
                root.attributes("-fullscreen", True)
                applied = True
            except Exception:
                pass
        self._phase6_fullscreen = bool(applied)
    else:
        restored = False
        try:
            root.attributes("-fullscreen", False)
        except Exception:
            pass
        try:
            root.attributes("-zoomed", False)
        except Exception:
            pass
        try:
            root.state("normal")
            restored = True
        except Exception:
            pass
        geometry = getattr(self, "_phase6_restore_geometry", None)
        if restored and geometry:
            try:
                root.geometry(geometry)
            except Exception:
                pass
        self._phase6_fullscreen = False
    button = getattr(self, "fullscreen_button", None)
    if button is not None:
        button.configure(text=("還原視窗" if self._phase6_fullscreen else "全螢幕"))
    return self._phase6_fullscreen


def _phase6_build_global_persistent_controls(self):
    host = self.left_global_controls

    self.parameter_lock_button = original.ttk.Button(
        host,
        text="參數鎖定",
        command=lambda: _phase6_toggle_parameter_panel(self),
        style="Secondary.TButton",
    )
    self.parameter_lock_button.grid(row=0, column=3, sticky="ew", padx=2, pady=2)

    state = _phase6_box_structure_state(self)
    active = BoxBodyStructureType(state["active_type"])
    structure_cell = original.ttk.Frame(host)
    structure_cell.grid(row=1, column=4, sticky="ew", padx=2, pady=2)
    self.left_global_cells["structure"] = structure_cell
    original.ttk.Label(structure_cell, text="結構").pack(anchor=original.tk.W)
    self.structure_type_var = original.tk.StringVar(value=_BOX_STRUCTURE_LABELS[active])
    self.structure_choice_button = build_choice_menubutton(
        structure_cell,
        variable=self.structure_type_var,
        values=tuple(_BOX_STRUCTURE_LABELS.values()),
        width=16,
        command=lambda: _phase6_select_box_structure_type(self, self.structure_type_var),
    )
    self.structure_choice_button.pack(fill=original.tk.X)

    assembly_cell = original.ttk.Frame(host)
    assembly_cell.grid(row=1, column=5, sticky="ew", padx=2, pady=2)
    self.left_global_cells["assembly"] = assembly_cell
    original.ttk.Label(assembly_cell, text="組合方式").pack(anchor=original.tk.W)
    self.assembly_type_var = original.tk.StringVar(
        value=ASSEMBLY_TYPE_LABELS[getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)]
    )
    self.assembly_choice_button = build_choice_menubutton(
        assembly_cell,
        variable=self.assembly_type_var,
        values=tuple(ASSEMBLY_TYPE_LABELS.values()),
        width=12,
        command=lambda: _phase6_on_assembly_type_selected(self),
    )
    self.assembly_choice_button.pack(fill=original.tk.X)

    # BOTTOM WRAP is selected through the canonical 組合方式 preset (包覆貼外).
    # Do not expose a second enable/disable control in the permanent 3D row.
    host.columnconfigure(4, weight=1)
    host.columnconfigure(5, weight=1)
    _phase6_refresh_persistent_structure_controls(self)


def _phase6_refresh_sticky_structure_tree(self):
    """Keep the one #124 Structure Tree on-screen while lower left inputs scroll.

    This is presentation-only.  The existing Treeview remains the single
    navigation surface and continues to consume DM7 stable identities/callbacks.
    A spacer owns its normal layout slot; ``place`` only offsets that same widget
    against the left Canvas viewport.
    """
    canvas = getattr(self, "left_scroll_canvas", None)
    host = getattr(self, "structure_tree_host", None)
    spacer = getattr(self, "structure_tree_spacer", None)
    if canvas is None or host is None or spacer is None:
        return
    try:
        requested_height = max(1, int(host.winfo_reqheight()))
        current_height = int(float(spacer.cget("height") or 0))
        if current_height != requested_height:
            spacer.configure(height=requested_height)
        base_y = float(spacer.winfo_y())
        scroll_y = float(canvas.canvasy(0))
        host.place_configure(
            x=0, y=int(round(max(base_y, scroll_y))),
            relwidth=1.0, height=requested_height,
        )
        host.lift()
    except Exception:
        # Presentation refresh must never block manufacturing/navigation state.
        return


def _phase6_commit_output_draw_stock(self):
    """Commit the 3D STOCK toggle through the project command owner."""
    return Phase6ProjectController.commit_output_stock(
        bool(self.output_draw_stock_var.get()),
        lambda key, value: _phase6_stage_setting_update(self, key, value),
    )

def _phase6_export_selected_dxf_from_3d(self):
    """Delegate the 3D action through the project command owner."""
    return Phase6ProjectController.route_selected_dxf_export(
        getattr(self, "_phase6_export_selected_dxf_callback", None),
        self.flush_pending_settings,
    )

def _phase6_build_output_controls(self, parent=None):
    """Compact top-row Output projection using the existing state/callback owners."""
    host = parent or self.top_command_row
    self.output_controls_frame = original.ttk.Frame(host, padding=(4, 0))
    self.output_controls_frame.pack(side=original.tk.RIGHT, fill=original.tk.X)

    draw_stock_var = getattr(self, "_phase6_external_draw_stock_var", None)
    if draw_stock_var is None:
        draw_stock_var = original.tk.BooleanVar(
            master=self.output_controls_frame,
            value=bool(self._settings_values.get("draw_stock", False)),
        )
    self.output_draw_stock_var = draw_stock_var
    self.output_draw_stock_check = original.ttk.Checkbutton(
        self.output_controls_frame,
        text="輸出 STOCK 母材外框",
        variable=self.output_draw_stock_var,
        command=lambda: _phase6_commit_output_draw_stock(self),
    )
    self.output_draw_stock_check.pack(side=original.tk.LEFT, padx=(0, 6))

    parts_host = original.ttk.Frame(self.output_controls_frame)
    parts_host.pack(side=original.tk.LEFT)
    external_vars = dict(getattr(self, "_phase6_external_export_vars", {}) or {})
    labels = (
        ("box_body", "箱身"),
        ("head", "封頭"),
        ("tail", "封尾"),
        ("door", "門"),
        ("base_plate", "底板"),
        ("indicator_box", "指示燈盒子"),
        ("indicator_door", "指示燈小門"),
    )
    default_enabled = {
        "box_body": True, "head": True, "tail": True,
        "door": True, "base_plate": True,
        "indicator_box": False, "indicator_door": False,
    }
    self.output_export_vars = {}
    self.output_export_checks = {}
    for index, (key, label) in enumerate(labels):
        var = external_vars.get(key)
        if var is None:
            var = original.tk.BooleanVar(
                master=parts_host, value=bool(default_enabled[key])
            )
        self.output_export_vars[key] = var
        check = original.ttk.Checkbutton(parts_host, text=label, variable=var)
        check.grid(row=0, column=index, sticky=original.tk.W, padx=(0, 6))
        self.output_export_checks[key] = check

    self.output_export_button = original.ttk.Button(
        self.output_controls_frame,
        text="輸出選取的 DXF 檔案",
        command=lambda: _phase6_export_selected_dxf_from_3d(self),
        style="Primary.TButton",
        takefocus=True,
    )
    self.output_export_button.pack(side=original.tk.LEFT, padx=(4, 0))


def _phase6_build_persistent_top_area(self):
    """Operator layout: top commands, scrollable left inputs, right controls/canvas."""
    previous_status = getattr(self, "status_bar", None)
    if previous_status is not None:
        try:
            previous_status.destroy()
        except Exception:
            pass
    self.status_bar = original.ttk.Frame(self.root, padding=(8, 2))
    original.ttk.Separator(
        self.status_bar, orient=original.tk.HORIZONTAL
    ).pack(fill=original.tk.X, pady=(0, 2))
    self.status_projection_var = original.tk.StringVar(
        master=self.status_bar, value=_phase6_status_projection(self)
    )
    self.status_projection_label = original.ttk.Label(
        self.status_bar, textvariable=self.status_projection_var, anchor=original.tk.W
    )
    self.status_projection_label.pack(fill=original.tk.X)
    self.status_bar.pack(side=original.tk.BOTTOM, fill=original.tk.X)

    try:
        self.left.pack_forget()
        self.right.pack_forget()
    except Exception:
        pass

    # The top command surface is intentionally tiny: project File + Corner Data only.
    self.top_persistent_bar = original.ttk.Frame(self.root, padding=(10, 8, 10, 4))
    self.top_persistent_bar.pack(side=original.tk.TOP, fill=original.tk.X)
    self.top_command_row = original.ttk.Frame(self.top_persistent_bar)
    self.top_command_row.pack(fill=original.tk.X)
    _phase6_build_project_toolbar(self, self.top_command_row)
    _phase6_build_output_controls(self, self.top_command_row)

    # Right-side controls are ordered for vertical economy: display/actions first,
    # global settings immediately below, then the existing renderer viewport.
    self.right_controls_host = original.ttk.Frame(self.right, padding=(8, 4, 8, 2))
    self.right_global_host = original.ttk.Frame(self.right_controls_host)
    panel = _phase6_ensure_settings_panel(self)
    panel.build_left_global_controls(
        self.right_global_host,
        baseline_models=tuple(self._baseline_models),
        initial_model=self._phase6_baseline_initial_model,
    )
    _phase6_sync_settings_panel_compat(self)
    _phase6_build_global_persistent_controls(self)
    _phase6_sync_settings_panel_compat(self)

    # Build display controls only after the shared settings panel has created
    # ui_text_size_var; this preserves the existing ownership/lifecycle.
    self.right_controls_primary = original.ttk.Frame(self.right_controls_host)
    self.right_controls_primary.pack(fill=original.tk.X, pady=(5, 0))
    _phase6_build_transaction_buttons(self, self.right_controls_primary)
    _phase6_build_visual_controls(self, self.right_controls_primary)
    self.fullscreen_button = original.ttk.Button(
        self.right_controls_primary,
        text="全螢幕",
        command=lambda: _phase6_toggle_fullscreen(self),
        style="Secondary.TButton",
        takefocus=True,
    )
    self.fullscreen_button.pack(side=original.tk.LEFT, padx=(0, 4))
    self.right_global_host.pack(fill=original.tk.X, pady=(4, 0))
    _phase6_pack_right_panel_above_canvas(self, self.right_controls_host)

    # The complete existing left workspace is one scroll owner. It keeps the same
    # selector/editor/state callbacks; this canvas changes presentation only.
    self.left_scroll_canvas = original.tk.Canvas(
        self.root,
        width=_phase6_left_workspace_width(self._settings_values.get("ui_text_size", "small")),
        highlightthickness=0,
        borderwidth=0,
        takefocus=False,
    )
    def _left_scroll_command(*args):
        self.left_scroll_canvas.yview(*args)
        _phase6_refresh_sticky_structure_tree(self)

    def _left_yview_changed(first, last):
        self.left_scrollbar.set(first, last)
        _phase6_refresh_sticky_structure_tree(self)

    self.left_scrollbar = original.ttk.Scrollbar(
        self.root,
        orient=original.tk.VERTICAL,
        command=_left_scroll_command,
    )
    self.left_scroll_canvas.configure(yscrollcommand=_left_yview_changed)
    try:
        self.left.pack_propagate(True)
    except Exception:
        pass
    self.left_scroll_window = self.left_scroll_canvas.create_window(
        (0, 0), window=self.left, anchor="nw"
    )

    def _sync_left_scrollregion(_event=None):
        try:
            bbox = self.left_scroll_canvas.bbox("all")
            if bbox is not None:
                self.left_scroll_canvas.configure(scrollregion=bbox)
            _phase6_refresh_sticky_structure_tree(self)
        except Exception:
            pass

    def _size_left_window(event):
        try:
            self.left_scroll_canvas.itemconfigure(
                self.left_scroll_window, width=max(1, int(event.width))
            )
        except Exception:
            pass
        _sync_left_scrollregion()

    self.left.bind("<Configure>", _sync_left_scrollregion, add="+")
    self.left_scroll_canvas.bind("<Configure>", _size_left_window, add="+")
    self.left_scroll_canvas.pack(side=original.tk.LEFT, fill=original.tk.Y)
    self.left_scrollbar.pack(side=original.tk.LEFT, fill=original.tk.Y)
    self.right.pack(side=original.tk.RIGHT, fill=original.tk.BOTH, expand=True)
    # self.left is a root child embedded as a Canvas window. Keep the embedded
    # operator workspace above its sibling Canvas so mapped controls are actually
    # visible and hit-testable instead of being painted underneath the Canvas.
    self.left.lift(self.left_scroll_canvas)
    _sync_left_scrollregion()
    _phase6_install_keyboard_shortcuts(self)


def _phase6_reset_initial_values(self):
    """Restore the immutable AE factory defaults inside the 3D transaction.

    The source is ``ae_engine.ae.default_config`` captured by the main GUI when
    開啟此設計器時的工作區內容。基準型號與手動截角交易資料不屬於
    of that mapping and therefore remain untouched.
    """
    self.flush_pending_settings()
    factory = dict(getattr(self, "_factory_defaults", {}) or {})
    if not factory:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set("找不到程式初始值")
        return False

    clean = {}
    for key, raw in factory.items():
        if key not in self._settings_values:
            continue
        if isinstance(self._settings_values.get(key), bool):
            clean[key] = bool(raw)
        else:
            try:
                clean[key] = float(raw)
            except (TypeError, ValueError):
                continue
    if not clean:
        return False

    _phase6_replace_mapping(self, "_phase6_pending_settings", {})
    self._settings_values.update(clean)
    self._phase6_input_snapshot.update(clean)
    if "t" in clean:
        self.state.phase6_thickness = float(clean["t"])
    for key in ("w", "h", "d"):
        if key in clean:
            self._phase6_box_whd[key] = _ui_len(clean[key])

    # Recreate the standard profiles rather than merging into the edited ones;
    # this is what makes added/changed fold segments truly return to defaults.
    _phase6_recalculate_part_dimensions(self)
    reset_snapshot = self._phase6_input_snapshot
    self.state.profiles_vault["箱身"] = build_box_body_profile(reset_snapshot)
    for part_key in self.designer_workspace.available_parts:
        if part_key == "box_body":
            continue
        defaults = (
            build_endcap_xy_profiles(reset_snapshot, part_key=part_key)
            if part_key in {"head", "tail"}
            else build_standard_part_profiles(reset_snapshot, part_key)
        )
        self.designer_workspace.stash_profiles(part_key, defaults)

    active = self.designer_workspace.active_part
    if active == "box_body":
        self.state.phase6_fold_ui_profiles = {"X": self.state.profiles_vault["箱身"]}
    elif active in self.designer_workspace.available_parts:
        profiles = self.designer_workspace.profiles_for(active, {}) or {}
        self.state.profiles["X"] = clone_profile(profiles.get("X", []))
        self.state.profiles["Y"] = clone_profile(profiles.get("Y", []))

    self._phase6_settings_guard = True
    try:
        if "w" in clean:
            self.v_w.set(_setting_number_text(clean["w"]))
        if "h" in clean:
            self.v_h.set(_setting_number_text(clean["h"]))
        if "d" in clean:
            self.v_d.set(_setting_number_text(clean["d"]))
        for key, var in getattr(self, "left_global_vars", {}).items():
            if key not in clean:
                continue
            if isinstance(var, original.tk.BooleanVar):
                var.set(bool(clean[key]))
            else:
                var.set(_setting_number_text(clean[key]))
        for key, var in getattr(self, "setting_vars", {}).items():
            if key not in clean:
                continue
            if isinstance(var, original.tk.BooleanVar):
                var.set(bool(clean[key]))
            else:
                var.set(_setting_number_text(clean[key]))
    finally:
        self._phase6_settings_guard = False

    self.designer_workspace.mark_dirty()
    try:
        self.bend_ui.render()
    except Exception:
        pass
    try:
        if hasattr(self, "settings_panel"):
            self.settings_panel.refresh_baseline_data()
    except Exception:
        pass
    try:
        self.do_update()
    except Exception:
        pass
    if hasattr(self, "settings_status_var"):
        self.settings_status_var.set("已還原程式初始值並同步主畫面")
    return True


def _phase6_save_settings_context_as_defaults(self, context):
    self.flush_pending_settings()
    callback = self._save_defaults_callback
    if callback is None:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set("未連接預設值儲存器")
        return False
    payload = _phase6_settings_transactions(self).settings_defaults_payload(context)
    try:
        Phase6ProjectController.route_settings_defaults(callback, payload)
    except Exception as exc:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"儲存失敗：{exc}")
        return False
    if hasattr(self, "settings_status_var"):
        self.settings_status_var.set("已儲存到 config.ini")
    return True

def _phase6_scene_from_structural_result(result, features, surface_id):
    from ae_engine.sheetmetal_drawing import DrawingScene, structural_result_to_primitives, resolved_features_to_primitives
    from ae_engine.sheetmetal_features import feature_surface_from_structural_result, resolve_surface_features

    scene = DrawingScene()
    scene.extend(structural_result_to_primitives(result))
    if features:
        surface = feature_surface_from_structural_result(surface_id, result)
        scene.extend(resolved_features_to_primitives(
            resolve_surface_features(surface, list(features), float(result.width), float(result.height))
        ))
    return scene








def _phase6_scene_query_payload_for_part(self, part_key):
    """Compatibility wrapper for the manufacturing adapter-owned payload builder."""
    return build_scene_payload_for_app(self, part_key)
def _phase6_scene_query_payload(self):
    """Return only current draft PartSpec inputs; no geometry is built here."""
    return _phase6_scene_query_payload_for_part(self, self.designer_workspace.active_part)



def _phase6_query_final_render_data(self):
    """Compatibility delegate to the T6 final-scene view adapter."""
    return _phase6_final_scene_adapter(self).query_final_render_data()

def _phase6_active_mesh_profiles(self, material):
    return _phase6_mesh_profiles_for_part(self, self.designer_workspace.active_part, material)


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



def _phase6_make_assembly_scene_render_data(
    *,
    assembly_parts,
    visible_part_keys=None,
    visible_box_body_piece_keys=None,
    show_interference=False,
    ignore_fixed_corner_relief=False,
    interference_probe_parts=(),
    joint_diagnostics=(),
    selected_joint_id=None,
    preserve_endcap_core_origin=False,
):
    """Compatibility delegate for assembly-scene bundle construction."""
    return _project_assembly_scene_render_data(
        assembly_parts=assembly_parts,
        visible_part_keys=visible_part_keys,
        visible_box_body_piece_keys=visible_box_body_piece_keys,
        show_interference=show_interference,
        ignore_fixed_corner_relief=ignore_fixed_corner_relief,
        interference_probe_parts=interference_probe_parts,
        joint_diagnostics=joint_diagnostics,
        selected_joint_id=selected_joint_id,
        preserve_endcap_core_origin=preserve_endcap_core_origin,
        render_data_cls=AssemblySceneRenderData,
    )

def _phase6_refresh_box_body_piece_info_rows(self, render_data) -> None:
    """Render resolved BoxBody children nested under the single logical 箱身 row."""
    host = getattr(self, "assembly_box_body_piece_host", None)
    if host is None:
        return
    projections = _phase6_box_body_piece_dimension_projections(render_data)
    wanted = tuple(row.part_key for row in projections)
    current = tuple(dict(getattr(self, "assembly_box_body_piece_formed_vars", {}) or {}))
    previous_visible = {
        key: bool(var.get())
        for key, var in dict(getattr(self, "assembly_box_body_piece_visible_vars", {}) or {}).items()
    }
    previous_visible = {
        **dict(getattr(self, "_phase6_box_body_piece_visibility_stash", {}) or {}),
        **previous_visible,
    }
    previous_open = dict(
        getattr(self, "_phase6_box_body_piece_detail_open_stash", {}) or {}
    )
    previous_open.update({
        key: bool(frame.winfo_manager())
        for key, frame in dict(
            getattr(self, "assembly_box_body_piece_detail_frames", {}) or {}
        ).items()
    })
    self._phase6_box_body_piece_detail_open_stash = previous_open
    if current != wanted:
        for child in host.winfo_children():
            child.destroy()
        self.assembly_box_body_piece_labels = {}
        self.assembly_box_body_piece_sections = {}
        self.assembly_box_body_piece_visible_vars = {}
        self.assembly_box_body_piece_checkbuttons = {}
        self.assembly_box_body_piece_detail_frames = {}
        self.assembly_box_body_piece_detail_buttons = {}
        self.assembly_box_body_piece_formed_vars = {}
        self.assembly_box_body_piece_blank_vars = {}
        self.assembly_box_body_piece_corner_vars = {}
        piece_by_role = {
            str(getattr(piece, "role", "")): piece
            for piece in tuple(getattr(render_data, "pieces", ()) or ())
        }
        for projection in projections:
            sub = original.ttk.Frame(host, padding=4)
            sub._phase6_part_key = projection.part_key
            sub.pack(fill=original.tk.X, padx=(18, 0), pady=(2, 4))
            self.assembly_box_body_piece_labels[projection.part_key] = projection.label
            self.assembly_box_body_piece_sections[projection.part_key] = sub
            visible = original.tk.BooleanVar(
                master=sub, value=previous_visible.get(projection.part_key, True)
            )
            header = original.ttk.Frame(sub)
            header.pack(fill=original.tk.X)
            check = original.ttk.Checkbutton(
                header, text=projection.label, variable=visible,
                command=lambda: _phase6_on_assembly_part_visibility_changed(self),
            )
            check.pack(side=original.tk.LEFT, anchor=original.tk.W, fill=original.tk.X, expand=True)
            details = original.ttk.Frame(sub)
            details_open = previous_open.get(projection.part_key, True)
            detail_button = original.ttk.Button(
                header,
                text=("▾" if details_open else "▸"),
                width=2,
                command=lambda k=projection.part_key: _phase6_toggle_box_body_piece_details(self, k),
                takefocus=True,
            )
            detail_button.pack(side=original.tk.RIGHT)
            formed = original.tk.StringVar(master=sub)
            blank = original.tk.StringVar(master=sub)
            corner = original.tk.StringVar(master=sub)
            original.ttk.Label(details, textvariable=formed, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(18, 0))
            original.ttk.Label(details, textvariable=blank, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(18, 0))
            original.ttk.Label(details, textvariable=corner, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(18, 0))
            if details_open:
                details.pack(fill=original.tk.X)
            self.assembly_box_body_piece_visible_vars[projection.part_key] = visible
            self.assembly_box_body_piece_checkbuttons[projection.part_key] = check
            self.assembly_box_body_piece_detail_frames[projection.part_key] = details
            self.assembly_box_body_piece_detail_buttons[projection.part_key] = detail_button
            self.assembly_box_body_piece_formed_vars[projection.part_key] = formed
            self.assembly_box_body_piece_blank_vars[projection.part_key] = blank
            self.assembly_box_body_piece_corner_vars[projection.part_key] = corner
            _phase6_bind_assembly_scroll(sub, self)
    piece_by_role = {
        str(getattr(piece, "role", "")): piece
        for piece in tuple(getattr(render_data, "pieces", ()) or ())
    }
    for projection in projections:
        self.assembly_box_body_piece_formed_vars[projection.part_key].set(
            f"成形尺寸：{_setting_number_text(projection.formed_width)} × {_setting_number_text(projection.formed_height)} mm"
        )
        self.assembly_box_body_piece_blank_vars[projection.part_key].set(
            f"展開料：{_setting_number_text(projection.blank_width)} × {_setting_number_text(projection.blank_height)} mm"
        )
        role = projection.part_key.split(":", 1)[-1]
        piece = piece_by_role.get(role)
        corner_text = _phase6_render_data_corner_dimension_text(piece.render_data) if piece is not None else "截角尺寸：無"
        self.assembly_box_body_piece_corner_vars[projection.part_key].set(corner_text)
    self._phase6_box_body_piece_visibility_stash = {
        key: bool(var.get())
        for key, var in dict(getattr(self, "assembly_box_body_piece_visible_vars", {}) or {}).items()
    }
    logical_formed = (getattr(self, "assembly_part_formed_vars", {}) or {}).get("box_body")
    logical_blank = (getattr(self, "assembly_part_blank_vars", {}) or {}).get("box_body")
    logical_corner = (getattr(self, "assembly_part_corner_vars", {}) or {}).get("box_body")
    if projections:
        if logical_formed is not None: logical_formed.set("成形尺寸：見下方各片")
        if logical_blank is not None: logical_blank.set("展開料：見下方各片")
        if logical_corner is not None: logical_corner.set("截角尺寸：見下方各片")


def _phase6_query_assembly_render_data(self):
    """Compatibility delegate to authoritative T6 assembly projection."""
    return _phase6_final_scene_adapter(self).query_assembly_render_data()

def _phase6_assembly_unfolded_blank_text(render_data, *, snapshot=None):
    rows = []
    for part in tuple(getattr(render_data, "assembly_parts", ()) or ()):
        text = _phase6_format_unfolded_blank_text(part.render_data, part_key=part.part_key)
        if text.startswith("展開料："):
            text = text[len("展開料："):]
        rows.append(f"{_phase6_part_label(part.part_key, snapshot=snapshot)}：{text}")
    return "展開尺寸：\n" + "\n".join(rows) if rows else "展開尺寸：-"



def _phase6_final_scene_view_request(self):
    """Compatibility delegate for final-scene request construction."""
    return _phase6_final_scene_adapter(self).build_request()


def _phase6_render_true_cutting_mesh(self):
    """Compatibility delegate; deep rendering remains Phase6FinalSceneView-owned."""
    return _phase6_final_scene_adapter(self).render_cutting_mesh()


def _phase6_on_3d_scroll(self, event):
    return _phase6_final_scene_adapter(self).on_scroll(event)


def _phase6_install_renderer_view(self):
    return _phase6_final_scene_adapter(self).install_renderer()

def _phase6_profile_material_total(profile):
    return float(sum(abs(_num(seg.get("len", 0.0))) for seg in (profile or ())))


def _phase6_corner_policy_for(self, part_key):
    raw_state = dict((getattr(self, "_phase6_corner_state", {}) or {}).get(part_key, {}) or {})
    if not all(key in raw_state for key in _CORNER_KEYS):
        return None
    selections = {key: _phase6_selection_from_raw(raw_state[key]) for key in _CORNER_KEYS}
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    snapshot["endcap_fw"] = deepcopy(getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(snapshot)))
    fw = resolve_endcap_fw(snapshot, part_key) if str(part_key) in ENDCAP_FW_PARTS else _num(snapshot.get("fw", 25), 25)

    # 受電箱下方的等價 FW 不是封頭/尾名義 FW，而是「側板後折 + 1T」。
    # 保留目前四角 selection（使用者仍可調截角方式/T 倍數），只把 family
    # geometry Source of Truth 注入 bottom_fw，讓 2D/3D/輸出共用同一 policy。
    try:
        if cabinet_family_policy.supports_bottom_wrap_controls(snapshot) and str(part_key) in ENDCAP_FW_PARTS:
            thickness = _num(snapshot.get("t", 2.0), 2.0)
            return FourCornerTypePolicy(
                bottom_left=selections["bottom_left"],
                bottom_right=selections["bottom_right"],
                top_left=selections["top_left"],
                top_right=selections["top_right"],
                fw=float(fw),
                bottom_fw=cabinet_family_policy.effective_endcap_bottom_fw(
                    snapshot,
                    snapshot.get("box_body_structure"),
                    thickness=thickness,
                    default_fw=float(fw),
                ),
            )
    except Exception:
        # 非受電箱與舊 snapshot 仍沿用既有通用 policy；真正的幾何錯誤會在
        # downstream manufacturing resolver fail closed，不在 UI adapter 猜值。
        pass
    return policy_from_corner_state(selections, fw=fw)


def _phase6_draw_operator_dimensions(self, x_profile, y_profile, *, triangles=None):
    """Legacy adapter to the FinalSceneView dimension drawing implementation."""
    view = getattr(self, "final_scene_view", None)
    if view is None:
        view = Phase6FinalSceneView(self.renderer, number_text=_setting_number_text)
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    settings = getattr(self, "_settings_values", {}) or {}
    request = FinalSceneViewRequest(
        render_data=None,
        x_profile=tuple(dict(seg) for seg in (x_profile or ())),
        y_profile=tuple(dict(seg) for seg in (y_profile or ())),
        part_key=str(getattr(self, "active_part_key", "") or ""),
        alpha_bend=float(getattr(getattr(self, "state", None), "alpha_bend", 0.85)),
        finished_dimensions=_phase6_operator_finished_dimensions(self),
        thickness=_num(settings.get("t", snapshot.get("t", 2.0)), 2.0),
    )
    return view._draw_operator_dimensions(request, list(triangles or ()))


def _phase6_render_data_for_blank(self, part_key=None):
    """Return canonical final material for blank reporting without a second geometry path."""
    key = str(part_key or self.designer_workspace.active_part or "")
    if not key:
        return None
    active = str(getattr(getattr(self, "designer_workspace", None), "active_part", "") or "")
    if key == active:
        return _phase6_query_final_render_data(self)
    if key in {"box_body", "head", "tail"}:
        return _phase6_resolve_manufacturing_geometry(self).part(key).render_data
    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        return None
    return callback(key, _phase6_scene_query_payload_for_part(self, key))


def _phase6_format_formed_size_text(
    render_data,
    *,
    part_key: str = "",
    x_profile=(),
    y_profile=(),
    thickness: float = 0.0,
    finished_dimensions=(),
) -> str:
    """Format already-authoritative formed dimensions; never reconstruct geometry."""
    dimensions = tuple(finished_dimensions or ())
    if not dimensions:
        dimensions = tuple(
            getattr(render_data, "formed_outer_dimensions", ()) or ()
        )
    return Phase6CornerDataViewAdapter.formed_size_text(
        dimensions,
        number_text=_setting_number_text,
    )

def _phase6_format_unfolded_blank_text(render_data, *, part_key=""):
    from ae_engine.manufacturing_api import measure_unfolded_blanks

    return Phase6CornerDataViewAdapter.unfolded_blank_text(
        render_data,
        part_key=part_key,
        measurer=measure_unfolded_blanks,
        number_text=_setting_number_text,
    )

def _phase6_current_unfolded_size(self, part_key=None):
    """Compatibility tuple measured only from canonical final material."""
    from ae_engine.manufacturing_api import measure_unfolded_blanks

    key = str(part_key or self.designer_workspace.active_part or "")
    render_data = _phase6_render_data_for_blank(self, key)
    return _phase6_corner_data_view(self).current_unfolded_size(
        render_data,
        part_key=key,
        measurer=measure_unfolded_blanks,
    )

def _phase6_update_unfolded_size_label(self):
    var = getattr(self, "unfolded_size_var", None)
    if var is None:
        return
    key = str(getattr(getattr(self, "designer_workspace", None), "active_part", "") or "")
    try:
        if getattr(self, "_phase6_initializing", False):
            # The authoritative startup render already attempted the canonical
            # manufacturing resolve. Annotation must consume that committed
            # result if available; it must not start a second startup solve.
            resolved = getattr(self, "_phase6_last_resolved_manufacturing_geometry", None)
            render_data = resolved.part(key).render_data if (resolved is not None and key) else None
        else:
            render_data = _phase6_render_data_for_blank(self, key) if key else None
    except Exception:
        render_data = None
    var.set(_phase6_format_unfolded_blank_text(render_data, part_key=key))


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

def _phase6_refresh_joint_diagnostic_menu(self, resolved=None):
    var = getattr(self, "assembly_joint_diag_var", None)
    button = getattr(self, "assembly_joint_diag_button", None)
    if var is None or button is None:
        return ()
    resolved = (
        resolved
        or getattr(self, "_phase6_last_resolved_manufacturing_geometry", None)
    )
    menu = getattr(self, "assembly_joint_diag_menu", None)
    if menu is None:
        menu_name = str(button.cget("menu") or "")
        if not menu_name:
            return ()
        try:
            menu = button.nametowidget(menu_name)
        except Exception:
            return ()
    menu.delete(0, "end")
    ids = list(_phase6_registry_diagnostics(self).diagnostic_ids(resolved))
    current = str(var.get() or "")
    if current not in ids:
        current = ids[0] if ids else ""
        var.set(current)
    labels = {
        joint_id: f"接合 {index + 1}"
        for index, joint_id in enumerate(ids)
    }
    for joint_id in ids:
        menu.add_radiobutton(
            label=labels[joint_id],
            value=joint_id,
            variable=var,
            command=lambda: _phase6_on_assembly_diagnostic_changed(self),
        )
    button.configure(text=labels.get(current, "接合"))
    return tuple(ids)

def _phase6_selected_joint_diagnostic(self):
    resolved = getattr(
        self, "_phase6_last_resolved_manufacturing_geometry", None
    )
    joint_id = str(
        getattr(
            getattr(self, "assembly_joint_diag_var", None),
            "get",
            lambda: "",
        )()
        or ""
    )
    return _phase6_registry_diagnostics(self).selected_diagnostic(
        resolved, joint_id
    )

def _phase6_build_assembly_diagnostics(self):
    frame = original.ttk.LabelFrame(self.right, text="組合體診斷", padding=6)
    self.assembly_diagnostics_frame = frame
    self.assembly_ignore_fixed_corner_var = original.tk.BooleanVar(value=True)
    self.assembly_show_interference_var = original.tk.BooleanVar(value=True)
    self.assembly_relief_clearance_var = original.tk.StringVar(value="0")
    self.assembly_relief_size_var = original.tk.StringVar(value="實際截角尺寸：等待計算")
    self.assembly_collision_status_var = original.tk.StringVar(value="3D驗證：等待計算")
    original.ttk.Checkbutton(
        frame, text="未知組合允許3D求截角",
        variable=self.assembly_ignore_fixed_corner_var,
        command=lambda: _phase6_on_assembly_diagnostic_changed(self),
    ).pack(side=original.tk.LEFT, padx=(0, 10))
    original.ttk.Label(frame, text="淨空 A").pack(side=original.tk.LEFT, padx=(0, 4))
    self.assembly_relief_clearance_entry = original.ttk.Entry(
        frame, textvariable=self.assembly_relief_clearance_var, width=7
    )
    self.assembly_relief_clearance_entry.pack(side=original.tk.LEFT, padx=(0, 10))
    self.assembly_relief_clearance_entry.bind(
        "<Return>", lambda _event: _phase6_on_assembly_diagnostic_changed(self)
    )
    self.assembly_relief_clearance_entry.bind(
        "<FocusOut>", lambda _event: _phase6_on_assembly_diagnostic_changed(self)
    )
    original.ttk.Checkbutton(
        frame, text="顯示干涉碰撞區",
        variable=self.assembly_show_interference_var,
        command=lambda: _phase6_on_assembly_diagnostic_changed(self),
    ).pack(side=original.tk.LEFT, padx=(0, 10))
    self.assembly_relief_promotion_button = original.ttk.Button(
        frame, text="建立認證候選",
        command=lambda: _phase6_create_relief_promotion_candidates(self),
    )
    self.assembly_relief_promotion_button.pack(side=original.tk.LEFT, padx=(0, 10))
    original.ttk.Label(frame, textvariable=self.assembly_relief_size_var).pack(side=original.tk.LEFT, padx=(0, 10))
    original.ttk.Label(frame, textvariable=self.assembly_collision_status_var).pack(side=original.tk.LEFT)
    frame.pack_forget()
    return frame


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


def _phase6_toggle_parameter_panel(self):
    self._phase6_parameters_unlocked = not bool(getattr(self, "_phase6_parameters_unlocked", False))
    unlocked = self._phase6_parameters_unlocked
    button = getattr(self, "parameter_lock_button", None)
    if button is not None:
        button.configure(text=("參數解鎖" if unlocked else "參數鎖定"))

    center = getattr(self, "settings_center", None)
    active = str(getattr(self, "active_part_key", None) or "box_body")
    assembly_selected = str(getattr(self, "_phase6_3d_display_mode", "single") or "single") == "assembly"
    diagnostics = getattr(self, "assembly_diagnostics_frame", None)
    if unlocked and assembly_selected:
        if center is not None and center.winfo_manager():
            center.pack_forget()
        if diagnostics is not None and not diagnostics.winfo_manager():
            _phase6_pack_right_panel_above_canvas(self, diagnostics)
        _phase6_update_assembly_diagnostic_status(self)
    elif unlocked:
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
        _phase6_invalidate_settings_page(self, active)
        _phase6_render_settings_context(self, active)
        if center is not None and not center.winfo_manager():
            _phase6_pack_right_panel_above_canvas(self, center)
    else:
        if center is not None and center.winfo_manager():
            center.pack_forget()
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
    return unlocked


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


def _phase6_scroll_assembly_parts(self, event):
    canvas = getattr(self, "assembly_parts_canvas", None)
    if canvas is None:
        return "break"
    def _event_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    delta = _event_int(getattr(event, "delta", 0))
    number = _event_int(getattr(event, "num", 0))
    if number == 4:
        steps = -1
    elif number == 5:
        steps = 1
    elif delta:
        steps = -1 if delta > 0 else 1
    else:
        return "break"
    try:
        canvas.yview_scroll(steps, "units")
    except Exception:
        pass
    return "break"


def _phase6_bind_assembly_scroll(widget, self):
    try:
        widget.bind("<MouseWheel>", lambda e: _phase6_scroll_assembly_parts(self, e))
        widget.bind("<Button-4>", lambda e: _phase6_scroll_assembly_parts(self, e))
        widget.bind("<Button-5>", lambda e: _phase6_scroll_assembly_parts(self, e))
    except Exception:
        pass
    for child in tuple(getattr(widget, "winfo_children", lambda: ())()):
        _phase6_bind_assembly_scroll(child, self)


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


def _phase6_set_assembly_part_details_open(self, key, is_open):
    """Show/hide one assembly row's read-only data without changing visibility."""
    key = str(key)
    details = dict(getattr(self, "assembly_part_detail_frames", {}) or {}).get(key)
    button = dict(getattr(self, "assembly_part_detail_buttons", {}) or {}).get(key)
    if details is None:
        return False
    is_open = bool(is_open)
    if is_open:
        if not details.winfo_manager():
            details.pack(fill=original.tk.X)
    else:
        if details.winfo_manager():
            details.pack_forget()
    if button is not None:
        try:
            button.configure(text=("▾" if is_open else "▸"))
        except Exception:
            pass
    stash = dict(getattr(self, "_phase6_assembly_part_detail_open_stash", {}) or {})
    stash[key] = is_open
    self._phase6_assembly_part_detail_open_stash = stash
    canvas = getattr(self, "assembly_parts_canvas", None)
    if canvas is not None:
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass
    return is_open


def _phase6_toggle_assembly_part_details(self, key):
    key = str(key)
    details = dict(getattr(self, "assembly_part_detail_frames", {}) or {}).get(key)
    if details is None:
        return False
    return _phase6_set_assembly_part_details_open(
        self, key, not bool(details.winfo_manager())
    )


def _phase6_set_box_body_piece_details_open(self, key, is_open):
    """Show/hide one BoxBody physical-piece data block only."""
    key = str(key)
    details = dict(
        getattr(self, "assembly_box_body_piece_detail_frames", {}) or {}
    ).get(key)
    button = dict(
        getattr(self, "assembly_box_body_piece_detail_buttons", {}) or {}
    ).get(key)
    if details is None:
        return False
    is_open = bool(is_open)
    if is_open:
        if not details.winfo_manager():
            details.pack(fill=original.tk.X)
    else:
        if details.winfo_manager():
            details.pack_forget()
    if button is not None:
        try:
            button.configure(text=("▾" if is_open else "▸"))
        except Exception:
            pass
    stash = dict(
        getattr(self, "_phase6_box_body_piece_detail_open_stash", {}) or {}
    )
    stash[key] = is_open
    self._phase6_box_body_piece_detail_open_stash = stash
    canvas = getattr(self, "assembly_parts_canvas", None)
    if canvas is not None:
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass
    return is_open


def _phase6_toggle_box_body_piece_details(self, key):
    key = str(key)
    details = dict(
        getattr(self, "assembly_box_body_piece_detail_frames", {}) or {}
    ).get(key)
    if details is None:
        return False
    return _phase6_set_box_body_piece_details_open(
        self, key, not bool(details.winfo_manager())
    )


def _phase6_refresh_assembly_parts_panel(self):
    panel = getattr(self, "assembly_parts_content", None) or getattr(self, "assembly_parts_panel", None)
    if panel is None:
        return
    old_visible = {
        key: bool(var.get()) for key, var in dict(getattr(self, "assembly_part_visible_vars", {}) or {}).items()
    }
    old_text = {
        key: str(var.get()) for key, var in dict(getattr(self, "assembly_part_corner_vars", {}) or {}).items()
    }
    old_formed = {
        key: str(var.get()) for key, var in dict(getattr(self, "assembly_part_formed_vars", {}) or {}).items()
    }
    old_blank = {
        key: str(var.get()) for key, var in dict(getattr(self, "assembly_part_blank_vars", {}) or {}).items()
    }
    old_open = dict(getattr(self, "_phase6_assembly_part_detail_open_stash", {}) or {})
    old_open.update({
        key: bool(frame.winfo_manager())
        for key, frame in dict(getattr(self, "assembly_part_detail_frames", {}) or {}).items()
    })
    self._phase6_assembly_part_detail_open_stash = old_open
    old_piece_visible = {
        key: bool(var.get())
        for key, var in dict(getattr(self, "assembly_box_body_piece_visible_vars", {}) or {}).items()
    }
    old_piece_visible = {
        **dict(getattr(self, "_phase6_box_body_piece_visibility_stash", {}) or {}),
        **old_piece_visible,
    }
    self._phase6_box_body_piece_visibility_stash = old_piece_visible
    for child in panel.winfo_children():
        child.destroy()
    self.assembly_part_visible_vars = {}
    self.assembly_part_corner_vars = {}
    self.assembly_part_formed_vars = {}
    self.assembly_part_blank_vars = {}
    self.assembly_part_checkbuttons = {}
    self.assembly_part_detail_frames = {}
    self.assembly_part_detail_buttons = {}
    self.assembly_box_body_piece_host = None
    self.assembly_box_body_piece_labels = {}
    self.assembly_box_body_piece_sections = {}
    self.assembly_box_body_piece_visible_vars = {}
    self.assembly_box_body_piece_checkbuttons = {}
    self.assembly_box_body_piece_detail_frames = {}
    self.assembly_box_body_piece_detail_buttons = {}
    self.assembly_box_body_piece_formed_vars = {}
    self.assembly_box_body_piece_blank_vars = {}
    self.assembly_box_body_piece_corner_vars = {}
    for key in _phase6_operator_part_selector_keys(self.designer_workspace.available_parts):
        row = original.ttk.Frame(panel)
        row.pack(fill=original.tk.X, pady=(0, 4))
        visible = original.tk.BooleanVar(value=old_visible.get(key, True))
        size_text = original.tk.StringVar(value=old_text.get(key, "截角尺寸：等待3D"))
        formed_text = original.tk.StringVar(value=old_formed.get(key, "成形尺寸：等待3D"))
        blank_text = original.tk.StringVar(value=old_blank.get(key, "展開料：等待3D"))
        header = original.ttk.Frame(row)
        header.pack(fill=original.tk.X)
        check = original.ttk.Checkbutton(
            header, text=_phase6_part_label(key, snapshot=getattr(self, "_phase6_input_snapshot", {})), variable=visible,
            command=lambda: _phase6_on_assembly_part_visibility_changed(self),
        )
        check.pack(side=original.tk.LEFT, anchor=original.tk.W, fill=original.tk.X, expand=True)
        details = original.ttk.Frame(row)
        details_open = old_open.get(key, True)
        detail_button = original.ttk.Button(
            header,
            text=("▾" if details_open else "▸"),
            width=2,
            command=lambda k=key: _phase6_toggle_assembly_part_details(self, k),
            takefocus=True,
        )
        detail_button.pack(side=original.tk.RIGHT)
        original.ttk.Label(
            details, textvariable=formed_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        original.ttk.Label(
            details, textvariable=blank_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        original.ttk.Label(
            details, textvariable=size_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        if key == "box_body":
            self.assembly_box_body_piece_host = original.ttk.Frame(details)
            self.assembly_box_body_piece_host.pack(fill=original.tk.X)
        if details_open:
            details.pack(fill=original.tk.X)
        self.assembly_part_visible_vars[key] = visible
        self.assembly_part_corner_vars[key] = size_text
        self.assembly_part_formed_vars[key] = formed_text
        self.assembly_part_blank_vars[key] = blank_text
        self.assembly_part_checkbuttons[key] = check
        self.assembly_part_detail_frames[key] = details
        self.assembly_part_detail_buttons[key] = detail_button
        _phase6_bind_assembly_scroll(row, self)
    _phase6_bind_assembly_scroll(panel, self)
    canvas = getattr(self, "assembly_parts_canvas", None)
    if canvas is not None:
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass


# Patch methods onto the FIX10 class instead of touching the user's original file.
_FIX10_INIT = Phase6FoldDesignerApp.__init__
_FIX10_EXPORT = Phase6FoldDesignerApp.export_phase6_snapshot


def _fix11_init(self, root, snapshot: Mapping[str, object], on_settings_change=None, on_save_defaults=None, on_corner_change=None, on_transaction_confirm=None, on_transaction_cancel=None, on_live_sync=None, on_baseline_data_query=None, on_scene_query=None, on_part_spec_query=None, on_ui_text_size_change=None, on_project_load=None, on_project_path_change=None, on_project_save=None, output_draw_stock_var=None, output_export_vars=None, on_export_selected_dxf=None):
    # Atomic lifecycle: inherited Tk construction may invoke traced callbacks and
    # legacy do_update() methods, but none of those bootstrap intermediates are
    # authoritative live-sync state. Publish is disabled until the final Phase6
    # workspace has ingested the current application snapshot and reached READY.
    self._phase6_initializing = True
    # Phase 4 composition services may be reached by inherited Tk callbacks
    # during construction. Establish the authoritative mapping identities before
    # any such callback can ask the composition root for Settings owners. From
    # here onward these mappings are mutated in place; they are never rebound.
    self._settings_values = {}
    self._phase6_input_snapshot = {}
    self._phase6_box_whd = {}
    self._phase6_pending_settings = {}
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
    _FIX10_INIT(self, root, snapshot)
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

    # One CAD-style Structure Tree is now the visible part/mode navigator. Its
    # rows are rebuilt from designer_workspace.available_parts and own no state.
    # #186: reserve the Tree's normal flow slot, but render that same single
    # Structure Tree as a sticky navigation surface.  Only lower inputs scroll.
    self.structure_tree_spacer = original.ttk.Frame(self.left, height=1)
    self.structure_tree_spacer.pack(fill=original.tk.X, pady=(0, 6))
    self.structure_tree_spacer.pack_propagate(False)
    self.structure_tree_host = original.ttk.Frame(self.left)
    self.structure_tree_host.place(x=0, y=0, relwidth=1.0)
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
    self.structure_tree_spacer.configure(
        height=max(1, int(self.structure_tree_host.winfo_reqheight()))
    )
    self.root.after_idle(lambda: _phase6_refresh_sticky_structure_tree(self))
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

    # 組合體內容直接使用左側剩餘空間；不再用帶標題/框線的 LabelFrame
    # 切出一塊獨立「組合圖」區域。
    self.assembly_parts_panel = original.ttk.Frame(self.left, padding=6)
    assembly_scroll_host = original.ttk.Frame(self.assembly_parts_panel)
    assembly_scroll_host.pack(fill=original.tk.BOTH, expand=True)
    self.assembly_parts_canvas = original.tk.Canvas(
        assembly_scroll_host, height=1, highlightthickness=0, borderwidth=0, takefocus=False
    )
    self.assembly_parts_scrollbar = original.ttk.Scrollbar(
        assembly_scroll_host, orient=original.tk.VERTICAL, command=self.assembly_parts_canvas.yview
    )
    self.assembly_parts_canvas.configure(yscrollcommand=self.assembly_parts_scrollbar.set)
    self.assembly_parts_scrollbar.pack(side=original.tk.RIGHT, fill=original.tk.Y)
    self.assembly_parts_canvas.pack(side=original.tk.LEFT, fill=original.tk.BOTH, expand=True)
    self.assembly_parts_content = original.ttk.Frame(self.assembly_parts_canvas)
    self._assembly_parts_window = self.assembly_parts_canvas.create_window(
        (0, 0), window=self.assembly_parts_content, anchor="nw"
    )
    self.assembly_parts_content.bind(
        "<Configure>",
        lambda _e: self.assembly_parts_canvas.configure(scrollregion=self.assembly_parts_canvas.bbox("all")),
    )
    self.assembly_parts_canvas.bind(
        "<Configure>",
        lambda e: self.assembly_parts_canvas.itemconfigure(self._assembly_parts_window, width=max(1, e.width)),
    )
    _phase6_bind_assembly_scroll(self.assembly_parts_canvas, self)
    _phase6_bind_assembly_scroll(self.assembly_parts_content, self)
    self.assembly_part_visible_vars = {}
    self.assembly_part_corner_vars = {}
    self.assembly_part_formed_vars = {}
    self.assembly_part_blank_vars = {}
    self.assembly_part_checkbuttons = {}
    self.assembly_box_body_piece_visible_vars = {}
    self.assembly_box_body_piece_checkbuttons = {}
    _phase6_refresh_assembly_parts_panel(self)

    self._refresh_part_buttons()
    self._refresh_add_part_menu()
    try:
        self.root.bind("<Delete>", lambda _e: self.remove_selected_part())
    except Exception:
        pass

    # 左側輸入區永久存在；右側只有參數面板受鎖定控制。
    self.fold_editor_host = original.ttk.Frame(self.left)
    self.bend_ui = Phase6BendingUI(self.fold_editor_host, self.state, self.queue_update)
    self.fold_editor_host.pack(fill=original.tk.BOTH, expand=True, pady=(0, 10))
    _phase6_build_settings_center(self)
    _phase6_install_renderer_view(self)
    self.settings_center.pack_forget()
    self.activate_part("box_body", initial=True)
    _phase6_show_assembly(self, initial=True)
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


def _phase6_show_input_content(self):
    """Return to the editor for the workspace's existing authoritative active part."""
    _phase6_clear_navigation_residue(self)
    workspace = _designer_workspace(self)
    available = tuple(getattr(workspace, "available_parts", ()) or ())
    key = str(getattr(workspace, "active_part", "") or "")
    if key not in available:
        key = "box_body" if "box_body" in available else (available[0] if available else "")
    if not key:
        return None
    result = self.activate_part(key)
    _phase6_refresh_content_switch(self)
    return result


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


def _phase6_structure_tree_visibility_var(self, key):
    """Return the existing assembly view-state owner for one physical identity."""
    key = str(key or "")
    if _phase6_is_box_body_physical_piece_key(key):
        return dict(getattr(self, "assembly_box_body_piece_visible_vars", {}) or {}).get(key)
    return dict(getattr(self, "assembly_part_visible_vars", {}) or {}).get(key)


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
    """Delegate hide/show to the existing drawing-sink visibility state only."""
    key = str(key or "")
    visible_var = _phase6_structure_tree_visibility_var(self, key)
    if visible_var is None:
        return False
    visible_var.set(bool(visible))
    _phase6_on_assembly_part_visibility_changed(self)
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

    fold_host = getattr(self, "fold_editor_host", None)
    if fold_host is not None and hasattr(fold_host, "pack_forget"):
        fold_host.pack_forget()

    assembly_panel = getattr(self, "assembly_parts_panel", None)
    if assembly_panel is not None and hasattr(assembly_panel, "pack_forget"):
        assembly_panel.pack_forget()

    panel = getattr(self, "corner_data_panel", None)
    if panel is None and getattr(self, "left", None) is not None:
        panel = original.ttk.Frame(self.left, padding=6)
        self.corner_data_panel = panel
    if panel is not None and hasattr(panel, "pack"):
        panel.pack(fill=original.tk.BOTH, expand=True, pady=(0, 8))

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
    if getattr(self, "fold_editor_host", None) is not None and self.fold_editor_host.winfo_manager():
        self.fold_editor_host.pack_forget()
    corner_data_panel = getattr(self, "corner_data_panel", None)
    if corner_data_panel is not None and hasattr(corner_data_panel, "pack_forget"):
        corner_data_panel.pack_forget()
    assembly_panel = getattr(self, "assembly_parts_panel", None)
    if assembly_panel is not None and not assembly_panel.winfo_manager():
        assembly_panel.pack(fill=original.tk.BOTH, expand=True, pady=(0, 8))
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


def _fix11_activate_selected_part(self):
    key = getattr(self, "selected_part_key", None)
    if key not in self.available_parts:
        return False
    _phase6_activate_operator_part(self, key)
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
    """Accept authoritative X/Y/FoldChain edits into the shared settings state.

    Part switching calls this to persist the outgoing editor.  Do not wake the
    main GUI when the persisted values are unchanged, and when something did
    change send only those keys.  The main GUI callback accepts partial setting
    payloads; sending the whole settings dictionary forced a full AE/main-preview
    recalculation on every part switch even when the operator changed nothing.
    """
    clean = dict(values or {})
    if not clean:
        return

    changed_settings = {}
    for key, value in list(clean.items()):
        if key not in self._settings_values:
            continue
        old = self._settings_values[key]
        if key == "ui_text_size":
            normalized = normalize_ui_text_size(value)
        elif isinstance(old, bool):
            normalized = bool(value)
        else:
            normalized = float(value)
        # Keep the snapshot/settings transaction on the same normalized value.
        # Family snapshots include string-valued ui_text_size alongside numeric
        # W/H/D; treating every non-bool as float aborted receiving rebases.
        clean[key] = normalized
        if key == "ui_text_size":
            different = normalize_ui_text_size(old) != normalized
        elif isinstance(old, bool):
            different = bool(old) != normalized
        else:
            try:
                different = abs(float(old) - float(normalized)) > 1e-9
            except (TypeError, ValueError):
                different = old != normalized
        if different:
            changed_settings[key] = normalized

    # A real box-FW edit is an explicit operator takeover.  Do this before
    # rebuilding linked EndCaps so Head/Tail resolve from the same state.
    if "fw" in changed_settings:
        commit_box_fw(self._phase6_endcap_fw_state, float(changed_settings["fw"]))
        self._phase6_input_snapshot["endcap_fw"] = deepcopy(self._phase6_endcap_fw_state)

    self._phase6_input_snapshot.update(clean)
    for key, value in clean.items():
        if key not in self._settings_values:
            continue
        if key == "ui_text_size":
            self._settings_values[key] = normalize_ui_text_size(value)
        elif isinstance(self._settings_values[key], bool):
            self._settings_values[key] = bool(value)
        else:
            self._settings_values[key] = float(value)
    for key in ("w", "h", "d"):
        if key in clean:
            self._phase6_box_whd[key] = original.get_int(clean[key])
    if hasattr(self, "left_global_vars"):
        self._phase6_settings_guard = True
        try:
            for key in ("w", "h", "d", "t", "fw"):
                if key not in clean or key not in self.left_global_vars:
                    continue
                text = _setting_number_text(clean[key])
                if self.left_global_vars[key].get() != text:
                    self.left_global_vars[key].set(text)
        finally:
            self._phase6_settings_guard = False
    _phase6_recalculate_part_dimensions(self)
    if {"w", "h", "d", "t", "fw"}.intersection(changed_settings):
        _phase6_refresh_linked_part_profiles(self, set(changed_settings))
    if (
        notify
        and changed_settings
        and not getattr(self, "_phase6_applying_settings", False)
        and not getattr(self, "_phase6_transactional_mode", False)
        and self._settings_change_callback is not None
    ):
        self._settings_change_callback(changed_settings)


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
    corner_data_panel = getattr(self, "corner_data_panel", None)
    if corner_data_panel is not None and corner_data_panel.winfo_manager():
        corner_data_panel.pack_forget()
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

    assembly_panel = getattr(self, "assembly_parts_panel", None)
    if assembly_panel is not None and assembly_panel.winfo_manager():
        assembly_panel.pack_forget()
    if getattr(self, "fold_editor_host", None) is not None and not self.fold_editor_host.winfo_manager():
        self.fold_editor_host.pack(fill=original.tk.BOTH, expand=True, pady=(0, 10))
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
_PHASE6_ORCHESTRATION_DEBOUNCE_MS = 75

def _phase6_publish_if_changed(self):
    return _phase6_publish_live_state(self)


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


def _phase6_flush_update_intents(self):
    return flush_fold_designer_update_intents(
        self,
        executor=lambda reasons: _phase6_execute_update_intents(self, reasons),
    )


def _phase6_submit_update_intent(self, reason, *, commit=False):
    return submit_fold_designer_update_intent(
        self,
        reason,
        commit=commit,
        executor=lambda reasons: _phase6_execute_update_intents(self, reasons),
    )


def _phase6_apply_settings_delta(self, delta, transaction_id):
    return apply_fold_designer_settings_delta(
        delta,
        transaction_id,
        transactions=_phase6_settings_service(self),
        apply_updates=lambda updates: _phase6_apply_setting_updates(
            self, updates, notify=True
        ),
    )

def _phase6_switch_active_part(self, part_key, *, commit=True):
    # ``activate_part`` owns the legacy editor wiring; its final action now
    # classifies geometry-vs-display and submits exactly one orchestration intent.
    return self.activate_part(str(part_key), initial=False)

def _phase6_preview_aware_do_update(self):
    """Legacy compatibility wrapper: submit intent, never execute update/render."""
    return self.submit_update_intent("geometry", commit=True)


def _phase6_set_3d_preview_enabled(self, enabled):
    return _phase6_final_scene_adapter(self).set_preview_enabled(enabled)


def _phase6_refresh_3d_preview(self):
    return _phase6_final_scene_adapter(self).refresh_preview()


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
        "_phase6_cutting_mesh_error": _phase6_view_property("cutting_mesh_error", None),
        "_phase6_zoom_scale": _phase6_view_property("zoom_scale", 1.0),
        "_phase6_view_initialized": _phase6_view_property("view_initialized", False),
        "_phase6_base_renderer_render": _phase6_view_property("base_renderer_render", None),
        "_phase6_scroll_cid": _phase6_view_property("scroll_cid", None),
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
        "activate_selected_part": _fix11_activate_selected_part,
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
        "show_global_settings": _phase6_show_global_settings,
        "toggle_baseline_data": _phase6_settings_panel_toggle_baseline,
        "save_settings_context_as_defaults": _phase6_save_settings_context_as_defaults,
        "save_current_settings_as_defaults": _phase6_save_current_settings_as_defaults,
        "flush_pending_settings": _phase6_flush_pending_settings,
        "_phase6_publish_live_state": _phase6_publish_live_state,
        "_phase6_resolve_manufacturing_geometry": _phase6_resolve_manufacturing_geometry,
        "toggle_advanced_settings": _phase6_settings_panel_toggle_advanced,
        "apply_external_settings": _phase6_apply_external_settings,
        "apply_external_model": _phase6_apply_external_model,
        "apply_external_sync": _phase6_apply_external_sync,
        "_phase6_refresh_corner_data_unfold_view": _phase6_refresh_corner_data_unfold_view,
        "on_ui_text_size_changed": _phase6_on_ui_text_size_changed,
        "apply_external_corner_state": _phase6_apply_external_corner_state,
        "_phase6_corner_parameters_unlocked": _phase6_corner_parameters_unlocked,
        "toggle_corner_parameter_lock": _phase6_toggle_corner_parameter_lock,
        "_render_settings_context": _phase6_render_settings_context,
        "on_baseline_model_changed": _phase6_on_baseline_model_changed,
        "confirm_corner_transaction": _phase6_confirm_corner_transaction,
        "cancel_corner_transaction": _phase6_cancel_corner_transaction,
        "reset_initial_values": _phase6_reset_initial_values,
        "export_workspace_state_if_dirty": _phase6_export_workspace_state_if_dirty,
        "save_diagnostic_file": _phase6_save_diagnostic_file,
        "save_project_file": _phase6_save_project_file,
        "save_project_file_as": _phase6_save_project_file_as,
        "load_project_file": _phase6_load_project_file,
        "_phase6_on_endcap_edge_relation_selected": _phase6_on_endcap_edge_relation_selected,
        "_phase6_render_endcap_edge_controls": _phase6_render_endcap_edge_controls,
        "_phase6_commit_base_plate_edge_shrink": _phase6_commit_base_plate_edge_shrink,
        "submit_update_intent": _phase6_submit_update_intent,
        "apply_settings_delta": _phase6_apply_settings_delta,
        "switch_active_part": _phase6_switch_active_part,
        "publish_if_changed": _phase6_publish_if_changed,
        "_phase6_flush_update_intents": _phase6_flush_update_intents,
        "set_3d_preview_enabled": _phase6_set_3d_preview_enabled,
        "refresh_3d_preview": _phase6_refresh_3d_preview,
    },
)
