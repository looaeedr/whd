
"""Exact-source and routing regressions for Skills / AI-library governance."""
from pathlib import Path

from tools.phase6_skill_preflight import required_skills_for, required_references_for

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_delete_tracked_baseline_is_github_localx_not_release_x():
    text = read(".agents/skills/engineering/刪除/SKILL.md")
    section = text.split("## 4. Repository tracked path 的刪除", 1)[1].split("## 5.", 1)[0]
    assert "GitHub `localX` 最新 exact HEAD" in section
    assert "完整 commit SHA" in section and "blob SHA" in section
    assert "TARGETED_NOT_RUN" in section
    assert "以 fresh `cleanup/2d-3d-sync` baseline" not in section


def test_bridge_current_routes_from_localx_not_formal_x_agents():
    text = read("個人AI檔案庫/第二層_專案與SOP/12_WHD_FoldDesignerBridgeOwnership規則.md")
    section = text.split("## Integration / future change contract", 1)[1].split("## Accepted lineage provenance", 1)[0]
    assert "GitHub `localX` 最新 exact HEAD 的 `AGENTS.md`" in section
    assert "tools/change_lane_gate.py" in section
    assert "施工分流依正式 X `AGENTS.md`" not in section
    assert "當次 `/推推`" in section


def test_writing_skill_baseline_can_be_verified_without_local_checkout():
    text = read(".agents/skills/engineering/寫技能/SKILL.md")
    section = text.split("## 4. 修改既有 Skill", 1)[1].split("## 5. RED", 1)[0]
    assert "GitHub `localX` 最新完整 commit SHA" in section
    assert "對應 blob SHA" in section
    assert "不得要求先取得本機 checkout" in section
    assert "TARGETED_NOT_RUN" in section


def test_python_source_and_routing_helper_follow_current_localx():
    skill = read(".agents/skills/engineering/Python測試實務/SKILL.md")
    helper = read("tools/phase6_skill_preflight.py")
    assert "GitHub `localX` 最新 exact HEAD" in skill
    assert "tools/quick_test.py" in skill
    assert "tools/change_test_profile.py::build_fast_feedback" in skill
    assert "WHD Product Regression" in skill
    assert "以 X `AGENTS.md`" not in helper
    assert "GitHub `localX` 同一 HEAD" in helper
    assert "不會授權讀寫、執行或發布" in helper


def test_reference_is_not_a_second_execution_authority():
    ref = read(".agents/skills/engineering/寫技能/references/preflight-keyword-boundary.md")
    library = read("個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md")
    assert "REFERENCE／非執行權威" in ref
    assert "不虛構本地結果" in ref
    assert "不得當今日執行入口" in library
    assert "不能當成今天可執行的測試入口" not in library


def test_skill_routes_do_not_capture_unrelated_source_only_work():
    for task in ("檢查 Bridge ownership 來源", "查詢 localX HEAD 分支資訊", "整理 GitHub 版本差異"):
        skills = set(required_skills_for(task=task))
        assert "刪除" not in skills, task
        assert "寫技能" not in skills, task
        assert "Python測試實務" not in skills, task


def test_skill_routes_still_trigger_on_explicit_intent():
    cases = (
        ("刪除已追蹤的測試檔", "刪除"),
        ("修改技能 SKILL.md", "寫技能"),
        ("pytest fixture isolation", "Python測試實務"),
    )
    for task, owner in cases:
        assert owner in required_skills_for(task=task), task
    assert "個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md" in required_references_for(task="pytest fixture isolation")


def test_code_review_uses_exact_localx_without_retired_remote_tokens():
    review = read(".agents/skills/engineering/code-review/SKILL.md")
    writing = read(".agents/skills/engineering/寫技能/SKILL.md")
    assert "WHD_GITHUB_LOCALX_REVIEW_SOURCE_V1" in review
    assert "GitHub `localX` 最新 exact HEAD" in review
    assert "已連線且可用" in review and "read-only" in review
    assert "不因欠缺另外一個 fixed-point 口令停工" in review
    assert "NO_REVIEW_DIFF" in review and "SOURCE_READ_PRECONDITION_FAILED" in review
    assert "SPEC_SOURCE_MISSING" in review
    assert "同一已核准 Issue／PR" in writing
    assert "可直接用已連線 GitHub read API" in writing
    assert "同一已核准 Issue／PR" in writing
    assert "同一 `WORKSPACE_DELIVERY` task" not in review
    assert "If they didn't specify one, ask for it." not in review
    assert "沒有 explicit remote authority 就保持離線" not in writing


