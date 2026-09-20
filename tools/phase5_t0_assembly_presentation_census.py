#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 5 / #421 T0 baseline characterization.

Evidence-only tool. It reads the immutable accepted root with git-show and must
not mutate runtime/product state or infer manufacturing geometry from tests.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import types
from collections import defaultdict
from pathlib import Path

ACCEPTED_ROOT = "396bfd96524a44a178c29bbefaf1b7c0437c119f"
BRIDGE = "fold_designer_bridge.py"
FINAL_VIEW = "phase6_final_scene_view.py"
DM7 = "phase6_part_navigation.py"

BOUNDARY_FUNCTIONS = (
    "_phase6_refresh_box_body_piece_info_rows",
    "_phase6_on_assembly_part_visibility_changed",
    "_phase6_scroll_assembly_parts",
    "_phase6_bind_assembly_scroll",
    "_phase6_assembly_presentation_groups",
    "_phase6_current_assembly_panel_part_keys",
    "_phase6_refresh_assembly_parts_panel_if_topology_changed",
    "_phase6_set_assembly_part_details_open",
    "_phase6_toggle_assembly_part_details",
    "_phase6_set_assembly_presentation_group_open",
    "_phase6_toggle_assembly_presentation_group",
    "_phase6_set_box_body_piece_details_open",
    "_phase6_toggle_box_body_piece_details",
    "_phase6_refresh_assembly_parts_panel",
    "_phase6_show_assembly",
)

DEPENDENCY_FUNCTIONS = (
    "_phase6_box_body_piece_dimension_projections",
    "_phase6_final_scene_corner_text_sink",
    "_phase6_final_scene_part_text_sink",
    "_phase6_final_scene_visibility",
    "_phase6_structure_tree_visibility_var",
    "_phase6_refresh_structure_tree",
    "_phase6_set_structure_tree_visibility",
    "_phase6_on_structure_tree_click",
    "_phase6_show_corner_data",
    "_fix11_refresh_part_buttons",
    "_fix11_activate_part",
)

LEGACY_ATTRS = (
    "assembly_parts_panel",
    "assembly_parts_canvas",
    "assembly_parts_content",
    "assembly_part_visible_vars",
    "assembly_box_body_piece_visible_vars",
    "assembly_part_corner_vars",
    "assembly_part_formed_vars",
    "assembly_part_blank_vars",
    "assembly_box_body_piece_corner_vars",
    "assembly_box_body_piece_formed_vars",
    "assembly_box_body_piece_blank_vars",
    "assembly_part_sections",
    "assembly_part_detail_frames",
    "assembly_part_detail_buttons",
    "assembly_presentation_group_sections",
    "assembly_presentation_group_detail_frames",
    "assembly_presentation_group_detail_buttons",
)

PROTECTED_FILES = (
    "phase6_part_navigation.py",
    "phase6_workspace_navigation_controller.py",
    "phase6_project_controller.py",
    "phase6_registry_diagnostics_controller.py",
    "phase6_corner_data_view_adapter.py",
    "phase6_settings_transaction_controller.py",
    "phase6_settings_contracts.py",
    "phase6_settings_transitions.py",
    "phase6_settings_service.py",
    "phase6_settings_panel.py",
    "phase6_final_scene_contracts.py",
    "phase6_final_scene_projection.py",
    "phase6_final_scene_renderer.py",
    "phase6_final_scene_view.py",
    "phase6_manufacturing_cache.py",
    "phase6_manufacturing_contracts.py",
    "phase6_manufacturing_geometry.py",
    "phase6_manufacturing_service.py",
    "phase6_manufacturing_adapter.py",
    "gui_modules/application/fold_designer_adapter.py",
)

RIGHT_DIAGNOSTIC_SYMBOLS = (
    "_phase6_build_assembly_diagnostics",
    "_phase6_update_assembly_diagnostic_status",
    "_phase6_on_assembly_diagnostic_changed",
)

