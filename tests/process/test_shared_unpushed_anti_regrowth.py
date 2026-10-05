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
    assert payload["phase"] == "DELIVERY_ONLY_AFTER_TESTED_DIFF_FROZEN"
    assert payload["reservation_required_before"] == "CREATE_DELIVERY_BRANCH_OR_GIT_WRITE"
    assert payload["root_authoring_policy"] == "NO_PREWRITE_RESERVATION__RESERVE_ONLY_FOR_GIT_DELIVERY"
    assert payload["workspace_policy"] == "EXECUTOR_LOCAL_WORKSPACE_DEFAULT__SHARED_ZERO_CONDITIONAL_FALLBACK"
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


def test_push_skill_is_shared_zero_fallback_and_does_not_override_control_plane():
    import json
    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads((ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(encoding="utf-8"))
    scope = contract["remote_authority_scope"]
    assert "普通 workspace-first 施工不經 `/推推`" in push
    assert "FRESH_SHARED_ZERO_DRIFT_ON_TOUCHED_PATHS" in push
    assert scope["control_plane_authority"] == "OWN_CURRENT_CONTRACTS_NOT_OVERRIDDEN_BY_PUSH_SKILL"
    assert scope["control_plane_cannot_author_root_content"] is True
    assert scope["interactive_repository_content"] == "WORKSPACE_BASELINE_READ_ALLOWED_OTHER_ACTIONS_REQUIRE_EXPLICIT_AUTHORITY"


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

def test_cloud_mount_invisibility_does_not_activate_sync_without_shared_zero_drift():
    import json

    push = (ROOT / ".agents/skills/engineering/推推/SKILL.md").read_text(encoding="utf-8")
    contract = json.loads(
        (ROOT / ".agents/contracts/WHD_SHARED_UNPUSHED_INTEGRATION_V1.json").read_text(
            encoding="utf-8"
        )
    )
    fallback = contract["delivery_transport"]["workspace_staged_fallback"]
    bridge = fallback["codex_cloud_mount_bridge"]

    assert "CHATGPT_CLOUD_MOUNT_NOT_VISIBLE_TO_CODEX" not in fallback["triggers"]
    assert "FRESH_SHARED_ZERO_DRIFT_ON_TOUCHED_PATHS" in fallback["triggers"]
    assert "不要求 Drive mount" in push
    assert bridge["classification_kind"] == "EXECUTION_SURFACE_TRANSPORT_MISMATCH"
    assert bridge["blocker"] is False
    assert bridge["activation_requires_shared_zero_drift"] is True
    assert bridge["stage_exact_paths_only"] is True


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

def test_workspace_canonical_sync_is_conditional_and_workspace_path_is_executor_local():
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

    assert "tools/workspace_canonical_sync.py" in push
    assert "普通 workspace startup **不要求**" in root_skill
    assert mirror["schema"] == "WHD_WORKSPACE_CANONICAL_SYNC_MANIFEST_V1"
    assert mirror["machine_owner"] == "tools/workspace_canonical_sync.py"
    assert mirror["activation"] == "SHARED_ZERO_FALLBACK_ONLY"
    assert mirror["ordinary_startup_required"] is False
    assert mirror["workspace_root_policy"] == "EXECUTOR_LOCAL_REPO_WORKSPACE"
    assert "workspace_root" not in mirror
    assert mirror["startup_reconcile_required"] is False
    assert mirror["persistence"] == "EXECUTOR_DEFINED"
    assert mirror["mirror_scope"] == "FALLBACK_RECONCILE_CACHE"
    assert mirror["authority"] is False
    assert mirror["dirty_path_conflict_state"] == "WORKSPACE_CANONICAL_RECONCILE_REQUIRED"
    assert mirror["invariant"] == "WORKSPACE_CANONICAL_SYNC_IS_CONDITIONAL_FALLBACK_NOT_DEFAULT_STARTUP"
    assert mirror["shared_workspace_invariant"] == "SYNC_MACHINE_IS_SHARED_BUT_WORKSPACE_PATH_IS_EXECUTOR_LOCAL"



def test_flow_v2_workspace_default_cannot_regrow_drive_root_only_handoff():
    flow = (ROOT / ".agents/skills/engineering/flow-v2-execution/SKILL.md").read_text(
        encoding="utf-8"
    )
    root_skill = (ROOT / ".agents/skills/engineering/root-local-first/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "WORKSPACE_EXECUTION_POLICY_V3 — EXECUTOR LOCAL WORKSPACE FIRST" in flow
    assert "REMOTE_CONTENT_IMPLEMENTATION_ROUTING_HARD_GATE_V3" in flow
    assert "CONTENT_MUTATION_TEST_HARD_GATE_V2" in flow
    assert "Google Drive mount 不可見本身不是 blocker" in flow
    assert "HANDOFF_TO_WORKSPACE_CAPABLE_RUNTIME_NO_UNTESTED_GITHUB_HOTFIX" in flow
    assert "HANDOFF_TO_SHARED_ZERO_CAPABLE_RUNTIME" in flow

    assert "互動式 / chat runtime 的 repository-content 工作面固定是 `/Google Drive/WHD` full repo root" not in flow
    assert "HANDOFF_TO_ROOT_CAPABLE_RUNTIME_NO_GITHUB_CONTENT_FALLBACK" not in flow
    assert "root content authoring 的 authority 是 shared-0 lineage" not in flow
    assert "普通施工工單仍走原本 shared-0 → delivery → QA/merge/finalize 流程" not in flow
    assert "fresh-read target `main`" not in flow

    assert "普通 workspace startup **不要求** Google Drive generation/manifest" in root_skill
    assert "shared_zero_drift_present=false → WORKSPACE_DEFAULT" in root_skill
