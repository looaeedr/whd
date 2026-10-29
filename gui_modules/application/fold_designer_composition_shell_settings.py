"""Phase6 Fold Designer composition shell settings implementation.

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

def toggle_fullscreen(self):
    """Apply fullscreen presentation effects while composition owns app state."""
    app = self.app
    enabled, geometry = workspace_shell_toggle_fullscreen(
        app.root,
        getattr(app, "fullscreen_button", None),
        enabled=bool(getattr(app, "_phase6_fullscreen", False)),
        restore_geometry=getattr(app, "_phase6_restore_geometry", None),
    )
    app._phase6_fullscreen = bool(enabled)
    app._phase6_restore_geometry = geometry
    return app._phase6_fullscreen

def build_settings_center(self, namespace):
    """Build Settings/diagnostics around the renderer without changing owners."""
    app = self.app
    renderer_widget = app.renderer.canvas.get_tk_widget()
    renderer_widget.pack_forget()
    panel = self.settings_panel(namespace)
    panel.build_settings_center(app.right)
    self.registry_panel(namespace).build_assembly_diagnostics(app.right)
    renderer_widget.pack(fill=tk.BOTH, expand=True)
    self.sync_settings_panel_compat()

def install_renderer_view(self, namespace):
    """Install the FinalScene view and keep its Tk canvas out of focus order."""
    app = self.app
    adapter = self.final_scene_adapter(self.final_scene_ports(namespace))
    result = adapter.install_renderer()
    # A double-click belongs to the physical sheet actually hit in the
    # rendered 3D view, not to the current left-hand selector or project mode.
    # Reuse the existing original Hole Editor entry and its Confirm/Cancel
    # lifecycle; do not manufacture or change geometry on the pick itself.
    def open_clicked_3d_sheet(part_key):
        key = str(part_key)
        workspace = app.designer_workspace
        if key not in workspace.available_parts:
            return None
        host = getattr(getattr(app, "_scene_query_callback", None), "__self__", None)
        opener = getattr(host, "open_part_hole_editor", None)
        if not callable(opener):
            return None

        def open_after_mpl_event():
            if (app.root.winfo_exists()
                    and key in app.designer_workspace.available_parts):
                opener(key)

        app.root.after_idle(open_after_mpl_event)
        return key

    result.set_hole_double_click_handler(open_clicked_3d_sheet)
    try:
        app.renderer.canvas.get_tk_widget().configure(takefocus=False)
    except Exception:
        pass
    return result

def workspace_shell_owner(self, namespace):
    """Compose WorkspaceShell state/actions without moving presentation ownership."""
    app = self.app
    current = getattr(app, "__dict__", {}).get("_phase6_workspace_shell_owner")
    if isinstance(current, WorkspaceShellOwner):
        self._workspace_shell_owner = current
        return current
    if self._workspace_shell_owner is not None:
        return self._workspace_shell_owner

    required = lambda name: self._required(namespace, name)
    panel = self.settings_panel(namespace)
    structure_state = required("_phase6_box_structure_state")(app)
    active_structure = BoxBodyStructureType(structure_state["active_type"])
    structure_labels = required("_BOX_STRUCTURE_LABELS")

    shell_state = WorkspaceShellState(
        root=app.root,
        left=app.left,
        right=app.right,
        renderer_canvas_widget=app.renderer.canvas.get_tk_widget(),
        ui_text_size_values=tuple(UI_TEXT_SIZE_LABELS.values()),
        v_a_bend=app.v_a_bend,
        v_a_face=app.v_a_face,
        baseline_models=tuple(app._baseline_models),
        initial_model=app._phase6_baseline_initial_model,
        structure_label=structure_labels[active_structure],
        structure_choices=tuple(structure_labels.values()),
        assembly_label=ASSEMBLY_TYPE_LABELS[
            getattr(app, "_phase6_assembly_type", CornerTypeId.INSERT_OVERLAY)
        ],
        assembly_choices=tuple(ASSEMBLY_TYPE_LABELS.values()),
        settings_values=dict(app._settings_values),
        external_draw_stock_var=getattr(
            app, "_phase6_external_draw_stock_var", None
        ),
        external_export_vars=dict(
            getattr(app, "_phase6_external_export_vars", {}) or {}
        ),
        left_workspace_width=required("_phase6_left_workspace_width")(
            app._settings_values.get("ui_text_size", "small")
        ),
        theme_background=WHD_THEME["background"],
    )
    actions = WorkspaceShellActions(
        status_projection=lambda: required("_phase6_status_projection")(app),
        load_project_file=app.load_project_file,
        save_project_file=app.save_project_file,
        save_project_file_as=app.save_project_file_as,
        open_relief_registry=lambda: required(
            "_phase6_open_relief_registry_form"
        )(app),
        reset_initial_values=app.reset_initial_values,
        build_settings_global_controls=lambda host: panel.build_left_global_controls(
            host,
            baseline_models=tuple(app._baseline_models),
            initial_model=app._phase6_baseline_initial_model,
        ),
        sync_settings_panel_compat=lambda: self.sync_settings_panel_compat(),
        get_left_global_controls=lambda: app.left_global_controls,
        get_left_global_cells=lambda: app.left_global_cells,
        get_ui_text_size_var=lambda: app.ui_text_size_var,
        set_ui_text_size_combo=lambda combo: setattr(
            app.settings_panel, "ui_text_size_combo", combo
        ),
        toggle_parameter_panel=lambda: self.toggle_parameter_panel(namespace),
        select_structure_type=lambda var: required(
            "_phase6_select_box_structure_type"
        )(app, var),
        select_assembly_type=lambda: self.on_assembly_type_selected(
            namespace
        ),
        refresh_persistent_structure_controls=lambda: required(
            "_phase6_refresh_persistent_structure_controls"
        )(app),
        commit_output_draw_stock=lambda: self.commit_output_draw_stock(namespace),
        export_selected_dxf=lambda: self.export_selected_dxf_from_3d(),
        queue_update=app.queue_update,
        pack_right_panel=lambda widget: required(
            "_phase6_pack_right_panel_above_canvas"
        )(app, widget),
        refresh_sticky_structure_tree=lambda: required(
            "_phase6_refresh_sticky_structure_tree"
        )(app),
        install_keyboard_shortcuts=lambda: required(
            "_phase6_install_keyboard_shortcuts"
        )(app),
        toggle_fullscreen=lambda: self.toggle_fullscreen(),
    )
    owner = WorkspaceShellOwner(shell_state, actions)
    self._workspace_shell_owner = owner
    app._phase6_workspace_shell_owner = owner
    return owner

def sync_authoritative_derived_parts(
    self, namespace, *, projected_snapshot=None,
    projected_workspace=None, projected_box_render_data=None,
):
    """Compose cross-domain derived topology, then delegate the unique workspace mutation."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    snapshot = dict(projected_snapshot if projected_snapshot is not None else getattr(app, "_phase6_input_snapshot", {}) or {})
    workspace = projected_workspace if projected_workspace is not None else getattr(app, "designer_workspace", None)
    navigation = Phase6WorkspaceNavigationController(workspace) if projected_workspace is not None else self.capabilities.workspace.navigation()
    if workspace is None or not navigation.supports_derived_sync:
        return (), ()

    # Pure collection/derivation only. Domain formulas stay in their existing owners.
    door_rows = required("_phase6_door_part_projections")(snapshot)
    source_part_features = dict(snapshot.get("part_features") or {})
    known_feature_keys = set(workspace.part_features_snapshot())
    source_parts = tuple(snapshot.get("existing_parts") or ())
    # A saved v3 Receiving project may omit the original BasePlate from the
    # historical existing_parts list despite having a committed NFB and an
    # authentic physical source. The manufacturing resolver can restore it,
    # but the 2D part selector must use the SAME source authority.
    # Never add it for drafts, unknown sources or non-Receiving families.
    if (snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True
            and "base_plate" not in source_parts):
        from ae_engine.receiving_base_plate_config import receiving_base_plate_values
        try:
            original_base = receiving_base_plate_values(snapshot)
        except (ValueError, TypeError, KeyError):
            original_base = None
        if original_base is not None:
            source_parts += ("base_plate",)
    available_parts = tuple(workspace.available_parts)

    build_profiles = required("build_standard_part_profiles")
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
        door_profiles[row.part_key] = build_profiles(local, row.part_key)

    # Receiving uses its ORIGINAL base_plate component, not a Base Plate
    # automatically manufactured for each Door cell (including the empty
    # lower 500-mm section). Other families keep their existing multi-door
    # base_plate_cN_rN projection unchanged.
    receiving_single_base = str(snapshot.get("model") or "").strip() in {"受電箱", "RECEIVING"}
    # Submitted NFB in TWO real tiers replaces the single root physical
    # BasePlate with TWO canonical tier PartSpecs. The original root remains
    # an internal manufacturing INPUT (registered at _canonical_part_keys),
    # never a third item in the operator's 2D selector.
    receiving_two_tier = (
        receiving_single_base
        and snapshot.get("nfb_config_submitted") is True
        and isinstance(snapshot.get("nfb_config"), Mapping)
        and snapshot["nfb_config"].get("layer_count") == 2
    )
    preserve_navigation_root = receiving_single_base and not receiving_two_tier
    base_plate_profiles = {}
    if door_rows and not receiving_single_base:
        columns = tuple(
            (float(row[0]), tuple(float(v) for v in row[1]))
            for row in tuple(snapshot.get("door_layout_columns") or ())
        )
        number = required("_num")
        shrink_left = number(snapshot.get("base_plate_shrink_left", 55), 55)
        shrink_right = number(snapshot.get("base_plate_shrink_right", 55), 55)
        shrink_top = number(snapshot.get("base_plate_shrink_top", 55), 55)
        shrink_bottom = number(snapshot.get("base_plate_shrink_bottom", 55), 55)
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
            base_plate_profiles[base_key] = build_profiles(local, base_key)

    if projected_workspace is not None:
        box_render_data = projected_box_render_data
    else:
        try:
            box_render_data = required("_phase6_box_body_structure_render_data")(app)
        except Exception:
            box_render_data = None
    box_piece_profiles = (
        required("_phase6_box_body_piece_part_profiles")(box_render_data, snapshot)
        if box_render_data is not None
        else {}
    )
    desired_piece_keys = set(box_piece_profiles)
    is_piece_key = required("_phase6_is_box_body_physical_piece_key")
    current_piece_keys = {key for key in available_parts if is_piece_key(key)}

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
            layout_scope=(str(snapshot.get("door_layout_scope") or "main").strip() or "main"),
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
            included = tuple(
                str(side).strip().lower()
                for side in (item.get("included_frame_sides") or ("top", "bottom", "left", "right"))
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
    # The real inner-door sheet must appear before its separate frame pieces
    # in the single-cabinet operator part selector.  Do not make opening
    # multi-settings a prerequisite to see or manufacture the panel.
    inner_profiles = inner_door_panel_part_profiles(panels)
    inner_profiles.update(inner_door_frame_part_profiles(frames))

    single_door_profiles = (
        build_profiles(snapshot, "door")
        if not door_rows and "door" in source_parts and "door" not in available_parts
        else None
    )
    single_base_plate_profiles = (
        build_profiles(snapshot, "base_plate")
        if (not door_rows or preserve_navigation_root) and "base_plate" in source_parts and "base_plate" not in available_parts
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
            preserve_single_base_plate=preserve_navigation_root,
        )
    )
    plan = build_derived_part_sync_plan(request)
    navigation.apply_derived_sync_plan(plan)

    # #1503: this is a real derived physical Part, not a menu-only label.
    # Synchronize the W800/T2 left/right fixing plates into the authoritative
    # workspace. Replacing the namespace also removes stale plates on Family
    # or cabinet-dimension switches. A short source drawing is catalog-only.
    from ae_engine.receiving_base_fixing_plate import (
        BASE_FIXING_PLATE_PREFIX, receiving_base_fixing_plate_previews,
    )
    plate_previews = receiving_base_fixing_plate_previews(
        snapshot, available_parts=workspace.available_parts,
    )
    navigation.sync_derived_parts(
        namespace=BASE_FIXING_PLATE_PREFIX,
        part_profiles={
            part.part_id: {
                "X": [{"len": part.nominal_source_outline_mm[0],
                       "phase6_key": "base_fixing_source_x"}],
                "Y": [{"len": part.nominal_source_outline_mm[1],
                       "phase6_key": "base_fixing_source_y"}],
            }
            for part in plate_previews
        },
    )

    # #1503: assembly expansion already creates two physical NFB-tier Base
    # Plates, but the original root-only navigation omitted BOTH from the
    # operator's 2D part selector. Publish their exact source-derived
    # profiles as navigation children; leave the root assembly input in
    # place because the manufacturing service expands that ONE root into
    # TWO actual FinalScene owners. Never create a tier for an unsubmitted
    # draft or a Base Plate with no selected physical source.
    tier_profiles = {}
    if (receiving_single_base
            and snapshot.get("nfb_config_submitted") is True
            and isinstance(snapshot.get("nfb_config"), Mapping)
            and snapshot["nfb_config"].get("layer_count") == 2):
        # Do not gate the operator's 2D tier selector on a SECOND manually
        # saved receiving_base_plate setting. The source-only
        # receiving_base_plate_3d_profiles(snapshot) below already returns
        # None for an unresolved physical shape and provides the SAME
        # submitted numeric-CSV authority as the actual Phase6 FinalScene.
        # Previously the real 3D scene had two tiers but 2D navigation
        # silently omitted both unless the operator re-entered a base plate.
        from ae_engine.receiving_nfb_base_assembly_xy import (
            receiving_nfb_layer_centers,
        )
        from ae_engine.receiving_base_plate_3d_profiles import (
            receiving_base_plate_3d_profiles,
        )
        upper = tuple(
            row for row in tuple(snapshot.get("inner_doors") or ())
            if isinstance(row, Mapping)
            and str(row.get("cell_key") or "").split(":")[-1] == "0"
            and str(row.get("stable_id") or "").strip()
        )
        if len(upper) == 1:
            try:
                centers = receiving_nfb_layer_centers(
                    snapshot, str(upper[0]["stable_id"]),
                )
            except ValueError as exc:
                # Switching between versions may briefly leave the old
                # runtime Set/Bay selector. Never publish stale navigation.
                if str(exc) not in {
                    "RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT",
                    "RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT",
                    "RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT",
                }:
                    raise
                centers = ()
            if len(centers) == 2:
                profiles = receiving_base_plate_3d_profiles(snapshot)
                if profiles is not None:
                    tier_profiles = {
                        center.layer_part_id: deepcopy(profiles)
                        for center in centers
                    }
    navigation.sync_derived_parts(
        namespace="base_plate:nfb_layer:",
        part_profiles=tier_profiles,
    )

    # PAD is its own genuine unfolded 2D sheet. Publish it in the existing
    # Part selector but never as a RAW manufacturing input. The selected
    # Bay's numeric V5 CSV and common tooling remain the sole source.
    from ae_engine.receiving_nfb_pad_operator_parts import (
        committed_nfb_pad_draft_parts,
    )
    # The original Hole Editor commits current NFB ProfileFeatures into
    # the authoritative workspace before the async geometry snapshot is
    # republished. A root-only snapshot still has the PREVIOUS features
    # at this point and _submitted_csv_holes legitimately returns ().
    # Reuse the CURRENT workspace's actual verified features, not inferred
    # slot X, to make 2D source ownership match the subsequent 3D resolve.
    # In dry-run projected workspace use only its projected features.
    live_features = workspace.part_features_snapshot()
    pad_source = {
        **snapshot,
        "part_features": {
            **source_part_features,
            **{
                str(key): value for key, value in live_features.items()
                if isinstance(key, str) and isinstance(value, (tuple, list))
            },
        },
    }
    # The canonical committed snapshot is also the source used by the
    # assembly's PAD render. Prefer it when it already resolves a real PAD:
    # a stale/empty workspace feature stash must not override a newly
    # committed Hole Editor source and silently erase the 2D Part selector.
    # Only fall back to the live workspace features during the short
    # pre-republish window when the root snapshot has not caught up yet.
    pad_preview_parts = ()
    for candidate_source in (snapshot, pad_source):
        try:
            candidate_parts = committed_nfb_pad_draft_parts(candidate_source)
        except (ValueError, TypeError, KeyError, OSError):
            continue
        if candidate_parts:
            pad_preview_parts = candidate_parts
            break
    navigation.sync_derived_parts(
        namespace="nfb_pad:",
        part_profiles={
            part.part_id: {
                "X": tuple(dict(row) for row in part.x_profile),
                "Y": tuple(dict(row) for row in part.y_profile),
            }
            for part in pad_preview_parts
        },
    )
    # No historical third root entry on two-tier navigation; once canonical
    # tier profiles are published, reconcile a stale root that survived an
    # older project load/single-to-two-tier transition. Never alter source
    # geometry or modify the original saved project during this projection.
    if receiving_two_tier and "base_plate" in workspace.available_parts:
        navigation.remove_part("base_plate")

    return (
        tuple(divider_profiles),
        tuple([*(frame.stable_id for frame in frames), *(panel.stable_id for panel in panels)]),
    )

