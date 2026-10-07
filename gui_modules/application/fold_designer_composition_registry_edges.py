"""Phase6 Fold Designer composition registry edges implementation.

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

def registry_collect_rule_form(self):
    """Collect one editable Registry rule record from the existing panel vars."""
    app = self.app
    intent = str(
        app.relief_registry_intent_var.get() or "INSERT_OVERLAY"
    )
    topology = int(
        float(
            app.relief_registry_topology_var.get()
            or (2 if intent == "INSERT_OVERLAY" else 1)
        )
    )
    main_target = str(
        app.relief_registry_target_role_var.get() or "BOX_SIDE"
    )
    region = str(
        app.relief_registry_joint_face_var.get() or "TOP"
    )
    signature = [
        {
            "relation": intent,
            "subject_role": str(
                app.relief_registry_part_role_var.get()
                or "HEAD_OR_TAIL"
            ),
            "target_role": main_target,
            "subject_region": region,
            "target_region": (
                "MATING_ZONE"
                if intent != "OVERLAY"
                else "OUTER_SURFACE"
            ),
        }
    ]
    extra = str(
        app.relief_registry_extra_joint_var.get() or "NONE"
    )
    if extra != "NONE":
        signature.append(
            {
                "relation": extra,
                "subject_role": str(
                    app.relief_registry_part_role_var.get()
                    or "HEAD_OR_TAIL"
                ),
                "target_role": str(
                    app.relief_registry_extra_target_role_var.get()
                    or "REAR_PANEL"
                ),
                "subject_region": region,
                "target_region": (
                    "WRAP_ZONE"
                    if extra == "WRAP"
                    else "MATING_ZONE"
                ),
            }
        )
    formula = {
        "primary_u": str(
            app.relief_registry_primary_u_var.get()
        ).strip(),
        "primary_v": str(
            app.relief_registry_primary_v_var.get()
        ).strip(),
    }
    if topology == 2:
        formula["secondary_u"] = str(
            app.relief_registry_secondary_u_var.get()
        ).strip()
        formula["secondary_depth"] = str(
            app.relief_registry_secondary_depth_var.get()
        ).strip()
    preconditions = [
        value.strip()
        for value in str(
            app.relief_registry_preconditions_var.get() or ""
        ).split(",")
        if value.strip()
    ]
    return {
        "rule_id": str(
            app.relief_registry_rule_id_var.get() or ""
        ).strip(),
        "cabinet_family": str(
            app.relief_registry_family_var.get() or "ANY"
        ).strip(),
        "part_role": str(
            app.relief_registry_part_role_var.get()
            or "HEAD_OR_TAIL"
        ).strip(),
        "joint_face": region,
        "assembly_intent": intent,
        "joint_signature": signature,
        "topology_levels": topology,
        "preconditions": preconditions,
        "formula": formula,
        "symmetry": str(
            app.relief_registry_symmetry_var.get()
            or "MIRROR_IF_GEOMETRY_SYMMETRIC"
        ),
        "source": str(
            app.relief_registry_source_var.get() or ""
        ).strip(),
    }

def registry_sample_variables(self):
    """Project the Registry sample controls into evaluator variables."""
    app = self.app
    values = {}
    mapping = {
        "T": app.relief_registry_sample_t_var,
        "FW": app.relief_registry_sample_fw_var,
        "side_fold": app.relief_registry_sample_side_var,
        "ytop1": app.relief_registry_sample_ytop_var,
        "mating_width": app.relief_registry_sample_mating_var,
    }
    for key, var in mapping.items():
        values[key] = float(var.get())
    values["effective_mating_width"] = values["mating_width"]
    values["fold_u"] = values["side_fold"]
    values["fold_v"] = values["ytop1"]
    values["clearance"] = 0.0
    return values

def registry_validate_formula_form(self):
    """Validate the editable Registry form through the existing controller."""
    from ae_engine.certified_relief_registry import (
        evaluate_relief_formula_record,
        _validate_editable_rule_record,
    )

    app = self.app
    controller = self.registry_diagnostics()
    try:
        result = controller.validate_formula(
            self.registry_collect_rule_form(),
            self.registry_sample_variables(),
            validator=_validate_editable_rule_record,
            evaluator=evaluate_relief_formula_record,
        )
        text = (
            f"公式有效：{result['primary_u']:.3f}"
            f"×{result['primary_v']:.3f}"
        )
        if result.get("secondary_u") is not None:
            text += (
                f" + {result['secondary_u']:.3f}"
                f"×{result['secondary_depth']:.3f}"
            )
        app.relief_registry_status_var.set(text)
        app._phase6_last_rule_form_result = result
        return result
    except Exception as exc:
        app.relief_registry_status_var.set(f"公式錯誤：{exc}")
        app._phase6_last_rule_form_result = None
        return None

def registry_preview_payload(self):
    """Return validated 2D preview data; drawing stays panel-owned."""
    result = self.registry_validate_formula_form()
    geometry = self.corner_data_view().registry_preview_geometry(result)
    return {"result": result, "geometry": geometry}

def registry_save_candidate_form(self, namespace):
    """Persist one candidate through the existing Registry controller."""
    from ae_engine.certified_relief_registry import (
        save_relief_rule_candidate,
    )

    app = self.app
    required = lambda name: self._required(namespace, name)
    result = self.registry_validate_formula_form()
    if result is None:
        return None
    try:
        record = self.registry_collect_rule_form()
        controller = self.registry_diagnostics()
        item = controller.save_candidate(
            record,
            saver=save_relief_rule_candidate,
        )
        required(
            "_phase6_sync_registry_diagnostics_compatibility_mirrors"
        )(app, controller)
        app.relief_registry_status_var.set(
            "候選已儲存（尚未認證）"
        )
        return item
    except Exception as exc:
        app.relief_registry_status_var.set(
            f"候選儲存失敗：{exc}"
        )
        return None

def registry_run_formula_matrix(self, namespace):
    """Run the Registry regression matrix through the existing controller."""
    from ae_engine.certified_relief_registry import (
        evaluate_relief_formula_record,
        _validate_editable_rule_record,
    )

    app = self.app
    required = lambda name: self._required(namespace, name)
    try:
        controller = self.registry_diagnostics()
        evidence = controller.run_formula_matrix(
            self.registry_collect_rule_form(),
            self.registry_sample_variables(),
            validator=_validate_editable_rule_record,
            evaluator=evaluate_relief_formula_record,
        )
        required(
            "_phase6_sync_registry_diagnostics_compatibility_mirrors"
        )(app, controller)
        app.relief_registry_status_var.set(
            f"公式矩陣通過：{evidence['cases']} 組；立體零穿透="
            + (
                "是"
                if evidence.get("zero_penetration")
                else "尚未"
            )
        )
        return evidence
    except Exception as exc:
        app.relief_registry_status_var.set(f"回歸失敗：{exc}")
        return None

def registry_preview_assembly_3d(self, namespace):
    """Sequence candidate-specific 3D evidence without owning the solver."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    controller = self.registry_diagnostics()
    try:
        candidate_id = controller.require_current_candidate(
            self.registry_collect_rule_form()
        )
        record = controller.candidate_record
        evidence3d = required(
            "_phase6_registry_validate_candidate_3d"
        )(app, record, candidate_id=candidate_id)
        evidence = controller.merge_3d_evidence(evidence3d)
        required(
            "_phase6_sync_registry_diagnostics_compatibility_mirrors"
        )(app, controller)
        zero = bool(evidence.get("zero_penetration"))
        app.relief_registry_status_var.set(
            "候選專屬立體組合驗證："
            + ("零非法穿透" if zero else "仍有非法穿透")
        )
        return zero
    except Exception as exc:
        app.relief_registry_status_var.set(
            f"立體組合驗證失敗：{exc}"
        )
        return False

