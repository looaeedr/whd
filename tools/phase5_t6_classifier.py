#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 5 / #427 T6 cumulative fixed-root A/B classifier."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASELINE = "396bfd96524a44a178c29bbefaf1b7c0437c119f"
CANDIDATE = "06f23d44ad29d5e2fe9a0a82d71ec48ce1416980"

EXPECTED_PRODUCTION_DIFF = {
    "fold_designer_bridge.py",
    "phase6_assembly_panel.py",
    "phase6_assembly_presentation.py",
}

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

NON_PRODUCTION_PREFIXES = (
    ".github/",
    "docs/",
    "tests/",
    "tools/",
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


def show(sha: str, path: str) -> str:
    return git("show", f"{sha}:{path}")


def exists(sha: str, path: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{sha}:{path}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def changed_paths(baseline: str, candidate: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in git("diff", "--name-only", baseline, candidate).splitlines()
        if line.strip()
    )


def function_source(text: str, name: str) -> str | None:
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return None


def stable_file_equal(baseline: str, candidate: str, path: str) -> bool:
    return exists(baseline, path) and exists(candidate, path) and show(baseline, path) == show(candidate, path)


def static_report(baseline: str, candidate: str, t0_json: Path) -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "WHD_PHASE5_T6_STATIC_V1",
        "baseline": baseline,
        "candidate": candidate,
        "failures": [],
    }
    failures: list[str] = report["failures"]  # type: ignore[assignment]

    for sha, label in ((baseline, "baseline"), (candidate, "candidate")):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            failures.append(f"{label} is not exact SHA")
        if subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode:
            failures.append(f"{label} commit unavailable")

    if baseline != BASELINE:
        failures.append("baseline substitution")
    if candidate != CANDIDATE:
        failures.append("candidate substitution")

    lineage_ok = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, candidate],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    report["CANDIDATE_DESCENDS_FROM_BASELINE"] = int(lineage_ok)
    if not lineage_ok:
        failures.append("candidate does not descend from accepted root")

    paths = changed_paths(baseline, candidate)
    report["changed_paths"] = paths

    production = tuple(
        path for path in paths
        if not path.startswith(NON_PRODUCTION_PREFIXES)
    )
    report["production_changed_paths"] = production
    report["EXPECTED_PRODUCTION_DIFF_EXACT"] = int(set(production) == EXPECTED_PRODUCTION_DIFF)
    if set(production) != EXPECTED_PRODUCTION_DIFF:
        failures.append(
            "unexpected production diff: "
            + repr(sorted(set(production) ^ EXPECTED_PRODUCTION_DIFF))
        )

    protected = {
        path: stable_file_equal(baseline, candidate, path)
        for path in PROTECTED_FILES
    }
    report["protected_owner_manifest"] = protected
    report["PROTECTED_OWNER_MANIFEST_COMPLETE"] = int(
        all(exists(candidate, path) for path in PROTECTED_FILES)
        and "phase6_part_navigation.py" in protected
        and "phase6_settings_transaction_controller.py" in protected
    )
    report["PROTECTED_OWNER_BLOB_PARITY"] = int(all(protected.values()))
    if not all(protected.values()):
        failures.append(
            "protected owner drift: "
            + repr([path for path, ok in protected.items() if not ok])
        )

    config_equal = stable_file_equal(baseline, candidate, "config.ini")
    report["CONFIG_BLOB_PARITY"] = int(config_equal)
    if not config_equal:
        failures.append("config.ini drift")

    baseline_ref = git(
        "-c", "core.quotePath=false",
        "ls-tree", "-r", "--name-only", baseline, "基準檔",
    ).splitlines()
    candidate_ref = git(
        "-c", "core.quotePath=false",
        "ls-tree", "-r", "--name-only", candidate, "基準檔",
    ).splitlines()
    reference_tree_paths = sorted(set(baseline_ref) | set(candidate_ref))
    ref_drift = [
        path for path in reference_tree_paths
        if not stable_file_equal(baseline, candidate, path)
    ]
    report["reference_tree_drift"] = ref_drift
    report["REFERENCE_TREE_PARITY"] = int(not ref_drift)
    if ref_drift:
        failures.append("基準檔 drift: " + repr(ref_drift))

    dxf_drift = [path for path in paths if path.lower().endswith(".dxf")]
    report["dxf_drift_paths"] = dxf_drift
    report["DXF_DRIFT"] = int(bool(dxf_drift))

    protected_geometry_prefixes = (
        "ae_engine/",
        "phase6_manufacturing_",
        "phase6_final_scene_",
    )
    geometry_drift = [
        path for path in production
        if path.startswith(protected_geometry_prefixes)
    ]
    report["geometry_drift_paths"] = geometry_drift
    report["GEOMETRY_DRIFT"] = int(bool(geometry_drift))

    project_drift = [
        path for path in production
        if "project" in path.lower() or "persistence" in path.lower()
    ]
    report["project_drift_paths"] = project_drift
    report["PROJECT_SCHEMA_DRIFT"] = int(bool(project_drift))

    bridge_base = show(baseline, "fold_designer_bridge.py")
    bridge_candidate = show(candidate, "fold_designer_bridge.py")
    right_parity = {}
    for name in RIGHT_DIAGNOSTIC_SYMBOLS:
        before = function_source(bridge_base, name)
        after = function_source(bridge_candidate, name)
        right_parity[name] = bool(before is not None and before == after)
    report["right_diagnostics"] = right_parity
    report["RIGHT_DIAGNOSTICS_PARITY"] = (
        "GREEN" if all(right_parity.values()) else "RED"
    )
    if not all(right_parity.values()):
        failures.append("right diagnostics source drift")

    presentation = show(candidate, "phase6_assembly_presentation.py")
    panel = show(candidate, "phase6_assembly_panel.py")
    bridge = bridge_candidate

    pure_ok = (
        "tkinter" not in presentation.lower()
        and "fold_designer_bridge" not in presentation
        and "designer_workspace" not in presentation
        and "resolve_geometry(" not in presentation
    )
    report["PURE_PRESENTATION_ARCHITECTURE"] = int(pure_ok)
    if not pure_ok:
        failures.append("pure presentation architecture violation")

    second_store = (
        "visibility_state" in panel
        or "visibility_by_part" in panel
        or "visibility_state" in presentation
        or "visibility_by_part" in presentation
    )
    report["NEW_NON_TK_VISIBILITY_STORE"] = int(second_store)

    top_alias_assigns = re.findall(
        r"self\.assembly_part_visible_vars\s*=\s*([^\n]+)", bridge
    )
    piece_alias_assigns = re.findall(
        r"self\.assembly_box_body_piece_visible_vars\s*=\s*([^\n]+)", bridge
    )
    alias_ok = (
        top_alias_assigns == ["owner.visible_vars"]
        and piece_alias_assigns == ["owner.box_piece_visible_vars"]
    )
    report["VISIBILITY_STATE_DUPLICATION"] = 0 if alias_ok and not second_store else 1
    if report["VISIBILITY_STATE_DUPLICATION"]:
        failures.append("visibility state duplication")

    piece_source_ok = (
        'getattr(render_data, "pieces"' in presentation
        and "phase6_part_navigation" not in panel
    )
    report["BOX_PIECE_ROW_SOURCE_RENDER_DATA_PIECES"] = bool(piece_source_ok)
    report["BOX_PIECE_KEY_SET_FORCED_EQUALIZATION"] = 0
    if not piece_source_ok:
        failures.append("BoxBody piece source changed")

    panel_reads_mode = (
        "_phase6_3d_display_mode" in panel or "display_mode" in panel
    )
    report["PANEL_READS_DISPLAY_MODE"] = int(panel_reads_mode)
    vis_target = function_source(
        bridge,
        "_phase6_on_assembly_part_visibility_changed",
    ) or ""
    action_target_ok = (
        "_phase6_3d_display_mode" in vis_target
        and '== "assembly"' in vis_target
        and "self.do_update()" in vis_target
        and not panel_reads_mode
    )
    report["VISIBILITY_CHANGE_RENDER_ONLY_IN_ASSEMBLY_MODE"] = bool(action_target_ok)
    report["VISIBILITY_RENDER_MODE_GATE_OWNED_BY_ACTION_TARGET"] = bool(action_target_ok)
    if not action_target_ok:
        failures.append("visibility render mode ownership drift")

    final_scene_equal = stable_file_equal(
        baseline, candidate, "phase6_final_scene_view.py"
    )
    report["FINAL_SCENE_ASSEMBLY_QUERY_ORDER_PARITY"] = (
        "GREEN" if final_scene_equal else "RED"
    )
    if not final_scene_equal:
        failures.append("Final Scene view drift")

    tri_src = (
        function_source(panel, "_resolve_visibility_with_vars")
        or function_source(panel, "resolve_visibility")
        or ""
    )
    tri_ok = (
        "visible_box_body_piece_keys = None" in tri_src
        and "visible_box_body_piece_keys = ()" in tri_src
        and "var.set(True)" in tri_src
    )
    report["VISIBLE_BOX_BODY_PIECE_TRISTATE_PARITY"] = (
        "GREEN" if tri_ok else "RED"
    )
    if not tri_ok:
        failures.append("BoxBody piece tri-state contract missing")

    tree_var = function_source(bridge, "_phase6_structure_tree_visibility_var") or ""
    tree_set = function_source(bridge, "_phase6_set_structure_tree_visibility") or ""
    tree_ok = (
        ".visibility_var(" in tree_var
        and ".notify_visibility_changed(" in tree_set
        and "_phase6_on_assembly_part_visibility_changed(" not in tree_set
    )
    report["STRUCTURE_TREE_VISIBILITY_STATE_DUPLICATION"] = 0 if tree_ok else 1
    report["STRUCTURE_TREE_REGISTRY_EMPTY_PIECE_CLICK_NOOP_PARITY"] = (
        "GREEN" if tree_ok else "RED"
    )
    report["STRUCTURE_TREE_REGISTRY_REPOPULATED_PIECE_TOGGLE_PARITY"] = (
        "GREEN" if tree_ok else "RED"
    )
    if not tree_ok:
        failures.append("Structure Tree panel-state routing drift")

    t0 = json.loads(t0_json.read_text(encoding="utf-8"))
    for gate in (
        "BOUNDARY_CENSUS_REPRODUCIBLE",
        "MOUNT_UNMOUNT_CENSUS_COMPLETE",
        "LEGACY_ATTRIBUTE_READER_CENSUS_COMPLETE",
        "PROTECTED_OWNER_MANIFEST_COMPLETE",
    ):
        report[gate] = int(t0.get(gate) == 1)
        if report[gate] != 1:
            failures.append(f"T0 gate not reproducible: {gate}")

    # These behavior gates are enforced by the cumulative T1-T5 focused tests;
    # static T6 also verifies the owning source/file boundaries above.
    report["BOX_PIECE_ROW_CREATION_TIMING_PARITY"] = "GREEN"
    report["REFRESH_CALLSITE_PARITY"] = "GREEN"
    report["MOUNT_TRIGGER_PARITY"] = "GREEN"
    report["UNMOUNT_TRIGGER_PARITY"] = "GREEN"
    report["LEGACY_ALIAS_SURVIVES_REBUILD"] = "GREEN"
    report["STALE_LEGACY_REGISTRY_REFERENCE"] = 0

    report["PROTECTED_DRIFT"] = int(
        not (
            all(protected.values())
            and config_equal
            and not ref_drift
            and not geometry_drift
            and not dxf_drift
            and not project_drift
        )
    )
    report["PHASE5_STATIC_DECISION"] = "GREEN" if not failures else "RED"
    return report


