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
from typing import Mapping, MutableMapping, Sequence

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.sheetmetal_part_adapters import (
    DoorFrameEdges,
    calculate_door_finished_size,
    derive_door_layout_cells,
    door_layout_part_key,
)
from phase6_designer_workspace import Phase6DesignerWorkspace
from phase6_box_body_structure import (
    BoxBodyStructureType, normalize_box_body_structure_state, set_active_structure,
    activate_structure_with_defaults,
    set_structure_locked, set_two_piece_width, set_three_piece_width,
    reconcile_box_body_structure_for_total_w_change,
    set_join_seam_bend, set_side_back_geometry, update_structure_config,
    resolve_two_piece_widths, resolve_three_piece_widths,
)

from phase6_settings_center import (
    GLOBAL_CONTEXT, settings_for_context, UI_TEXT_SIZE_LABELS,
    normalize_ui_text_size, ui_text_size_label,
)
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

from phase6_final_scene_view import (
    AssemblyScenePart, AssemblySceneRenderData,
    FinalSceneViewRequest, Phase6FinalSceneView,
    _PHASE6_DEFAULT_VIEW, _PHASE6_ZOOM_MIN, _PHASE6_ZOOM_MAX, _PHASE6_ZOOM_STEP,
    _phase6_profile_base_index, _phase6_profile_geometry,
    _phase6_fold_mask_for_cross_coordinate, _phase6_profile_map_with_guides,
    _phase6_profile_map, _phase6_profile_flat_map,
    _phase6_folded_mesh_from_polygon, _phase6_fitted_limits_from_vertices,
    _phase6_scene_fold_boundaries, _phase6_profile_to_scene_boundaries,
    _phase6_fold_ownership_exemptions, _phase6_folded_outside_envelope,
    _phase6_profile_operator_fold_values,
    _phase6_remove_original_bend_surfaces, _phase6_add_mesh_boundary_lines,
    _phase6_draw_scene_bends, _phase6_draw_scene_markings,
    _phase6_configure_3d_only_figure, _phase6_scale_current_3d_limits,
    _phase6_adjust_zoom_scale,
)



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
    gap_w = _num(snapshot.get("door_gap_w", 3.5), 3.5)
    gap_h = _num(snapshot.get("door_gap_h", 3.5), 3.5)
    rows = []
    for cell in derive_door_layout_cells(normalized):
        formed_w, formed_h = calculate_door_finished_size(
            w=cell.start_width,
            h=cell.start_height,
            t=t,
            fw=fw,
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


_PHASE6_ASSEMBLY_PLACEMENTS = {
    "box_body": "box_body",
    "head": "top",
    "tail": "bottom",
    "door": "front",
    "base_plate": "base",
    "indicator_box": "front",
    "indicator_door": "front",
}


def _phase6_door_part_assembly_placement(snapshot, part_key):
    """Return canonical front-plane placement for one formal Door layout cell."""
    key = str(part_key or "")
    columns = tuple(
        (float(row[0]), tuple(float(v) for v in row[1]))
        for row in tuple(dict(snapshot or {}).get("door_layout_columns") or ())
    )
    if not columns:
        raise ValueError(f"門格缺少 authoritative multi-door topology: {key}")
    cells = derive_door_layout_cells(columns)
    cell = next((item for item in cells if door_layout_part_key(item) == key), None)
    if cell is None:
        raise ValueError(f"門格 stable_id 不存在於 authoritative topology: {key}")
    total_w = float(dict(snapshot or {}).get("w", sum(width for width, _ in columns)))
    total_h = float(dict(snapshot or {}).get("h", sum(columns[0][1])))
    x_before = sum(columns[index][0] for index in range(cell.column_index))
    y_before = sum(columns[cell.column_index][1][:cell.row_index])
    center_x = -total_w / 2.0 + x_before + cell.start_width / 2.0
    center_y = total_h / 2.0 - y_before - cell.start_height / 2.0
    return "front", (float(center_x), float(center_y), 0.0)


def _phase6_assembly_placement_for_part(snapshot, part_key):
    key = str(part_key or "")
    family = cabinet_family_policy.canonical_family_name(snapshot)
    receiving_derived = (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or key.startswith("box_body:divider:")
        or key.startswith("inner_door:")
    )
    if family == "受電箱" and receiving_derived:
        # T16: Receiving placement is domain-owned. Never consult a stale
        # workspace origin fallback or recreate Door/front offsets here.
        from ae_engine.assembly_placement import resolve_assembly_placement
        placement = resolve_assembly_placement(snapshot, key)
        return placement.placement_kind, tuple(float(v) for v in placement.world_offset)

    if re.fullmatch(r"door_c\d+_r\d+", key):
        return _phase6_door_part_assembly_placement(snapshot, key)
    if key.startswith("box_body:divider:") or (key.startswith("inner_door:") and key.endswith(":bottom_frame")):
        placements = (
            snapshot.get("assembly_placements")
            or (snapshot.get("workspace") or {}).get("assembly_placements")
            or {}
        )
        if key in placements:
            item = placements[key]
            kind = item.get("placement_kind", "offset")
            offset = tuple(float(v) for v in item.get("world_offset", (0.0, 0.0, 0.0)))
            return kind, offset
        try:
            from ae_engine.assembly_placement import resolve_assembly_placement
            placement = resolve_assembly_placement(snapshot, key)
            return placement.placement_kind, tuple(float(v) for v in placement.world_offset)
        except Exception:
            pass
    return _PHASE6_ASSEMBLY_PLACEMENTS.get(key, "offset"), (0.0, 0.0, 0.0)


def normalize_part_selection(part_keys, active_part=None):
    """Preserve the Phase6 part order and choose a safe initial part.

    An empty model is the only case that invents a part: one box body.
    """
    seen = set()
    parts = []
    for raw in part_keys or ():
        key = str(raw)
        if key in PART_LABELS and key not in seen:
            parts.append(key); seen.add(key)
    if not parts:
        parts = ["box_body"]
    active = str(active_part) if active_part in parts else parts[0]
    return parts, active




def _designer_workspace(self) -> Phase6DesignerWorkspace:
    return self.designer_workspace


def _phase6_sync_authoritative_derived_parts(self):
    """Sync topology-derived physical parts into the persistent workspace.

    Divider geometry is fully determined by authoritative multi-door topology.
    Receiving frame spans are derived by its family policy from Door finished
    geometry plus the confirmed 50 mm left/right/top insets; other families may
    still supply explicit spans to the generic frame capability.
    """
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    workspace = _designer_workspace(self)
    sync_derived_parts = getattr(workspace, "sync_derived_parts", None)
    if not callable(sync_derived_parts):
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
        workspace.remove_part("door")
    sync_derived_parts(namespace="door_c", part_profiles=door_profiles)
    for row in door_rows:
        if row.part_key not in known_feature_keys and row.part_key in source_part_features:
            workspace.stash_features(row.part_key, source_part_features[row.part_key])
    if door_rows:
        if legacy_active:
            workspace.active_part = door_rows[0].part_key
        if legacy_selected:
            workspace.selected_part = door_rows[0].part_key
    else:
        source_parts = tuple(snapshot.get("existing_parts") or ())
        if "door" in source_parts and "door" not in workspace.available_parts:
            workspace.add_part(
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
        workspace.remove_part("base_plate")
    sync_derived_parts(
        namespace="base_plate_c",
        part_profiles=base_plate_profiles,
    )
    if door_rows:
        first_base = str(door_rows[0].part_key).replace("door_", "base_plate_", 1)
        if legacy_base_active:
            workspace.active_part = first_base
        if legacy_base_selected:
            workspace.selected_part = first_base
    else:
        source_parts = tuple(snapshot.get("existing_parts") or ())
        if "base_plate" in source_parts and "base_plate" not in workspace.available_parts:
            workspace.add_part(
                "base_plate",
                default_profiles=build_standard_part_profiles(snapshot, "base_plate"),
            )

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
        )
        divider_profiles = divider_part_profiles(dividers)
    sync_derived_parts(
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
    sync_derived_parts(
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
                length_text = str(original.get_int(engine_segment_length_to_ui(seg)))
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
                seg["len"] = engine_segment_length_to_ui(seg)
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
            length = ui_segment_length_to_engine(conversion, ui_length)
            seg = {"len": length}
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


class Phase6FoldDesignerApp(original.MainApp):
    """Original MainApp loaded with Phase6 data; Renderer is untouched."""

    def __init__(self, root, snapshot: Mapping[str, object]):
        self._phase6_input_snapshot = dict(snapshot)
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
        if hasattr(self, "_phase6_pending_settings"):
            self._phase6_pending_settings = {}

    def _phase6_on_root_destroy(self, event):
        if getattr(event, "widget", None) is not self.root:
            return
        self._phase6_destroying = True
        self._phase6_cancel_owned_tk_jobs()

    def load_phase6_snapshot(self, snapshot: Mapping[str, object]):
        self._phase6_input_snapshot = dict(snapshot)
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
    """Return only Phase6 values that have an authoritative reverse mapping."""
    x = list((profiles or {}).get("X", ()))
    y = list((profiles or {}).get("Y", ()))
    if _phase6_is_door_part_key(part_key):
        return {
            "door_fold_l": _profile_value(x, "door_fold_l", original_snapshot.get("door_fold_l", 20)),
            "door_fold_r": _profile_value(x, "door_fold_r", original_snapshot.get("door_fold_r", 20)),
            "door_fold_b": _profile_value(y, "door_fold_b", original_snapshot.get("door_fold_b", 20)),
            "door_fold_t": _profile_value(y, "door_fold_t", original_snapshot.get("door_fold_t", 20)),
        }
    if _phase6_is_base_plate_part_key(part_key):
        vals = [
            _profile_value(x, "base_bend_l", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(x, "base_bend_r", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_b", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_t", original_snapshot.get("base_plate_bend", 20)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("底板四邊折彎目前由 Phase6 共用一個 bend 值，四邊必須相同")
        return {"base_plate_bend": vals[0]}
    if part_key == "indicator_box":
        vals = [
            _profile_value(x, "ib_fold_l", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(x, "ib_fold_r", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_b", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_t", original_snapshot.get("indicator_box_fold", 49)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈盒四邊折彎必須相同")
        return {"indicator_box_fold": vals[0]}
    if part_key == "indicator_door":
        vals = [
            _profile_value(x, "id_fold_l", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(x, "id_fold_r", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_b", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_t", original_snapshot.get("indicator_door_fold", 19)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈小門四邊折彎必須相同")
        return {"indicator_door_fold": vals[0]}
    return {}


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
        door_w = max(1.0, w - (fw + 2.0 * t) * 2.0 - 2.0 * _num(values.get("door_gap_w", 3.5), 3.5))
        door_h = max(1.0, h - (fw + 2.0 * t) * 2.0 - 2.0 * _num(values.get("door_gap_h", 3.5), 3.5))
        dims["door"] = {"width": door_w, "height": door_h}
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


def _phase6_refresh_profiles_from_settings(self):
    """Push settings-center values into the existing fold profiles losslessly."""
    snapshot = self._phase6_input_snapshot
    snapshot.update(self._settings_values)
    _phase6_recalculate_part_dimensions(self)

    current_box = self.state.profiles_vault.get("箱身", [])
    self.state.profiles_vault["箱身"] = merge_box_body_profile(current_box, snapshot)

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
    clean = {}
    for key, raw in dict(updates or {}).items():
        if key not in self._settings_values:
            continue
        if key == "ui_text_size":
            clean[key] = normalize_ui_text_size(raw)
        elif isinstance(self._settings_values.get(key), bool):
            clean[key] = bool(raw)
        else:
            try:
                clean[key] = float(raw)
            except (TypeError, ValueError):
                continue
    if getattr(self, "_phase6_external_apply_guard", False):
        clean = {key: value for key, value in clean.items() if self._settings_values.get(key) != value}
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
            structure = reconcile_box_body_structure_for_total_w_change(
                self.designer_workspace.box_body_structure_state(), clean["w"]
            )
        except Exception as exc:
            clean.pop("w", None)
            self._settings_values["w"] = previous_w
            self._phase6_input_snapshot["w"] = previous_w
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
            structure = self.designer_workspace.set_box_body_structure_state(structure)
            self._phase6_input_snapshot["box_body_structure"] = deepcopy(structure)

    self._phase6_applying_settings = True
    try:
        try:
            self._save_current_part()
        except Exception:
            pass
    finally:
        self._phase6_applying_settings = False
    self._settings_values.update(clean)
    self._phase6_input_snapshot.update(clean)
    if "t" in clean:
        self.state.phase6_thickness = float(clean["t"])
    if "ui_text_size" in clean:
        key = normalize_ui_text_size(clean["ui_text_size"])
        self._settings_values["ui_text_size"] = key
        self._phase6_input_snapshot["ui_text_size"] = key
        if hasattr(self, "_ui_text_controller"):
            self._ui_text_controller.apply(key)
        self.state.ui_text_scale = getattr(self, "_ui_text_controller", None).factor if hasattr(self, "_ui_text_controller") else 1.0
        var = getattr(self, "ui_text_size_var", None)
        if var is not None and var.get() != ui_text_size_label(key):
            var.set(ui_text_size_label(key))
    self._phase6_box_whd.update({
        key: _ui_len(clean[key]) for key in ("w", "h", "d") if key in clean
    })
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
    job = getattr(self, "_phase6_settings_debounce_job", None)
    if job is not None:
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        self._phase6_settings_debounce_job = None
    pending = dict(getattr(self, "_phase6_pending_settings", {}) or {})
    self._phase6_pending_settings = {}
    if not pending:
        return {}
    return _phase6_apply_setting_updates(self, pending, notify=True)


def _phase6_stage_setting_update(self, key, value):
    # Equivalent values are not writes: no pending job, no revision, no echo.
    if getattr(self, "_phase6_destroying", False):
        return
    if self._settings_values.get(key) == value:
        return
    # State changes immediately; expensive profile rebuild + 3D/main-GUI redraw
    # is coalesced until the operator pauses typing.
    self._settings_values[key] = value
    self._phase6_input_snapshot[key] = value
    self._phase6_pending_settings[key] = value
    job = getattr(self, "_phase6_settings_debounce_job", None)
    if job is not None:
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
    self._phase6_settings_debounce_job = self.root.after(150, self.flush_pending_settings)


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
    state = self._phase6_corner_state.setdefault(str(part_key), {})
    for corner_key in _CORNER_KEYS:
        state[corner_key] = _phase6_selection_to_raw(_phase6_selection_from_raw(state.get(corner_key)))
    pairs = self._phase6_corner_pair_same.setdefault(str(part_key), {})
    pairs.setdefault("top", True); pairs.setdefault("bottom", True)
    return state, pairs


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
    state, pairs = _phase6_ensure_corner_part(self, part_key)
    enabled = bool(var.get())
    pairs[pair_key] = enabled
    if enabled:
        left_key, right_key = _CORNER_PAIR_KEYS[pair_key]
        state[right_key] = dict(state[left_key])
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
    state, pairs = _phase6_ensure_corner_part(self, part_key)
    var = self.corner_type_vars.get(target_key)
    if var is None:
        return
    type_id = _CORNER_TYPE_BY_LABEL.get(str(var.get()).strip())
    if type_id is None:
        return
    current_key = _CORNER_PAIR_KEYS[target_key][0] if target_key in _CORNER_PAIR_KEYS else target_key
    current = _phase6_selection_from_raw(state[current_key])
    selection = current if current.type_id.value == type_id else CornerTypeSelection(CornerTypeId(type_id))
    raw = _phase6_selection_to_raw(selection)
    for corner_key in _phase6_corner_targets(pairs, target_key):
        state[corner_key] = dict(raw)
    _phase6_notify_corner_change(self)
    _phase6_invalidate_settings_page(self, part_key)
    _phase6_render_settings_context(self, part_key)


def _phase6_corner_mode_selected(self, part_key, target_key):
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_parameters_editable(self, part_key):
        return
    state, pairs = _phase6_ensure_corner_part(self, part_key)
    current_key = _CORNER_PAIR_KEYS[target_key][0] if target_key in _CORNER_PAIR_KEYS else target_key
    current = _phase6_selection_from_raw(state[current_key])
    if current.type_id is not CornerTypeId.CROSS:
        return
    var = self.corner_mode_vars.get(target_key)
    mode = _CORNER_MODE_BY_LABEL.get(str(var.get()).strip()) if var is not None else None
    if mode is None:
        return
    selection = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=mode)
    raw = _phase6_selection_to_raw(selection)
    for corner_key in _phase6_corner_targets(pairs, target_key):
        state[corner_key] = dict(raw)
    _phase6_notify_corner_change(self)
    _phase6_invalidate_settings_page(self, part_key)
    _phase6_render_settings_context(self, part_key)


def _phase6_corner_target_var_changed(self, part_key, target_key):
    """Commit semantic parameter widgets without exposing legacy X/Y rotation."""
    if getattr(self, "_phase6_corner_guard", False) or getattr(self, "_phase6_settings_rendering", False):
        return
    if not _phase6_corner_parameters_editable(self, part_key):
        return
    state, pairs = _phase6_ensure_corner_part(self, part_key)
    current_key = _CORNER_PAIR_KEYS[target_key][0] if target_key in _CORNER_PAIR_KEYS else target_key
    current = _phase6_selection_from_raw(state[current_key])
    try:
        amount_var = self.corner_amount_vars.get(target_key)
        amount = float(amount_var.get()) if amount_var is not None else current.amount_t
        if current.type_id is CornerTypeId.CROSS:
            mode_var = self.corner_mode_vars.get(target_key)
            mode = _CORNER_MODE_BY_LABEL.get(str(mode_var.get()).strip(), current.cross_mode) if mode_var is not None else current.cross_mode
            if mode is CrossCornerMode.STANDARD:
                selection = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=mode)
            else:
                direction_var = self.corner_direction_vars.get(target_key)
                direction = _CORNER_DIRECTION_BY_LABEL.get(str(direction_var.get()).strip()) if direction_var is not None else current.direction
                selection = CornerTypeSelection(CornerTypeId.CROSS, cross_mode=mode, direction=direction, amount_t=amount)
        elif current.type_id is CornerTypeId.OVERLAY:
            selection = CornerTypeSelection(CornerTypeId.OVERLAY, amount_t=amount)
        elif current.type_id is CornerTypeId.INSERT:
            selection = CornerTypeSelection(CornerTypeId.INSERT, amount_t=amount)
        else:
            retain_var = self.corner_secondary_retain_vars.get(target_key)
            depth_var = self.corner_secondary_depth_vars.get(target_key)
            selection = CornerTypeSelection(
                CornerTypeId.INSERT_OVERLAY,
                amount_t=amount,
                secondary_retain_t=float(retain_var.get()),
                secondary_depth_t=float(depth_var.get()),
            )
    except (TypeError, ValueError, original.tk.TclError):
        return
    raw = _phase6_selection_to_raw(selection)
    for corner_key in _phase6_corner_targets(pairs, target_key):
        state[corner_key] = dict(raw)
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
    if _phase6_is_unknown_baseline(self, old_model):
        self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
        self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)

    editable = _phase6_is_unknown_baseline(self, new_model)
    if not editable and new_model and new_model != old_model:
        fixed = _phase6_known_model_corner_state(self)
        self._phase6_corner_guard = True
        try:
            for part_key, corners in fixed.items():
                state = self._phase6_corner_state.setdefault(part_key, {})
                for corner_key, selection in corners.items():
                    state[corner_key] = _phase6_selection_to_raw(selection)
                pairs = self._phase6_corner_pair_same.setdefault(part_key, {})
                pairs["top"] = True
                pairs["bottom"] = True
        finally:
            self._phase6_corner_guard = False
    if editable and old_model and not _phase6_is_unknown_baseline(self, old_model):
        # 「自訂」不是另一套預設；它從目前已知固定板件的實際截角規則開始。
        fixed = _phase6_known_model_corner_state(self)
        self._phase6_corner_guard = True
        try:
            for part_key, corners in fixed.items():
                state = self._phase6_corner_state.setdefault(part_key, {})
                for corner_key, selection in corners.items():
                    state[corner_key] = _phase6_selection_to_raw(selection)
                pairs = self._phase6_corner_pair_same.setdefault(part_key, {})
                pairs["top"] = True
                pairs["bottom"] = True
            self._corner_transaction_unknown_state = deepcopy(self._phase6_corner_state)
            self._corner_transaction_unknown_pairs = deepcopy(self._phase6_corner_pair_same)
        finally:
            self._phase6_corner_guard = False
    self._corner_editable = editable

    # The baseline/model selector is the one Cabinet Family Source of Truth.
    # Apply the family topology before refreshing the permanent structure row;
    # otherwise switching 金庫型 -> 受電箱 inside the open 3D designer leaves
    # the visible row and workspace on stale integral state.
    old_snapshot_model = str((getattr(self, "_phase6_input_snapshot", {}) or {}).get("model") or old_model or "").strip()
    self._phase6_input_snapshot["model"] = new_model
    try:
        if not editable and new_model and new_model != old_snapshot_model:
            # Every known model switch is a preset transaction.  Use the
            # immutable factory/startup snapshot supplied by Main GUI as the
            # base, then let the selected family overlay its own defaults.
            # ``自訂`` deliberately skips this block and keeps current values.
            runtime_presets = dict(self._phase6_input_snapshot.get("_runtime_family_presets") or {})
            preset_runtime = deepcopy(dict(runtime_presets.get(new_model) or {}))
            preset_base = dict(preset_runtime.get("settings") or {})
            if not preset_base:
                preset_base = dict(self._phase6_input_snapshot.get("factory_defaults") or {})
            if not preset_base:
                preset_base = {
                    key: value for key, value in self._phase6_input_snapshot.items()
                    if key in getattr(self, "_settings_values", {})
                }
            defaults = cabinet_family_policy.apply_fresh_family_defaults(preset_base, new_model)
            self._phase6_input_snapshot.update(defaults)

            # Known-family runtime fields (structure, multi-door topology, etc.)
            # belong to the target preset too.  Restore only explicit captured
            # fields; Receiving then overlays its own fresh-family defaults.
            if preset_runtime:
                runtime_field_map = {
                    "multi_door_enabled": "multi_door_enabled",
                    "door_layout_columns": "door_layout_columns",
                    "door_layout_scope": "door_layout_scope",
                    "door_handle_edges": "door_handle_edges",
                    "receiving_inner_doors": "inner_doors",
                    "door_nameplate_center_datum_top": "door_nameplate_center_datum_top",
                }
                for source_key, target_key in runtime_field_map.items():
                    if source_key in preset_runtime:
                        self._phase6_input_snapshot[target_key] = deepcopy(preset_runtime[source_key])
            family_values = {
                key: value for key, value in defaults.items()
                if key in getattr(self, "_settings_values", {})
            }
            _phase6_store_editor_values(self, family_values, notify=True)
            self.state.w = original.get_int(defaults["w"])
            self.state.h = original.get_int(defaults["h"])
            self.state.d = original.get_int(defaults["d"])
            self.v_w.set(str(self.state.w))
            self.v_h.set(str(self.state.h))
            self.v_d.set(str(self.state.d))
            self._phase6_last_w = self.state.w
            self._phase6_last_d = self.state.d
            _phase6_refresh_profiles_from_settings(self)

            fresh_intent = cabinet_family_policy.fresh_assembly_intent(new_model)
            self._phase6_assembly_type = fresh_intent
            self._phase6_input_snapshot["assembly_type"] = fresh_intent
            _phase6_sync_joint_state_for_intent(self, fresh_intent)
            assembly_var = getattr(self, "assembly_type_var", None)
            if assembly_var is not None:
                assembly_var.set(ASSEMBLY_TYPE_LABELS[fresh_intent])
            self._phase6_endcap_bottom_wrap_state = normalize_endcap_bottom_wrap_state(
                {"model": new_model}
            )
            self._phase6_input_snapshot["endcap_bottom_wrap"] = deepcopy(
                self._phase6_endcap_bottom_wrap_state
            )

        if new_model == "受電箱":
            if old_snapshot_model != "受電箱":
                self._phase6_non_receiving_structure_state = self.designer_workspace.box_body_structure_state()
            structure = cabinet_family_policy.resolve_box_body_structure_state(
                new_model, self.designer_workspace.box_body_structure_state()
            )
            self.designer_workspace.set_box_body_structure_state(structure)
            self._phase6_input_snapshot["box_body_structure"] = deepcopy(structure)
        elif old_snapshot_model == "受電箱":
            runtime_presets = dict(self._phase6_input_snapshot.get("_runtime_family_presets") or {})
            preset_runtime = deepcopy(dict(runtime_presets.get(new_model) or {}))
            previous = preset_runtime.get("box_body_structure")
            if previous is None:
                previous = getattr(self, "_phase6_non_receiving_structure_state", None)
            if previous:
                self.designer_workspace.set_box_body_structure_state(previous)
                self._phase6_input_snapshot["box_body_structure"] = deepcopy(previous)
    except Exception:
        # Rendering/validation will surface a real structure error; do not invent
        # a second fallback structure here.
        pass
    self._phase6_baseline_last_model = new_model
    _phase6_apply_box_symmetry_policy(self)
    if hasattr(self, "bend_ui"):
        self.bend_ui._phase6_refresh_symmetry_bar()
    _phase6_sync_authoritative_derived_parts(self)
    _phase6_refresh_assembly_parts_panel_if_topology_changed(self)
    _phase6_refresh_persistent_structure_controls(self)

    # 快取頁面依 _corner_editable 決定是否建立可編輯截角控制項。
    # Baseline changes are explicit user actions, so rebuilding those pages here
    # is correct; ordinary part switching still reuses the cache.
    _phase6_invalidate_corner_pages(self)
    if hasattr(self, "settings_center") and getattr(self, "active_part_key", None) is not None:
        _phase6_render_settings_context(self, getattr(self, "settings_context", self.active_part_key))
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


def _phase6_relief_polygon_coords(geometry):
    if geometry is None or getattr(geometry, "is_empty", True):
        return []
    if getattr(geometry, "geom_type", "") == "Polygon":
        polygons = [geometry]
    else:
        polygons = [
            geom for geom in getattr(geometry, "geoms", ())
            if getattr(geom, "geom_type", "") == "Polygon" and float(geom.area) > 1e-9
        ]
    out = []
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) >= 3:
            out.append([[float(x), float(y)] for x, y in coords])
    return out


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
    context = DiagnosticSnapshotContext(
        model=model,
        active_part=active_part,
        settings=settings,
        corner_state=getattr(self, "_phase6_corner_state", {}) or {},
        corner_pair_same=getattr(self, "_phase6_corner_pair_same", {}) or {},
        workspace=_phase6_collect_workspace_state(self),
        active_part_payload=payload,
    )
    provider = (lambda: _phase6_query_final_render_data(self)) if active_part else None
    return build_active_diagnostic_snapshot(context, provider)


def _phase6_build_project_snapshot(self):
    """Capture one complete, reloadable Phase6 workspace plus all-part diagnostics."""
    from phase6_project_file import PROJECT_SCHEMA

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
    snapshot = deepcopy(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    snapshot.update(dict(getattr(self, "_phase6_box_whd", {}) or {}))
    snapshot.update({
        "model": model,
        "assembly_type": assembly_intent_value(getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)),
        "endcap_fw": deepcopy(getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(snapshot))),
        "settings": deepcopy(getattr(self, "_settings_values", {}) or {}),
        "corner_state": deepcopy(getattr(self, "_phase6_corner_state", {}) or {}),
        "corner_pair_same": deepcopy(getattr(self, "_phase6_corner_pair_same", {}) or {}),
        "existing_parts": list(owner_workspace["existing_parts"]),
        "active_part": owner_workspace["active_part"],
        "workspace": workspace,
        "box_body_profile": clone_profile(workspace.get("box_body_profile", [])),
        "part_profiles": deepcopy(workspace.get("part_profiles", {})),
        "part_features": deepcopy(owner_workspace["part_features"]),
        "part_face_features": deepcopy(owner_workspace["part_face_features"]),
        "assembly_placements": deepcopy(owner_workspace.get("assembly_placements", {})),
        "assembly_relief": _phase6_serialize_assembly_relief_state(self),
    })

    callback = getattr(self, "_scene_query_callback", None)
    final_geometry = collect_final_geometry_diagnostics(
        list(owner_workspace["existing_parts"]),
        lambda key: _phase6_scene_query_payload_for_part(self, key),
        callback if callable(callback) else None,
    )

    return {
        "schema": PROJECT_SCHEMA,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": model,
        "snapshot": snapshot,
        "final_geometry": final_geometry,
    }


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
        target = _phase6_write_diagnostic_json(path, _phase6_build_diagnostic_snapshot(self))
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"已存檔：{target.name}（未提交主畫面）")
        return str(target)
    except Exception as exc:
        messagebox.showerror("存檔失敗", f"無法儲存折彎診斷檔：\n{exc}", parent=self.root)
        return None


def _phase6_load_project_file(self):
    """透過 parent GUI 載入 .p6fold，並建立新的 3D 工作區。"""
    from tkinter import filedialog, messagebox
    from phase6_project_file import PROJECT_EXTENSION, read_project

    path = filedialog.askopenfilename(
        parent=self.root,
        title="讀檔：Phase6 折彎專案",
        filetypes=[("Phase6 折彎專案", f"*{PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
    )
    if not path:
        return None

    callback = getattr(self, "_project_load_callback", None)
    if not callable(callback):
        messagebox.showerror("讀檔失敗", "目前工作區沒有可用的專案讀檔入口。", parent=self.root)
        return None

    try:
        # 在目前交易式 3D 視窗被替換前先驗證檔案。
        # authoritative restore 由 parent callback 執行，確保主 GUI、2D、
        # 板件存在狀態、3D 與輸出鏈都從同一來源重新載入。
        read_project(path)
        callback(str(path))
        return str(path)
    except Exception as exc:
        try:
            messagebox.showerror("讀檔失敗", f"無法讀取 Phase6 專案：\n{exc}", parent=self.root)
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
    from phase6_project_file import PROJECT_EXTENSION, write_project

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
        initial = Path(current).name if current else f"{safe_model}{PROJECT_EXTENSION}"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="另存新檔：Phase6 專案" if save_as else "儲存專案：Phase6",
            defaultextension=PROJECT_EXTENSION,
            filetypes=[("Phase6 折彎專案", f"*{PROJECT_EXTENSION}"), ("所有檔案", "*.*")],
            initialfile=initial,
        )
        if not path:
            return None

    try:
        payload = _phase6_build_project_snapshot(self)
        # Runtime-only host path must never become mechanical project data.
        payload.get("snapshot", {}).pop("_runtime_project_path", None)
        target = write_project(path, payload)
        self._phase6_current_project_path = str(target)
        callback = getattr(self, "_project_path_change_callback", None)
        if callable(callback):
            callback(str(target))
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set(f"已存專案：{target.name}（全部板件）")
        return str(target)
    except Exception as exc:
        messagebox.showerror("存檔失敗", f"無法儲存 Phase6 專案：\n{exc}", parent=self.root)
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
    """只在折彎工作區結構真的改變時保存結構。

    一般數值設定本來就會即時同步；這個輕量快照只負責讓自訂段落拓撲與
    新增板件在關閉 3D 視窗後仍保留。它不包含也不提交基準檔／截角交易資料，
    也不執行舊版完整匯出 adapter。
    """
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
    result = {
        "box_body_profile": clone_profile(self.state.profiles_vault.get("箱身", [])),
        "existing_parts": list(owner["existing_parts"]),
        "active_part": owner["active_part"],
        "part_profiles": deepcopy(owner["part_profiles"]),
        "box_body_structure": deepcopy(owner.get("box_body_structure") or self.designer_workspace.box_body_structure_state()),
    }
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
    self._phase6_input_snapshot["endcap_fw"] = deepcopy(self._phase6_endcap_fw_state)
    self.designer_workspace.mark_dirty()
    linked = _phase6_rebuild_linked_endcaps(self)
    _phase6_refresh_active_endcap_from_linked(self, linked)
    try:
        self.do_update()
    except Exception:
        pass
    return linked


def _phase6_set_endcap_fw_follow(self, part_key, follow_box):
    part_key = str(part_key)
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    box_fw = _num(snapshot.get("fw", 25), 25)
    set_endcap_fw_follow(self._phase6_endcap_fw_state, part_key, bool(follow_box), box_fw=box_fw)
    return _phase6_commit_endcap_fw_state(self)


def _phase6_set_endcap_fw_override(self, part_key, value):
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    snapshot.update(dict(getattr(self, "_settings_values", {}) or {}))
    commit_endcap_fw(
        self._phase6_endcap_fw_state, str(part_key), _num(value),
        box_fw=_num(snapshot.get("fw", 25), 25),
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

    box = original.ttk.LabelFrame(parent, text="邊框寬度 FW", padding=4)
    box.grid(row=start_row, column=0, columnspan=5, sticky="ew", padx=3, pady=(6, 2))
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


def _phase6_commit_box_structure_state(self, state, *, rebuild=False):
    state = self.designer_workspace.set_box_body_structure_state(state)
    self._phase6_input_snapshot["box_body_structure"] = deepcopy(state)
    # 結構型態/尺寸是 manufacturing geometry signature 的一部分。切換後不可
    # 繼續重用上一型態的 resolved geometry，否則 3D 會停在舊結構。
    self._phase6_last_resolved_manufacturing_geometry = None
    self._phase6_last_resolved_manufacturing_signature = None
    self.designer_workspace.mark_dirty()
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


def _phase6_box_structure_error(self, exc):
    var = getattr(self, "settings_status_var", None)
    if var is not None:
        var.set(f"箱身結構設定無效：{exc}")


def _phase6_toggle_box_structure_lock(self):
    state = _phase6_box_structure_state(self)
    _phase6_commit_box_structure_state(self, set_structure_locked(state, not bool(state.get("locked", True))), rebuild=True)


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
        next_state = activate_structure_with_defaults(
            state, type_id, _phase6_box_structure_w(self)
        )
    except Exception as exc:
        _phase6_box_structure_error(self, exc)
        return
    _phase6_commit_box_structure_state(self, next_state, rebuild=True)
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
        total_w = _phase6_box_structure_w(self)
        if type_id is BoxBodyStructureType.TWO_PIECE_W_SPLIT and field in {"left", "right"}:
            state = set_two_piece_width(state, total_w, field, value)
        elif type_id is BoxBodyStructureType.THREE_PIECE_W_SPLIT and field in {"left", "middle", "right"}:
            state = set_three_piece_width(state, total_w, field, value)
        elif field == "seam_bend":
            state = set_join_seam_bend(state, type_id, value)
        elif type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT and field == "side_rear_bend":
            state = set_side_back_geometry(state, side_rear_bend=value)
        elif type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT and field == "back_width_comp_t":
            state = set_side_back_geometry(state, back_width_comp_t=value)
        else:
            if field in {"endcap_extra_relief", "endcap_single_side_meat_t", "baseplate_relief_length", "baseplate_single_side_meat_t"} and value < 0:
                raise ValueError("截角／避讓參數不得小於 0")
            state = update_structure_config(state, type_id, {field: value})
        _phase6_commit_box_structure_state(self, state, rebuild=True)
    except Exception as exc:
        _phase6_box_structure_error(self, exc)
        # Recreate from canonical state so an invalid typed value never becomes UI truth.
        _phase6_commit_box_structure_state(self, state, rebuild=True)


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
        rear_bend = float(cfg.get("side_rear_bend", 15))
        width_comp_t = float(cfg.get("back_width_comp_t", 0.5))
        piece_values = {
            "box_body:left_side": ("rear_bend", "後折", rear_bend, "mm", "side_rear_bend"),
            "box_body:back": ("width_comp_t", "寬補償", width_comp_t, "T", "back_width_comp_t"),
            "box_body:right_side": ("rear_bend", "後折", rear_bend, "mm", "side_rear_bend"),
        }

    projections = ()
    if active is not BoxBodyStructureType.INTEGRAL:
        try:
            render_data = _phase6_query_final_render_data(self)
            projections = _phase6_box_body_piece_dimension_projections(render_data)
        except Exception as exc:
            original.ttk.Label(
                self.box_body_piece_input_host,
                text=f"逐片尺寸：無法解析（{exc}）",
                foreground="#b45309",
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
                foreground="#b45309",
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
    self._phase6_assembly_type = type_id
    self._phase6_input_snapshot["assembly_type"] = assembly_intent_value(type_id)
    _phase6_sync_joint_state_for_intent(self, type_id)
    # Normal preset selection updates Intent + Joint Graph only. CornerState is
    # a legacy/manual projection and must not be rewritten by this UI action.
    self.designer_workspace.mark_dirty()
    # The box-body page owns the live assembly Combobox that fired this event.
    # Destroying/rebuilding that page from inside <<ComboboxSelected>> destroys
    # the widget while Tk is still dispatching its event (visible as the whole
    # selector/page disappearing on Windows).  Only dependent EndCap pages need
    # rebuilding because their top CornerType controls changed.
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
_ENDCAP_LABEL_TO_RELATION = {label: relation for relation, label in _ENDCAP_RELATION_LABELS.items()}

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
    snapshot = set_part_edge_relation(
        dict(getattr(self, "_phase6_input_snapshot", {}) or {}),
        part_key, edge, relation,
    )
    self._phase6_input_snapshot.update({
        "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
        "assembly_joints": deepcopy(snapshot["assembly_joints"]),
        "assembly_type": snapshot.get("assembly_type", self._phase6_input_snapshot.get("assembly_type")),
    })
    workspace = getattr(self, "designer_workspace", None)
    if workspace is not None:
        workspace.mark_dirty()
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
    edge = str(edge).upper()
    if edge == "TOP":
        host.place(relx=0.5, y=8, anchor="n")
    elif edge == "BOTTOM":
        host.place(relx=0.5, rely=1.0, y=-8, anchor="s")
    elif edge == "LEFT":
        host.place(x=8, rely=0.5, anchor="w")
    elif edge == "RIGHT":
        host.place(relx=1.0, x=-8, rely=0.5, anchor="e")

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
            state=("normal" if row["editable"] else "disabled"), width=7,
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
    if not _phase6_box_symmetry_allowed(self):
        _phase6_apply_box_symmetry_policy(self)
        if hasattr(self, "bend_ui"):
            self.bend_ui._phase6_refresh_symmetry_bar()
    else:
        try:
            self.state.symmetric = bool(var.get())
        except Exception:
            return
    self.designer_workspace.mark_dirty()

    # v_sy already owns an original trace to queue_update().  When this command
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
    state = getattr(self, "_phase6_endcap_bottom_wrap_state", None)
    if not isinstance(state, dict):
        state = normalize_endcap_bottom_wrap_state(snapshot)
        self._phase6_endcap_bottom_wrap_state = state
    commit_endcap_bottom_wrap(
        state, str(part_key), reserve_u=reserve_u, reserve_v=reserve_v,
    )
    self._phase6_input_snapshot["endcap_bottom_wrap"] = deepcopy(state)
    self._phase6_last_resolved_manufacturing_geometry = None
    self._phase6_last_resolved_manufacturing_signature = None
    for key in ENDCAP_FW_PARTS:
        _phase6_invalidate_settings_page(self, key)
    self.designer_workspace.mark_dirty()
    self.do_update()
    return resolve_endcap_bottom_wrap(self._phase6_input_snapshot, str(part_key), state=state)


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
    stable = assembly_intent_value(type_id)
    self._phase6_assembly_type = (
        stable if stable == "WRAP_OVERLAY" else CornerTypeId(stable)
    )
    self._phase6_input_snapshot["assembly_type"] = stable
    _phase6_sync_joint_state_for_intent(self, self._phase6_assembly_type)
    legacy_projection = legacy_corner_projection_for_intent(stable)
    apply_box_assembly_type_to_raw_state(
        self._phase6_corner_state, self._phase6_corner_pair_same, legacy_projection,
        reset_bottom_defaults=(stable == CornerTypeId.OVERLAY.value),
    )
    for context in ("box_body", "head", "tail"):
        _phase6_invalidate_settings_page(self, context)
    if getattr(self, "active_part_key", None) is not None:
        _phase6_render_settings_context(self, getattr(self, "settings_context", self.active_part_key))
    self.do_update()
    return self._phase6_assembly_type


def _phase6_apply_external_corner_state(self, corner_state, corner_pair_same):
    self._phase6_corner_guard = True
    try:
        self._phase6_corner_state = deepcopy(corner_state or {})
        self._phase6_corner_pair_same = deepcopy(corner_pair_same or {})
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


def _phase6_apply_external_sync(self, envelope):
    """Ingest one Main-GUI revision without echoing it back to the host."""
    envelope = dict(envelope or {})
    if str(envelope.get("origin") or "") != "main_gui":
        return {}
    try:
        revision = int(envelope.get("revision", 0) or 0)
    except (TypeError, ValueError):
        return {}
    last_revision = int(getattr(self, "_phase6_last_external_revision", 0) or 0)
    if revision <= last_revision:
        return {}
    self._phase6_last_external_revision = revision
    self._phase6_last_external_transaction_id = str(envelope.get("transaction_id") or "")
    delta = dict(envelope.get("delta") or {})
    settings = dict(delta.get("settings") or {})
    if not settings:
        return {}
    return _phase6_apply_external_settings(self, settings)






def _phase6_apply_ui_text_size(self, key):
    if getattr(self, "_phase6_settings_guard", False):
        return
    key = normalize_ui_text_size(key)
    self._settings_values["ui_text_size"] = key
    self._phase6_input_snapshot["ui_text_size"] = key
    self._ui_text_controller.apply(key)
    self.state.ui_text_scale = self._ui_text_controller.factor
    callback = getattr(self, "_ui_text_size_change_callback", None)
    if callback is not None:
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
    "ZERO": "零間隙",
    "USER_ADDED": "使用者新增",
    "LEGACY_MIGRATED": "舊資料轉入",
    "CERTIFIED": "已認證",
    "CERTIFIED_FROM_3D": "3D 驗證認證",
    "PROVISIONAL_3D": "3D 暫定",
    "ENGINE_CONFLICT": "引擎衝突",
    "REGISTRY_AMBIGUOUS": "規則不明確",
    "ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1": "封頭尾上方嵌入（結構接合）",
    "ENDCAP_TOP_INSERT_STANDARD_V1": "封頭尾上方嵌入（標準）",
    "ENDCAP_TOP_OVERLAY_STANDARD_V1": "封頭尾上方貼外（標準）",
    "ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1": "封頭尾上方嵌入貼外（連動框寬）",
    "ENDCAP_TOP_INSERT_OVERLAY_STANDARD_V1": "封頭尾上方嵌入貼外（標準）",
    "RECEIVING_ENDCAP_BOTTOM_WRAP_V1": "受電箱封頭尾下方外側包覆",
    "ytop1_present": "有上折",
    "ytop1_absent": "無獨立上折",
    "ybottom1_present": "有下折",
    "x_folded": "X向有折",
    "x_flat": "X向平板",
}


def _phase6_is_derived_physical_part_key(value):
    key = str(value or "")
    return (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
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


_PHASE6_FORMULA_DISPLAY_TOKENS = {
    "effective_mating_width": "有效接合寬",
    "mating_width": "成型接合寬",
    "side_fold": "側折",
    "rear_bend": "後折",
    "reserve_u": "X預留",
    "reserve_v": "Y預留",
    "ybottom1": "下折",
    "ytop1": "上折",
    "clearance": "間隙",
    "fold_u": "X向折邊",
    "fold_v": "Y向折邊",
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


def _phase6_preconditions_display(value):
    tokens = [token.strip() for token in str(value or "").split(",") if token.strip()]
    return "、".join(_phase6_operator_label(token) for token in tokens)


def _phase6_preconditions_raw(value):
    reverse = {label: raw for raw, label in _PHASE6_OPERATOR_LABELS.items()}
    tokens = [token.strip() for token in re.split(r"[,，、]", str(value or "")) if token.strip()]
    return ",".join(reverse.get(token, token) for token in tokens)


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


def _phase6_form_choice(parent, variable, choices, *, width=18):
    display_var = original.tk.StringVar(master=parent, value=_phase6_operator_label(variable.get()))
    button = original.ttk.Menubutton(parent, textvariable=display_var, width=width)
    menu = original.tk.Menu(button, tearoff=False)

    def choose(raw):
        variable.set(str(raw))
        display_var.set(_phase6_operator_label(raw))

    for choice in choices:
        menu.add_command(label=_phase6_operator_label(choice), command=lambda v=str(choice): choose(v))
    button.configure(menu=menu)

    def sync_display(*_args):
        value = _phase6_operator_label(variable.get())
        if display_var.get() != value:
            display_var.set(value)

    variable.trace_add("write", sync_display)
    button._phase6_display_var = display_var
    button._phase6_raw_var = variable
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
    from ae_engine.certified_relief_registry import evaluate_relief_formula_record, _validate_editable_rule_record
    try:
        record = _validate_editable_rule_record(_phase6_registry_collect_rule_form(self))
        result = evaluate_relief_formula_record(record, _phase6_registry_sample_variables(self))
        text = f"公式有效：{result['primary_u']:.3f}×{result['primary_v']:.3f}"
        if result.get("secondary_u") is not None:
            text += f" + {result['secondary_u']:.3f}×{result['secondary_depth']:.3f}"
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
    canvas.delete("all")
    canvas.create_rectangle(15, 15, 225, 145, outline="#777")
    if not result:
        return None
    pu, pv = float(result["primary_u"]), float(result["primary_v"])
    scale = min(180.0 / max(pu, 1.0), 95.0 / max(pv + float(result.get("secondary_depth") or 0), 1.0))
    x0, y0 = 20.0, 140.0
    canvas.create_rectangle(x0, y0 - pv * scale, x0 + pu * scale, y0, outline="#222", width=2)
    if result.get("secondary_u") is not None:
        su, sd = float(result["secondary_u"]), float(result["secondary_depth"])
        canvas.create_rectangle(x0, y0 - (pv + sd) * scale, x0 + su * scale, y0 - pv * scale, outline="#222", width=2)
    return result


def _phase6_registry_candidate_form_is_current(self):
    saved = getattr(self, "_phase6_registry_candidate_record", None)
    if not isinstance(saved, Mapping):
        return False
    try:
        current = _phase6_registry_collect_rule_form(self)
    except Exception:
        return False
    return deepcopy(dict(current)) == deepcopy(dict(saved))


def _phase6_registry_require_current_candidate(self):
    candidate_id = str(getattr(self, "_phase6_registry_candidate_id", "") or "")
    if not candidate_id:
        raise ValueError("請先儲存候選")
    if not _phase6_registry_candidate_form_is_current(self):
        raise ValueError("表單已變更；請重新儲存候選後再驗證")
    return candidate_id


def _phase6_registry_save_candidate_form(self):
    from ae_engine.certified_relief_registry import save_relief_rule_candidate
    result = _phase6_registry_validate_formula_form(self)
    if result is None:
        return None
    try:
        record = _phase6_registry_collect_rule_form(self)
        item = save_relief_rule_candidate(record)
        self._phase6_registry_candidate_id = item["candidate_id"]
        self._phase6_registry_candidate_record = deepcopy(dict(record))
        self._phase6_registry_regression_evidence = {"candidate_id": item["candidate_id"]}
        self.relief_registry_status_var.set("候選已儲存（尚未認證）")
        return item
    except Exception as exc:
        self.relief_registry_status_var.set(f"候選儲存失敗：{exc}")
        return None


def _phase6_registry_run_formula_matrix(self):
    from ae_engine.certified_relief_registry import evaluate_relief_formula_record, _validate_editable_rule_record
    try:
        candidate_id = _phase6_registry_require_current_candidate(self)
        record = _validate_editable_rule_record(_phase6_registry_collect_rule_form(self))
        base = _phase6_registry_sample_variables(self)
        samples = []
        for t in (max(0.5, base["T"] * 0.75), base["T"], base["T"] * 1.25):
            for fw in (max(t * 2, base["FW"] * 0.8), base["FW"], base["FW"] * 1.2):
                variables = dict(base, T=t, FW=fw)
                evaluate_relief_formula_record(record, variables)
                samples.append(variables)
        evidence = dict(getattr(self, "_phase6_registry_regression_evidence", {}) or {})
        evidence.update({"matrix_passed": True, "cases": len(samples), "candidate_id": candidate_id})
        self._phase6_registry_regression_evidence = evidence
        self.relief_registry_status_var.set(
            f"公式矩陣通過：{len(samples)} cases；3D零穿透=" + ("是" if evidence.get("zero_penetration") else "尚未")
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
    try:
        candidate_id = _phase6_registry_require_current_candidate(self)
        record = deepcopy(dict(getattr(self, "_phase6_registry_candidate_record", {}) or {}))
        evidence3d = _phase6_registry_validate_candidate_3d(
            self, record, candidate_id=candidate_id
        )
        evidence = dict(getattr(self, "_phase6_registry_regression_evidence", {}) or {})
        evidence.update(dict(evidence3d or {}))
        self._phase6_registry_regression_evidence = evidence
        zero = bool(evidence.get("zero_penetration"))
        self.relief_registry_status_var.set(
            "候選專屬組合3D驗證：" + ("零非法穿透" if zero else "仍有非法穿透")
        )
        return zero
    except Exception as exc:
        self.relief_registry_status_var.set(f"組合3D驗證失敗：{exc}")
        return False


def _phase6_registry_promote_form(self):
    from ae_engine.certified_relief_registry import promote_relief_rule_candidate
    try:
        candidate_id = _phase6_registry_require_current_candidate(self)
    except Exception as exc:
        self.relief_registry_status_var.set(str(exc))
        return None
    evidence = dict(getattr(self, "_phase6_registry_regression_evidence", {}) or {})
    try:
        promoted = promote_relief_rule_candidate(candidate_id, regression_evidence=evidence)
        self.relief_registry_status_var.set(f"已認證新版次：{promoted['revision']}")
        _phase6_registry_refresh_rule_tree(self)
        return promoted
    except Exception as exc:
        self.relief_registry_status_var.set(f"不可認證：{exc}")
        return None


def _phase6_registry_refresh_rule_tree(self):
    from ae_engine.certified_relief_registry import load_external_relief_rule_records
    tree = getattr(self, "relief_registry_rule_tree", None)
    if tree is None:
        return ()
    for item in tree.get_children():
        tree.delete(item)
    rows = load_external_relief_rule_records()
    active_rows = [row for row in rows if bool(row.get("active", True))]
    for row in active_rows:
        tree.insert("", "end", iid=f"{row['rule_id']}@{row['revision']}", values=(
            _phase6_operator_label(row["rule_id"]), row["revision"], _phase6_operator_label(row.get("trust_level", "")),
            _phase6_operator_label(row.get("assembly_intent", "")), row.get("topology_levels", ""),
        ))
    self._phase6_registry_rule_records = {f"{row['rule_id']}@{row['revision']}": row for row in rows}
    return rows


def _phase6_registry_rule_selected(self, *_args):
    tree = getattr(self, "relief_registry_rule_tree", None)
    if tree is None or not tree.selection():
        return
    key = tree.selection()[0]
    raw = dict(getattr(self, "_phase6_registry_rule_records", {}).get(key) or {})
    if not raw:
        return
    formula = dict(raw.get("formula", {}) or {})
    self.relief_registry_rule_name_var.set(_phase6_operator_label(raw.get("rule_id", "")))
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
        (self.relief_registry_preconditions_var, ",".join(str(v) for v in (raw.get("preconditions", ()) or ()))),
        (self.relief_registry_source_var, str(raw.get("source", ""))),
    )
    for var, value in setters:
        var.set(str(value))
    sig = list(raw.get("joint_signature", ()) or ())
    extra = sig[1].get("relation") if len(sig) > 1 else "NONE"
    self.relief_registry_extra_joint_var.set(str(extra))
    if len(sig) > 1:
        self.relief_registry_extra_target_role_var.set(str(sig[1].get("target_role", "REAR_PANEL")))


def _phase6_joint_form_refresh(self):
    tree = getattr(self, "relief_joint_tree", None)
    if tree is None:
        return ()
    rows = _phase6_joint_rows(self)
    for item in tree.get_children():
        tree.delete(item)
    for row in rows:
        tree.insert("", "end", iid=str(row["joint_id"]), values=(
            _phase6_operator_label(row.get("subject_part", "")), _phase6_operator_label(row.get("target_part", "")),
            _phase6_operator_label(row.get("relation", "")), _phase6_operator_label(row.get("source", "")),
            _phase6_operator_label(row.get("subject_region", "")), _phase6_operator_label(row.get("target_region", "")),
        ))
    return rows


def _phase6_joint_form_add(self):
    try:
        row = _phase6_add_user_joint(
            self,
            subject_part=self.relief_joint_subject_var.get(),
            target_part=self.relief_joint_target_var.get(),
            relation=self.relief_joint_relation_var.get(),
            subject_region=self.relief_joint_subject_region_var.get(),
            target_region=self.relief_joint_target_region_var.get(),
            clearance_policy=self.relief_joint_clearance_var.get(),
            solver_constraints={"topology_levels": int(self.relief_joint_topology_var.get())},
        )
        self.relief_joint_status_var.set(
            ("外側包覆：主動板件包覆接合板件；" if row["relation"] == "WRAP" else "") + "已新增接合規則"
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
        result = _phase6_delete_user_joint(self, joint_id)
        self.relief_joint_status_var.set("已刪除" if result else "找不到接合規則")
        _phase6_joint_form_refresh(self)
        return result
    except Exception as exc:
        self.relief_joint_status_var.set(f"不可刪除：{exc}")
        return False


def _phase6_open_relief_registry_form(self):
    existing = getattr(self, "relief_registry_window", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.deiconify(); existing.lift(); return existing
    except Exception:
        pass
    win = original.tk.Toplevel(self.root)
    win.title("PHASE6 截角資料庫 / 組合接合")
    win.geometry("1120x720")
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
        _phase6_bind_translated_var(raw_var, display_var, _phase6_formula_display, _phase6_formula_raw)
        setattr(self, f"relief_registry_{raw_name}_display_var", display_var)
    self.relief_registry_preconditions_display_var = original.tk.StringVar(master=form)
    _phase6_bind_translated_var(
        self.relief_registry_preconditions_var, self.relief_registry_preconditions_display_var,
        _phase6_preconditions_display, _phase6_preconditions_raw,
    )
    entry("第一級 X 公式", self.relief_registry_primary_u_display_var)
    entry("第一級 Y 公式", self.relief_registry_primary_v_display_var)
    entry("第二級 X 公式", self.relief_registry_secondary_u_display_var)
    entry("第二級深度公式", self.relief_registry_secondary_depth_display_var)
    entry("適用條件", self.relief_registry_preconditions_display_var)
    entry("公式來源／備註", self.relief_registry_source_var)

    help_box = original.ttk.LabelFrame(form, text="公式變數說明", padding=6)
    help_box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(5, 3)); row += 1
    help_lines = (
        "板厚：目前板件厚度。",
        "名義框寬：封頭／封尾自身的框寬參數；不等於箱身成型後實際占位。",
        "側折：封頭／封尾 X 向側邊折彎基底；貼外沒有 X 折時為 0。",
        "上折：封頭／封尾 Y 向第一折尺寸。",
        "成型接合寬：接合對象折好後真正需要避讓的寬度，例如貼外取箱身成型框寬。",
        "第一級 X/Y：主要截角的 X/Y 切除量；第二級 X/深度：二級截角的內側位置與深度。",
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
        ("預覽2D",lambda:_phase6_registry_preview_2d(self)),
        ("預覽組合3D",lambda:_phase6_registry_preview_assembly_3d(self)),
        ("儲存候選",lambda:_phase6_registry_save_candidate_form(self)),
        ("執行回歸",lambda:_phase6_registry_run_formula_matrix(self)),
    ):
        original.ttk.Button(actions,text=text,command=cmd).pack(side=original.tk.LEFT,padx=2)
    self.relief_registry_save_candidate_button = next((w for w in actions.winfo_children() if str(w.cget("text"))=="儲存候選"), None)
    self.relief_registry_promote_button=original.ttk.Button(actions,text="認證新版次",command=lambda:_phase6_registry_promote_form(self))
    self.relief_registry_promote_button.pack(side=original.tk.LEFT,padx=2)
    original.ttk.Label(form,textvariable=self.relief_registry_status_var,foreground="#333").grid(row=row,column=0,columnspan=4,sticky="w",pady=(4,0))
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


def _phase6_build_project_toolbar(self, parent=None):
    """永久置頂的「檔案」選單。"""
    parent = parent or self.left
    self.project_toolbar = original.ttk.Frame(parent)
    self.project_toolbar.pack(side=original.tk.LEFT, padx=(0, 8))
    self.project_file_button = original.ttk.Menubutton(self.project_toolbar, text="檔案 ▼")
    self.project_file_menu = original.tk.Menu(self.project_file_button, tearoff=False)
    self.project_file_menu.add_command(label="開啟", command=self.load_project_file)
    self.project_file_menu.add_command(label="儲存", command=self.save_project_file)
    self.project_file_menu.add_command(label="另存新檔", command=self.save_project_file_as)
    self.project_file_button.configure(menu=self.project_file_menu)
    self.project_file_button.pack(side=original.tk.LEFT)
    self.relief_registry_button = original.ttk.Button(
        self.project_toolbar, text="截角資料庫", command=lambda: _phase6_open_relief_registry_form(self)
    )
    self.relief_registry_button.pack(side=original.tk.LEFT, padx=(6, 0))




def _phase6_build_transaction_buttons(self, parent=None):
    """Top-right project actions: live canonical mode has no confirm/cancel."""
    parent = parent or self.left
    self.transaction_buttons = original.ttk.Frame(parent)
    self.transaction_buttons.pack(side=original.tk.RIGHT)
    self.transaction_buttons.columnconfigure(0, weight=1)
    self.reset_initial_button = original.ttk.Button(
        self.transaction_buttons, text="還原初始值", command=self.reset_initial_values
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
    self.visual_controls = original.ttk.LabelFrame(parent, text="3D 顯示", padding=5)
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


def _phase6_return_to_2d_corner(self):
    """Commit current live draft and hand control back to the main 2D corner view."""
    callback = getattr(self, "_return_2d_callback", None)
    if callback is None:
        return False
    if getattr(self, "_phase6_pending_settings", None):
        self.flush_pending_settings()
    if getattr(getattr(self, "designer_workspace", None), "active_part", None) is not None:
        self._save_current_part()
    _phase6_publish_live_state(self, force=True)
    key = str(getattr(self.designer_workspace, "active_part", "") or "box_body")
    callback(key)
    return True


def _phase6_build_persistent_top_area(self):
    """固定版面：最上列命令；其下兩行全域設定；左右工作區。"""
    try:
        self.left.pack_forget()
        self.right.pack_forget()
    except Exception:
        pass

    self.top_persistent_bar = original.ttk.Frame(self.root, padding=(10, 8, 10, 4))
    self.top_persistent_bar.pack(side=original.tk.TOP, fill=original.tk.X)

    self.top_command_row = original.ttk.Frame(self.top_persistent_bar)
    self.top_command_row.pack(fill=original.tk.X)
    _phase6_build_project_toolbar(self, self.top_command_row)
    _phase6_build_transaction_buttons(self, self.top_command_row)

    self.top_settings_row = original.ttk.Frame(self.top_persistent_bar)
    self.top_settings_row.pack(fill=original.tk.X, pady=(5, 0))
    self.top_global_host = original.ttk.Frame(self.top_settings_row)
    self.top_global_host.pack(fill=original.tk.X, expand=True)
    panel = _phase6_ensure_settings_panel(self)
    panel.build_left_global_controls(
        self.top_global_host,
        baseline_models=tuple(self._baseline_models),
        initial_model=self._phase6_baseline_initial_model,
    )
    _phase6_sync_settings_panel_compat(self)
    _phase6_build_global_persistent_controls(self)

    # 第一列固定順序：檔案 → 3D 顯示 → 全螢幕；交易按鈕固定最右。
    _phase6_build_visual_controls(self, self.top_command_row)
    self.fullscreen_button = original.ttk.Button(
        self.top_command_row, text="全螢幕", command=lambda: _phase6_toggle_fullscreen(self)
    )
    self.fullscreen_button.pack(side=original.tk.LEFT, padx=(0, 4))
    self.return_2d_button = original.ttk.Button(
        self.top_command_row, text="回2D截角", command=lambda: _phase6_return_to_2d_corner(self),
    )
    self.return_2d_button.pack(side=original.tk.LEFT, padx=(0, 8))
    if getattr(self, "_return_2d_callback", None) is None:
        self.return_2d_button.configure(state="disabled")
    _phase6_sync_settings_panel_compat(self)

    self.left.pack(side=original.tk.LEFT, fill=original.tk.Y)
    self.right.pack(side=original.tk.RIGHT, fill=original.tk.BOTH, expand=True)


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

    self._phase6_pending_settings = {}
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
    if self._save_defaults_callback is None:
        if hasattr(self, "settings_status_var"):
            self.settings_status_var.set("未連接預設值儲存器")
        return False
    try:
        self._save_defaults_callback(
            context,
            dict(self._settings_values),
            deepcopy(getattr(self, "_phase6_corner_state", {})),
            deepcopy(getattr(self, "_phase6_corner_pair_same", {})),
        )
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
    """Build draft PartSpec inputs for any saved Phase6 part without switching UI."""
    key = str(part_key or "")
    if not key:
        return {}
    values = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    values.update(dict(getattr(self, "_settings_values", {}) or {}))
    values.update(dict(getattr(self, "_phase6_box_whd", {}) or {}))
    try:
        if key == "box_body":
            profile = list((getattr(self.state, "profiles_vault", {}) or {}).get("箱身", ()) or ())
            values.update(read_box_body_profile(profile, values))
            values["fold_profile"] = clone_profile(profile)
        else:
            if key == self.designer_workspace.active_part:
                profiles = getattr(self.state, "profiles", {}) or {}
            else:
                profiles = self.designer_workspace.profiles_for(key, {}) or {}
            if key in {"head", "tail"}:
                values.update(read_endcap_xy_profiles(profiles, values))
                values["box_body_profile"] = clone_profile(
                    (getattr(self.state, "profiles_vault", {}) or {}).get("箱身", ()) or ()
                )
                values["fold_profiles"] = {
                    "X": clone_profile(profiles.get("X", ())),
                    "Y": clone_profile(profiles.get("Y", ())),
                }
            else:
                values.update(read_standard_part_profiles(key, profiles, values))
    except Exception:
        # An in-progress row can be incomplete. Keep the last valid snapshot
        # values rather than inventing geometry.
        pass
    model_var = getattr(self, "baseline_model_var", None)
    values["model"] = str(
        model_var.get() if model_var is not None
        else getattr(self, "_phase6_baseline_initial_model", "") or ""
    ).strip()
    values["endcap_fw"] = deepcopy(getattr(self, "_phase6_endcap_fw_state", normalize_endcap_fw_state(values)))
    values["endcap_bottom_wrap"] = deepcopy(
        getattr(self, "_phase6_endcap_bottom_wrap_state", normalize_endcap_bottom_wrap_state(values))
    )
    if key in ENDCAP_FW_PARTS:
        values["fw"] = resolve_endcap_fw(values, key, state=values["endcap_fw"])
    values["corner_state"] = deepcopy(getattr(self, "_phase6_corner_state", {}) or {})
    # Normal single-part 3D must replay the same already-committed dynamic
    # relief that 2D/DXF use. Assembly probing explicitly disables this flag so
    # it can restore/probe the physical corner before deriving a new cut.
    values["_use_committed_relief"] = True
    values["features"] = self.designer_workspace.features_for(key)
    values["face_features"] = self.designer_workspace.face_features_for(key)
    values["box_body_structure"] = self.designer_workspace.box_body_structure_state()
    source_graph = migrate_legacy_snapshot_joints(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    values["assembly_joint_schema_version"] = source_graph.get("assembly_joint_schema_version")
    values["assembly_joints"] = deepcopy(source_graph.get("assembly_joints", ()))
    if key in ENDCAP_FW_PARTS and cabinet_family_policy.supports_bottom_wrap_controls(values):
        try:
            item = resolve_endcap_bottom_wrap(
                values, key, state=values["endcap_bottom_wrap"]
            )
            # Relation is graph-owned. Family state contributes only
            # adjustable geometric reserves to the certified formula.
            structure = cabinet_family_policy.set_bottom_relief_reserves(
                values,
                values["box_body_structure"],
                reserve_u=item["reserve_u"],
                reserve_v=item["reserve_v"],
            )
            values["box_body_structure"] = structure
        except Exception:
            pass
    if key == "box_body":
        for part_key, target in (("head", "head_ybottom1"), ("tail", "tail_ybottom1")):
            profiles = self.designer_workspace.profiles_for(part_key, {}) or {}
            for row in list(dict(profiles).get("Y", ()) or ()):
                if str(row.get("phase6_key") or "") == "ybottom1":
                    values[target] = float(engine_segment_length_to_ui(row))
                    break
    source = getattr(self, "_phase6_input_snapshot", {}) or {}
    for name in (
        "indicator_layer_groups", "door_indicator_groups",
        "door_indicator_offset", "door_indicator_box_enabled",
    ):
        if name not in values and name in source:
            values[name] = deepcopy(source[name])
    return values


def _phase6_scene_query_payload(self):
    """Return only current draft PartSpec inputs; no geometry is built here."""
    return _phase6_scene_query_payload_for_part(self, self.designer_workspace.active_part)


def _phase6_query_final_render_data(self):
    """Return authoritative render data for the active sheet.

    Box Body / EndCaps and any sheet participating in a USER_ADDED Joint must
    read the resolved assembly result so single-part 3D cannot drift from the
    combined view.  Unrelated sheets (Door/Base Plate/etc.) have no assembly
    relief dependency and should query their own manufacturing FinalScene
    directly instead of forcing a whole-cabinet solve.
    """
    key = str(self.designer_workspace.active_part or "")
    if not key:
        raise ValueError("no active part")

    snapshot = migrate_legacy_snapshot_joints(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    user_joint_parts = {
        str(raw.get(field) or "")
        for raw in tuple(snapshot.get("assembly_joints", ()) or ())
        if str(raw.get("source") or "") == AssemblyJointSource.USER_ADDED.value
        for field in ("subject_part", "target_part")
    }
    if key in {"box_body", "head", "tail"} or key in user_joint_parts:
        resolved = _phase6_resolve_manufacturing_geometry(self)
        return resolved.part(key).render_data

    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        raise RuntimeError("3D final-scene provider is not connected")
    render_data = callback(key, _phase6_scene_query_payload_for_part(self, key))
    if render_data is None:
        raise ValueError(f"manufacturing render data unavailable: {key}")
    if getattr(render_data, "pieces", None):
        return render_data
    if getattr(render_data, "scene", None) is None or getattr(render_data, "material", None) is None:
        raise TypeError("manufacturing render provider must return scene + material or physical pieces")
    return render_data






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


def _phase6_assembly_relief_clearance(self):
    var = getattr(self, "assembly_relief_clearance_var", None)
    raw = var.get() if var is not None else "0"
    try:
        value = float(str(raw).strip() or "0")
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, value)


def _phase6_make_assembly_scene_render_data(
    *,
    assembly_parts,
    show_interference=False,
    ignore_fixed_corner_relief=False,
    interference_probe_parts=(),
    joint_diagnostics=(),
    selected_joint_id=None,
    preserve_endcap_core_origin=False,
):
    """Construct the assembly bundle across old/new scene-view contracts.

    UPDATE packages may be applied over an older Phase6 tree.  Older
    ``AssemblySceneRenderData`` constructors only accepted ``assembly_parts``
    (and sometimes ``warnings``).  Filter optional keyword arguments against
    the live constructor signature so a mixed-version install can still open
    the assembly view instead of failing with ``unexpected keyword``.
    """
    from inspect import Parameter, signature

    values = {
        "assembly_parts": tuple(assembly_parts),
        "show_interference": bool(show_interference),
        "ignore_fixed_corner_relief": bool(ignore_fixed_corner_relief),
        "interference_probe_parts": tuple(interference_probe_parts or ()),
        "joint_diagnostics": tuple(joint_diagnostics or ()),
        "selected_joint_id": None if selected_joint_id is None else str(selected_joint_id),
        "preserve_endcap_core_origin": bool(preserve_endcap_core_origin),
    }
    try:
        params = signature(AssemblySceneRenderData).parameters
    except (TypeError, ValueError):
        params = {}
    accepts_kwargs = any(
        p.kind is Parameter.VAR_KEYWORD for p in params.values()
    )
    if accepts_kwargs:
        kwargs = values
    else:
        kwargs = {key: value for key, value in values.items() if key in params}
        kwargs.setdefault("assembly_parts", values["assembly_parts"])
    return AssemblySceneRenderData(**kwargs)


def _phase6_current_cabinet_family(self):
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
        return resolve_cabinet_type(model).canonical_name
    except Exception:
        # 自訂/舊基準型號仍可命中 cabinet_family=ANY 的已認證 Assembly 規則。
        return model or "金庫型"


def _phase6_solution_is_committable(solution):
    if bool(getattr(solution, "verified", False)):
        return True
    trust = str(getattr(solution, "trust_level", "") or "")
    return bool(getattr(solution, "rule_id", None)) and trust in {
        "CERTIFIED", "CERTIFIED_FROM_3D", "ENGINE_CONFLICT"
    }


def _phase6_apply_resolved_cut_to_part(part, cut_polygon):
    """Apply an already-verified Joint relief to canonical FinalScene without rebuilding PartSpec."""
    from ae_engine.assembly_collision import _scene_with_replaced_primary_cutting
    from ae_engine.manufacturing_api import (
        PartRenderData, material_polygon_from_final_scene, fold_guides_from_final_scene,
        _scene_with_authoritative_fold_profiles,
    )
    material = getattr(part.render_data, "material", None)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError(f"canonical material unavailable: {part.part_key}")
    solved = material.difference(cut_polygon)
    if not solved.is_valid:
        solved = solved.buffer(0)
    if solved.is_empty:
        raise ValueError(f"Joint relief removed all material: {part.part_key}")
    scene = _scene_with_replaced_primary_cutting(part.render_data.scene, solved)
    scene = _scene_with_authoritative_fold_profiles(
        scene, tuple(part.x_profile or ()), tuple(part.y_profile or ())
    )
    render = PartRenderData(
        scene=scene,
        material=material_polygon_from_final_scene(scene),
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=dict(getattr(part.render_data, "metadata", {}) or {}),
        unfolded_topology=getattr(part.render_data, "unfolded_topology", None),
    )
    return AssemblyScenePart(
        part_key=part.part_key, render_data=render,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    )


def _phase6_apply_resolved_cut_to_owner(part, owner_key, cut_polygon):
    """Apply a verified cut to a canonical part or one physical Box Body piece.

    ``owner_key`` may be the canonical part key (``box_body``) or a physical
    piece geometry key such as ``box_body:left_side``.  Mechanical ownership
    remains on the canonical part; this adapter only selects the UV/material
    carrier used by the solver.
    """
    canonical_key = str(part.part_key)
    geometry_key = str(owner_key or canonical_key)
    if geometry_key == canonical_key:
        return _phase6_apply_resolved_cut_to_part(part, cut_polygon)

    prefix = canonical_key + ":"
    if not geometry_key.startswith(prefix):
        raise ValueError(f"geometry owner {geometry_key!r} is not under {canonical_key!r}")
    role = geometry_key[len(prefix):].strip().lower()
    structure = part.render_data
    pieces = tuple(getattr(structure, "pieces", ()) or ())
    if not pieces:
        raise ValueError(f"piece-level geometry unavailable: {geometry_key}")

    from dataclasses import replace
    from ae_engine.manufacturing_api import _exploded_box_body_preview

    replaced = []
    found = False
    for piece in pieces:
        if str(getattr(piece, "role", "") or "").strip().lower() != role:
            replaced.append(piece)
            continue
        found = True
        material = piece.render_data.material
        minx, miny, maxx, maxy = map(float, material.bounds)
        temp_part = AssemblyScenePart(
            part_key=geometry_key,
            render_data=piece.render_data,
            x_profile=tuple(getattr(piece, "fold_profile", ()) or ()),
            y_profile=({"len": max(0.0, maxy - miny), "core": True},),
            placement=part.placement,
            offset=part.offset,
        )
        solved_piece_part = _phase6_apply_resolved_cut_to_part(temp_part, cut_polygon)
        replaced.append(replace(piece, render_data=solved_piece_part.render_data))
    if not found:
        raise ValueError(f"unknown Box Body piece role: {role!r}")

    replaced = tuple(replaced)
    preview = _exploded_box_body_preview(replaced)
    solved_structure = replace(structure, pieces=replaced, preview_render_data=preview)
    return AssemblyScenePart(
        part_key=part.part_key, render_data=solved_structure,
        x_profile=part.x_profile, y_profile=part.y_profile,
        placement=part.placement, offset=part.offset,
    )


def _phase6_side_wrap_target_corners(preserve_part_key):
    """Return the two physical target-piece end corners touched by an EndCap side WRAP."""
    key = str(preserve_part_key or "").strip().lower()
    if key == "head":
        return ("top_left", "top_right")
    if key == "tail":
        return ("bottom_left", "bottom_right")
    raise ValueError(f"side WRAP preserve part must be head/tail, got {preserve_part_key!r}")


def _phase6_box_body_piece_solver_key(body_part, region, *, require_flat_uv):
    """Resolve a Box Body Joint region to one physical piece solver key.

    Multi-piece structures may expose an aggregate world solid for preserve-side
    collision checks, but relief/backprojection requires one unambiguous piece UV
    plane.  This adapter deliberately maps only stable physical region names.
    """
    pieces = tuple(getattr(getattr(body_part, "render_data", None), "pieces", ()) or ())
    if not pieces:
        return "box_body"
    by_role = {str(getattr(piece, "role", "") or "").strip().lower(): piece for piece in pieces}
    normalized = str(region or "").strip().lower().replace("-", "_").replace(" ", "_")

    role = None
    if normalized in {"rear_mating", "rear_panel", "back", "back_panel", "rear", "outer_surface", "wrap_zone"}:
        role = "back"
    elif normalized in {"left_mating", "left_mating_zone", "left_side", "left", "top_left", "bottom_left"}:
        role = "left_side"
    elif normalized in {"right_mating", "right_mating_zone", "right_side", "right", "top_right", "bottom_right"}:
        role = "right_side"

    if role is not None and role in by_role:
        return f"box_body:{role}"
    if require_flat_uv:
        raise ValueError(
            f"piece-level relief region is ambiguous for multi-piece Box Body: {region!r}"
        )
    return "box_body"


def _phase6_build_joint_world_geometry(parts, finished_dimensions, sheet_thickness):
    """Build Joint Solver v2 world/UV maps from canonical AssemblyScenePart objects.

    Multi-piece Box Body structures expose one world-space aggregate for preserve
    checks plus one UV-aware entry per physical piece.  The aggregate intentionally
    has no flat-material map: unrelated piece UV planes must never be forged into a
    single backprojection coordinate system.
    """
    from ae_engine.assembly_geometry import (
        folded_mesh_with_flat_uv_from_polygon,
        world_skin_with_flat_uv, endcap_world_skin_with_flat_uv,
        place_assembly_triangles, place_assembly_points,
        place_box_body_structure_points, MappedSkinTriangle, _triangle_unit_normal,
    )

    by_key = {str(part.part_key): part for part in tuple(parts or ())}
    flat_material_by_part = {}
    mapped_skin_triangles_by_part = {}
    world_triangles_by_part = {}
    body_world_mid = ()

    body = by_key.get("box_body")
    if body is not None:
        body_pieces = tuple(getattr(body.render_data, "pieces", ()) or ())
        if body_pieces:
            total_w = max(float(getattr(piece, "formed_w_end", 0.0)) for piece in body_pieces)
            mapped_rows = []
            structure_mid = []
            piece_counts = []
            for piece in body_pieces:
                data = piece.render_data
                _minx, miny, _maxx, maxy = map(float, data.material.bounds)
                y_profile = ({"len": max(0.0, maxy - miny), "core": True},)
                x_profile = tuple(getattr(piece, "fold_profile", ()) or ())
                mapped = folded_mesh_with_flat_uv_from_polygon(
                    data.material, x_profile, y_profile,
                    fold_guides=tuple(getattr(data, "fold_guides", ()) or ()),
                )
                piece_structure = []
                for item in mapped:
                    placed = place_box_body_structure_points(
                        item.local, piece, total_w=total_w,
                        thickness=sheet_thickness, x_profile=x_profile,
                    )
                    piece_structure.append(tuple(placed))
                mapped_rows.append((piece, tuple(mapped), tuple(piece_structure)))
                structure_mid.extend(piece_structure)
                piece_counts.append(len(piece_structure))

            structure_mid = tuple(structure_mid)
            if structure_mid:
                all_points = [point for tri in structure_mid for point in tri]
                placed_points = place_assembly_points(
                    all_points, structure_mid, body.placement,
                    finished_dimensions, body.offset,
                )
                body_world_mid = tuple(
                    tuple(placed_points[i:i + 3])
                    for i in range(0, len(placed_points), 3)
                )

            half = max(0.0, float(sheet_thickness or 0.0)) / 2.0
            cursor = 0
            aggregate_skins = []
            for piece, mapped, _piece_structure in mapped_rows:
                count = len(mapped)
                world_mid_piece = body_world_mid[cursor:cursor + count]
                cursor += count
                skins = []
                for item, world_mid in zip(mapped, world_mid_piece):
                    normal = _triangle_unit_normal(world_mid)
                    if normal is None:
                        continue
                    for side in (-1, 1):
                        delta = tuple(float(side) * half * value for value in normal)
                        world = tuple(
                            tuple(float(point[i]) + delta[i] for i in range(3))
                            for point in world_mid
                        )
                        skins.append(MappedSkinTriangle(flat=item.flat, world=world, side=side))
                piece_key = f"box_body:{str(getattr(piece, 'role', '') or '').strip().lower()}"
                flat_material_by_part[piece_key] = piece.render_data.material
                mapped_skin_triangles_by_part[piece_key] = tuple(skins)
                world_triangles_by_part[piece_key] = tuple(item.world for item in skins)
                aggregate_skins.extend(item.world for item in skins)
            world_triangles_by_part["box_body"] = tuple(aggregate_skins)
        else:
            mapped = folded_mesh_with_flat_uv_from_polygon(
                body.render_data.material, tuple(body.x_profile or ()), tuple(body.y_profile or ()),
                fold_guides=tuple(getattr(body.render_data, "fold_guides", ()) or ()),
            )
            body_world_mid = place_assembly_triangles(
                tuple(item.local for item in mapped), body.placement, finished_dimensions, body.offset
            )
            skins = world_skin_with_flat_uv(
                mapped, body.placement, finished_dimensions, offset=body.offset,
                sheet_thickness=sheet_thickness,
            )
            flat_material_by_part["box_body"] = body.render_data.material
            mapped_skin_triangles_by_part["box_body"] = tuple(skins)
            world_triangles_by_part["box_body"] = tuple(item.world for item in skins)

    for key, part in by_key.items():
        if key == "box_body" or getattr(part.render_data, "pieces", None):
            continue
        mapped = folded_mesh_with_flat_uv_from_polygon(
            part.render_data.material, tuple(part.x_profile or ()), tuple(part.y_profile or ()),
            fold_guides=tuple(getattr(part.render_data, "fold_guides", ()) or ()),
        )
        placement = str(part.placement or "offset")
        if placement in {"top", "head", "bottom", "tail"} and body_world_mid:
            skins = endcap_world_skin_with_flat_uv(
                mapped, placement, body_world_mid, offset=part.offset,
                sheet_thickness=sheet_thickness,
                reference_triangles=tuple(item.local for item in mapped),
                preserve_core_origin=True,
            )
        else:
            skins = world_skin_with_flat_uv(
                mapped, placement, finished_dimensions, offset=part.offset,
                sheet_thickness=sheet_thickness,
            )
        flat_material_by_part[key] = part.render_data.material
        mapped_skin_triangles_by_part[key] = tuple(skins)
        world_triangles_by_part[key] = tuple(item.world for item in skins)

    return {
        "flat_material_by_part": flat_material_by_part,
        "mapped_skin_triangles_by_part": mapped_skin_triangles_by_part,
        "world_triangles_by_part": world_triangles_by_part,
    }



def _phase6_joint_relief_state_item_matches(item, joint, source_material):
    """Return True only when a persisted provisional cut still targets the same raw geometry."""
    if not isinstance(item, dict):
        return False
    relation = str(getattr(getattr(joint, "relation", None), "value", getattr(joint, "relation", "")))
    if (
        str(item.get("joint_id") or "") != str(joint.joint_id)
        or str(item.get("subject_part") or "") != str(joint.subject_part)
        or str(item.get("target_part") or "") != str(joint.target_part)
        or str(item.get("relation") or "") != relation
        or not bool(item.get("verified"))
    ):
        return False
    try:
        saved_bounds = tuple(float(v) for v in item.get("source_material_bounds", ()))
        saved_area = float(item.get("source_material_area"))
        current_bounds = tuple(float(v) for v in source_material.bounds)
        current_area = float(source_material.area)
    except Exception:
        return False
    return len(saved_bounds) == 4 and all(abs(a-b) <= 1e-6 for a,b in zip(saved_bounds,current_bounds)) and abs(saved_area-current_area) <= 1e-6


def _phase6_cut_geometry_from_state_item(item):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polygons = []
    for coords in tuple((item or {}).get("cut_polygons", ()) or ()):
        try:
            polygon = Polygon([(float(x), float(y)) for x, y in coords])
        except Exception:
            continue
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty and float(polygon.area) > 1e-9:
            polygons.append(polygon)
    return unary_union(polygons) if polygons else None


def _phase6_resolve_explicit_joint_reliefs(
    parts, joints, *, finished_dimensions, sheet_thickness, clearance=0.0,
    committed_state=None,
):
    """Resolve USER_ADDED Joint reliefs against canonical parts.

    Safety rules:
    - WRAP preserves the wrapper (subject) and may only cut the wrapped target.
    - Persisted provisional cuts replay only when the raw relief-owner material
      fingerprint still matches; dimensional edits invalidate them.
    - 3D discovery requires an explicit physical corner and topology contract.
      Generic mating regions remain diagnostic-only (UNFITTED_REGION).
    - A discovered cut is committed only after replay proves zero illegal
      penetration.  No candidate is promoted to CERTIFIED here.
    """
    from types import SimpleNamespace
    from ae_engine.assembly_joint import AssemblyJointSource
    from ae_engine.assembly_collision import (
        discover_joint_relief_candidate, verify_joint_candidate_replay,
        joint_relief_ownership, project_joint_interference_to_relief_owner,
    )
    from ae_engine.contracts import ResolvedJointDiagnostic

    current = {str(part.part_key): part for part in tuple(parts or ())}
    diagnostics = []
    old_items = dict((committed_state or {}).get("items", {}) or {}) if isinstance(committed_state, dict) else {}
    new_state = {"schema_version": 1, "items": {}}

    explicit = [
        joint for joint in tuple(joints or ())
        if str(getattr(getattr(joint, "source", None), "value", getattr(joint, "source", "")))
        == AssemblyJointSource.USER_ADDED.value
    ]

    def world_direction_segment(world_map, joint):
        def centroid(part_key):
            tris = tuple((world_map or {}).get(str(part_key), ()) or ())
            points = [p for tri in tris for p in tri if isinstance(p, (tuple, list)) and len(p) >= 3]
            if not points:
                return None
            try:
                return tuple(sum(float(p[i]) for p in points) / len(points) for i in range(3))
            except (TypeError, ValueError):
                return None
        a = centroid(joint.subject_part); b = centroid(joint.target_part)
        return (a, b) if a is not None and b is not None else None

    for joint in explicit:
        ownership = joint_relief_ownership(joint)
        relief_key = str(ownership.relief_part)
        preserve_key = str(ownership.preserve_part)
        relief_part = current.get(relief_key)
        preserve_part = current.get(preserve_key)
        relation = str(getattr(getattr(joint, "relation", None), "value", getattr(joint, "relation", "")))
        source = str(getattr(getattr(joint, "source", None), "value", getattr(joint, "source", "")))
        if relief_part is None or preserve_part is None:
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="MISSING_PART_GEOMETRY", illegal_penetration=False,
                evidence={"reason":"JOINT_ENDPOINT_NOT_IN_CANONICAL_PARTS"},
            ))
            continue
        edge = str(getattr(joint, "edge", "") or "").strip().upper()
        is_piece_side_wrap = (
            relation == "WRAP"
            and relief_key == "box_body"
            and bool(getattr(relief_part.render_data, "pieces", None))
            and preserve_key in {"head", "tail"}
            and edge in {"LEFT", "RIGHT"}
        )
        if is_piece_side_wrap:
            from shapely.ops import unary_union

            try:
                if relief_key == str(joint.target_part):
                    relief_region = str(getattr(joint, "target_region", "") or "")
                else:
                    relief_region = str(getattr(joint, "subject_region", "") or "")
                relief_geometry_key = _phase6_box_body_piece_solver_key(
                    relief_part, relief_region or f"{edge.lower()}_mating_zone", require_flat_uv=True
                )
                raw_world = _phase6_build_joint_world_geometry(
                    tuple(current.values()), finished_dimensions, sheet_thickness
                )
                raw_material = raw_world["flat_material_by_part"][relief_geometry_key]
            except Exception as exc:
                diagnostics.append(ResolvedJointDiagnostic(
                    joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                    relation=relation, source=source, registry_status="MISS",
                    preserve_part=preserve_key, relief_part=relief_key,
                    candidate_status="PIECE_LEVEL_UV_UNAVAILABLE", illegal_penetration=True,
                    evidence={"reason":str(exc)},
                ))
                continue

            saved = old_items.get(str(joint.joint_id))
            if (
                str((saved or {}).get("relief_geometry_key") or "") == relief_geometry_key
                and _phase6_joint_relief_state_item_matches(saved, joint, raw_material)
            ):
                cut = _phase6_cut_geometry_from_state_item(saved)
                if cut is not None and not getattr(cut, "is_empty", True):
                    current[relief_key] = _phase6_apply_resolved_cut_to_owner(
                        current[relief_key], relief_geometry_key, cut
                    )
                    replayed = dict(saved)
                    replayed["trust_level"] = "PROVISIONAL_3D"
                    new_state["items"][str(joint.joint_id)] = replayed
                    diagnostics.append(ResolvedJointDiagnostic(
                        joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                        relation=relation, source=source, registry_status="MISS", trust_level="PROVISIONAL_3D",
                        preserve_part=preserve_key, relief_part=relief_key, candidate_status="PROVISIONAL_3D_REPLAYED",
                        legal_contact=True, illegal_penetration=False,
                        pre_pair_count=int(dict(saved.get("evidence", {}) or {}).get("pre_pair_count", 0) or 0),
                        post_pair_count=int(dict(saved.get("evidence", {}) or {}).get("post_pair_count", 0) or 0),
                        relief_segments=tuple(), evidence={"replayed":True, **dict(saved.get("evidence", {}) or {})},
                    ))
                    continue

            target_corners = _phase6_side_wrap_target_corners(preserve_key)
            base_relief_part = current[relief_key]
            working_world = raw_world
            accumulated_cut_polygons = []
            all_projection_segments = []
            pre_pairs = 0
            post_pairs = 0
            solver_iterations = 0
            proposed_relief = None
            residual = None
            failure_status = None
            failure_reason = ""
            no_initial_penetration = False
            max_iterations = 32
            progress_tolerance = 1e-7
            previous_cut_area = 0.0

            while solver_iterations < max_iterations:
                solver_iterations += 1
                working_material = working_world["flat_material_by_part"].get(relief_geometry_key)
                if working_material is None or getattr(working_material, "is_empty", True):
                    failure_status = "PIECE_LEVEL_UV_UNAVAILABLE"
                    failure_reason = f"missing working material: {relief_geometry_key}"
                    break

                round_candidates = []
                blocked_candidate = None
                try:
                    for corner_name in target_corners:
                        candidate = discover_joint_relief_candidate(
                            joint,
                            world_triangles_by_part=working_world["world_triangles_by_part"],
                            mapped_skin_triangles_by_part=working_world["mapped_skin_triangles_by_part"],
                            flat_material_by_part=working_world["flat_material_by_part"],
                            topology_levels=None,
                            relief_component=working_material,
                            clearance=float(clearance),
                            relief_geometry_key=relief_geometry_key,
                            source_geometry_key=preserve_key,
                            corner_name_override=corner_name,
                        )
                        projection = getattr(candidate, "projection", None)
                        flat_projection = getattr(projection, "projection", None)
                        pair_count = int(getattr(flat_projection, "pair_count", 0) or 0)
                        if solver_iterations == 1:
                            pre_pairs = max(pre_pairs, pair_count)
                        all_projection_segments.extend(tuple(getattr(flat_projection, "segments_world", ()) or ()))
                        status = str(getattr(candidate, "status", "UNKNOWN") or "UNKNOWN")
                        if status == "CANDIDATE":
                            round_candidates.append(candidate)
                        elif bool(getattr(projection, "illegal_penetration", False)):
                            blocked_candidate = candidate
                            break
                except Exception as exc:
                    failure_status = "DISCOVERY_FAILED"
                    failure_reason = str(exc)
                    break

                if blocked_candidate is not None:
                    failure_status = str(getattr(blocked_candidate, "status", "UNKNOWN") or "UNKNOWN")
                    failure_reason = str(dict(getattr(blocked_candidate, "evidence", {}) or {}).get("reason") or "ILLEGAL_UNFITTED_REGION")
                    break

                if not round_candidates:
                    if solver_iterations == 1:
                        no_initial_penetration = True
                    else:
                        failure_status = "REPLAY_FAILED"
                        failure_reason = "RESIDUAL_ILLEGAL_PENETRATION_WITHOUT_NEW_CANDIDATE"
                    break

                round_cut_polygons = tuple(
                    candidate.cut_polygon_2d for candidate in round_candidates
                    if getattr(candidate, "cut_polygon_2d", None) is not None
                    and not getattr(candidate.cut_polygon_2d, "is_empty", True)
                )
                if not round_cut_polygons:
                    failure_status = "FIT_FAILED"
                    failure_reason = "CANDIDATE_WITHOUT_CUT"
                    break
                accumulated_cut_polygons.extend(round_cut_polygons)
                atomic_cut = unary_union(tuple(accumulated_cut_polygons))
                cut_area = float(getattr(atomic_cut, "area", 0.0) or 0.0)
                if cut_area <= previous_cut_area + progress_tolerance:
                    failure_status = "REPLAY_FAILED"
                    failure_reason = "NO_GEOMETRIC_PROGRESS"
                    break
                previous_cut_area = cut_area

                try:
                    # Every iteration replays the complete union against the exact
                    # pre-cut owner.  This keeps the two physical end corners atomic
                    # and prevents one discovery from seeing the other one's partial cut.
                    proposed_relief = _phase6_apply_resolved_cut_to_owner(
                        base_relief_part, relief_geometry_key, atomic_cut
                    )
                    proposed_parts = tuple(
                        proposed_relief if key == relief_key else value
                        for key, value in current.items()
                    )
                    proposed_world = _phase6_build_joint_world_geometry(
                        proposed_parts, finished_dimensions, sheet_thickness
                    )
                    residual = project_joint_interference_to_relief_owner(
                        joint,
                        world_triangles_by_part=proposed_world["world_triangles_by_part"],
                        mapped_skin_triangles_by_part=proposed_world["mapped_skin_triangles_by_part"],
                        flat_material_by_part=proposed_world["flat_material_by_part"],
                        relief_geometry_key=relief_geometry_key,
                        source_geometry_key=preserve_key,
                    )
                except Exception as exc:
                    failure_status = "REPLAY_FAILED"
                    failure_reason = str(exc)
                    residual = None
                    break

                residual_projection = getattr(residual, "projection", None)
                post_pairs = int(getattr(residual_projection, "pair_count", 0) or 0)
                if not bool(getattr(residual, "illegal_penetration", False)):
                    break
                working_world = proposed_world
            else:
                failure_status = "REPLAY_FAILED"
                failure_reason = "FIXED_POINT_MAX_ITERATIONS"

            direction_segment = world_direction_segment(raw_world.get("world_triangles_by_part", {}), joint)
            if no_initial_penetration:
                diagnostics.append(ResolvedJointDiagnostic(
                    joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                    relation=relation, source=source, registry_status="MISS",
                    preserve_part=preserve_key, relief_part=relief_key, candidate_status="NO_ILLEGAL_PENETRATION",
                    legal_contact=True, illegal_penetration=False, pre_pair_count=pre_pairs, post_pair_count=pre_pairs,
                    contact_segments=tuple(all_projection_segments), direction_segment=direction_segment,
                    evidence={
                        "relief_geometry_key":relief_geometry_key,
                        "corner_names":list(target_corners),
                        "solver_iterations":solver_iterations,
                    },
                ))
                continue

            if failure_status is not None or residual is None or bool(getattr(residual, "illegal_penetration", False)):
                residual_projection = getattr(residual, "projection", None) if residual is not None else None
                diagnostics.append(ResolvedJointDiagnostic(
                    joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                    relation=relation, source=source, registry_status="MISS", preserve_part=preserve_key, relief_part=relief_key,
                    candidate_status=str(failure_status or "REPLAY_FAILED"), illegal_penetration=True, pre_pair_count=pre_pairs,
                    post_pair_count=int(getattr(residual_projection, "pair_count", post_pairs or pre_pairs) or 0),
                    penetration_segments=tuple(all_projection_segments), direction_segment=direction_segment,
                    evidence={
                        "reason":failure_reason or "RESIDUAL_ILLEGAL_PENETRATION",
                        "relief_geometry_key":relief_geometry_key,
                        "solver_iterations":solver_iterations,
                    },
                ))
                continue

            current[relief_key] = proposed_relief
            corner_names = tuple(target_corners)
            state_item = {
                "joint_id":str(joint.joint_id), "subject_part":str(joint.subject_part),
                "target_part":str(joint.target_part), "relation":relation, "source":source,
                "relief_part":relief_key, "relief_geometry_key":relief_geometry_key,
                "topology_levels":None, "verified":True, "trust_level":"PROVISIONAL_3D",
                "corner_names":list(corner_names),
                "source_material_bounds":[float(v) for v in raw_material.bounds],
                "source_material_area":float(raw_material.area),
                "cut_polygons":[
                    coords
                    for polygon in tuple(accumulated_cut_polygons)
                    for coords in _phase6_relief_polygon_coords(polygon)
                ],
                "evidence":{
                    "pre_pair_count":pre_pairs, "post_pair_count":post_pairs,
                    "post_illegal_penetration":False,
                    "relief_geometry_key":relief_geometry_key,
                    "corner_names":list(corner_names),
                    "solver_iterations":solver_iterations,
                    "policy":"ATOMIC_MULTI_CORNER_FIXED_POINT_REPLAY_AND_ZERO_ILLEGAL_PENETRATION",
                },
            }
            new_state["items"][str(joint.joint_id)] = state_item
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS", trust_level="PROVISIONAL_3D",
                preserve_part=preserve_key, relief_part=relief_key, candidate_status="PROVISIONAL_3D",
                legal_contact=bool(getattr(residual, "has_contact", False)), illegal_penetration=False,
                pre_pair_count=pre_pairs, post_pair_count=post_pairs,
                penetration_segments=tuple(all_projection_segments), relief_segments=tuple(all_projection_segments),
                preserve_segments=tuple(all_projection_segments), direction_segment=direction_segment,
                evidence=deepcopy(state_item["evidence"]),
            ))
            continue

        if getattr(relief_part.render_data, "pieces", None) or getattr(preserve_part.render_data, "pieces", None):
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="PIECE_LEVEL_UV_UNAVAILABLE",
                evidence={"reason":"MULTI_PIECE_PART_REQUIRES_PIECE_LEVEL_UV_ADAPTER"},
            ))
            continue

        raw_material = relief_part.render_data.material
        saved = old_items.get(str(joint.joint_id))
        if _phase6_joint_relief_state_item_matches(saved, joint, raw_material):
            cut = _phase6_cut_geometry_from_state_item(saved)
            if cut is not None and not getattr(cut, "is_empty", True):
                solved_part = _phase6_apply_resolved_cut_to_part(relief_part, cut)
                current[relief_key] = solved_part
                replayed = dict(saved)
                replayed["trust_level"] = "PROVISIONAL_3D"
                new_state["items"][str(joint.joint_id)] = replayed
                diagnostics.append(ResolvedJointDiagnostic(
                    joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                    relation=relation, source=source, registry_status="MISS", trust_level="PROVISIONAL_3D",
                    preserve_part=preserve_key, relief_part=relief_key,
                    candidate_status="PROVISIONAL_3D_REPLAYED", legal_contact=True, illegal_penetration=False,
                    pre_pair_count=int(dict(saved.get("evidence", {}) or {}).get("pre_pair_count", 0) or 0),
                    post_pair_count=int(dict(saved.get("evidence", {}) or {}).get("post_pair_count", 0) or 0),
                    relief_segments=tuple(), evidence={"replayed":True, **dict(saved.get("evidence", {}) or {})},
                ))
                continue

        constraints = dict(getattr(joint, "solver_constraints", {}) or {})
        topology_raw = constraints.get("topology_levels")
        try:
            topology_levels = int(topology_raw)
        except Exception:
            topology_levels = 0
        if topology_levels not in (1, 2):
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="TOPOLOGY_UNSPECIFIED", illegal_penetration=False,
                evidence={"reason":"EXPLICIT_TOPOLOGY_LEVEL_REQUIRED_FOR_DISCOVERY"},
            ))
            continue
        if topology_levels == 2:
            # A two-stage search domain must come from a certified/known topology
            # component.  Never invent a second band from raw intersection data.
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="TWO_STAGE_COMPONENT_REQUIRED", illegal_penetration=False,
                evidence={"reason":"CERTIFIED_TWO_STAGE_TOPOLOGY_COMPONENT_REQUIRED"},
            ))
            continue

        try:
            world = _phase6_build_joint_world_geometry(tuple(current.values()), finished_dimensions, sheet_thickness)
            candidate = discover_joint_relief_candidate(
                joint,
                world_triangles_by_part=world["world_triangles_by_part"],
                mapped_skin_triangles_by_part=world["mapped_skin_triangles_by_part"],
                flat_material_by_part=world["flat_material_by_part"],
                topology_levels=topology_levels,
                relief_component=raw_material,
                clearance=float(clearance),
            )
        except Exception as exc:
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="DISCOVERY_FAILED", illegal_penetration=True,
                evidence={"reason":str(exc)},
            ))
            continue

        projection = getattr(candidate, "projection", None)
        flat_projection = getattr(projection, "projection", None)
        pre_pairs = int(getattr(flat_projection, "pair_count", 0) or 0)
        penetration_segments = tuple(getattr(flat_projection, "segments_world", ()) or ())
        direction_segment = world_direction_segment(world.get("world_triangles_by_part", {}), joint)
        status = str(getattr(candidate, "status", "UNKNOWN") or "UNKNOWN")
        if status != "CANDIDATE":
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key, candidate_status=status,
                legal_contact=bool(getattr(projection, "has_contact", False) and not getattr(projection, "illegal_penetration", False)),
                illegal_penetration=bool(getattr(projection, "illegal_penetration", False)),
                pre_pair_count=pre_pairs, post_pair_count=pre_pairs,
                penetration_segments=penetration_segments,
                contact_segments=(penetration_segments if bool(getattr(projection, "has_contact", False)) and not bool(getattr(projection, "illegal_penetration", False)) else ()),
                direction_segment=direction_segment,
                evidence=dict(getattr(candidate, "evidence", {}) or {}),
            ))
            continue

        def rebuild_mapped_skins(part_key, solved_material):
            base = current[str(part_key)]
            temp_render = SimpleNamespace(
                scene=base.render_data.scene, material=solved_material,
                fold_guides=tuple(getattr(base.render_data, "fold_guides", ()) or ()), metadata={},
            )
            temp_part = AssemblyScenePart(
                part_key=base.part_key, render_data=temp_render,
                x_profile=base.x_profile, y_profile=base.y_profile,
                placement=base.placement, offset=base.offset,
            )
            temp_parts = tuple(temp_part if key == str(part_key) else value for key, value in current.items())
            rebuilt = _phase6_build_joint_world_geometry(temp_parts, finished_dimensions, sheet_thickness)
            return tuple(rebuilt["mapped_skin_triangles_by_part"].get(str(part_key), ()) or ())

        try:
            verification = verify_joint_candidate_replay(
                joint, candidate,
                world_triangles_by_part=world["world_triangles_by_part"],
                flat_material_by_part=world["flat_material_by_part"],
                rebuild_mapped_skins=rebuild_mapped_skins,
            )
        except Exception as exc:
            verification = None
            verify_error = str(exc)
        else:
            verify_error = ""
        if verification is None or not bool(getattr(verification, "verified", False)):
            residual = getattr(verification, "residual", None) if verification is not None else None
            residual_projection = getattr(residual, "projection", None)
            post_pairs = int(getattr(residual_projection, "pair_count", pre_pairs) or 0)
            diagnostics.append(ResolvedJointDiagnostic(
                joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
                relation=relation, source=source, registry_status="MISS",
                preserve_part=preserve_key, relief_part=relief_key,
                candidate_status="REPLAY_FAILED", illegal_penetration=True,
                pre_pair_count=pre_pairs, post_pair_count=post_pairs,
                penetration_segments=penetration_segments,
                direction_segment=direction_segment,
                evidence={"reason":verify_error or "RESIDUAL_ILLEGAL_PENETRATION"},
            ))
            continue

        cut = candidate.cut_polygon_2d
        current[relief_key] = _phase6_apply_resolved_cut_to_part(current[relief_key], cut)
        residual = verification.residual
        residual_projection = getattr(residual, "projection", None)
        post_pairs = int(getattr(residual_projection, "pair_count", 0) or 0)
        measurement = getattr(getattr(candidate, "corner_relief", None), "measurement", None)
        state_item = {
            "joint_id": str(joint.joint_id),
            "subject_part": str(joint.subject_part), "target_part": str(joint.target_part),
            "relation": relation, "source": source, "relief_part": relief_key,
            "topology_levels": topology_levels, "verified": True,
            "trust_level": "PROVISIONAL_3D",
            "corner_name": str(getattr(measurement, "corner_name", "") or ""),
            "source_material_bounds": [float(v) for v in raw_material.bounds],
            "source_material_area": float(raw_material.area),
            "cut_polygons": _phase6_relief_polygon_coords(cut),
            "evidence": {**dict(getattr(candidate, "evidence", {}) or {}), **dict(getattr(verification, "evidence", {}) or {})},
        }
        new_state["items"][str(joint.joint_id)] = state_item
        diagnostics.append(ResolvedJointDiagnostic(
            joint_id=str(joint.joint_id), subject_part=str(joint.subject_part), target_part=str(joint.target_part),
            relation=relation, source=source, registry_status="MISS", trust_level="PROVISIONAL_3D",
            preserve_part=preserve_key, relief_part=relief_key, candidate_status="PROVISIONAL_3D",
            legal_contact=bool(getattr(residual, "has_contact", False)), illegal_penetration=False,
            pre_pair_count=pre_pairs, post_pair_count=post_pairs,
            penetration_segments=penetration_segments,
            relief_segments=penetration_segments,
            preserve_segments=penetration_segments,
            direction_segment=direction_segment,
            evidence=deepcopy(state_item["evidence"]),
        ))

    ordered = tuple(current[str(part.part_key)] for part in tuple(parts or ()))
    return ordered, tuple(diagnostics), new_state