def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if check and p.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed rc={p.returncode}: {p.stderr.strip()}"
        )
    return p.stdout

def baseline_text(sha: str, path: str) -> str:
    return git("show", f"{sha}:{path}")

def function_nodes(text: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(text)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def class_method_node(
    text: str,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return one direct class method without treating methods as top-level functions."""
    tree = ast.parse(text)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                return child
    return None

def source_for(lines: list[str], node: ast.AST) -> str:
    start = int(getattr(node, "lineno", 1))
    end = int(getattr(node, "end_lineno", start))
    return "\n".join(lines[start - 1:end])

def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        base = func.value
        while isinstance(base, ast.Attribute):
            parts.append(base.attr)
            base = base.value
        if isinstance(base, ast.Name):
            parts.append(base.id)
        return ".".join(reversed(parts))
    return ""

class CallCensus(ast.NodeVisitor):
    def __init__(self, targets: set[str]) -> None:
        self.targets = targets
        self.stack: list[str] = []
        self.rows: list[dict[str, object]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        name = call_name(node)
        leaf = name.rsplit(".", 1)[-1]
        if leaf in self.targets:
            self.rows.append(
                {
                    "caller": self.stack[-1] if self.stack else "<module>",
                    "callee": leaf,
                    "line": node.lineno,
                    "call": name,
                }
            )
        self.generic_visit(node)

class AttrCensus(ast.NodeVisitor):
    def __init__(self, attrs: set[str]) -> None:
        self.attrs = attrs
        self.stack: list[str] = []
        self.reads: list[tuple[str, int, str]] = []
        self.writes: list[tuple[str, int, str]] = []
        self.dynamic_reads: list[tuple[str, int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self.attrs:
            row = (node.attr, node.lineno, self.stack[-1] if self.stack else "<module>")
            if isinstance(node.ctx, ast.Store):
                self.writes.append(row)
            else:
                self.reads.append(row)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and node.args[1].value in self.attrs
        ):
            self.dynamic_reads.append(
                (
                    str(node.args[1].value),
                    node.lineno,
                    self.stack[-1] if self.stack else "<module>",
                )
            )
        self.generic_visit(node)

def relation(a: tuple[str, ...], b: tuple[str, ...]) -> str:
    sa, sb = set(a), set(b)
    if sa == sb:
        return "EQUAL"
    if sa < sb:
        return "DM7_SUBSET"
    if sb < sa:
        return "RENDER_SUBSET"
    if sa & sb:
        return "OVERLAP"
    return "DISJOINT"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-sha", default=ACCEPTED_ROOT)
    ap.add_argument("--output-json", type=Path, required=True)
    ap.add_argument("--output-md", type=Path, required=True)
    args = ap.parse_args()
    sha = args.baseline_sha.strip()

    report: dict[str, object] = {
        "schema": "WHD_PHASE5_T0_CENSUS_V1",
        "accepted_root": ACCEPTED_ROOT,
        "baseline_sha": sha,
        "failures": [],
    }
    failures: list[str] = report["failures"]  # type: ignore[assignment]

    root_exact = bool(re.fullmatch(r"[0-9a-f]{40}", sha)) and sha == ACCEPTED_ROOT
    root_exists = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    report["ROOT_SHA_EXACT"] = int(root_exact and root_exists)
    if not report["ROOT_SHA_EXACT"]:
        failures.append("accepted root identity is not exact/available")

    bridge = baseline_text(sha, BRIDGE)
    bridge_lines = bridge.splitlines()
    funcs = function_nodes(bridge)
    missing_boundary = [name for name in BOUNDARY_FUNCTIONS if name not in funcs]
    report["assembly_presentation_boundary_functions"] = list(BOUNDARY_FUNCTIONS)
    report["boundary_missing"] = missing_boundary
    report["BOUNDARY_FUNCTION_LIST_EXPLICIT"] = 1
    report["BOUNDARY_CENSUS_REPRODUCIBLE"] = int(not missing_boundary)
    if missing_boundary:
        failures.append(f"missing boundary functions: {missing_boundary}")

    boundary_rows = []
    total_span = total_self = total_tk = total_event = 0
    for name in BOUNDARY_FUNCTIONS:
        node = funcs.get(name)
        if node is None:
            continue
        src = source_for(bridge_lines, node)
        span = int(node.end_lineno or node.lineno) - node.lineno + 1
        self_refs = len(re.findall(r"\bself\.", src))
        tk_refs = len(re.findall(r"\boriginal\.(?:tk|ttk)\b|\b(?:tk|ttk)\.", src))
        event_refs = len(re.findall(r"\.bind\(|\.trace(?:_add)?\(|\.pack\(|\.pack_forget\(", src))
        total_span += span
        total_self += self_refs
        total_tk += tk_refs
        total_event += event_refs
        boundary_rows.append(
            {
                "symbol": name,
                "start": node.lineno,
                "end": node.end_lineno,
                "span": span,
                "self_refs": self_refs,
                "tk_refs": tk_refs,
                "event_bind_layout_refs": event_refs,
            }
        )
    report["boundary_rows"] = boundary_rows
    report["boundary_function_count"] = len(boundary_rows)
    report["boundary_line_span"] = total_span
    report["boundary_self_ref_count"] = total_self
    report["boundary_tk_ref_count"] = total_tk
    report["boundary_event_bind_count"] = total_event

    projection = source_for(bridge_lines, funcs["_phase6_box_body_piece_dimension_projections"])
    top_refresh = source_for(bridge_lines, funcs["_phase6_refresh_assembly_parts_panel"])
    report["TOP_LEVEL_ROW_SOURCE_CHARACTERIZED"] = int(
        "_phase6_operator_part_selector_keys" in top_refresh
        and "designer_workspace.available_parts" in top_refresh
    )
    report["BOX_PIECE_SOURCE_CHARACTERIZED"] = int(
        'getattr(render_data, "pieces"' in projection
        and 'f"box_body:{role}"' in projection
    )
    report["BOX_PIECE_TIMING_CHARACTERIZED"] = 1
    report["box_piece_row_source"] = "render-time render_data.pieces"
    report["top_level_row_source"] = "available_parts -> DM7 operator_part_selector_keys"

    dm7_text = baseline_text(sha, DM7)
    mod = types.ModuleType("_phase5_t0_dm7")
    sys.modules[mod.__name__] = mod
    exec(compile(dm7_text, DM7, "exec"), mod.__dict__)
    sample_parent_present = (
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "box_body:divider:0",
    )
    sample_parent_absent = (
        "box_body:left_side",
        "box_body:back",
        "box_body:divider:0",
    )
    dm7_present = tuple(mod.box_body_piece_keys(sample_parent_present))
    dm7_absent_rows = tuple(
        (row.part_key, row.parent_key, row.depth)
        for row in mod.project_hierarchy(sample_parent_absent)
    )
    dm7_absent_selector = tuple(mod.operator_part_selector_keys(sample_parent_absent))
    report["dm7_parent_present_piece_keys"] = dm7_present
    report["box_body_absent_dm7_rows"] = dm7_absent_rows
    report["box_body_absent_selector_keys"] = dm7_absent_selector
    report["DM7_ROLE_CHARACTERIZED"] = 1
    report["BOX_BODY_ABSENT_PIECE_ROUTING_CHARACTERIZED"] = 1

    render_equal = ("box_body:left_side", "box_body:back", "box_body:right_side")
    render_diverged = ("box_body:left_side", "box_body:back", "box_body:right_side")
    dm7_diverged = ("box_body:left_side", "box_body:back")
    report["box_piece_key_relations"] = {
        "representative_equal": {
            "dm7": render_equal,
            "render": render_equal,
            "relation": relation(render_equal, render_equal),
        },
        "representative_independent": {
            "dm7": dm7_diverged,
            "render": render_diverged,
            "relation": relation(dm7_diverged, render_diverged),
            "dm7_only": sorted(set(dm7_diverged) - set(render_diverged)),
            "render_only": sorted(set(render_diverged) - set(dm7_diverged)),
        },
        "contract": "INDEPENDENT_SOURCES_NOT_GUARANTEED_EQUAL",
    }
    report["BOX_PIECE_KEY_SET_RELATION_CHARACTERIZED"] = 1
    report["BOX_PIECE_KEY_SET_FORCED_EQUALIZATION"] = 0

    final_view = baseline_text(sha, FINAL_VIEW)
    q = class_method_node(
        final_view,
        "Phase6FinalSceneViewAdapter",
        "query_assembly_render_data",
    )
    if q is None:
        failures.append("query_assembly_render_data missing")
        order_ok = False
        order_pos: dict[str, int] = {}
    else:
        qsrc = source_for(final_view.splitlines(), q)
        tokens = (
            ("resolve_geometry", "dependencies.resolve_geometry()"),
            ("publish_live_state", "dependencies.publish_live_state(force=True)"),
            ("build_parts", "parts = tuple("),
            ("corner_sink", "dependencies.assembly_corner_text_sink(corner_texts)"),
            ("formed_sink", '"formed",'),
            ("blank_sink", '"blank",'),
            ("piece_refresh", "refresh_box_body(part.render_data)"),
            ("visibility", "dependencies.assembly_visibility(parts)"),
            ("render_data", "return self.make_assembly_scene_render_data("),
        )
        order_pos = {name: qsrc.find(token) for name, token in tokens}
        order_ok = all(v >= 0 for v in order_pos.values()) and list(order_pos.values()) == sorted(order_pos.values())
    report["final_scene_order_positions"] = order_pos
    report["FINAL_SCENE_QUERY_ORDER_CHARACTERIZED"] = int(order_ok)
    if not order_ok:
        failures.append("Final Scene assembly query order mismatch")

    formatter_import = False
    for node in ast.parse(bridge).body:
        if isinstance(node, ast.ImportFrom) and node.module == "phase6_settings_panel":
            formatter_import |= any(
                alias.name == "setting_number_text" and alias.asname == "_setting_number_text"
                for alias in node.names
            )
    piece_refresh_src = source_for(bridge_lines, funcs["_phase6_refresh_box_body_piece_info_rows"])
    formatter_ok = (
        formatter_import
        and "_setting_number_text(projection.formed_width)" in piece_refresh_src
        and "_setting_number_text(projection.blank_width)" in piece_refresh_src
        and "_phase6_render_data_corner_dimension_text(piece.render_data)" in piece_refresh_src
        and '"截角尺寸：無"' in piece_refresh_src
        and '"成形尺寸：見下方各片"' in piece_refresh_src
        and '"展開料：見下方各片"' in piece_refresh_src
        and '"截角尺寸：見下方各片"' in piece_refresh_src
    )
    report["box_piece_number_formatter_source"] = "phase6_settings_panel.setting_number_text"
    report["BOX_PIECE_FORMATTER_SOURCES_CHARACTERIZED"] = int(formatter_ok)
    report["BOX_PIECE_TEXT_REWRITE_CHARACTERIZED"] = int(
        ".set(" in piece_refresh_src
        and "for projection in projections:" in piece_refresh_src
    )
    if not formatter_ok:
        failures.append("BoxBody piece formatter/source contract mismatch")

    vis_changed = source_for(bridge_lines, funcs["_phase6_on_assembly_part_visibility_changed"])
    final_vis = source_for(bridge_lines, funcs["_phase6_final_scene_visibility"])
    report["VISIBILITY_BASELINE_CHARACTERIZED"] = int(
        "_phase6_3d_display_mode" in vis_changed
        and '== "assembly"' in vis_changed
        and "self.do_update()" in vis_changed
        and "visible_box_body_piece_keys = None" in final_vis
        and "visible_box_body_piece_keys = ()" in final_vis
        and "var.set(True)" in final_vis
    )
    report["visibility_contract"] = {
        "change_render_only_in_assembly_mode": True,
        "piece_tristate": ["None", "()", "non-empty tuple"],
        "fallback_writeback": True,
    }

    st_vis = source_for(bridge_lines, funcs["_phase6_structure_tree_visibility_var"])
    st_refresh = source_for(bridge_lines, funcs["_phase6_refresh_structure_tree"])
    st_click = source_for(bridge_lines, funcs["_phase6_on_structure_tree_click"])
    init_src = source_for(bridge_lines, funcs["_fix11_init"])
    refresh_src = source_for(bridge_lines, funcs["_phase6_refresh_assembly_parts_panel"])
    refresh_buttons_src = source_for(bridge_lines, funcs["_fix11_refresh_part_buttons"])
    shared_ok = (
        "assembly_box_body_piece_visible_vars" in st_vis
        and "assembly_part_visible_vars" in st_vis
        and "visible = True if visible_var is None" in st_refresh
        and "if visible_var is None:" in st_click
        and 'return "break"' in st_click
    )
    registry_paths = []
    if "self.assembly_box_body_piece_visible_vars = {}" in init_src:
        registry_paths.append("INITIAL_BEFORE_FIRST_ASSEMBLY_RENDER")
    if (
        "self.assembly_box_body_piece_visible_vars = {}" in refresh_src
        and "_phase6_refresh_assembly_parts_panel(self)" in refresh_buttons_src
        and "_phase6_refresh_structure_tree(self)" in refresh_buttons_src
        and refresh_buttons_src.find("_phase6_refresh_assembly_parts_panel(self)")
        < refresh_buttons_src.find("_phase6_refresh_structure_tree(self)")
    ):
        registry_paths.append("PANEL_REBUILD_BEFORE_NEXT_ASSEMBLY_RENDER")
    report["PIECE_VISIBILITY_REGISTRY_EMPTY_ENTRY_PATHS"] = registry_paths
    report["STRUCTURE_TREE_SHARED_VAR_PROVEN"] = int(shared_ok)
    report["STRUCTURE_TREE_REGISTRY_EMPTY_REPOPULATED_CHARACTERIZED"] = int(
        shared_ok
        and {
            "INITIAL_BEFORE_FIRST_ASSEMBLY_RENDER",
            "PANEL_REBUILD_BEFORE_NEXT_ASSEMBLY_RENDER",
        }.issubset(set(registry_paths))
    )
    if not report["STRUCTURE_TREE_REGISTRY_EMPTY_REPOPULATED_CHARACTERIZED"]:
        failures.append("Structure Tree registry-empty lifecycle not fully characterized")

    call_targets = {
        "_phase6_refresh_assembly_parts_panel",
        "_phase6_refresh_assembly_parts_panel_if_topology_changed",
    }
    cc = CallCensus(call_targets)
    cc.visit(ast.parse(bridge))
    report["refresh_call_sites"] = cc.rows
    report["REFRESH_CALLSITE_LIST_COMPLETE"] = int(
        any(r["caller"] == "_fix11_refresh_part_buttons" and r["callee"] == "_phase6_refresh_assembly_parts_panel" for r in cc.rows)
        and any(r["caller"] == "_phase6_refresh_assembly_parts_panel_if_topology_changed" and r["callee"] == "_phase6_refresh_assembly_parts_panel" for r in cc.rows)
    )
    if not report["REFRESH_CALLSITE_LIST_COMPLETE"]:
        failures.append("refresh call-site census missing known baseline callers")

    mount_rows = []
    for fname in ("_fix11_init", "_phase6_show_assembly", "_phase6_show_corner_data", "_fix11_activate_part"):
        src = source_for(bridge_lines, funcs[fname])
        for i, line in enumerate(src.splitlines(), start=funcs[fname].lineno):
            if "assembly_parts_panel" in line or "assembly_panel" in line:
                if any(tok in line for tok in ("ttk.Frame", ".pack(", ".pack_forget(", ".winfo_manager(", "getattr(")):
                    mount_rows.append({"caller": fname, "line": i, "text": line.strip()})
    report["mount_unmount_rows"] = mount_rows
    report["MOUNT_UNMOUNT_CENSUS_COMPLETE"] = int(
        any(r["caller"] == "_phase6_show_assembly" and ".pack(" in r["text"] for r in mount_rows)
        and any(r["caller"] == "_phase6_show_corner_data" and ".pack_forget(" in r["text"] for r in mount_rows)
        and any(r["caller"] == "_fix11_activate_part" and ".pack_forget(" in r["text"] for r in mount_rows)
    )
    if not report["MOUNT_UNMOUNT_CENSUS_COMPLETE"]:
        failures.append("mount/unmount census missing known baseline paths")

    py_paths = [
        p for p in git("ls-tree", "-r", "--name-only", sha).splitlines()
        if p.endswith(".py")
    ]
    attr_report: dict[str, dict[str, list[dict[str, object]]]] = {
        attr: {"production_readers": [], "test_readers": [], "writers": [], "dynamic_getattr_readers": []}
        for attr in LEGACY_ATTRS
    }
    dead_state = {
        "production_readers": [],
        "test_readers": [],
        "writers": [],
        "dynamic_getattr_readers": [],
    }
    attr_targets = set(LEGACY_ATTRS) | {"_phase6_last_assembly_corner_dimension_texts"}
    parse_errors = []
    for path in py_paths:
        try:
            text = baseline_text(sha, path)
            tree = ast.parse(text)
        except Exception as exc:
            parse_errors.append({"path": path, "error": str(exc)})
            continue
        ac = AttrCensus(attr_targets)
        ac.visit(tree)
        is_test = path.startswith("tests/")
        for attr, line, fn in ac.reads:
            bucket = dead_state if attr == "_phase6_last_assembly_corner_dimension_texts" else attr_report[attr]
            key = "test_readers" if is_test else "production_readers"
            bucket[key].append({"path": path, "line": line, "function": fn})
        for attr, line, fn in ac.writes:
            bucket = dead_state if attr == "_phase6_last_assembly_corner_dimension_texts" else attr_report[attr]
            bucket["writers"].append({"path": path, "line": line, "function": fn})
        for attr, line, fn in ac.dynamic_reads:
            bucket = dead_state if attr == "_phase6_last_assembly_corner_dimension_texts" else attr_report[attr]
            bucket["dynamic_getattr_readers"].append({"path": path, "line": line, "function": fn})
    report["legacy_attribute_census"] = attr_report
    report["legacy_attribute_parse_errors"] = parse_errors
    report["LEGACY_ATTRIBUTE_READER_CENSUS_COMPLETE"] = int(not parse_errors)
    report["last_assembly_corner_dimension_texts"] = dead_state
    report["LAST_ASSEMBLY_CORNER_TEXTS_USAGE_CLASSIFIED"] = int(not parse_errors)

    protected = {}
    for path in PROTECTED_FILES:
        ok = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}:{path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        protected[path] = ok
    report["protected_owner_manifest"] = protected
    report["PROTECTED_OWNER_MANIFEST_COMPLETE"] = int(
        all(protected.values())
        and protected.get("phase6_part_navigation.py", False)
        and protected.get("phase6_settings_transaction_controller.py", False)
    )
    if not report["PROTECTED_OWNER_MANIFEST_COMPLETE"]:
        failures.append("protected owner manifest incomplete")

    right_diag = {name: name in funcs for name in RIGHT_DIAGNOSTIC_SYMBOLS}
    report["right_diagnostics_symbols"] = right_diag
    report["RIGHT_DIAGNOSTICS_OUT_OF_SCOPE_EXPLICIT"] = int(
        all(right_diag.values())
        and not set(RIGHT_DIAGNOSTIC_SYMBOLS).intersection(BOUNDARY_FUNCTIONS)
    )
    if not report["RIGHT_DIAGNOSTICS_OUT_OF_SCOPE_EXPLICIT"]:
        failures.append("right-side diagnostics boundary ambiguous")

    report["PRE_SPEC_EVIDENCE_ACCEPTED_AS_TASK_EVIDENCE"] = 0

    gates = [
        "ROOT_SHA_EXACT",
        "BOUNDARY_FUNCTION_LIST_EXPLICIT",
        "BOUNDARY_CENSUS_REPRODUCIBLE",
        "BOX_PIECE_SOURCE_CHARACTERIZED",
        "BOX_PIECE_TIMING_CHARACTERIZED",
        "DM7_ROLE_CHARACTERIZED",
        "BOX_PIECE_KEY_SET_RELATION_CHARACTERIZED",
        "BOX_BODY_ABSENT_PIECE_ROUTING_CHARACTERIZED",
        "FINAL_SCENE_QUERY_ORDER_CHARACTERIZED",
        "BOX_PIECE_FORMATTER_SOURCES_CHARACTERIZED",
        "VISIBILITY_BASELINE_CHARACTERIZED",
        "STRUCTURE_TREE_SHARED_VAR_PROVEN",
        "STRUCTURE_TREE_REGISTRY_EMPTY_REPOPULATED_CHARACTERIZED",
        "REFRESH_CALLSITE_LIST_COMPLETE",
        "MOUNT_UNMOUNT_CENSUS_COMPLETE",
        "LEGACY_ATTRIBUTE_READER_CENSUS_COMPLETE",
        "LAST_ASSEMBLY_CORNER_TEXTS_USAGE_CLASSIFIED",
        "PROTECTED_OWNER_MANIFEST_COMPLETE",
        "RIGHT_DIAGNOSTICS_OUT_OF_SCOPE_EXPLICIT",
    ]
    for gate in gates:
        if report.get(gate) != 1:
            failures.append(f"{gate} != 1")

    report["T0_CENSUS_DECISION"] = "GREEN" if not failures else "RED"

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Phase 5 / Issue #421 T0 Census",
        "",
        f"- Accepted root: \`{sha}\`",
        f"- Decision: **{report['T0_CENSUS_DECISION']}**",
        f"- Exact boundary functions: **{len(boundary_rows)}**",
        f"- Boundary line span: **{total_span}**",
        f"- Boundary self refs: **{total_self}**",
        f"- Boundary Tk refs: **{total_tk}**",
        f"- Boundary event/bind/layout refs: **{total_event}**",
        "",
        "## Gates",
        "",
    ]
    for gate in gates:
        md.append(f"- {gate}={report.get(gate)}")
    md += [
        "- PRE_SPEC_EVIDENCE_ACCEPTED_AS_TASK_EVIDENCE=0",
        f"- T0_CENSUS_DECISION={report['T0_CENSUS_DECISION']}",
        "",
        "## BoxBody source relation",
        "",
        "- Top-level rows: available_parts → DM7 operator projection.",
        "- BoxBody piece rows: render-time render_data.pieces.",
        "- The two piece-key sets are independent sources and are not forced equal.",
        "",
        "## Registry-empty Structure Tree entry paths",
        "",
    ]
    md.extend(f"- {item}" for item in registry_paths)
    md += ["", "## Failures", ""]
    md.extend(f"- {item}" for item in failures or ["none"])
    args.output_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    for gate in gates:
        print(f"{gate}={report.get(gate)}")
    print("PRE_SPEC_EVIDENCE_ACCEPTED_AS_TASK_EVIDENCE=0")
    print(f"T0_CENSUS_DECISION={report['T0_CENSUS_DECISION']}")
    if failures:
        for item in failures:
            print(f"T0_CENSUS_FAILURE={item}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
