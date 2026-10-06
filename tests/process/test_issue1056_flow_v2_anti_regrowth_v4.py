from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
ROOT_SKILL = ".agents/skills/engineering/root-local-first/SKILL.md"
SPEC_GOV = "docs/governance/WHD_規格書Skill前置與Grounding規則.md"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _json(rel: str) -> dict[str, object]:
    return json.loads(_read(rel))


def _frontmatter_value(text: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else None


def test_no_current_markdown_document_points_to_a_second_canonical_owner() -> None:
    offenders = []
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if _frontmatter_value(text, "whd_doc_role") != "CURRENT":
            continue
        canonical = _frontmatter_value(text, "whd_canonical")
        if canonical not in (None, "", "null"):
            offenders.append((path.relative_to(ROOT).as_posix(), canonical))
    assert offenders == []


def test_spec_governance_is_mirror_and_cannot_restore_branch_first() -> None:
    text = _read(SPEC_GOV)
    assert "whd_doc_role: MIRROR" in text
    assert "whd_canonical: .agents/skills/engineering/寫成規格書/SKILL.md" in text
    assert "ROOT_LOCAL_FIRST_SPEC_GOVERNANCE_BRIDGE_V1" in text
    assert "GIT_WRITE_UNLOCKED" in text
    for stale in (
        "AGENTS.md` 已要求 Phase6 Knowledge Preflight、required Skills、required references 與 branch-first",
        "branch-first authority 仍由 `AGENTS.md` 擁有",
        "本輪 branch-first：",
    ):
        assert stale not in text


def test_deterministic_repo_migration_cannot_bypass_flow_or_root_local_first() -> None:
    skill = _read(".agents/skills/engineering/deterministic-repo-migration/SKILL.md")
    registry = _json(".agents/skills/skill_registry.json")
    assert "WHD_REPOSITORY_MUTATION_GATE_V1" in skill
    assert "WHD_EXECUTION_RECORD_V2" in skill
    assert "WHD_TEST_EXECUTION_RECEIPT_V1" in skill
    assert "WORKSPACE_DEFAULT" in skill
    assert "SHARED_ZERO_FALLBACK" not in skill
    assert "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION" not in skill
    by_id = {route["id"]: route for route in registry["routes"]}
    expected = ["flow-v2-execution", "root-local-first", "deterministic-repo-migration"]
    assert by_id["deterministic-repo-migration"]["required_skills"] == expected
    assert by_id["explicit-skill-deterministic-repo-migration"]["required_skills"] == expected


def test_work_root_next_gate_explicitly_covers_remote_repository_content() -> None:
    payload = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert payload["next_gate"]["schema"] == "WHD_WORKSPACE_ENTRY_HARD_GATE_V1"
    root = _json(".agents/contracts/WHD_WORKSPACE_ENTRY_HARD_GATE_V1.json")
    for mode in ("SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"):
        assert root["execution_modes"][mode] == "CONTROL_PLANE_OR_POST_PUSH_ONLY_REPOSITORY_CONTENT_REQUIRES_WORKSPACE_CAPABLE_RUNTIME_HANDOFF"
    assert root["remote_content_implementation"]["github_side_hotfix_forbidden"] is True


def test_authority_map_fences_historical_governance_parity() -> None:
    text = _read("個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    section = text.split("ISSUE693_COMBINED_ACCEPTANCE_WRITEBACK_V1", 1)[1].split("WHD_PHASE7_OWNERSHIP_WRITEBACK_V1", 1)[0]
    assert "FLOW_V2_LEGACY_CHUNK_FENCE_V1" in section
    assert "superseded" in section
    assert "retained invariant: Production/trusted governance parity is machine-readable" not in section


def test_global_pitfall_limits_update_ref_to_non_authoritative_work_branch() -> None:
    text = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    section = text.split("單一 Code Mode orchestration 超過工具呼叫上限", 1)[1].split("Receiving Door", 1)[0]
    assert "non-authoritative dedicated work branch" in section
    assert "production target 不得由 chat/runtime `update_ref` 前推" in section
    assert "Flow v2 trusted `MERGE / SYNC_TARGET`" in section


def test_legacy_gui_plans_fence_old_finalization_commands() -> None:
    for rel in (
        "docs/superpowers/plans/2026-09-16-issue292-t4-part-panels.md",
        "docs/superpowers/plans/2026-09-17-issue293-t5-editors.md",
        "docs/superpowers/plans/2026-09-18-issue294-t6-rendering.md",
        "docs/superpowers/plans/2026-09-18-issue295-t7-controller.md",
    ):
        text = _read(rel)
        assert "whd_doc_role: REFERENCE" in text
        assert "FLOW_V2_LEGACY_CHUNK_FENCE_V1" in text
        assert "tools/execution_invocation_exit.py" in text
        assert "MERGE → FINALIZE → DONE" in text


def test_default_branch_fail_closed_contract_declares_minimal_stub_surfaces() -> None:
    payload = _json(".agents/contracts/WHD_DEFAULT_BRANCH_FAIL_CLOSED_V1.json")
    assert payload["production_branch"] == "cleanup/2d-3d-sync"
    assert payload["default_branch"] == "main"
    assert payload["policy"] == "MAIN_MINIMAL_TOMBSTONE_TREE"
    assert payload["legacy_tree_preserved_under_archive_branch"] is True
    assert set(payload["required_main_stub_paths"]) >= {
        "README.md",
        "AGENTS.md",
        ".agents/skills/engineering/flow-v2-execution/SKILL.md",
        ".agents/skills/skill_registry.json",
        "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md",
        "tools/phase6_skill_preflight.py",
    }


def test_control_plane_regression_owns_v4_guard() -> None:
    rel = "tests/process/test_issue1056_flow_v2_anti_regrowth_v4.py"
    assert rel in _read("tools/control_plane_regression.py")
    assert rel in _read(".github/workflows/whd-control-plane-regression.yml")