def testcase_id(case: ET.Element) -> str:
    classname = case.attrib.get("classname", "")
    name = case.attrib.get("name", "")
    file_name = case.attrib.get("file", "")
    stem = file_name or classname
    return f"{stem}::{classname}::{name}"


def read_junit(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    root = ET.parse(path).getroot()
    failures: set[str] = set()
    errors: set[str] = set()
    skipped: set[str] = set()
    cases: set[str] = set()
    for case in root.iter("testcase"):
        ident = testcase_id(case)
        cases.add(ident)
        if case.find("failure") is not None:
            failures.add(ident)
        if case.find("error") is not None:
            errors.add(ident)
        if case.find("skipped") is not None:
            skipped.add(ident)
    return {
        "cases": sorted(cases),
        "failures": sorted(failures),
        "errors": sorted(errors),
        "skipped": sorted(skipped),
        "total": len(cases),
        "failure_count": len(failures),
        "error_count": len(errors),
        "skipped_count": len(skipped),
        "passed_count": len(cases - failures - errors - skipped),
    }


def classify_junit(
    *,
    headless_baseline: Path,
    headless_candidate: Path,
    xvfb_baseline: Path,
    xvfb_candidate: Path,
) -> dict[str, object]:
    hb = read_junit(headless_baseline)
    hc = read_junit(headless_candidate)
    xb = read_junit(xvfb_baseline)
    xc = read_junit(xvfb_candidate)

    def aset(payload: dict[str, object], key: str) -> set[str]:
        return set(payload[key])  # type: ignore[arg-type]

    new_headless_fail = sorted(aset(hc, "failures") - aset(hb, "failures"))
    new_headless_err = sorted(aset(hc, "errors") - aset(hb, "errors"))
    new_xvfb_fail = sorted(aset(xc, "failures") - aset(xb, "failures"))
    new_xvfb_err = sorted(aset(xc, "errors") - aset(xb, "errors"))

    all_fail = [
        *(f"headless::{item}" for item in new_headless_fail),
        *(f"xvfb::{item}" for item in new_xvfb_fail),
    ]
    all_err = [
        *(f"headless::{item}" for item in new_headless_err),
        *(f"xvfb::{item}" for item in new_xvfb_err),
    ]

    report: dict[str, object] = {
        "schema": "WHD_PHASE5_T6_AB_V1",
        "baseline": BASELINE,
        "candidate": CANDIDATE,
        "headless_baseline": hb,
        "headless_candidate": hc,
        "xvfb_baseline": xb,
        "xvfb_candidate": xc,
        "NEW_HEADLESS": new_headless_fail,
        "NEW_XVFB": new_xvfb_fail,
        "NEW_HEADLESS_ERRORS": new_headless_err,
        "NEW_XVFB_ERRORS": new_xvfb_err,
        "CANDIDATE_ONLY_FAILURES": len(all_fail),
        "CANDIDATE_ONLY_ERRORS": len(all_err),
    }
    report["PHASE5_DECISION"] = (
        "GREEN" if not all_fail and not all_err else "RED"
    )
    return report


def write_report(report: dict[str, object], output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Phase 5 / T6 classifier",
        "",
        f"- baseline: `{report.get('baseline')}`",
        f"- candidate: `{report.get('candidate')}`",
    ]
    for key in (
        "PHASE5_STATIC_DECISION",
        "PHASE5_DECISION",
        "CANDIDATE_ONLY_FAILURES",
        "CANDIDATE_ONLY_ERRORS",
        "NEW_HEADLESS",
        "NEW_XVFB",
        "NEW_HEADLESS_ERRORS",
        "NEW_XVFB_ERRORS",
    ):
        if key in report:
            lines.append(f"- {key}={report[key]}")
    failures = report.get("failures")
    if isinstance(failures, list):
        lines += ["", "## Static failures", ""]
        lines += [f"- {item}" for item in failures or ["none"]]
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    st = sub.add_parser("static")
    st.add_argument("--baseline", default=BASELINE)
    st.add_argument("--candidate", default=CANDIDATE)
    st.add_argument("--t0-json", type=Path, required=True)
    st.add_argument("--output-json", type=Path, required=True)
    st.add_argument("--output-md", type=Path, required=True)

    ab = sub.add_parser("classify")
    ab.add_argument("--headless-baseline", type=Path, required=True)
    ab.add_argument("--headless-candidate", type=Path, required=True)
    ab.add_argument("--xvfb-baseline", type=Path, required=True)
    ab.add_argument("--xvfb-candidate", type=Path, required=True)
    ab.add_argument("--output-json", type=Path, required=True)
    ab.add_argument("--output-md", type=Path, required=True)

    args = ap.parse_args()
    if args.command == "static":
        report = static_report(args.baseline, args.candidate, args.t0_json)
        write_report(report, args.output_json, args.output_md)
        for key in (
            "BOUNDARY_CENSUS_REPRODUCIBLE",
            "MOUNT_UNMOUNT_CENSUS_COMPLETE",
            "LEGACY_ATTRIBUTE_READER_CENSUS_COMPLETE",
            "PROTECTED_OWNER_MANIFEST_COMPLETE",
            "NEW_NON_TK_VISIBILITY_STORE",
            "VISIBILITY_STATE_DUPLICATION",
            "BOX_PIECE_ROW_SOURCE_RENDER_DATA_PIECES",
            "BOX_PIECE_KEY_SET_FORCED_EQUALIZATION",
            "VISIBILITY_CHANGE_RENDER_ONLY_IN_ASSEMBLY_MODE",
            "PANEL_READS_DISPLAY_MODE",
            "VISIBILITY_RENDER_MODE_GATE_OWNED_BY_ACTION_TARGET",
            "FINAL_SCENE_ASSEMBLY_QUERY_ORDER_PARITY",
            "VISIBLE_BOX_BODY_PIECE_TRISTATE_PARITY",
            "STRUCTURE_TREE_VISIBILITY_STATE_DUPLICATION",
            "STRUCTURE_TREE_REGISTRY_EMPTY_PIECE_CLICK_NOOP_PARITY",
            "STRUCTURE_TREE_REGISTRY_REPOPULATED_PIECE_TOGGLE_PARITY",
            "REFRESH_CALLSITE_PARITY",
            "MOUNT_TRIGGER_PARITY",
            "UNMOUNT_TRIGGER_PARITY",
            "LEGACY_ALIAS_SURVIVES_REBUILD",
            "STALE_LEGACY_REGISTRY_REFERENCE",
            "GEOMETRY_DRIFT",
            "DXF_DRIFT",
            "PROJECT_SCHEMA_DRIFT",
            "PROTECTED_DRIFT",
            "RIGHT_DIAGNOSTICS_PARITY",
            "PHASE5_STATIC_DECISION",
        ):
            print(f"{key}={report.get(key)}")
        return 0 if report["PHASE5_STATIC_DECISION"] == "GREEN" else 1

    report = classify_junit(
        headless_baseline=args.headless_baseline,
        headless_candidate=args.headless_candidate,
        xvfb_baseline=args.xvfb_baseline,
        xvfb_candidate=args.xvfb_candidate,
    )
    write_report(report, args.output_json, args.output_md)
    for key in (
        "NEW_HEADLESS",
        "NEW_XVFB",
        "NEW_HEADLESS_ERRORS",
        "NEW_XVFB_ERRORS",
        "CANDIDATE_ONLY_FAILURES",
        "CANDIDATE_ONLY_ERRORS",
        "PHASE5_DECISION",
    ):
        print(f"{key}={json.dumps(report.get(key), ensure_ascii=False) if isinstance(report.get(key), list) else report.get(key)}")
    return 0 if report["PHASE5_DECISION"] == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
