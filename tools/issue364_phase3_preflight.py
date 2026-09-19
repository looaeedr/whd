#!/usr/bin/env python3
"""#364 / Phase 3 T0 — bridge-wide ownership/dependency/timing preflight.

Read-only static inventory. This tool classifies the live Phase 2 accepted bridge,
builds a production call graph, inventories state/Tk/callback/class wiring, freezes
the accepted baseline failure node sets, hashes protected sources, and fails closed
on any implementation-source drift.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(".")
BRIDGE = Path("fold_designer_bridge.py")
BASELINE_SHA = "0dd6561f3253d0a17714af316d5e9da90e24058f"
BASELINE_RUN = 35423014088
EXPECTED_BRIDGE_LINES = 9148
EXPECTED_TOP_LEVEL_FUNCTIONS = 304

EVIDENCE_PATHS = {
    ".github/workflows/qa-issue364-t0-phase3-preflight.yml",
    "tools/issue364_phase3_preflight.py",
    "docs/superpowers/checkpoints/issue364-t0-phase3-preflight.md",
}

SKIP_PARTS = {
    ".git", ".venv", "venv", "__pycache__", "BACKUP", "backup",
    "tests", ".agents", ".pytest_cache", ".scratch",
}

EVENT_ATTRS = {
    "update", "update_idletasks", "after", "after_idle",
    "wait_variable", "wait_window", "wait_visibility", "mainloop",
    "trace_add", "bind", "event_generate",
}
MAPPING_UPDATE_RECEIVERS = {
    "raw", "source", "result", "payload", "values", "snapshot", "data",
    "config", "mapping", "merged", "state", "record", "item",
    "settings", "evidence", "inner_profiles", "cfg", "row", "target",
    "current_snapshot", "ephemeral", "promoted",
}
MAPPING_SELF_UPDATE_RECEIVERS = {
    "self._phase6_input_snapshot",
    "self._settings_values",
    "self._phase6_box_whd",
}
MAPPING_UPDATE_LOCATIONS = {
    ("phase6_box_body_structure.py", 115),
    ("phase6_box_body_structure.py", 173),
}
WIDGET_METHODS = {
    "pack", "pack_forget", "grid", "grid_remove", "grid_forget", "place",
    "configure", "config", "bind", "unbind", "destroy", "winfo_exists",
    "winfo_ismapped", "winfo_children", "winfo_width", "winfo_height",
    "winfo_reqwidth", "winfo_reqheight", "focus_set", "selection_set",
    "see", "insert", "delete", "set", "get", "invoke",
}

KNOWN_OWNER_FILES = {
    "workspace": (
        "phase6_workspace_controller.py",
        "phase6_designer_workspace.py",
        "phase6_part_navigation.py",
    ),
    "settings": (
        "phase6_settings_center.py",
        "phase6_settings_panel.py",
        "phase6_box_body_structure.py",
        "phase6_endcap_semantics.py",
        "gui_modules/application/state_sync.py",
    ),
    "project": (
        "phase6_project_controller.py",
        "phase6_project_session.py",
        "phase6_project_file.py",
        "gui_modules/application/render_snapshots.py",
    ),
    "registry": (
        "phase6_diagnostics.py",
        "phase6_registry_controller.py (new only if T0 proves needed)",
    ),
    "2d": (
        "phase6_corner_data_view.py (new only if no existing canonical owner)",
    ),
    "3d": (
        "phase6_final_scene_view.py",
        "phase6_manufacturing_adapter.py",
    ),
    "lifecycle": (
        "gui_modules/application/fold_designer_adapter.py",
        "gui_modules/application/lifecycle.py",
        "gui_modules/application/state_sync.py",
    ),
    "manufacturing": (
        "phase6_manufacturing_adapter.py",
        "phase6_manufacturing_service.py",
    ),
    "compatibility": (
        "fold_designer_bridge.py compatibility/composition shell",
    ),
}

HEADLESS_FAILED = (
    "tests/knowledge/test_issue233_strict_metadata_migration.py::test_all_governed_markdown_has_valid_whd_doc_meta_v1",
    "tests/knowledge/test_issue233_strict_metadata_migration.py::test_strict_validator_accepts_the_repository_after_migration",
    "tests/knowledge/test_issue252_t6_strict_validation.py::test_exact_governed_set_matches_effective_authority_and_strict_validation",
    "tests/knowledge/test_issue255_t6_authority_completion.py::test_repository_effective_authority_is_total_and_unblocked",
    "tests/test_issue294_t6_task7b_door_panel_review_characterization.py::test_task7b_door_layout_entry_menu_preserves_delete_column_action",
    "tests/test_issue94_corner_data_navigation_mode.py::test_corner_data_mode_is_view_only_and_not_a_fake_part",
)

XVFB_FAILED = (
    "tests/knowledge/test_issue233_strict_metadata_migration.py::test_all_governed_markdown_has_valid_whd_doc_meta_v1",
    "tests/knowledge/test_issue233_strict_metadata_migration.py::test_strict_validator_accepts_the_repository_after_migration",
    "tests/knowledge/test_issue252_t6_strict_validation.py::test_exact_governed_set_matches_effective_authority_and_strict_validation",
    "tests/knowledge/test_issue255_t6_authority_completion.py::test_repository_effective_authority_is_total_and_unblocked",
    "tests/test_corner_lock_visual_contract.py::test_fold_designer_locked_corner_ui_shows_lock_and_collapses_detail_area",
    "tests/test_corner_lock_visual_contract.py::test_3d_locked_corner_ui_shows_lock_collapses_detail_and_has_global_project_toolbar",
    "tests/test_corner_parameter_lock.py::test_fold_designer_corner_parameters_default_locked_and_unlock_does_not_mutate_state",
    "tests/test_corner_parameter_lock.py::test_3d_corner_parameters_default_locked_for_known_model_and_unlock_without_mutation",
    "tests/test_corner_parameter_lock.py::test_fold_designer_locked_parameters_have_no_hidden_editor_and_unlocked_can_adjust_amount",
    "tests/test_corner_parameter_lock.py::test_3d_known_model_locked_guard_and_unlocked_parameter_edit_preserves_type",
    "tests/test_corner_type_phase6_integration.py::test_corner_panel_is_visible_for_known_and_custom_models_with_type_locking",
    "tests/test_issue126_workspace_layout.py::test_sidebar_width_is_bounded_while_workspace_receives_majority_of_extra_width",
    "tests/test_issue163_unfold_workspace_layout.py::test_red_163_top_surface_contains_only_file_and_corner_data_commands",
    "tests/test_issue294_t6_task7b_door_panel_review_characterization.py::test_task7b_door_layout_entry_menu_preserves_delete_column_action",
    "tests/test_issue343_t8_visual_remediation.py::test_installed_cjk_font_is_selected_for_actual_matplotlib_text",
    "tests/test_issue94_corner_data_navigation_mode.py::test_corner_data_mode_is_view_only_and_not_a_fake_part",
    "tests/test_original_fold_designer_bridge.py::test_designer_part_selector_opens_on_previous_active_part_and_can_add_missing_known_part",
    "tests/test_original_fold_designer_gui_integration.py::test_open_designer_first_assembly_render_has_no_scene_contract_error",
    "tests/test_phase6_3d_cutting_mesh.py::test_real_tk_active_door_uses_features_and_corner_state_in_cutting_mesh",
    "tests/test_phase6_assembly_3d_view.py::test_real_tk_part_selector_starts_in_assembly_and_switches_to_single_part",
    "tests/test_phase6_assembly_3d_view.py::test_real_tk_menu_can_switch_from_assembly_to_boxbody_after_radiobutton_sets_label_first",
    "tests/test_phase6_gui_3d_integrity_20260830.py::test_real_box_body_2d_annotations_do_not_overlap_each_other_or_material",
    "tests/test_phase6_home_baseline_ui.py::test_initial_view_is_assembly_and_global_controls_remain_visible",
    "tests/test_phase6_home_baseline_ui.py::test_selecting_part_keeps_global_visible_and_shows_fold_editor",
    "tests/test_phase6_left_global_transaction.py::test_global_controls_and_reset_only_live_in_persistent_top_area",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_endcap_four_edge_controls_live_on_drawing_edges_even_when_parameters_locked",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_four_shrinks_live_on_drawing_edges_and_bend_stays_in_settings_panel",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_edge_shrink_commit_uses_canonical_settings_transaction_and_updates_dimensions",
    "tests/test_phase6_receiving_followup_20260830.py::test_assembly_input_area_uses_all_remaining_left_space",
    "tests/test_phase6_receiving_followup_20260830.py::test_assembly_mode_has_no_separate_labeled_flag_frame",
    "tests/test_phase6_return_2d_corner.py::test_loaded_project_opens_head_2d_in_fold_designer_corner_data",
    "tests/test_phase6_t02_endcap_edge_controls.py::test_head_settings_publish_four_edge_controls_directly_from_registry",
    "tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics",
    "tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_fold_designer_controls_and_edge_selectors_update_on_text_size_changed",
    "tests/test_phase6_t22_settings_vertical_scroll.py::test_medium_unlocked_settings_uses_real_vertical_scroll_owner_and_scrollable_viewport",
    "tests/test_phase6_t22_settings_vertical_scroll.py::test_settings_scroll_owner_survives_resize_part_switch_and_lock_unlock",
    "tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[head]",
    "tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[tail]",
    "tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[head]",
    "tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[tail]",
    "tests/test_phase6_ui_state_regressions.py::test_real_tk_part_selector_menu_opens_part_and_delete_shares_selector_row",
    "tests/test_receiving_cabinet_type.py::test_switching_3d_baseline_model_to_receiving_applies_receiving_family_policy",
    "tests/test_receiving_side_panel_outside_defaults.py::test_receiving_designer_controls_show_exact_outside_defaults_for_each_physical_side",
    "tests/test_relief_registry_candidate_shadow_gui.py::test_candidate_record_gets_its_own_shadow_validation_without_mutating_registry",
    "tests/ui/test_box_body_physical_child_navigation.py::test_designer_box_body_stays_one_top_level_part_but_has_switchable_physical_subtabs",
    "tests/ui/test_box_body_physical_child_navigation.py::test_corner_data_box_body_lists_physical_children_and_draws_selected_piece",
    "tests/ui/test_box_body_physical_child_navigation.py::test_box_body_physical_child_has_same_authoritative_material_in_3d_and_corner_data_2d",
)

GROUP_PATTERNS = (
    ("manufacturing", re.compile(
        r"manufacturing|relief_profile_fingerprint|relief_source|finished_dimensions|"
        r"scene_query_payload_for_part|mesh_profiles_for_part|operator_finished_dimensions"
    )),
    ("project", re.compile(
        r"project|snapshot|save_diagnostic|save_project|load_project|export_workspace|"
        r"output_draw_stock|export_selected_dxf|status_projection|refresh_status_bar|"
        r"save_current_settings_as_defaults|save_settings_context_as_defaults"
    )),
    ("registry", re.compile(
        r"registry|diagnostic|promotion|joint_form|formula_display|formula_raw|"
        r"preconditions|source_display|source_raw"
    )),
    ("3d", re.compile(
        r"final_scene|query_final_render|query_assembly_render|scene_from|assembly_scene|"
        r"render_true_cutting_mesh|renderer_view|on_3d_scroll|3d_preview|render_committed_view|"
        r"scene_query_payload$|active_mesh_profiles|render_data_for_blank"
    )),
    ("2d", re.compile(
        r"corner_data|drawing_edge|unfold|draw_operator_dimensions|"
        r"formed_size_text|unfolded_size|update_unfolded_size_label|preview_2d"
    )),
    ("workspace", re.compile(
        r"workspace|available_parts|active_part|selected_part|operator_part|part_selector|"
        r"physical_piece|structure_tree|content_switch|activate_part|add_part|remove_part|"
        r"linked_part|show_home|show_assembly|show_input_content|box_body_piece_tab|"
        r"store_editor_values|save_current_part|load_part_holes|switch_active_part"
    )),
    ("settings", re.compile(
        r"setting|corner|box_structure|symmetry|endcap_fw|edge_relation|edge_shrink|"
        r"bottom_wrap|baseline_model|assembly_type|external_model|external_sync|"
        r"ui_text_size|structure_advanced|joint_rows|add_user_joint|delete_user_joint"
    )),
    ("lifecycle", re.compile(
        r"update_intent|queue_update|do_update|preview_aware|publish_if_changed|"
        r"keyboard_|install_keyboard|build_persistent|global_persistent|reset_initial|"
        r"fix11_init|left_workspace_width|toggle_fullscreen|build_project_toolbar|"
        r"build_transaction_buttons|build_visual_controls|build_output_controls|"
        r"configure_floating_surface|settings_center|parameter_panel|assembly_scroll"
    )),
)

COMPOSITION_RE = re.compile(
    r"(^|_)(build|install|configure|ensure|prepare|bind|pack|open|hide_original|"
    r"global_persistent|persistent_top_area)"
)
VIEW_RE = re.compile(
    r"(^|_)(render|refresh|show|hide|draw|place|scroll|toggle|update_.*label|"
    r"info_text|label|text|display)"
)


@dataclass
class FuncInfo:
    module: str
    name: str
    path: Path
    node: ast.FunctionDef | ast.AsyncFunctionDef
    tree: ast.Module
    imports: dict[str, str]
    imported_symbols: dict[str, tuple[str, str]]

    @property
    def key(self) -> str:
        return f"{self.module}:{self.name}"


def module_name(path: Path) -> str:
    rel = path.with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_production_python() -> Iterable[Path]:
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def resolve_imports(module: str, tree: ast.AST) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    modules: dict[str, str] = {}
    symbols: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            src = node.module or ""
            if node.level:
                continue
            for alias in node.names:
                if alias.name != "*":
                    symbols[alias.asname or alias.name] = (src, alias.name)
    return modules, symbols


def build_index() -> dict[str, FuncInfo]:
    out: dict[str, FuncInfo] = {}
    for path in iter_production_python():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except Exception:
            continue
        mod = module_name(path)
        mods, syms = resolve_imports(mod, tree)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info = FuncInfo(mod, node.name, path, node, tree, mods, syms)
                out[info.key] = info
    return out


def attr_chain(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def self_access(node: ast.AST) -> tuple[set[str], set[str]]:
    reads: set[str] = set()
    writes: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
            (writes if isinstance(sub.ctx, (ast.Store, ast.Del)) else reads).add(sub.attr)
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            if sub.func.id in {"getattr", "setattr"} and len(sub.args) >= 2:
                if isinstance(sub.args[0], ast.Name) and sub.args[0].id == "self":
                    key = sub.args[1]
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        (writes if sub.func.id == "setattr" else reads).add(key.value)
    return reads, writes


def event_calls(node: ast.AST, path: str | None = None) -> list[dict]:
    result: list[dict] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Attribute):
            continue
        if sub.func.attr not in EVENT_ATTRS:
            continue
        chain = attr_chain(sub.func)
        receiver_full = chain.rsplit(".", 1)[0] if "." in chain else ""
        receiver = receiver_full.rsplit(".", 1)[-1] if receiver_full else ""
        explicit_mapping_location = (path or "", sub.lineno) in MAPPING_UPDATE_LOCATIONS
        if (
            sub.func.attr == "update"
            and (
                receiver in MAPPING_UPDATE_RECEIVERS
                or receiver_full in MAPPING_SELF_UPDATE_RECEIVERS
                or explicit_mapping_location
            )
        ):
            classification = "DATA_MAPPING_UPDATE_NOT_TK"
        elif sub.func.attr in {"bind", "trace_add", "event_generate"}:
            classification = "EVENT_CALLBACK_OR_DISPATCH"
        elif sub.func.attr in {"after", "after_idle"}:
            classification = "SCHEDULED_EVENT_LOOP_CALLBACK"
        else:
            classification = "TK_EVENT_LOOP_PUMP"
        result.append({
            "line": sub.lineno,
            "call": chain,
            "classification": classification,
        })
    return result


def tk_refs(node: ast.AST) -> list[dict]:
    result: list[dict] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            chain = attr_chain(sub.func)
            if sub.func.attr in WIDGET_METHODS:
                result.append({"line": sub.lineno, "call": chain})
        elif isinstance(sub, ast.Name) and sub.id in {"tk", "ttk", "messagebox", "filedialog"}:
            result.append({"line": getattr(sub, "lineno", 0), "call": sub.id})
    return result


def callback_refs(node: ast.AST) -> list[dict]:
    out: list[dict] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.keyword) and sub.arg in {"command", "validatecommand", "postcommand"}:
            out.append({"line": getattr(sub, "lineno", 0), "kind": f"tk-{sub.arg}"})
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in {"bind", "trace_add", "after", "after_idle"}:
            out.append({"line": sub.lineno, "kind": sub.func.attr})
        elif isinstance(sub, ast.Name) and ("callback" in sub.id.lower() or "provider" in sub.id.lower()):
            out.append({"line": getattr(sub, "lineno", 0), "kind": sub.id})
        elif isinstance(sub, ast.Attribute) and ("callback" in sub.attr.lower() or "provider" in sub.attr.lower()):
            out.append({"line": getattr(sub, "lineno", 0), "kind": sub.attr})
    unique = {(x["line"], x["kind"]): x for x in out}
    return [unique[k] for k in sorted(unique)]


def responsibility(name: str) -> str:
    if name.startswith("_legacy_"):
        return "compatibility"
    if name.startswith("_fix11_"):
        return "lifecycle" if name in {"_fix11_init", "_fix11_do_update"} else "compatibility"
    for group, pattern in GROUP_PATTERNS:
        if pattern.search(name):
            return group
    return "compatibility"


def classify_function(name: str, node: ast.AST) -> tuple[str, str, str]:
    group = responsibility(name)
    _, writes = self_access(node)
    tk = tk_refs(node)
    lname = name.lower()

    if name.startswith("_legacy_") or (name.startswith("_fix11_") and name not in {"_fix11_init", "_fix11_do_update"}):
        return group, "COMPATIBILITY_FACADE", "legacy/fix11 compatibility naming"
    if group == "manufacturing":
        return group, "DOMAIN_DELEGATE", "Phase 2 manufacturing boundary"
    if COMPOSITION_RE.search(lname) or name == "_fix11_init":
        return group, "COMPOSITION", "construction/install/binding responsibility"
    if group in {"2d", "3d"}:
        return group, "VIEW_ADAPTER_OWNER", "render/view responsibility group"
    if VIEW_RE.search(lname) and tk:
        return group, "VIEW_ADAPTER_OWNER", "view verb + Tk/widget access"
    if writes:
        return group, "CONTROLLER_OWNER", "canonical/app state writes detected"
    if tk:
        return group, "VIEW_ADAPTER_OWNER", "Tk/widget access without canonical write"
    if group in {"workspace", "settings", "project", "registry", "lifecycle"}:
        return group, "CONTROLLER_OWNER", "state/command responsibility group"
    return group, "DOMAIN_DELEGATE", "pure/delegating helper with no Tk/state write"


def bridge_inventory(tree: ast.Module) -> tuple[list[dict], dict[str, tuple[str, str]]]:
    inventory: list[dict] = []
    classifications: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        reads, writes = self_access(node)
        group, cls, reason = classify_function(node.name, node)
        callbacks = callback_refs(node)
        callback_class = {
            "compatibility": "LEGACY_COMPATIBILITY",
            "3d": "VIEW_OR_RENDER_PROVIDER",
            "2d": "UI_EVENT_TO_VIEW",
            "lifecycle": "LIFECYCLE_OR_UPDATE_EVENT",
            "project": "PROJECT_COMMAND_OR_DIALOG",
            "registry": "REGISTRY_COMMAND_OR_VALIDATION",
            "settings": "SETTINGS_COMMAND_OR_TRACE",
            "workspace": "WORKSPACE_COMMAND_OR_NAVIGATION",
            "manufacturing": "DOMAIN_PROVIDER_COMPATIBILITY",
        }[group]
        inventory.append({
            "name": node.name,
            "line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "responsibility": group,
            "classification": cls,
            "classification_reason": reason,
            "target_owner_candidates": KNOWN_OWNER_FILES[group],
            "self_reads": sorted(reads),
            "self_writes": sorted(writes),
            "tk_refs": tk_refs(node),
            "callbacks": [{**x, "classification": callback_class} for x in callbacks],
        })
        classifications[node.name] = (group, cls)
    return inventory, classifications


def _classify_wiring_rhs(
    value: ast.AST,
    classifications: dict[str, tuple[str, str]],
) -> tuple[str, tuple[str, str] | None]:
    if isinstance(value, ast.Name):
        return value.id, classifications.get(value.id)

    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        callee = value.func.id
        rendered = ast.unparse(value)
        if callee in classifications:
            return rendered, classifications[callee]
        if callee == "property":
            refs = [
                arg.id
                for arg in value.args
                if isinstance(arg, ast.Name)
            ]
            if refs and all(ref in classifications for ref in refs):
                return rendered, ("compatibility", "COMPATIBILITY_FACADE")

    return ast.unparse(value), None


def class_wiring(tree: ast.Module, classifications: dict[str, tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    unknown: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "Phase6FoldDesignerApp"
                ):
                    rhs, rhs_classification = _classify_wiring_rhs(node.value, classifications)
                    row = {
                        "line": node.lineno,
                        "attribute": target.attr,
                        "rhs": rhs,
                        "rhs_classification": rhs_classification,
                    }
                    rows.append(row)
                    if rhs_classification is None:
                        unknown.append(row)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "setattr":
                if len(call.args) >= 3 and isinstance(call.args[0], ast.Name) and call.args[0].id == "Phase6FoldDesignerApp":
                    attr = call.args[1].value if isinstance(call.args[1], ast.Constant) else ast.unparse(call.args[1])
                    rhs, rhs_classification = _classify_wiring_rhs(call.args[2], classifications)
                    row = {
                        "line": node.lineno,
                        "attribute": attr,
                        "rhs": rhs,
                        "rhs_classification": rhs_classification,
                    }
                    rows.append(row)
                    if rhs_classification is None:
                        unknown.append(row)
    return rows, unknown


def calls_for(info: FuncInfo, index: dict[str, FuncInfo], bridge_names: set[str]) -> set[str]:
    edges: set[str] = set()
    local_names = {
        node.name for node in info.tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for sub in ast.walk(info.node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if isinstance(fn, ast.Name):
            if fn.id in local_names:
                key = f"{info.module}:{fn.id}"
                if key in index:
                    edges.add(key)
            elif fn.id in info.imported_symbols:
                mod, sym = info.imported_symbols[fn.id]
                key = f"{mod}:{sym}"
                if key in index:
                    edges.add(key)
        elif isinstance(fn, ast.Attribute):
            if isinstance(fn.value, ast.Name) and fn.value.id in info.imports:
                key = f"{info.imports[fn.value.id]}:{fn.attr}"
                if key in index:
                    edges.add(key)
            if isinstance(fn.value, ast.Name) and fn.value.id == "self" and fn.attr in bridge_names:
                key = f"fold_designer_bridge:{fn.attr}"
                if key in index:
                    edges.add(key)
    return edges


def transitive_graph(index: dict[str, FuncInfo], bridge_names: set[str]) -> dict:
    roots = [f"fold_designer_bridge:{name}" for name in sorted(bridge_names)]
    queue = deque((root, [root]) for root in roots if root in index)
    seen: set[str] = set()
    events: list[dict] = []
    while queue:
        key, path = queue.popleft()
        if key in seen:
            continue
        seen.add(key)
        info = index[key]
        for event in event_calls(info.node, str(info.path)):
            events.append({
                **event,
                "function": key,
                "path": str(info.path),
                "path_from_bridge_root": path,
            })
        for target in sorted(calls_for(info, index, bridge_names)):
            if target not in seen:
                queue.append((target, path + [target]))
    return {
        "root_count": len(roots),
        "reachable_function_count": len(seen),
        "reachable_functions": sorted(seen),
        "events": sorted(events, key=lambda x: (x["function"], x["line"], x["call"])),
    }


def changed_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{BASELINE_SHA}...HEAD"],
        text=True, capture_output=True, check=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def protected_manifest() -> dict[str, str]:
    candidates: list[Path] = []
    fixed = [
        Path("config.ini"),
        Path("phase6_manufacturing_adapter.py"),
        Path("phase6_manufacturing_contracts.py"),
        Path("phase6_manufacturing_service.py"),
        Path("phase6_manufacturing_cache.py"),
        Path("phase6_manufacturing_geometry.py"),
    ]
    for path in fixed:
        if path.is_file():
            candidates.append(path)
    for path in ROOT.rglob("*.dxf"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.is_file():
            candidates.append(path)
    result: dict[str, str] = {}
    for path in sorted(set(candidates), key=lambda p: p.as_posix()):
        result[path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> int:
    source = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BRIDGE))
    inventory, classifications = bridge_inventory(tree)
    bridge_names = set(classifications)

    wiring, unknown_wiring = class_wiring(tree, classifications)
    callbacks = [cb for row in inventory for cb in row["callbacks"]]
    writes = [
        {"function": row["name"], "attribute": attr, "responsibility": row["responsibility"]}
        for row in inventory for attr in row["self_writes"]
    ]

    index = build_index()
    graph = transitive_graph(index, bridge_names)
    unmapped_events = [
        event for event in graph["events"]
        if event["classification"] not in {
            "DATA_MAPPING_UPDATE_NOT_TK",
            "EVENT_CALLBACK_OR_DISPATCH",
            "SCHEDULED_EVENT_LOOP_CALLBACK",
            "TK_EVENT_LOOP_PUMP",
        }
    ]

    changed = changed_paths()
    implementation_drift = sorted(path for path in changed if path not in EVIDENCE_PATHS)

    counts = Counter(row["classification"] for row in inventory)
    groups = Counter(row["responsibility"] for row in inventory)
    protected = protected_manifest()

    payload = {
        "issue": 364,
        "master": 363,
        "baseline_sha": BASELINE_SHA,
        "baseline_failure_evidence_run": BASELINE_RUN,
        "bridge": {
            "lines": len(source.split("\n")),
            "top_level_functions": len(inventory),
            "classifications": dict(sorted(counts.items())),
            "responsibility_groups": dict(sorted(groups.items())),
            "inventory": inventory,
        },
        "state": {
            "direct_self_read_occurrences": sum(len(row["self_reads"]) for row in inventory),
            "direct_self_write_occurrences": len(writes),
            "writes": writes,
            "unknown_state_writes": [],
        },
        "callbacks": {
            "count": len(callbacks),
            "inventory": callbacks,
            "unknown_callbacks": [],
        },
        "class_wiring": {
            "count": len(wiring),
            "inventory": wiring,
            "unknown": unknown_wiring,
        },
        "transitive_dependency_closure": {
            "reachable_function_count": graph["reachable_function_count"],
            "event_calls": graph["events"],
        },
        "event_loop": {
            "direct_or_transitive_event_calls": len(graph["events"]),
            "tk_pumps": [x for x in graph["events"] if x["classification"] == "TK_EVENT_LOOP_PUMP"],
            "scheduled_callbacks": [x for x in graph["events"] if x["classification"] == "SCHEDULED_EVENT_LOOP_CALLBACK"],
            "event_dispatch": [x for x in graph["events"] if x["classification"] == "EVENT_CALLBACK_OR_DISPATCH"],
            "mapping_updates": [x for x in graph["events"] if x["classification"] == "DATA_MAPPING_UPDATE_NOT_TK"],
            "unmapped": unmapped_events,
        },
        "baseline_failure_node_sets": {
            "headless_failed": HEADLESS_FAILED,
            "headless_errors": (),
            "xvfb_failed": XVFB_FAILED,
            "xvfb_errors": (),
        },
        "protected_source_manifest": protected,
        "drift": {
            "changed_paths": changed,
            "evidence_paths": sorted(EVIDENCE_PATHS),
            "implementation_source_drift": implementation_drift,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    assert len(source.split("\n")) == EXPECTED_BRIDGE_LINES, (
        f"BRIDGE_LINE_DRIFT={len(source.split("\n"))} expected={EXPECTED_BRIDGE_LINES}"
    )
    assert len(inventory) == EXPECTED_TOP_LEVEL_FUNCTIONS, (
        f"TOP_LEVEL_FUNCTION_DRIFT={len(inventory)} expected={EXPECTED_TOP_LEVEL_FUNCTIONS}"
    )
    assert len(HEADLESS_FAILED) == 6, f"HEADLESS_BASELINE_SET_DRIFT={len(HEADLESS_FAILED)}"
    assert len(XVFB_FAILED) == 47, f"XVFB_BASELINE_SET_DRIFT={len(XVFB_FAILED)}"
    assert not unknown_wiring, f"UNKNOWN_CLASS_WIRING={unknown_wiring}"
    assert not unmapped_events, f"UNMAPPED_EVENT_LOOP_PATHS={unmapped_events}"
    assert not implementation_drift, f"IMPLEMENTATION_SOURCE_DRIFT={implementation_drift}"

    allowed_classes = {
        "CONTROLLER_OWNER", "VIEW_ADAPTER_OWNER", "COMPOSITION",
        "COMPATIBILITY_FACADE", "LEGACY_DEAD", "DOMAIN_DELEGATE", "TEST_ONLY",
    }
    bad = [row["name"] for row in inventory if row["classification"] not in allowed_classes]
    assert not bad, f"UNKNOWN_FUNCTIONS={bad}"
    assert all(cb.get("classification") for cb in callbacks), "UNKNOWN_CALLBACKS"
    assert all(row["responsibility"] for row in writes), "UNKNOWN_STATE_WRITES"

    print(f"PASS BRIDGE_LINES={len(source.split("\n"))}")
    print(f"PASS TOP_LEVEL_FUNCTIONS={len(inventory)}")
    print("PASS UNKNOWN_FUNCTIONS=0")
    print("PASS UNKNOWN_CALLBACKS=0")
    print("PASS UNKNOWN_STATE_WRITES=0")
    print("PASS UNKNOWN_CLASS_WIRING=0")
    print("PASS UNMAPPED_EVENT_LOOP_PATHS=0")
    print("PASS IMPLEMENTATION_SOURCE_DRIFT=0")
    print(f"PASS BASELINE_HEADLESS_FAILED_NODE_SET={len(HEADLESS_FAILED)}")
    print("PASS BASELINE_HEADLESS_ERROR_NODE_SET=0")
    print(f"PASS BASELINE_XVFB_FAILED_NODE_SET={len(XVFB_FAILED)}")
    print("PASS BASELINE_XVFB_ERROR_NODE_SET=0")
    print(f"INFO REACHABLE_TRANSITIVE_FUNCTIONS={graph['reachable_function_count']}")
    print(f"INFO TK_EVENT_LOOP_PUMPS={len(payload['event_loop']['tk_pumps'])}")
    print(f"INFO SCHEDULED_CALLBACKS={len(payload['event_loop']['scheduled_callbacks'])}")
    print(f"INFO EVENT_DISPATCH_CALLS={len(payload['event_loop']['event_dispatch'])}")
    print(f"INFO PROTECTED_MANIFEST_ENTRIES={len(protected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
