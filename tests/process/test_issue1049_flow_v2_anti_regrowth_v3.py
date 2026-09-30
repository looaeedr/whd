from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FLOW = ".agents/skills/engineering/flow-v2-execution/SKILL.md"
ROOT_GATE_ID = "1qOMBtDwNGK5yxq_iyfISKYYDkBITXFuV"
ROOT_GATE_PATH = "/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json"
REMOTE_POLICY = "CONTROL_PLANE_OR_POST_PUSH_ONLY_REPOSITORY_CONTENT_REQUIRES_ROOT_WORKSPACE_HANDOFF"


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


def test_root_local_drive_canonical_projection_validates_and_hashes_to_pointer() -> None:
    from tools.root_local_first_gate import validate_contract

    mirror = _json(".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json")
    canonical = _canonical_payload_from_mirror(".agents/contracts/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1.json")
    validate_contract(canonical)
    for mode in ("SCHEDULER_LANE", "GITHUB_ONLY", "REMOTE_ACTION"):
        assert canonical["execution_modes"][mode] == REMOTE_POLICY
    source = mirror["canonical_source"]
    assert source["library_path"] == ROOT_GATE_PATH
    assert source["drive_file_id"] == ROOT_GATE_ID
    assert source["canonical_payload_sha256"] == hashlib.sha256(_canonical_bytes(canonical)).hexdigest()


def test_work_root_pointer_tracks_current_drive_canonical_hash_and_next_gate() -> None:
    mirror = _json(".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json")
    assert mirror["canonical_source"]["canonical_payload_sha256"] == "269cfb0d61363a902bcf551a63650be70cf832e0572fd5953cd68f48ef7a3ac0"
    assert mirror["required_sequence"][-2] == "ROOT_LOCAL_FIRST_GATE_READ"
    assert mirror["next_gate"]["drive_path"] == ROOT_GATE_PATH
    assert mirror["override_policy"]["allowed_only_when"][-2] == "execution_mode is GITHUB_ONLY or REMOTE_ACTION"

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


def _manifest(*, complete: bool) -> dict[str, object]:
    base: dict[str, object] = {
        "source_sha": "c" * 40,
        "tree_sha": "d" * 40,
        "root_local_gate_json_path": ROOT_GATE_PATH,
        "root_local_gate_json_file_id": ROOT_GATE_ID,
    }
    if complete:
        base.update({
            "durable_snapshot_base_sha": "c" * 40,
            "durable_snapshot_base_tree_sha": "d" * 40,
            "durable_snapshot_file_id": "drive-file",
            "durable_snapshot_name": "snapshot.zip",
            "durable_snapshot_status": "CURRENT_EXACT_HEAD",
            "export_writeback_status": "COMPLETE",
            "post_integration_export_run_id": 1,
            "post_integration_export_trigger_head_sha": "c" * 40,
            "post_integration_export_artifact_id": 2,
            "post_integration_export_artifact_digest": "sha256:" + "e" * 64,
            "durable_snapshot_sha256": "f" * 64,
            "durable_snapshot_readback": "VERIFIED",
        })
    return base


def test_repository_content_completion_blocks_after_done_until_durability_tail_complete() -> None:
    from tools.execution_invocation_exit import InvocationExitError, assert_repository_content_cycle_complete

    record = _done_record()
    with pytest.raises(InvocationExitError, match="POST_INTEGRATION_DURABILITY_PENDING:CONSUME_SOURCE_EXPORT"):
        assert_repository_content_cycle_complete(record, source_manifest=_manifest(complete=False), workspace_location="ACTIVE")
    with pytest.raises(InvocationExitError, match="POST_INTEGRATION_DURABILITY_PENDING:ARCHIVE_WORKSPACE_TO_DONE"):
        assert_repository_content_cycle_complete(record, source_manifest=_manifest(complete=True), workspace_location="ACTIVE")
    assert assert_repository_content_cycle_complete(record, source_manifest=_manifest(complete=True), workspace_location="DONE") is True


def test_post_integration_manifest_writeback_self_heals_root_gate_pointer() -> None:
    from tools.post_integration_durability import validate_completed_source_manifest
    manifest = _manifest(complete=True)
    assert validate_completed_source_manifest(manifest)["root_local_gate_json_file_id"] == ROOT_GATE_ID
    stale = dict(manifest, root_local_gate_json_path="/Google Drive/WHD/WHD_ROOT_LOCAL_FIRST_ENTRY_HARD_GATE_V1_v4.json", root_local_gate_json_file_id="1vjSwAJNNwcEKIHh4iXqYuuYXJ_1YkA9L")
    with pytest.raises(ValueError, match="root-local gate path is stale"):
        validate_completed_source_manifest(stale)


def test_control_plane_regression_owns_v3_guard() -> None:
    runner = _read("tools/control_plane_regression.py")
    workflow = _read(".github/workflows/whd-control-plane-regression.yml")
    rel = "tests/process/test_issue1049_flow_v2_anti_regrowth_v3.py"
    assert rel in runner
    assert rel in workflow


def test_connector_merge_has_post_integration_export_trigger() -> None:
    workflow = _read(".github/workflows/drive-source-snapshot-export.yml")
    assert "pull_request:" in workflow
    assert "types: [closed]" in workflow
    assert "github.event.pull_request.merged == true" in workflow
    assert "github.event.pull_request.merge_commit_sha" in workflow


def test_pr_transport_head_is_not_reinterpreted_as_export_source_identity() -> None:
    contract = _json(".agents/contracts/WHD_POST_INTEGRATION_DURABILITY_V1.json")
    assert contract["artifact_source_identity_policy"].startswith("TRUSTED_EXPORT_MANIFEST_SOURCE_SHA_PLUS_EXACT_ARTIFACT_NAME")
    tool = _read("tools/post_integration_durability.py")
    assert 'trigger_head_sha = _sha(run.get("head_sha"), "artifact head_sha")' in tool
    assert 'artifact head_sha mismatch' not in tool
    assert '"trigger_head_sha": trigger_head_sha' in tool