def registry_promote_form(self):
    """Promote the current candidate through the existing controller."""
    from ae_engine.certified_relief_registry import (
        promote_relief_rule_candidate,
    )

    app = self.app
    controller = self.registry_diagnostics()
    try:
        promoted = controller.promote_candidate(
            self.registry_collect_rule_form(),
            promoter=promote_relief_rule_candidate,
        )
        app.relief_registry_status_var.set(
            f"已認證新版次：{promoted['revision']}"
        )
        panel = self._registry_panel or getattr(
            app, "registry_diagnostics_panel", None
        )
        refresh = getattr(panel, "refresh_rule_rows", None)
        if callable(refresh):
            refresh()
        return promoted
    except Exception as exc:
        message = str(exc)
        if message in {
            "請先儲存候選",
            "表單已變更；請重新儲存候選後再驗證",
        }:
            app.relief_registry_status_var.set(message)
        else:
            app.relief_registry_status_var.set(
                f"不可認證：{exc}"
            )
        return None

def corner_pair_var_changed(
    self,
    namespace,
    part_key,
    pair_key,
    var,
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if (
        getattr(app, "_phase6_corner_guard", False)
        or getattr(app, "_phase6_settings_rendering", False)
    ):
        return None
    if not required("_phase6_corner_parameters_editable")(
        app, part_key
    ):
        return None
    self.settings_transactions().commit_corner_pair(
        part_key, pair_key, bool(var.get())
    )
    required("_phase6_notify_corner_change")(app)
    self.invalidate_settings_page(part_key)
    self.render_settings_context(namespace, part_key)
    return True

def corner_type_selected(self, namespace, part_key, target_key):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if (
        getattr(app, "_phase6_corner_guard", False)
        or getattr(app, "_phase6_settings_rendering", False)
    ):
        return None
    if not required("_phase6_corner_type_editable")(app, part_key):
        return None
    var = app.corner_type_vars.get(target_key)
    if var is None:
        return None
    type_id = required("_CORNER_TYPE_BY_LABEL").get(
        str(var.get()).strip()
    )
    if type_id is None:
        return None
    self.settings_transactions().commit_corner_type(
        part_key, target_key, type_id
    )
    required("_phase6_notify_corner_change")(app)
    self.invalidate_settings_page(part_key)
    self.render_settings_context(namespace, part_key)
    return type_id

def corner_mode_selected(self, namespace, part_key, target_key):
    app = self.app
    required = lambda name: self._required(namespace, name)
    if (
        getattr(app, "_phase6_corner_guard", False)
        or getattr(app, "_phase6_settings_rendering", False)
    ):
        return None
    if not required("_phase6_corner_parameters_editable")(
        app, part_key
    ):
        return None
    transactions = self.settings_transactions()
    current = transactions.corner_selection(part_key, target_key)
    if current.type_id is not CornerTypeId.CROSS:
        return None
    var = app.corner_mode_vars.get(target_key)
    mode = (
        required("_CORNER_MODE_BY_LABEL").get(str(var.get()).strip())
        if var is not None
        else None
    )
    if mode is None:
        return None
    transactions.commit_corner_mode(part_key, target_key, mode)
    required("_phase6_notify_corner_change")(app)
    self.invalidate_settings_page(part_key)
    self.render_settings_context(namespace, part_key)
    return mode

def corner_target_var_changed(self, namespace, part_key, target_key):
    """Commit semantic Corner parameter widgets through the T2 owner."""
    app = self.app
    required = lambda name: self._required(namespace, name)
    if (
        getattr(app, "_phase6_corner_guard", False)
        or getattr(app, "_phase6_settings_rendering", False)
    ):
        return None
    if not required("_phase6_corner_parameters_editable")(
        app, part_key
    ):
        return None

    transactions = self.settings_transactions()
    current = transactions.corner_selection(part_key, target_key)
    try:
        amount_var = app.corner_amount_vars.get(target_key)
        amount = (
            float(amount_var.get())
            if amount_var is not None
            else current.amount_t
        )
        mode_var = app.corner_mode_vars.get(target_key)
        mode = (
            required("_CORNER_MODE_BY_LABEL").get(
                str(mode_var.get()).strip(), current.cross_mode
            )
            if mode_var is not None
            else current.cross_mode
        )
        direction_var = app.corner_direction_vars.get(target_key)
        direction = (
            required("_CORNER_DIRECTION_BY_LABEL").get(
                str(direction_var.get()).strip(), current.direction
            )
            if direction_var is not None
            else current.direction
        )
        retain_var = app.corner_secondary_retain_vars.get(target_key)
        depth_var = app.corner_secondary_depth_vars.get(target_key)
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
    except (
        TypeError,
        ValueError,
        required("original").tk.TclError,
    ):
        return None
    required("_phase6_notify_corner_change")(app)
    return True

def refresh_active_endcap_from_linked(
    self, namespace, linked
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    key = str(app.designer_workspace.active_part or "")
    if key not in required("ENDCAP_FW_PARTS") or key not in linked:
        return None
    profiles = linked[key]
    clone_profile = required("clone_profile")
    app.state.profiles = {
        "X": clone_profile(profiles.get("X", ())),
        "Y": clone_profile(profiles.get("Y", ())),
    }
    try:
        app.bend_ui.rebuild_tabs()
    except Exception:
        pass
    return app.state.profiles

def commit_endcap_fw_state(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    linked = required("_phase6_rebuild_linked_endcaps")(app)
    self.refresh_active_endcap_from_linked(namespace, linked)
    try:
        app.do_update()
    except Exception:
        pass
    return linked

def set_endcap_fw_override(
    self, namespace, part_key, value
):
    self.settings_transactions().commit_endcap_fw_override(
        str(part_key), value
    )
    return self.commit_endcap_fw_state(namespace)

def on_endcap_fw_value_selected(
    self, namespace, part_key, value_var
):
    try:
        value = float(value_var.get())
    except (TypeError, ValueError):
        return None
    return self.set_endcap_fw_override(
        namespace, part_key, value
    )

def on_box_symmetry_changed(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    var = getattr(app, "v_sy", None)
    if var is None:
        return None
    if not required("_phase6_box_symmetry_allowed")(app):
        required("_phase6_apply_box_symmetry_policy")(app)
        target = bool(getattr(app.state, "symmetric", False))
        if hasattr(app, "bend_ui"):
            app.bend_ui._phase6_refresh_symmetry_bar()
    else:
        try:
            target = bool(var.get())
        except Exception:
            return None
    self.settings_transactions().commit_symmetry(app.state, target)

    pending = getattr(app, "_job", None)
    root = getattr(app, "root", None)
    if pending and root is not None:
        try:
            root.after_cancel(pending)
        except Exception:
            pass
        app._job = None
    try:
        app.do_update()
    except Exception:
        pass
    return target

def on_endcap_edge_relation_selected(
    self, namespace, part_key, edge
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    part_key = str(part_key)
    edge = str(edge).upper()
    var = dict(getattr(app, "endcap_joint_vars", {}) or {}).get(edge)
    if var is None:
        return None
    relation = required("_ENDCAP_LABEL_TO_RELATION").get(
        str(var.get()).strip()
    )
    if relation is None:
        return None
    self.settings_transactions().commit_endcap_edge_relation(
        part_key, edge, relation
    )
    try:
        app.do_update()
    except Exception:
        pass
    return relation

def ensure_drawing_edge_hosts(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    existing = getattr(app, "drawing_edge_hosts", None)
    if existing is not None:
        try:
            if all(
                host.winfo_exists()
                for host in (
                    existing.top,
                    existing.bottom,
                    existing.left,
                    existing.right,
                )
            ):
                return existing
        except Exception:
            pass

    original = required("original")
    canvas = app.renderer.canvas.get_tk_widget()
    hosts = required("Phase6DrawingEdgeHosts")(
        top=original.ttk.Frame(canvas, padding=(4, 2)),
        bottom=original.ttk.Frame(canvas, padding=(4, 2)),
        left=original.ttk.Frame(canvas, padding=(4, 2)),
        right=original.ttk.Frame(canvas, padding=(4, 2)),
        center=canvas,
    )
    app.drawing_edge_hosts = hosts
    return hosts

def clear_drawing_edge_controls(self):
    app = self.app
    hosts = getattr(app, "drawing_edge_hosts", None)
    if hosts is None:
        return None
    for host in (hosts.top, hosts.bottom, hosts.left, hosts.right):
        try:
            for child in host.winfo_children():
                child.destroy()
            host.place_forget()
        except Exception:
            pass
    return None

def render_endcap_edge_controls(
    self, namespace, *, part_key
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    rows = required("_phase6_endcap_joint_policy_rows")(app, part_key)
    self.clear_drawing_edge_controls()
    app.endcap_joint_vars = {}
    app.endcap_joint_widgets = {}
    app.endcap_joint_allowed = {}
    if not rows:
        return None

    hosts = self.ensure_drawing_edge_hosts(namespace)
    edge_hosts = {
        "TOP": hosts.top,
        "BOTTOM": hosts.bottom,
        "LEFT": hosts.left,
        "RIGHT": hosts.right,
    }
    original = required("original")
    labels = required("_ENDCAP_EDGE_LABELS")
    build_choice_menubutton = required("build_choice_menubutton")
    place_host = required("_phase6_place_drawing_edge_host")
    for row in rows:
        edge = row["edge"]
        host = edge_hosts[edge]
        original.ttk.Label(
            host, text=f"{labels[edge]}："
        ).pack(side=original.tk.LEFT)
        var = original.tk.StringVar(
            master=host, value=row["value"]
        )
        widget = build_choice_menubutton(
            host,
            variable=var,
            values=row["allowed"],
            state=("normal" if row["editable"] else "disabled"),
            width=5,
            command=lambda p=part_key, e=edge: self.on_endcap_edge_relation_selected(
                namespace, p, e
            ),
        )
        widget.pack(side=original.tk.LEFT)
        app.endcap_joint_vars[edge] = var
        app.endcap_joint_widgets[edge] = widget
        app.endcap_joint_allowed[edge] = tuple(row["allowed"])
        place_host(host, edge)
    return hosts

def commit_base_plate_edge_shrink(
    self, namespace, edge, raw_value
):
    app = self.app
    required = lambda name: self._required(namespace, name)
    edge = str(edge).upper()
    key = required("_BASE_PLATE_EDGE_SETTING_KEYS").get(edge)
    if key is None:
        return False
    original = required("original")
    try:
        value = float(raw_value)
    except (TypeError, ValueError, original.tk.TclError):
        return False
    if value < 0:
        return False
    self.stage_setting_update(namespace, key, value)
    self.flush_pending_settings(namespace)
    var = dict(
        getattr(app, "base_plate_edge_shrink_vars", {}) or {}
    ).get(edge)
    if var is not None:
        text = required("_setting_number_text")(
            app._settings_values.get(key, value)
        )
        if var.get() != text:
            var.set(text)
    return True

def render_base_plate_edge_controls(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    self.clear_drawing_edge_controls()
    app.endcap_joint_vars = {}
    app.endcap_joint_widgets = {}
    app.endcap_joint_allowed = {}
    app.base_plate_edge_shrink_vars = {}
    app.base_plate_edge_shrink_widgets = {}

    hosts = self.ensure_drawing_edge_hosts(namespace)
    edge_hosts = {
        "TOP": hosts.top,
        "BOTTOM": hosts.bottom,
        "LEFT": hosts.left,
        "RIGHT": hosts.right,
    }
    values = dict(getattr(app, "_settings_values", {}) or {})
    values.update(
        dict(getattr(app, "_phase6_input_snapshot", {}) or {})
    )
    original = required("original")
    labels = required("_ENDCAP_EDGE_LABELS")
    place_host = required("_phase6_place_drawing_edge_host")
    number_text = required("_setting_number_text")
    for edge, key in required(
        "_BASE_PLATE_EDGE_SETTING_KEYS"
    ).items():
        host = edge_hosts[edge]
        original.ttk.Label(
            host, text=f"{labels[edge]}縮："
        ).pack(side=original.tk.LEFT)
        var = original.tk.StringVar(
            master=host,
            value=number_text(values.get(key, 55.0)),
        )
        entry = original.ttk.Entry(
            host,
            textvariable=var,
            width=7,
            justify=original.tk.CENTER,
        )
        entry.pack(side=original.tk.LEFT)
        entry.bind(
            "<Return>",
            lambda _e, ed=edge, v=var: self.commit_base_plate_edge_shrink(
                namespace, ed, v.get()
            ),
        )
        entry.bind(
            "<FocusOut>",
            lambda _e, ed=edge, v=var: self.commit_base_plate_edge_shrink(
                namespace, ed, v.get()
            ),
        )
        app.base_plate_edge_shrink_vars[edge] = var
        app.base_plate_edge_shrink_widgets[edge] = entry
        place_host(host, edge)
    return hosts

def render_active_drawing_edge_controls(self, namespace):
    app = self.app
    required = lambda name: self._required(namespace, name)
    mode = str(
        getattr(app, "_phase6_3d_display_mode", "single") or "single"
    )
    part_key = str(getattr(app, "active_part_key", None) or "")
    if mode != "single":
        self.clear_drawing_edge_controls()
        app.endcap_joint_vars = {}
        app.endcap_joint_widgets = {}
        app.endcap_joint_allowed = {}
        app.base_plate_edge_shrink_vars = {}
        app.base_plate_edge_shrink_widgets = {}
        return None
    if part_key in required("ENDCAP_FW_PARTS"):
        app.base_plate_edge_shrink_vars = {}
        app.base_plate_edge_shrink_widgets = {}
        return self.render_endcap_edge_controls(
            namespace, part_key=part_key
        )
    if part_key == "base_plate":
        return self.render_base_plate_edge_controls(namespace)
    self.clear_drawing_edge_controls()
    app.endcap_joint_vars = {}
    app.endcap_joint_widgets = {}
    app.endcap_joint_allowed = {}
    app.base_plate_edge_shrink_vars = {}
    app.base_plate_edge_shrink_widgets = {}
    return None
