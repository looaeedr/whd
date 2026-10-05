from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_deterministic_migration_is_workspace_first():
    text = _read(".agents/skills/engineering/deterministic-repo-migration/SKILL.md")
    assert "WORKSPACE_DEFAULT" in text
    assert "SHARED_ZERO_FALLBACK" not in text
    assert "executor-local repo workspace" in text
    assert "HANDOFF_TO_ROOT_WORKSPACE_IMPLEMENTATION" not in text
    assert "delivery phase 只可由 `/推推 文檔|主體`" not in text
    assert "shared-0 gate：" not in text


def test_tracked_deletion_is_workspace_first():
    text = _read(".agents/skills/engineering/刪除/SKILL.md")
    section = text.split("## 4. Repository tracked path 的刪除", 1)[1].split(
        "## 5. ACTIVE_ZERO_PHYSICAL_CLEANUP_HARD_GATE_V1", 1
    )[0]
    assert "WORKSPACE_DEFAULT" in section
    assert "WORKSPACE_DELIVERY" in section
    assert "SHARED_ZERO_FALLBACK" not in section
    assert "Missing Drive mount" in section
    assert "先在 canonical `/Google Drive/WHD` root 確認 path" not in section
    assert "只有使用者下 `/推推 文檔|主體` 才開 GitHub delivery" not in section


def test_scheduler_current_sections_do_not_force_drive_or_shared_zero():
    text = _read("個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md")
    current = text.split("<!-- ISSUE808_SCHEDULER_REMOTE_ONLY_EXECUTION_V1 -->", 1)[1]
    assert "workspace-capable runtime" in current
    assert "WORKSPACE_DEFAULT" in current
    assert "SHARED_ZERO_FALLBACK" not in current
    assert "固定 HANDOFF 到 canonical `/Google Drive/WHD`" not in current
    assert "HANDOFF 到 canonical Google Drive root workspace" not in current


def test_required_pitfall_library_current_guidance_is_workspace_first():
    text = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    section80 = text.split("### 80. 長任務只在聊天或臨時工作樹記進度", 1)[1].split(
        "### 81.", 1
    )[0]
    section118 = text.split(
        "### 118. 2026-09-10 — 先改 target 再想起要隔離施工", 1
    )[1].split("## 2026-09-10 — Registry", 1)[0]
    assert "WORKSPACE_DEFAULT" in section80
    assert "SHARED_ZERO_FALLBACK" not in section80
    assert "repository-content authority 固定是 canonical `/Google Drive/WHD`" not in section80
    assert "WORKSPACE_DEFAULT" in section118
    assert "SHARED_ZERO_FALLBACK" not in section118
    assert "ROOT_SOURCE_CURRENT → UNPUSHED_LANE_CLASSIFIED" not in section118


def test_control_only_note_does_not_restore_shared_zero_as_normal_path():
    text = _read("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    marker = "- **普通工單不變**："
    i = text.index(marker)
    excerpt = text[i : i + 500]
    assert "WORKSPACE_DEFAULT" in excerpt
    assert "SHARED_ZERO_FALLBACK" not in excerpt
    assert "仍走 shared-0 → frozen manifest" not in excerpt
