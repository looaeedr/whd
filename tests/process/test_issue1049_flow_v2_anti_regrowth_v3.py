from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
REMOTE_POLICY = "CONTROL_PLANE_OR_POST_PUSH_ONLY_REPOSITORY_CONTENT_REQUIRES_WORKSPACE_CAPABLE_RUNTIME_HANDOFF"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _json(rel: str) -> dict[str, object]:
    return json.loads(_read(rel))


def _canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _canonical_payload_from_mirror(rel: str) -> dict[str, object]:
    payload = _json(rel)
    for key in ("role", "mirror_policy", "canonical_source"):
        payload.pop(key, None)
    return payload


def test_root_shared_unpushed_contract_is_current_canonical_projection() -> None:
    from tools.root_local_first_gate import validate_contract

    contract = _json(".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json")
    validate_contract(contract)
    assert contract["schema"] == "WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1"
    assert contract["canonical_root"]["provider"] == "executor_local_workspace"
    assert contract["canonical_root"]["path_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert contract["canonical_root"]["production_branch"] == "cleanup/2d-3d-sync"
    assert contract["canonical_root"]["drive_role"] == "MIRROR_BACKUP_ONLY"
    assert contract["canonical_root"]["drive_mirror_root"] == "/Google Drive/WHD/WHD_MIRROR/CURRENT"
    assert "canonical_drive_overlay" not in contract["canonical_root"]
    assert contract["shared_unpushed_integration"]["mode"] == "SUPERSEDED_DATA_ONLY"
    for mode in ("SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"):
        assert contract["execution_modes"][mode] == REMOTE_POLICY
    assert not (ROOT / ".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json").exists()


def test_work_root_v2_points_to_shared_unpushed_entry_gate() -> None:
    contract = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json")
    assert contract["status"] == "CURRENT"
    assert contract["required_sequence"][-2] == "ROOT_SHARED_UNPUSHED_GATE_READ"
    assert contract["next_gate"]["schema"] == "WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1"
    assert contract["next_gate"]["repository_contract"] == ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json"
    assert not (ROOT / ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json").exists()


def test_every_registry_route_loading_flow_v2_mirror_loads_canonical_first() -> None:
    registry = _json(".agents/skills/skill_registry.json")
    mirror_names: set[str] = set()
    for path in (ROOT / ".agents/skills").glob("**/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        if "whd_doc_role: MIRROR" not in text or f"whd_canonical: {FLOW}" not in text:
            continue
        for line in text.splitlines():
            if line.startswith("name:"):
                mirror_names.add(line.split(":", 1)[1].strip())
                break
    offenders = []
    for route in registry["routes"]:
        required = route.get("required_skills", [])
        if mirror_names.intersection(required) and "flow-v2-execution" not in required:
            offenders.append((route["id"], required))
    assert offenders == []


def test_active_required_reference_cannot_restore_remote_qa_active_lock() -> None:
    text = _read("個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md")
    section = text.split("Remote QA 30 秒規則曾缺少互斥", 1)[1].split("## 2026-09-09 — 只鎖 collision metadata", 1)[0]
    assert "FLOW_V2_LEGACY_CHUNK_FENCE_V1" in section
    assert "WHD_EXECUTION_RECORD_V2.active_run + structured next_action" in section
    assert "REMOTE_QA_ACTIVE_LOCK` 是舊事故修法" in section
    assert "**永久防線**：取得 `run_id + head_sha` 後進 `REMOTE_QA_ACTIVE_LOCK`" not in section


def test_current_skills_forbid_connector_update_ref_as_whd_production_transport() -> None:
    fallback = _read(".agents/skills/misc/git-remote-sync-fallback/SKILL.md")
    root_local = _read(".agents/skills/engineering/root-local-first/SKILL.md")
    flow = _read(FLOW)
    assert "WHD production integration is not a Connector fallback surface" in fallback
    assert "chat/runtime `update_ref`" in fallback
    assert "production target 的 ref advancement 一律交回 Flow v2 trusted `MERGE` / `SYNC_TARGET`" in root_local
    assert "chat/runtime 不得以 local git、Remote Desktop 或 connector `update_ref` 取代" in flow


def test_authority_map_has_one_machine_row_per_physical_line() -> None:
    authority = _read("個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md")
    assert "\\n<!-- WHD_AUTHORITY" not in authority
    assert "contract=workstation-poweroff-safety role=CURRENT" in authority
    assert "contract=ha-poweroff-projection role=CURRENT" in authority


def _done_record():
    from tools.execution_record import execution_record_from_payload
    return execution_record_from_payload({
        "schema": "WHD_EXECUTION_RECORD_V2",
        "version": 2,
        "generation": 1,
        "issue": 1049,
        "execution_intent": "EXECUTE_TICKET",
        "owner_kind": "NONE",
        "owner_id": "NONE",
        "lane_id": None,
        "slot_id": "worker.slot.0",
        "source_branch": "cleanup/2d-3d-sync",
        "source_sha": "a" * 40,
        "work_branch": "governance/issue1049",
        "head_sha": "b" * 40,
        "target_branch": "cleanup/2d-3d-sync",
        "target_sha": "c" * 40,
        "state": "DONE",
        "semantic_state": "DONE",
        "next_action": None,
        "lease": None,
        "active_run": None,
        "transaction": None,
        "mutation_scope": {
            "target_branch": "cleanup/2d-3d-sync",
            "base_sha": "a" * 40,
            "write_paths": ["AGENTS.md"],
            "delete_paths": [],
            "reservation_state": "RELEASED",
        },
        "qa": {"last_accepted_run": 123, "accepted_head_sha": "b" * 40},
        "blocker": None,
        "closure": {"merged_sha": "c" * 40, "issue_closed": True, "released_at": "2026-09-30T03:00:00Z"},
        "chain": {"parent_issue": None, "next_issue": None, "next_action": None},
        "recovery_history": [],
        "updated_at": "2026-09-30T03:00:00Z",
    })


def _root_sync_receipt():
    from tools.post_integration_durability import build_root_sync_receipt
    return build_root_sync_receipt(
        accepted_sha="c" * 40, accepted_tree_sha="d" * 40,
        root_head_sha="c" * 40, root_tree_sha="d" * 40,
    )


def _lane_delivery_receipt():
    from tools.post_integration_durability import build_lane_delivery_receipt
    return build_lane_delivery_receipt(
        lane="docs", issue=1049, generation=2, merged_sha="c" * 40,
        manifest_digest="e" * 64, delivered_paths=["AGENTS.md"], lane_state_after="EMPTY",
    )


def test_repository_content_completion_blocks_after_done_until_v2_durability_complete() -> None:
    from tools.execution_invocation_exit import InvocationExitError, assert_repository_content_cycle_complete

    record = _done_record()
    assert assert_repository_content_cycle_complete(record) is True
    assert assert_repository_content_cycle_complete(
        record, root_sync_receipt=None, lane_delivery_receipt=_lane_delivery_receipt()
    ) is True
    assert assert_repository_content_cycle_complete(
        record, root_sync_receipt=_root_sync_receipt(), lane_delivery_receipt=_lane_delivery_receipt()
    ) is True


def test_post_integration_v2_rejects_legacy_snapshot_authority() -> None:
    contract = _json(".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json")
    assert set(contract["forbidden_current_authorities"]) == {
        "SOURCE_SNAPSHOT", "CURRENT_SOURCE_MANIFEST", "WORK_ACTIVE_ARCHIVE"
    }
    assert not (ROOT / ".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json").exists()


def test_control_plane_regression_owns_v3_guard() -> None:
    runner = _read("tools/control_plane_regression.py")
    workflow = _read(".github/workflows/whd-control-plane-regression.yml")
    rel = "tests/process/test_issue1049_flow_v2_anti_regrowth_v3.py"
    assert rel in runner
    assert rel in workflow


def test_legacy_source_snapshot_workflow_is_absent() -> None:
    assert not (ROOT / ".github/workflows/drive-source-snapshot-export.yml").exists()


def test_v2_durability_keeps_root_sync_optional_and_lane_finalization_required() -> None:
    contract = _json(".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V2.json")
    assert "CANONICAL_ROOT_SYNCED_TO_MERGED_HEAD" not in contract["required_order"]
    assert contract["root_sync_policy"]["terminal_gate"] is False
    assert contract["root_sync_policy"]["closure_authority"] is False
    assert "LANE_0_ROLLED_FORWARD_OR_EMPTY" not in contract["required_order"]
    tool = _read("tools/post_integration_durability.py")
    assert "ROOT_SYNC_PENDING" not in tool
    assert "INVALID_NON_BLOCKING" in tool
    assert "FINALIZE_DELIVERED_LANE_ZERO" in tool
    assert "/work/active" not in tool
    assert "/source/snapshots" not in tool