def test_triage_source_and_retired_remote_tokens_are_not_current_gates():
    skill = read(".agents/skills/engineering/triage/SKILL.md")
    brief = read(".agents/skills/engineering/triage/AGENT-BRIEF.md")
    historical = read(".agents/skills/engineering/triage/OUT-OF-SCOPE.md")
    assert "WHD_LOCALX_TRIAGE_SOURCE_AND_SCOPE_V1" in skill
    assert "GitHub `localX` **最新 exact HEAD**" in skill
    assert "查核預設唯讀" in skill
    assert "同一已授權工單" in skill
    assert "TARGETED_NOT_RUN" in skill
    assert "建立 `USER_EXPLICIT_REMOTE` authority" not in skill
    assert "Wait for direction." not in skill
    assert "not a second CURRENT requirement" in brief
    assert "The original body and discussion are context: the agent brief is the contract." not in brief
    assert "WHD applicability: REFERENCE only." in historical
    assert "do not create this directory" in historical
    assert "only if this directory already exists" in skill


def test_merge_conflict_skill_reconciles_verified_localx_without_forced_resolution():
    skill = read(".agents/skills/engineering/resolving-merge-conflicts/SKILL.md")
    assert "GitHub `localX` **latest exact HEAD**" in skill
    assert "MERGE_CONFLICT_AUTHORITY_UNRESOLVED" in skill
    assert "expected_head_sha" in skill
    assert "TARGETED_NOT_RUN" in skill
    assert "trusted gate" in skill
    assert 'Always resolve; never `--abort`' not in skill
    assert "No unconditional" in skill


def test_release_packaging_skill_does_not_claim_generic_full_update_authority():
    release = read(".agents/skills/engineering/phase6-release-packaging/SKILL.md")
    assert "只有在明確**出包／release／packaging** 語意" in release
    assert "單獨 `FULL`、`UPDATE`" in release
    assert "tools/phase6_skill_preflight.py" in release


def test_deletion_transport_and_gui_performance_triggers_are_scope_bound():
    delete = read(".agents/skills/engineering/刪除/SKILL.md")
    git = read(".agents/skills/misc/git-remote-sync-fallback/SKILL.md")
    gui = read(".agents/skills/engineering/phase6-gui-performance-integrity/SKILL.md")
    assert "英文 `delete`／`remove` 路由須符合完整單字邊界" in delete
    assert "`undelete`、`removed`" in delete
    assert "單純閱讀 `GitHub Connector` 文件" in git
    assert "不得因通用關鍵字就進入傳輸備援" in git
    assert "`traceability`" in gui
    assert "`scheduler prompt`" in gui


def test_issue_closure_and_publish_skills_do_not_promote_mentions_into_authority():
    closure = read(".agents/skills/engineering/issue-closure-gate/SKILL.md")
    publish = read(".agents/skills/engineering/推推/SKILL.md")
    debug = read(".agents/skills/engineering/diagnosing-bugs/SKILL.md")

    assert "單純查 `Master issue` 進度" in closure
    assert "Registry 路由只是查找 Skill，不授予關閉權限" in closure
    assert "路由選中 ≠ 正式發布授權" in publish
    assert "不是當次肯定的發布指令" in publish
    assert "不得留言發布授權、建立正式 X PR" in publish
    assert "當次**肯定、明確地下達**" in publish
    assert "`bugfix` / `bug fix`" in debug
    assert "`Bugatti`" in debug


def test_current_local_executor_does_not_assume_negated_takeover_permission():
    local = read(".agents/skills/engineering/root-local-first/SKILL.md")
    dispatch = read(".agents/skills/engineering/派工/SKILL.md")
    parser = read("tools/interactive_command_no_stop_gate.py")
    router = read("tools/phase6_skill_preflight.py")
    assert "不要 `/接手`，改用 `/派工`" in local
    assert "不用 `/派工`，改用 `/debug`" in dispatch
    assert "without_negated_command_mentions" in parser
    assert "without_negated_command_mentions" in router


def test_publish_negative_alias_is_filtered_without_changing_publish_authority():
    publish = read(".agents/skills/engineering/推推/SKILL.md")
    parser = read("tools/interactive_command_no_stop_gate.py")
    assert "排除明確否定的 `/推推` 與不帶斜線的「推推」" in publish
    assert "即使 Registry 因其他上下文選中本 Skill" in publish
    assert "_NEGATABLE_COMMAND_PATTERN" in parser
    assert "never a substitute for explicit user authorization" in parser
