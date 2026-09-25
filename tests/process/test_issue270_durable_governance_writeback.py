from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPATCH_SKILL = ROOT / ".agents/skills/engineering/派工/SKILL.md"
AI_SPEC = ROOT / "個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md"
FINAL_SEAL = ROOT / "docs/governance/issue270-t7-final-seal.json"

MASTER_ID = "262"
T7_ISSUE = 270
FROZEN_BASE = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
T6_ACCEPTED = "95243d18a06a96b5907991681873f8c3d0ebdf84"
TARGET_X = "cleanup/2d-3d-sync"
CURRENT_X = "269a2972f0f88ffc7085ee3f1483a57145d8b2e8"
AI_SPEC_REPO_PATH = "個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md"

REQUIRED_MARKERS = [
    "X_SECOND_MAIN_INDEPENDENT_CHAIN_CONTRACT",
    "FROZEN_X_BASE_SHA",
    "CURRENT_X_HEAD",
    "RUN_NOT_CREATED",
    "Task Acceptance",
    "Integration Acceptance",
    "READY_FOR_X_INTEGRATION",
    "DO_NOT_MERGE_X",
]


def _read(path: Path) -> str:
    assert path.is_file(), f"required durable governance file missing: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_dispatch_skill_contains_x_independent_chain_contract() -> None:
    text = _read(DISPATCH_SKILL)
    assert "X_SECOND_MAIN_INDEPENDENT_CHAIN_CONTRACT" in text
    assert AI_SPEC_REPO_PATH in text
    for marker in REQUIRED_MARKERS[1:]:
        assert marker in text, f"派工 skill missing durable marker: {marker}"


def test_dispatch_skill_keeps_complete_chain_and_explicit_authorization_gates() -> None:
    text = _read(DISPATCH_SKILL)
    assert "整鏈完成前禁止合回 X" in text
    assert "child parent" in text or "previous accepted HEAD" in text
    assert "non-force" in text
    assert "explicit authorization" in text
    assert "兄弟鏈" in text


def test_ai_library_canonical_spec_exists_and_matches_master_identity() -> None:
    text = _read(AI_SPEC)
    assert "# X 第二主分支與獨立工單鏈治理規格" in text
    assert "GitHub #262" in text
    assert TARGET_X in text
    assert "T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7" in text


def test_ai_library_spec_has_required_fail_closed_rules() -> None:
    text = _read(AI_SPEC)
    for marker in [
        "FROZEN_X_BASE_SHA",
        "CURRENT_X_HEAD",
        "RUN_NOT_CREATED",
        "Task Acceptance",
        "Integration Acceptance",
        "READY_FOR_X_INTEGRATION",
        "DO_NOT_MERGE_X",
        "兄弟鏈完全隔離",
    ]:
        assert marker in text, f"AI Library spec missing durable marker: {marker}"


def test_final_seal_is_fail_closed_ready_but_not_merged() -> None:
    payload = json.loads(_read(FINAL_SEAL))
    assert payload == {
        "schema_version": 1,
        "master_id": MASTER_ID,
        "task_id": "T7",
        "issue_number": T7_ISSUE,
        "target_x": TARGET_X,
        "frozen_x_base_sha": FROZEN_BASE,
        "parent_accepted_head": T6_ACCEPTED,
        "current_x_sha": CURRENT_X,
        "task_acceptance": "ACCEPTED",
        "integration_readiness": "READY_FOR_X_INTEGRATION",
        "integration_acceptance": "NOT_PERFORMED",
        "do_not_merge_x": True,
        "x_mutated": False,
    }


def test_final_state_never_equates_readiness_with_merge_permission() -> None:
    text = _read(AI_SPEC) + "\n" + _read(DISPATCH_SKILL)
    assert "READY_FOR_X_INTEGRATION 不等於自動 merge" in text
    assert "explicit authorization" in text


def test_t7_parent_is_exact_t6_accepted_head() -> None:
    payload = json.loads(_read(FINAL_SEAL))
    assert payload["parent_accepted_head"] == T6_ACCEPTED
    assert payload["frozen_x_base_sha"] == FROZEN_BASE
    assert payload["target_x"] == TARGET_X
