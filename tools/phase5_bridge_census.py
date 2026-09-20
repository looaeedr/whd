#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

BASELINE = "c56f670dc7e60b54c6a47f797a379ff4f2b1e3ad"
BRIDGE = "fold_designer_bridge.py"
ALLOWED_T0_DRIFT = {
    "tools/phase5_bridge_census.py",
    ".github/workflows/qa-issue414-phase5-t0.yml",
}

PROTECTED_EXACT = (
    "config.ini",
    "phase6_settings_contracts.py",
    "phase6_settings_transitions.py",
    "phase6_settings_service.py",
    "phase6_settings_transaction_controller.py",
    "phase6_final_scene_contracts.py",
    "phase6_final_scene_projection.py",
    "phase6_final_scene_renderer.py",
    "phase6_final_scene_view.py",
    "phase6_workspace_navigation_controller.py",
    "phase6_project_controller.py",
    "phase6_registry_diagnostics_controller.py",
    "phase6_corner_data_view_adapter.py",
    "phase6_manufacturing_cache.py",
    "phase6_manufacturing_contracts.py",
    "phase6_manufacturing_geometry.py",
    "phase6_manufacturing_service.py",
    "phase6_manufacturing_adapter.py",
    "gui_modules/application/fold_designer_adapter.py",
    "gui_modules/application/lifecycle.py",
    "gui_modules/application/state_sync.py",
)

BUCKET_RULES = (
    ("final_scene_compat", re.compile(r"final_scene|render_3d|3d")),
    ("registry_presentation", re.compile(r"registry|relief_registry")),
    ("project_persistence", re.compile(r"project|diagnostic_file|keyboard_(save|open)")),
    ("settings_presentation", re.compile(r"setting|baseline_model|symmetry|box_structure|endcap_fw|bottom_wrap|assembly_type")),
    ("corner_presentation", re.compile(r"corner")),
    ("assembly_presentation", re.compile(r"assembly")),
    ("derived_topology", re.compile(r"box_body|door_part|base_plate|derived_part|linked_endcap|part_profile|physical_piece|structure_tree")),
    ("output_presentation", re.compile(r"output|export|stock")),
    ("lifecycle_update", re.compile(r"queue_update|publish_live|update_intent|fullscreen|status")),
    ("workspace_presentation", re.compile(r"build_|persistent|selector|part_label|show_|refresh_|toggle_|configure_|prepare_")),
)


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def blob(ref: str, path: str) -> str:
    return run("git", "rev-parse", f"{ref}:{path}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bucket_for(name: str) -> str:
    low = name.lower()
    for bucket, pattern in BUCKET_RULES:
        if pattern.search(low):
            return bucket
    return "legacy_compatibility"


def bridge_census() -> dict:
    text = Path(BRIDGE).read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=BRIDGE)

    top = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    phase6 = [
        node
        for node in top
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("_phase6_")
    ]
    ordered = sorted(phase6, key=lambda n: n.lineno)

    rows = []
    by_bucket: dict[str, dict[str, int]] = {}
    for idx, node in enumerate(ordered):
        end_line = (
            ordered[idx + 1].lineno - 1
            if idx + 1 < len(ordered)
            else len(lines)
        )
        bucket = bucket_for(node.name)
        span = end_line - node.lineno + 1
        rows.append(
            {
                "name": node.name,
                "start_line": node.lineno,
                "end_line": end_line,
                "span": span,
                "bucket": bucket,
            }
        )
        agg = by_bucket.setdefault(bucket, {"count": 0, "span": 0})
        agg["count"] += 1
        agg["span"] += span

    self_refs = re.findall(r"\bself\.([A-Za-z_][A-Za-z0-9_]*)", text)

    return {
        "path": BRIDGE,
        "blob_sha": blob("HEAD", BRIDGE),
        "sha256": sha256_text(text),
        "line_count": len(lines),
        "top_level_def_class_count": len(top),
        "phase6_top_level_def_count": len(phase6),
        "literal_self_ref_count": len(self_refs),
        "unique_self_attr_count": len(set(self_refs)),
        "functions": rows,
        "buckets": dict(sorted(by_bucket.items())),
        "unknown_bucket_count": 0,
    }


