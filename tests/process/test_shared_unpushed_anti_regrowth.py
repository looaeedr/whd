from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CURRENT = [
    "AGENTS.md",
    ".agents/skills/engineering/root-local-first/SKILL.md",
    ".agents/skills/engineering/flow-v2-execution/SKILL.md",
    ".agents/skills/engineering/排程模擬/SKILL.md",
    ".agents/skills/engineering/寫技能/SKILL.md",
    ".agents/skills/engineering/deterministic-repo-migration/SKILL.md",
    ".agents/skills/engineering/diagnosing-bugs/SKILL.md",
    ".agents/contracts/WHD_WORK_ROOT_HARD_GATE_V2.json",
    ".agents/contracts/WHD_ROOT_SHARED_UNPUSHED_ENTRY_HARD_GATE_V1.json",
    ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json",
    ".agents/contracts/WHD_PATH_RESERVATION_V1.json",
    ".agents/skills/engineering/推推/SKILL.md",
    "個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md",
    "個人AI檔案庫/踩坑庫/root_local_first_entry_gate_pitfall.md",
    "個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md",
]

def test_current_entrypoints_do_not_restore_legacy_control_root_or_prewrite_reservation():
    joined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in CURRENT)
    forbidden = [
        "/Google Drive/WHD/work/active",
        "/Google Drive/WHD/source/manifests/WHD Current Source Manifest",
        "第一次 root/content write 前固定用 atomic",
        "同一 repository path 同時間只允許一個 authoritative writer",
        "ROOT_SOURCE_CURRENT → PATHS_RESERVED → ROOT_MUTATIONS_COMPLETE",
        "新 READY work 使用 atomic `ACQUIRE.effect.admission_reservation`",
        "READY → atomic ACQUIRE+reservation",
        "canonical `/Google Drive/WHD/work/active",
    ]
    for marker in forbidden:
        assert marker not in joined

def test_conflict_and_push_scope_hard_gates_are_current():
    joined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in CURRENT)
    assert "BLOCKED_USER_DECISION" in joined
    assert "EXPLICIT_USER_CONFLICT_DECISION" in joined
    assert "PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_LOCK" in joined
    assert ".unpushed/docs/0" in joined
    assert ".unpushed/body/0" in joined
    assert "DELIVERY_RESERVATION" in joined
    assert "GIT_WRITE_UNLOCKED" in joined


def test_delivery_reservation_is_never_a_root_prewrite_gate():
    import json
    payload = json.loads((ROOT / ".agents/contracts/WHD_PATH_RESERVATION_V1.json").read_text(encoding="utf-8"))
    assert payload["phase"] == "DELIVERY_ONLY_AFTER_LANE_MANIFEST_FROZEN"
    assert payload["reservation_required_before"] == "CREATE_DELIVERY_BRANCH_OR_GIT_WRITE"
    assert payload["root_authoring_policy"] == "SHARED_0_LINEAGE_NO_PREWRITE_RESERVATION"
    assert payload["workspace_policy"] == "SHARED_UNPUSHED_LANE_0"
    assert "FIRST_ROOT_OR_CONTENT_WRITE" not in json.dumps(payload, ensure_ascii=False)


def test_unpushed_workspace_is_never_git_delivery_content():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".unpushed/" in ignore
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    assert "PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_LOCK" in push
    assert ".unpushed" in push


def test_push_delivery_tail_requires_flow_v2_done_before_lane_cleanup():
    import json
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(encoding="utf-8"))
    ordered = [
        "MERGE_READBACK_VERIFIED",
        "DELIVERY_RECEIPT_BOUND",
        "SYNC_LINKED_GITHUB_ISSUES",
        "ISSUE_SYNC_READBACK_VERIFIED",
        "FLOW_V2_DONE",
        "LANE_DELIVERY_RECEIPT_BOUND",
        "FINALIZE_DELIVERED_LANE_ZERO",
        "DURABLE_CLEANUP_COMPLETE",
    ]
    positions = [push.index(marker) for marker in ordered]
    assert positions == sorted(positions)
    assert contract["post_delivery_tail"]["required_order"] == ordered
    assert contract["post_delivery_tail"]["lane_cleanup_requires_flow_v2_done"] is True
    assert contract["post_delivery_tail"]["execution_terminal_owner"] == "WHD_EXECUTION_RECORD_V2"


def test_push_root_sync_is_optional_maintenance_not_terminal_authority():
    import json
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(encoding="utf-8"))
    policy = contract["root_sync_policy"]
    assert "ROOT_SYNC_MAINTENANCE_NON_BLOCKING_V1" in push
    assert "不得因此保持 Issue OPEN" in push
    assert policy["mode"] == "OPTIONAL_MAINTENANCE"
    assert policy["terminal_gate"] is False
    assert policy["issue_closure_authority"] is False


def test_push_remote_deny_does_not_override_control_plane_authority():
    import json
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(encoding="utf-8"))
    scope = contract["remote_authority_scope"]
    assert "只約束 **interactive/default repository-content discovery / authoring / delivery**" in push
    assert "不得拿本節去撤銷 Flow v2、scheduler、trusted Preflight" in push
    assert scope["control_plane_authority"] == "OWN_CURRENT_CONTRACTS_NOT_OVERRIDDEN_BY_PUSH_SKILL"
    assert scope["control_plane_cannot_author_root_content"] is True