def settings_service(self):
    """Construct the Settings service once from explicit committed-state ports."""
    service = self._capabilities.settings.service()
    self._settings_service = service
    return service

def settings_transactions(self):
    if self._settings_transactions is None:
        app = self.app
        input_snapshot = getattr(app, "_phase6_input_snapshot", {})
        self._settings_transactions = Phase6SettingsTransactionController(
            settings_values=getattr(app, "_settings_values", {}),
            input_snapshot=input_snapshot,
            box_whd=getattr(app, "_phase6_box_whd", {}),
            workspace=getattr(app, "designer_workspace", None),
            endcap_fw_state=getattr(app, "_phase6_endcap_fw_state", {}),
            endcap_bottom_wrap_state=getattr(
                app, "_phase6_endcap_bottom_wrap_state", {}
            ),
            corner_state=getattr(app, "_phase6_corner_state", {}),
            corner_pair_same=getattr(app, "_phase6_corner_pair_same", {}),
            assembly_type=input_snapshot.get(
                "assembly_type", CornerTypeId.INSERT_OVERLAY
            ),
            orchestration=self.settings_service(),
        )
    return self._settings_transactions

def apply_settings_profile_projection(
    self,
    namespace,
    plan,
    *,
    render=True,
):
    """Apply one pure Settings profile plan through existing app owners."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    materialize = required("materialize_settings_profile_value")
    clone = required("clone_profile")

    snapshot = materialize(plan.snapshot)
    # Settings freezes dataclasses into plain mappings to keep its own
    # boundary deterministic. Actual Receiving Hole Editor Features belong
    # to the already-committed manufacturing/workspace snapshot, NOT to
    # Settings. Copy their typed source back before any downstream
    # ReceivingLayout validation (otherwise genuine ProfileFeature rows
    # become plain dicts and every Bay selector fails on a model switch).
    live = getattr(app, "_phase6_input_snapshot", {}) or {}
    if str(snapshot.get("model") or "") in {"受電箱", "RECEIVING"}:
        for key in ("receiving_layout", "part_features"):
            if key in live and key in snapshot:
                snapshot[key] = deepcopy(live[key])
    app._phase6_input_snapshot.update(snapshot)

    box_profile = materialize(plan.box_body_profile)
    app.state.profiles_vault["箱身"] = box_profile

    if plan.derived_sync_required:
        self.sync_authoritative_derived_parts(namespace)
    self.refresh_assembly_parts_panel_if_topology_changed(namespace)

    navigation = self.capabilities.workspace.navigation()
    planned_profiles = materialize(plan.part_profiles)
    for key, profiles in planned_profiles.items():
        navigation.stash_profiles(key, profiles)

    active = str(
        plan.active_part
        or app.designer_workspace.active_part
        or "box_body"
    )
    if active == "box_body":
        app.state.phase6_fold_ui_profiles = {
            "X": app.state.profiles_vault["箱身"]
        }
    elif active in app.designer_workspace.available_parts:
        active_profiles = materialize(plan.active_profiles)
        profiles = active_profiles or (
            app.designer_workspace.profiles_for(active, {}) or {}
        )
        app.state.profiles["X"] = clone(profiles.get("X", []))
        app.state.profiles["Y"] = clone(profiles.get("Y", []))

    if render:
        try:
            app.bend_ui.render()
        except Exception:
            pass
    return plan

def refresh_profiles_from_settings(
    self,
    namespace,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
):
    """Build the pure Settings projection, then apply it at composition."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    workspace = app.designer_workspace
    snapshot = getattr(app, "_phase6_input_snapshot", {})
    settings = dict(getattr(app, "_settings_values", {}) or {})
    if str(snapshot.get("model") or "") in {"受電箱", "RECEIVING"}:
        # The pure Settings projection overlays settings onto the current
        # snapshot. Supply live Receiving W/H/D to this *detached request* so
        # geometry, CUTTING and 3D track the active Bay/Quantity without
        # mutating or using up the operator's saved default W/H/D.
        current_box = getattr(app, "_phase6_box_whd", {}) or {}
        settings.update({
            axis: current_box[axis] for axis in ("w", "h", "d")
            if axis in current_box
        })
    request = required("SettingsProfileProjectionRequest")(
        settings_values=settings,
        input_snapshot=snapshot,
        available_parts=tuple(workspace.available_parts),
        existing_profiles=workspace.part_profiles_snapshot(),
        box_body_profile=app.state.profiles_vault.get("箱身", []),
        active_part=workspace.active_part or "box_body",
        reset_box_profile=bool(reset_box_profile),
        reset_all_profiles=bool(reset_all_profiles),
    )
    plan = required("build_settings_profile_projection")(request)
    return self.apply_settings_profile_projection(
        namespace,
        plan,
        render=bool(render),
    )

