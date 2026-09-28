"""Deterministic WHD change classification and QA test-profile selection."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import PurePosixPath
from typing import Iterable

SCHEMA = "WHD_CHANGE_TEST_PROFILE_V1"

PRIMARY_TYPES = ("BUGFIX", "FEATURE", "UPDATE", "REFACTOR", "GOVERNANCE", "DOCS_METADATA")
DOMAIN_OVERLAYS = ("UI", "GEOMETRY")

BASE_STAGES = {
    "BUGFIX": ("REPRODUCER_RED", "TARGETED_REGRESSION", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "FEATURE": ("FEATURE_ACCEPTANCE", "UNIT_OR_COMPONENT", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "UPDATE": ("COMPATIBILITY", "MIGRATION_CONFIG", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "REFACTOR": ("BEHAVIORAL_EQUIVALENCE", "UNIT", "INTEGRATION"),
    "GOVERNANCE": ("CONTRACT", "CONTROL_PLANE_REGRESSION", "GOVERNANCE_MIRROR_HARD_GATE"),
    "DOCS_METADATA": ("SCHEMA_LINT_LINK",),
}

OVERLAY_STAGES = {
    "UI": ("UI_CONTRACT_STATE", "TK_XVFB", "VISUAL_ACCEPTANCE"),
    "GEOMETRY": ("GEOMETRY_INVARIANTS", "DXF_ACCEPTANCE", "RENDERER_SYNC", "SAVE_RELOAD"),
}

_KEYWORDS = {
    "BUGFIX": ("bug", "fix", "regression", "除蟲", "錯誤", "修正", "故障"),
    "FEATURE": ("feature", "add", "新增", "新功能"),
    "UPDATE": ("update", "upgrade", "migration", "compat", "更新", "升級", "相容"),
    "REFACTOR": ("refactor", "move-only", "重構", "搬移"),
    "GOVERNANCE": ("governance", "control plane", "flow v2", "scheduler", "治理", "派工", "排程"),
}

_UI_PREFIXES = ("gui_modules/",)
_UI_EXACT = {
    "gui.py", "fold_designer_bridge.py", "phase6_corner_data_view_adapter.py",
    "phase6_final_scene_view.py", "phase6_final_scene_renderer.py",
}
_UI_TOKENS = ("_ui", "ui_", "widget", "layout", "renderer", "view_adapter")

_GEOMETRY_PREFIXES = ("ae_engine/", "基準檔/截角資料庫/")
_GEOMETRY_TOKENS = ("geometry", "dxf", "relief", "corner", "final_scene", "manufacturing", "multipart")

_GOVERNANCE_PREFIXES = (".agents/", ".github/workflows/", "coord/", "docs/governance/", "tests/process/")
_GOVERNANCE_TOOL_PREFIXES = (
    "tools/control_", "tools/execution_", "tools/flow_v2_", "tools/scheduler_",
    "tools/work_root_", "tools/governance_", "tools/continuity_",
)
_DOC_PREFIXES = ("docs/", "個人AI檔案庫/", "修改日誌/")
_DOC_SUFFIXES = (".md", ".txt", ".rst")


def _normalize_files(changed_files: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in changed_files:
        text = str(raw).strip().replace("\\", "/")
        if not text:
            continue
        path = PurePosixPath(text)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"invalid changed file: {raw!r}")
        normalized.append(path.as_posix())
    if not normalized:
        raise ValueError("changed_files must not be empty")
    return tuple(dict.fromkeys(normalized))


def _contains_keyword(task: str, keyword: str) -> bool:
    lowered = task.casefold()
    key = keyword.casefold()
    if re.fullmatch(r"[a-z0-9_-]+", key):
        return re.search(rf"(?<![a-z0-9_-]){re.escape(key)}(?![a-z0-9_-])", lowered) is not None
    return key in lowered


def _is_governance_path(path: str) -> bool:
    return path.startswith(_GOVERNANCE_PREFIXES) or path.startswith(_GOVERNANCE_TOOL_PREFIXES)


def _is_docs_metadata_path(path: str) -> bool:
    if path.startswith(_DOC_PREFIXES) and not path.startswith("docs/governance/"):
        return True
    if path in {"README.md", "LICENSE", ".gitignore", ".gitattributes"}:
        return True
    return path.endswith(_DOC_SUFFIXES) and not _is_governance_path(path)


def _is_ui_path(path: str) -> bool:
    lowered = path.casefold()
    return path in _UI_EXACT or path.startswith(_UI_PREFIXES) or any(token in lowered for token in _UI_TOKENS)


def _is_geometry_path(path: str) -> bool:
    lowered = path.casefold()
    return path.startswith(_GEOMETRY_PREFIXES) or any(token in lowered for token in _GEOMETRY_TOKENS)


def detect_domains(changed_files: Iterable[str]) -> tuple[str, ...]:
    files = _normalize_files(changed_files)
    domains: list[str] = []
    if any(_is_ui_path(path) for path in files):
        domains.append("UI")
    if any(_is_geometry_path(path) for path in files):
        domains.append("GEOMETRY")
    return tuple(domains)


def infer_change_type(task: str, changed_files: Iterable[str], *, explicit_type: str | None = None) -> str:
    files = _normalize_files(changed_files)
    if explicit_type:
        value = str(explicit_type).strip().upper()
        if value not in PRIMARY_TYPES:
            raise ValueError(f"unsupported explicit change type: {explicit_type}")
        return value

    if all(_is_docs_metadata_path(path) for path in files):
        return "DOCS_METADATA"

    task = str(task).strip()
    hits = [
        kind for kind, keywords in _KEYWORDS.items()
        if any(_contains_keyword(task, keyword) for keyword in keywords)
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ValueError("ambiguous change type; provide explicit change type: " + ", ".join(hits))
    if all(_is_governance_path(path) for path in files):
        return "GOVERNANCE"
    raise ValueError("unable to infer change type; provide explicit change type")


def _final_full_gate(change_type: str, files: tuple[str, ...]) -> tuple[str, bool]:
    if change_type == "DOCS_METADATA" and all(_is_docs_metadata_path(path) for path in files):
        return "NONE", False
    if files and all(_is_governance_path(path) for path in files):
        return "GOVERNANCE_FULL_SUITE", True
    return "PRODUCT_FULL_REGRESSION", True


def build_test_profile(*, task: str, changed_files: Iterable[str], explicit_type: str | None = None) -> dict[str, object]:
    files = _normalize_files(changed_files)
    change_type = infer_change_type(task, files, explicit_type=explicit_type)
    domains = detect_domains(files)
    stages: list[str] = list(BASE_STAGES[change_type])
    for domain in domains:
        for stage in OVERLAY_STAGES[domain]:
            if stage not in stages:
                stages.append(stage)
    full_gate_kind, full_gate_required = _final_full_gate(change_type, files)
    if full_gate_required and full_gate_kind not in stages:
        stages.append(full_gate_kind)
    return {
        "schema": SCHEMA,
        "change_type": change_type,
        "domains": list(domains),
        "changed_files": list(files),
        "required_stages": stages,
        "full_gate_kind": full_gate_kind,
        "full_gate_required": full_gate_required,
        "profile_id": "+".join([change_type, *domains, full_gate_kind]),
        "workspace_root": "/Google Drive/WHD",
        "workspace_work_prefix": "/Google Drive/WHD/work",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--change-type", choices=PRIMARY_TYPES)
    args = parser.parse_args(argv)
    profile = build_test_profile(task=args.task, changed_files=args.changed_file, explicit_type=args.change_type)
    print(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
