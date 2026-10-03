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
    assert "PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST" in joined
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
    assert "PUSH_SCOPE_MUST_EQUAL_SELECTED_LANE_MANIFEST" in push
    assert ".unpushed" in push