def test_workspace_staged_delivery_fallback_preserves_exact_lock():
    import json
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(encoding="utf-8"))
    fallback = contract["delivery_transport"]["workspace_staged_fallback"]
    assert "WORKSPACE_STAGED_GIT_DELIVERY_FALLBACK_V1" in push
    assert "WORKSPACE_STAGED_RELAY_DOES_NOT_CHANGE_DELIVERY_AUTHORITY_OR_FILESET" in push
    assert "bundle 只作 transport capsule / audit evidence" in push
    assert fallback["status"] == "CURRENT"
    assert fallback["workspace_authority"] is False
    assert fallback["requires_frozen_manifest"] is True
    assert fallback["requires_exact_hash_readback"] is True
    assert fallback["bundle_role"] == "TRANSPORT_CAPSULE_ONLY_NOT_REPOSITORY_CONTENT"
    assert fallback["git_tree_must_expand_to_exact_locked_paths"] is True
    assert fallback["invariant"] == "WORKSPACE_STAGED_RELAY_DOES_NOT_CHANGE_DELIVERY_AUTHORITY_OR_FILESET"

def test_codex_cloud_mount_invisibility_uses_workspace_bridge_not_blocker():
    import json

    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    root_skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(
        encoding="utf-8"
    )
    contract = json.loads(
        (ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(
            encoding="utf-8"
        )
    )
    fallback = contract["delivery_transport"]["workspace_staged_fallback"]
    bridge = fallback["codex_cloud_mount_bridge"]

    assert "CHATGPT_CLOUD_MOUNT_NOT_VISIBLE_TO_CODEX" in fallback["triggers"]
    assert "CHATGPT_CLOUD_MOUNT_NOT_VISIBLE_TO_CODEX" in push
    assert "CHATGPT_CLOUD_MOUNT_NOT_VISIBLE_TO_CODEX" in root_skill
    assert "CODEX_WORKSPACE_EXECUTION_NEVER_BECOMES_CANONICAL_AUTHORITY" in push
    assert bridge["classification_kind"] == "EXECUTION_SURFACE_TRANSPORT_MISMATCH"
    assert bridge["blocker"] is False
    assert bridge["local_machine_unavailable"] is False
    assert bridge["authority_loss"] is False
    assert bridge["codex_must_not_require_direct_canonical_mount"] is True
    assert bridge["stage_exact_paths_only"] is False
    assert bridge["mismatch_state"] == "CODEX_WORKSPACE_STAGE_IDENTITY_MISMATCH"
    assert bridge["mismatch_action"] == "RESTAGE_FROM_CANONICAL_AUTHORITY"
    assert bridge["invariant"] == "CODEX_WORKSPACE_EXECUTION_NEVER_BECOMES_CANONICAL_AUTHORITY"


def test_codex_workspace_bridge_requires_exact_stage_identity():
    import json

    contract = json.loads(
        (ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(
            encoding="utf-8"
        )
    )
    bridge = contract["delivery_transport"]["workspace_staged_fallback"][
        "codex_cloud_mount_bridge"
    ]
    assert bridge["required_stage_identity"] == [
        "canonical_path",
        "workspace_path",
        "size",
        "sha256",
        "source_generation_or_manifest_digest",
    ]

def test_codex_workspace_keeps_persistent_latest_mirror_without_becoming_authority():
    import json

    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    root_skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(
        encoding="utf-8"
    )
    contract = json.loads(
        (ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(
            encoding="utf-8"
        )
    )
    mirror = contract["delivery_transport"]["workspace_staged_fallback"][
        "codex_cloud_mount_bridge"
    ]["workspace_mirror_policy"]

    assert "CODEX_WORKSPACE_LATEST_MIRROR_V1" in push
    assert "CODEX_WORKSPACE_LATEST_MIRROR_V1" in root_skill
    assert "tools/workspace_canonical_sync.py" in push
    assert mirror["schema"] == "WHD_WORKSPACE_CANONICAL_SYNC_MANIFEST_V1"
    assert mirror["machine_owner"] == "tools/workspace_canonical_sync.py"
    assert "WHD_CODEX_WORKSPACE_LATEST_MIRROR_V1" in mirror["compatibility_aliases"]
    assert mirror["persistence"] == "RETAIN_ACROSS_INVOCATIONS"
    assert mirror["mirror_scope"] == "FULL_REPOSITORY_CACHE_ALLOWED"
    assert mirror["authority"] is False
    assert mirror["canonical_latest_owner"] == "/Google Drive/WHD"
    assert mirror["startup_reconcile_required"] is True
    assert mirror["sync_mode"] == "INCREMENTAL_CHANGED_PATHS"
    assert mirror["commands"] == ["sync-in", "status", "prepare-outbound", "verify-outbound"]
    assert mirror["required_schemas"] == [
        "WHD_WORKSPACE_CANONICAL_SYNC_MANIFEST_V1",
        "WHD_WORKSPACE_CANONICAL_MIRROR_RECEIPT_V1",
        "WHD_WORKSPACE_CANONICAL_OUTBOUND_RELAY_V1",
        "WHD_WORKSPACE_CANONICAL_OUTBOUND_RECEIPT_V1",
    ]
    assert mirror["preserve_dirty_work"] is True
    assert mirror["dirty_path_conflict_state"] == "WORKSPACE_CANONICAL_RECONCILE_REQUIRED"
    assert mirror["delivery_scope_still_locked"] is True
    assert mirror["terminal_cleanup"] == "KEEP_MIRROR_DROP_EPHEMERAL_RELAY_ONLY"
    assert mirror["invariant"] == "PERSISTENT_CODEX_WORKSPACE_MIRROR_IS_CACHE_NOT_AUTHORITY"
    assert mirror["shared_workspace_invariant"] == "WORKSPACE_CANONICAL_SYNC_OWNER_IS_SHARED_NOT_CODEX_ONLY"