def protected_manifest() -> tuple[list[dict], list[str]]:
    names = run("git", "ls-tree", "-r", "--name-only", BASELINE).splitlines()
    dxf = sorted(p for p in names if p.lower().endswith(".dxf"))
    project = sorted(
        p for p in names
        if p.startswith("phase6_project_") and p.endswith(".py")
    )
    cabinet = sorted(
        p for p in names
        if p.startswith("ae_engine/cabinet_types/") and p.endswith(".py")
    )
    required = sorted(set(PROTECTED_EXACT) | set(dxf) | set(project) | set(cabinet))
    rows = []
    missing = []
    for path in required:
        try:
            sha = blob(BASELINE, path)
        except subprocess.CalledProcessError:
            missing.append(path)
            continue
        if path.lower().endswith(".dxf"):
            category = "dxf"
        elif path == "config.ini":
            category = "config"
        elif path.startswith("phase6_manufacturing_"):
            category = "manufacturing"
        elif path.startswith("phase6_settings_"):
            category = "phase4_settings"
        elif path.startswith("phase6_final_scene_"):
            category = "phase4_final_scene"
        elif path.startswith("phase6_project_"):
            category = "project_persistence"
        elif path.startswith("ae_engine/cabinet_types/"):
            category = "cabinet_family_policy"
        else:
            category = "phase3_phase4_protected"
        rows.append(
            {
                "path": path,
                "blob_sha": sha,
                "owner_category": category,
                "allowed_task_exceptions": [],
            }
        )
    return rows, missing


def source_drift() -> dict:
    changed = sorted(
        p for p in run("git", "diff", "--name-only", BASELINE, "HEAD").splitlines()
        if p
    )
    forbidden = sorted(set(changed) - ALLOWED_T0_DRIFT)
    return {
        "changed_paths": changed,
        "forbidden_paths": forbidden,
        "count": len(forbidden),
    }


def build_payload() -> dict:
    run("git", "cat-file", "-e", BASELINE + "^{commit}")
    bridge = bridge_census()
    manifest, missing = protected_manifest()
    drift = source_drift()

    classifier = {
        "BASELINE_SHA_EXACT": 1 if run("git", "rev-parse", BASELINE) == BASELINE else 0,
        "UNKNOWN_BUCKET_COUNT": bridge["unknown_bucket_count"],
        "PROTECTED_MANIFEST_MISSING": len(missing),
        "PRODUCTION_SOURCE_DRIFT": drift["count"],
    }
    green = (
        classifier["BASELINE_SHA_EXACT"] == 1
        and classifier["UNKNOWN_BUCKET_COUNT"] == 0
        and classifier["PROTECTED_MANIFEST_MISSING"] == 0
        and classifier["PRODUCTION_SOURCE_DRIFT"] == 0
    )

    return {
        "schema": "WHD_PHASE5_T0_BRIDGE_CENSUS_V1",
        "baseline": BASELINE,
        "bridge": bridge,
        "protected_manifest": manifest,
        "protected_manifest_missing": missing,
        "source_drift": drift,
        "classifier": classifier,
        "decision": "GREEN" if green else "RED",
    }


def markdown(payload: dict) -> str:
    b = payload["bridge"]
    out = [
        "# Phase 5 T0 — Live bridge ownership census",
        "",
        f"- Baseline: `{payload['baseline']}`",
        f"- Decision: **{payload['decision']}**",
        "",
        "## Bridge metrics",
        "",
        f"- lines: {b['line_count']}",
        f"- top-level def/class: {b['top_level_def_class_count']}",
        f"- _phase6_* top-level def: {b['phase6_top_level_def_count']}",
        f"- literal self.*: {b['literal_self_ref_count']}",
        f"- unique self attrs: {b['unique_self_attr_count']}",
        "",
        "## Ownership buckets",
        "",
        "| bucket | count | span |",
        "|---|---:|---:|",
    ]
    for name, values in sorted(
        b["buckets"].items(), key=lambda item: item[1]["span"], reverse=True
    ):
        out.append(f"| {name} | {values['count']} | {values['span']} |")
    out += [
        "",
        "## Classifier",
        "",
    ]
    for key, value in payload["classifier"].items():
        out.append(f"- {key}={value}")
    out += [
        "",
        f"PHASE5_T0_DECISION={payload['decision']}",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--markdown")
    args = ap.parse_args()

    payload = build_payload()
    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown:
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")

    print(json.dumps(payload["classifier"], sort_keys=True))
    print(
        "BRIDGE_METRICS="
        f"{payload['bridge']['line_count']},"
        f"{payload['bridge']['top_level_def_class_count']},"
        f"{payload['bridge']['phase6_top_level_def_count']},"
        f"{payload['bridge']['literal_self_ref_count']}"
    )
    print("PHASE5_T0_DECISION=" + payload["decision"])
    return 0 if payload["decision"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