def settings_application_apply_profile_plan(
    self,
    namespace,
    committed,
    *,
    reset_box_profile=False,
    reset_all_profiles=False,
    render=True,
    editor_commit=False,
    editor_changed_keys=(),
):
    """Apply Settings profile effects at the existing application composition boundary."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    committed = dict(committed or {})
    if bool(editor_commit):
        required("_phase6_recalculate_part_dimensions")(app)
        changed_keys = set(editor_changed_keys or ())
        if {"w", "h", "d", "t", "fw"}.intersection(changed_keys):
            required("_phase6_refresh_linked_part_profiles")(app, changed_keys)
        return committed
    if "t" in committed:
        app.state.phase6_thickness = float(committed["t"])
    app._phase6_settings_guard = True
    try:
        return self.refresh_profiles_from_settings(
            namespace,
            reset_box_profile=bool(reset_box_profile),
            reset_all_profiles=bool(reset_all_profiles),
            render=bool(render),
        )
    finally:
        app._phase6_settings_guard = False

def settings_application_project_ui_values(
    self,
    namespace,
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
    """Project committed Settings state onto Fold Designer application widgets."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    values = dict(values or {})
    plan = baseline_transition
    number_text = required("_setting_number_text")
    original = required("original")

    if baseline_stage == "rollback":
        model_var = getattr(app, "baseline_model_var", None)
        app._phase6_baseline_guard = True
        try:
            if (
                model_var is not None
                and str(model_var.get() or "").strip()
                != str(new_model or "").strip()
            ):
                model_var.set(str(new_model or ""))
        finally:
            app._phase6_baseline_guard = False
        return

    if bool(editor_commit) and editor_snapshot is not None:
        app._phase6_input_snapshot.update(dict(editor_snapshot or {}))

    if rejected_key == "w":
        if error is not None:
            required("_phase6_box_structure_error")(app, ValueError(str(error)))
        app._phase6_settings_guard = True
        try:
            previous_w = values.get("w")
            if previous_w is not None and hasattr(app, "v_w"):
                app.v_w.set(number_text(previous_w))
            var = getattr(app, "left_global_vars", {}).get("w")
            if previous_w is not None and var is not None:
                var.set(number_text(previous_w))
        finally:
            app._phase6_settings_guard = False
        return

    if baseline_stage == "commit" and plan is not None:
        if old_model != "受電箱" and new_model == "受電箱":
            # FamilyModelPlan already committed the newly initialized
            # Set1/Bay1 NFB source to _phase6_input_snapshot. An old loaded
            # Quantity/Vault workspace still owns its previous mode/layout,
            # and a later Settings/derived pass can silently reproject that
            # unconfigured Bay over the new source (KeyError on real Bay
            # nfb_config_submitted). Sync the workspace authority NOW,
            # before the one Family profile/geometry projection begins.
            # Only an explicit NEW Family switch reaches this block; normal
            # project load and subsequent user Bay edits are untouched.
            self.capabilities.workspace.navigation().replace_receiving_mode(
                deepcopy(app._phase6_input_snapshot),
            )
            # ReceivingCapabilityOwner caches a Set/Bay adapter independently
            # of the workspace. Reusing the prior (unconfigured) adapter
            # causes sync_receiving_current_bay() to overwrite this fresh
            # submitted NFB with the old Bay on the next UI refresh.
            # Rebind it to the committed new Family source before projecting.
            self.receiving_adapter(namespace, reset=True)
        remembered = getattr(plan, "remember_non_receiving_structure", None)
        if remembered is not None:
            app._phase6_non_receiving_structure_state = deepcopy(remembered)

        # Restore the user's original Family part-presence set *before* the
        # Settings profile projection and the single Scheduler baseline solve.
        # Do not force Door present: an intentionally absent Door remains
        # absent. Do not reuse this set for a different cabinet family.
        if old_model == "受電箱" and new_model != "受電箱":
            previous_parts = getattr(
                app, "_phase6_non_receiving_part_presence_state", None
            )
            if (
                isinstance(previous_parts, dict)
                and previous_parts.get("model") == new_model
            ):
                parts = tuple(previous_parts.get("parts") or ())
                app.designer_workspace.replace_available_parts(parts)
                app._phase6_input_snapshot["existing_parts"] = list(parts)

        if "fw" in values:
            state = getattr(app, "_phase6_endcap_fw_state", None)
            if isinstance(state, required("MutableMapping")):
                required("commit_box_fw")(state, float(values["fw"]))
                app._phase6_input_snapshot["endcap_fw"] = deepcopy(state)

        defaults = dict(getattr(plan, "defaults", {}) or {})
        if defaults:
            for key, attr in (("w", "w"), ("h", "h"), ("d", "d")):
                if key in defaults:
                    setattr(app.state, attr, original.get_int(defaults[key]))
            app.v_w.set(str(app.state.w))
            app.v_h.set(str(app.state.h))
            app.v_d.set(str(app.state.d))
            app._phase6_last_w = app.state.w
            app._phase6_last_d = app.state.d

        assembly_var = getattr(app, "assembly_type_var", None)
        if assembly_var is not None:
            assembly_var.set(ASSEMBLY_TYPE_LABELS[plan.assembly_type])

    if "ui_text_size" in values:
        key = values["ui_text_size"]
        if hasattr(app, "_ui_text_controller"):
            app._ui_text_controller.apply(key)
        app.state.ui_text_scale = (
            getattr(app, "_ui_text_controller", None).factor
            if hasattr(app, "_ui_text_controller")
            else 1.0
        )
        required("_phase6_update_left_workspace_width")(app, key)

    app._phase6_settings_guard = True
    try:
        if "w" in values:
            app.v_w.set(number_text(values["w"]))
        if "h" in values:
            app.v_h.set(number_text(values["h"]))
        if "d" in values:
            app.v_d.set(number_text(values["d"]))
        for key, var in getattr(app, "left_global_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(required("ui_text_size_label")(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(number_text(values[key]))
        for key, var in getattr(app, "setting_vars", {}).items():
            if key not in values:
                continue
            if key == "ui_text_size":
                var.set(required("ui_text_size_label")(values[key]))
            elif isinstance(var, original.tk.BooleanVar):
                var.set(bool(values[key]))
            else:
                var.set(number_text(values[key]))
    finally:
        app._phase6_settings_guard = False

    if baseline_stage == "state":
        if bool(new_editable) and str(old_model or "") and not bool(old_editable):
            app._corner_transaction_unknown_state = deepcopy(
                app._phase6_corner_state
            )
            app._corner_transaction_unknown_pairs = deepcopy(
                app._phase6_corner_pair_same
            )
        app._corner_editable = bool(new_editable)
        app._phase6_baseline_last_model = str(new_model or "")
        required("_phase6_apply_box_symmetry_policy")(app)
        bend_ui = getattr(app, "bend_ui", None)
        refresh_symmetry = getattr(bend_ui, "_phase6_refresh_symmetry_bar", None)
        if callable(refresh_symmetry):
            refresh_symmetry()

    if baseline_stage == "finalize":
        required("_phase6_invalidate_corner_pages")(app)
        if (
            hasattr(app, "settings_center")
            and getattr(app, "active_part_key", None) is not None
        ):
            self.render_settings_context(
                namespace,
                getattr(app, "settings_context", app.active_part_key),
            )
        corner_data_panel = getattr(app, "corner_data_panel", None)
        if (
            str(getattr(app, "_phase6_3d_display_mode", "") or "")
            == "corner_data"
            and corner_data_panel is not None
            and corner_data_panel.winfo_manager()
        ):
            required("_phase6_refresh_corner_data_parts_panel")(app)
            if getattr(app, "corner_data_canvas", None) is not None:
                required("_phase6_refresh_corner_data_unfold_view")(app)

def settings_application_submit_update_intent(self, namespace, committed):
    """Submit the Settings application update through existing runtime ownership."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    payload = dict(committed or {}) if isinstance(committed, Mapping) else {}
    if payload.get("reason") == "baseline":
        cache = getattr(app, "_phase6_manufacturing_cache_service", None)
        clear_cache = getattr(cache, "clear", None)
        if callable(clear_cache):
            clear_cache()
        app._phase6_last_resolved_manufacturing_geometry = None
        app._phase6_last_resolved_manufacturing_signature = None
        submit = getattr(app, "submit_update_intent", None)
        if callable(submit):
            return submit("baseline", commit=True)
        return required("_phase6_publish_live_state")(
            app, force=bool(payload.get("force", True))
        )

    legacy_job = getattr(app, "_job", None)
    if legacy_job is not None:
        try:
            app.root.after_cancel(legacy_job)
        except Exception:
            pass
        app._job = None
    try:
        return app.do_update()
    except Exception:
        return None

def settings_application_publish_live_state(self, committed, *, partial=False):
    """Publish Settings changes without moving state ownership out of existing owners."""
    app = self.app
    if (
        not getattr(app, "_phase6_transactional_mode", False)
        and app._settings_change_callback is not None
    ):
        payload = (
            dict(committed or {})
            if bool(partial)
            else dict(app._settings_values)
        )
        if payload:
            app._settings_change_callback(payload)

def settings_application_ports(self, namespace):
    """Compose shallow Settings application ports at the application root."""
    app = self.app
    required = lambda name: self._required(namespace, name)

    def read_settings_snapshot():
        return SettingsStateSnapshot(
            settings_values=getattr(app, "_settings_values", {}),
            input_snapshot=getattr(app, "_phase6_input_snapshot", {}),
            box_whd=getattr(app, "_phase6_box_whd", {}),
        )

    def read_profile_snapshot():
        workspace = getattr(app, "designer_workspace", None)
        snapshot = getattr(workspace, "part_profiles_snapshot", None)
        return snapshot() if callable(snapshot) else {}

    def save_current_part():
        app._phase6_applying_settings = True
        try:
            return app._save_current_part()
        finally:
            app._phase6_applying_settings = False

    def render_bending():
        bend_ui = getattr(app, "bend_ui", None)
        render = getattr(bend_ui, "render", None)
        if not callable(render):
            return None
        try:
            return render()
        except Exception:
            return None

    def refresh_settings_panel():
        panel = getattr(app, "settings_panel", None)
        refresh = getattr(panel, "refresh_baseline_data", None)
        if not callable(refresh):
            return None
        try:
            return refresh()
        except Exception:
            return None

    def refresh_topology(*args, **kwargs):
        if kwargs.get("reason") == "baseline":
            result = None
            refresh_parts = getattr(app, "_refresh_part_buttons", None)
            if (
                callable(refresh_parts)
                and getattr(app, "part_choice_menu", None) is not None
            ):
                result = refresh_parts()
            self.refresh_receiving_set_bay_control(namespace)
            self.refresh_back_panel_mode_control(namespace)
            self.refresh_assembly_parts_panel_if_topology_changed(namespace)
            return result
        return required(
            "_phase6_refresh_assembly_parts_panel_if_topology_changed"
        )(app)

    def project_status(*args, **kwargs):
        message = kwargs.get("message")
        if message is None and args:
            message = args[0]
        status_name = (
            "settings_status_var"
            if kwargs.get("settings")
            else "_phase6_status_var"
        )
        status_var = getattr(app, status_name, None)
        setter = getattr(status_var, "set", None)
        if callable(setter) and message is not None:
            setter(str(message))

    return Phase6SettingsApplicationPorts(
        read_settings_snapshot=read_settings_snapshot,
        read_profile_snapshot=read_profile_snapshot,
        save_current_part=save_current_part,
        apply_profile_plan=lambda committed, **kwargs: self.settings_application_apply_profile_plan(
            namespace, committed, **kwargs
        ),
        sync_derived_parts=lambda *args, **kwargs: required(
            "_phase6_sync_authoritative_derived_parts"
        )(app),
        project_ui_values=lambda values, **kwargs: self.settings_application_project_ui_values(
            namespace, values, **kwargs
        ),
        render_bending=render_bending,
        refresh_settings_panel=refresh_settings_panel,
        refresh_topology=refresh_topology,
        refresh_persistent_controls=lambda: required(
            "_phase6_refresh_persistent_structure_controls"
        )(app),
        submit_update_intent=lambda committed: self.settings_application_submit_update_intent(
            namespace, committed
        ),
        publish_live_state=lambda committed, **kwargs: self.settings_application_publish_live_state(
            committed, **kwargs
        ),
        project_status=project_status,
    )

def settings_coordinator(self, ports: Phase6SettingsApplicationPorts):
    """Return the single Phase 5 Settings application sequencing owner."""
    if self._settings_coordinator is None:
        self._settings_coordinator = Phase6FoldDesignerSettingsCoordinator(
            transactions=self.settings_transactions(),
            ports=ports,
        )
    return self._settings_coordinator