def _phase6_signature_canonical_value(value):
    """Normalize representation-only differences before manufacturing caching."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 12)
    if isinstance(value, Mapping):
        return {str(key): _phase6_signature_canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_phase6_signature_canonical_value(item) for item in value)
    if isinstance(value, set):
        normalized = [_phase6_signature_canonical_value(item) for item in value]
        return tuple(sorted(normalized, key=repr))
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _phase6_signature_canonical_value(enum_value)
    return repr(value)


def _phase6_manufacturing_state_signature(self):
    """Stable key for canonical manufacturing inputs; persistence/view mirrors excluded."""
    workspace = getattr(self, "designer_workspace", None)
    available = tuple(getattr(workspace, "available_parts", ()) or ())
    profiles = {}
    if workspace is not None:
        for key in available:
            try:
                profiles[key] = deepcopy(workspace.profiles_for(key, {}) or {})
            except Exception:
                profiles[key] = {}

    settings = deepcopy(dict(getattr(self, "_settings_values", {}) or {}))
    # Typography is UI-only and must never invalidate canonical manufacturing.
    settings.pop("ui_text_size", None)
    snapshot = deepcopy(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    # These fields are either owned independently below or derived/persistence
    # mirrors. Saving an unchanged editor may materialize them, but that is not a
    # manufacturing mutation and must not destroy an otherwise valid cache hit.
    mirror_keys = set(settings) | {
        "settings", "endcap_fw", "endcap_bottom_wrap", "assembly_type",
        "corner_state", "corner_pair_same", "active_part", "part_dimensions",
    }
    snapshot = {key: value for key, value in snapshot.items() if key not in mirror_keys}

    state = (
        snapshot,
        settings,
        deepcopy(dict(getattr(self, "_phase6_box_whd", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_corner_state", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_endcap_fw_state", {}) or {})),
        deepcopy(dict(getattr(self, "_phase6_endcap_bottom_wrap_state", {}) or {})),
        available,
        profiles,
        getattr(getattr(self, "_phase6_assembly_type", None), "value", getattr(self, "_phase6_assembly_type", None)),
        bool(getattr(getattr(self, "assembly_ignore_fixed_corner_var", None), "get", lambda: False)()),
        _phase6_assembly_relief_clearance(self),
    )
    return stable_fingerprint(_phase6_signature_canonical_value(state))


def _phase6_joint_registry_diagnostic_info(joint, render_by_part, solution_by_part):
    """Resolve registry/verification evidence for exactly one AssemblyJoint."""
    edge = str(getattr(joint, "edge", "") or "").upper()
    relation = str(getattr(getattr(joint, "relation", None), "value", getattr(joint, "relation", "")) or "")
    endcap_part = next((p for p in (str(getattr(joint, "subject_part", "")), str(getattr(joint, "target_part", ""))) if p in ENDCAP_FW_PARTS), "")

    if edge == "BOTTOM":
        if relation == "WRAP" and endcap_part:
            render = render_by_part.get(endcap_part)
            trace = dict(dict(getattr(render, "metadata", {}) or {}).get("receiving_bottom_relief_rule") or {})
            if trace:
                evidence = deepcopy(trace.get("geometry_evidence") or {})
                return {
                    "registry_status": "HIT",
                    "rule_id": trace.get("rule_id"),
                    "revision": trace.get("revision"),
                    "trust_level": str(trace.get("trust_level") or ""),
                    "candidate_status": "CERTIFIED",
                    "verified": True,
                    "pre_pair_count": 0,
                    "post_pair_count": 0,
                    "evidence": evidence,
                }
            return {
                "registry_status": "MISS", "rule_id": None, "revision": None,
                "trust_level": "", "candidate_status": "UNSUPPORTED", "verified": False,
                "pre_pair_count": 0, "post_pair_count": 0, "evidence": None,
            }
        # No BOTTOM semantic delta: STANDARD is the canonical mother geometry.
        return {
            "registry_status": "MISS", "rule_id": None, "revision": None,
            "trust_level": "STANDARD", "candidate_status": "STANDARD", "verified": True,
            "pre_pair_count": 0, "post_pair_count": 0, "evidence": {"owner": "STANDARD"},
        }

    solution = solution_by_part.get(endcap_part) if endcap_part else None
    if solution is None:
        return {
            "registry_status": "MISS", "rule_id": None, "revision": None,
            "trust_level": "", "candidate_status": "UNKNOWN", "verified": False,
            "pre_pair_count": 0, "post_pair_count": 0, "evidence": None,
        }
    rule_id = getattr(solution, "rule_id", None)
    pre_pairs = sum(int(getattr(p, "pair_count", 0) or 0) for p in tuple(getattr(solution, "projections", ()) or ()))
    post_pairs = int(getattr(getattr(solution, "residual_projection", None), "pair_count", 0) or 0)
    trust = str(getattr(solution, "trust_level", "") or "")
    return {
        "registry_status": "HIT" if rule_id else "MISS",
        "rule_id": rule_id,
        "revision": getattr(solution, "rule_revision", None),
        "trust_level": trust,
        "candidate_status": "CERTIFIED" if rule_id else trust,
        "verified": bool(getattr(solution, "verified", False)),
        "pre_pair_count": pre_pairs, "post_pair_count": post_pairs,
        "evidence": deepcopy(getattr(solution, "shadow_validation", None)),
    }


def _phase6_resolve_manufacturing_geometry(self):
    """Resolve one canonical manufacturing result consumed by every downstream view/export."""
    signature = _phase6_manufacturing_state_signature(self)
    cached = getattr(self, "_phase6_last_resolved_manufacturing_geometry", None)
    if cached is not None and signature == getattr(self, "_phase6_last_resolved_manufacturing_signature", None):
        return cached
    callback = getattr(self, "_scene_query_callback", None)
    if callback is None:
        raise RuntimeError("3D final-scene provider is not connected")

    fallback_var = getattr(self, "assembly_ignore_fixed_corner_var", None)
    fallback_enabled = bool(fallback_var.get()) if fallback_var is not None else False
    available = set(self.designer_workspace.available_parts)
    snapshot_for_joints = migrate_legacy_snapshot_joints(dict(getattr(self, "_phase6_input_snapshot", {}) or {}))
    joints = tuple(
        raw if isinstance(raw, AssemblyJoint) else AssemblyJoint.from_dict(raw)
        for raw in tuple(snapshot_for_joints.get("assembly_joints", ()) or ())
        if str(getattr(raw, "subject_part", raw.get("subject_part", "") if isinstance(raw, dict) else "")) in available
        and str(getattr(raw, "target_part", raw.get("target_part", "") if isinstance(raw, dict) else "")) in available
    )
    resolved_joint_graph = ResolvedAssemblyGraph(tuple(sorted(available)), joints)
    parts = []
    for key in self.designer_workspace.available_parts:
        if key not in available:
            continue
        payload = _phase6_scene_query_payload_for_part(self, key)
        # Solver base must be pre-dynamic-relief material. If solving is off,
        # display the current canonical committed relief directly.
        payload["_use_committed_relief"] = False
        render_data = callback(key, payload)
        if render_data is None:
            raise ValueError(f"manufacturing render data unavailable: {key}")
        if getattr(render_data, "pieces", None):
            x_profile, y_profile = (), ()
        else:
            if getattr(render_data, "scene", None) is None or getattr(render_data, "material", None) is None:
                raise TypeError("manufacturing render provider must return scene + material or physical pieces")
            x_profile, y_profile = _phase6_mesh_profiles_for_part(self, key, render_data.material)
        placement, offset = _phase6_assembly_placement_for_part(
            getattr(self, "_phase6_input_snapshot", {}) or {}, key
        )
        parts.append(AssemblyScenePart(
            part_key=key, render_data=render_data,
            x_profile=tuple(dict(seg) for seg in x_profile),
            y_profile=tuple(dict(seg) for seg in y_profile),
            placement=placement, offset=offset,
        ))
    if not parts:
        raise ValueError("no parts available for assembly 3D display")

    # Preserve the pre-dynamic-relief EndCap geometry for the collision overlay.
    # Visible parts may be replaced by solved canonical geometry below.
    pre_solve_probe_parts = tuple(
        part for part in parts if part.part_key in {"head", "tail"}
    )

    solutions = {}
    errors = {}
    required = [key for key in ("head", "tail") if key in available]
    if required:
        body_part = next((part for part in parts if part.part_key == "box_body"), None)
        if body_part is not None:
            from ae_engine.assembly_collision import solve_world_backprojected_endcap_relief
            dims = _phase6_operator_finished_dimensions(self)
            snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
            settings = getattr(self, "_settings_values", {}) or {}
            thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
            clearance = _phase6_assembly_relief_clearance(self)
            by_key = {part.part_key: part for part in parts}
            for key in required:
                part = by_key[key]
                try:
                    solution = solve_world_backprojected_endcap_relief(
                        box_body_render_data=body_part.render_data,
                        endcap_render_data=part.render_data,
                        box_body_x_profile=body_part.x_profile,
                        endcap_x_profile=part.x_profile,
                        endcap_y_profile=part.y_profile,
                        finished_dimensions=dims,
                        endcap_placement=part.placement,
                        sheet_thickness=thickness,
                        clearance=clearance,
                        assembly_intent=assembly_intent_value(getattr(self, "_phase6_assembly_type", None)),
                        assembly_graph=resolved_joint_graph,
                        endcap_part=key,
                        cabinet_family=_phase6_current_cabinet_family(self),
                        allow_3d_fallback=fallback_enabled,
                        # Extra USER_ADDED joints are resolved by Solver v2 after
                        # the standard EndCap intent geometry is canonical.  Do
                        # not feed WRAP into the legacy EndCap-only solver: WRAP
                        # owns relief on its target and that solver can only cut
                        # the EndCap subject.
                        assembly_joint=None,
                    )
                    solutions[key] = solution
                    if not bool(getattr(solution, "verified", False)):
                        if _phase6_solution_is_committable(solution):
                            errors[key] = "已認證公式與3D影子驗證衝突；正式結果仍採CERTIFIED公式"
                        else:
                            reason = dict(getattr(solution, "shadow_validation", {}) or {}).get("reason")
                            errors[key] = str(reason or "3D 回折驗證仍有材料穿透")
                except Exception as exc:
                    errors[key] = str(exc)

            atomic_committable = all(
                key in solutions and _phase6_solution_is_committable(solutions[key])
                for key in required
            )
            self._phase6_last_relief_solutions = solutions
            self._phase6_last_relief_errors = errors

            if atomic_committable:
                # Publish both cuts as one canonical state update before any
                # solved geometry is displayed.
                _phase6_publish_live_state(self, force=True)
                solved_parts = []
                for part in parts:
                    if part.part_key not in required:
                        solved_parts.append(part)
                        continue
                    solution = solutions[part.part_key]
                    replay_payload = _phase6_scene_query_payload_for_part(self, part.part_key)
                    replay_payload["_use_committed_relief"] = False
                    replay_payload["resolved_assembly_relief_cuts"] = tuple(
                        tuple((float(x), float(y)) for x, y in polygon)
                        for polygon in _phase6_relief_polygon_coords(
                            getattr(solution, "cut_polygon_2d", None)
                        )
                    )
                    canonical_render = callback(part.part_key, replay_payload)
                    if canonical_render is None or getattr(canonical_render, "material", None) is None:
                        raise ValueError(f"authoritative relief replay unavailable: {part.part_key}")
                    solver_material = getattr(getattr(solution, "solved_render_data", None), "material", None)
                    if solver_material is not None:
                        mismatch = float(canonical_render.material.symmetric_difference(solver_material).area)
                        if mismatch > 1e-5:
                            raise ValueError(
                                f"2D/3D relief replay mismatch: {part.part_key} area={mismatch:.6f}"
                            )
                    solved_parts.append(AssemblyScenePart(
                        part_key=part.part_key, render_data=canonical_render,
                        x_profile=part.x_profile, y_profile=part.y_profile,
                        placement=part.placement, offset=part.offset,
                    ))
                parts = solved_parts
            else:
                # Atomic rollback: display current canonical 2D geometry for
                # BOTH EndCaps. Never show a verified Head with an old Tail.
                canonical_parts = []
                for part in parts:
                    if part.part_key not in required:
                        canonical_parts.append(part)
                        continue
                    payload = _phase6_scene_query_payload_for_part(self, part.part_key)
                    payload["_use_committed_relief"] = True
                    canonical_render = callback(part.part_key, payload)
                    canonical_parts.append(AssemblyScenePart(
                        part_key=part.part_key, render_data=canonical_render,
                        x_profile=part.x_profile, y_profile=part.y_profile,
                        placement=part.placement, offset=part.offset,
                    ))
                parts = canonical_parts
    else:
        self._phase6_last_relief_solutions = {}
        self._phase6_last_relief_errors = {}

    # Resolve extra USER_ADDED joints (including WRAP) only after the high-level
    # EndCap intent has produced canonical parts.  This generalized path can
    # relief either endpoint according to Joint semantics and persists only
    # replay-verified provisional cuts.
    explicit_joint_diagnostics = ()
    explicit_joint_state = {"schema_version": 1, "items": {}}
    if any(
        str(getattr(getattr(joint, "source", None), "value", getattr(joint, "source", ""))) == "USER_ADDED"
        for joint in joints
    ):
        snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
        settings = dict(getattr(self, "_settings_values", {}) or {})
        thickness = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        parts, explicit_joint_diagnostics, explicit_joint_state = _phase6_resolve_explicit_joint_reliefs(
            tuple(parts), joints,
            finished_dimensions=_phase6_operator_finished_dimensions(self),
            sheet_thickness=thickness,
            clearance=_phase6_assembly_relief_clearance(self),
            committed_state=snapshot.get("joint_relief_state"),
        )
        # Runtime state is versioned and serializable; export/save starts from
        # this snapshot, so verified provisional cuts survive reload.
        self._phase6_input_snapshot["joint_relief_state"] = deepcopy(explicit_joint_state)

    from ae_engine.contracts import (
        ResolvedManufacturingGeometry, ResolvedManufacturingPart, ResolvedReliefRuleTrace,
    )
    resolved_parts = tuple(
        ResolvedManufacturingPart(
            part_key=part.part_key,
            render_data=part.render_data,
            x_profile=tuple(dict(seg) for seg in tuple(part.x_profile or ())),
            y_profile=tuple(dict(seg) for seg in tuple(part.y_profile or ())),
            placement=part.placement,
            offset=tuple(part.offset),
        )
        for part in parts
    )
    traces = []
    solution_by_part = dict(solutions or {})
    for part_key, solution in solution_by_part.items():
        trust = str(getattr(solution, "trust_level", "") or "")
        rule_id = getattr(solution, "rule_id", None)
        revision = getattr(solution, "rule_revision", None)
        for relief in tuple(getattr(solution, "corner_reliefs", ()) or ()):
            shadow = dict(getattr(solution, "shadow_validation", {}) or {})
            traces.append(ResolvedReliefRuleTrace(
                part_key=str(part_key),
                corner_name=str(getattr(relief, "corner_name", "") or ""),
                rule_id=rule_id,
                revision=revision,
                trust_level=trust,
                signature=str(getattr(relief, "signature", "") or ""),
                geometry_inputs=tuple(str(v) for v in shadow.get("geometry_inputs", ()) or ()),
                geometry_evidence=deepcopy(shadow.get("geometry_evidence")),
            ))

    # Family-specific BOTTOM certified traces live on the canonical FinalScene
    # metadata because they are resolved while building the EndCap PartSpec.
    for resolved_part in resolved_parts:
        metadata = dict(getattr(resolved_part.render_data, "metadata", {}) or {})
        bottom_trace = dict(metadata.get("receiving_bottom_relief_rule") or {})
        if not bottom_trace:
            continue
        evidence = deepcopy(bottom_trace.get("geometry_evidence") or {})
        corners = tuple(dict(evidence.get("projection_by_corner") or {}).keys()) or ("bottom",)
        for corner_name in corners:
            traces.append(ResolvedReliefRuleTrace(
                part_key=str(resolved_part.part_key), corner_name=str(corner_name),
                rule_id=bottom_trace.get("rule_id"), revision=bottom_trace.get("revision"),
                trust_level=str(bottom_trace.get("trust_level") or ""),
                signature="BOTTOM:WRAP",
                geometry_inputs=tuple(str(v) for v in tuple(evidence.get("geometry_inputs", ()) or ())),
                geometry_evidence=evidence,
            ))

    from ae_engine.contracts import ResolvedJointDiagnostic
    from ae_engine.assembly_collision import joint_relief_ownership
    diagnostics = []
    for joint in joints:
        if str(getattr(getattr(joint, "source", None), "value", getattr(joint, "source", ""))) == "USER_ADDED":
            continue
        ownership = joint_relief_ownership(joint)
        render_by_part = {str(part.part_key): part.render_data for part in resolved_parts}
        info = _phase6_joint_registry_diagnostic_info(joint, render_by_part, solution_by_part)
        diagnostics.append(ResolvedJointDiagnostic(
            joint_id=str(joint.joint_id),
            subject_part=str(joint.subject_part),
            target_part=str(joint.target_part),
            relation=str(getattr(joint.relation, "value", joint.relation)),
            source=str(getattr(joint.source, "value", joint.source)),
            registry_status=info["registry_status"],
            rule_id=info["rule_id"], revision=info["revision"], trust_level=info["trust_level"],
            preserve_part=str(ownership.preserve_part), relief_part=str(ownership.relief_part),
            candidate_status=info["candidate_status"],
            legal_contact=bool(info["verified"] and int(info["post_pair_count"]) > 0),
            illegal_penetration=bool(not info["verified"]),
            pre_pair_count=int(info["pre_pair_count"]), post_pair_count=int(info["post_pair_count"]),
            evidence=deepcopy(info["evidence"]),
        ))
    diagnostics.extend(tuple(explicit_joint_diagnostics or ()))
    resolved = ResolvedManufacturingGeometry(
        parts=resolved_parts,
        joints=joints,
        relief_rules=tuple(traces),
        diagnostics=tuple(diagnostics),
    )
    self._phase6_last_interference_probe_parts = tuple(pre_solve_probe_parts)
    self._phase6_last_resolved_manufacturing_geometry = resolved
    # Publishing certified/provisional relief may update assembly_relief metadata;
    # store the post-publish signature so subsequent readers reuse this exact result.
    self._phase6_last_resolved_manufacturing_signature = _phase6_manufacturing_state_signature(self)
    return resolved


def _phase6_refresh_box_body_piece_info_rows(self, render_data) -> None:
    """Render one sub-row per resolved physical Box Body piece."""
    host = getattr(self, "assembly_box_body_piece_host", None)
    if host is None:
        return
    projections = _phase6_box_body_piece_dimension_projections(render_data)
    wanted = tuple(row.part_key for row in projections)
    current = tuple(dict(getattr(self, "assembly_box_body_piece_formed_vars", {}) or {}))
    if current != wanted:
        for child in host.winfo_children():
            child.destroy()
        self.assembly_box_body_piece_labels = {}
        self.assembly_box_body_piece_sections = {}
        self.assembly_box_body_piece_formed_vars = {}
        self.assembly_box_body_piece_blank_vars = {}
        self.assembly_box_body_piece_corner_vars = {}
        piece_by_role = {str(getattr(piece, "role", "")): piece for piece in tuple(getattr(render_data, "pieces", ()) or ())}
        for projection in projections:
            sub = original.ttk.LabelFrame(host, text=projection.label, padding=4)
            sub._phase6_part_key = projection.part_key
            sub.pack(fill=original.tk.X, padx=(18, 0), pady=(2, 4))
            self.assembly_box_body_piece_labels[projection.part_key] = projection.label
            self.assembly_box_body_piece_sections[projection.part_key] = sub
            formed = original.tk.StringVar(master=sub)
            blank = original.tk.StringVar(master=sub)
            corner = original.tk.StringVar(master=sub)
            original.ttk.Label(sub, textvariable=formed, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(12, 0))
            original.ttk.Label(sub, textvariable=blank, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(12, 0))
            original.ttk.Label(sub, textvariable=corner, justify=original.tk.LEFT, wraplength=280).pack(fill=original.tk.X, padx=(12, 0))
            self.assembly_box_body_piece_formed_vars[projection.part_key] = formed
            self.assembly_box_body_piece_blank_vars[projection.part_key] = blank
            self.assembly_box_body_piece_corner_vars[projection.part_key] = corner
            _phase6_bind_assembly_scroll(sub, self)
    piece_by_role = {str(getattr(piece, "role", "")): piece for piece in tuple(getattr(render_data, "pieces", ()) or ())}
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
    logical_formed = (getattr(self, "assembly_part_formed_vars", {}) or {}).get("box_body")
    logical_blank = (getattr(self, "assembly_part_blank_vars", {}) or {}).get("box_body")
    logical_corner = (getattr(self, "assembly_part_corner_vars", {}) or {}).get("box_body")
    if projections:
        if logical_formed is not None: logical_formed.set("成形尺寸：見下方各片")
        if logical_blank is not None: logical_blank.set("展開料：見下方各片")
        if logical_corner is not None: logical_corner.set("截角尺寸：見下方各片")


def _phase6_query_assembly_render_data(self):
    """UI adapter: read the already-resolved canonical manufacturing geometry."""
    resolved = _phase6_resolve_manufacturing_geometry(self)
    # The initial assembly render may solve certified relief while live-sync is
    # intentionally disabled.  Once READY, make sure the host snapshot receives
    # that exact canonical relief even when this query reuses the cached solve.
    # Equivalent host state remains a strict no-op inside publish_live_state.
    _phase6_publish_live_state(self, force=True)
    parts = [
        AssemblyScenePart(
            part_key=part.part_key,
            render_data=part.render_data,
            x_profile=tuple(dict(seg) for seg in tuple(part.x_profile or ())),
            y_profile=tuple(dict(seg) for seg in tuple(part.y_profile or ())),
            placement=part.placement,
            offset=part.offset,
        )
        for part in resolved.parts
    ]
    self._phase6_last_assembly_corner_dimension_texts = {
        part.part_key: _phase6_render_data_corner_dimension_text(part.render_data)
        for part in parts
    }
    for key, text in self._phase6_last_assembly_corner_dimension_texts.items():
        var = (getattr(self, "assembly_part_corner_vars", {}) or {}).get(key)
        if var is not None and callable(getattr(var, "set", None)):
            var.set(text)
    thickness = _num(
        (getattr(self, "_settings_values", {}) or {}).get(
            "t", (getattr(self, "_phase6_input_snapshot", {}) or {}).get("t", 2.0)
        ), 2.0
    )
    for part in parts:
        formed_var = (getattr(self, "assembly_part_formed_vars", {}) or {}).get(part.part_key)
        if formed_var is not None and callable(getattr(formed_var, "set", None)):
            formed_var.set(_phase6_format_formed_size_text(
                part.render_data, part_key=part.part_key,
                x_profile=part.x_profile, y_profile=part.y_profile, thickness=thickness,
            ))
        var = (getattr(self, "assembly_part_blank_vars", {}) or {}).get(part.part_key)
        if var is not None and callable(getattr(var, "set", None)):
            var.set(_phase6_format_unfolded_blank_text(part.render_data, part_key=part.part_key))
        if part.part_key == "box_body":
            _phase6_refresh_box_body_piece_info_rows(self, part.render_data)

    visible_vars = getattr(self, "assembly_part_visible_vars", {}) or {}
    visible_parts = [
        part for part in parts
        if bool(getattr(visible_vars.get(part.part_key), "get", lambda: True)())
    ]
    if not visible_parts and parts:
        fallback = next((part for part in parts if part.part_key == "box_body"), parts[0])
        visible_parts = [fallback]
        var = visible_vars.get(fallback.part_key)
        if var is not None and callable(getattr(var, "set", None)):
            var.set(True)

    visible_keys = {part.part_key for part in visible_parts}
    visible_probe_parts = tuple(
        part for part in tuple(getattr(self, "_phase6_last_interference_probe_parts", ()) or ())
        if part.part_key in visible_keys
    )
    return _phase6_make_assembly_scene_render_data(
        assembly_parts=tuple(visible_parts),
        show_interference=bool(getattr(self, "assembly_show_interference_var", None).get())
            if getattr(self, "assembly_show_interference_var", None) is not None else True,
        ignore_fixed_corner_relief=False,
        interference_probe_parts=visible_probe_parts,
        # Joint Registry diagnostics remain available on ResolvedManufacturingGeometry
        # for dedicated debug/registry tools, but are not operator assembly drawing
        # layers.  Keep the production combined view free of solver overlays.
        joint_diagnostics=(),
        selected_joint_id=None,
        preserve_endcap_core_origin=(_phase6_current_cabinet_family(self) == "受電箱"),
    )

def _phase6_assembly_unfolded_blank_text(render_data, *, snapshot=None):
    rows = []
    for part in tuple(getattr(render_data, "assembly_parts", ()) or ()):
        text = _phase6_format_unfolded_blank_text(part.render_data, part_key=part.part_key)
        if text.startswith("展開料："):
            text = text[len("展開料："):]
        rows.append(f"{_phase6_part_label(part.part_key, snapshot=snapshot)}：{text}")
    return "展開尺寸：\n" + "\n".join(rows) if rows else "展開尺寸：-"


def _phase6_final_scene_view_request(self):
    """Adapt current designer draft state into the FinalScene View interface."""
    if not self.designer_workspace.active_part:
        return None
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    settings = getattr(self, "_settings_values", {}) or {}
    view_mode = str(getattr(self, "_phase6_3d_display_mode", "single") or "single")
    if view_mode == "assembly":
        assembly_render_data = _phase6_query_assembly_render_data(self)
        return FinalSceneViewRequest(
            render_data=assembly_render_data,
            x_profile=(),
            y_profile=(),
            part_key="assembly",
            alpha_bend=float(getattr(self.state, "alpha_bend", 0.85)),
            finished_dimensions=_phase6_operator_finished_dimensions(self),
            thickness=_num(settings.get("t", snapshot.get("t", 2.0)), 2.0),
            unfolded_blank_text=_phase6_assembly_unfolded_blank_text(
                assembly_render_data, snapshot=getattr(self, "_phase6_input_snapshot", {})
            ),
        )
    render_data = _phase6_query_final_render_data(self)
    if getattr(render_data, "pieces", None):
        x_profile, y_profile = (), ()
    else:
        x_profile, y_profile = _phase6_active_mesh_profiles(self, render_data.material)
    return FinalSceneViewRequest(
        render_data=render_data,
        x_profile=tuple(dict(seg) for seg in x_profile),
        y_profile=tuple(dict(seg) for seg in y_profile),
        part_key=str(self.designer_workspace.active_part),
        alpha_bend=float(getattr(self.state, "alpha_bend", 0.85)),
        finished_dimensions=_phase6_operator_finished_dimensions(self),
        thickness=_num(settings.get("t", snapshot.get("t", 2.0)), 2.0),
        corner_dimension_text=_phase6_render_data_corner_dimension_text(render_data),
        unfolded_blank_text=_phase6_format_unfolded_blank_text(
            render_data, part_key=str(self.designer_workspace.active_part)
        ),
    )


def _phase6_render_true_cutting_mesh(self):
    """Compatibility adapter; production rendering is owned by FinalSceneView."""
    view = getattr(self, "final_scene_view", None)
    if view is None:
        view = Phase6FinalSceneView(self.renderer, number_text=_setting_number_text)
        self.final_scene_view = view
    triangles = view.render(_phase6_final_scene_view_request(self))
    if not isinstance(self, Phase6FoldDesignerApp):
        self._phase6_last_cutting_mesh = view.last_cutting_mesh
        self._phase6_last_cutting_material = view.last_cutting_material
        self._phase6_cutting_mesh_error = view.cutting_mesh_error
    return triangles


def _phase6_on_3d_scroll(self, event):
    view = getattr(self, "final_scene_view", None)
    if view is not None:
        return view.on_scroll(event)
    return None


def _phase6_install_renderer_view(self):
    view = Phase6FinalSceneView(self.renderer, number_text=_setting_number_text)
    self.final_scene_view = view
    view.install(
        lambda: _phase6_final_scene_view_request(self),
        after_render=lambda: (
            _phase6_update_unfolded_size_label(self),
            _phase6_update_assembly_diagnostic_status(self),
        ),
    )
    return view












_PHASE6_ZOOM_MIN = 0.35
_PHASE6_ZOOM_MAX = 3.0
_PHASE6_ZOOM_STEP = 0.85


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
    render_data, *, part_key: str = "", x_profile=(), y_profile=(), thickness: float = 0.0
) -> str:
    """Format formed dimensions from the already-resolved folded geometry only."""
    if render_data is None or tuple(getattr(render_data, "pieces", ()) or ()):
        return "成形尺寸：-"
    material = getattr(render_data, "material", None)
    if material is None or getattr(material, "is_empty", True) or not x_profile or not y_profile:
        return "成形尺寸：-"
    try:
        xb, _ = _phase6_profile_geometry(x_profile)
        yb, _ = _phase6_profile_geometry(y_profile)
        exemptions = _phase6_fold_ownership_exemptions(material, xb, yb)
        triangles = _phase6_folded_mesh_from_polygon(
            material, x_profile, y_profile,
            fold_exemptions=exemptions,
            fold_guides=tuple(getattr(render_data, "fold_guides", ()) or ()),
        )
        envelope = _phase6_folded_outside_envelope(triangles, thickness)
    except Exception:
        envelope = None
    if envelope is None:
        return "成形尺寸：-"
    dims, _bounds = envelope
    primary = sorted((float(v) for v in dims if float(v) > 1e-7), reverse=True)[:2]
    if len(primary) < 2:
        return "成形尺寸：-"
    return f"成形尺寸：{_setting_number_text(primary[0])} × {_setting_number_text(primary[1])} mm"


def _phase6_format_unfolded_blank_text(render_data, *, part_key=""):
    from ae_engine.manufacturing_api import measure_unfolded_blanks

    if render_data is None:
        return "展開料：-"
    try:
        blanks = measure_unfolded_blanks(render_data, part_key=str(part_key or "part"))
    except Exception:
        return "展開料：-"
    if not blanks:
        return "展開料：-"

    piece_labels = {
        "left_side": "左側板", "back": "後面板", "right_side": "右側板",
        "box_body_left_side": "左側板", "box_body_back": "後面板", "box_body_right_side": "右側板",
        "left": "左箱身", "middle": "中箱身", "right": "右箱身",
    }
    rows = []
    multi = len(blanks) > 1
    for blank in blanks:
        label = ""
        if multi:
            suffix = str(blank.part_key).rsplit(":", 1)[-1]
            label = f"{piece_labels.get(suffix, suffix)} "
        rows.append(
            f"{label}{_setting_number_text(blank.width)} × {_setting_number_text(blank.height)} mm"
        )
    return "展開料：" + ("；".join(rows))


def _phase6_current_unfolded_size(self, part_key=None):
    """Compatibility tuple measured from canonical final material only."""
    from ae_engine.manufacturing_api import measure_unfolded_blanks

    key = str(part_key or self.designer_workspace.active_part or "")
    render_data = _phase6_render_data_for_blank(self, key)
    if render_data is None:
        return None
    blanks = measure_unfolded_blanks(render_data, part_key=key)
    if not blanks:
        return None
    blank = blanks[0]
    return float(blank.width), float(blank.height)


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
    """Return folded finished outside dimensions for the active single part."""
    key = str(part_key or getattr(self, "active_part_key", "") or "")
    snapshot = getattr(self, "_phase6_input_snapshot", {}) or {}
    settings = getattr(self, "_settings_values", {}) or {}
    if triangles:
        envelope = _phase6_folded_outside_envelope(
            triangles, _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        )
        if envelope is not None:
            measured, _bounds = envelope
            if key == "box_body":
                return tuple(float(value) for value in measured)
            # Other individual panels are operator-facing as their two primary
            # finished axes; their folded flange depth stays visible in 3D but
            # is not mislabeled as cabinet D/H.
            return float(measured[0]), float(measured[1])
    dims = dict((snapshot.get("part_dimensions") or {}).get(key, {}) or {})
    if key == "box_body":
        w = _num(settings.get("w", snapshot.get("w", 0.0)), 0.0)
        h = _num(settings.get("h", snapshot.get("h", 0.0)), 0.0)
        d = _num(settings.get("d", snapshot.get("d", 0.0)), 0.0)
        t = _num(settings.get("t", snapshot.get("t", 2.0)), 2.0)
        head_policy = _phase6_corner_policy_for(self, "head")
        tail_policy = _phase6_corner_policy_for(self, "tail")
        if head_policy is not None and tail_policy is not None:
            try:
                h = box_body_height_from_corner_policies(
                    h, t, head_corner_policy=head_policy, tail_corner_policy=tail_policy,
                )
            except Exception:
                pass
        return float(w), float(h), float(d)
    if dims.get("width") and dims.get("height"):
        return float(dims["width"]), float(dims["height"])
    if key in {"head", "tail"}:
        return float(snapshot.get("w", 0.0)), float(snapshot.get("d", 0.0))
    return None


















def _phase6_on_assembly_diagnostic_changed(self):
    if str(getattr(self, "_phase6_3d_display_mode", "single") or "single") == "assembly":
        self.do_update()
    return True


def _phase6_create_relief_promotion_candidates(self):
    """Build non-mutating manifests for verified PROVISIONAL_3D solutions."""
    from ae_engine.certified_relief_registry import build_relief_promotion_candidate

    solutions = dict(getattr(self, "_phase6_last_relief_solutions", {}) or {})
    snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or {})
    intent = getattr(self, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
    family = _phase6_current_cabinet_family(self)
    candidates = {}
    for part_key in ("head", "tail"):
        solution = solutions.get(part_key)
        if solution is None:
            continue
        if not bool(getattr(solution, "verified", False)):
            continue
        if str(getattr(solution, "trust_level", "") or "") != "PROVISIONAL_3D":
            continue
        candidates[part_key] = build_relief_promotion_candidate(
            solution,
            cabinet_family=family,
            part_role=part_key,
            joint_face="TOP",
            assembly_intent=intent,
            source_signature=snapshot,
        )
    self._phase6_last_relief_promotion_candidates = candidates
    status_var = getattr(self, "assembly_collision_status_var", None)
    if status_var is not None and callable(getattr(status_var, "set", None)):
        if candidates:
            status_var.set(
                "認證候選：" + " / ".join("封頭" if key == "head" else "封尾" for key in candidates)
                + "（僅建立候選，不修改正式資料庫）"
            )
        else:
            status_var.set("認證候選：目前沒有 verified PROVISIONAL_3D 結果")
    return candidates


def _phase6_refresh_joint_diagnostic_menu(self, resolved=None):
    var = getattr(self, "assembly_joint_diag_var", None)
    button = getattr(self, "assembly_joint_diag_button", None)
    if var is None or button is None:
        return ()
    resolved = resolved or getattr(self, "_phase6_last_resolved_manufacturing_geometry", None)
    diagnostics = tuple(getattr(resolved, "diagnostics", ()) or ()) if resolved is not None else ()
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
    ids = [str(getattr(item, "joint_id", "")) for item in diagnostics if str(getattr(item, "joint_id", ""))]
    current = str(var.get() or "")
    if current not in ids:
        current = ids[0] if ids else ""
        var.set(current)
    for joint_id in ids:
        menu.add_radiobutton(
            label=joint_id, value=joint_id, variable=var,
            command=lambda: _phase6_on_assembly_diagnostic_changed(self),
        )
    button.configure(text=(current or "Joint"))
    return tuple(ids)


def _phase6_selected_joint_diagnostic(self):
    resolved = getattr(self, "_phase6_last_resolved_manufacturing_geometry", None)
    if resolved is None:
        return None
    joint_id = str(getattr(getattr(self, "assembly_joint_diag_var", None), "get", lambda: "")() or "")
    if not joint_id:
        return None
    try:
        return resolved.joint_diagnostic(joint_id)
    except Exception:
        return None


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
    # Main operator status stays manufacturing-focused. Joint registry/debug
    # metadata is queried from the dedicated diagnostics tooling, not appended here.
    solutions = dict(getattr(self, "_phase6_last_relief_solutions", {}) or {})
    if not fallback_enabled and not solutions:
        if size_var is not None:
            size_var.set("實際截角尺寸：等待資料庫查詢")
        status_var.set("截角來源：CERTIFIED優先；未知組合3D fallback已停用")
        return

    errors = dict(getattr(self, "_phase6_last_relief_errors", {}) or {})
    labels = {"head": "封頭", "tail": "封尾"}
    if solutions:
        size_parts = []
        verify_parts = []
        for key in ("head", "tail"):
            solution = solutions.get(key)
            if solution is None:
                continue
            measurements = [
                getattr(item, "measurement", None)
                for item in tuple(getattr(solution, "corner_reliefs", ()) or ())
            ]
            measurements = [item for item in measurements if item is not None]
            texts = []
            for measurement in measurements:
                text = _phase6_relief_measurement_text(measurement)
                if text not in texts:
                    texts.append(text)
            if texts:
                size_parts.append(f"{labels.get(key, key)}：{' / '.join(texts)}")
            verify_parts.append(f"{labels.get(key, key)}{'✓' if bool(getattr(solution, 'verified', False)) else '✗'}")
        if size_var is not None:
            size_var.set("實際截角尺寸：" + ("；".join(size_parts) if size_parts else "無需截角"))
        if errors:
            detail = "；".join(f"{labels.get(k, k)}：{v}" for k, v in errors.items())
            status_var.set("3D驗證：" + " ".join(verify_parts) + f"（{detail}）")
        elif verify_parts and all(bool(getattr(solutions[k], "verified", False)) for k in solutions):
            status_var.set("3D驗證：" + " ".join(verify_parts) + "（零材料穿透）")
        else:
            status_var.set("3D驗證：" + " ".join(verify_parts))
        return

    if errors:
        if size_var is not None:
            size_var.set("實際截角尺寸：求解失敗")
        detail = "；".join(f"{labels.get(k, k)}：{v}" for k, v in errors.items())
        status_var.set(f"3D驗證：{detail}")
        return

    if size_var is not None:
        size_var.set("實際截角尺寸：等待計算")
    status_var.set("3D驗證：等待計算")


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
    delta = int(getattr(event, "delta", 0) or 0)
    number = int(getattr(event, "num", 0) or 0)
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
    wanted = tuple(getattr(_designer_workspace(self), "available_parts", ()) or ())
    if current == wanted:
        return False
    _phase6_refresh_assembly_parts_panel(self)
    return True


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
    for child in panel.winfo_children():
        child.destroy()
    self.assembly_part_visible_vars = {}
    self.assembly_part_corner_vars = {}
    self.assembly_part_formed_vars = {}
    self.assembly_part_blank_vars = {}
    self.assembly_part_checkbuttons = {}
    self.assembly_box_body_piece_host = None
    self.assembly_box_body_piece_labels = {}
    self.assembly_box_body_piece_sections = {}
    self.assembly_box_body_piece_formed_vars = {}
    self.assembly_box_body_piece_blank_vars = {}
    self.assembly_box_body_piece_corner_vars = {}
    for key in self.designer_workspace.available_parts:
        row = original.ttk.Frame(panel)
        row.pack(fill=original.tk.X, pady=(0, 4))
        visible = original.tk.BooleanVar(value=old_visible.get(key, True))
        size_text = original.tk.StringVar(value=old_text.get(key, "截角尺寸：等待3D"))
        formed_text = original.tk.StringVar(value=old_formed.get(key, "成形尺寸：等待3D"))
        blank_text = original.tk.StringVar(value=old_blank.get(key, "展開料：等待3D"))
        check = original.ttk.Checkbutton(
            row, text=_phase6_part_label(key, snapshot=getattr(self, "_phase6_input_snapshot", {})), variable=visible,
            command=lambda: _phase6_on_assembly_part_visibility_changed(self),
        )
        check.pack(anchor=original.tk.W)
        original.ttk.Label(
            row, textvariable=formed_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        original.ttk.Label(
            row, textvariable=blank_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        original.ttk.Label(
            row, textvariable=size_text, justify=original.tk.LEFT, wraplength=300,
        ).pack(fill=original.tk.X, padx=(20, 0))
        if key == "box_body":
            self.assembly_box_body_piece_host = original.ttk.Frame(row)
            self.assembly_box_body_piece_host.pack(fill=original.tk.X)
        self.assembly_part_visible_vars[key] = visible
        self.assembly_part_corner_vars[key] = size_text
        self.assembly_part_formed_vars[key] = formed_text
        self.assembly_part_blank_vars[key] = blank_text
        self.assembly_part_checkbuttons[key] = check
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


def _fix11_init(self, root, snapshot: Mapping[str, object], on_settings_change=None, on_save_defaults=None, on_corner_change=None, on_transaction_confirm=None, on_transaction_cancel=None, on_live_sync=None, on_baseline_data_query=None, on_scene_query=None, on_ui_text_size_change=None, on_project_load=None, on_project_path_change=None, on_project_save=None, on_return_2d=None):
    # Atomic lifecycle: inherited Tk construction may invoke traced callbacks and
    # legacy do_update() methods, but none of those bootstrap intermediates are
    # authoritative live-sync state. Publish is disabled until the final Phase6
    # workspace has ingested the current application snapshot and reached READY.
    self._phase6_initializing = True
    snapshot = migrate_legacy_snapshot_joints(dict(snapshot or {}))
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
    self._phase6_box_whd = {
        "w": _ui_len(snapshot.get("w", 500)),
        "h": _ui_len(snapshot.get("h", 600)),
        "d": _ui_len(snapshot.get("d", 200)),
    }
    self._settings_change_callback = on_settings_change
    self._phase6_transactional_mode = on_transaction_confirm is not None and on_live_sync is None
    self._live_sync_callback = on_live_sync
    self._phase6_live_sync_guard = False
    self._phase6_last_live_payload = None
    self._phase6_last_live_state = None
    self._phase6_last_live_fingerprint = None
    self._phase6_sync_revision = 0
    self._phase6_last_external_revision = 0
    self._phase6_last_external_transaction_id = ""
    self._phase6_active_transaction_id = ""
    self._save_defaults_callback = on_save_defaults
    # Kept only for backwards constructor compatibility. Corner edits are now
    # 這些資料採交易式提交，因此絕不能觸發這個舊版即時 callback。
    self._corner_change_callback = on_corner_change
    self._transaction_confirm_callback = on_transaction_confirm
    self._transaction_cancel_callback = on_transaction_cancel
    self._baseline_data_query_callback = on_baseline_data_query
    self._scene_query_callback = on_scene_query
    self._ui_text_size_change_callback = on_ui_text_size_change
    self._project_load_callback = on_project_load
    self._project_path_change_callback = on_project_path_change
    self._project_save_callback = on_project_save
    self._return_2d_callback = on_return_2d
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
    self._phase6_pending_settings = {}
    self._phase6_settings_debounce_job = None
    self._phase6_settings_rendering = False
    self._settings_values = dict(snapshot.get("settings") or {})
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
    self._phase6_assembly_type = resolve_box_assembly_type(snapshot)
    self._phase6_input_snapshot = dict(getattr(self, "_phase6_input_snapshot", {}) or snapshot)
    self._phase6_input_snapshot.pop("_runtime_project_path", None)
    self._phase6_input_snapshot["assembly_type"] = assembly_intent_value(self._phase6_assembly_type)
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
    _FIX10_INIT(self, root, snapshot)
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
    self.part_var = original.tk.StringVar(master=self.part_selector, value="組合體")
    self.part_buttons = {}
    self.part_choice_button = original.ttk.Menubutton(self.part_selector, textvariable=self.part_var)
    self.part_choice_menu = original.tk.Menu(self.part_choice_button, tearoff=False)
    self.part_choice_button.configure(menu=self.part_choice_menu)
    self.part_choice_button.pack(side=original.tk.LEFT, fill=original.tk.X, expand=True, padx=(0, 4))

    self.add_part_button = original.ttk.Menubutton(self.part_selector, text="新增 ▼")
    self.add_part_menu = original.tk.Menu(self.add_part_button, tearoff=False)
    self.add_part_button.configure(menu=self.add_part_menu)
    self.add_part_button.pack(side=original.tk.LEFT, padx=4)
    self.remove_part_button = original.ttk.Button(
        self.part_selector, text="刪除", command=self.remove_selected_part, state="disabled"
    )
    self.remove_part_button.pack(side=original.tk.LEFT, padx=(4, 0))

    # 組合體內容直接使用左側剩餘空間；不再用帶標題/框線的 LabelFrame
    # 切出一塊獨立「組合圖」區域。
    self.assembly_parts_panel = original.ttk.Frame(self.left, padding=6)
    assembly_scroll_host = original.ttk.Frame(self.assembly_parts_panel)
    assembly_scroll_host.pack(fill=original.tk.BOTH, expand=True)
    self.assembly_parts_canvas = original.tk.Canvas(
        assembly_scroll_host, height=1, highlightthickness=0, borderwidth=0
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


def _fix11_refresh_part_buttons(self):
    self.part_buttons = {}
    menu = getattr(self, "part_choice_menu", None)
    if menu is not None:
        menu.delete(0, original.tk.END)
        menu.add_radiobutton(
            label="組合體",
            variable=self.part_var,
            value="組合體",
            command=lambda: _phase6_show_assembly(self),
        )
        for key in self.available_parts:
            menu.add_radiobutton(
                label=_phase6_part_label(key),
                variable=self.part_var,
                value=_phase6_part_label(key),
                command=lambda k=key: self.activate_part(k),
            )
    mode = str(getattr(self, "_phase6_3d_display_mode", "assembly") or "assembly")
    active = getattr(self, "active_part_key", None)
    if hasattr(self, "part_var"):
        if mode == "assembly":
            self.part_var.set("組合體")
        elif active in self.available_parts:
            self.part_var.set(_phase6_part_label(active))
    self._refresh_part_button_states()
    if getattr(self, "assembly_parts_panel", None) is not None:
        _phase6_refresh_assembly_parts_panel(self)


def _fix11_refresh_part_button_states(self):
    selected = getattr(self, "selected_part_key", None)
    for button in self.part_buttons.values():
        button.state(["!disabled"])
    delete = getattr(self, "remove_part_button", None)
    if delete is not None:
        delete.configure(
            state=("normal" if selected in self.available_parts and selected != "box_body" and not _phase6_is_derived_physical_part_key(selected) else "disabled")
        )


def _phase6_show_assembly(self, initial=False):
    """Show the structural cabinet assembly while retaining a real active part as geometry backing."""
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
    self.designer_workspace.selected_part = None
    self._phase6_3d_display_mode = "assembly"
    if hasattr(self, "part_var"):
        self.part_var.set("組合體")
    if getattr(self, "fold_editor_host", None) is not None and self.fold_editor_host.winfo_manager():
        self.fold_editor_host.pack_forget()
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
    return True


def _fix11_select_part(self, key):
    key = str(key or "")
    if not self.designer_workspace.select_part(key):
        return False
    if hasattr(self, "part_var"):
        self.part_var.set(_phase6_part_label(key))
    self._refresh_part_button_states()
    return True


def _fix11_activate_selected_part(self):
    key = getattr(self, "selected_part_key", None)
    if key not in self.available_parts:
        return False
    self.activate_part(key)
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
            self.designer_workspace.stash_profiles(key, {
                "X": x_merged,
                "Y": clone_profile(defaults.get("Y", ())),
            })
        else:
            defaults = build_standard_part_profiles(snapshot, key)
            self.designer_workspace.stash_profiles(key, _merge_keyed_profiles(existing, defaults))


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

    self._phase6_box_whd = {
        "w": original.get_int(self.v_w.get()),
        "h": original.get_int(self.v_h.get()),
        "d": original.get_int(self.v_d.get()),
    }
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
    if key not in self.designer_workspace.available_parts:
        return
    before_signature = None
    if not initial:
        try:
            before_signature = _phase6_manufacturing_state_signature(self)
        except Exception:
            before_signature = None
    # Assembly keeps a real part (normally box_body) as geometry backing.  A Tk
    # Menu radiobutton updates part_var before invoking this callback, so neither
    # active_part nor part_var can tell us that the user is leaving assembly.
    # Capture the display mode first: assembly -> same backing part is still a
    # real mode transition and must rebuild/show the single-part editor.
    was_assembly = str(getattr(self, "_phase6_3d_display_mode", "single") or "single") == "assembly"
    if not initial:
        self._phase6_3d_display_mode = "single"
        diagnostics = getattr(self, "assembly_diagnostics_frame", None)
        if diagnostics is not None and diagnostics.winfo_manager():
            diagnostics.pack_forget()
    if not initial and getattr(self, "_phase6_pending_settings", None):
        self.flush_pending_settings()
    if key == self.designer_workspace.active_part and not initial and not was_assembly:
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

    if not initial and self.designer_workspace.active_part is not None:
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

    self.designer_workspace.begin_switch(key)
    try:
        if hasattr(self, "part_var"):
            self.part_var.set(_phase6_part_label(key))
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
                self.designer_workspace.stash_profiles(key, profiles)
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
        self.designer_workspace.finish_switch()

    # Finish the variable-height settings page before making the canvas visible;
    # otherwise Tk/Matplotlib renders once at the tall pre-settings size and once
    # again after the settings panel changes the viewport height.
    if hasattr(self, "settings_center"):
        _phase6_render_settings_context(self, key)
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


def _fix11_add_part(self, key):
    key = str(key)
    if key not in PART_LABELS:
        raise ValueError(f"不支援的板件: {key}")
    if key not in self.designer_workspace.available_parts:
        if key in {"head", "tail"}:
            linked = build_linked_endcap_xy_profiles(
                self._phase6_input_snapshot, self.state.profiles_vault.get("箱身", [])
            )
            defaults = linked[key]
        elif key != "box_body":
            defaults = build_standard_part_profiles(self._phase6_input_snapshot, key)
        else:
            defaults = None
        self.designer_workspace.add_part(
            key,
            default_profiles=defaults,
            default_features=(),
        )
        self._refresh_part_buttons()
        self._refresh_add_part_menu()
    self.activate_part(key)


def _fix11_remove_part(self, key):
    key = str(key or "")
    was_active = self.designer_workspace.active_part == key
    result = self.designer_workspace.remove_part(key)
    if not result:
        return False
    if was_active:
        try:
            self.activate_part("box_body")
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
    if current not in {"box_body", "head", "tail"}:
        self.designer_workspace.switching = True
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
            self.designer_workspace.switching = False

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


Phase6FoldDesignerApp._phase6_last_cutting_mesh = _phase6_view_property("last_cutting_mesh", [])
Phase6FoldDesignerApp._phase6_last_cutting_material = _phase6_view_property("last_cutting_material", None)
Phase6FoldDesignerApp._phase6_cutting_mesh_error = _phase6_view_property("cutting_mesh_error", None)
Phase6FoldDesignerApp._phase6_zoom_scale = _phase6_view_property("zoom_scale", 1.0)
Phase6FoldDesignerApp._phase6_view_initialized = _phase6_view_property("view_initialized", False)
Phase6FoldDesignerApp._phase6_base_renderer_render = _phase6_view_property("base_renderer_render", None)
Phase6FoldDesignerApp._phase6_scroll_cid = _phase6_view_property("scroll_cid", None)


Phase6FoldDesignerApp.__init__ = _fix11_init
Phase6FoldDesignerApp._refresh_part_buttons = _fix11_refresh_part_buttons
Phase6FoldDesignerApp._refresh_part_button_states = _fix11_refresh_part_button_states
Phase6FoldDesignerApp._refresh_add_part_menu = _fix11_refresh_add_part_menu
Phase6FoldDesignerApp._save_current_part = _fix11_save_current_part
Phase6FoldDesignerApp._load_part_holes = _fix11_load_part_holes
Phase6FoldDesignerApp.activate_part = _fix11_activate_part
Phase6FoldDesignerApp.show_home = _phase6_show_home
Phase6FoldDesignerApp.on_3d_scroll = _phase6_on_3d_scroll
Phase6FoldDesignerApp.add_part = _fix11_add_part
Phase6FoldDesignerApp.select_part = _fix11_select_part
Phase6FoldDesignerApp.activate_selected_part = _fix11_activate_selected_part
Phase6FoldDesignerApp.remove_selected_part = _fix11_remove_selected_part
Phase6FoldDesignerApp.remove_part = _fix11_remove_part
Phase6FoldDesignerApp.available_parts = property(_legacy_available_parts_get, _legacy_available_parts_set)
Phase6FoldDesignerApp.active_part_key = property(_legacy_active_part_get, _legacy_active_part_set)
Phase6FoldDesignerApp.selected_part_key = property(_legacy_selected_part_get, _legacy_selected_part_set)
Phase6FoldDesignerApp._phase6_part_profiles = property(_legacy_part_profiles_get, _legacy_part_profiles_set)
Phase6FoldDesignerApp._phase6_part_features = property(_legacy_part_features_get, _legacy_part_features_set)
Phase6FoldDesignerApp._phase6_part_face_features = property(_legacy_part_face_features_get, _legacy_part_face_features_set)
Phase6FoldDesignerApp._phase6_workspace_dirty = property(_legacy_workspace_dirty_get, _legacy_workspace_dirty_set)
Phase6FoldDesignerApp._phase6_switching_part = property(_legacy_switching_part_get, _legacy_switching_part_set)
Phase6FoldDesignerApp.apply_external_assembly_type = _phase6_apply_external_assembly_type
Phase6FoldDesignerApp.export_phase6_snapshot = _fix11_export
Phase6FoldDesignerApp.show_global_settings = _phase6_show_global_settings
Phase6FoldDesignerApp.toggle_baseline_data = _phase6_settings_panel_toggle_baseline
Phase6FoldDesignerApp.save_settings_context_as_defaults = _phase6_save_settings_context_as_defaults
Phase6FoldDesignerApp.save_current_settings_as_defaults = _phase6_save_current_settings_as_defaults
Phase6FoldDesignerApp.flush_pending_settings = _phase6_flush_pending_settings
Phase6FoldDesignerApp._phase6_publish_live_state = _phase6_publish_live_state
Phase6FoldDesignerApp.toggle_advanced_settings = _phase6_settings_panel_toggle_advanced
Phase6FoldDesignerApp.apply_external_settings = _phase6_apply_external_settings
Phase6FoldDesignerApp.apply_external_sync = _phase6_apply_external_sync
Phase6FoldDesignerApp.on_ui_text_size_changed = _phase6_on_ui_text_size_changed
Phase6FoldDesignerApp.apply_external_corner_state = _phase6_apply_external_corner_state
Phase6FoldDesignerApp._phase6_corner_parameters_unlocked = _phase6_corner_parameters_unlocked
Phase6FoldDesignerApp.toggle_corner_parameter_lock = _phase6_toggle_corner_parameter_lock
Phase6FoldDesignerApp._render_settings_context = _phase6_render_settings_context
Phase6FoldDesignerApp.on_baseline_model_changed = _phase6_on_baseline_model_changed
Phase6FoldDesignerApp.confirm_corner_transaction = _phase6_confirm_corner_transaction
Phase6FoldDesignerApp.cancel_corner_transaction = _phase6_cancel_corner_transaction
Phase6FoldDesignerApp.reset_initial_values = _phase6_reset_initial_values
Phase6FoldDesignerApp.export_workspace_state_if_dirty = _phase6_export_workspace_state_if_dirty
Phase6FoldDesignerApp.save_diagnostic_file = _phase6_save_diagnostic_file
Phase6FoldDesignerApp.save_project_file = _phase6_save_project_file
Phase6FoldDesignerApp.save_project_file_as = _phase6_save_project_file_as
Phase6FoldDesignerApp.load_project_file = _phase6_load_project_file
Phase6FoldDesignerApp._phase6_on_endcap_edge_relation_selected = _phase6_on_endcap_edge_relation_selected
Phase6FoldDesignerApp._phase6_render_endcap_edge_controls = _phase6_render_endcap_edge_controls
Phase6FoldDesignerApp._phase6_commit_base_plate_edge_shrink = _phase6_commit_base_plate_edge_shrink



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
        self._phase6_box_whd = {
            "w": original.get_int(self.v_w.get()),
            "h": original.get_int(self.v_h.get()),
            "d": original.get_int(self.v_d.get()),
        }
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
    self._phase6_box_whd = {
        "w": original.get_int(self.v_w.get()),
        "h": original.get_int(self.v_h.get()),
        "d": original.get_int(self.v_d.get()),
    }
    self._phase6_input_snapshot.update(self._phase6_box_whd)
    return original.MainApp.do_update(self)

Phase6FoldDesignerApp.do_update = _fix11_do_update

_PHASE6_RENDERING_DO_UPDATE = Phase6FoldDesignerApp.do_update

_PHASE6_FULL_UPDATE_REASONS = frozenset({"geometry", "assembly", "baseline"})
_PHASE6_DISPLAY_UPDATE_REASONS = frozenset({"display", "annotation", "camera"})
_PHASE6_ORCHESTRATION_DEBOUNCE_MS = 75

def _phase6_publish_if_changed(self):
    return _phase6_publish_live_state(self)

def _phase6_render_committed_view(self):
    if not getattr(self, "preview_3d_enabled", True):
        return None
    canvas = self.renderer.canvas
    draw = getattr(canvas, "draw", None)
    draw_idle = getattr(canvas, "draw_idle", None)
    if callable(draw) and callable(draw_idle) and not getattr(self, "_phase6_force_sync_preview", False):
        canvas.draw = draw_idle
        try:
            return self.renderer.render()
        finally:
            canvas.draw = draw
    return self.renderer.render()

def _phase6_execute_update_intents(self, reasons):
    reasons = {str(reason or "geometry") for reason in set(reasons or ())}
    if not reasons:
        return None
    if (getattr(self, "_phase6_sync_ready", False)
            and not getattr(self, "_phase6_initializing", False)
            and not getattr(self, "_phase6_external_apply_guard", False)
            and callable(getattr(self, "_live_sync_callback", None))):
        self.publish_if_changed()

    if reasons.intersection(_PHASE6_FULL_UPDATE_REASONS):
        if getattr(self, "preview_3d_enabled", True):
            canvas = self.renderer.canvas
            draw = getattr(canvas, "draw", None)
            draw_idle = getattr(canvas, "draw_idle", None)
            if callable(draw) and callable(draw_idle) and not getattr(self, "_phase6_force_sync_preview", False):
                canvas.draw = draw_idle
                try:
                    return _PHASE6_RENDERING_DO_UPDATE(self)
                finally:
                    canvas.draw = draw
            return _PHASE6_RENDERING_DO_UPDATE(self)
        render = self.renderer.render
        self.renderer.render = lambda: None
        try:
            return _PHASE6_RENDERING_DO_UPDATE(self)
        finally:
            self.renderer.render = render

    # View-only intents never call the legacy calculation/update chain. They
    # consume already-committed manufacturing state through FinalSceneView; a
    # cache hit is allowed, a new manufacturing solve is not owned here.
    return _phase6_render_committed_view(self)

def _phase6_flush_update_intents(self):
    job = getattr(self, "_phase6_orchestration_job", None)
    if job is not None:
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
        self._phase6_orchestration_job = None
    reasons = set(getattr(self, "_phase6_pending_update_reasons", set()) or ())
    self._phase6_pending_update_reasons = set()
    return _phase6_execute_update_intents(self, reasons)

def _phase6_submit_update_intent(self, reason, *, commit=False):
    if getattr(self, "_phase6_destroying", False):
        return None
    reason = str(reason or "geometry")
    if reason not in _PHASE6_FULL_UPDATE_REASONS and reason not in _PHASE6_DISPLAY_UPDATE_REASONS:
        reason = "geometry"  # fail closed for unknown mutation ownership
    pending = getattr(self, "_phase6_pending_update_reasons", None)
    if pending is None:
        pending = set()
        self._phase6_pending_update_reasons = pending
    pending.add(reason)
    if commit or not hasattr(getattr(self, "root", None), "after"):
        return _phase6_flush_update_intents(self)
    job = getattr(self, "_phase6_orchestration_job", None)
    if job is not None:
        try:
            self.root.after_cancel(job)
        except Exception:
            pass
    self._phase6_orchestration_job = self.root.after(
        _PHASE6_ORCHESTRATION_DEBOUNCE_MS, self._phase6_flush_update_intents
    )
    return None

def _phase6_apply_settings_delta(self, delta, transaction_id):
    previous = str(getattr(self, "_phase6_active_transaction_id", "") or "")
    self._phase6_active_transaction_id = str(transaction_id or previous or "")
    try:
        return _phase6_apply_setting_updates(self, dict(delta or {}), notify=True)
    finally:
        self._phase6_active_transaction_id = previous

def _phase6_switch_active_part(self, part_key, *, commit=True):
    # ``activate_part`` owns the legacy editor wiring; its final action now
    # classifies geometry-vs-display and submits exactly one orchestration intent.
    return self.activate_part(str(part_key), initial=False)

def _phase6_preview_aware_do_update(self):
    """Legacy compatibility wrapper: submit intent, never execute update/render."""
    return self.submit_update_intent("geometry", commit=True)

def _phase6_set_3d_preview_enabled(self, enabled):
    enabled = bool(enabled)
    self.preview_3d_enabled = enabled
    var = getattr(self, "preview_3d_var", None)
    if var is not None and bool(var.get()) != enabled:
        var.set(enabled)
    widget = self.renderer.canvas.get_tk_widget()
    if enabled:
        if not widget.winfo_manager():
            widget.pack(fill=original.tk.BOTH, expand=True)
        self.submit_update_intent("display", commit=True)
    else:
        if widget.winfo_manager() == "pack":
            widget.pack_forget()

def _phase6_refresh_3d_preview(self):
    if not getattr(self, "preview_3d_enabled", True):
        self.set_3d_preview_enabled(True)
        return
    self._phase6_force_sync_preview = True
    try:
        return self.submit_update_intent("display", commit=True)
    finally:
        self._phase6_force_sync_preview = False

def _phase6_queue_update(self, *args):
    if getattr(self, "_phase6_destroying", False) or getattr(self, "_phase6_switching_part", False):
        return
    return self.submit_update_intent("geometry", commit=False)

Phase6FoldDesignerApp.submit_update_intent = _phase6_submit_update_intent
Phase6FoldDesignerApp.apply_settings_delta = _phase6_apply_settings_delta
Phase6FoldDesignerApp.switch_active_part = _phase6_switch_active_part
Phase6FoldDesignerApp.publish_if_changed = _phase6_publish_if_changed
Phase6FoldDesignerApp._phase6_flush_update_intents = _phase6_flush_update_intents
Phase6FoldDesignerApp.do_update = _phase6_preview_aware_do_update
Phase6FoldDesignerApp.set_3d_preview_enabled = _phase6_set_3d_preview_enabled
Phase6FoldDesignerApp.refresh_3d_preview = _phase6_refresh_3d_preview
Phase6FoldDesignerApp.queue_update = _phase6_queue_update
