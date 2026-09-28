from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "governance" / "issue843_control_plane_behavior_matrix.json"

EXPECTED_BASELINE = {
    "authoritative_branch": "cleanup/2d-3d-sync",
    "head_sha": "500e6f806de40a74ee8cd5bb4a6372245c5df53c",
    "default_branch": "main",
    "default_head_sha": "cb80310e2643d1ab9624e90085d4abda6e4d125e",
}
REQUIRED_SKILL_OWNERS = {
    ".agents/skills/engineering/派工/SKILL.md",
    ".agents/skills/engineering/執行開發任務/SKILL.md",
    ".agents/skills/engineering/executable-continuity-controller/SKILL.md",
    ".agents/skills/engineering/issue-closure-gate/SKILL.md",
    ".agents/skills/engineering/排程模擬/SKILL.md",
    ".agents/skills/engineering/工作槽/SKILL.md",
    ".agents/skills/engineering/remote-execution-guard/SKILL.md",
    ".agents/skills/engineering/monitoring-remote-qa/SKILL.md",
}
REQUIRED_DOMAINS = {
    "normal_path",
    "resume",
    "remote_qa_identity",
    "finalization",
    "takeover_recovery",
    "scheduler_wakeup",
    "work_slot_projection",
}
ALLOWED_CLASSIFICATIONS = {
    "invariant",
    "implementation_detail",
    "compatibility_behavior",
    "duplicated_bridge_prose",
}


def _load_matrix() -> dict:
    assert MATRIX.is_file(), (
        "ISSUE843_RED: machine-readable control-plane behavior matrix is missing"
    )
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def test_issue843_matrix_is_bound_to_frozen_baseline_and_scope() -> None:
    payload = _load_matrix()
    assert payload["schema"] == "WHD_CONTROL_PLANE_BEHAVIOR_MATRIX_V1"
    assert payload["issue"] == 843
    assert payload["parent_issue"] == 842
    assert payload["baseline"] == EXPECTED_BASELINE
    assert payload["production_behavior_change"] is False
    assert set(payload["prohibited_changes"]) == {
        "new_execution_record",
        "remote_guard_semantic_change",
        "scheduler_discovery_redesign",
    }


def test_issue843_matrix_covers_all_required_skill_owners_and_domains() -> None:
    payload = _load_matrix()
    assert set(payload["skill_owners"]) == REQUIRED_SKILL_OWNERS
    assert set(payload["required_domains"]) == REQUIRED_DOMAINS

    domains = {
        rule["domain"]
        for rule in payload["rules"]
        if rule["classification"] == "invariant"
    }
    assert REQUIRED_DOMAINS <= domains


def test_issue843_every_retained_safety_invariant_has_executable_or_external_authority() -> None:
    payload = _load_matrix()
    rules = payload["rules"]
    ids = [rule["id"] for rule in rules]
    assert len(ids) == len(set(ids)), "matrix rule ids must be unique"

    for rule in rules:
        assert rule["classification"] in ALLOWED_CLASSIFICATIONS
        if rule["classification"] != "invariant":
            continue
        regressions = rule.get("regressions", [])
        external = rule.get("external_invariant")
        assert regressions or external, (
            f"retained invariant {rule['id']} has neither executable regression "
            "nor explicit justified external invariant"
        )


def test_issue843_regression_node_references_resolve_to_real_tests() -> None:
    payload = _load_matrix()
    for rule in payload["rules"]:
        for regression in rule.get("regressions", []):
            path = ROOT / regression["file"]
            assert path.is_file(), f"missing regression file for {rule['id']}: {path}"
            functions = _test_functions(path)
            for node in regression["nodes"]:
                assert node in functions, (
                    f"unknown regression node for {rule['id']}: "
                    f"{regression['file']}::{node}"
                )


def test_issue843_machine_owner_paths_resolve_and_do_not_use_docs_as_enforcement() -> None:
    payload = _load_matrix()
    for rule in payload["rules"]:
        for owner in rule.get("machine_owners", []):
            path = ROOT / owner
            assert path.is_file(), f"missing machine owner for {rule['id']}: {owner}"
            assert not owner.startswith("docs/"), (
                f"documentation cannot be machine enforcement for {rule['id']}: {owner}"
            )


def test_issue843_duplicate_bridge_inventory_is_identify_only() -> None:
    payload = _load_matrix()
    duplicates = payload["duplicated_bridges"]
    assert duplicates
    for item in duplicates:
        assert item["classification"] == "duplicated_bridge_prose"
        assert item["action"] == "identify_only_no_deletion"
        authority = ROOT / item["authoritative_owner"]
        assert authority.is_file()
        copies = item["duplicates"]
        assert copies
        for copy in copies:
            assert (ROOT / copy).is_file()
