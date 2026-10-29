"""Deterministic WHD change classification and QA test-profile selection."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from typing import Iterable

SCHEMA = "WHD_CHANGE_TEST_PROFILE_V1"

PRIMARY_TYPES = ("BUGFIX", "FEATURE", "UPDATE", "REFACTOR", "GOVERNANCE", "DOCS_METADATA")
DOMAIN_OVERLAYS = ("UI", "GEOMETRY")

BASE_STAGES = {
    "BUGFIX": ("REPRODUCER_RED", "TARGETED_REGRESSION", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "FEATURE": ("FEATURE_ACCEPTANCE", "UNIT_OR_COMPONENT", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "UPDATE": ("COMPATIBILITY", "MIGRATION_CONFIG", "AFFECTED_SUBSYSTEM", "INTEGRATION"),
    "REFACTOR": ("BEHAVIORAL_EQUIVALENCE", "UNIT", "INTEGRATION"),
    "GOVERNANCE": ("CONTRACT", "AUTHORITY_CONSISTENCY"),
    "DOCS_METADATA": ("SCHEMA_LINT_LINK",),
}

FULL_GATE_COMMANDS = {
    "GOVERNANCE_FULL_SUITE": (),
    "PRODUCT_FULL_REGRESSION": ("python tools/product_ci_regression.py",),
    "NONE": (),
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
    "GOVERNANCE": ("governance", "control plane", "scheduler", "治理", "派工", "排程"),
}

_UI_PREFIXES = ("gui_modules/",)
_UI_EXACT = {
    "gui.py", "fold_designer_bridge.py", "phase6_corner_data_view_adapter.py",
    "phase6_final_scene_view.py", "phase6_final_scene_renderer.py",
}
_UI_TOKENS = ("_ui", "ui_", "widget", "layout", "renderer", "view_adapter")

_GEOMETRY_PREFIXES = ("ae_engine/", "基準檔/截角資料庫/")
_GEOMETRY_TOKENS = ("geometry", "dxf", "relief", "corner", "final_scene", "manufacturing", "multipart")

_GOVERNANCE_PREFIXES = (".agents/", ".github/workflows/", "coord/", "docs/governance/", "tests/process/", "tests/governance/", "tests/knowledge/")
_GOVERNANCE_TOOL_PREFIXES = (
    "tools/work_root_", "tools/governance_", "tools/continuity_", "tools/root_local_", "tools/change_test_",
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


_GOVERNANCE_TOOL_EXACT = {
    "tools/change_lane_gate.py",
    "tools/localx_publish_gate.py",
    "tools/phase6_skill_preflight.py",
    "tools/knowledge_governance.py",
    "tools/interactive_command_no_stop_gate.py",
}


def _is_governance_path(path: str) -> bool:
    return (
        path in _GOVERNANCE_TOOL_EXACT
        or path.startswith(_GOVERNANCE_PREFIXES)
        or path.startswith(_GOVERNANCE_TOOL_PREFIXES)
    )



def _is_docs_metadata_path(path: str) -> bool:
    if path.startswith(_DOC_PREFIXES) and not path.startswith("docs/governance/"):
        return True
    if path in {"README.md", "LICENSE", ".gitignore", ".gitattributes"}:
        return True
    return path.endswith(_DOC_SUFFIXES) and not _is_governance_path(path)


def _is_governance_support_path(path: str) -> bool:
    if _is_governance_path(path):
        return True
    if path == "AGENTS.md":
        return True
    if path.startswith("個人AI檔案庫/") and path.endswith(".md"):
        return True
    if path.startswith("tests/") and any(token in path.casefold() for token in ("skill", "preflight", "governance")):
        return True
    return False


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



def build_fast_feedback(
    changed_files: Iterable[str], *, feedback_tests: Iterable[str] = (),
) -> dict[str, object]:
    """Produce a safe *development-only* pytest command; never a merge receipt.

    Changed test files are trustworthy selector candidates. A production-only
    diff is not enough to infer which regression covers the user symptom, so
    it requires an explicit test node/file instead of guessing.
    """
    files = _normalize_files(changed_files)
    explicit = list(feedback_tests)
    candidates = explicit if explicit else [
        path for path in files
        if path.startswith("tests/")
        and (PurePosixPath(path).name.startswith("test_")
             or PurePosixPath(path).name.endswith("_test.py"))
        and path.endswith(".py")
    ]
    selectors: list[str] = []
    for raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("feedback test selectors must be nonempty strings")
        selector = raw.strip()
        if any(ord(c) < 32 or ord(c) == 127 for c in selector):
            raise ValueError("feedback test selector contains control characters")
        test_file, separator, node = selector.partition("::")
        test_file = test_file.replace("\\", "/")
        path = PurePosixPath(test_file)
        if (path.is_absolute() or ".." in path.parts
                or path.as_posix() != test_file
                or not test_file.startswith("tests/")
                or not test_file.endswith(".py")
                or not (path.name.startswith("test_")
                        or path.name.endswith("_test.py"))):
            raise ValueError(f"invalid feedback test file: {test_file!r}")
        if separator and (not node or any(not part for part in node.split("::"))):
            raise ValueError("feedback test node ID is incomplete")
        candidate = test_file + ("::" + node if separator else "")
        if candidate not in selectors:
            selectors.append(candidate)
    command = None
    if selectors:
        command = "python -m pytest -q --tb=short " + " ".join(
            shlex.quote(selector) for selector in selectors
        )
    return {
        "status": "READY" if command else "NEEDS_EXPLICIT_TEST",
        "test_selectors": selectors,
        "command": command,
        "authority": "DEVELOPMENT_FEEDBACK_ONLY",
        "may_replace_full_gate": False,
    }


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
    if change_type == "GOVERNANCE" and files and all(_is_governance_support_path(path) for path in files):
        return "GOVERNANCE_FULL_SUITE", True
    if files and all(_is_governance_path(path) for path in files):
        return "GOVERNANCE_FULL_SUITE", True
    return "PRODUCT_FULL_REGRESSION", True


def build_test_profile(*, task: str, changed_files: Iterable[str], explicit_type: str | None = None,
                       feedback_tests: Iterable[str] = ()) -> dict[str, object]:
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
        "fast_feedback": build_fast_feedback(files, feedback_tests=feedback_tests),
        "full_gate_kind": full_gate_kind,
        "full_gate_required": full_gate_required,
        "exact_commands": list(FULL_GATE_COMMANDS[full_gate_kind]),
        "command_owner": "tools/control_plane_regression.py" if full_gate_kind == "GOVERNANCE_FULL_SUITE" else "tools/product_ci_regression.py" if full_gate_kind == "PRODUCT_FULL_REGRESSION" else None,
        "profile_id": "+".join([change_type, *domains, full_gate_kind]),
        "workspace_root": "EXECUTOR_LOCAL_REPO_WORKSPACE",
        "workspace_unpushed_root": None,
    }


def evaluate_merge_test_reuse(
    *, repo_root: str | Path, tested_commit: str, integrated_commit: str,
    ci_head_sha: str, ci_conclusion: str, required_tests_complete: bool,
) -> dict[str, object]:
    """Read-only gate: reuse exact successful test evidence only for identical Git trees.

    Test/CI attestation must be validated from a trusted source by the caller.
    Git commands independently inspect real commit trees; a different SHA alone
    is not a reason to retest. The gate never launches any tests or mutations.
    """
    def result(decision: str, reason: str, **details: object) -> dict[str, object]:
        return {"schema": "WHD_LOCALX_MERGE_TEST_REUSE_V1",
                "decision": decision, "reason": reason, **details}

    sha = re.compile(r"[0-9a-f]{40}\Z")
    if (not all(isinstance(v, str) and sha.fullmatch(v)
                for v in (tested_commit, integrated_commit, ci_head_sha))
            or ci_head_sha != tested_commit
            or ci_conclusion != "SUCCESS"
            or required_tests_complete is not True):
        return result("EVIDENCE_INCOMPLETE", "MISSING_EXACT_GREEN_TEST_RECEIPT")

    def git(*args: str, binary: bool = False) -> str | bytes:
        done = subprocess.run(["git", "-C", str(repo_root), *args],
                              capture_output=True, check=False)
        if done.returncode:
            raise ValueError("GIT_TREE_READ_FAILED")
        return done.stdout if binary else done.stdout.decode("ascii", "strict").strip()

    try:
        for ref in (tested_commit, integrated_commit):
            if git("cat-file", "-t", ref) != "commit":
                raise ValueError("NOT_A_COMMIT")
        tested_tree = git("rev-parse", tested_commit + "^{tree}")
        integrated_tree = git("rev-parse", integrated_commit + "^{tree}")
        if tested_tree == integrated_tree:
            return result("REUSE_VERIFIED", "IDENTICAL_TESTED_GIT_TREE",
                          tested_tree=tested_tree, integrated_tree=integrated_tree,
                          extra_test_runs=0)
        changed_raw = git("diff", "--name-only", "-z", "--no-ext-diff",
                          tested_commit, integrated_commit, binary=True)
        paths = sorted(p.decode("utf-8", "strict")
                       for p in changed_raw.split(b"\x00") if p)
        if not paths:
            raise ValueError("TREE_DIFF_UNEXPLAINED")
        return result("IMPACT_TEST_REQUIRED", "UNTESTED_INTEGRATION_TREE_DIFFERENCE",
                      tested_tree=tested_tree, integrated_tree=integrated_tree,
                      changed_paths=paths, full_regression_default=False)
    except (ValueError, UnicodeError, OSError):
        return result("EVIDENCE_INCOMPLETE", "CANNOT_VERIFY_GIT_TREE_OR_DIFF")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--change-type", choices=PRIMARY_TYPES)
    parser.add_argument("--feedback-test", action="append", default=[],
                        help="pytest test path or node ID for fast development feedback")
    parser.add_argument("--merge-test-reuse", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--tested-commit")
    parser.add_argument("--integrated-commit")
    parser.add_argument("--ci-head-sha")
    parser.add_argument("--ci-conclusion")
    parser.add_argument("--required-tests-complete", action="store_true")
    args = parser.parse_args(argv)
    if args.merge_test_reuse:
        result = evaluate_merge_test_reuse(
            repo_root=args.repo_root, tested_commit=args.tested_commit,
            integrated_commit=args.integrated_commit, ci_head_sha=args.ci_head_sha,
            ci_conclusion=args.ci_conclusion,
            required_tests_complete=args.required_tests_complete)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["decision"] == "REUSE_VERIFIED" else 2
    if not args.task:
        parser.error("--task is required without --merge-test-reuse")
    profile = build_test_profile(task=args.task, changed_files=args.changed_file,
                                 explicit_type=args.change_type, feedback_tests=args.feedback_test)
    print(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
